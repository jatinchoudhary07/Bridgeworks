import json
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APITestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from datetime import timedelta

from core.models import ShopCredentials, Order
from core.models.delivery import Shipment, WeatherAlert, ShipmentRiskScore
from core.services.control_tower_service import compute_and_save_shipment_risk_scores
from core.services.weather_service import sync_weather_alerts_via_gemini
from core.tasks.logistics_enterprise import sync_weather_alerts_task

User = get_user_model()


class WeatherSyncTestCase(TestCase):
    """
    Tests for Gemini-powered Weather Sync Service, control tower risk integrations, and tasks.
    """
    def setUp(self):
        cache.clear()
        self.org_id = 'weather-test-org'
        self.user = User.objects.create_user(username='weathertest', password='password123')
        
        # Clear out database state
        WeatherAlert.objects.all().delete()
        Shipment.objects.all().delete()
        Order.objects.all().delete()

        # Update the auto-created shop credential
        ShopCredentials.objects.filter(owner=self.user).update(
            organization_id=self.org_id,
            myshopify_domain='weather-test.myshopify.com'
        )
        self.user.refresh_from_db()

        # Create some shipments for testing
        # Shipment 1: Assam (falls back to active if DB is empty, otherwise governed by DB)
        order_assam = Order.objects.create(
            org_id=self.org_id,
            shopify_id=10101,
            order_number=2001,
            shipping_state='Assam',
            shipping_pincode='781001'
        )
        self.shipment_assam = Shipment.objects.create(
            org_id=self.org_id,
            order=order_assam,
            awb_number='AWB_ASSAM',
            courier_partner='Bluedart',
            current_stage='In Transit',
            dispatch_date=timezone.now() - timedelta(days=2)
        )

        # Shipment 2: Maharashtra
        order_maharashtra = Order.objects.create(
            org_id=self.org_id,
            shopify_id=10102,
            order_number=2002,
            shipping_state='Maharashtra',
            shipping_pincode='400001'
        )
        self.shipment_mah = Shipment.objects.create(
            org_id=self.org_id,
            order=order_maharashtra,
            awb_number='AWB_MAH',
            courier_partner='Bluedart',
            current_stage='In Transit',
            dispatch_date=timezone.now() - timedelta(days=2)
        )

    @patch('google.genai.Client')
    def test_sync_weather_alerts_via_gemini_success(self, mock_client_class):
        """
        Verify that sync_weather_alerts_via_gemini successfully queries the mocked Gemini Client,
        parses the Pydantic-like JSON output, and updates WeatherAlert entries in the database.
        """
        # Set up mock response
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            'alerts': [
                {'state_name': 'maharashtra', 'is_active': True, 'alert_type': 'Heavy Rain'},
                {'state_name': 'assam', 'is_active': False, 'alert_type': 'None'},
                {'state_name': 'kerala', 'is_active': True, 'alert_type': 'Flood Alert'}
            ]
        })
        mock_client.models.generate_content.return_value = mock_response

        # Execute sync
        result = sync_weather_alerts_via_gemini()

        # Assertions on service return value
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['total_states'], 3)
        self.assertEqual(result['active_warnings'], 2)
        self.assertEqual(result['inactive'], 1)

        # Verify DB writes
        mah_alert = WeatherAlert.objects.get(state_name='maharashtra')
        self.assertTrue(mah_alert.is_active)
        self.assertEqual(mah_alert.alert_type, 'Heavy Rain')

        assam_alert = WeatherAlert.objects.get(state_name='assam')
        self.assertFalse(assam_alert.is_active)
        self.assertEqual(assam_alert.alert_type, 'None')

        kerala_alert = WeatherAlert.objects.get(state_name='kerala')
        self.assertTrue(kerala_alert.is_active)
        self.assertEqual(kerala_alert.alert_type, 'Flood Alert')

    def test_risk_scoring_weather_fallback(self):
        """
        If the WeatherAlert table has no records at all, verify it falls back to
        ['assam', 'kerala'] as the default active weather states.
        """
        # Ensure table is empty
        self.assertEqual(WeatherAlert.objects.count(), 0)

        # Run risk scoring
        compute_and_save_shipment_risk_scores(self.org_id)

        # Assam should have weather_flag = True and score modifier applied
        risk_assam = ShipmentRiskScore.objects.get(shipment=self.shipment_assam)
        self.assertTrue(risk_assam.signals['weather_flag'])

        # Maharashtra should have weather_flag = False
        risk_mah = ShipmentRiskScore.objects.get(shipment=self.shipment_mah)
        self.assertFalse(risk_mah.signals['weather_flag'])

    def test_risk_scoring_dynamic_db_alerts(self):
        """
        If the WeatherAlert table contains records, verify that the risk scorer
        correctly checks active status from the database and ignores fallbacks.
        """
        # Populate DB (Maharashtra is active, Assam is INACTIVE)
        WeatherAlert.objects.create(state_name='maharashtra', is_active=True, alert_type='Storm Warning')
        WeatherAlert.objects.create(state_name='assam', is_active=False, alert_type='None')

        # Run risk scoring
        compute_and_save_shipment_risk_scores(self.org_id)

        # Maharashtra should have weather_flag = True
        risk_mah = ShipmentRiskScore.objects.get(shipment=self.shipment_mah)
        self.assertTrue(risk_mah.signals['weather_flag'])

        # Assam should have weather_flag = False (even though it's in the fallback, since DB has records)
        risk_assam = ShipmentRiskScore.objects.get(shipment=self.shipment_assam)
        self.assertFalse(risk_assam.signals['weather_flag'])

    @patch('core.services.weather_service.sync_weather_alerts_via_gemini')
    def test_sync_weather_alerts_task_execution(self, mock_sync_func):
        """
        Verify the Celery/Django-Q background task correctly invokes the service.
        """
        mock_sync_func.return_value = {'status': 'success'}
        res = sync_weather_alerts_task()
        self.assertEqual(res, {'status': 'success'})
        mock_sync_func.assert_called_once()


class WeatherAnomaliesAPITestCase(APITestCase):
    """
    Tests for the dynamic Control Tower anomalies/warnings endpoint.
    """
    def setUp(self):
        cache.clear()
        self.org_id = 'weather-test-org'
        self.user = User.objects.create_user(username='weathertestapi', password='password123')
        self.client.force_authenticate(user=self.user)
        
        # Update the auto-created shop credential
        ShopCredentials.objects.filter(owner=self.user).update(
            organization_id=self.org_id,
            myshopify_domain='weather-test-api.myshopify.com'
        )
        self.user.refresh_from_db()
        
        # Clear out database state
        WeatherAlert.objects.all().delete()

    def test_anomalies_endpoint_fallback(self):
        """If there are no alerts in DB, it falls back to mock alerts."""
        response = self.client.get('/api/control-tower/anomalies/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
        self.assertEqual(response.data[0]['level'], 'CRITICAL')
        self.assertIn('Jaipur Hub', response.data[0]['msg'])

    def test_anomalies_endpoint_dynamic_weather(self):
        """Active weather alerts in the DB should be returned dynamically."""
        WeatherAlert.objects.create(state_name='assam', is_active=True, alert_type='Torrential Rainfall')
        
        response = self.client.get('/api/control-tower/anomalies/')
        self.assertEqual(response.status_code, 200)
        
        # Assam warning should exist and fallback list should be bypassed
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['level'], 'HIGH')
        self.assertIn('Assam', response.data[0]['msg'])
        self.assertIn('Torrential Rainfall', response.data[0]['msg'])

