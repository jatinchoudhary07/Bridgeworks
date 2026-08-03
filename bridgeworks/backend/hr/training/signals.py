from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from hr.training.models import TrainingPushRecipient, TrainingAcknowledgement
from core.models import PersonalTodoItem, UnifiedNotification

@receiver(post_save, sender=TrainingPushRecipient)
def handle_training_push_recipient_changed(sender, instance, created, **kwargs):
    push = instance.push
    user = instance.user
    training_file = push.training_file
    pushed_by = push.pushed_by

    if created:
        # 1. Create a Notification
        msg = f"New training material shared: '{training_file.title}'."
        if push.is_mandatory:
            msg = f"MANDATORY training assigned: '{training_file.title}'. Please complete and acknowledge."

        UnifiedNotification.objects.create(
            recipient=user,
            actor=pushed_by,
            module=UnifiedNotification.MODULE_TRAINING,
            action=UnifiedNotification.ACTION_SHARE,
            title="Training Hub Update",
            message=msg,
            preview=f"Category: {training_file.get_category_display()}",
            entity_type="TrainingPushRecipient",
            entity_id=str(instance.id),
            deep_link={"pathname": "/mydesk/training"}
        )

        # 2. If mandatory, create a PersonalTodoItem task
        if push.is_mandatory and not instance.task_id:
            due_date = training_file.expiry_date or (timezone.now() + timezone.timedelta(days=7)).date()
            due_date_str = due_date.isoformat()
            assignee_name = user.profile.full_name if hasattr(user, 'profile') and user.profile.full_name else user.username
            assigned_by_name = pushed_by.profile.full_name if pushed_by and hasattr(pushed_by, 'profile') and pushed_by.profile.full_name else (pushed_by.username if pushed_by else 'HR System')
            
            meta = {
                "type": "task",
                "title": f"Complete Training: {training_file.title}",
                "dueDate": due_date_str,
                "dueTime": "18:00",
                "priority": "high",
                "status": "todo",
                "assignee": assignee_name,
                "assignee_id": user.id,
                "assignees": [{"id": user.id, "label": assignee_name}],
                "assignee_ids": [user.id],
                "assignedBy": assigned_by_name,
                "assigned_by_id": pushed_by.id if pushed_by else None,
                "description": f"Please read the training document '{training_file.title}' and mark it as acknowledged in the Training Hub.\n\nLink to training document: {training_file.file.url if training_file.file else ''}",
                "training_push_recipient_id": instance.id
            }

            task = PersonalTodoItem.objects.create(
                user=user,
                org_id=push.org_id,
                text=f"Complete Training: {training_file.title}",
                is_done=False,
                recurring="none",
                sort_order=0,
                meta=meta
            )
            
            # Save task_id back to TrainingPushRecipient (use update to avoid post_save recursion loop)
            TrainingPushRecipient.objects.filter(pk=instance.pk).update(task_id=task.id)
    else:
        # If acknowledged, update the associated task (PersonalTodoItem)
        if instance.is_acknowledged and instance.task_id:
            try:
                task = PersonalTodoItem.objects.get(pk=instance.task_id)
                if not task.is_done:
                    task.is_done = True
                    if isinstance(task.meta, dict):
                        task.meta['status'] = 'done'
                    task.save()
            except PersonalTodoItem.DoesNotExist:
                pass


@receiver(post_save, sender=PersonalTodoItem)
def handle_task_completed(sender, instance, created, **kwargs):
    if created:
        return
    if instance.is_done:
        meta = instance.meta
        if isinstance(meta, dict) and 'training_push_recipient_id' in meta:
            recipient_id = meta['training_push_recipient_id']
            try:
                recipient = TrainingPushRecipient.objects.get(pk=recipient_id)
                if not recipient.is_acknowledged:
                    recipient.is_acknowledged = True
                    recipient.acknowledged_at = timezone.now()
                    recipient.save()
                    
                    # Create TrainingAcknowledgement
                    TrainingAcknowledgement.objects.get_or_create(
                        org_id=recipient.push.org_id,
                        training_file=recipient.push.training_file,
                        user=recipient.user,
                        defaults={
                            'push_recipient': recipient,
                            'acknowledged_at': timezone.now()
                        }
                    )
            except TrainingPushRecipient.DoesNotExist:
                pass
