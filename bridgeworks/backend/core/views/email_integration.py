from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType

from core.models.email_integration import EmailThread, EmailMessage
from core.serializers.email_integration import EmailThreadSerializer, EmailMessageSerializer
from core.services.email_provider import EmailProviderService
from core.permissions_crm import IsAllowedCRMAccess
from core.views_sales import _resolve_org
from core.models import WholesaleLead, RetailStore, RetailStoreCustomer, Quotation

class EmailThreadViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAllowedCRMAccess]
    serializer_class = EmailThreadSerializer
    queryset = EmailThread.objects.all().prefetch_related('messages')

    def get_content_type_and_object_id(self):
        entity_type = self.kwargs.get('entity_type')
        entity_id = self.kwargs.get('entity_id')

        if not entity_type:
            entity_type = self.request.query_params.get('content_type')
        if not entity_id:
            entity_id = self.request.query_params.get('object_id')

        if not entity_type or not entity_id:
            return None, None

        slug = str(entity_type).lower().replace('_', '-').rstrip('/')
        mapping = {
            'wholesale-leads': 'wholesalelead',
            'wholesale-lead': 'wholesalelead',
            'leads': 'wholesalelead',
            'lead': 'wholesalelead',
            'companies': 'retailstore',
            'company': 'retailstore',
            'stores': 'retailstore',
            'store': 'retailstore',
            'quotations': 'quotation',
            'quotation': 'quotation',
            'quotes': 'quotation',
            'quote': 'quotation',
            'customers': 'retailstorecustomer',
            'customer': 'retailstorecustomer',
        }

        model_name = mapping.get(slug)
        if not model_name:
            raise ValidationError(f"Unsupported entity type: {entity_type}")

        try:
            content_type = ContentType.objects.get(app_label='core', model=model_name)
        except ContentType.DoesNotExist:
            raise ValidationError(f"ContentType not found for model: {model_name}")

        return content_type, entity_id

    def get_queryset(self):
        qs = super().get_queryset()
        content_type, object_id = self.get_content_type_and_object_id()

        if content_type and object_id:
            return qs.filter(content_type=content_type, object_id=object_id)

        _, shop = _resolve_org(self.request)
        if not shop:
            return qs.none()

        return qs.filter(shop=shop)

    @action(detail=False, methods=['post'], url_path='send')
    def send_email(self, request):
        _, shop = _resolve_org(request)
        if not shop:
            return Response({'error': 'Organization/Shop not found'}, status=status.HTTP_400_BAD_REQUEST)

        content_type, object_id = self.get_content_type_and_object_id()
        if not content_type or not object_id:
            return Response({'error': 'content_type and object_id are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve parent entity object
        model_class = content_type.model_class()
        try:
            parent_entity = model_class.objects.get(pk=object_id)
        except model_class.DoesNotExist:
            return Response({'error': 'Target entity not found'}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve fields from request
        sender = request.data.get('sender', shop.email or 'noreply@bridgeworks.com')
        recipient = request.data.get('recipient')
        subject = request.data.get('subject')
        body = request.data.get('body')
        cc = request.data.get('cc', '')
        bcc = request.data.get('bcc', '')

        if not recipient or not subject or not body:
            return Response({'error': 'recipient, subject, and body are required fields'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            msg = EmailProviderService.send_and_log_email(
                shop=shop,
                parent_entity=parent_entity,
                sender=sender,
                recipient=recipient,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc
            )
            serializer = EmailMessageSerializer(msg)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='sync-incoming')
    def sync_incoming(self, request):
        _, shop = _resolve_org(request)
        if not shop:
            return Response({'error': 'Organization/Shop not found'}, status=status.HTTP_400_BAD_REQUEST)

        content_type, object_id = self.get_content_type_and_object_id()
        if not content_type or not object_id:
            return Response({'error': 'content_type and object_id are required'}, status=status.HTTP_400_BAD_REQUEST)

        model_class = content_type.model_class()
        try:
            parent_entity = model_class.objects.get(pk=object_id)
        except model_class.DoesNotExist:
            return Response({'error': 'Target entity not found'}, status=status.HTTP_404_NOT_FOUND)

        sender = request.data.get('sender')
        recipient = request.data.get('recipient')
        subject = request.data.get('subject')
        body = request.data.get('body')

        if not sender or not recipient or not subject or not body:
            return Response({'error': 'sender, recipient, subject, and body are required fields'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            msg = EmailProviderService.sync_incoming_email(
                shop=shop,
                parent_entity=parent_entity,
                sender=sender,
                recipient=recipient,
                subject=subject,
                body=body
            )
            serializer = EmailMessageSerializer(msg)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
