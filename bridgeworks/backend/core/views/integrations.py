import secrets
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from core.models import ShopCredentials
from core.models.webhooks import WebhookSubscription, OutboundWebhookLog, OAuthApp, IntegrationConnection
from core.serializers.integrations import (
    WebhookSubscriptionSerializer,
    OutboundWebhookLogSerializer,
    OAuthAppSerializer,
    IntegrationConnectionSerializer
)
from core.views.helpers import _get_org_id_or_none

class BaseIntegrationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def _get_shop(self):
        org_id = _get_org_id_or_none(self.request)
        if not org_id:
            return None
        return ShopCredentials.objects.filter(organization_id=org_id).first()


class WebhookSubscriptionViewSet(BaseIntegrationViewSet):
    serializer_class = WebhookSubscriptionSerializer

    def get_queryset(self):
        shop = self._get_shop()
        if not shop:
            return WebhookSubscription.objects.none()
        return WebhookSubscription.objects.filter(shop=shop)

    def perform_create(self, serializer):
        shop = self._get_shop()
        if not shop:
            raise ValidationError("Organization context not found.")
        # Generate a secret token for signing if not provided
        secret_token = self.request.data.get('secret_token') or f"whsec_{secrets.token_hex(16)}"
        serializer.save(shop=shop, secret_token=secret_token)


class OutboundWebhookLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = OutboundWebhookLogSerializer

    def get_queryset(self):
        org_id = _get_org_id_or_none(self.request)
        if not org_id:
            return OutboundWebhookLog.objects.none()
        shop = ShopCredentials.objects.filter(organization_id=org_id).first()
        if not shop:
            return OutboundWebhookLog.objects.none()
        return OutboundWebhookLog.objects.filter(shop=shop)


class OAuthAppViewSet(BaseIntegrationViewSet):
    serializer_class = OAuthAppSerializer

    def get_queryset(self):
        shop = self._get_shop()
        if not shop:
            return OAuthApp.objects.none()
        return OAuthApp.objects.filter(shop=shop)

    def perform_create(self, serializer):
        shop = self._get_shop()
        if not shop:
            raise ValidationError("Organization context not found.")
        
        client_id = f"cli_{secrets.token_hex(16)}"
        client_secret = f"sec_{secrets.token_hex(32)}"
        serializer.save(
            shop=shop,
            client_id=client_id,
            client_secret=client_secret
        )


class IntegrationConnectionViewSet(BaseIntegrationViewSet):
    serializer_class = IntegrationConnectionSerializer
    lookup_field = 'provider'

    def get_queryset(self):
        shop = self._get_shop()
        if not shop:
            return IntegrationConnection.objects.none()
        return IntegrationConnection.objects.filter(shop=shop)

    def perform_create(self, serializer):
        shop = self._get_shop()
        if not shop:
            raise ValidationError("Organization context not found.")
        serializer.save(shop=shop)

    @action(detail=True, methods=['post'])
    def toggle(self, request, provider=None):
        shop = self._get_shop()
        if not shop:
            return Response({"error": "Organization context not found."}, status=status.HTTP_404_NOT_FOUND)
        
        connection = IntegrationConnection.objects.filter(shop=shop, provider=provider).first()
        if not connection:
            return Response({"error": "Connection not found."}, status=status.HTTP_404_NOT_FOUND)
        
        connection.is_active = not connection.is_active
        connection.save()
        return Response({
            "provider": provider,
            "is_active": connection.is_active,
            "message": f"Connection {'enabled' if connection.is_active else 'disabled'} successfully."
        })
