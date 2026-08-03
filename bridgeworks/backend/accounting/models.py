from django.db import models
import hashlib



class Ledger(models.Model):
    class LedgerType(models.TextChoices):
        ASSET = 'asset', 'Asset'
        LIABILITY = 'liability', 'Liability'
        INCOME = 'income', 'Income'
        EXPENSE = 'expense', 'Expense'

    name = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=LedgerType.choices)
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')

    class Meta:
        ordering = ['name']
        unique_together = [['org_id', 'name']]

    def __str__(self):
        return f'{self.name} ({self.type})'


class JournalEntry(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    date = models.DateField()
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    import_hash = models.CharField(max_length=64, blank=True, null=True, unique=True, db_index=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'JournalEntry #{self.pk} - {self.date}'


class JournalItem(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='items')
    ledger = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name='journal_items')
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # Detailed fields from the comprehensive form
    department = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    vendor_payee = models.CharField(max_length=150, blank=True, null=True)
    bill_date = models.DateField(blank=True, null=True)
    ref_id = models.CharField(max_length=100, blank=True, null=True)
    notes = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(debit__gte=0) & models.Q(credit__gte=0),
                name='accounting_journalitem_non_negative_amounts',
            ),
            models.CheckConstraint(
                condition=~(models.Q(debit=0) & models.Q(credit=0)),
                name='accounting_journalitem_not_both_zero',
            ),
            models.CheckConstraint(
                condition=models.Q(debit=0) | models.Q(credit=0),
                name='accounting_journalitem_single_sided',
            ),
        ]

    def __str__(self):
        return f'Item #{self.pk} entry={self.entry_id} ledger={self.ledger_id}'


class PendingExpense(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    employee_name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    # Maps to an expense-type Ledger (e.g. Travel, Salary)
    category = models.ForeignKey(
        'Ledger',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_expenses',
    )
    description = models.TextField(blank=True, default='')

    # Identity from the external expense system
    source_id = models.CharField(max_length=200, unique=True)
    source = models.CharField(max_length=100, default='external_app')

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Set once the expense is approved and a journal entry is created
    journal_entry = models.OneToOneField(
        'JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_expense',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'PendingExpense #{self.pk} – {self.employee_name} ({self.status})'


class JournalItemAttachment(models.Model):
    journal_item = models.ForeignKey(JournalItem, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='journal_receipts/%Y/%m/')
    name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Attachment {self.name} for item {self.journal_item_id}'


class Account(models.Model):
    class AccountType(models.TextChoices):
        BANK = 'bank', 'Bank'
        CASH = 'cash', 'Cash'
        WALLET = 'wallet', 'Wallet'
        SETTLEMENT = 'settlement', 'Settlement'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=20, choices=AccountType.choices)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    financial_account = models.OneToOneField(
        'FinancialAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_detail',
    )

    class Meta:
        ordering = ['name']
        unique_together = [['org_id', 'name']]

    def __str__(self):
        return f'{self.name} ({self.type})'

    def get_or_create_ledger(self):
        ledger, created = Ledger.objects.get_or_create(
            org_id=self.org_id,
            name=f'{self.name} Account',
            defaults={'type': Ledger.LedgerType.ASSET}
        )
        return ledger

    def save(self, *args, **kwargs):
        if getattr(self, '_syncing', False):
            super().save(*args, **kwargs)
            return

        self._syncing = True
        try:
            if not self.financial_account:
                from accounting.models import FinancialAccount
                if self.type == self.AccountType.CASH:
                    acc_class = FinancialAccount.AccountClass.CASH
                    acc_type_str = 'Cash'
                elif self.type == self.AccountType.BANK:
                    acc_class = FinancialAccount.AccountClass.BANK
                    acc_type_str = 'Bank'
                elif self.type == self.AccountType.SETTLEMENT:
                    acc_class = FinancialAccount.AccountClass.SETTLEMENT
                    acc_type_str = 'Settlement'
                else:
                    acc_class = FinancialAccount.AccountClass.WALLET
                    acc_type_str = 'Wallet'

                fa = FinancialAccount(
                    org_id=self.org_id,
                    account_name=self.name,
                    account_class=acc_class,
                    account_type=acc_type_str,
                    balance=self.balance,
                    status='active',
                )
                fa._syncing = True
                fa.save()
                self.financial_account = fa

            super().save(*args, **kwargs)

            fa = self.financial_account
            fa._syncing = True
            fa.account_name = self.name
            fa.balance = self.balance
            fa.save()
        finally:
            self._syncing = False


class Expense(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    category = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name='expenses')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='expenses')
    date = models.DateField()
    description = models.TextField()
    department = models.CharField(max_length=100, blank=True, null=True)
    receipt = models.FileField(upload_to='expenses/%Y/%m/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    journal_entry = models.OneToOneField(JournalEntry, on_delete=models.CASCADE, null=True, blank=True, related_name='expense')

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'Expense #{self.pk} - {self.amount} on {self.date}'


class Income(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    category = models.ForeignKey(Ledger, on_delete=models.PROTECT, related_name='incomes')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='incomes')
    date = models.DateField()
    description = models.TextField()
    department = models.CharField(max_length=100, blank=True, null=True)
    receipt = models.FileField(upload_to='incomes/%Y/%m/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    journal_entry = models.OneToOneField(
        JournalEntry, on_delete=models.CASCADE, null=True, blank=True, related_name='income'
    )

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'Income #{self.pk} - {self.amount} on {self.date}'


class Outstanding(models.Model):
    class OutstandingType(models.TextChoices):
        RECEIVABLE = 'receivable', 'Receivable'
        PAYABLE = 'payable', 'Payable'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    type = models.CharField(max_length=20, choices=OutstandingType.choices)
    party_name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    linked_journal = models.ForeignKey(
        JournalEntry, on_delete=models.PROTECT, related_name='outstandings', null=True, blank=True
    )
    settlement_journal = models.ForeignKey(
        JournalEntry, on_delete=models.PROTECT, related_name='settlements', null=True, blank=True
    )
    settlement_account = models.ForeignKey(
        Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='settled_outstandings'
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    description = models.TextField(blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.type.capitalize()} #{self.pk} - {self.party_name} ({self.amount})'


class OutstandingReceipt(models.Model):
    outstanding = models.ForeignKey(Outstanding, on_delete=models.CASCADE, related_name='receipts')
    file = models.FileField(upload_to='receipts/outstandings/')
    filename = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Receipt for {self.outstanding} - {self.filename}'


class Invoice(models.Model):
    class InvoiceType(models.TextChoices):
        SALES    = 'sales',    'Sales Invoice'
        PURCHASE = 'purchase', 'Purchase Bill'

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        SETTLED  = 'settled',  'Settled'

    org_id       = models.CharField(max_length=120, db_index=True, blank=True, default='')
    type         = models.CharField(max_length=20, choices=InvoiceType.choices)
    party_name   = models.CharField(max_length=200)
    amount       = models.DecimalField(max_digits=14, decimal_places=2)
    department   = models.CharField(max_length=100, blank=True, default='')
    due_date     = models.DateField(blank=True, null=True)
    description  = models.TextField(blank=True, default='')
    status       = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Created immediately on invoice creation (receivable or payable)
    outstanding  = models.OneToOneField(
        Outstanding,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoice',
    )

    # Created only at settlement
    journal_entry = models.OneToOneField(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='invoice',
    )

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_type_display()} #{self.pk} – {self.party_name} ₹{self.amount} ({self.status})'

# ---------------------------------------------------------------------------
# Master Financial Accounts Hub
# ---------------------------------------------------------------------------

class AccountGroup(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    name = models.CharField(max_length=120)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'account_groups'
        ordering = ['name']
        unique_together = [['org_id', 'name']]

    def __str__(self):
        return self.name


class FinancialAccount(models.Model):
    class AccountClass(models.TextChoices):
        BANK = 'bank', 'Bank Account'
        CASH = 'cash', 'Cash Account'
        WALLET = 'wallet', 'Wallet Account'
        SETTLEMENT = 'settlement', 'Settlement Account'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    account_name = models.CharField(max_length=120)
    account_class = models.CharField(max_length=50, choices=AccountClass.choices)
    account_type = models.CharField(max_length=50) # Current, Savings, Petty Cash, Paytm, etc.
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default='active')
    group = models.ForeignKey(AccountGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name='accounts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financial_accounts'
        ordering = ['account_name']

    def __str__(self):
        return f'{self.account_name} ({self.get_account_class_display()})'

    @property
    def ledger(self):
        if self.account_class == 'bank' and hasattr(self, 'bank_account_detail') and self.bank_account_detail.ledger:
            return self.bank_account_detail.ledger
        from accounting.models import Ledger
        ledger, _ = Ledger.objects.get_or_create(
            org_id=self.org_id,
            name=f"{self.account_name} ({self.get_account_class_display()})",
            defaults={'type': Ledger.LedgerType.ASSET}
        )
        return ledger

    def save(self, *args, **kwargs):
        if getattr(self, '_syncing', False):
            super().save(*args, **kwargs)
            return

        self._syncing = True
        try:
            super().save(*args, **kwargs)
            if self.account_class == 'bank':
                from accounting.models import BankAccount
                ba, created = BankAccount.objects.get_or_create(
                    financial_account=self,
                    defaults={
                        'org_id': self.org_id,
                        'name': self.account_name,
                        'account_name': self.account_name,
                        'bank_name': self.account_name,
                        'status': self.status,
                        'opening_balance': self.balance,
                    }
                )
                if not created:
                    ba._syncing = True
                    ba.name = self.account_name
                    ba.account_name = self.account_name
                    ba.status = self.status
                    ba.opening_balance = self.balance
                    ba.save()

            # Bidirectional sync with Account model
            from accounting.models import Account
            acc_type = None
            if self.account_class == 'bank':
                acc_type = Account.AccountType.BANK
            elif self.account_class == 'cash':
                acc_type = Account.AccountType.CASH
            elif self.account_class == 'wallet':
                acc_type = Account.AccountType.WALLET
            elif self.account_class == 'settlement':
                acc_type = Account.AccountType.SETTLEMENT

            if acc_type:
                acc, created = Account.objects.get_or_create(
                    financial_account=self,
                    defaults={
                        'org_id': self.org_id,
                        'name': self.account_name,
                        'type': acc_type,
                        'balance': self.balance,
                    }
                )
                if not created:
                    acc._syncing = True
                    acc.name = self.account_name
                    acc.type = acc_type
                    acc.balance = self.balance
                    acc.save()
        finally:
            self._syncing = False


class CashAccount(models.Model):
    financial_account = models.OneToOneField(FinancialAccount, on_delete=models.CASCADE, primary_key=True, related_name='cash_detail')
    location = models.CharField(max_length=150, blank=True, default='')
    custodian = models.CharField(max_length=150, blank=True, default='')
    purpose = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'cash_accounts'


class WalletAccount(models.Model):
    financial_account = models.OneToOneField(FinancialAccount, on_delete=models.CASCADE, primary_key=True, related_name='wallet_detail')
    provider = models.CharField(max_length=120)
    linked_account = models.ForeignKey(FinancialAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_wallets')

    class Meta:
        db_table = 'wallet_accounts'


class SettlementAccount(models.Model):
    financial_account = models.OneToOneField(FinancialAccount, on_delete=models.CASCADE, primary_key=True, related_name='settlement_detail')
    provider = models.CharField(max_length=120)
    settlement_frequency = models.CharField(max_length=100, blank=True, default='')
    linked_bank_account = models.ForeignKey('BankAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_settlements')

    class Meta:
        db_table = 'settlement_accounts'


class AccountActivityLog(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    account = models.ForeignKey(FinancialAccount, on_delete=models.CASCADE, related_name='activities')
    action = models.CharField(max_length=50) # created, updated, balance_imported, statement_imported, archived
    details = models.TextField(blank=True, default='')
    performed_by = models.CharField(max_length=150, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'account_activity_logs'
        ordering = ['-created_at']


# ---------------------------------------------------------------------------
# Banking Module
# ---------------------------------------------------------------------------

class BankAccount(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    name = models.CharField(max_length=120)  # Legacy field, kept in sync with account_name
    account_name = models.CharField(max_length=120, blank=True, default='')
    bank_name = models.CharField(max_length=120, blank=True, default='')
    account_number = models.CharField(max_length=50, blank=True, default='')
    ifsc = models.CharField(max_length=20, blank=True, default='')
    branch = models.CharField(max_length=120, blank=True, default='')
    currency = models.CharField(max_length=10, default='INR')
    account_type = models.CharField(max_length=50, default='Current')
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, default='active')
    financial_account = models.OneToOneField(
        FinancialAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_account_detail',
    )
    # Optional link to a Ledger so journal entries auto-use it
    ledger = models.OneToOneField(
        'Ledger',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_account',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name or self.account_name} ({self.bank_name})'

    def save(self, *args, **kwargs):
        if getattr(self, '_syncing', False):
            if not self.account_name and self.name:
                self.account_name = self.name
            elif not self.name and self.account_name:
                self.name = self.account_name
            super().save(*args, **kwargs)
            return

        self._syncing = True
        try:
            if not self.account_name and self.name:
                self.account_name = self.name
            elif not self.name and self.account_name:
                self.name = self.account_name

            if not self.financial_account:
                from accounting.models import FinancialAccount
                fa = FinancialAccount(
                    org_id=self.org_id,
                    account_name=self.account_name,
                    account_class=FinancialAccount.AccountClass.BANK,
                    account_type=self.account_type,
                    balance=self.opening_balance,
                    status=self.status,
                )
                fa._syncing = True
                fa.save()
                self.financial_account = fa

            super().save(*args, **kwargs)

            fa = self.financial_account
            fa._syncing = True
            fa.account_name = self.account_name
            fa.status = self.status
            fa.balance = self.opening_balance
            fa.save()
        finally:
            self._syncing = False


class BankStatementImport(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='statement_imports')
    file_name = models.CharField(max_length=255)
    statement_period = models.CharField(max_length=100)  # e.g., "01 Jun – 30 Jun"
    transactions_count = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default='Imported')  # Imported, Processing, Failed, Completed
    imported_by = models.CharField(max_length=150, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Import {self.file_name} for {self.account} - {self.created_at}'


class BankTransaction(models.Model):
    class TxType(models.TextChoices):
        DEBIT = 'debit', 'Debit'
        CREDIT = 'credit', 'Credit'

    class Status(models.TextChoices):
        UNPROCESSED = 'unprocessed', 'Unprocessed'
        PROCESSED = 'processed', 'Processed'
        IGNORED = 'ignored', 'Ignored'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name='transactions')
    
    # New spec fields
    transaction_date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=100, blank=True, default='')
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    statement_import = models.ForeignKey(
        BankStatementImport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    
    # Legacy fields (kept in sync via save())
    date = models.DateField()
    description = models.TextField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)  # always positive
    type = models.CharField(max_length=10, choices=TxType.choices)  # debit/credit
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPROCESSED)

    department = models.CharField(max_length=100, blank=True, null=True)
    suggested_ledger = models.ForeignKey(
        'Ledger',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='suggested_transactions',
    )
    journal_entry = models.OneToOneField(
        'JournalEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_transaction',
    )

    unique_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'BankTx #{self.pk} [{self.type}] {self.amount} on {self.date}'

    def save(self, *args, **kwargs):
        # Sync date and transaction_date
        if self.transaction_date:
            self.date = self.transaction_date
        elif self.date:
            self.transaction_date = self.date
        
        # Sync amount and type with debit/credit
        if self.debit > 0:
            self.amount = self.debit
            self.type = self.TxType.DEBIT
        elif self.credit > 0:
            self.amount = self.credit
            self.type = self.TxType.CREDIT
        else:
            # Fallback if both debit and credit are 0
            if self.type == self.TxType.DEBIT:
                self.debit = self.amount
            else:
                self.credit = self.amount
                self.type = self.TxType.CREDIT

        # Generate unique hash if not present
        if not self.unique_hash:
            raw = f"{self.date}|{self.debit or self.credit}|{self.description}".strip().lower()
            self.unique_hash = hashlib.sha256(raw.encode()).hexdigest()[:64]

        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Bulk Settlement — groups multiple Outstanding settlements done at once
# ---------------------------------------------------------------------------

class BulkSettlement(models.Model):
    """A named batch/folder that groups N Outstanding items settled together."""

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    label = models.CharField(max_length=255, blank=True, default='')
    settlement_account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='bulk_settlements',
    )
    settlement_date = models.DateField()
    total_amount = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    items_count = models.IntegerField(default=0)
    # JSON list of outstanding IDs settled in this batch
    outstanding_ids = models.JSONField(default=list)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'BulkSettlement #{self.pk} – {self.items_count} items – ₹{self.total_amount}'


class GSTSettings(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, unique=True, help_text="The organization this setting belongs to.")
    gstin = models.CharField(max_length=15, blank=True, default='')
    legal_name = models.CharField(max_length=255, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    registration_type = models.CharField(
        max_length=50,
        choices=[('regular', 'Regular'), ('composition', 'Composition')],
        default='regular'
    )
    filing_frequency = models.CharField(
        max_length=50,
        choices=[('monthly', 'Monthly'), ('quarterly', 'Quarterly')],
        default='monthly'
    )
    default_gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "GST Settings"
        verbose_name_plural = "GST Settings"

    def __str__(self):
        return f"GST Settings for Org: {self.org_id}"


class GSTTransaction(models.Model):
    class TransactionType(models.TextChoices):
        SALE = 'sale', 'Sale'
        PURCHASE = 'purchase', 'Purchase'
        EXPENSE = 'expense', 'Expense'

    class SourceModule(models.TextChoices):
        SALES = 'sales', 'Sales Module'
        PURCHASES = 'purchases', 'Purchases Module'
        EXPENSES = 'expenses', 'Expenses Module'

    class GSTType(models.TextChoices):
        CGST = 'cgst', 'CGST'
        SGST = 'sgst', 'SGST'
        IGST = 'igst', 'IGST'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RECORDED = 'recorded', 'Recorded'
        FILED = 'filed', 'Filed'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    transaction_id = models.CharField(max_length=100, db_index=True, unique=True)
    reference_number = models.CharField(max_length=100, blank=True, default='')
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    source_module = models.CharField(max_length=20, choices=SourceModule.choices)
    taxable_amount = models.DecimalField(max_digits=14, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=14, decimal_places=2)
    gst_type = models.CharField(max_length=10, choices=GSTType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECORDED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"GST Txn #{self.pk} - {self.transaction_type} ({self.gst_type}: {self.gst_amount})"


class GSTSummary(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    month = models.IntegerField()
    year = models.IntegerField()
    input_gst = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    output_gst = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    net_gst = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['org_id', 'month', 'year']]
        verbose_name = "GST Summary"
        verbose_name_plural = "GST Summaries"

    def __str__(self):
        return f"GST Summary for Org {self.org_id} - {self.month}/{self.year}"


class ReconciliationRule(models.Model):
    rule_name = models.CharField(max_length=150)
    priority = models.IntegerField(default=1)
    confidence_score = models.IntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['priority']

    def __str__(self):
        return f"{self.rule_name} (Priority {self.priority})"


class ReconciliationMatch(models.Model):
    class MatchMethod(models.TextChoices):
        AUTOMATIC = 'automatic', 'Automatic'
        MANUAL = 'manual', 'Manual'
        BULK = 'bulk', 'Bulk Match'

    class Status(models.TextChoices):
        SUGGESTED = 'suggested', 'Suggested'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    bank_transaction = models.ForeignKey('BankTransaction', on_delete=models.CASCADE, related_name='reconciliation_matches')
    journal_item = models.ForeignKey('JournalItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='reconciliation_matches')
    confidence_score = models.IntegerField(default=100)
    match_method = models.CharField(max_length=20, choices=MatchMethod.choices, default=MatchMethod.AUTOMATIC)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUGGESTED)
    matched_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True)
    matched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-matched_at']

    def __str__(self):
        return f"Match #{self.pk} (Confidence {self.confidence_score}%, Status: {self.status})"


class ReconciliationException(models.Model):
    class ExceptionType(models.TextChoices):
        NO_MATCH = 'no_match', 'No Match Found'
        MULTIPLE_MATCHES = 'multiple_matches', 'Multiple Matches'
        DUPLICATE_CANDIDATE = 'duplicate_candidate', 'Duplicate Candidate'
        AMOUNT_MISMATCH = 'amount_mismatch', 'Amount Mismatch'
        DATE_MISMATCH = 'date_mismatch', 'Date Mismatch'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        IN_REVIEW = 'in_review', 'In Review'
        RESOLVED = 'resolved', 'Resolved'
        IGNORED = 'ignored', 'Ignored'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    bank_transaction = models.ForeignKey('BankTransaction', on_delete=models.CASCADE, related_name='reconciliation_exceptions')
    exception_type = models.CharField(max_length=30, choices=ExceptionType.choices, default=ExceptionType.NO_MATCH)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    severity = models.CharField(
        max_length=10,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        default='low'
    )
    assigned_to = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_exceptions'
    )
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Exception #{self.pk} - {self.get_exception_type_display()} ({self.status})"


class DuplicateCandidate(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    transaction_1 = models.ForeignKey('BankTransaction', on_delete=models.CASCADE, related_name='duplicate_candidates_as_1')
    transaction_2 = models.ForeignKey('BankTransaction', on_delete=models.CASCADE, related_name='duplicate_candidates_as_2')
    similarity_score = models.IntegerField(default=100)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('reviewed', 'Reviewed'), ('ignored', 'Ignored'), ('merged', 'Merged')],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [['transaction_1', 'transaction_2']]


class RiskAlert(models.Model):
    class RiskType(models.TextChoices):
        WEEKEND = 'weekend_transaction', 'Weekend Transaction'
        ROUND_NUMBER = 'round_number', 'Round Number Transaction'
        SUSPICIOUS_DESCRIPTION = 'suspicious_description', 'Suspicious Description'
        HIGH_AMOUNT = 'unusually_high_amount', 'Unusually High Amount'

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    bank_transaction = models.ForeignKey('BankTransaction', on_delete=models.CASCADE, related_name='risk_alerts')
    risk_type = models.CharField(max_length=50, choices=RiskType.choices)
    risk_score = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-risk_score', '-created_at']


class ReconciliationAuditLog(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='recon_audit_logs')
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=50)  # e.g., 'import', 'match', 'exception', 'duplicate', 'risk_alert'
    entity_id = models.CharField(max_length=100)
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# ---------------------------------------------------------------------------
# Asset Management Module
# ---------------------------------------------------------------------------

class Asset(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        DISPOSED = 'disposed', 'Disposed'
        UNDER_REPAIR = 'under_repair', 'Under Repair'
        FULLY_DEPRECIATED = 'fully_depreciated', 'Fully Depreciated'

    class Category(models.TextChoices):
        COMPUTER = 'computer', 'Computer & IT'
        FURNITURE = 'furniture', 'Furniture & Fixtures'
        VEHICLE = 'vehicle', 'Vehicle'
        MACHINERY = 'machinery', 'Machinery & Equipment'
        BUILDING = 'building', 'Building & Property'
        OTHER = 'other', 'Other'

    class DepreciationMethod(models.TextChoices):
        SLM = 'slm', 'Straight Line Method (SLM)'
        WDV = 'wdv', 'Written Down Value (WDV)'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    asset_code = models.CharField(max_length=50, blank=True, default='')  # e.g. AST-0001
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=Category.choices, default=Category.OTHER)
    description = models.TextField(blank=True, default='')
    serial_number = models.CharField(max_length=100, blank=True, default='')
    vendor = models.CharField(max_length=200, blank=True, default='')
    location = models.CharField(max_length=200, blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')

    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=14, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    useful_life_years = models.IntegerField(default=5)  # in years
    depreciation_method = models.CharField(max_length=10, choices=DepreciationMethod.choices, default=DepreciationMethod.SLM)
    depreciation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)  # % per annum

    current_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    accumulated_depreciation = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    last_depreciation_date = models.DateField(blank=True, null=True)

    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ACTIVE)

    # Optional journal entry link for purchase
    purchase_journal = models.ForeignKey(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_purchases',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'assets'

    def __str__(self):
        return f'{self.asset_code} – {self.name}'

    def save(self, *args, **kwargs):
        if not self.asset_code:
            last = Asset.objects.filter(org_id=self.org_id).order_by('-id').first()
            next_num = (last.id + 1) if last else 1
            self.asset_code = f'AST-{next_num:04d}'
        if not self.current_value:
            self.current_value = self.purchase_cost
        super().save(*args, **kwargs)


class AssetAssignment(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='assignments')
    assigned_to = models.CharField(max_length=200)  # Employee name
    department = models.CharField(max_length=100, blank=True, default='')
    assigned_date = models.DateField()
    returned_date = models.DateField(blank=True, null=True)
    notes = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assigned_date']
        db_table = 'asset_assignments'

    def __str__(self):
        return f'{self.asset} → {self.assigned_to}'


class AssetDepreciation(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='depreciations')
    period_month = models.IntegerField()  # 1-12
    period_year = models.IntegerField()
    depreciation_amount = models.DecimalField(max_digits=14, decimal_places=2)
    book_value_before = models.DecimalField(max_digits=14, decimal_places=2)
    book_value_after = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=10)
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_depreciations',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period_year', '-period_month']
        unique_together = [['asset', 'period_month', 'period_year']]
        db_table = 'asset_depreciation'

    def __str__(self):
        return f'Depreciation for {self.asset} – {self.period_month}/{self.period_year}'


class AssetDisposal(models.Model):
    class DisposalMethod(models.TextChoices):
        SOLD = 'sold', 'Sold'
        SCRAPPED = 'scrapped', 'Scrapped'
        DONATED = 'donated', 'Donated'
        STOLEN = 'stolen', 'Stolen / Lost'
        REPLACED = 'replaced', 'Replaced'

    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    asset = models.OneToOneField(Asset, on_delete=models.CASCADE, related_name='disposal')
    disposal_date = models.DateField()
    method = models.CharField(max_length=20, choices=DisposalMethod.choices)
    sale_proceeds = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    book_value_at_disposal = models.DecimalField(max_digits=14, decimal_places=2)
    gain_loss = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # positive = gain
    notes = models.TextField(blank=True, default='')
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asset_disposals',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-disposal_date']
        db_table = 'asset_disposals'

    def __str__(self):
        return f'Disposal of {self.asset} on {self.disposal_date}'


class AssetAuditLog(models.Model):
    org_id = models.CharField(max_length=120, db_index=True, blank=True, default='')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=100)  # e.g. 'created', 'assigned', 'deprecated', 'disposed', 'repaired'
    performed_by = models.CharField(max_length=150, blank=True, default='System')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'asset_audit_logs'

    def __str__(self):
        return f'[{self.action}] {self.asset} at {self.created_at}'




