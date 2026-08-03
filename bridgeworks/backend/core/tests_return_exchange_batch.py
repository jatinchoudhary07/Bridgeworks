from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from core.models import (
    Order,
    ReturnExchangeBatch,
    ReturnExchangeCase,
    ReturnExchangeActivity,
)

User = get_user_model()


class ReturnExchangeBatchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='batch_operator', password='pass1234')
        if hasattr(self.user, 'shop_credentials') and self.user.shop_credentials:
            self.user.shop_credentials.organization_id = 'org-test'
            self.user.shop_credentials.save()
        if hasattr(self.user, 'team_settings') and self.user.team_settings and self.user.team_settings.organization:
            self.user.team_settings.organization.organization_id = 'org-test'
            self.user.team_settings.organization.save()
        self.client.force_authenticate(user=self.user)
        
        # Create a mock order
        self.order1 = Order.objects.create(
            org_id='org-test',
            shopify_id=111111,
            order_number=101,
            total_price=99.99,
        )
        self.order2 = Order.objects.create(
            org_id='org-test',
            shopify_id=222222,
            order_number=102,
            total_price=149.99,
        )

    def test_create_batch_model(self):
        batch = ReturnExchangeBatch.objects.create(
            name="RE-20260603-01",
            created_by=self.user,
            status="Open",
        )
        self.assertEqual(batch.name, "RE-20260603-01")
        self.assertEqual(batch.created_by, self.user)
        self.assertEqual(batch.status, "Open")
        self.assertEqual(str(batch), "RE-20260603-01")

    def test_case_linked_to_batch(self):
        batch = ReturnExchangeBatch.objects.create(
            name="RE-20260603-02",
            created_by=self.user,
        )
        case = ReturnExchangeCase.objects.create(
            batch=batch,
            order=self.order1,
            case_type='return',
            status='pending_qc',
            created_by=self.user,
        )
        self.assertEqual(case.batch, batch)
        self.assertIn(case, batch.cases.all())

    def test_batch_create_endpoint_success(self):
        payload = {
            "items": [
                {"order_id": self.order1.id, "remarks": "Torn package", "return_awb": "AWB123"},
                {"order_id": self.order2.id, "remarks": "Size too small", "return_awb": "AWB456"},
            ]
        }
        
        response = self.client.post('/api/returns-engine/batch/create/', payload, format='json')
        self.assertEqual(response.status_code, 201)
        
        data = response.json()
        self.assertIn("batch_name", data)
        self.assertEqual(data["batch_name"], "Batch 2")
        
        batch = ReturnExchangeBatch.objects.get(name=data["batch_name"])
        self.assertEqual(batch.cases.count(), 2)
        
        case1 = batch.cases.get(order=self.order1)
        self.assertEqual(case1.remarks, "Torn package")
        self.assertEqual(case1.return_awb, "AWB123")
        
        # Verify that activity logs were created
        self.assertTrue(ReturnExchangeActivity.objects.filter(case=case1, action='parcel_scanned').exists())
        self.assertTrue(ReturnExchangeActivity.objects.filter(case=case1, action='moved_to_qc').exists())

    def test_batch_create_endpoint_no_items(self):
        payload = {"items": []}
        response = self.client.post('/api/returns-engine/batch/create/', payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "No items selected for batching"})
