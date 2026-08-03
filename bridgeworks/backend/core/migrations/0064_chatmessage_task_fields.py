from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0063_chatmessage_is_broadcast'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='is_task',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='task_title',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='task_description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='task_due_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='task_status',
            field=models.CharField(blank=True, default='pending', max_length=20),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='task_source_message_id',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='task_assignee',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_chat_tasks', to=settings.AUTH_USER_MODEL),
        ),
    ]
