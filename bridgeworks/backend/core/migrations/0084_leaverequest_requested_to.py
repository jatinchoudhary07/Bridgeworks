from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0083_expenseshare'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='requested_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='mydesk_leave_inbox', to=settings.AUTH_USER_MODEL),
        ),
    ]
