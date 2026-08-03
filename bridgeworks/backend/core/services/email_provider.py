import logging
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from core.models.email_integration import EmailThread, EmailMessage
from core.models.crm import CRMActivity

logger = logging.getLogger(__name__)

class EmailProviderService:
    @staticmethod
    def send_and_log_email(shop, parent_entity, sender, recipient, subject, body, cc="", bcc=""):
        """
        Sends an email using Django's email configuration and logs it in the CRM database.
        """
        try:
            to_list = [recipient]
            cc_list = [c.strip() for c in cc.split(",") if c.strip()] if cc else None
            bcc_list = [b.strip() for b in bcc.split(",") if b.strip()] if bcc else None
            
            email = EmailMultiAlternatives(
                subject=subject,
                body=body,
                from_email=sender,
                to=to_list,
                cc=cc_list,
                bcc=bcc_list,
            )
            email.send(fail_silently=False)
            logger.info(f"Email sent successfully to {recipient}")
        except Exception as e:
            logger.error(f"SMTP execution failed: {str(e)}. Proceeding to log record in database.")

        # Log in the CRM models
        content_type = ContentType.objects.get_for_model(parent_entity)
        
        # Get or create thread
        thread, created = EmailThread.objects.get_or_create(
            shop=shop,
            content_type=content_type,
            object_id=parent_entity.id,
            subject=subject,
        )
        
        # Create EmailMessage
        msg = EmailMessage.objects.create(
            thread=thread,
            sender=sender,
            recipient=recipient,
            cc=cc,
            bcc=bcc,
            subject=subject,
            body=body,
            sent_at=timezone.now(),
            is_incoming=False
        )
        
        # Update thread last message timestamp
        thread.last_message_at = msg.sent_at
        thread.save()

        # Create CRMActivity for the CRM timeline
        CRMActivity.objects.create(
            content_type=content_type,
            object_id=parent_entity.id,
            activity_type='email',
            description=f"Sent Email: {subject}\n\n{body[:200]}...",
            created_by_id=None, # System/Auth user can be assigned in viewset context if desired
        )
        
        return msg

    @staticmethod
    def sync_incoming_email(shop, parent_entity, sender, recipient, subject, body, sent_at=None):
        """
        Logs an incoming email inside the CRM and adds it to the CRM Activity timeline.
        """
        if not sent_at:
            sent_at = timezone.now()

        content_type = ContentType.objects.get_for_model(parent_entity)
        
        thread, _ = EmailThread.objects.get_or_create(
            shop=shop,
            content_type=content_type,
            object_id=parent_entity.id,
            subject=subject,
        )
        
        msg = EmailMessage.objects.create(
            thread=thread,
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            sent_at=sent_at,
            is_incoming=True
        )
        
        thread.last_message_at = msg.sent_at
        thread.save()

        CRMActivity.objects.create(
            content_type=content_type,
            object_id=parent_entity.id,
            activity_type='email',
            description=f"Received Email from {sender}: {subject}\n\n{body[:200]}...",
        )
        
        return msg
