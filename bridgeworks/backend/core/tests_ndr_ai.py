from datetime import datetime, timedelta
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from core.models import Order, ShopCredentials
from core.models.delivery import Shipment, CourierZoneMapping, NDRPlaybook, NDRFraudFlag, ShipmentException
from core.services.ndr_classifier import classify_ndr_remark, _rule_based_fallback
from core.services.customer_risk_service import compute_ndr_rto_score
from core.services.fraud_detector import audit_shipment_attempts, calculate_geodistance
from core.services.ndr_playbook_runner import run_ndr_playbook_for_order
from django.contrib.auth import get_user_model

User = get_user_model()


class NDRAITests(TestCase):
    def setUp(self):
        self.org_id = 'org-ndr-ai-test'
        self.owner = User.objects.create_user(username='ndr_owner', email='ndr_owner@test.com', password='pass')
        # The user post_save signal automatically creates a ShopCredentials,
        # so we fetch and update it to avoid UNIQUE constraint violations.
        self.shop = ShopCredentials.objects.filter(owner=self.owner).first()
        if not self.shop:
            self.shop = ShopCredentials(owner=self.owner)
        self.shop.organization_id = self.org_id
        self.shop.shipway_email_encrypted = 'x'
        self.shop.shipway_license_key_encrypted = 'x'
        self.shop.chatwoot_endpoint = 'https://chatwoot.example.com/webhook'
        self.shop.set_chatwoot_api_key('test_api_token')
        self.shop.save()

    def test_classifier_fallback(self):
        # Test keyword fallback patterns
        res_refused = _rule_based_fallback("Customer refused to accept parcel")
        self.assertEqual(res_refused['category'], 'REFUSED_DELIVERY')

        res_cod = _rule_based_fallback("Consignee did not have payment ready")
        self.assertEqual(res_cod['category'], 'COD_NOT_READY')

        res_addr = _rule_based_fallback("Incorrect pincode and address incomplete")
        self.assertEqual(res_addr['category'], 'ADDRESS_ISSUE')

        res_closed = _rule_based_fallback("Premises closed, Sunday holiday")
        self.assertEqual(res_closed['category'], 'PREMISES_CLOSED')

        res_unavail = _rule_based_fallback("Consignee phone switched off unreachable")
        self.assertEqual(res_unavail['category'], 'CUSTOMER_UNAVAILABLE')

    @patch('google.genai.Client')
    def test_classifier_retry(self, mock_client_class):
        # Setup mocks
        mock_client = mock_client_class.return_value
        
        class MockResponse:
            text = '{"category": "ADDRESS_ISSUE", "confidence": 90, "explanation": "Street name missing"}'
            
        mock_generate = mock_client.models.generate_content
        
        # Fail twice with 503, succeed on 3rd try
        mock_generate.side_effect = [
            Exception("503 Service Unavailable"),
            Exception("503 Service Unavailable"),
            MockResponse()
        ]
        
        with self.settings(GEMINI_API_KEY='test-key'):
            with patch('time.sleep') as mock_sleep:
                result = classify_ndr_remark("Wrong address")
                
                # Check outcome
                self.assertEqual(result['category'], 'ADDRESS_ISSUE')
                self.assertEqual(result['confidence'], 90)
                # Verify sleep was called twice (for 2s and 4s)
                self.assertEqual(mock_sleep.call_count, 2)
                mock_sleep.assert_any_call(2)
                mock_sleep.assert_any_call(4)

    def test_rto_scorer_signals(self):
        # Create an order in active NDR state
        order = Order.objects.create(
            org_id=self.org_id,
            shopify_id=991,
            order_number=99001,
            contact_phone='9999988888',
            financial_status='pending', # COD
            ndr_reason_category='REFUSED_DELIVERY',
            ndr_call_status='Not Answering',
        )

        shipment = Shipment.objects.create(
            org_id=self.org_id,
            order=order,
            awb_number='AWB991',
            courier_partner='Bluedart',
            current_stage='OFD',
            total_delivery_attempts=2,
            first_attempt_date=timezone.now() - timedelta(days=4)
        )

        score = compute_ndr_rto_score(order)
        # Expected components:
        # Signal 1 & 2: 0 (No CustomerRiskProfile yet)
        # Signal 3: COD (+15)
        # Signal 4: 2 attempts (+10)
        # Signal 5: >3 days elapsed (+5)
        # Signal 6: REFUSED_DELIVERY category (+15)
        # Signal 8: Not Answering call status (+10)
        # Total: 15 + 10 + 5 + 15 + 10 = 55
        self.assertEqual(score, 55)

        # Update call status to "Will Accept" (reduces risk by 30)
        order.ndr_call_status = 'Will Accept'
        order.save()
        score_will_accept = compute_ndr_rto_score(order)
        # COD (15) + Attempts (10) + Elapsed (5) + Category (15) - Will Accept (-30) = 15
        self.assertEqual(score_will_accept, 15)

    @patch('core.services.ndr_playbook_runner.requests.post')
    def test_ndr_playbook_runner(self, mock_post):
        # Mock external webhook response
        mock_post.return_value.ok = True
        mock_post.return_value.status_code = 200

        # Define a playbook
        playbook = NDRPlaybook.objects.create(
            org_id=self.org_id,
            name='Unavailable Playbook',
            reason_category='CUSTOMER_UNAVAILABLE',
            priority=1,
            conditions={'min_order_value': 500},
            actions=[
                {'action': 'send_whatsapp', 'template_id': 100},
                {'action': 'manual_agent_queue'}
            ]
        )

        order = Order.objects.create(
            org_id=self.org_id,
            shopify_id=992,
            order_number=99002,
            contact_phone='9999988888',
            total_price='1000.00',
            ndr_reason_category='CUSTOMER_UNAVAILABLE',
        )

        # Trigger playbook
        success = run_ndr_playbook_for_order(order)
        self.assertTrue(success)
        
        # Verify order has been routed to agent queue in call history
        order.refresh_from_db()
        self.assertEqual(order.ndr_call_status, 'Pending Agent Call')
        self.assertTrue(any('Auto-assigned' in h['remark'] for h in order.ndr_call_history))

    def test_fraud_detector(self):
        # Create zone mapping with hub coordinates
        CourierZoneMapping.objects.create(
            org_id=self.org_id,
            courier_partner='Bluedart',
            pincode='302001',
            zone_code='A',
            city='Jaipur',
            state='Rajasthan',
            hub_name='Jaipur Hub',
            hub_latitude=26.9124,
            hub_longitude=75.7873,
            pincode_latitude=26.9800,  # roughly 10km away
            pincode_longitude=75.8500
        )

        order = Order.objects.create(
            org_id=self.org_id,
            shopify_id=993,
            order_number=99003,
            contact_phone='8888877777',
            shipping_pincode='302001'
        )

        shipment = Shipment.objects.create(
            org_id=self.org_id,
            order=order,
            awb_number='AWB993',
            courier_partner='Bluedart',
            transit_hub='Jaipur Hub',
            shipping_mode='Surface',
        )

        # Create fulfillment and tracking events representing an impossible 6-minute attempt
        from core.models import Fulfillment, TrackingEvent
        ful = Fulfillment.objects.create(order=order)
        from core.models import TrackingInfo
        TrackingInfo.objects.create(fulfillment=ful, number='AWB993', company='Bluedart')

        now = timezone.now()
        TrackingEvent.objects.create(fulfillment=ful, status='Out for Delivery', datetime=now - timedelta(minutes=6))
        TrackingEvent.objects.create(fulfillment=ful, status='Undelivered', datetime=now, details='Premises closed')

        # Delete any auto-created flags/exceptions from signals to test the auditor in isolation
        NDRFraudFlag.objects.filter(shipment=shipment).delete()
        ShipmentException.objects.filter(shipment=shipment).delete()

        # Run audit
        flags = audit_shipment_attempts(shipment)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].flag_type, 'SCAN_GAP')

        # Verify ShipmentException has been automatically logged
        self.assertTrue(ShipmentException.objects.filter(shipment=shipment, exception_type='FraudAlert').exists())

    def test_ndr_conversion_transitions(self):
        # Create an order in active NDR state
        order = Order.objects.create(
            org_id=self.org_id,
            shopify_id=994,
            order_number=99004,
            contact_phone='9999988888',
            financial_status='pending', # COD
            is_ndr=True,
            ndr_conversion_status='PENDING'
        )

        # Create fulfillment and tracking events representing Undelivered -> Delivered
        from core.models import Fulfillment, TrackingEvent, TrackingInfo
        ful = Fulfillment.objects.create(order=order)
        TrackingInfo.objects.create(fulfillment=ful, number='AWB994', company='Bluedart')

        # Update order status to Delivered
        now = timezone.now()
        TrackingEvent.objects.create(fulfillment=ful, status='Undelivered', datetime=now - timedelta(hours=1), details='Customer Unavailable')
        TrackingEvent.objects.create(fulfillment=ful, status='Delivered', datetime=now, details='Delivered successfully')

        order.update_tracking_status()
        self.assertFalse(order.is_ndr)
        self.assertEqual(order.ndr_conversion_status, 'CONVERTED')

        # Reset to pending NDR
        TrackingEvent.objects.create(fulfillment=ful, status='Undelivered', datetime=now + timedelta(hours=1), details='Address Incorrect')
        order.update_tracking_status()
        self.assertTrue(order.is_ndr)
        self.assertEqual(order.ndr_conversion_status, 'PENDING')

        # Complete to RTO
        TrackingEvent.objects.create(fulfillment=ful, status='RTO Delivered', datetime=now + timedelta(hours=2), details='Returned to sender')
        order.update_tracking_status()
        self.assertFalse(order.is_ndr)
        self.assertEqual(order.ndr_conversion_status, 'RTO')
