import json
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class AIAgent(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sandbox', 'Sandbox-Testing'),
        ('live', 'Live')
    ]
    
    RESPONSE_MODE_CHOICES = [
        ('auto', 'Auto-Response'),
        ('manual', 'Manual-Approval')
    ]

    SCRAPING_INTERVAL_CHOICES = [
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly')
    ]

    organization_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=150, default="Shori")
    avatar_url = models.CharField(max_length=500, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    response_mode = models.CharField(max_length=20, choices=RESPONSE_MODE_CHOICES, default='auto')
    
    chatwoot_inbox_id = models.IntegerField(blank=True, null=True, unique=True, db_index=True)
    sandbox_numbers = models.TextField(default="[]", help_text="JSON array of phone numbers whitelisted for testing")
    
    system_prompt = models.TextField(
        blank=True, 
        default="You are Shori, the warm, polite and exceptionally helpful AI Support Executive for our storefront. Treat customers with care.",
        help_text="Core guidelines and character behavior instructions for the bot"
    )
    
    gemini_cache_id = models.CharField(max_length=255, blank=True, null=True, help_text="Google Gemini API Context Cache reference ID")
    
    # --- Human Handover Settings ---
    handover_enabled = models.BooleanField(default=True, help_text="Enable/disable automatic human handover")
    handover_mode = models.CharField(max_length=20, default='round_robin', help_text="Handover mode: round_robin or specific_agent")
    handover_agent_id = models.IntegerField(blank=True, null=True, help_text="ID of specific agent to assign if handover_mode is specific_agent")
    last_assigned_agent_id = models.IntegerField(blank=True, null=True, help_text="ID of the last assigned agent for round robin")
    handover_labels = models.TextField(default='["human-needed", "ai-escalated"]', help_text="JSON list of labels to attach to conversation on handover")
    
    # --- Website Scraper Options ---
    recurring_scraping = models.BooleanField(default=False)
    scraping_interval = models.CharField(max_length=20, choices=SCRAPING_INTERVAL_CHOICES, default='weekly')
    last_scraped_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "AI Agent"
        verbose_name_plural = "AI Agents"

    def __str__(self):
        return f"{self.name} ({self.organization_id})"

    def get_sandbox_numbers_list(self):
        try:
            return json.loads(self.sandbox_numbers)
        except Exception:
            return []

    def set_sandbox_numbers_list(self, numbers_list):
        self.sandbox_numbers = json.dumps(numbers_list)


class KnowledgeNugget(models.Model):
    SOURCE_TYPE_CHOICES = [
        ('document', 'Document'),
        ('url', 'URL'),
        ('text', 'Raw Text')
    ]

    agent = models.ForeignKey(AIAgent, on_delete=models.CASCADE, related_name='knowledge_nuggets')
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES, default='text')
    title = models.CharField(max_length=255, default="", blank=True)
    content = models.TextField(default="")
    metadata = models.TextField(default="{}", help_text="JSON string representing metadata like file name, page links, etc.")
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Knowledge Nugget"
        verbose_name_plural = "Knowledge Nuggets"

    def __str__(self):
        return f"{self.title or 'Nugget'} - {self.agent.name}"

    def get_metadata_dict(self):
        try:
            return json.loads(self.metadata)
        except Exception:
            return {}

    def set_metadata_dict(self, metadata_dict):
        self.metadata = json.dumps(metadata_dict)


class AgentAuditLog(models.Model):
    ROLE_CHOICES = [
        ('manager', 'Manager Directive'),
        ('system', 'System Notification'),
        ('customer', 'Simulated Customer'),
        ('bot', 'Simulated Bot Response')
    ]

    agent = models.ForeignKey(AIAgent, on_delete=models.CASCADE, related_name='audit_logs')
    directed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='manager')
    message = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Agent Audit Log"
        verbose_name_plural = "Agent Audit Logs"
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role} in {self.agent.name} session at {self.created_at}"
