from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from django.contrib.contenttypes.models import ContentType
from core.views_sales import _resolve_org
from core.permissions import is_org_owner, _check_granular_permission


class IsAllowedCRMAccess(BasePermission):
    """
    Ensures that:
    1. The user is authenticated.
    2. The user belongs to the same shop/organization as the parent entity linked via GenericForeignKey.
    3. Handles check during create (when content_type and object_id are in request data/query parameters)
       and during retrieve/update/delete (verifying target object's parent owner).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Superusers and owners have full access
        if is_org_owner(request.user):
            return True

        # Resolve current request's shop
        _, shop = _resolve_org(request)
        if not shop:
            return False

        # For POST requests, validate the parent entity from request data or query params
        if request.method == 'POST':
            content_type_id = request.data.get('content_type') or request.query_params.get('content_type')
            object_id = request.data.get('object_id') or request.query_params.get('object_id')

            if not content_type_id or not object_id:
                # If fields are missing, let the view raise validation errors rather than permission denied
                return True

            try:
                content_type = ContentType.objects.get_for_id(content_type_id)
                model_class = content_type.model_class()
                parent = model_class.objects.get(pk=object_id)
            except Exception:
                raise ValidationError("Invalid parent entity ID or content type.")

            return self._verify_parent_ownership(request.user, shop, model_class.__name__, parent)

        return True

    def has_object_permission(self, request, view, obj):
        # Superusers and owners have full access
        if is_org_owner(request.user):
            return True

        _, shop = _resolve_org(request)
        if not shop:
            return False

        # Get parent object from the GFK
        parent = obj.content_object
        if not parent:
            raise NotFound("Parent object associated with this CRM item no longer exists.")

        model_name = parent.__class__.__name__
        return self._verify_parent_ownership(request.user, shop, model_name, parent)

    def _verify_parent_ownership(self, user, shop, model_name, parent):
        """Verifies if the parent object belongs to the user's shop and checks module access."""
        # 1. Access boundaries
        if model_name == 'WholesaleLead':
            if parent.shop != shop:
                return False
            # Check if has B2B leads access
            return _check_granular_permission(user, 'operations_fulfillment', 'calling_sheet')

        elif model_name == 'RetailStore':
            if parent.shop != shop:
                return False
            return True

        elif model_name == 'Quotation':
            if parent.shop != shop:
                return False
            return True

        elif model_name == 'RetailStoreCustomer':
            if parent.store.shop != shop:
                return False
            return True

        # Fallback dynamic checks for future-proofing
        if hasattr(parent, 'shop') and parent.shop != shop:
            return False
        elif hasattr(parent, 'store') and hasattr(parent.store, 'shop') and parent.store.shop != shop:
            return False

        return True
