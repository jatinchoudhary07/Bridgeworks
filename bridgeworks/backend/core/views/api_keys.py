from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from ..models import ShopAPIKey, ShopCredentials
from ..permissions import is_org_owner, _check_granular_permission
from django.utils.crypto import get_random_string
from django.contrib.auth.hashers import make_password
from .helpers import _get_org_id_or_none


class APIKeyManagementView(APIView):
    """
    Internal UI endpoint for Shop Administrators to manage their API keys.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not is_org_owner(request.user) and not _check_granular_permission(request.user, 'settings', 'api_management', 'view'):
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        
        # Get ShopCredentials for the current organization
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization context not found."}, status=status.HTTP_404_NOT_FOUND)
            
        shop = ShopCredentials.objects.filter(organization_id=org_id).first()
        if not shop:
            return Response({"error": "Shop context not found."}, status=status.HTTP_404_NOT_FOUND)


        keys = ShopAPIKey.objects.filter(shop=shop).values('id', 'name', 'prefix', 'created_at', 'last_used_at', 'is_active')
        return Response(keys, status=status.HTTP_200_OK)

    def post(self, request):
        if not is_org_owner(request.user) and not _check_granular_permission(request.user, 'settings', 'api_management', 'create'):
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
            
        name = request.data.get('name')
        if not name:
            return Response({"error": "Key name is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve shop
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({"error": "Organization context not found."}, status=status.HTTP_404_NOT_FOUND)
            
        shop = ShopCredentials.objects.filter(organization_id=org_id).first()
        if not shop:
            return Response({"error": "Shop not found."}, status=status.HTTP_404_NOT_FOUND)


        # Generate Key
        raw_key, prefix = ShopAPIKey.generate_key()
        
        # Save securely
        key_obj = ShopAPIKey.objects.create(
            shop=shop,
            name=name,
            prefix=prefix,
            key_hash=make_password(raw_key),
            is_active=True
        )

        return Response({
            "id": key_obj.id,
            "name": key_obj.name,
            "prefix": key_obj.prefix,
            "raw_key": raw_key, # SHOWN ONLY ONCE
            "message": "Key created successfully. Please copy the raw key now, it will not be shown again."
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, key_id):
        if not is_org_owner(request.user) and not _check_granular_permission(request.user, 'settings', 'api_management', 'delete'):
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            org_id = _get_org_id_or_none(request)
            if not org_id:
                return Response({"error": "Organization context not found."}, status=status.HTTP_404_NOT_FOUND)
                
            # Ensure the key belongs to the requester's shop
            shop = ShopCredentials.objects.get(organization_id=org_id)
            key_obj = ShopAPIKey.objects.get(id=key_id, shop=shop)
            key_obj.is_active = False # Or delete, but deactivation is safer for audit
            key_obj.save()
            return Response({"message": "Key revoked."}, status=status.HTTP_200_OK)
        except ShopCredentials.DoesNotExist:
            return Response({"error": "Shop context not found."}, status=status.HTTP_404_NOT_FOUND)
        except ShopAPIKey.DoesNotExist:
            return Response({"error": "Key not found."}, status=status.HTTP_404_NOT_FOUND)

