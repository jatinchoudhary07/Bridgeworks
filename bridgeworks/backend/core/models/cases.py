from django.db import models
from django.conf import settings


class CaseFile(models.Model):
    """Represents a specific customer service case (FIR/Ticket)."""

    STATUS_CHOICES = [
        ('NEW_FIR', 'New FIR Filed'),
        ('INVESTIGATING', 'Investigating'),
        ('PENDING_CUST', 'Pending Customer Reply'),
        ('PENDING_OP', 'Pending Operations'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    ISSUE_TYPE_CHOICES = [
        ('DELIVERY', 'Delivery/Tracking Issue'),
        ('RTO', 'RTO Dispute'),
        ('DAMAGE', 'Product Damage/Quality'),
        ('MISSING', 'Missing Item/Order'),
        ('REFUND', 'Refund/Payment Issue'),
        ('CANCELLATION', 'Cancellation Request'),
        ('OTHER', 'Other'),
    ]

    CONTACT_CHOICES = [
        ('EMAIL', 'Email'),
        ('WHATSAPP', 'Whatsapp'),
        ('CALL', 'Call'),
        ('OTHER', 'Other'),
    ]

    case_number = models.CharField(max_length=20, unique=True, editable=False) 
    
    order = models.ForeignKey(
        'core.Order',
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='case_files',
        verbose_name='Associated Order'
    )
    
    subject = models.CharField(max_length=255)
    description = models.TextField(verbose_name="Problem Explanation") 
    issue_type = models.CharField(max_length=50, choices=ISSUE_TYPE_CHOICES, default='DELIVERY')
    
    first_place_of_contact = models.CharField(
        max_length=20, 
        choices=CONTACT_CHOICES, 
        default='WHATSAPP',
        blank=True, null=True
    )

    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='filed_cases',
        verbose_name='Person contact name'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NEW_FIR')
    priority = models.IntegerField(default=1, choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')])
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_cases'
    )
    
    latest_remark = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Remark"
    )
    solution_provided_text = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Solution Provided"
    )
    reshipment_order_number = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="New order (if created)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when status changed to RESOLVED or CLOSED")
    
    class Meta:
        app_label = 'core'
        verbose_name = "Case File"
        verbose_name_plural = "Case Files"
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.case_number:
            last_case = CaseFile.objects.all().order_by('id').last()
            new_id = (last_case.id if last_case else 0) + 1
            self.case_number = f"{new_id:05d}"
        
        if self.status in ['RESOLVED', 'CLOSED']:
            if not self.resolved_at:
                from django.utils import timezone
                self.resolved_at = timezone.now()
        else:
            self.resolved_at = None

        super().save(*args, **kwargs)


class IssueComment(models.Model):
    """Stores comments, replies, and internal notes related to a CaseFile."""
    
    case = models.ForeignKey(
        CaseFile, 
        on_delete=models.CASCADE, 
        related_name='comments'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='case_posts'
    )
    
    message = models.TextField()
    
    is_internal_note = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Issue Comment"
        verbose_name_plural = "Issue Comments"
        ordering = ['created_at']

    def __str__(self):
        return f"Comment on CF-{self.case.case_number} by {self.user.username if self.user else 'System'}"
    

class CaseFileImage(models.Model):
    case = models.ForeignKey(CaseFile, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to='case_images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image for Case {self.case.case_number}"

    class Meta:
        app_label = 'core'
