import json
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APITestCase

from core.models.delivery import (
    Shipment, CourierSLAContract, ShipmentException,
    ShipmentRiskScore, CourierHealthScore, ControlTowerActionAuditLog, PenaltyTicket
)
from core.models import ShopCredentials, Order
from core.services.control_tower_service import (
    compute_and_save_shipment_risk_scores,
    calculate_courier_composite_health,
    process_sla_breach_penalties,
    get_heatmap_geo_stats
)

User = get_user_model()


class ControlTowerEnhancementTestCase(TestCase):
    """
    Unit and integration tests for Control Tower Enhancement services.
    """
    def setUp(self):
        cache.clear()
        self.org_id = 'janki-jewels'
        self.user = User.objects.create_user(username='testops', password='password123')
        
        # Update the auto-created shop credential
        ShopCredentials.objects.filter(owner=self.user).update(
            organization_id=self.org_id,
            myshopify_domain='janki-jewels.myshopify.com'
        )
        self.user.refresh_from_db()

        # Create active warehouse fallback or shipments
        # Let's mock a shipment that is currently active and close to breach
        order1 = Order.objects.create(
            org_id=self.org_id,
            shopify_id=111111111,
            order_number=1001,
            shipping_state='Rajasthan',
            shipping_pincode='302001'
        )
        self.shipment_active = Shipment.objects.create(
            org_id=self.org_id,
            order=order1,
            awb_number='AWB10001',
            courier_partner='Bluedart',
            current_stage='In Transit',
            dispatch_date=timezone.now() - timedelta(days=2) # 2 days ago
        )

        # Create a delivered shipment that has breached SLA
        order2 = Order.objects.create(
            org_id=self.org_id,
            shopify_id=222222222,
            order_number=1002,
            shipping_state='Delhi',
            shipping_pincode='110001'
        )
        self.shipment_breached = Shipment.objects.create(
            org_id=self.org_id,
            order=order2,
            awb_number='AWB10002',
            courier_partner='Bluedart',
            current_stage='Delivered',
            dispatch_date=timezone.now() - timedelta(days=5),
            delivery_date=timezone.now() # delivered today (took 5 days)
        )

        # Create an SLA Contract for Bluedart (promised 3 days, penalty ₹100 per day)
        self.contract = CourierSLAContract.objects.create(
            org_id=self.org_id,
            courier_partner='Bluedart',
            zone='National',
            shipping_mode='Surface',
            promised_days=3,
            penalty_per_day=Decimal('100.00'),
            is_active=True
        )

    def test_predictive_risk_scoring(self):
        """Verify the risk scoring simulator updates models and classifies horizon flags."""
        count = compute_and_save_shipment_risk_scores(self.org_id)
        self.assertTrue(count >= 1)
        
        risk_score = ShipmentRiskScore.objects.get(shipment=self.shipment_active)
        self.assertTrue(risk_score.risk_score > 0.0)
        # Elapsed days = 2, promised days = 3 -> horizon_24h should be True (1 day left)
        self.assertTrue(risk_score.horizon_24h)
        self.assertIn('hub_delay_rate', risk_score.signals)

    def test_courier_composite_health_scoring(self):
        """Verify the composite scorecard executes and stores daily score cards."""
        calculate_courier_composite_health(self.org_id)
        
        score_record = CourierHealthScore.objects.filter(
            courier_id='Bluedart',
            score_date=date.today()
        ).first()
        
        self.assertIsNotNone(score_record)
        self.assertTrue(score_record.composite_score > 0)
        self.assertIn(score_record.status, ['green', 'amber', 'red'])

    def test_process_sla_breach_penalties(self):
        """Verify delivered shipments with breach generate penalty claim tickets."""
        tickets_created = process_sla_breach_penalties(self.org_id)
        self.assertEqual(tickets_created, 1)
        
        ticket = PenaltyTicket.objects.get(shipment=self.shipment_breached)
        # SLA deadline was dispatch + 3 days = dispatch + 3. Delivered after 5 days.
        # Breach = 2 days. Penalty = 2 * ₹100 = ₹200.
        self.assertEqual(ticket.breach_days, 2)
        self.assertEqual(ticket.penalty_amount, Decimal('200.00'))
        self.assertEqual(ticket.status, 'open')

    def test_geo_stats(self):
        """Verify coordinate translation maps return valid Leaflet payloads."""
        stats = get_heatmap_geo_stats(self.org_id, metric='delay')
        self.assertTrue(len(stats) > 0)
        for hub in stats:
            self.assertIn('lat', hub)
            self.assertIn('lng', hub)
            self.assertTrue(hub['active_shipments'] > 0)


class ControlTowerAPITestCase(APITestCase):
    """
    Test suite for Control Tower REST Endpoints.
    """
    def setUp(self):
        cache.clear()
        self.org_id = 'janki-jewels'
        self.user = User.objects.create_user(username='testops', password='password123')
        self.client.force_authenticate(user=self.user)
        
        # Update the auto-created shop credential
        ShopCredentials.objects.filter(owner=self.user).update(
            organization_id=self.org_id,
            myshopify_domain='janki-jewels.myshopify.com'
        )
        self.user.refresh_from_db()

        order3 = Order.objects.create(
            org_id=self.org_id,
            shopify_id=333333333,
            order_number=1003,
            shipping_state='Delhi',
            shipping_pincode='110001'
        )
        self.shipment = Shipment.objects.create(
            org_id=self.org_id,
            order=order3,
            awb_number='AWB20001',
            courier_partner='Bluedart',
            current_stage='In Transit',
            dispatch_date=timezone.now() - timedelta(days=1)
        )

    def test_get_control_tower_kpis(self):
        response = self.client.get('/api/control-tower/kpis/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('active_shipments', response.data)
        self.assertIn('today_dispatches', response.data)

    def test_bulk_reassign_endpoint(self):
        payload = {
            'awbs': ['AWB20001'],
            'target_courier_id': 'Delhivery'
        }
        response = self.client.post('/api/shipments/bulk-reassign/', payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['reassigned'], 1)
        
        # Verify DB updated
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.courier_partner, 'Delhivery')
        
        # Verify audit log logged
        audit_log = ControlTowerActionAuditLog.objects.filter(action_type='REASSIGN').first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.operator, self.user)
