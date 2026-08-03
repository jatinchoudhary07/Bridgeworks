"""
OrderAttribution Model
======================
Stores per-order marketing attribution data extracted from Shopify's
`landing_site` and `referring_site` fields.

This is a OneToOne extension of the existing Order model — it does NOT
modify Order in any way. All reads are via `order.attribution`.
"""
from django.db import models


class OrderAttribution(models.Model):
    """
    Per-order attribution data: UTMs, click IDs, and computed channel.
    Linked via OneToOne to Order so existing Order logic is untouched.
    """
    order = models.OneToOneField(
        'core.Order',
        on_delete=models.CASCADE,
        related_name='attribution',
        help_text="The order this attribution data belongs to."
    )

    # ─── UTM Parameters ─────────────────────────────────────────────
    utm_source = models.CharField(
        max_length=255, blank=True, default='',
        db_index=True,
        help_text="e.g. facebook, google, instagram, newsletter"
    )
    utm_medium = models.CharField(
        max_length=255, blank=True, default='',
        help_text="e.g. cpc, paid, social, email, organic"
    )
    utm_campaign = models.CharField(
        max_length=500, blank=True, default='',
        db_index=True,
        help_text="Campaign name from the UTM tag"
    )
    utm_content = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Ad creative or content variant identifier"
    )
    utm_term = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Keyword / Ad ID — often maps to the specific ad"
    )

    # ─── Platform Click IDs ──────────────────────────────────────────
    fbclid = models.CharField(
        max_length=500, blank=True, default='',
        db_index=True,
        help_text="Facebook/Meta click identifier"
    )
    gclid = models.CharField(
        max_length=500, blank=True, default='',
        db_index=True,
        help_text="Google Ads click identifier"
    )
    ttclid = models.CharField(
        max_length=500, blank=True, default='',
        help_text="TikTok click identifier"
    )
    # Pinterest click ID
    epik = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Pinterest click identifier"
    )
    # Snapchat click ID
    sclid = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Snapchat click identifier"
    )

    # ─── Raw Shopify Data ────────────────────────────────────────────
    landing_page = models.URLField(
        max_length=2000, blank=True, default='',
        help_text="Raw landing_site value from Shopify API"
    )
    referring_site = models.URLField(
        max_length=2000, blank=True, default='',
        help_text="Raw referring_site value from Shopify API"
    )

    # ─── Computed Channel Classification ─────────────────────────────
    CHANNEL_CHOICES = [
        ('meta_paid', 'Meta Paid'),
        ('google_paid', 'Google Paid'),
        ('tiktok_paid', 'TikTok Paid'),
        ('pinterest_paid', 'Pinterest Paid'),
        ('snapchat_paid', 'Snapchat Paid'),
        ('organic_social', 'Organic Social'),
        ('organic_search', 'Organic Search'),
        ('direct', 'Direct'),
        ('email', 'Email'),
        ('whatsapp', 'WhatsApp'),
        ('referral', 'Referral'),
        ('unknown', 'Unknown'),
    ]
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default='unknown',
        db_index=True,
        help_text="Deterministic channel from Boolean signal cascade"
    )

    # ─── Cross-Reference to Meta/Google Campaign Data ────────────────
    matched_campaign_id = models.CharField(
        max_length=255, blank=True, default='',
        help_text="ID of MetaCampaign or GoogleCampaign matched via utm_campaign"
    )
    matched_adset_id = models.CharField(
        max_length=255, blank=True, default='',
        help_text="ID of MetaAdSet matched via utm_content"
    )
    matched_ad_id = models.CharField(
        max_length=255, blank=True, default='',
        help_text="ID of MetaAd matched via utm_term"
    )
    matched_platform = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Which platform the match was found in: 'meta', 'google', etc."
    )

    # ─── Multi-Touch Journey (Phase 2 Placeholder) ───────────────────
    touch_journey = models.JSONField(
        default=list, blank=True,
        help_text="Future: Array of touchpoints from BridgeWorks pixel, e.g. "
                  "[{'source': 'google_ad', 'ts': '...'}, {'source': 'fb_retargeting', ...}]"
    )

    # ─── FlexyPe Session Tracking ────────────────────────────────────
    fp_id = models.CharField(
        max_length=255, blank=True, default='',
        db_index=True,
        help_text="FlexyPe session ID for multi-touch attribution"
    )
    referer = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Referer value from FlexyPe tracking script note_attributes"
    )

    # ─── Metadata ────────────────────────────────────────────────────
    SOURCE_CHOICES = [
        ('backfill', 'Historical Backfill'),
        ('webhook', 'Live Webhook'),
        ('pixel', 'BridgeWorks Pixel'),
    ]
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='backfill',
        help_text="How this attribution was created"
    )
    backfilled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Order Attribution'
        verbose_name_plural = 'Order Attributions'
        indexes = [
            models.Index(fields=['channel', '-backfilled_at'], name='idx_attr_channel_date'),
            models.Index(fields=['utm_source', 'utm_campaign'], name='idx_attr_src_camp'),
        ]

    def __str__(self):
        order_num = self.order.order_number if self.order_id else '?'
        return f"Attribution #{order_num} → {self.channel} ({self.utm_source})"
