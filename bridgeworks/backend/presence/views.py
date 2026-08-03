from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from core.views_chat import CsrfExemptSessionAuthentication
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from presence.models import UserPresence
from presence.serializers import UserPresenceSerializer
from core.views_chat import _get_org_id, _org_members

User = get_user_model()

class BulkPresenceView(APIView):
    """
    GET /api/presence/
    Returns the presence statuses of all users in the user's organization.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response([])

        member_ids = list(_org_members(org_id).values_list('id', flat=True))
        
        presences = UserPresence.objects.filter(user_id__in=member_ids).select_related('user')
        pres_dict = {p.user.id: p for p in presences}
        
        results = []
        for mid in member_ids:
            p = pres_dict.get(mid)
            if p:
                results.append(UserPresenceSerializer(p).data)
            else:
                try:
                    user = User.objects.get(pk=mid)
                    p, created = UserPresence.objects.get_or_create(user=user)
                    results.append(UserPresenceSerializer(p).data)
                except User.DoesNotExist:
                    pass
        return Response(results)


class UserPresenceView(APIView):
    """
    GET /api/presence/<user_id>/
    Returns the presence details of a specific user.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        presence, created = UserPresence.objects.get_or_create(user=user)
        return Response(UserPresenceSerializer(presence).data)


class MyPresenceView(APIView):
    """
    PATCH /api/presence/me/
    Allows the authenticated user to set a manual override status.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        manual_status = request.data.get('manual_status')
        if manual_status == '':
            manual_status = None

        VALID_STATUSES = ('online', 'offline', 'in_meeting', 'on_leave', 'working_remotely')
        if manual_status is not None and manual_status not in VALID_STATUSES:
            return Response({'detail': f'Invalid manual status. Must be one of: {", ".join(VALID_STATUSES)}'}, status=400)

        presence, created = UserPresence.objects.get_or_create(user=request.user)
        presence.manual_status = manual_status
        presence.resolve_status()
        presence.save_and_broadcast(source='manual_override')

        return Response(UserPresenceSerializer(presence).data)


class MeetWebhookView(APIView):
    """
    POST /api/presence/meet/
    Webhook endpoint for Google Meet events (updates meeting_active).
    Matches request token against GOOGLE_MEET_WEBHOOK_TOKEN.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.headers.get('X-Meet-Token') or request.data.get('token')
        expected_token = getattr(settings, 'GOOGLE_MEET_WEBHOOK_TOKEN', 'test_meet_token')
        
        if not token or token != expected_token:
            return Response({'detail': 'Unauthorized'}, status=401)

        event = request.data.get('event')
        email = request.data.get('email')

        if not event or not email:
            return Response({'detail': 'Missing event or email'}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'detail': 'User not found'}, status=44)

        presence, created = UserPresence.objects.get_or_create(user=user)

        if event == 'meeting.started':
            presence.meeting_active = True
        elif event == 'meeting.ended':
            presence.meeting_active = False
        else:
            return Response({'detail': f'Invalid event: {event}'}, status=400)

        presence.resolve_status()
        presence.save_and_broadcast(source='google_meet_webhook')

        return Response({'ok': True})


class MyMeetingStatusView(APIView):
    """
    PATCH /api/presence/me/meeting/
    Allows the authenticated user to manually set their meeting_active flag.
    Called by the frontend when user clicks "Join Meet" or leaves a meeting.

    Body: { "active": true | false }
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        active = request.data.get('active')
        if active is None:
            return Response({'detail': 'Missing "active" field (true/false).'}, status=400)

        presence, created = UserPresence.objects.get_or_create(user=request.user)
        presence.meeting_active = bool(active)
        presence.resolve_status()
        presence.save_and_broadcast(source='user_joined_meet')

        return Response(UserPresenceSerializer(presence).data)

