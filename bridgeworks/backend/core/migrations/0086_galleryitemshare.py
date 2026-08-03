from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0085_diaryentry_logbook_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='GalleryItemShare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('org_id', models.CharField(blank=True, db_index=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='core.galleryitem')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mydesk_gallery_shares', to=settings.AUTH_USER_MODEL)),
                ('sent_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mydesk_gallery_sent_shares', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('item', 'recipient')},
            },
        ),
    ]
