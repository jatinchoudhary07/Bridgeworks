from django.apps import AppConfig

class PresenceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'presence'

    def ready(self):
        import presence.signals  # noqa
        
        # Register recurring task after migrations have completed
        from django.db.models.signals import post_migrate
        post_migrate.connect(self._register_tasks, sender=self)

    @classmethod
    def _register_tasks(cls, sender, **kwargs):
        try:
            from django_q.models import Schedule
            Schedule.objects.get_or_create(
                func='presence.tasks.degrade_inactive_users',
                schedule_type='C',  # CRON schedule
                cron='*/5 * * * *',  # every 5 minutes
                name='degrade_inactive_users'
            )
        except Exception:
            pass
