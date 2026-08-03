from rest_framework import serializers
from django.contrib.auth import get_user_model
from core.models import WholesaleLead, AbandonedCart, Quotation
from core.models.sales import (
    RetailStore, RetailStoreCustomer,
    ChannelDraftOrder, ChannelAbandonedCheckout,
    MarketplaceCustomer,
    QuotationVersion, QuotationTimeline, QuotationApprovalHistory, QuotationEmailLog,
)

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name']

    def get_full_name(self, obj):
        if obj.first_name or obj.last_name:
            return f"{obj.first_name} {obj.last_name}".strip()
        return obj.username


class WholesaleLeadSerializer(serializers.ModelSerializer):
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)

    class Meta:
        model = WholesaleLead
        fields = '__all__'
        read_only_fields = ['shop', 'created_by', 'created_at', 'updated_at']


class AbandonedCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = AbandonedCart
        fields = '__all__'
        read_only_fields = ['shop', 'created_at']


class RetailStoreSerializer(serializers.ModelSerializer):
    customer_count = serializers.SerializerMethodField()

    class Meta:
        model = RetailStore
        fields = '__all__'
        read_only_fields = ['shop', 'created_at', 'updated_at']

    def get_customer_count(self, obj):
        return obj.customers.count()


class RetailStoreCustomerSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source='store.name', read_only=True)

    class Meta:
        model = RetailStoreCustomer
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class ChannelDraftOrderSerializer(serializers.ModelSerializer):
    total_price = serializers.DecimalField(source='total', max_digits=14, decimal_places=2, read_only=True)
    email = serializers.EmailField(source='customer_email', read_only=True)
    customer = serializers.SerializerMethodField()
    display_created_at = serializers.SerializerMethodField()

    class Meta:
        model = ChannelDraftOrder
        fields = '__all__'
        read_only_fields = ['shop', 'created_by', 'created_at', 'updated_at']

    def get_customer(self, obj):
        parts = (obj.customer_name or "").split(" ", 1)
        return {
            "first_name": parts[0] if len(parts) > 0 else "",
            "last_name": parts[1] if len(parts) > 1 else "",
            "email": obj.customer_email,
            "phone": obj.customer_phone
        }

    def get_display_created_at(self, obj):
        # Prefer shopify_created_at for accurate historical view
        return obj.shopify_created_at or obj.created_at


class ChannelAbandonedCheckoutSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelAbandonedCheckout
        fields = '__all__'
        read_only_fields = ['shop', 'created_at']


class MarketplaceCustomerSerializer(serializers.ModelSerializer):
    platform_display = serializers.CharField(source='get_platform_display', read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = MarketplaceCustomer
        fields = '__all__'
        read_only_fields = ['shop', 'created_at', 'updated_at']


from core.models.sales import WholesaleLeadActivity, WholesaleLeadTask, WholesaleLeadNote
from django.contrib.auth import get_user_model
User = get_user_model()

class UserMinimalSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

class WholesaleLeadActivitySerializer(serializers.ModelSerializer):
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)
    activity_type_display = serializers.CharField(source='get_activity_type_display', read_only=True)

    class Meta:
        model = WholesaleLeadActivity
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at']

class WholesaleLeadTaskSerializer(serializers.ModelSerializer):
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)
    assignee_details = UserMinimalSerializer(source='assignee', read_only=True)

    class Meta:
        model = WholesaleLeadTask
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at']

class WholesaleLeadNoteSerializer(serializers.ModelSerializer):
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)

    class Meta:
        model = WholesaleLeadNote
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at', 'updated_at']


class QuotationVersionSerializer(serializers.ModelSerializer):
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)

    class Meta:
        model = QuotationVersion
        fields = '__all__'


class QuotationTimelineSerializer(serializers.ModelSerializer):
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)

    class Meta:
        model = QuotationTimeline
        fields = '__all__'


class QuotationApprovalHistorySerializer(serializers.ModelSerializer):
    action_by_details = UserMinimalSerializer(source='action_by', read_only=True)

    class Meta:
        model = QuotationApprovalHistory
        fields = '__all__'


class QuotationEmailLogSerializer(serializers.ModelSerializer):
    sent_by_details = UserMinimalSerializer(source='sent_by', read_only=True)

    class Meta:
        model = QuotationEmailLog
        fields = '__all__'


class QuotationSerializer(serializers.ModelSerializer):
    timeline = QuotationTimelineSerializer(many=True, read_only=True)
    versions = QuotationVersionSerializer(many=True, read_only=True)
    approvals = QuotationApprovalHistorySerializer(many=True, read_only=True)
    emails = QuotationEmailLogSerializer(many=True, read_only=True)
    created_by_details = UserMinimalSerializer(source='created_by', read_only=True)

    class Meta:
        model = Quotation
        fields = '__all__'
        read_only_fields = ['shop', 'created_by', 'created_at', 'updated_at', 'version']


# --- SALES & BD MODULE SERIALIZERS (DAY 1) ---
from core.models.sales import (
    SalesRepresentative, SalesActivity, SalesActivityProduct,
    IncentiveRule, IncentiveRecord
)

class SalesRepresentativeSerializer(serializers.ModelSerializer):
    user_details = UserMinimalSerializer(source='user', read_only=True)
    reporting_manager_name = serializers.CharField(source='reporting_manager.full_name', read_only=True)

    class Meta:
        model = SalesRepresentative
        fields = '__all__'
        read_only_fields = ['shop', 'created_at', 'updated_at']


class SalesActivityProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesActivityProduct
        fields = ['id', 'product_id', 'product_name', 'quantity', 'unit_price', 'total_amount', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class SalesActivitySerializer(serializers.ModelSerializer):
    products = SalesActivityProductSerializer(many=True, required=False)
    sales_rep_name = serializers.CharField(source='sales_rep.full_name', read_only=True)
    approved_by_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    invoice_url = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()

    class Meta:
        model = SalesActivity
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            name = f"{obj.approved_by.first_name} {obj.approved_by.last_name}".strip()
            return name or obj.approved_by.username
        return None

    def get_image_url(self, obj):
        try:
            if obj.image_file:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.image_file.url)
                return obj.image_file.url
        except Exception:
            pass
        return None

    def get_invoice_url(self, obj):
        try:
            if obj.invoice_file:
                request = self.context.get('request')
                if request:
                    return request.build_absolute_uri(obj.invoice_file.url)
                return obj.invoice_file.url
        except Exception:
            pass
        return None

    def get_total_value(self, obj):
        try:
            return float(sum(p.total_amount for p in obj.products.all()))
        except Exception:
            return 0.0

    def to_internal_value(self, data):
        import json as _json
        # Handle products and activities_performed sent as JSON strings (from FormData/multipart)
        mutable = data.copy() if hasattr(data, 'copy') else dict(data)
        for field in ('products', 'activities_performed'):
            val = mutable.get(field)
            if isinstance(val, str):
                try:
                    mutable[field] = _json.loads(val)
                except Exception:
                    mutable[field] = []
        return super().to_internal_value(mutable)

    def create(self, validated_data):
        products_data = validated_data.pop('products', [])
        activity = SalesActivity.objects.create(**validated_data)
        for prod in products_data:
            SalesActivityProduct.objects.create(sales_activity=activity, **prod)
        return activity

    def update(self, instance, validated_data):
        products_data = validated_data.pop('products', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if products_data is not None:
            instance.products.all().delete()
            for prod in products_data:
                SalesActivityProduct.objects.create(sales_activity=instance, **prod)
        return instance


class IncentiveRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncentiveRule
        fields = '__all__'
        read_only_fields = ['shop', 'created_at', 'updated_at']


class IncentiveRecordSerializer(serializers.ModelSerializer):
    sales_rep_name = serializers.CharField(source='sales_rep.full_name', read_only=True)
    rule_name = serializers.CharField(source='rule.rule_name', read_only=True)
    activity_customer = serializers.CharField(source='sales_activity.customer_name', read_only=True, default='')

    class Meta:
        model = IncentiveRecord
        fields = '__all__'
        read_only_fields = ['calculated_at', 'created_at', 'updated_at']



