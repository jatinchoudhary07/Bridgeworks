from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        import core.signals  # ✅ Correct placement inside the class
        
        # Enable SQLite WAL mode for better concurrency
        # WAL allows readers while a writer is active (vs default that blocks everything)
        from django.db.backends.signals import connection_created
        connection_created.connect(self._enable_wal_mode)

        # Register recurring task after migrations have completed (safest way to avoid DB access warning)
        from django.db.models.signals import post_migrate
        post_migrate.connect(self._register_tasks, sender=self)

    @classmethod
    def _register_tasks(cls, sender, **kwargs):
        try:
            from django_q.models import Schedule
            Schedule.objects.get_or_create(
                func='core.tasks.auto_close_inactive_conversations',
                schedule_type='C',  # CRON schedule
                cron='*/30 * * * *',  # every 30 minutes
                name='auto_close_conversations'
            )
            Schedule.objects.get_or_create(
                func='core.tasks.fetch_meta_daily_metrics',
                schedule_type='C',  # CRON schedule
                cron='0 */6 * * *',  # every 6 hours
                name='fetch_meta_daily_metrics'
            )
            Schedule.objects.get_or_create(
                func='core.tasks.sync_weather_alerts_task',
                schedule_type='C',  # CRON schedule
                cron='0 */6 * * *',  # every 6 hours
                name='sync_weather_alerts'
            )
            # NDR: Classify unclassified NDR remarks via AI (every 15 minutes)
            Schedule.objects.get_or_create(
                func='core.tasks.ndr_tasks.batch_classify_remarks_task',
                schedule_type='C',
                cron='*/15 * * * *',  # every 15 minutes
                name='ndr_batch_classify_remarks'
            )
            # NDR: Recalculate RTO risk scores for all active NDR orders (daily at midnight)
            Schedule.objects.get_or_create(
                func='core.tasks.ndr_tasks.daily_ndr_risk_rescoring_task',
                schedule_type='C',
                cron='0 0 * * *',  # midnight every day
                name='ndr_daily_rto_rescoring'
            )
            # Timezone-aware midnight logout task (runs every 15 minutes)
            Schedule.objects.get_or_create(
                func='core.tasks.midnight_logout.midnight_logout_job',
                schedule_type='C',
                cron='*/15 * * * *',  # every 15 minutes
                name='midnight_logout_job'
            )
            # Sweep active sessions to close idle ones (runs every 5 minutes)
            Schedule.objects.get_or_create(
                func='core.tasks.midnight_logout.close_idle_sessions_job',
                schedule_type='C',
                cron='*/5 * * * *',  # every 5 minutes
                name='close_idle_sessions_job'
            )
            from core.models import ShopCredentials
            shop = ShopCredentials.objects.first()
            if shop:
                org_id = shop.organization_id
                default_name = f'morning_picklist_emails_default_{org_id}'
                if not Schedule.objects.filter(func='core.tasks.morning_picklist.send_morning_picklist_task').exists():
                    Schedule.objects.create(
                        func='core.tasks.morning_picklist.send_morning_picklist_task',
                        schedule_type='C',
                        cron='0 7 * * *',  # 07:00 AM IST (local timezone schedule)
                        name=default_name
                    )
        except Exception:
            pass

    @staticmethod
    def _enable_wal_mode(sender, connection, **kwargs):
        if connection.vendor == 'sqlite':
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA busy_timeout=30000;')  # 30s busy timeout
        elif connection.vendor == 'postgresql':
            cursor = connection.cursor()
            cursor.execute("SELECT set_config('app.bypass_rls', 'true', false);")
