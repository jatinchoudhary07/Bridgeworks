from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0062_google_calendar_auth'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='is_broadcast',
            field=models.BooleanField(default=False),
        ),
    ]
