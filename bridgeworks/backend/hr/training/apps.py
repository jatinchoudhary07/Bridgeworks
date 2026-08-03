from django.apps import AppConfig

class TrainingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hr.training'

    def ready(self):
        import hr.training.signals  # noqa
        
        # Register recurring task after migrations have completed
        from django.db.models.signals import post_migrate
        post_migrate.connect(self._register_tasks, sender=self)

    @classmethod
    def _register_tasks(cls, sender, **kwargs):
        try:
            from django_q.models import Schedule
            Schedule.objects.get_or_create(
                func='hr.training.tasks.check_training_expiry_and_compliance',
                schedule_type='D',  # Daily
                name='check_training_expiry_and_compliance'
            )
        except Exception:
            pass
