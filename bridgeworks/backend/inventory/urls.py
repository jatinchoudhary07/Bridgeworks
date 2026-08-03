from django.urls import path
from .views import (
    InventoryTableView,
    InventoryItemListCreateView,
    InventoryItemDetailView,
    InventoryBulkDeleteView,
    BestSellingView,
    ProductionOrderRequestView,
    AIStockKeeperView,
    ShopifyProductsView,
    ShopifyCategoriesView,
    ProductSheetSyncView,
    ShopifyCacheSyncView,
    VendorListCreateView,
    VendorDetailView,
    PurchaseOrderListCreateView,
    PurchaseOrderDetailView,
)

urlpatterns = [
    # ── Shopify Live Data ────────────────────────────────────────────────────
    path("shopify/products/", ShopifyProductsView.as_view(), name="shopify-products"),
    path("shopify/categories/", ShopifyCategoriesView.as_view(), name="shopify-categories"),
    path("shopify/sync/", ShopifyCacheSyncView.as_view(), name="shopify-cache-sync"),

    # ── Production Software Sync ─────────────────────────────────────────────
    path("production-software/sync/", ProductSheetSyncView.as_view(), name="production-sheet-sync"),

    # ── Analytics (must be before <table_key> to avoid URL conflicts) ──────
    path("analytics/best-selling/", BestSellingView.as_view(), name="inventory-best-selling"),
    path("analytics/ai-stock/", AIStockKeeperView.as_view(), name="inventory-ai-stock"),

    # ── Production Orders ─────────────────────────────────────────────────
    path("production-orders/", ProductionOrderRequestView.as_view(), name="inventory-production-orders"),

    # ── Vendor Management ─────────────────────────────────────────────────
    path("vendors/", VendorListCreateView.as_view(), name="vendor-list"),
    path("vendors/<int:vendor_id>/", VendorDetailView.as_view(), name="vendor-detail"),

    # ── Purchase Orders ───────────────────────────────────────────────────
    path("purchase-orders/", PurchaseOrderListCreateView.as_view(), name="purchase-order-list"),
    path("purchase-orders/<int:po_id>/", PurchaseOrderDetailView.as_view(), name="purchase-order-detail"),

    # ── Table config + full data ────────────────────────────────────────────
    path("<str:table_key>/", InventoryTableView.as_view(), name="inventory-table"),
    path("<str:table_key>/items/", InventoryItemListCreateView.as_view(), name="inventory-item-list"),
    path("<str:table_key>/items/bulk-delete/", InventoryBulkDeleteView.as_view(), name="inventory-bulk-delete"),
    path("<str:table_key>/items/<int:item_id>/", InventoryItemDetailView.as_view(), name="inventory-item-detail"),
]
