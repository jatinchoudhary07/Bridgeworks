from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0075_add_chatmessage_feed_indexes'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='chatmessagerecipient',
            name='chatmsgrecip_recipient_read_idx',
        ),
        migrations.RemoveIndex(
            model_name='chatmessagerecipient',
            name='chatmsgrecip_recipient_archived_idx',
        ),
        migrations.RemoveIndex(
            model_name='chatmessagerecipient',
            name='chatmsgrecip_recipient_id_idx',
        ),
        migrations.AddIndex(
            model_name='chatmessagerecipient',
            index=models.Index(
                fields=['recipient', 'is_read'],
                name='chatmsgrecip_rcpt_read_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='chatmessagerecipient',
            index=models.Index(
                fields=['recipient', 'is_archived'],
                name='chatmsgrecip_rcpt_arch_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='chatmessagerecipient',
            index=models.Index(
                fields=['recipient'],
                name='chatmsgrecip_rcpt_idx',
            ),
        ),
    ]
