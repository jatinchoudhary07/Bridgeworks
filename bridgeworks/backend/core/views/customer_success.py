from rest_framework import viewsets, status, permissions
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from core.models.customer_success import CustomerHealthScore, RenewalTracker, SuccessTask
from core.serializers.customer_success import (
    CustomerHealthScoreSerializer, RenewalTrackerSerializer, SuccessTaskSerializer
)
from core.permissions_crm import IsAllowedCRMAccess
from core.views_sales import _resolve_org
from core.models import WholesaleLead, RetailStore, RetailStoreCustomer, Quotation

class CustomerSuccessBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAllowedCRMAccess]

    def get_content_type_and_object_id(self):
        entity_type = self.kwargs.get('entity_type')
        entity_id = self.kwargs.get('entity_id') or self.kwargs.get('lead_pk')

        if not entity_type:
            entity_type = self.request.query_params.get('content_type')
        if not entity_id:
            entity_id = self.request.query_params.get('object_id')

        if not entity_type or not entity_id:
            return None, None

        slug = str(entity_type).lower().replace('_', '-').rstrip('/')
        mapping = {
            'wholesale-leads': 'wholesalelead',
            'wholesale-lead': 'wholesalelead',
            'wholesalelead': 'wholesalelead',
            'leads': 'wholesalelead',
            'lead': 'wholesalelead',

            'retail-stores': 'retailstore',
            'retail-store': 'retailstore',
            'retailstore': 'retailstore',
            'companies': 'retailstore',
            'company': 'retailstore',
            'stores': 'retailstore',
            'store': 'retailstore',

            'quotations': 'quotation',
            'quotation': 'quotation',
            'quotes': 'quotation',
            'quote': 'quotation',

            'retail-store-customers': 'retailstorecustomer',
            'retail-store-customer': 'retailstorecustomer',
            'retailstorecustomer': 'retailstorecustomer',
            'customers': 'retailstorecustomer',
            'customer': 'retailstorecustomer',
        }

        model_name = mapping.get(slug)
        if not model_name:
            raise ValidationError(f"Unsupported entity type: {entity_type}")

        try:
            content_type = ContentType.objects.get(app_label='core', model=model_name)
        except ContentType.DoesNotExist:
            raise ValidationError(f"ContentType not found for model: {model_name}")

        return content_type, entity_id

    def get_queryset(self):
        qs = super().get_queryset()
        content_type, object_id = self.get_content_type_and_object_id()

        if content_type and object_id:
            return qs.filter(content_type=content_type, object_id=object_id)

        _, shop = _resolve_org(self.request)
        if not shop:
            return qs.none()

        return qs.filter(shop=shop)

    def perform_create(self, serializer):
        _, shop = _resolve_org(self.request)
        if not shop:
            raise ValidationError("Organization/Shop not found")

        content_type, object_id = self.get_content_type_and_object_id()

        extra_kwargs = {'shop': shop}
        if content_type and object_id:
            extra_kwargs['content_type'] = content_type
            extra_kwargs['object_id'] = object_id

        model_class = serializer.Meta.model
        if hasattr(model_class, 'created_by'):
            extra_kwargs['created_by'] = self.request.user
        elif hasattr(model_class, 'assignee') and 'assignee' not in self.request.data:
            extra_kwargs['assignee'] = self.request.user

        serializer.save(**extra_kwargs)


class CustomerHealthScoreViewSet(CustomerSuccessBaseViewSet):
    queryset = CustomerHealthScore.objects.all()
    serializer_class = CustomerHealthScoreSerializer


class RenewalTrackerViewSet(CustomerSuccessBaseViewSet):
    queryset = RenewalTracker.objects.all()
    serializer_class = RenewalTrackerSerializer


class SuccessTaskViewSet(CustomerSuccessBaseViewSet):
    queryset = SuccessTask.objects.all()
    serializer_class = SuccessTaskSerializer
