from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import Sum
from accounting.models import (
    Expense, Invoice, GSTTransaction
)
from core.models.orders import Order
from accounting.services.gst_service import GSTService

@receiver(post_save, sender=Order)
def order_gst_trigger(sender, instance, created, **kwargs):
    if not instance.org_id:
        return
    if instance.status == 'Cancelled':
        GSTTransaction.objects.filter(org_id=instance.org_id, transaction_id__startswith=f"sale_{instance.id}_").delete()
        from accounting.services.gst_service import _parse_date
        date = _parse_date(instance.created_at)
        GSTService.refreshDashboardMetrics(instance.org_id, date.month, date.year)
    else:
        GSTService.captureSaleGST(instance)



@receiver(post_save, sender=Expense)
def expense_gst_trigger(sender, instance, created, **kwargs):
    if not instance.org_id:
        return
    GSTService.captureExpenseGST(instance)


@receiver(post_save, sender=Invoice)
def invoice_gst_trigger(sender, instance, created, **kwargs):
    if not instance.org_id:
        return
    if instance.type == 'purchase':
        GSTService.capturePurchaseGST(instance)



