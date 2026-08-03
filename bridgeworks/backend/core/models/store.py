from django.db import models
from django.contrib.auth import get_user_model
from .constants import encrypt_data, decrypt_data

User = get_user_model()


class ShopCredentials(models.Model):
    owner = models.OneToOneField(User, on_delete=models.CASCADE, related_name='shop_credentials')
    
    organization_id = models.CharField(max_length=50, unique=True, db_index=True)
    store_name = models.CharField(max_length=150, blank=True, default='', help_text="Human-readable store/brand name, e.g. 'Janki Jewels'")
    
    # --- Shop Profile Fields ---
    phone_number = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    license_key = models.CharField(max_length=255, blank=True, default='')
    gst_registration = models.CharField(
        max_length=50, 
        choices=[('registered', 'Registered'), ('unregistered', 'Unregistered')], 
        default='unregistered',
        blank=True
    )
    timezone = models.CharField(max_length=100, default='Asia/Kolkata', blank=True)
    legal_business_name = models.CharField(max_length=255, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    gst_number = models.CharField(max_length=50, blank=True, default='')
    billing_address = models.TextField(blank=True, default='')
    store_url = models.URLField(max_length=255, blank=True, default='')
    logo = models.ImageField(upload_to='shop_logos/', blank=True, null=True)
    
    # --- Encrypted Keys ---
    shopify_api_key_encrypted = models.CharField(max_length=255, null=True, blank=True)
    shopify_api_password_encrypted = models.CharField(max_length=255, null=True, blank=True)
    shopify_shop_url_encrypted = models.URLField(max_length=255, null=True, blank=True)
    shopify_webhook_secret_encrypted = models.CharField(max_length=255, null=True, blank=True)
    shopify_order_prefix = models.CharField(max_length=20, default='JANKI')
    shopify_api_version = models.CharField(max_length=10, default='2024-07')

    # --- Currency Settings ---
    # ISO 4217 currency code, e.g. 'INR', 'USD', 'EUR', 'GBP', 'AED'
    currency = models.CharField(max_length=8, default='INR')
    # BCP 47 locale for number formatting, e.g. 'en-IN', 'en-US', 'de-DE'
    currency_locale = models.CharField(max_length=16, default='en-IN')

    # --- OAuth Fields ---
    myshopify_domain = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    shopify_access_token_encrypted = models.CharField(max_length=255, null=True, blank=True)
    auth_method = models.CharField(
        max_length=20,
        choices=[('legacy', 'Legacy (API Key)'), ('oauth', 'OAuth (Partner App)')],
        default='legacy'
    )
    shipway_email_encrypted = models.CharField(max_length=255)
    shipway_license_key_encrypted = models.CharField(max_length=255)
    return_prime_token_encrypted = models.CharField(max_length=255, null=True, blank=True)
    onboarding_complete = models.BooleanField(default=False)

    # --- Blue Dart API Integration ---
    bluedart_client_id = models.CharField(max_length=255, null=True, blank=True)
    bluedart_client_secret = models.CharField(max_length=255, null=True, blank=True)
    bluedart_login_id = models.CharField(max_length=255, null=True, blank=True)
    bluedart_licence_key = models.CharField(max_length=255, null=True, blank=True)
    bluedart_api_type = models.CharField(max_length=1, default="S", help_text="'S' for Sandbox, 'P' for Production")
    bluedart_jwt_token = models.TextField(null=True, blank=True)
    bluedart_jwt_expiry = models.DateTimeField(null=True, blank=True)

    # --- Chatwoot Outbound CRM Integration ---
    chatwoot_endpoint = models.CharField(
        max_length=500, 
        null=True, 
        blank=True, 
        help_text="Webhook or API endpoint for Chatwoot outbound integration"
    )
    chatwoot_api_key_encrypted = models.CharField(
        max_length=255, 
        null=True, 
        blank=True, 
        help_text="Encrypted API token/key for Chatwoot"
    )

    # --- Configurable Shipway Settings ---
    shipway_warehouse_id = models.IntegerField(default=39842, blank=True, null=True)
    shipway_return_warehouse_id = models.IntegerField(default=39842, blank=True, null=True)
    shipway_order_weight = models.IntegerField(default=500, blank=True, null=True)
    shipway_box_length = models.IntegerField(default=10, blank=True, null=True)
    shipway_box_breadth = models.IntegerField(default=10, blank=True, null=True)
    shipway_box_height = models.IntegerField(default=10, blank=True, null=True)
    shipway_invoice_number_prefix = models.CharField(max_length=10, default="N", blank=True)
    shipway_primary_carrier_id = models.CharField(max_length=50, default="82600", blank=True)
    shipway_primary_carrier_title = models.CharField(max_length=100, default="Bluedart Direct - Surface", blank=True)
    shipway_fallback_carrier_id = models.CharField(max_length=50, default="2", blank=True)
    shipway_fallback_carrier_title = models.CharField(max_length=100, default="Direct Delhivery", blank=True)
    shipway_store_code = models.IntegerField(default=44180, blank=True, null=True)
    skip_shipway_pii_sync = models.BooleanField(
        default=False,
        help_text="Skip fetching customer PII from Shipway (enable if Shopify app has native PII access)"
    )
    enable_auto_confirm_orders = models.BooleanField(
        default=True,
        help_text="Automatically confirm eligible orders based on AI risk evaluation"
    )
    enable_auto_assign_couriers = models.BooleanField(
        default=True,
        help_text="Automatically assign couriers / book AWB for confirmed orders"
    )
    enable_auto_send_picklists = models.BooleanField(
        default=True,
        help_text="Automatically compile and send morning picklist reports via email"
    )

    # --- Global Idle Alarm Settings ---
    global_idle_timeout_enabled = models.BooleanField(
        default=True,
        help_text="Default toggle status for idle timer buzzer across all workspaces/users"
    )
    global_idle_timeout_minutes = models.PositiveIntegerField(
        default=15,
        help_text="Default timeout in minutes before triggering inactivity buzzer"
    )


    shipping_platform = models.CharField(
        max_length=20,
        choices=[('shipway', 'Shipway'), ('shiprocket', 'Shiprocket')],
        default='shipway',
        help_text="Select active shipping/AWB generation provider platform"
    )
    shiprocket_email_encrypted = models.CharField(max_length=255, null=True, blank=True)
    shiprocket_password_encrypted = models.CharField(max_length=255, null=True, blank=True)
    shiprocket_pickup_location = models.CharField(max_length=150, blank=True, default='', help_text="Nickname of pickup address in Shiprocket")
    shiprocket_token = models.TextField(null=True, blank=True)
    shiprocket_token_expiry = models.DateTimeField(null=True, blank=True)
    shiprocket_order_weight = models.FloatField(default=0.5, blank=True, null=True, help_text="Default shipment weight in Kilograms (e.g. 0.5 for 500g)")
    shiprocket_box_length = models.IntegerField(default=10, blank=True, null=True)
    shiprocket_box_breadth = models.IntegerField(default=10, blank=True, null=True)
    shiprocket_box_height = models.IntegerField(default=10, blank=True, null=True)


    def is_bluedart_token_valid(self):
        from django.utils import timezone
        import datetime
        if not self.bluedart_jwt_token or not self.bluedart_jwt_expiry:
            return False
        return timezone.now() < (self.bluedart_jwt_expiry - datetime.timedelta(minutes=5))

    def __str__(self):
        return f"{self.owner.email}'s Shop ({self.organization_id})"
    
    # --- Setters/Getters ---
    def set_shopify_api_key(self, key): self.shopify_api_key_encrypted = encrypt_data(key) or ''
    def set_shopify_password(self, password): self.shopify_api_password_encrypted = encrypt_data(password) or ''
    def set_shopify_shop_url(self, url): self.shopify_shop_url_encrypted = encrypt_data(url) or ''
    def set_shopify_webhook_secret(self, secret): self.shopify_webhook_secret_encrypted = encrypt_data(secret) or ''
    def set_shipway_email(self, email): self.shipway_email_encrypted = encrypt_data(email) or ''
    def set_shipway_license_key(self, key): self.shipway_license_key_encrypted = encrypt_data(key) or ''
    def set_return_prime_token(self, token):
        if token:
            self.return_prime_token_encrypted = encrypt_data(token)
        else:
            self.return_prime_token_encrypted = None

    def set_chatwoot_api_key(self, token):
        if token:
            self.chatwoot_api_key_encrypted = encrypt_data(token)
        else:
            self.chatwoot_api_key_encrypted = None

    def set_shiprocket_email(self, email):
        if email:
            self.shiprocket_email_encrypted = encrypt_data(email)
        else:
            self.shiprocket_email_encrypted = None

    def set_shiprocket_password(self, password):
        if password:
            self.shiprocket_password_encrypted = encrypt_data(password)
        else:
            self.shiprocket_password_encrypted = None

    def get_shopify_api_key(self): return decrypt_data(self.shopify_api_key_encrypted)
    def get_shopify_password(self): return decrypt_data(self.shopify_api_password_encrypted)
    def get_shopify_shop_url(self): return decrypt_data(self.shopify_shop_url_encrypted)
    def get_shopify_webhook_secret(self): return decrypt_data(self.shopify_webhook_secret_encrypted)
    def get_shipway_email(self): return decrypt_data(self.shipway_email_encrypted)
    def get_shipway_license_key(self): return decrypt_data(self.shipway_license_key_encrypted)
    def get_return_prime_token(self):
        if self.return_prime_token_encrypted:
            return decrypt_data(self.return_prime_token_encrypted)
        return None

    def get_chatwoot_api_key(self):
        if self.chatwoot_api_key_encrypted:
            return decrypt_data(self.chatwoot_api_key_encrypted)
        return None

    def get_shiprocket_email(self):
        if self.shiprocket_email_encrypted:
            return decrypt_data(self.shiprocket_email_encrypted)
        return ""

    def get_shiprocket_password(self):
        if self.shiprocket_password_encrypted:
            return decrypt_data(self.shiprocket_password_encrypted)
        return ""

    class Meta:
        app_label = 'core'
