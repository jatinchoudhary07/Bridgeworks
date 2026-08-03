from rest_framework import serializers
from core.models import (
    AgentConfiguration, AnalyticsAgentConfiguration, MarketingAgentConfiguration,
    LogisticsAgentConfiguration, ServiceAgentConfiguration, ThorfinnChatSession, ThorfinnChatMessage
)


class AgentConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentConfiguration
        fields = ['id', 'name', 'is_active', 'system_prompt', 'model_name', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class AnalyticsAgentConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsAgentConfiguration
        fields = ['id', 'name', 'is_active', 'system_prompt', 'model_name', 'created_at', 'updated_at']

class MarketingAgentConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketingAgentConfiguration
        fields = ['id', 'name', 'is_active', 'response_style', 'persona', 'system_prompt', 'general_prompt', 'model_name', 'cogs_margin_pct', 'created_at', 'updated_at']


class LogisticsAgentConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogisticsAgentConfiguration
        fields = ['id', 'name', 'is_active', 'response_style', 'persona', 'system_prompt', 'general_prompt', 'model_name', 'created_at', 'updated_at']


class ServiceAgentConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceAgentConfiguration
        fields = ['id', 'name', 'is_active', 'response_style', 'persona', 'system_prompt', 'general_prompt', 'model_name', 'created_at', 'updated_at']


class ThorfinnChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThorfinnChatSession
        fields = ['id', 'title', 'created_at', 'updated_at']


class ThorfinnChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ThorfinnChatMessage
        fields = ['id', 'session', 'role', 'content', 'actions', 'created_at']
