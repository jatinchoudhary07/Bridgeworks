from core.models import ShopifyCustomApp
from django.contrib import admin
from .models import (
    PaymentMethodRule,
    Order, LineItem, Fulfillment, TrackingInfo, Batch, PackagingBatch,
    PackagingImage, ShopCredentials, TeamMemberSettings, TrackingEvent,
    NDREscalationBatch,
    UserProfile, Invitation, CaseFile, IssueComment, CaseFileImage, StickyNote, RTOBatch,
    PostItComment, PostItNotification, AgentConfiguration, Customer,
    DiaryEntry, DiaryAttachment,
    MarketingCredential, CampaignDailyMetric,
    GoogleAdsCredential, GoogleCampaignDailyMetric,
    GoogleAdsCredential, GoogleCampaignDailyMetric,
    UnifiedNotification, ChannelDraftOrder, RTOEngineItem,
    ReturnExchangeCase, ReturnExchangeActivity, ReturnExchangeBatch,
)


# ==============================================================================
# 1. ShopCredentials Admin (The Organization)
# ==============================================================================

@admin.register(ShopCredentials)
class ShopCredentialsAdmin(admin.ModelAdmin):
    list_display = (
        'owner', 
        'organization_id', 
        'display_shop_url', 
        'onboarding_complete'
    )
    search_fields = ('owner__email', 'organization_id')
    raw_id_fields = ('owner',)
    
    readonly_fields = (
        'shopify_api_key_encrypted', 'shopify_api_password_encrypted', 
        'shopify_shop_url_encrypted', 'shopify_webhook_secret_encrypted',
        'shopify_access_token_encrypted',
        'shipway_email_encrypted', 'shipway_license_key_encrypted',
        'return_prime_token_encrypted',
        'organization_id',
    )
    
    fieldsets = (
        (None, {'fields': ('owner', 'organization_id', 'onboarding_complete', 'myshopify_domain')}),
        ('SHOPIFY CONFIGURATION', {'fields': ('shopify_order_prefix', 'shopify_api_version')}),
        ('BLUE DART CONFIGURATION', {'fields': (
            'bluedart_api_type', 'bluedart_client_id', 'bluedart_client_secret', 
            'bluedart_login_id', 'bluedart_licence_key', 'bluedart_jwt_token', 'bluedart_jwt_expiry'
        )}),
        
        ('ENCRYPTED SHOPIFY KEYS (DO NOT EDIT)', {
            'fields': (
                'shopify_shop_url_encrypted', 'shopify_api_key_encrypted', 
                'shopify_api_password_encrypted', 'shopify_webhook_secret_encrypted',
                'shopify_access_token_encrypted'
            ),
            'classes': ('collapse', 'wide')
        }),
        ('ENCRYPTED SHIPWAY KEYS', {
            'fields': (
                'shipway_email_encrypted', 'shipway_license_key_encrypted'
            ),
            'classes': ('collapse', 'wide')
        }),
        ('SHIPWAY CONFIGURATION DETAILS', {
            'fields': (
                'shipway_warehouse_id', 'shipway_return_warehouse_id',
                'shipway_order_weight', 'shipway_box_length', 'shipway_box_breadth', 'shipway_box_height',
                'shipway_invoice_number_prefix',
                'shipway_primary_carrier_id', 'shipway_primary_carrier_title',
                'shipway_fallback_carrier_id', 'shipway_fallback_carrier_title',
                'shipway_store_code', 'skip_shipway_pii_sync'
            ),
        }),
        ('RETURN PRIME', {
            'fields': (
                'return_prime_token_encrypted',
            ),
            'classes': ('collapse', 'wide')
        }),
    )

    def display_shop_url(self, obj):
        return obj.get_shopify_shop_url()
    display_shop_url.short_description = 'Shop URL'


# ==============================================================================
# 2. Granular Permissions Admin (Team Member Settings)
# ==============================================================================
@admin.register(TeamMemberSettings)
class TeamMemberSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_organization_id', 'role', 'subscribe_picklist_email', 'display_permissions_summary')
    list_editable = ('subscribe_picklist_email',)
    list_filter = ('organization__organization_id', 'role', 'subscribe_picklist_email')
    search_fields = ('user__username', 'user__email', 'organization__organization_id')
    raw_id_fields = ('user', 'organization')
    
    fields = ('user', 'organization', 'role', 'subscribe_picklist_email', 'granular_permissions')

    def get_organization_id(self, obj):
        if obj.organization:
            return obj.organization.organization_id
        return "---"
    get_organization_id.short_description = 'Organization'

    def display_permissions_summary(self, obj):
        enabled = [
            f'{area}.{feat}' for area, feats in obj.granular_permissions.items() 
            for feat, enabled_status in feats.items() if enabled_status
        ]
        if not enabled:
            return "No specific permissions set."
        return ", ".join(enabled)
    display_permissions_summary.short_description = 'Enabled Features'


# ==============================================================================
# 3. Inline Definitions and Main Model Registrations
# ==============================================================================

class LineItemInline(admin.TabularInline):
    model = LineItem
    extra = 0
    readonly_fields = ('title', 'sku', 'quantity', 'price') 

class FulfillmentInline(admin.TabularInline):
    model = Fulfillment
    extra = 0

class TrackingInfoInline(admin.StackedInline): # Stacked looks better for single items
    model = TrackingInfo
    extra = 0

class PackagingImageInline(admin.TabularInline):
    model = PackagingImage
    extra = 0
    readonly_fields = ('image', 'uploaded_at')

# --- NEW INLINE FOR SCAN HISTORY ---
class TrackingEventInline(admin.TabularInline):
    model = TrackingEvent
    extra = 0
    readonly_fields = ('status', 'datetime', 'details')
    can_delete = False 
    ordering = ('-datetime',)

# --- NEW INLINES FOR CASE FILES ---
class IssueCommentInline(admin.TabularInline):
    model = IssueComment
    extra = 0
    readonly_fields = ('user', 'created_at')

class CaseFileImageInline(admin.TabularInline):
    model = CaseFileImage
    extra = 0
    readonly_fields = ('uploaded_at',)

# --- RTO ENGINE ITEM INLINE ---
class RTOEngineItemInline(admin.TabularInline):
    model = RTOEngineItem
    extra = 0
    raw_id_fields = ('line_item',)
    readonly_fields = ('scanned_at', 'scanned_by', 'qc_at', 'qc_by', 'created_at', 'updated_at')
    fields = ('line_item', 'scan_status', 'scanned_by', 'scanned_at', 'qc_by', 'qc_at', 'qc_notes', 'investigation_notes', 'investigation_status', 'write_off_reason')
    show_change_link = True

# -----------------------------------

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'org_id', 'status', 'current_status_date', 'internal_fulfillment_status', 'rto_internal_status', 'total_price', 'confirmed_at', 'is_test_order', 'is_auto_confirmed')
    raw_id_fields = ('rto_batch', 'packaged_by', 'confirmed_by', 'parent_order')
    readonly_fields = ('current_status_date',)
    list_filter = ('status', 'internal_fulfillment_status', 'rto_internal_status', 'org_id', 'is_ndr', 'is_test_order', 'is_auto_confirmed')
    search_fields = ('order_number', 'customer_first_name', 'customer_last_name', 'contact_phone', 'fulfillment_status')
    inlines = [LineItemInline, FulfillmentInline, PackagingImageInline, RTOEngineItemInline]

    fieldsets = (
        (None, {'fields': ('org_id', 'order_number', 'shopify_id', 'status', 'internal_fulfillment_status', 'is_test_order', 'source', 'marketplace_platform')}),
        ('Customer Info & Address', {'fields': ('customer_first_name', 'customer_last_name', 'contact_phone', 'contact_email', 'shipping_address', 'shipping_state', 'shipping_pincode', 'billing_address', 'tags')}),
        ('Financials', {'fields': ('total_price', 'subtotal_price', 'total_discounts', 'financial_status', 'fulfillment_status')}),
        ('Operational Stats & Timeline', {'fields': ('risk_status', 'call_attempts', 'last_called_at', 'confirmed_by', 'confirmed_at', 'fulfillment_reason', 'packaged_by', 'packaged_at', 'manifested_at', 'is_auto_confirmed', 'picklist_generated_at', 'previous_order_count', 'awb_error')}),
        ('AI Intelligence', {'fields': ('risk_score', 'intelligence_flag', 'system_suggestion', 'agent_reasoning', 'confirmation_reason', 'hold_reason')}),
        ('NDR & Call Center Details', {'fields': ('is_ndr', 'ndr_call_status', 'ndr_remarks', 'ndr_call_history', 'ndr_last_called_at', 'ndr_call_attempts', 'ndr_reason_category', 'ndr_classification_confidence', 'ndr_conversion_status', 'ndr_rto_risk_score', 'ndr_last_scan_time', 'ndr_escalation_status', 'ndr_escalation_count')}),
        ('Reverse Logistics (RTO)', {'fields': ('rto_internal_status', 'rto_batch', 'rto_received_at', 'rto_restocked_at', 'rto_remarks', 'return_awb', 'return_shipping_company', 'exchange_awb', 'exchange_shipping_company', 'parent_order', 'is_exchange_order')}),
        ('Tracking & Status', {'fields': ('current_status', 'current_status_details', 'current_status_date')}),
        ('Raw Data', {'fields': ('raw_data',), 'classes': ('collapse',)})
    )


@admin.register(Fulfillment)
class FulfillmentAdmin(admin.ModelAdmin):
    # --- Updated Inlines ---
    inlines = [TrackingInfoInline, TrackingEventInline] # Added TrackingEventInline here
    # -----------------------
    list_display = ('id', 'order', 'status', 'shipment_status', 'created_at') # Added 'id' and 'created_at' for easier debugging
    raw_id_fields = ('order',)
    list_filter = ('status', 'shipment_status')
    search_fields = ('order__order_number', 'shopify_id')


# Register the simpler models using the standard method
admin.site.register(TrackingInfo)

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at', 'created_by')
    search_fields = ('name',)
    raw_id_fields = ('orders',)

@admin.register(PackagingBatch)
class PackagingBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'assigned_to', 'created_at')
    raw_id_fields = ('orders', 'assigned_to')

@admin.register(ChannelDraftOrder)
class ChannelDraftOrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'channel', 'shopify_draft_id', 'customer_name', 'total', 'status', 'payment_mode', 'created_at')
    list_filter = ('channel', 'status', 'payment_mode')
    search_fields = ('shopify_draft_id', 'customer_name', 'customer_email', 'customer_phone')
    readonly_fields = ('created_at', 'updated_at')


# ==============================================================================
# 4. NEW MODEL REGISTRATIONS
# ==============================================================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'phone', 'location')
    search_fields = ('user__username', 'user__email', 'full_name', 'phone')

@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'org_id', 'sent_by', 'accepted_user', 'created_at')
    list_filter = ('org_id',)
    search_fields = ('email', 'org_id')

@admin.register(CaseFile)
class CaseFileAdmin(admin.ModelAdmin):
    list_display = ('case_number', 'subject', 'status', 'priority', 'issue_type', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority', 'issue_type')
    search_fields = ('case_number', 'subject', 'description', 'order__order_number')
    inlines = [IssueCommentInline, CaseFileImageInline]
    
@admin.register(IssueComment)
class IssueCommentAdmin(admin.ModelAdmin):
    list_display = ('case', 'user', 'short_message', 'is_internal_note', 'created_at')
    list_filter = ('is_internal_note',)
    
    def short_message(self, obj):
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message

@admin.register(StickyNote)
class StickyNoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'short_content', 'created_by', 'assigned_to', 'is_completed', 'completed_by', 'completed_at', 'sent_by', 'shared_with_names', 'is_deleted', 'color')
    list_filter = ('is_completed', 'is_deleted', 'created_by', 'assigned_to', 'completed_by')
    search_fields = ('content', 'created_by__username', 'assigned_to__username', 'shared_with_names')
    list_editable = ('is_deleted',)  # Quick toggle for soft-delete from admin
    ordering = ('-created_at',)

    def short_content(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content

@admin.register(RTOBatch)
class RTOBatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_by', 'created_at')
    list_filter = ('status',)
    search_fields = ('name',)



@admin.register(RTOEngineItem)
class RTOEngineItemAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'get_order_number', 'get_product_name', 'scan_status',
        'scanned_by', 'scanned_at', 'qc_by', 'qc_at', 'investigation_status', 'write_off_reason'
    )
    list_filter = ('scan_status', 'investigation_status', 'write_off_reason', 'scanned_at', 'qc_at')
    search_fields = ('order__order_number', 'scan_notes', 'qc_notes', 'investigation_notes', 'line_item__title', 'line_item__sku')
    raw_id_fields = ('order', 'line_item', 'scanned_by', 'qc_by', 'resolved_by')
    readonly_fields = ('scanned_at', 'created_at', 'updated_at')
    ordering = ('-scanned_at',)
    date_hierarchy = 'scanned_at'
    list_per_page = 50

    fieldsets = (
        ('Order & Item', {
            'fields': ('order', 'line_item')
        }),
        ('Scan Info', {
            'fields': ('scan_status', 'scanned_by', 'scanned_at', 'scan_notes')
        }),
        ('QC Info', {
            'fields': ('qc_by', 'qc_at', 'qc_notes')
        }),
        ('Investigation', {
            'fields': ('investigation_notes', 'investigation_status', 'resolved_by', 'resolved_at'),
            'classes': ('collapse',)
        }),
        ('Others / Write-off', {
            'fields': ('write_off_reason',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_order_number(self, obj):
        return obj.order.order_number if obj.order else '—'
    get_order_number.short_description = 'Order #'
    get_order_number.admin_order_field = 'order__order_number'

    def get_product_name(self, obj):
        if obj.line_item:
            return obj.line_item.title[:50]
        return '—'
    get_product_name.short_description = 'Product'


@admin.register(PostItComment)
class PostItCommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'note', 'user', 'short_text', 'created_at')
    list_filter = ('user',)
    search_fields = ('text',)
    ordering = ('-created_at',)

    def short_text(self, obj):
        return obj.text[:60] + '...' if len(obj.text) > 60 else obj.text


@admin.register(PostItNotification)
class PostItNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'sender', 'short_message', 'is_read', 'created_at')
    list_filter = ('is_read', 'recipient', 'sender')
    search_fields = ('message',)
    ordering = ('-created_at',)

    def short_message(self, obj):
        return obj.message[:60] + '...' if len(obj.message) > 60 else obj.message


@admin.register(UnifiedNotification)
class UnifiedNotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'recipient', 'actor', 'module', 'action', 'short_message', 'is_read', 'created_at')
    list_filter = ('is_read', 'module', 'action')
    search_fields = ('message', 'title', 'recipient__username', 'actor__username')
    ordering = ('-created_at',)

    def short_message(self, obj):
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message


class DiaryAttachmentInline(admin.TabularInline):
    model = DiaryAttachment
    extra = 0
    readonly_fields = ('file', 'original_name', 'mime_type', 'file_size', 'created_at')


@admin.register(DiaryEntry)
class DiaryEntryAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'user', 'created_at', 'updated_at')
    search_fields = ('title', 'note', 'user__username', 'user__email')
    list_filter = ('created_at',)
    ordering = ('-created_at',)
    inlines = [DiaryAttachmentInline]

@admin.register(PaymentMethodRule)
class PaymentMethodRuleAdmin(admin.ModelAdmin):
    list_display = ('gateway_name', 'payment_type')
    list_filter = ('payment_type',)
    search_fields = ('gateway_name',)


@admin.register(AgentConfiguration)
class AgentConfigurationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    fieldsets = (
        (None, {'fields': ('name', 'is_active')}),
        ('AI System Prompt', {
            'fields': ('system_prompt',),
            'description': 'Edit the prompt below to change the AI agent behavior without deploying code.'
        }),
    )

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone', 'email', 'total_orders', 'total_spent', 'delivered_orders', 'rto_orders', 'cancelled_orders', 'created_at')
    list_filter = ('org_id',)
    search_fields = ('name', 'phone', 'email')
    readonly_fields = ('total_orders', 'total_spent', 'delivered_orders', 'rto_orders', 'cancelled_orders')
    change_list_template = "admin/customer_changelist.html"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('upload-customers/', self.admin_site.admin_view(self.upload_customers), name='customer-upload'),
        ]
        return custom_urls + urls

    def upload_customers(self, request):
        from django.db import transaction
        from django.contrib import messages
        from django.http import HttpResponseRedirect
        from decimal import Decimal
        import pandas as pd
        from core.models import Customer, Order, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES
        from django.db.models import Q, Count

        # Resolve default user org_id
        default_org_id = 'janki-jewels'
        if hasattr(request.user, 'shop_credentials'):
            default_org_id = request.user.shop_credentials.organization_id
        elif hasattr(request.user, 'team_settings') and request.user.team_settings.organization:
            default_org_id = request.user.team_settings.organization.organization_id

        if request.method == "POST":
            org_id = request.POST.get('org_id') or default_org_id
            file_obj = request.FILES.get('file')
            if not file_obj:
                self.message_user(request, "No file uploaded.", level=messages.ERROR)
                return HttpResponseRedirect("../")

            try:
                filename = file_obj.name.lower()
                if filename.endswith('.csv'):
                    df = pd.read_csv(file_obj, dtype=str, keep_default_na=False)
                elif filename.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_obj, dtype=str, keep_default_na=False)
                else:
                    self.message_user(request, "Unsupported file format. Must be CSV or Excel (.xlsx/.xls).", level=messages.ERROR)
                    return HttpResponseRedirect("../")

                df.replace('', pd.NA, inplace=True)

                # Check if at least Email or Phone is in columns
                if not ('Email' in df.columns or 'Phone' in df.columns or 'Default Address Phone' in df.columns):
                    self.message_user(
                        request,
                        "Invalid file format. Must contain 'Email', 'Phone', or 'Default Address Phone' columns.",
                        level=messages.ERROR
                    )
                    return HttpResponseRedirect("../")

                def _clean_nan(val):
                    if pd.isna(val):
                        return None
                    return str(val).strip()

                def clean_phone(val):
                    val = _clean_nan(val)
                    if not val:
                        return None
                    s = val.strip("'").strip('"').strip()
                    if not s:
                        return None
                    # Normalize formatting
                    digits = ''.join(filter(str.isdigit, s))
                    if len(digits) == 10:
                        return f"+91{digits}"
                    elif len(digits) > 10:
                        if s.startswith('+'):
                            return s
                        else:
                            return f"+{digits}"
                    return s

                def build_address(row):
                    parts = []
                    for col in ['Default Address Address1', 'Default Address Address2', 'Default Address City', 'Default Address Province Code', 'Default Address Country Code', 'Default Address Zip']:
                        val = _clean_nan(row.get(col))
                        if val:
                            parts.append(val)
                    return ', '.join(parts) if parts else None

                # Query existing customers of this org
                existing_customers = Customer.objects.filter(org_id=org_id)
                existing_by_phone = {}
                existing_by_email = {}

                for c in existing_customers:
                    if c.phone:
                        existing_by_phone[c.phone] = c
                    if c.email:
                        existing_by_email[c.email.lower()] = c

                new_count = 0
                updated_count = 0
                
                creates = []
                updates = []

                # Track duplicates in the CSV itself
                seen_phones = set()
                seen_emails = set()

                for _, row in df.iterrows():
                    first_name = _clean_nan(row.get('First Name')) or ''
                    last_name = _clean_nan(row.get('Last Name')) or ''
                    name = f"{first_name} {last_name}".strip()
                    email = _clean_nan(row.get('Email'))
                    phone = clean_phone(row.get('Phone')) or clean_phone(row.get('Default Address Phone'))
                    address = build_address(row)
                    
                    try:
                        total_orders_val = int(float(row.get('Total Orders', 0)))
                    except:
                        total_orders_val = 0

                    try:
                        total_spent_val = Decimal(str(row.get('Total Spent', '0.00')).replace(',', '').strip() or '0.00')
                    except:
                        total_spent_val = Decimal('0.00')

                    if not email and not phone:
                        continue

                    if email:
                        email = email.lower()

                    if phone and phone in seen_phones:
                        continue
                    if email and email in seen_emails:
                        continue

                    if phone:
                        seen_phones.add(phone)
                    if email:
                        seen_emails.add(email)

                    customer = None
                    if phone and phone in existing_by_phone:
                        customer = existing_by_phone[phone]
                    elif email and email in existing_by_email:
                        customer = existing_by_email[email]

                    if customer:
                        changed = False
                        if name and customer.name != name:
                            customer.name = name
                            changed = True
                        if email and customer.email != email:
                            customer.email = email
                            changed = True
                        if phone and customer.phone != phone:
                            customer.phone = phone
                            changed = True
                        if address and customer.address != address:
                            customer.address = address
                            changed = True
                        if total_orders_val and customer.total_orders != total_orders_val:
                            customer.total_orders = total_orders_val
                            changed = True
                        if total_spent_val and customer.total_spent != total_spent_val:
                            customer.total_spent = total_spent_val
                            changed = True
                            
                        if changed:
                            updates.append(customer)
                            updated_count += 1
                    else:
                        new_cust = Customer(
                            org_id=org_id,
                            name=name or email or 'Unknown',
                            email=email,
                            phone=phone,
                            address=address,
                            total_orders=total_orders_val,
                            total_spent=total_spent_val
                        )
                        creates.append(new_cust)
                        if phone:
                            existing_by_phone[phone] = new_cust
                        if email:
                            existing_by_email[email.lower()] = new_cust
                        new_count += 1

                with transaction.atomic():
                    if creates:
                        Customer.objects.bulk_create(creates, batch_size=2000)
                    if updates:
                        Customer.objects.bulk_update(updates, fields=['name', 'email', 'phone', 'address', 'total_orders', 'total_spent'], batch_size=2000)

                    # Refresh customer maps
                    refreshed_customers = Customer.objects.filter(org_id=org_id)
                    by_phone = {}
                    by_email = {}
                    for c in refreshed_customers:
                        if c.phone:
                            by_phone[c.phone] = c
                        if c.email:
                            by_email[c.email.lower()] = c

                    # Link orders
                    orders = list(Order.objects.filter(org_id=org_id).only('id', 'contact_phone', 'contact_email', 'customer'))
                    linked_count = 0
                    modified_orders = []

                    for order in orders:
                        cust_match = None
                        o_phone = clean_phone(order.contact_phone)
                        o_email = (order.contact_email or '').strip().lower()

                        if o_phone and o_phone in by_phone:
                            cust_match = by_phone[o_phone]
                        elif o_email and o_email in by_email:
                            cust_match = by_email[o_email]

                        if cust_match and order.customer_id != cust_match.id:
                            order.customer = cust_match
                            modified_orders.append(order)
                            linked_count += 1

                    if modified_orders:
                        Order.objects.bulk_update(modified_orders, fields=['customer'], batch_size=2000)

                    # Recalculate customer metrics with distinct order IDs
                    stats = Order.objects.filter(org_id=org_id, customer__isnull=False).values('customer_id').annotate(
                        total=Count('id', distinct=True),
                        delivered=Count('id', filter=Q(status__iexact='Delivered') | Q(current_status__iexact='Delivered') | Q(fulfillments__shipment_status__iexact='Delivered'), distinct=True),
                        rto=Count('id', filter=Q(current_status__in=RTO_TRANSIT_STATUSES) | Q(current_status__in=RTO_DELIVERED_STATUSES) | Q(fulfillments__shipment_status__in=RTO_TRANSIT_STATUSES) | Q(fulfillments__shipment_status__in=RTO_DELIVERED_STATUSES), distinct=True),
                        cancelled=Count('id', filter=Q(status__iexact='Cancelled') | Q(current_status__iexact='Cancelled'), distinct=True)
                    )

                    stats_map = {s['customer_id']: s for s in stats}
                    customers_to_update_metrics = []

                    for c in refreshed_customers:
                        changed = False
                        if c.id in stats_map:
                            cs = stats_map[c.id]
                            tot = max(cs['total'], c.total_orders)
                            if c.total_orders != tot:
                                c.total_orders = tot
                                changed = True
                            if c.delivered_orders != cs['delivered']:
                                c.delivered_orders = cs['delivered']
                                changed = True
                            if c.rto_orders != cs['rto']:
                                c.rto_orders = cs['rto']
                                changed = True
                            if c.cancelled_orders != cs['cancelled']:
                                c.cancelled_orders = cs['cancelled']
                                changed = True
                        else:
                            if c.delivered_orders != 0:
                                c.delivered_orders = 0
                                changed = True
                            if c.rto_orders != 0:
                                c.rto_orders = 0
                                changed = True
                            if c.cancelled_orders != 0:
                                c.cancelled_orders = 0
                                changed = True

                        if changed:
                            customers_to_update_metrics.append(c)

                    if customers_to_update_metrics:
                        Customer.objects.bulk_update(
                            customers_to_update_metrics, 
                            fields=['total_orders', 'delivered_orders', 'rto_orders', 'cancelled_orders'], 
                            batch_size=2000
                        )

                self.message_user(
                    request,
                    f"Successfully processed customers for org '{org_id}': Created {new_count} new, "
                    f"Updated {updated_count} existing. Linked {linked_count} database orders.",
                    level=messages.SUCCESS
                )
                return HttpResponseRedirect("../")

            except Exception as e:
                self.message_user(request, f"Failed to parse or save file: {str(e)}", level=messages.ERROR)
                import traceback
                traceback.print_exc()
                return HttpResponseRedirect("../")

        # GET request: render the form template
        from django.template.response import TemplateResponse
        from core.models import Order
        db_org_ids = list(Order.objects.values_list('org_id', flat=True).distinct())
        if default_org_id not in db_org_ids:
            db_org_ids.append(default_org_id)
        db_org_ids = sorted([o for o in db_org_ids if o])

        context = {
            **self.admin_site.each_context(request),
            'title': 'Upload Shopify Customers',
            'opts': self.model._meta,
            'org_ids': db_org_ids,
            'default_org_id': default_org_id,
            'is_superuser': request.user.is_superuser,
        }
        return TemplateResponse(request, 'admin/customer_upload.html', context)

@admin.register(NDREscalationBatch)
class NDREscalationBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_name', 'escalation_level', 'status', 'get_order_count', 'created_at', 'processed_at')
    list_filter = ('escalation_level', 'status')
    search_fields = ('batch_name',)
    readonly_fields = ('summary',)

    def get_order_count(self, obj):
        return obj.orders.count()
    get_order_count.short_description = 'Orders'

# ==============================================================================
# 5. MARKETING & ANALYTICS
# ==============================================================================

@admin.register(MarketingCredential)
class MarketingCredentialAdmin(admin.ModelAdmin):
    list_display = ('shop', 'platform', 'ad_account_id', 'is_active', 'created_at')
    list_filter = ('platform', 'is_active', 'shop')
    search_fields = ('ad_account_id', 'shop__organization_id')
    readonly_fields = ('access_token_encrypted', 'app_id_encrypted', 'app_secret_encrypted')
    
    fieldsets = (
        (None, {'fields': ('shop', 'platform', 'ad_account_id', 'is_active')}),
        ('ENCRYPTED CREDENTIALS', {
            'fields': ('access_token_encrypted', 'app_id_encrypted', 'app_secret_encrypted'),
            'classes': ('collapse', 'wide')
        }),
    )

@admin.register(CampaignDailyMetric)
class CampaignDailyMetricAdmin(admin.ModelAdmin):
    list_display = ('date', 'campaign_name', 'platform', 'spend', 'revenue', 'roas', 'purchases')
    list_filter = ('date', 'credential__platform')
    search_fields = ('campaign_name', 'campaign_id', 'credential__ad_account_id')
    date_hierarchy = 'date'
    
    def platform(self, obj):
        return obj.credential.platform
    platform.short_description = 'Platform'
    
    def has_add_permission(self, request):
        return False  # Should be populated via background task
        
    def has_change_permission(self, request, obj=None):
        return False  # Read-only historical data

@admin.register(GoogleAdsCredential)
class GoogleAdsCredentialAdmin(admin.ModelAdmin):
    list_display = ('shop', 'customer_id', 'is_active', 'created_at')
    list_filter = ('is_active', 'shop')
    search_fields = ('customer_id', 'login_customer_id', 'client_id', 'shop__organization_id')
    readonly_fields = ('developer_token_encrypted', 'client_secret_encrypted', 'refresh_token_encrypted')

    fieldsets = (
        (None, {'fields': ('shop', 'client_id', 'login_customer_id', 'customer_id', 'is_active')}),
        ('ENCRYPTED CREDENTIALS', {
            'fields': ('developer_token_encrypted', 'client_secret_encrypted', 'refresh_token_encrypted'),
            'classes': ('collapse', 'wide')
        }),
    )

@admin.register(GoogleCampaignDailyMetric)
class GoogleCampaignDailyMetricAdmin(admin.ModelAdmin):
    list_display = ('date', 'campaign_name', 'spend', 'conversions')
    list_filter = ('date',)
    search_fields = ('campaign_name', 'credential__customer_id')
    date_hierarchy = 'date'
    
    def has_add_permission(self, request):
        return False
        
    def has_change_permission(self, request, obj=None):
        return False

from core.models.attribution import OrderAttribution

@admin.register(OrderAttribution)
class OrderAttributionAdmin(admin.ModelAdmin):
    list_display = ('get_order_number', 'channel', 'utm_source', 'utm_campaign', 'matched_platform', 'source', 'backfilled_at')
    list_filter = ('channel', 'source', 'matched_platform')
    search_fields = ('utm_campaign', 'utm_source', 'fbclid', 'gclid', 'order__order_number')
    raw_id_fields = ('order',)
    readonly_fields = ('backfilled_at',)
    date_hierarchy = 'backfilled_at'

    fieldsets = (
        (None, {'fields': ('order', 'channel', 'source', 'backfilled_at')}),
        ('UTM Parameters', {'fields': ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term')}),
        ('Click IDs', {'fields': ('fbclid', 'gclid', 'ttclid')}),
        ('Raw URLs', {'fields': ('landing_page', 'referring_site'), 'classes': ('collapse',)}),
        ('Campaign Match', {'fields': ('matched_campaign_id', 'matched_adset_id', 'matched_ad_id', 'matched_platform')}),
        ('Multi-Touch (Phase 2)', {'fields': ('touch_journey',), 'classes': ('collapse',)}),
    )

    def get_order_number(self, obj):
        return obj.order.order_number
    get_order_number.short_description = 'Order #'

from core.models.pixel import PixelEvent

@admin.register(PixelEvent)
class PixelEventAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'session_id', 'cart_token', 'utm_source', 'utm_campaign', 'ip_address')
    list_filter = ('timestamp', 'utm_source')
    search_fields = ('session_id', 'cart_token', 'utm_campaign', 'ip_address')
    readonly_fields = ('timestamp',)
    date_hierarchy = 'timestamp'


# ==============================================================================
# 6. DELIVERY & LOGISTICS MODULE
# ==============================================================================

from core.models.delivery import (
    Shipment, ShipmentCost, CourierRule, DeliveryPartner, CODRemittance,
    Warehouse, CourierRateCard, RateSlab, CourierSurchargeHistory,
    CourierZoneMapping, CourierInvoiceLine, BillingPattern,
    NDRPlaybook, NDRFraudFlag, ShipmentException,
    PrepaidRemittance, PaymentGatewayFeeRule
)


class ShipmentCostInline(admin.StackedInline):
    model = ShipmentCost
    extra = 0
    readonly_fields = ('true_cost', 'is_overbilled', 'overbilling_amount')


class CODRemittanceInline(admin.TabularInline):
    model = CODRemittance
    extra = 0
    readonly_fields = ('delay_days',)


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = (
        'awb_number', 'courier_partner', 'payment_type', 'current_stage',
        'dispatch_date', 'delivery_date', 'total_delivery_attempts', 'org_id'
    )
    list_filter = ('courier_partner', 'payment_type', 'current_stage', 'zone', 'shipping_mode', 'org_id')
    search_fields = ('awb_number', 'order__order_number')
    raw_id_fields = ('order',)
    inlines = [ShipmentCostInline, CODRemittanceInline]

    fieldsets = (
        (None, {'fields': ('order', 'org_id', 'awb_number')}),
        ('Courier & Shipping', {'fields': ('courier_partner', 'shipping_mode', 'zone', 'weight_slab')}),
        ('Payment', {'fields': ('payment_type', 'payment_status')}),
        ('Lifecycle', {'fields': ('current_stage', 'dispatch_date', 'delivery_date')}),
        ('NDR / Attempts', {'fields': ('total_delivery_attempts', 'first_attempt_date', 'ndr_reason')}),
    )


@admin.register(ShipmentCost)
class ShipmentCostAdmin(admin.ModelAdmin):
    list_display = (
        'get_awb', 'forward_cost', 'rto_cost', 'cod_charges',
        'true_cost', 'is_overbilled', 'overbilling_amount'
    )
    list_filter = ('is_overbilled',)
    search_fields = ('shipment__awb_number',)
    raw_id_fields = ('shipment',)
    readonly_fields = ('true_cost', 'is_overbilled', 'overbilling_amount')

    def get_awb(self, obj):
        return obj.shipment.awb_number
    get_awb.short_description = 'AWB'


@admin.register(CourierRule)
class CourierRuleAdmin(admin.ModelAdmin):
    list_display = ('rule_name', 'condition', 'action_courier_partner', 'priority', 'is_active', 'org_id')
    list_filter = ('condition', 'is_active', 'org_id')
    search_fields = ('rule_name', 'action_courier_partner')


@admin.register(DeliveryPartner)
class DeliveryPartnerAdmin(admin.ModelAdmin):
    list_display = ('name', 'partner_type', 'is_active', 'org_id')
    list_filter = ('partner_type', 'is_active', 'org_id')
    search_fields = ('name',)


@admin.register(CODRemittance)
class CODRemittanceAdmin(admin.ModelAdmin):
    list_display = (
        'get_awb', 'expected_amount', 'received_amount', 'status',
        'delay_days', 'expected_remittance_date', 'actual_remittance_date'
    )
    list_filter = ('status',)
    search_fields = ('shipment__awb_number',)
    raw_id_fields = ('shipment',)
    readonly_fields = ('delay_days',)

    def get_awb(self, obj):
        return obj.shipment.awb_number
    get_awb.short_description = 'AWB'


@admin.register(PrepaidRemittance)
class PrepaidRemittanceAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'gateway_name', 'gross_amount', 'gateway_fee', 'net_amount',
        'status', 'expected_settlement_date', 'actual_settlement_date', 'received_amount'
    )
    list_filter = ('status', 'gateway_name')
    search_fields = ('order_number', 'order__shopify_id')
    raw_id_fields = ('order',)


@admin.register(PaymentGatewayFeeRule)
class PaymentGatewayFeeRuleAdmin(admin.ModelAdmin):
    list_display = ('gateway_name', 'fee_type', 'fee_value', 'active', 'org_id')
    list_filter = ('fee_type', 'active', 'org_id')
    search_fields = ('gateway_name', 'org_id')


# ==============================================================================
# 7. WAREHOUSE, RATE CARDS & SLABS
# ==============================================================================

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'pincode', 'city', 'state', 'is_default', 'is_active', 'org_id')
    list_filter = ('is_default', 'is_active', 'org_id')
    search_fields = ('name', 'pincode', 'city', 'state')
    list_editable = ('is_default', 'is_active')


class RateSlabInline(admin.TabularInline):
    model = RateSlab
    extra = 3
    fields = ('zone', 'weight_from_kg', 'weight_to_kg', 'rate', 'increment_kg')


@admin.register(CourierRateCard)
class CourierRateCardAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'courier_partner', 'shipping_mode', 'pricing_mode',
        'fuel_surcharge_percent', 'caf_percent', 'rto_charge_multiplier', 'is_active', 'org_id'
    )
    list_filter = ('courier_partner', 'shipping_mode', 'pricing_mode', 'is_active', 'org_id')
    search_fields = ('name', 'courier_partner')
    inlines = [RateSlabInline]

    fieldsets = (
        (None, {'fields': ('org_id', 'courier_partner', 'name', 'shipping_mode', 'pricing_mode', 'is_active')}),
        ('Flat Charges', {'fields': (
            'cod_charge_flat', 'cod_charge_percent', 'rto_charge_multiplier', 'ndr_reattempt_charge', 'efss_surcharge_percent'
        )}),
        ('Fuel Surcharge Settings', {'fields': (
            'fuel_surcharge_percent', 'fuel_surcharge_mode', 'fuel_surcharge_offset'
        )}),
        ('CAF Settings', {'fields': (
            'caf_percent', 'caf_mode', 'caf_offset'
        )}),
    )


@admin.register(CourierSurchargeHistory)
class CourierSurchargeHistoryAdmin(admin.ModelAdmin):
    list_display = ('courier_partner', 'effective_date', 'fuel_surcharge', 'caf', 'org_id')
    list_filter = ('courier_partner', 'month_date', 'org_id')
    search_fields = ('courier_partner', 'org_id')
    ordering = ('-month_date',)

    def effective_date(self, obj):
        return obj.month_date
    effective_date.short_description = 'Effective Date'
    effective_date.admin_order_field = 'month_date'

    def fuel_surcharge(self, obj):
        return f"{obj.fuel_surcharge_percent}%"
    fuel_surcharge.short_description = 'Fuel Surcharge'
    fuel_surcharge.admin_order_field = 'fuel_surcharge_percent'

    def caf(self, obj):
        return f"{obj.caf_percent}%"
    caf.short_description = 'CAF'
    caf.admin_order_field = 'caf_percent'



@admin.register(CourierZoneMapping)
class CourierZoneMappingAdmin(admin.ModelAdmin):
    change_list_template = "admin/courierzonemapping_changelist.html"
    list_display = ('courier_partner', 'pincode', 'city', 'state', 'region', 'zone_code', 'org_id')
    list_filter = ('courier_partner', 'zone_code', 'org_id')
    search_fields = ('pincode', 'city', 'state', 'org_id')

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('upload-matrix/', self.admin_site.admin_view(self.upload_matrix), name='courierzonemapping-upload'),
        ]
        return custom_urls + urls

    def upload_matrix(self, request):
        from django.db import transaction
        from django.contrib import messages
        from django.http import HttpResponseRedirect
        import pandas as pd

        # Resolve default user org_id
        default_org_id = 'janki-jewels'
        if hasattr(request.user, 'shop_credentials'):
            default_org_id = request.user.shop_credentials.organization_id
        elif hasattr(request.user, 'team_settings') and request.user.team_settings.organization:
            default_org_id = request.user.team_settings.organization.organization_id

        if request.method == "POST":
            # Allow POST param override
            org_id = request.POST.get('org_id') or default_org_id

            file_obj = request.FILES.get('file')
            if not file_obj:
                self.message_user(request, "No file uploaded.", level=messages.ERROR)
                return HttpResponseRedirect("../")

            try:
                # 2. Parse TSV/Excel using pandas
                df = pd.read_csv(file_obj, sep='\t', dtype=str)
                required_cols = {'CPINCODE', 'ZONE'}
                if not required_cols.issubset(df.columns):
                    self.message_user(request, "Invalid file format. Must contain 'CPINCODE' and 'ZONE' columns.", level=messages.ERROR)
                    return HttpResponseRedirect("../")

                with transaction.atomic():
                    # Delete existing mappings for Bluedart and this org
                    CourierZoneMapping.objects.filter(org_id=org_id, courier_partner='Bluedart').delete()

                    # Deduplicate and build model instances
                    mappings = []
                    seen_pincodes = set()
                    for _, row in df.iterrows():
                        pincode = str(row.get('CPINCODE', '')).strip()
                        if not pincode or pincode == 'nan':
                            continue
                        if '.' in pincode:
                            pincode = pincode.split('.')[0]
                        if pincode.isdigit() and len(pincode) < 6:
                            pincode = pincode.zfill(6)

                        if pincode in seen_pincodes:
                            continue
                        seen_pincodes.add(pincode)

                        zone_code = str(row.get('ZONE', '')).strip()
                        if not zone_code or zone_code == 'nan':
                            continue

                        mappings.append(CourierZoneMapping(
                            org_id=org_id,
                            courier_partner='Bluedart',
                            pincode=pincode,
                            city=str(row.get('CITY', '')).strip()[:100],
                            state=str(row.get('STATE', '')).strip()[:100],
                            region=str(row.get('REGION', '')).strip()[:50],
                            zone_code=zone_code[:10]
                        ))

                    CourierZoneMapping.objects.bulk_create(mappings, batch_size=2000)

                self.message_user(
                    request,
                    f"Successfully imported {len(mappings)} pincode mappings for Bluedart.",
                    level=messages.SUCCESS
                )
                return HttpResponseRedirect("../")

            except Exception as e:
                self.message_user(request, f"Failed to parse or save file: {str(e)}", level=messages.ERROR)
                return HttpResponseRedirect("../")

        # GET request: render the form template
        from django.template.response import TemplateResponse
        from core.models.orders import Order
        db_org_ids = list(Order.objects.values_list('org_id', flat=True).distinct())
        if default_org_id not in db_org_ids:
            db_org_ids.append(default_org_id)
        db_org_ids = sorted([o for o in db_org_ids if o])

        context = {
            **self.admin_site.each_context(request),
            'title': 'Upload Bluedart Zone Mapping',
            'opts': self.model._meta,
            'org_ids': db_org_ids,
            'default_org_id': default_org_id,
            'is_superuser': request.user.is_superuser,
        }
        return TemplateResponse(request, 'admin/courierzonemapping_upload.html', context)


@admin.register(RateSlab)
class RateSlabAdmin(admin.ModelAdmin):
    list_display = ('rate_card', 'zone', 'weight_from_kg', 'weight_to_kg', 'rate', 'increment_kg')
    list_filter = ('zone', 'rate_card__courier_partner')
    search_fields = ('rate_card__name',)


# ==============================================================================
# 8. RETURNS & EXCHANGE ENGINE
# ==============================================================================

class ReturnExchangeActivityInline(admin.TabularInline):
    model = ReturnExchangeActivity
    extra = 0
    readonly_fields = ('action', 'notes', 'performed_by', 'created_at')
    fields = ('action', 'notes', 'performed_by', 'created_at')
    can_delete = False
    ordering = ('created_at',)


@admin.register(ReturnExchangeCase)
class ReturnExchangeCaseAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'get_order_number', 'case_type', 'status',
        'return_awb', 'get_customer_name', 'created_by', 'created_at',
    )
    list_filter = ('case_type', 'status', 'created_at')
    search_fields = (
        'order__order_number', 'remarks', 'return_awb',
        'order__customer_first_name', 'order__customer_last_name',
        'order__contact_phone',
    )
    raw_id_fields = ('order', 'customer', 'created_by')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    inlines = [ReturnExchangeActivityInline]

    fieldsets = (
        ('Case Info', {'fields': ('order', 'customer', 'case_type', 'status')}),
        ('AWB & Details', {'fields': ('return_awb', 'remarks', 'created_by')}),
        ('Refund Details', {
            'fields': (
                'refund_amount', 'refund_notes', 'refund_completed_at',
                'refund_completed_by', 'refund_rejection_reason', 'refund_screenshot',
                'refund_method', 'transaction_reference', 'wallet_credit_reference'
            ),
            'classes': ('collapse',),
        }),
        ('Exchange Settlement Details', {
            'fields': (
                'settlement_type', 'difference_amount', 'settlement_method',
                'settlement_notes', 'settlement_completed_at', 'settlement_completed_by',
                'payment_reference'
            ),
            'classes': ('collapse',),
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def get_order_number(self, obj):
        return obj.order.order_number if obj.order else '—'
    get_order_number.short_description = 'Order #'
    get_order_number.admin_order_field = 'order__order_number'

    def get_customer_name(self, obj):
        if obj.customer:
            return obj.customer.name
        if obj.order:
            return f"{obj.order.customer_first_name or ''} {obj.order.customer_last_name or ''}".strip()
        return '—'
    get_customer_name.short_description = 'Customer'


@admin.register(ReturnExchangeActivity)
class ReturnExchangeActivityAdmin(admin.ModelAdmin):
    list_display = ('id', 'case', 'action', 'performed_by', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('case__order__order_number', 'notes', 'performed_by__email')
    raw_id_fields = ('case', 'performed_by')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(ReturnExchangeBatch)
class ReturnExchangeBatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('name',)
    raw_id_fields = ('created_by',)
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(CourierInvoiceLine)
class CourierInvoiceLineAdmin(admin.ModelAdmin):
    list_display = (
        'awb_number', 'courier_ref', 'shipment_type', 'billing_layer',
        'total_billed', 'expected_pdf_amount', 'expected_net_amount',
        'overcharge_amount', 'anomaly_category', 'confidence_score'
    )
    list_filter = ('anomaly_category', 'shipment_type', 'billing_layer', 'org_id', 'discrepancy_type')
    search_fields = ('awb_number', 'courier_ref', 'dest_pincode')
    raw_id_fields = ('freight_invoice', 'shipment', 'dispute')
    readonly_fields = ('created_at',)
    ordering = ('-overcharge_amount',)


@admin.register(BillingPattern)
class BillingPatternAdmin(admin.ModelAdmin):
    list_display = (
        'courier_partner', 'pincode', 'city', 'zone', 'weight_slab',
        'billed_amount', 'freight', 'cod', 'occurrence_count'
    )
    list_filter = ('courier_partner', 'zone', 'org_id')
    search_fields = ('pincode', 'city')
    ordering = ('-occurrence_count',)


@admin.register(NDRPlaybook)
class NDRPlaybookAdmin(admin.ModelAdmin):
    list_display = ('name', 'org_id', 'reason_category', 'priority', 'is_active', 'created_at')
    list_filter = ('reason_category', 'is_active', 'org_id')
    search_fields = ('name', 'org_id')
    ordering = ('priority', '-created_at')


@admin.register(NDRFraudFlag)
class NDRFraudFlagAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'flag_type', 'is_resolved', 'resolved_at', 'created_at')
    list_filter = ('flag_type', 'is_resolved')
    search_fields = ('shipment__awb_number',)
    raw_id_fields = ('shipment',)
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


@admin.register(ShipmentException)
class ShipmentExceptionAdmin(admin.ModelAdmin):
    list_display = ('shipment', 'org_id', 'exception_type', 'status', 'detected_at')
    list_filter = ('exception_type', 'status', 'org_id')
    search_fields = ('shipment__awb_number', 'notes')
    raw_id_fields = ('shipment', 'assigned_to')
    readonly_fields = ('detected_at', 'resolved_at')
    ordering = ('-detected_at',)



@admin.register(ShopifyCustomApp)
class ShopifyCustomAppAdmin(admin.ModelAdmin):
    list_display  = ['shop_domain', 'client_id', 'created_at', 'is_active']
    search_fields = ['shop_domain', 'client_id']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Store Info', {'fields': ('shop_domain', 'is_active')}),
        ('Shopify App Credentials', {
            'fields': ('client_id', 'client_secret'),
            'description': 'Get these from Shopify Partner Dashboard -> Apps -> [App Name] -> Client credentials'
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)})
    )
