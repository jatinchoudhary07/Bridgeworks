import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("action", models.CharField(max_length=128)),
                ("component", models.CharField(blank=True, default="", max_length=256)),
                ("page", models.CharField(blank=True, default="", max_length=512)),
                ("session_id", models.CharField(blank=True, default="", max_length=128)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_sensitive", models.BooleanField(default=False)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("method", models.CharField(blank=True, default="", max_length=10)),
                ("status_code", models.SmallIntegerField(blank=True, null=True)),
                ("duration_ms", models.IntegerField(blank=True, null=True)),
                ("timestamp", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-timestamp"],
            },
        ),
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["user", "timestamp"], name="actlog_user_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["action", "timestamp"], name="actlog_action_ts_idx"),
        ),
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["session_id"], name="actlog_session_idx"),
        ),
        # Standalone index on timestamp for date-range-only queries
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["timestamp"], name="actlog_ts_idx"),
        ),
    ]
