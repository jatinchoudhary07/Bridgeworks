from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Candidate(models.Model):
    """A unique person applying for jobs. Identified by email per org."""
    SOURCE_CHOICES = [
        ('google_form', 'Google Form'),
        ('manual', 'Manual Entry'),
        ('referral', 'Referral'),
        ('linkedin', 'LinkedIn'),
        ('portal', 'Job Portal'),
        ('other', 'Other'),
    ]

    org_id = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True, default='')
    resume_url = models.URLField(max_length=1000, blank=True, default='')
    linkedin_url = models.URLField(max_length=500, blank=True, default='')
    github_url = models.URLField(max_length=500, blank=True, default='')
    portfolio_url = models.URLField(max_length=500, blank=True, default='')
    skills = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    total_experience_years = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    current_company = models.CharField(max_length=255, blank=True, default='')
    current_designation = models.CharField(max_length=255, blank=True, default='')
    expected_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    current_salary = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notice_period_days = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=30, choices=SOURCE_CHOICES, default='manual')
    notes = models.TextField(blank=True, default='')
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['org_id', 'email'], name='uniq_candidate_org_email')
        ]
        indexes = [
            models.Index(fields=['org_id', 'email']),
        ]

    def __str__(self):
        return f"{self.name} <{self.email}>"


class CandidateNote(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='candidate_notes')
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['-created_at']
