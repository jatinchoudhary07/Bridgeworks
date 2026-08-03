"""
zone_engine.py — Shipping Zone & Cost Calculation Engine
=========================================================
Services:
  1. Zone Mapper: Classify destination pincodes into 7 zones relative to warehouse
  2. Cost Calculator: Auto-compute all ShipmentCost fields using rate cards
  3. Backfill Utility: Retroactively compute zones & costs for existing shipments
"""

import logging
import math
from decimal import Decimal

from core.models.delivery import (
    Shipment, ShipmentCost, Warehouse, CourierRateCard, CourierZoneMapping
)

logger = logging.getLogger(__name__)


# ==============================================================================
# PINCODE REGION MAPPING (India Post Structure)
# ==============================================================================

# 1st digit → postal macro-region
PINCODE_REGION = {
    '1': 'NORTH',    # Delhi, Haryana, Punjab, HP, J&K, Chandigarh, Ladakh
    '2': 'NORTH_UP', # UP, Uttarakhand
    '3': 'WEST_RG',  # Rajasthan, Gujarat, Daman & Diu, Dadra & Nagar Haveli
    '4': 'WEST_MH',  # Maharashtra, MP, Chhattisgarh, Goa
    '5': 'SOUTH_KA', # Karnataka, Telangana, AP
    '6': 'SOUTH_TN', # Tamil Nadu, Kerala, Puducherry, Lakshadweep
    '7': 'EAST_NE',  # WB, Odisha, NE States, Sikkim, Andaman & Nicobar
    '8': 'EAST_BJ',  # Bihar, Jharkhand
    '9': 'ARMY',     # Army Postal Service
}

# First 2 digits → State mapping (for "Within State" zone detection)
# Groups pincodes that belong to the same state
PINCODE_STATE_MAP = {
    # Delhi NCR
    '11': 'DL',
    # Haryana
    '12': 'HR', '13': 'HR',
    # Punjab
    '14': 'PB', '15': 'PB', '16': 'PB',
    # Himachal Pradesh
    '17': 'HP',
    # J&K / Ladakh
    '18': 'JK', '19': 'JK',
    # UP / Uttarakhand
    '20': 'UP', '21': 'UP', '22': 'UP', '23': 'UP',
    '24': 'UP', '25': 'UP', '26': 'UP', '27': 'UP', '28': 'UP',
    # Rajasthan
    '30': 'RJ', '31': 'RJ', '32': 'RJ', '33': 'RJ', '34': 'RJ',
    # Gujarat
    '36': 'GJ', '37': 'GJ', '38': 'GJ', '39': 'GJ',
    # Maharashtra / Goa
    '40': 'MH', '41': 'MH', '42': 'MH', '43': 'MH', '44': 'MH',
    # Madhya Pradesh
    '45': 'MP', '46': 'MP', '47': 'MP',
    # Chhattisgarh
    '49': 'CG',
    # AP / Telangana
    '50': 'TS', '51': 'AP', '52': 'AP', '53': 'AP',
    # Karnataka
    '56': 'KA', '57': 'KA', '58': 'KA', '59': 'KA',
    # Tamil Nadu
    '60': 'TN', '61': 'TN', '62': 'TN', '63': 'TN', '64': 'TN',
    # Kerala
    '67': 'KL', '68': 'KL', '69': 'KL',
    # West Bengal
    '70': 'WB', '71': 'WB', '72': 'WB', '73': 'WB', '74': 'WB',
    # Odisha
    '75': 'OD', '76': 'OD', '77': 'OD',
    # NE States (Assam, Meghalaya, etc.)
    '78': 'AS', '79': 'NE',
    # Bihar / Jharkhand
    '80': 'BR', '81': 'BR', '82': 'JH', '83': 'JH', '84': 'BR', '85': 'BR',
}

# Metro city prefixes (first 3 digits of major metro pincodes to avoid outer regions)
METRO_PREFIXES = {
    '110',  # Delhi
    '201',  # Noida / Ghaziabad
    '122',  # Gurgaon
    '121',  # Faridabad
    '400',  # Mumbai
    '411', '412',  # Pune (avoids 415/Satara/Karad or 416/Kolhapur)
    '560',  # Bangalore
    '600',  # Chennai
    '500',  # Hyderabad
    '700',  # Kolkata
    '380',  # Ahmedabad
    '302',  # Jaipur
}

# Special/Remote area prefixes — NE India, J&K, Ladakh, Islands
SPECIAL_PREFIXES = {
    '19',  # J&K / Ladakh (Leh, Kargil)
    '74',  # NE - Sikkim / North WB hills (Darjeeling etc.)
    '78',  # Assam
    '79',  # NE states (Manipur, Mizoram, Nagaland, Tripura, Arunachal, Meghalaya)
    '68',  # Lakshadweep (682xxx, 683xxx)
    '69',  # Kerala hills / remote
}

# Andaman & Nicobar — specifically 744xxx
ANDAMAN_PREFIX = '744'


# ==============================================================================
# ZONE DETERMINATION
# ==============================================================================

def get_zone(origin_pincode: str, destination_pincode: str, courier_partner: str = None) -> str:
    """
    Determine the shipping zone between two pincodes using India Post's
    hierarchical structure.

    Returns one of: Local, Intra-City, Within State, Regional, Metro, National, Special
    """
    origin = str(origin_pincode).strip()[:6]
    dest = str(destination_pincode).strip()[:6]

    if len(origin) < 3 or len(dest) < 3:
        return 'National'  # Fallback for invalid pincodes

    # --- Special / Remote check (highest priority) ---
    if dest[:2] in SPECIAL_PREFIXES or dest[:3] == ANDAMAN_PREFIX:
        return 'Special'

    # --- Local: Same district (first 3 digits) ---
    if origin[:3] == dest[:3]:
        return 'Local'

    # --- Intra-City: Same city/metro area (first 2 digits) ---
    if origin[:2] == dest[:2]:
        return 'Intra-City'

    # --- Within State: Same state (mapped from first 2 digits) ---
    origin_state = PINCODE_STATE_MAP.get(origin[:2])
    dest_state = PINCODE_STATE_MAP.get(dest[:2])
    if origin_state and dest_state and origin_state == dest_state:
        return 'Within State'

    # --- Metro-to-Metro: Both are metro area prefixes (first 3 digits) ---
    if origin[:3] in METRO_PREFIXES and dest[:3] in METRO_PREFIXES:
        if courier_partner == 'Bluedart':
            # Limit Metro to core metro prefixes for Bluedart
            if dest[:3] in {'110', '121', '122', '201', '400', '560', '600', '700'}:
                return 'Metro'
        else:
            return 'Metro'

    # --- Regional: Same postal macro-region (first 1 digit) ---
    origin_region = PINCODE_REGION.get(origin[0])
    dest_region = PINCODE_REGION.get(dest[0])
    if origin_region and dest_region and origin_region == dest_region:
        if courier_partner == 'Bluedart':
            # Cross-state regional check
            origin_state = PINCODE_STATE_MAP.get(origin[:2])
            dest_state = PINCODE_STATE_MAP.get(dest[:2])
            if origin_state and dest_state and origin_state != dest_state:
                return 'National'
        return 'Regional'

    # --- National: Everything else ---
    return 'National'


def get_mapped_zone(org_id: str, origin_pincode: str, destination_pincode: str, courier_partner: str = None) -> str:
    """
    Determine the shipping zone between two pincodes, taking into account courier-specific 
    pincode mappings (e.g. Bluedart) first, falling back to India Post hierarchical rules.
    """
    origin = str(origin_pincode).strip()[:6]
    dest = str(destination_pincode).strip()[:6]

    if courier_partner == 'Bluedart' and org_id:
        mapping = CourierZoneMapping.objects.filter(
            org_id=org_id,
            courier_partner='Bluedart',
            pincode=dest
        ).first()

        if mapping:
            zone_code = mapping.zone_code.upper()
            if zone_code == 'A':
                # Local: same first 3 digits
                if origin[:3] == dest[:3]:
                    return 'Local'
                # Intra-City: same first 2 digits
                if origin[:2] == dest[:2]:
                    return 'Intra-City'
                # For Bluedart, if not in core metros, fall back to National
                if dest[:3] not in {'110', '121', '122', '201', '400', '560', '600', '700'}:
                    return 'National'
                return 'Metro'
            elif zone_code == 'B':
                # Within State: same state
                origin_state = PINCODE_STATE_MAP.get(origin[:2])
                dest_state = PINCODE_STATE_MAP.get(dest[:2])
                if origin_state and dest_state and origin_state == dest_state:
                    return 'Within State'
                # For Bluedart, regional cross-state falls back to National
                return 'National'
            elif zone_code == 'C':
                return 'National'

    return get_zone(origin_pincode, destination_pincode, courier_partner)


# ==============================================================================
# COST CALCULATION ENGINE
# ==============================================================================

def _lookup_forward_cost(rate_card, zone, weight_kg):
    """
    Compute forward shipping cost from rate card slabs.
    Supports both SLAB and BASE_PLUS pricing modes.
    """
    weight = Decimal(str(weight_kg))

    if zone == 'Local' and not rate_card.slabs.filter(zone='Local').exists():
        zone = 'Intra-City'

    if rate_card.pricing_mode == 'SLAB':
        # Find the exact slab that covers this weight
        slab = rate_card.slabs.filter(
            zone=zone,
            weight_from_kg__lte=weight,
            weight_to_kg__gte=weight,
        ).order_by('weight_to_kg').first()
        if slab:
            return slab.rate

        # If no exact match, find the highest slab (for "and above" scenario)
        highest_slab = rate_card.slabs.filter(
            zone=zone,
        ).order_by('-weight_from_kg').first()
        if highest_slab:
            return highest_slab.rate

        return None

    elif rate_card.pricing_mode == 'BASE_PLUS':
        # Get base slab (lowest weight_from for this zone)
        base_slab = rate_card.slabs.filter(
            zone=zone,
        ).order_by('weight_from_kg').first()

        if not base_slab:
            return None

        base_rate = base_slab.rate
        base_weight = base_slab.weight_to_kg  # Base covers up to this weight

        if weight <= base_weight:
            return base_rate

        # Get additional per-increment rate
        additional_slab = rate_card.slabs.filter(
            zone=zone,
            weight_from_kg__gte=base_weight,
        ).order_by('weight_from_kg').first()

        if not additional_slab:
            return base_rate

        extra_weight = weight - base_weight
        increment = additional_slab.increment_kg or Decimal('0.50')
        # Round up to nearest increment
        num_increments = math.ceil(float(extra_weight / increment))
        additional_cost = Decimal(str(num_increments)) * additional_slab.rate

        return base_rate + additional_cost

    return None


def resolve_surcharges(rate_card, org_id, date_val):
    """
    Resolve effective Fuel Surcharge and CAF percentages for a rate card based on a given date.
    """
    if not rate_card:
        return Decimal('0'), Decimal('0')

    from datetime import date
    from core.models.delivery import CourierSurchargeHistory

    fsc_percent = rate_card.fuel_surcharge_percent
    caf_percent = rate_card.caf_percent

    if date_val:
        # Resolve target date as first of the month
        target_month_date = date(date_val.year, date_val.month, 1)
        
        global_surcharge = CourierSurchargeHistory.objects.filter(
            org_id=org_id,
            courier_partner__iexact=rate_card.courier_partner,
            month_date=target_month_date
        ).first()

        if not global_surcharge:
            global_surcharge = CourierSurchargeHistory.objects.filter(
                org_id=org_id,
                courier_partner__iexact=rate_card.courier_partner,
                month_date__lte=target_month_date
            ).order_by('-month_date').first()

        if global_surcharge:
            if rate_card.fuel_surcharge_mode == 'DYNAMIC_OFF_MECHANISM':
                fsc_percent = max(Decimal('0'), global_surcharge.fuel_surcharge_percent - rate_card.fuel_surcharge_offset)
            if rate_card.caf_mode == 'DYNAMIC_OFF_MECHANISM':
                caf_percent = max(Decimal('0'), global_surcharge.caf_percent - rate_card.caf_offset)

    return fsc_percent, caf_percent


def calculate_shipment_cost(shipment, warehouse=None, save=True):
    """
    Auto-calculate all cost fields for a shipment using:
      1. Warehouse pincode → zone mapping
      2. Rate card lookup → forward rate
      3. Apply RTO multiplier, COD charges, fuel surcharge

    Args:
        shipment: Shipment instance
        warehouse: Optional explicit Warehouse, otherwise uses shipment.warehouse or default
        save: Whether to save the ShipmentCost record

    Returns:
        ShipmentCost instance or None if missing config
    """
    # 1. Resolve warehouse
    if not warehouse:
        warehouse = shipment.warehouse
    if not warehouse:
        warehouse = Warehouse.objects.filter(
            org_id=shipment.org_id, is_default=True, is_active=True
        ).first()
    if not warehouse:
        # Try any active warehouse
        warehouse = Warehouse.objects.filter(
            org_id=shipment.org_id, is_active=True
        ).first()
    if not warehouse:
        return None  # No warehouse configured

    # 2. Get destination pincode from order
    dest_pincode = getattr(shipment.order, 'shipping_pincode', None)
    if not dest_pincode:
        return None

    # 3. Determine zone
    zone = get_mapped_zone(shipment.org_id, warehouse.pincode, dest_pincode, shipment.courier_partner)

    # 4. Find active rate card for this courier + mode
    rate_card = CourierRateCard.objects.filter(
        org_id=shipment.org_id,
        courier_partner=shipment.courier_partner,
        shipping_mode=shipment.shipping_mode,
        is_active=True,
    ).first()

    if not rate_card:
        # Try without shipping mode filter (any mode for this courier)
        rate_card = CourierRateCard.objects.filter(
            org_id=shipment.org_id,
            courier_partner=shipment.courier_partner,
            is_active=True,
        ).first()

    if not rate_card:
        # Still update zone even without rate card
        if shipment.zone != zone:
            shipment.zone = zone
            shipment.save(update_fields=['zone'])
        return None

    # 5. Calculate forward cost from rate slabs
    weight = shipment.weight_slab or Decimal('0.50')
    forward_cost = _lookup_forward_cost(rate_card, zone, weight)

    if forward_cost is None:
        # Try 'National' zone as fallback
        forward_cost = _lookup_forward_cost(rate_card, 'National', weight)
    if forward_cost is None:
        # Update zone at minimum
        if shipment.zone != zone:
            shipment.zone = zone
            shipment.save(update_fields=['zone'])
        return None

    # 6. Compute all cost components
    date_val = shipment.dispatch_date or shipment.created_at
    fsc_percent, caf_percent = resolve_surcharges(rate_card, shipment.org_id, date_val)

    fuel_fsc = forward_cost * (fsc_percent / Decimal('100'))
    fuel_caf = (forward_cost + fuel_fsc) * (caf_percent / Decimal('100'))
    efss = forward_cost * (rate_card.efss_surcharge_percent / Decimal('100'))

    # Sum all surcharges (FSC + CAF + EFSS) into the fuel container field
    fuel = fuel_fsc + fuel_caf + efss
    rto_cost = forward_cost * rate_card.rto_charge_multiplier

    cod_charges = Decimal('0')
    if shipment.payment_type in ['COD', 'Partially Paid']:
        order_val = Decimal(str(shipment.order.total_price or 0))
        cod_pct = order_val * (rate_card.cod_charge_percent / Decimal('100'))
        cod_charges = max(rate_card.cod_charge_flat, cod_pct)

    expected_cost = forward_cost + fuel + cod_charges

    # 7. Update Shipment zone + warehouse linkage
    update_fields = []
    if shipment.zone != zone:
        shipment.zone = zone
        update_fields.append('zone')
    if shipment.warehouse != warehouse:
        shipment.warehouse = warehouse
        update_fields.append('warehouse')
    if update_fields:
        shipment.save(update_fields=update_fields)

    # 8. Create/Update ShipmentCost
    cost, created = ShipmentCost.objects.get_or_create(shipment=shipment)

    # Only update auto-calculated fields if they haven't been manually set
    # (i.e., if forward_cost is still 0 or was auto-calculated)
    if cost.forward_cost == 0 or created:
        cost.forward_cost = forward_cost
    if cost.rto_cost == 0 or created:
        cost.rto_cost = rto_cost
    if cost.cod_charges == 0 or created:
        cost.cod_charges = cod_charges
    if cost.fuel_surcharge == 0 or created:
        cost.fuel_surcharge = fuel
    if cost.expected_cost == 0 or created:
        cost.expected_cost = expected_cost

    # NDR reattempt cost based on actual attempts
    if shipment.total_delivery_attempts > 1 and rate_card.ndr_reattempt_charge > 0:
        reattempts = max(0, shipment.total_delivery_attempts - 1)
        cost.ndr_reattempt_cost = rate_card.ndr_reattempt_charge * reattempts

    if save:
        cost.save()

        # Also calculate true cost
        from core.services.delivery_services import calculate_true_cost
        calculate_true_cost(cost)

    return cost


# ==============================================================================
# BACKFILL UTILITY
# ==============================================================================

def backfill_zones_and_costs(org_id, recalculate_all=False):
    """
    Retroactively compute zones and costs for existing shipments.

    Args:
        org_id: Organization ID to backfill
        recalculate_all: If True, recalculate even for shipments that already have costs

    Returns:
        dict with counts of processed, updated, skipped, errors
    """
    warehouse = Warehouse.objects.filter(
        org_id=org_id, is_default=True, is_active=True
    ).first()

    if not warehouse:
        warehouse = Warehouse.objects.filter(
            org_id=org_id, is_active=True
        ).first()

    if not warehouse:
        return {'error': 'No warehouse configured for this organization'}

    shipments = Shipment.objects.filter(
        org_id=org_id,
        order__shipping_pincode__isnull=False,
    ).select_related('order', 'cost', 'warehouse').exclude(
        order__shipping_pincode=''
    )

    if not recalculate_all:
        # Only process shipments without cost records
        shipments = shipments.filter(cost__isnull=True)

    stats = {'processed': 0, 'updated': 0, 'skipped': 0, 'errors': 0}

    for shipment in shipments.iterator(chunk_size=500):
        stats['processed'] += 1
        try:
            result = calculate_shipment_cost(shipment, warehouse=warehouse)
            if result:
                stats['updated'] += 1
            else:
                stats['skipped'] += 1
        except Exception as e:
            stats['errors'] += 1
            logger.warning(f"Error calculating cost for Shipment {shipment.awb_number}: {e}")

    return stats
