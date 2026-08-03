from django.urls import path
from presence.views import BulkPresenceView, UserPresenceView, MyPresenceView, MeetWebhookView, MyMeetingStatusView

urlpatterns = [
    path('', BulkPresenceView.as_view(), name='bulk-presence'),
    path('me/', MyPresenceView.as_view(), name='my-presence'),
    path('me/meeting/', MyMeetingStatusView.as_view(), name='my-meeting-status'),
    path('meet/', MeetWebhookView.as_view(), name='meet-webhook'),
    path('<int:user_id>/', UserPresenceView.as_view(), name='user-presence'),
]
