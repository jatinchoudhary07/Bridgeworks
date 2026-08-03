from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0116_merge_20260418_1050'),
    ]

    operations = [
        migrations.CreateModel(
            name='HrMeetingManagerCompanyEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('org_id', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('title', models.CharField(blank=True, default='', max_length=255)),
                ('event_type', models.CharField(choices=[('birthday', 'Birthday'), ('high_pressure', 'High Pressure Day'), ('holiday', 'Holiday'), ('event', 'Event'), ('big_sale', 'Big Sale'), ('annual_event', 'Annual Event')], default='event', max_length=32)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField(blank=True, null=True)),
                ('description', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hr_meeting_manager_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'app_label': 'core',
                'ordering': ['-start_date', '-created_at'],
            },
        ),
    ]
