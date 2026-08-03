"""
fraud_detector.py
=================
Geodistance and scan timing anomaly auditor.
Flags impossible courier delivery attempts (fake delivery sheets).
"""

import logging
import math
from django.utils import timezone
from core.models import TrackingEvent, ShipmentException
from core.models.delivery import Shipment, CourierZoneMapping, NDRFraudFlag

logger = logging.getLogger(__name__)

# Static fallback coordinates for major Indian logistics hubs/cities
STATIC_COORDINATES = {
    "jaipur": (26.9124, 75.7873),
    "delhi": (28.6139, 77.2090),
    "mumbai": (18.9220, 72.8347),
    "bangalore": (12.9716, 77.5946),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
}


def calculate_geodistance(lat1, lon1, lat2, lon2) -> float:
    """Haversine formula to compute great-circle distance between two points in km."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return 0.0
    R = 6371.0
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def audit_shipment_attempts(shipment: Shipment):
    """
    Audits tracking events for a shipment to detect physically impossible attempts.
    Logs NDRFraudFlag and creates a ShipmentException (type FraudAlert) when flagged.
    """
    fulfillment = shipment.order.fulfillments.first()
    if not fulfillment:
        return []

    events = list(fulfillment.tracking_events.all().order_by('datetime'))
    if len(events) < 2:
        return []

    flags_created = []

    # Get coordinate data
    hub_lat, hub_lon = None, None
    pin_lat, pin_lon = None, None

    mapping = CourierZoneMapping.objects.filter(
        org_id=shipment.org_id,
        courier_partner=shipment.courier_partner,
        pincode=shipment.shipping_pincode
    ).first()

    if mapping:
        hub_lat, hub_lon = mapping.hub_latitude, mapping.hub_longitude
        pin_lat, pin_lon = mapping.pincode_latitude, mapping.pincode_longitude

    # Fallback to static values if not populated in mapping
    if hub_lat is None or hub_lon is None:
        hub_name = shipment.transit_hub or ""
        for city, coords in STATIC_COORDINATES.items():
            if city.lower() in hub_name.lower():
                hub_lat, hub_lon = coords
                break
        if hub_lat is None:
            # Absolute default to Delhi central hub coordinates
            hub_lat, hub_lon = STATIC_COORDINATES["delhi"]

    if pin_lat is None or pin_lon is None:
        pin = shipment.shipping_pincode or ""
        # Check static pincode mapping or default to some distance
        pin_lat, pin_lon = STATIC_COORDINATES.get(pin.lower(), (hub_lat + 0.15, hub_lon + 0.15))

    distance_km = calculate_geodistance(hub_lat, hub_lon, pin_lat, pin_lon)

    # Walk through sorted events to detect anomalies
    for i in range(1, len(events)):
        prev_evt = events[i-1]
        curr_evt = events[i]

        # 1. SCAN GAP: Out for Delivery to Failed Attempt time gap
        is_ofd = "out for delivery" in prev_evt.status.lower() or prev_evt.status == "OOD"
        is_failed = "undelivered" in curr_evt.status.lower() or "attempted" in curr_evt.status.lower() or curr_evt.status == "UND"

        if is_ofd and is_failed:
            time_gap_mins = (curr_evt.datetime - prev_evt.datetime).total_seconds() / 60.0
            
            # If distance is > 5km and time elapsed is < 15 minutes, it is physically impossible
            if distance_km > 5.0 and time_gap_mins < 15.0:
                flag_details = {
                    "reason": f"Shipment went from Out for Delivery to Undelivered in {time_gap_mins:.1f} mins.",
                    "distance_km": round(distance_km, 2),
                    "time_gap_mins": round(time_gap_mins, 2),
                    "hub": shipment.transit_hub or "Unknown Hub",
                    "pincode": shipment.shipping_pincode
                }
                
                # Log Fraud Flag
                flag, created = NDRFraudFlag.objects.get_or_create(
                    shipment=shipment,
                    flag_type='SCAN_GAP',
                    defaults={"details": flag_details}
                )
                
                if created:
                    flags_created.append(flag)
                    # Create exception
                    ShipmentException.objects.create(
                        org_id=shipment.org_id,
                        shipment=shipment,
                        exception_type='FraudAlert',
                        status='Open',
                        description=f"AI Alert: Fake attempt detected. {flag_details['reason']} Pincode {flag_details['pincode']} is {flag_details['distance_km']}km away from hub.",
                        is_auto_detected=True
                    )

        # 2. DUPLICATE ATTEMPT: Back-to-back failed attempts logged in minutes
        if is_failed and ("undelivered" in prev_evt.status.lower() or "attempted" in prev_evt.status.lower()):
            time_gap_mins = (curr_evt.datetime - prev_evt.datetime).total_seconds() / 60.0
            if time_gap_mins < 5.0:
                flag_details = {
                    "reason": f"Two delivery failure scans logged within {time_gap_mins:.1f} minutes of each other.",
                    "first_scan": prev_evt.status,
                    "second_scan": curr_evt.status,
                    "time_gap_mins": round(time_gap_mins, 2)
                }

                flag, created = NDRFraudFlag.objects.get_or_create(
                    shipment=shipment,
                    flag_type='DUPLICATE_ATTEMPT',
                    defaults={"details": flag_details}
                )

                if created:
                    flags_created.append(flag)
                    ShipmentException.objects.create(
                        org_id=shipment.org_id,
                        shipment=shipment,
                        exception_type='FraudAlert',
                        status='Open',
                        description=f"AI Alert: Duplicate failed scans logged at {curr_evt.datetime} (gap of {time_gap_mins:.1f} mins).",
                        is_auto_detected=True
                    )

    return flags_created
