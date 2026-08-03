from django.db import models
from django.contrib.auth import get_user_model
from .application import Application

User = get_user_model()


class Offer(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
        ('revoked', 'Revoked'),
    ]

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='offer')
    offered_salary = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    joining_date = models.DateField(null=True, blank=True)
    offer_letter_url = models.URLField(max_length=1000, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    responded_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['-created_at']

    def __str__(self):
        return f"Offer for {self.application.candidate.name} — {self.get_status_display()}"
