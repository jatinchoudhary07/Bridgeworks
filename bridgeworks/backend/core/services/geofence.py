"""
Geofence service for WFO/WFH attendance detection.

Provides:
- get_client_ip(request) — robust IP extraction from behind reverse proxies
- haversine_distance(lat1, lon1, lat2, lon2) — great-circle distance in meters
- detect_work_mode(org_id, ip, latitude, longitude) — main detection logic
- check_anomalies(session) — anomaly flag checker
- geocode_address(address) — address → lat/lng via Nominatim (OSM)
"""

import math
import logging
import requests
from decimal import Decimal

logger = logging.getLogger(__name__)

# Earth's mean radius in meters
EARTH_RADIUS_M = 6_371_000


# ==============================================================================
# IP EXTRACTION
# ==============================================================================

import ipaddress
from django.conf import settings

def _is_ip_in_list(ip_str, trusted_list):
    if not ip_str or not trusted_list:
        return False
    try:
        ip = ipaddress.ip_address(ip_str)
        for net_str in trusted_list:
            net_str = net_str.strip()
            if '/' in net_str:
                net = ipaddress.ip_network(net_str, strict=False)
                if ip in net:
                    return True
            else:
                if ip_str == net_str:
                    return True
    except Exception:
        pass
    return False

def get_client_ip(request):
    """
    Extract the real client IP from the request, handling reverse proxies
    (Nginx, Cloudflare, Render, AWS ALB).

    Priority:
    1. CF-Connecting-IP (Cloudflare)
    2. X-Real-IP (Nginx)
    3. X-Forwarded-For (first non-private IP in the chain)
    4. REMOTE_ADDR (direct connection / fallback)
    """
    remote_addr = request.META.get('REMOTE_ADDR', '').strip()
    trusted_proxies = getattr(settings, 'TRUSTED_PROXY_IPS', [])

    # If trusted proxies list is defined, only trust forwarded headers if the REMOTE_ADDR is in that list.
    if trusted_proxies and not _is_ip_in_list(remote_addr, trusted_proxies):
        return remote_addr

    # Cloudflare
    cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
    if cf_ip:
        return cf_ip.strip()

    # Nginx X-Real-IP
    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip.strip()

    # X-Forwarded-For chain: "client, proxy1, proxy2"
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        # Take the first (leftmost) IP — that's the original client
        ips = [ip.strip() for ip in xff.split(',') if ip.strip()]
        if ips:
            return ips[0]

    # Direct connection
    return remote_addr


# ==============================================================================
# HAVERSINE DISTANCE
# ==============================================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on Earth
    using the Haversine formula.

    Args:
        lat1, lon1: Latitude/longitude of point 1 (degrees, Decimal or float)
        lat2, lon2: Latitude/longitude of point 2 (degrees, Decimal or float)

    Returns:
        Distance in meters (float).
    """
    lat1, lon1, lat2, lon2 = [
        math.radians(float(x)) for x in (lat1, lon1, lat2, lon2)
    ]

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c


# ==============================================================================
# WORK MODE DETECTION
# ==============================================================================

def detect_work_mode(org_id, ip, latitude=None, longitude=None):
    """
    Determine whether a login is WFO or WFH based on IP and GPS signals.

    Returns:
        dict with keys:
        - work_mode: 'wfo' | 'wfh' | 'unknown'
        - reason: human-readable explanation
        - ip_matched_office_id: int or None
        - gps_nearest_office_id: int or None
        - gps_distance_meters: float or None
    """
    from core.models import OfficeLocation, OfficeIP

    result = {
        'work_mode': 'unknown',
        'reason': '',
        'ip_matched_office_id': None,
        'gps_nearest_office_id': None,
        'gps_distance_meters': None,
    }

    offices = list(
        OfficeLocation.objects.filter(org_id=org_id, is_active=True)
        .prefetch_related('registered_ips')
    )

    if not offices:
        result['reason'] = 'no_offices_configured'
        return result

    # --- IP Matching ---
    ip_matched_office = None
    if ip:
        import ipaddress
        try:
            client_ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            client_ip_obj = None

        if client_ip_obj:
            for office in offices:
                matching_ips = []
                for oip in office.registered_ips.all():
                    if not oip.is_active:
                        continue
                    if oip.ip_cidr:
                        try:
                            net = ipaddress.ip_network(oip.ip_cidr, strict=False)
                            if client_ip_obj in net:
                                matching_ips.append(oip)
                        except ValueError:
                            pass
                    elif oip.ip_address:
                        try:
                            if ipaddress.ip_address(oip.ip_address) == client_ip_obj:
                                matching_ips.append(oip)
                        except ValueError:
                            pass

                if matching_ips:
                    ip_matched_office = office
                    break

    if ip_matched_office:
        result['ip_matched_office_id'] = ip_matched_office.id

    # --- GPS Distance Matching ---
    gps_nearest_office = None
    gps_min_distance = None

    if latitude is not None and longitude is not None:
        for office in offices:
            if office.latitude is None or office.longitude is None:
                continue
            dist = haversine_distance(latitude, longitude, office.latitude, office.longitude)
            if gps_min_distance is None or dist < gps_min_distance:
                gps_min_distance = dist
                gps_nearest_office = office

    if gps_nearest_office:
        result['gps_nearest_office_id'] = gps_nearest_office.id
        result['gps_distance_meters'] = round(gps_min_distance, 1)

    # --- Decision Logic ---
    gps_within_geofence = (
        gps_nearest_office is not None
        and gps_min_distance is not None
        and gps_min_distance <= gps_nearest_office.geofence_radius_meters
    )

    # Determine WFO based on dual signal requirements
    wfo_office = None
    wfo_reason = None

    for office in offices:
        is_ip_matched = (office == ip_matched_office)
        is_gps_matched = (gps_nearest_office == office and gps_within_geofence)

        if office.require_dual_signal:
            if is_ip_matched and is_gps_matched:
                wfo_office = office
                wfo_reason = 'ip_match_and_gps_within_geofence'
                break
        else:
            if is_ip_matched or is_gps_matched:
                wfo_office = office
                if is_ip_matched and is_gps_matched:
                    wfo_reason = 'ip_match_and_gps_within_geofence'
                elif is_ip_matched:
                    wfo_reason = 'ip_match'
                else:
                    wfo_reason = 'gps_within_geofence'
                break

    if wfo_office:
        result['work_mode'] = 'wfo'
        result['reason'] = wfo_reason
    else:
        result['work_mode'] = 'wfh'
        reasons = []
        if ip:
            if ip_matched_office:
                if ip_matched_office.require_dual_signal:
                    reasons.append('dual_signal_required')
                    if latitude is None:
                        reasons.append('gps_not_available')
                    elif gps_nearest_office != ip_matched_office:
                        reasons.append('gps_mismatch')
                    else:
                        reasons.append(f'gps_outside_geofence({int(gps_min_distance or 0)}m)')
            else:
                reasons.append('ip_no_match')
        else:
            reasons.append('ip_not_available')

        if not ip_matched_office:
            if latitude is not None and not gps_within_geofence:
                reasons.append(f'gps_outside_geofence({int(gps_min_distance or 0)}m)')
            if latitude is None:
                reasons.append('gps_not_available')

        result['reason'] = '+'.join(reasons) or 'no_match'

    return result


# ==============================================================================
# ANOMALY DETECTION (Phase 6)
# ==============================================================================

def check_anomalies(session):
    """
    Check an AttendanceSession for suspicious patterns.

    Returns:
        list of anomaly reason strings. Empty list = no anomalies.
    """
    # Exemption check
    from core.models import AttendanceSessionExemption
    exemptions = AttendanceSessionExemption.objects.filter(
        org_id=session.org_id,
        user=session.user,
        is_active=True
    )
    if exemptions.filter(exemption_type='all').exists():
        return []

    exempt_types = set(exemptions.values_list('exemption_type', flat=True))
    anomalies = []

    # 1. IP-GPS mismatch: IP says WFO but GPS distance is very large
    if 'ip_mismatch' not in exempt_types:
        if (
            session.ip_matched_office is not None
            and session.gps_distance_meters is not None
            and session.gps_nearest_office is not None
        ):
            geofence = session.gps_nearest_office.geofence_radius_meters or 200
            # Flag if GPS distance > 2x the geofence radius
            if session.gps_distance_meters > geofence * 2:
                anomalies.append(
                    f'ip_gps_mismatch: IP matched {session.ip_matched_office.name} '
                    f'but GPS is {int(session.gps_distance_meters)}m away'
                )

    # 2. Reverse: GPS says WFO but IP doesn't match any office
    if 'ip_mismatch' not in exempt_types:
        if (
            session.gps_distance_meters is not None
            and session.gps_nearest_office is not None
            and session.gps_distance_meters <= session.gps_nearest_office.geofence_radius_meters
            and session.ip_matched_office is None
            and session.login_ip  # has an IP to check
        ):
            anomalies.append(
                f'gps_ip_mismatch: GPS within {session.gps_nearest_office.name} '
                f'geofence but IP {session.login_ip} not registered'
            )

    # 3. Suspiciously exact/round GPS coordinates (common spoof tell)
    if 'gps_precision' not in exempt_types:
        if (
            session.login_latitude is not None
            and session.login_longitude is not None
        ):
            lat_f = float(session.login_latitude)
            lon_f = float(session.login_longitude)

            # Check if coordinates are suspiciously round (exactly N decimal places)
            lat_str = f"{lat_f:.7f}"
            lon_str = f"{lon_f:.7f}"

            # Exactly integer coordinates (e.g., 19.0000000, 72.0000000)
            if lat_f == int(lat_f) and lon_f == int(lon_f):
                anomalies.append('suspicious_gps: coordinates are exact integers')

            # Very few significant decimal digits (less than 3 non-zero decimals)
            def _significant_decimals(s):
                parts = s.split('.')
                if len(parts) < 2:
                    return 0
                return len(parts[1].rstrip('0'))

            if _significant_decimals(lat_str) <= 1 and _significant_decimals(lon_str) <= 1:
                anomalies.append('suspicious_gps: coordinates have very low precision')

    # 4. Very low GPS accuracy (> 500m means basically useless)
    if 'gps_precision' not in exempt_types:
        if (
            session.gps_accuracy_meters is not None
            and session.gps_accuracy_meters > 500
        ):
            anomalies.append(
                f'low_gps_accuracy: reported accuracy is {int(session.gps_accuracy_meters)}m'
            )

    # 5. Location jump: check for impossibly fast travel on same day
    if 'location_jump' not in exempt_types:
        if session.login_at and session.login_latitude is not None:
            from django.conf import settings
            from core.models import AttendanceSession as AS
            import pytz
            from django.utils import timezone as dj_tz

            local_date = session.login_at.date()
            earlier_sessions = AS.objects.filter(
                org_id=session.org_id,
                user=session.user,
                login_at__date=local_date,
                login_latitude__isnull=False,
                login_longitude__isnull=False,
            ).exclude(id=session.id).order_by('-login_at')[:1]

            # Configurable thresholds (fallback to 100km / 1hr)
            jump_km = getattr(settings, 'ATTENDANCE_LOCATION_JUMP_KM', 100)
            jump_time_secs = getattr(settings, 'ATTENDANCE_LOCATION_JUMP_TIME_SECONDS', 3600)
            threshold_dist_m = jump_km * 1000

            for prev in earlier_sessions:
                dist = haversine_distance(
                    session.login_latitude, session.login_longitude,
                    prev.login_latitude, prev.login_longitude,
                )
                time_diff = abs((session.login_at - prev.login_at).total_seconds())
                # If > threshold_dist_m apart with < jump_time_secs gap — impossible commute
                if dist > threshold_dist_m and time_diff < jump_time_secs:
                    anomalies.append(
                        f'location_jump: {int(dist / 1000)}km apart from previous '
                        f'session {int(time_diff / 60)}min ago'
                    )

    return anomalies


# ==============================================================================
# GEOCODING (Nominatim / OpenStreetMap)
# ==============================================================================

def geocode_address(address):
    """
    Convert a physical address to lat/lng coordinates using OpenStreetMap Nominatim.

    Returns:
        (latitude, longitude) as Decimal tuple, or (None, None) on failure.

    Note: Nominatim rate limit is 1 req/sec, max 1 per second.
    Only use for admin-triggered geocoding, never in hot paths.
    """
    if not address or not address.strip():
        return None, None

    import hashlib
    from django.core.cache import cache

    clean_addr = address.strip()
    addr_hash = hashlib.md5(clean_addr.encode('utf-8')).hexdigest()
    cache_key = f'geocode:{addr_hash}'

    cached_val = cache.get(cache_key)
    if cached_val is not None:
        lat_str, lon_str = cached_val
        if lat_str is None:
            return None, None
        return Decimal(lat_str), Decimal(lon_str)

    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params={
                'q': clean_addr,
                'format': 'json',
                'limit': 1,
                'addressdetails': 0,
            },
            headers={
                'User-Agent': 'BridgeWorksAttendance/1.0 (admin geocoding)',
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()

        if results and len(results) > 0:
            lat = Decimal(str(results[0]['lat']))
            lon = Decimal(str(results[0]['lon']))
            cache.set(cache_key, (str(lat), str(lon)), timeout=60*60*24*30)  # 30 days
            return lat, lon

        cache.set(cache_key, (None, None), timeout=60*60*24)  # 1 day for negative result
        logger.warning('[geocode] No results for address: %s', clean_addr[:100])
        return None, None

    except Exception as exc:
        logger.error('[geocode] Failed to geocode "%s": %s', clean_addr[:100], exc)
        return None, None
