from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from core.models import Order, PackagingBatch, UnifiedNotification

User = get_user_model()

class PackagingAssignmentNotificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(username='manager', password='pass1234')
        self.agent = User.objects.create_user(username='agent', password='pass1234')
        
        # Create unfulfilled orders that can be sent for packaging (must have status other than 'Sent for Packaging' / 'Packaged', e.g. 'Fulfilled')
        self.order1 = Order.objects.create(
            order_number=1001,
            shopify_id=123456789,
            org_id='test-org',
            status='Batched',
            internal_fulfillment_status='Fulfilled',
            total_price=100.0
        )
        self.order2 = Order.objects.create(
            order_number=1002,
            shopify_id=987654321,
            org_id='test-org',
            status='Batched',
            internal_fulfillment_status='Fulfilled',
            total_price=150.0
        )

    def test_assign_packaging_batch_notifies_agent(self):
        self.client.force_authenticate(user=self.manager)
        payload = {
            'order_numbers': [1001, 1002],
            'assigned_to_id': self.agent.id
        }

        with patch('core.views.batches._get_org_id_or_none', return_value='test-org'), \
             patch('core.services.notifications.get_channel_layer', return_value=None):
            response = self.client.post('/api/packaging-batches/create/', payload, format='json')

        self.assertEqual(response.status_code, 201)
        batch_id = response.json()['batch_id']

        # Check if the notification was created
        notifications = list(
            UnifiedNotification.objects.filter(
                recipient=self.agent,
                module='tasks',
                action='share',
                entity_type='packaging_batch',
                entity_id=str(batch_id)
            )
        )
        self.assertEqual(len(notifications), 1)
        notif = notifications[0]
        self.assertEqual(notif.actor, self.manager)
        self.assertIn("assigned 2 order(s) for packaging", notif.message)
        self.assertEqual(notif.metadata.get('category'), 'operations')
        self.assertEqual(notif.metadata.get('priority'), 'medium')
        self.assertEqual(notif.metadata.get('sound_category'), 'assign_batch')
        self.assertEqual(notif.deep_link.get('pathname'), '/operations/packaging')
        self.assertEqual(notif.deep_link.get('batchId'), str(batch_id))

    def test_assign_packaging_batch_to_self_does_not_notify_self(self):
        self.client.force_authenticate(user=self.agent)
        payload = {
            'order_numbers': [1001, 1002],
            'assigned_to_id': self.agent.id
        }

        with patch('core.views.batches._get_org_id_or_none', return_value='test-org'), \
             patch('core.services.notifications.get_channel_layer', return_value=None):
            response = self.client.post('/api/packaging-batches/create/', payload, format='json')

        self.assertEqual(response.status_code, 201)
        batch_id = response.json()['batch_id']

        # No notification should be sent to the agent since agent == manager (self)
        self.assertFalse(
            UnifiedNotification.objects.filter(
                recipient=self.agent,
                entity_type='packaging_batch',
                entity_id=str(batch_id)
            ).exists()
        )
