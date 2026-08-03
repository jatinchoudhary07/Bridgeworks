from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Job(models.Model):
    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
        ('freelance', 'Freelance'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('paused', 'Paused'),
        ('closed', 'Closed'),
    ]
    POSTING_TYPE_CHOICES = [
        ('internal', 'Internal'),
        ('external', 'External'),
        ('both', 'Both'),
    ]
    LOCATION_TYPE_CHOICES = [
        ('onsite', 'On-site'),
        ('remote', 'Remote'),
        ('hybrid', 'Hybrid'),
    ]

    org_id = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=255)
    department = models.CharField(max_length=120, blank=True, default='')
    employment_type = models.CharField(max_length=30, choices=EMPLOYMENT_TYPE_CHOICES, default='full_time')
    experience_min = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    experience_max = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default='INR')
    location = models.CharField(max_length=255, blank=True, default='')
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES, default='onsite')
    description = models.TextField(blank=True, default='')
    requirements = models.TextField(blank=True, default='')
    openings_count = models.PositiveIntegerField(default=1)
    hiring_manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_jobs'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    posting_type = models.CharField(max_length=20, choices=POSTING_TYPE_CHOICES, default='external')
    skills_required = models.JSONField(default=list, blank=True)
    google_form_url = models.URLField(max_length=1000, blank=True, default='')
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['org_id', 'status']),
            models.Index(fields=['org_id', 'department']),
        ]

    def __str__(self):
        return f"{self.title} ({self.org_id})"
