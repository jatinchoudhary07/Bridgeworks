from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0080_personaltodoitem_meta'),
    ]

    operations = [
        migrations.AddField(
            model_name='personaltodoitem',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to='mydesk/todos/'),
        ),
    ]
