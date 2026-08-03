import logging
import pandas as pd
from datetime import datetime, date, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Q
from core.models.delivery import Shipment, CODRemittance
from core.permissions import HasModulePermission
from core.views_delivery_analytics import _get_org_id

logger = logging.getLogger(__name__)

class CODRemittanceUploadView(APIView):
    """
    POST /api/delivery/cod-remittance/upload-excel/
    Accepts an .xlsb file, start_date, and end_date.
    Parses 'AwbNo' and 'CustPayAmt' and matches against internal shipments.
    Returns a JSON payload with 'matched' and 'mismatched' lists.
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

        try:
            df = pd.read_excel(file, engine='pyxlsb', header=None)
            
            # Find the actual header row
            header_idx = None
            for idx, row in df.iterrows():
                row_str = ' '.join([str(val).lower() for val in row.values])
                if ('awbno' in row_str or 'awb' in row_str) and ('custpayamt' in row_str or 'amount' in row_str):
                    header_idx = idx
                    break
                    
            if header_idx is not None:
                df.columns = df.iloc[header_idx]
                df = df.iloc[header_idx + 1:].reset_index(drop=True)
            else:
                return Response({'error': 'Could not find header row containing AWB and Amount columns.'}, status=400)
                
        except Exception as e:
            logger.error(f"Error parsing COD Remittance excel: {e}")
            return Response({'error': 'Failed to parse Excel file. Ensure it is a valid .xlsb file.'}, status=400)

        # Look for expected columns
        awb_col = None
        amt_col = None
        for col in df.columns:
            col_str = str(col).lower()
            if 'awbno' in col_str or 'awb no' in col_str or 'awb' in col_str:
                awb_col = col
            if 'custpayamt' in col_str or 'amount' in col_str or 'payamt' in col_str:
                amt_col = col

        if not awb_col or not amt_col:
            return Response({'error': f"Could not find required columns. Found: {list(df.columns)}"}, status=400)

        # Drop NaNs and convert
        df = df.dropna(subset=[awb_col])
        awb_list = df[awb_col].astype(str).str.replace(r'\.0$', '', regex=True).tolist()
        
        # Batch query all shipments in the list
        shipments = Shipment.objects.filter(
            org_id=org_id,
            awb_number__in=awb_list
        ).select_related('order')

        # Create a lookup map
        shipment_map = {s.awb_number: s for s in shipments}

        matched = []
        mismatched = []

        for index, row in df.iterrows():
            awb = str(row[awb_col]).replace('.0', '').strip()
            if not awb or awb.lower() == 'nan':
                continue
                
            raw_amt = row[amt_col]
            try:
                amt = float(raw_amt)
            except (ValueError, TypeError):
                amt = 0.0

            shipment = shipment_map.get(awb)

            if not shipment:
                mismatched.append({
                    'awb': awb,
                    'amount': amt,
                    'reason': 'AWB not found in system'
                })
                continue

            if shipment.payment_type not in ['COD', 'Partially Paid']:
                mismatched.append({
                    'awb': awb,
                    'order_number': shipment.order.order_number if shipment.order else '',
                    'amount': amt,
                    'reason': f"Not a COD order (Type: {shipment.payment_type})"
                })
                continue

            # We use delivery_date as the source of truth for delivery, as current_stage might lag.
            del_date = None
            if shipment.delivery_date:
                del_date = shipment.delivery_date.date()
            else:
                # Fallback: Check for 'Delivered' tracking events if shipment.delivery_date is missing
                from core.models.orders import TrackingEvent
                latest_del_event = TrackingEvent.objects.filter(
                    fulfillment__order=shipment.order,
                    status__iexact='Delivered'
                ).order_by('-datetime').first()
                
                if latest_del_event:
                    del_date = latest_del_event.datetime.date()

            if not del_date:
                mismatched.append({
                    'awb': awb,
                    'order_number': shipment.order.order_number if shipment.order else '',
                    'amount': amt,
                    'reason': f"Not Delivered / Missing Date (Stage: {shipment.current_stage})"
                })
                continue
                
            if not (start_date <= del_date <= end_date):
                mismatched.append({
                    'awb': awb,
                    'order_number': shipment.order.order_number if shipment.order else '',
                    'delivery_date': str(del_date),
                    'amount': amt,
                    'reason': f"Delivered on {del_date}, outside selected range"
                })
                continue

            # Matched!
            matched.append({
                'awb': awb,
                'order_number': shipment.order.order_number if shipment.order else '',
                'delivery_date': str(del_date),
                'amount': amt
            })

        return Response({
            'total_processed': len(awb_list),
            'matched': matched,
            'mismatched': mismatched
        })


class CODRemittanceConfirmView(APIView):
    """
    POST /api/delivery/cod-remittance/confirm/
    Accepts an array of AWBs with their received amounts to mark them as 'Received'.
    Payload format: { "remittances": [{ "awb": "123", "amount": 500 }, ...] }
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

        # Batch query all shipments
        awbs = [item['awb'] for item in remittances_data if 'awb' in item]
        shipments = Shipment.objects.filter(org_id=org_id, awb_number__in=awbs)
        shipment_map = {s.awb_number: s for s in shipments}

        updated_count = 0

        with transaction.atomic():
            for item in remittances_data:
                awb = item.get('awb')
                amount = item.get('amount', 0)
                
                shipment = shipment_map.get(awb)
                if not shipment:
                    continue
                
                # Get or create CODRemittance for this shipment
                remittance = CODRemittance.objects.filter(shipment=shipment).first()
                if not remittance:
                    # Fallback if no expected remittance was generated yet
                    remittance = CODRemittance(
                        shipment=shipment,
                        expected_amount=shipment.order.total_price if shipment.order else 0,
                    )
                
                remittance.received_amount = amount
                remittance.actual_remittance_date = date.today()
                remittance.status = 'Received'
                remittance.save()
                
                # Also mark shipment payment_status as Remitted
                shipment.payment_status = 'Remitted'
                shipment.save(update_fields=['payment_status'])
                
                updated_count += 1

        return Response({
            'message': f"Successfully marked {updated_count} remittances as received."
        })
