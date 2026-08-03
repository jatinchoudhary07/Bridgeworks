from rest_framework import serializers

from core.models import FinanceOption, FinanceTransaction


class FinanceTransactionSerializer(serializers.ModelSerializer):
    receipt_url = serializers.SerializerMethodField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = FinanceTransaction
        fields = [
            'id',
            'entry_type',
            'entry_date',
            'particular',
            'department',
            'sub_department',
            'category',
            'nature',
            'payment_type',
            'bank_name',
            'account_number',
            'reference_id',
            'invoice_no',
            'amount',
            'vendor_payee',
            'bill_due_date',
            'approval_workflow',
            'cost_centre',
            'tds_section',
            'status',
            'notes',
            'receipt',
            'receipt_url',
            'total_amount',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'receipt_url', 'total_amount', 'created_at', 'updated_at']

    def validate(self, attrs):
        entry_type = attrs.get('entry_type') or getattr(self.instance, 'entry_type', None)
        payment_type = (attrs.get('payment_type') or getattr(self.instance, 'payment_type', '')).strip()

        if payment_type in {'Bank Transfer', 'Cheque', 'DD'}:
            bank_name = attrs.get('bank_name') if 'bank_name' in attrs else getattr(self.instance, 'bank_name', '')
            account_number = attrs.get('account_number') if 'account_number' in attrs else getattr(self.instance, 'account_number', '')
            if not bank_name or not account_number:
                raise serializers.ValidationError({'bank_name': 'Bank name and account number are required for selected payment type.'})

        if entry_type == 'income':
            attrs.setdefault('vendor_payee', '')
            attrs.setdefault('approval_workflow', '')
            attrs.setdefault('cost_centre', '')
            attrs.setdefault('tds_section', '')

        return attrs

    def get_receipt_url(self, obj):
        request = self.context.get('request')
        if not obj.receipt:
            return None
        try:
            url = obj.receipt.url
            return request.build_absolute_uri(url) if request else url
        except Exception:
            return None

    def get_total_amount(self, obj):
        return obj.amount or 0


class FinanceOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceOption
        fields = [
            'id',
            'option_type',
            'value',
            'parent_value',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        option_type = attrs.get('option_type') or getattr(self.instance, 'option_type', '')
        value = (attrs.get('value') if 'value' in attrs else getattr(self.instance, 'value', '')).strip()
        parent_value = (attrs.get('parent_value') if 'parent_value' in attrs else getattr(self.instance, 'parent_value', '')).strip()

        if not value:
            raise serializers.ValidationError({'value': 'Option value is required.'})

        if option_type == 'sub_department' and not parent_value:
            raise serializers.ValidationError({'parent_value': 'Parent department is required for sub-department.'})

        attrs['value'] = value
        attrs['parent_value'] = parent_value if option_type == 'sub_department' else ''
        return attrs
