# Generated manually

from django.db import migrations

def sync_existing_accounts(apps, schema_editor):
    FinancialAccount = apps.get_model('accounting', 'FinancialAccount')
    Account = apps.get_model('accounting', 'Account')
    
    for fa in FinancialAccount.objects.filter(status='active'):
        # Determine account type mapping
        if fa.account_class == 'bank':
            acc_type = 'bank'
        elif fa.account_class == 'cash':
            acc_type = 'cash'
        elif fa.account_class == 'wallet':
            acc_type = 'wallet'
        elif fa.account_class == 'settlement':
            acc_type = 'settlement'
        else:
            acc_type = 'wallet'
            
        acc, created = Account.objects.get_or_create(
            financial_account=fa,
            defaults={
                'org_id': fa.org_id,
                'name': fa.account_name,
                'type': acc_type,
                'balance': fa.balance,
            }
        )
        if not created:
            acc.name = fa.account_name
            acc.type = acc_type
            acc.balance = fa.balance
            acc.save()

class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0020_reconciliationexception_assigned_to_and_more'),
    ]

    operations = [
        migrations.RunPython(sync_existing_accounts),
    ]
