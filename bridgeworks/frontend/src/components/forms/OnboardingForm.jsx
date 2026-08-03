import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  TextField,
  Typography,
  Alert,
  CircularProgress,
  IconButton,
  InputAdornment,
  Divider,
  Switch,
  FormControlLabel,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Tabs,
  Tab,
  Grid,
  Card,
  CardContent,
  CardActions,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  OutlinedInput
} from "@mui/material";
import {
  Visibility,
  VisibilityOff,
  CheckCircle,
  Cancel,
  Search,
  ShoppingCart,
  LocalShipping,
  Undo,
  TrendingUp,
  Inventory2,
  Settings,
  HelpOutline,
  CloudUpload,
  Info,
  AltRoute,
  Assessment,
  Timeline,
  People,
  RequestQuote,
  RemoveShoppingCart,
  Store,
  Storefront,
  SupportAgent,
  Psychology,
  Campaign,
  AccountBalanceWallet,
  NotificationsActive,
  Email,
  PhoneAndroid
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

// --- CONFIGURATION ---
import { BACKEND_URL } from "../../config/api";
import { apiClient } from "../../apiClient";
import ShopifyConnect from './ShopifyConnect';
import { useUser } from '../../contexts/UserContext';
import { checkActionPermission } from '../../utils/rbac';

const MODULE_LABELS = {
  leadership: 'Leadership & Strategy',
  product: 'Product & Merchandising',
  branding: 'Branding & Creative',
  marketing: 'Marketing & Growth',
  ecommerce: 'E-Commerce & Website',
  operations: 'Operations & Fulfilment',
  tracking: 'Logistics',
  rto_management: 'Reverse Shipment',
  taskmanager: 'My Desk',
  customerExperience: 'Customer Experience',
  intelligence: 'Intelligence',
  webhooks: 'Webhooks',
  finance: 'Finance & Accounting',
  hr: 'Human Resources',
  it: 'IT & Data',
  production: 'Production / Manufacturing',
  sales: 'Sales & Business Dev',
};

const getModuleIcon = (moduleKey, sx) => {
  switch (moduleKey) {
    case 'sales_overview':
      return <TrendingUp sx={sx} />;
    case 'order_attribution':
      return <AltRoute sx={sx} />;
    case 'performance_analytics':
      return <Assessment sx={sx} />;
    case 'sales_forecasting':
      return <Timeline sx={sx} />;
    case 'retail_crm_leads':
      return <People sx={sx} />;
    case 'quotation_tracker':
      return <RequestQuote sx={sx} />;
    case 'cart_recovery':
      return <RemoveShoppingCart sx={sx} />;
    case 'shopify_analytics':
      return <Store sx={sx} />;
    case 'marketplace':
      return <Storefront sx={sx} />;
    case 'operations':
      return <Settings sx={sx} />;
    case 'logistics':
      return <LocalShipping sx={sx} />;
    case 'rto_engine':
      return <Undo sx={sx} />;
    case 'customer_care':
      return <SupportAgent sx={sx} />;
    case 'intelligence':
      return <Psychology sx={sx} />;
    case 'product_merchandising':
      return <Inventory2 sx={sx} />;
    case 'marketing':
      return <Campaign sx={sx} />;
    case 'finance_accounting':
      return <AccountBalanceWallet sx={sx} />;
    default:
      return <NotificationsActive sx={sx} />;
  }
};

export default function OnboardingForm() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user: currentUser } = useUser();

  // Selected Tab state
  const [tabValue, setTabValue] = useState(() => {
    const params = new URLSearchParams(location.search);
    const tabParam = params.get('tab');
    if (tabParam === 'notifications') {
      return 6;
    }
    const num = parseInt(tabParam, 10);
    if (!isNaN(num) && num >= 0 && num < 7) {
      return num;
    }
    return 0;
  });

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tabParam = params.get('tab');
    if (tabParam === 'notifications') {
      setTabValue(6);
    } else {
      const num = parseInt(tabParam, 10);
      if (!isNaN(num) && num >= 0 && num < 7) {
        setTabValue(num);
      }
    }
  }, [location.search]);

  const [searchQuery, setSearchQuery] = useState('');

  // Notification Preferences state
  const [preferences, setPreferences] = useState([]);
  const [prefLoading, setPrefLoading] = useState(false);

  const fetchPreferences = async () => {
    setPrefLoading(true);
    try {
      const res = await apiClient(`${BACKEND_URL}/api/notification-preferences/bulk-settings/`);
      if (res.ok) {
        const data = await res.json();
        setPreferences(data);
      }
    } catch (err) {
      console.error("Error fetching notification preferences:", err);
    } finally {
      setPrefLoading(false);
    }
  };

  const handleTogglePref = async (category, field) => {
    const updatedPrefs = preferences.map(pref => {
      if (pref.category === category) {
        return { ...pref, [field]: !pref[field] };
      }
      return pref;
    });
    setPreferences(updatedPrefs);

    try {
      const res = await apiClient(`${BACKEND_URL}/api/notification-preferences/bulk-settings/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preferences: updatedPrefs }),
      });
      if (!res.ok) {
        fetchPreferences();
      }
    } catch (err) {
      console.error("Network error saving preferences:", err);
      fetchPreferences();
    }
  };

  // Active modal platform ID state (null, 'shopify', 'shipway', 'shiprocket', etc.)
  const [activeModal, setActiveModal] = useState(null);

  // Form states matching backend keys
  const [formData, setFormData] = useState({
    shopify_api_key: '',
    shopify_api_password: '',
    shopify_shop_url: '',
    shopify_webhook_secret: '',
    shopify_api_version: '2024-07',
    shopify_order_prefix: 'JANKI',
    auth_method: 'legacy',
    shipping_platform: 'shipway',
    shipway_email: '',
    shipway_license_key: '',
    shipway_warehouse_id: 39842,
    shipway_return_warehouse_id: 39842,
    shipway_order_weight: 500,
    shipway_box_length: 10,
    shipway_box_breadth: 10,
    shipway_box_height: 10,
    shipway_invoice_number_prefix: 'N',
    shipway_primary_carrier_id: '82600',
    shipway_primary_carrier_title: 'Bluedart Direct - Surface',
    shipway_fallback_carrier_id: '2',
    shipway_fallback_carrier_title: 'Direct Delhivery',
    shipway_store_code: 44180,
    skip_shipway_pii_sync: false,
    shiprocket_email: '',
    shiprocket_password: '',
    shiprocket_pickup_location: '',
    shiprocket_order_weight: 0.5,
    shiprocket_box_length: 10,
    shiprocket_box_breadth: 10,
    shiprocket_box_height: 10,
    return_prime_token: '',
    bluedart_client_id: '',
    bluedart_client_secret: '',
    bluedart_login_id: '',
    bluedart_licence_key: '',
    bluedart_api_type: 'S',
    enable_auto_confirm_orders: true,
    enable_auto_assign_couriers: true,
    enable_auto_send_picklists: true
  });

  const [metaCreds, setMetaCreds] = useState({
    ad_account_id: '',
    access_token: '',
    app_id: '',
    app_secret: '',
    is_active: true,
  });

  const [googleCreds, setGoogleCreds] = useState({
    client_id: '',
    login_customer_id: '',
    customer_id: '',
    developer_token: '',
    client_secret: '',
    refresh_token: '',
    is_active: true,
  });

  const [prodCreds, setProdCreds] = useState({ api_url: '', api_key: '' });

  // Status & Loading states
  const [initialLoading, setInitialLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showCreds, setShowCreds] = useState(false);

  // Fetch all credentials on mount
  const fetchAllCredentials = async () => {
    try {
      // 1. Shopify & Shipping (Shipway / Shiprocket / Bluedart)
      const onboardingRes = await apiClient(`${BACKEND_URL}/api/onboarding/`, { credentials: 'include' });
      if (onboardingRes.ok) {
        const data = await onboardingRes.json();
        if (!data.onboarding_needed && !data.error) {
          setFormData(prev => ({
            ...prev,
            shopify_api_key: data.shopify_api_key || '',
            shopify_api_password: data.shopify_api_password || '',
            shopify_shop_url: data.shopify_shop_url || '',
            shopify_webhook_secret: data.shopify_webhook_secret || '',
            shopify_api_version: '2024-07',
            shopify_order_prefix: data.shopify_order_prefix || 'JANKI',
            auth_method: data.auth_method || 'legacy',
            shipping_platform: data.shipping_platform || 'shipway',
            shipway_email: data.shipway_email || '',
            shipway_license_key: data.shipway_license_key || '',
            shipway_warehouse_id: data.shipway_warehouse_id !== undefined ? data.shipway_warehouse_id : 39842,
            shipway_return_warehouse_id: data.shipway_return_warehouse_id !== undefined ? data.shipway_return_warehouse_id : 39842,
            shipway_order_weight: data.shipway_order_weight !== undefined ? data.shipway_order_weight : 500,
            shipway_box_length: data.shipway_box_length !== undefined ? data.shipway_box_length : 10,
            shipway_box_breadth: data.shipway_box_breadth !== undefined ? data.shipway_box_breadth : 10,
            shipway_box_height: data.shipway_box_height !== undefined ? data.shipway_box_height : 10,
            shipway_invoice_number_prefix: data.shipway_invoice_number_prefix || 'N',
            shipway_primary_carrier_id: data.shipway_primary_carrier_id || '82600',
            shipway_primary_carrier_title: data.shipway_primary_carrier_title || 'Bluedart Direct - Surface',
            shipway_fallback_carrier_id: data.shipway_fallback_carrier_id || '2',
            shipway_fallback_carrier_title: data.shipway_fallback_carrier_title || 'Direct Delhivery',
            shipway_store_code: data.shipway_store_code !== undefined ? data.shipway_store_code : 44180,
            skip_shipway_pii_sync: data.skip_shipway_pii_sync !== undefined ? data.skip_shipway_pii_sync : false,
            shiprocket_email: data.shiprocket_email || '',
            shiprocket_password: data.shiprocket_password || '',
            shiprocket_pickup_location: data.shiprocket_pickup_location || '',
            shiprocket_order_weight: data.shiprocket_order_weight !== undefined ? data.shiprocket_order_weight : 0.5,
            shiprocket_box_length: data.shiprocket_box_length !== undefined ? data.shiprocket_box_length : 10,
            shiprocket_box_breadth: data.shiprocket_box_breadth !== undefined ? data.shiprocket_box_breadth : 10,
            shiprocket_box_height: data.shiprocket_box_height !== undefined ? data.shiprocket_box_height : 10,
            return_prime_token: data.return_prime_token || '',
            bluedart_client_id: data.bluedart_client_id || '',
            bluedart_client_secret: data.bluedart_client_secret || '',
            bluedart_login_id: data.bluedart_login_id || '',
            bluedart_licence_key: data.bluedart_licence_key || '',
            bluedart_api_type: data.bluedart_api_type || 'S',
            enable_auto_confirm_orders: data.enable_auto_confirm_orders !== undefined ? data.enable_auto_confirm_orders : true,
            enable_auto_assign_couriers: data.enable_auto_assign_couriers !== undefined ? data.enable_auto_assign_couriers : true,
            enable_auto_send_picklists: data.enable_auto_send_picklists !== undefined ? data.enable_auto_send_picklists : true
          }));
        }
      }

      // 2. Meta marketing
      const metaRes = await apiClient(`${BACKEND_URL}/api/marketing/credentials/`);
      if (metaRes.ok) {
        const data = await metaRes.json();
        setMetaCreds(data);
      }

      // 3. Google Ads
      const googleRes = await apiClient(`${BACKEND_URL}/api/marketing/credentials/google/`);
      if (googleRes.ok) {
        const data = await googleRes.json();
        setGoogleCreds(data);
      }

      // 4. Production API
      const prodRes = await apiClient(`${BACKEND_URL}/api/settings/production-software/`);
      if (prodRes.ok) {
        const data = await prodRes.json();
        setProdCreds(data);
      }
    } catch (err) {
      console.error("Failed to load credentials:", err);
    } finally {
      setInitialLoading(false);
    }
  };

  useEffect(() => {
    fetchAllCredentials();
    fetchPreferences();
  }, []);

  // Form field change handlers
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleMetaChange = (e) => {
    const { name, value, type, checked } = e.target;
    setMetaCreds(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  const handleGoogleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setGoogleCreds(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };

  // Generic Save handler mapped to respective endpoints
  const handleSaveConfig = async (platformId) => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      let response;
      if (platformId === 'shopify' || platformId === 'shipway' || platformId === 'shiprocket' || platformId === 'bluedart' || platformId === 'returnprime' || platformId === 'workflows') {
        // Send fields to onboarding endpoint
        response = await apiClient(`${BACKEND_URL}/api/onboarding/`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData),
        });
      } else if (platformId === 'meta') {
        response = await apiClient(`${BACKEND_URL}/api/marketing/credentials/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(metaCreds),
        });
      } else if (platformId === 'google') {
        response = await apiClient(`${BACKEND_URL}/api/marketing/credentials/google/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(googleCreds),
        });
      } else if (platformId === 'production') {
        response = await apiClient(`${BACKEND_URL}/api/settings/production-software/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(prodCreds),
        });
      }

      if (response.ok) {
        setSuccess('Integration configuration saved successfully!');
        // Refresh statuses
        await fetchAllCredentials();
        setTimeout(() => {
          setActiveModal(null);
          setSuccess(null);
        }, 1500);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || errorData.error || 'Failed to save configuration.');
      }
    } catch (err) {
      setError(`Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Integration card listing definition
  const INTEGRATIONS = [
    {
      id: 'shopify',
      title: 'Shopify',
      category: 'commerce',
      description: 'Connect your store to sync customer orders, line items, and product catalogs.',
      isInstalled: !!formData.shopify_shop_url,
      avatarColor: 'rgba(94, 142, 62, 0.08)',
      avatarIcon: <ShoppingCart sx={{ fontSize: '2rem', color: '#5e8e3e' }} />
    },
    {
      id: 'shipway',
      title: 'Shipway',
      category: 'shipping',
      description: 'Automate AWB booking, cascading carrier routing, and real-time shipment updates.',
      isInstalled: !!formData.shipway_email && !!formData.shipway_license_key,
      isActive: formData.shipping_platform === 'shipway',
      avatarColor: 'rgba(25, 118, 210, 0.08)',
      avatarIcon: <LocalShipping sx={{ fontSize: '2rem', color: '#1976d2' }} />
    },
    {
      id: 'shiprocket',
      title: 'Shiprocket',
      category: 'shipping',
      description: 'Direct integration with Shiprocket for auto-AWB assignment and delivery updates.',
      isInstalled: !!formData.shiprocket_email,
      isActive: formData.shipping_platform === 'shiprocket',
      avatarColor: 'rgba(115, 0, 230, 0.08)',
      avatarIcon: <LocalShipping sx={{ fontSize: '2rem', color: '#7300e6' }} />
    },
    {
      id: 'bluedart',
      title: 'Blue Dart (Direct)',
      category: 'shipping',
      description: 'Connect your Blue Dart Direct account for automated tracking and label prints.',
      isInstalled: !!formData.bluedart_client_id,
      avatarColor: 'rgba(255, 204, 0, 0.08)',
      avatarIcon: <LocalShipping sx={{ fontSize: '2rem', color: '#f5b000' }} />
    },
    {
      id: 'returnprime',
      title: 'Return Prime',
      category: 'returns',
      description: 'Listen to product return events and auto-reconciliation of return states.',
      isInstalled: !!formData.return_prime_token,
      avatarColor: 'rgba(233, 30, 99, 0.08)',
      avatarIcon: <Undo sx={{ fontSize: '2rem', color: '#e91e63' }} />
    },
    {
      id: 'meta',
      title: 'Meta Ads',
      category: 'marketing',
      description: 'Enrich marketing KPIs, fetch ad campaign costs, and audit return on ad spend (ROAS).',
      isInstalled: !!metaCreds.ad_account_id,
      avatarColor: 'rgba(0, 102, 255, 0.08)',
      avatarIcon: <TrendingUp sx={{ fontSize: '2rem', color: '#0066ff' }} />
    },
    {
      id: 'google',
      title: 'Google Ads',
      category: 'marketing',
      description: 'Import Campaign performance, conversion counts, and CAC calculations.',
      isInstalled: !!googleCreds.customer_id,
      avatarColor: 'rgba(234, 67, 53, 0.08)',
      avatarIcon: <TrendingUp sx={{ fontSize: '2rem', color: '#ea4335' }} />
    },
    {
      id: 'production',
      title: 'Production Software API',
      category: 'production',
      description: 'Connect your production software for inventory enrichment (actual quantities, WIP, SKU mapping).',
      isInstalled: !!prodCreds.api_url,
      avatarColor: 'rgba(46, 125, 50, 0.08)',
      avatarIcon: <Inventory2 sx={{ fontSize: '2rem', color: '#2e7d32' }} />
    },
    {
      id: 'workflows',
      title: 'Internal Workflows',
      category: 'commerce',
      description: 'Configure automated background workflows for order confirmations, courier/AWB routing, and scheduled reports.',
      isInstalled: true,
      avatarColor: 'rgba(2, 136, 209, 0.08)',
      avatarIcon: <Settings sx={{ fontSize: '2rem', color: '#0288d1' }} />
    }
  ];

  const canEditGeneral = checkActionPermission(currentUser, 'settings', 'general_settings', 'edit');
  const canEditMeta = checkActionPermission(currentUser, 'marketing_growth', 'meta_ads', 'edit');
  const canEditGoogle = checkActionPermission(currentUser, 'marketing_growth', 'google_ads', 'edit');
  const canEditProd = canEditGeneral || checkActionPermission(currentUser, 'inventory', 'inventory_management', 'edit');

  if (!canEditGeneral && !canEditMeta && !canEditGoogle) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary">
          You do not have permission to modify any store settings.
        </Typography>
      </Box>
    );
  }

  // Categories lookup map
  const categories = [
    { value: 'all', label: 'All' },
    { value: 'commerce', label: 'Commerce' },
    { value: 'shipping', label: 'Shipping' },
    { value: 'returns', label: 'Returns' },
    { value: 'marketing', label: 'Marketing' },
    { value: 'production', label: 'Production' },
    { value: 'notifications', label: 'Notifications' }
  ];

  const activeCategory = categories[tabValue].value;

  const filteredIntegrations = INTEGRATIONS.filter(item => {
    if (activeCategory !== 'all' && item.category !== activeCategory) return false;
    if (searchQuery && !item.title.toLowerCase().includes(searchQuery.toLowerCase()) && !item.description.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const filteredPrefs = preferences.filter(pref => {
    const label = MODULE_LABELS[pref.category] || pref.category_display || pref.category;
    return label.toLowerCase().includes(searchQuery.toLowerCase());
  });

  return (
    <Box sx={{ p: 4, height: '100%', overflowY: 'auto', bgcolor: '#f8fafc' }}>


      {/* 2. Tabs and Search controls */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4, borderBottom: 1, borderColor: '#e2e8f0', gap: 2, flexWrap: 'wrap' }}>
        <Tabs
          value={tabValue}
          onChange={(e, val) => setTabValue(val)}
          sx={{
            '& .MuiTabs-indicator': { bgcolor: '#1e293b', height: 3 },
            '& .MuiTab-root': { fontWeight: 600, fontSize: '0.9rem', color: '#64748b', '&.Mui-selected': { color: '#0f172a' } }
          }}
        >
          {categories.map((cat, idx) => (
            <Tab key={idx} label={cat.label} />
          ))}
        </Tabs>

        <TextField
          placeholder={activeCategory === 'notifications' ? "Search modules..." : "Search integrations..."}
          size="small"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search sx={{ color: '#94a3b8' }} />
              </InputAdornment>
            ),
          }}
          sx={{
            width: 280,
            mb: 1.5,
            bg: 'white',
            '& .MuiOutlinedInput-root': { borderRadius: '8px', bgcolor: 'white' }
          }}
        />
      </Box>

      {initialLoading || prefLoading ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 300, gap: 2 }}>
          <CircularProgress />
          <Typography variant="body2" color="text.secondary">Loading settings...</Typography>
        </Box>
      ) : activeCategory === 'notifications' ? (
        <Box sx={{ animation: 'fadeIn 0.3s ease-in-out' }}>

          <Grid container spacing={3}>
            {filteredPrefs.map((pref) => {
              const moduleName = MODULE_LABELS[pref.category] || pref.category_display || pref.category;
              const hasActiveChannel = pref.in_app_delivery || pref.email_delivery || pref.push_delivery;
              return (
                <Grid item xs={12} md={6} lg={4} key={pref.id} sx={{ display: 'flex' }}>
                  <Card sx={{
                    width: '100%',
                    borderRadius: 4,
                    border: '1px solid #f1f5f9',
                    boxShadow: '0 4px 18px rgba(0, 0, 0, 0.02)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: '0 10px 25px rgba(0,0,0,0.06)'
                    }
                  }}>
                    <CardContent sx={{ p: 3 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2.5 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                          <Box sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 44,
                            height: 44,
                            borderRadius: '12px',
                            bgcolor: hasActiveChannel ? 'rgba(30, 41, 59, 0.05)' : 'rgba(241, 245, 249, 1)',
                            color: hasActiveChannel ? '#1e293b' : '#94a3b8'
                          }}>
                            {getModuleIcon(pref.category, { fontSize: '1.4rem' })}
                          </Box>
                          <Typography variant="subtitle1" fontWeight={700} color="#0f172a">
                            {moduleName}
                          </Typography>
                        </Box>
                        <Chip
                          label={hasActiveChannel ? "Enabled" : "Muted"}
                          size="small"
                          sx={{
                            fontWeight: 700,
                            bgcolor: hasActiveChannel ? 'rgba(22, 163, 74, 0.08)' : 'rgba(244, 63, 94, 0.08)',
                            color: hasActiveChannel ? '#16a34a' : '#e11d48'
                          }}
                        />
                      </Box>
                      <Divider sx={{ my: 2, borderColor: '#f1f5f9' }} />
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                        {/* In App Channel */}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                            <NotificationsActive sx={{ color: pref.in_app_delivery ? '#0f172a' : '#94a3b8', fontSize: '1.2rem' }} />
                            <Box>
                              <Typography variant="body2" fontWeight={600} color="#334155">In-App Notification</Typography>
                              <Typography variant="caption" color="text.secondary">Display in Notification Bell</Typography>
                            </Box>
                          </Box>
                          <Switch
                            checked={pref.in_app_delivery}
                            onChange={() => handleTogglePref(pref.category, 'in_app_delivery')}
                            color="primary"
                            size="small"
                          />
                        </Box>
                        {/* Email Channel */}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                            <Email sx={{ color: pref.email_delivery ? '#0f172a' : '#94a3b8', fontSize: '1.2rem' }} />
                            <Box>
                              <Typography variant="body2" fontWeight={600} color="#334155">Email Digest</Typography>
                              <Typography variant="caption" color="text.secondary">Send to registered email</Typography>
                            </Box>
                          </Box>
                          <Switch
                            checked={pref.email_delivery}
                            onChange={() => handleTogglePref(pref.category, 'email_delivery')}
                            color="primary"
                            size="small"
                          />
                        </Box>
                        {/* Push Channel */}
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
                            <PhoneAndroid sx={{ color: pref.push_delivery ? '#0f172a' : '#94a3b8', fontSize: '1.2rem' }} />
                            <Box>
                              <Typography variant="body2" fontWeight={600} color="#334155">Push Notification</Typography>
                              <Typography variant="caption" color="text.secondary">Browser Push Alerts</Typography>
                            </Box>
                          </Box>
                          <Switch
                            checked={pref.push_delivery}
                            onChange={() => handleTogglePref(pref.category, 'push_delivery')}
                            color="primary"
                            size="small"
                          />
                        </Box>
                      </Box>
                    </CardContent>
                  </Card>
                </Grid>
              );
            })}
          </Grid>
        </Box>
      ) : (
        <Grid container spacing={3}>
          {filteredIntegrations.map((item) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={item.id} sx={{ display: 'flex' }}>
              <Card
                sx={{
                  width: '100%',
                  height: 270,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  borderRadius: 3,
                  boxShadow: '0 4px 18px rgba(0, 0, 0, 0.03)',
                  border: '1px solid #f1f5f9',
                  transition: 'transform 0.2s, box-shadow 0.2s',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.06)'
                  }
                }}
              >
                <CardContent sx={{ p: 3 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                    <Box sx={{ p: 1.5, borderRadius: 3, bgcolor: item.avatarColor }}>
                      {item.avatarIcon}
                    </Box>
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 0.5 }}>
                      {item.isInstalled ? (
                        <Chip
                          icon={<CheckCircle style={{ color: '#16a34a', fontSize: '16px' }} />}
                          label="Installed"
                          size="small"
                          sx={{ bgcolor: 'rgba(22, 163, 74, 0.08)', color: '#16a34a', fontWeight: 700 }}
                        />
                      ) : (
                        <Chip
                          label="Not Connected"
                          size="small"
                          sx={{ bgcolor: '#f1f5f9', color: '#64748b', fontWeight: 600 }}
                        />
                      )}
                      {item.isActive && (
                        <Chip
                          label="Active Route"
                          size="small"
                          color="primary"
                          sx={{ fontWeight: 700, fontSize: '0.7rem' }}
                        />
                      )}
                    </Box>
                  </Box>

                  <Typography variant="h6" fontWeight={700} gutterBottom sx={{ color: '#0f172a' }}>
                    {item.title}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ minHeight: 40, lineHeight: 1.5 }}>
                    {item.description}
                  </Typography>
                </CardContent>

                <CardActions sx={{ p: 3, pt: 0 }}>
                  <Button
                    variant={item.isInstalled ? "outlined" : "contained"}
                    color="primary"
                    fullWidth
                    onClick={() => setActiveModal(item.id)}
                    sx={{
                      borderRadius: '8px',
                      py: 1,
                      fontWeight: 700,
                      textTransform: 'none',
                      boxShadow: 'none',
                      ...(item.isInstalled ? {
                        color: '#1e293b',
                        borderColor: '#cbd5e1',
                        '&:hover': { bgcolor: '#f8fafc', borderColor: '#94a3b8' }
                      } : {
                        bgcolor: '#1e293b',
                        '&:hover': { bgcolor: '#0f172a' }
                      })
                    }}
                  >
                    {item.isInstalled ? 'Configure' : 'Connect'}
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* ============================================================================== */}
      {/* 3. MODALS FOR INDIVIDUAL CONFIGURATIONS */}
      {/* ============================================================================== */}

      {/* dialog toggle button helper */}
      <Dialog
        open={activeModal !== null}
        onClose={() => setActiveModal(null)}
        maxWidth="sm"
        fullWidth
        PaperProps={{ sx: { borderRadius: 4, p: 2 } }}
      >
        <DialogTitle sx={{ fontWeight: 800, pb: 1, color: '#0f172a' }}>
          Configure {activeModal ? INTEGRATIONS.find(i => i.id === activeModal)?.title : ''}
        </DialogTitle>

        <DialogContent sx={{ py: 2 }}>
          {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{error}</Alert>}
          {success && <Alert severity="success" sx={{ mb: 2, borderRadius: 2 }}>{success}</Alert>}

          {/* Visibility toggle bar */}
          {(activeModal === 'shopify' || activeModal === 'shipway' || activeModal === 'shiprocket' || activeModal === 'bluedart' || activeModal === 'returnprime' || activeModal === 'meta' || activeModal === 'google' || activeModal === 'production') && (
            <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 2 }}>
              <Button
                startIcon={showCreds ? <VisibilityOff /> : <Visibility />}
                onClick={() => setShowCreds(!showCreds)}
                variant="text"
                color="secondary"
                size="small"
                sx={{ textTransform: 'none', fontWeight: 600 }}
              >
                {showCreds ? 'Hide Secret Keys' : 'Reveal Secret Keys'}
              </Button>
            </Box>
          )}

          {/* A. SHOPIFY INTEGRATION FORM */}
          {activeModal === 'shopify' && (
            <Box>
              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 2, color: '#475569' }}>
                Option 1: OAuth Quick Connect (Recommended)
              </Typography>
              <ShopifyConnect />

              <Divider sx={{ my: 3 }} />

              <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1, color: '#475569' }}>
                Option 2: Private Custom App Connection
              </Typography>

              <FormControl fullWidth margin="normal">
                <InputLabel id="auth-method-label">Authentication Method</InputLabel>
                <Select
                  labelId="auth-method-label"
                  name="auth_method"
                  value={formData.auth_method}
                  onChange={handleChange}
                  label="Authentication Method"
                >
                  <MenuItem value="legacy">Legacy (Private App Password)</MenuItem>
                  <MenuItem value="oauth">OAuth (Partner App Token)</MenuItem>
                </Select>
              </FormControl>

              <TextField fullWidth margin="normal" label="Shopify Shop URL (e.g. store.myshopify.com)" name="shopify_shop_url" value={formData.shopify_shop_url} onChange={handleChange} required />
              <TextField fullWidth margin="normal" label="API Key / Client Client ID" name="shopify_api_key" value={formData.shopify_api_key} onChange={handleChange} required type={showCreds ? 'text' : 'password'} />
              <TextField fullWidth margin="normal" label="Access Token / Password" name="shopify_api_password" value={formData.shopify_api_password} onChange={handleChange} required type={showCreds ? 'text' : 'password'} />
              <TextField fullWidth margin="normal" label="Webhook Verification Secret" name="shopify_webhook_secret" value={formData.shopify_webhook_secret} onChange={handleChange} required type={showCreds ? 'text' : 'password'} />
              <TextField fullWidth margin="normal" label="Order ID Prefix Filter" name="shopify_order_prefix" value={formData.shopify_order_prefix} onChange={handleChange} placeholder="e.g. JANKI" />
            </Box>
          )}

          {/* B. SHIPWAY INTEGRATION FORM */}
          {activeModal === 'shipway' && (
            <Box>
              <FormControl fullWidth margin="normal" sx={{ mb: 2 }}>
                <InputLabel id="shipping-platform-label">Active Shipping Platform</InputLabel>
                <Select
                  labelId="shipping-platform-label"
                  name="shipping_platform"
                  value={formData.shipping_platform}
                  onChange={handleChange}
                  label="Active Shipping Platform"
                >
                  <MenuItem value="shipway">Shipway (Active)</MenuItem>
                  <MenuItem value="shiprocket">Shiprocket</MenuItem>
                </Select>
              </FormControl>

              <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 2, mb: 1, color: '#334155' }}>Authentication</Typography>
              <TextField fullWidth margin="normal" label="Shipway Registered Email" name="shipway_email" type="email" value={formData.shipway_email} onChange={handleChange} required />
              <TextField fullWidth margin="normal" label="License Key" name="shipway_license_key" value={formData.shipway_license_key} onChange={handleChange} required type={showCreds ? 'text' : 'password'} />

              <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 3, mb: 1, color: '#334155' }}>Warehouse & Weight</Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2, mt: 1 }}>
                <TextField label="Warehouse ID" name="shipway_warehouse_id" type="number" value={formData.shipway_warehouse_id} onChange={handleChange} required />
                <TextField label="Return Wh ID" name="shipway_return_warehouse_id" type="number" value={formData.shipway_return_warehouse_id} onChange={handleChange} required />
                <TextField label="Store Code" name="shipway_store_code" type="number" value={formData.shipway_store_code} onChange={handleChange} required />
              </Box>

              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2, mt: 2 }}>
                <TextField label="Weight (g)" name="shipway_order_weight" type="number" value={formData.shipway_order_weight} onChange={handleChange} required />
                <TextField label="Length (cm)" name="shipway_box_length" type="number" value={formData.shipway_box_length} onChange={handleChange} required />
                <TextField label="Breadth (cm)" name="shipway_box_breadth" type="number" value={formData.shipway_box_breadth} onChange={handleChange} required />
                <TextField label="Height (cm)" name="shipway_box_height" type="number" value={formData.shipway_box_height} onChange={handleChange} required />
              </Box>

              <TextField fullWidth margin="normal" label="Invoice Number Prefix" name="shipway_invoice_number_prefix" value={formData.shipway_invoice_number_prefix} onChange={handleChange} />

              <FormControlLabel
                control={
                  <Switch
                    checked={formData.skip_shipway_pii_sync}
                    onChange={(e) => setFormData(prev => ({ ...prev, skip_shipway_pii_sync: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Skip Customer PII Sync (Enable if Shopify App already has PII access)"
                sx={{ mt: 2, display: 'block' }}
              />

              <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 3, mb: 1, color: '#334155' }}>Carrier IDs</Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2, mt: 1 }}>
                <TextField label="Primary Carrier ID" name="shipway_primary_carrier_id" value={formData.shipway_primary_carrier_id} onChange={handleChange} required />
                <TextField label="Primary Carrier Title" name="shipway_primary_carrier_title" value={formData.shipway_primary_carrier_title} onChange={handleChange} required />
              </Box>

              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2, mt: 2 }}>
                <TextField label="Fallback Carrier ID" name="shipway_fallback_carrier_id" value={formData.shipway_fallback_carrier_id} onChange={handleChange} required />
                <TextField label="Fallback Carrier Title" name="shipway_fallback_carrier_title" value={formData.shipway_fallback_carrier_title} onChange={handleChange} required />
              </Box>
            </Box>
          )}

          {/* C. SHIPROCKET INTEGRATION FORM */}
          {activeModal === 'shiprocket' && (
            <Box>
              <FormControl fullWidth margin="normal" sx={{ mb: 3 }}>
                <InputLabel id="shipping-platform-rocket-label">Active Shipping Platform</InputLabel>
                <Select
                  labelId="shipping-platform-rocket-label"
                  name="shipping_platform"
                  value={formData.shipping_platform}
                  onChange={handleChange}
                  label="Active Shipping Platform"
                >
                  <MenuItem value="shipway">Shipway</MenuItem>
                  <MenuItem value="shiprocket">Shiprocket (Active)</MenuItem>
                </Select>
              </FormControl>

              <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 2, mb: 1, color: '#334155' }}>Authentication</Typography>
              <TextField fullWidth margin="normal" label="Shiprocket API User Email" name="shiprocket_email" type="email" value={formData.shiprocket_email} onChange={handleChange} required />
              <TextField fullWidth margin="normal" label="API User Password" name="shiprocket_password" value={formData.shiprocket_password} onChange={handleChange} required type={showCreds ? 'text' : 'password'} />

              <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 3, mb: 1, color: '#334155' }}>Warehouse</Typography>
              <TextField fullWidth margin="normal" label="Pickup Location Nickname (as set in Shiprocket panel)" name="shiprocket_pickup_location" value={formData.shiprocket_pickup_location} onChange={handleChange} required placeholder="e.g. Primary, Warehouse-1" />
              <Typography variant="caption" color="text.secondary">
                Note: In Shiprocket API, the <strong>Pickup Location Nickname</strong> is case-sensitive and must exactly match the name of the warehouse set in your Shiprocket configuration.
              </Typography>

              <Typography variant="subtitle2" fontWeight={700} sx={{ mt: 3, mb: 1, color: '#334155' }}>Default Parcel Properties</Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 2, mt: 1, mb: 2 }}>
                <TextField label="Weight (kg)" name="shiprocket_order_weight" type="number" inputProps={{ step: "0.01" }} value={formData.shiprocket_order_weight} onChange={handleChange} required />
                <TextField label="Length (cm)" name="shiprocket_box_length" type="number" value={formData.shiprocket_box_length} onChange={handleChange} required />
                <TextField label="Breadth (cm)" name="shiprocket_box_breadth" type="number" value={formData.shiprocket_box_breadth} onChange={handleChange} required />
                <TextField label="Height (cm)" name="shiprocket_box_height" type="number" value={formData.shiprocket_box_height} onChange={handleChange} required />
              </Box>
            </Box>
          )}

          {/* D. BLUE DART DIRECT INTEGRATION FORM */}
          {activeModal === 'bluedart' && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Configure your credentials for direct Blue Dart API booking. This runs independently of shipway aggregations.
              </Typography>
              <TextField fullWidth margin="normal" label="Client ID" name="bluedart_client_id" value={formData.bluedart_client_id} onChange={handleChange} required />
              <TextField fullWidth margin="normal" label="Client Secret" name="bluedart_client_secret" value={formData.bluedart_client_secret} onChange={handleChange} required type={showCreds ? 'text' : 'password'} />
              <TextField fullWidth margin="normal" label="Login ID" name="bluedart_login_id" value={formData.bluedart_login_id} onChange={handleChange} required />
              <TextField fullWidth margin="normal" label="Licence Key" name="bluedart_licence_key" value={formData.bluedart_licence_key} onChange={handleChange} required type={showCreds ? 'text' : 'password'} />

              <FormControl fullWidth margin="normal">
                <InputLabel id="bd-api-type-label">API Mode</InputLabel>
                <Select
                  labelId="bd-api-type-label"
                  name="bluedart_api_type"
                  value={formData.bluedart_api_type}
                  onChange={handleChange}
                  label="API Mode"
                >
                  <MenuItem value="S">Sandbox (Testing)</MenuItem>
                  <MenuItem value="P">Production (Live)</MenuItem>
                </Select>
              </FormControl>
            </Box>
          )}

          {/* E. RETURN PRIME INTEGRATION FORM */}
          {activeModal === 'returnprime' && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Enter your Return Prime developer API token. BridgeWorks uses this to listen to returned and rejected shipments.
              </Typography>
              <TextField fullWidth margin="normal" label="Return Prime API Token" name="return_prime_token" value={formData.return_prime_token} onChange={handleChange} required type={showCreds ? 'text' : 'password'} />
            </Box>
          )}

          {/* F. META MARKETING FORM */}
          {activeModal === 'meta' && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Configure campaign cost sync for Meta Ads accounts.
              </Typography>
              <TextField fullWidth margin="normal" label="Meta Ad Account ID" name="ad_account_id" value={metaCreds.ad_account_id} onChange={handleMetaChange} required />
              <TextField fullWidth margin="normal" label="Developer Access Token" name="access_token" value={metaCreds.access_token} onChange={handleMetaChange} required type={showCreds ? 'text' : 'password'} />
              <TextField fullWidth margin="normal" label="App ID" name="app_id" value={metaCreds.app_id} onChange={handleMetaChange} />
              <TextField fullWidth margin="normal" label="App Secret" name="app_secret" value={metaCreds.app_secret} onChange={handleMetaChange} type={showCreds ? 'text' : 'password'} />

              <FormControlLabel
                control={<Switch name="is_active" checked={metaCreds.is_active} onChange={handleMetaChange} color="primary" />}
                label="Enable Meta data sync"
                sx={{ mt: 2 }}
              />
            </Box>
          )}

          {/* G. GOOGLE ADS MARKETING FORM */}
          {activeModal === 'google' && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Enter API credentials to sync Google Ads performance metrics.
              </Typography>
              <TextField fullWidth margin="normal" label="Target Customer ID" name="customer_id" value={googleCreds.customer_id} onChange={handleGoogleChange} required />
              <TextField fullWidth margin="normal" label="Manager ID" name="login_customer_id" value={googleCreds.login_customer_id} onChange={handleGoogleChange} />
              <TextField fullWidth margin="normal" label="Developer Token" name="developer_token" value={googleCreds.developer_token} onChange={handleGoogleChange} required type={showCreds ? 'text' : 'password'} />
              <TextField fullWidth margin="normal" label="OAuth Client ID" name="client_id" value={googleCreds.client_id} onChange={handleGoogleChange} />
              <TextField fullWidth margin="normal" label="OAuth Client Secret" name="client_secret" value={googleCreds.client_secret} onChange={handleGoogleChange} type={showCreds ? 'text' : 'password'} />
              <TextField fullWidth margin="normal" label="OAuth Refresh Token" name="refresh_token" value={googleCreds.refresh_token} onChange={handleGoogleChange} type={showCreds ? 'text' : 'password'} multiline rows={2} />

              <FormControlLabel
                control={<Switch name="is_active" checked={googleCreds.is_active} onChange={handleGoogleChange} color="primary" />}
                label="Enable Google Ads data sync"
                sx={{ mt: 2 }}
              />
            </Box>
          )}

          {/* H. PRODUCTION SOFTWARE API FORM */}
          {activeModal === 'production' && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Connect your production software for inventory reconciliation and WIP mapping.
              </Typography>
              <TextField
                fullWidth margin="normal"
                label="API URL"
                placeholder="https://product-sheet.onrender.com/api/v1/inventory/"
                value={prodCreds.api_url}
                onChange={(e) => setProdCreds(prev => ({ ...prev, api_url: e.target.value }))}
                required
              />
              <TextField
                fullWidth margin="normal"
                label="API Key"
                value={prodCreds.api_key}
                onChange={(e) => setProdCreds(prev => ({ ...prev, api_key: e.target.value }))}
                required
                type={showCreds ? 'text' : 'password'}
              />
            </Box>
          )}

          {/* I. INTERNAL WORKFLOWS FORM */}
          {activeModal === 'workflows' && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Configure automated background workflows for order confirmations, courier/AWB routing, and scheduled reports.
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                {/* Auto-confirm orders */}
                <Box sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  p: 2,
                  borderRadius: 2,
                  bgcolor: formData.enable_auto_confirm_orders ? 'rgba(33, 150, 243, 0.04)' : 'rgba(0, 0, 0, 0.02)',
                  border: '1px solid',
                  borderColor: formData.enable_auto_confirm_orders ? 'rgba(33, 150, 243, 0.15)' : 'rgba(0, 0, 0, 0.06)',
                  transition: 'all 0.25s ease'
                }}>
                  <Box sx={{ pr: 2 }}>
                    <Typography variant="subtitle2" fontWeight={650} color="text.primary">
                      Auto-Confirm Orders
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      Automatically verify and confirm eligible low-risk orders using AI evaluation scores.
                    </Typography>
                  </Box>
                  <Switch
                    checked={formData.enable_auto_confirm_orders}
                    onChange={(e) => setFormData(prev => ({ ...prev, enable_auto_confirm_orders: e.target.checked }))}
                    color="primary"
                  />
                </Box>

                {/* Auto-assign couriers */}
                <Box sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  p: 2,
                  borderRadius: 2,
                  bgcolor: formData.enable_auto_assign_couriers ? 'rgba(76, 175, 80, 0.04)' : 'rgba(0, 0, 0, 0.02)',
                  border: '1px solid',
                  borderColor: formData.enable_auto_assign_couriers ? 'rgba(76, 175, 80, 0.15)' : 'rgba(0, 0, 0, 0.06)',
                  transition: 'all 0.25s ease'
                }}>
                  <Box sx={{ pr: 2 }}>
                    <Typography variant="subtitle2" fontWeight={650} color="text.primary">
                      Auto-Assign Couriers & AWB
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      Book shipping waybills on platforms (Shipway/Shiprocket) dynamically upon confirmation.
                    </Typography>
                  </Box>
                  <Switch
                    checked={formData.enable_auto_assign_couriers}
                    onChange={(e) => setFormData(prev => ({ ...prev, enable_auto_assign_couriers: e.target.checked }))}
                    color="success"
                  />
                </Box>

                {/* Auto-send picklists */}
                <Box sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  p: 2,
                  borderRadius: 2,
                  bgcolor: formData.enable_auto_send_picklists ? 'rgba(156, 39, 176, 0.04)' : 'rgba(0, 0, 0, 0.02)',
                  border: '1px solid',
                  borderColor: formData.enable_auto_send_picklists ? 'rgba(156, 39, 176, 0.15)' : 'rgba(0, 0, 0, 0.06)',
                  transition: 'all 0.25s ease'
                }}>
                  <Box sx={{ pr: 2 }}>
                    <Typography variant="subtitle2" fontWeight={650} color="text.primary">
                      Auto-Send Morning Picklists
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                      Compile and email consolidated PDF picklists to subscribed team members at scheduled times.
                    </Typography>
                  </Box>
                  <Switch
                    checked={formData.enable_auto_send_picklists}
                    onChange={(e) => setFormData(prev => ({ ...prev, enable_auto_send_picklists: e.target.checked }))}
                    color="secondary"
                  />
                </Box>
              </Box>
            </Box>
          )}

        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button onClick={() => setActiveModal(null)} color="inherit" sx={{ fontWeight: 600 }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={loading}
            onClick={() => handleSaveConfig(activeModal)}
            sx={{
              bgcolor: '#1e293b',
              color: 'white',
              fontWeight: 700,
              px: 3,
              borderRadius: '8px',
              '&:hover': { bgcolor: '#0f172a' }
            }}
          >
            {loading ? 'Saving...' : 'Save Integration'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
