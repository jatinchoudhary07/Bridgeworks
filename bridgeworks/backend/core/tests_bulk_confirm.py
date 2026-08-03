from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch
from django.utils import timezone
from django.db.utils import OperationalError

from core.models import Order
from core.tasks.order_automation import bulk_confirm_orders_task

User = get_user_model()


class BulkConfirmTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.force_authenticate(user=self.user)
        
        # Create test orders
        self.order1 = Order.objects.create(
            org_id='org123',
            shopify_id=111111,
            order_number=101,
            status='Pending',
            total_price=150.00
        )
        self.order2 = Order.objects.create(
            org_id='org123',
            shopify_id=222222,
            order_number=102,
            status='Pending',
            total_price=250.00
        )

    @patch('core.views.orders._get_org_id_or_none', return_value='org123')
    @patch('core.views.orders.HasModulePermission.has_permission', return_value=True)
    @patch('core.views.orders.async_task')
    def test_bulk_confirm_orders_view_queues_task(self, mock_async_task, mock_has_perm, mock_get_org):
        mock_async_task.return_value = 'mock-task-uuid-123'
        
        response = self.client.post('/api/orders/bulk-confirm/', {
            'order_numbers': [101, 102]
        }, format='json')
        
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['task_id'], 'mock-task-uuid-123')
        
        # Verify task enqueued correctly
        mock_async_task.assert_called_once_with(
            'core.tasks.order_automation.bulk_confirm_orders_task',
            [101, 102],
            'org123',
            self.user.id
        )

    def test_bulk_confirm_orders_task_updates_db(self):
        # Set one order to 'On Hold' to verify both 'Pending' and 'On Hold' are confirmed.
        self.order2.status = 'On Hold'
        self.order2.save()
        
        res = bulk_confirm_orders_task([101, 102], 'org123', self.user.id)
        self.assertEqual(res['confirmed_count'], 2)
        self.assertEqual(res['total'], 2)
        
        self.order1.refresh_from_db()
        self.order2.refresh_from_db()
        
        self.assertEqual(self.order1.status, 'Confirmed')
        self.assertEqual(self.order2.status, 'Confirmed')
        self.assertEqual(self.order1.confirmed_by, self.user)
        self.assertIsNotNone(self.order1.confirmed_at)

    @patch('core.views.orders._get_org_id_or_none', return_value='org123')
    @patch('core.views.orders.HasModulePermission.has_permission', return_value=True)
    def test_bulk_confirm_status_view_pending(self, mock_has_perm, mock_get_org):
        response = self.client.get('/api/orders/bulk-confirm/status/non-existent-task-id/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'pending')

    @patch('core.views.orders._get_org_id_or_none', return_value='org123')
    @patch('core.views.orders.HasModulePermission.has_permission', return_value=True)
    def test_bulk_confirm_status_view_success(self, mock_has_perm, mock_get_org):
        from django_q.models import Success
        
        success_task = Success.objects.create(
            id='mock-success-task-id',
            name='bulk-confirm-task',
            func='core.tasks.order_automation.bulk_confirm_orders_task',
            success=True,
            result={'confirmed_count': 2, 'total': 2},
            started=timezone.now(),
            stopped=timezone.now()
        )
        
        response = self.client.get(f'/api/orders/bulk-confirm/status/{success_task.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        self.assertEqual(response.json()['result']['confirmed_count'], 2)

    @patch('core.views.orders._get_org_id_or_none', return_value='org123')
    @patch('core.views.orders.HasModulePermission.has_permission', return_value=True)
    def test_bulk_confirm_status_view_failure(self, mock_has_perm, mock_get_org):
        from django_q.models import Failure
        
        failure_task = Failure.objects.create(
            id='mock-failure-task-id',
            name='bulk-confirm-task',
            func='core.tasks.order_automation.bulk_confirm_orders_task',
            success=False,
            result='Database lock error occurred.',
            started=timezone.now(),
            stopped=timezone.now()
        )
        
        response = self.client.get(f'/api/orders/bulk-confirm/status/{failure_task.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'failed')
        self.assertEqual(response.json()['error'], 'Database lock error occurred.')

    @patch('django.db.connection.vendor', 'postgresql')
    @patch('django.db.connection.cursor')
    def test_rls_middleware_handles_operational_error(self, mock_cursor):
        mock_cursor.side_effect = OperationalError("FATAL: database system is in recovery mode")
        
        # When calling an endpoint, RLSMiddleware catches OperationalError and returns 503
        response = self.client.get('/api/current-user/')
        
        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.json()['error'])
