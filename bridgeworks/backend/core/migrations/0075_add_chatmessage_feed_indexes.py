from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0074_add_indexes_to_chatmessagerecipient'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(
                fields=['sender', 'created_at'],
                name='chatmsg_sender_created_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(
                fields=['is_broadcast', 'created_at'],
                name='chatmsg_broadcast_created_idx',
            ),
        ),
    ]
