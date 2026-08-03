from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0119_remove_diaryentry_mood'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # New model: per-employee Attendance Rulebook
        migrations.CreateModel(
            name='AttendanceRulebook',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('org_id', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='attendance_rulebook',
                    to=settings.AUTH_USER_MODEL,
                )),
                # Shift
                ('shift_start', models.TimeField(default='09:30:00')),
                ('shift_end', models.TimeField(default='18:30:00')),
                ('lunch_duration_minutes', models.PositiveIntegerField(default=30)),
                # Grace / Thresholds (in minutes)
                ('grace_period_minutes', models.PositiveIntegerField(default=14)),
                ('late_deduction_threshold_minutes', models.PositiveIntegerField(default=15)),
                ('half_day_late_threshold_minutes', models.PositiveIntegerField(default=40)),
                ('early_leave_deduction_minutes', models.PositiveIntegerField(default=10)),
                ('half_day_early_leave_minutes', models.PositiveIntegerField(default=40)),
                # Regularization
                ('regularization_limit_per_month', models.PositiveIntegerField(default=3)),
                # Employee type
                ('employee_type', models.CharField(
                    choices=[('office', 'Office'), ('labour', 'Labour'), ('field', 'Field')],
                    default='office', max_length=20,
                )),
                # Weekly off / Saturday
                ('weekly_off', models.CharField(
                    choices=[
                        ('sunday', 'Sunday'), ('saturday', 'Saturday'), ('none', 'None'),
                    ],
                    default='sunday', max_length=20,
                )),
                ('saturday_working', models.CharField(
                    choices=[('yes', 'Yes'), ('no', 'No'), ('alternate', 'Alternate')],
                    default='yes', max_length=20,
                )),
                # Audit
                ('last_edited_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='rulebook_edits',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'app_label': 'core',
                'ordering': ['user_id'],
            },
        ),

        # AttendanceEntry: add auto-status engine fields
        migrations.AddField(
            model_name='attendanceentry',
            name='auto_status',
            field=models.CharField(
                blank=True, default='',
                help_text='System-computed status before HR override',
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name='attendanceentry',
            name='hr_override_status',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        migrations.AddField(
            model_name='attendanceentry',
            name='hr_override_reason',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='attendanceentry',
            name='hr_override_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='attendance_overrides',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='attendanceentry',
            name='hr_override_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Deduction tracking (in fractional days: 0, 0.5, 1.0)
        migrations.AddField(
            model_name='attendanceentry',
            name='salary_deduction_days',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=4),
        ),
        # Attendance score per entry (0-100 pts contribution)
        migrations.AddField(
            model_name='attendanceentry',
            name='attendance_score_points',
            field=models.PositiveSmallIntegerField(default=100),
        ),
        # Shift lock: locked after 10 PM same day
        migrations.AddField(
            model_name='attendanceentry',
            name='is_locked',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='attendanceentry',
            name='locked_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Sunday paid/unpaid flag
        migrations.AddField(
            model_name='attendanceentry',
            name='is_paid_off',
            field=models.BooleanField(default=True),
        ),
        # Comp-off tracking
        migrations.AddField(
            model_name='attendanceentry',
            name='comp_off_claimed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='attendanceentry',
            name='comp_off_approved',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='attendanceentry',
            name='comp_off_expires_on',
            field=models.DateField(blank=True, null=True),
        ),
        # Early leave minutes (mirror of late_minutes for departure)
        migrations.AddField(
            model_name='attendanceentry',
            name='early_leave_minutes',
            field=models.PositiveIntegerField(default=0),
        ),
    ]
