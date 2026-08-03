from rest_framework import viewsets, status
from rest_framework.response import Response
from core.permissions import HasModulePermission

# Mock Order Model / Serializer for demonstration purposes
class OrderViewSet(viewsets.ViewSet):
    """
    Enterprise RBAC Example implementation.
    This ViewSet uses the new `HasModulePermission` to dynamically check
    granluar permissions based on the incoming request method.
    """
    permission_classes = [HasModulePermission]

    # Map the HTTP method to the required module:action string permission.
    required_permissions = {
        'GET': 'orders:view',
        'POST': 'orders:create',
        'PUT': 'orders:edit',
        'PATCH': 'orders:edit',
        'DELETE': 'orders:delete'
    }

    def list(self, request):
        """Maps to GET method - requires 'orders:view'"""
        # Business logic for returning a list of orders
        return Response({"message": "Successfully fetched orders."}, status=status.HTTP_200_OK)

    def create(self, request):
        """Maps to POST method - requires 'orders:create'"""
        # Business logic for creating an order
        return Response({"message": "Order created successfully."}, status=status.HTTP_201_CREATED)

    def retrieve(self, request, pk=None):
        """Maps to GET method -> requires 'orders:view'"""
        return Response({"message": f"Successfully fetched order {pk}."}, status=status.HTTP_200_OK)

    def update(self, request, pk=None):
        """Maps to PUT method -> requires 'orders:edit'"""
        return Response({"message": f"Successfully updating order {pk}."}, status=status.HTTP_200_OK)

    def partial_update(self, request, pk=None):
        """Maps to PATCH method -> requires 'orders:edit'"""
        return Response({"message": f"Successfully patch updating order {pk}."}, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None):
        """Maps to DELETE method -> requires 'orders:delete'"""
        return Response({"message": f"Successfully deleted order {pk}."}, status=status.HTTP_204_NO_CONTENT)
