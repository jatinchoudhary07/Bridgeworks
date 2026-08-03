from decimal import Decimal

from django.db import migrations


def seed_default_ledgers_and_account(apps, schema_editor):
    Ledger = apps.get_model('accounting', 'Ledger')
    Account = apps.get_model('accounting', 'Account')

    default_ledgers = [
        ('Cash', 'asset'),
        ('Bank', 'asset'),
        ('Sales', 'income'),
        ('Expenses', 'expense'),
        ('Inventory', 'asset'),
    ]

    for name, ledger_type in default_ledgers:
        Ledger.objects.get_or_create(name=name, defaults={'type': ledger_type})

    Account.objects.get_or_create(
        name='Cash account',
        defaults={
            'type': 'cash',
            'balance': Decimal('0.00'),
        },
    )


def unseed_default_ledgers_and_account(apps, schema_editor):
    Ledger = apps.get_model('accounting', 'Ledger')
    Account = apps.get_model('accounting', 'Account')

    Ledger.objects.filter(name__in=['Cash', 'Bank', 'Sales', 'Expenses', 'Inventory']).delete()
    Account.objects.filter(name='Cash account').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_default_ledgers_and_account, unseed_default_ledgers_and_account),
    ]
