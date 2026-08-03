import logging
from decimal import Decimal
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

from core.models.approval import ApprovalPolicy, ApprovalStep, ApprovalRequest, ApprovalHistory
from core.models.sales import Quotation
from core.models.crm import CRMActivity
from core.services.notifications import push_unified_notification

logger = logging.getLogger(__name__)

def check_condition(entity, cond):
    """
    Checks if a single condition dict matches the entity attributes.
    """
    field = cond.get('field')
    operator = cond.get('operator')
    target_value = cond.get('value')
    
    if not hasattr(entity, field):
        return False
        
    val = getattr(entity, field)
    
    # Standardize values for numeric comparisons
    try:
        if isinstance(val, (int, float, Decimal)) or isinstance(target_value, (int, float, str)):
            val = float(val)
            target_value = float(target_value)
    except (ValueError, TypeError):
        pass
        
    if operator in ('equals', 'eq'):
        return val == target_value
    elif operator == 'contains':
        return str(target_value).lower() in str(val).lower()
    elif operator in ('gte', 'greater_than_or_equal'):
        return val >= target_value
    elif operator in ('lte', 'less_than_or_equal'):
        return val <= target_value
    elif operator in ('gt', 'greater_than'):
        return val > target_value
    elif operator in ('lt', 'less_than'):
        return val < target_value
    return False


def evaluate_policy(policy, entity):
    """
    Evaluates trigger conditions of the policy against the entity.
    """
    conds = policy.trigger_conditions
    if not conds:
        return True # Default to true if no conditions specified
        
    # Support both a single condition or a list of conditions
    if isinstance(conds, dict):
        conds = [conds]
        
    for cond in conds:
        if not check_condition(entity, cond):
            return False
    return True


def find_matching_policy(shop, entity_type, entity):
    """
    Finds the first active policy matching the entity conditions.
    """
    policies = ApprovalPolicy.objects.filter(shop=shop, entity_type=entity_type, is_active=True)
    for policy in policies:
        if evaluate_policy(policy, entity):
            return policy
    return None


def submit_for_approval(entity_type, entity_id, shop, user):
    """
    Submits an entity for approval. Creates request & steps if matching policy is found.
    """
    # Load underlying entity
    entity = None
    if entity_type == 'quote':
        try:
            entity = Quotation.objects.get(id=entity_id, shop=shop)
        except Quotation.DoesNotExist:
            raise ValueError("Quotation not found.")
            
    if not entity:
        raise ValueError(f"Unsupported entity type: {entity_type}")

    # Prevent submitting if already pending
    existing_pending = ApprovalRequest.objects.filter(
        shop=shop, entity_type=entity_type, entity_id=str(entity_id), status='pending'
    ).exists()
    if existing_pending:
        raise ValueError("This entity is already pending approval.")

    # Find matching policy
    policy = find_matching_policy(shop, entity_type, entity)
    
    if not policy or not policy.steps.exists():
        # Auto-approve flow if no active policies/steps are found
        if entity_type == 'quote':
            entity.status = 'sent'
            entity.save()
            
            # Log CRM timeline activity
            ct = ContentType.objects.get_for_model(entity)
            CRMActivity.objects.create(
                content_type=ct,
                object_id=entity.id,
                activity_type='stage_change',
                description="Quotation auto-approved and updated to Sent (no matching policies found).",
                created_by=user
            )
        return None

    # Create Request
    req = ApprovalRequest.objects.create(
        shop=shop,
        policy=policy,
        entity_type=entity_type,
        entity_id=str(entity_id),
        status='pending',
        current_step_sequence=1,
        created_by=user
    )

    # Log submission in history
    ApprovalHistory.objects.create(
        request=req,
        sequence=1,
        action='submitted',
        approver=user,
        comments="Submitted for approval."
    )

    # Transition entity status
    if entity_type == 'quote':
        entity.status = 'pending_approval'
        entity.save()

    # Trigger notifications for Step 1 approvers
    step1 = policy.steps.filter(sequence=1).first()
    if step1:
        for approver in step1.approvers.all():
            push_unified_notification(
                recipient=approver,
                actor=user,
                module='tasks',
                action='share',
                title="Approval Required",
                message=f"You have a pending approval request for {entity_type} #{entity_id}.",
                entity_type=entity_type,
                entity_id=entity_id
            )
            
    return req


def process_approval_action(request, approver, action, comments=""):
    """
    Approves or rejects the current step of an active approval request.
    """
    if request.status != 'pending':
        raise ValueError("This request is already finalized.")

    policy = request.policy
    if not policy:
        raise ValueError("No policy associated with this request.")

    # Fetch current step
    step = policy.steps.filter(sequence=request.current_step_sequence).first()
    if not step:
        raise ValueError("Current step configuration not found.")

    # Validate that approver is authorized for this step
    if approver not in step.approvers.all() and (step.escalate_to != approver):
        raise ValueError("You are not an authorized approver for this step.")

    # Record history
    history = ApprovalHistory.objects.create(
        request=request,
        step=step,
        sequence=request.current_step_sequence,
        action=action,
        approver=approver,
        comments=comments
    )

    # Find underlying entity
    entity = None
    if request.entity_type == 'quote':
        try:
            entity = Quotation.objects.get(id=request.entity_id, shop=request.shop)
        except Quotation.DoesNotExist:
            pass

    if action == 'rejected':
        request.status = 'rejected'
        request.save()

        if entity:
            if request.entity_type == 'quote':
                entity.status = 'rejected'
                entity.save()
            
            # Log CRM Timeline activity
            ct = ContentType.objects.get_for_model(entity)
            CRMActivity.objects.create(
                content_type=ct,
                object_id=entity.id,
                activity_type='stage_change',
                description=f"Quotation rejected during approval step {request.current_step_sequence} by {approver.username}. Comments: {comments}",
                created_by=approver
            )

        # Notify submitter
        if request.created_by:
            push_unified_notification(
                recipient=request.created_by,
                actor=approver,
                module='tasks',
                action='reminder',
                title="Approval Rejected",
                message=f"Your approval request for {request.entity_type} #{request.entity_id} was rejected.",
                entity_type=request.entity_type,
                entity_id=request.entity_id
            )
        return

    # Handle 'approved' action
    # Count how many approvals have been recorded for the current step in the history
    step_approvals_count = ApprovalHistory.objects.filter(
        request=request,
        sequence=request.current_step_sequence,
        action='approved'
    ).values('approver').distinct().count()

    if step_approvals_count >= step.min_approvals_required:
        # Step is complete! Move to next step
        next_step = policy.steps.filter(sequence=request.current_step_sequence + 1).first()
        if next_step:
            request.current_step_sequence += 1
            request.save()

            # Notify next step approvers
            for app in next_step.approvers.all():
                push_unified_notification(
                    recipient=app,
                    actor=request.created_by,
                    module='tasks',
                    action='share',
                    title="Approval Required",
                    message=f"You have a pending approval request for {request.entity_type} #{request.entity_id} (Step {request.current_step_sequence}).",
                    entity_type=request.entity_type,
                    entity_id=request.entity_id
                )
        else:
            # All steps completed! Auto approve the request
            request.status = 'approved'
            request.save()

            if entity:
                if request.entity_type == 'quote':
                    entity.status = 'sent'
                    entity.save()

                # Log CRM Timeline activity
                ct = ContentType.objects.get_for_model(entity)
                CRMActivity.objects.create(
                    content_type=ct,
                    object_id=entity.id,
                    activity_type='stage_change',
                    description=f"Quotation fully approved through policy '{policy.name}'.",
                    created_by=approver
                )

            # Notify submitter
            if request.created_by:
                push_unified_notification(
                    recipient=request.created_by,
                    actor=approver,
                    module='tasks',
                    action='reminder',
                    title="Approval Request Approved",
                    message=f"Your approval request for {request.entity_type} #{request.entity_id} has been fully approved.",
                    entity_type=request.entity_type,
                    entity_id=request.entity_id
                )


def check_and_escalate_approvals():
    """
    Finds pending approval requests whose current step SLA has expired,
    and escalates them to the configured escalation user.
    """
    now = timezone.now()
    pending_requests = ApprovalRequest.objects.filter(status='pending')
    escalated_count = 0

    for req in pending_requests:
        policy = req.policy
        if not policy:
            continue
        step = policy.steps.filter(sequence=req.current_step_sequence).first()
        if not step or not step.sla_hours or not step.escalate_to:
            continue

        # Calculate time elapsed since last history entry or request creation
        last_action = req.history.all().order_by('-created_at').first()
        start_time = last_action.created_at if last_action else req.created_at
        elapsed_hours = (now - start_time).total_seconds() / 3600.0

        if elapsed_hours >= step.sla_hours:
            # Escalate request
            req.status = 'escalated'
            req.save()

            # Record history
            ApprovalHistory.objects.create(
                request=req,
                step=step,
                sequence=req.current_step_sequence,
                action='escalated',
                approver=step.escalate_to,
                comments=f"SLA of {step.sla_hours} hours exceeded. Auto-escalated to {step.escalate_to.username}."
            )

            # Send notification
            push_unified_notification(
                recipient=step.escalate_to,
                actor=None,
                module='tasks',
                action='share',
                title="Approval Escalated",
                message=f"Approval request for {req.entity_type} #{req.entity_id} has been escalated to you due to SLA breach.",
                entity_type=req.entity_type,
                entity_id=req.entity_id
            )
            escalated_count += 1

    return escalated_count

