from rest_framework import serializers
from core.models.email_integration import EmailThread, EmailMessage

class EmailMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMessage
        fields = ['id', 'thread', 'message_id', 'sender', 'recipient', 'cc', 'bcc', 'subject', 'body', 'sent_at', 'is_incoming', 'created_at']
        read_only_fields = ['created_at']


class EmailThreadSerializer(serializers.ModelSerializer):
    messages = EmailMessageSerializer(many=True, read_only=True)
    entity_type_display = serializers.CharField(source='get_entity_type_display', read_only=True)

    class Meta:
        model = EmailThread
        fields = ['id', 'shop', 'subject', 'content_type', 'object_id', 'entity_type_display', 'last_message_at', 'created_at', 'messages']
        read_only_fields = ['shop', 'last_message_at', 'created_at']
