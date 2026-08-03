from rest_framework import serializers
from core.models import Batch, PackagingBatch
from .orders import SimpleOrderSerializer, MinimalOrderSerializer


class AWBBatchSerializer(serializers.ModelSerializer):
    """
    Lightweight batch serializer for AWB list - uses MinimalOrderSerializer.
    """
    orders = MinimalOrderSerializer(many=True, read_only=True)
    created_by_username = serializers.ReadOnlyField(source='created_by.username')
    order_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Batch
        fields = ['id', 'name', 'created_at', 'created_by_username', 'order_count', 'orders']
    
    def get_order_count(self, obj):
        return len(obj.orders.all())


class BatchSerializer(serializers.ModelSerializer):
    orders = SimpleOrderSerializer(many=True, read_only=True)
    order_numbers = serializers.ListField(child=serializers.CharField(), write_only=True, required=True)
    
    created_by_username = serializers.ReadOnlyField(source='created_by.username')
    
    class Meta: 
        model = Batch
        fields = ['id', 'name', 'created_at', 'orders', 'order_numbers', 'created_by_username']


class PackagingBatchSerializer(serializers.ModelSerializer):
    orders = SimpleOrderSerializer(many=True, read_only=True)
    order_numbers = serializers.ListField(child=serializers.CharField(), write_only=True, required=True)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True, allow_null=True)
    
    class Meta:
        model = PackagingBatch
        fields = ['id', 'created_at', 'orders', 'order_numbers', 'assigned_to_username']
