"""
ndr_views.py
============
API views for the NDR Escalation Engine.

Endpoints:
- NDRBatchListView: List all escalation batches
- UploadPanelCSVView: Upload BlueDart panel CSV (Escalation 1)
- UploadRawTextView: Paste raw text for AI parsing (Escalation 2+)
- GenerateEscalationExportView: Generate escalation CSV export
"""

import csv
import io
import logging
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from core.models import Order, NDREscalationBatch, ShopCredentials
from core.services.bluedart_service import submit_ndr_action
from core.permissions import HasModulePermission
from core.utils import _get_org_id_or_none

logger = logging.getLogger(__name__)


# ==============================================================================
# 0. BULK NDR ACTION (Blue Dart)
# ==============================================================================
class BulkNDRActionView(APIView):
    """
    Submits a bulk array of Alternative Instructions for Blue Dart NDRs.
    Receives JSON: { "orders": [{"awb": "123", "mobile": "999"}], "action_code": "DT" }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:ndr_action:create'
    }

    def post(self, request):
        orders_data = request.data.get('orders', [])
        action_code = request.data.get('action_code')

        if not orders_data or not isinstance(orders_data, list):
            return Response({'error': 'Valid orders array is required.'}, status=400)
        
        if not action_code:
            return Response({'error': 'action_code is required.'}, status=400)

        # Get user's shop/organization
        shop = getattr(request.user, 'shop_credentials', None)
        if not shop and hasattr(request.user, 'team_settings'):
            shop = request.user.team_settings.organization

        if not shop:
            return Response({'error': 'Organization/Shop not found for this user.'}, status=400)

        results = []
        for item in orders_data:
            awb = item.get('awb')
            mobile = item.get('mobile', '')
            landmark = item.get('landmark', '')
            
            if not awb:
                results.append({
                    'awb': 'Unknown',
                    'success': False,
                    'message': 'AWB missing in request for this order.'
                })
                continue
                
            try:
                resp = submit_ndr_action(shop, awb, action_code, mobile_no=mobile, landmark=landmark)
                results.append({
                    'awb': awb,
                    'success': not resp.get('IsError', True),
                    'message': resp.get('StatusInformation', 'Unknown final status')
                })
            except Exception as e:
                results.append({
                    'awb': awb,
                    'success': False,
                    'message': str(e)
                })

        return Response({'results': results})


# ==============================================================================
# 1. LIST BATCHES
# ==============================================================================
class NDRBatchListView(APIView):
    """List all NDR escalation batches, newest first."""
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:ndr_action:view'
    }

    def get(self, request):
        batches = NDREscalationBatch.objects.all()
        data = []
        for b in batches:
            data.append({
                'id': b.id,
                'batch_name': b.batch_name,
                'escalation_level': b.escalation_level,
                'status': b.status,
                'order_count': b.orders.count(),
                'created_at': b.created_at.isoformat() if b.created_at else None,
                'processed_at': b.processed_at.isoformat() if b.processed_at else None,
                'created_by': b.created_by.username if b.created_by else None,
                'summary': b.summary,
            })
        return Response(data)


# ==============================================================================
# 2. UPLOAD BLUEDART PANEL CSV (Escalation 1)
# ==============================================================================
class UploadPanelCSVView(APIView):
    """
    Upload a BlueDart panel CSV to process escalation results.
    Expects a file upload with the CSV and a batch_id.
    If no batch_id is provided, a new batch is created.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:ndr_action:create'
    }
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response({'error': 'No CSV file provided'}, status=400)

        batch_id = request.data.get('batch_id')

        try:
            if batch_id:
                batch = NDREscalationBatch.objects.get(id=batch_id)
            else:
                # Create a new batch
                batch_name = f"PANEL_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
                batch = NDREscalationBatch.objects.create(
                    batch_name=batch_name,
                    escalation_level=1,
                    status='AWAITING_PANEL_OUTPUT',
                    created_by=request.user if request.user.is_authenticated else None,
                )

            from core.services.ndr_engine import process_bluedart_panel_csv
            summary = process_bluedart_panel_csv(batch.id, csv_file)

            return Response({
                'batch_id': batch.id,
                'batch_name': batch.batch_name,
                'summary': summary,
            })

        except NDREscalationBatch.DoesNotExist:
            return Response({'error': f'Batch {batch_id} not found'}, status=404)
        except Exception as e:
            logger.exception(f"Error processing panel CSV: {e}")
            return Response({'error': str(e)}, status=500)


# ==============================================================================
# 3. UPLOAD RAW TEXT FOR AI PARSING (Escalation 2+)
# ==============================================================================
class UploadRawTextView(APIView):
    """
    Accept raw text from BlueDart email reply and parse it with AI.
    Expects JSON: { "raw_text": "...", "batch_id": 123 (optional) }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:ndr_action:create'
    }

    def post(self, request):
        raw_text = request.data.get('raw_text', '').strip()
        if not raw_text:
            return Response({'error': 'No raw_text provided'}, status=400)

        batch_id = request.data.get('batch_id')

        try:
            if batch_id:
                batch = NDREscalationBatch.objects.get(id=batch_id)
            else:
                # Create a new batch
                batch_name = f"EMAIL_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
                batch = NDREscalationBatch.objects.create(
                    batch_name=batch_name,
                    escalation_level=2,
                    status='AWAITING_EMAIL_REPLY',
                    created_by=request.user if request.user.is_authenticated else None,
                )

            from core.services.ai_ndr_parser import parse_bluedart_raw_reply, process_parsed_results

            # Step 1: AI Parse
            parsed_results = parse_bluedart_raw_reply(raw_text)
            if not parsed_results:
                return Response({
                    'batch_id': batch.id,
                    'error': 'AI could not parse any AWBs from the text',
                    'parsed_count': 0,
                }, status=200)

            # Step 2: Process
            summary = process_parsed_results(batch.id, parsed_results)

            return Response({
                'batch_id': batch.id,
                'batch_name': batch.batch_name,
                'parsed_count': len(parsed_results),
                'summary': summary,
            })

        except NDREscalationBatch.DoesNotExist:
            return Response({'error': f'Batch {batch_id} not found'}, status=404)
        except Exception as e:
            logger.exception(f"Error processing raw text: {e}")
            return Response({'error': str(e)}, status=500)


# ==============================================================================
# 4. GENERATE ESCALATION EXPORT CSV
# ==============================================================================
class GenerateEscalationExportView(APIView):
    """
    Generate a CSV export for a specific escalation level.
    Query params: ?level=2 (required)
    
    Returns a downloadable CSV formatted for BlueDart's email team.
    Also creates a new NDREscalationBatch to track this export.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:ndr_action:view'
    }

    def get(self, request):
        level = request.query_params.get('level')
        if not level:
            return Response({'error': 'level query parameter is required (1, 2, or 3)'}, status=400)

        try:
            level = int(level)
        except ValueError:
            return Response({'error': 'level must be an integer'}, status=400)

        # Map level to escalation status
        level_to_status = {
            1: 'ESCALATION_1',
            2: 'ESCALATION_2',
            3: 'ESCALATION_3',
        }
        target_status = level_to_status.get(level)
        if not target_status:
            return Response({'error': 'level must be 1, 2, or 3'}, status=400)

        # Query orders at this escalation tier
        orders = Order.objects.filter(
            ndr_escalation_status=target_status,
            is_ndr=True,
        ).select_related('customer').prefetch_related('fulfillments__tracking_info')

        if not orders.exists():
            return Response({
                'error': f'No orders found at escalation level {level}',
                'count': 0,
            }, status=200)

        # Create a batch to track this export
        batch_name = f"ESCA_{level}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        batch = NDREscalationBatch.objects.create(
            batch_name=batch_name,
            escalation_level=level,
            status='AWAITING_EMAIL_REPLY' if level >= 2 else 'AWAITING_PANEL_OUTPUT',
            created_by=request.user if request.user.is_authenticated else None,
        )
        batch.orders.set(orders)

        # Generate CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{batch_name}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'AWB Number',
            'Order Number',
            'Customer Name',
            'Customer Phone',
            'Escalation Level',
            'Remark',
        ])

        remark_templates = {
            1: "Please reattempt delivery. Customer is available.",
            2: "Re-escalation: Customer was not reachable previously. Please reattempt with priority.",
            3: "URGENT Re-re-escalation: Multiple failed attempts. Final reattempt before RTO confirmation.",
        }
        remark = remark_templates.get(level, "Please reattempt delivery.")

        for order in orders:
            awb = order.awb_number or 'N/A'
            customer_name = ''
            customer_phone = ''

            if order.customer:
                customer_name = order.customer.name or ''
                customer_phone = order.customer.phone or ''
            else:
                customer_name = f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip()
                customer_phone = order.contact_phone or ''

            writer.writerow([
                awb,
                order.order_number,
                customer_name,
                customer_phone,
                f"Level {level}",
                remark,
            ])

        # Update batch summary
        batch.summary = {
            'exported_count': orders.count(),
            'exported_at': timezone.now().isoformat(),
        }
        batch.save()

        return response


# ==============================================================================
# 5. GENERATE BATCH FROM CALLING SHEET EXPORT
# ==============================================================================
class GenerateCallingSheetBatchView(APIView):
    """
    Generate an NDREscalationBatch from an explicit list of order IDs (from Calling Sheet).
    Expects POST JSON: { "order_ids": [123, 456], "level": 1 }
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'logistics:ndr_action:create'
    }

    def post(self, request):
        order_ids = request.data.get('order_ids', [])
        level = request.data.get('level', 1)

        if not order_ids or not isinstance(order_ids, list):
            return Response({'error': 'order_ids list is required'}, status=400)

        try:
            level = int(level)
            if level not in [1, 2, 3]:
                raise ValueError
        except ValueError:
            return Response({'error': 'level must be 1, 2, or 3'}, status=400)

        orders = Order.objects.filter(id__in=order_ids)
        if not orders.exists():
            return Response({'error': 'No matching orders found'}, status=400)

        # Create a batch
        batch_name = f"CALLING_SHEET_L{level}_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        batch = NDREscalationBatch.objects.create(
            batch_name=batch_name,
            escalation_level=level,
            status='AWAITING_EMAIL_REPLY' if level >= 2 else 'AWAITING_PANEL_OUTPUT',
            created_by=request.user if request.user.is_authenticated else None,
        )
        batch.orders.set(orders)

        # Update order status to match the new tier
        level_to_status = {
            1: 'ESCALATION_1',
            2: 'ESCALATION_2',
            3: 'ESCALATION_3',
        }
        target_status = level_to_status.get(level)
        
        # Increment count and set status for all selected orders
        for order in orders:
            # Only jump to the target status if it makes sense (or just force it for the batch)
            order.ndr_escalation_status = target_status
            if order.ndr_escalation_count < level:
                order.ndr_escalation_count = level
        
        Order.objects.bulk_update(orders, ['ndr_escalation_status', 'ndr_escalation_count'])

        batch.summary = {
            'source': 'calling_sheet',
            'exported_count': orders.count(),
            'exported_at': timezone.now().isoformat(),
        }
        batch.save()

        return Response({
            'message': f'Batch {batch_name} created successfully',
            'batch_id': batch.id,
            'batch_name': batch.batch_name,
            'order_count': orders.count()
        })


# ==============================================================================
# 6. SAGEPILOT WEBHOOK (Automated Journeys)
# ==============================================================================
class SagepilotWebhookView(APIView):
    """
    Webhook endpoint for Sagepilot Automated Journeys.
    Receives JSON payload when a customer responds to a WhatsApp message.
    """
    permission_classes = []  # Open to Sagepilot, consider adding signature verification later

    def post(self, request):
        from core.models import ShopCredentials, WebhookLog

        awb = request.data.get('awb', '')
        action_code = request.data.get('action_code', '')
        mobile = request.data.get('mobile', '')
        landmark = request.data.get('landmark', '')
        shop_domain = request.data.get('shop_domain')

        if not awb or not action_code or not shop_domain:
            return Response({'error': 'awb, action_code, and shop_domain are required'}, status=400)

        try:
            shop = ShopCredentials.objects.get(myshopify_domain=shop_domain)
        except ShopCredentials.DoesNotExist:
            return Response({'error': f'Shop with domain {shop_domain} not found'}, status=404)

        try:
            resp = submit_ndr_action(shop, awb, action_code, mobile_no=mobile, landmark=landmark)
            status_info = resp.get('StatusInformation', '')
            is_error = resp.get('IsError', True)

            # Determine the log status
            if not is_error:
                log_status = 'success'
            elif 'attempted as per sop' in status_info.lower():
                log_status = 'sop'
            else:
                log_status = 'failed'

            # Persist the log — store the full raw payload so we can see exactly what Sagepilot sent
            WebhookLog.objects.create(
                source='sagepilot',
                awb=awb,
                action_code=action_code,
                mobile=mobile,
                landmark=landmark,
                status=log_status,
                response_message=status_info,
                payload_json=request.data,
            )

            # --- AUTO-MARK ORDER AS "Will Accept" via Sagepilot ---
            # This runs AFTER the webhook log is saved, so the core flow is untouched.
            if log_status in ('success', 'sop'):
                try:
                    from core.models import Order
                    order = Order.objects.filter(
                        fulfillments__tracking_info__number=awb
                    ).first()
                    if order:
                        order.ndr_call_status = 'Will Accept'
                        order.ndr_last_called_at = timezone.now()
                        order.ndr_call_attempts = (order.ndr_call_attempts or 0) + 1
                        if not isinstance(order.ndr_call_history, list):
                            order.ndr_call_history = []
                        order.ndr_call_history.insert(0, {
                            'datetime': timezone.now().isoformat(),
                            'status': 'Will Accept',
                            'remark': f'Auto-marked via Sagepilot. BlueDart response: {status_info}',
                            'agent': 'Sagepilot',
                            'source': 'sagepilot',
                        })
                        order.save(update_fields=[
                            'ndr_call_status', 'ndr_last_called_at',
                            'ndr_call_attempts', 'ndr_call_history'
                        ])
                except Exception as mark_err:
                    logger.warning(f'Failed to auto-mark order for AWB {awb}: {mark_err}')

            if is_error and log_status == 'failed':
                return Response({'status': 'Failed', 'details': status_info}, status=400)

            # Build user-facing message based on BlueDart response
            if log_status == 'success':
                user_message = 'Reattempt scheduled. Order will be reattempted tomorrow or the following day.'
            else:  # sop
                user_message = 'Attempted as per SOP. Please contact your BlueDart manager/KAM for further attempts, or try pushing it from the panel after a day or two.'

            return Response({'status': 'Success' if log_status == 'success' else 'SOP', 'details': status_info, 'message': user_message})

        except Exception as e:
            logger.exception(f"Error processing Sagepilot webhook: {e}")
            # Still log the failure — include full raw payload
            WebhookLog.objects.create(
                source='sagepilot',
                awb=awb,
                action_code=action_code,
                mobile=mobile,
                landmark=landmark,
                status='failed',
                response_message=str(e),
                payload_json=request.data,
            )
            return Response({'error': str(e)}, status=500)


# ==============================================================================
# 7. WEBHOOK LOG LIST / STATS VIEW
# ==============================================================================
class WebhookLogListView(APIView):
    """
    Returns a paginated list of WebhookLog entries and summary stats.
    Query params: ?source=sagepilot&page=1&limit=25
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:analytics:view'
    }

    def get(self, request):
        from core.models import WebhookLog
        from django.core.paginator import Paginator

        source = request.query_params.get('source', 'sagepilot')
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 25))

        qs = WebhookLog.objects.filter(source=source).order_by('-created_at')

        # Summary counts
        total = qs.count()
        success_count = qs.filter(status='success').count()
        sop_count = qs.filter(status='sop').count()
        failed_count = qs.filter(status='failed').count()

        paginator = Paginator(qs, limit)
        page_obj = paginator.get_page(page)

        logs = []
        for log in page_obj:
            logs.append({
                'id': log.id,
                'awb': log.awb,
                'action_code': log.action_code,
                'mobile': log.mobile,
                'landmark': log.landmark,
                'status': log.status,
                'response_message': log.response_message,
                'payload_json': log.payload_json,
                'created_at': log.created_at.isoformat(),
            })

        return Response({
            'summary': {
                'total': total,
                'success': success_count,
                'sop': sop_count,
                'failed': failed_count,
            },
            'logs': logs,
            'page': page,
            'total_pages': paginator.num_pages,
        })

# ==============================================================================
# 8. NDR ANALYTICS DATA VIEW (Webhooks + Orders Joined)
# ==============================================================================
class NDRAnalyticsDataView(APIView):
    """
    Returns data for the NDR Analytics Dashboard.
    Supports tab=webhooks and tab=recovered.
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'logistics:analytics:view'
    }

    def get(self, request):
        from core.models import WebhookLog, Order
        from core.models.constants import NDR_STATUSES
        from django.core.paginator import Paginator
        from django.db.models import Q
        import dateutil.parser

        tab = request.query_params.get('tab', 'webhooks')
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 25))
        search = request.query_params.get('search', '').strip()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        payment_method = request.query_params.get('payment_method')
        courier = request.query_params.get('courier', '').strip()

        order_filters = Q()

        # CRITICAL: Always filter by org to avoid cross-tenant data leakage
        org_id = _get_org_id_or_none(request)
        if org_id:
            order_filters &= Q(org_id=org_id)

        if search:
            # Separate index-friendly lookup to avoid slow OR join
            tracking_filter = Q(fulfillments__tracking_info__number__icontains=search)
            if org_id:
                tracking_filter &= Q(org_id=org_id)
            order_ids_from_tracking = list(Order.objects.filter(tracking_filter).values_list('id', flat=True))

            order_filters &= (
                Q(id__in=order_ids_from_tracking) |
                Q(order_number__icontains=search) | 
                Q(customer__name__icontains=search) | 
                Q(customer_first_name__icontains=search) | 
                Q(customer_last_name__icontains=search)
            )
        if start_date:
            try:
                dt = dateutil.parser.parse(start_date)
                order_filters &= Q(created_at__gte=dt)
            except Exception: pass
        if end_date:
            try:
                dt = dateutil.parser.parse(end_date)
                order_filters &= Q(created_at__lte=dt)
            except Exception: pass
        if payment_method:
            if payment_method.lower() == 'cod':
                order_filters &= Q(financial_status='pending')
            elif payment_method.lower() == 'prepaid':
                order_filters &= Q(financial_status='paid') & ~Q(tags__icontains='Partial Payment')
            elif payment_method.lower() == 'partially_paid':
                order_filters &= (Q(financial_status='partially_paid') | Q(tags__icontains='Partial Payment'))

        if courier:
            order_filters &= Q(fulfillments__tracking_info__company__icontains=courier)

        # Drill-down order extraction for reason categories funnel
        extract_category = request.query_params.get('extract_category')
        extract_status = request.query_params.get('extract_status')  # 'all', 'converted', 'rto', 'pending'
        if extract_category:
            if extract_category == 'OTHERS':
                category_filter = Q(ndr_reason_category='OTHERS') | Q(ndr_reason_category__isnull=True) | Q(ndr_reason_category='')
            else:
                category_filter = Q(ndr_reason_category=extract_category)

            # Wrap OR in parentheses to prevent logic breakage with subsequent & filters
            base_funnel_filter = (Q(is_ndr=True) | Q(ndr_conversion_status__in=['CONVERTED', 'RTO']))

            # FIX: Pre-materialize distinct IDs to prevent JOIN fan-out double counting.
            # When a courier filter joins through fulfillments__tracking_info, each order
            # can appear multiple times in the SQL result — one row per tracking record.
            # We resolve this by fetching a clean set of unique IDs first, then filtering
            # on that set so no join-multiplied counts can leak through.
            safe_ids = Order.objects.filter(
                order_filters & category_filter & base_funnel_filter
            ).values_list('id', flat=True).distinct()
            orders_qs = Order.objects.filter(id__in=safe_ids)

            if extract_status == 'converted':
                orders_qs = orders_qs.filter(ndr_conversion_status='CONVERTED')
            elif extract_status == 'rto':
                orders_qs = orders_qs.filter(ndr_conversion_status='RTO')
            elif extract_status == 'pending':
                orders_qs = orders_qs.exclude(ndr_conversion_status__in=['CONVERTED', 'RTO'])

            extract_payment = request.query_params.get('extract_payment')
            if extract_payment and extract_payment != 'all':
                if extract_payment == 'cod':
                    orders_qs = orders_qs.filter(financial_status='pending')
                elif extract_payment == 'prepaid':
                    orders_qs = orders_qs.filter(financial_status='paid').exclude(tags__icontains='Partial Payment')
                elif extract_payment == 'partial':
                    orders_qs = orders_qs.filter(Q(financial_status='partially_paid') | Q(tags__icontains='Partial Payment'))

            # Order queryset — no courier join needed here, already filtered by ID
            orders_qs = orders_qs.select_related('customer').prefetch_related('fulfillments__tracking_info').order_by('-created_at')

            # Paginate extract request
            extract_page = int(request.query_params.get('extract_page', 1))
            extract_limit = int(request.query_params.get('extract_limit', 15))

            paginator = Paginator(orders_qs, extract_limit)
            page_obj = paginator.get_page(extract_page)

            results = []
            for ord_obj in page_obj:
                customer_name = ""
                if ord_obj.customer:
                    customer_name = ord_obj.customer.name or ''
                else:
                    customer_name = f"{ord_obj.customer_first_name or ''} {ord_obj.customer_last_name or ''}".strip()

                payment_method_val = 'PARTIALLY_PAID' if (ord_obj.financial_status == 'partially_paid' or 'partial payment' in str(ord_obj.tags or '').lower()) else ('PREPAID' if ord_obj.financial_status == 'paid' else 'COD')

                tracking_number = ""
                tracking_url = ""
                courier_partner = ""
                detailed_remark = ord_obj.current_status_details
                for f in ord_obj.fulfillments.all():
                    tracking_infos = list(f.tracking_info.all())
                    if tracking_infos:
                        tracking_number = tracking_infos[0].number
                        tracking_url = tracking_infos[0].url
                        courier_partner = tracking_infos[0].company
                        
                        events = sorted([ev for ev in f.tracking_events.all()], key=lambda e: e.datetime)
                        attempts = [ev for ev in events if "attempted" in ev.status.lower() or ev.status in NDR_STATUSES]
                        if attempts:
                            detailed_remark = f"{attempts[-1].status} - {attempts[-1].details}"
                        break

                results.append({
                    'id': ord_obj.id,
                    'order_number': ord_obj.order_number,
                    'date': ord_obj.created_at.isoformat() if ord_obj.created_at else None,
                    'customer': customer_name,
                    'total_price': float(ord_obj.total_price) if ord_obj.total_price else 0,
                    'payment': payment_method_val.lower(),
                    'tracking_number': tracking_number,
                    'tracking_url': tracking_url,
                    'courier': courier_partner,
                    'shipping_remark': detailed_remark or 'No remark'
                })

            return Response({
                "extracted_orders": results,
                "total_count": paginator.count,
                "page": extract_page,
                "total_pages": paginator.num_pages
            })

        if tab == 'webhooks':
            source = request.query_params.get('source', 'sagepilot')
            qs = WebhookLog.objects.filter(source=source).order_by('-created_at')
            if search or start_date or end_date or payment_method or courier:
                filtered_orders = Order.objects.filter(order_filters)
                valid_awbs = set(filtered_orders.values_list('fulfillments__tracking_info__number', flat=True))
                qs = qs.filter(awb__in=valid_awbs)

            total = qs.count()
            success_count = qs.filter(status='success').count()
            sop_count = qs.filter(status='sop').count()
            failed_count = qs.filter(status='failed').count()

            paginator = Paginator(qs, limit)
            page_obj = paginator.get_page(page)

            # Pre-fetch orders for the current page's AWBs & Mobiles to avoid N+1 querying
            awb_list = [log.awb for log in page_obj if log.awb]
            mobile_list = [log.mobile for log in page_obj if log.mobile]

            cleaned_mobiles = []
            for m in mobile_list:
                m_clean = str(m).strip()
                if m_clean:
                    cleaned_mobiles.append(m_clean)
                    if len(m_clean) > 10:
                        cleaned_mobiles.append(m_clean[-10:])
            
            # Fetch order IDs using separate index-friendly queries to avoid slow OR join
            order_ids_from_awb = list(Order.objects.filter(
                fulfillments__tracking_info__number__in=awb_list
            ).values_list('id', flat=True))

            order_ids_from_mobile = []
            if cleaned_mobiles:
                order_ids_from_mobile = list(Order.objects.filter(
                    contact_phone__in=cleaned_mobiles
                ).values_list('id', flat=True))

            order_ids = set(order_ids_from_awb).union(order_ids_from_mobile)

            orders_qs = Order.objects.filter(
                id__in=order_ids
            ).select_related('customer').prefetch_related(
                'fulfillments__tracking_events', 
                'fulfillments__tracking_info'
            )
            
            # Create speedy lookups: Dict[awb] -> order, Dict[phone] -> order
            order_map = {}
            phone_order_map = {}
            for ord_obj in orders_qs:
                customer_name = ""
                if ord_obj.customer:
                    customer_name = ord_obj.customer.name or ''
                else:
                    customer_name = f"{ord_obj.customer_first_name or ''} {ord_obj.customer_last_name or ''}".strip()

                payment_method_val = 'PARTIALLY_PAID' if (ord_obj.financial_status == 'partially_paid' or 'partial payment' in str(ord_obj.tags or '').lower()) else ('PREPAID' if ord_obj.financial_status == 'paid' else 'COD')

                for f in ord_obj.fulfillments.all():
                    tracking_infos = list(f.tracking_info.all())
                    ti_number = ""
                    tracking_url = ""
                    ti_company = ""
                    if tracking_infos:
                        ti = tracking_infos[0]
                        ti_number = ti.number
                        ti_company = ti.company
                        tracking_url = ti.url

                    events = sorted([ev for ev in f.tracking_events.all()], key=lambda e: e.datetime)
                    attempts = [ev for ev in events if "attempted" in ev.status.lower() or ev.status in NDR_STATUSES]
                    first_attempt = attempts[0].datetime if attempts else None
                    total_attempts = len(attempts)

                    detailed_remark = ""
                    if attempts:
                        detailed_remark = f"{attempts[-1].status} - {attempts[-1].details}"
                    else:
                        detailed_remark = ord_obj.current_status_details

                    ord_details = {
                        'order_number': ord_obj.order_number,
                        'order_date': ord_obj.created_at.isoformat() if ord_obj.created_at else None,
                        'payment_method': payment_method_val,
                        'shipped_date': ord_obj.fulfilled_at.isoformat() if ord_obj.fulfilled_at else (f.created_at.isoformat() if f.created_at else None),
                        'total_price': float(ord_obj.total_price) if ord_obj.total_price else 0,
                        'customer_name': customer_name,
                        'tracking_number': ti_number,
                        'courier': ti_company,
                        'first_delivery_attempt_date': first_attempt.isoformat() if first_attempt else None,
                        'total_delivery_attempts': total_attempts,
                        'order_id': ord_obj.id,
                        'tracking_url': tracking_url,
                        'current_status_details': detailed_remark,
                        'ndr_call_status': ord_obj.ndr_call_status or '',
                        'ndr_reason_category': ord_obj.ndr_reason_category or 'OTHERS',
                        'ndr_rto_risk_score': ord_obj.ndr_rto_risk_score or 0,
                        'ndr_conversion_status': ord_obj.ndr_conversion_status or 'PENDING',
                    }

                    if ti_number:
                        order_map[ti_number] = ord_details

                if ord_obj.contact_phone:
                    f_list = list(ord_obj.fulfillments.all())
                    f_first = f_list[0] if f_list else None
                    ti_number = ""
                    tracking_url = ""
                    ti_company = ""
                    first_attempt = None
                    total_attempts = 0
                    detailed_remark = ord_obj.current_status_details

                    if f_first:
                        tracking_infos = list(f_first.tracking_info.all())
                        if tracking_infos:
                            ti_number = tracking_infos[0].number
                            ti_company = tracking_infos[0].company
                            tracking_url = tracking_infos[0].url
                        events = sorted([ev for ev in f_first.tracking_events.all()], key=lambda e: e.datetime)
                        attempts = [ev for ev in events if "attempted" in ev.status.lower() or ev.status in NDR_STATUSES]
                        first_attempt = attempts[0].datetime if attempts else None
                        total_attempts = len(attempts)
                        if attempts:
                            detailed_remark = f"{attempts[-1].status} - {attempts[-1].details}"

                    ord_details_phone = {
                        'order_number': ord_obj.order_number,
                        'order_date': ord_obj.created_at.isoformat() if ord_obj.created_at else None,
                        'payment_method': payment_method_val,
                        'shipped_date': ord_obj.fulfilled_at.isoformat() if ord_obj.fulfilled_at else (f_first.created_at.isoformat() if f_first and f_first.created_at else None),
                        'total_price': float(ord_obj.total_price) if ord_obj.total_price else 0,
                        'customer_name': customer_name,
                        'tracking_number': ti_number,
                        'courier': ti_company,
                        'first_delivery_attempt_date': first_attempt.isoformat() if first_attempt else None,
                        'total_delivery_attempts': total_attempts,
                        'order_id': ord_obj.id,
                        'tracking_url': tracking_url,
                        'current_status_details': detailed_remark,
                        'ndr_call_status': ord_obj.ndr_call_status or '',
                        'ndr_reason_category': ord_obj.ndr_reason_category or 'OTHERS',
                        'ndr_rto_risk_score': ord_obj.ndr_rto_risk_score or 0,
                        'ndr_conversion_status': ord_obj.ndr_conversion_status or 'PENDING',
                    }
                    phone_order_map[ord_obj.contact_phone.strip()] = ord_details_phone
                    if len(ord_obj.contact_phone.strip()) > 10:
                        phone_order_map[ord_obj.contact_phone.strip()[-10:]] = ord_details_phone

            logs_list = []
            for log in page_obj:
                order_info = order_map.get(log.awb)
                if not order_info and log.mobile:
                    order_info = phone_order_map.get(log.mobile.strip()) or phone_order_map.get(log.mobile.strip()[-10:])
                if not order_info:
                    order_info = {}

                logs_list.append({
                    'id': log.id,
                    'awb': log.awb,
                    'status': log.status,
                    'webhook_remark': log.response_message,
                    'shipping_remark': order_info.get('current_status_details') or log.response_message,
                    'mobile': log.mobile,
                    'created_at': log.created_at.isoformat(),
                    'order_number': order_info.get('order_number'),
                    'order_date': order_info.get('order_date'),
                    'payment_method': order_info.get('payment_method'),
                    'shipped_date': order_info.get('shipped_date'),
                    'total_price': order_info.get('total_price'),
                    'customer_name': order_info.get('customer_name'),
                    'courier': order_info.get('courier'),
                    'tracking_url': order_info.get('tracking_url'),
                    'first_delivery_attempt_date': order_info.get('first_delivery_attempt_date'),
                    'total_delivery_attempts': order_info.get('total_delivery_attempts', 0),
                    'order_id': order_info.get('order_id'),
                    'ndr_call_status': order_info.get('ndr_call_status', ''),
                    'ndr_reason_category': order_info.get('ndr_reason_category', 'OTHERS'),
                    'ndr_rto_risk_score': order_info.get('ndr_rto_risk_score', 0),
                    'ndr_conversion_status': order_info.get('ndr_conversion_status', 'PENDING'),
                })

            # Calculate reason categories funnel — filtered by org and is_ndr/conversion + active filters
            from django.db.models import Count

            # Wrap the OR in parentheses so subsequent & filters don't break the predicate logic
            funnel_qs_filters = (Q(is_ndr=True) | Q(ndr_conversion_status__in=['CONVERTED', 'RTO']))
            if org_id:
                funnel_qs_filters &= Q(org_id=org_id)
            if start_date:
                try:
                    dt = dateutil.parser.parse(start_date)
                    funnel_qs_filters &= Q(created_at__gte=dt)
                except Exception: pass
            if end_date:
                try:
                    dt = dateutil.parser.parse(end_date)
                    funnel_qs_filters &= Q(created_at__lte=dt)
                except Exception: pass
            if payment_method:
                if payment_method.lower() == 'cod':
                    funnel_qs_filters &= Q(financial_status='pending')
                elif payment_method.lower() == 'prepaid':
                    funnel_qs_filters &= Q(financial_status='paid') & ~Q(tags__icontains='Partial Payment')
                elif payment_method.lower() == 'partially_paid':
                    funnel_qs_filters &= (Q(financial_status='partially_paid') | Q(tags__icontains='Partial Payment'))
            if courier:
                funnel_qs_filters &= Q(fulfillments__tracking_info__company__icontains=courier)

            # FIX: Pre-materialize distinct order IDs to prevent JOIN fan-out double-counting.
            # When a courier filter is present, the JOIN on fulfillments__tracking_info can produce
            # multiple SQL rows per Order, inflating the Count even with distinct=True inside annotate.
            # Solution: resolve to a clean ID set first, then annotate from there — no JOINs involved.
            funnel_safe_ids = Order.objects.filter(funnel_qs_filters).values_list('id', flat=True).distinct()
            category_stats = (
                Order.objects
                .filter(id__in=funnel_safe_ids)
                .values('ndr_reason_category', 'ndr_conversion_status')
                .annotate(count=Count('id'))
            )
            
            funnel_data = {}
            for stat in category_stats:
                cat = stat['ndr_reason_category'] or 'OTHERS'
                conv_status = stat['ndr_conversion_status'] or 'PENDING'
                count = stat['count']
                
                if cat not in funnel_data:
                    funnel_data[cat] = {'total': 0, 'converted': 0, 'rto': 0, 'pending': 0}
                
                funnel_data[cat]['total'] += count
                if conv_status == 'CONVERTED':
                    funnel_data[cat]['converted'] += count
                elif conv_status == 'RTO':
                    funnel_data[cat]['rto'] += count
                else:
                    funnel_data[cat]['pending'] += count
            
            funnel_summary = []
            for cat, counts in funnel_data.items():
                cat_total = counts['total']
                cat_converted = counts['converted']
                rate = round((cat_converted / cat_total) * 100) if cat_total > 0 else 0
                funnel_summary.append({
                    'category': cat,
                    'total': cat_total,
                    'converted': cat_converted,
                    'rto': counts['rto'],
                    'pending': counts['pending'],
                    'conversion_rate': rate
                })
            funnel_summary.sort(key=lambda x: x['total'], reverse=True)

            return Response({
                'summary': {
                    'total': total,
                    'success': success_count,
                    'sop': sop_count,
                    'failed': failed_count,
                    'funnel': funnel_summary,
                },
                'logs': logs_list,
                'page': page,
                'total_pages': paginator.num_pages,
            })

        elif tab in ('recovered', 'unrecovered'):
            if tab == 'recovered':
                # Only see orders where NDR status is 'Will Accept' and shipping status is 'Delivered' (case-insensitive)
                order_filters &= Q(ndr_call_status='Will Accept', current_status__iexact='Delivered')
            else:
                # Unrecovered orders: 'Will Accept' but any shipping status other than 'Delivered' (case-insensitive)
                order_filters &= Q(ndr_call_status='Will Accept') & ~Q(current_status__iexact='Delivered')
            
            # Recovery source filter: sagepilot, manual, or all
            recovery_source = request.query_params.get('recovery_source', '')

            orders = Order.objects.filter(order_filters).select_related('customer').prefetch_related(
                'fulfillments__tracking_events', 
                'fulfillments__tracking_info'
            ).distinct().order_by('-updated_at')

            # Apply recovery source filter if specified
            if recovery_source == 'sagepilot':
                orders = orders.filter(
                    ndr_call_history__icontains='"source": "sagepilot"'
                )
            elif recovery_source == 'manual':
                orders = orders.exclude(
                    ndr_call_history__icontains='"source": "sagepilot"'
                )

            paginator = Paginator(orders, limit)
            page_obj = paginator.get_page(page)

            results = []
            for ord_obj in page_obj:
                customer_name = ""
                if ord_obj.customer:
                    customer_name = ord_obj.customer.name or ''
                else:
                    customer_name = f"{ord_obj.customer_first_name or ''} {ord_obj.customer_last_name or ''}".strip()

                first_attempt = None
                total_attempts = 0
                ti_number = ""
                courier = ""
                last_ndr_remark = ""
                tracking_url = "" 

                for f in ord_obj.fulfillments.all():
                    # Optimized to read from prefetched cache list instead of triggering individual SQL query per fulfillment (.first())
                    tracking_infos = list(f.tracking_info.all())
                    if tracking_infos:
                        ti = tracking_infos[0]
                        ti_number = ti.number
                        courier = ti.company
                        tracking_url = ti.url

                    events = sorted([ev for ev in f.tracking_events.all()], key=lambda e: e.datetime)
                    ndr_events = [ev for ev in events if ev.status in NDR_STATUSES or "attempted" in ev.status.lower()]
                    
                    if ndr_events:
                        first_attempt = ndr_events[0].datetime
                        total_attempts = len(ndr_events)
                        last_ndr_remark = f"{ndr_events[-1].status} - {ndr_events[-1].details}"

                # Determine recovery source from call history
                recovery_src = 'manual'
                if isinstance(ord_obj.ndr_call_history, list):
                    for entry in ord_obj.ndr_call_history:
                        if isinstance(entry, dict) and entry.get('source') == 'sagepilot':
                            recovery_src = 'sagepilot'
                            break

                results.append({
                    'order_id': ord_obj.id,
                    'order_number': ord_obj.order_number,
                    'order_date': ord_obj.created_at.isoformat() if ord_obj.created_at else None,
                    'payment_method': 'PARTIALLY_PAID' if (ord_obj.financial_status == 'partially_paid' or 'partial payment' in str(ord_obj.tags or '').lower()) else ('PREPAID' if ord_obj.financial_status == 'paid' else 'COD'),
                    'customer_name': customer_name,
                    'total_price': float(ord_obj.total_price) if ord_obj.total_price else 0,
                    'shipped_date': ord_obj.fulfilled_at.isoformat() if ord_obj.fulfilled_at else None,
                    'tracking_number': ti_number,
                    'tracking_url': tracking_url,
                    'courier': courier,
                    'first_delivery_attempt_date': first_attempt.isoformat() if first_attempt else None,
                    'total_delivery_attempts': total_attempts,
                    'ndr_call_attempts': ord_obj.ndr_call_attempts,
                    'ndr_call_status': ord_obj.ndr_call_status or '',
                    'recovery_source': recovery_src,
                    'shipment_status': last_ndr_remark or ord_obj.current_status or '',
                    'shippment_status': last_ndr_remark or ord_obj.current_status or '',
                    'shipping_remark': last_ndr_remark or ord_obj.current_status or '',  # for compatibility
                    'updated_at': ord_obj.updated_at.isoformat() if ord_obj.updated_at else None,
                })

            # Calculate pushed to BlueDart stats for these filtered orders
            all_awbs_qs = orders.values_list('fulfillments__tracking_info__number', flat=True).distinct()
            all_awbs = [awb for awb in all_awbs_qs if awb]

            pushed_to_bluedart_count = WebhookLog.objects.filter(
                awb__in=all_awbs,
                status__in=['success', 'sop']
            ).values('awb').distinct().count()

            total_pushed_to_bluedart = WebhookLog.objects.filter(
                status__in=['success', 'sop']
            ).values('awb').distinct().count()

            # Calculate reason categories funnel — already scoped to this org/tab via `orders`
            from django.db.models import Count
            category_stats = orders.values('ndr_reason_category', 'ndr_conversion_status').annotate(count=Count('id', distinct=True))
            
            funnel_data = {}
            for stat in category_stats:
                cat = stat['ndr_reason_category'] or 'OTHERS'
                conv_status = stat['ndr_conversion_status'] or 'PENDING'
                count = stat['count']
                
                if cat not in funnel_data:
                    funnel_data[cat] = {'total': 0, 'converted': 0, 'rto': 0, 'pending': 0}
                
                funnel_data[cat]['total'] += count
                if conv_status == 'CONVERTED':
                    funnel_data[cat]['converted'] += count
                elif conv_status == 'RTO':
                    funnel_data[cat]['rto'] += count
                else:
                    funnel_data[cat]['pending'] += count
            
            funnel_summary = []
            for cat, counts in funnel_data.items():
                cat_total = counts['total']
                cat_converted = counts['converted']
                rate = round((cat_converted / cat_total) * 100) if cat_total > 0 else 0
                funnel_summary.append({
                    'category': cat,
                    'total': cat_total,
                    'converted': cat_converted,
                    'rto': counts['rto'],
                    'pending': counts['pending'],
                    'conversion_rate': rate
                })
            funnel_summary.sort(key=lambda x: x['total'], reverse=True)

            return Response({
                'summary': {
                    'total': paginator.count,
                    'pushed_to_bluedart': pushed_to_bluedart_count,
                    'total_pushed_to_bluedart': total_pushed_to_bluedart,
                    'funnel': funnel_summary,
                },
                'logs': results,
                'page': page,
                'total_pages': paginator.num_pages,
            })

        return Response({'error': 'Invalid tab'}, status=400)


# ==============================================================================
# 9. NDR PLAYBOOK VIEWS
# ==============================================================================
class NDRPlaybookListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.views.helpers import _get_org_id_or_none
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)
        
        from core.models.delivery import NDRPlaybook
        playbooks = NDRPlaybook.objects.filter(org_id=org_id)
        
        data = []
        for p in playbooks:
            data.append({
                'id': p.id,
                'name': p.name,
                'reason_category': p.reason_category,
                'priority': p.priority,
                'is_active': p.is_active,
                'conditions': p.conditions,
                'actions': p.actions,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'updated_at': p.updated_at.isoformat() if p.updated_at else None,
            })
        return Response(data)

    def post(self, request):
        from core.views.helpers import _get_org_id_or_none
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)
        
        from core.models.delivery import NDRPlaybook
        name = request.data.get('name', '').strip()
        reason_category = request.data.get('reason_category', '').strip()
        priority = int(request.data.get('priority', 0))
        is_active = bool(request.data.get('is_active', True))
        conditions = request.data.get('conditions', {})
        actions = request.data.get('actions', [])

        if not name or not reason_category:
            return Response({'error': 'name and reason_category are required'}, status=400)

        playbook = NDRPlaybook.objects.create(
            org_id=org_id,
            name=name,
            reason_category=reason_category,
            priority=priority,
            is_active=is_active,
            conditions=conditions,
            actions=actions
        )

        return Response({
            'id': playbook.id,
            'name': playbook.name,
            'reason_category': playbook.reason_category,
            'priority': playbook.priority,
            'is_active': playbook.is_active,
            'conditions': playbook.conditions,
            'actions': playbook.actions,
        }, status=201)


class NDRPlaybookDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, org_id):
        from core.models.delivery import NDRPlaybook
        from django.shortcuts import get_object_or_404
        return get_object_or_404(NDRPlaybook, pk=pk, org_id=org_id)

    def get(self, request, pk):
        from core.views.helpers import _get_org_id_or_none
        org_id = _get_org_id_or_none(request)
        playbook = self.get_object(pk, org_id)
        return Response({
            'id': playbook.id,
            'name': playbook.name,
            'reason_category': playbook.reason_category,
            'priority': playbook.priority,
            'is_active': playbook.is_active,
            'conditions': playbook.conditions,
            'actions': playbook.actions,
        })

    def put(self, request, pk):
        from core.views.helpers import _get_org_id_or_none
        org_id = _get_org_id_or_none(request)
        playbook = self.get_object(pk, org_id)

        playbook.name = request.data.get('name', playbook.name)
        playbook.reason_category = request.data.get('reason_category', playbook.reason_category)
        playbook.priority = int(request.data.get('priority', playbook.priority))
        playbook.is_active = bool(request.data.get('is_active', playbook.is_active))
        playbook.conditions = request.data.get('conditions', playbook.conditions)
        playbook.actions = request.data.get('actions', playbook.actions)
        playbook.save()

        return Response({
            'id': playbook.id,
            'name': playbook.name,
            'reason_category': playbook.reason_category,
            'priority': playbook.priority,
            'is_active': playbook.is_active,
            'conditions': playbook.conditions,
            'actions': playbook.actions,
        })

    def delete(self, request, pk):
        from core.views.helpers import _get_org_id_or_none
        org_id = _get_org_id_or_none(request)
        playbook = self.get_object(pk, org_id)
        playbook.delete()
        return Response({'success': True}, status=204)


# ==============================================================================
# 10. NDR FRAUD FLAG VIEWS
# ==============================================================================
class NDRFraudFlagListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.views.helpers import _get_org_id_or_none
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        from core.models.delivery import NDRFraudFlag
        flags = NDRFraudFlag.objects.filter(shipment__order__org_id=org_id).select_related('shipment__order')

        data = []
        for f in flags:
            data.append({
                'id': f.id,
                'awb': f.shipment.awb_number,
                'order_number': f.shipment.order.order_number,
                'order_id': f.shipment.order.id,
                'flag_type': f.flag_type,
                'details': f.details,
                'is_resolved': f.is_resolved,
                'created_at': f.created_at.isoformat() if f.created_at else None,
                'resolved_at': f.resolved_at.isoformat() if f.resolved_at else None,
            })
        return Response(data)


class NDRFraudFlagResolveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from core.views.helpers import _get_org_id_or_none
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'error': 'Organization not found'}, status=400)

        from core.models.delivery import NDRFraudFlag
        from django.utils import timezone
        from django.shortcuts import get_object_or_404
        
        flag = get_object_or_404(NDRFraudFlag, pk=pk, shipment__order__org_id=org_id)
        flag.is_resolved = True
        flag.resolved_at = timezone.now()
        flag.save()

        return Response({
            'id': flag.id,
            'is_resolved': flag.is_resolved,
            'resolved_at': flag.resolved_at.isoformat(),
        })
