from rest_framework import serializers
from core.models import (
    Order, LineItem, Fulfillment, TrackingInfo, TrackingEvent, 
    PackagingImage, CaseFile
)


class ConfirmedByUsernameField(serializers.Field):
    def to_representation(self, obj):
        if obj.is_auto_confirmed:
            return "Shori"
        return obj.confirmed_by.username if obj.confirmed_by else None



class SimpleOrderForCaseFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'customer_first_name', 'customer_last_name', 'contact_phone']
        read_only_fields = fields 


class SimpleCaseFileSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    type_display = serializers.CharField(source='get_issue_type_display', read_only=True)

    class Meta:
        model = CaseFile
        fields = [
            'case_number', 'subject', 'status', 'status_display', 
            'issue_type', 'type_display', 'created_at'
        ]


class TrackingInfoSerializer(serializers.ModelSerializer):
    class Meta: 
        model = TrackingInfo
        fields = ['company', 'number', 'url']


class TrackingEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingEvent
        fields = ['status', 'datetime', 'details']


class FulfillmentSerializer(serializers.ModelSerializer):
    tracking_info = TrackingInfoSerializer(many=True, read_only=True)

    class Meta: 
        model = Fulfillment
        fields = ['status', 'shipment_status', 'service', 'created_at', 'tracking_info']


class LineItemSerializer(serializers.ModelSerializer):
    class Meta: 
        model = LineItem
        fields = ['title', 'sku', 'vendor', 'quantity', 'price']


class PackagingImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackagingImage
        fields = ['image', 'uploaded_at']


class OrderSerializer(serializers.ModelSerializer):
    line_items = LineItemSerializer(many=True, read_only=True)
    fulfillments = FulfillmentSerializer(many=True, read_only=True)
    case_files = SimpleCaseFileSerializer(many=True, read_only=True)
    fir_customer_name = serializers.SerializerMethodField()
    tracking_events = serializers.SerializerMethodField()
    
    status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    risk_status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    call_status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    internal_fulfillment_status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    fulfillment_reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    hold_history = serializers.JSONField(required=False)
    packaged_by_username = serializers.CharField(source='packaged_by.username', read_only=True, allow_null=True)
    packaging_images = PackagingImageSerializer(many=True, read_only=True)
    
    confirmed_by_username = ConfirmedByUsernameField(source='*')
    shopify_extra = serializers.SerializerMethodField()
    fulfillment_status = serializers.SerializerMethodField()
    overview_status = serializers.CharField(read_only=True, required=False)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'financial_status', 'fulfillment_status', 'created_at',
            'total_price', 'fir_customer_name', 'customer_first_name', 'customer_last_name', 'contact_phone', 'contact_email',
            'shipping_address', 'billing_address', 'line_items', 
            'fulfillments', 
            'tracking_events', 
            'payment_gateway_names', 'discount_codes', 'tags', 'previous_order_count',
            'status', 'risk_status', 'confirmed_at', 
            'confirmed_by_username',
            'call_attempts', 'last_called_at', 'call_history', 'call_status',
            'internal_fulfillment_status', 'fulfillment_reason', 'hold_history',
            'packaged_by_username', 'packaged_at', 'manifested_at', 'fulfilled_at', 'packaging_images',
            'case_files',
            'current_status', 'current_status_details', 'is_ndr',
            'ndr_call_status', 'ndr_remarks', 'ndr_call_history', 'ndr_last_called_at',
            'shopify_extra',
            'risk_score', 'intelligence_flag', 'system_suggestion', 'agent_reasoning',
            'confirmation_reason', 'hold_reason',
            'overview_status',
            'return_awb', 'return_shipping_company', 'exchange_awb', 'exchange_shipping_company',
            'is_test_order', 'is_auto_confirmed', 'picklist_generated_at', 'awb_error',
        ]

    def get_fir_customer_name(self, obj):
        return f"{obj.customer_first_name or ''} {obj.customer_last_name or ''}".strip() or "N/A"

    def get_fulfillment_status(self, obj):
        status = obj.fulfillment_status or ""
        mapping = {
            "fulfilled": "Fulfilled",
            "Tracking_added": "Tracking Added",
            "tracking_added": "Tracking Added",
            "unfulfilled": "Unfulfilled",
            "null": "Unfulfilled",
            "partial": "Partially Fulfilled",
            "restored": "Restored"
        }
        return mapping.get(status, status.capitalize() if status else "Unfulfilled")

    def get_tracking_events(self, obj):
        fulfillments = getattr(obj, '_prefetched_objects_cache', {}).get('fulfillments')
        if fulfillments is None:
            fulfillments = list(obj.fulfillments.all())
            
        if not fulfillments:
            return []
            
        fulfillments = sorted(fulfillments, key=lambda x: x.id, reverse=True)
        latest_fulfillment = fulfillments[0]
        
        events = getattr(latest_fulfillment, '_prefetched_objects_cache', {}).get('tracking_events')
        if events is None:
            events = list(latest_fulfillment.tracking_events.all())
            
        events = sorted(events, key=lambda x: x.datetime.isoformat() if x.datetime else '', reverse=True)
        return TrackingEventSerializer(events, many=True).data

    def get_shopify_extra(self, obj):
        """Extract useful Shopify sidebar data from raw_data."""
        raw = obj.raw_data or {}
        extra = {}
        note_attrs = raw.get('note_attributes', [])
        if note_attrs:
            extra['note_attributes'] = {attr.get('name', ''): attr.get('value', '') for attr in note_attrs if attr.get('name')}
        if raw.get('note'):
            extra['note'] = raw['note']
        if raw.get('browser_ip'):
            extra['browser_ip'] = raw['browser_ip']
        if raw.get('source_name'):
            extra['source_name'] = raw['source_name']
        if raw.get('landing_site'):
            extra['landing_site'] = raw['landing_site']
        if raw.get('referring_site'):
            extra['referring_site'] = raw['referring_site']
        client_details = raw.get('client_details') or {}
        if client_details.get('user_agent'):
            extra['user_agent'] = client_details['user_agent']
        customer = raw.get('customer', {})
        if customer:
            extra['customer_orders_count'] = customer.get('orders_count', 0)
            extra['customer_total_spent'] = customer.get('total_spent', '0.00')
            if customer.get('email'):
                extra['customer_email'] = customer['email']
            if customer.get('phone'):
                extra['customer_phone'] = customer['phone']
        return extra if extra else None


class MinimalOrderSerializer(serializers.ModelSerializer):
    """
    Ultra-lightweight serializer for AWB Batch list.
    Only includes essential display fields - NO nested relations.
    """
    customer_name = serializers.SerializerMethodField()
    awb_number = serializers.SerializerMethodField()
    courier = serializers.SerializerMethodField()
    confirmed_by_username = ConfirmedByUsernameField(source='*')
    shipping_label_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer_name', 'total_price',
            'status', 'current_status', 'awb_number', 'courier',
            'confirmed_at', 'confirmed_by_username', 'financial_status',
            'is_test_order', 'is_auto_confirmed', 'picklist_generated_at', 'awb_error',
            'shipping_label_url',
        ]
    
    def get_customer_name(self, obj):
        return f"{obj.customer_first_name or ''} {obj.customer_last_name or ''}".strip() or "N/A"
    
    def get_awb_number(self, obj):
        # Use prefetched objects from related manager to avoid N+1 queries
        for f in obj.fulfillments.all():
            for t in f.tracking_info.all():
                return t.number
        return "N/A"
    
    def get_courier(self, obj):
        for f in obj.fulfillments.all():
            for t in f.tracking_info.all():
                return t.company
        return "N/A"

    def get_shipping_label_url(self, obj):
        for f in obj.fulfillments.all():
            for t in f.tracking_info.all():
                return t.url
        return None


class SimpleOrderSerializer(serializers.ModelSerializer):
    customer_full_name = serializers.SerializerMethodField()
    fulfillments = FulfillmentSerializer(many=True, read_only=True)
    line_items = LineItemSerializer(many=True, read_only=True)
    packaged_by_username = serializers.CharField(source='packaged_by.username', read_only=True, allow_null=True)
    hold_history = serializers.JSONField(read_only=True)
    case_files = SimpleCaseFileSerializer(many=True, read_only=True)
    tracking_events = serializers.SerializerMethodField()
    packaging_images = PackagingImageSerializer(many=True, read_only=True)

    confirmed_by_username = ConfirmedByUsernameField(source='*')

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer_full_name', 
            'customer_first_name', 'customer_last_name',
            'contact_phone', 'contact_email',
            'fulfillments', 
            'tracking_events', 
            'line_items',
            'total_price', 'payment_gateway_names', 'financial_status',
            'status', 'internal_fulfillment_status',
            'fulfillment_reason', 'hold_history', 'shipping_address',
            'packaged_by_username', 'packaged_at', 'manifested_at', 'packaging_images',
            'confirmed_by_username', 'confirmed_at',
            'case_files', 
            'current_status', 'current_status_details', 'is_ndr',
            'risk_score', 'intelligence_flag', 'system_suggestion', 'agent_reasoning',
            'confirmation_reason', 'hold_reason',
            'return_awb', 'return_shipping_company', 'exchange_awb', 'exchange_shipping_company',
            'is_test_order', 'is_auto_confirmed', 'picklist_generated_at', 'awb_error',
        ]

    def get_customer_full_name(self, obj):
        return f"{obj.customer_first_name or ''} {obj.customer_last_name or ''}".strip()

    def get_tracking_events(self, obj):
        fulfillments = getattr(obj, '_prefetched_objects_cache', {}).get('fulfillments')
        if fulfillments is None:
            fulfillments = list(obj.fulfillments.all())
            
        if not fulfillments:
            return []
            
        fulfillments = sorted(fulfillments, key=lambda x: x.id, reverse=True)
        latest_fulfillment = fulfillments[0]
        
        events = getattr(latest_fulfillment, '_prefetched_objects_cache', {}).get('tracking_events')
        if events is None:
            events = list(latest_fulfillment.tracking_events.all())
            
        events = sorted(events, key=lambda x: x.datetime.isoformat() if x.datetime else '', reverse=True)
        return TrackingEventSerializer(events, many=True).data


class LightweightConfirmedOrderSerializer(serializers.ModelSerializer):
    confirmed_by_username = ConfirmedByUsernameField(source='*')
    has_awb = serializers.SerializerMethodField()
    customer_full_name = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'confirmed_at', 'confirmed_by_username',
            'is_auto_confirmed', 'is_test_order', 'picklist_generated_at',
            'financial_status', 'customer_full_name', 'customer_first_name', 'customer_last_name',
            'total_price', 'status', 'has_awb', 'awb_error'
        ]

    def get_customer_full_name(self, obj):
        return f"{obj.customer_first_name or ''} {obj.customer_last_name or ''}".strip() or "N/A"

    def get_has_awb(self, obj):
        fulfillments = getattr(obj, '_prefetched_objects_cache', {}).get('fulfillments', [])
        if not fulfillments:
            fulfillments = list(obj.fulfillments.all())
        for f in fulfillments:
            tracking = getattr(f, '_prefetched_objects_cache', {}).get('tracking_info', [])
            if not tracking:
                tracking = list(f.tracking_info.all())
            for t in tracking:
                if t.number and t.number.strip():
                    return True
        return False

