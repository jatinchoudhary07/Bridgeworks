# Generated migration for adding indexes to ChatMessageRecipient

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0073_diaryentry_diaryattachment'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='chatmessagerecipient',
            index=models.Index(
                fields=['recipient_id', 'is_read'],
                name='chatmsgrecip_recipient_read_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='chatmessagerecipient',
            index=models.Index(
                fields=['recipient_id', 'is_archived'],
                name='chatmsgrecip_recipient_archived_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='chatmessagerecipient',
            index=models.Index(
                fields=['recipient_id'],
                name='chatmsgrecip_recipient_id_idx',
            ),
        ),
    ]
