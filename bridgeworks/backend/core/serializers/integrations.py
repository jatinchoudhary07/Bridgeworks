from rest_framework import serializers
from core.models.webhooks import WebhookSubscription, OutboundWebhookLog, OAuthApp, IntegrationConnection

class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookSubscription
        fields = ['id', 'target_url', 'event_type', 'is_active', 'secret_token', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class OutboundWebhookLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutboundWebhookLog
        fields = ['id', 'subscription', 'event_type', 'target_url', 'payload', 'response_status', 'response_body', 'duration_ms', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']

class OAuthAppSerializer(serializers.ModelSerializer):
    class Meta:
        model = OAuthApp
        fields = ['id', 'name', 'client_id', 'client_secret', 'redirect_uris', 'is_active', 'created_at']
        read_only_fields = ['id', 'client_id', 'client_secret', 'created_at']

class IntegrationConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationConnection
        fields = ['id', 'provider', 'connection_type', 'is_active', 'credentials_json', 'metadata', 'last_sync_at', 'created_at']
        read_only_fields = ['id', 'created_at', 'last_sync_at']
