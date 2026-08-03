from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0084_leaverequest_requested_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='diaryentry',
            name='entry_date',
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
        migrations.AddField(
            model_name='diaryentry',
            name='entry_type',
            field=models.CharField(choices=[('work', 'Work'), ('meeting', 'Meeting'), ('learning', 'Learning'), ('review', 'Review'), ('issue', 'Issue')], default='work', max_length=20),
        ),
        migrations.AddField(
            model_name='diaryentry',
            name='hours',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        
        migrations.AddField(
            model_name='diaryentry',
            name='tags',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
