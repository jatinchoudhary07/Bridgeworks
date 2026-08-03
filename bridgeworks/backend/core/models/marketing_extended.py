"""
Extended Marketing Models for BridgeWorks ERP
========================================
Covers: Social Media, Influencer, Offline, PR, Celebrity, Brand Monitoring,
        Attribution, Campaigns Hub, and Leads/CRM.

All models follow the unified architecture:
  Campaign → Activity → Asset → Audience → Spend → Performance → Revenue
"""
from django.db import models
from django.contrib.auth.models import User
from .store import ShopCredentials


# ═══════════════════════════════════════════════════════════════════════
# 1. CORE MARKETING TABLES (Foundation — shared by all sub-modules)
# ═══════════════════════════════════════════════════════════════════════

class MktCampaign(models.Model):
    """Central campaign table used by every marketing sub-module."""
    CAMPAIGN_TYPES = [
        ('social', 'Social Media'),
        ('offline', 'Offline / Events'),
        ('pr', 'Public Relations'),
        ('influencer', 'Influencer'),
        ('celebrity', 'Celebrity Endorsement'),
        ('ads', 'Paid Advertising'),
    ]
    OBJECTIVE_CHOICES = [
        ('sales', 'Sales'),
        ('awareness', 'Brand Awareness'),
        ('leads', 'Lead Generation'),
        ('engagement', 'Engagement'),
        ('traffic', 'Website Traffic'),
    ]
    STATUS_CHOICES = [
        ('planned', 'Planned'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_campaigns')
    name = models.CharField(max_length=300)
    campaign_type = models.CharField(max_length=20, choices=CAMPAIGN_TYPES, default='social')
    objective = models.CharField(max_length=20, choices=OBJECTIVE_CHOICES, default='sales')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planned')
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_campaigns')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.campaign_type})"


class MktChannel(models.Model):
    """Marketing channels / platforms."""
    CHANNEL_TYPES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('pr', 'PR / Media'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_channels')
    name = models.CharField(max_length=200)
    channel_type = models.CharField(max_length=10, choices=CHANNEL_TYPES, default='online')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return self.name


class MktCampaignChannel(models.Model):
    """M2M mapping of campaigns to channels."""
    campaign = models.ForeignKey(MktCampaign, on_delete=models.CASCADE, related_name='campaign_channels')
    channel = models.ForeignKey(MktChannel, on_delete=models.CASCADE, related_name='channel_campaigns')

    class Meta:
        app_label = 'core'
        unique_together = ('campaign', 'channel')


class MktCampaignGoal(models.Model):
    """KPI targets for a campaign."""
    campaign = models.ForeignKey(MktCampaign, on_delete=models.CASCADE, related_name='goals')
    metric_name = models.CharField(max_length=100)
    target_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        app_label = 'core'


class MktCampaignTag(models.Model):
    """Tags for campaign categorisation (Festive, Launch, Evergreen, etc.)."""
    campaign = models.ForeignKey(MktCampaign, on_delete=models.CASCADE, related_name='tags')
    tag_name = models.CharField(max_length=100)

    class Meta:
        app_label = 'core'


# ═══════════════════════════════════════════════════════════════════════
# 2. CONTENT / CREATIVE ASSET MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

class MktAsset(models.Model):
    """Creative asset (image, video, reel, poster, etc.)."""
    ASSET_TYPES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('reel', 'Reel'),
        ('banner', 'Banner'),
        ('poster', 'Poster'),
        ('document', 'Document'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_assets')
    name = models.CharField(max_length=300)
    asset_type = models.CharField(max_length=20, choices=ASSET_TYPES, default='image')
    file_url = models.URLField(max_length=1000, blank=True)
    file = models.FileField(upload_to='marketing/assets/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class MktAssetVersion(models.Model):
    """Version control for creative assets."""
    asset = models.ForeignKey(MktAsset, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField(default=1)
    file_url = models.URLField(max_length=1000, blank=True)
    file = models.FileField(upload_to='marketing/asset_versions/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['version_number']


class MktAssetTag(models.Model):
    """Tags for creative assets."""
    asset = models.ForeignKey(MktAsset, on_delete=models.CASCADE, related_name='asset_tags')
    tag = models.CharField(max_length=100)

    class Meta:
        app_label = 'core'


class MktAssetProduct(models.Model):
    """Link a creative asset to a Shopify product/SKU."""
    asset = models.ForeignKey(MktAsset, on_delete=models.CASCADE, related_name='asset_products')
    product_id = models.CharField(max_length=100, help_text="Shopify product ID")
    product_title = models.CharField(max_length=300, blank=True)

    class Meta:
        app_label = 'core'


# ═══════════════════════════════════════════════════════════════════════
# 3. SOCIAL MEDIA MARKETING
# ═══════════════════════════════════════════════════════════════════════

class SocialAccount(models.Model):
    """Connected social media accounts."""
    PLATFORMS = [
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('pinterest', 'Pinterest'),
        ('youtube', 'YouTube'),
        ('whatsapp', 'WhatsApp'),
        ('twitter', 'Twitter/X'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='social_accounts')
    platform = models.CharField(max_length=20, choices=PLATFORMS)
    account_name = models.CharField(max_length=200)
    account_id = models.CharField(max_length=200, blank=True)
    connected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'

    def __str__(self):
        return f"{self.platform} — {self.account_name}"


class SocialPost(models.Model):
    """Scheduled or published social media posts."""
    POST_TYPES = [
        ('reel', 'Reel'),
        ('carousel', 'Carousel'),
        ('static', 'Static Image'),
        ('story', 'Story'),
        ('video', 'Video'),
        ('text', 'Text Post'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('review', 'In Review'),
        ('approved', 'Approved'),
        ('scheduled', 'Scheduled'),
        ('published', 'Published'),
        ('failed', 'Failed'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='social_posts')
    campaign = models.ForeignKey(MktCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='social_posts')
    account = models.ForeignKey(SocialAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    asset = models.ForeignKey(MktAsset, on_delete=models.SET_NULL, null=True, blank=True, related_name='social_posts')
    caption = models.TextField(blank=True)
    post_type = models.CharField(max_length=20, choices=POST_TYPES, default='static')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.post_type} — {self.status}"


class SocialPostMetric(models.Model):
    """Performance metrics for a social post."""
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='metrics')
    impressions = models.IntegerField(default=0)
    reach = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)
    saves = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    engagement_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-recorded_at']


class SocialHashtag(models.Model):
    """Reusable hashtag bank."""
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='social_hashtags')
    hashtag = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True, help_text="e.g. luxury, bridal, daily wear")

    class Meta:
        app_label = 'core'

    def __str__(self):
        return self.hashtag


class SocialPostHashtag(models.Model):
    """M2M linking posts to hashtags."""
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='post_hashtags')
    hashtag = models.ForeignKey(SocialHashtag, on_delete=models.CASCADE, related_name='hashtag_posts')

    class Meta:
        app_label = 'core'
        unique_together = ('post', 'hashtag')


class SocialPostProduct(models.Model):
    """Link a social post to a Shopify product/SKU for SKU-level tracking."""
    post = models.ForeignKey(SocialPost, on_delete=models.CASCADE, related_name='post_products')
    product_id = models.CharField(max_length=100)
    product_title = models.CharField(max_length=300, blank=True)

    class Meta:
        app_label = 'core'


# ═══════════════════════════════════════════════════════════════════════
# 4. INFLUENCER / CREATOR MARKETING
# ═══════════════════════════════════════════════════════════════════════

class MktInfluencer(models.Model):
    """Influencer / creator database."""
    CATEGORIES = [
        ('fashion', 'Fashion'),
        ('bridal', 'Bridal'),
        ('lifestyle', 'Lifestyle'),
        ('beauty', 'Beauty'),
        ('luxury', 'Luxury'),
        ('celebrity', 'Celebrity'),
        ('micro', 'Micro-Influencer'),
        ('other', 'Other'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_influencers')
    name = models.CharField(max_length=200)
    handle = models.CharField(max_length=200, blank=True)
    platform = models.CharField(max_length=50, default='instagram')
    followers = models.IntegerField(default=0)
    engagement_rate = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    category = models.CharField(max_length=20, choices=CATEGORIES, default='fashion')
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-followers']

    def __str__(self):
        return f"{self.name} (@{self.handle})"


class MktInfluencerCampaign(models.Model):
    """Collaboration between an influencer and a campaign."""
    COLLAB_TYPES = [
        ('paid', 'Paid'),
        ('barter', 'Barter'),
        ('affiliate', 'Affiliate'),
        ('gifting', 'Gifting'),
    ]
    influencer = models.ForeignKey(MktInfluencer, on_delete=models.CASCADE, related_name='campaigns')
    campaign = models.ForeignKey(MktCampaign, on_delete=models.CASCADE, related_name='influencer_campaigns')
    collaboration_type = models.CharField(max_length=20, choices=COLLAB_TYPES, default='paid')
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    contract_url = models.URLField(blank=True)
    deliverables_description = models.TextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'


class MktInfluencerDeliverable(models.Model):
    """Individual deliverable for an influencer campaign."""
    DELIVERABLE_TYPES = [
        ('post', 'Instagram Post'),
        ('reel', 'Reel'),
        ('story', 'Story'),
        ('video', 'YouTube Video'),
        ('blog', 'Blog Post'),
        ('event', 'Event Appearance'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('delivered', 'Delivered'),
        ('approved', 'Approved'),
    ]
    influencer_campaign = models.ForeignKey(MktInfluencerCampaign, on_delete=models.CASCADE, related_name='deliverables')
    deliverable_type = models.CharField(max_length=20, choices=DELIVERABLE_TYPES, default='post')
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    class Meta:
        app_label = 'core'


class MktInfluencerPost(models.Model):
    """Content posted by an influencer for a campaign."""
    influencer_campaign = models.ForeignKey(MktInfluencerCampaign, on_delete=models.CASCADE, related_name='posts')
    post_url = models.URLField(blank=True)
    platform = models.CharField(max_length=50, default='instagram')
    posted_at = models.DateTimeField(null=True, blank=True)
    asset = models.ForeignKey(MktAsset, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        app_label = 'core'


class MktInfluencerMetric(models.Model):
    """Performance metrics for an influencer post."""
    influencer_post = models.ForeignKey(MktInfluencerPost, on_delete=models.CASCADE, related_name='metrics')
    impressions = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)
    shares = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    orders_generated = models.IntegerField(default=0)
    revenue_generated = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        app_label = 'core'


# ═══════════════════════════════════════════════════════════════════════
# 5. PR / MEDIA COVERAGE
# ═══════════════════════════════════════════════════════════════════════

class MktMediaPublication(models.Model):
    """Publication / media house database."""
    PUB_TYPES = [
        ('magazine', 'Magazine'),
        ('newspaper', 'Newspaper'),
        ('blog', 'Blog / Online Media'),
        ('digital', 'Digital Media'),
        ('tv', 'Television'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_publications')
    name = models.CharField(max_length=300)
    pub_type = models.CharField(max_length=20, choices=PUB_TYPES, default='magazine')
    audience_size = models.IntegerField(default=0, help_text="Estimated readership / audience")
    website_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['name']

    def __str__(self):
        return self.name


class MktJournalist(models.Model):
    """Journalists / editors for PR outreach."""
    publication = models.ForeignKey(MktMediaPublication, on_delete=models.CASCADE, related_name='journalists')
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    beat = models.CharField(max_length=100, blank=True, help_text="e.g. Fashion, Luxury, Lifestyle")

    class Meta:
        app_label = 'core'


class MktPROutreach(models.Model):
    """PR pitch / outreach tracking."""
    STATUS_CHOICES = [
        ('sent', 'Pitch Sent'),
        ('follow_up', 'Follow-up'),
        ('replied', 'Replied'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('no_response', 'No Response'),
    ]
    campaign = models.ForeignKey(MktCampaign, on_delete=models.CASCADE, related_name='pr_outreach')
    journalist = models.ForeignKey(MktJournalist, on_delete=models.SET_NULL, null=True, blank=True, related_name='outreach')
    publication = models.ForeignKey(MktMediaPublication, on_delete=models.SET_NULL, null=True, blank=True)
    outreach_date = models.DateField(auto_now_add=True)
    pitch_subject = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    notes = models.TextField(blank=True)

    class Meta:
        app_label = 'core'
        ordering = ['-outreach_date']


class MktPRCoverage(models.Model):
    """PR output — articles, features, mentions."""
    COVERAGE_TYPES = [
        ('organic', 'Organic'),
        ('paid', 'Paid PR'),
        ('earned', 'Earned Media'),
    ]
    campaign = models.ForeignKey(MktCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='pr_coverage')
    publication = models.ForeignKey(MktMediaPublication, on_delete=models.SET_NULL, null=True, blank=True)
    article_title = models.CharField(max_length=500)
    article_url = models.URLField(blank=True)
    coverage_type = models.CharField(max_length=20, choices=COVERAGE_TYPES, default='organic')
    publish_date = models.DateField(null=True, blank=True)
    estimated_reach = models.IntegerField(default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-publish_date']


# ═══════════════════════════════════════════════════════════════════════
# 6. CELEBRITY / SPOTTING
# ═══════════════════════════════════════════════════════════════════════

class MktCelebrity(models.Model):
    """Celebrity / stylist database."""
    PROFESSION_CHOICES = [
        ('actor', 'Actor'),
        ('model', 'Model'),
        ('stylist', 'Stylist'),
        ('designer', 'Designer'),
        ('musician', 'Musician'),
        ('influencer', 'Digital Influencer'),
        ('tv_personality', 'TV Personality'),
        ('other', 'Other'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_celebrities')
    name = models.CharField(max_length=200)
    profession = models.CharField(max_length=20, choices=PROFESSION_CHOICES, default='actor')
    social_followers = models.IntegerField(default=0)
    agency = models.CharField(max_length=200, blank=True)
    contact_person = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['name']
        verbose_name_plural = 'Celebrities'

    def __str__(self):
        return f"{self.name} ({self.profession})"


class MktCelebrityCampaign(models.Model):
    """Endorsement / collaboration with a celebrity."""
    ENDORSEMENT_TYPES = [
        ('event', 'Event Appearance'),
        ('photoshoot', 'Photoshoot'),
        ('social_post', 'Social Media Post'),
        ('ambassador', 'Brand Ambassador'),
        ('seeding', 'Product Seeding'),
    ]
    celebrity = models.ForeignKey(MktCelebrity, on_delete=models.CASCADE, related_name='celeb_campaigns')
    campaign = models.ForeignKey(MktCampaign, on_delete=models.CASCADE, related_name='celebrity_campaigns')
    endorsement_type = models.CharField(max_length=20, choices=ENDORSEMENT_TYPES, default='event')
    contract_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    contract_start = models.DateField(null=True, blank=True)
    contract_end = models.DateField(null=True, blank=True)
    usage_rights = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'


class MktCelebritySpotting(models.Model):
    """Track when a celebrity was spotted wearing a product."""
    celebrity = models.ForeignKey(MktCelebrity, on_delete=models.CASCADE, related_name='spottings')
    product_id = models.CharField(max_length=100, blank=True, help_text="Shopify product ID")
    product_title = models.CharField(max_length=300, blank=True)
    event_name = models.CharField(max_length=300, blank=True)
    spotting_date = models.DateField(null=True, blank=True)
    image_url = models.URLField(blank=True)
    media_links = models.TextField(blank=True, help_text="Comma-separated media coverage URLs")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-spotting_date']


class MktCelebritySpottingMetric(models.Model):
    """Impact metrics after a celebrity spotting."""
    spotting = models.ForeignKey(MktCelebritySpotting, on_delete=models.CASCADE, related_name='metrics')
    social_mentions = models.IntegerField(default=0)
    media_pickups = models.IntegerField(default=0)
    reach_estimate = models.IntegerField(default=0)
    sales_impact = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'


# ═══════════════════════════════════════════════════════════════════════
# 7. OFFLINE MARKETING
# ═══════════════════════════════════════════════════════════════════════

class MktOfflineEvent(models.Model):
    """Offline marketing events — exhibitions, pop-ups, trunk shows, etc."""
    EVENT_TYPES = [
        ('exhibition', 'Exhibition'),
        ('popup', 'Pop-Up Store'),
        ('trunk_show', 'Trunk Show'),
        ('retail', 'Retail Activation'),
        ('society', 'Society Event'),
        ('wedding_fair', 'Wedding Fair'),
        ('other', 'Other'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_offline_events')
    campaign = models.ForeignKey(MktCampaign, on_delete=models.SET_NULL, null=True, blank=True, related_name='offline_events')
    event_name = models.CharField(max_length=300)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='exhibition')
    city = models.CharField(max_length=100)
    venue = models.CharField(max_length=300, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.event_name} — {self.city}"


class MktOfflineEventInventory(models.Model):
    """SKU-level inventory tracking per offline event."""
    event = models.ForeignKey(MktOfflineEvent, on_delete=models.CASCADE, related_name='inventory')
    product_id = models.CharField(max_length=100, help_text="Shopify product ID")
    product_title = models.CharField(max_length=300, blank=True)
    qty_sent = models.IntegerField(default=0)
    qty_sold = models.IntegerField(default=0)
    qty_returned = models.IntegerField(default=0)

    class Meta:
        app_label = 'core'


class MktOfflineEventSale(models.Model):
    """Sales recorded at an offline event."""
    event = models.ForeignKey(MktOfflineEvent, on_delete=models.CASCADE, related_name='sales')
    order_id = models.CharField(max_length=100, blank=True)
    order_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sale_date = models.DateField(auto_now_add=True)

    class Meta:
        app_label = 'core'


class MktOfflineLead(models.Model):
    """Leads captured at offline events."""
    INTEREST_TYPES = [
        ('bridal', 'Bridal'),
        ('gifting', 'Gifting'),
        ('daily_wear', 'Daily Wear'),
        ('custom', 'Customization'),
        ('bulk', 'Bulk Order'),
        ('other', 'Other'),
    ]
    event = models.ForeignKey(MktOfflineEvent, on_delete=models.CASCADE, related_name='leads')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    interest_type = models.CharField(max_length=20, choices=INTEREST_TYPES, default='bridal')
    budget_range = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-captured_at']


class MktOfflineExpense(models.Model):
    """Expense tracking per offline event."""
    EXPENSE_TYPES = [
        ('stall_rent', 'Stall Rent'),
        ('travel', 'Travel & Stay'),
        ('staff', 'Staff Cost'),
        ('logistics', 'Logistics'),
        ('marketing_material', 'Marketing Material'),
        ('setup', 'Setup & Decoration'),
        ('other', 'Other'),
    ]
    event = models.ForeignKey(MktOfflineEvent, on_delete=models.CASCADE, related_name='expenses')
    expense_type = models.CharField(max_length=30, choices=EXPENSE_TYPES, default='stall_rent')
    description = models.CharField(max_length=300, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense_date = models.DateField(auto_now_add=True)

    class Meta:
        app_label = 'core'


# ═══════════════════════════════════════════════════════════════════════
# 8. MARKETING FINANCE
# ═══════════════════════════════════════════════════════════════════════

class MktSpend(models.Model):
    """Marketing spend tracking per campaign/channel."""
    SPEND_TYPES = [
        ('ads', 'Advertising'),
        ('influencer', 'Influencer'),
        ('pr', 'Public Relations'),
        ('event', 'Events'),
        ('content', 'Content Production'),
        ('other', 'Other'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_spend')
    campaign = models.ForeignKey(MktCampaign, on_delete=models.SET_NULL, null=True, blank=True)
    channel = models.ForeignKey(MktChannel, on_delete=models.SET_NULL, null=True, blank=True)
    spend_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    spend_date = models.DateField()
    spend_type = models.CharField(max_length=20, choices=SPEND_TYPES, default='ads')
    notes = models.TextField(blank=True)

    class Meta:
        app_label = 'core'
        ordering = ['-spend_date']


class MktBudget(models.Model):
    """Budget allocation for a campaign."""
    campaign = models.ForeignKey(MktCampaign, on_delete=models.CASCADE, related_name='budgets')
    planned_budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    spent_budget = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'


# ═══════════════════════════════════════════════════════════════════════
# 9. ATTRIBUTION / PERFORMANCE
# ═══════════════════════════════════════════════════════════════════════

class MktAttribution(models.Model):
    """Revenue attribution tracking."""
    ATTRIBUTION_TYPES = [
        ('first_touch', 'First Touch'),
        ('last_touch', 'Last Touch'),
        ('assisted', 'Assisted'),
        ('linear', 'Linear'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_attributions')
    campaign = models.ForeignKey(MktCampaign, on_delete=models.SET_NULL, null=True, blank=True)
    order_id = models.CharField(max_length=100)
    attribution_type = models.CharField(max_length=20, choices=ATTRIBUTION_TYPES, default='last_touch')
    attributed_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'


class MktCampaignPerformance(models.Model):
    """Aggregated performance snapshot per campaign."""
    campaign = models.ForeignKey(MktCampaign, on_delete=models.CASCADE, related_name='performance')
    date = models.DateField()
    impressions = models.IntegerField(default=0)
    clicks = models.IntegerField(default=0)
    leads = models.IntegerField(default=0)
    orders = models.IntegerField(default=0)
    revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    spend = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        app_label = 'core'
        unique_together = ('campaign', 'date')
        ordering = ['-date']


# ═══════════════════════════════════════════════════════════════════════
# 10. LEADS / CRM INTEGRATION
# ═══════════════════════════════════════════════════════════════════════

class MktLead(models.Model):
    """Marketing-generated leads from any channel."""
    SOURCE_CHOICES = [
        ('social', 'Social Media'),
        ('influencer', 'Influencer'),
        ('exhibition', 'Exhibition'),
        ('pr', 'PR Coverage'),
        ('celebrity', 'Celebrity Spotting'),
        ('ads', 'Paid Ads'),
        ('organic', 'Organic'),
        ('referral', 'Referral'),
    ]
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('converted', 'Converted'),
        ('lost', 'Lost'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_leads')
    campaign = models.ForeignKey(MktCampaign, on_delete=models.SET_NULL, null=True, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='social')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']


class MktLeadActivity(models.Model):
    """Activity log for a marketing lead."""
    lead = models.ForeignKey(MktLead, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    activity_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-activity_date']


# ═══════════════════════════════════════════════════════════════════════
# 11. BRAND MONITORING
# ═══════════════════════════════════════════════════════════════════════

class MktBrandMention(models.Model):
    """Social / web brand mentions."""
    SENTIMENT_CHOICES = [
        ('positive', 'Positive'),
        ('neutral', 'Neutral'),
        ('negative', 'Negative'),
    ]
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_brand_mentions')
    platform = models.CharField(max_length=100)
    mention_link = models.URLField(blank=True)
    sentiment = models.CharField(max_length=10, choices=SENTIMENT_CHOICES, default='neutral')
    reach_estimate = models.IntegerField(default=0)
    mention_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-mention_date']


class MktBrandMetric(models.Model):
    """Daily brand health metrics."""
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='mkt_brand_metrics')
    date = models.DateField()
    branded_search_volume = models.IntegerField(default=0)
    social_mentions_count = models.IntegerField(default=0)
    direct_traffic = models.IntegerField(default=0)
    follower_count = models.IntegerField(default=0)

    class Meta:
        app_label = 'core'
        unique_together = ('shop', 'date')
        ordering = ['-date']
