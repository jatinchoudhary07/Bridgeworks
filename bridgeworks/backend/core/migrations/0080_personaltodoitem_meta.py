from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0079_mydesknoteattachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='personaltodoitem',
            name='meta',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
