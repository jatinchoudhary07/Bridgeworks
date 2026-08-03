from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0066_chatmessage_task_priority'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='chat_attachments/'),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='attachment_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='attachment_mime_type',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='chatmessage',
            name='attachment_kind',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
