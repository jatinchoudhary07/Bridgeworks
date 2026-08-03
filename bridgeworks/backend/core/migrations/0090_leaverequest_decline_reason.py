from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0089_leaverequest_reminder_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='decline_reason',
            field=models.TextField(blank=True, default=''),
        ),
    ]
