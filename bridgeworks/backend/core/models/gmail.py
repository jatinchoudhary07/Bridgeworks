from django.db import models
from django.conf import settings


class GmailAuth(models.Model):
    """Stores Google OAuth2 tokens scoped to Gmail for a user."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gmail_auth',
    )
    access_token  = models.TextField()
    refresh_token = models.TextField(blank=True)
    token_expiry  = models.DateTimeField(null=True, blank=True)
    scopes        = models.TextField(blank=True)
    gmail_email   = models.EmailField(blank=True)   # the Gmail address connected
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"GmailAuth(user={self.user_id}, email={self.gmail_email})"

    class Meta:
        app_label = 'core'
