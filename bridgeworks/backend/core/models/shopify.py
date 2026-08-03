from django.db import models
from encrypted_model_fields.fields import EncryptedCharField

class ShopifyCustomApp(models.Model):
    shop_domain   = models.CharField(max_length=255, unique=True)  
    # e.g. janki-jewels.myshopify.com
    client_id     = models.CharField(max_length=255)
    client_secret = EncryptedCharField(max_length=255)
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.shop_domain

    class Meta:
        verbose_name = "Shopify Custom App"
        verbose_name_plural = "Shopify Custom Apps"

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache

@receiver(post_save, sender=ShopifyCustomApp)
def bust_credential_cache(sender, instance, **kwargs):
    cache.delete(f"shopify_creds:{instance.shop_domain}")
