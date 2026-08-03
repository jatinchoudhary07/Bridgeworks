"""
Admin API views for managing office locations, registered IPs,
and attendance session start/end with WFO/WFH detection.
"""

import logging
from datetime import time, date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.models import (
    OfficeLocation, OfficeIP, AttendanceSession, AttendanceEntry,
    PublicHoliday, AttendanceSessionExemption,
)
from core.views.helpers import _get_org_id_or_none, CsrfExemptSessionAuthentication
from core.permissions import HasModulePermission
from core.serializers.mydesk import (
    PublicHolidaySerializer, AttendanceSessionExemptionSerializer,
)
from core.services.geofence import (
    get_client_ip, detect_work_mode, check_anomalies, geocode_address,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ==============================================================================
# BASE
# ==============================================================================

class OrgScopedBaseAPIView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_org_id(self):
        return _get_org_id_or_none(self.request) or ''


# ==============================================================================
# OFFICE LOCATION CRUD (Admin only)
# ==============================================================================

class OfficeLocationListCreateView(OrgScopedBaseAPIView):
    """
    GET  → List all office locations for the org
    POST → Create a new office (optionally auto-geocode the address)
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
        'POST': 'human_resources:attendance_dashboard:edit',
    }
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        offices = OfficeLocation.objects.filter(org_id=org_id).prefetch_related('registered_ips')
        data = [_office_payload(o) for o in offices]
        return Response({'offices': data})

    def post(self, request):
        org_id = self.get_org_id()
        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'name': 'Office name is required.'}, status=status.HTTP_400_BAD_REQUEST)

        address = (request.data.get('address') or '').strip()
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        radius = request.data.get('geofence_radius_meters', 200)
        idle_timeout = request.data.get('idle_timeout_minutes', 15)
        idle_timeout_enabled_val = request.data.get('idle_timeout_enabled', True)
        if isinstance(idle_timeout_enabled_val, str):
            idle_timeout_enabled_val = idle_timeout_enabled_val.lower() != 'false'
        else:
            idle_timeout_enabled_val = bool(idle_timeout_enabled_val)

        # Auto-geocode if address given but no coordinates
        if address and (latitude is None or longitude is None):
            lat, lon = geocode_address(address)
            if lat is not None:
                latitude = lat
                longitude = lon

        try:
            idle_timeout_val = int(idle_timeout) if idle_timeout is not None else 15
            if idle_timeout_val <= 0:
                idle_timeout_val = 15
        except (ValueError, TypeError):
            idle_timeout_val = 15

        require_dual_signal_val = request.data.get('require_dual_signal', False)
        if isinstance(require_dual_signal_val, str):
            require_dual_signal_val = require_dual_signal_val.lower() != 'false'
        else:
            require_dual_signal_val = bool(require_dual_signal_val)

        office = OfficeLocation.objects.create(
            org_id=org_id,
            name=name,
            address=address,
            latitude=latitude,
            longitude=longitude,
            geofence_radius_meters=int(radius) if radius else 200,
            idle_timeout_enabled=idle_timeout_enabled_val,
            idle_timeout_minutes=idle_timeout_val,
            require_dual_signal=require_dual_signal_val,
            created_by=request.user,
        )
        return Response(_office_payload(office), status=status.HTTP_201_CREATED)


class OfficeLocationDetailView(OrgScopedBaseAPIView):
    """
    GET    → Office detail
    PUT    → Update office
    DELETE → Remove office
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
        'PUT': 'human_resources:attendance_dashboard:edit',
        'DELETE': 'human_resources:attendance_dashboard:edit',
    }
    parser_classes = [JSONParser]

    def _get_office(self, pk):
        org_id = self.get_org_id()
        return generics.get_object_or_404(OfficeLocation, pk=pk, org_id=org_id)

    def get(self, request, pk):
        return Response(_office_payload(self._get_office(pk)))

    def put(self, request, pk):
        office = self._get_office(pk)

        if 'name' in request.data:
            office.name = (request.data['name'] or '').strip() or office.name
        if 'address' in request.data:
            office.address = (request.data['address'] or '').strip()
        if 'latitude' in request.data:
            office.latitude = request.data['latitude']
        if 'longitude' in request.data:
            office.longitude = request.data['longitude']
        if 'geofence_radius_meters' in request.data:
            office.geofence_radius_meters = int(request.data['geofence_radius_meters'])
        if 'is_active' in request.data:
            office.is_active = bool(request.data['is_active'])
        if 'idle_timeout_enabled' in request.data:
            val = request.data['idle_timeout_enabled']
            if isinstance(val, str):
                office.idle_timeout_enabled = val.lower() != 'false'
            else:
                office.idle_timeout_enabled = bool(val)
        if 'idle_timeout_minutes' in request.data:
            try:
                val = int(request.data['idle_timeout_minutes'])
                office.idle_timeout_minutes = val if val > 0 else 15
            except (ValueError, TypeError):
                pass
        if 'require_dual_signal' in request.data:
            val = request.data['require_dual_signal']
            if isinstance(val, str):
                office.require_dual_signal = val.lower() != 'false'
            else:
                office.require_dual_signal = bool(val)

        office.save()
        return Response(_office_payload(office))

    def delete(self, request, pk):
        office = self._get_office(pk)
        office.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OfficeLocationGeocodeView(OrgScopedBaseAPIView):
    """POST → Re-geocode an office's address"""
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'human_resources:attendance_dashboard:edit'}
    parser_classes = [JSONParser]

    def post(self, request, pk):
        org_id = self.get_org_id()
        office = generics.get_object_or_404(OfficeLocation, pk=pk, org_id=org_id)

        address = (request.data.get('address') or office.address or '').strip()
        if not address:
            return Response(
                {'detail': 'No address to geocode.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        lat, lon = geocode_address(address)
        if lat is None:
            return Response(
                {'detail': 'Geocoding failed. Address may be too vague or the service is unavailable.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        office.latitude = lat
        office.longitude = lon
        if address != office.address:
            office.address = address
        office.save(update_fields=['latitude', 'longitude', 'address', 'updated_at'])

        return Response(_office_payload(office))


# ==============================================================================
# OFFICE IP MANAGEMENT
# ==============================================================================

class OfficeIPCreateView(OrgScopedBaseAPIView):
    """POST → Add a registered IP to an office"""
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'human_resources:attendance_dashboard:edit'}
    parser_classes = [JSONParser]

    def post(self, request, office_pk):
        org_id = self.get_org_id()
        office = generics.get_object_or_404(OfficeLocation, pk=office_pk, org_id=org_id)

        ip_address = (request.data.get('ip_address') or '').strip()
        ip_cidr = (request.data.get('ip_cidr') or '').strip()

        if not ip_address and not ip_cidr:
            return Response({'detail': 'Either IP address or CIDR range is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if ip_address and ip_cidr:
            return Response({'detail': 'Provide either IP address or CIDR range, not both.'}, status=status.HTTP_400_BAD_REQUEST)

        label = (request.data.get('label') or '').strip()

        from django.core.exceptions import ValidationError
        ip_obj = OfficeIP(
            office=office,
            ip_address=ip_address or None,
            ip_cidr=ip_cidr or None,
            label=label
        )
        try:
            ip_obj.clean()
        except ValidationError as e:
            msg = getattr(e, 'message_dict', {}).get('ip_cidr', [str(e)])[0]
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)

        if ip_address:
            if OfficeIP.objects.filter(office=office, ip_address=ip_address).exists():
                return Response(
                    {'detail': f'IP {ip_address} is already registered for this office.'},
                    status=status.HTTP_409_CONFLICT,
                )
        if ip_cidr:
            if OfficeIP.objects.filter(office=office, ip_cidr=ip_cidr).exists():
                return Response(
                    {'detail': f'CIDR range {ip_cidr} is already registered for this office.'},
                    status=status.HTTP_409_CONFLICT,
                )

        ip_obj.save()
        return Response(_office_payload(office), status=status.HTTP_201_CREATED)


class OfficeIPDeleteView(OrgScopedBaseAPIView):
    """DELETE → Remove a registered IP from an office"""
    permission_classes = [HasModulePermission]
    required_permissions = {'DELETE': 'human_resources:attendance_dashboard:edit'}

    def delete(self, request, office_pk, ip_pk):
        org_id = self.get_org_id()
        office = generics.get_object_or_404(OfficeLocation, pk=office_pk, org_id=org_id)
        ip_obj = generics.get_object_or_404(OfficeIP, pk=ip_pk, office=office)
        ip_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DetectMyIPView(OrgScopedBaseAPIView):
    """GET → Return the client's public IP (so admin can easily register it)"""

    def get(self, request):
        ip = get_client_ip(request)
        return Response({'ip': ip})


# ==============================================================================
# ATTENDANCE SESSION (Login/Logout with WFO/WFH detection)
# ==============================================================================

class AttendanceSessionStartView(OrgScopedBaseAPIView):
    """
    POST → Start an attendance session.
    Called by frontend after successful JWT login.
    Captures IP + GPS, runs WFO/WFH detection, creates session + daily entry.
    """
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'session_start'

    def post(self, request):
        org_id = self.get_org_id()
        user = request.user

        # Extract signals
        ip = get_client_ip(request)
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        gps_accuracy = request.data.get('gps_accuracy')
        gps_status_val = request.data.get('gps_status', 'unavailable')
        user_agent = request.META.get('HTTP_USER_AGENT', '')

        # Parse lat/lon safely
        try:
            latitude = float(latitude) if latitude is not None else None
            longitude = float(longitude) if longitude is not None else None
        except (ValueError, TypeError):
            latitude = longitude = None

        try:
            gps_accuracy = float(gps_accuracy) if gps_accuracy is not None else None
        except (ValueError, TypeError):
            gps_accuracy = None

        # Run WFO/WFH detection
        detection = detect_work_mode(org_id, ip, latitude, longitude)

        # Close any existing open sessions for this user (superseded by new login)
        AttendanceSession.objects.filter(
            org_id=org_id,
            user=user,
            logout_at__isnull=True,
        ).update(
            logout_at=timezone.now(),
            logout_source='superseded',
        )

        # Create session
        session = AttendanceSession.objects.create(
            org_id=org_id,
            user=user,
            login_ip=ip or None,
            login_latitude=latitude,
            login_longitude=longitude,
            gps_accuracy_meters=gps_accuracy,
            gps_status=gps_status_val,
            user_agent=user_agent[:2000],
            ip_matched_office_id=detection['ip_matched_office_id'],
            gps_nearest_office_id=detection['gps_nearest_office_id'],
            gps_distance_meters=detection['gps_distance_meters'],
            work_mode=detection['work_mode'],
            work_mode_reason=detection['reason'][:100],
        )

        # Check anomalies
        anomalies = check_anomalies(session)
        if anomalies:
            session.is_anomalous = True
            session.anomaly_reasons = anomalies
            session.save(update_fields=['is_anomalous', 'anomaly_reasons'])

        # Create or update today's AttendanceEntry if none exists
        today = timezone.localdate()
        existing_entry = AttendanceEntry.objects.filter(
            org_id=org_id, user=user, entry_date=today, is_active=True,
        ).order_by('-updated_at').first()

        if not existing_entry:
            from core.views_mydesk import _effective_rulebook, _auto_compute_status
            rb = _effective_rulebook(user)
            now_time = timezone.localtime().time()

            final_status, total_deduction, late_minutes, _, _, score = _auto_compute_status(
                in_time=now_time,
                out_time=None,
                rulebook=rb
            )

            # Map 'present' status to 'wfh' if the session detection resolved to WFH
            if final_status == 'present' and detection['work_mode'] == 'wfh':
                final_status = 'wfh'

            AttendanceEntry.objects.create(
                org_id=org_id,
                user=user,
                entry_date=today,
                in_time=now_time,
                status=final_status,
                auto_status=final_status,
                work_mode=detection['work_mode'],
                late_minutes=late_minutes,
                salary_deduction_days=total_deduction,
                attendance_score_points=score,
                approval_status='approved',
                source='self',
                is_active=True,
            )
        else:
            from core.views_mydesk import _effective_rulebook, _auto_compute_status
            rb = _effective_rulebook(user)

            # Clear out_time and recalculate status since they are logging back in (active again)
            final_status, total_deduction, late_minutes, _, _, score = _auto_compute_status(
                in_time=existing_entry.in_time,
                out_time=None,
                rulebook=rb
            )

            # Map 'present' status to 'wfh' if the session detection resolved to WFH
            if final_status == 'present' and detection['work_mode'] == 'wfh':
                final_status = 'wfh'

            existing_entry.out_time = None
            existing_entry.hours_worked = 0.0
            existing_entry.early_leave_minutes = 0
            existing_entry.work_mode = detection['work_mode']
            existing_entry.auto_status = final_status

            if not existing_entry.hr_override_status:
                existing_entry.status = final_status
                existing_entry.salary_deduction_days = total_deduction
                existing_entry.attendance_score_points = score

            existing_entry.save(update_fields=[
                'out_time', 'hours_worked', 'early_leave_minutes', 'work_mode',
                'status', 'auto_status', 'salary_deduction_days', 'attendance_score_points', 'updated_at'
            ])

        # Build response
        office_name = None
        if detection['ip_matched_office_id']:
            try:
                office_name = OfficeLocation.objects.get(id=detection['ip_matched_office_id']).name
            except OfficeLocation.DoesNotExist:
                pass
        if not office_name and detection['gps_nearest_office_id'] and detection['work_mode'] == 'wfo':
            try:
                office_name = OfficeLocation.objects.get(id=detection['gps_nearest_office_id']).name
            except OfficeLocation.DoesNotExist:
                pass

        # Resolve idle alarm settings via Priority Chain
        idle_timeout_enabled_res = True
        idle_timeout_mins = 15  # Default fallback

        # 1. Start with Org-wide global default from ShopCredentials
        from core.models import ShopCredentials
        try:
            shop_creds = ShopCredentials.objects.filter(organization_id=org_id).first()
            if shop_creds:
                idle_timeout_enabled_res = shop_creds.global_idle_timeout_enabled
                idle_timeout_mins = shop_creds.global_idle_timeout_minutes
        except Exception as e:
            logger.warning(f"Error fetching ShopCredentials: {e}")

        # 2. Override with matched office's setting (if user is matched to an office)
        office_id = detection['ip_matched_office_id'] or detection['gps_nearest_office_id']
        if office_id:
            try:
                office_obj = OfficeLocation.objects.get(id=office_id)
                idle_timeout_mins = office_obj.idle_timeout_minutes
                idle_timeout_enabled_res = office_obj.idle_timeout_enabled
            except OfficeLocation.DoesNotExist:
                pass

        # 3. Override with user profile's personal override (if set)
        try:
            profile = getattr(user, 'profile', None)
            if profile:
                if profile.idle_timeout_override_enabled is not None:
                    idle_timeout_enabled_res = profile.idle_timeout_override_enabled
                if profile.idle_timeout_override_minutes is not None:
                    idle_timeout_mins = profile.idle_timeout_override_minutes
        except Exception as e:
            logger.warning(f"Error fetching UserProfile override: {e}")

        gps_required = False
        if detection['ip_matched_office_id']:
            try:
                matched_office = OfficeLocation.objects.get(id=detection['ip_matched_office_id'])
                if matched_office.require_dual_signal and gps_status_val != 'captured':
                    gps_required = True
            except OfficeLocation.DoesNotExist:
                pass

        return Response({
            'session_id': session.id,
            'work_mode': session.work_mode,
            'work_mode_reason': session.work_mode_reason,
            'office_name': office_name,
            'is_anomalous': session.is_anomalous,
            'login_ip': ip,
            'idle_timeout_enabled': idle_timeout_enabled_res,
            'idle_timeout_minutes': idle_timeout_mins,
            'gps_required': gps_required,
        }, status=status.HTTP_201_CREATED)


class AttendanceSessionEndView(OrgScopedBaseAPIView):
    """
    POST → End an active attendance session (manual logout).
    Also updates the daily AttendanceEntry out_time.
    """
    parser_classes = [JSONParser]

    def post(self, request):
        org_id = self.get_org_id()
        user = request.user
        logout_source = request.data.get('source', 'manual')

        # Find the most recent active (un-ended) session for this user
        session = AttendanceSession.objects.filter(
            org_id=org_id, user=user, logout_at__isnull=True,
        ).order_by('-login_at').first()

        if not session:
            return Response(
                {'detail': 'No active session found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        now = timezone.now()
        session.logout_at = now
        session.logout_source = logout_source[:20]
        session.save(update_fields=['logout_at', 'logout_source'])

        # Update today's entry out_time
        today = timezone.localdate()
        entry = AttendanceEntry.objects.filter(
            org_id=org_id, user=user, entry_date=today, is_active=True,
        ).order_by('-updated_at').first()

        if entry:
            entry.out_time = timezone.localtime(now).time()
            from core.views_mydesk import _effective_rulebook, _auto_compute_status, _calculate_net_worked_hours
            rb = _effective_rulebook(user)
            net_hours = _calculate_net_worked_hours(user, today)

            final_status, total_deduction, late_minutes, early_leave, hours_worked, score = _auto_compute_status(
                in_time=entry.in_time,
                out_time=entry.out_time,
                rulebook=rb,
                hours_worked=net_hours
            )

            # Preserve WFH status mapping if final calculated status is 'present'
            if final_status == 'present' and (entry.status == 'wfh' or entry.work_mode == 'wfh'):
                final_status = 'wfh'

            # Update entry's work_mode from session if available
            if session.work_mode != 'unknown':
                entry.work_mode = session.work_mode

            entry.auto_status = final_status

            # If HR has overridden the status, preserve it and adjust deduction/score accordingly
            if entry.hr_override_status:
                entry.status = entry.hr_override_status
                if entry.status == 'absent':
                    entry.attendance_score_points = 0
                    entry.salary_deduction_days = 1.0
                elif entry.status == 'half_day':
                    entry.attendance_score_points = 50
                    entry.salary_deduction_days = 0.5
                elif entry.status == 'leave':
                    entry.attendance_score_points = 0
                    entry.salary_deduction_days = 1.0
                elif entry.status in ('present', 'wfh', 'on_duty'):
                    entry.attendance_score_points = 100
                    entry.salary_deduction_days = 0.0
            else:
                entry.status = final_status
                entry.salary_deduction_days = total_deduction
                entry.attendance_score_points = score

            entry.late_minutes = late_minutes
            entry.early_leave_minutes = early_leave
            entry.hours_worked = hours_worked
            entry.save(update_fields=[
                'status', 'auto_status', 'work_mode', 'out_time', 'late_minutes',
                'early_leave_minutes', 'hours_worked', 'salary_deduction_days',
                'attendance_score_points', 'updated_at'
            ])

        return Response({
            'detail': 'Session ended.',
            'session_id': session.id,
            'logout_at': now.isoformat(),
        })


class AttendanceSessionListView(OrgScopedBaseAPIView):
    """GET → List attendance sessions for the current user (recent)"""
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        days = int(request.query_params.get('days', 7))
        since = timezone.now() - timezone.timedelta(days=min(days, 90))

        sessions = AttendanceSession.objects.filter(
            org_id=org_id,
            user=request.user,
            login_at__gte=since,
        ).select_related('ip_matched_office', 'gps_nearest_office')[:100]

        data = [_session_payload(s) for s in sessions]
        return Response({'sessions': data})


# ==============================================================================
# ANOMALY VIEWS (Phase 6 — Admin)
# ==============================================================================

class AttendanceAnomalyListView(OrgScopedBaseAPIView):
    """GET → List anomalous sessions for the org (admin)"""
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'human_resources:attendance_dashboard:view'}
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        resolution_filter = request.query_params.get('resolution', 'unresolved')
        days = int(request.query_params.get('days', 30))
        since = timezone.now() - timezone.timedelta(days=min(days, 180))

        qs = AttendanceSession.objects.filter(
            org_id=org_id,
            is_anomalous=True,
            login_at__gte=since,
        ).select_related('user', 'ip_matched_office', 'gps_nearest_office')

        if resolution_filter != 'all':
            qs = qs.filter(anomaly_resolution=resolution_filter)

        sessions = qs[:200]
        data = [_session_payload(s, include_user=True) for s in sessions]

        # Summary counts
        total_unresolved = AttendanceSession.objects.filter(
            org_id=org_id, is_anomalous=True, anomaly_resolution='unresolved',
        ).count()

        return Response({
            'anomalies': data,
            'total_unresolved': total_unresolved,
        })


class AttendanceAnomalyResolveView(OrgScopedBaseAPIView):
    """POST → Resolve an anomaly (admin)"""
    permission_classes = [HasModulePermission]
    required_permissions = {'POST': 'human_resources:attendance_dashboard:edit'}
    parser_classes = [JSONParser]

    def post(self, request, pk):
        org_id = self.get_org_id()
        session = generics.get_object_or_404(
            AttendanceSession, pk=pk, org_id=org_id, is_anomalous=True
        )

        resolution = request.data.get('resolution', 'ok')
        if resolution not in ('ok', 'suspicious', 'dismissed'):
            return Response(
                {'resolution': "Must be 'ok', 'suspicious', or 'dismissed'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        note = (request.data.get('note') or '').strip()
        session.anomaly_resolution = resolution
        session.anomaly_resolved_by = request.user
        session.anomaly_resolved_at = timezone.now()
        session.anomaly_resolution_note = note
        session.save(update_fields=[
            'anomaly_resolution', 'anomaly_resolved_by',
            'anomaly_resolved_at', 'anomaly_resolution_note',
        ])

        return Response(_session_payload(session, include_user=True))


# ==============================================================================
# REPORTING (Phase 5)
# ==============================================================================

class AttendanceReportView(OrgScopedBaseAPIView):
    """
    GET → Generate attendance reports with WFO/WFH breakdown.
    Query params: period=daily|weekly|monthly, date=YYYY-MM-DD, month=YYYY-MM
    """
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'human_resources:attendance_dashboard:view'}
    parser_classes = [JSONParser]

    def get(self, request):
        from datetime import timedelta
        import calendar

        org_id = self.get_org_id()
        period = request.query_params.get('period', 'daily')

        # Determine date range
        if period == 'daily':
            target_date = _parse_date(request.query_params.get('date'))
            start_date = target_date
            end_date = target_date
        elif period == 'weekly':
            target_date = _parse_date(request.query_params.get('date'))
            start_date = target_date - timedelta(days=target_date.weekday())  # Monday
            end_date = start_date + timedelta(days=6)
        else:  # monthly
            month_str = request.query_params.get('month')
            if month_str:
                try:
                    year, mon = [int(x) for x in month_str.split('-')]
                except (ValueError, TypeError):
                    year, mon = timezone.localdate().year, timezone.localdate().month
            else:
                today = timezone.localdate()
                year, mon = today.year, today.month
            start_date = date(year, mon, 1)
            end_date = date(year, mon, calendar.monthrange(year, mon)[1])

        # Get all org users
        from core.views.helpers import _get_org_id_or_none
        org_users = _get_organization_users(org_id)
        user_ids = [u.id for u in org_users]
        user_map = {u.id: u for u in org_users}

        # Fetch attendance entries
        entries = list(
            AttendanceEntry.objects.filter(
                org_id=org_id,
                user_id__in=user_ids,
                entry_date__gte=start_date,
                entry_date__lte=end_date,
                is_active=True,
                approval_status='approved',
            ).select_related('user')
        )

        # Fetch sessions for WFO/WFH data
        sessions = list(
            AttendanceSession.objects.filter(
                org_id=org_id,
                user_id__in=user_ids,
                login_at__date__gte=start_date,
                login_at__date__lte=end_date,
            )
        )

        # Build session work_mode map: {(user_id, date): work_mode}
        session_mode_map = {}
        for s in sessions:
            key = (s.user_id, s.login_at.date())
            # If any session is WFO, the day is WFO
            existing = session_mode_map.get(key)
            if existing != 'wfo':
                session_mode_map[key] = s.work_mode

        # Build per-employee summary
        employee_data = {}
        for user in org_users:
            employee_data[user.id] = {
                'user_id': user.id,
                'name': user.get_full_name() or user.first_name or user.username or user.email,
                'email': user.email,
                'present': 0,
                'wfo': 0,
                'wfh': 0,
                'absent': 0,
                'half_day': 0,
                'leave': 0,
                'on_duty': 0,
                'total_hours': 0,
                'total_late_minutes': 0,
                'days': [],
            }

        # Build entry map
        entry_map = {}  # (user_id, date) → entry
        for e in entries:
            key = (e.user_id, e.entry_date)
            existing = entry_map.get(key)
            if existing is None or e.updated_at > existing.updated_at:
                entry_map[key] = e

        # Iterate over date range
        current = start_date
        all_dates = []
        while current <= end_date:
            all_dates.append(current)
            current += timedelta(days=1)

        for uid, emp in employee_data.items():
            for d in all_dates:
                entry = entry_map.get((uid, d))
                session_mode = session_mode_map.get((uid, d), 'unknown')

                if entry:
                    active_work_mode = entry.work_mode if entry.work_mode != 'unknown' else session_mode
                    st = entry.status
                    if st in ('present', 'wfh', 'on_duty'):
                        emp['present'] += 1
                        if active_work_mode == 'wfo' or st == 'present':
                            emp['wfo'] += (1 if active_work_mode == 'wfo' else 0)
                            emp['wfh'] += (1 if active_work_mode == 'wfh' or st == 'wfh' else 0)
                        elif st == 'wfh':
                            emp['wfh'] += 1
                    elif st == 'half_day':
                        emp['half_day'] += 1
                    elif st == 'leave':
                        emp['leave'] += 1
                    elif st == 'absent':
                        emp['absent'] += 1

                    emp['total_hours'] += float(entry.hours_worked or 0)
                    emp['total_late_minutes'] += int(entry.late_minutes or 0)

                    emp['days'].append({
                        'date': d.isoformat(),
                        'status': entry.status,
                        'work_mode': active_work_mode,
                        'in_time': entry.in_time.strftime('%H:%M') if entry.in_time else '',
                        'out_time': entry.out_time.strftime('%H:%M') if entry.out_time else '',
                        'hours': float(entry.hours_worked or 0),
                        'late_min': int(entry.late_minutes or 0),
                    })
                else:
                    # Check if Sunday / not a working day
                    is_sunday = d.weekday() == 6
                    emp['days'].append({
                        'date': d.isoformat(),
                        'status': 'off' if is_sunday else 'absent',
                        'work_mode': 'unknown',
                        'in_time': '',
                        'out_time': '',
                        'hours': 0,
                        'late_min': 0,
                    })
                    if not is_sunday and d <= timezone.localdate():
                        emp['absent'] += 1

        # Build org-level summary
        total_wfo = sum(e['wfo'] for e in employee_data.values())
        total_wfh = sum(e['wfh'] for e in employee_data.values())
        total_present = sum(e['present'] for e in employee_data.values())
        total_absent = sum(e['absent'] for e in employee_data.values())

        return Response({
            'period': period,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'summary': {
                'total_employees': len(org_users),
                'total_present_days': total_present,
                'total_wfo_days': total_wfo,
                'total_wfh_days': total_wfh,
                'total_absent_days': total_absent,
                'wfo_ratio': round(total_wfo / max(total_wfo + total_wfh, 1) * 100, 1),
            },
            'employees': list(employee_data.values()),
        })


class AttendanceReportExportView(OrgScopedBaseAPIView):
    """GET → Export attendance data as CSV"""
    permission_classes = [HasModulePermission]
    required_permissions = {'GET': 'human_resources:attendance_dashboard:view'}

    def get(self, request):
        import csv
        import io
        from datetime import timedelta
        import calendar

        org_id = self.get_org_id()
        month_str = request.query_params.get('month')
        if month_str:
            try:
                year, mon = [int(x) for x in month_str.split('-')]
            except (ValueError, TypeError):
                year, mon = timezone.localdate().year, timezone.localdate().month
        else:
            today = timezone.localdate()
            year, mon = today.year, today.month

        start_date = date(year, mon, 1)
        end_date = date(year, mon, calendar.monthrange(year, mon)[1])

        org_users = _get_organization_users(org_id)
        user_ids = [u.id for u in org_users]

        entries = list(
            AttendanceEntry.objects.filter(
                org_id=org_id, user_id__in=user_ids,
                entry_date__gte=start_date, entry_date__lte=end_date,
                is_active=True, approval_status='approved',
            ).select_related('user').order_by('user__email', 'entry_date')
        )

        sessions = list(
            AttendanceSession.objects.filter(
                org_id=org_id, user_id__in=user_ids,
                login_at__date__gte=start_date, login_at__date__lte=end_date,
            )
        )
        session_mode_map = {}
        for s in sessions:
            key = (s.user_id, s.login_at.date())
            existing = session_mode_map.get(key)
            if existing != 'wfo':
                session_mode_map[key] = s.work_mode

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Employee', 'Email', 'Date', 'Status', 'Work Mode',
            'In Time', 'Out Time', 'Hours Worked', 'Late (min)',
            'Salary Deduction (days)', 'Attendance Score',
            'Login IP', 'GPS Distance (m)',
        ])

        entry_map = {}
        for e in entries:
            key = (e.user_id, e.entry_date)
            existing = entry_map.get(key)
            if existing is None or e.updated_at > existing.updated_at:
                entry_map[key] = e

        session_detail_map = {}
        for s in sessions:
            key = (s.user_id, s.login_at.date())
            if key not in session_detail_map:
                session_detail_map[key] = s

        current = start_date
        while current <= end_date:
            for user in org_users:
                entry = entry_map.get((user.id, current))
                session = session_detail_map.get((user.id, current))
                work_mode = session_mode_map.get((user.id, current), '')

                writer.writerow([
                    user.get_full_name() or user.username,
                    user.email,
                    current.isoformat(),
                    entry.status if entry else ('off' if current.weekday() == 6 else 'absent'),
                    work_mode.upper() if work_mode else '',
                    entry.in_time.strftime('%H:%M') if entry and entry.in_time else '',
                    entry.out_time.strftime('%H:%M') if entry and entry.out_time else '',
                    float(entry.hours_worked or 0) if entry else '',
                    int(entry.late_minutes or 0) if entry else '',
                    float(entry.salary_deduction_days or 0) if entry else '',
                    int(entry.attendance_score_points or 100) if entry else '',
                    session.login_ip if session else '',
                    int(session.gps_distance_meters) if session and session.gps_distance_meters else '',
                ])
            current += timedelta(days=1)

        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="attendance_{year}_{mon:02d}.csv"'
        return response


# ==============================================================================
# HELPERS
# ==============================================================================

def _office_payload(office):
    """Serialize an OfficeLocation with its registered IPs."""
    return {
        'id': office.id,
        'name': office.name,
        'address': office.address,
        'latitude': float(office.latitude) if office.latitude else None,
        'longitude': float(office.longitude) if office.longitude else None,
        'geofence_radius_meters': office.geofence_radius_meters,
        'is_active': office.is_active,
        'idle_timeout_enabled': office.idle_timeout_enabled,
        'idle_timeout_minutes': office.idle_timeout_minutes,
        'require_dual_signal': office.require_dual_signal,
        'registered_ips': [
            {
                'id': ip.id,
                'ip_address': ip.ip_address,
                'ip_cidr': ip.ip_cidr,
                'label': ip.label,
                'is_active': ip.is_active,
            }
            for ip in office.registered_ips.all()
        ],
        'created_at': office.created_at.isoformat() if office.created_at else None,
    }


def _session_payload(session, include_user=False):
    """Serialize an AttendanceSession."""
    data = {
        'id': session.id,
        'login_at': session.login_at.isoformat() if session.login_at else None,
        'logout_at': session.logout_at.isoformat() if session.logout_at else None,
        'logout_source': session.logout_source,
        'login_ip': session.login_ip,
        'gps_status': session.gps_status,
        'gps_distance_meters': session.gps_distance_meters,
        'work_mode': session.work_mode,
        'work_mode_reason': session.work_mode_reason,
        'ip_matched_office': session.ip_matched_office.name if session.ip_matched_office else None,
        'gps_nearest_office': session.gps_nearest_office.name if session.gps_nearest_office else None,
        'is_anomalous': session.is_anomalous,
        'anomaly_reasons': session.anomaly_reasons,
        'anomaly_resolution': session.anomaly_resolution,
    }
    if include_user:
        data['user_id'] = session.user_id
        data['user_name'] = (
            session.user.get_full_name()
            or session.user.first_name
            or session.user.username
            or session.user.email
        )
        data['user_email'] = session.user.email
        # Include raw GPS for admin review
        data['login_latitude'] = float(session.login_latitude) if session.login_latitude else None
        data['login_longitude'] = float(session.login_longitude) if session.login_longitude else None
        data['gps_accuracy_meters'] = session.gps_accuracy_meters
        data['anomaly_resolved_by'] = (
            session.anomaly_resolved_by.get_full_name()
            if session.anomaly_resolved_by else None
        )
        data['anomaly_resolved_at'] = (
            session.anomaly_resolved_at.isoformat()
            if session.anomaly_resolved_at else None
        )
        data['anomaly_resolution_note'] = session.anomaly_resolution_note
    return data


def _parse_date(value):
    """Parse a date string, default to today."""
    if value:
        try:
            return date.fromisoformat(str(value))
        except (ValueError, TypeError):
            pass
    return timezone.localdate()


def _get_organization_users(org_id):
    """Get all users belonging to an organization."""
    from django.db.models import Q
    if not org_id:
        return []
    return list(
        User.objects.filter(
            Q(shop_credentials__organization_id=org_id)
            | Q(team_settings__organization__organization_id=org_id)
            | Q(workspace_memberships__workspace__organization_id=org_id)
        ).distinct()
    )


class PublicHolidayListCreateView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view'],
        'POST': 'human_resources:workforce_sheet:edit'
    }

    def get(self, request):
        org_id = self.get_org_id()
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=400)
        holidays = PublicHoliday.objects.filter(org_id=org_id).order_by('date')
        serializer = PublicHolidaySerializer(holidays, many=True)
        return Response(serializer.data, status=200)

    def post(self, request):
        org_id = self.get_org_id()
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=400)
        serializer = PublicHolidaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        holiday = serializer.save(org_id=org_id)
        return Response(PublicHolidaySerializer(holiday).data, status=201)


class PublicHolidayDetailView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view'],
        'PUT': 'human_resources:workforce_sheet:edit',
        'PATCH': 'human_resources:workforce_sheet:edit',
        'DELETE': 'human_resources:workforce_sheet:edit'
    }

    def _get_holiday(self, pk):
        org_id = self.get_org_id()
        return PublicHoliday.objects.filter(id=pk, org_id=org_id).first()

    def get(self, request, pk):
        holiday = self._get_holiday(pk)
        if not holiday:
            return Response({'detail': 'Holiday not found.'}, status=404)
        serializer = PublicHolidaySerializer(holiday)
        return Response(serializer.data, status=200)

    def put(self, request, pk):
        holiday = self._get_holiday(pk)
        if not holiday:
            return Response({'detail': 'Holiday not found.'}, status=404)
        serializer = PublicHolidaySerializer(holiday, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)

    def patch(self, request, pk):
        holiday = self._get_holiday(pk)
        if not holiday:
            return Response({'detail': 'Holiday not found.'}, status=404)
        serializer = PublicHolidaySerializer(holiday, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)

    def delete(self, request, pk):
        holiday = self._get_holiday(pk)
        if not holiday:
            return Response({'detail': 'Holiday not found.'}, status=404)
        holiday.delete()
        return Response(status=204)


class AttendanceSessionExemptionListCreateView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view'],
        'POST': 'human_resources:workforce_sheet:edit'
    }

    def get(self, request):
        org_id = self.get_org_id()
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=400)
        exemptions = AttendanceSessionExemption.objects.filter(org_id=org_id).order_by('-created_at')
        serializer = AttendanceSessionExemptionSerializer(exemptions, many=True)
        return Response(serializer.data, status=200)

    def post(self, request):
        org_id = self.get_org_id()
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=400)
        serializer = AttendanceSessionExemptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        exemption = serializer.save(org_id=org_id)
        return Response(AttendanceSessionExemptionSerializer(exemption).data, status=201)


class AttendanceSessionExemptionDetailView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view'],
        'PUT': 'human_resources:workforce_sheet:edit',
        'PATCH': 'human_resources:workforce_sheet:edit',
        'DELETE': 'human_resources:workforce_sheet:edit'
    }

    def _get_exemption(self, pk):
        org_id = self.get_org_id()
        return AttendanceSessionExemption.objects.filter(id=pk, org_id=org_id).first()

    def get(self, request, pk):
        exemption = self._get_exemption(pk)
        if not exemption:
            return Response({'detail': 'Exemption not found.'}, status=404)
        serializer = AttendanceSessionExemptionSerializer(exemption)
        return Response(serializer.data, status=200)

    def put(self, request, pk):
        exemption = self._get_exemption(pk)
        if not exemption:
            return Response({'detail': 'Exemption not found.'}, status=404)
        serializer = AttendanceSessionExemptionSerializer(exemption, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)

    def patch(self, request, pk):
        exemption = self._get_exemption(pk)
        if not exemption:
            return Response({'detail': 'Exemption not found.'}, status=404)
        serializer = AttendanceSessionExemptionSerializer(exemption, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)

    def delete(self, request, pk):
        exemption = self._get_exemption(pk)
        if not exemption:
            return Response({'detail': 'Exemption not found.'}, status=404)
        exemption.delete()
        return Response(status=204)


class AttendanceSessionHeartbeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'detail': 'Organization not found.'}, status=400)
        session = AttendanceSession.objects.filter(
            org_id=org_id,
            user=request.user,
            logout_at__isnull=True
        ).order_by('-login_at').first()

        if not session:
            return Response({'detail': 'No active attendance session found.'}, status=400)

        now = timezone.now()
        if session.last_activity_at and (now - session.last_activity_at).total_seconds() < 270:
            return Response({'status': 'Heartbeat received (throttled).'}, status=200)

        session.last_activity_at = now
        session.save(update_fields=['last_activity_at'])
        return Response({'status': 'Heartbeat received.'}, status=200)
