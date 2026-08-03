"""
discrepancy_engine.py — Freight Billing Reconciliation Engine
==============================================================
Runs billing discrepancy analysis on CourierInvoiceLine records by:

1. Determining the correct zone (pincode-based, not city-only)
2. Looking up base freight from the rate card
3. Computing expected charges using the correct two-layer billing model:
     PDF layer:   freight + cod + efss
     Excel layer: freight + cod + efss + fs + caf
4. Comparing calculated vs billed amounts
5. Classifying anomalies with granular categories
6. Computing confidence scores based on formula match + historical patterns

CRITICAL BILLING FORMULAS (verified against Blue Dart invoices):
    freight = rate_card[zone][weight_slab]
    cod     = max(flat, invoice_value × percent)
    efss    = freight × efss_percent / 100
    fs      = freight × fs_percent / 100              ← on base freight ONLY
    caf     = (freight + fs) × caf_percent / 100      ← on freight + fs, NOT freight alone

    PDF amount = freight + cod + efss
    Net amount = freight + cod + efss + fs + caf

Discrepancy types (old → kept for backward compatibility):
    None, WrongSlab, WrongRate, WrongZone, UnexpectedRTO, UnexpectedFOD,
    CreditNote, NoMatch, Multiple

Anomaly categories (new — granular classification):
    exact_match, minor_rounding, surcharge_mismatch, weight_slab_mismatch,
    cod_mismatch, duplicate_charge, unknown_pricing
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Optional

from core.services.billing_strategy import (
    get_billing_strategy, BluedartBillingStrategy, BillingBreakdown,
)
from core.services.zone_engine import resolve_surcharges, get_zone, get_mapped_zone, PINCODE_STATE_MAP

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal('0.01')

# ─── Business Constraint ────────────────────────────────────────────────────
EXPECTED_SLAB_KG = Decimal('0.5')
RTO_VALID_STAGES = {'RTO', 'Lost'}


# ─── Anomaly Categories ─────────────────────────────────────────────────────

class AnomalyCategory(str, Enum):
    EXACT_MATCH = 'exact_match'
    MINOR_ROUNDING = 'minor_rounding'
    SURCHARGE_MISMATCH = 'surcharge_mismatch'
    WEIGHT_SLAB_MISMATCH = 'weight_slab_mismatch'
    COD_MISMATCH = 'cod_mismatch'
    DUPLICATE_CHARGE = 'duplicate_charge'
    UNKNOWN_PRICING = 'unknown_pricing'


# ─── Legacy helpers (kept for backward compatibility) ────────────────────────

# Bluedart rate-card lookup table (per 0.5 kg) — fallback only
RATE_CARD_RATES = {
    'Within State': Decimal('20'),
    'Intra-City':   Decimal('20'),
    'Metro':        Decimal('24'),
    'National':     Decimal('28'),
    'Special':      Decimal('32'),
}


def infer_zone_from_freight(freight: Decimal, charged_slab: Decimal) -> str:
    """
    Reverse-lookup zone from the per-0.5kg freight unit rate.

    Bluedart Surface rate card (from DB):
      Within State / Intra-City : Rs 20  per 0.5 kg
      Metro                     : Rs 24  per 0.5 kg
      National                  : Rs 28  per 0.5 kg
      Special                   : Rs 32  per 0.5 kg
    """
    if charged_slab <= 0:
        return 'National'
    per_unit = freight / (charged_slab / EXPECTED_SLAB_KG)
    per_unit = round(float(per_unit), 1)

    if per_unit <= 20.0:
        return 'Within State'
    elif per_unit <= 24.0:
        return 'Metro'
    elif per_unit <= 28.0:
        return 'National'
    else:
        return 'Special'


def get_correct_freight(org_id: str, zone: str, courier_partner: str = 'Bluedart') -> Optional[Decimal]:
    """Public API — look up rate from DB (used by simulation scripts)."""
    return _get_rate_from_db(org_id, zone, courier_partner)


def get_rto_multiplier(org_id: str, courier_partner: str = 'Bluedart') -> Decimal:
    """
    Look up the RTO charge multiplier from the active rate card.
    Returns Decimal('1.0') if no rate card found (i.e. RTO = same as forward).
    """
    try:
        from core.models.delivery import CourierRateCard
        card = CourierRateCard.objects.filter(
            org_id=org_id,
            courier_partner__icontains=courier_partner,
            is_active=True,
        ).first()
        return card.rto_charge_multiplier if card else Decimal('1.0')
    except Exception:
        return Decimal('1.0')


def _get_rate_from_db(org_id: str, zone: str, courier_partner: str = 'Bluedart') -> Optional[Decimal]:
    """Look up the 0.5 kg rate from the live rate card in the DB."""
    try:
        from core.models.delivery import CourierRateCard, RateSlab
        card = CourierRateCard.objects.filter(
            org_id=org_id,
            courier_partner__icontains=courier_partner,
            is_active=True,
        ).first()
        if not card:
            return None

        slab = RateSlab.objects.filter(
            rate_card=card,
            zone=zone,
            weight_from_kg=0,
            weight_to_kg__lte=EXPECTED_SLAB_KG,
        ).first()
        if slab:
            return slab.rate

        slab = RateSlab.objects.filter(
            rate_card=card,
            zone=zone,
            weight_from_kg__lte=EXPECTED_SLAB_KG,
            weight_to_kg__gte=EXPECTED_SLAB_KG,
        ).first()
        return slab.rate if slab else None

    except Exception as e:
        logger.warning("Rate card lookup failed for zone %s: %s", zone, e)
        return None


# ==============================================================================
# RECONCILIATION ENGINE
# ==============================================================================

class ReconciliationEngine:
    """
    Main reconciliation engine. Orchestrates:
        1. Zone resolution
        2. Billing breakdown computation (via CourierBillingStrategy)
        3. Two-layer comparison (PDF vs Excel)
        4. Anomaly classification
        5. Confidence scoring (via PatternLearningEngine)
    """

    def __init__(self, org_id: str, courier_partner: str = 'Bluedart'):
        self.org_id = org_id
        self.courier_partner = courier_partner
        self.strategy = get_billing_strategy(courier_partner)
        self._pattern_engine = None
        self.zone_mappings_dict = {}  # In-memory pre-fetched zone mappings
        self._surcharge_cache = {}    # In-memory cache for resolved surcharges

    @property
    def default_warehouse(self):
        """Lazy-init and cache the default warehouse."""
        if not hasattr(self, '_default_warehouse'):
            from core.models.delivery import Warehouse
            self._default_warehouse = Warehouse.objects.filter(
                org_id=self.org_id, is_default=True
            ).first()
        return self._default_warehouse

    @property
    def pattern_engine(self):
        """Lazy-init the pattern learning engine."""
        if self._pattern_engine is None:
            from core.services.pattern_learning import PatternLearningEngine
            self._pattern_engine = PatternLearningEngine(self.org_id, self.courier_partner)
        return self._pattern_engine

    def _is_decomposable(self, line) -> bool:
        """
        Check if a line's total_billed can be decomposed into individual components.
        Excel-parsed lines: total ≈ freight + fsc + caf + fod + idc + dv.
        PDF-parsed lines: total includes merged charges (EFSS, COD, forward+return).
        """
        if line.fsc == 0 and line.caf == 0:
            return False  # PDF lines have 0 row-level FSC and CAF
            
        return True

    def _resolve_zone(self, line, rate_card) -> str:
        """Resolve the shipping zone for an invoice line.
        
        IMPORTANT: For Return/RTO/Exchange shipments, the invoice's dest_pincode
        is the WAREHOUSE pincode (return destination), not the original customer.
        The zone must be based on the original customer pincode (order.shipping_pincode)
        because couriers charge the return leg at the same zone rate as the forward leg.
        """
        zone = None

        if line.shipment:
            warehouse = line.shipment.warehouse
            if not warehouse:
                warehouse = self.default_warehouse

            # For Return/RTO/Exchange: use order's shipping_pincode (customer),
            # NOT dest_pincode (which is the warehouse for return shipments).
            is_return_leg = line.shipment_type in ('RTO', 'Return', 'Exchange')
            if is_return_leg and line.shipment.order and line.shipment.order.shipping_pincode:
                dest_pincode = line.shipment.order.shipping_pincode
            else:
                dest_pincode = line.dest_pincode or (
                    line.shipment.order.shipping_pincode
                    if line.shipment.order else None
                )
            if warehouse and dest_pincode:
                # Use in-memory zone mapping dict if available to avoid N+1 DB lookups
                if self.courier_partner == 'Bluedart' and dest_pincode in self.zone_mappings_dict:
                    zone_code = self.zone_mappings_dict[dest_pincode].upper()
                    origin = str(warehouse.pincode).strip()[:6]
                    dest = str(dest_pincode).strip()[:6]
                    if zone_code == 'A':
                        if origin[:3] == dest[:3]:
                            zone = 'Local'
                        elif origin[:2] == dest[:2]:
                            zone = 'Intra-City'
                        elif dest[:3] not in {'110', '121', '122', '201', '400', '560', '600', '700'}:
                            zone = 'National'
                        else:
                            zone = 'Metro'
                    elif zone_code == 'B':
                        origin_state = PINCODE_STATE_MAP.get(origin[:2])
                        dest_state = PINCODE_STATE_MAP.get(dest[:2])
                        if origin_state and dest_state and origin_state == dest_state:
                            zone = 'Within State'
                        else:
                            zone = 'National'
                    elif zone_code == 'C':
                        zone = 'National'
                else:
                    zone = get_mapped_zone(
                        self.org_id, warehouse.pincode, dest_pincode,
                        line.freight_invoice.courier_partner,
                    )

        if not zone:
            zone = infer_zone_from_freight(line.freight, line.charged_weight_kg)

        return zone

    def _resolve_surcharge_percents(self, rate_card, invoice_date):
        """Resolve FS and CAF percentages for the invoice date with caching."""
        if not invoice_date:
            return Decimal('0'), Decimal('0')
            
        cache_key = (rate_card.id if rate_card else None, invoice_date)
        if cache_key in self._surcharge_cache:
            return self._surcharge_cache[cache_key]

        res = resolve_surcharges(rate_card, self.org_id, invoice_date)
        self._surcharge_cache[cache_key] = res
        return res

    def _is_cod_shipment(self, line) -> bool:
        """Determine if the shipment is COD."""
        return (
            line.shipment is not None
            and line.shipment.payment_type in ('COD', 'Partially Paid')
        )

    def _get_invoice_value(self, line) -> Decimal:
        """Get the order value for COD calculation."""
        if line.shipment and line.shipment.order:
            return Decimal(str(line.shipment.order.total_price or 0))
        return Decimal('0')

    # ─── Main Entry Points ───────────────────────────────────────────────────

    def analyse_line(self, line, rate_card=None, slabs=None) -> None:
        """
        Analyse a single CourierInvoiceLine for billing discrepancies.

        This is the main entry point for per-line analysis.
        Mutates the line object with computed expected amounts and flags.
        """
        flags = []
        notes_parts = []

        if rate_card is None:
            from core.models.delivery import CourierRateCard
            rate_card = CourierRateCard.objects.filter(
                org_id=self.org_id,
                courier_partner__icontains=self.courier_partner,
                is_active=True,
            ).first()

        # ── 1. Initialize Expected Weight ────────────────────────────────────
        line.expected_weight_kg = EXPECTED_SLAB_KG

        # ── 2. Handle Credit lines / Negative adjustments ────────────────────
        if line.total_billed < 0 or line.shipment_type == 'Credit':
            self._handle_credit_line(line)
            return

        # ── 3. Detect invoice format ─────────────────────────────────────────
        decomposable = self._is_decomposable(line)
        line.billing_layer = 'excel' if decomposable else 'pdf'

        # ── 4. Resolve Zone ──────────────────────────────────────────────────
        zone = self._resolve_zone(line, rate_card)

        # ── 5. Resolve Surcharge Percentages ─────────────────────────────────
        fs_percent, caf_percent = self._resolve_surcharge_percents(
            rate_card, line.freight_invoice.invoice_date,
        )

        # ── 6. Determine if COD ──────────────────────────────────────────────
        is_cod = self._is_cod_shipment(line)
        is_forward_cod = is_cod and line.shipment_type not in ('RTO', 'Return', 'Exchange')
        invoice_value = self._get_invoice_value(line) if is_cod else Decimal('0')

        # ── 7. Compute Full Billing Breakdown ────────────────────────────────
        breakdown = self.strategy.compute_full_breakdown(
            zone=zone,
            weight_kg=EXPECTED_SLAB_KG,
            service_type=line.product_code or '',
            is_cod=is_forward_cod,
            invoice_value=invoice_value,
            rate_card=rate_card,
            slabs=slabs or [],
            fs_percent=fs_percent,
            caf_percent=caf_percent,
        )

        if breakdown:
            # Set expected amounts
            line.expected_freight = breakdown.freight
            line.efss = breakdown.efss
            line.expected_pdf_amount = breakdown.pdf_amount
            line.expected_net_amount = breakdown.net_amount

            # Handle RTO/Return multipliers
            if line.shipment_type in ('RTO', 'Return', 'Exchange'):
                is_rvp = line.shipment_type in ('Return', 'Exchange')
                rto_mult = Decimal('1.0') if is_rvp else (rate_card.rto_charge_multiplier if rate_card else Decimal('1.0'))
                # For RTO, apply multiplier to the freight portion
                freight_portion = breakdown.freight if not decomposable else (breakdown.freight + breakdown.fs + breakdown.caf)
                adjusted_freight_portion = freight_portion * rto_mult

                # Add flat reverse pickup fee for returns/exchanges
                rvp_charge = Decimal('0')
                if is_rvp and rate_card:
                    rvp_charge = getattr(rate_card, 'reverse_pickup_charge', Decimal('0'))

                # RTO lines don't get COD but may get negative COD reversal
                rto_cod = Decimal('0')
                if is_cod:
                    rto_cod = -breakdown.cod if is_cod else Decimal('0')

                line.expected_total = (
                    adjusted_freight_portion
                    + breakdown.efss
                    + rto_cod
                    + rvp_charge
                    + line.idc_charge
                    + line.declared_value_charge
                ).quantize(TWO_PLACES)
                
                # Update the layer-specific expected amounts so diffs are correct
                if decomposable:
                    line.expected_net_amount = line.expected_total
                else:
                    line.expected_pdf_amount = line.expected_total
            else:
                line.expected_total = breakdown.pdf_amount if not decomposable else breakdown.net_amount

            # Also set expected_freight considering COD merged in some formats
            if is_forward_cod and not decomposable:
                # For PDF COD lines where COD is merged into freight
                line.expected_freight = breakdown.freight + breakdown.cod
        else:
            # Fallback: proportional scaling if overweight and no rate card matches
            if line.charged_weight_kg > EXPECTED_SLAB_KG:
                ratio = EXPECTED_SLAB_KG / line.charged_weight_kg
                line.expected_freight = (line.freight * ratio).quantize(TWO_PLACES)
                line.expected_total = (line.total_billed * ratio).quantize(TWO_PLACES)
            else:
                line.expected_total = line.total_billed
                line.expected_freight = line.freight

            # Still set the amounts even without breakdown
            line.expected_pdf_amount = line.expected_total
            line.expected_net_amount = line.expected_total

        # ── 8. Compute Differences ───────────────────────────────────────────
        pdf_diff = Decimal('0')
        net_diff = Decimal('0')

        if breakdown:
            if decomposable:
                net_diff = line.total_billed - line.expected_net_amount
            else:
                pdf_diff = line.total_billed - line.expected_pdf_amount

        # ── 9. Discrepancy Flag Audits ───────────────────────────────────────

        # Check AWB NoMatch
        if line.shipment is None:
            flags.append('NoMatch')
            notes_parts.append(f"AWB {line.awb_number} not found in system.")

        # Check WrongSlab
        if line.charged_weight_kg > EXPECTED_SLAB_KG:
            flags.append('WrongSlab')
            notes_parts.append(
                f"Charged {line.charged_weight_kg}kg slab (Should be {EXPECTED_SLAB_KG}kg)."
            )

        # Check WrongRate / Total Overcharge
        if breakdown is not None:
            active_diff = net_diff if decomposable else pdf_diff
            if abs(active_diff) > Decimal('1.50'):
                if line.charged_weight_kg <= EXPECTED_SLAB_KG:
                    flags.append('WrongRate')
                    layer_name = 'Excel' if decomposable else 'PDF'
                    expected_val = line.expected_net_amount if decomposable else line.expected_pdf_amount
                    notes_parts.append(
                        f"Billed total ₹{line.total_billed:.2f} vs expected ₹{expected_val:.2f} "
                        f"(diff ₹{active_diff:.2f}). [{layer_name} invoice]"
                    )

        # Check UnexpectedFOD (COD charges billed on a Prepaid order)
        if line.fod_charge > 0:
            is_prepaid = (
                line.shipment is not None
                and getattr(line.shipment, 'payment_type', None) == 'PrePaid'
            )
            is_return_leg = line.shipment_type in ('RTO', 'Return', 'Exchange')
            if is_prepaid or is_return_leg:
                flags.append('UnexpectedFOD')
                reason = "Prepaid order" if is_prepaid else f"{line.shipment_type} shipment"
                notes_parts.append(f"FOD charge ₹{line.fod_charge} on {reason}.")

        # Check UnexpectedRTO
        if line.shipment_type in ('RTO', 'Return') and line.shipment is not None:
            if line.shipment.current_stage not in RTO_VALID_STAGES:
                flags.append('UnexpectedRTO')
                notes_parts.append(
                    f"RTO billed but shipment stage is '{line.shipment.current_stage}'."
                )

        # ── 10. Classify Anomaly Category (new granular system) ──────────────
        anomaly_category = self._classify_anomaly(
            line, breakdown, pdf_diff, net_diff, decomposable, flags,
        )
        line.anomaly_category = anomaly_category

        # ── 11. Compute Confidence Score ─────────────────────────────────────
        line.confidence_score = self.pattern_engine.calculate_confidence_score(
            line, breakdown, pdf_diff, net_diff,
        )

        # ── 12. Store Pattern for Learning ───────────────────────────────────
        if breakdown and line.shipment is not None:
            try:
                self.pattern_engine.store_pattern(line, breakdown)
            except Exception as e:
                logger.debug("Pattern storage skipped: %s", e)

        # ── 13. Finalize Taxes & Flags ───────────────────────────────────────
        self._finalize_taxes_and_flags(line, flags, notes_parts)

    def _handle_credit_line(self, line):
        """Handle credit/negative adjustment lines."""
        line.discrepancy_type = 'CreditNote'
        line.anomaly_category = AnomalyCategory.EXACT_MATCH.value

        if line.shipment_type in ('RTO', 'Return', 'Exchange'):
            line.discrepancy_notes = f"Return adjustment of ₹{abs(line.total_billed):.2f}"
        else:
            line.discrepancy_notes = f"Credit adjustment of ₹{abs(line.total_billed):.2f}"

        line.expected_total = Decimal('0')
        line.expected_freight = Decimal('0')
        line.expected_pdf_amount = Decimal('0')
        line.expected_net_amount = Decimal('0')
        line.overcharge_amount = Decimal('0')
        line.confidence_score = 90
        line.billing_layer = 'credit'

        line.tax_cgst = (line.total_billed * Decimal('0.09')).quantize(TWO_PLACES)
        line.tax_sgst = (line.total_billed * Decimal('0.09')).quantize(TWO_PLACES)
        line.total_billed_with_tax = line.total_billed + line.tax_cgst + line.tax_sgst

        line.expected_tax_cgst = Decimal('0')
        line.expected_tax_sgst = Decimal('0')
        line.expected_total_with_tax = Decimal('0')

    def _classify_anomaly(
        self, line, breakdown, pdf_diff, net_diff,
        decomposable, flags,
    ) -> str:
        """
        Classify the anomaly with granular categories.

        Categories:
            exact_match:          abs(diff) <= 0.5
            minor_rounding:       0.5 < diff <= 2
            surcharge_mismatch:   FS/CAF issue detected
            weight_slab_mismatch: diff approximates next weight slab
            cod_mismatch:         COD calculation difference
            duplicate_charge:     same surcharge appears twice
            unknown_pricing:      no known formula fits
        """
        if not breakdown:
            return AnomalyCategory.UNKNOWN_PRICING.value

        active_diff = net_diff if decomposable else pdf_diff
        abs_diff = abs(active_diff)

        # Exact match
        if abs_diff <= Decimal('0.50'):
            return AnomalyCategory.EXACT_MATCH.value

        # Minor rounding
        if abs_diff <= Decimal('2.00'):
            return AnomalyCategory.MINOR_ROUNDING.value

        # Weight slab mismatch: check if the difference approximates
        # an additional weight slab charge
        if 'WrongSlab' in flags or line.charged_weight_kg > EXPECTED_SLAB_KG:
            return AnomalyCategory.WEIGHT_SLAB_MISMATCH.value

        # Surcharge mismatch: check if FS or CAF are off
        if decomposable and breakdown.freight > 0:
            # Check FS consistency
            if line.fsc > 0:
                expected_fs = breakdown.fs
                fs_diff = abs(line.fsc - expected_fs)
                if fs_diff > Decimal('1.00'):
                    return AnomalyCategory.SURCHARGE_MISMATCH.value

            # Check CAF consistency
            if line.caf > 0:
                expected_caf = breakdown.caf
                caf_diff = abs(line.caf - expected_caf)
                if caf_diff > Decimal('1.00'):
                    return AnomalyCategory.SURCHARGE_MISMATCH.value

        # COD mismatch: check if COD is the source of difference
        if line.fod_charge > 0 and breakdown.cod > 0:
            cod_diff = abs(line.fod_charge - breakdown.cod)
            if cod_diff > Decimal('1.00'):
                return AnomalyCategory.COD_MISMATCH.value

        # Duplicate charge detection: check if any surcharge component is doubled
        if decomposable and breakdown.freight > 0:
            if line.fsc > 0 and line.caf > 0:
                # Check if FS ≈ 2× expected (indicating double charge)
                if abs(line.fsc - 2 * breakdown.fs) < Decimal('1.00'):
                    return AnomalyCategory.DUPLICATE_CHARGE.value
                if abs(line.caf - 2 * breakdown.caf) < Decimal('1.00'):
                    return AnomalyCategory.DUPLICATE_CHARGE.value

        # Unknown pricing: none of the above patterns matched
        return AnomalyCategory.UNKNOWN_PRICING.value

    def _finalize_taxes_and_flags(self, line, flags, notes_parts):
        """Apply taxes and set final discrepancy type/notes."""
        # Taxes (18% GST = 9% CGST + 9% SGST)
        line.tax_cgst = (line.total_billed * Decimal('0.09')).quantize(TWO_PLACES)
        line.tax_sgst = (line.total_billed * Decimal('0.09')).quantize(TWO_PLACES)
        line.total_billed_with_tax = line.total_billed + line.tax_cgst + line.tax_sgst

        if line.expected_total is None:
            line.expected_total = line.total_billed

        line.expected_tax_cgst = (line.expected_total * Decimal('0.09')).quantize(TWO_PLACES)
        line.expected_tax_sgst = (line.expected_total * Decimal('0.09')).quantize(TWO_PLACES)
        line.expected_total_with_tax = (
            line.expected_total + line.expected_tax_cgst + line.expected_tax_sgst
        )

        if line.expected_total is not None:
            # Calculate overcharge using tax-exclusive totals (excluding GST)
            line.overcharge_amount = max(
                (line.total_billed - line.expected_total).quantize(TWO_PLACES),
                Decimal('0')
            )
        else:
            line.overcharge_amount = Decimal('0')

        if not flags:
            line.discrepancy_type = 'None'
            line.discrepancy_notes = ''
        elif len(flags) == 1:
            line.discrepancy_type = flags[0]
            line.discrepancy_notes = ' | '.join(notes_parts)
        else:
            line.discrepancy_type = 'Multiple'
            line.discrepancy_notes = ' | '.join(notes_parts)


# ==============================================================================
# BATCH RUNNER
# ==============================================================================

def analyse_invoice(invoice_id: int, org_id: str) -> dict:
    """
    Run discrepancy analysis on all lines of a FreightInvoice.

    This is the main entry point called by the upload pipeline.
    """
    from core.models.delivery import CourierInvoiceLine, CourierRateCard, RateSlab, ShipmentCost
    from django.db import transaction
    from django.db.models import Sum, Q

    # 1. Pre-fetch Rate Card Data
    rate_card = CourierRateCard.objects.filter(
        org_id=org_id,
        courier_partner__icontains='Bluedart',
        is_active=True
    ).first()
    slabs = list(RateSlab.objects.filter(rate_card=rate_card)) if rate_card else []

    lines = CourierInvoiceLine.objects.filter(
        freight_invoice_id=invoice_id,
        org_id=org_id,
    ).select_related('shipment', 'shipment__order', 'shipment__warehouse', 'freight_invoice')

    # Determine courier partner from invoice
    try:
        from core.models.delivery import FreightInvoice
        invoice = FreightInvoice.objects.get(id=invoice_id)
        courier_partner = invoice.courier_partner or 'Bluedart'
    except Exception:
        courier_partner = 'Bluedart'

    # Initialize the reconciliation engine
    engine = ReconciliationEngine(org_id, courier_partner)

    stats = {
        'total': 0,
        'no_discrepancy': 0,
        'wrong_slab': 0,
        'wrong_rate': 0,
        'unexpected_fod': 0,
        'unexpected_rto': 0,
        'no_match': 0,
        'credit_note': 0,
        'multiple': 0,
        'total_overcharge': Decimal('0'),
        # New stats
        'exact_match': 0,
        'minor_rounding': 0,
        'surcharge_mismatch': 0,
        'weight_slab_mismatch': 0,
        'cod_mismatch': 0,
        'duplicate_charge': 0,
        'unknown_pricing': 0,
        'avg_confidence': 0,
    }

    line_list = list(lines)
    
    # Pre-fetch zone mappings to avoid N+1 database queries
    from core.models.delivery import CourierZoneMapping
    pincodes = {line.dest_pincode for line in line_list if line.dest_pincode}
    zone_mappings = CourierZoneMapping.objects.filter(
        org_id=org_id,
        courier_partner='Bluedart',
        pincode__in=list(pincodes)
    )
    engine.zone_mappings_dict = {zm.pincode: zm.zone_code for zm in zone_mappings}

    confidence_sum = 0

    # Perform analysis in memory
    for line in line_list:
        engine.analyse_line(line, rate_card=rate_card, slabs=slabs)

        stats['total'] += 1
        dt = line.discrepancy_type
        if dt == 'None':
            stats['no_discrepancy'] += 1
        elif dt == 'WrongSlab':
            stats['wrong_slab'] += 1
        elif dt == 'WrongRate':
            stats['wrong_rate'] += 1
        elif dt == 'UnexpectedFOD':
            stats['unexpected_fod'] += 1
        elif dt == 'UnexpectedRTO':
            stats['unexpected_rto'] += 1
        elif dt == 'NoMatch':
            stats['no_match'] += 1
        elif dt == 'CreditNote':
            stats['credit_note'] += 1
        elif dt == 'Multiple':
            stats['multiple'] += 1

        stats['total_overcharge'] += line.overcharge_amount

        # Anomaly category stats
        ac = line.anomaly_category or ''
        if ac in stats:
            stats[ac] += 1

        confidence_sum += (line.confidence_score or 0)

    # Perform bulk update on all reconciled lines
    fields_to_update = [
        'expected_weight_kg', 'expected_freight', 'expected_total',
        'expected_tax_cgst', 'expected_tax_sgst', 'expected_total_with_tax',
        'tax_cgst', 'tax_sgst', 'total_billed_with_tax',
        'overcharge_amount', 'discrepancy_type', 'discrepancy_notes',
        'efss', 'billing_layer',
        'expected_pdf_amount', 'expected_net_amount',
        'confidence_score', 'anomaly_category',
    ]
    with transaction.atomic():
        CourierInvoiceLine.objects.bulk_update(line_list, fields_to_update, batch_size=200)

    # Flush all buffered patterns to the database
    if engine.pattern_engine:
        engine.pattern_engine.flush_patterns()

    # Compute average confidence
    if stats['total'] > 0:
        stats['avg_confidence'] = round(confidence_sum / stats['total'])

    # ─── Sync aggregated costs to ShipmentCost ──────────────────────────────
    shipment_ids = [line.shipment_id for line in line_list if line.shipment_id]
    shipment_ids = list(set(shipment_ids))

    all_lines_summary = CourierInvoiceLine.objects.filter(
        shipment_id__in=shipment_ids,
        org_id=org_id
    ).values('shipment_id').annotate(
        total_overall=Sum('total_billed'),
        total_fsc=Sum('fsc'),
        total_caf=Sum('caf'),
        total_fod=Sum('fod_charge'),
        total_expected=Sum('expected_total'),
        total_forward=Sum('total_billed', filter=Q(shipment_type='Forward')),
        total_rto=Sum('total_billed', filter=Q(shipment_type__in=['Return', 'Exchange']))
    )

    if all_lines_summary:
        existing_costs = {
            sc.shipment_id: sc 
            for sc in ShipmentCost.objects.filter(shipment_id__in=shipment_ids)
        }
        
        to_create_costs = []
        to_update_costs = []
        
        for summary in all_lines_summary:
            sid = summary['shipment_id']
            if not sid:
                continue
                
            cost_record = existing_costs.get(sid)
            is_new = False
            if not cost_record:
                cost_record = ShipmentCost(shipment_id=sid)
                is_new = True
                
            cost_record.actual_billed_cost = summary['total_overall'] or Decimal('0')
            if summary['total_expected']:
                cost_record.expected_cost = summary['total_expected']
            if summary['total_forward']:
                cost_record.forward_cost = summary['total_forward']
            if summary['total_rto']:
                cost_record.rto_cost = summary['total_rto']
            if summary['total_fsc'] or summary['total_caf']:
                cost_record.fuel_surcharge = (summary['total_fsc'] or 0) + (summary['total_caf'] or 0)
            if summary['total_fod']:
                cost_record.cod_charges = summary['total_fod']
                
            # Compute overbilling fields manually
            if cost_record.actual_billed_cost > 0 and cost_record.expected_cost > 0:
                diff = cost_record.actual_billed_cost - cost_record.expected_cost
                cost_record.is_overbilled = diff > 0
                cost_record.overbilling_amount = max(diff, 0)
            else:
                cost_record.is_overbilled = False
                cost_record.overbilling_amount = Decimal('0')
                
            if is_new:
                to_create_costs.append(cost_record)
            else:
                to_update_costs.append(cost_record)
                
        with transaction.atomic():
            if to_create_costs:
                ShipmentCost.objects.bulk_create(to_create_costs, batch_size=200)
            if to_update_costs:
                ShipmentCost.objects.bulk_update(
                    to_update_costs,
                    [
                        'actual_billed_cost', 'expected_cost', 'forward_cost', 'rto_cost',
                        'fuel_surcharge', 'cod_charges', 'is_overbilled', 'overbilling_amount'
                    ],
                    batch_size=200
                )

    stats['total_overcharge'] = str(stats['total_overcharge'].quantize(TWO_PLACES))
    logger.info("Reconciliation analysis complete for invoice %d: %s", invoice_id, stats)
    return stats


# ==============================================================================
# BACKWARD-COMPATIBLE analyse_line (for external callers)
# ==============================================================================

def analyse_line(line, org_id: str, rate_card=None, slabs=None) -> None:
    """
    Backward-compatible wrapper around ReconciliationEngine.analyse_line().

    Callers that imported `analyse_line` directly will continue to work.
    """
    courier_partner = 'Bluedart'
    if hasattr(line, 'freight_invoice') and line.freight_invoice:
        courier_partner = line.freight_invoice.courier_partner or 'Bluedart'

    engine = ReconciliationEngine(org_id, courier_partner)
    engine.analyse_line(line, rate_card=rate_card, slabs=slabs)
