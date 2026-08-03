from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0088_merge_20260330_1529'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='reminder_count',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
