from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0081_personaltodoitem_attachment'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalTodoAttachment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='mydesk/todos/')),
                ('original_name', models.CharField(blank=True, default='', max_length=255)),
                ('mime_type', models.CharField(blank=True, default='', max_length=120)),
                ('file_size', models.PositiveBigIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('todo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_attachments', to='core.personaltodoitem')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
