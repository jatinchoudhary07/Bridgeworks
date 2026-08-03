import logging
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from core.models.workflow import Workflow, WorkflowExecution
from core.models.crm import CRMTask, CRMActivity
from core.models import WholesaleLead, RetailStore, Quotation, RetailStoreCustomer, UnifiedNotification
from core.services.notifications import push_unified_notification
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger('workflow_engine')

def execute_workflows_for_entity(entity, trigger_type, user_who_triggered=None):
    """
    Core engine that finds all matching active workflows for the entity,
    evaluates conditions, executes actions, and audits execution.
    """
    if getattr(entity, '_skip_workflow', False):
        return

    # Map the model instance to entity_type string
    model_map = {
        WholesaleLead: 'lead',
        RetailStore: 'company',
        Quotation: 'quote',
        RetailStoreCustomer: 'customer',
        CRMTask: 'task',
    }
    entity_class = entity.__class__
    entity_type = model_map.get(entity_class)
    if not entity_type:
        return

    # Resolve shop
    shop = None
    if hasattr(entity, 'shop'):
        shop = entity.shop
    elif hasattr(entity, 'store') and hasattr(entity.store, 'shop'):
        shop = entity.store.shop
    
    # If CRMTask, resolve shop from its generic target object
    if entity_type == 'task' and entity.content_object:
        target_obj = entity.content_object
        if hasattr(target_obj, 'shop'):
            shop = target_obj.shop
        elif hasattr(target_obj, 'store') and hasattr(target_obj.store, 'shop'):
            shop = target_obj.store.shop

    if not shop:
        return

    # Find matching active workflows
    workflows = Workflow.objects.filter(
        shop=shop,
        is_active=True,
        trigger__entity_type=entity_type,
        trigger__trigger_type=trigger_type
    )

    for workflow in workflows:
        run_workflow(workflow, entity, entity_type, user_who_triggered)


def run_workflow(workflow, entity, entity_type, user_who_triggered):
    # Setup audit log
    execution = WorkflowExecution.objects.create(
        workflow=workflow,
        entity_type=entity_type,
        entity_id=str(entity.id),
        status='success',
        logs=[]
    )
    
    logs = []
    
    def log(msg):
        logs.append(f"[{timezone.now().isoformat()}] {msg}")
        execution.logs = logs
        execution.save(update_fields=['logs'])

    log(f"Started workflow '{workflow.name}' on {entity_type}#{entity.id}")

    try:
        # 1. Evaluate conditions
        conditions_passed = True
        for cond in workflow.conditions.all():
            val = get_entity_field_value(entity, cond.field_name)
            
            # Perform operator match
            passed = evaluate_condition(entity, cond, val, log)
            if not passed:
                conditions_passed = False
                log(f"Condition failed: {cond.field_name} ({val}) {cond.operator} {cond.value}")
                break
            else:
                log(f"Condition passed: {cond.field_name} ({val}) {cond.operator} {cond.value}")

        if not conditions_passed:
            execution.status = 'skipped'
            execution.save(update_fields=['status'])
            log("Workflow skipped because conditions were not met.")
            return

        # 2. Execute actions
        for action in workflow.actions.all():
            log(f"Running action: {action.action_type}")
            execute_action(action, entity, user_who_triggered, log)
            
        log("Workflow completed successfully.")
        
    except Exception as e:
        logger.exception("Error executing workflow")
        execution.status = 'failed'
        execution.save(update_fields=['status'])
        log(f"Workflow failed: {str(e)}")


def get_entity_field_value(entity, field_name):
    return getattr(entity, field_name, None)


def evaluate_condition(entity, condition, val, log):
    op = condition.operator
    cond_val = condition.value
    
    if op == 'days_since_activity':
        dt_val = None
        if hasattr(entity, 'last_activity') and entity.last_activity:
            dt_val = entity.last_activity
        elif hasattr(entity, 'updated_at'):
            dt_val = entity.updated_at
        
        # fallback to newest CRMActivity if exists
        ct = ContentType.objects.get_for_model(entity)
        last_act = CRMActivity.objects.filter(content_type=ct, object_id=entity.id).order_by('-created_at').first()
        if last_act:
            dt_val = last_act.created_at
            
        if not dt_val:
            return False
            
        diff = timezone.now() - dt_val
        days = diff.days
        try:
            return days >= int(cond_val)
        except ValueError:
            return False

    if val is None:
        return False

    # Standard comparisons
    if op == 'equals':
        return str(val).strip().lower() == str(cond_val).strip().lower()
    elif op == 'contains':
        return str(cond_val).strip().lower() in str(val).strip().lower()
    elif op == 'greater_than':
        try:
            return float(val) > float(cond_val)
        except (ValueError, TypeError):
            return False
    elif op == 'less_than':
        try:
            return float(val) < float(cond_val)
        except (ValueError, TypeError):
            return False
            
    return False


def execute_action(action, entity, user_who_triggered, log):
    config = action.configuration or {}
    action_type = action.action_type
    
    actor = user_who_triggered or action.workflow.created_by
    if not actor:
        actor = entity.shop.owner if hasattr(entity, 'shop') else User.objects.first()

    if action_type == 'create_task':
        ct = ContentType.objects.get_for_model(entity)
        
        due_date = None
        offset = config.get('due_date_offset')
        if offset is not None:
            from datetime import date, timedelta
            try:
                due_date = date.today() + timedelta(days=int(offset))
            except ValueError:
                pass
                
        assignee_id = config.get('assignee_id')
        assignee = None
        if assignee_id:
            try:
                assignee = User.objects.get(pk=assignee_id)
            except User.DoesNotExist:
                pass
        
        if not assignee:
            assignee = actor

        CRMTask.objects.create(
            content_type=ct,
            object_id=entity.id,
            title=config.get('title', 'Workflow Generated Task'),
            description=config.get('description', ''),
            due_date=due_date,
            priority=config.get('priority', 'medium'),
            status='pending',
            assignee=assignee,
            created_by=actor
        )
        log(f"Created task: '{config.get('title')}' assigned to {assignee.username}")

    elif action_type == 'create_activity':
        ct = ContentType.objects.get_for_model(entity)
        CRMActivity.objects.create(
            content_type=ct,
            object_id=entity.id,
            activity_type=config.get('activity_type', 'note'),
            description=config.get('description', 'Workflow automated activity log'),
            created_by=actor
        )
        log(f"Created activity log of type '{config.get('activity_type')}'")

    elif action_type == 'assign_user':
        assignee_id = config.get('user_id') or config.get('assignee_id')
        if not assignee_id:
            log("Skipped assign_user: no user_id specified")
            return
            
        try:
            assignee = User.objects.get(pk=assignee_id)
        except User.DoesNotExist:
            log(f"Skipped assign_user: user {assignee_id} not found")
            return
            
        entity._skip_workflow = True
        
        if hasattr(entity, 'created_by'):
            entity.created_by = assignee
            entity.save(update_fields=['created_by'])
            log(f"Assigned owner to {assignee.username}")
        elif hasattr(entity, 'assignee'):
            entity.assignee = assignee
            entity.save(update_fields=['assignee'])
            log(f"Assigned assignee to {assignee.username}")
        else:
            log("Entity does not support creator/assignee fields")

    elif action_type == 'change_status':
        status_val = config.get('status') or config.get('stage')
        if not status_val:
            log("Skipped change_status: no status/stage value specified")
            return
            
        entity._skip_workflow = True
        
        if hasattr(entity, 'status'):
            entity.status = status_val
            entity.save(update_fields=['status'])
            log(f"Changed status to '{status_val}'")
        elif hasattr(entity, 'stage'):
            entity.stage = status_val
            entity.save(update_fields=['stage'])
            log(f"Changed stage to '{status_val}'")
        elif hasattr(entity, 'funnel_stage'):
            entity.funnel_stage = status_val
            entity.save(update_fields=['funnel_stage'])
            log(f"Changed funnel stage to '{status_val}'")
        else:
            log("Entity does not support status/stage fields")

    elif action_type == 'send_notification':
        recipient = None
        rec_val = config.get('recipient_id')
        if rec_val == 'owner' and hasattr(entity, 'created_by') and entity.created_by:
            recipient = entity.created_by
        elif rec_val == 'assignee' and hasattr(entity, 'assignee') and entity.assignee:
            recipient = entity.assignee
        elif rec_val:
            try:
                recipient = User.objects.get(pk=rec_val)
            except User.DoesNotExist:
                pass
        
        if not recipient:
            recipient = actor

        if recipient:
            push_unified_notification(
                recipient=recipient,
                actor=actor,
                module=UnifiedNotification.MODULE_TASKS,
                action=UnifiedNotification.ACTION_REMINDER,
                title=config.get('title', 'Workflow Alert'),
                message=config.get('message', 'A workflow automation has triggered this alert.'),
                entity_type=entity.__class__.__name__.lower(),
                entity_id=entity.id
            )
            log(f"Dispatched in-app notification to {recipient.username}")
        else:
            log("Skipped notification: no valid recipient resolved")


def execute_overdue_task_workflows():
    """
    Finds all pending tasks that are overdue and executes workflows
    that have a 'task_overdue' trigger.
    """
    from datetime import date
    from core.models.crm import CRMTask
    
    overdue_tasks = CRMTask.objects.filter(
        status='pending',
        due_date__lt=date.today()
    )
    
    for task in overdue_tasks:
        already_run = WorkflowExecution.objects.filter(
            entity_type='task',
            entity_id=str(task.id),
            workflow__trigger__trigger_type='task_overdue'
        ).exists()
        
        if already_run:
            continue
            
        execute_workflows_for_entity(task, 'task_overdue')
        
        # Send overdue alert to the assignee
        if task.assignee:
            try:
                from core.services.notifications import push_unified_notification
                push_unified_notification(
                    recipient=task.assignee,
                    actor=None,
                    module='tasks',
                    action='reminder',
                    title="Task Overdue Alert",
                    message=f"The task '{task.title}' is overdue (was due on {task.due_date}).",
                    entity_type='task',
                    entity_id=task.id,
                    metadata={'category': 'task_overdue'}
                )
            except Exception:
                pass
