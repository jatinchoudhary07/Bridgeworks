from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0086_galleryitemshare'),
    ]

    operations = [
        migrations.AddField(
            model_name='expenseentry',
            name='transaction_type',
            field=models.CharField(choices=[('expense', 'Expense'), ('income', 'Income')], default='expense', max_length=20),
        ),
    ]
