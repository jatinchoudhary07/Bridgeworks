from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class TeamMemberSettings(models.Model):
    ROLE_CHOICES = [
        ('founder', 'Founder'),
        ('teammate', 'Teammate'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='team_settings')
    organization = models.ForeignKey('core.ShopCredentials', on_delete=models.CASCADE, related_name='members', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='teammate')
    granular_permissions = models.JSONField(default=dict, blank=True)
    
    # --- POST-IT IDENTITY ---
    postit_color = models.CharField(max_length=7, default='#FFFD82', help_text="Hex code for user's sticky notes")
    subscribe_picklist_email = models.BooleanField(
        default=False,
        help_text="Whether this team member receives daily morning picklist emails."
    )

    def __str__(self):
        org_name = self.organization.organization_id if self.organization else "No Org"
        return f"{self.user.username} ({self.role}) in {org_name}"

    class Meta:
        app_label = 'core'
    

class Invitation(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    email = models.EmailField(unique=True)

    org_id = models.CharField(max_length=50, db_index=True)

    permissions_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='sent_invites'
    )

    accepted_user = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='accepted_org_invites'
    )

    def __str__(self):
        return f"Invite for {self.email} to join {self.org_id}"

    class Meta:
        app_label = 'core'


class UserProfile(models.Model):
    """Stores personal profile information for users."""
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Personal Information
    full_name = models.CharField(max_length=255, blank=True, default='')
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')
    phone = models.CharField(max_length=20, blank=True, default='')
    whatsapp = models.CharField(max_length=20, blank=True, default='')
    location = models.CharField(max_length=255, blank=True, default='')
    first_language = models.CharField(max_length=50, blank=True, default='Hindi')
    second_language = models.CharField(max_length=50, blank=True, default='English')
    about = models.TextField(blank=True, default='')
    
    # Bank Details
    bank_account_holder = models.CharField(max_length=255, blank=True, default='')
    bank_account_number = models.CharField(max_length=50, blank=True, default='')
    bank_ifsc_code = models.CharField(max_length=20, blank=True, default='')
    bank_name = models.CharField(max_length=255, blank=True, default='')
    
    # Profile & Documents
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    aadhaar_card = models.ImageField(upload_to='documents/', blank=True, null=True)
    pan_card = models.ImageField(upload_to='documents/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Idle Alarm Overrides
    idle_timeout_override_enabled = models.BooleanField(null=True, blank=True, default=None)
    idle_timeout_override_minutes = models.PositiveIntegerField(null=True, blank=True, default=None)

    def __str__(self):
        return f"Profile for {self.user.username}"

    class Meta:
        app_label = 'core'

# ==============================================================================
# ENTERPRISE RBAC (GRANULAR PERMISSIONS)
# ==============================================================================

class Permission(models.Model):
    """
    Represents a specific, granular capability. 
    Format is typically "module:action". 
    Example identifiers: 'orders:view', 'orders:create', 'marketing:edit'.
    """
    identifier = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return self.identifier

    class Meta:
        app_label = 'core'
        ordering = ['identifier']


class Role(models.Model):
    """
    A customizable Role containing specific Permissions.
    Belongs to a specific Workspace (ShopCredentials).
    """
    workspace = models.ForeignKey('core.ShopCredentials', on_delete=models.CASCADE, related_name='custom_roles')
    name = models.CharField(max_length=100)
    permissions = models.ManyToManyField(Permission, related_name='roles', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.workspace.organization_id})"

    class Meta:
        app_label = 'core'
        unique_together = ('workspace', 'name')
        ordering = ['name']


class WorkspaceMembership(models.Model):
    """
    Links a User to a Workspace with a specific Role.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspace_memberships')
    workspace = models.ForeignKey('core.ShopCredentials', on_delete=models.CASCADE, related_name='workspace_members')
    role = models.ForeignKey(Role, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    is_co_founder = models.BooleanField(default=False, help_text="Co-founders have the same full access as the original founder.")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        role_name = self.role.name if self.role else "No Role"
        return f"{self.user.username} in {self.workspace.organization_id} as {role_name}"

    class Meta:
        app_label = 'core'
        unique_together = ('user', 'workspace')
