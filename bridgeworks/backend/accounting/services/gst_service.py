from decimal import Decimal
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import Sum
from accounting.models import GSTSettings, GSTTransaction, GSTSummary


def _parse_date(value):
    """Safely coerce a value to an aware datetime.
    Handles: datetime objects, ISO strings (from Shopify), and None.
    """
    if value is None:
        return timezone.now()
    if hasattr(value, 'month'):  # already a datetime
        if timezone.is_naive(value):
            return timezone.make_aware(value)
        return value
    # Try parsing as ISO string
    try:
        dt = parse_datetime(str(value))
        if dt is None:
            return timezone.now()
        if timezone.is_naive(dt):
            return timezone.make_aware(dt)
        return dt
    except Exception:
        return timezone.now()


class GSTService:
    @staticmethod
    def get_or_create_settings(org_id):
        settings, created = GSTSettings.objects.get_or_create(
            org_id=org_id,
            defaults={
                'gstin': '',
                'legal_name': 'Test Company',
                'state': 'Delhi',
                'registration_type': 'regular',
                'filing_frequency': 'monthly',
                'default_gst_rate': Decimal('18.00')
            }
        )
        return settings

    @staticmethod
    def captureSaleGST(order):
        if not order or not order.org_id:
            return

        # Delete any existing GST transactions for this sale to ensure idempotency
        GSTTransaction.objects.filter(org_id=order.org_id, transaction_id__startswith=f"sale_{order.id}_").delete()

        total_price = Decimal(str(order.total_price or order.subtotal_price or 0.00))
        if total_price <= 0:
            return

        settings = GSTService.get_or_create_settings(order.org_id)
        default_rate = Decimal(str(settings.default_gst_rate))
        rate_fraction = default_rate / Decimal('100.00')

        # Taxable amount = Inclusive total / (1 + rate)
        taxable_amount = total_price / (Decimal('1.00') + rate_fraction)
        gst_amount = total_price - taxable_amount

        # Determine CGST/SGST vs IGST
        order_state = (order.shipping_state or '').strip().lower()
        settings_state = (settings.state or '').strip().lower()

        date = _parse_date(order.created_at)

        if order_state == settings_state and settings_state != '':
            # Intra-state: CGST (50%) + SGST (50%)
            half_rate = default_rate / Decimal('2.00')
            half_gst = gst_amount / Decimal('2.00')

            GSTTransaction.objects.create(
                org_id=order.org_id,
                transaction_id=f"sale_{order.id}_cgst",
                reference_number=f"ORD-{order.order_number or order.id}",
                transaction_type=GSTTransaction.TransactionType.SALE,
                source_module=GSTTransaction.SourceModule.SALES,
                taxable_amount=taxable_amount,
                gst_rate=half_rate,
                gst_amount=half_gst,
                gst_type=GSTTransaction.GSTType.CGST,
                status=GSTTransaction.Status.RECORDED,
                created_at=date
            )
            GSTTransaction.objects.create(
                org_id=order.org_id,
                transaction_id=f"sale_{order.id}_sgst",
                reference_number=f"ORD-{order.order_number or order.id}",
                transaction_type=GSTTransaction.TransactionType.SALE,
                source_module=GSTTransaction.SourceModule.SALES,
                taxable_amount=taxable_amount,
                gst_rate=half_rate,
                gst_amount=half_gst,
                gst_type=GSTTransaction.GSTType.SGST,
                status=GSTTransaction.Status.RECORDED,
                created_at=date
            )
        else:
            # Inter-state: IGST (100%)
            GSTTransaction.objects.create(
                org_id=order.org_id,
                transaction_id=f"sale_{order.id}_igst",
                reference_number=f"ORD-{order.order_number or order.id}",
                transaction_type=GSTTransaction.TransactionType.SALE,
                source_module=GSTTransaction.SourceModule.SALES,
                taxable_amount=taxable_amount,
                gst_rate=default_rate,
                gst_amount=gst_amount,
                gst_type=GSTTransaction.GSTType.IGST,
                status=GSTTransaction.Status.RECORDED,
                created_at=date
            )

        GSTService.refreshDashboardMetrics(order.org_id, date.month, date.year)

    @staticmethod
    def capturePurchaseGST(invoice):
        if not invoice or not invoice.org_id or invoice.type != 'purchase':
            return

        # Delete any existing GST transactions for this purchase to ensure idempotency
        GSTTransaction.objects.filter(org_id=invoice.org_id, transaction_id__startswith=f"purchase_{invoice.id}_").delete()

        amount = Decimal(str(invoice.amount or 0.00))
        if amount <= 0:
            return

        settings = GSTService.get_or_create_settings(invoice.org_id)
        default_rate = Decimal(str(settings.default_gst_rate))
        rate_fraction = default_rate / Decimal('100.00')

        taxable_amount = amount / (Decimal('1.00') + rate_fraction)
        gst_amount = amount - taxable_amount

        # For purchases, default to local CGST/SGST split
        half_rate = default_rate / Decimal('2.00')
        half_gst = gst_amount / Decimal('2.00')

        date = _parse_date(invoice.created_at)

        GSTTransaction.objects.create(
            org_id=invoice.org_id,
            transaction_id=f"purchase_{invoice.id}_cgst",
            reference_number=f"BILL-{invoice.id}",
            transaction_type=GSTTransaction.TransactionType.PURCHASE,
            source_module=GSTTransaction.SourceModule.PURCHASES,
            taxable_amount=taxable_amount,
            gst_rate=half_rate,
            gst_amount=half_gst,
            gst_type=GSTTransaction.GSTType.CGST,
            status=GSTTransaction.Status.RECORDED,
            created_at=date
        )
        GSTTransaction.objects.create(
            org_id=invoice.org_id,
            transaction_id=f"purchase_{invoice.id}_sgst",
            reference_number=f"BILL-{invoice.id}",
            transaction_type=GSTTransaction.TransactionType.PURCHASE,
            source_module=GSTTransaction.SourceModule.PURCHASES,
            taxable_amount=taxable_amount,
            gst_rate=half_rate,
            gst_amount=half_gst,
            gst_type=GSTTransaction.GSTType.SGST,
            status=GSTTransaction.Status.RECORDED,
            created_at=date
        )

        GSTService.refreshDashboardMetrics(invoice.org_id, date.month, date.year)

    @staticmethod
    def captureExpenseGST(expense):
        if not expense or not expense.org_id:
            return

        # Delete any existing GST transactions for this expense to ensure idempotency
        GSTTransaction.objects.filter(org_id=expense.org_id, transaction_id__startswith=f"expense_{expense.id}_").delete()

        amount = Decimal(str(expense.amount or 0.00))
        if amount <= 0:
            return

        settings = GSTService.get_or_create_settings(expense.org_id)
        default_rate = Decimal(str(settings.default_gst_rate))
        rate_fraction = default_rate / Decimal('100.00')

        taxable_amount = amount / (Decimal('1.00') + rate_fraction)
        gst_amount = amount - taxable_amount

        # For expenses, default to local CGST/SGST split
        half_rate = default_rate / Decimal('2.00')
        half_gst = gst_amount / Decimal('2.00')

        # Use expense date or current time
        txn_date = timezone.now()
        if expense.date:
            txn_date = timezone.make_aware(timezone.datetime.combine(expense.date, timezone.datetime.min.time()))

        GSTTransaction.objects.create(
            org_id=expense.org_id,
            transaction_id=f"expense_{expense.id}_cgst",
            reference_number=f"EXP-{expense.id}",
            transaction_type=GSTTransaction.TransactionType.EXPENSE,
            source_module=GSTTransaction.SourceModule.EXPENSES,
            taxable_amount=taxable_amount,
            gst_rate=half_rate,
            gst_amount=half_gst,
            gst_type=GSTTransaction.GSTType.CGST,
            status=GSTTransaction.Status.RECORDED,
            created_at=txn_date
        )
        GSTTransaction.objects.create(
            org_id=expense.org_id,
            transaction_id=f"expense_{expense.id}_sgst",
            reference_number=f"EXP-{expense.id}",
            transaction_type=GSTTransaction.TransactionType.EXPENSE,
            source_module=GSTTransaction.SourceModule.EXPENSES,
            taxable_amount=taxable_amount,
            gst_rate=half_rate,
            gst_amount=half_gst,
            gst_type=GSTTransaction.GSTType.SGST,
            status=GSTTransaction.Status.RECORDED,
            created_at=txn_date
        )

        GSTService.refreshDashboardMetrics(expense.org_id, txn_date.month, txn_date.year)

    @staticmethod
    def calculateInputGST(org_id, month=None, year=None):
        qs = GSTTransaction.objects.filter(
            org_id=org_id,
            transaction_type__in=[GSTTransaction.TransactionType.PURCHASE, GSTTransaction.TransactionType.EXPENSE]
        )
        if month:
            qs = qs.filter(created_at__month=month)
        if year:
            qs = qs.filter(created_at__year=year)
        return qs.aggregate(s=Sum('gst_amount'))['s'] or Decimal('0.00')

    @staticmethod
    def calculateOutputGST(org_id, month=None, year=None):
        qs = GSTTransaction.objects.filter(
            org_id=org_id,
            transaction_type=GSTTransaction.TransactionType.SALE
        )
        if month:
            qs = qs.filter(created_at__month=month)
        if year:
            qs = qs.filter(created_at__year=year)
        return qs.aggregate(s=Sum('gst_amount'))['s'] or Decimal('0.00')

    @staticmethod
    def calculateNetGST(org_id, month=None, year=None):
        output_gst = GSTService.calculateOutputGST(org_id, month, year)
        input_gst = GSTService.calculateInputGST(org_id, month, year)
        return output_gst - input_gst

    @staticmethod
    def refreshDashboardMetrics(org_id, month, year):
        input_gst = GSTService.calculateInputGST(org_id, month, year)
        output_gst = GSTService.calculateOutputGST(org_id, month, year)
        net_gst = output_gst - input_gst

        GSTSummary.objects.update_or_create(
            org_id=org_id,
            month=month,
            year=year,
            defaults={
                'input_gst': input_gst,
                'output_gst': output_gst,
                'net_gst': net_gst
            }
        )
