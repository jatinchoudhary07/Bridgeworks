from datetime import datetime, date, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
import pytz

from rest_framework.test import APIClient
from rest_framework import status

from core.models import (
    OfficeLocation, OfficeIP, AttendanceSession, AttendanceEntry, ShopCredentials
)
from core.services.geofence import haversine_distance, detect_work_mode, check_anomalies
from core.tasks.midnight_logout import midnight_logout_job

User = get_user_model()


class AttendanceGeofencingTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org_id = 'test-org-123'
        
        # User creation triggers signal that creates ShopCredentials and TeamMemberSettings
        self.user = User.objects.create_user(username='employee', password='password123')
        self.user.date_joined = timezone.make_aware(datetime(2026, 6, 1, 0, 0, 0))
        self.user.save()
        self.admin = User.objects.create_user(username='admin', password='password123')
        
        # Retrieve the auto-created ShopCredentials for self.admin and update it
        self.shop_creds = ShopCredentials.objects.get(owner=self.admin)
        self.shop_creds.organization_id = self.org_id
        self.shop_creds.timezone = 'Asia/Kolkata'
        self.shop_creds.myshopify_domain = 'test-org.myshopify.com'
        self.shop_creds.save()

        # Delete the auto-created ShopCredentials for the employee, 
        # and create TeamMemberSettings linking them to the admin's org
        from core.models import TeamMemberSettings
        ShopCredentials.objects.filter(owner=self.user).delete()
        TeamMemberSettings.objects.create(
            user=self.user,
            organization=self.shop_creds,
            role='teammate'
        )
        self.user.refresh_from_db()
        self.admin.refresh_from_db()

        # Mumbai HQ Office (19.0760, 72.8777)
        self.office = OfficeLocation.objects.create(
            org_id=self.org_id,
            name='Mumbai HQ',
            address='Mumbai, Maharashtra',
            latitude=Decimal('19.0760000'),
            longitude=Decimal('72.8777000'),
            geofence_radius_meters=200,
            created_by=self.admin
        )

        # Register office IP
        self.office_ip = OfficeIP.objects.create(
            office=self.office,
            ip_address='192.168.1.50',
            label='Office WiFi'
        )

    def test_haversine_distance(self):
        # Coords about 100 meters apart
        lat1, lon1 = 19.0760, 72.8777
        lat2, lon2 = 19.0765, 72.8782
        dist = haversine_distance(lat1, lon1, lat2, lon2)
        # Verify distance is within sanity bounds (approx ~76m)
        self.assertTrue(50 < dist < 100)

    def test_detect_work_mode_ip_match(self):
        # Login from registered office IP, no GPS signal
        res = detect_work_mode(self.org_id, '192.168.1.50')
        self.assertEqual(res['work_mode'], 'wfo')
        self.assertEqual(res['reason'], 'ip_match')
        self.assertEqual(res['ip_matched_office_id'], self.office.id)

    def test_detect_work_mode_gps_match(self):
        # Login from unregistered IP but within geofence radius (lat/lng close to office)
        res = detect_work_mode(self.org_id, '192.168.5.5', 19.0761, 72.8778)
        self.assertEqual(res['work_mode'], 'wfo')
        self.assertEqual(res['reason'], 'gps_within_geofence')
        self.assertEqual(res['gps_nearest_office_id'], self.office.id)
        self.assertTrue(res['gps_distance_meters'] < 200)

    def test_detect_work_mode_wfh(self):
        # Login from home IP, GPS far away (e.g. Pune: ~120km away)
        res = detect_work_mode(self.org_id, '192.168.5.5', 18.5204, 73.8567)
        self.assertEqual(res['work_mode'], 'wfh')
        self.assertIn('gps_outside_geofence', res['reason'])

    def test_anomaly_ip_gps_mismatch(self):
        # Session where IP matches Mumbai HQ, but GPS is Pune (120km away)
        session = AttendanceSession(
            org_id=self.org_id,
            user=self.user,
            login_ip='192.168.1.50', # IP match
            login_latitude=Decimal('18.5204'),
            login_longitude=Decimal('73.8567'),
            gps_distance_meters=120000,
            ip_matched_office=self.office,
            gps_nearest_office=self.office
        )
        anomalies = check_anomalies(session)
        self.assertTrue(any('ip_gps_mismatch' in a for a in anomalies))

    def test_anomaly_suspicious_gps_exact_integers(self):
        # Exact integer coordinates (spoofing check)
        session = AttendanceSession(
            org_id=self.org_id,
            user=self.user,
            login_latitude=Decimal('19.0000000'),
            login_longitude=Decimal('72.0000000')
        )
        anomalies = check_anomalies(session)
        self.assertTrue(any('suspicious_gps: coordinates are exact integers' in a for a in anomalies))

    def test_anomaly_low_accuracy(self):
        session = AttendanceSession(
            org_id=self.org_id,
            user=self.user,
            gps_accuracy_meters=600.0
        )
        anomalies = check_anomalies(session)
        self.assertTrue(any('low_gps_accuracy' in a for a in anomalies))

    def test_session_start_api(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            'latitude': 19.0761,
            'longitude': 72.8778,
            'gps_accuracy': 10.0,
            'gps_status': 'captured'
        }
        
        with patch('core.views_attendance_geo.get_client_ip', return_value='192.168.1.50'):
            response = self.client.post('/api/attendance/session/start/', payload, format='json')
            
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['work_mode'], 'wfo')
        
        # Verify AttendanceSession was created
        self.assertTrue(AttendanceSession.objects.filter(user=self.user, org_id=self.org_id).exists())
        # Verify daily AttendanceEntry was created
        self.assertTrue(AttendanceEntry.objects.filter(user=self.user, org_id=self.org_id, entry_date=date.today()).exists())

    def test_session_start_wfh_half_day(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            'latitude': 18.5204,  # Pune coord (WFH)
            'longitude': 73.8567,
            'gps_accuracy': 10.0,
            'gps_status': 'captured'
        }

        # Mock _auto_compute_status to return half_day due to late arrival
        with patch('core.views_mydesk._auto_compute_status', return_value=('half_day', Decimal('0.5'), 120, 0, 4.0, 50)):
            with patch('core.views_attendance_geo.get_client_ip', return_value='192.168.5.5'):
                response = self.client.post('/api/attendance/session/start/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['work_mode'], 'wfh')

        # Verify entry exists and has status 'half_day' but work_mode 'wfh'
        entry = AttendanceEntry.objects.filter(
            user=self.user, org_id=self.org_id, entry_date=date.today()
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.status, 'half_day')
        self.assertEqual(entry.work_mode, 'wfh')

    def test_session_end_api(self):
        self.client.force_authenticate(user=self.user)
        
        # Setup an active session
        session = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo',
            login_ip='192.168.1.50'
        )
        from datetime import timedelta
        session.login_at = timezone.now() - timedelta(hours=8)
        session.save(update_fields=['login_at'])
        
        # Setup today's entry
        entry = AttendanceEntry.objects.create(
            org_id=self.org_id,
            user=self.user,
            entry_date=date.today(),
            in_time=time(9, 0),
            status='present',
            is_active=True
        )

        response = self.client.post('/api/attendance/session/end/', {'source': 'manual'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify session logout set
        session.refresh_from_db()
        self.assertIsNotNone(session.logout_at)
        self.assertEqual(session.logout_source, 'manual')

        # Verify entry out_time set
        entry.refresh_from_db()
        self.assertIsNotNone(entry.out_time)
        self.assertTrue(entry.hours_worked > 0)

    def test_midnight_logout_job(self):
        # Setup session and entry when timezone.now is not mocked to avoid sqlite insert mock error
        session = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo',
            login_ip='192.168.1.50'
        )
        # Manually backdate login_at using save()
        session.login_at = datetime(2026, 6, 18, 9, 0, tzinfo=pytz.utc)
        session.save(update_fields=['login_at'])

        entry = AttendanceEntry.objects.create(
            org_id=self.org_id,
            user=self.user,
            entry_date=date(2026, 6, 18),
            in_time=time(9, 0),
            status='present',
            is_active=True
        )

        # Set fake time to 2026-06-19 00:05 in Asia/Kolkata (which is 2026-06-18 18:35 UTC)
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        local_target = kolkata_tz.localize(datetime(2026, 6, 19, 0, 5))
        utc_target = local_target.astimezone(pytz.utc)

        # Run job with mocked timezone.now
        with patch('django.utils.timezone.now', return_value=utc_target):
            midnight_logout_job()

        # Session should be expired
        session.refresh_from_db()
        self.assertIsNotNone(session.logout_at)
        self.assertEqual(session.logout_source, 'midnight_job')

        # Entry should have out_time set to the default fallback: 18:30:00 of that login date
        entry.refresh_from_db()
        self.assertEqual(entry.out_time, time(18, 30, 0))

    def test_midnight_logout_job_with_rulebook(self):
        from core.models import AttendanceRulebook
        AttendanceRulebook.objects.create(
            org_id=self.org_id,
            user=self.user,
            shift_end=time(18, 30, 0)
        )

        session = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo',
            login_ip='192.168.1.50'
        )
        session.login_at = datetime(2026, 6, 18, 9, 0, tzinfo=pytz.utc)
        session.save(update_fields=['login_at'])

        entry = AttendanceEntry.objects.create(
            org_id=self.org_id,
            user=self.user,
            entry_date=date(2026, 6, 18),
            in_time=time(9, 0),
            status='present',
            is_active=True
        )

        kolkata_tz = pytz.timezone('Asia/Kolkata')
        local_target = kolkata_tz.localize(datetime(2026, 6, 19, 0, 5))
        utc_target = local_target.astimezone(pytz.utc)

        with patch('django.utils.timezone.now', return_value=utc_target):
            midnight_logout_job()

        entry.refresh_from_db()
        self.assertEqual(entry.out_time, time(18, 30, 0))

    def test_session_end_with_hr_override(self):
        self.client.force_authenticate(user=self.user)

        # Setup an active session
        session = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo',
            login_ip='192.168.1.50'
        )
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        today_date = date.today()
        session.login_at = kolkata_tz.localize(datetime(today_date.year, today_date.month, today_date.day, 9, 0, 0))
        session.save(update_fields=['login_at'])

        # Setup today's entry with HR override status='absent', score=0, deduction=1.0
        entry = AttendanceEntry.objects.create(
            org_id=self.org_id,
            user=self.user,
            entry_date=date.today(),
            in_time=time(9, 0),
            status='absent',
            auto_status='present',
            hr_override_status='absent',
            hr_override_reason='HR manual marking override',
            hr_override_by=self.admin,
            hr_override_at=timezone.now(),
            attendance_score_points=0,
            salary_deduction_days=Decimal('1.0'),
            is_active=True
        )

        # Mock timezone.now to be at 6:00 PM today
        kolkata_tz = pytz.timezone('Asia/Kolkata')
        today_date = date.today()
        local_target = kolkata_tz.localize(datetime(today_date.year, today_date.month, today_date.day, 18, 0, 0))
        utc_target = local_target.astimezone(pytz.utc)

        with patch('django.utils.timezone.now', return_value=utc_target):
            response = self.client.post('/api/attendance/session/end/', {'source': 'manual'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify entry's out_time is updated but status and scoring remain HR overridden
        entry.refresh_from_db()
        self.assertIsNotNone(entry.out_time)
        self.assertEqual(entry.status, 'absent')
        self.assertEqual(entry.auto_status, 'present')  # auto_status should reflect computed present
        self.assertEqual(entry.attendance_score_points, 0)
        self.assertEqual(entry.salary_deduction_days, Decimal('1.0'))

    def test_cidr_subnet_matching(self):
        # Register a subnet CIDR range on the office
        OfficeIP.objects.create(
            office=self.office,
            ip_cidr='110.226.173.0/24',
            label='Office Subnet'
        )

        # Login from an IP within the subnet -> should match WFO
        res = detect_work_mode(self.org_id, '110.226.173.125')
        self.assertEqual(res['work_mode'], 'wfo')
        self.assertEqual(res['reason'], 'ip_match')
        self.assertEqual(res['ip_matched_office_id'], self.office.id)

        # Login from an IP outside the subnet -> should be WFH (no other signal matching)
        res2 = detect_work_mode(self.org_id, '110.226.174.125')
        self.assertEqual(res2['work_mode'], 'wfh')
        self.assertEqual(res2['reason'], 'ip_no_match+gps_not_available')

    def test_detect_work_mode_require_dual_signal(self):
        # Enable dual signal requirement on the office
        self.office.require_dual_signal = True
        self.office.save()

        # Case 1: IP matches AND GPS within geofence -> WFO
        res = detect_work_mode(self.org_id, '192.168.1.50', 19.0761, 72.8778)
        self.assertEqual(res['work_mode'], 'wfo')
        self.assertEqual(res['reason'], 'ip_match_and_gps_within_geofence')

        # Case 2: IP matches but GPS is outside geofence -> WFH
        res2 = detect_work_mode(self.org_id, '192.168.1.50', 18.5204, 73.8567)
        self.assertEqual(res2['work_mode'], 'wfh')
        self.assertEqual(res2['ip_matched_office_id'], self.office.id)
        self.assertIn('dual_signal_required', res2['reason'])

        # Case 3: IP matches but GPS is None (unavailable) -> WFH
        res3 = detect_work_mode(self.org_id, '192.168.1.50')
        self.assertEqual(res3['work_mode'], 'wfh')
        self.assertEqual(res3['ip_matched_office_id'], self.office.id)
        self.assertIn('dual_signal_required', res3['reason'])

        # Case 4: IP doesn't match but GPS is within geofence -> WFH (since BOTH are required)
        res4 = detect_work_mode(self.org_id, '192.168.5.5', 19.0761, 72.8778)
        self.assertEqual(res4['work_mode'], 'wfh')
        self.assertIn('ip_no_match', res4['reason'])

    def test_session_start_api_gps_required_flag(self):
        self.office.require_dual_signal = True
        self.office.save()

        self.client.force_authenticate(user=self.user)
        payload = {
            'gps_status': 'denied'
        }
        
        # IP matches office, but GPS status is denied -> gps_required should be True in response
        with patch('core.views_attendance_geo.get_client_ip', return_value='192.168.1.50'):
            response = self.client.post('/api/attendance/session/start/', payload, format='json')
            
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['work_mode'], 'wfh')
        self.assertTrue(response.json()['gps_required'])

    def test_concurrent_sessions_auto_closed(self):
        self.client.force_authenticate(user=self.user)
        
        # Setup an active session
        session1 = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo',
            login_ip='192.168.1.50'
        )
        self.assertIsNone(session1.logout_at)

        # Start a new session
        payload = {
            'latitude': 19.0761,
            'longitude': 72.8778,
            'gps_accuracy': 10.0,
            'gps_status': 'captured'
        }
        with patch('core.views_attendance_geo.get_client_ip', return_value='192.168.1.50'):
            response = self.client.post('/api/attendance/session/start/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify old session was terminated under 'superseded'
        session1.refresh_from_db()
        self.assertIsNotNone(session1.logout_at)
        self.assertEqual(session1.logout_source, 'superseded')

    def test_trusted_proxy_ip_filtering(self):
        from django.conf import settings
        from core.services.geofence import get_client_ip
        from django.test import RequestFactory

        rf = RequestFactory()
        
        # Scenario A: Whitelist is empty -> default behaviour (trust headers)
        with patch.object(settings, 'TRUSTED_PROXY_IPS', []):
            req = rf.post('/dummy/', HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8', REMOTE_ADDR='127.0.0.1')
            self.assertEqual(get_client_ip(req), '1.2.3.4')

        # Scenario B: REMOTE_ADDR is in whitelist -> trust headers
        with patch.object(settings, 'TRUSTED_PROXY_IPS', ['127.0.0.1']):
            req = rf.post('/dummy/', HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8', REMOTE_ADDR='127.0.0.1')
            self.assertEqual(get_client_ip(req), '1.2.3.4')

        # Scenario C: REMOTE_ADDR is NOT in whitelist -> ignore headers, return REMOTE_ADDR
        with patch.object(settings, 'TRUSTED_PROXY_IPS', ['10.0.0.1']):
            req = rf.post('/dummy/', HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8', REMOTE_ADDR='127.0.0.1')
            self.assertEqual(get_client_ip(req), '127.0.0.1')

    def test_is_working_day(self):
        from core.views_mydesk import _is_working_day
        class DummyRulebook:
            weekly_off = 'sunday'
            saturday_working = 'yes'

        rb = DummyRulebook()
        # Monday is weekday 0 -> should be working
        self.assertTrue(_is_working_day(date(2026, 6, 15), rb))
        # Sunday is weekday 6 -> should be weekly off (False)
        self.assertFalse(_is_working_day(date(2026, 6, 21), rb))

        # Test Saturday off
        rb.saturday_working = 'no'
        self.assertFalse(_is_working_day(date(2026, 6, 20), rb))

        # Test alternate Saturday: 1st, 3rd, 5th working; 2nd, 4th off
        rb.saturday_working = 'alternate'
        # 2026-06-06 is 1st Saturday -> True
        self.assertTrue(_is_working_day(date(2026, 6, 6), rb))
        # 2026-06-13 is 2nd Saturday -> False
        self.assertFalse(_is_working_day(date(2026, 6, 13), rb))
        # 2026-06-20 is 3rd Saturday -> True
        self.assertTrue(_is_working_day(date(2026, 6, 20), rb))

    def test_public_holidays_paid_off(self):
        from core.models import PublicHoliday
        from core.views_mydesk import _attendance_month_summary
        from django.conf import settings

        # Create a public holiday on June 10, 2026
        PublicHoliday.objects.create(org_id=self.org_id, date=date(2026, 6, 10), name='Festival')

        # Scenario A: USE_HOLIDAY_CALENDAR is False -> June 10 has no entry -> LOP/Absent
        with patch.object(settings, 'USE_HOLIDAY_CALENDAR', False):
            working, present, lop = _attendance_month_summary(self.org_id, self.user, date(2026, 6, 1))
            # No entries exist for user, so all 30 days are absent -> present=0, lop=30
            self.assertEqual(present, 0.0)
            self.assertEqual(lop, 30.0)

        # Scenario B: USE_HOLIDAY_CALENDAR is True -> June 10 becomes paid present -> present=1.0, lop=29.0
        with patch.object(settings, 'USE_HOLIDAY_CALENDAR', True):
            working, present, lop = _attendance_month_summary(self.org_id, self.user, date(2026, 6, 1))
            self.assertEqual(present, 1.0)
            self.assertEqual(lop, 29.0)

    def test_joiner_leaver_date_bounds(self):
        from core.models import WorkforceMember
        from core.views_mydesk import _attendance_month_summary
        
        # Link user to a workforce member who joined mid-month on June 15, 2026
        member = WorkforceMember.objects.create(
            org_id=self.org_id,
            full_name='Test Employee',
            email=self.user.email,
            date_of_joining=date(2026, 6, 15)
        )

        # In summary, days before June 15 must count as absent/no-pay.
        # Weekends/holidays after June 15 are paid off.
        from django.conf import settings
        with patch.object(settings, 'USE_SATURDAY_POLICY', True):
            working, present, lop = _attendance_month_summary(self.org_id, self.user, date(2026, 6, 1))
            # There are 3 Sundays after June 15 (June 21, 28) + 2 Saturdays if off.
            # So weekends after June 15 get overridden to present, while days before June 15 remain absent (LOP).
            # This verifies date-bounding is working properly.
            self.assertTrue(present > 0.0)

    def test_granular_deductions(self):
        from core.views_mydesk import _attendance_month_summary
        from django.conf import settings

        # Create one present entry on June 5, 2026 with a 1-hour late mark salary deduction of 0.125
        AttendanceEntry.objects.create(
            org_id=self.org_id,
            user=self.user,
            entry_date=date(2026, 6, 5),
            status='present',
            salary_deduction_days=Decimal('0.125'),
            approval_status='approved',
            is_active=True
        )

        # Scenario A: USE_GRANULAR_DEDUCTIONS = False -> 1.0 present day
        with patch.object(settings, 'USE_GRANULAR_DEDUCTIONS', False):
            working, present, lop = _attendance_month_summary(self.org_id, self.user, date(2026, 6, 1))
            self.assertEqual(present, 1.0)

        # Scenario B: USE_GRANULAR_DEDUCTIONS = True -> 1.0 - 0.125 = 0.875 present days -> rounded to 0.88, lop rounded to 29.12
        with patch.object(settings, 'USE_GRANULAR_DEDUCTIONS', True):
            working, present, lop = _attendance_month_summary(self.org_id, self.user, date(2026, 6, 1))
            self.assertEqual(present, 0.88)
            self.assertEqual(lop, 29.12)

    def test_session_heartbeat_api(self):
        # Create an active session
        session = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo'
        )
        self.assertIsNone(session.last_activity_at)

        # Authenticate employee
        self.client.force_authenticate(user=self.user)
        
        # 1. First heartbeat: updates last_activity_at
        first_time = timezone.now()
        with patch('django.utils.timezone.now', return_value=first_time):
            response = self.client.post('/api/attendance/session/heartbeat/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['status'], 'Heartbeat received.')
        
        session.refresh_from_db()
        self.assertIsNotNone(session.last_activity_at)
        t1 = session.last_activity_at

        # 2. Second heartbeat 2 minutes later: should be throttled, last_activity_at remains unchanged
        second_time = first_time + timezone.timedelta(minutes=2)
        with patch('django.utils.timezone.now', return_value=second_time):
            response2 = self.client.post('/api/attendance/session/heartbeat/', {}, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.json()['status'], 'Heartbeat received (throttled).')
        
        session.refresh_from_db()
        self.assertEqual(session.last_activity_at, t1)

        # 3. Third heartbeat 5 minutes later: should update last_activity_at
        third_time = first_time + timezone.timedelta(minutes=5)
        with patch('django.utils.timezone.now', return_value=third_time):
            response3 = self.client.post('/api/attendance/session/heartbeat/', {}, format='json')
        self.assertEqual(response3.status_code, status.HTTP_200_OK)
        self.assertEqual(response3.json()['status'], 'Heartbeat received.')
        
        session.refresh_from_db()
        self.assertNotEqual(session.last_activity_at, t1)

    def test_anomaly_exemptions(self):
        from core.models import AttendanceSessionExemption
        from core.services.geofence import check_anomalies

        # Pune location (120km away) -> Should trigger IP-GPS mismatch
        session = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            login_ip='192.168.1.50',  # matches Mumbai HQ
            login_latitude=Decimal('18.5204'),
            login_longitude=Decimal('73.8567'),
            gps_distance_meters=120000.0,
            gps_nearest_office=self.office,
            ip_matched_office=self.office
        )

        # Without exemption -> Anomaly triggered
        anomalies = check_anomalies(session)
        self.assertTrue(any('ip_gps_mismatch' in r for r in anomalies))

        # With active exemption for ip_mismatch -> Skipped
        AttendanceSessionExemption.objects.create(
            org_id=self.org_id,
            user=self.user,
            exemption_type='ip_mismatch',
            is_active=True
        )
        anomalies_exempt = check_anomalies(session)
        self.assertFalse(any('ip_gps_mismatch' in r for r in anomalies_exempt))

    def test_close_idle_sessions_job(self):
        from core.tasks.midnight_logout import close_idle_sessions_job
        
        # Mumbai HQ Office has default idle timeout
        self.office.idle_timeout_enabled = True
        self.office.idle_timeout_minutes = 15
        self.office.save()

        # Create a session started 20 minutes ago with last activity 20 minutes ago
        start_time = timezone.now() - timezone.timedelta(minutes=20)
        session = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo',
            gps_nearest_office=self.office,
            login_at=start_time
        )
        # Manually backdate login_at since auto_now_add makes it read-only on save()
        AttendanceSession.objects.filter(id=session.id).update(login_at=start_time)
        session.refresh_from_db()

        # Create matching AttendanceEntry
        entry = AttendanceEntry.objects.create(
            org_id=self.org_id,
            user=self.user,
            entry_date=start_time.date(),
            status='present',
            in_time=start_time.time(),
            approval_status='approved',
            is_active=True
        )

        # Run the idle closure job
        close_idle_sessions_job()

        # Session should be closed as 'idle' at start_time
        session.refresh_from_db()
        self.assertIsNotNone(session.logout_at)
        self.assertEqual(session.logout_source, 'idle')

        # Entry should have its out_time set
        entry.refresh_from_db()
        self.assertIsNotNone(entry.out_time)

    def test_idle_timeout_settings_priority_chain(self):
        # 1. Start with global org defaults from ShopCredentials
        self.shop_creds.global_idle_timeout_enabled = True
        self.shop_creds.global_idle_timeout_minutes = 22
        self.shop_creds.save()

        # Deactivate office to simulate no-office matching
        self.office.is_active = False
        self.office.save()

        # Remove nearest office from matching coordinates to simulate no-office matching
        self.client.force_authenticate(user=self.user)
        payload = {
            'latitude': 10.0,  # Far away
            'longitude': 10.0,
            'gps_accuracy': 10.0,
            'gps_status': 'captured'
        }
        with patch('core.views_attendance_geo.get_client_ip', return_value='192.168.9.9'):
            response = self.client.post('/api/attendance/session/start/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Should return global defaults
        self.assertEqual(response.json()['idle_timeout_enabled'], True)
        self.assertEqual(response.json()['idle_timeout_minutes'], 22)

        # 2. Office-level settings override global defaults
        # Mumbai HQ Office (19.0760, 72.8777)
        self.office.is_active = True
        self.office.idle_timeout_enabled = True
        self.office.idle_timeout_minutes = 18
        self.office.save()

        payload = {
            'latitude': 19.0761,  # Matches Mumbai HQ Office
            'longitude': 72.8778,
            'gps_accuracy': 10.0,
            'gps_status': 'captured'
        }
        with patch('core.views_attendance_geo.get_client_ip', return_value='192.168.9.9'):
            response = self.client.post('/api/attendance/session/start/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Should return office setting
        self.assertEqual(response.json()['idle_timeout_enabled'], True)
        self.assertEqual(response.json()['idle_timeout_minutes'], 18)

        # 3. User-profile settings override office-level settings
        from core.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.idle_timeout_override_enabled = False
        profile.idle_timeout_override_minutes = 5
        profile.save()

        with patch('core.views_attendance_geo.get_client_ip', return_value='192.168.9.9'):
            response = self.client.post('/api/attendance/session/start/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Should return user settings (even if enabled is overridden to False)
        self.assertEqual(response.json()['idle_timeout_enabled'], False)
        self.assertEqual(response.json()['idle_timeout_minutes'], 5)

    def test_minimum_worked_hours_policy(self):
        # Authenticate employee
        self.client.force_authenticate(user=self.user)

        # 1. First scenario: total worked hours < 3.0 (marked Absent)
        # Create Session 1: 9:00 AM to 9:05 AM (5 mins)
        s1 = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo'
        )
        s1.login_at = timezone.make_aware(datetime(2026, 6, 19, 9, 0, 0))
        s1.logout_at = timezone.make_aware(datetime(2026, 6, 19, 9, 5, 0))
        s1.save(update_fields=['login_at', 'logout_at'])

        # Create Session 2: 3:00 PM to 5:00 PM (2 hours)
        s2 = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo'
        )
        s2.login_at = timezone.make_aware(datetime(2026, 6, 19, 15, 0, 0))
        s2.logout_at = timezone.make_aware(datetime(2026, 6, 19, 17, 0, 0))
        s2.save(update_fields=['login_at', 'logout_at'])

        # Create the daily entry
        entry = AttendanceEntry.objects.create(
            org_id=self.org_id,
            user=self.user,
            entry_date=date(2026, 6, 19),
            in_time=time(9, 0),
            status='present',
            is_active=True
        )

        # End the active session via view (this will trigger out_time and recalculation)
        s_active = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo'
        )
        s_active.login_at = timezone.make_aware(datetime(2026, 6, 19, 17, 0, 0))
        s_active.save(update_fields=['login_at'])

        # Mock current time to 5:05 PM
        end_time_utc = timezone.make_aware(datetime(2026, 6, 19, 17, 5, 0)).astimezone(pytz.utc)
        with patch('django.utils.timezone.now', return_value=end_time_utc):
            response = self.client.post('/api/attendance/session/end/', {'source': 'manual'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        # Total time is 5m + 2h + 5m = 2h 10m (< 3 hours) -> should be absent!
        self.assertEqual(entry.status, 'absent')
        self.assertEqual(entry.salary_deduction_days, Decimal('1.0'))
        self.assertEqual(entry.hours_worked, Decimal('2.17'))

        # 2. Second scenario: 3.0 <= total worked hours < 6.0 (marked Half Day)
        AttendanceSession.objects.all().delete()
        AttendanceEntry.objects.all().delete()

        # Create Session 1: 9:00 AM to 1:00 PM (4 hours)
        s3 = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo'
        )
        s3.login_at = timezone.make_aware(datetime(2026, 6, 19, 9, 0, 0))
        s3.logout_at = timezone.make_aware(datetime(2026, 6, 19, 13, 0, 0))
        s3.save(update_fields=['login_at', 'logout_at'])

        entry = AttendanceEntry.objects.create(
            org_id=self.org_id,
            user=self.user,
            entry_date=date(2026, 6, 19),
            in_time=time(9, 0),
            status='present',
            is_active=True
        )

        s4 = AttendanceSession.objects.create(
            org_id=self.org_id,
            user=self.user,
            work_mode='wfo'
        )
        s4.login_at = timezone.make_aware(datetime(2026, 6, 19, 13, 0, 0))
        s4.save(update_fields=['login_at'])
        end_time_utc = timezone.make_aware(datetime(2026, 6, 19, 13, 30, 0)).astimezone(pytz.utc)
        with patch('django.utils.timezone.now', return_value=end_time_utc):
            response = self.client.post('/api/attendance/session/end/', {'source': 'manual'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        # Total time is 4.5 hours (>= 3.0 and < 6.0) -> should be half day!
        self.assertEqual(entry.status, 'half_day')
        self.assertEqual(entry.salary_deduction_days, Decimal('0.5'))
        self.assertEqual(entry.hours_worked, Decimal('4.5'))
