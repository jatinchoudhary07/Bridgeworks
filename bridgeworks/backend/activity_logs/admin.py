from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "action",
        "component",
        "page",
        "method",
        "status_code",
        "duration_ms",
        "is_sensitive",
        "timestamp",
    )
    list_filter = ("action", "method", "is_sensitive", "status_code")
    search_fields = ("user__username", "user__email", "action", "component", "page", "session_id")
    readonly_fields = (
        "user",
        "action",
        "component",
        "page",
        "session_id",
        "metadata",
        "is_sensitive",
        "ip_address",
        "user_agent",
        "method",
        "status_code",
        "duration_ms",
        "timestamp",
        "created_at",
    )
    ordering = ("-timestamp",)
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
