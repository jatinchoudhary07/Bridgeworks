from django.urls import path

from .views import BatchIngestView, HRExportView, HRLogsView, MyLogsView

urlpatterns = [
    # POST /api/logs/batch   — frontend event ingest (202 async)
    path("batch", BatchIngestView.as_view(), name="actlog-batch-ingest"),

    # GET  /api/logs/me      — personal log history
    path("me", MyLogsView.as_view(), name="actlog-my-logs"),

    # GET  /api/logs/hr/logs — HR: all-user filtered logs
    path("hr/logs", HRLogsView.as_view(), name="actlog-hr-logs"),

    # GET  /api/logs/hr/export — HR: CSV stream download
    path("hr/export", HRExportView.as_view(), name="actlog-hr-export"),
]
