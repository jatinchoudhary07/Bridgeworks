from django.urls import path, include
from rest_framework.routers import DefaultRouter

from hr.training.views import (
    # New ViewSet-based views
    TrainingFileViewSet,
    TrainingPushViewSet,
    TrainingMyAssignmentsViewSet,
    TrainingComplianceDashboardView,
    # Legacy CBV-based views (backward-compat)
    TrainingFileListCreateView,
    TrainingFileDetailView,
    TrainingFileVersionsListView,
    TrainingPushListCreateView,
    TrainingMyAssignmentsListView,
    TrainingPushRecipientAcknowledgeView,
)

# ─── ViewSet router ───────────────────────────────────────────────────────────
router = DefaultRouter()
router.register(r'training-files',  TrainingFileViewSet,          basename='training-files')
router.register(r'training-pushes', TrainingPushViewSet,          basename='training-pushes')
router.register(r'my-assignments',  TrainingMyAssignmentsViewSet, basename='my-assignments-vs')

# ─── URL patterns ─────────────────────────────────────────────────────────────
urlpatterns = [
    # ViewSet routes (new)
    path('', include(router.urls)),

    # Legacy CBV routes – frontend still calls these paths
    path('files/',                            TrainingFileListCreateView.as_view(),        name='training-files-list-create'),
    path('files/<int:pk>/',                   TrainingFileDetailView.as_view(),            name='training-files-detail'),
    path('files/<int:pk>/versions/',          TrainingFileVersionsListView.as_view(),      name='training-files-versions'),
    path('pushes/',                           TrainingPushListCreateView.as_view(),        name='training-pushes-list-create'),
    path('my-assignments/',                   TrainingMyAssignmentsListView.as_view(),     name='training-my-assignments-list'),
    path('my-assignments/<int:pk>/acknowledge/', TrainingPushRecipientAcknowledgeView.as_view(), name='training-my-assignments-acknowledge'),
    path('compliance/',                       TrainingComplianceDashboardView.as_view(),   name='training-compliance-dashboard'),
]

# Mounted in main urls.py as:
#   path('api/hr/training/', include('hr.training.urls'))
