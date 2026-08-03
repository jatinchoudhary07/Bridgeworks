from django.db import models
from django.contrib.auth import get_user_model
from .job import Job
from .candidate import Candidate

User = get_user_model()


class HiringStage(models.Model):
    """Per-org customizable pipeline stages."""
    DEFAULT_STAGES = [
        ('screening', 'Screening', 1),
        ('assessment', 'Assessment', 2),
        ('technical_interview', 'Technical Interview', 3),
        ('hr_interview', 'HR Interview', 4),
        ('offer', 'Offer', 5),
        ('hired', 'Hired', 6),
        ('rejected', 'Rejected', 7),
    ]

    org_id = models.CharField(max_length=100, db_index=True)
    name = models.CharField(max_length=100)
    slug = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=20, default='#6366f1')
    is_terminal = models.BooleanField(default=False)   # hired / rejected
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['org_id', 'slug'], name='uniq_hiring_stage_org_slug')
        ]

    def __str__(self):
        return self.name


class JobPipelineStage(models.Model):
    """Per-job pipeline columns — independent from the global HiringStage."""
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='pipeline_stages')
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=20, default='#6366f1')
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['order', 'created_at']
        unique_together = [['job', 'name']]

    def __str__(self):
        return f"{self.job.title} → {self.name}"


class Application(models.Model):
    """A candidate's application to a specific job."""
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='applications')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    current_stage = models.ForeignKey(
        HiringStage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='current_applications'
    )
    cover_letter = models.TextField(blank=True, default='')
    referral_by = models.CharField(max_length=255, blank=True, default='')
    extra_data = models.JSONField(default=dict, blank=True)
    pipeline_stage = models.ForeignKey(
        'JobPipelineStage', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='applications'
    )
    is_saved = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['-applied_at']
        constraints = [
            models.UniqueConstraint(fields=['candidate', 'job'], name='uniq_application_candidate_job')
        ]

    def __str__(self):
        return f"{self.candidate.name} → {self.job.title}"


class ApplicationStageHistory(models.Model):
    """Audit trail for every stage move."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='stage_history')
    from_stage = models.ForeignKey(
        HiringStage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='history_from'
    )
    to_stage = models.ForeignKey(
        HiringStage, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='history_to'
    )
    moved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    moved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'hiring'
        ordering = ['-moved_at']
