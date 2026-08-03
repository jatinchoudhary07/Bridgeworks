from django.db import models

class PixelEvent(models.Model):
    """
    Stores raw storefront tracking events captured by the BridgeWorks Pixel.
    Used to build multi-touch attribution journeys.
    """
    org_id = models.CharField(max_length=100, db_index=True)
    session_id = models.CharField(max_length=255, db_index=True)
    cart_token = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    # ─── Tracking Data ──────────────────────────────────────────────
    utm_source = models.CharField(max_length=255, blank=True, default='')
    utm_medium = models.CharField(max_length=255, blank=True, default='')
    utm_campaign = models.CharField(max_length=500, blank=True, default='')
    utm_content = models.CharField(max_length=500, blank=True, default='')
    utm_term = models.CharField(max_length=500, blank=True, default='')
    
    fbclid = models.CharField(max_length=500, blank=True, default='')
    gclid = models.CharField(max_length=500, blank=True, default='')
    ttclid = models.CharField(max_length=500, blank=True, default='')
    epik = models.CharField(max_length=500, blank=True, default='')
    sclid = models.CharField(max_length=500, blank=True, default='')
    
    # ─── Context ────────────────────────────────────────────────────
    url = models.URLField(max_length=2000)
    referrer = models.URLField(max_length=2000, blank=True, default='')
    user_agent = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Pixel Event'
        verbose_name_plural = 'Pixel Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['cart_token', '-timestamp'], name='idx_pixel_cart_ts'),
            models.Index(fields=['session_id', '-timestamp'], name='idx_pixel_session_ts'),
        ]

    def __str__(self):
        return f"Pixel Hit ({self.utm_source}) - {self.timestamp}"
