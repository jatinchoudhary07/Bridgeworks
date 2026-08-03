from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
import datetime
import zoneinfo
from django_q.models import Schedule

from core.models import Order, TeamMemberSettings
from core.services.picklist_service import get_pending_picklist_orders, send_picklist_email

class PicklistConfigView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Returns picklist metadata:
        - Current user subscription status
        - List of subscribed team members in the organization
        - Quantities of pending, auto-confirmed, and test orders
        """
        user = request.user
        try:
            member_settings = TeamMemberSettings.objects.get(user=user)
            org = member_settings.organization
        except TeamMemberSettings.DoesNotExist:
            return Response({"error": "User settings not found"}, status=status.HTTP_404_NOT_FOUND)

        if not org:
            return Response({"error": "No organization linked"}, status=status.HTTP_400_BAD_REQUEST)

        # Get list of subscribed colleagues
        subscribers = TeamMemberSettings.objects.filter(
            organization=org,
            subscribe_picklist_email=True
        ).select_related('user')
        
        subscribers_list = [
            {"username": s.user.username, "email": s.user.email, "role": s.role}
            for s in subscribers
        ]

        # Get order stats
        pending_orders = get_pending_picklist_orders(org.organization_id)
        
        total_pending = pending_orders.count()
        auto_confirmed = pending_orders.filter(is_auto_confirmed=True).count()
        
        # Test orders currently pending in system (not confirmed, or marked as test)
        test_orders = Order.objects.filter(
            org_id=org.organization_id,
            status='Pending'
        )
        test_orders_count = sum(1 for o in test_orders if o.check_is_test())

        # Query schedules matching this function
        schedules = Schedule.objects.filter(
            func='core.tasks.morning_picklist.send_morning_picklist_task'
        )

        local_times = []
        ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        
        for sch in schedules:
            cron = sch.cron
            if not cron:
                continue
            parts = cron.split()
            if len(parts) >= 2:
                try:
                    minute = int(parts[0])
                    hour = int(parts[1])
                    local_times.append(f"{hour:02d}:{minute:02d}")
                except ValueError:
                    continue

        local_times = sorted(list(set(local_times)))

        return Response({
            "is_subscribed": member_settings.subscribe_picklist_email,
            "subscribers": subscribers_list,
            "schedules": local_times,
            "stats": {
                "total_pending_picklist": total_pending,
                "auto_confirmed_count": auto_confirmed,
                "manual_confirmed_count": total_pending - auto_confirmed,
                "unconfirmed_test_orders": test_orders_count
            }
        })

class PicklistSubscribeToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Toggles the current user's picklist email subscription."""
        subscribe = request.data.get("subscribe", False)
        try:
            member_settings, _ = TeamMemberSettings.objects.get_or_create(user=request.user)
            member_settings.subscribe_picklist_email = subscribe
            member_settings.save(update_fields=['subscribe_picklist_email'])
            return Response({
                "message": f"Successfully {'subscribed to' if subscribe else 'unsubscribed from'} picklist emails.",
                "is_subscribed": member_settings.subscribe_picklist_email
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class PicklistManualEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Manually triggers sending the picklist email right now.
        Accepts optional `order_ids` to export only selected orders.
        """
        user = request.user
        try:
            member_settings = TeamMemberSettings.objects.get(user=user)
            org = member_settings.organization
        except TeamMemberSettings.DoesNotExist:
            return Response({"error": "User settings not found"}, status=404)

        order_ids = request.data.get("order_ids", [])
        
        if order_ids:
            # Filter specifically by selected order IDs (only confirmed ones)
            orders = Order.objects.filter(id__in=order_ids, org_id=org.organization_id, status='Confirmed')
        else:
            # Send all pending
            orders = get_pending_picklist_orders(org.organization_id)
            
        if not orders.exists():
            return Response({"error": "No eligible orders found to email."}, status=400)

        # Send to the specified recipient emails, or fallback to active roster subscribers
        recipient_emails = request.data.get("recipient_emails")
        if not recipient_emails:
            # Query all subscribed team members for this organization
            subscribers = TeamMemberSettings.objects.filter(
                organization=org,
                subscribe_picklist_email=True
            ).select_related('user')
            recipient_emails = [sub.user.email for sub in subscribers if sub.user.email]
            
            # If no roster subscriber has a valid email, fallback to the requesting user
            if not recipient_emails:
                recipient_emails = [user.email]
        elif isinstance(recipient_emails, str):
            recipient_emails = [r.strip() for r in recipient_emails.split(",") if r.strip()]
            if not recipient_emails:
                subscribers = TeamMemberSettings.objects.filter(
                    organization=org,
                    subscribe_picklist_email=True
                ).select_related('user')
                recipient_emails = [sub.user.email for sub in subscribers if sub.user.email]
                if not recipient_emails:
                    recipient_emails = [user.email]
        
        if not recipient_emails:
            return Response({"error": "No email addresses available to receive the report."}, status=400)

        try:
            from django_q.tasks import async_task
            order_ids = list(orders.values_list('id', flat=True))
            async_task(
                'core.tasks.shipway_sync.auto_generate_awb_for_orders_task',
                order_ids,
                org.organization_id,
                recipient_emails,
                True, # is_manual = True
                user.id, # user_id
                task_name=f"auto_awb_manual_{org.organization_id}_{len(order_ids)}"
            )
            return Response({"message": f"Auto AWB generation and Picklist export queued in background. Email will be sent to {', '.join(recipient_emails)} once completed."})
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class OrderBulkMarkTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Bulk toggles the is_test_order flag on a list of order IDs."""
        order_ids = request.data.get("order_ids", [])
        is_test = request.data.get("is_test", True)
        
        if not order_ids:
            return Response({"error": "No order_ids provided"}, status=400)
            
        try:
            updated = Order.objects.filter(id__in=order_ids).update(is_test_order=is_test)
            return Response({
                "message": f"Successfully updated {updated} orders.",
                "updated_count": updated
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class PicklistScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Returns a list of scheduled picklist export times in local time (Asia/Kolkata).
        """
        user = request.user
        try:
            member_settings = TeamMemberSettings.objects.get(user=user)
            org = member_settings.organization
        except TeamMemberSettings.DoesNotExist:
            return Response({"error": "User settings not found"}, status=status.HTTP_404_NOT_FOUND)

        if not org:
            return Response({"error": "No organization linked"}, status=status.HTTP_400_BAD_REQUEST)

        # Query schedules matching this function
        schedules = Schedule.objects.filter(
            func='core.tasks.morning_picklist.send_morning_picklist_task'
        )

        # Parse cron expressions back to local times (HH:MM)
        local_times = []
        ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        
        for sch in schedules:
            cron = sch.cron
            if not cron:
                continue
            parts = cron.split()
            if len(parts) >= 2:
                try:
                    minute = int(parts[0])
                    hour = int(parts[1])
                    local_times.append(f"{hour:02d}:{minute:02d}")
                except ValueError:
                    continue

        # De-duplicate and sort
        local_times = sorted(list(set(local_times)))

        return Response({
            "schedules": local_times
        })

    def post(self, request):
        """
        Updates the scheduled picklist times.
        Receives an array of times in local format: e.g. ["07:00", "18:30"]
        """
        user = request.user
        try:
            member_settings = TeamMemberSettings.objects.get(user=user)
            org = member_settings.organization
        except TeamMemberSettings.DoesNotExist:
            return Response({"error": "User settings not found"}, status=status.HTTP_404_NOT_FOUND)

        if not org:
            return Response({"error": "No organization linked"}, status=status.HTTP_400_BAD_REQUEST)

        org_id = org.organization_id
        times = request.data.get("times", [])

        if not isinstance(times, list):
            return Response({"error": "Times must be a list of HH:MM strings."}, status=status.HTTP_400_BAD_REQUEST)

        ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
        
        # 1. Parse and validate times
        valid_times = []
        for t in times:
            try:
                # Expecting format "HH:MM"
                hour, minute = map(int, t.split(':'))
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError
                valid_times.append((hour, minute))
            except Exception:
                return Response({"error": f"Invalid time format: '{t}'. Must be HH:MM (24-hour style)."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Delete all existing picklist schedules
        Schedule.objects.filter(
            func='core.tasks.morning_picklist.send_morning_picklist_task'
        ).delete()

        # 3. Create new schedules
        new_schedules = []
        now_ist = datetime.datetime.now(ist_tz)
        
        for idx, (hour, minute) in enumerate(valid_times, 1):
            cron_expr = f"{minute} {hour} * * *"
            local_time_str = f"{hour:02d}:{minute:02d}"
            
            # Construct a clean schedule name
            schedule_name = f"picklist_email_schedule_{org_id}_{hour:02d}{minute:02d}"
            
            Schedule.objects.create(
                func='core.tasks.morning_picklist.send_morning_picklist_task',
                schedule_type='C',  # Cron
                cron=cron_expr,
                name=schedule_name,
                repeats=-1 # Infinite repeat
            )
            new_schedules.append({
                "time": local_time_str,
                "cron": cron_expr
            })

        return Response({
            "message": "Schedules successfully updated.",
            "schedules": new_schedules
        })
