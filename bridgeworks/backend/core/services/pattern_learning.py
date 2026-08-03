"""
pattern_learning.py — Billing Pattern Learning Engine
=======================================================
Stores and clusters billing patterns from processed invoices.
Learns recurring pricing buckets per city/pincode/zone/weight.

Design Principle:
    DO NOT hardcode: Bengaluru = 55.68
    Instead: learn clusters, infer pricing, classify patterns.

    The system becomes smarter with more invoices.

Confidence Score (0–100):
    Based on:
    - Formula match (exact/close/mismatch)
    - Historical similarity (seen this exact pattern before?)
    - Known cluster (belongs to a pricing bucket?)
    - Surcharge consistency (FS/CAF match expected percentages?)
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal('0.01')


class PatternLearningEngine:
    """
    Stores and queries billing patterns for a single organization.

    Usage:
        engine = PatternLearningEngine(org_id='abc123')

        # After reconciling a line:
        engine.store_pattern(line, breakdown)

        # To find matching historical patterns:
        patterns = engine.find_matching_patterns(city='Bengaluru', pincode='560001', weight=0.5)

        # To get billing clusters for the dashboard:
        clusters = engine.get_billing_clusters()

        # To compute confidence:
        score = engine.calculate_confidence_score(line, breakdown, pdf_diff, net_diff)
    """

    def __init__(self, org_id: str, courier_partner: str = 'Bluedart'):
        self.org_id = org_id
        self.courier_partner = courier_partner
        self._buffered_patterns = {}
        self._find_cache = {}

    def store_pattern(self, line, breakdown) -> None:
        """
        Buffer a billing pattern from a reconciled invoice line.
        Does not perform DB writes immediately. Call flush_patterns() to write.
        """
        city = (line.dest_area or '').strip()
        pincode = (line.dest_pincode or '').strip()

        if not pincode and not city:
            return  # Can't learn from lines with no location data

        zone = breakdown.zone if breakdown else ''
        weight_slab = breakdown.weight_slab_kg if breakdown else line.charged_weight_kg
        billed_amount = line.total_billed

        # Normalize Decimals for consistent hashing
        if weight_slab is not None:
            weight_slab = Decimal(str(weight_slab)).quantize(Decimal('0.01'))
        else:
            weight_slab = Decimal('0.50')

        if billed_amount is not None:
            billed_amount = Decimal(str(billed_amount)).quantize(Decimal('0.01'))
        else:
            billed_amount = Decimal('0.00')

        freight = breakdown.freight if breakdown else line.freight
        cod = breakdown.cod if breakdown else line.fod_charge
        efss = breakdown.efss if breakdown else Decimal('0')
        fs = breakdown.fs if breakdown else line.fsc
        caf = breakdown.caf if breakdown else line.caf

        # Normalize breakdown components to 2 decimal places
        freight = Decimal(str(freight or 0)).quantize(Decimal('0.01'))
        cod = Decimal(str(cod or 0)).quantize(Decimal('0.01'))
        efss = Decimal(str(efss or 0)).quantize(Decimal('0.01'))
        fs = Decimal(str(fs or 0)).quantize(Decimal('0.01'))
        caf = Decimal(str(caf or 0)).quantize(Decimal('0.01'))

        service_type = line.product_code or ''

        key = (pincode, zone, weight_slab, billed_amount)

        if key in self._buffered_patterns:
            self._buffered_patterns[key]['occurrence_count'] += 1
            if city and not self._buffered_patterns[key]['city']:
                self._buffered_patterns[key]['city'] = city
        else:
            self._buffered_patterns[key] = {
                'city': city,
                'freight': freight,
                'cod': cod,
                'efss': efss,
                'fs': fs,
                'caf': caf,
                'service_type': service_type,
                'occurrence_count': 1,
            }

    def flush_patterns(self) -> None:
        """
        Flush all buffered patterns to the database in bulk.
        """
        if not self._buffered_patterns:
            return

        from core.models.delivery import BillingPattern
        from django.db import transaction

        pincodes = {key[0] for key in self._buffered_patterns}
        
        # Query existing patterns for these pincodes to minimize database lookup
        existing_qs = BillingPattern.objects.filter(
            org_id=self.org_id,
            courier_partner=self.courier_partner,
            pincode__in=list(pincodes)
        )
        
        # Index existing records by key in-memory
        existing_map = {}
        for bp in existing_qs:
            bp_ws = Decimal(str(bp.weight_slab)).quantize(Decimal('0.01'))
            bp_ba = Decimal(str(bp.billed_amount)).quantize(Decimal('0.01'))
            key = (bp.pincode, bp.zone, bp_ws, bp_ba)
            existing_map[key] = bp

        to_create = []
        to_update = []

        for key, info in self._buffered_patterns.items():
            pincode, zone, weight_slab, billed_amount = key
            
            if key in existing_map:
                bp = existing_map[key]
                bp.occurrence_count += info['occurrence_count']
                if info['city'] and not bp.city:
                    bp.city = info['city']
                to_update.append(bp)
            else:
                bp = BillingPattern(
                    org_id=self.org_id,
                    courier_partner=self.courier_partner,
                    pincode=pincode,
                    zone=zone,
                    weight_slab=weight_slab,
                    billed_amount=billed_amount,
                    city=info['city'],
                    freight=info['freight'],
                    cod=info['cod'],
                    efss=info['efss'],
                    fs=info['fs'],
                    caf=info['caf'],
                    service_type=info['service_type'],
                    occurrence_count=info['occurrence_count']
                )
                to_create.append(bp)

        try:
            with transaction.atomic():
                if to_create:
                    BillingPattern.objects.bulk_create(to_create, batch_size=500)
                if to_update:
                    BillingPattern.objects.bulk_update(to_update, ['occurrence_count', 'city', 'updated_at'], batch_size=500)
            logger.info("Successfully flushed %d billing patterns (%d created, %d updated)", 
                        len(self._buffered_patterns), len(to_create), len(to_update))
        except Exception as e:
            logger.error("Failed to bulk flush billing patterns: %s", e)
        finally:
            self._buffered_patterns.clear()

    def find_matching_patterns(
        self, city: str = '', pincode: str = '',
        weight: Decimal = None, amount: Decimal = None,
        limit: int = 20,
    ) -> list:
        """
        Find historical billing patterns that match the given criteria with caching.
        """
        # Normalize decimals to strings for key serialization
        weight_str = str(weight) if weight is not None else None
        amount_str = str(amount) if amount is not None else None
        cache_key = (city, pincode, weight_str, amount_str, limit)
        
        if cache_key in self._find_cache:
            return self._find_cache[cache_key]

        from core.models.delivery import BillingPattern

        qs = BillingPattern.objects.filter(
            org_id=self.org_id,
            courier_partner=self.courier_partner,
        )

        if pincode:
            qs = qs.filter(pincode=pincode)
        elif city:
            qs = qs.filter(city__icontains=city)

        if weight is not None:
            qs = qs.filter(weight_slab=weight)

        if amount is not None:
            # Allow ±2 Rs tolerance
            qs = qs.filter(
                billed_amount__gte=amount - Decimal('2'),
                billed_amount__lte=amount + Decimal('2'),
            )

        results = list(qs.order_by('-occurrence_count')[:limit])
        self._find_cache[cache_key] = results
        return results

    def get_billing_clusters(self, city: str = None, zone: str = None) -> dict:
        """
        Group billing patterns into clusters for the dashboard.

        Returns:
            {
                'Bengaluru': {
                    'zone': 'Metro',
                    'amounts': [55.68, 63.03, 69.17, 81.36],
                    'total_occurrences': 342,
                    'patterns': [...]
                },
                ...
            }
        """
        from core.models.delivery import BillingPattern
        from django.db.models import Sum, Count

        qs = BillingPattern.objects.filter(
            org_id=self.org_id,
            courier_partner=self.courier_partner,
        )

        if city:
            qs = qs.filter(city__icontains=city)
        if zone:
            qs = qs.filter(zone=zone)

        # Group by city
        clusters = defaultdict(lambda: {
            'zone': '',
            'amounts': [],
            'total_occurrences': 0,
            'patterns': [],
        })

        for pattern in qs.order_by('city', '-occurrence_count')[:500]:
            key = pattern.city or pattern.pincode or 'Unknown'
            cluster = clusters[key]
            cluster['zone'] = pattern.zone or cluster['zone']
            cluster['total_occurrences'] += pattern.occurrence_count

            amt = float(pattern.billed_amount)
            if amt not in cluster['amounts']:
                cluster['amounts'].append(amt)

            cluster['patterns'].append({
                'pincode': pattern.pincode,
                'weight_slab': float(pattern.weight_slab),
                'billed_amount': float(pattern.billed_amount),
                'freight': float(pattern.freight),
                'cod': float(pattern.cod),
                'efss': float(pattern.efss),
                'fs': float(pattern.fs),
                'caf': float(pattern.caf),
                'occurrences': pattern.occurrence_count,
                'service_type': pattern.service_type,
            })

        # Sort amounts within each cluster
        for cluster in clusters.values():
            cluster['amounts'] = sorted(set(cluster['amounts']))

        return dict(clusters)

    def calculate_confidence_score(
        self, line, breakdown, pdf_diff: Decimal, net_diff: Decimal,
    ) -> int:
        """
        Compute a confidence score (0–100) for the reconciliation result.

        Scoring breakdown:
            Formula match:          0–40 points
            Historical similarity:  0–25 points
            Surcharge consistency:  0–20 points
            Weight match:          0–15 points
        """
        score = 0

        # ── 1. Formula match (0–40 pts) ──────────────────────────────────────
        abs_pdf = abs(pdf_diff)
        abs_net = abs(net_diff)

        if abs_net <= Decimal('0.50'):
            score += 40  # Exact match
        elif abs_net <= Decimal('2.00'):
            score += 32  # Minor rounding
        elif abs_net <= Decimal('5.00'):
            score += 20  # Close
        elif abs_net <= Decimal('15.00'):
            score += 10  # Approximate
        else:
            score += 0   # Big mismatch

        # ── 2. Historical similarity (0–25 pts) ──────────────────────────────
        matching_patterns = self.find_matching_patterns(
            pincode=line.dest_pincode or '',
            weight=line.charged_weight_kg,
            amount=line.total_billed,
            limit=5,
        )

        if matching_patterns:
            # Found exact matches in history
            total_occurrences = sum(p.occurrence_count for p in matching_patterns)
            if total_occurrences >= 10:
                score += 25
            elif total_occurrences >= 5:
                score += 20
            elif total_occurrences >= 2:
                score += 15
            else:
                score += 10
        else:
            # Check broader city-level patterns
            city_patterns = self.find_matching_patterns(
                city=line.dest_area or '',
                weight=line.charged_weight_kg,
                limit=5,
            )
            if city_patterns:
                score += 5

        # ── 3. Surcharge consistency (0–20 pts) ──────────────────────────────
        if breakdown and line.fsc > 0 and breakdown.freight > 0:
            # Check if billed FS% matches expected FS%
            billed_fs_pct = (line.fsc / breakdown.freight * 100)
            expected_fs_pct = breakdown.fs_percent
            fs_diff = abs(billed_fs_pct - expected_fs_pct)

            if fs_diff <= Decimal('1.0'):
                score += 10
            elif fs_diff <= Decimal('5.0'):
                score += 5

            # Check if billed CAF% matches expected CAF%
            if line.caf > 0:
                billed_caf_base = breakdown.freight + line.fsc
                if billed_caf_base > 0:
                    billed_caf_pct = (line.caf / billed_caf_base * 100)
                    expected_caf_pct = breakdown.caf_percent
                    caf_diff = abs(billed_caf_pct - expected_caf_pct)

                    if caf_diff <= Decimal('1.0'):
                        score += 10
                    elif caf_diff <= Decimal('5.0'):
                        score += 5

        elif breakdown is not None:
            # Line has no surcharges — that's consistent if breakdown also shows 0
            if breakdown.fs == 0 and breakdown.caf == 0:
                score += 20

        # ── 4. Weight match (0–15 pts) ───────────────────────────────────────
        expected_weight = Decimal('0.5')  # Business rule: all orders < 250g
        if line.charged_weight_kg <= expected_weight:
            score += 15
        elif line.charged_weight_kg <= Decimal('1.0'):
            score += 8
        else:
            score += 0  # Definite weight slab issue

        return min(score, 100)
