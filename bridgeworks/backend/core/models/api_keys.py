import secrets
from django.db import models
from django.contrib.auth.hashers import make_password, check_password

class ShopAPIKey(models.Model):
    shop = models.ForeignKey(
        'core.ShopCredentials', 
        on_delete=models.CASCADE, 
        related_name='api_keys'
    )
    name = models.CharField(max_length=255, help_text="A friendly name for the key (e.g., 'Warehouse System')")
    prefix = models.CharField(max_length=16, unique=True, db_index=True)
    key_hash = models.CharField(max_length=128)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Shop API Key"
        verbose_name_plural = "Shop API Keys"

    def __str__(self):
        return f"{self.name} ({self.prefix}...)"

    @staticmethod
    def generate_key():
        """Generates a raw key and its prefix."""
        raw_key = f"sk_live_{secrets.token_urlsafe(32)}"
        # We use the first 12 chars of the unique part as the prefix
        prefix = raw_key[:16] 
        return raw_key, prefix

    def verify_key(self, raw_key):
        return check_password(raw_key, self.key_hash)
