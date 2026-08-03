from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hiring', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='google_form_url',
            field=models.URLField(blank=True, default='', max_length=1000),
        ),
    ]
