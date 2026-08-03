from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class WorkforceDepartment(models.Model):
    org_id = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=120)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['org_id', 'name'], name='uniq_workforce_department_org_name')
        ]

    def __str__(self):
        return f"{self.name} ({self.org_id})"


class WorkforceMember(models.Model):
    WORKING_STYLE_CHOICES = [
        ('On-site', 'On-site'),
        ('Remote', 'Remote'),
        ('Hybrid', 'Hybrid'),
        ('Field Work', 'Field Work'),
        ('Part-time', 'Part-time'),
        ('Contractual', 'Contractual'),
    ]
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    org_id = models.CharField(max_length=100, db_index=True)
    full_name = models.CharField(max_length=255)
    department = models.ForeignKey(
        WorkforceDepartment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members'
    )
    category = models.CharField(max_length=100, blank=True, default='')
    role_designation = models.CharField(max_length=150, blank=True, default='')
    working_style = models.CharField(max_length=30, choices=WORKING_STYLE_CHOICES, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True, default='Active')
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    current_location = models.CharField(max_length=255, blank=True, default='')
    notes = models.TextField(blank=True, default='')
    extra_data = models.JSONField(default=dict, blank=True)
    is_archived = models.BooleanField(default=False)
    date_of_joining = models.DateField(null=True, blank=True)
    date_of_leaving = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.org_id})"
