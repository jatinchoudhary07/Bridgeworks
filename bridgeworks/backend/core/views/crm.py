from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from core.models.crm import CRMActivity, CRMTask, CRMNote, CRMAttachment
from core.models import WholesaleLead, RetailStore, RetailStoreCustomer, Quotation
from core.serializers.crm import (
    CRMActivitySerializer, CRMTaskSerializer, CRMNoteSerializer, CRMAttachmentSerializer
)
from core.permissions_crm import IsAllowedCRMAccess


class CRMBaseViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAllowedCRMAccess]

    def get_content_type_and_object_id(self):
        # 1. Resolve from URL parameters (e.g., nested routes)
        entity_type = self.kwargs.get('entity_type')
        entity_id = self.kwargs.get('entity_id') or self.kwargs.get('lead_pk')

        # 2. Fallback to query parameters (e.g., flat endpoints)
        if not entity_type:
            entity_type = self.request.query_params.get('content_type')
        if not entity_id:
            entity_id = self.request.query_params.get('object_id')

        if not entity_type or not entity_id:
            return None, None

        # Standardize and map the entity type string to the respective ContentType
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

        # If a parent context is provided, narrow down to it directly
        if content_type and object_id:
            return qs.filter(content_type=content_type, object_id=object_id)

        # Multi-tenant isolation: when accessing flat listing, filter CRM records to the user's organization
        from core.views_sales import _resolve_org
        _, shop = _resolve_org(self.request)
        if not shop:
            return qs.none()

        lead_ct = ContentType.objects.get_for_model(WholesaleLead)
        store_ct = ContentType.objects.get_for_model(RetailStore)
        quote_ct = ContentType.objects.get_for_model(Quotation)
        cust_ct = ContentType.objects.get_for_model(RetailStoreCustomer)

        lead_ids = WholesaleLead.objects.filter(shop=shop).values_list('id', flat=True)
        store_ids = RetailStore.objects.filter(shop=shop).values_list('id', flat=True)
        quote_ids = Quotation.objects.filter(shop=shop).values_list('id', flat=True)
        cust_ids = RetailStoreCustomer.objects.filter(store__shop=shop).values_list('id', flat=True)

        return qs.filter(
            Q(content_type=lead_ct, object_id__in=lead_ids) |
            Q(content_type=store_ct, object_id__in=store_ids) |
            Q(content_type=quote_ct, object_id__in=quote_ids) |
            Q(content_type=cust_ct, object_id__in=cust_ids)
        )

    def perform_create(self, serializer):
        content_type, object_id = self.get_content_type_and_object_id()

        # Build injection parameters
        extra_kwargs = {}
        if content_type and object_id:
            extra_kwargs['content_type'] = content_type
            extra_kwargs['object_id'] = object_id

        # Auto-populate creator/uploader field
        model_class = serializer.Meta.model
        if hasattr(model_class, 'created_by'):
            extra_kwargs['created_by'] = self.request.user
        elif hasattr(model_class, 'uploaded_by'):
            extra_kwargs['uploaded_by'] = self.request.user

        serializer.save(**extra_kwargs)


class CRMActivityViewSet(CRMBaseViewSet):
    queryset = CRMActivity.objects.all()
    serializer_class = CRMActivitySerializer


class CRMTaskViewSet(CRMBaseViewSet):
    queryset = CRMTask.objects.all()
    serializer_class = CRMTaskSerializer


class CRMNoteViewSet(CRMBaseViewSet):
    queryset = CRMNote.objects.all()
    serializer_class = CRMNoteSerializer


class CRMAttachmentViewSet(CRMBaseViewSet):
    queryset = CRMAttachment.objects.all()
    serializer_class = CRMAttachmentSerializer
    parser_classes = [MultiPartParser, FormParser]
