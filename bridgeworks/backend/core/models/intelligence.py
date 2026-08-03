from django.db import models
from django.utils import timezone
import uuid
from django.conf import settings
from .store import ShopCredentials


class PaymentMethodRule(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('cod', 'Cash On Delivery (COD)'),
        ('partial', 'Partially Paid (PPCOD)'),
        ('prepaid', 'Prepaid'),
    ]
    gateway_name = models.CharField(max_length=100, unique=True, help_text="e.g., 'Cash on Delivery (COD)' or 'Razorpay'")
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    
    class Meta:
        app_label = 'core'
        ordering = ['payment_type', 'gateway_name']

    def __str__(self):
        return f"{self.gateway_name} ({self.get_payment_type_display()})"


class AgentConfiguration(models.Model):
    """
    Stores the master system prompt for the AI Agent.
    Editable from Django Admin — no code deploy needed to change AI behavior.
    """
    name = models.CharField(max_length=100, default='Default Agent Config')
    is_active = models.BooleanField(default=True, help_text="Only one configuration should be active at a time.")
    system_prompt = models.TextField(
        help_text="Master instructions for the AI agent in plain English. "
                  "This prompt tells the agent how to evaluate orders for fraud and logistics."
    )
    model_name = models.CharField(
        max_length=100, 
        default='gemini-2.5-flash-lite',
        help_text="Gemini model to use, e.g. 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash'"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Agent Configuration"
        verbose_name_plural = "Agent Configurations"

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class AnalyticsAgentConfiguration(models.Model):
    """
    Stores the master system prompt for the Conversational Analytics Agent (Thorfinn).
    Editable from Django Admin or Frontend.
    """
    name = models.CharField(max_length=100, default='Default Analytics Agent Config')
    is_active = models.BooleanField(default=True, help_text="Only one configuration should be active at a time.")
    system_prompt = models.TextField(
        help_text="Master instructions for the Analytics Agent in plain English."
    )
    model_name = models.CharField(
        max_length=100, 
        default='gemini-2.5-flash',
        help_text="Gemini model to use for the Analytics Agent"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Analytics Agent Configuration"
        verbose_name_plural = "Analytics Agent Configurations"

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class MarketingAgentConfiguration(models.Model):
    """
    Stores the master system prompt for the Marketing Aura Agent (Gemini).
    Editable from Django Admin or Frontend.
    """
    RESPONSE_STYLE_CHOICES = [
        ('Concise', 'Concise'),
        ('Balanced', 'Balanced'),
        ('Detailed', 'Detailed'),
    ]
    PERSONA_CHOICES = [
        ('default', 'Default (Professional Analyst)'),
        ('warm', 'Warm & Encouraging'),
        ('calm', 'Calm & Measured'),
        ('genz', 'Gen Z (Casual & Energetic)'),
        ('aggressive', 'Aggressive (Bold & Direct)'),
        ('zen', 'Zen (Minimal & Mindful)'),
    ]
    name = models.CharField(max_length=100, default='Default Marketing Agent Config')
    is_active = models.BooleanField(default=True, help_text="Only one configuration should be active at a time.")
    response_style = models.CharField(
        max_length=20,
        choices=RESPONSE_STYLE_CHOICES,
        default='Balanced',
        help_text="Controls the verbosity and style of the AI's response."
    )
    persona = models.CharField(
        max_length=20,
        choices=PERSONA_CHOICES,
        default='default',
        help_text="Controls the tone and personality of the AI's responses."
    )
    system_prompt = models.TextField(
        help_text="Master instructions for the deep audit analysis."
    )
    general_prompt = models.TextField(
        help_text="Master instructions for the general conversational chat (no payload loaded).",
        default="",
        blank=True
    )
    model_name = models.CharField(
        max_length=100, 
        default='gemini-2.5-flash-lite',
        help_text="Gemini model to use, e.g. 'gemini-2.5-flash-lite', 'gemini-2.5-flash', 'gemini-2.5-pro'"
    )
    cogs_margin_pct = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Estimated COGS Margin % (e.g. 35.00) to calculate actual ROI. Leave blank to disable."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Marketing Agent Configuration"
        verbose_name_plural = "Marketing Agent Configurations"

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


# ─────────────────────────────────────────────────────────────────────────────
# AGENT MANAGER — Three tables that power global overrides, corrections, audit
# ─────────────────────────────────────────────────────────────────────────────

class MarketingAgentGlobalRule(models.Model):
    """
    Broadcast rules injected into EVERY Marketing AURA system prompt.
    Use cases: budget freezes, seasonal context, platform restrictions,
    emergency overrides (e.g. "Do not recommend scaling — we are pausing ads").

    Rules are fetched on every Gemini API call so changes take effect instantly.
    Set expires_at so rules auto-expire (e.g. end of a sale period).
    """
    rule_text = models.TextField(
        help_text="The instruction to inject. Plain English. E.g. 'Do not recommend increasing budget on any campaign. We are in a budget freeze until further notice.'"
    )
    created_by = models.CharField(max_length=150, blank=True, default='admin')
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=0,
        help_text="Higher number = shown earlier in the prompt. Use to control rule ordering."
    )
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Optional. Rule auto-deactivates after this datetime. Leave blank for permanent rules."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-priority', '-created_at']
        verbose_name = "Marketing Agent Global Rule"
        verbose_name_plural = "Marketing Agent Global Rules"

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def __str__(self):
        status = "ACTIVE" if self.is_active and not self.is_expired else "INACTIVE"
        return f"[{status}] {self.rule_text[:80]}"


class MarketingCorrectionRule(models.Model):
    """
    Correction rules learned from admin feedback.
    When admin flags a bad response and says "don't repeat this",
    the correction gets stored here and appended to every future system prompt.

    Optionally store example bad/good pairs as few-shot examples for the LLM.
    """
    bad_behavior_description = models.TextField(
        help_text="Describe the mistake the AI made. E.g. 'Recommended scaling a campaign with <50 purchases'"
    )
    corrected_instruction = models.TextField(
        help_text="The rule to enforce going forward. E.g. 'Never recommend scaling a campaign with fewer than 50 purchases in the period.'"
    )
    example_bad_response = models.TextField(
        blank=True, default='',
        help_text="Optional: paste the exact bad AI response here for few-shot context."
    )
    example_good_response = models.TextField(
        blank=True, default='',
        help_text="Optional: the corrected/ideal response the AI should have given."
    )
    source_log_id = models.IntegerField(
        null=True, blank=True,
        help_text="ID of the MarketingConversationLog entry that triggered this correction."
    )
    created_by = models.CharField(max_length=150, blank=True, default='admin')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        verbose_name = "Marketing Correction Rule"
        verbose_name_plural = "Marketing Correction Rules"

    def __str__(self):
        return f"Correction: {self.corrected_instruction[:80]}"


class MarketingConversationLog(models.Model):
    """
    Full audit trail of every Marketing AURA Gemini API call.
    Stores the exact system_prompt snapshot, the user message, and AI response.

    This is what powers the "Why did it say that?" feature:
    → Replay the stored system_prompt + user_message into an audit Gemini call.
    → The AI explains its own reasoning against the exact rules that were active.
    """
    session_id = models.CharField(max_length=100, db_index=True, blank=True, default='')
    user_identifier = models.CharField(
        max_length=255, blank=True, default='',
        help_text="Username or user ID of the person who asked the question."
    )
    shop_name = models.CharField(max_length=255, blank=True, default='')

    system_prompt_snapshot = models.TextField(
        help_text="Exact system prompt used for this API call — including all active global rules and corrections."
    )
    user_message = models.TextField()
    ai_response = models.TextField()

    model_used = models.CharField(max_length=100, blank=True, default='')
    tokens_input = models.IntegerField(default=0)
    tokens_output = models.IntegerField(default=0)
    response_time_ms = models.IntegerField(default=0)

    flagged_for_review = models.BooleanField(
        default=False,
        help_text="Set to True when admin flags a response for correction."
    )
    admin_note = models.TextField(
        blank=True, default='',
        help_text="Admin's note explaining why this response was flagged."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        verbose_name = "Marketing Conversation Log"
        verbose_name_plural = "Marketing Conversation Logs"

    def __str__(self):
        flag = " ⚠️ FLAGGED" if self.flagged_for_review else ""
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}]{flag} {self.user_message[:60]}"


# ─────────────────────────────────────────────────────────────────────────────
# LOGISTICS AURA — Agent Manager models (parallel to Marketing AURA)
# ─────────────────────────────────────────────────────────────────────────────

class LogisticsAgentConfiguration(models.Model):
    """
    Stores the master system prompt for the Logistics AURA Agent (Gemini).
    Editable from Django Admin or Frontend (Intelligence section).
    """
    RESPONSE_STYLE_CHOICES = [
        ('Concise', 'Concise'),
        ('Balanced', 'Balanced'),
        ('Detailed', 'Detailed'),
    ]
    PERSONA_CHOICES = [
        ('default', 'Default (Professional Analyst)'),
        ('warm', 'Warm & Encouraging'),
        ('calm', 'Calm & Measured'),
        ('genz', 'Gen Z (Casual & Energetic)'),
        ('aggressive', 'Aggressive (Bold & Direct)'),
        ('zen', 'Zen (Minimal & Mindful)'),
    ]
    name = models.CharField(max_length=100, default='Default Logistics Agent Config')
    is_active = models.BooleanField(default=True)
    response_style = models.CharField(max_length=20, choices=RESPONSE_STYLE_CHOICES, default='Balanced')
    persona = models.CharField(max_length=20, choices=PERSONA_CHOICES, default='default')
    system_prompt = models.TextField(help_text="Master instructions for the deep logistics audit analysis.")
    general_prompt = models.TextField(
        help_text="Master instructions for general conversational chat (no payload loaded).",
        default="", blank=True
    )
    model_name = models.CharField(max_length=100, default='gemini-2.5-flash-lite')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Logistics Agent Configuration"
        verbose_name_plural = "Logistics Agent Configurations"

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class LogisticsAgentGlobalRule(models.Model):
    """
    Broadcast rules injected into EVERY Logistics AURA system prompt.
    Use for courier restrictions, SLA freezes, seasonal context, emergency overrides.
    Changes take effect instantly — no code deploy needed.
    """
    rule_text = models.TextField()
    created_by = models.CharField(max_length=150, blank=True, default='admin')
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=0, help_text="Higher = shown earlier in the prompt.")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-priority', '-created_at']
        verbose_name = "Logistics Agent Global Rule"
        verbose_name_plural = "Logistics Agent Global Rules"

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def __str__(self):
        status = "ACTIVE" if self.is_active and not self.is_expired else "INACTIVE"
        return f"[{status}] {self.rule_text[:80]}"


class LogisticsCorrectionRule(models.Model):
    """
    Correction rules learned from admin feedback on Logistics AURA responses.
    Appended to every future system prompt as few-shot examples.
    """
    bad_behavior_description = models.TextField()
    corrected_instruction = models.TextField()
    example_bad_response = models.TextField(blank=True, default='')
    example_good_response = models.TextField(blank=True, default='')
    source_log_id = models.IntegerField(null=True, blank=True)
    created_by = models.CharField(max_length=150, blank=True, default='admin')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        verbose_name = "Logistics Correction Rule"
        verbose_name_plural = "Logistics Correction Rules"

    def __str__(self):
        return f"Correction: {self.corrected_instruction[:80]}"


class LogisticsConversationLog(models.Model):
    """
    Full audit trail of every Logistics AURA Gemini API call.
    Powers the 'Why did it say that?' feature and correction workflow.
    """
    session_id = models.CharField(max_length=100, db_index=True, blank=True, default='')
    user_identifier = models.CharField(max_length=255, blank=True, default='')
    shop_name = models.CharField(max_length=255, blank=True, default='')
    system_prompt_snapshot = models.TextField()
    user_message = models.TextField()
    ai_response = models.TextField()
    model_used = models.CharField(max_length=100, blank=True, default='')
    tokens_input = models.IntegerField(default=0)
    tokens_output = models.IntegerField(default=0)
    response_time_ms = models.IntegerField(default=0)
    flagged_for_review = models.BooleanField(default=False)
    admin_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']
        verbose_name = "Logistics Conversation Log"
        verbose_name_plural = "Logistics Conversation Logs"

    def __str__(self):
        flag = " ⚠️ FLAGGED" if self.flagged_for_review else ""
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}]{flag} {self.user_message[:60]}"


class ServiceAgentConfiguration(models.Model):
    """
    Stores the master system prompt for the Service AURA Agent (Gemini).
    Editable from Django Admin or Frontend (Intelligence section).
    """
    RESPONSE_STYLE_CHOICES = [
        ('Concise', 'Concise'),
        ('Balanced', 'Balanced'),
        ('Detailed', 'Detailed'),
    ]
    PERSONA_CHOICES = [
        ('default', 'Default (Professional Agent)'),
        ('warm', 'Warm & Encouraging'),
        ('calm', 'Calm & Measured'),
        ('genz', 'Gen Z (Casual & Energetic)'),
        ('aggressive', 'Aggressive (Bold & Direct)'),
        ('zen', 'Zen (Minimal & Mindful)'),
    ]
    name = models.CharField(max_length=100, default='Default Service Agent Config')
    is_active = models.BooleanField(default=True)
    response_style = models.CharField(max_length=20, choices=RESPONSE_STYLE_CHOICES, default='Balanced')
    persona = models.CharField(max_length=20, choices=PERSONA_CHOICES, default='default')
    system_prompt = models.TextField(help_text="Master instructions for the deep customer service audit analysis.")
    general_prompt = models.TextField(
        help_text="Master instructions for general conversational chat (no payload loaded).",
        default="", blank=True
    )
    model_name = models.CharField(max_length=100, default='gemini-2.5-flash-lite')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Service Agent Configuration"
        verbose_name_plural = "Service Agent Configurations"

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class ThorfinnChatSession(models.Model):
    """
    Groups a single conversational thread for the Thorfinn (Data Analyst) assistant.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(ShopCredentials, on_delete=models.CASCADE, related_name='thorfinn_sessions')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='thorfinn_sessions')
    title = models.CharField(max_length=255, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-updated_at']

    def __str__(self):
        return f"Thorfinn Session: {self.title} ({self.created_at.strftime('%Y-%m-%d')})"


class ThorfinnChatMessage(models.Model):
    """
    Individual message inside a Thorfinn Chat Session.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('ai', 'AI'),
    ]
    session = models.ForeignKey(ThorfinnChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    actions = models.JSONField(null=True, blank=True, help_text="Interactive actions triggered by the bot")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['created_at']

    def __str__(self):
        return f"Thorfinn Message from {self.role} at {self.created_at}"
