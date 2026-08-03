import logging
import pandas as pd
from datetime import datetime, date, timedelta
from decimal import Decimal
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db import transaction
from django.db.models import Q, Sum, Count, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import Order
from core.models.delivery import PrepaidRemittance, PaymentGatewayFeeRule
from core.permissions import HasModulePermission
from core.views_delivery_analytics import _get_org_id, _parse_dates

# Accounting models
from accounting.models import Ledger, JournalEntry, JournalItem, Account, Outstanding

logger = logging.getLogger(__name__)

class PrepaidRemittanceListView(APIView):
    """
    GET /api/finance/prepaid-remittance/
    Returns prepaid remittance records with filters and KPIs.
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
        gateway_filter = request.query_params.get('gateway', '').strip()
        search_query = request.query_params.get('q', '').strip()
        status_filter = request.query_params.get('status', '').strip()

        # Update status of pending remittances to Overdue in-place if they passed expected date
        today = timezone.now().date()
        PrepaidRemittance.objects.filter(
            order__org_id=org_id,
            status='Pending',
            expected_settlement_date__lt=today
        ).update(status='Overdue')

        qs = PrepaidRemittance.objects.filter(
            order__org_id=org_id
        ).select_related('order').order_by('-order__created_at')

        if search_query:
            qs = qs.filter(
                Q(order_number__icontains=search_query) |
                Q(order__shopify_id__icontains=search_query)
            )

        if start_date:
            qs = qs.filter(order__created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(order__created_at__date__lte=end_date)
        if gateway_filter:
            qs = qs.filter(gateway_name__iexact=gateway_filter)
        if status_filter:
            qs = qs.filter(status=status_filter)

        total_count = qs.count()

        # Summary KPIs
        kpis = qs.aggregate(
            total_gross=Coalesce(Sum('gross_amount'), Value(0), output_field=DecimalField()),
            total_net=Coalesce(Sum('net_amount'), Value(0), output_field=DecimalField()),
            total_rec=Coalesce(Sum('received_amount'), Value(0), output_field=DecimalField()),
            pending_cnt=Count('id', filter=Q(status__in=['Pending', 'Overdue'])),
            overdue_cnt=Count('id', filter=Q(status='Overdue'))
        )

        paginated_qs = qs[offset:offset + limit]

        items_data = []
        for item in paginated_qs:
            if item.actual_settlement_date:
                delay = (item.actual_settlement_date - item.expected_settlement_date).days
            elif item.expected_settlement_date:
                delay = (today - item.expected_settlement_date).days
            else:
                delay = 0
            delay_days = max(delay, 0)

            items_data.append({
                'id': item.id,
                'order_number': item.order_number or '-',
                'shopify_order_id': item.order.shopify_id if item.order else '-',
                'gateway': item.gateway_name or '-',
                'order_date': str(item.order.created_at.date()) if item.order and item.order.created_at else None,
                'gross_amount': float(item.gross_amount),
                'gateway_fee': float(item.gateway_fee),
                'net_remittance': float(item.net_amount),
                'received_amount': float(item.received_amount),
                'expected_remittance_date': str(item.expected_settlement_date) if item.expected_settlement_date else None,
                'actual_remittance_date': str(item.actual_settlement_date) if item.actual_settlement_date else None,
                'remittance_status': item.status,
                'delay_days': delay_days,
            })

        return Response({
            'orders': items_data,
            'count': total_count,
            'page': page,
            'limit': limit,
            'summary': {
                'total_cod_value': float(kpis['total_gross']), # Gross Amount mapped to total_cod_value for matching frontend KPI exactly
                'total_expected_cost': float(kpis['total_gross'] - kpis['total_net']), # Fee mapped to total_expected_cost
                'net_expected_remittance': float(kpis['total_net']),
                'total_received': float(kpis['total_rec']),
                'pending_count': kpis['pending_cnt'],
                'overdue_count': kpis['overdue_cnt'],
            }
        })


class PrepaidRemittanceWeeklySummaryView(APIView):
    """
    GET /api/finance/prepaid-remittance/weekly-summary/
    Returns weekly group summary for prepaid remittances.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:cost_management:view'
    }

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        gateway_filter = request.query_params.get('gateway', '').strip()
        six_months_ago = timezone.now().date() - timedelta(days=180)

        qs = PrepaidRemittance.objects.filter(
            order__org_id=org_id,
            order__created_at__date__gte=six_months_ago
        ).select_related('order')

        if gateway_filter:
            qs = qs.filter(gateway_name__iexact=gateway_filter)

        summary_data = {}
        for r in qs:
            order_date = r.order.created_at
            if not order_date:
                continue
            order_date = order_date.date()
            month_key = order_date.strftime("%B %Y")
            day = order_date.day

            if month_key not in summary_data:
                summary_data[month_key] = {
                    "Week 1 (1-7)": Decimal('0'),
                    "Week 2 (8-14)": Decimal('0'),
                    "Week 3 (15-21)": Decimal('0'),
                    "Week 4 (22+)": Decimal('0'),
                    "Total": Decimal('0')
                }

            week_label = "Week 4 (22+)"
            if day <= 7:
                week_label = "Week 1 (1-7)"
            elif day <= 14:
                week_label = "Week 2 (8-14)"
            elif day <= 21:
                week_label = "Week 3 (15-21)"

            summary_data[month_key][week_label] += r.net_amount
            summary_data[month_key]["Total"] += r.net_amount

        final_list = []
        for month, weeks in summary_data.items():
            row = {"month": month}
            row.update({k: float(v) for k, v in weeks.items()})
            final_list.append(row)

        final_list.sort(key=lambda x: datetime.strptime(x['month'], "%B %Y"), reverse=True)

        return Response({
            'summary': final_list,
            'gateway': gateway_filter
        })


class PrepaidRemittanceUploadView(APIView):
    """
    POST /api/finance/prepaid-remittance/upload-excel/
    Accepts uploaded settlement report files (CSV or Excel).
    Required columns: Order ID, Settlement Amount, Gateway, Settlement Date
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:cost_management:edit'
    }

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        file = request.FILES.get('file')
        start_date_str = request.data.get('start_date')
        end_date_str = request.data.get('end_date')

        if not file or not start_date_str or not end_date_str:
            return Response({'error': 'File, start_date, and end_date are required'}, status=400)

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'Invalid date format. Use YYYY-MM-DD.'}, status=400)

        filename = file.name.lower()
        try:
            if filename.endswith('.xlsb'):
                df = pd.read_excel(file, engine='pyxlsb')
            elif filename.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file)
            else:
                df = pd.read_csv(file)
        except Exception as e:
            logger.error(f"Error parsing Prepaid Remittance report: {e}")
            return Response({'error': 'Failed to parse file. Ensure it is a valid CSV or Excel file.'}, status=400)

        # Standardize column header names
        df.columns = [str(col).strip().lower() for col in df.columns]

        # Look for expected columns: Order ID, Settlement Amount, Gateway, Settlement Date
        order_col = None
        amt_col = None
        gw_col = None
        date_col = None

        for col in df.columns:
            if 'order id' in col or 'orderid' in col or 'order_id' in col or 'order' in col or 'order number' in col or 'order_number' in col:
                order_col = col
            if 'settlement amount' in col or 'amount' in col or 'settlement_amount' in col or 'net' in col or 'net_amount' in col:
                amt_col = col
            if 'gateway' in col or 'payment gateway' in col or 'payment_gateway' in col:
                gw_col = col
            if 'settlement date' in col or 'date' in col or 'settlement_date' in col:
                date_col = col

        if not order_col or not amt_col:
            return Response({
                'error': f"Required columns 'Order ID' and 'Settlement Amount' not found. Available columns: {list(df.columns)}"
            }, status=400)

        df = df.dropna(subset=[order_col])
        matched = []
        mismatched = []

        # Gather order numbers from file
        order_num_list = df[order_col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().tolist()

        # Batch query all PrepaidRemittances matching order numbers or shopify IDs
        remittances = PrepaidRemittance.objects.filter(
            order__org_id=org_id,
            order_number__in=order_num_list
        ).select_related('order')

        rem_map = {r.order_number.strip(): r for r in remittances}

        for _, row in df.iterrows():
            order_id_raw = str(row[order_col]).replace('.0', '').strip()
            if not order_id_raw or order_id_raw.lower() == 'nan':
                continue

            raw_amt = row[amt_col]
            try:
                amt = float(raw_amt)
            except (ValueError, TypeError):
                amt = 0.0

            rem = rem_map.get(order_id_raw)
            if not rem:
                mismatched.append({
                    'order_number': order_id_raw,
                    'amount': amt,
                    'reason': 'Order remittance record not found in system'
                })
                continue

            order_date = rem.order.created_at.date() if rem.order and rem.order.created_at else None

            if order_date and not (start_date <= order_date <= end_date):
                mismatched.append({
                    'order_number': order_id_raw,
                    'order_date': str(order_date),
                    'amount': amt,
                    'reason': f"Order date {order_date} is outside selected range"
                })
                continue

            matched.append({
                'order_number': order_id_raw,
                'order_date': str(order_date),
                'amount': amt,
                'gateway': str(row.get(gw_col, rem.gateway_name or '')).strip(),
                'settlement_date': str(row.get(date_col, date.today().strftime('%Y-%m-%d'))).strip()
            })

        return Response({
            'total_processed': len(order_num_list),
            'matched': matched,
            'mismatched': mismatched
        })


class PrepaidRemittanceConfirmView(APIView):
    """
    POST /api/finance/prepaid-remittance/confirm/
    Saves the received amount and updates the status of the confirmed matched remittances.
    Also integrates with double-entry accounting ledger to create Journal Entries.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:cost_management:edit'
    }

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        remittances_data = request.data.get('remittances', [])
        if not remittances_data:
            return Response({'error': 'No remittances data provided'}, status=400)

        order_numbers = [item['order_number'] for item in remittances_data if 'order_number' in item]
        remittances = PrepaidRemittance.objects.filter(
            order__org_id=org_id,
            order_number__in=order_numbers
        ).select_related('order')

        rem_map = {r.order_number: r for r in remittances}
        updated_count = 0

        with transaction.atomic():
            for item in remittances_data:
                order_num = item.get('order_number')
                amount = Decimal(str(item.get('amount', 0)))
                settle_date_str = item.get('settlement_date')

                try:
                    settle_date = datetime.strptime(settle_date_str.split(' ')[0], '%Y-%m-%d').date()
                except Exception:
                    settle_date = date.today()

                rem = rem_map.get(order_num)
                if not rem:
                    continue

                rem.received_amount = amount
                rem.actual_settlement_date = settle_date
                rem.status = 'Received'
                rem.save()

                # --- PHASE 12: DOUBLE-ENTRY ACCOUNTING LEDGER INTEGRATION ---
                gateway_label = rem.gateway_name or 'Prepaid'
                
                # 1. Resolve Settlement Account & Ledger
                settlement_account_name = f"{gateway_label} Settlement"
                settlement_account, _ = Account.objects.get_or_create(
                    org_id=org_id,
                    name=settlement_account_name,
                    defaults={'type': Account.AccountType.SETTLEMENT}
                )
                bank_ledger = settlement_account.get_or_create_ledger()

                # 2. Resolve Settlement Receivable Ledger (usually accounts receivable)
                receivable_ledger, _ = Ledger.objects.get_or_create(
                    org_id=org_id,
                    name='Accounts Receivable',
                    defaults={'type': Ledger.LedgerType.ASSET}
                )

                # 3. Create Journal Entry
                journal = JournalEntry.objects.create(
                    org_id=org_id,
                    date=settle_date,
                    description=f"Prepaid Remittance Settlement for Order {order_num} via {gateway_label}"
                )

                # Debit: Bank (Settlement Account Ledger) -> Received Net Amount
                JournalItem.objects.create(
                    org_id=org_id,
                    entry=journal,
                    ledger=bank_ledger,
                    debit=amount,
                    credit=0,
                    notes=f"Order {order_num} Settlement"
                )

                # Credit: Settlement Receivable Ledger -> Received Net Amount
                JournalItem.objects.create(
                    org_id=org_id,
                    entry=journal,
                    ledger=receivable_ledger,
                    debit=0,
                    credit=amount,
                    notes=f"Order {order_num} Settlement"
                )

                updated_count += 1

        return Response({
            'message': f"Successfully marked {updated_count} prepaid remittances as received and generated accounting journals."
        })


class PaymentGatewayFeeRuleView(APIView):
    """
    GET /api/finance/gateway-fee-rules/
    POST /api/finance/gateway-fee-rules/
    View and edit payment gateway fee rules.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        rules = PaymentGatewayFeeRule.objects.filter(org_id=org_id)
        # Seed defaults if empty
        if not rules.exists():
            defaults = [
                ('Razorpay', 'percentage', 2.0, 2),
                ('PayU', 'percentage', 2.2, 2),
                ('PhonePe', 'percentage', 1.8, 2),
                ('Easebuzz', 'percentage', 2.0, 2),
                ('Cashfree', 'percentage', 1.75, 1),
                ('GoKwik', 'percentage', 2.0, 2),
                ('FlexyPe', 'percentage', 2.0, 2),
                ('Shopify Payments', 'percentage', 2.0, 3),
            ]
            rules_to_create = []
            for gw, f_type, val, days in defaults:
                rules_to_create.append(PaymentGatewayFeeRule(
                    org_id=org_id,
                    gateway_name=gw,
                    fee_type=f_type,
                    fee_value=Decimal(str(val)),
                    settlement_days=days,
                    active=True
                ))
            PaymentGatewayFeeRule.objects.bulk_create(rules_to_create)
            rules = PaymentGatewayFeeRule.objects.filter(org_id=org_id)
        else:
            # Explicitly ensure FlexyPe exists
            if not rules.filter(gateway_name__iexact='FlexyPe').exists():
                PaymentGatewayFeeRule.objects.create(
                    org_id=org_id,
                    gateway_name='FlexyPe',
                    fee_type='percentage',
                    fee_value=Decimal('2.0'),
                    settlement_days=2,
                    active=True
                )
                rules = PaymentGatewayFeeRule.objects.filter(org_id=org_id)

        data = []
        for r in rules:
            data.append({
                'id': r.id,
                'gateway_name': r.gateway_name,
                'fee_type': r.fee_type,
                'fee_value': float(r.fee_value),
                'settlement_days': r.settlement_days,
                'active': r.active
            })
        return Response(data)

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        rules_data = request.data.get('rules', [])
        if not isinstance(rules_data, list):
            return Response({'error': 'Invalid rules format'}, status=400)

        with transaction.atomic():
            sent_ids = [rd.get('id') for rd in rules_data if rd.get('id')]
            PaymentGatewayFeeRule.objects.filter(org_id=org_id).exclude(id__in=sent_ids).delete()

            for rd in rules_data:
                rule_id = rd.get('id')
                gateway_name = rd.get('gateway_name')
                fee_type = rd.get('fee_type', 'percentage')
                fee_value = Decimal(str(rd.get('fee_value', 0)))
                settlement_days = int(rd.get('settlement_days', 2))
                active = rd.get('active', True)

                if rule_id:
                    rule = PaymentGatewayFeeRule.objects.filter(id=rule_id, org_id=org_id).first()
                else:
                    rule = PaymentGatewayFeeRule.objects.filter(gateway_name__iexact=gateway_name, org_id=org_id).first()

                if rule:
                    rule.fee_type = fee_type
                    rule.fee_value = fee_value
                    rule.settlement_days = settlement_days
                    rule.active = active
                    rule.save()
                else:
                    PaymentGatewayFeeRule.objects.create(
                        org_id=org_id,
                        gateway_name=gateway_name,
                        fee_type=fee_type,
                        fee_value=fee_value,
                        settlement_days=settlement_days,
                        active=active
                    )

        return Response({'message': 'Payment Gateway Fee Rules updated successfully.'})


class PrepaidRemittanceBackfillView(APIView):
    """
    POST /api/finance/prepaid-remittance/backfill/
    Generates Prepaid Remittance records for all existing paid prepaid orders.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:cost_management:edit'
    }

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        from core.services.delivery_services import sync_prepaid_remittance, derive_payment_type
        from core.models import Order
        from core.models.delivery import PrepaidRemittance

        # 1. Fetch all orders for this org, optimized to prevent statement timeout and memory bloat
        orders = Order.objects.filter(org_id=org_id).only(
            'id', 'order_number', 'shopify_id', 'financial_status',
            'payment_gateway_names', 'total_price', 'tags', 'raw_data', 'created_at'
        ).iterator(chunk_size=1000)

        # 2. Pre-fetch existing remittance order IDs to avoid N+1 queries
        existing_order_ids = set(
            PrepaidRemittance.objects.filter(order__org_id=org_id).values_list('order_id', flat=True)
        )

        created_count = 0
        total_gross = Decimal('0')
        total_net = Decimal('0')

        with transaction.atomic():
            for o in orders:
                if o.id in existing_order_ids:
                    continue

                if derive_payment_type(o) == 'PrePaid' and o.financial_status == 'paid':
                    rem = sync_prepaid_remittance(o)
                    if rem:
                        created_count += 1
                        total_gross += rem.gross_amount
                        total_net += rem.net_amount

        return Response({
            'count': created_count,
            'gross_volume': float(total_gross),
            'expected_settlement': float(total_net)
        })
