"""
billing_strategy.py — Courier Billing Strategy Pattern
========================================================
Abstract base and concrete implementations for courier-specific billing logic.

Architecture:
    CourierBillingStrategy (ABC)
        └── BluedartBillingStrategy
        └── (future) DelhiveryBillingStrategy
        └── (future) XpressbeesBillingStrategy

Two Billing Layers:
    PDF layer:   freight + cod + efss
    Excel layer: freight + cod + efss + fs + caf

The distinction matters because:
    - Invoice PDF AWB amount = freight + cod + efss
    - Excel NTOTAMOUNT       = freight + cod + efss + fs + caf
    These are DIFFERENT billing layers and must NOT be compared directly.
"""

from abc import ABC, abstractmethod
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, NamedTuple

import logging

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal('0.01')


class BillingBreakdown(NamedTuple):
    """Complete billing breakdown for a single AWB."""
    freight: Decimal
    cod: Decimal
    efss: Decimal
    fs: Decimal
    caf: Decimal
    pdf_amount: Decimal      # freight + cod + efss
    net_amount: Decimal      # freight + cod + efss + fs + caf
    fs_percent: Decimal
    caf_percent: Decimal
    efss_percent: Decimal
    zone: str
    weight_slab_kg: Decimal


# ==============================================================================
# ABSTRACT BASE
# ==============================================================================

class CourierBillingStrategy(ABC):
    """
    Abstract base for courier-specific billing logic.

    Each courier has its own:
        - surcharge formulas
        - COD calculation rules
        - base freight lookup methods
        - billing layer definitions

    Subclasses must implement all abstract methods.
    """

    @abstractmethod
    def calculate_base_freight(
        self, zone: str, weight_kg: Decimal,
        service_type: str, rate_card, slabs: list,
    ) -> Optional[Decimal]:
        """Look up the base freight from the rate card for the given zone/weight."""

    @abstractmethod
    def calculate_cod(
        self, invoice_value: Decimal, rate_card,
    ) -> Decimal:
        """Calculate COD charge. Returns 0 for prepaid shipments."""

    @abstractmethod
    def calculate_efss(self, freight: Decimal, efss_percent: Decimal) -> Decimal:
        """Calculate Elevated Freight Stability Surcharge."""

    @abstractmethod
    def calculate_fuel_surcharge(
        self, freight: Decimal, fs_percent: Decimal,
    ) -> Decimal:
        """Calculate Fuel Surcharge. Applied on base freight only."""

    @abstractmethod
    def calculate_caf(
        self, freight: Decimal, fs: Decimal, caf_percent: Decimal,
    ) -> Decimal:
        """Calculate Currency Adjustment Factor. Applied on (freight + fs)."""

    def calculate_pdf_amount(
        self, freight: Decimal, cod: Decimal, efss: Decimal,
    ) -> Decimal:
        """
        PDF operational amount = freight + cod + efss.
        This matches invoice PDF AWB rows.
        """
        return (freight + cod + efss).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    def calculate_net_amount(
        self, freight: Decimal, cod: Decimal, efss: Decimal,
        fs: Decimal, caf: Decimal,
    ) -> Decimal:
        """
        Excel net amount = freight + cod + efss + fs + caf.
        This matches Excel NTOTAMOUNT.
        """
        return (freight + cod + efss + fs + caf).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    @abstractmethod
    def compute_full_breakdown(
        self, *,
        zone: str,
        weight_kg: Decimal,
        service_type: str,
        is_cod: bool,
        invoice_value: Decimal,
        rate_card,
        slabs: list,
        fs_percent: Decimal,
        caf_percent: Decimal,
    ) -> Optional[BillingBreakdown]:
        """
        Compute the complete billing breakdown for an AWB.
        Returns None if rate card lookup fails.
        """


# ==============================================================================
# BLUEDART IMPLEMENTATION
# ==============================================================================

class BluedartBillingStrategy(CourierBillingStrategy):
    """
    Blue Dart billing strategy.

    Verified formulas (from actual invoice analysis):
        freight = rate_card[zone][weight_slab]
        cod     = max(flat, invoice_value × percent)
        efss    = freight × efss_percent
        fs      = freight × fs_percent                   ← applied on base freight ONLY
        caf     = (freight + fs) × caf_percent           ← applied on freight + fs
        pdf     = freight + cod + efss
        net     = freight + cod + efss + fs + caf
    """

    # ─── Business Constraint ────────────────────────────────────────────────
    EXPECTED_SLAB_KG = Decimal('0.5')

    # ─── Fallback rate-card lookup table (per 0.5 kg) ────────────────────────
    FALLBACK_RATES = {
        'Local':        Decimal('20'),
        'Intra-City':   Decimal('20'),
        'Within State': Decimal('20'),
        'Regional':     Decimal('24'),
        'Metro':        Decimal('24'),
        'National':     Decimal('28'),
        'Special':      Decimal('32'),
    }

    # ─── COD defaults ────────────────────────────────────────────────────────
    DEFAULT_COD_FLAT = Decimal('30.00')
    DEFAULT_COD_PERCENT = Decimal('1.5')  # 1.5%

    def calculate_base_freight(
        self, zone: str, weight_kg: Decimal,
        service_type: str, rate_card, slabs: list,
    ) -> Optional[Decimal]:
        """
        Look up base freight from rate card slabs.

        Priority:
            1. Pre-fetched slabs list (batch optimised)
            2. Rate card DB query
            3. Hardcoded fallback rates
        """
        target_weight = weight_kg if weight_kg > 0 else self.EXPECTED_SLAB_KG

        if zone == 'Local':
            has_local = any(s.zone == 'Local' for s in slabs) if slabs else False
            if not has_local and rate_card:
                has_local = rate_card.slabs.filter(zone='Local').exists()
            if not has_local:
                zone = 'Intra-City'

        # 1. Try pre-fetched slabs
        if slabs:
            rate = self._lookup_from_slabs(slabs, zone, target_weight)
            if rate is not None:
                return rate

        # 2. Try DB lookup via rate card
        if rate_card:
            from core.services.zone_engine import _lookup_forward_cost
            rate = _lookup_forward_cost(rate_card, zone, target_weight)
            if rate is not None:
                return rate

        # 3. Fallback
        return self.FALLBACK_RATES.get(zone)

    def _lookup_from_slabs(
        self, slabs: list, zone: str, weight_kg: Decimal,
    ) -> Optional[Decimal]:
        """Find rate from pre-fetched slab objects for a given zone and weight."""
        # Exact match
        for slab in slabs:
            if slab.zone == zone and slab.weight_from_kg <= weight_kg <= slab.weight_to_kg:
                return slab.rate
        # Fallback: 0.5kg slab
        for slab in slabs:
            if slab.zone == zone and slab.weight_from_kg == 0 and slab.weight_to_kg <= self.EXPECTED_SLAB_KG:
                return slab.rate
        return None

    def calculate_cod(
        self, invoice_value: Decimal, rate_card,
    ) -> Decimal:
        """
        COD = max(flat_fee, invoice_value × percent).

        Example: max(30, 1800 × 0.015) = max(30, 27) = 30
        """
        if rate_card:
            flat = rate_card.cod_charge_flat or self.DEFAULT_COD_FLAT
            pct = rate_card.cod_charge_percent or self.DEFAULT_COD_PERCENT
        else:
            flat = self.DEFAULT_COD_FLAT
            pct = self.DEFAULT_COD_PERCENT

        percent_amount = (invoice_value * pct / Decimal('100')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        return max(flat, percent_amount)

    def calculate_efss(self, freight: Decimal, efss_percent: Decimal) -> Decimal:
        """
        EFSS = freight × efss_percent / 100.

        Example: 28 × 7 / 100 = 1.96
        """
        if efss_percent <= 0:
            return Decimal('0')
        return (freight * efss_percent / Decimal('100')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    def calculate_fuel_surcharge(
        self, freight: Decimal, fs_percent: Decimal,
    ) -> Decimal:
        """
        Fuel Surcharge = freight × fs_percent / 100.
        Applied ONLY on base freight.

        Example: 28 × 56.8 / 100 = 15.90
        """
        if fs_percent <= 0:
            return Decimal('0')
        return (freight * fs_percent / Decimal('100')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    def calculate_caf(
        self, freight: Decimal, fs: Decimal, caf_percent: Decimal,
    ) -> Decimal:
        """
        CAF = (freight + fs) × caf_percent / 100.
        CAF is NOT calculated on freight alone — it includes the fuel surcharge.

        Example: (28 + 15.90) × 16.5 / 100 = 43.90 × 0.165 = 7.24
        """
        if caf_percent <= 0:
            return Decimal('0')
        base = freight + fs
        return (base * caf_percent / Decimal('100')).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    def compute_full_breakdown(
        self, *,
        zone: str,
        weight_kg: Decimal,
        service_type: str,
        is_cod: bool,
        invoice_value: Decimal,
        rate_card,
        slabs: list,
        fs_percent: Decimal,
        caf_percent: Decimal,
    ) -> Optional[BillingBreakdown]:
        """
        Compute the complete billing breakdown for a Blue Dart AWB.

        Returns BillingBreakdown or None if freight lookup fails.
        """
        freight = self.calculate_base_freight(zone, weight_kg, service_type, rate_card, slabs)
        if freight is None:
            return None

        efss_percent = Decimal('0')
        if rate_card and hasattr(rate_card, 'efss_surcharge_percent'):
            efss_percent = rate_card.efss_surcharge_percent

        cod = self.calculate_cod(invoice_value, rate_card) if is_cod else Decimal('0')
        efss = self.calculate_efss(freight, efss_percent)
        fs = self.calculate_fuel_surcharge(freight, fs_percent)
        caf = self.calculate_caf(freight, fs, caf_percent)

        pdf_amount = self.calculate_pdf_amount(freight, cod, efss)
        net_amount = self.calculate_net_amount(freight, cod, efss, fs, caf)

        return BillingBreakdown(
            freight=freight,
            cod=cod,
            efss=efss,
            fs=fs,
            caf=caf,
            pdf_amount=pdf_amount,
            net_amount=net_amount,
            fs_percent=fs_percent,
            caf_percent=caf_percent,
            efss_percent=efss_percent,
            zone=zone,
            weight_slab_kg=weight_kg,
        )


# ==============================================================================
# STRATEGY REGISTRY
# ==============================================================================

_STRATEGY_MAP = {
    'bluedart': BluedartBillingStrategy,
}


def get_billing_strategy(courier_partner: str) -> CourierBillingStrategy:
    """
    Factory function — return the correct strategy for the given courier.

    Args:
        courier_partner: e.g. 'Bluedart', 'Delhivery'

    Returns:
        Instantiated strategy object.

    Raises:
        NotImplementedError if no strategy exists for the courier.
    """
    key = courier_partner.strip().lower()
    cls = _STRATEGY_MAP.get(key)
    if cls is None:
        raise NotImplementedError(
            f"No billing strategy implemented for '{courier_partner}'. "
            f"Available: {list(_STRATEGY_MAP.keys())}"
        )
    return cls()
