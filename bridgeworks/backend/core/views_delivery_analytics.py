"""
views_delivery_analytics.py — Delivery Dashboard API
=====================================================
Single endpoint returning:
  - 8 KPI metrics + 3 cost analytics metrics
  - Table 1: Shipping Performance
  - Table 2: Delivery Attempt Effectiveness
  - Table 3: Delivery Speed (Day 1-7+)
  - Table 4: NDR Breakdown
  - Table 5: Geographic & Reason Performance
  - Table 6: Shipping Cost Breakdown

ALL tables are grouped by Courier Company × Order Type (COD/Partially Paid/PrePaid).
"""

import logging
import csv
from datetime import timedelta, datetime
from decimal import Decimal

from django.db.models import (
    Count, Sum, Avg, Q, F, Case, When, Value,
    DecimalField, IntegerField, CharField, FloatField,
    ExpressionWrapper, DurationField
)
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.http import HttpResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.models import Order, Fulfillment, TrackingInfo, TrackingEvent
from core.models.delivery import (
    Shipment, ShipmentCost, CODRemittance, FreightInvoice, ShipmentDispute
)
from core.models.constants import NDR_STATUSES, RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES
from core.permissions import HasModulePermission
from core.services.delivery_services import (
    check_cod_remittances, reconcile_orders, get_ndr_analytics, check_freight_invoices
)

logger = logging.getLogger(__name__)


# ==============================================================================
# HELPERS
# ==============================================================================

def _get_org_id(request):
    """Extract org_id from the current user's shop or team settings."""
    user = request.user
    if hasattr(user, 'shop_credentials'):
        return user.shop_credentials.organization_id
    if hasattr(user, 'team_settings') and user.team_settings and user.team_settings.organization:
        return user.team_settings.organization.organization_id
    return None


def _parse_dates(request):
    """Parse start_date and end_date from query params."""
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    start = request.query_params.get('start_date')
    end = request.query_params.get('end_date')
    
    def parse_any_date(date_str):
        if not date_str:
            return None
        # Try standard YYYY-MM-DD
        from django.utils.dateparse import parse_date
        parsed = parse_date(date_str)
        if parsed:
            return parsed
        # Try frontend format DD-MM-YYYY
        try:
            return datetime.strptime(date_str, '%d-%m-%Y').date()
        except ValueError:
            return None

    start_date = parse_any_date(start) if start else (timezone.now() - timedelta(days=30)).date()
    end_date = parse_any_date(end) if end else timezone.now().date()
    return start_date, end_date


def _build_grouped_data(queryset, extra_annotations=None):
    """
    Generic grouping by courier_partner × payment_type with Total rows.
    Returns dict: { courier: { payment_type: { ...metrics }, "Total": { ... } }, "Total": { ... } }
    """
    if extra_annotations is None:
        extra_annotations = {}

    base_annotations = {
        'qty': Count('id'),
        'amount': Coalesce(Sum('order__total_price'), Value(0), output_field=DecimalField()),
    }
    base_annotations.update(extra_annotations)

    rows = queryset.values(
        'courier_partner', 'payment_type'
    ).annotate(**base_annotations).order_by('courier_partner', 'payment_type')

    result = {}
    grand_total = {}

    for row in rows:
        courier = row['courier_partner']
        ptype = row['payment_type']

        if courier not in result:
            result[courier] = {}

        # Store per-payment-type
        row_data = {k: _safe_val(row[k]) for k in base_annotations.keys()}
        row_data['aov'] = round(row_data['amount'] / row_data['qty'], 2) if row_data['qty'] > 0 else 0
        result[courier][ptype] = row_data

        # Accumulate courier total
        if 'Total' not in result[courier]:
            result[courier]['Total'] = {k: 0 for k in row_data.keys()}
        for k, v in row_data.items():
            if k != 'aov':
                result[courier]['Total'][k] += v

        # Accumulate grand total per payment type
        if ptype not in grand_total:
            grand_total[ptype] = {k: 0 for k in row_data.keys()}
        for k, v in row_data.items():
            if k != 'aov':
                grand_total[ptype][k] += v

        # Accumulate grand total overall
        if 'Total' not in grand_total:
            grand_total['Total'] = {k: 0 for k in row_data.keys()}
        for k, v in row_data.items():
            if k != 'aov':
                grand_total['Total'][k] += v

    # Recalculate AOVs for totals
    for courier in result:
        t = result[courier].get('Total', {})
        if t.get('qty', 0) > 0:
            t['aov'] = round(t['amount'] / t['qty'], 2)

    for ptype in grand_total:
        t = grand_total[ptype]
        if t.get('qty', 0) > 0:
            t['aov'] = round(t['amount'] / t['qty'], 2)

    result['Total'] = grand_total
    return result


def _safe_val(v):
    """Convert Decimal/None to float/0."""
    if v is None:
        return 0
    if isinstance(v, Decimal):
        return float(v)
    return v


# ==============================================================================
# MAIN DASHBOARD VIEW
# ==============================================================================

class DeliveryDashboardView(APIView):
    """
    GET /api/delivery/dashboard/
    Query params: start_date, end_date, courier (optional)

    Returns complete delivery analytics dashboard data:
    - KPIs, Cost Analytics
    - Tables 1-6 (all courier × payment_type grouped)
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:delivery_analytics:view'
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        start_date, end_date = _parse_dates(request)
        courier_filter = request.query_params.get('courier', '')

        # Base shipment queryset
        base_qs = Shipment.objects.filter(
            org_id=org_id,
            dispatch_date__date__gte=start_date,
            dispatch_date__date__lte=end_date,
        ).select_related('order', 'cost')

        if courier_filter:
            base_qs = base_qs.filter(courier_partner=courier_filter)

        # ====================================================================
        # KPI SECTION
        # ====================================================================
        kpis = self._compute_kpis(base_qs, org_id)
        cost_analytics = self._compute_cost_analytics(base_qs)

        # ====================================================================
        # TABLE 1: Shipping Performance
        # ====================================================================
        total_shipped = base_qs.count() or 1  # avoid div/0

        table1 = _build_grouped_data(
            base_qs,
            extra_annotations={
                'delivered_qty': Count('id', filter=Q(current_stage='Delivered')),
                'rto_qty': Count('id', filter=Q(current_stage='RTO')),
                'ndr_qty': Count('id', filter=Q(order__is_ndr=True)),
            }
        )
        # Add percentages and load_share to each cell
        for courier, ptypes in table1.items():
            for ptype, data in ptypes.items():
                if isinstance(data, dict) and 'qty' in data:
                    qty = data['qty']
                    data['delivery_pct'] = round((data.get('delivered_qty', 0) / qty) * 100, 1) if qty > 0 else 0
                    data['rto_pct'] = round((data.get('rto_qty', 0) / qty) * 100, 1) if qty > 0 else 0
                    data['ndr_pct'] = round((data.get('ndr_qty', 0) / qty) * 100, 1) if qty > 0 else 0
                    data['load_share'] = round((qty / total_shipped) * 100, 1)

        # ====================================================================
        # TABLE 2: Delivery Attempt Effectiveness
        # ====================================================================
        table2 = _build_grouped_data(
            base_qs.filter(current_stage='Delivered'),
            extra_annotations={
                'first_attempt': Count('id', filter=Q(total_delivery_attempts__lte=1)),
                'second_attempt': Count('id', filter=Q(total_delivery_attempts=2)),
                'ndr_delivered': Count('id', filter=Q(total_delivery_attempts__gte=3)),
                'escalation_delivered': Count('id', filter=Q(order__ndr_escalation_status='DELIVERED')),
            }
        )
        # Add percentages
        for courier, ptypes in table2.items():
            for ptype, data in ptypes.items():
                if isinstance(data, dict) and 'qty' in data:
                    qty = data['qty']
                    data['total_delivery_pct'] = 100.0  # All rows here are delivered
                    data['first_attempt_pct'] = round((data.get('first_attempt', 0) / qty) * 100, 1) if qty > 0 else 0
                    data['second_attempt_pct'] = round((data.get('second_attempt', 0) / qty) * 100, 1) if qty > 0 else 0
                    data['ndr_pct'] = round((data.get('ndr_delivered', 0) / qty) * 100, 1) if qty > 0 else 0
                    data['escalation_pct'] = round((data.get('escalation_delivered', 0) / qty) * 100, 1) if qty > 0 else 0

        # ====================================================================
        # TABLE 3: Delivery Speed (Day 1-7+)
        # ====================================================================
        delivered_qs = base_qs.filter(
            current_stage='Delivered',
            dispatch_date__isnull=False,
            delivery_date__isnull=False,
        )

        table3 = self._compute_delivery_speed(delivered_qs)

        # ====================================================================
        # TABLE 4: NDR Breakdown
        # ====================================================================
        ndr_qs = base_qs.filter(order__is_ndr=True)

        table4 = _build_grouped_data(
            ndr_qs,
            extra_annotations={
                'will_accept': Count('id', filter=Q(order__ndr_call_status__icontains='Will Accept')),
                'delivered_after_yes': Count('id', filter=Q(
                    order__ndr_call_status__icontains='Will Accept',
                    current_stage='Delivered'
                )),
                'failed_after_escalation': Count('id', filter=Q(
                    order__ndr_escalation_count__gte=1,
                    current_stage__in=['RTO', 'In Transit']
                )),
                'no_want': Count('id', filter=Q(
                    order__ndr_call_status__icontains='Refused'
                ) | Q(order__ndr_call_status__icontains='Cancel')),
                'pending_answer': Count('id', filter=Q(
                    order__ndr_call_status__isnull=True
                ) | Q(order__ndr_call_status='')),
                'rto_from_ndr': Count('id', filter=Q(current_stage='RTO')),
            }
        )
        # Add percentages
        for courier, ptypes in table4.items():
            for ptype, data in ptypes.items():
                if isinstance(data, dict) and 'qty' in data:
                    qty = data['qty']
                    for key in ['will_accept', 'delivered_after_yes', 'failed_after_escalation',
                                'no_want', 'pending_answer', 'rto_from_ndr']:
                        data[f'{key}_pct'] = round((data.get(key, 0) / qty) * 100, 1) if qty > 0 else 0

        # ====================================================================
        # TABLE 5: Geographic & Reason Performance
        # ====================================================================
        table5 = self._compute_geographic_performance(base_qs)

        # ====================================================================
        # TABLE 6: Shipping Cost Breakdown
        # ====================================================================
        table6 = self._compute_cost_breakdown(base_qs)

        return Response({
            'kpis': kpis,
            'cost_analytics': cost_analytics,
            'date_range': {
                'start_date': str(start_date),
                'end_date': str(end_date),
            },
            'tables': {
                'shipping_performance': table1,
                'delivery_effectiveness': table2,
                'delivery_speed': table3,
                'ndr_breakdown': table4,
                'geographic_performance': table5,
                'cost_breakdown': table6,
            }
        })

    # ------------------------------------------------------------------
    # KPI COMPUTATION
    # ------------------------------------------------------------------
    def _compute_kpis(self, base_qs, org_id):
        """8 KPI metrics for the dashboard header."""
        total = base_qs.count()
        if total == 0:
            return {
                'total_shipped': 0, 'delivered_pct': 0, 'rto_pct': 0,
                'in_transit_pct': 0, 'avg_delivery_time': 0,
                'cost_per_shipment': 0, 'cod_pending_amount': 0,
                'courier_success_rate': 0,
            }

        stats = base_qs.aggregate(
            delivered=Count('id', filter=Q(current_stage='Delivered')),
            rto=Count('id', filter=Q(current_stage='RTO')),
            in_transit=Count('id', filter=Q(current_stage__in=['In Transit', 'in-transit', 'In-Transit', 'in transit'])),
        )

        # Avg delivery time (in days)
        delivered_with_dates = base_qs.filter(
            current_stage='Delivered',
            dispatch_date__isnull=False,
            delivery_date__isnull=False,
        )
        avg_tat = 0
        if delivered_with_dates.exists():
            # Calculate average timedelta
            tats = []
            for dispatch, delivery in delivered_with_dates.values_list('dispatch_date', 'delivery_date')[:2000]:
                if dispatch and delivery:
                    delta = (delivery - dispatch).total_seconds() / 86400
                    tats.append(delta)
            avg_tat = round(sum(tats) / len(tats), 1) if tats else 0

        # Cost per shipment
        cost_agg = ShipmentCost.objects.filter(
            shipment__in=base_qs
        ).aggregate(
            total_cost=Coalesce(Sum(
                F('forward_cost') + F('rto_cost') + F('cod_charges') +
                F('fuel_surcharge') + F('weight_discrepancy_charges') +
                F('ndr_reattempt_cost')
            ), Value(0), output_field=DecimalField())
        )
        total_cost = float(cost_agg['total_cost'])
        cost_per_shipment = round(total_cost / total, 2) if total > 0 else 0

        # COD pending amount
        # Tier 1: Use CODRemittance records if they exist (formal tracking after upload)
        cod_remittance_qs = CODRemittance.objects.filter(
            shipment__in=base_qs,
            status__in=['Pending', 'Overdue'],
        )
        if cod_remittance_qs.exists():
            cod_pending = cod_remittance_qs.aggregate(
                pending=Coalesce(
                    Sum(F('expected_amount') - F('received_amount')),
                    Value(0), output_field=DecimalField()
                )
            )['pending']
        else:
            # Tier 2: Fallback — sum order values for all delivered COD/Partially Paid
            # shipments in the date range that haven't been remitted yet.
            # This represents the amount the courier OWES us.
            cod_pending = base_qs.filter(
                current_stage='Delivered',
                payment_type__in=['COD', 'Partially Paid'],
            ).aggregate(
                pending=Coalesce(
                    Sum('order__total_price'),
                    Value(0), output_field=DecimalField()
                )
            )['pending']

        return {
            'total_shipped': total,
            'delivered_pct': round((stats['delivered'] / total) * 100, 1),
            'rto_pct': round((stats['rto'] / total) * 100, 1),
            'in_transit_pct': round((stats['in_transit'] / total) * 100, 1),
            'avg_delivery_time': avg_tat,
            'cost_per_shipment': cost_per_shipment,
            'cod_pending_amount': float(cod_pending),
            'courier_success_rate': round((stats['delivered'] / total) * 100, 1),
        }

    # ------------------------------------------------------------------
    # COST ANALYTICS
    # ------------------------------------------------------------------
    def _compute_cost_analytics(self, base_qs):
        """3 cost analytics metrics."""
        costs = ShipmentCost.objects.filter(shipment__in=base_qs)

        if not costs.exists():
            return {
                'avg_shipping_cost': 0,
                'overbilling_pct': 0,
                'expected_vs_actual': {'expected': 0, 'actual': 0, 'variance': 0},
            }

        agg = costs.aggregate(
            avg_cost=Coalesce(Avg(
                F('forward_cost') + F('rto_cost') + F('cod_charges') +
                F('fuel_surcharge') + F('weight_discrepancy_charges') + 
                F('ndr_reattempt_cost')
            ), Value(0), output_field=DecimalField()),
            overbilled=Count('id', filter=Q(is_overbilled=True)),
            total_costs=Count('id'),
            total_expected=Coalesce(Sum('expected_cost'), Value(0), output_field=DecimalField()),
            total_actual=Coalesce(Sum('actual_billed_cost'), Value(0), output_field=DecimalField()),
        )

        overbilling_pct = round(
            (agg['overbilled'] / agg['total_costs']) * 100, 1
        ) if agg['total_costs'] > 0 else 0

        return {
            'avg_shipping_cost': float(agg['avg_cost']),
            'overbilling_pct': overbilling_pct,
            'expected_vs_actual': {
                'expected': float(agg['total_expected']),
                'actual': float(agg['total_actual']),
                'variance': float(agg['total_actual'] - agg['total_expected']),
            },
        }

    # ------------------------------------------------------------------
    # TABLE 3: Delivery Speed
    # ------------------------------------------------------------------
    def _compute_delivery_speed(self, delivered_qs):
        """
        Bucket delivered orders into Day 1 through Day 7+ bins.
        Grouped by courier_partner × payment_type.
        """
        rows = delivered_qs.values('courier_partner', 'payment_type').annotate(
            total=Count('id'),
            amount=Coalesce(Sum('order__total_price'), Value(0), output_field=DecimalField()),
        ).order_by('courier_partner', 'payment_type')

        # We need day buckets — compute in Python (DB-level timedelta arithmetic varies by engine)
        # Build {courier: {ptype: {day1_qty: N, day1_pct: N, ...}}}
        result = {}
        grand_totals = {}

        # Pre-fetch all delivered shipments with dates for in-memory computation
        all_delivered = list(
            delivered_qs.values(
                'id', 'courier_partner', 'payment_type',
                'dispatch_date', 'delivery_date', 'order__total_price'
            )[:10000]  # Safety cap
        )

        for s in all_delivered:
            courier = s['courier_partner']
            ptype = s['payment_type']
            amt = float(s['order__total_price'] or 0)

            if s['dispatch_date'] and s['delivery_date']:
                days = max(1, (s['delivery_date'] - s['dispatch_date']).days)
            else:
                days = 0

            day_bucket = f'day_{min(days, 7)}' if days <= 7 else 'day_7'
            if days == 0:
                day_bucket = 'day_1'

            # Initialize courier dict
            if courier not in result:
                result[courier] = {}
            if ptype not in result[courier]:
                result[courier][ptype] = self._empty_speed_row()

            # Increment
            result[courier][ptype]['total_qty'] += 1
            result[courier][ptype]['total_amount'] += amt
            result[courier][ptype][f'{day_bucket}_qty'] += 1
            result[courier][ptype][f'{day_bucket}_amount'] += amt

            # Courier total
            if 'Total' not in result[courier]:
                result[courier]['Total'] = self._empty_speed_row()
            result[courier]['Total']['total_qty'] += 1
            result[courier]['Total']['total_amount'] += amt
            result[courier]['Total'][f'{day_bucket}_qty'] += 1
            result[courier]['Total'][f'{day_bucket}_amount'] += amt

            # Grand total by ptype
            if ptype not in grand_totals:
                grand_totals[ptype] = self._empty_speed_row()
            grand_totals[ptype]['total_qty'] += 1
            grand_totals[ptype]['total_amount'] += amt
            grand_totals[ptype][f'{day_bucket}_qty'] += 1
            grand_totals[ptype][f'{day_bucket}_amount'] += amt

            # Grand total overall
            if 'Total' not in grand_totals:
                grand_totals['Total'] = self._empty_speed_row()
            grand_totals['Total']['total_qty'] += 1
            grand_totals['Total']['total_amount'] += amt
            grand_totals['Total'][f'{day_bucket}_qty'] += 1
            grand_totals['Total'][f'{day_bucket}_amount'] += amt

        # Compute percentages
        for courier in result:
            for ptype in result[courier]:
                self._add_speed_pcts(result[courier][ptype])
        for ptype in grand_totals:
            self._add_speed_pcts(grand_totals[ptype])

        result['Total'] = grand_totals
        return result

    def _empty_speed_row(self):
        row = {'total_qty': 0, 'total_amount': 0}
        for d in range(1, 8):
            row[f'day_{d}_qty'] = 0
            row[f'day_{d}_amount'] = 0
        return row

    def _add_speed_pcts(self, row):
        total = row['total_qty']
        for d in range(1, 8):
            qty = row[f'day_{d}_qty']
            row[f'day_{d}_pct'] = round((qty / total) * 100, 1) if total > 0 else 0

    # ------------------------------------------------------------------
    # TABLE 5: Geographic & Reason Performance
    # ------------------------------------------------------------------
    def _compute_geographic_performance(self, base_qs):
        """Top failure reasons + Top 10 states + Top 20 cities."""

        # 5A: Top Reasons for Failed Delivery
        failed_shipments = base_qs.filter(
            current_stage__in=['RTO', 'OFD'],
            ndr_reason__gt='',
        )
        top_reasons = list(
            failed_shipments.values('ndr_reason').annotate(
                qty=Count('id'),
                amount=Coalesce(Sum('order__total_price'), Value(0), output_field=DecimalField()),
            ).order_by('-qty')[:15]
        )
        total_failed = sum(r['qty'] for r in top_reasons) or 1
        for r in top_reasons:
            r['amount'] = float(r['amount'])
            r['aov'] = round(r['amount'] / r['qty'], 2) if r['qty'] > 0 else 0
            r['pct'] = round((r['qty'] / total_failed) * 100, 1)

        # 5B: Top 10 States
        top_states = list(
            base_qs.filter(
                order__shipping_state__isnull=False,
            ).exclude(
                order__shipping_state=''
            ).values('order__shipping_state').annotate(
                qty=Count('id'),
                amount=Coalesce(Sum('order__total_price'), Value(0), output_field=DecimalField()),
                delivered_qty=Count('id', filter=Q(current_stage='Delivered')),
                rto_qty=Count('id', filter=Q(current_stage='RTO')),
            ).order_by('-qty')[:10]
        )
        for s in top_states:
            s['amount'] = float(s['amount'])
            s['aov'] = round(s['amount'] / s['qty'], 2) if s['qty'] > 0 else 0
            s['delivery_pct'] = round((s['delivered_qty'] / s['qty']) * 100, 1) if s['qty'] > 0 else 0
            s['rto_pct'] = round((s['rto_qty'] / s['qty']) * 100, 1) if s['qty'] > 0 else 0
            s['state'] = s.pop('order__shipping_state')

        # 5C: Top 20 Cities (using pincode-derived city if available)
        # We use shipping_pincode prefix as a proxy since city isn't stored on Shipment
        top_cities = list(
            base_qs.filter(
                order__shipping_pincode__isnull=False,
            ).exclude(
                order__shipping_pincode=''
            ).values('order__shipping_pincode').annotate(
                qty=Count('id'),
                amount=Coalesce(Sum('order__total_price'), Value(0), output_field=DecimalField()),
                delivered_qty=Count('id', filter=Q(current_stage='Delivered')),
                rto_qty=Count('id', filter=Q(current_stage='RTO')),
            ).order_by('-qty')[:20]
        )
        for c in top_cities:
            c['amount'] = float(c['amount'])
            c['aov'] = round(c['amount'] / c['qty'], 2) if c['qty'] > 0 else 0
            c['delivery_pct'] = round((c['delivered_qty'] / c['qty']) * 100, 1) if c['qty'] > 0 else 0
            c['rto_pct'] = round((c['rto_qty'] / c['qty']) * 100, 1) if c['qty'] > 0 else 0
            c['pincode'] = c.pop('order__shipping_pincode')

        return {
            'top_failure_reasons': top_reasons,
            'top_states': top_states,
            'top_cities': top_cities,
        }

    # ------------------------------------------------------------------
    # TABLE 6: Shipping Cost Breakdown
    # ------------------------------------------------------------------
    def _compute_cost_breakdown(self, base_qs):
        """
        Cost breakdown: Total / Delivered / RTO orders each with
        qty, shipping cost, avg shipping cost — grouped by courier × ptype.
        """
        # Total orders with cost
        cost_qs = base_qs.filter(cost__isnull=False)

        total_data = _build_grouped_data(
            cost_qs,
            extra_annotations={
                'shipping_cost': Coalesce(Sum(
                    F('cost__forward_cost') + F('cost__rto_cost') +
                    F('cost__cod_charges') + F('cost__fuel_surcharge') +
                    F('cost__weight_discrepancy_charges') + F('cost__ndr_reattempt_cost')
                ), Value(0), output_field=DecimalField()),
            }
        )

        delivered_data = _build_grouped_data(
            cost_qs.filter(current_stage='Delivered'),
            extra_annotations={
                'shipping_cost': Coalesce(Sum(
                    F('cost__forward_cost') + F('cost__cod_charges') +
                    F('cost__fuel_surcharge')
                ), Value(0), output_field=DecimalField()),
            }
        )

        rto_data = _build_grouped_data(
            cost_qs.filter(current_stage='RTO'),
            extra_annotations={
                'shipping_cost': Coalesce(Sum(
                    F('cost__forward_cost') + F('cost__rto_cost') +
                    F('cost__fuel_surcharge')
                ), Value(0), output_field=DecimalField()),
            }
        )

        # Add avg_shipping_cost to each cell
        for dataset in [total_data, delivered_data, rto_data]:
            for courier, ptypes in dataset.items():
                for ptype, data in ptypes.items():
                    if isinstance(data, dict) and 'qty' in data:
                        data['avg_shipping_cost'] = round(
                            data.get('shipping_cost', 0) / data['qty'], 2
                        ) if data['qty'] > 0 else 0

        return {
            'total_orders': total_data,
            'delivered_orders': delivered_data,
            'rto_orders': rto_data,
        }


# ==============================================================================
# COST CSV UPLOAD VIEW
# ==============================================================================

class ShipmentCostUploadView(APIView):
    """
    POST /api/delivery/upload-costs/
    Upload a CSV from courier billing sheets to populate ShipmentCost records.

    Expected CSV columns:
    awb_number, forward_cost, rto_cost, cod_charges, fuel_surcharge,
    weight_discrepancy_charges, ndr_reattempt_cost, expected_cost, actual_billed_cost
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:delivery_analytics:create'
    }

    def post(self, request):
        import csv
        import io
        from rest_framework.parsers import MultiPartParser, FormParser

        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'error': 'No CSV file provided'}, status=400)

        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        try:
            decoded = csv_file.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(decoded))

            created = 0
            updated = 0
            errors = []

            for row_num, row in enumerate(reader, start=2):
                awb = (row.get('awb_number') or '').strip()
                if not awb:
                    errors.append(f"Row {row_num}: Missing awb_number")
                    continue

                try:
                    shipment = Shipment.objects.get(awb_number=awb, org_id=org_id)
                except Shipment.DoesNotExist:
                    errors.append(f"Row {row_num}: Shipment {awb} not found")
                    continue

                cost, was_created = ShipmentCost.objects.get_or_create(shipment=shipment)

                # Update fields from CSV
                for field in ['forward_cost', 'rto_cost', 'cod_charges', 'fuel_surcharge',
                              'weight_discrepancy_charges', 'ndr_reattempt_cost',
                              'expected_cost', 'actual_billed_cost']:
                    val = row.get(field, '').strip()
                    if val:
                        try:
                            setattr(cost, field, Decimal(val))
                        except Exception:
                            pass

                cost.save()  # Triggers overbilling detection in model.save()

                # Calculate true cost
                from core.services.delivery_services import calculate_true_cost
                calculate_true_cost(cost)

                if was_created:
                    created += 1
                else:
                    updated += 1

            return Response({
                'message': f'{created} created, {updated} updated',
                'total_processed': created + updated,
                'errors': errors[:50],  # Cap error list
            })

        except Exception as e:
            logger.exception(f"Error processing cost CSV: {e}")
            return Response({'error': str(e)}, status=500)


# ==============================================================================
# RECONCILIATION VIEW
# ==============================================================================

class ReconciliationView(APIView):
    """
    GET /api/delivery/reconciliation/
    Returns reconciliation flags for the organization.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:delivery_analytics:view'
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        start_date, end_date = _parse_dates(request)
        result = reconcile_orders(org_id, start_date, end_date)

        # Also include COD remittance status
        cod_status = check_cod_remittances(org_id)

        return Response({
            'reconciliation': result,
            'cod_remittance': cod_status,
        })


# ==============================================================================
# MANUAL COST ENTRY VIEW
# ==============================================================================

class ShipmentCostManualView(APIView):
    """
    GET  /api/delivery/shipment-cost/?awb=<AWB>  — Lookup shipment + cost by AWB
    POST /api/delivery/shipment-cost/             — Create/update cost for a shipment
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:delivery_analytics:view',
        'POST': 'logistics:delivery_analytics:create',
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        awb = request.query_params.get('awb', '').strip()
        if not awb:
            return Response({'error': 'AWB number is required'}, status=400)

        try:
            shipment = Shipment.objects.select_related('order', 'cost').get(
                awb_number=awb, org_id=org_id
            )
        except Shipment.DoesNotExist:
            return Response({'error': f'Shipment with AWB {awb} not found'}, status=404)

        # Build cost data (empty template if no cost record exists)
        cost_fields = [
            'forward_cost', 'rto_cost', 'cod_charges', 'fuel_surcharge',
            'weight_discrepancy_charges', 'ndr_reattempt_cost',
            'expected_cost', 'actual_billed_cost',
        ]
        cost_data = {}
        has_cost = hasattr(shipment, 'cost') and shipment.cost is not None
        try:
            cost_obj = shipment.cost
            has_cost = True
        except ShipmentCost.DoesNotExist:
            has_cost = False

        for f in cost_fields:
            cost_data[f] = float(getattr(cost_obj, f, 0)) if has_cost else 0

        if has_cost:
            cost_data['is_overbilled'] = cost_obj.is_overbilled
            cost_data['overbilling_amount'] = float(cost_obj.overbilling_amount)
            cost_data['true_cost'] = float(cost_obj.true_cost)
            cost_data['total_cost'] = float(cost_obj.total_cost)
        else:
            cost_data['is_overbilled'] = False
            cost_data['overbilling_amount'] = 0
            cost_data['true_cost'] = 0
            cost_data['total_cost'] = 0

        return Response({
            'shipment': {
                'id': shipment.id,
                'awb_number': shipment.awb_number,
                'courier_partner': shipment.courier_partner,
                'payment_type': shipment.payment_type,
                'current_stage': shipment.current_stage,
                'order_number': shipment.order.order_number if shipment.order else None,
                'dispatch_date': str(shipment.dispatch_date) if shipment.dispatch_date else None,
                'delivery_date': str(shipment.delivery_date) if shipment.delivery_date else None,
            },
            'cost': cost_data,
            'has_cost': has_cost,
        })

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        awb = request.data.get('awb_number', '').strip()
        if not awb:
            return Response({'error': 'AWB number is required'}, status=400)

        try:
            shipment = Shipment.objects.get(awb_number=awb, org_id=org_id)
        except Shipment.DoesNotExist:
            return Response({'error': f'Shipment with AWB {awb} not found'}, status=404)

        cost, created = ShipmentCost.objects.get_or_create(shipment=shipment)

        cost_fields = [
            'forward_cost', 'rto_cost', 'cod_charges', 'fuel_surcharge',
            'weight_discrepancy_charges', 'ndr_reattempt_cost',
            'expected_cost', 'actual_billed_cost',
        ]
        for field in cost_fields:
            val = request.data.get(field)
            if val is not None:
                try:
                    setattr(cost, field, Decimal(str(val)))
                except Exception:
                    pass

        cost.save()  # Triggers overbilling detection

        # Recalculate true cost
        from core.services.delivery_services import calculate_true_cost
        calculate_true_cost(cost)

        return Response({
            'message': 'Cost saved successfully',
            'created': created,
            'total_cost': float(cost.total_cost),
            'is_overbilled': cost.is_overbilled,
        })

# ==============================================================================
# COD REMITTANCE LIST VIEW
# ==============================================================================

class CODRemittanceListView(APIView):
    """
    GET /api/delivery/cod-remittance/
    Returns delivered COD orders with lifecycle dates, tracking info,
    expected shipping cost (from rate card), and remittance status.

    Query params: page, limit, start_date, end_date, courier
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:cost_management:view'
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        page = int(request.query_params.get('page', 1))
        limit = min(int(request.query_params.get('limit', 50)), 200)
        offset = (page - 1) * limit

        start_date, end_date = _parse_dates(request)
        courier_filter = request.query_params.get('courier', '')
        search_query = request.query_params.get('q', '').strip()

        # Only COD / Partially Paid delivered orders
        qs = Shipment.objects.filter(
            Q(current_stage='Delivered') | Q(delivery_date__isnull=False),
            org_id=org_id,
            payment_type__in=['COD', 'Partially Paid'],
        ).select_related('order', 'cost').order_by('-delivery_date')

        if search_query:
            qs = qs.filter(
                Q(awb_number__icontains=search_query) |
                Q(order__order_number__icontains=search_query)
            )

        if start_date:
            qs = qs.filter(delivery_date__gte=start_date)
        if end_date:
            from datetime import timedelta
            # Add 1 day to end_date to make it inclusive for datetime fields
            inclusive_end = end_date + timedelta(days=1)
            qs = qs.filter(delivery_date__lt=inclusive_end)
        if courier_filter:
            qs = qs.filter(courier_partner=courier_filter)

        total_count = qs.count()

        # Summary KPIs
        summary = qs.aggregate(
            total_order_value=Coalesce(
                Sum('order__total_price'), Value(0), output_field=DecimalField()
            ),
            total_expected_cost=Coalesce(
                Sum('cost__expected_cost'), Value(0), output_field=DecimalField()
            ),
        )

        # Remittance aggregates
        remittance_agg = CODRemittance.objects.filter(
            shipment__in=qs,
        ).aggregate(
            total_expected=Coalesce(
                Sum('expected_amount'), Value(0), output_field=DecimalField()
            ),
            total_received=Coalesce(
                Sum('received_amount'), Value(0), output_field=DecimalField()
            ),
            pending_count=Count('id', filter=Q(status__in=['Pending', 'Overdue'])),
            overdue_count=Count('id', filter=Q(status='Overdue')),
        )

        # Paginated shipments
        shipments = qs[offset:offset + limit]

        orders_data = []
        for s in shipments:
            order = s.order
            cost_obj = getattr(s, 'cost', None)

            # Get latest remittance for this shipment
            remittance = s.remittances.order_by('-created_at').first()
            
            # Use remittance expected_amount if available, else fallback to order total (for pure COD)
            expected_remittance = float(remittance.expected_amount) if remittance else (float(order.total_price) if order else 0)

            orders_data.append({
                'id': s.id,
                'order_number': order.order_number if order else '-',
                'order_date': str(order.created_at.date()) if order and order.created_at else None,
                'dispatch_date': str(s.dispatch_date.date()) if s.dispatch_date else None,
                'delivery_date': str(s.delivery_date.date()) if s.delivery_date else None,
                'awb_number': s.awb_number,
                'courier': s.courier_partner,
                'payment_type': s.payment_type,
                'zone': s.zone,
                'pincode': order.shipping_pincode if order else '-',
                'order_value': float(order.total_price) if order and order.total_price else 0,
                'expected_shipping_cost': float(cost_obj.expected_cost) if cost_obj else 0,
                'actual_billed_cost': float(cost_obj.actual_billed_cost) if cost_obj else 0,
                'net_remittance': expected_remittance,
                'remittance_status': remittance.status if remittance else 'No Record',
                'expected_remittance_date': str(remittance.expected_remittance_date) if remittance and remittance.expected_remittance_date else None,
                'actual_remittance_date': str(remittance.actual_remittance_date) if remittance and remittance.actual_remittance_date else None,
                'received_amount': float(remittance.received_amount) if remittance else 0,
                'delay_days': remittance.delay_days if remittance else 0,
            })

        return Response({
            'orders': orders_data,
            'count': total_count,
            'page': page,
            'limit': limit,
            'summary': {
                'total_cod_value': float(summary['total_order_value']),
                'total_expected_cost': float(summary['total_expected_cost']),
                'net_expected_remittance': float(remittance_agg['total_expected']),
                'total_received': float(remittance_agg['total_received']),
                'pending_count': remittance_agg['pending_count'],
                'overdue_count': remittance_agg['overdue_count'],
            }
        })


class CODRemittanceWeeklySummaryView(APIView):
    """
    GET /api/delivery/cod-remittance/weekly-summary/
    Returns COD remittance totals grouped by Month and Weekly cycles (1-7, 8-14, 15-21, 22-end).
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:cost_management:view'
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        courier_filter = request.query_params.get('courier', '')
        
        # Group by delivery date (not expected_remittance_date)
        # This shows settlement cycles for all deliveries in the past 6 months.
        six_months_ago = timezone.now().date() - timedelta(days=180)
        
        remittances = CODRemittance.objects.filter(
            shipment__org_id=org_id,
        ).filter(
            # Include remittances where delivery happened in last 6 months
            # OR where expected_remittance_date is in last 6 months (future/upcoming)
            Q(shipment__delivery_date__date__gte=six_months_ago) |
            Q(expected_remittance_date__gte=six_months_ago)
        ).select_related('shipment')
        
        if courier_filter:
            remittances = remittances.filter(shipment__courier_partner=courier_filter)
            
        # Grouping in memory for flexibility with day-ranges
        summary_data = {} # { "Month Year": { "Week 1": 0, "Week 2": 0, ... } }
        
        for r in remittances:
            # Group by delivery_date (Settlement for orders delivered in Week X)
            delivery_date = r.shipment.delivery_date
            if not delivery_date: continue
            
            month_key = delivery_date.strftime("%B %Y")
            day = delivery_date.day
            
            if month_key not in summary_data:
                summary_data[month_key] = {
                    "Week 1 (1-7)": Decimal('0'),
                    "Week 2 (8-14)": Decimal('0'),
                    "Week 3 (15-21)": Decimal('0'),
                    "Week 4 (22+)": Decimal('0'),
                    "Total": Decimal('0')
                }
            
            week_label = "Week 4 (22+)"
            if day <= 7: week_label = "Week 1 (1-7)"
            elif day <= 14: week_label = "Week 2 (8-14)"
            elif day <= 21: week_label = "Week 3 (15-21)"
            
            summary_data[month_key][week_label] += r.expected_amount
            summary_data[month_key]["Total"] += r.expected_amount

        # Convert to sorted list
        final_list = []
        for month, weeks in summary_data.items():
            row = {"month": month}
            row.update({k: float(v) for k, v in weeks.items()})
            final_list.append(row)
            
        # Sort by date (parsing month string back)
        final_list.sort(key=lambda x: datetime.strptime(x['month'], "%B %Y"), reverse=True)

        return Response({
            'summary': final_list,
            'courier': courier_filter
        })


# ==============================================================================
# CONCILIATION (RECONCILIATION) LIST VIEW
# ==============================================================================

class ConciliationListView(APIView):
    """
    GET /api/delivery/conciliation/
    Returns all shipped orders with expected vs actual cost comparison
    for billing reconciliation. Highlights overbilled orders.

    Query params: page, limit, start_date, end_date, courier, overbilled_only
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:cost_management:view'
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        page = int(request.query_params.get('page', 1))
        limit = min(int(request.query_params.get('limit', 50)), 200)
        offset = (page - 1) * limit

        start_date, end_date = _parse_dates(request)
        courier_filter = request.query_params.get('courier', '')
        overbilled_only = request.query_params.get('overbilled_only', '').lower() == 'true'

        # All shipments that have cost records
        qs = Shipment.objects.filter(
            org_id=org_id,
            cost__isnull=False,
        ).select_related('order', 'cost').order_by('-dispatch_date')

        if start_date:
            qs = qs.filter(dispatch_date__date__gte=start_date)
        if end_date:
            qs = qs.filter(dispatch_date__date__lte=end_date)
        if courier_filter:
            qs = qs.filter(courier_partner=courier_filter)
        if overbilled_only:
            qs = qs.filter(cost__is_overbilled=True)

        total_count = qs.count()

        # Summary KPIs
        summary = ShipmentCost.objects.filter(shipment__in=qs).aggregate(
            total_expected=Coalesce(Sum('expected_cost'), Value(0), output_field=DecimalField()),
            total_actual=Coalesce(Sum('actual_billed_cost'), Value(0), output_field=DecimalField()),
            total_overbilled_amount=Coalesce(
                Sum('overbilling_amount', filter=Q(is_overbilled=True)),
                Value(0), output_field=DecimalField()
            ),
            overbilled_count=Count('id', filter=Q(is_overbilled=True)),
            total_records=Count('id'),
        )

        # Paginated shipments
        shipments = qs[offset:offset + limit]

        # --- Enrich with CourierInvoiceLine data (from Excel invoice upload) ---
        from core.models.delivery import CourierInvoiceLine
        awb_list = [s.awb_number for s in shipments]
        # Also lookup RTO AWBs (AWB + 'R' suffix) for the same shipments
        rto_awb_list = [awb + 'R' for awb in awb_list]
        invoice_lines = CourierInvoiceLine.objects.filter(
            org_id=org_id,
            awb_number__in=awb_list + rto_awb_list,
        ).order_by('-created_at')
        invoice_line_map = {}
        for il in invoice_lines:
            # Normalise AWB to the forward AWB (strip trailing 'R')
            base_awb = il.awb_number
            if base_awb.upper().endswith('R') and base_awb[:-1] in awb_list:
                base_awb = base_awb[:-1]

            if base_awb not in invoice_line_map:
                invoice_line_map[base_awb] = {
                    'total_billed': Decimal('0'),
                    'forward_billed': Decimal('0'),
                    'rto_billed': Decimal('0'),
                    'expected_total': Decimal('0'),
                    'overcharge_amount': Decimal('0'),
                    'freight': Decimal('0'),
                    'fsc': Decimal('0'),
                    'caf': Decimal('0'),
                    'fod': Decimal('0'),
                    'charged_weight_kg': Decimal('0'),
                    'actual_weight_kg': Decimal('0'),
                    'discrepancy_types': set(),
                    'shipment_types': [],
                    'is_disputed': False,
                    'line_ids': [],
                    'invoice_ids': set(),
                    'line_count': 0,
                }

            data = invoice_line_map[base_awb]
            data['total_billed'] += il.total_billed
            data['expected_total'] += (il.expected_total or il.total_billed)
            data['overcharge_amount'] += il.overcharge_amount
            data['freight'] += il.freight
            data['fsc'] += il.fsc
            data['caf'] += il.caf
            data['fod'] += il.fod_charge
            data['charged_weight_kg'] = max(data['charged_weight_kg'], il.charged_weight_kg)
            data['actual_weight_kg'] = max(data['actual_weight_kg'], il.actual_weight_kg)
            data['line_count'] += 1

            # Track forward vs RTO amounts separately
            if il.shipment_type == 'Forward':
                data['forward_billed'] += il.total_billed
            else:
                data['rto_billed'] += il.total_billed

            if il.shipment_type not in data['shipment_types']:
                data['shipment_types'].append(il.shipment_type)

            if il.discrepancy_type != 'None':
                data['discrepancy_types'].add(il.discrepancy_type)
            if il.is_disputed:
                data['is_disputed'] = True
            data['line_ids'].append(il.id)
            data['invoice_ids'].add(il.freight_invoice_id)

        # Post-process for display
        for awb, data in invoice_line_map.items():
            dt_list = list(data['discrepancy_types'])
            if not dt_list:
                data['discrepancy_type'] = 'None'
            elif len(dt_list) == 1:
                data['discrepancy_type'] = dt_list[0]
            else:
                data['discrepancy_type'] = 'Multiple'

        orders_data = []
        for s in shipments:
            order = s.order
            cost  = s.cost
            il    = invoice_line_map.get(s.awb_number)

            orders_data.append({
                'id':                s.id,
                'order_number':      order.order_number if order else '-',
                'order_date':        str(order.created_at.date()) if order and order.created_at else None,
                'dispatch_date':     str(s.dispatch_date.date()) if s.dispatch_date else None,
                'delivery_date':     str(s.delivery_date.date()) if s.delivery_date else None,
                'awb_number':        s.awb_number,
                'courier':           s.courier_partner,
                'current_stage':     s.current_stage,
                'payment_type':      s.payment_type,
                'zone':              s.zone,
                'weight_slab':       float(s.weight_slab),
                'pincode':           order.shipping_pincode if order else '-',
                'order_value':       float(order.total_price) if order and order.total_price else 0,
                'forward_cost':      float(cost.forward_cost),
                'rto_cost':          float(cost.rto_cost),
                'cod_charges':       float(cost.cod_charges),
                'fuel_surcharge':    float(cost.fuel_surcharge),
                'expected_cost':     float(cost.expected_cost),
                'actual_billed_cost':float(cost.actual_billed_cost),
                'is_overbilled':     cost.is_overbilled,
                'overbilling_amount':float(cost.overbilling_amount),
                'total_cost':        float(cost.total_cost),
                # --- Invoice-level billing detail (aggregated) ---
                'invoice_charged_slab':  float(il['charged_weight_kg'])  if il else None,
                'invoice_actual_weight': float(il['actual_weight_kg'])   if il else None,
                'invoice_total_billed':  float(il['total_billed'])        if il else None,
                'invoice_forward_billed':float(il['forward_billed'])     if il else None,
                'invoice_rto_billed':    float(il['rto_billed'])         if il else None,
                'invoice_expected_total':float(il['expected_total'])      if il and il['expected_total'] else None,
                'invoice_overcharge':    float(il['overcharge_amount'])   if il else None,
                'invoice_discrepancy':   il['discrepancy_type']           if il else None,
                'invoice_freight':       float(il['freight'])             if il else None,
                'invoice_fsc':           float(il['fsc'])                 if il else None,
                'invoice_caf':           float(il['caf'])                 if il else None,
                'invoice_fod':           float(il['fod'])                 if il else None,
                'invoice_is_disputed':   il['is_disputed']                if il else None,
                'invoice_line_id':       il['line_ids'][0]                if il and il['line_ids'] else None,
                'invoice_id':            list(il['invoice_ids'])[0]       if il and il['invoice_ids'] else None,
                'invoice_line_count':    il['line_count']                 if il else 0,
                'invoice_shipment_types':il['shipment_types']             if il else [],
            })

        return Response({
            'orders': orders_data,
            'count': total_count,
            'page': page,
            'limit': limit,
            'summary': {
                'total_expected': float(summary['total_expected']),
                'total_actual': float(summary['total_actual']),
                'variance': round(float(summary['total_actual']) - float(summary['total_expected']), 2),
                'total_overbilled_amount': float(summary['total_overbilled_amount']),
                'overbilled_count': summary['overbilled_count'],
                'total_records': summary['total_records'],
            }
        })

# ==============================================================================
# 9. FREIGHT INVOICE UPLOAD VIEW
# ==============================================================================
import os
import time
import tempfile
from datetime import datetime
from django.db import transaction
from rest_framework.parsers import MultiPartParser, FormParser
from core.services.delivery_services import parse_bluedart_pdf

class FreightInvoiceUploadView(APIView):
    """
    Accepts a Courier Freight Invoice PDF, parses it, creates a FreightInvoice,
    and updates ShipmentCost records.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        file_obj = request.FILES.get('file')
        courier_partner = request.data.get('courier_partner', 'Bluedart')
        invoice_date_str = request.data.get('invoice_date')

        if not file_obj:
            return Response({'error': 'No invoice PDF file provided'}, status=400)

        invoice_date = timezone.now().date()
        if invoice_date_str:
            try:
                invoice_date = datetime.strptime(invoice_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Save to temp file for parsing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            for chunk in file_obj.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            parsed_invoice_date_str = None
            if courier_partner == 'Bluedart':
                invoice_number, parsed_invoice_date_str, summary_dict, rows = parse_bluedart_pdf(tmp_path)
            # Placeholder for future courier parsers (Delhivery, Ekart)
            elif courier_partner == 'Delhivery':
                return Response({'error': 'Delhivery parser coming soon!'}, status=400)
            elif courier_partner == 'Ekart':
                return Response({'error': 'Ekart parser coming soon!'}, status=400)
            else:
                return Response({'error': f'Parser for {courier_partner} not found.'}, status=400)

            if parsed_invoice_date_str:
                try:
                    invoice_date = datetime.strptime(parsed_invoice_date_str, '%d/%m/%Y').date()
                except ValueError:
                    pass

            if not invoice_number:
                invoice_number = f"INV-{int(time.time())}"

            if not rows:
                return Response({'error': 'No valid AWBs or costs found in this PDF.'}, status=400)

            # Get invoice-level FSC and CAF
            grand_total = summary_dict.get('grand_total', Decimal('0'))
            fuel_total = summary_dict.get('fuel_total', Decimal('0'))
            caf_total = summary_dict.get('caf_total', Decimal('0'))

            sum_amounts = sum(r['forward_cost'] for r in rows)
            
            # If no grand total was extracted from the PDF, fall back to calculating from rows
            if not grand_total or grand_total <= 0:
                net_calc = sum_amounts + fuel_total + caf_total
                grand_total = (net_calc * Decimal('1.18')).quantize(Decimal('0.01'))

            fsc_ratio = fuel_total / sum_amounts if sum_amounts > 0 else Decimal('0')
            caf_ratio = caf_total / sum_amounts if sum_amounts > 0 else Decimal('0')

            from core.models.delivery import CourierInvoiceLine
            from core.services.discrepancy_engine import analyse_invoice

            with transaction.atomic():
                # 1. Create or Update the FreightInvoice record
                invoice, created = FreightInvoice.objects.get_or_create(
                    org_id=org_id,
                    invoice_number=invoice_number,
                    defaults={
                        'courier_partner': courier_partner,
                        'invoice_date': invoice_date,
                        'total_amount': grand_total,
                    }
                )

                # Attach file
                file_obj.seek(0)
                invoice.invoice_file.save(file_obj.name, file_obj, save=False)
                
                if not created:
                    # Wipe existing CourierInvoiceLines on re-upload
                    CourierInvoiceLine.objects.filter(freight_invoice=invoice).delete()
                    invoice.total_amount = grand_total
                    invoice.invoice_date = invoice_date
                invoice.save()

                # 2. Build AWB -> Shipment map
                awb_list = set()
                for r in rows:
                    awb_list.add(r['awb'])
                    if r['awb'].upper().endswith('R'):
                        awb_list.add(r['awb'][:-1])

                shipments = Shipment.objects.filter(org_id=org_id, awb_number__in=awb_list).select_related('order')
                shipment_map = {s.awb_number: s for s in shipments}

                line_objects = []
                type_counts = {'Forward': 0, 'RTO': 0, 'Return': 0, 'Exchange': 0, 'Credit': 0}
                unmatched = 0

                for row in rows:
                    awb = row['awb']
                    shipment = shipment_map.get(awb)
                    
                    if not shipment and awb.upper().endswith('R'):
                        shipment = shipment_map.get(awb[:-1])

                    if not shipment:
                        unmatched += 1

                    row_amount = row['forward_cost']
                    awb_upper = awb.upper()
                    
                    if awb_upper.endswith('R') or awb_upper.startswith('R'):
                        stype = 'RTO'
                    elif row['is_return']:
                        stype = 'RTO'
                    elif row_amount < 0:
                        stype = 'Credit'
                    else:
                        stype = 'Forward'

                    # Fallback check if it's Return/Forward but shipment/order is RTO status
                    if stype in ('Return', 'Forward') and shipment and shipment.order:
                        from core.models.constants import RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES
                        combined_rto_statuses = RTO_TRANSIT_STATUSES + RTO_DELIVERED_STATUSES
                        if shipment.order.current_status in combined_rto_statuses:
                            stype = 'RTO'

                    type_counts[stype] = type_counts.get(stype, 0) + 1

                    # Distribute FSC and CAF proportionally
                    fsc = (row_amount * fsc_ratio).quantize(Decimal('0.01'))
                    caf = (row_amount * caf_ratio).quantize(Decimal('0.01'))
                    total_billed = row_amount + fsc + caf

                    line_objects.append(CourierInvoiceLine(
                        org_id=org_id,
                        freight_invoice=invoice,
                        shipment=shipment,
                        awb_number=awb,
                        courier_ref="",
                        product_code=row['type'],
                        origin_area="",
                        dest_area=row['dest'],
                        dest_pincode="",
                        commodity="",
                        actual_weight_kg=Decimal('0.0'),
                        charged_weight_kg=row['chrg_wt'],
                        expected_weight_kg=Decimal('0.5'),
                        pieces=1,
                        freight=row_amount,
                        fsc=fsc,
                        caf=caf,
                        fod_charge=Decimal('0.0'),
                        declared_value_charge=Decimal('0.0'),
                        idc_charge=Decimal('0.0'),
                        misc_charges=Decimal('0.0'),
                        total_billed=total_billed,
                        shipment_type=stype,
                    ))

                # 3. Bulk save lines
                CourierInvoiceLine.objects.bulk_create(line_objects, ignore_conflicts=True)

                # 4. Run discrepancy analysis
                disc_stats = analyse_invoice(invoice.id, org_id)

                # Calculate and save product type
                cod_count = invoice.lines.filter(shipment__payment_type__in=['COD', 'Partially Paid']).count()
                matched_count = invoice.lines.exclude(shipment=None).count()
                if matched_count > 0:
                    invoice.product_type = 'COD' if (cod_count / matched_count > 0.5) else 'Prepaid'
                else:
                    # Fallback if no shipments matched: check product codes
                    cod_code_count = invoice.lines.filter(Q(product_code__icontains='C') | Q(product_code__icontains='COD')).count()
                    total_count = invoice.lines.count()
                    invoice.product_type = 'COD' if (total_count > 0 and cod_code_count / total_count > 0.5) else 'Prepaid'
                invoice.save(update_fields=['product_type'])

            return Response({
                'invoice_id': invoice.id,
                'invoice_number': invoice.invoice_number,
                'courier_partner': courier_partner,
                'total_rows': len(rows),
                'forward': type_counts.get('Forward', 0),
                'rto': type_counts.get('RTO', 0),
                'returns': type_counts.get('Return', 0),
                'exchanges': type_counts.get('Exchange', 0),
                'credits': type_counts.get('Credit', 0),
                'unmatched_awbs': unmatched,
                'discrepancies': disc_stats,
            })

        except Exception as e:
            logger.error(f"Error parsing invoice: {e}")
            return Response({'error': str(e)}, status=500)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


# ==============================================================================
# 10. FREIGHT INVOICE LIST VIEW
# ==============================================================================
class FreightInvoiceListView(APIView):
    """
    List freight invoices with optional filtering and pagination.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        # Filters
        courier = request.query_params.get('courier')
        status = request.query_params.get('status')
        start = request.query_params.get('start_date')
        end = request.query_params.get('end_date')
        
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 50))
        offset = (page - 1) * limit

        # Update statuses for overdue invoices
        check_freight_invoices(org_id)

        qs = FreightInvoice.objects.filter(org_id=org_id)
        if courier:
            qs = qs.filter(courier_partner__iexact=courier)
        if status:
            qs = qs.filter(status__iexact=status)
        if start:
            qs = qs.filter(invoice_date__gte=parse_date(start))
        if end:
            qs = qs.filter(invoice_date__lte=parse_date(end))

        total_count = qs.count()
        invoices = qs.order_by('-invoice_date')[offset:offset + limit]

        # Summary
        summary_agg = qs.aggregate(
            agg_total_amount=Coalesce(Sum('total_amount'), Decimal('0.0')),
            overdue_amount=Coalesce(Sum('total_amount', filter=Q(status='Overdue')), Decimal('0.0')),
            pending_count=Count('id', filter=Q(status='Pending')),
            overdue_count=Count('id', filter=Q(status='Overdue'))
        )
        
        summary = {
            'total_amount': summary_agg['agg_total_amount'],
            'overdue_amount': summary_agg['overdue_amount'],
            'pending_count': summary_agg['pending_count'],
            'overdue_count': summary_agg['overdue_count'],
        }

        data = []
        for inv in invoices:
            product_type = inv.product_type
            if not product_type:
                cod_count = inv.lines.filter(shipment__payment_type__in=['COD', 'Partially Paid']).count()
                matched_count = inv.lines.exclude(shipment=None).count()
                if matched_count > 0:
                    product_type = 'COD' if (cod_count / matched_count > 0.5) else 'Prepaid'
                else:
                    # Fallback if no shipments matched: check product codes
                    cod_code_count = inv.lines.filter(Q(product_code__icontains='C') | Q(product_code__icontains='COD')).count()
                    total_count = inv.lines.count()
                    product_type = 'COD' if (total_count > 0 and cod_code_count / total_count > 0.5) else 'Prepaid'
                inv.product_type = product_type
                inv.save(update_fields=['product_type'])
            data.append({
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'courier_partner': inv.courier_partner,
                'invoice_date': str(inv.invoice_date),
                'due_date': str(inv.due_date),
                'total_amount': float(inv.total_amount),
                'status': inv.status,
                'paid_date': str(inv.paid_date) if inv.paid_date else None,
                'product_type': product_type,
            })

        return Response({
            'invoices': data,
            'count': total_count,
            'page': page,
            'limit': limit,
            'summary': {
                'total_amount': float(summary['total_amount']),
                'overdue_amount': float(summary['overdue_amount']),
                'pending_count': summary['pending_count'],
                'overdue_count': summary['overdue_count'],
            }
        })


# ==============================================================================
# 9.5. FREIGHT INVOICE SEIZURE VIEW (The Nuclear Option)
# ==============================================================================
class InvoiceSeizeView(APIView):
    """
    Manually trigger COD Seizure for an invoice that is > 60 days overdue.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, invoice_id):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        try:
            invoice = FreightInvoice.objects.get(id=invoice_id, org_id=org_id)
        except FreightInvoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=404)

        if invoice.status == 'Paid':
            return Response({'error': 'Invoice is already paid'}, status=400)

        # Check if 60 days overdue
        from datetime import date
        today = date.today()
        days_overdue = (today - invoice.invoice_date).days
        if days_overdue <= 60:
            return Response({'error': f'Invoice is only {days_overdue} days old. Must be > 60 days to seize COD.'}, status=400)

        # Seize COD funds
        pending_cod = CODRemittance.objects.filter(
            shipment__org_id=org_id,
            shipment__courier_partner=invoice.courier_partner,
            status__in=['Pending', 'Overdue']
        )
        
        amount_to_recover = invoice.total_amount
        recovered = Decimal('0.0')
        seized_count = 0

        for cod in pending_cod:
            if amount_to_recover <= 0:
                break
                
            available = cod.expected_amount
            cod.status = 'Seized'
            cod.save(update_fields=['status'])
            
            amount_to_recover -= available
            recovered += available
            seized_count += 1

        # Update invoice
        if amount_to_recover <= 0:
            invoice.status = 'Seized'
            invoice.save(update_fields=['status'])

        return Response({
            'message': f'Successfully seized {seized_count} COD remittances.',
            'recovered_amount': float(recovered),
            'remaining_debt': float(max(amount_to_recover, Decimal('0.0'))),
            'invoice_status': invoice.status
        })


# ==============================================================================
# 10. DISPUTE LIST VIEW
# ==============================================================================
class DisputeListView(APIView):
    """
    List shipment disputes with optional filtering and pagination.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        status = request.query_params.get('status')
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 50))
        offset = (page - 1) * limit

        qs = ShipmentDispute.objects.filter(org_id=org_id).select_related('shipment', 'freight_invoice')
        if status:
            qs = qs.filter(status__iexact=status)

        total_count = qs.count()
        disputes = qs.order_by('-logged_date')[offset:offset + limit]

        summary = qs.aggregate(
            total_disputed=Coalesce(Sum('disputed_amount'), Decimal('0.0')),
            total_recovered=Coalesce(Sum('credit_note_amount'), Decimal('0.0')),
            open_count=Count('id', filter=Q(status='Open'))
        )

        data = []
        for d in disputes:
            awb     = d.shipment.awb_number    if d.shipment else '—'
            courier = d.shipment.courier_partner if d.shipment else '—'
            data.append({
                'id':                d.id,
                'awb_number':        awb,
                'courier':           courier,
                'invoice_number':    d.freight_invoice.invoice_number,
                'disputed_amount':   float(d.disputed_amount),
                'reason':            d.reason,
                'status':            d.status,
                'credit_note_amount':float(d.credit_note_amount),
                'logged_date':       str(d.logged_date.date()),
                'resolved_date':     str(d.resolved_date.date()) if d.resolved_date else None,
            })

        return Response({
            'disputes': data,
            'count': total_count,
            'page': page,
            'limit': limit,
            'summary': {
                'total_disputed': float(summary['total_disputed']),
                'total_recovered': float(summary['total_recovered']),
                'open_count': summary['open_count'],
            }
        })

class FreightInvoiceDetailView(APIView):
    """
    Handle individual freight invoice actions.
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)
        try:
            invoice = FreightInvoice.objects.get(id=pk, org_id=org_id)
            invoice.delete()
            return Response({'message': 'Invoice deleted successfully'})
        except FreightInvoice.DoesNotExist:
            return Response({'error': 'Invoice not found'}, status=404)

class DisputeExportView(APIView):
    """
    Export all disputes for the organization as a CSV file.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organization linked'}, status=400)

        disputes = ShipmentDispute.objects.filter(org_id=org_id).select_related(
            'shipment', 'freight_invoice_line', 'freight_invoice_line__freight_invoice'
        ).order_by('-logged_date')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="disputes_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'AWB Number',
            'Invoice #',
            'Logged Date',
            'Reason',
            'Disputed Amount',
            'Recovered Amount',
            'Status'
        ])

        for dispute in disputes:
            awb = dispute.shipment.awb_number if dispute.shipment else ''
            invoice = dispute.freight_invoice_line.freight_invoice.invoice_number if dispute.freight_invoice_line and dispute.freight_invoice_line.freight_invoice else ''
            
            writer.writerow([
                awb,
                invoice,
                dispute.logged_date.strftime('%Y-%m-%d') if dispute.logged_date else '',
                dispute.reason,
                dispute.disputed_amount,
                dispute.credit_note_amount,
                dispute.status
            ])

        return response
