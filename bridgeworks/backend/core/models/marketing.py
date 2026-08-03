from django.db import models
from .store import ShopCredentials
from .constants import encrypt_data, decrypt_data

PLATFORM_CHOICES = [
    ('Meta', 'Meta'),
    ('Google', 'Google Ads'),
    ('TikTok', 'TikTok Ads'),
]

class MarketingCredential(models.Model):
    """
    Stores API credentials per shop per ad platform.
    Typically one account per platform, but supports multiple.
    """
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='marketing_credentials')
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='Meta')
    ad_account_id = models.CharField(max_length=100, help_text="e.g. act_123456789")
    
    # Encrypted credentials
    access_token_encrypted = models.TextField(help_text="System access token")
    app_id_encrypted = models.CharField(max_length=255, null=True, blank=True)
    app_secret_encrypted = models.CharField(max_length=255, null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('shop', 'platform', 'ad_account_id')
        verbose_name = 'Marketing Credential'
        verbose_name_plural = 'Marketing Credentials'

    def __str__(self):
        return f"{self.shop.organization_id} - {self.platform} ({self.ad_account_id})"

    # Getters and Setters for Encryption
    def set_access_token(self, token):
        self.access_token_encrypted = encrypt_data(token)
        
    def get_access_token(self):
        return decrypt_data(self.access_token_encrypted)

    def set_app_id(self, app_id):
        if app_id:
            self.app_id_encrypted = encrypt_data(app_id)
            
    def get_app_id(self):
        if self.app_id_encrypted:
            return decrypt_data(self.app_id_encrypted)
        return None

    def set_app_secret(self, app_secret):
        if app_secret:
            self.app_secret_encrypted = encrypt_data(app_secret)
            
    def get_app_secret(self):
        if self.app_secret_encrypted:
            return decrypt_data(self.app_secret_encrypted)
        return None


class MarketingSettings(models.Model):
    """
    Per-shop marketing settings. Stores configurable values like GST rate.
    """
    shop = models.OneToOneField(ShopCredentials, on_delete=models.CASCADE, related_name='marketing_settings')
    gst_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=18.00,
        help_text="GST percentage applied to ad spend (e.g. 18.00 for India)"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Marketing Settings'
        verbose_name_plural = 'Marketing Settings'

    def __str__(self):
        return f"{self.shop.organization_id} - GST: {self.gst_rate}%"


class MetaCampaign(models.Model):
    """
    Stores structural data for Meta Campaigns (Status, Budget) 
    synced directly from the 'Campaign Objects' API.
    """
    credential = models.ForeignKey(MarketingCredential, on_delete=models.CASCADE, related_name='campaigns')
    campaign_id = models.CharField(max_length=255)
    name = models.CharField(max_length=500)
    status = models.CharField(max_length=50, default='UNKNOWN')
    effective_status = models.CharField(max_length=50, default='UNKNOWN')
    daily_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    objective = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'campaign_id')
        verbose_name = 'Meta Campaign'
        verbose_name_plural = 'Meta Campaigns'

    def __str__(self):
        return f"{self.name} ({self.status})"


class CampaignDailyMetric(models.Model):
    """
    Daily snapshot of campaign performance fetched via silent poller.
    Allows instant dashboard loading without hitting Meta's API limits.
    """
    credential = models.ForeignKey(MarketingCredential, on_delete=models.CASCADE, related_name='daily_metrics')
    date = models.DateField()
    
    campaign_id = models.CharField(max_length=255)
    campaign_name = models.CharField(max_length=500)
    
    # Financial Metrics
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    roas = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cost_per_purchase_cpa = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Interaction Metrics
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    purchases = models.IntegerField(default=0)
    
    # Funnel Metrics
    reach = models.IntegerField(default=0)
    engagement = models.IntegerField(default=0)
    view_content = models.IntegerField(default=0)
    add_to_cart = models.IntegerField(default=0)
    initiate_checkout = models.IntegerField(default=0)
    add_payment_info = models.IntegerField(default=0)
    outbound_clicks = models.IntegerField(default=0)
    
    # Ratios
    cpc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cpm = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ctr = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'date', 'campaign_id')
        indexes = [
            models.Index(fields=['credential', 'date']),
        ]
        ordering = ['-date', '-spend']

    def __str__(self):
        return f"{self.campaign_name} on {self.date}"


class MetaAdSet(models.Model):
    """
    Stores structural data for Meta Ad Sets synced from get_ad_sets().
    """
    credential = models.ForeignKey(MarketingCredential, on_delete=models.CASCADE, related_name='adsets')
    adset_id = models.CharField(max_length=255)
    campaign_id = models.CharField(max_length=255)
    name = models.CharField(max_length=500)
    status = models.CharField(max_length=50, default='UNKNOWN')
    effective_status = models.CharField(max_length=50, default='UNKNOWN')
    daily_budget = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'adset_id')
        verbose_name = 'Meta Ad Set'
        verbose_name_plural = 'Meta Ad Sets'

    def __str__(self):
        return f"{self.name} ({self.status})"


class MetaAd(models.Model):
    """
    Stores structural data for Meta Ads synced from get_ads().
    """
    credential = models.ForeignKey(MarketingCredential, on_delete=models.CASCADE, related_name='ads')
    ad_id = models.CharField(max_length=255)
    adset_id = models.CharField(max_length=255)
    campaign_id = models.CharField(max_length=255)
    name = models.CharField(max_length=500)
    status = models.CharField(max_length=50, default='UNKNOWN')
    effective_status = models.CharField(max_length=50, default='UNKNOWN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'ad_id')
        verbose_name = 'Meta Ad'
        verbose_name_plural = 'Meta Ads'

    def __str__(self):
        return f"{self.name} ({self.status})"


class AdSetDailyMetric(models.Model):
    """
    Daily snapshot of ad set performance.
    """
    credential = models.ForeignKey(MarketingCredential, on_delete=models.CASCADE, related_name='adset_daily_metrics')
    date = models.DateField()
    adset_id = models.CharField(max_length=255)
    adset_name = models.CharField(max_length=500)
    campaign_id = models.CharField(max_length=255)

    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    roas = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cost_per_purchase_cpa = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    purchases = models.IntegerField(default=0)
    reach = models.IntegerField(default=0)
    engagement = models.IntegerField(default=0)
    view_content = models.IntegerField(default=0)
    add_to_cart = models.IntegerField(default=0)
    initiate_checkout = models.IntegerField(default=0)
    add_payment_info = models.IntegerField(default=0)
    outbound_clicks = models.IntegerField(default=0)
    cpc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cpm = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ctr = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'date', 'adset_id')
        indexes = [
            models.Index(fields=['credential', 'date']),
            models.Index(fields=['campaign_id']),
        ]
        ordering = ['-date', '-spend']

    def __str__(self):
        return f"{self.adset_name} on {self.date}"


class AdDailyMetric(models.Model):
    """
    Daily snapshot of individual ad performance.
    """
    credential = models.ForeignKey(MarketingCredential, on_delete=models.CASCADE, related_name='ad_daily_metrics')
    date = models.DateField()
    ad_id = models.CharField(max_length=255)
    ad_name = models.CharField(max_length=500)
    adset_id = models.CharField(max_length=255)
    campaign_id = models.CharField(max_length=255)

    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    roas = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cost_per_purchase_cpa = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    purchases = models.IntegerField(default=0)
    reach = models.IntegerField(default=0)
    engagement = models.IntegerField(default=0)
    view_content = models.IntegerField(default=0)
    add_to_cart = models.IntegerField(default=0)
    initiate_checkout = models.IntegerField(default=0)
    add_payment_info = models.IntegerField(default=0)
    outbound_clicks = models.IntegerField(default=0)
    cpc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cpm = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ctr = models.DecimalField(max_digits=10, decimal_places=4, default=0.0000)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'date', 'ad_id')
        indexes = [
            models.Index(fields=['credential', 'date']),
            models.Index(fields=['adset_id']),
            models.Index(fields=['campaign_id']),
        ]
        ordering = ['-date', '-spend']

    def __str__(self):
        return f"{self.ad_name} on {self.date}"

from django.contrib.auth.models import User
import uuid

class MarketingAIChatSession(models.Model):
    """
    Groups a single conversational thread for the AI agent.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='marketing_ai_sessions')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='marketing_ai_sessions')
    title = models.CharField(max_length=255, help_text="Chat title, e.g., 'Last 30 Days Analysis'")
    date_preset = models.CharField(max_length=50, null=True, blank=True)
    model_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"AI Session: {self.title}"


class MarketingAIChatMessage(models.Model):
    """
    Individual message inside an AI Chat Session.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('ai', 'AI'),
    ]
    session = models.ForeignKey(MarketingAIChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    
    # Store plain string message
    content = models.TextField(blank=True)
    
    # Store rich initial insight JSON for the dashboard rendering
    structured_data = models.JSONField(null=True, blank=True)

    # Attached file (PDF, Image, Word, Excel)
    attachment = models.FileField(upload_to='marketing_ai_uploads/', null=True, blank=True)
    attachment_name = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.role} in {self.session.title}"


# =============================================================================
# Logistics Aura AI Chat Models
# =============================================================================

class LogisticsAIChatSession(models.Model):
    """
    Groups a single conversational thread for the Logistics Aura AI agent.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='logistics_ai_sessions')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='logistics_ai_sessions')
    title = models.CharField(max_length=255, help_text="Chat title, e.g., 'Last 30 Days Logistics Analysis'")
    model_name = models.CharField(max_length=100, default='gemini-2.5-flash')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"Logistics AI Session: {self.title}"


class LogisticsAIChatMessage(models.Model):
    """
    Individual message inside a Logistics AI Chat Session.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('ai', 'AI'),
    ]
    session = models.ForeignKey(LogisticsAIChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField(blank=True)
    structured_data = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.role} in {self.session.title}"


class GoogleAdsCredential(models.Model):
    """
    Stores API credentials for Google Ads per shop.
    """
    shop = models.ForeignKey('ShopCredentials', on_delete=models.CASCADE, related_name='google_ads_credentials')
    
    # Non-encrypted identifiers
    client_id = models.CharField(max_length=255, null=True, blank=True)
    login_customer_id = models.CharField(max_length=100, help_text="Manager ID")
    customer_id = models.CharField(max_length=100, help_text="Target Ad Account ID")
    
    # Encrypted sensitive credentials
    developer_token_encrypted = models.CharField(max_length=255, null=True, blank=True)
    client_secret_encrypted = models.CharField(max_length=255, null=True, blank=True)
    refresh_token_encrypted = models.TextField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('shop', 'customer_id')
        verbose_name = 'Google Ads Credential'
        verbose_name_plural = 'Google Ads Credentials'

    def __str__(self):
        return f"{self.shop.organization_id} - Google Ads ({self.customer_id})"

    def set_developer_token(self, token):
        if token: self.developer_token_encrypted = encrypt_data(token)
    def get_developer_token(self):
        return decrypt_data(self.developer_token_encrypted) if self.developer_token_encrypted else None

    def set_client_secret(self, secret):
        if secret: self.client_secret_encrypted = encrypt_data(secret)
    def get_client_secret(self):
        return decrypt_data(self.client_secret_encrypted) if self.client_secret_encrypted else None

    def set_refresh_token(self, token):
        if token: self.refresh_token_encrypted = encrypt_data(token)
    def get_refresh_token(self):
        return decrypt_data(self.refresh_token_encrypted) if self.refresh_token_encrypted else None


class GoogleCampaignDailyMetric(models.Model):
    """
    Daily snapshot of Google Ads campaign performance.
    """
    credential = models.ForeignKey(GoogleAdsCredential, on_delete=models.CASCADE, related_name='daily_metrics')
    date = models.DateField()
    
    campaign_name = models.CharField(max_length=500)
    
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    conversions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Expanded Financials/Impression Share
    search_impression_share = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    search_budget_lost_impression_share = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'date', 'campaign_name')
        indexes = [
            models.Index(fields=['credential', 'date']),
        ]
        ordering = ['-date', '-spend']

    def __str__(self):
        return f"{self.campaign_name} on {self.date}"

class GoogleSearchTermMetric(models.Model):
    """
    Search term level performance for Google Ads.
    """
    credential = models.ForeignKey(GoogleAdsCredential, on_delete=models.CASCADE, related_name='search_term_metrics')
    date = models.DateField()
    campaign_name = models.CharField(max_length=500)
    search_term = models.CharField(max_length=500)

    clicks = models.IntegerField(default=0)
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    conversions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'date', 'campaign_name', 'search_term')
        indexes = [
            models.Index(fields=['credential', 'date']),
        ]

class MetaDemographicMetric(models.Model):
    """
    Demographic (Age, Gender) metrics for Meta Ads.
    """
    DIMENSION_CHOICES = [
        ('age', 'Age Range'),
        ('gender', 'Gender'),
        ('country', 'Country'),
        ('region', 'Region'),
    ]
    credential = models.ForeignKey(MarketingCredential, on_delete=models.CASCADE, related_name='demographic_metrics')
    date = models.DateField()
    dimension = models.CharField(max_length=20, choices=DIMENSION_CHOICES)
    dimension_value = models.CharField(max_length=255)

    clicks = models.IntegerField(default=0)
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    purchases = models.IntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    impressions = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'date', 'dimension', 'dimension_value')
        indexes = [
            models.Index(fields=['credential', 'date', 'dimension']),
        ]


class GoogleDemographicMetric(models.Model):
    """
    Demographic (Age, Gender, Device, Location) metrics for Google Ads.
    """
    DIMENSION_CHOICES = [
        ('age', 'Age Range'),
        ('gender', 'Gender'),
        ('device', 'Device'),
        ('location', 'Location (Region)'),
    ]
    credential = models.ForeignKey(GoogleAdsCredential, on_delete=models.CASCADE, related_name='demographic_metrics')
    date = models.DateField()
    dimension = models.CharField(max_length=20, choices=DIMENSION_CHOICES)
    dimension_value = models.CharField(max_length=255)

    clicks = models.IntegerField(default=0)
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    conversions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'date', 'dimension', 'dimension_value')
        indexes = [
            models.Index(fields=['credential', 'date', 'dimension']),
        ]

class GoogleAdPerformanceMetric(models.Model):
    """
    Creative level performance (headlines, descriptions) for Google Ads.
    """
    credential = models.ForeignKey(GoogleAdsCredential, on_delete=models.CASCADE, related_name='ad_performance_metrics')
    date = models.DateField()
    campaign_name = models.CharField(max_length=500)
    ad_group_name = models.CharField(max_length=500)
    ad_id = models.CharField(max_length=100)

    # Store creative content as JSON
    headlines = models.JSONField(default=list, blank=True)
    descriptions = models.JSONField(default=list, blank=True)

    clicks = models.IntegerField(default=0)
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    conversions = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('credential', 'date', 'ad_id')
        indexes = [
            models.Index(fields=['credential', 'date']),
        ]


class StoreFinancials(models.Model):
    """
    Per-workspace financial constraints used for profitability calculations.
    Stores COGS percentage, shipping cost, and performance targets.
    """
    shop = models.OneToOneField(ShopCredentials, on_delete=models.CASCADE, related_name='store_financials')
    average_cogs_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, default=30.00,
        help_text="Average Cost of Goods Sold as a percentage (e.g. 30.00 for 30%)"
    )
    shipping_cost_per_order = models.DecimalField(
        max_digits=10, decimal_places=2, default=50.00,
        help_text="Average shipping cost per order in store currency (e.g. ₹50)"
    )
    target_roas = models.DecimalField(
        max_digits=6, decimal_places=2, default=3.00,
        help_text="Target Return on Ad Spend (e.g. 3.00 means 3x)"
    )
    target_cpa = models.DecimalField(
        max_digits=10, decimal_places=2, default=500.00,
        help_text="Target Cost Per Acquisition in store currency (e.g. ₹500)"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Store Financials'
        verbose_name_plural = 'Store Financials'

    def __str__(self):
        return f"{self.shop.organization_id} — COGS: {self.average_cogs_percentage}%, Shipping: ₹{self.shipping_cost_per_order}"


class MarketingAlert(models.Model):
    """
    AI-generated watchdog alerts for anomalous metric changes.
    Created by the daily anomaly detection task when CPA spikes or ROAS drops.
    """
    ALERT_TYPE_CHOICES = [
        ('cpa_spike', 'CPA Spike'),
        ('roas_drop', 'ROAS Drop'),
        ('general', 'General'),
    ]
    SEVERITY_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='marketing_alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES, default='general')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='warning')
    title = models.CharField(max_length=300)
    message = models.TextField(help_text="AI-generated alert message from Gemini")
    metric_data = models.JSONField(
        default=dict, blank=True,
        help_text="Stores delta values, 7-day avg, today's values for context"
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        verbose_name = 'Marketing Alert'
        verbose_name_plural = 'Marketing Alerts'

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title} ({self.shop.organization_id})"


class ProductionSoftwareCredential(models.Model):
    """
    Stores the external Production Software API connection details per shop.
    The API key is encrypted at rest via Fernet.
    """
    shop = models.OneToOneField(
        ShopCredentials,
        on_delete=models.CASCADE,
        related_name='production_software_credential',
    )
    api_url = models.URLField(max_length=500, blank=True, default='')
    api_key_encrypted = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = 'Production Software Credential'
        verbose_name_plural = 'Production Software Credentials'

    def __str__(self):
        return f"{self.shop.organization_id} - Production Software"

    def set_api_key(self, key):
        if key:
            self.api_key_encrypted = encrypt_data(key)

    def get_api_key(self):
        return decrypt_data(self.api_key_encrypted) if self.api_key_encrypted else ''
