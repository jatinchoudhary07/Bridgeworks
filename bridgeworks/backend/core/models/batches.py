from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Batch(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True, help_text="Custom name like 'printed_AWB_batch_XYZ'")
    
    created_at = models.DateTimeField(auto_now_add=True)
    orders = models.ManyToManyField('core.Order', related_name='batches')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_batches')

    class Meta: 
        app_label = 'core'
        verbose_name_plural = "Batches"
        ordering = ['-created_at']

    def __str__(self): 
        return self.name or f"Batch {self.id} created on {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class PackagingBatch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    orders = models.ManyToManyField('core.Order', related_name='packaging_batches')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='packaging_assignments')
    class Meta:
        app_label = 'core'
        verbose_name = "Packaging Batch"
        verbose_name_plural = "Packaging Batches"
    def __str__(self):
        agent = self.assigned_to.username if self.assigned_to else "Unassigned"
        return f"Packaging Batch {self.id} (Assigned to: {agent})"
    

class PackagingImage(models.Model):
    order = models.ForeignKey('core.Order', related_name='packaging_images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='packaging_files/') 
    uploaded_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"File for Order {self.order.order_number}"

    class Meta:
        app_label = 'core'


class NDREscalationBatch(models.Model):
    BATCH_STATUS_CHOICES = [
        ('AWAITING_PANEL_OUTPUT', 'Awaiting Panel Output'),
        ('AWAITING_EMAIL_REPLY', 'Awaiting Email Reply'),
        ('PROCESSED', 'Processed'),
        ('CLOSED', 'Closed'),
    ]
    batch_name = models.CharField(max_length=255, unique=True)
    escalation_level = models.IntegerField(default=1, help_text="1 = Panel, 2 = Re-escalate, 3 = Re-re-escalate")
    status = models.CharField(max_length=30, choices=BATCH_STATUS_CHOICES, default='AWAITING_PANEL_OUTPUT')
    orders = models.ManyToManyField('core.Order', related_name='ndr_escalation_batches', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    summary = models.JSONField(default=dict, blank=True, help_text="Processing results summary")

    class Meta:
        app_label = 'core'
        verbose_name = 'NDR Escalation Batch'
        verbose_name_plural = 'NDR Escalation Batches'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.batch_name} (Level {self.escalation_level}) — {self.status}"
