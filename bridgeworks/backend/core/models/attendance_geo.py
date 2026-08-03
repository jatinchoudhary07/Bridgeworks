from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# ==============================================================================
# OFFICE LOCATION & IP MANAGEMENT
# ==============================================================================

class OfficeLocation(models.Model):
    """
    A physical office location with geofence configuration.
    Each firm (org) can have multiple offices (HQ, branch, warehouse, etc.).
    """
    org_id = models.CharField(max_length=64, db_index=True)
    name = models.CharField(max_length=150, help_text="e.g. 'HQ', 'Warehouse', 'Mumbai Branch'")
    address = models.TextField(blank=True, default='')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    geofence_radius_meters = models.PositiveIntegerField(
        default=200,
        help_text='Radius in meters within which an employee is considered WFO'
    )
    is_active = models.BooleanField(default=True)
    idle_timeout_enabled = models.BooleanField(
        default=True,
        help_text='Whether the inactivity alarm is enabled'
    )
    idle_timeout_minutes = models.PositiveIntegerField(
        default=15,
        help_text='Inactivity time limit in minutes before alerting the user'
    )
    require_dual_signal = models.BooleanField(
        default=False,
        help_text='Whether BOTH IP matching and GPS location are required to mark WFO'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_office_locations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['name']
        indexes = [
            models.Index(fields=['org_id', 'is_active'], name='core_offloc_org_active_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.org_id})"


class OfficeIP(models.Model):
    """
    Registered public IPs or subnets for an office location.
    Used to match employee login IP to determine WFO status.
    """
    office = models.ForeignKey(
        OfficeLocation, on_delete=models.CASCADE, related_name='registered_ips'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    ip_cidr = models.CharField(
        max_length=50, blank=True, null=True,
        help_text="Optional CIDR subnet range (e.g. '110.226.173.0/24') for dynamic IP matching"
    )
    label = models.CharField(
        max_length=100, blank=True, default='',
        help_text="e.g. 'Main ISP', 'Backup Line', 'WiFi'"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['office', 'ip_address'],
                name='uniq_office_ip'
            ),
            models.UniqueConstraint(
                fields=['office', 'ip_cidr'],
                name='uniq_office_cidr'
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.ip_address and not self.ip_cidr:
            raise ValidationError("Either IP Address or IP CIDR range must be provided.")
        if self.ip_address and self.ip_cidr:
            raise ValidationError("Provide either IP Address or IP CIDR range, not both.")
        if self.ip_cidr:
            import ipaddress
            try:
                ipaddress.ip_network(self.ip_cidr, strict=False)
            except ValueError:
                raise ValidationError({"ip_cidr": "Invalid CIDR range format. E.g. '110.226.173.0/24'"})

    def __str__(self):
        label = f" ({self.label})" if self.label else ""
        val = self.ip_cidr if self.ip_cidr else self.ip_address
        return f"{val}{label} → {self.office.name}"


# ==============================================================================
# ATTENDANCE SESSION (Login/Logout with WFO/WFH detection)
# ==============================================================================

class AttendanceSession(models.Model):
    """
    Tracks a single login→logout session with all geofence signals.
    Multiple sessions per day are possible (e.g., morning login, lunch break re-login).
    The daily AttendanceEntry is derived from these sessions.
    """
    WORK_MODE_CHOICES = [
        ('wfo', 'Work From Office'),
        ('wfh', 'Work From Home'),
        ('unknown', 'Unknown'),
    ]
    GPS_STATUS_CHOICES = [
        ('captured', 'Captured'),
        ('denied', 'Permission Denied'),
        ('unavailable', 'Unavailable'),
        ('timeout', 'Timeout'),
        ('error', 'Error'),
    ]
    LOGOUT_SOURCE_CHOICES = [
        ('manual', 'Manual Logout'),
        ('midnight_job', 'Midnight Auto-Logout'),
        ('idle', 'Idle Timeout'),
        ('page_unload', 'Page Unload'),
        ('superseded', 'Superseded'),
    ]
    ANOMALY_RESOLUTION_CHOICES = [
        ('unresolved', 'Unresolved'),
        ('ok', 'Marked OK'),
        ('suspicious', 'Confirmed Suspicious'),
        ('dismissed', 'Dismissed'),
    ]

    org_id = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='attendance_sessions'
    )

    # Timestamps
    login_at = models.DateTimeField(auto_now_add=True, db_index=True)
    logout_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    logout_source = models.CharField(
        max_length=20, choices=LOGOUT_SOURCE_CHOICES, blank=True, default=''
    )

    # Raw signals — always stored for audit regardless of detection outcome
    login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    login_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    gps_accuracy_meters = models.FloatField(null=True, blank=True)
    gps_status = models.CharField(
        max_length=20, choices=GPS_STATUS_CHOICES, default='unavailable'
    )
    user_agent = models.TextField(blank=True, default='')

    # Detection results
    ip_matched_office = models.ForeignKey(
        OfficeLocation, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        help_text='Office whose registered IP matched the login IP'
    )
    gps_nearest_office = models.ForeignKey(
        OfficeLocation, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        help_text='Nearest office by GPS distance'
    )
    gps_distance_meters = models.FloatField(
        null=True, blank=True,
        help_text='Distance in meters from the nearest office'
    )

    work_mode = models.CharField(
        max_length=10, choices=WORK_MODE_CHOICES, default='unknown'
    )
    work_mode_reason = models.CharField(
        max_length=100, blank=True, default='',
        help_text="e.g. 'ip_match', 'gps_within_geofence', 'no_match'"
    )

    # Anomaly flags (Phase 6)
    is_anomalous = models.BooleanField(default=False, db_index=True)
    anomaly_reasons = models.JSONField(default=list, blank=True)
    anomaly_resolution = models.CharField(
        max_length=20, choices=ANOMALY_RESOLUTION_CHOICES, default='unresolved'
    )
    anomaly_resolved_by = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='resolved_anomalies'
    )
    anomaly_resolved_at = models.DateTimeField(null=True, blank=True)
    anomaly_resolution_note = models.TextField(blank=True, default='')

    class Meta:
        app_label = 'core'
        ordering = ['-login_at']
        indexes = [
            models.Index(
                fields=['org_id', 'user', 'login_at'],
                name='attsess_org_usr_login_idx'
            ),
            models.Index(
                fields=['org_id', 'login_at'],
                name='attsess_org_login_idx'
            ),
            models.Index(
                fields=['org_id', 'is_anomalous', 'anomaly_resolution'],
                name='attsess_org_anomaly_idx'
            ),
        ]

    def __str__(self):
        return (
            f"{self.user.username} — {self.work_mode} "
            f"({self.login_at.strftime('%Y-%m-%d %H:%M') if self.login_at else '?'})"
        )


class PublicHoliday(models.Model):
    org_id = models.CharField(max_length=64, db_index=True)
    date = models.DateField(db_index=True)
    name = models.CharField(max_length=100)
    holiday_type = models.CharField(
        max_length=20,
        choices=[('national', 'National'), ('regional', 'Regional'), ('optional', 'Optional')],
        default='national'
    )

    class Meta:
        app_label = 'core'
        unique_together = ('org_id', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.name} ({self.date}) — {self.org_id}"


class AttendanceSessionExemption(models.Model):
    org_id = models.CharField(max_length=64, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_exemptions')
    exemption_type = models.CharField(
        max_length=50,
        choices=[
            ('all', 'Exempt from all anomaly checks'),
            ('ip_mismatch', 'Exempt from IP mismatch checks'),
            ('gps_precision', 'Exempt from GPS precision checks'),
            ('location_jump', 'Exempt from Location jump checks'),
        ],
        default='all'
    )
    reason = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_attendance_exemptions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.exemption_type} (Active: {self.is_active})"
