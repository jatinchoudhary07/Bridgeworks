from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from core.views.helpers import _get_org_id_or_none

from .models import (
    Account, BankAccount, BankTransaction, BankStatementImport,
    BulkSettlement,
    Invoice, JournalEntry, JournalItem, Ledger, Outstanding, PendingExpense,
)


class LedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ledger
        fields = ('id', 'name', 'type')


class JournalItemCreateSerializer(serializers.Serializer):
    ledger = serializers.PrimaryKeyRelatedField(queryset=Ledger.objects.all())
    debit = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
    credit = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
    department = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    payment_method = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    vendor_payee = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    bill_date = serializers.DateField(required=False, allow_null=True)
    ref_id = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        debit = attrs.get('debit', Decimal('0'))
        credit = attrs.get('credit', Decimal('0'))

        if debit == 0 and credit == 0:
            raise serializers.ValidationError('Each journal item must have either debit or credit amount.')
        if debit > 0 and credit > 0:
            raise serializers.ValidationError('A journal item cannot have both debit and credit values.')

        # Enforce ledger org_id matching request's org_id
        request = self.context.get('request')
        if request:
            org_id = _get_org_id_or_none(request) or ''
            ledger = attrs.get('ledger')
            if ledger and ledger.org_id != org_id:
                raise serializers.ValidationError('Invalid ledger for this organization.')

        return attrs


class JournalEntryCreateSerializer(serializers.Serializer):
    date = serializers.DateField()
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    items = JournalItemCreateSerializer(many=True, min_length=2)

    def validate(self, attrs):
        items = attrs.get('items', [])
        total_debit = sum((item['debit'] for item in items), Decimal('0'))
        total_credit = sum((item['credit'] for item in items), Decimal('0'))

        if total_debit != total_credit:
            raise serializers.ValidationError(
                {'items': 'Total debit must be equal to total credit.'}
            )

        return attrs

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # We also need request to access uploaded files
        request = self.context.get('request')
        org_id = _get_org_id_or_none(request) or ''

        with transaction.atomic():
            entry = JournalEntry.objects.create(org_id=org_id, **validated_data)
            
            from .models import JournalItemAttachment
            
            for index, item_data in enumerate(items_data):
                # Pop out standard fields to leave extra fields
                debit = item_data.pop('debit', Decimal('0'))
                credit = item_data.pop('credit', Decimal('0'))
                ledger = item_data.pop('ledger')
                item_data.pop('type', None)

                # Create the item with the rest of the attributes
                j_item = JournalItem.objects.create(
                    org_id=org_id,
                    entry=entry,
                    ledger=ledger,
                    debit=debit,
                    credit=credit,
                    **item_data
                )
                
            return entry


class JournalItemSerializer(serializers.ModelSerializer):
    ledger_name = serializers.CharField(source='ledger.name', read_only=True)

    class Meta:
        model = JournalItem
        fields = ('id', 'ledger', 'ledger_name', 'debit', 'credit', 'department', 'payment_method', 'vendor_payee', 'bill_date', 'ref_id', 'notes')


class JournalEntrySerializer(serializers.ModelSerializer):
    items = JournalItemSerializer(many=True, read_only=True)

    class Meta:
        model = JournalEntry
        fields = ('id', 'date', 'description', 'created_at', 'items')


class PendingExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True)
    category_id = serializers.PrimaryKeyRelatedField(source='category', read_only=True, allow_null=True)

    class Meta:
        model = PendingExpense
        fields = (
            'id', 'employee_name', 'amount', 'category_id', 'category_name',
            'description', 'source_id', 'source', 'status', 'created_at', 'updated_at',
        )


class ApproveExpenseSerializer(serializers.Serializer):
    """Expects the Ledger (asset type) that will be credited (payment account)."""
    payment_ledger = serializers.PrimaryKeyRelatedField(
        queryset=Ledger.objects.filter(type__in=['asset', 'liability']),
        help_text='ID of the asset/liability ledger to credit (e.g. Cash, Bank).',
    )

    def validate(self, attrs):
        request = self.context.get('request')
        if request:
            org_id = _get_org_id_or_none(request) or ''
            payment_ledger = attrs.get('payment_ledger')
            if payment_ledger and payment_ledger.org_id != org_id:
                raise serializers.ValidationError({'payment_ledger': 'Invalid payment ledger for this organization.'})
        return attrs


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        from .models import Expense
        model = Expense
        fields = ('id', 'amount', 'category', 'category_name', 'account', 'account_name', 'date', 'description', 'department', 'receipt', 'created_at')


class IncomeSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)

    class Meta:
        from .models import Income
        model = Income
        fields = ('id', 'amount', 'category', 'category_name', 'account', 'account_name', 'date', 'description', 'department', 'receipt', 'created_at')


class OutstandingReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import OutstandingReceipt
        model = OutstandingReceipt
        fields = ('id', 'file', 'filename', 'uploaded_at')


class OutstandingSerializer(serializers.ModelSerializer):
    linked_journal_id = serializers.IntegerField(source='linked_journal.id', read_only=True, allow_null=True)
    settlement_journal_id = serializers.IntegerField(source='settlement_journal.id', read_only=True, allow_null=True)
    settlement_account_name = serializers.CharField(source='settlement_account.name', read_only=True, allow_null=True, default=None)
    receipts = OutstandingReceiptSerializer(many=True, read_only=True)

    class Meta:
        model = Outstanding
        fields = (
            'id', 'type', 'party_name', 'amount', 'status', 'description', 'department',
            'due_date', 'linked_journal_id', 'settlement_journal_id',
            'settlement_account_name', 'receipts', 'created_at', 'updated_at'
        )


class InvoiceSerializer(serializers.ModelSerializer):
    outstanding_id = serializers.IntegerField(source='outstanding.id', read_only=True, allow_null=True)
    journal_entry_id = serializers.IntegerField(source='journal_entry.id', read_only=True, allow_null=True)

    class Meta:
        model = Invoice
        fields = (
            'id', 'type', 'party_name', 'amount', 'department',
            'due_date', 'description', 'status',
            'outstanding_id', 'journal_entry_id',
            'created_at', 'updated_at',
        )
        read_only_fields = ('status', 'outstanding_id', 'journal_entry_id', 'created_at', 'updated_at')


class InvoiceCreateSerializer(serializers.Serializer):
    type        = serializers.ChoiceField(choices=Invoice.InvoiceType.choices)
    party_name  = serializers.CharField(max_length=200)
    amount      = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    department  = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    due_date    = serializers.DateField(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')


class InvoiceSettleSerializer(serializers.Serializer):
    """
    payment_account: ID of the Account to use for settlement (Bank / Cash).
    """
    payment_account = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        help_text='ID of the Account (bank/cash) used for payment.',
    )

    def validate(self, attrs):
        request = self.context.get('request')
        if request:
            org_id = _get_org_id_or_none(request) or ''
            payment_account = attrs.get('payment_account')
            if payment_account and payment_account.org_id != org_id:
                raise serializers.ValidationError({'payment_account': 'Invalid payment account for this organization.'})
        return attrs


class BankAccountSerializer(serializers.ModelSerializer):
    ledger_id = serializers.IntegerField(source='ledger.id', read_only=True, allow_null=True)
    ledger_name = serializers.CharField(source='ledger.name', read_only=True, allow_null=True, default=None)
    # Computed balance
    balance = serializers.SerializerMethodField()
    total_credits = serializers.SerializerMethodField()
    total_debits = serializers.SerializerMethodField()
    transaction_count = serializers.SerializerMethodField()
    unprocessed_count = serializers.SerializerMethodField()
    last_transaction_date = serializers.SerializerMethodField()

    class Meta:
        model = BankAccount
        fields = (
            'id', 'name', 'account_name', 'bank_name', 'account_number', 'opening_balance',
            'ifsc', 'branch', 'currency', 'account_type', 'status',
            'ledger_id', 'ledger_name',
            'balance', 'total_credits', 'total_debits',
            'transaction_count', 'unprocessed_count', 'last_transaction_date',
            'created_at', 'updated_at',
        )

    def _txns(self, obj):
        return obj.transactions.exclude(status=BankTransaction.Status.IGNORED)

    def get_total_credits(self, obj):
        if hasattr(obj, 'annotated_total_credits'):
            return float(obj.annotated_total_credits or 0)
        from django.db.models import Sum
        result = self._txns(obj).filter(type='credit').aggregate(s=Sum('amount'))['s'] or 0
        return float(result)

    def get_total_debits(self, obj):
        if hasattr(obj, 'annotated_total_debits'):
            return float(obj.annotated_total_debits or 0)
        from django.db.models import Sum
        result = self._txns(obj).filter(type='debit').aggregate(s=Sum('amount'))['s'] or 0
        return float(result)

    def get_balance(self, obj):
        if hasattr(obj, 'annotated_balance'):
            return float(obj.annotated_balance or 0)
        return float(obj.opening_balance) + self.get_total_credits(obj) - self.get_total_debits(obj)

    def get_transaction_count(self, obj):
        if hasattr(obj, 'annotated_transaction_count'):
            return int(obj.annotated_transaction_count or 0)
        return obj.transactions.count()

    def get_unprocessed_count(self, obj):
        if hasattr(obj, 'annotated_unprocessed_count'):
            return int(obj.annotated_unprocessed_count or 0)
        return obj.transactions.filter(status=BankTransaction.Status.UNPROCESSED).count()

    def get_last_transaction_date(self, obj):
        if hasattr(obj, 'annotated_last_transaction_date'):
            val = obj.annotated_last_transaction_date
            return str(val) if val else None
        last = obj.transactions.order_by('-date').values_list('date', flat=True).first()
        return str(last) if last else None


class BankAccountCreateSerializer(serializers.ModelSerializer):
    ledger_id = serializers.PrimaryKeyRelatedField(
        queryset=Ledger.objects.all(), source='ledger', required=False, allow_null=True,
    )

    class Meta:
        model = BankAccount
        fields = ('id', 'name', 'account_name', 'bank_name', 'account_number', 'ifsc', 'branch', 'currency', 'account_type', 'status', 'opening_balance', 'ledger_id')

    def validate(self, attrs):
        request = self.context.get('request')
        if request:
            org_id = _get_org_id_or_none(request) or ''
            ledger = attrs.get('ledger')
            if ledger and ledger.org_id != org_id:
                raise serializers.ValidationError({'ledger_id': 'Invalid ledger for this organization.'})
        return attrs


class BankStatementImportSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.account_name', read_only=True)

    class Meta:
        model = BankStatementImport
        fields = (
            'id', 'account', 'account_name', 'file_name',
            'statement_period', 'transactions_count', 'status',
            'imported_by', 'created_at'
        )


class BankTransactionSerializer(serializers.ModelSerializer):
    bank_account_name = serializers.CharField(source='bank_account.name', read_only=True)
    suggested_ledger_name = serializers.CharField(source='suggested_ledger.name', read_only=True, allow_null=True, default=None)
    journal_entry_id = serializers.IntegerField(source='journal_entry.id', read_only=True, allow_null=True)
    statement_import_file = serializers.CharField(source='statement_import.file_name', read_only=True, allow_null=True)
    suggested_match = serializers.SerializerMethodField()

    class Meta:
        model = BankTransaction
        fields = (
            'id', 'bank_account', 'bank_account_name',
            'date', 'transaction_date', 'description', 'amount', 'type', 'status',
            'reference', 'debit', 'credit', 'balance', 'statement_import', 'statement_import_file',
            'department', 'suggested_ledger', 'suggested_ledger_name',
            'journal_entry_id', 'unique_hash', 'suggested_match', 'created_at',
        )

    def get_suggested_match(self, obj):
        from .models import ReconciliationMatch
        match = obj.reconciliation_matches.filter(status='suggested').first()
        if match:
            ji = match.journal_item
            if not ji:
                return None
            
            # Formulate reasoning message
            if match.confidence_score == 100:
                reasoning = "Matched because: Amount matches, Reference matches."
            elif match.confidence_score == 95:
                ji_date = ji.entry.date
                tx_date = obj.date
                diff_days = abs((tx_date - ji_date).days)
                reasoning = f"Matched because: Amount matches, Date difference {diff_days} day(s)."
            elif match.confidence_score == 90:
                reasoning = "Matched because: Amount matches, Description similarity matches."
            else:
                reasoning = "Matched because: Amount matches."
                
            return {
                'match_id': match.id,
                'confidence_score': match.confidence_score,
                'match_method': match.match_method,
                'journal_item_id': ji.id,
                'voucher': f'JV #{ji.entry.id}',
                'ledger_account': ji.ledger.name,
                'amount': float(ji.debit or ji.credit),
                'date': str(ji.entry.date),
                'type': 'debit' if ji.debit > 0 else 'credit',
                'description': ji.entry.description or ji.notes or '',
                'reasoning': reasoning
            }
        return None



class BulkSettlementSerializer(serializers.ModelSerializer):
    settlement_account_name = serializers.CharField(
        source='settlement_account.name', read_only=True
    )
    # Resolve the Outstanding objects for the detail view
    items = serializers.SerializerMethodField()

    class Meta:
        model = BulkSettlement
        fields = (
            'id', 'label', 'settlement_account', 'settlement_account_name',
            'settlement_date', 'total_amount', 'items_count',
            'outstanding_ids', 'notes', 'created_at', 'items',
        )

    def get_items(self, obj):
        qs = Outstanding.objects.filter(pk__in=obj.outstanding_ids)
        return OutstandingSerializer(qs, many=True).data


class GSTSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import GSTSettings
        model = GSTSettings
        fields = ('gstin', 'legal_name', 'state', 'registration_type', 'filing_frequency', 'default_gst_rate', 'updated_at')


class GSTTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import GSTTransaction
        model = GSTTransaction
        fields = (
            'id', 'transaction_id', 'reference_number', 'transaction_type',
            'source_module', 'taxable_amount', 'gst_rate', 'gst_amount',
            'gst_type', 'status', 'created_at', 'updated_at'
        )


class GSTSummarySerializer(serializers.ModelSerializer):
    class Meta:
        from .models import GSTSummary
        model = GSTSummary
        fields = ('id', 'month', 'year', 'input_gst', 'output_gst', 'net_gst', 'updated_at')


class AccountGroupSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import AccountGroup
        model = AccountGroup
        fields = ('id', 'name', 'is_system', 'created_at', 'updated_at')


class CashAccountSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import CashAccount
        model = CashAccount
        fields = ('location', 'custodian', 'purpose')


class WalletAccountSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import WalletAccount
        model = WalletAccount
        fields = ('provider', 'linked_account')


class SettlementAccountSerializer(serializers.ModelSerializer):
    linked_bank_account_name = serializers.CharField(source='linked_bank_account.name', read_only=True, allow_null=True)

    class Meta:
        from .models import SettlementAccount
        model = SettlementAccount
        fields = ('provider', 'settlement_frequency', 'linked_bank_account', 'linked_bank_account_name')


class FinancialAccountSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True, allow_null=True)
    cash_detail = CashAccountSerializer(read_only=True)
    wallet_detail = WalletAccountSerializer(read_only=True)
    settlement_detail = SettlementAccountSerializer(read_only=True)
    bank_detail = serializers.SerializerMethodField()

    class Meta:
        from .models import FinancialAccount
        model = FinancialAccount
        fields = (
            'id', 'account_name', 'account_class', 'account_type',
            'balance', 'status', 'group', 'group_name',
            'cash_detail', 'wallet_detail', 'settlement_detail', 'bank_detail',
            'created_at', 'updated_at'
        )

    def get_bank_detail(self, obj):
        if obj.account_class == 'bank' and hasattr(obj, 'bank_account_detail') and obj.bank_account_detail:
            ba = obj.bank_account_detail
            unprocessed = ba.transactions.filter(status='unprocessed').count()
            last_txn = ba.transactions.order_by('-date').values_list('date', flat=True).first()
            return {
                'bank_name': ba.bank_name,
                'account_number': ba.account_number,
                'ifsc': ba.ifsc,
                'branch': ba.branch,
                'currency': ba.currency,
                'opening_balance': float(ba.opening_balance),
                'unprocessed_count': unprocessed,
                'last_transaction_date': str(last_txn) if last_txn else None,
            }
        return None


class AccountActivityLogSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.account_name', read_only=True)

    class Meta:
        from .models import AccountActivityLog
        model = AccountActivityLog
        fields = ('id', 'account', 'account_name', 'action', 'details', 'performed_by', 'created_at')


class ReconciliationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import ReconciliationRule
        model = ReconciliationRule
        fields = ('id', 'rule_name', 'priority', 'confidence_score', 'is_active', 'created_at')


class ReconciliationMatchSerializer(serializers.ModelSerializer):
    bank_transaction_detail = serializers.SerializerMethodField()
    journal_item_detail = serializers.SerializerMethodField()

    class Meta:
        from .models import ReconciliationMatch
        model = ReconciliationMatch
        fields = (
            'id', 'bank_transaction', 'bank_transaction_detail',
            'journal_item', 'journal_item_detail', 'confidence_score',
            'match_method', 'status', 'matched_by', 'matched_at'
        )

    def get_bank_transaction_detail(self, obj):
        tx = obj.bank_transaction
        return {
            'id': tx.id,
            'date': str(tx.date),
            'reference': tx.reference,
            'amount': float(tx.amount),
            'debit': float(tx.debit),
            'credit': float(tx.credit),
            'description': tx.description
        }

    def get_journal_item_detail(self, obj):
        if not obj.journal_item:
            return None
        ji = obj.journal_item
        return {
            'id': ji.id,
            'date': str(ji.entry.date),
            'voucher': f'JV #{ji.entry.id}',
            'ledger_account': ji.ledger.name,
            'amount': float(ji.debit or ji.credit),
            'debit': float(ji.debit),
            'credit': float(ji.credit),
            'type': 'debit' if ji.debit > 0 else 'credit',
            'description': ji.entry.description or ji.notes or '',
            'ref_id': ji.ref_id,
            'vendor_payee': ji.vendor_payee
        }


class ReconciliationExceptionSerializer(serializers.ModelSerializer):
    bank_transaction_detail = serializers.SerializerMethodField()
    assigned_to_name = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)

    class Meta:
        from .models import ReconciliationException
        model = ReconciliationException
        fields = (
            'id', 'bank_transaction', 'bank_transaction_detail',
            'exception_type', 'status', 'severity', 'assigned_to', 'assigned_to_name', 'notes', 'created_at'
        )

    def get_bank_transaction_detail(self, obj):
        tx = obj.bank_transaction
        return {
            'id': tx.id,
            'date': str(tx.date),
            'reference': tx.reference,
            'amount': float(tx.amount),
            'debit': float(tx.debit),
            'credit': float(tx.credit),
            'description': tx.description
        }


class DuplicateCandidateSerializer(serializers.ModelSerializer):
    transaction_1_detail = serializers.SerializerMethodField()
    transaction_2_detail = serializers.SerializerMethodField()

    class Meta:
        from .models import DuplicateCandidate
        model = DuplicateCandidate
        fields = ('id', 'transaction_1', 'transaction_1_detail', 'transaction_2', 'transaction_2_detail', 'similarity_score', 'status', 'created_at')

    def get_transaction_detail(self, tx):
        if not tx:
            return None
        return {
            'id': tx.id,
            'date': str(tx.date),
            'reference': tx.reference,
            'amount': float(tx.amount),
            'debit': float(tx.debit),
            'credit': float(tx.credit),
            'description': tx.description
        }

    def get_transaction_1_detail(self, obj):
        return self.get_transaction_detail(obj.transaction_1)

    def get_transaction_2_detail(self, obj):
        return self.get_transaction_detail(obj.transaction_2)


class RiskAlertSerializer(serializers.ModelSerializer):
    bank_transaction_detail = serializers.SerializerMethodField()

    class Meta:
        from .models import RiskAlert
        model = RiskAlert
        fields = ('id', 'bank_transaction', 'bank_transaction_detail', 'risk_type', 'risk_score', 'status', 'notes', 'created_at')

    def get_bank_transaction_detail(self, obj):
        tx = obj.bank_transaction
        return {
            'id': tx.id,
            'date': str(tx.date),
            'reference': tx.reference,
            'amount': float(tx.amount),
            'debit': float(tx.debit),
            'credit': float(tx.credit),
            'description': tx.description
        }


class ReconciliationAuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, allow_null=True)

    class Meta:
        from .models import ReconciliationAuditLog
        model = ReconciliationAuditLog
        fields = ('id', 'user', 'username', 'action', 'entity_type', 'entity_id', 'notes', 'created_at')


# ---------------------------------------------------------------------------
# Asset Management Serializers
# ---------------------------------------------------------------------------

class AssetAuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import AssetAuditLog
        model = AssetAuditLog
        fields = ('id', 'asset', 'action', 'performed_by', 'notes', 'created_at')


class AssetAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import AssetAssignment
        model = AssetAssignment
        fields = ('id', 'asset', 'assigned_to', 'department', 'assigned_date', 'returned_date', 'notes', 'is_active', 'created_at')


class AssetDepreciationSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import AssetDepreciation
        model = AssetDepreciation
        fields = ('id', 'asset', 'period_month', 'period_year', 'depreciation_amount',
                  'book_value_before', 'book_value_after', 'method', 'journal_entry', 'created_at')


class AssetDisposalSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import AssetDisposal
        model = AssetDisposal
        fields = ('id', 'asset', 'disposal_date', 'method', 'sale_proceeds',
                  'book_value_at_disposal', 'gain_loss', 'notes', 'journal_entry', 'created_at')


class AssetSerializer(serializers.ModelSerializer):
    current_assignment = serializers.SerializerMethodField()
    depreciations_count = serializers.SerializerMethodField()

    class Meta:
        from .models import Asset
        model = Asset
        fields = (
            'id', 'asset_code', 'name', 'category', 'description',
            'serial_number', 'vendor', 'location', 'department',
            'purchase_date', 'purchase_cost', 'salvage_value',
            'useful_life_years', 'depreciation_method', 'depreciation_rate',
            'current_value', 'accumulated_depreciation', 'last_depreciation_date',
            'status', 'current_assignment', 'depreciations_count',
            'created_at', 'updated_at',
        )

    def get_current_assignment(self, obj):
        assignment = obj.assignments.filter(is_active=True).first()
        if assignment:
            return {
                'id': assignment.id,
                'assigned_to': assignment.assigned_to,
                'department': assignment.department,
                'assigned_date': str(assignment.assigned_date),
            }
        return None

    def get_depreciations_count(self, obj):
        return obj.depreciations.count()


class AssetCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    category = serializers.ChoiceField(choices=['computer', 'furniture', 'vehicle', 'machinery', 'building', 'other'])
    description = serializers.CharField(required=False, allow_blank=True, default='')
    serial_number = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    vendor = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    location = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    department = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    purchase_date = serializers.DateField()
    purchase_cost = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0.01'))
    salvage_value = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), min_value=Decimal('0'))
    useful_life_years = serializers.IntegerField(default=5, min_value=1)
    depreciation_method = serializers.ChoiceField(choices=['slm', 'wdv'], default='slm')
    depreciation_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'), min_value=Decimal('0'))


class AssetDisposalCreateSerializer(serializers.Serializer):
    disposal_date = serializers.DateField()
    method = serializers.ChoiceField(choices=['sold', 'scrapped', 'donated', 'stolen', 'replaced'])
    sale_proceeds = serializers.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'), min_value=Decimal('0'))
    notes = serializers.CharField(required=False, allow_blank=True, default='')


