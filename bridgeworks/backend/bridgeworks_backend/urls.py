from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from core.views_shopify_auth import shopify_install, shopify_callback, shopify_app_landing
from core.views_auth import CustomTokenObtainPairView, CustomTokenRefreshView, LogoutView, google_callback_with_jwt, google_id_token, google_token_exchange
from core.views_logistics_analytics import LogisticsDashboardView
from core.views_chatwoot import (
    ChatwootSSORedirectView, 
    ChatwootSidebarWidgetView, 
    ChatwootWebhookView,
    ChatwootAgentSimulationView,
    ChatwootAgentAuditLogsView,
    ChatwootAgentConfigView,
    ChatwootInboxAgentsView,
    ChatwootAgentTriggerScrapeView,
    ChatwootAgentNuggetsView,
    ChatwootAgentNuggetParseView
)

from core.views import (
    # --- AUTH & USER ---
    OnboardingView,
    get_csrf_token,
    CurrentUserView,  # <--- Updated Import (Class-based View)
    ShopProfileView,
    ShopLogoUploadView,
    UserBankDetailsView,
    UserProfilePictureView,
    UserDocumentUploadView,
    UserPermissionsView,
    UserListView,
    RoleListCreateView,
    RoleDetailView,

    # --- TEAM MANAGEMENT ---
    InviteTeammateView, 
    TeamMemberListAPIView,
    TeamMemberDetailView,
    TeammatePermissionsView,
    CoFounderToggleView,
    HRUserAttendanceSettingsView,
    PermissionSchemaView, 
    TeammateDeleteView,
    WorkforceDepartmentListCreateView,
    WorkforceDepartmentDetailView,
    WorkforceMemberListCreateView,
    WorkforceMemberDetailView,
    WorkforceMemberBulkArchiveView,
    WorkforceMemberPermissionsView,
    WorkforceDocumentUploadView,

    # --- ORDER RETRIEVAL ---
    GetOrdersView,
    GetUnfulfilledOrdersView,
    ConfirmedOrdersView,
    AllOrdersView,
    PaginatedPendingOrdersView,
    PaginatedOrderListView,
    OnHoldOrdersView,
    OrderLookupView,
    SyncOrderView,

    # --- ORDER ACTIONS ---
    UpdateOrderView,
    BulkScanActionView,
    BulkConfirmOrdersView,
    BulkConfirmStatusView,
    FetchTrackingDataView,
    confirmation_stats,
    
    # --- BATCHING & PACKAGING ---
    BatchListView,
    BatchCreateView,
    PackagingBatchListView,
    PackagingBatchCreateView,
    PackagingImageView,

    # --- MANIFEST ---
    ManifestSheetView,
    PaginatedManifestOrderListView,
    BulkManifestOrdersView,
    ManifestOrdersListView,

    # --- WEBHOOKS ---
    ShopifyWebhookView,
    
    # --- CUSTOMER CARE ---
    CaseFileListCreateView, 
    CaseFileRetrieveUpdateView, 
    IssueCommentListCreateView,
    CustomerHistoryView,
    TrackingPageOrderListView,
    LogNDRCallView,
    GenerateAWBAndBatchView,
    AWBBatchListView,
    FetchTrackingAndBatchView,
    MergeLabelsView,
    GlobalSearchView,
    PicklistAggregationView, LogisticsAnalyticsView,
    AgentConfigurationView,
    AgentActivityView,
    ReevaluateOrderView,
    ChatAnalyticsView,
    ThorfinnChatSessionListView,
    ThorfinnChatSessionDetailView,
    ThorfinnChatMessageListView,
    AnalyticsAgentConfigurationView,
    MarketingAgentConfigurationView,
    LogisticsAgentConfigurationView,
    ServiceAgentConfigurationView,
)

from core.views import (
    CRMActivityViewSet, CRMTaskViewSet, CRMNoteViewSet, CRMAttachmentViewSet,
    WorkflowViewSet, WorkflowExecutionViewSet, check_overdue_tasks_view,
    RecommendationViewSet, recommendation_summary, run_recommendation_scan,
    ApprovalPolicyViewSet, ApprovalRequestViewSet,
    SalesQuotaViewSet, get_sales_forecast,
    DealRiskViewSet,
    CustomerHealthScoreViewSet, RenewalTrackerViewSet, SuccessTaskViewSet,
    EmailThreadViewSet, crm_advanced_report,
    SystemAuditLogViewSet, SavedFilterViewSet, import_leads_csv, export_leads_csv,
    WebhookSubscriptionViewSet, OutboundWebhookLogViewSet, OAuthAppViewSet, IntegrationConnectionViewSet,
    SystemObservabilityView
)

from core.views.sales_incentives import (
    SalesRepresentativeViewSet, SalesActivityViewSet,
    IncentiveRuleViewSet, IncentiveRecordViewSet
)

from core.views_rto import (
    RTOReceiveScanView,
    RTOBatchCreateView,
    RTOUnpackListView,
    RTORestockActionView,
)

from core.views_rto_engine import (
    RTOEngineScanView,
    RTOEngineDispatchView,
    RTOEngineBatchScanView,
    RTOEngineBatchDispatchView,
    RTOEngineQCListView,
    RTOEngineQCActionView,
    RTOEngineQCBulkInventoryView,
    RTOEngineQCBulkActionView,
    RTOEngineInvestigationListView,
    RTOEngineInvestigationActionView,
    RTOEngineInvestigationBulkActionView,
    RTOEngineRepairBulkCompleteView,
    RTOEngineLogView,
)

from core.ndr_views import (
    NDRBatchListView,
    UploadPanelCSVView,
    UploadRawTextView,
    GenerateEscalationExportView,
    GenerateCallingSheetBatchView,
    BulkNDRActionView,
    SagepilotWebhookView,
    WebhookLogListView,
    NDRAnalyticsDataView,
    NDRPlaybookListView,
    NDRPlaybookDetailView,
    NDRFraudFlagListView,
    NDRFraudFlagResolveView,
)

from core.views_delivery_analytics import (
    DeliveryDashboardView,
    ShipmentCostUploadView,
    ReconciliationView,
    ShipmentCostManualView,
    CODRemittanceListView,
    CODRemittanceWeeklySummaryView,
    ConciliationListView,
    FreightInvoiceListView,
    FreightInvoiceUploadView,
    InvoiceSeizeView,
    DisputeListView,
    FreightInvoiceDetailView,
    DisputeExportView,
)
from core.views_invoice_lines import (
    InvoiceExcelUploadView,
    InvoiceLineListView,
    InvoiceLineDisputeView,
    InvoiceDisputeAllView,
    InvoiceDisputeReportView,
    BillingPatternsView,
    ReconciliationDashboardView,
    InvoiceReanalyseView,
    InvoiceBulkReanalyseView,
)

from core.views_cod_reconciliation import (
    CODRemittanceUploadView,
    CODRemittanceConfirmView
)

from core.views_prepaid_remittance import (
    PrepaidRemittanceListView,
    PrepaidRemittanceWeeklySummaryView,
    PrepaidRemittanceUploadView,
    PrepaidRemittanceConfirmView,
    PaymentGatewayFeeRuleView,
    PrepaidRemittanceBackfillView
)

from core.views_shipping_engine import (
    WarehouseListView,
    WarehouseDetailView,
    WarehouseSetDefaultView,
    RateCardListView,
    RateCardDetailView,
    RateCardUploadView,
    RateCardVisionScanView,
    ZoneCheckView,
    RecalculateCostsView,
    CourierSurchargeHistoryView,
    CourierZoneMappingUploadView
)

from core.views_postit import (
    StickyNoteViewSet,
    PostItNotificationViewSet,
    DiaryEntryListCreateView,
    DiaryEntryDetailView,
    HRDiaryLogbookListView,
)
from core.views_notifications import UnifiedNotificationViewSet, NotificationPreferenceViewSet

from core.views_chat import (
    ChatMessageListCreateView,
    ChatMessageDetailView,
    ChatMessageArchiveView,
    ChatMessageAttachmentView,
    ChatMessageReadView,
    ChatMessageReactionView,
    ChatUnreadCountView,
    ConversationsListView,
    ChatRoomListCreateView,
    ChatRoomDetailView,
    ChatRoomMemberView,
    ChatRoomPinView,
    ChatChannelPinView,
    ChatChannelListCreateView,
    ChatChannelDetailView,
    ChatChannelMemberView,
    ChatCommunityListCreateView,
    ChatCommunityDetailView,
    ChatCommunityMemberView,
    ChatTaskCreateView,
    ChatTaskToggleView,
    ChatDeliveryMetricsView,
    ChatClientDropMetricView,
    ChatPresenceHeartbeatView,
    ChatPresenceListView,
    ChatPresenceOfflineView,
    ChatSearchView,
)
from core.views_gmail import (
    GmailAuthStatusView,
    GmailAuthInitiateView,
    GmailAuthCallbackView,
    GmailDisconnectView,
    EmailListView,
    EmailSearchView,
    EmailDetailView,
    EmailSendView,
    EmailModifyView,
    EmailTrashView,
    EmailAttachmentView,
)
from core.views_calendar import (
    CalendarAuthStatusView,
    CalendarAuthInitView,
    CalendarAuthCallbackView,
    ScheduleMeetingView,
    CalendarEventsView,
    CalendarEventDetailView,
    CalendarSyncView,
)
from core.views_mydesk import (
    MyDeskNoteListCreateView,
    MyDeskNoteDetailView,
    MyDeskNoteAttachmentDetailView,
    MyDeskNoteShareView,
    MyDeskNoteVersionRestoreView,
    MyDeskNoteVersionDetailView,
    MyDeskNoteShareRecipientsView,
    MyDeskNoteAISummaryView,
    MyDeskNoteAICopilotView,
    PersonalTodoListCreateView,
    PersonalTodoDetailView,
    PersonalTodoAttachmentDetailView,
    ExpenseListCreateView,
    ExpenseDetailView,
    ExpenseSendToHrView,
    LeaveRequestListCreateView,
    LeaveRequestDetailView,
    HrLeaveRequestView,
    MyDeskAttendanceOverviewView,
    MyDeskAttendanceEntryCreateView,
    MyDeskPayrollOverviewView,
    MyDeskPayrollDeclarationsView,
    MyDeskPayrollDisputeView,
    HrAttendanceTodayView,
    HrAttendanceMonthlyRegisterView,
    HrAttendanceEmployeeSummaryView,
    AttendanceRulebookView,
    MyAttendanceRulebookView,
    HrRegularizationQueueView,
    HrAttendanceOverrideView,
    AttendanceScoreView,
    HrAttendanceScoreListView,
    HrMasterTaskTrackerView,
    HrMasterTaskTrackerAssignView,
    HrMasterTaskTrackerExportView,
    HrMeetingManagerOverviewView,
    HrMeetingManagerCompanyEventDetailView,
    HrPayrollRunControlView,
    HrPayrollDashboardView,
    HrPayrollEmployeeDetailView,
    FinancePayrollLedgerView,
    HrExpenseTrackerOverviewView,
    HrExpenseTrackerMemberDetailView,
    HrExpenseTrackerApprovalActionView,
    HrExpenseTrackerRequestApprovalView,
    GalleryAlbumListCreateView,
    GalleryItemListCreateView,
    GalleryItemDetailView,
    GalleryItemDownloadView,
    VaultSaveFromChatView,
    VaultStorageStatsView,
)
from core.views_attendance_geo import (
    OfficeLocationListCreateView,
    OfficeLocationDetailView,
    OfficeLocationGeocodeView,
    OfficeIPCreateView,
    OfficeIPDeleteView,
    DetectMyIPView,
    AttendanceSessionStartView,
    AttendanceSessionEndView,
    AttendanceSessionListView,
    AttendanceAnomalyListView,
    AttendanceAnomalyResolveView,
    AttendanceReportView,
    AttendanceReportExportView,
    PublicHolidayListCreateView,
    PublicHolidayDetailView,
    AttendanceSessionExemptionListCreateView,
    AttendanceSessionExemptionDetailView,
    AttendanceSessionHeartbeatView,
)
from core.views_finance import (
    FinanceIncomeListCreateView,
    FinanceIncomeDetailView,
    FinanceExpenseListCreateView,
    FinanceExpenseDetailView,
    FinanceOptionListCreateView,
    FinanceOptionDetailView,
    FinanceLedgerSummaryView,
    FinanceTrialBalanceView,
    FinanceProfitLossView,
    FinanceBalanceSheetView,
    FinancePendingExpenseListView,
    FinancePendingExpenseSyncView,
    FinancePendingExpenseApproveView,
    FinancePendingExpenseRejectView,
    FinancePendingExpenseMemberDetailView,
    FinanceAIChatView,
    FinanceGeneratePlanView,
    FinanceGenerateReportView,
    FinanceControlTowerDashboardView,
)
from core.views_returns import (
    ReturnPrimeWebhookView,
    ReturnScannerView,
    ReturnRequestListView,
    ReturnActionStockView,
    ReturnStockingListView,
)
from core.views_returns_engine import (
    ReturnEngineScanLookupView,
    ReturnEngineBatchScanView,
    ReturnEngineMoveToQCView,
    ReturnEngineCasesListView,
    ReturnEngineCaseDetailView,
    ReturnEngineSearchView,
    ReturnEngineActivityView,
    ReturnEngineQCActionView,
    ReturnEngineRefundListView,
    ReturnEngineRefundDetailView,
    ReturnEngineRefundActionView,
    ReturnEngineExchangeListView,
    ReturnEngineExchangeDetailView,
    ReturnEngineExchangeActionView,
    ReturnEngineBatchCreateView,
    ReturnEngineConvertToExchangeView,
    ReturnEngineSelfShippedIntakeView,
    ReturnEngineProductSearchView,
    ReturnEngineOrderLookupView,
    ReturnEngineManualIntakeView,
    ReturnEngineProductVariantsView,
    ReturnEngineCreateExchangeOrderView,
)
from core.views.external import (
    PicklistExternalAPIView,
    WorkforceExternalAPIView,
    ExpenseExternalAPIView,
    RepairQueueExternalAPIView,
    RepairQueueCompleteExternalAPIView,
)
from core.views.api_keys import APIKeyManagementView
from core.views.views_pixel import PixelTrackView
from core.views.picklist import (
    PicklistConfigView,
    PicklistSubscribeToggleView,
    PicklistManualEmailView,
    OrderBulkMarkTestView,
    PicklistScheduleView,
)


router = DefaultRouter()
router.register(r'api/postits', StickyNoteViewSet, basename='stickynote')
router.register(r'api/postit-notifications', PostItNotificationViewSet, basename='postit-notification')
router.register(r'api/notifications', UnifiedNotificationViewSet, basename='unified-notification')
router.register(r'api/notification-preferences', NotificationPreferenceViewSet, basename='notification-preference')
router.register(r'api/deal-risk', DealRiskViewSet, basename='deal-risk')
router.register(r'api/customer-health', CustomerHealthScoreViewSet, basename='customer-health')
router.register(r'api/renewal-tracker', RenewalTrackerViewSet, basename='renewal-tracker')
router.register(r'api/success-tasks', SuccessTaskViewSet, basename='success-task')
router.register(r'api/email-threads', EmailThreadViewSet, basename='email-thread')
router.register(r'api/audit-logs', SystemAuditLogViewSet, basename='audit-log')
router.register(r'api/saved-filters', SavedFilterViewSet, basename='saved-filter')
router.register(r'api/integrations/webhooks', WebhookSubscriptionViewSet, basename='webhook-subscription')
router.register(r'api/integrations/webhook-logs', OutboundWebhookLogViewSet, basename='outbound-webhook-log')
router.register(r'api/integrations/oauth-apps', OAuthAppViewSet, basename='oauth-app')
router.register(r'api/sales-representatives', SalesRepresentativeViewSet, basename='sales-representative')
router.register(r'api/sales-activities', SalesActivityViewSet, basename='sales-activity')
router.register(r'api/incentive-rules', IncentiveRuleViewSet, basename='incentive-rule')
router.register(r'api/incentive-records', IncentiveRecordViewSet, basename='incentive-record')




from core.views_analytics import get_stage_summary
from core.views_analytics_operations import operations_analytics
from core.views_operations_summary import operations_summary
from core.views_sales import (
    sales_overview, sales_attribution, sales_performance,
    sales_forecast, sales_ai_recommendations,
    wholesale_leads_list, wholesale_lead_detail,
    abandoned_carts_list, abandoned_cart_detail,
    quotations_list, quotation_detail,
    shopify_analytics, marketplace_analytics,
    retail_stores_list, retail_store_detail,
    retail_store_customers_list, retail_store_customer_detail,
    retail_store_funnel, b2b_funnel,
    shopify_draft_orders, shopify_complete_draft_order, shopify_abandoned_checkouts, shopify_sync_abandoned_checkouts,
    shopify_register_webhooks,
    flexype_abandoned_cart_webhook,
    customer_search_for_draft,
    lead_activities_list, lead_tasks_list, lead_task_detail,
    lead_notes_list, lead_note_detail, lead_quotes_list, lead_orders_list,
    company_workspace_timeline,
    quotation_submit_approval, quotation_approve, quotation_reject, quotation_send_email,
    quotation_pdf_view,
)
from core.views.orders import DjangoQTaskStatusView
from core.views_marketing import (
    marketing_overview, meta_campaigns_list, meta_adsets_list, meta_ads_list,
    marketing_settings_view, meta_demographic_insights,
    marketing_ai_sessions, marketing_ai_session_detail, marketing_ai_chat,
    google_campaigns_list, google_search_terms_list,
    google_demographics_summary, google_ads_creative_list,
    profitability_income_analysis, profitability_best_ads,
    profitability_retention, profitability_goal_tracker,
    profitability_alerts, profitability_financials,
    # Agent Manager
    agent_global_rules, agent_global_rule_detail,
    agent_conversation_logs, agent_audit_response, agent_flag_and_correct,
)
from core.views_marketing_creds import MarketingCredentialView, GoogleAdsCredentialView, ProductionSoftwareCredentialView, InternalWorkflowsView
from core.views_logistics_ai import (
    logistics_ai_sessions, logistics_ai_session_detail, logistics_ai_chat,
    logistics_agent_global_rules, logistics_agent_global_rule_detail,
    logistics_agent_conversation_logs, logistics_agent_audit_response, logistics_agent_flag_and_correct,
    logistics_sync_cache,
)
from core.views_sla_dashboard import (
    SLAKPIsView, SLACourierPerformanceView, SLAStatePerformanceView,
    SLAContractListView, SLAContractDetailView,
)
from core.views_exception_center import (
    ExceptionListCreateView, ExceptionSummaryView,
    ExceptionAutoDetectView, ExceptionDetailView,
)
from core.views_customer_risk import (
    CustomerRiskListView, CustomerRiskDistributionView,
    CustomerRiskRecomputeView, CustomerRiskCheckView, CustomerRiskDetailView,
)
from core.views_hub_analytics import HubAnalyticsView, HubBottlenecksView
from core.views_control_tower import (
    ControlTowerLiveView, ControlTowerCourierHealthView, ControlTowerAlertsView,
)
from core.views_control_tower_enhancements import (
    ControlTowerKPIsView, ControlTowerShiftBreakdownView,
    ShipmentAtRiskView, ShipmentRiskSignalsView, PredictionAccuracyView,
    CourierHealthListView, CourierHealthHistoryView,
    BulkReassignCourierView, BulkNDRRescueView, FlagHubView, BulkNotifyCustomerView,
    GeoHeatmapStatsView, HubDetailSummaryView,
    AuraContextView, AuraChatView,
    PenaltyTicketsListView, PenaltySummaryView, UpdatePenaltyStatusView, ExportPenaltiesView,
    ControlTowerAnomaliesView,
)
from core.views_marketing_sync import trigger_meta_sync, trigger_google_ads_sync
from core.views_attribution import TriggerAttributionBackfillView, AttributionSummaryView, AttributionOrderSheetView, AttributionReconciliationView, AttributionModelView
from core.views_marketing_extended import (
    SocialPostsAPIView, SocialCalendarAPIView, SocialAnalyticsAPIView,
    InfluencerListAPIView, InfluencerCampaignsAPIView,
    OfflineEventsAPIView, OfflineLeadsAPIView, OfflineAnalyticsAPIView,
    PRCoverageAPIView, PROutreachAPIView,
    CelebritySpottingsAPIView, CelebrityCampaignsAPIView,
    CampaignsHubAPIView, BrandMonitoringAPIView, AttributionAPIView,
    YouTubeAdsAPIView, PinterestAdsAPIView, SnapchatAdsAPIView,
    AmazonAdsAPIView, FlipkartAdsAPIView, EtsyAdsAPIView, AjioAdsAPIView, 
    TataCliqAdsAPIView, MyntraAdsAPIView, NykaaAdsAPIView,
    BlinkitAdsAPIView, InstamartAdsAPIView, ZeptoAdsAPIView
)

def home(request):
    return HttpResponse("<h1>Welcome to BridgeWorks Backend is Live! 🚀</h1>")

def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /api/",
        "Disallow: /admin/",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

urlpatterns = [
    # --- Robots.txt ---
    path('robots.txt', robots_txt, name='robots_txt'),

    # --- Django Admin ---
    path('admin/', admin.site.urls),

    # --- Analytics & Marketing ---
    path('api/analytics/stage-summary/', get_stage_summary, name='stage-summary'),
    path('api/analytics/operations/', operations_analytics, name='operations-analytics'),
    path('api/operations/summary/', operations_summary, name='operations-summary'),
    path('api/observability/metrics/', SystemObservabilityView.as_view(), name='system-observability-metrics'),

    # =====================================================================
    # SALES & BUSINESS DEVELOPMENT MODULE
    # =====================================================================
    path('api/sales/overview/', sales_overview, name='sales-overview'),
    path('api/sales/attribution/', sales_attribution, name='sales-attribution'),
    path('api/sales/performance/', sales_performance, name='sales-performance'),
    path('api/sales/forecast/', sales_forecast, name='sales-forecast'),
    path('api/sales/ai-recommendations/', sales_ai_recommendations, name='sales-ai-recommendations'),
    path('api/sales/wholesale-leads/', wholesale_leads_list, name='wholesale-leads-list'),
    path('api/sales/wholesale-leads/<int:pk>/', wholesale_lead_detail, name='wholesale-lead-detail'),
    path('api/sales/wholesale-leads/<int:lead_pk>/activities/', lead_activities_list, name='lead-activities-list'),
    path('api/sales/wholesale-leads/<int:lead_pk>/tasks/', lead_tasks_list, name='lead-tasks-list'),
    path('api/sales/wholesale-leads/<int:lead_pk>/tasks/<int:pk>/', lead_task_detail, name='lead-task-detail'),
    path('api/sales/wholesale-leads/<int:lead_pk>/notes/', lead_notes_list, name='lead-notes-list'),
    path('api/sales/wholesale-leads/<int:lead_pk>/notes/<int:pk>/', lead_note_detail, name='lead-note-detail'),
    path('api/sales/wholesale-leads/<int:lead_pk>/quotes/', lead_quotes_list, name='lead-quotes-list'),
    path('api/sales/wholesale-leads/<int:lead_pk>/orders/', lead_orders_list, name='lead-orders-list'),
    path('api/sales/wholesale-leads/<int:lead_pk>/crm-timeline/', company_workspace_timeline, name='company-workspace-timeline'),


    # Reusable Generic CRM Endpoints (Flat)
    path('api/crm/activities/', CRMActivityViewSet.as_view({'get': 'list', 'post': 'create'}), name='crm-activities-list'),
    path('api/crm/activities/<int:pk>/', CRMActivityViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='crm-activity-detail'),
    path('api/crm/tasks/', CRMTaskViewSet.as_view({'get': 'list', 'post': 'create'}), name='crm-tasks-list'),
    path('api/crm/tasks/<int:pk>/', CRMTaskViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='crm-task-detail'),
    path('api/crm/notes/', CRMNoteViewSet.as_view({'get': 'list', 'post': 'create'}), name='crm-notes-list'),
    path('api/crm/notes/<int:pk>/', CRMNoteViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='crm-note-detail'),
    path('api/crm/attachments/', CRMAttachmentViewSet.as_view({'get': 'list', 'post': 'create'}), name='crm-attachments-list'),
    path('api/crm/attachments/<int:pk>/', CRMAttachmentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='crm-attachment-detail'),

    # Reusable Generic CRM Endpoints (Nested/Dynamic)
    path('api/sales/<str:entity_type>/<int:entity_id>/activities/', CRMActivityViewSet.as_view({'get': 'list', 'post': 'create'}), name='generic-crm-activities'),
    path('api/sales/<str:entity_type>/<int:entity_id>/activities/<int:pk>/', CRMActivityViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='generic-crm-activity-detail'),
    path('api/sales/<str:entity_type>/<int:entity_id>/tasks/', CRMTaskViewSet.as_view({'get': 'list', 'post': 'create'}), name='generic-crm-tasks'),
    path('api/sales/<str:entity_type>/<int:entity_id>/tasks/<int:pk>/', CRMTaskViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='generic-crm-task-detail'),
    path('api/sales/<str:entity_type>/<int:entity_id>/notes/', CRMNoteViewSet.as_view({'get': 'list', 'post': 'create'}), name='generic-crm-notes'),
    path('api/sales/<str:entity_type>/<int:entity_id>/notes/<int:pk>/', CRMNoteViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='generic-crm-note-detail'),
    path('api/sales/<str:entity_type>/<int:entity_id>/attachments/', CRMAttachmentViewSet.as_view({'get': 'list', 'post': 'create'}), name='generic-crm-attachments'),
    # Workflow Automation Endpoints
    path('api/sales/workflows/', WorkflowViewSet.as_view({'get': 'list', 'post': 'create'}), name='workflow-list'),
    path('api/sales/workflows/<int:pk>/', WorkflowViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='workflow-detail'),
    path('api/sales/workflows/<int:workflow_id>/executions/', WorkflowExecutionViewSet.as_view({'get': 'list'}), name='workflow-execution-list'),
    path('api/sales/workflows/executions/', WorkflowExecutionViewSet.as_view({'get': 'list'}), name='workflow-execution-all'),
    path('api/sales/workflows/check-overdue/', check_overdue_tasks_view, name='workflow-check-overdue'),

    # Recommendation Engine Endpoints
    path('api/sales/recommendations/', RecommendationViewSet.as_view({'get': 'list'}), name='recommendation-list'),
    path('api/sales/recommendations/<int:pk>/', RecommendationViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update'}), name='recommendation-detail'),
    path('api/sales/recommendations/summary/', recommendation_summary, name='recommendation-summary'),
    path('api/sales/recommendations/run/', run_recommendation_scan, name='recommendation-run'),

    # Approval Engine Endpoints
    path('api/sales/approval-policies/', ApprovalPolicyViewSet.as_view({'get': 'list', 'post': 'create'}), name='approval-policy-list'),
    path('api/sales/approval-policies/<int:pk>/', ApprovalPolicyViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='approval-policy-detail'),
    path('api/sales/approval-requests/', ApprovalRequestViewSet.as_view({'get': 'list'}), name='approval-request-list'),
    path('api/sales/approval-requests/<int:pk>/', ApprovalRequestViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='approval-request-detail'),
    path('api/sales/approval-requests/submit/', ApprovalRequestViewSet.as_view({'post': 'submit_entity'}), name='approval-request-submit'),
    path('api/sales/approval-requests/<int:pk>/approve/', ApprovalRequestViewSet.as_view({'post': 'approve_step'}), name='approval-request-approve'),
    path('api/sales/approval-requests/<int:pk>/reject/', ApprovalRequestViewSet.as_view({'post': 'reject_step'}), name='approval-request-reject'),

    # Forecasting Endpoints
    path('api/sales/sales-quotas/', SalesQuotaViewSet.as_view({'get': 'list', 'post': 'create'}), name='sales-quota-list'),
    path('api/sales/sales-quotas/<int:pk>/', SalesQuotaViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='sales-quota-detail'),
    path('api/sales/forecasting/', get_sales_forecast, name='sales-forecasting'),
    path('api/sales/reporting/', crm_advanced_report, name='crm-advanced-report'),
    path('api/sales/import-leads/', import_leads_csv, name='import-leads-csv'),
    path('api/sales/export-leads/', export_leads_csv, name='export-leads-csv'),



    path('api/sales/abandoned-carts/', abandoned_carts_list, name='abandoned-carts-list'),

    path('api/sales/abandoned-carts/<int:pk>/', abandoned_cart_detail, name='abandoned-cart-detail'),
    path('api/sales/quotations/', quotations_list, name='quotations-list'),
    path('api/sales/quotations/<int:pk>/', quotation_detail, name='quotation-detail'),
    path('api/sales/quotations/<int:pk>/submit-approval/', quotation_submit_approval, name='quotation-submit-approval'),
    path('api/sales/quotations/<int:pk>/approve/', quotation_approve, name='quotation-approve'),
    path('api/sales/quotations/<int:pk>/reject/', quotation_reject, name='quotation-reject'),
    path('api/sales/quotations/<int:pk>/send-email/', quotation_send_email, name='quotation-send-email'),
    path('api/sales/quotations/<int:pk>/pdf/', quotation_pdf_view, name='quotation-pdf'),
    path('api/sales/shopify/', shopify_analytics, name='shopify-analytics'),
    path('api/sales/customer-search/', customer_search_for_draft, name='customer-search-for-draft'),
    path('api/sales/shopify/draft-orders/', shopify_draft_orders, name='shopify-draft-orders'),
    path('api/sales/shopify/draft-orders/<int:draft_id>/complete/', shopify_complete_draft_order, name='shopify-complete-draft'),
    path('api/sales/shopify/abandoned-checkouts/', shopify_abandoned_checkouts, name='shopify-abandoned-checkouts'),
    path('api/sales/shopify/abandoned-checkouts/sync/', shopify_sync_abandoned_checkouts, name='shopify-sync-abandoned-checkouts'),
    path('api/tasks/<str:task_id>/status/', DjangoQTaskStatusView.as_view(), name='django-q-task-status'),
    path('api/shopify/register-webhooks/', shopify_register_webhooks, name='shopify-register-webhooks'),
    path('api/sales/marketplace/', marketplace_analytics, name='marketplace-analytics'),
    path('api/sales/retail-stores/', retail_stores_list, name='retail-stores-list'),
    path('api/sales/retail-stores/<int:pk>/', retail_store_detail, name='retail-store-detail'),
    path('api/sales/retail-store-customers/', retail_store_customers_list, name='retail-store-customers-list'),
    path('api/sales/retail-store-customers/<int:pk>/', retail_store_customer_detail, name='retail-store-customer-detail'),
    path('api/sales/retail-store-funnel/', retail_store_funnel, name='retail-store-funnel'),
    path('api/sales/b2b-funnel/', b2b_funnel, name='b2b-funnel'),
    path('api/marketing/overview/', marketing_overview, name='marketing-overview'),
    path('api/marketing/meta-campaigns/', meta_campaigns_list, name='meta-campaigns'),
    path('api/marketing/meta-adsets/', meta_adsets_list, name='meta-adsets'),
    path('api/marketing/meta-ads/', meta_ads_list, name='meta-ads'),
    path('api/marketing/google-campaigns/', google_campaigns_list, name='google-campaigns'),
    path('api/marketing/google-search-terms/', google_search_terms_list, name='google-search-terms'),
    path('api/marketing/google-demographics/', google_demographics_summary, name='google-demographics'),
    path('api/marketing/google-ads-creatives/', google_ads_creative_list, name='google-ads-creatives'),
    path('api/marketing/settings/', marketing_settings_view, name='marketing-settings'),
    path('api/marketing/demographics/', meta_demographic_insights, name='marketing-demographics'),
    path('api/marketing/ai-sessions/', marketing_ai_sessions, name='marketing-ai-sessions'),
    path('api/marketing/ai-sessions/<str:session_id>/', marketing_ai_session_detail, name='marketing-ai-session-detail'),
    path('api/marketing/ai-chat/', marketing_ai_chat, name='marketing-ai-chat'),

    # --- Logistics Aura AI ---
    path('api/logistics/ai-sessions/', logistics_ai_sessions, name='logistics-ai-sessions'),
    path('api/logistics/ai-sessions/<str:session_id>/', logistics_ai_session_detail, name='logistics-ai-session-detail'),
    path('api/logistics/ai-chat/', logistics_ai_chat, name='logistics-ai-chat'),
    path('api/logistics/sync-cache/', logistics_sync_cache, name='logistics-sync-cache'),
    path('api/logistics/agent/global-rules/', logistics_agent_global_rules, name='logistics-agent-global-rules'),
    path('api/logistics/agent/global-rules/<int:rule_id>/', logistics_agent_global_rule_detail, name='logistics-agent-global-rule-detail'),
    path('api/logistics/agent/conversation-logs/', logistics_agent_conversation_logs, name='logistics-agent-conversation-logs'),
    path('api/logistics/agent/audit-response/', logistics_agent_audit_response, name='logistics-agent-audit-response'),
    path('api/logistics/agent/flag-and-correct/', logistics_agent_flag_and_correct, name='logistics-agent-flag-and-correct'),

    # =====================================================================
    # SLA DASHBOARD
    # =====================================================================
    path('api/logistics/sla/kpis/', SLAKPIsView.as_view(), name='sla-kpis'),
    path('api/logistics/sla/courier-performance/', SLACourierPerformanceView.as_view(), name='sla-courier-performance'),
    path('api/logistics/sla/state-performance/', SLAStatePerformanceView.as_view(), name='sla-state-performance'),
    path('api/logistics/sla/contracts/', SLAContractListView.as_view(), name='sla-contracts'),
    path('api/logistics/sla/contracts/<int:pk>/', SLAContractDetailView.as_view(), name='sla-contract-detail'),

    # =====================================================================
    # EXCEPTION MANAGEMENT CENTER
    # =====================================================================
    path('api/logistics/exceptions/', ExceptionListCreateView.as_view(), name='exception-list-create'),
    path('api/logistics/exceptions/summary/', ExceptionSummaryView.as_view(), name='exception-summary'),
    path('api/logistics/exceptions/auto-detect/', ExceptionAutoDetectView.as_view(), name='exception-auto-detect'),
    path('api/logistics/exceptions/<int:pk>/', ExceptionDetailView.as_view(), name='exception-detail'),

    # =====================================================================
    # CUSTOMER RISK ENGINE
    # =====================================================================
    path('api/logistics/customer-risk/', CustomerRiskListView.as_view(), name='customer-risk-list'),
    path('api/logistics/customer-risk/distribution/', CustomerRiskDistributionView.as_view(), name='customer-risk-distribution'),
    path('api/logistics/customer-risk/recompute/', CustomerRiskRecomputeView.as_view(), name='customer-risk-recompute'),
    path('api/logistics/customer-risk/check/', CustomerRiskCheckView.as_view(), name='customer-risk-check'),
    path('api/logistics/customer-risk/<str:phone>/', CustomerRiskDetailView.as_view(), name='customer-risk-detail'),

    # =====================================================================
    # HUB ANALYTICS
    # =====================================================================
    path('api/logistics/hub-analytics/', HubAnalyticsView.as_view(), name='hub-analytics'),
    path('api/logistics/hub-analytics/top-bottlenecks/', HubBottlenecksView.as_view(), name='hub-bottlenecks'),

    # =====================================================================
    # LOGISTICS CONTROL TOWER
    # =====================================================================
    path('api/logistics/control-tower/live/', ControlTowerLiveView.as_view(), name='control-tower-live'),
    path('api/logistics/control-tower/courier-health/', ControlTowerCourierHealthView.as_view(), name='control-tower-courier-health'),
    path('api/logistics/control-tower/alerts/', ControlTowerAlertsView.as_view(), name='control-tower-alerts'),

    # --- Control Tower Shift View & KPIs ---
    path('api/control-tower/kpis/', ControlTowerKPIsView.as_view(), name='control-tower-kpis'),
    path('api/control-tower/shift-breakdown/', ControlTowerShiftBreakdownView.as_view(), name='control-tower-shift-breakdown'),
    path('api/control-tower/anomalies/', ControlTowerAnomaliesView.as_view(), name='control-tower-anomalies'),

    # --- Predictive Risk ---
    path('api/shipments/at-risk/', ShipmentAtRiskView.as_view(), name='shipments-at-risk'),
    path('api/shipments/at-risk/signals/', ShipmentRiskSignalsView.as_view(), name='shipments-at-risk-signals'),
    path('api/predictions/accuracy/', PredictionAccuracyView.as_view(), name='predictions-accuracy'),

    # --- Courier Health Scorecard ---
    path('api/couriers/health/all/', CourierHealthListView.as_view(), name='couriers-health-all'),
    path('api/couriers/<str:id>/health/history/', CourierHealthHistoryView.as_view(), name='couriers-health-history'),

    # --- Bulk Actions Drawer ---
    path('api/shipments/bulk-reassign/', BulkReassignCourierView.as_view(), name='shipments-bulk-reassign'),
    path('api/ndr/bulk-rescue/', BulkNDRRescueView.as_view(), name='ndr-bulk-rescue'),
    path('api/hubs/<str:id>/flag/', FlagHubView.as_view(), name='hubs-flag'),
    path('api/shipments/bulk-notify/', BulkNotifyCustomerView.as_view(), name='shipments-bulk-notify'),

    # --- Geo-Heatmap view ---
    path('api/hubs/geo-stats/', GeoHeatmapStatsView.as_view(), name='hubs-geo-stats'),
    path('api/hubs/<str:id>/summary/', HubDetailSummaryView.as_view(), name='hubs-detail-summary'),

    # --- Aura Copilot SSE ---
    path('api/aura/context/', AuraContextView.as_view(), name='aura-context'),
    path('api/aura/chat/', AuraChatView.as_view(), name='aura-chat'),

    # --- SLA Breach Penalty Claims ---
    path('api/penalties/', PenaltyTicketsListView.as_view(), name='penalties-list'),
    path('api/penalties/summary/', PenaltySummaryView.as_view(), name='penalties-summary'),
    path('api/penalties/<uuid:id>/status/', UpdatePenaltyStatusView.as_view(), name='penalties-status-update'),
    path('api/penalties/export/', ExportPenaltiesView.as_view(), name='penalties-export'),

    path('api/marketing/credentials/', MarketingCredentialView.as_view(), name='marketing-credentials'),
    path('api/marketing/credentials/google/', GoogleAdsCredentialView.as_view(), name='google-marketing-credentials'),
    path('api/settings/production-software/', ProductionSoftwareCredentialView.as_view(), name='production-software-credentials'),
    path('api/settings/internal-workflows/', InternalWorkflowsView.as_view(), name='internal-workflows-settings'),
    path('api/marketing/sync/', trigger_meta_sync, name='marketing-sync'),
    path('api/marketing/sync-google/', trigger_google_ads_sync, name='marketing-sync-google'),

    # --- Profitability & Income Analysis ---
    path('api/marketing/profitability/income-analysis/', profitability_income_analysis, name='profitability-income-analysis'),
    path('api/marketing/profitability/best-ads/', profitability_best_ads, name='profitability-best-ads'),
    path('api/marketing/profitability/retention/', profitability_retention, name='profitability-retention'),
    path('api/marketing/profitability/goal-tracker/', profitability_goal_tracker, name='profitability-goal-tracker'),
    path('api/marketing/profitability/alerts/', profitability_alerts, name='profitability-alerts'),
    path('api/marketing/profitability/financials/', profitability_financials, name='profitability-financials'),

    # --- Agent Manager ---
    path('api/marketing/agent/global-rules/', agent_global_rules, name='agent-global-rules'),
    path('api/marketing/agent/global-rules/<int:rule_id>/', agent_global_rule_detail, name='agent-global-rule-detail'),
    path('api/marketing/agent/conversation-logs/', agent_conversation_logs, name='agent-conversation-logs'),
    path('api/marketing/agent/audit-response/', agent_audit_response, name='agent-audit-response'),
    path('api/marketing/agent/flag-and-correct/', agent_flag_and_correct, name='agent-flag-and-correct'),

    path('api/marketing/social/posts/', SocialPostsAPIView.as_view(), name='mkt-social-posts'),
    path('api/marketing/social/calendar/', SocialCalendarAPIView.as_view(), name='mkt-social-calendar'),
    path('api/marketing/social/analytics/', SocialAnalyticsAPIView.as_view(), name='mkt-social-analytics'),
    path('api/marketing/influencers/', InfluencerListAPIView.as_view(), name='mkt-influencers'),
    path('api/marketing/influencer-campaigns/', InfluencerCampaignsAPIView.as_view(), name='mkt-influencer-campaigns'),
    path('api/marketing/offline/events/', OfflineEventsAPIView.as_view(), name='mkt-offline-events'),
    path('api/marketing/offline/leads/', OfflineLeadsAPIView.as_view(), name='mkt-offline-leads'),
    path('api/marketing/offline/analytics/', OfflineAnalyticsAPIView.as_view(), name='mkt-offline-analytics'),
    path('api/marketing/pr/coverage/', PRCoverageAPIView.as_view(), name='mkt-pr-coverage'),
    path('api/marketing/pr/outreach/', PROutreachAPIView.as_view(), name='mkt-pr-outreach'),
    path('api/marketing/celebrity/spottings/', CelebritySpottingsAPIView.as_view(), name='mkt-celebrity-spottings'),
    path('api/marketing/celebrity/campaigns/', CelebrityCampaignsAPIView.as_view(), name='mkt-celebrity-campaigns'),
    path('api/marketing/campaigns-hub/', CampaignsHubAPIView.as_view(), name='mkt-campaigns-hub'),
    path('api/marketing/brand/monitoring/', BrandMonitoringAPIView.as_view(), name='mkt-brand-monitoring'),
    path('api/marketing/attribution/', AttributionAPIView.as_view(), name='mkt-attribution'),

    # --- Attribution Backfill Engine ---
    path('api/marketing/attribution/backfill/', TriggerAttributionBackfillView.as_view(), name='attribution-backfill'),
    path('api/marketing/attribution/summary/', AttributionSummaryView.as_view(), name='attribution-summary'),
    path('api/marketing/attribution/sheet/', AttributionOrderSheetView.as_view(), name='attribution-sheet'),
    path('api/marketing/attribution/reconciliation/', AttributionReconciliationView.as_view(), name='attribution-reconciliation'),
    path('api/marketing/attribution/model/', AttributionModelView.as_view(), name='attribution-model'),

    # Video & Social Ads
    path('api/marketing/youtube/', YouTubeAdsAPIView.as_view(), name='mkt-youtube-ads'),
    path('api/marketing/pinterest/', PinterestAdsAPIView.as_view(), name='mkt-pinterest-ads'),
    path('api/marketing/snapchat/', SnapchatAdsAPIView.as_view(), name='mkt-snapchat-ads'),

    # Marketplace Ads
    path('api/marketing/marketplace/amazon/', AmazonAdsAPIView.as_view(), name='mkt-amazon-ads'),
    path('api/marketing/marketplace/flipkart/', FlipkartAdsAPIView.as_view(), name='mkt-flipkart-ads'),
    path('api/marketing/marketplace/etsy/', EtsyAdsAPIView.as_view(), name='mkt-etsy-ads'),
    path('api/marketing/marketplace/ajio/', AjioAdsAPIView.as_view(), name='mkt-ajio-ads'),
    path('api/marketing/marketplace/tatacliq/', TataCliqAdsAPIView.as_view(), name='mkt-tatacliq-ads'),
    path('api/marketing/marketplace/myntra/', MyntraAdsAPIView.as_view(), name='mkt-myntra-ads'),
    path('api/marketing/marketplace/nykaa/', NykaaAdsAPIView.as_view(), name='mkt-nykaa-ads'),

    # Quick Commerce Ads
    path('api/marketing/quick-commerce/blinkit/', BlinkitAdsAPIView.as_view(), name='mkt-blinkit-ads'),
    path('api/marketing/quick-commerce/instamart/', InstamartAdsAPIView.as_view(), name='mkt-instamart-ads'),
    path('api/marketing/quick-commerce/zepto/', ZeptoAdsAPIView.as_view(), name='mkt-zepto-ads'),

    #home
    path('', shopify_app_landing, name='home'),

    # --- AUTHENTICATION (Allauth & JWT wrapper) ---
    path('accounts/google/login/callback/', google_callback_with_jwt, name='google_callback_with_jwt'),
    path('accounts/', include('allauth.urls')),

    # =====================================================================
    # SECURITY / ONBOARDING / USER
    # =====================================================================
    path('api/onboarding/', OnboardingView.as_view(), name='onboarding'),
    path('api/get-csrf-token/', get_csrf_token, name='get-csrf-token'),
    path('api/team/co-founder/<int:user_id>/', CoFounderToggleView.as_view(), name='co-founder-toggle'),
    path('api/hr/users/<int:user_id>/attendance-settings/', HRUserAttendanceSettingsView.as_view(), name='hr-user-attendance-settings'),
    
    # --- EXTERNAL API & TOKEN MGMT ---
    path('api/external/shops/<str:shop_id>/picklists/', PicklistExternalAPIView.as_view(), name='external-picklist'),
    path('api/external/shops/<str:shop_id>/workforce/', WorkforceExternalAPIView.as_view(), name='external-workforce'),
    path('api/external/shops/<str:shop_id>/expenses/', ExpenseExternalAPIView.as_view(), name='external-expenses'),
    path('api/external/shops/<str:shop_id>/repair-queue/', RepairQueueExternalAPIView.as_view(), name='external-repair-queue'),
    path('api/external/shops/<str:shop_id>/repair-queue/complete/', RepairQueueCompleteExternalAPIView.as_view(), name='external-repair-queue-complete'),
    path('api/settings/api-keys/', APIKeyManagementView.as_view(), name='api-key-mgmt'),
    path('api/settings/api-keys/<int:key_id>/', APIKeyManagementView.as_view(), name='api-key-revoke'),


    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/google-exchange/', google_token_exchange, name='token_google_exchange'),
    path('api/logout/', LogoutView.as_view(), name='logout'),
    path('api/google-id-token/', google_id_token, name='google-id-token'),

    # Updated to use the Class-Based View for robust Prefix handling
    path('api/current-user/', CurrentUserView.as_view(), name='get-current-user'),
    path('api/shop-profile/', ShopProfileView.as_view(), name='shop-profile'),
    path('api/shop-profile/logo/', ShopLogoUploadView.as_view(), name='shop-logo-upload'),
    path('api/current-user/bank/', UserBankDetailsView.as_view(), name='user-bank-details'),
    path('api/current-user/profile-picture/', UserProfilePictureView.as_view(), name='user-profile-picture'),
    path('api/current-user/documents/<str:doc_type>/', UserDocumentUploadView.as_view(), name='user-document-upload'),

    # =====================================================================
    # ORDER RETRIEVAL VIEWS
    # =====================================================================
    path('api/orders/', GetOrdersView.as_view(), name='order-list'),
    path('api/orders/paginated/', PaginatedOrderListView.as_view(), name='paginated-orders'),
    path('api/orders/overview/', AllOrdersView.as_view(), name='orders-overview'),
    path('api/orders/pending-paginated/', PaginatedPendingOrdersView.as_view(), name='pending-orders-paginated'),
    path('api/orders/unfulfilled/', GetUnfulfilledOrdersView.as_view(), name='unfulfilled-orders'),
    path('api/orders/confirmed/', ConfirmedOrdersView.as_view(), name='confirmed-orders'),
    path('api/orders/on-hold/', OnHoldOrdersView.as_view(), name='on-hold-orders'),
    path('api/orders/history/', CustomerHistoryView.as_view(), name='customer-history'),

    # Single Order Lookup (Used by FIR form)
    path('api/orders/lookup/', OrderLookupView.as_view(), name='order-lookup'),
    path('api/orders/sync/', SyncOrderView.as_view(), name='sync-order'),

    # Global Search (Shopify-style Omnibox)
    path('api/search/', GlobalSearchView.as_view(), name='global-search'),

    # Picklist Aggregation (Backend-side)
    path('api/orders/picklist-aggregation/', PicklistAggregationView.as_view(), name='picklist-aggregation'),
    path('api/analytics/logistics/', LogisticsAnalyticsView.as_view(), name='logistics-analytics'),
    
    # Picklist settings, email exports, and bulk marking
    path('api/picklist/config/', PicklistConfigView.as_view(), name='picklist-config'),
    path('api/picklist/config/subscribe/', PicklistSubscribeToggleView.as_view(), name='picklist-subscribe'),
    path('api/picklist/email/', PicklistManualEmailView.as_view(), name='picklist-email-manual'),
    path('api/picklist/schedule/', PicklistScheduleView.as_view(), name='picklist-schedule'),
    path('api/orders/bulk-mark-test/', OrderBulkMarkTestView.as_view(), name='orders-bulk-mark-test'),
    
    # NEW DASHBOARD
    path('api/logistics/analytics-dashboard/', LogisticsDashboardView.as_view(), name='logistics-analytics-dashboard'),

    # =====================================================================
    # REVERSE LOGISTICS (RTO) MODULE
    # =====================================================================
    path('api/rto/scan/', RTOReceiveScanView.as_view(), name='rto-scan'),
    path('api/rto/batch/create/', RTOBatchCreateView.as_view(), name='rto-batch-create'),
    path('api/rto/unpack-list/', RTOUnpackListView.as_view(), name='rto-unpack-list'),
    path('api/rto/restock-action/', RTORestockActionView.as_view(), name='rto-restock-action'),

    # RTO ENGINE
    path('api/rto-engine/scan/', RTOEngineScanView.as_view(), name='rto-engine-scan'),
    path('api/rto-engine/dispatch/', RTOEngineDispatchView.as_view(), name='rto-engine-dispatch'),
    path('api/rto-engine/batch-scan/', RTOEngineBatchScanView.as_view(), name='rto-engine-batch-scan'),
    path('api/rto-engine/batch-dispatch/', RTOEngineBatchDispatchView.as_view(), name='rto-engine-batch-dispatch'),
    path('api/rto-engine/qc/', RTOEngineQCListView.as_view(), name='rto-engine-qc-list'),
    path('api/rto-engine/qc/action/', RTOEngineQCActionView.as_view(), name='rto-engine-qc-action'),
    path('api/rto-engine/qc/bulk-inventory/', RTOEngineQCBulkInventoryView.as_view(), name='rto-engine-qc-bulk-inventory'),
    path('api/rto-engine/qc/bulk-action/', RTOEngineQCBulkActionView.as_view(), name='rto-engine-qc-bulk-action'),
    path('api/rto-engine/investigation/', RTOEngineInvestigationListView.as_view(), name='rto-engine-investigation-list'),
    path('api/rto-engine/investigation/action/', RTOEngineInvestigationActionView.as_view(), name='rto-engine-investigation-action'),
    path('api/rto-engine/investigation/bulk-action/', RTOEngineInvestigationBulkActionView.as_view(), name='rto-engine-investigation-bulk-action'),
    path('api/rto-engine/repair/bulk-complete/', RTOEngineRepairBulkCompleteView.as_view(), name='rto-engine-repair-bulk-complete'),
    path('api/rto-engine/log/', RTOEngineLogView.as_view(), name='rto-engine-log'),

    # =====================================================================
    # DELIVERY ANALYTICS MODULE
    # =====================================================================
    path('api/delivery/upload-costs/', ShipmentCostUploadView.as_view(), name='delivery-upload-costs'),
    path('api/delivery/shipment-cost/', ShipmentCostManualView.as_view(), name='delivery-shipment-cost'),
    path('api/delivery/reconciliation/', ReconciliationView.as_view(), name='delivery-reconciliation'),
    path('api/delivery/conciliation/', ConciliationListView.as_view(), name='conciliation-list'),
    path('api/delivery/invoices/', FreightInvoiceListView.as_view(), name='invoice-list'),
    path('api/delivery/invoices/upload/', FreightInvoiceUploadView.as_view(), name='invoice-upload'),
    path('api/delivery/invoices/upload-excel/', InvoiceExcelUploadView.as_view(), name='invoice-upload-excel'),
    path('api/delivery/invoices/<int:invoice_id>/seize/', InvoiceSeizeView.as_view(), name='invoice-seize'),
    path('api/delivery/invoices/<int:invoice_id>/lines/', InvoiceLineListView.as_view(), name='invoice-line-list'),
    path('api/delivery/invoices/<int:invoice_id>/lines/<int:line_id>/dispute/', InvoiceLineDisputeView.as_view(), name='invoice-line-dispute'),
    path('api/delivery/invoices/<int:invoice_id>/dispute-all/', InvoiceDisputeAllView.as_view(), name='invoice-dispute-all'),
    path('api/delivery/invoices/<int:invoice_id>/dispute-report/', InvoiceDisputeReportView.as_view(), name='invoice-dispute-report'),
    path('api/delivery/invoices/reanalyse-all/', InvoiceBulkReanalyseView.as_view(), name='invoice-bulk-reanalyse'),
    path('api/delivery/invoices/<int:pk>/', FreightInvoiceDetailView.as_view(), name='invoice-detail'),
    path('api/delivery/invoices/<int:invoice_id>/reanalyse/', InvoiceReanalyseView.as_view(), name='invoice-reanalyse'),
    path('api/delivery/disputes/', DisputeListView.as_view(), name='dispute-list'),
    path('api/delivery/disputes/export/', DisputeExportView.as_view(), name='dispute-export'),
    path('api/delivery/billing-patterns/', BillingPatternsView.as_view(), name='billing-patterns'),
    path('api/delivery/reconciliation-dashboard/', ReconciliationDashboardView.as_view(), name='reconciliation-dashboard'),

    # --- Shipping Engine (Warehouse, Rate Cards, Zones) ---
    path('api/delivery/warehouses/', WarehouseListView.as_view(), name='warehouse-list'),
    path('api/delivery/warehouses/<int:pk>/', WarehouseDetailView.as_view(), name='warehouse-detail'),
    path('api/delivery/warehouses/<int:pk>/set-default/', WarehouseSetDefaultView.as_view(), name='warehouse-set-default'),
    
    path('api/delivery/rate-cards/', RateCardListView.as_view(), name='rate-card-list'),
    path('api/delivery/rate-cards/upload/', RateCardUploadView.as_view(), name='rate-card-upload'),
    path('api/delivery/rate-cards/vision-scan/', RateCardVisionScanView.as_view(), name='rate-card-vision-scan'),
    path('api/delivery/rate-cards/<int:pk>/', RateCardDetailView.as_view(), name='rate-card-detail'),
    path('api/delivery/surcharge-history/', CourierSurchargeHistoryView.as_view(), name='surcharge-history'),
    
    path('api/delivery/zone-check/', ZoneCheckView.as_view(), name='zone-check'),
    path('api/delivery/recalculate-costs/', RecalculateCostsView.as_view(), name='recalculate-costs'),
    path('api/delivery/zone-mappings/upload/', CourierZoneMappingUploadView.as_view(), name='zone-mappings-upload'),

    # =====================================================================
    # RETURN PRIME (RETURNS & EXCHANGES) MODULE
    # =====================================================================
    path('api/returns/scan/', ReturnScannerView.as_view(), name='returns-scan'),
    path('api/returns/list/', ReturnRequestListView.as_view(), name='returns-list'),
    path('api/returns/stocking/action/', ReturnActionStockView.as_view(), name='returns-stocking-action'),
    path('api/returns/stocking/list/', ReturnStockingListView.as_view(), name='returns-stocking-list'),

    # =====================================================================
    # RETURNS & EXCHANGE ENGINE (Day 1 + Day 2 — QC Pipeline)
    # =====================================================================
    path('api/returns-engine/scan/', ReturnEngineScanLookupView.as_view(), name='returns-engine-scan'),
    path('api/returns-engine/batch-scan/', ReturnEngineBatchScanView.as_view(), name='returns-engine-batch-scan'),
    path('api/returns-engine/batch/create/', ReturnEngineBatchCreateView.as_view(), name='returns-engine-batch-create'),
    path('api/returns-engine/move-to-qc/', ReturnEngineMoveToQCView.as_view(), name='returns-engine-move-to-qc'),
    path('api/returns-engine/cases/', ReturnEngineCasesListView.as_view(), name='returns-engine-cases'),
    path('api/returns-engine/cases/<int:case_id>/', ReturnEngineCaseDetailView.as_view(), name='returns-engine-case-detail'),
    path('api/returns-engine/cases/<int:case_id>/activity/', ReturnEngineActivityView.as_view(), name='returns-engine-activity'),
    path('api/returns-engine/qc-action/', ReturnEngineQCActionView.as_view(), name='returns-engine-qc-action'),
    path('api/returns-engine/search/', ReturnEngineSearchView.as_view(), name='returns-engine-search'),
    # Day 3 — Refund Queue
    path('api/returns-engine/refunds/', ReturnEngineRefundListView.as_view(), name='returns-engine-refund-list'),
    path('api/returns-engine/refunds/<int:case_id>/', ReturnEngineRefundDetailView.as_view(), name='returns-engine-refund-detail'),
    path('api/returns-engine/refund-action/', ReturnEngineRefundActionView.as_view(), name='returns-engine-refund-action'),
    
    # Day 4 — Exchange Settlement
    path('api/returns-engine/exchange-settlement/', ReturnEngineExchangeListView.as_view(), name='returns-engine-exchange-list'),
    path('api/returns-engine/exchange-settlement/<int:case_id>/', ReturnEngineExchangeDetailView.as_view(), name='returns-engine-exchange-detail'),
    path('api/returns-engine/exchange-action/', ReturnEngineExchangeActionView.as_view(), name='returns-engine-exchange-action'),

    # Feature: Convert Return → Exchange & Self-Shipped Intake
    path('api/returns-engine/convert-to-exchange/', ReturnEngineConvertToExchangeView.as_view(), name='returns-engine-convert-to-exchange'),
    path('api/returns-engine/self-shipped-intake/', ReturnEngineSelfShippedIntakeView.as_view(), name='returns-engine-self-shipped-intake'),
    path('api/returns-engine/product-search/', ReturnEngineProductSearchView.as_view(), name='returns-engine-product-search'),
    path('api/returns-engine/order-lookup/', ReturnEngineOrderLookupView.as_view(), name='returns-engine-order-lookup'),
    path('api/returns-engine/manual-intake/', ReturnEngineManualIntakeView.as_view(), name='returns-engine-manual-intake'),
    path('api/returns-engine/products/<int:product_id>/variants/', ReturnEngineProductVariantsView.as_view(), name='returns-engine-product-variants'),
    path('api/returns-engine/create-exchange-order/', ReturnEngineCreateExchangeOrderView.as_view(), name='returns-engine-create-exchange-order'),

    # =====================================================================
    # NDR ESCALATION ENGINE
    # =====================================================================
    path('api/ndr/batches/', NDRBatchListView.as_view(), name='ndr-batch-list'),
    path('api/ndr/upload-panel-csv/', UploadPanelCSVView.as_view(), name='ndr-upload-panel-csv'),
    path('api/ndr/upload-raw-text/', UploadRawTextView.as_view(), name='ndr-upload-raw-text'),
    path('api/ndr/export/', GenerateEscalationExportView.as_view(), name='ndr-export'),
    path('api/ndr/calling-sheet-batch/', GenerateCallingSheetBatchView.as_view(), name='ndr-calling-sheet-batch'),
    path('api/ndr/bulk-action/', BulkNDRActionView.as_view(), name='ndr-bulk-action'),
    path('api/ndr/analytics/', NDRAnalyticsDataView.as_view(), name='ndr-analytics'),
    path('api/ndr/playbooks/', NDRPlaybookListView.as_view(), name='ndr-playbooks'),
    path('api/ndr/playbooks/<int:pk>/', NDRPlaybookDetailView.as_view(), name='ndr-playbook-detail'),
    path('api/ndr/fraud-flags/', NDRFraudFlagListView.as_view(), name='ndr-fraud-flags'),
    path('api/ndr/fraud-flags/<int:pk>/resolve/', NDRFraudFlagResolveView.as_view(), name='ndr-fraud-flag-resolve'),

    # =====================================================================
    # ORDER ACTIONS & STATS
    # =====================================================================
    path('api/orders/confirmation-stats/', confirmation_stats, name='confirmation-stats'),
    path('api/orders/<int:order_number>/update/', UpdateOrderView.as_view(), name='update-order'),
    path('api/orders/bulk-confirm/', BulkConfirmOrdersView.as_view(), name='bulk-confirm-orders'),
    path('api/orders/bulk-confirm/status/<str:task_id>/', BulkConfirmStatusView.as_view(), name='bulk-confirm-status'),
    path('api/orders/bulk-scan-action/', BulkScanActionView.as_view(), name='bulk-scan-action'),
    path('api/orders/fetch-tracking/', FetchTrackingDataView.as_view(), name='fetch-tracking'),
    path('api/orders/fetch-and-batch/', FetchTrackingAndBatchView.as_view()),

    # =====================================================================
    # BATCHING SYSTEM
    # =====================================================================
    path('api/batches/', BatchListView.as_view(), name='batch-list'),
    path('api/batches/create/', BatchCreateView.as_view(), name='batch-create'),
    path('api/orders/generate-awb-batch/', GenerateAWBAndBatchView.as_view(), name='generate-awb-batch'),
    path('api/batches/awb-list/', AWBBatchListView.as_view(), name='awb-batch-list'),
    path('api/batches/merge-labels/', MergeLabelsView.as_view(), name='merge-labels'),

    # =====================================================================
    # PACKAGING & MANIFEST VIEWS
    # =====================================================================
    path('api/users/', UserListView.as_view(), name='user-list'),
    path('api/packaging-batches/', PackagingBatchListView.as_view(), name='packaging-batch-list'),
    path('api/packaging-batches/create/', PackagingBatchCreateView.as_view(), name='packaging-batch-create'),
    path('api/orders/<int:order_number>/upload-packaging-photos/', PackagingImageView.as_view(), name='upload-packaging-photos'),

    path('api/orders/manifest-sheet/', ManifestSheetView.as_view(), name='manifest-sheet'),
    path('api/orders/manifest/paginated/', PaginatedManifestOrderListView.as_view(), name='paginated-manifest-orders'),
    path('api/orders/manifest-bulk/', BulkManifestOrdersView.as_view(), name='manifest-bulk'),
    path('api/orders/manifested-orders/', ManifestOrdersListView.as_view(), name='manifested-orders'),
    path('api/orders/tracking-optimized/', TrackingPageOrderListView.as_view(), name='tracking-optimized'),
    path('api/orders/log-ndr-call/', LogNDRCallView.as_view(), name='log-ndr-call'),

    # =====================================================================
    # EXTERNAL / WEBHOOKS
    # =====================================================================
    path('webhooks/shopify/orders/', ShopifyWebhookView.as_view(), name='shopify-webhook'),
    path('api/v1/pixel/track/', PixelTrackView.as_view(), name='pixel-track'),
    path('api/webhooks/sagepilot/', SagepilotWebhookView.as_view(), name='sagepilot-webhook'),
    path('api/webhooks/logs/', WebhookLogListView.as_view(), name='webhook-log-list'),
    path('api/webhooks/return-prime/', ReturnPrimeWebhookView.as_view(), name='return-prime-webhook'),
    path('api/webhooks/flexype/abandoned-cart/', flexype_abandoned_cart_webhook, name='flexype-abandoned-cart-webhook'),

    # =====================================================================
    # SHOPIFY OAUTH HANDSHAKE
    # =====================================================================
    path('api/shopify/install/', shopify_install, name='shopify-install'),
    path('api/shopify/callback/', shopify_callback, name='shopify-callback'),

    # =====================================================================
    # PERMISSIONS / TEAM MANAGEMENT
    # =====================================================================
    path('api/user-permissions/', UserPermissionsView.as_view(), name='user-permissions'),
    path('api/team/members/', TeamMemberListAPIView.as_view(), name='team-member-list'),
    path('api/team/members/<int:user_id>/', TeamMemberDetailView.as_view(), name='team-member-detail'),
    path('api/team/permissions/<int:user_id>/', TeammatePermissionsView.as_view(), name='teammate-permissions'),
    path('api/roles/', RoleListCreateView.as_view(), name='role-list-create'),
    path('api/roles/<int:pk>/', RoleDetailView.as_view(), name='role-detail'),
    path('api/team/invite/', InviteTeammateView.as_view(), name='invite-teammate'),
    path("api/permissions/schema/", PermissionSchemaView.as_view(), name="permission-schema"),
    path('api/team/delete/<int:user_id>/', TeammateDeleteView.as_view(), name='teammate-delete'),
    path('api/workforce/departments/', WorkforceDepartmentListCreateView.as_view(), name='workforce-departments'),
    path('api/workforce/departments/<int:department_id>/', WorkforceDepartmentDetailView.as_view(), name='workforce-department-detail'),
    path('api/workforce/members/', WorkforceMemberListCreateView.as_view(), name='workforce-members'),
    path('api/workforce/members/<int:member_id>/', WorkforceMemberDetailView.as_view(), name='workforce-member-detail'),
    path('api/workforce/permissions/<int:member_id>/', WorkforceMemberPermissionsView.as_view(), name='workforce-member-permissions'),
    path('api/workforce/members/archive/', WorkforceMemberBulkArchiveView.as_view(), name='workforce-member-archive'),
    path('api/workforce/documents/<str:doc_type>/', WorkforceDocumentUploadView.as_view(), name='workforce-document-upload'),

    # =====================================================================
    # CUSTOMER CARE / CASE FILE MODULE
    # =====================================================================

    # 1. FIR SHEET & CASE FILE LIST
    path('api/cases/', CaseFileListCreateView.as_view(), name='case-list-create'),

    # 2. CASE FILE DETAIL
    path('api/cases/<str:case_number>/', CaseFileRetrieveUpdateView.as_view(), name='case-detail-update'),

    # 3. ISSUE COMMENTS
    path('api/cases/<str:case_number>/comments/', IssueCommentListCreateView.as_view(), name='comment-list-create'),

    # =====================================================================
    # INTELLIGENCE MODULE
    # =====================================================================
    path('api/intelligence/config/', AgentConfigurationView.as_view(), name='agent-config'),
    path('api/analytics/config/', AnalyticsAgentConfigurationView.as_view(), name='analytics-agent-config'),
    path('api/intelligence/activity/', AgentActivityView.as_view(), name='agent-activity'),
    path('api/intelligence/reevaluate/', ReevaluateOrderView.as_view(), name='agent-reevaluate'),
    path('api/analytics/chat/', ChatAnalyticsView.as_view(), name='chat-analytics'),
    path('api/analytics/chat/sessions/', ThorfinnChatSessionListView.as_view(), name='thorfinn-chat-sessions'),
    path('api/analytics/chat/sessions/<uuid:session_id>/', ThorfinnChatSessionDetailView.as_view(), name='thorfinn-chat-session-detail'),
    path('api/analytics/chat/sessions/<uuid:session_id>/messages/', ThorfinnChatMessageListView.as_view(), name='thorfinn-chat-messages'),
    path('api/intelligence/marketing-config/', MarketingAgentConfigurationView.as_view(), name='marketing-agent-config'),
    path('api/intelligence/logistics-config/', LogisticsAgentConfigurationView.as_view(), name='logistics-agent-config'),
    path('api/intelligence/service-config/', ServiceAgentConfigurationView.as_view(), name='service-agent-config'),


    # =====================================================================
    # TEAM CHAT MODULE
    # =====================================================================
    path('api/chat/messages/', ChatMessageListCreateView.as_view(), name='chat-message-list-create'),
    path('api/chat/messages/<int:pk>/', ChatMessageDetailView.as_view(), name='chat-message-detail'),
    path('api/chat/messages/<int:pk>/reactions/', ChatMessageReactionView.as_view(), name='chat-message-reactions'),
    path('api/chat/messages/<int:pk>/attachment/', ChatMessageAttachmentView.as_view(), name='chat-message-attachment'),
    path('api/chat/messages/<int:pk>/archive/', ChatMessageArchiveView.as_view(), name='chat-message-archive'),
    path('api/chat/messages/<int:pk>/read/', ChatMessageReadView.as_view(), name='chat-message-read'),
    path('api/chat/unread-count/', ChatUnreadCountView.as_view(), name='chat-unread-count'),
    path('api/chat/conversations/', ConversationsListView.as_view(), name='chat-conversations'),
    path('api/chat/search/', ChatSearchView.as_view(), name='chat-search'),
    path('api/chat/rooms/', ChatRoomListCreateView.as_view(), name='chat-room-list-create'),
    path('api/chat/rooms/<uuid:room_id>/', ChatRoomDetailView.as_view(), name='chat-room-detail'),
    path('api/chat/rooms/<uuid:room_id>/members/', ChatRoomMemberView.as_view(), name='chat-room-members'),
    path('api/chat/rooms/<uuid:room_id>/pins/', ChatRoomPinView.as_view(), name='chat-room-pins'),
    path('api/chat/communities/', ChatCommunityListCreateView.as_view(), name='chat-community-list-create'),
    path('api/chat/communities/<int:community_id>/', ChatCommunityDetailView.as_view(), name='chat-community-detail'),
    path('api/chat/communities/<int:community_id>/members/', ChatCommunityMemberView.as_view(), name='chat-community-members'),
    path('api/chat/channels/', ChatChannelListCreateView.as_view(), name='chat-channel-list-create'),
    path('api/chat/channels/<int:channel_id>/', ChatChannelDetailView.as_view(), name='chat-channel-detail'),
    path('api/chat/channels/<int:channel_id>/members/', ChatChannelMemberView.as_view(), name='chat-channel-members'),
    path('api/chat/channels/<int:channel_id>/pins/', ChatChannelPinView.as_view(), name='chat-channel-pins'),
    path('api/chat/tasks/', ChatTaskCreateView.as_view(), name='chat-task-create'),
    path('api/chat/tasks/<int:pk>/toggle/', ChatTaskToggleView.as_view(), name='chat-task-toggle'),
    path('api/chat/metrics/', ChatDeliveryMetricsView.as_view(), name='chat-metrics'),
    path('api/chat/metrics/ws-drop/', ChatClientDropMetricView.as_view(), name='chat-metrics-ws-drop'),
    path('api/chat/presence/', ChatPresenceListView.as_view(), name='chat-presence-list'),
    path('api/chat/presence/heartbeat/', ChatPresenceHeartbeatView.as_view(), name='chat-presence-heartbeat'),
    path('api/chat/presence/offline/', ChatPresenceOfflineView.as_view(), name='chat-presence-offline'),
    path('api/presence/', include('presence.urls')),


    # =====================================================================
    # DIARY MODULE
    # =====================================================================
    path('api/diary/entries/', DiaryEntryListCreateView.as_view(), name='diary-entry-list-create'),
    path('api/diary/entries/<int:pk>/', DiaryEntryDetailView.as_view(), name='diary-entry-delete'),

    # =====================================================================
    # GOOGLE CALENDAR & MEET MODULE
    # =====================================================================
    path('api/calendar/status/',   CalendarAuthStatusView.as_view(),  name='calendar-auth-status'),
    path('api/calendar/auth/',     CalendarAuthInitView.as_view(),    name='calendar-auth-init'),
    path('api/calendar/callback/', CalendarAuthCallbackView.as_view(), name='calendar-auth-callback'),
    path('api/calendar/schedule/', ScheduleMeetingView.as_view(),     name='calendar-schedule'),
    path('api/calendar/events/',   CalendarEventsView.as_view(),      name='calendar-events'),
    path('api/calendar/events/<str:event_id>/', CalendarEventDetailView.as_view(), name='calendar-event-detail'),
    path('api/calendar/sync/', CalendarSyncView.as_view(), name='calendar-sync'),

    # =====================================================================
    # GMAIL MODULE
    # =====================================================================
    path('api/emails/auth/status/', GmailAuthStatusView.as_view(), name='gmail-auth-status'),
    path('api/emails/auth/initiate/', GmailAuthInitiateView.as_view(), name='gmail-auth-initiate'),
    path('api/emails/auth/callback/', GmailAuthCallbackView.as_view(), name='gmail-auth-callback'),
    path('api/emails/auth/disconnect/', GmailDisconnectView.as_view(), name='gmail-auth-disconnect'),
    path('api/emails/', EmailListView.as_view(), name='email-list'),
    path('api/emails/search/', EmailSearchView.as_view(), name='email-search'),
    path('api/emails/<str:message_id>/', EmailDetailView.as_view(), name='email-detail'),
    path('api/emails/send/', EmailSendView.as_view(), name='email-send'),
    path('api/emails/modify/', EmailModifyView.as_view(), name='email-modify'),
    path('api/emails/<str:message_id>/trash/', EmailTrashView.as_view(), name='email-trash'),
    path('api/emails/<str:message_id>/attachments/<str:attachment_id>/', EmailAttachmentView.as_view(), name='email-attachment'),

    # =====================================================================
    # MYDESK MODULE
    # =====================================================================
    path('api/mydesk/notes/', MyDeskNoteListCreateView.as_view(), name='mydesk-notes-list-create'),
    path('api/mydesk/notes/share-recipients/', MyDeskNoteShareRecipientsView.as_view(), name='mydesk-notes-share-recipients'),
    path('api/mydesk/notes/<int:pk>/', MyDeskNoteDetailView.as_view(), name='mydesk-notes-detail'),
    path('api/mydesk/notes/<int:pk>/share/', MyDeskNoteShareView.as_view(), name='mydesk-notes-share'),
    path('api/mydesk/notes/<int:pk>/versions/<int:vid>/restore/', MyDeskNoteVersionRestoreView.as_view(), name='mydesk-notes-version-restore'),
    path('api/mydesk/notes/<int:pk>/versions/<int:vid>/', MyDeskNoteVersionDetailView.as_view(), name='mydesk-notes-version-detail'),
    path('api/mydesk/notes/attachments/<int:pk>/', MyDeskNoteAttachmentDetailView.as_view(), name='mydesk-notes-attachment-detail'),
    path('api/mydesk/notes/<int:pk>/ai-summary/', MyDeskNoteAISummaryView.as_view(), name='mydesk-notes-ai-summary'),
    path('api/mydesk/notes/ai-copilot/', MyDeskNoteAICopilotView.as_view(), name='mydesk-notes-ai-copilot'),

    path('api/mydesk/todos/', PersonalTodoListCreateView.as_view(), name='mydesk-todos-list-create'),
    path('api/mydesk/todos/<int:pk>/', PersonalTodoDetailView.as_view(), name='mydesk-todos-detail'),
    path('api/mydesk/todos/attachments/<int:pk>/', PersonalTodoAttachmentDetailView.as_view(), name='mydesk-todos-attachment-detail'),

    path('api/mydesk/expenses/', ExpenseListCreateView.as_view(), name='mydesk-expenses-list-create'),
    path('api/mydesk/expenses/<int:pk>/', ExpenseDetailView.as_view(), name='mydesk-expenses-detail'),
    path('api/mydesk/expenses/send-to-hr/', ExpenseSendToHrView.as_view(), name='mydesk-expenses-send-to-hr'),

    path('api/mydesk/leaves/', LeaveRequestListCreateView.as_view(), name='mydesk-leaves-list-create'),
    path('api/mydesk/leaves/<int:pk>/', LeaveRequestDetailView.as_view(), name='mydesk-leaves-detail'),

    path('api/hr/leaves/', HrLeaveRequestView.as_view(), name='hr-leaves-list'),
    path('api/hr/leaves/<int:pk>/', HrLeaveRequestView.as_view(), name='hr-leaves-detail'),

    path('api/mydesk/attendance/overview/', MyDeskAttendanceOverviewView.as_view(), name='mydesk-attendance-overview'),
    path('api/mydesk/attendance/entries/', MyDeskAttendanceEntryCreateView.as_view(), name='mydesk-attendance-entry-create'),
    path('api/mydesk/attendance/rulebook/', MyAttendanceRulebookView.as_view(), name='mydesk-attendance-rulebook'),
    path('api/mydesk/attendance/score/', AttendanceScoreView.as_view(), name='mydesk-attendance-score'),
    path('api/mydesk/payroll/overview/', MyDeskPayrollOverviewView.as_view(), name='mydesk-payroll-overview'),
    path('api/mydesk/payroll/declarations/', MyDeskPayrollDeclarationsView.as_view(), name='mydesk-payroll-declarations'),
    path('api/mydesk/payroll/dispute/', MyDeskPayrollDisputeView.as_view(), name='mydesk-payroll-dispute'),

    path('api/hr/attendance/today/', HrAttendanceTodayView.as_view(), name='hr-attendance-today'),
    path('api/hr/attendance/monthly-register/', HrAttendanceMonthlyRegisterView.as_view(), name='hr-attendance-monthly-register'),
    path('api/hr/attendance/employee-summary/', HrAttendanceEmployeeSummaryView.as_view(), name='hr-attendance-employee-summary'),
    path('api/hr/attendance/regularizations/', HrRegularizationQueueView.as_view(), name='hr-attendance-regularizations'),
    path('api/hr/attendance/regularizations/<int:entry_id>/', HrRegularizationQueueView.as_view(), name='hr-attendance-regularization-detail'),
    path('api/hr/attendance/override/<int:entry_id>/', HrAttendanceOverrideView.as_view(), name='hr-attendance-override'),
    path('api/hr/attendance/rulebook/<int:user_id>/', AttendanceRulebookView.as_view(), name='hr-attendance-rulebook'),
    path('api/hr/attendance/scores/', HrAttendanceScoreListView.as_view(), name='hr-attendance-scores'),

    # --- WFO/WFH Geofenced Attendance ---
    path('api/hr/offices/', OfficeLocationListCreateView.as_view(), name='office-location-list-create'),
    path('api/hr/offices/<int:pk>/', OfficeLocationDetailView.as_view(), name='office-location-detail'),
    path('api/hr/offices/<int:pk>/geocode/', OfficeLocationGeocodeView.as_view(), name='office-location-geocode'),
    path('api/hr/offices/<int:office_pk>/ips/', OfficeIPCreateView.as_view(), name='office-ip-create'),
    path('api/hr/offices/<int:office_pk>/ips/<int:ip_pk>/', OfficeIPDeleteView.as_view(), name='office-ip-delete'),
    path('api/hr/detect-ip/', DetectMyIPView.as_view(), name='detect-my-ip'),
    
    path('api/attendance/session/start/', AttendanceSessionStartView.as_view(), name='attendance-session-start'),
    path('api/attendance/session/end/', AttendanceSessionEndView.as_view(), name='attendance-session-end'),
    path('api/attendance/sessions/', AttendanceSessionListView.as_view(), name='attendance-session-list'),
    
    path('api/hr/attendance/anomalies/', AttendanceAnomalyListView.as_view(), name='hr-attendance-anomalies'),
    path('api/hr/attendance/anomalies/<int:pk>/resolve/', AttendanceAnomalyResolveView.as_view(), name='hr-attendance-anomaly-resolve'),
    
    path('api/hr/attendance/report/', AttendanceReportView.as_view(), name='hr-attendance-report'),
    path('api/hr/attendance/report/export/', AttendanceReportExportView.as_view(), name='hr-attendance-report-export'),
    path('api/hr/attendance/holidays/', PublicHolidayListCreateView.as_view(), name='hr-attendance-holidays'),
    path('api/hr/attendance/holidays/<int:pk>/', PublicHolidayDetailView.as_view(), name='hr-attendance-holiday-detail'),
    path('api/hr/attendance/exemptions/', AttendanceSessionExemptionListCreateView.as_view(), name='hr-attendance-exemptions'),
    path('api/hr/attendance/exemptions/<int:pk>/', AttendanceSessionExemptionDetailView.as_view(), name='hr-attendance-exemption-detail'),
    path('api/attendance/session/heartbeat/', AttendanceSessionHeartbeatView.as_view(), name='attendance-session-heartbeat'),
    path('api/hr/tasks/master-tracker/', HrMasterTaskTrackerView.as_view(), name='hr-master-task-tracker'),
    path('api/hr/tasks/master-tracker/assign/', HrMasterTaskTrackerAssignView.as_view(), name='hr-master-task-tracker-assign'),
    path('api/hr/tasks/master-tracker/export/', HrMasterTaskTrackerExportView.as_view(), name='hr-master-task-tracker-export'),
    path('api/hr/payroll/run/', HrPayrollRunControlView.as_view(), name='hr-payroll-run-control'),
    
    # DELIVERY ANALYTICS MODULE
    path('api/logistics/analytics-dashboard/', LogisticsAnalyticsView.as_view(), name='logistics-analytics-dashboard'),

    path('api/hr/payroll/dashboard/', HrPayrollDashboardView.as_view(), name='hr-payroll-dashboard'),
    path('api/hr/payroll/dashboard/<int:user_id>/', HrPayrollEmployeeDetailView.as_view(), name='hr-payroll-employee-detail'),
    path('api/finance/payroll/ledger/', FinancePayrollLedgerView.as_view(), name='finance-payroll-ledger'),
    path('api/hr/meeting-manager/', HrMeetingManagerOverviewView.as_view(), name='hr-meeting-manager-overview'),
    path('api/hr/meeting-manager/company-events/<int:event_id>/', HrMeetingManagerCompanyEventDetailView.as_view(), name='hr-meeting-manager-company-event-detail'),
    path('api/hr/diary/logbooks/', HRDiaryLogbookListView.as_view(), name='hr-diary-logbooks'),
    path('api/hr/expenses/tracker/', HrExpenseTrackerOverviewView.as_view(), name='hr-expense-tracker-overview'),
    path('api/hr/expenses/tracker/member/<int:user_id>/', HrExpenseTrackerMemberDetailView.as_view(), name='hr-expense-tracker-member-detail'),
    path('api/hr/expenses/tracker/<int:expense_id>/approval/', HrExpenseTrackerApprovalActionView.as_view(), name='hr-expense-tracker-approval-action'),
    path('api/hr/expenses/tracker/member/<int:user_id>/request-approval/', HrExpenseTrackerRequestApprovalView.as_view(), name='hr-expense-tracker-request-approval'),
    path('api/hr/training/', include('hr.training.urls')),

    path('api/mydesk/gallery/albums/', GalleryAlbumListCreateView.as_view(), name='mydesk-gallery-albums'),
    path('api/mydesk/gallery/items/', GalleryItemListCreateView.as_view(), name='mydesk-gallery-items-list-create'),
    path('api/mydesk/gallery/items/<int:pk>/', GalleryItemDetailView.as_view(), name='mydesk-gallery-items-detail'),
    path('api/mydesk/gallery/items/<int:pk>/download/', GalleryItemDownloadView.as_view(), name='mydesk-gallery-items-download'),
    path('api/mydesk/vault/save-from-chat/', VaultSaveFromChatView.as_view(), name='mydesk-vault-save-from-chat'),
    path('api/mydesk/vault/stats/', VaultStorageStatsView.as_view(), name='mydesk-vault-stats'),

    # =====================================================================
    # INVENTORY MODULE
    # =====================================================================
    path("api/inventory/", include("inventory.urls")),

    # =====================================================================
    # FINANCE ACCOUNTING MODULE
    # =====================================================================
    path('api/accounting/', include('accounting.urls')),
    path('api/finance/income/', FinanceIncomeListCreateView.as_view(), name='finance-income-list-create'),
    path('api/finance/income/<int:pk>/', FinanceIncomeDetailView.as_view(), name='finance-income-detail'),
    path('api/finance/expenses/', FinanceExpenseListCreateView.as_view(), name='finance-expense-list-create'),
    path('api/finance/expenses/<int:pk>/', FinanceExpenseDetailView.as_view(), name='finance-expense-detail'),
    path('api/finance/options/', FinanceOptionListCreateView.as_view(), name='finance-option-list-create'),
    path('api/finance/options/<int:pk>/', FinanceOptionDetailView.as_view(), name='finance-option-detail'),
    path('api/finance/ledger-summary/', FinanceLedgerSummaryView.as_view(), name='finance-ledger-summary'),
    path('api/finance/trial-balance/', FinanceTrialBalanceView.as_view(), name='finance-trial-balance'),
    path('api/finance/profit-loss/', FinanceProfitLossView.as_view(), name='finance-profit-loss'),
    path('api/finance/balance-sheet/', FinanceBalanceSheetView.as_view(), name='finance-balance-sheet'),
    path('api/finance/pending-expenses/', FinancePendingExpenseListView.as_view(), name='finance-pending-expenses'),
    path('api/finance/pending-expenses/sync/', FinancePendingExpenseSyncView.as_view(), name='finance-pending-expenses-sync'),
    path('api/finance/pending-expenses/member/<int:user_id>/', FinancePendingExpenseMemberDetailView.as_view(), name='finance-pending-expense-member'),
    path('api/finance/pending-expenses/<int:pk>/approve/', FinancePendingExpenseApproveView.as_view(), name='finance-pending-expense-approve'),
    path('api/finance/pending-expenses/<int:pk>/reject/', FinancePendingExpenseRejectView.as_view(), name='finance-pending-expense-reject'),
    path('api/finance/ai-chat/', FinanceAIChatView.as_view(), name='finance-ai-chat'),
    path('api/finance/financial-plan/', FinanceGeneratePlanView.as_view(), name='finance-financial-plan'),
    path('api/finance/executive-report/', FinanceGenerateReportView.as_view(), name='finance-executive-report'),
    path('api/finance/control-tower/dashboard/', FinanceControlTowerDashboardView.as_view(), name='finance-control-tower-dashboard'),

    # --- COD Remittance (moved from /api/delivery/ to Finance section) ---
    path('api/finance/cod-remittance/', CODRemittanceListView.as_view(), name='finance-cod-remittance-list'),
    path('api/finance/cod-remittance/upload-excel/', CODRemittanceUploadView.as_view(), name='finance-cod-remittance-upload'),
    path('api/finance/cod-remittance/confirm/', CODRemittanceConfirmView.as_view(), name='finance-cod-remittance-confirm'),
    path('api/finance/cod-remittance/weekly-summary/', CODRemittanceWeeklySummaryView.as_view(), name='finance-cod-remittance-weekly-summary'),

    # --- Prepaid Remittance ---
    path('api/finance/prepaid-remittance/', PrepaidRemittanceListView.as_view(), name='finance-prepaid-remittance-list'),
    path('api/finance/prepaid-remittance/upload-excel/', PrepaidRemittanceUploadView.as_view(), name='finance-prepaid-remittance-upload'),
    path('api/finance/prepaid-remittance/confirm/', PrepaidRemittanceConfirmView.as_view(), name='finance-prepaid-remittance-confirm'),
    path('api/finance/prepaid-remittance/weekly-summary/', PrepaidRemittanceWeeklySummaryView.as_view(), name='finance-prepaid-remittance-weekly-summary'),
    path('api/finance/prepaid-remittance/backfill/', PrepaidRemittanceBackfillView.as_view(), name='finance-prepaid-remittance-backfill'),
    path('api/finance/gateway-fee-rules/', PaymentGatewayFeeRuleView.as_view(), name='finance-gateway-fee-rules'),

    path("api/logs/", include("activity_logs.urls")),
    path("api/hiring/", include("hiring.urls", namespace="hiring")),

    # =====================================================================
    # CHATWOOT OMNICHANNEL INTEGRATION
    # =====================================================================
    path('api/chatwoot/sso-login/', ChatwootSSORedirectView.as_view(), name='chatwoot-sso-login'),
    path('api/chatwoot/sidebar-context/', ChatwootSidebarWidgetView.as_view(), name='chatwoot-sidebar-context'),
    path('api/chatwoot/webhook/', ChatwootWebhookView.as_view(), name='chatwoot-webhook'),
    path('api/chatwoot/audit/simulate/', ChatwootAgentSimulationView.as_view(), name='chatwoot-audit-simulate'),
    path('api/chatwoot/audit/logs/', ChatwootAgentAuditLogsView.as_view(), name='chatwoot-audit-logs'),
    path('api/chatwoot/agent/config/', ChatwootAgentConfigView.as_view(), name='chatwoot-agent-config'),
    path('api/chatwoot/agent/assignable-agents/', ChatwootInboxAgentsView.as_view(), name='chatwoot-agent-assignable-agents'),
    path('api/chatwoot/agent/trigger-scrape/', ChatwootAgentTriggerScrapeView.as_view(), name='chatwoot-agent-trigger-scrape'),
    path('api/chatwoot/agent/nuggets/', ChatwootAgentNuggetsView.as_view(), name='chatwoot-agent-nuggets'),
    path('api/chatwoot/agent/nuggets/parse/', ChatwootAgentNuggetParseView.as_view(), name='chatwoot-agent-nuggets-parse'),

] + router.urls


# --- CRITICAL FIX: Add Media Serving in Development ---
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
# Triggered reload to fix 404
