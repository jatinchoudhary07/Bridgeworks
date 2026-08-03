from django.contrib import admin
from .models import InventoryTable, InventoryItem, ShopifyProductCache, ShopifyCollectionCache


@admin.register(InventoryTable)
class InventoryTableAdmin(admin.ModelAdmin):
    list_display = ("organization_id", "table_key", "updated_at")
    list_filter = ("table_key",)
    search_fields = ("organization_id", "table_key")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("id", "table", "created_at")
    list_filter = ("table__table_key",)
    search_fields = ("table__organization_id",)


@admin.register(ShopifyProductCache)
class ShopifyProductCacheAdmin(admin.ModelAdmin):
    list_display = ("shopify_id", "organization_id", "synced_at")
    list_filter = ("organization_id",)
    search_fields = ("organization_id", "shopify_id")
    readonly_fields = ("synced_at",)
    ordering = ("-synced_at",)


@admin.register(ShopifyCollectionCache)
class ShopifyCollectionCacheAdmin(admin.ModelAdmin):
    list_display = ("shopify_id", "organization_id", "synced_at")
    list_filter = ("organization_id",)
    search_fields = ("organization_id", "shopify_id")
    readonly_fields = ("synced_at",)
    ordering = ("-synced_at",)
