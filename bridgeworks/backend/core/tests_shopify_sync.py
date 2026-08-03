from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import hmac
import hashlib
import base64
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework import status

from django.utils import timezone as django_timezone
from core.models import ShopCredentials
from core.models.sales import ChannelAbandonedCheckout
from core.tasks.shopify_sync import sync_shopify_checkouts_task

User = get_user_model()

class ShopifySyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='test_user', email='test@test.com', password='password123')
        
        # Configure setting for test
        settings.SHOPIFY_API_SECRET = 'dummy_partner_secret'
        
        self.shop = ShopCredentials.objects.filter(owner=self.user).first()
        if not self.shop:
            self.shop = ShopCredentials.objects.create(
                owner=self.user,
                organization_id='test-org',
                myshopify_domain='test-shop.myshopify.com',
                shopify_webhook_secret_encrypted='dummy_secret',
                shopify_api_key_encrypted='x',
                shopify_api_password_encrypted='x',
                shopify_shop_url_encrypted='test-shop.myshopify.com',
            )
        else:
            self.shop.organization_id = 'test-org'
            self.shop.myshopify_domain = 'test-shop.myshopify.com'
            self.shop.shopify_webhook_secret_encrypted = 'dummy_secret'
            self.shop.shopify_api_key_encrypted = 'x'
            self.shop.shopify_api_password_encrypted = 'x'
            self.shop.shopify_shop_url_encrypted = 'test-shop.myshopify.com'
            self.shop.save()
        self.client.force_authenticate(user=self.user)

    @patch('core.tasks.shopify_sync.shopify_lib')
    @patch('core.shopify_utils.get_shopify_session')
    def test_sync_shopify_checkouts_task(self, mock_get_session, mock_shopify_lib):
        # Setup mocks
        mock_checkout = MagicMock()
        mock_checkout.to_dict.return_value = {
            'id': 123456789,
            'token': 'checkout_token_123',
            'abandoned_checkout_url': 'http://checkout-url.com',
            'customer': {
                'id': 987654,
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john@example.com',
                'phone': '1234567890'
            },
            'shipping_address': {
                'first_name': 'John',
                'last_name': 'Doe',
                'province': 'MH',
                'zip': '400001',
                'city': 'Mumbai'
            },
            'line_items': [
                {'title': 'Product 1', 'quantity': 1, 'price': '999.00'}
            ],
            'total_price': '999.00',
            'created_at': '2026-06-23T10:00:00Z'
        }
        
        mock_shopify_lib.Checkout.find.return_value = [mock_checkout]
        mock_session = MagicMock()
        mock_session.site = 'https://test-shop.myshopify.com'
        mock_session.headers = {}
        mock_get_session.return_value = mock_session

        # Run task
        res = sync_shopify_checkouts_task(self.shop.id, 'test-org')
        self.assertTrue(res['success'])
        self.assertEqual(res['synced'], 1)

        # Assert local DB has checkout
        checkout_obj = ChannelAbandonedCheckout.objects.get(shopify_token='checkout_token_123')
        self.assertEqual(checkout_obj.customer_name, 'John Doe')
        self.assertEqual(checkout_obj.customer_email, 'john@example.com')
        self.assertEqual(checkout_obj.cart_value, 999.00)
        self.assertEqual(checkout_obj.channel_meta['province'], 'MH')

    @patch('django_q.tasks.async_task')
    def test_shopify_sync_abandoned_checkouts_view(self, mock_async_task):
        mock_async_task.return_value = 'task_id_xyz'
        
        url = reverse('shopify-sync-abandoned-checkouts')
        response = self.client.post(url, data={'date_from': '2026-06-01'})
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['task_id'], 'task_id_xyz')
        mock_async_task.assert_called_once()

    def test_django_q_task_status_view_success(self):
        from django_q.models import Success
        Success.objects.create(
            id='task_id_success',
            name='test_task',
            func='core.tasks.shopify_sync.sync_shopify_checkouts_task',
            success=True,
            result='Done',
            started=django_timezone.now(),
            stopped=django_timezone.now()
        )

        url = reverse('django-q-task-status', kwargs={'task_id': 'task_id_success'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['result'], 'Done')

    def test_django_q_task_status_view_failure(self):
        from django_q.models import Failure
        Failure.objects.create(
            id='task_id_failure',
            name='test_task',
            func='core.tasks.shopify_sync.sync_shopify_checkouts_task',
            success=False,
            result='Failed trace',
            started=django_timezone.now(),
            stopped=django_timezone.now()
        )

        url = reverse('django-q-task-status', kwargs={'task_id': 'task_id_failure'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'failed')
        self.assertEqual(response.data['error'], 'Failed trace')

    @patch('core.views.webhooks.ShopifyWebhookView._process_webhook_async')
    @patch('core.views.webhooks._get_decrypted_credentials')
    def test_webhook_signature_security_and_parsing(self, mock_get_decrypted, mock_process_async):
        mock_get_decrypted.return_value = {
            'webhook_secret': 'dummy_secret',
            'shop_url': 'test-shop.myshopify.com',
            'api_key': 'x',
            'password': 'x',
            'api_version': '2024-01'
        }
        
        payload = json.dumps({'id': 99999, 'token': 'webhook_token'})
        payload_bytes = payload.encode('utf-8')
        
        # Calculate valid HMAC
        digest = hmac.new('dummy_secret'.encode('utf-8'), payload_bytes, hashlib.sha256).digest()
        valid_hmac = base64.b64encode(digest).decode('utf-8')

        url = reverse('shopify-webhook')
        
        # 1. Invalid signature should fail with 401
        response = self.client.post(
            url,
            data=payload,
            content_type='application/json',
            HTTP_X_SHOPIFY_SHOP_DOMAIN='test-shop.myshopify.com',
            HTTP_X_SHOPIFY_HMAC_SHA256='wrong_hmac',
            HTTP_X_SHOPIFY_TOPIC='checkouts/update'
        )
        print("WEBHOOK ERROR RESPONSE:", response.status_code, response.content)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        mock_process_async.assert_not_called()

        # 2. Valid signature should return 200
        response = self.client.post(
            url,
            data=payload,
            content_type='application/json',
            HTTP_X_SHOPIFY_SHOP_DOMAIN='test-shop.myshopify.com',
            HTTP_X_SHOPIFY_HMAC_SHA256=valid_hmac,
            HTTP_X_SHOPIFY_TOPIC='checkouts/update'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_process_async.assert_called_once_with(
            'checkouts/update',
            {'id': 99999, 'token': 'webhook_token'},
            'test-org',
            mock_get_decrypted.return_value,
            'test-shop.myshopify.com'
        )
