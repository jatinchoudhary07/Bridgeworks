from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import Order
from core.models.delivery import PrepaidRemittance, PaymentGatewayFeeRule
from accounting.models import Ledger, JournalEntry, JournalItem, Account

User = get_user_model()

from django.utils import timezone

class PrepaidRemittanceTestCase(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            username='testuser', 
            email='test@example.com', 
            password='password123',
            is_staff=True,
            is_superuser=True # Organization Owners / superusers bypass permission class checks
        )
        self.org_id = self.user.shop_credentials.organization_id
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_prepaid_remittance_auto_generation(self):
        # 1. Create a paid prepaid order
        order = Order.objects.create(
            org_id=self.org_id,
            order_number='1001',
            shopify_id='999991',
            financial_status='paid',
            payment_gateway_names=['Razorpay'],
            total_price=Decimal('1000.00'),
            tags='payment_mode:prepaid',
            created_at=timezone.now()
        )

        # Verify PrepaidRemittance record is automatically generated via signals
        remittance = PrepaidRemittance.objects.filter(order=order).first()
        self.assertIsNotNone(remittance)
        self.assertEqual(remittance.order_number, '1001')
        self.assertEqual(remittance.gateway_name, 'Razorpay')
        self.assertEqual(remittance.gross_amount, Decimal('1000.00'))
        
        # 2% default fee rule should apply
        self.assertEqual(remittance.gateway_fee, Decimal('20.00'))
        self.assertEqual(remittance.net_amount, Decimal('980.00'))
        self.assertEqual(remittance.status, 'Pending')
        self.assertEqual(remittance.expected_settlement_date, order.created_at.date() + timedelta(days=2))

    def test_custom_gateway_fee_rule(self):
        # Create a custom rule for PhonePe (1.8%)
        PaymentGatewayFeeRule.objects.create(
            org_id=self.org_id,
            gateway_name='PhonePe',
            fee_type='percentage',
            fee_value=Decimal('1.80'),
            active=True
        )

        order = Order.objects.create(
            org_id=self.org_id,
            order_number='1002',
            shopify_id='999992',
            financial_status='paid',
            payment_gateway_names=['PhonePe'],
            total_price=Decimal('500.00'),
            tags='payment_mode:prepaid',
            created_at=timezone.now()
        )

        remittance = PrepaidRemittance.objects.filter(order=order).first()
        self.assertIsNotNone(remittance)
        self.assertEqual(remittance.gateway_name, 'PhonePe')
        self.assertEqual(remittance.gateway_fee, Decimal('9.00'))  # 1.8% of 500
        self.assertEqual(remittance.net_amount, Decimal('491.00'))

    def test_reconciliation_upload_and_confirm(self):
        # Create order & remittance
        order = Order.objects.create(
            org_id=self.org_id,
            order_number='1003',
            shopify_id='999993',
            financial_status='paid',
            payment_gateway_names=['Razorpay'],
            total_price=Decimal('1000.00'),
            tags='payment_mode:prepaid',
            created_at=timezone.now()
        )

        rem = PrepaidRemittance.objects.get(order=order)

        # Call list API
        list_resp = self.client.get('/api/finance/prepaid-remittance/')
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.data['summary']['net_expected_remittance'], 980.0)

        # Call confirm API directly simulating matched Excel uploads
        confirm_data = {
            'remittances': [
                {
                    'order_number': '1003',
                    'amount': 980.00,
                    'settlement_date': '2026-06-23'
                }
            ]
        }
        
        confirm_resp = self.client.post('/api/finance/prepaid-remittance/confirm/', data=confirm_data, format='json')
        self.assertEqual(confirm_resp.status_code, 200)

        # Verify remittance status updated
        rem.refresh_from_db()
        self.assertEqual(rem.status, 'Received')
        self.assertEqual(rem.received_amount, Decimal('980.00'))

        # Verify JournalEntry is created in double-entry accounting ledger
        je = JournalEntry.objects.filter(description__icontains='Prepaid Remittance Settlement').first()
        self.assertIsNotNone(je)
        
        # Debited Bank/Settlement Account and Credited Accounts Receivable
        items = list(je.items.all())
        self.assertEqual(len(items), 2)
        
        debit_item = next(i for i in items if i.debit > 0)
        credit_item = next(i for i in items if i.credit > 0)
        
        self.assertEqual(debit_item.debit, Decimal('980.00'))
        self.assertEqual(debit_item.ledger.name, 'Razorpay Settlement Account')
        
        self.assertEqual(credit_item.credit, Decimal('980.00'))
        self.assertEqual(credit_item.ledger.name, 'Accounts Receivable')

    def test_prepaid_remittance_backfill(self):
        # 1. Create a prepaid order (signal will auto-generate remittance)
        order = Order.objects.create(
            org_id=self.org_id,
            order_number='1004',
            shopify_id='999994',
            financial_status='paid',
            payment_gateway_names=['Razorpay'],
            total_price=Decimal('1200.00'),
            tags='payment_mode:prepaid',
            created_at=timezone.now()
        )
        
        # Delete the auto-generated remittance to simulate missing historical records
        PrepaidRemittance.objects.filter(order=order).delete()
        self.assertFalse(PrepaidRemittance.objects.filter(order=order).exists())
        
        # 2. Call the backfill API
        resp = self.client.post('/api/finance/prepaid-remittance/backfill/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['gross_volume'], 1200.0)
        self.assertEqual(resp.data['expected_settlement'], 1176.0) # 1200 - 2% fee
        
        # Verify the record was recreated correctly
        rem = PrepaidRemittance.objects.filter(order=order).first()
        self.assertIsNotNone(rem)
        self.assertEqual(rem.gross_amount, Decimal('1200.00'))
