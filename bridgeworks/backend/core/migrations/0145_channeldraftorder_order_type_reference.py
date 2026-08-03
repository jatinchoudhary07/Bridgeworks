from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0144_alter_channeldraftorder_customer_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='channeldraftorder',
            name='order_type',
            field=models.CharField(
                choices=[
                    ('new', 'New'),
                    ('exchange', 'Exchange'),
                    ('reship', 'Reship'),
                    ('duplicate', 'Duplicate'),
                ],
                default='new',
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='channeldraftorder',
            name='reference_order_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='channeldraftorder',
            name='tags',
            field=models.CharField(blank=True, max_length=500),
        ),
    ]
