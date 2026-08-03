from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0156_rto_engine_item_lineitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='rtoengineitem',
            name='write_off_reason',
            field=models.CharField(
                blank=True,
                choices=[('not_our_product', 'Not Our Product'), ('fraud', 'Fraud')],
                max_length=30,
                null=True,
            ),
        ),
    ]
