from django.utils import timezone
from rest_framework import serializers, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models.notification import Notification, NotificationPreference, NotificationDeliveryLog
from core.serializers.notification import NotificationSerializer, NotificationPreferenceSerializer
from core.services.notifications import broadcast_notification_all_read, broadcast_notification_read
from core.views_sales import _resolve_org

class UnifiedNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org_id, shop = _resolve_org(self.request)
        queryset = Notification.objects.filter(recipient=self.request.user).select_related('actor').order_by('-created_at')
        if shop:
            queryset = queryset.filter(shop=shop)

        # Exclude notifications from disabled categories (where in_app_delivery is False)
        disabled_categories = NotificationPreference.objects.filter(
            user=self.request.user,
            in_app_delivery=False
        ).values_list('category', flat=True)
        if disabled_categories:
            queryset = queryset.exclude(category__in=disabled_categories)

        detail_actions = {'retrieve', 'mark_read'}
        if getattr(self, 'action', None) in detail_actions:
            return queryset

        module = (self.request.query_params.get('module') or '').strip()
        if module:
            queryset = queryset.filter(module=module)

        action_name = (self.request.query_params.get('action') or '').strip()
        if action_name:
            queryset = queryset.filter(action=action_name)

        category = (self.request.query_params.get('category') or '').strip()
        if category:
            queryset = queryset.filter(category=category)

        is_read = (self.request.query_params.get('is_read') or '').strip().lower()
        if is_read in {'true', 'false'}:
            queryset = queryset.filter(is_read=is_read == 'true')

        limit_value = (self.request.query_params.get('limit') or '').strip()
        if limit_value.isdigit():
            return queryset[: max(1, min(200, int(limit_value)))]

        return queryset[:100]

    @action(detail=False, methods=['get'], url_path='unread_count')
    def unread_count(self, request):
        org_id, shop = _resolve_org(request)
        
        # Exclude notifications from disabled categories
        disabled_categories = NotificationPreference.objects.filter(
            user=request.user,
            in_app_delivery=False
        ).values_list('category', flat=True)
        
        qs = Notification.objects.filter(recipient=request.user, is_read=False)
        if shop:
            qs = qs.filter(shop=shop)
            
        if disabled_categories:
            qs = qs.exclude(category__in=disabled_categories)
            
        count = qs.count()
        return Response({'count': count})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        was_unread = not notification.is_read
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
        if was_unread:
            broadcast_notification_read(recipient_id=request.user.id, notification_id=notification.id)
        return Response({'status': 'read'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        org_id, shop = _resolve_org(request)
        unread_qs = Notification.objects.filter(recipient=request.user, is_read=False)
        if shop:
            unread_qs = unread_qs.filter(shop=shop)
            
        unread_ids = list(unread_qs.values_list('id', flat=True))
        read_at = timezone.now()
        unread_qs.update(
            is_read=True,
            read_at=read_at,
        )
        if unread_ids:
            broadcast_notification_all_read(
                recipient_id=request.user.id,
                notification_ids=unread_ids,
                read_at=read_at.isoformat(),
            )
        return Response({'status': 'all_read'})


class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationPreferenceSerializer

    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get', 'post'], url_path='bulk-settings')
    def bulk_settings(self, request):
        """
        Gets or updates notification preferences in bulk for the authenticated user.
        """
        user = request.user
        categories = [c[0] for c in Notification.CATEGORY_CHOICES]
        
        if request.method == 'POST':
            preferences_data = request.data.get('preferences', [])
            for pref_data in preferences_data:
                category = pref_data.get('category')
                if category in categories:
                    NotificationPreference.objects.update_or_create(
                        user=user,
                        category=category,
                        defaults={
                            'email_delivery': pref_data.get('email_delivery', True),
                            'in_app_delivery': pref_data.get('in_app_delivery', True),
                            'push_delivery': pref_data.get('push_delivery', True)
                        }
                    )
            
        # Return all preferences for user
        prefs = []
        for cat in categories:
            pref, _ = NotificationPreference.objects.get_or_create(
                user=user,
                category=cat,
                defaults={'email_delivery': True, 'in_app_delivery': True, 'push_delivery': True}
            )
            prefs.append(pref)
            
        return Response(NotificationPreferenceSerializer(prefs, many=True).data)
