from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    ShopCredentials, TeamMemberSettings, Permission, Role, WorkspaceMembership,
    Order, Shipment, CourierZoneMapping, CourierSLAContract, ShipmentException,
    CustomerRiskProfile, TrackingInfo, Fulfillment
)
from core.services.sla_service import (
    compute_sla_kpis, get_sla_breach_table, get_sla_state_performance
)
from core.services.exception_service import auto_detect_exceptions, get_exception_summary
from core.services.customer_risk_service import (
    compute_risk_profile, bulk_recompute, check_order_risk, get_risk_distribution
)
from core.services.hub_analytics_service import get_hub_metrics, get_top_bottlenecks
from core.tasks.logistics_enterprise import auto_detect_exceptions_task, recompute_customer_risk_profiles_task

User = get_user_model()


class LogisticsEnterpriseTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org_id = 'org-logistics-test'

        # 1. Create owner and non-owner users
        self.owner = User.objects.create_user(username='logistics_owner', email='owner@test.com', password='pass1234')
        self.agent = User.objects.create_user(username='logistics_agent', email='agent@test.com', password='pass1234')

        # 2. Setup ShopCredentials (Organization)
        self.org = ShopCredentials.objects.filter(owner=self.owner).first()
        if not self.org:
            self.org = ShopCredentials.objects.create(
                owner=self.owner,
                organization_id=self.org_id,
                shopify_api_key_encrypted='x',
                shopify_api_password_encrypted='x',
                shopify_shop_url_encrypted='https://test-shop.myshopify.com',
                shopify_webhook_secret_encrypted='x',
                shipway_email_encrypted='x',
                shipway_license_key_encrypted='x'
            )
        else:
            self.org.organization_id = self.org_id
            self.org.save()

        # Delete the auto-created ShopCredentials for the non-owner agent
        # to ensure that is_org_owner(self.agent) evaluates to False
        ShopCredentials.objects.filter(owner=self.agent).delete()

        # Reload users from DB to clear Django's cached in-memory relationship descriptors!
        self.owner = User.objects.get(pk=self.owner.pk)
        self.agent = User.objects.get(pk=self.agent.pk)

        # 3. Setup TeamMemberSettings
        TeamMemberSettings.objects.update_or_create(user=self.owner, defaults={'organization': self.org})
        TeamMemberSettings.objects.update_or_create(user=self.agent, defaults={'organization': self.org})

        # 4. Setup Roles and Custom Permissions for Agent
        self.role = Role.objects.create(workspace=self.org, name='Logistics Manager')
        
        # Populate new permissions
        self.perms = {}
        from core.permissions import LOGISTICS_ENTERPRISE_PERMISSIONS
        for perm_id in LOGISTICS_ENTERPRISE_PERMISSIONS:
            perm_obj, _ = Permission.objects.get_or_create(
                identifier=perm_id,
                defaults={'description': f'Can perform {perm_id}'}
            )
            self.perms[perm_id] = perm_obj
            self.role.permissions.add(perm_obj)

        WorkspaceMembership.objects.create(user=self.agent, workspace=self.org, role=self.role)

        # 5. Create some dummy shipments and orders with timezone-aware created_at
        now = timezone.now()
        self.order_1 = Order.objects.create(
            org_id=self.org_id,
            shopify_id=101,
            order_number=1001,
            contact_phone='9999988888',
            customer_first_name='John',
            customer_last_name='Doe',
            contact_email='john@test.com',
            total_price='1500.00',
            current_status='DELIVERED',
            shipping_state='Rajasthan',
            ndr_call_status='Will Accept',
            created_at=now - timedelta(days=5)
        )
        self.order_2 = Order.objects.create(
            org_id=self.org_id,
            shopify_id=102,
            order_number=1002,
            contact_phone='9999988888',
            customer_first_name='John',
            customer_last_name='Doe',
            contact_email='john@test.com',
            total_price='2000.00',
            current_status='IN_TRANSIT',
            shipping_state='Delhi',
            ndr_call_status='',
            created_at=now - timedelta(days=5)
        )
        self.order_3 = Order.objects.create(
            org_id=self.org_id,
            shopify_id=103,
            order_number=1003,
            contact_phone='1111122222',
            customer_first_name='Jane',
            customer_last_name='Smith',
            contact_email='jane@test.com',
            total_price='800.00',
            current_status='RTO',
            shipping_state='Maharashtra',
            ndr_call_status='Refused',
            created_at=now - timedelta(days=5)
        )

        # Create zone mappings for hub analytics
        CourierZoneMapping.objects.create(
            org_id=self.org_id,
            courier_partner='Bluedart',
            pincode='302001',
            zone_code='A',
            city='Jaipur',
            state='Rajasthan',
            region='North',
            hub_name='Jaipur Hub'
        )
        CourierZoneMapping.objects.create(
            org_id=self.org_id,
            courier_partner='Delhivery',
            pincode='110001',
            zone_code='B',
            city='Delhi',
            state='Delhi',
            region='North',
            hub_name='Delhi Hub'
        )

        # Create fulfillments and tracking info
        self.ful_1 = Fulfillment.objects.create(order=self.order_1)
        self.ti_1 = TrackingInfo.objects.create(fulfillment=self.ful_1, number='AWB101', company='Bluedart')
        
        self.ful_2 = Fulfillment.objects.create(order=self.order_2)
        self.ti_2 = TrackingInfo.objects.create(fulfillment=self.ful_2, number='AWB102', company='Delhivery')

        self.ful_3 = Fulfillment.objects.create(order=self.order_3)
        self.ti_3 = TrackingInfo.objects.create(fulfillment=self.ful_3, number='AWB103', company='Bluedart')

        # Create shipments with timezone-aware datetimes and matching zones
        # Delivered shipment with SLA breach
        self.shipment_1 = Shipment.objects.create(
            org_id=self.org_id,
            order=self.order_1,
            awb_number='AWB101',
            courier_partner='Bluedart',
            current_stage='Delivered',
            shipping_mode='Surface',
            transit_hub='Jaipur Hub',
            zone='Within State',
            dispatch_date=now - timedelta(days=10),
            delivery_date=now - timedelta(days=2),
            payment_type='COD'
        )
        # In transit shipment (delayed)
        self.shipment_2 = Shipment.objects.create(
            org_id=self.org_id,
            order=self.order_2,
            awb_number='AWB102',
            courier_partner='Delhivery',
            current_stage='In Transit',
            shipping_mode='Surface',
            transit_hub='Delhi Hub',
            zone='National',
            dispatch_date=now - timedelta(days=20),
            payment_type='PrePaid'
        )
        # RTO shipment
        self.shipment_3 = Shipment.objects.create(
            org_id=self.org_id,
            order=self.order_3,
            awb_number='AWB103',
            courier_partner='Bluedart',
            current_stage='RTO',
            shipping_mode='Surface',
            transit_hub='',
            zone='Within State',
            dispatch_date=now - timedelta(days=5),
            payment_type='COD'
        )

        # 6. Create SLA Contracts
        self.contract_bluedart = CourierSLAContract.objects.create(
            org_id=self.org_id,
            courier_partner='Bluedart',
            zone='Within State',
            shipping_mode='Surface',
            promised_days=3,
            penalty_per_day=Decimal('50.00')
        )
        self.contract_delhivery = CourierSLAContract.objects.create(
            org_id=self.org_id,
            courier_partner='Delhivery',
            zone='National',
            shipping_mode='Surface',
            promised_days=5,
            penalty_per_day=Decimal('100.00')
        )

        # Authenticate client with agent
        self.client.force_authenticate(user=self.agent)

    @patch('core.services.zone_engine.get_mapped_zone', return_value='Within State')
    def test_sla_dashboard_views(self, mock_zone):
        # Test KPIs
        response = self.client.get('/api/logistics/sla/kpis/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('sla_met_pct', data)
        self.assertIn('penalty_recovery', data)

        # Test Courier Performance table
        response = self.client.get('/api/logistics/sla/courier-performance/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 2)

        # Test State Performance table
        response = self.client.get('/api/logistics/sla/state-performance/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('rows', response.json())

        # Test Contract List/Create/Update/Delete CRUD
        response = self.client.get('/api/logistics/sla/contracts/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 2)

        # Create contract
        payload = {
            'courier_partner': 'Delhivery',
            'zone': 'Metro',
            'shipping_mode': 'Air',
            'promised_days': 2,
            'penalty_per_day': 75.00,
            'is_active': True,
            'notes': 'Test contract'
        }
        response = self.client.post('/api/logistics/sla/contracts/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        new_contract_id = response.json()['id']

        # Update contract
        response = self.client.patch(f'/api/logistics/sla/contracts/{new_contract_id}/', {'promised_days': 3}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['promised_days'], 3)

        # Delete contract
        response = self.client.delete(f'/api/logistics/sla/contracts/{new_contract_id}/')
        self.assertEqual(response.status_code, 200)

    def test_exception_center_views(self):
        # Post manual exception
        payload = {
            'shipment_id': self.shipment_1.id,
            'exception_type': 'Lost',
            'description': 'Lost by courier partner',
            'claim_amount': 1500.00
        }
        response = self.client.post('/api/logistics/exceptions/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        exc_id = response.json()['id']

        # List exceptions
        response = self.client.get('/api/logistics/exceptions/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 1)

        # Patch exception (Invalid transition)
        response = self.client.patch(f'/api/logistics/exceptions/{exc_id}/', {'status': 'ClaimRecovery'}, format='json')
        self.assertEqual(response.status_code, 400)

        # Valid transition: Open -> InvestigationPending
        response = self.client.patch(f'/api/logistics/exceptions/{exc_id}/', {'status': 'InvestigationPending'}, format='json')
        self.assertEqual(response.status_code, 200)

        # Summary KPIs
        response = self.client.get('/api/logistics/exceptions/summary/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_open', response.json())

    @patch('core.services.zone_engine.get_mapped_zone', return_value='National')
    def test_exception_auto_detection(self, mock_zone):
        # Trigger auto-detect API
        response = self.client.post('/api/logistics/exceptions/auto-detect/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ShipmentException.objects.filter(org_id=self.org_id, exception_type='Delayed').exists())

        # Test daily Celery task
        # Clear database exceptions
        ShipmentException.objects.all().delete()
        auto_detect_exceptions_task()
        self.assertTrue(ShipmentException.objects.filter(exception_type='Delayed').exists())

    def test_customer_risk_profile_views(self):
        # Force recompute
        response = self.client.post('/api/logistics/customer-risk/recompute/')
        self.assertEqual(response.status_code, 200)

        # List risk profiles
        response = self.client.get('/api/logistics/customer-risk/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()['total'], 1)

        # Check a specific customer's risk
        response = self.client.post('/api/logistics/customer-risk/check/', {'phone': '9999988888'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('risk_score', response.json())

        # Get risk distribution histogram
        response = self.client.get('/api/logistics/customer-risk/distribution/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Low', response.json())

        # Recompute Celery task
        recompute_customer_risk_profiles_task()

    def test_hub_analytics_views(self):
        # Get hub performance analytics
        response = self.client.get('/api/logistics/hub-analytics/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('rows', response.json())

        # Get top bottlenecks
        response = self.client.get('/api/logistics/hub-analytics/top-bottlenecks/')
        self.assertEqual(response.status_code, 200)

    def test_control_tower_views(self):
        # GET live snapshot
        response = self.client.get('/api/logistics/control-tower/live/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('active_shipments', response.json())
        self.assertIn('alerts', response.json())

        # GET courier health
        response = self.client.get('/api/logistics/control-tower/courier-health/')
        self.assertEqual(response.status_code, 200)

        # GET alerts
        response = self.client.get('/api/logistics/control-tower/alerts/')
        self.assertEqual(response.status_code, 200)

    def test_cod_remittance_moved_urls(self):
        # Verify new finance endpoints returns 200
        # Test with owner to bypass any permission checks
        self.client.force_authenticate(user=self.owner)
        response = self.client.get('/api/finance/cod-remittance/')
        self.assertEqual(response.status_code, 200)

        # Old delivery COD endpoints should return 404
        response = self.client.get('/api/delivery/cod-remittance/')
        self.assertEqual(response.status_code, 404)

    def test_rbac_restrictions(self):
        # Authenticate a user with no role/membership
        outsider = User.objects.create_user(username='outsider', email='outsider@test.com', password='pass')
        
        # Delete the auto-created ShopCredentials for the outsider to test RBAC properly
        ShopCredentials.objects.filter(owner=outsider).delete()
        # Reload outsider to clear relationship descriptor cache
        outsider = User.objects.get(pk=outsider.pk)

        self.client.force_authenticate(user=outsider)

        # Accessing SLA dashboard should return 403
        response = self.client.get('/api/logistics/sla/kpis/')
        self.assertEqual(response.status_code, 403)

        # Accessing exceptions should return 403
        response = self.client.get('/api/logistics/exceptions/')
        self.assertEqual(response.status_code, 403)
