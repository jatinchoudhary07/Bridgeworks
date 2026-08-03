import logging
from django.utils import timezone
from django.contrib.auth import get_user_model
from hr.training.models import TrainingPushRecipient
from core.models import UnifiedNotification

logger = logging.getLogger(__name__)
User = get_user_model()

def check_training_expiry_and_compliance():
    """
    Daily background task to monitor compliance and alert users about training files
    that are close to expiry or overdue.
    """
    logger.info("Starting training compliance and expiry check task.")
    today = timezone.now().date()
    
    # 1. Fetch non-acknowledged recipients where the training file has an expiry date
    pending_recipients = TrainingPushRecipient.objects.filter(
        is_acknowledged=False,
        push__training_file__expiry_date__isnull=False
    ).select_related('push__training_file', 'user', 'push__pushed_by')
    
    reminders_sent = 0
    
    for recipient in pending_recipients:
        expiry_date = recipient.push.training_file.expiry_date
        days_left = (expiry_date - today).days
        
        # We send reminders when:
        # - Training is overdue (days_left < 0) - send a weekly reminder on Monday, or just once when it becomes overdue
        # - Training is expiring in 3 days (days_left == 3)
        # - Training is expiring tomorrow (days_left == 1)
        
        send_reminder = False
        subject = "Training Alert"
        msg = ""
        
        if days_left == 3:
            send_reminder = True
            subject = "Training Due in 3 Days"
            msg = f"Reminder: The mandatory training '{recipient.push.training_file.title}' is due in 3 days ({expiry_date})."
        elif days_left == 1:
            send_reminder = True
            subject = "Training Due Tomorrow"
            msg = f"Urgent: The mandatory training '{recipient.push.training_file.title}' is due tomorrow ({expiry_date})."
        elif days_left < 0 and abs(days_left) % 7 == 0:  # Weekly reminder for overdue training
            send_reminder = True
            subject = "Training Overdue"
            msg = f"Overdue Alert: The training '{recipient.push.training_file.title}' was due on {expiry_date}."

        if send_reminder:
            try:
                UnifiedNotification.objects.create(
                    recipient=recipient.user,
                    actor=recipient.push.pushed_by,
                    module=UnifiedNotification.MODULE_TRAINING,
                    action=UnifiedNotification.ACTION_REMINDER,
                    title=subject,
                    message=msg,
                    preview="Compliance alert from Training Hub.",
                    entity_type="TrainingPushRecipient",
                    entity_id=str(recipient.id),
                    deep_link={"pathname": "/mydesk/training"}
                )
                reminders_sent += 1
            except Exception as e:
                logger.error(f"Failed to create training reminder notification for user {recipient.user.username}: {e}")
                
    logger.info(f"Training compliance and expiry check task completed. Sent {reminders_sent} reminders.")
    return f"Sent {reminders_sent} reminders"
