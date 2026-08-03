from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from core.models import TeamMemberSettings, ShopCredentials, Invitation

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_settings_and_org(sender, instance, created, **kwargs):
    """
    This runs every time a new user logs in (via Google).
    - If it's a new user: check if invited or first-time founder.
    """
    if not created:
        return

    # 1️⃣ Check if user was invited
    try:
        invite = Invitation.objects.get(email=instance.email)
        org_id = invite.org_id
        invite.accepted_user = instance
        invite.save()

        # Link user to org
        org = ShopCredentials.objects.filter(organization_id=org_id).first()
        if org:
            TeamMemberSettings.objects.create(
                user=instance,
                organization=org,
                role='teammate',
                granular_permissions=invite.permissions_json
            )
        import sys; print(f"[OK] Linked invited user {instance.email} to org {org_id}", file=sys.stderr)
        return
    except Invitation.DoesNotExist:
        pass

    # 2️⃣ If not invited, they’re a new founder
    # Create blank org credentials first (onboarding fills this later)
    organization_id = f"org-{instance.id}"
    shop_creds = ShopCredentials.objects.create(
        owner=instance,
        organization_id=organization_id,
        shopify_api_key_encrypted='',
        shopify_api_password_encrypted='',
        shopify_shop_url_encrypted='',
        shopify_webhook_secret_encrypted='',
        shipway_email_encrypted='',
        shipway_license_key_encrypted='',
    )

    # Assign founder role and default permissions
    TeamMemberSettings.objects.create(
        user=instance,
        organization=shop_creds,
        role='founder',
        granular_permissions={
            "operations_fulfillment": {
                "calling_sheet": True,
                "packaging_sheet": True,
                "batch_creation": True,
                "awb_sheet": True,
                "confirmation_sheet": True,
                "pending_orders": True
            },
            "analytics_reporting": {
                "view_kpis": True,
                "view_audit_logs": True
            },
            "customer_experience": {
                "view_all_tickets": True
            }
        }
    )

    import sys; print(f"[OK] Founder setup complete for {instance.email}", file=sys.stderr)

@receiver(post_save, sender='core.Order')
def update_customer_metrics_on_order_save(sender, instance, **kwargs):
    """
    Whenever an Order is saved, recalculate the lifetime metrics for its linked Customer.
    """
    if not instance.customer_id:
        return

    from core.models import Order, Customer, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES
    from django.db.models import Q, Count

    # Short-circuit: if update_fields was provided, and it does NOT include
    # any status-changing fields, we skip the heavy metrics recalculation entirely.
    if kwargs.get('update_fields'):
        update_fields = set(kwargs['update_fields'])
        relevant_fields = {'status', 'current_status', 'fulfillments'}
        if not update_fields.intersection(relevant_fields):
            return

    customer = instance.customer
    past_orders = Order.objects.filter(customer=customer)

    # Calculate all metrics in a single database aggregation query (O(1) instead of O(N))
    counts = past_orders.aggregate(
        total=Count('id', distinct=True),
        delivered=Count(
            'id', 
            filter=Q(status__iexact='Delivered') |
                   Q(current_status__iexact='Delivered') |
                   Q(fulfillments__shipment_status__iexact='Delivered'),
            distinct=True
        ),
        rto=Count(
            'id',
            filter=Q(current_status__in=RTO_TRANSIT_STATUSES) |
                   Q(current_status__in=RTO_DELIVERED_STATUSES) |
                   Q(fulfillments__shipment_status__in=RTO_TRANSIT_STATUSES) |
                   Q(fulfillments__shipment_status__in=RTO_DELIVERED_STATUSES),
            distinct=True
        ),
        cancelled=Count(
            'id',
            filter=Q(status__iexact='Cancelled'),
            distinct=True
        )
    )

    customer.total_orders = counts['total'] or 0
    customer.delivered_orders = counts['delivered'] or 0
    customer.rto_orders = counts['rto'] or 0
    customer.cancelled_orders = counts['cancelled'] or 0

    customer.save(update_fields=['total_orders', 'delivered_orders', 'rto_orders', 'cancelled_orders'])


# --- CACHE INVALIDATION ---
from core.cache import CacheManager

@receiver(post_save, sender='core.Order')
def invalidate_order_cache_on_save(sender, instance, created, **kwargs):
    """Invalidate all cached lists/KPIs for this org when an order changes."""
    if not created:  # Only on update — new orders don't invalidate existing pages
        CacheManager.invalidate_order(instance)

@receiver(post_delete, sender='core.Order')
def invalidate_order_cache_on_delete(sender, instance, **kwargs):
    """Invalidate cache when an order is deleted."""
    CacheManager.invalidate_order(instance)


@receiver(post_save, sender='core.Order')
def auto_link_exchange_orders(sender, instance, created, **kwargs):
    """
    Automates the linking of Return Prime exchange orders to their parent orders.
    Runs on every save to ensure tags are processed whenever they arrive.
    """
    # 1. If already linked, skip
    if instance.parent_order_id and instance.is_exchange_order:
        return

    tags = str(instance.tags or '')
    is_exchange = 'Exchange' in tags
    associated_tag = 'Associated order:#'
    
    parent_order = None
    found_via_tag = False

    # 2. Try Direct Match via 'Associated order:#' tag
    if associated_tag in tags:
        try:
            # Extract parent order number (e.g. #JANKI12345 -> 12345)
            # Find the part after 'Associated order:#'
            parts = tags.split(associated_tag)
            if len(parts) > 1:
                after_tag = parts[1].split(',')[0].strip()
                clean_number = ''.join(filter(str.isdigit, after_tag))
                if clean_number:
                    from core.models import Order
                    parent_order = Order.objects.filter(order_number=clean_number).first()
                    if parent_order:
                        found_via_tag = True
        except Exception:
            pass

    # 3. Fuzzy Match Fallback (if 'Exchange' tag is present but no association tag)
    if not parent_order and is_exchange:
        try:
            from core.models import ReturnRequest
            from django.db.models import Q
            
            # Look for recent Exchange requests by this customer
            query = Q(request_type__iexact='EXCHANGE')
            
            # Match by customer ID, email, or phone
            cust_filters = Q()
            if instance.customer_id: cust_filters |= Q(order__customer_id=instance.customer_id)
            if instance.contact_email: cust_filters |= Q(order__contact_email=instance.contact_email)
            if instance.contact_phone: cust_filters |= Q(order__contact_phone=instance.contact_phone)
            
            if cust_filters:
                # Find the most recent unlinked exchange request for this customer
                ret_req = ReturnRequest.objects.filter(query & cust_filters).order_by('-created_at').first()
                if ret_req:
                    parent_order = ret_req.order

        except Exception:
            pass

    # 4. Apply Linkage if found
    if parent_order:
        # Use update_fields to avoid infinite recursion of post_save
        instance.parent_order = parent_order
        instance.is_exchange_order = True
        instance.save(update_fields=['parent_order', 'is_exchange_order'])
        import sys; print(f"[OK] Auto-linked Order #{instance.order_number} to Parent #{parent_order.order_number} (Method: {'Tag' if found_via_tag else 'Fuzzy'})", file=sys.stderr)
    elif is_exchange:
        # If it's definitely an exchange but we can't find the parent yet, 
        # at least mark it as an exchange order for analytics.
        if not instance.is_exchange_order:
            instance.is_exchange_order = True
            instance.save(update_fields=['is_exchange_order'])


# ==============================================================================
# DELIVERY MODULE: Auto-sync Shipment on TrackingEvent creation
# ==============================================================================
@receiver(post_save, sender='core.TrackingEvent')
def auto_sync_shipment_on_tracking(sender, instance, created, **kwargs):
    """
    When a TrackingEvent is saved (new scan from courier),
    auto-create or update the corresponding Shipment record.
    """
    if not created:
        return

    try:
        fulfillment = instance.fulfillment
        order = fulfillment.order
        from core.services.delivery_services import sync_shipment_from_order
        sync_shipment_from_order(order)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"Failed to sync shipment for TrackingEvent {instance.id}: {e}"
        )


# ==============================================================================
# WORKFLOW AUTOMATION MODULE: Signals to trigger execution engine
# ==============================================================================

@receiver(pre_save, sender='core.WholesaleLead')
@receiver(pre_save, sender='core.Quotation')
@receiver(pre_save, sender='core.CRMTask')
def cache_original_fields_for_workflow(sender, instance, **kwargs):
    """
    Cache original field values before saving to detect status/assignee transitions in post_save.
    """
    if instance.pk:
        try:
            original = sender.objects.get(pk=instance.pk)
            # Cache status/stage
            instance._original_status = getattr(original, 'status', getattr(original, 'stage', getattr(original, 'funnel_stage', None)))
            # Cache assignee/owner
            if sender.__name__ == 'CRMTask':
                instance._original_assignee = original.assignee_id
            else:
                instance._original_assignee = getattr(original, 'created_by_id', None)
        except Exception:
            pass


@receiver(post_save, sender='core.WholesaleLead')
@receiver(post_save, sender='core.RetailStore')
@receiver(post_save, sender='core.Quotation')
@receiver(post_save, sender='core.RetailStoreCustomer')
@receiver(post_save, sender='core.CRMTask')
def trigger_workflow_on_save(sender, instance, created, **kwargs):
    """
    Trigger workflow executions on creation, update, status/assignee transitions.
    """
    from core.services.workflow_engine import execute_workflows_for_entity
    
    # Avoid loop recursion
    if getattr(instance, '_skip_workflow', False):
        return

    # Trigger created or updated
    trigger = 'created' if created else 'updated'
    execute_workflows_for_entity(instance, trigger)

    if not created:
        # Check for status changed
        current_status = getattr(instance, 'status', getattr(instance, 'stage', getattr(instance, 'funnel_stage', None)))
        original_status = getattr(instance, '_original_status', None)
        if original_status is not None and current_status != original_status:
            execute_workflows_for_entity(instance, 'status_changed')
            
            # Check for quote accepted specifically
            if sender.__name__ == 'Quotation' and current_status == 'accepted':
                execute_workflows_for_entity(instance, 'quote_accepted')

        # Check for lead assigned specifically
        if sender.__name__ == 'WholesaleLead':
            current_assignee = getattr(instance, 'created_by_id', None)
            original_assignee = getattr(instance, '_original_assignee', None)
            if current_assignee != original_assignee:
                execute_workflows_for_entity(instance, 'lead_assigned')
                if instance.created_by:
                    from core.services.notifications import push_unified_notification
                    push_unified_notification(
                        recipient=instance.created_by,
                        actor=None,
                        module='leads',
                        action='share',
                        title="Lead Assigned",
                        message=f"You have been assigned the B2B Lead: {instance.company_name}",
                        entity_type='lead',
                        entity_id=instance.id,
                        metadata={'category': 'lead_assigned'}
                    )

        # Check for task assigned specifically
        if sender.__name__ == 'CRMTask':
            current_assignee = getattr(instance, 'assignee_id', None)
            original_assignee = getattr(instance, '_original_assignee', None)
            if (created and current_assignee) or (not created and current_assignee != original_assignee):
                if instance.assignee:
                    from core.services.notifications import push_unified_notification
                    push_unified_notification(
                        recipient=instance.assignee,
                        actor=instance.created_by or None,
                        module='tasks',
                        action='share',
                        title="Task Assigned",
                        message=f"You have been assigned the task: {instance.title}",
                        entity_type='task',
                        entity_id=instance.id,
                        metadata={'category': 'task_assigned'}
                    )


@receiver(post_delete, sender='core.WholesaleLead')
@receiver(post_delete, sender='core.RetailStore')
@receiver(post_delete, sender='core.Quotation')
@receiver(post_delete, sender='core.RetailStoreCustomer')
@receiver(post_delete, sender='core.CRMTask')
def trigger_workflow_on_delete(sender, instance, **kwargs):
    """
    Trigger workflow executions on deleted entities.
    """
    from core.services.workflow_engine import execute_workflows_for_entity
    execute_workflows_for_entity(instance, 'deleted')


# --- CORS Bypassing for Storefront Pixels ---
try:
    from corsheaders.signals import check_request_enabled

    @receiver(check_request_enabled)
    def cors_allow_pixel_endpoint(sender, request, **kwargs):
        if request.path.startswith('/api/v1/pixel/track/'):
            return True
        return False
except ImportError:
    pass


@receiver(post_save, sender='core.Order')
def auto_generate_prepaid_remittance(sender, instance, **kwargs):
    """
    Auto-generate PrepaidRemittance when an Order is saved and it is prepaid + paid.
    """
    if kwargs.get('update_fields'):
        update_fields = set(kwargs['update_fields'])
        relevant_fields = {'financial_status', 'payment_gateway_names', 'tags'}
        if not update_fields.intersection(relevant_fields):
            return

    try:
        from core.services.delivery_services import sync_prepaid_remittance
        sync_prepaid_remittance(instance)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to auto-generate prepaid remittance for order {instance.id}: {e}")



