from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from decimal import Decimal
import json
import csv
import io

from datetime import date
from accounting.models import (
    BankAccount, BankTransaction, BankStatementImport, Ledger, FinancialAccount, Account, AccountGroup,
    Expense
)

User = get_user_model()

class BankReconciliationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='password', is_staff=True, is_superuser=True)
        self.org_id = 'test-org'
        if hasattr(self.user, 'shop_credentials') and self.user.shop_credentials:
            self.user.shop_credentials.organization_id = self.org_id
            self.user.shop_credentials.save()
        else:
            from core.models.store import ShopCredentials
            ShopCredentials.objects.create(owner=self.user, organization_id=self.org_id)
        self.client.force_authenticate(user=self.user)
        
        # Create a ledger
        self.ledger = Ledger.objects.create(org_id=self.org_id, name='Test Bank Ledger', type='asset')

    def test_bank_account_field_sync(self):
        """Test that legacy name and new account_name sync properly."""
        # Case 1: create with name
        acc1 = BankAccount.objects.create(org_id=self.org_id, name='Primary HDFC', bank_name='HDFC', ledger=self.ledger)
        self.assertEqual(acc1.account_name, 'Primary HDFC')

        # Case 2: create with account_name
        acc2 = BankAccount.objects.create(org_id=self.org_id, account_name='Secondary ICICI', bank_name='ICICI')
        self.assertEqual(acc2.name, 'Secondary ICICI')

    def test_bank_transaction_field_sync(self):
        """Test date/transaction_date and debit/credit/amount/type sync."""
        acc = BankAccount.objects.create(org_id=self.org_id, name='Recon HDFC', bank_name='HDFC', ledger=self.ledger)

        # Debit transaction (money out)
        t1 = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=acc,
            transaction_date='2026-06-01',
            debit=Decimal('1500.00'),
            description='Test Debit Outflow'
        )
        self.assertEqual(t1.date, t1.transaction_date)
        self.assertEqual(t1.amount, Decimal('1500.00'))
        self.assertEqual(t1.type, 'debit')

        # Credit transaction (money in)
        t2 = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=acc,
            date='2026-06-02',
            credit=Decimal('5000.00'),
            description='Test Credit Inflow'
        )
        self.assertEqual(t2.transaction_date, t2.date)
        self.assertEqual(t2.amount, Decimal('5000.00'))
        self.assertEqual(t2.type, 'credit')

    def test_parse_headers_endpoint(self):
        """Test file parsing endpoint extracts headers and raw rows."""
        csv_content = "Date,Particulars,Cheque No.,Debit,Credit,Balance\n01/06/2026,Salary Transfer,,0.00,50000.00,50000.00\n02/06/2026,Office Rent,123456,15000.00,0.00,35000.00"
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'statement.csv'

        url = reverse('accounting-bank-import-parse-headers')
        response = self.client.post(url, {'file': csv_file, 'file_type': 'csv'}, format='multipart')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertIn('Date', response.data['data']['headers'])
        self.assertEqual(len(response.data['data']['preview_rows']), 2)

    def test_validate_statement_endpoint(self):
        """Test validation engine detects duplicate matches and failures."""
        acc = BankAccount.objects.create(org_id=self.org_id, name='Recon Account', bank_name='HDFC', ledger=self.ledger)

        # Create one existing transaction to trigger duplicate validation
        BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=acc,
            transaction_date='2026-06-02',
            debit=Decimal('15000.00'),
            description='Office Rent'
        )

        csv_content = "Date,Particulars,Cheque No.,Debit,Credit,Balance\n01/06/2026,Salary Transfer,,0.00,50000.00,50000.00\n02/06/2026,Office Rent,123456,15000.00,0.00,35000.00"
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = 'statement.csv'

        mapping = {
            'transaction_date': 'Date',
            'reference': 'Cheque No.',
            'description': 'Particulars',
            'debit': 'Debit',
            'credit': 'Credit',
            'balance': 'Balance'
        }

        url = reverse('accounting-bank-import-validate-statement')
        response = self.client.post(url, {
            'file': csv_file,
            'bank_account_id': acc.id,
            'column_mapping': json.dumps(mapping),
            'file_type': 'csv'
        }, format='multipart')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        metrics = response.data['data']['metrics']
        self.assertEqual(metrics['rows_imported'], 1)  # 1 row is new
        self.assertEqual(metrics['duplicate_rows'], 1)  # 1 row is duplicate


class AccountsCenterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser2', password='password', is_staff=True, is_superuser=True)
        self.org_id = 'test-org'
        if hasattr(self.user, 'shop_credentials') and self.user.shop_credentials:
            self.user.shop_credentials.organization_id = self.org_id
            self.user.shop_credentials.save()
        else:
            from core.models.store import ShopCredentials
            ShopCredentials.objects.create(owner=self.user, organization_id=self.org_id)
        self.client.force_authenticate(user=self.user)

    def test_financial_account_bank_sync(self):
        """Test that creating a bank FinancialAccount creates a BankAccount legacy record."""
        fa = FinancialAccount.objects.create(
            org_id=self.org_id,
            account_name='Central Savings HDFC',
            account_class=FinancialAccount.AccountClass.BANK,
            account_type='Savings',
            balance=Decimal('25000.00'),
            status='active'
        )
        # Check that legacy BankAccount got created
        self.assertTrue(BankAccount.objects.filter(financial_account=fa).exists())
        ba = BankAccount.objects.get(financial_account=fa)
        self.assertEqual(ba.account_name, 'Central Savings HDFC')
        self.assertEqual(ba.opening_balance, Decimal('25000.00'))

        # Test patch update from FinancialAccount propagates to BankAccount
        fa.account_name = 'Central Savings HDFC Updated'
        fa.balance = Decimal('30000.00')
        fa.save()
        ba.refresh_from_db()
        self.assertEqual(ba.account_name, 'Central Savings HDFC Updated')
        self.assertEqual(ba.opening_balance, Decimal('30000.00'))

    def test_financial_account_cash_sync(self):
        """Test that creating a cash FinancialAccount creates an Account legacy record."""
        fa = FinancialAccount.objects.create(
            org_id=self.org_id,
            account_name='Safe Cash Box',
            account_class=FinancialAccount.AccountClass.CASH,
            account_type='Cash',
            balance=Decimal('500.00'),
            status='active'
        )
        # Check that legacy Account got created
        self.assertTrue(Account.objects.filter(financial_account=fa).exists())
        acc = Account.objects.get(financial_account=fa)
        self.assertEqual(acc.name, 'Safe Cash Box')
        self.assertEqual(acc.type, Account.AccountType.CASH)
        self.assertEqual(acc.balance, Decimal('500.00'))

    def test_dashboard_api(self):
        """Test the accounts center dashboard aggregates KPIs correctly."""
        # Create bank account
        FinancialAccount.objects.create(
            org_id=self.org_id,
            account_name='Dash Bank',
            account_class=FinancialAccount.AccountClass.BANK,
            balance=Decimal('10000.00')
        )
        # Create cash account
        FinancialAccount.objects.create(
            org_id=self.org_id,
            account_name='Dash Cash',
            account_class=FinancialAccount.AccountClass.CASH,
            balance=Decimal('2000.00')
        )
        # Create wallet account
        FinancialAccount.objects.create(
            org_id=self.org_id,
            account_name='Dash Wallet',
            account_class=FinancialAccount.AccountClass.WALLET,
            balance=Decimal('1500.00')
        )

        url = reverse('accounting-accounts-center-dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        self.assertEqual(data['total_accounts'], 3)
        self.assertEqual(data['total_balance'], 13500.00)
        self.assertEqual(data['cash_in_hand'], 2000.00)
        self.assertEqual(data['wallet_balance'], 1500.00)
        self.assertEqual(data['available_funds'], 13500.00)

    def test_financial_account_all_classes_sync(self):
        """Test that all classes of FinancialAccount sync with the Account model."""
        # 1. Bank class
        fa_bank = FinancialAccount.objects.create(
            org_id=self.org_id,
            account_name='HDFC Bank Sync',
            account_class=FinancialAccount.AccountClass.BANK,
            account_type='Savings',
            balance=Decimal('1000.00'),
            status='active'
        )
        self.assertTrue(Account.objects.filter(financial_account=fa_bank).exists())
        acc_bank = Account.objects.get(financial_account=fa_bank)
        self.assertEqual(acc_bank.name, 'HDFC Bank Sync')
        self.assertEqual(acc_bank.type, Account.AccountType.BANK)

        # 2. Settlement class
        fa_settlement = FinancialAccount.objects.create(
            org_id=self.org_id,
            account_name='Stripe Settlement',
            account_class=FinancialAccount.AccountClass.SETTLEMENT,
            account_type='Settlement',
            balance=Decimal('2000.00'),
            status='active'
        )
        self.assertTrue(Account.objects.filter(financial_account=fa_settlement).exists())
        acc_settlement = Account.objects.get(financial_account=fa_settlement)
        self.assertEqual(acc_settlement.name, 'Stripe Settlement')
        self.assertEqual(acc_settlement.type, Account.AccountType.SETTLEMENT)

    def test_account_active_filtering_and_dashboard(self):
        """Test that only active accounts are returned in AccountListView and all active show on dashboard."""
        fa_active = FinancialAccount.objects.create(
            org_id=self.org_id,
            account_name='Active Account',
            account_class=FinancialAccount.AccountClass.CASH,
            account_type='Cash',
            balance=Decimal('100.00'),
            status='active'
        )
        fa_inactive = FinancialAccount.objects.create(
            org_id=self.org_id,
            account_name='Inactive Account',
            account_class=FinancialAccount.AccountClass.CASH,
            account_type='Cash',
            balance=Decimal('200.00'),
            status='archived'
        )

        # 1. Test account list view filtering
        url_list = reverse('accounting-accounts')
        response_list = self.client.get(url_list)
        self.assertEqual(response_list.status_code, 200)
        account_names = [a['name'] for a in response_list.data['data']]
        self.assertIn('Active Account', account_names)
        self.assertNotIn('Inactive Account', account_names)

        # 2. Test finance dashboard account breakdown returns active account
        url_dash = reverse('accounting-finance-dashboard')
        response_dash = self.client.get(url_dash)
        self.assertEqual(response_dash.status_code, 200)
        breakdown = response_dash.data['data']['account_breakdown']
        breakdown_names = [a['account_name'] for a in breakdown]
        self.assertIn('Active Account', breakdown_names)
        self.assertNotIn('Inactive Account', breakdown_names)


class ReconciliationEngineTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='reconuser', password='password', is_staff=True, is_superuser=True)
        self.org_id = 'test-org'
        if hasattr(self.user, 'shop_credentials') and self.user.shop_credentials:
            self.user.shop_credentials.organization_id = self.org_id
            self.user.shop_credentials.save()
        else:
            from core.models.store import ShopCredentials
            ShopCredentials.objects.create(owner=self.user, organization_id=self.org_id)
        self.client.force_authenticate(user=self.user)

        # Create bank account and ledger
        self.bank_ledger = Ledger.objects.create(org_id=self.org_id, name='Bank Ledger', type='asset')
        self.bank_acc = BankAccount.objects.create(
            org_id=self.org_id,
            name='HDFC Recon Bank',
            bank_name='HDFC',
            ledger=self.bank_ledger
        )

        # Auto-seed rules
        from accounting.models import ReconciliationRule
        # Make sure rules are loaded by calling rules API or seeding
        url = reverse('accounting-reconciliation-rules')
        self.client.get(url)

    def test_exact_ref_number_match(self):
        """Test exact reference number match (Confidence 100)."""
        from accounting.models import BankTransaction, JournalEntry, JournalItem, ReconciliationMatch

        # Create ledger journal item (Debit of 500)
        je = JournalEntry.objects.create(org_id=self.org_id, date='2026-06-01', description='Invoice Receipt')
        ji = JournalItem.objects.create(
            org_id=self.org_id,
            entry=je,
            ledger=self.bank_ledger,
            debit=Decimal('500.00'),
            ref_id='REF12345'
        )

        # Create bank transaction credit (inflow) matching the debit
        tx = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date='2026-06-01',
            credit=Decimal('500.00'),
            reference='REF12345',
            description='Customer Payment',
            status='unprocessed'
        )

        # Run auto-match
        url = reverse('accounting-reconciliation-auto-match')
        response = self.client.post(url, {'bank_account': self.bank_acc.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['auto_matched'], 1)

        # Verify suggested match
        match = ReconciliationMatch.objects.get(bank_transaction=tx)
        self.assertEqual(match.journal_item, ji)
        self.assertEqual(match.confidence_score, 100)
        self.assertEqual(match.status, 'suggested')

    def test_amount_date_tolerance_match(self):
        """Test amount + date tolerance within 2 days (Confidence 95)."""
        from accounting.models import BankTransaction, JournalEntry, JournalItem, ReconciliationMatch

        # Create ledger journal item (Debit of 1000) on 2026-06-03
        je = JournalEntry.objects.create(org_id=self.org_id, date='2026-06-03', description='Payment')
        ji = JournalItem.objects.create(
            org_id=self.org_id,
            entry=je,
            ledger=self.bank_ledger,
            debit=Decimal('1000.00')
        )

        # Create bank transaction credit (inflow) on 2026-06-05 (2 days diff)
        tx = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date='2026-06-05',
            credit=Decimal('1000.00'),
            description='Random Payment',
            status='unprocessed'
        )

        url = reverse('accounting-reconciliation-auto-match')
        response = self.client.post(url, {'bank_account': self.bank_acc.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['auto_matched'], 1)

        match = ReconciliationMatch.objects.get(bank_transaction=tx)
        self.assertEqual(match.journal_item, ji)
        self.assertEqual(match.confidence_score, 95)

    def test_amount_description_match(self):
        """Test amount + description similarity (Confidence 90)."""
        from accounting.models import BankTransaction, JournalEntry, JournalItem, ReconciliationMatch

        # Create ledger journal item (Credit of 150 - money out)
        je = JournalEntry.objects.create(org_id=self.org_id, date='2026-06-01', description='Vendor Payment to ABC Corp')
        ji = JournalItem.objects.create(
            org_id=self.org_id,
            entry=je,
            ledger=self.bank_ledger,
            credit=Decimal('150.00')
        )

        # Create bank transaction debit (outflow) with similar description
        tx = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date='2026-06-10',  # Date diff > 2, so Rule 2 won't match
            debit=Decimal('150.00'),
            description='ABC Corp',
            status='unprocessed'
        )

        url = reverse('accounting-reconciliation-auto-match')
        response = self.client.post(url, {'bank_account': self.bank_acc.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['auto_matched'], 1)

        match = ReconciliationMatch.objects.get(bank_transaction=tx)
        self.assertEqual(match.journal_item, ji)
        self.assertEqual(match.confidence_score, 90)

    def test_amount_only_match(self):
        """Test amount only match (Confidence 70)."""
        from accounting.models import BankTransaction, JournalEntry, JournalItem, ReconciliationMatch

        # Create ledger journal item
        je = JournalEntry.objects.create(org_id=self.org_id, date='2026-06-01', description='Some random entry')
        ji = JournalItem.objects.create(
            org_id=self.org_id,
            entry=je,
            ledger=self.bank_ledger,
            debit=Decimal('777.00')
        )

        # Create bank transaction with date diff > 2 and completely different description
        tx = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date='2026-06-15',
            credit=Decimal('777.00'),
            description='XYZ Ltd',
            status='unprocessed'
        )

        url = reverse('accounting-reconciliation-auto-match')
        response = self.client.post(url, {'bank_account': self.bank_acc.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['auto_matched'], 1)

        match = ReconciliationMatch.objects.get(bank_transaction=tx)
        self.assertEqual(match.journal_item, ji)
        self.assertEqual(match.confidence_score, 70)

    def test_multiple_matches_exception(self):
        """Test multiple matches generate exception instead of automatic match."""
        from accounting.models import BankTransaction, JournalEntry, JournalItem, ReconciliationMatch, ReconciliationException

        # Create two ledger items of same amount
        je1 = JournalEntry.objects.create(org_id=self.org_id, date='2026-06-01', description='Entry 1')
        ji1 = JournalItem.objects.create(org_id=self.org_id, entry=je1, ledger=self.bank_ledger, debit=Decimal('200.00'))

        je2 = JournalEntry.objects.create(org_id=self.org_id, date='2026-06-01', description='Entry 2')
        ji2 = JournalItem.objects.create(org_id=self.org_id, entry=je2, ledger=self.bank_ledger, debit=Decimal('200.00'))

        # Bank transaction
        tx = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date='2026-06-01',
            credit=Decimal('200.00'),
            description='Duplicate Ref Test',
            status='unprocessed'
        )

        url = reverse('accounting-reconciliation-auto-match')
        response = self.client.post(url, {'bank_account': self.bank_acc.id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['auto_matched'], 0)
        self.assertEqual(response.data['data']['review_required'], 1)

        # Verify exception is created
        self.assertTrue(ReconciliationException.objects.filter(bank_transaction=tx, exception_type='multiple_matches').exists())
        self.assertFalse(ReconciliationMatch.objects.filter(bank_transaction=tx).exists())

    def test_match_approval_and_reconciliation(self):
        """Test approving suggested match and verifying journal entry sync."""
        from accounting.models import BankTransaction, JournalEntry, JournalItem, ReconciliationMatch

        je = JournalEntry.objects.create(org_id=self.org_id, date='2026-06-01', description='Approved Item')
        ji = JournalItem.objects.create(org_id=self.org_id, entry=je, ledger=self.bank_ledger, debit=Decimal('350.00'))

        tx = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date='2026-06-01',
            credit=Decimal('350.00'),
            status='unprocessed'
        )

        # Run match to create suggestion
        self.client.post(reverse('accounting-reconciliation-auto-match'), {'bank_account': self.bank_acc.id})
        match = ReconciliationMatch.objects.get(bank_transaction=tx, status='suggested')

        # Approve match
        url = reverse('accounting-reconciliation-matches')
        response = self.client.post(url, {'action': 'approve', 'match_id': match.id})
        self.assertEqual(response.status_code, 200)

        # Refresh
        tx.refresh_from_db()
        match.refresh_from_db()
        self.assertEqual(tx.status, 'processed')
        self.assertEqual(tx.journal_entry, je)
        self.assertEqual(match.status, 'approved')

    def test_duplicate_detection_flow(self):
        from accounting.models import BankTransaction, DuplicateCandidate, ReconciliationException
        import datetime
        
        # Create two duplicate transactions
        tx1 = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date=datetime.date(2026, 6, 1),
            credit=Decimal('5000.00'),
            description='Test Duplicate Transfer A',
            status='unprocessed'
        )
        tx2 = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date=datetime.date(2026, 6, 1),
            credit=Decimal('5000.00'),
            description='Test Duplicate Transfer B',
            status='unprocessed'
        )
        
        # Refresh to ensure fields are populated correctly from DB
        tx1.refresh_from_db()
        tx2.refresh_from_db()
        
        from accounting.views import scan_duplicates_and_risks
        scan_duplicates_and_risks(self.org_id, [tx1, tx2])
        
        self.assertTrue(DuplicateCandidate.objects.filter(org_id=self.org_id, transaction_1=tx1, transaction_2=tx2).exists() or 
                        DuplicateCandidate.objects.filter(org_id=self.org_id, transaction_1=tx2, transaction_2=tx1).exists())
        
        self.assertTrue(ReconciliationException.objects.filter(org_id=self.org_id, bank_transaction=tx1, exception_type='duplicate_candidate').exists())
        self.assertTrue(ReconciliationException.objects.filter(org_id=self.org_id, bank_transaction=tx2, exception_type='duplicate_candidate').exists())

    def test_risk_monitoring_alerts(self):
        from accounting.models import BankTransaction, RiskAlert
        import datetime
        
        tx_weekend = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date=datetime.date(2026, 6, 7),  # Sunday
            credit=Decimal('150.00'),
            description='Weekend Payment',
            status='unprocessed'
        )
        
        tx_round = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date=datetime.date(2026, 6, 1),
            credit=Decimal('10000.00'),
            description='Consulting Fee',
            status='unprocessed'
        )
        
        tx_suspicious = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date=datetime.date(2026, 6, 1),
            credit=Decimal('250.00'),
            description='Urgent Cash Withdrawal',
            status='unprocessed'
        )
        
        tx_weekend.refresh_from_db()
        tx_round.refresh_from_db()
        tx_suspicious.refresh_from_db()
        
        from accounting.views import scan_duplicates_and_risks
        scan_duplicates_and_risks(self.org_id, [tx_weekend, tx_round, tx_suspicious])
        
        self.assertTrue(RiskAlert.objects.filter(org_id=self.org_id, bank_transaction=tx_weekend, risk_type='weekend_transaction').exists())
        self.assertTrue(RiskAlert.objects.filter(org_id=self.org_id, bank_transaction=tx_round, risk_type='round_number').exists())
        self.assertTrue(RiskAlert.objects.filter(org_id=self.org_id, bank_transaction=tx_suspicious, risk_type='suspicious_description').exists())

    def test_audit_logger_flow(self):
        from accounting.models import ReconciliationAuditLog
        from accounting.views import log_reconciliation_audit
        
        log_reconciliation_audit(
            org_id=self.org_id,
            user=None,
            action='Test Action',
            entity_type='test',
            entity_id='123',
            notes='Test notes'
        )
        
        self.assertTrue(ReconciliationAuditLog.objects.filter(org_id=self.org_id, action='Test Action', entity_id='123').exists())

    def test_exception_assignment(self):
        from accounting.models import BankTransaction, ReconciliationException
        from django.contrib.auth.models import User
        
        tx = BankTransaction.objects.create(
            org_id=self.org_id,
            bank_account=self.bank_acc,
            date='2026-06-01',
            credit=Decimal('350.00'),
            status='unprocessed'
        )
        ex = ReconciliationException.objects.create(
            org_id=self.org_id,
            bank_transaction=tx,
            exception_type='no_match',
            status='open',
            severity='low'
        )
        
        user = User.objects.create_user(username='test_reviewer', password='password123')
        
        url = reverse('accounting-reconciliation-exceptions')
        self.client.force_login(user)
        response = self.client.post(url, {
            'action': 'assign',
            'exception_id': ex.id,
            'assigned_to_id': user.id
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        ex.refresh_from_db()
        self.assertEqual(ex.assigned_to, user)
        self.assertEqual(ex.status, 'in_review')


class AssetCatchupDepreciationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username='assetuser', password='password', is_staff=True, is_superuser=True)
        # Fetch the org_id automatically created by default founder setup signals
        if hasattr(self.user, 'shop_credentials') and self.user.shop_credentials:
            self.org_id = self.user.shop_credentials.organization_id
        else:
            self.org_id = 'org-1'
            from core.models.store import ShopCredentials
            ShopCredentials.objects.create(owner=self.user, organization_id=self.org_id)
        self.client.force_authenticate(user=self.user)

    def test_depreciation_catchup(self):
        from accounting.models import Asset, AssetDepreciation
        import datetime
        from decimal import Decimal

        # Create asset purchased in Jan 2023
        asset = Asset.objects.create(
            org_id=self.org_id,
            name='Test Bike 2023',
            category='vehicle',
            purchase_date=datetime.date(2023, 1, 15),
            purchase_cost=Decimal('120000.00'),
            salvage_value=Decimal('0.00'),
            useful_life_years=5,
            depreciation_method='slm',
            depreciation_rate=Decimal('20.00'),
            current_value=Decimal('120000.00'),
            status='active'
        )

        # Post to run-depreciation for March 2023
        url = reverse('accounting-assets-run-depreciation')
        response = self.client.post(url, {
            'month': 3,
            'year': 2023
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])

        # Verify that 3 periods were depreciated (Jan, Feb, Mar 2023)
        deprs = AssetDepreciation.objects.filter(asset=asset).order_by('period_year', 'period_month')
        self.assertEqual(deprs.count(), 3)
        
        # Monthly depreciation: 120,000 / 60 months = 2,000
        for dep in deprs:
            self.assertEqual(dep.depreciation_amount, Decimal('2000.00'))

        asset.refresh_from_db()
        # End value should be 120,000 - 6,000 = 114,000
        self.assertEqual(asset.current_value, Decimal('114000.00'))
        self.assertEqual(asset.accumulated_depreciation, Decimal('6000.00'))
        self.assertEqual(asset.last_depreciation_date, datetime.date(2023, 3, 1))








