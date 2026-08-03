from django.db import models
from django.conf import settings
from django.utils import timezone
from core.storage import AutoResourceCloudinaryStorage


class TrainingCategory(models.TextChoices):
    ONBOARDING = "onboarding", "Onboarding"
    COMPLIANCE = "compliance", "Compliance"
    SKILLS     = "skills",     "Skills"
    SOPS       = "sops",       "SOPs"


class TrainingFile(models.Model):
    """
    Master record for every training file uploaded by HR.
    Versioning: uploading a new file for the same title bumps version;
    parent_file tracks the lineage root.
    """
    org_id            = models.CharField(max_length=64, db_index=True)
    title             = models.CharField(max_length=255)
    description       = models.TextField(blank=True, default='')
    file              = models.FileField(
        upload_to='hr/training/', storage=AutoResourceCloudinaryStorage(),
        null=True, blank=True
    )
    video_url         = models.URLField(max_length=500, blank=True, default='')
    file_type         = models.CharField(max_length=20, blank=True, default='')
    file_size_kb      = models.PositiveIntegerField(default=0)
    category          = models.CharField(
        max_length=50, default="onboarding"
    )
    is_mandatory      = models.BooleanField(default=False)
    # Two aliased columns so both `target_dept` and `department_target` work in filters
    target_dept       = models.CharField(max_length=100, blank=True, default='')
    department_target = models.CharField(max_length=100, blank=True, default='')
    expiry_date       = models.DateField(null=True, blank=True)
    version           = models.PositiveSmallIntegerField(default=1)
    superseded_by     = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='previous_versions'
    )
    parent_file       = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='versions'
    )
    uploaded_by       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='uploaded_training_files'
    )
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} v{self.version}"

    @property
    def is_expiring_soon(self):
        if not self.expiry_date:
            return False
        return (self.expiry_date - timezone.now().date()).days <= 30

    @property
    def is_expired(self):
        if not self.expiry_date:
            return False
        return self.expiry_date < timezone.now().date()

    def get_category_display(self):
        for val, label in TrainingCategory.choices:
            if val == self.category:
                return label
        return self.category.replace('_', ' ').title()

    def save(self, *args, **kwargs):
        """Keep target_dept and department_target in sync."""
        if self.target_dept and not self.department_target:
            self.department_target = self.target_dept
        elif self.department_target and not self.target_dept:
            self.target_dept = self.department_target
        super().save(*args, **kwargs)


class TrainingPush(models.Model):
    """
    One push = one training file pushed to a vault (department / members).
    """
    org_id             = models.CharField(max_length=64, db_index=True)
    training_file      = models.ForeignKey(
        TrainingFile, on_delete=models.CASCADE, related_name='pushes'
    )
    # New fields from spec
    vault_id           = models.CharField(max_length=100, blank=True, default='')
    vault_name         = models.CharField(max_length=150, blank=True, default='')
    pushed_by          = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='training_pushes'
    )
    is_mandatory       = models.BooleanField(default=False)
    create_task        = models.BooleanField(default=False)
    notify_members     = models.BooleanField(default=True)
    pushed_at          = models.DateTimeField(auto_now_add=True)
    notes              = models.TextField(blank=True, default='')
    # Legacy compat field kept in DB
    target_departments = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-pushed_at']

    def __str__(self):
        return f"{self.training_file.title} → {self.vault_name or self.org_id}"

    @property
    def completion_percentage(self):
        total = self.recipients.count()
        if total == 0:
            return 0
        acked = self.recipients.filter(is_acknowledged=True).count()
        return round((acked / total) * 100)


class TrainingPushRecipient(models.Model):
    """
    Individual member who received a push.
    DB stores the FK as `user`; `member` is a Python property alias so
    the new API design and the old DB schema coexist without a migration rename.
    """
    push            = models.ForeignKey(
        TrainingPush, on_delete=models.CASCADE, related_name='recipients'
    )
    # DB column stays as `user` to avoid data-loss migration
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='training_recipient_shares'
    )
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    task_id         = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ('push', 'user')
        ordering = ['user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.push}"

    # ── New-design aliases ────────────────────────────────────────────────────

    @property
    def member(self):
        """Alias used by new serializers / views that follow the spec."""
        return self.user

    @property
    def acknowledged(self):
        """Alias for new-design serializers."""
        return self.is_acknowledged

    def mark_acknowledged(self):
        self.is_acknowledged = True
        self.acknowledged_at = timezone.now()
        self.save(update_fields=['is_acknowledged', 'acknowledged_at'])


class TrainingAcknowledgement(models.Model):
    """
    Audit log – one row per acknowledgement event.
    """
    org_id          = models.CharField(max_length=64, db_index=True, default='')
    training_file   = models.ForeignKey(
        TrainingFile, on_delete=models.CASCADE, related_name='acknowledgements'
    )
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='training_acknowledgements'
    )
    push_recipient  = models.OneToOneField(
        TrainingPushRecipient, on_delete=models.CASCADE,
        related_name='acknowledgement', null=True, blank=True
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    ip_address      = models.GenericIPAddressField(null=True, blank=True)
    device_info     = models.CharField(max_length=255, blank=True, default='')
    notes           = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('training_file', 'user')
        ordering = ['-acknowledged_at']

    # ── Property aliases ──────────────────────────────────────────────────────

    @property
    def recipient(self):
        """Alias for new-design views that call `.recipient`."""
        return self.push_recipient
