from rest_framework import serializers
from ..models import Order, LineItem, WorkforceMember, ExpenseEntry

class PicklistLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = LineItem
        fields = ['sku', 'title', 'quantity']

class PicklistOrderSerializer(serializers.ModelSerializer):
    items = PicklistLineItemSerializer(source='line_items', many=True)
    batch_numbers = serializers.SerializerMethodField()

    def get_batch_numbers(self, obj):
        return [
            {'id': b.id, 'name': b.name or f'Batch {b.id}'}
            for b in obj.batches.all()
        ]

    class Meta:
        model = Order
        fields = ['id', 'order_number', 'created_at', 'status', 'batch_numbers', 'items']

class GlobalPicklistSerializer(serializers.Serializer):
    """
    Groups items across multiple orders for warehouse pickers.
    """
    sku = serializers.CharField()
    title = serializers.CharField()
    total_quantity = serializers.IntegerField()

class WorkforceMemberExternalSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = WorkforceMember
        fields = [
            'id', 'full_name', 'department_name', 'category', 'role_designation', 
            'working_style', 'status', 'phone', 'email', 'current_location', 
        ]

class ExpenseExternalSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = ExpenseEntry
        fields = [
            'id', 'user_email', 'user_name', 'amount', 'spent_on', 
            'category', 'status', 'notes', 'created_at', 'updated_at'
        ]
