from rest_framework import serializers
from .models import InventoryTable, InventoryItem


class InventoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryItem
        fields = ("id", "data", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class InventoryTableSerializer(serializers.ModelSerializer):
    items = InventoryItemSerializer(many=True, read_only=True)

    class Meta:
        model = InventoryTable
        fields = ("id", "table_key", "columns", "items", "updated_at")
        read_only_fields = ("id", "updated_at")
