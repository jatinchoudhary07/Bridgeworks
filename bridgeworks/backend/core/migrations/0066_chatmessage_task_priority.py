from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0065_repair_chatmessage_task_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='task_priority',
            field=models.CharField(blank=True, default='medium', max_length=20),
        ),
    ]
