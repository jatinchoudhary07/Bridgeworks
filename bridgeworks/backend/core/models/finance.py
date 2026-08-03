from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class FinanceTransaction(models.Model):
    ENTRY_TYPE_CHOICES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='finance_transactions')

    entry_type = models.CharField(max_length=12, choices=ENTRY_TYPE_CHOICES, db_index=True)
    entry_date = models.DateField(db_index=True)
    particular = models.CharField(max_length=255, blank=True, default='')
    department = models.CharField(max_length=120, blank=True, default='')
    sub_department = models.CharField(max_length=120, blank=True, default='')
    category = models.CharField(max_length=120, blank=True, default='')
    nature = models.CharField(max_length=120, blank=True, default='')
    payment_type = models.CharField(max_length=60, blank=True, default='')
    bank_name = models.CharField(max_length=120, blank=True, default='')
    account_number = models.CharField(max_length=64, blank=True, default='')
    reference_id = models.CharField(max_length=120, blank=True, default='', db_index=True)
    invoice_no = models.CharField(max_length=120, blank=True, default='')

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vendor_payee = models.CharField(max_length=180, blank=True, default='')
    bill_due_date = models.DateField(blank=True, null=True)
    approval_workflow = models.CharField(max_length=180, blank=True, default='')
    cost_centre = models.CharField(max_length=120, blank=True, default='')
    tds_section = models.CharField(max_length=24, blank=True, default='')

    status = models.CharField(max_length=60, blank=True, default='Draft', db_index=True)
    notes = models.TextField(blank=True, default='')
    receipt = models.FileField(upload_to='finance/receipts/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-entry_date', '-created_at']
        indexes = [
            models.Index(fields=['org_id', 'entry_type', 'entry_date']),
            models.Index(fields=['org_id', 'status']),
        ]


class FinanceOption(models.Model):
    OPTION_TYPE_CHOICES = [
        ('department', 'Department'),
        ('sub_department', 'Sub Department'),
        ('category', 'Category'),
        ('nature', 'Nature'),
        ('payment_type', 'Payment Type'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    option_type = models.CharField(max_length=32, choices=OPTION_TYPE_CHOICES, db_index=True)
    value = models.CharField(max_length=120)
    parent_value = models.CharField(max_length=120, blank=True, default='')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='finance_options')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['option_type', 'value']
        constraints = [
            models.UniqueConstraint(
                fields=['org_id', 'option_type', 'value', 'parent_value'],
                name='finance_option_unique_per_org',
            ),
        ]
