import logging


def process_return_prime_webhook(payload):
    """
    Django-Q Background Task: Parses Return Prime webhooks and syncs with BridgeWorks.
    
    Expected events: Request created, approved, updated, received, inspected, refunded, rejected...
    """
    logger = logging.getLogger(__name__)
    
    try:
        from core.models import WebhookLog
        wb_log = WebhookLog.objects.create(
            source='return_prime',
            awb='',
            status='failed',
            payload_json=payload
        )
        
        data = payload.get('request', payload)
        
        return_id = str(data.get('id', ''))
        
        order_data = data.get('order', {})
        order_name = str(order_data.get('name', ''))
        order_id_raw = str(order_data.get('id', ''))
        
        status = data.get('status', 'REQUEST_CREATED').upper()
        
        request_type = data.get('request_type', '').upper()
        req_type_str = request_type if request_type in ['RETURN', 'EXCHANGE'] else 'RETURN'
        
        awb_number = ''
        shipping_company = ''
        line_items = data.get('line_items', [])
        if line_items and isinstance(line_items, list):
            shipping_data = line_items[0].get('shipping', [])
            if shipping_data and isinstance(shipping_data, list):
                awb_number = shipping_data[0].get('awb', '')
                shipping_company = shipping_data[0].get('shipping_company', '')
                
        if not awb_number:
            awb_number = data.get('tracking_number', '') or data.get('awb', '')
            
        request_number = str(data.get('request_number') or data.get('id') or '').strip()
            
        wb_log.awb = awb_number
        wb_log.save(update_fields=['awb'])
        
        customer_notes = ''
        refund_amount = 0.00
        
        if line_items and isinstance(line_items, list):
            first_item = line_items[0]
            customer_notes = first_item.get('reason', '') or first_item.get('notes', '')
            
            refund_data = first_item.get('refund', {})
            if refund_data and isinstance(refund_data, dict):
                refund_amount_data = refund_data.get('refunded_amount', {})
                if refund_amount_data:
                    shop_money = refund_amount_data.get('shop_money', {})
                    refund_amount = shop_money.get('amount', 0.00)
        
        if not return_id:
            logger.error("[RETURN-PRIME] Received webhook without a Return ID. Aborting.")
            wb_log.response_message = "Missing Return ID in payload"
            wb_log.save(update_fields=['response_message'])
            return "Failed: Missing Return ID"

        from core.models import Order, ReturnRequest
        order = None
        
        if order_id_raw:
            order = Order.objects.filter(shopify_id=order_id_raw).first()
            
        if not order and order_name:
            clean_number = ''.join(filter(str.isdigit, order_name))
            if clean_number:
                order = Order.objects.filter(order_number=clean_number).first()
                
        if not order:
            logger.error(f"[RETURN-PRIME] Order not found for return {return_id} (order_name: {order_name})")
            wb_log.response_message = f"Order {order_name} not found"
            wb_log.save()
            return f"Failed: Order {order_name} not found"

        # Update order with return/exchange tracking details
        if awb_number:
            if req_type_str == 'RETURN':
                order.return_awb = awb_number
                order.return_shipping_company = shipping_company or order.return_shipping_company
            elif req_type_str == 'EXCHANGE':
                order.exchange_awb = awb_number
                order.exchange_shipping_company = shipping_company or order.exchange_shipping_company
            order.save(update_fields=['return_awb', 'return_shipping_company', 'exchange_awb', 'exchange_shipping_company'])

        existing_req = ReturnRequest.objects.filter(return_prime_id=return_id).first()
        
        merged_raw_data = data
        if existing_req and existing_req.raw_data:
            old_data = existing_req.raw_data
            
            def deep_merge(target, source):
                for k, v in source.items():
                    if isinstance(v, dict) and isinstance(target.get(k), dict):
                        target[k] = deep_merge(target[k], v)
                    elif isinstance(v, list) and isinstance(target.get(k), list):
                        if all(isinstance(i, dict) and 'id' in i for i in v) and all(isinstance(i, dict) and 'id' in i for i in target.get(k)):
                            target_dict = {item['id']: item for item in target[k]}
                            for src_item in v:
                                if src_item['id'] in target_dict:
                                    target_dict[src_item['id']] = deep_merge(target_dict[src_item['id']], src_item)
                                else:
                                    target_dict[src_item['id']] = src_item
                            target[k] = list(target_dict.values())
                        else:
                            target[k] = v
                    else:
                        target[k] = v
                return target

            merged_raw_data = deep_merge(old_data, data)

        if existing_req:
            existing_req.status = status
            existing_req.request_type = req_type_str
            if awb_number: existing_req.awb_number = awb_number
            if request_number: existing_req.request_number = request_number
            if refund_amount: existing_req.refund_amount = refund_amount
            if customer_notes: existing_req.customer_notes = customer_notes
            existing_req.raw_data = merged_raw_data
            existing_req.save()
            created = False
            return_req = existing_req
        else:
            return_req = ReturnRequest.objects.create(
                return_prime_id=return_id,
                order=order,
                status=status,
                request_type=req_type_str,
                awb_number=awb_number,
                request_number=request_number,
                refund_amount=refund_amount,
                customer_notes=customer_notes,
                raw_data=merged_raw_data
            )
            created = True
        
        # Dynamically propagate exchange details to ReturnExchangeCase if it exists
        if req_type_str == 'EXCHANGE':
            try:
                from core.models import ReturnExchangeCase
                case = ReturnExchangeCase.objects.filter(order=order).first()
                if case:
                    from core.views_returns_engine import _get_exchange_details, _calculate_exchange_settlement
                    from django.utils import timezone
                    exch = _get_exchange_details(return_req)
                    if exch.get('exchange_exists'):
                        case.exchange_exists = exch['exchange_exists']
                        case.exchange_order_number = exch['exchange_order_number']
                        case.exchange_status = exch['exchange_status']
                        case.replacement_order_number = exch['replacement_order_number']
                        case.replacement_order_status = exch['replacement_order_status']
                        case.exchange_created_at = exch['exchange_created_at']
                        case.exchange_meta = {'replacement_products': exch['replacement_products']}
                        
                        update_fields = [
                            'exchange_exists', 'exchange_order_number', 'exchange_status',
                            'replacement_order_number', 'replacement_order_status',
                            'exchange_created_at', 'exchange_meta',
                        ]
                        
                        # If the case was exchange_pending, auto-close it now that the exchange order is created
                        if case.status == 'exchange_pending':
                            calc = _calculate_exchange_settlement(case)
                            case.settlement_type = calc['settlement_type']
                            case.difference_amount = float(calc['difference'])
                            case.settlement_completed_at = timezone.now()
                            case.settlement_method = 'no_settlement' if calc['settlement_type'] == 'no_settlement' else 'auto_settled'
                            case.status = 'exchange_closed'
                            update_fields.extend([
                                'status', 'settlement_type', 'difference_amount',
                                'settlement_completed_at', 'settlement_method',
                            ])
                            
                        case.save(update_fields=update_fields)
            except Exception as ex_err:
                logger.error(f"[RETURN-PRIME] Failed to propagate exchange details to ReturnExchangeCase: {ex_err}")

        # Warm the cache proactively
        try:
            from core.views_returns_engine import _build_scan_payload, _cache_scan_payload
            payload = _build_scan_payload(order, return_req)
            _cache_scan_payload(payload)
        except Exception as cache_err:
            logger.error(f"[RETURN-PRIME] Failed to warm cache for order {order.order_number}: {cache_err}")

        action = "Created" if created else "Updated"
        msg = f"✅ Sync successful: {action} {return_id}"
        
        wb_log.status = 'success'
        wb_log.response_message = msg
        wb_log.save()
        
        logger.info(f"[RETURN-PRIME] {msg} for Order #{order.order_number}")
        return msg
        
    except Exception as e:
        logger.error(f"[RETURN-PRIME] ❌ Error processing webhook: {e}", exc_info=True)
        if 'wb_log' in locals() and wb_log:
            wb_log.status = 'failed'
            wb_log.response_message = f"Exception: {e}"
            wb_log.save()
        return f"Error: {e}"
