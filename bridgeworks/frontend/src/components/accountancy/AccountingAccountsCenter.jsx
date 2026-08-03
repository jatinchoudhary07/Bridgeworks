import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Button,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  Tab,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Alert,
  IconButton,
  Chip,
  LinearProgress,
  Divider,
  Card,
  CardContent,
  Tooltip,
} from '@mui/material';
import {
  AccountBalance as BankIcon,
  AccountBalanceWallet as WalletIcon,
  AttachMoney as CashIcon,
  SwapHoriz as SettlementIcon,
  Folder as GroupIcon,
  History as ActivityIcon,
  Add as AddIcon,
  Close as CloseIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  CheckCircle as CheckCircleIcon,
  ChevronRight as ChevronRightIcon,
  Warning as WarningIcon
} from '@mui/icons-material';

import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';

const COLORS = {
  bg: '#F8FAFC',
  card: '#FFFFFF',
  border: '#E2E8F0',
  radius: '16px',
  radiusSm: '10px',
  primary: '#4F46E5',
  primaryHover: '#4338CA',
  primaryLight: '#EEF2FF',
  success: '#10B981',
  error: '#EF4444',
  warning: '#F59E0B',
  text: '#0F172A',
  muted: '#64748B',
};

const fmt = (value) => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function AccountingAccountsCenter() {
  const { canViewAmounts, canCreate, canEdit, canDelete } = usePagePermissions();
  const [activeTab, setActiveTab] = useState(0);
  const [accounts, setAccounts] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Drawer / Dialog states
  const [openDrawer, setOpenDrawer] = useState(false);
  const [drawerType, setDrawerType] = useState('bank'); // bank, cash, wallet, settlement, group
  const [editingAccount, setEditingAccount] = useState(null);

  // Form State
  const [formFields, setFormFields] = useState({
    account_name: '',
    account_class: 'bank',
    account_type: 'Current',
    balance: '0',
    group: '',
    status: 'active',
    // Sub-class details
    bank_name: '',
    account_number: '',
    ifsc: '',
    branch: '',
    currency: 'INR',
    location: '',
    custodian: '',
    purpose: '',
    provider: '',
    linked_account: '',
    linked_bank_account: '',
    settlement_frequency: 'Daily',
    group_name: '' // unused, kept for compat
  });

  const fetchAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient('/api/accounting/financial-accounts/', { credentials: 'include' });
      const payload = await res.json().catch(() => null);
      if (res.ok && payload?.success) {
        setAccounts(payload.data || []);
        setError(''); // Clear error on successful fetch!
      } else {
        setError(payload?.message || 'Failed to load financial accounts.');
      }
    } catch {
      setError('Could not reach backend financial accounts API.');
    } finally {
      setLoading(false);
    }
  }, []);


  const fetchDashboard = useCallback(async () => {
    try {
      const res = await apiClient('/api/accounting/accounts-center/dashboard/', { credentials: 'include' });
      const payload = await res.json().catch(() => null);
      if (res.ok && payload?.success) {
        setDashboardData(payload.data || null);
      }
    } catch {
      console.error('Failed to load dashboard data.');
    }
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      const res = await apiClient('/api/accounting/accounts-center/activity/', { credentials: 'include' });
      const payload = await res.json().catch(() => null);
      if (res.ok && payload?.success) {
        setLogs(payload.data || []);
      }
    } catch {
      console.error('Failed to load activity logs.');
    }
  }, []);

  const refreshData = useCallback(() => {
    fetchAccounts();
    fetchDashboard();
    fetchLogs();
  }, [fetchAccounts, fetchDashboard, fetchLogs]);

  useEffect(() => {
    refreshData();
  }, [refreshData]);

  const handleTabChange = (event, newValue) => {
    setActiveTab(newValue);
  };

  const handleOpenAdd = (type) => {
    setDrawerType(type);
    setEditingAccount(null);
    setFormFields({
      account_name: '',
      account_class: type,
      account_type: type === 'bank' ? 'Current' : type === 'cash' ? 'Cash' : type === 'wallet' ? 'Wallet' : type === 'settlement' ? 'Settlement' : 'Group',
      balance: '0',
      group: '',
      status: 'active',
      bank_name: '',
      account_number: '',
      ifsc: '',
      branch: '',
      currency: 'INR',
      location: '',
      custodian: '',
      purpose: '',
      provider: '',
      linked_account: '',
      linked_bank_account: '',
      settlement_frequency: 'Daily',
      group_name: ''
    });
    setOpenDrawer(true);
  };

  const handleOpenEdit = (account) => {
    setEditingAccount(account);
    setDrawerType(account.account_class);
    
    // Populate form fields
    const details = {
      account_name: account.account_name,
      account_class: account.account_class,
      account_type: account.account_type,
      balance: String(account.balance),
      group: account.group || '',
      status: account.status,
      bank_name: account.bank_detail?.bank_name || '',
      account_number: account.bank_detail?.account_number || '',
      ifsc: account.bank_detail?.ifsc || '',
      branch: account.bank_detail?.branch || '',
      currency: account.bank_detail?.currency || 'INR',
      location: account.cash_detail?.location || '',
      custodian: account.cash_detail?.custodian || '',
      purpose: account.cash_detail?.purpose || '',
      provider: account.wallet_detail?.provider || account.settlement_detail?.provider || '',
      linked_account: account.wallet_detail?.linked_account || '',
      linked_bank_account: account.settlement_detail?.linked_bank_account || '',
      settlement_frequency: account.settlement_detail?.settlement_frequency || 'Daily',
      group_name: ''
    };
    setFormFields(details);
    setOpenDrawer(true);
  };

  const handleClassChange = (newClass) => {
    setDrawerType(newClass);
    setFormFields(prev => ({
      ...prev,
      account_class: newClass,
      account_type: newClass === 'bank' ? 'Current' : newClass === 'cash' ? 'Cash' : newClass === 'wallet' ? 'Wallet' : 'Settlement',
    }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setError('');


    // Prepare payload
    const payload = {
      account_name: formFields.account_name.trim(),
      account_class: drawerType,
      account_type: formFields.account_type,
      balance: parseFloat(formFields.balance || 0),
      status: formFields.status
    };

    if (!payload.account_name) {
      setError('Account name is required.');
      return;
    }

    if (drawerType === 'bank') {
      payload.bank_name = formFields.bank_name.trim();
      payload.account_number = formFields.account_number.trim();
      payload.ifsc = formFields.ifsc.trim();
      payload.branch = formFields.branch.trim();
      payload.currency = formFields.currency;
    } else if (drawerType === 'cash') {
      payload.location = formFields.location.trim();
      payload.custodian = formFields.custodian.trim();
      payload.purpose = formFields.purpose.trim();
    } else if (drawerType === 'wallet') {
      payload.provider = formFields.provider.trim();
      payload.linked_account = formFields.linked_account || null;
    } else if (drawerType === 'settlement') {
      payload.provider = formFields.provider.trim();
      payload.settlement_frequency = formFields.settlement_frequency;
      payload.linked_bank_account = formFields.linked_bank_account || null;
    }

    try {
      const url = editingAccount 
        ? `/api/accounting/financial-accounts/${editingAccount.id}/`
        : '/api/accounting/financial-accounts/';
      
      const method = editingAccount ? 'PATCH' : 'POST';

      const res = await apiClient(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        setOpenDrawer(false);
        refreshData();
      } else {
        setError(data?.message || 'Failed to save account.');
      }
    } catch {
      setError('Network error saving account.');
    }
  };

  const handleArchive = async (id) => {
    if (!window.confirm('Are you sure you want to archive this account?')) return;
    try {
      const res = await apiClient(`/api/accounting/financial-accounts/${id}/`, {
        method: 'DELETE',
        credentials: 'include'
      });
      const data = await res.json().catch(() => null);
      if (res.ok && data?.success) {
        refreshData();
      } else {
        alert(data?.message || 'Failed to archive account.');
      }
    } catch {
      alert('Error archiving account.');
    }
  };


  const getFilteredAccounts = (cls) => {
    return accounts.filter(acc => acc.account_class === cls);
  };

  const ACC = '#4F46E5';
  const CLASS_OPTIONS = [
    { key: 'bank',   label: 'Bank Account',   icon: <BankIcon sx={{ fontSize: 16 }} />,   color: ACC, bg: '#EEF2FF' },
    { key: 'cash',   label: 'Cash Account',   icon: <CashIcon sx={{ fontSize: 16 }} />,   color: ACC, bg: '#EEF2FF' },
    { key: 'wallet', label: 'Digital Wallet', icon: <WalletIcon sx={{ fontSize: 16 }} />, color: ACC, bg: '#EEF2FF' },
  ];

  return (
    <Box sx={{ bgcolor: COLORS.bg, minHeight: '100%', p: 3, display: 'flex', flexDirection: 'column', gap: 3.5 }}>
      {/* Page Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h5" fontWeight="800" sx={{ color: COLORS.text, letterSpacing: '-0.03em', fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
            Finance Accounts Center
          </Typography>
          <Typography variant="body2" sx={{ color: COLORS.muted, mt: 0.5, fontWeight: 500 }}>
            Master financial accounts registry. Centralize and control your cash flow sources.
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          {canCreate && (
            <>
              <Button
                variant="contained"
                onClick={() => handleOpenAdd('bank')}
                startIcon={<AddIcon />}
                sx={{
                  borderRadius: COLORS.radiusSm,
                  textTransform: 'none',
                  bgcolor: COLORS.primary,
                  boxShadow: '0 4px 12px rgba(79, 70, 229, 0.2)',
                  fontWeight: 700,
                  fontSize: '0.85rem',
                  px: 2.5,
                  py: 1,
                  transition: 'all 0.2s',
                  '&:hover': { bgcolor: COLORS.primaryHover, boxShadow: '0 6px 16px rgba(79, 70, 229, 0.3)' }
                }}
              >
                Add Account
              </Button>
            </>
          )}
        </Box>
      </Box>

      {/* Segmented Control Tabs */}
      <Tabs
        value={activeTab}
        onChange={handleTabChange}
        variant="scrollable"
        scrollButtons="auto"
        sx={{
          bgcolor: '#ECEFF1',
          p: 0.5,
          borderRadius: '12px',
          minHeight: 44,
          alignSelf: 'flex-start',
          maxWidth: '100%',
          '& .MuiTabs-indicator': {
            bgcolor: '#FFF',
            borderRadius: '8px',
            height: '100%',
            bottom: 0,
            boxShadow: '0 1px 3px rgba(15, 23, 42, 0.08)',
            zIndex: 0
          },
          '& .MuiTabs-flexContainer': {
            position: 'relative',
            zIndex: 1
          },
          '& .MuiTab-root': {
            textTransform: 'none',
            fontWeight: 700,
            fontSize: '0.85rem',
            minHeight: 36,
            py: 1.25,
            px: 3,
            borderRadius: '8px',
            color: COLORS.muted,
            transition: 'all 0.2s',
            zIndex: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 1.25,
            minWidth: 'auto',
            '&.Mui-selected': {
              color: '#0F172A !important',
            },
            '&:hover:not(.Mui-selected)': {
              color: '#0F172A',
            }
          }
        }}
      >
        <Tab label="Overview" icon={<ActivityIcon sx={{ fontSize: 18 }} />} iconPosition="start" />
        <Tab label="Bank Accounts" icon={<BankIcon sx={{ fontSize: 18 }} />} iconPosition="start" />
        <Tab label="Cash Accounts" icon={<CashIcon sx={{ fontSize: 18 }} />} iconPosition="start" />
        <Tab label="Wallet Accounts" icon={<WalletIcon sx={{ fontSize: 18 }} />} iconPosition="start" />
        <Tab label="Settlement Accounts" icon={<SettlementIcon sx={{ fontSize: 18 }} />} iconPosition="start" />
        <Tab label="Activity Log" icon={<ActivityIcon sx={{ fontSize: 18 }} />} iconPosition="start" />
      </Tabs>

      {/* Main Tab Views */}
      <Box sx={{ flexGrow: 1 }}>
        {activeTab === 0 && (
          <OverviewTab 
            data={dashboardData} 
            loading={loading} 
            onNavigate={setActiveTab} 
            canViewAmounts={canViewAmounts}
          />
        )}
        
        {activeTab === 1 && (
          <AccountsListTab 
            accounts={getFilteredAccounts('bank')} 
            loading={loading} 
            onEdit={handleOpenEdit} 
            onArchive={handleArchive}
            onAdd={() => handleOpenAdd('bank')}
            type="bank"
            canViewAmounts={canViewAmounts}
            canEdit={canEdit}
            canDelete={canDelete}
          />
        )}

        {activeTab === 2 && (
          <AccountsListTab 
            accounts={getFilteredAccounts('cash')} 
            loading={loading} 
            onEdit={handleOpenEdit} 
            onArchive={handleArchive}
            onAdd={() => handleOpenAdd('cash')}
            type="cash"
            canViewAmounts={canViewAmounts}
            canEdit={canEdit}
            canDelete={canDelete}
          />
        )}

        {activeTab === 3 && (
          <AccountsListTab 
            accounts={getFilteredAccounts('wallet')} 
            loading={loading} 
            onEdit={handleOpenEdit} 
            onArchive={handleArchive}
            onAdd={() => handleOpenAdd('wallet')}
            type="wallet"
            canViewAmounts={canViewAmounts}
            canEdit={canEdit}
            canDelete={canDelete}
          />
        )}

        {activeTab === 4 && (
          <AccountsListTab 
            accounts={getFilteredAccounts('settlement')} 
            loading={loading} 
            onEdit={handleOpenEdit} 
            onArchive={handleArchive}
            onAdd={() => handleOpenAdd('settlement')}
            type="settlement"
            canViewAmounts={canViewAmounts}
            canEdit={canEdit}
            canDelete={canDelete}
          />
        )}

        {activeTab === 5 && (
          <ActivityLogsTab
            logs={logs}
            loading={loading}
          />
        )}
      </Box>

      {/* ─── Modern Dialog ─── */}
      <Dialog
        open={openDrawer}
        onClose={() => setOpenDrawer(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: '20px',
            overflow: 'hidden',
            boxShadow: '0 32px 64px -12px rgba(79,70,229,0.18), 0 0 0 1px rgba(79,70,229,0.08)',
            p: 0,
            maxHeight: '90vh',
            display: 'flex',
            flexDirection: 'column',
          }
        }}
        BackdropProps={{ sx: { backdropFilter: 'blur(4px)', bgcolor: 'rgba(15,23,42,0.4)' } }}
      >
        {/* Gradient Header */}
        <Box sx={{
          background: 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)',
          px: 3, py: 2.5,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <Box>
            <Typography variant="h6" fontWeight="800" sx={{ color: '#fff', letterSpacing: '-0.02em', lineHeight: 1.2 }}>
              {editingAccount ? `Edit Account` : `New Financial Account`}
            </Typography>
            {!editingAccount && (
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', fontWeight: 500 }}>
                Add a bank, cash, or digital wallet account
              </Typography>
            )}
          </Box>
          <IconButton onClick={() => setOpenDrawer(false)} size="small" sx={{ color: 'rgba(255,255,255,0.8)', '&:hover': { bgcolor: 'rgba(255,255,255,0.15)' } }}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
          <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 0, p: 0, flex: 1, overflowY: 'auto' }}>
            {error && (
              <Alert severity="error" sx={{ mx: 3, mt: 2, borderRadius: '10px', fontSize: '0.82rem' }}>{error}</Alert>
            )}

            <Box sx={{ px: 3, pt: 2.5, pb: 2, display: 'flex', flexDirection: 'column', gap: 2.5 }}>

            {drawerType === 'group' ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Typography variant="caption" fontWeight="700" sx={{ color: COLORS.muted, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.68rem' }}>Group Details</Typography>
                <TextField
                  label="Group Name"
                  variant="outlined"
                  fullWidth
                  required
                  value={formFields.group_name}
                  onChange={(e) => setFormFields({ ...formFields, group_name: e.target.value })}
                  sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.9rem' }, '& .MuiOutlinedInput-notchedOutline': { borderColor: COLORS.border } }}
                />
              </Box>
            ) : (
              <>
                {/* Account Class Selector */}
                {!editingAccount && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <Typography variant="caption" fontWeight="700" sx={{ color: COLORS.muted, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.68rem' }}>
                      Account Class
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, p: '3px', bgcolor: '#F1F5F9', borderRadius: '10px' }}>
                      {CLASS_OPTIONS.map(opt => {
                        const selected = drawerType === opt.key;
                        return (
                          <Box
                            key={opt.key}
                            onClick={() => handleClassChange(opt.key)}
                            sx={{
                              flex: 1,
                              py: 0.85,
                              px: 1,
                              borderRadius: '8px',
                              bgcolor: selected ? '#fff' : 'transparent',
                              boxShadow: selected ? '0 1px 4px rgba(79,70,229,0.15)' : 'none',
                              cursor: 'pointer',
                              transition: 'all 0.16s ease',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              gap: 0.6,
                            }}
                          >
                            <Box sx={{ color: selected ? COLORS.primary : COLORS.muted, display: 'flex', alignItems: 'center', transition: 'color 0.16s' }}>
                              {React.cloneElement(opt.icon, { sx: { fontSize: 15 } })}
                            </Box>
                            <Typography sx={{ fontSize: '0.78rem', fontWeight: selected ? 700 : 500, color: selected ? COLORS.primary : COLORS.muted, whiteSpace: 'nowrap', transition: 'color 0.16s' }}>
                              {opt.label}
                            </Typography>
                          </Box>
                        );
                      })}
                    </Box>
                  </Box>
                )}

                {/* General Details */}
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="caption" fontWeight="700" sx={{ color: COLORS.muted, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.68rem' }}>
                      Account Details
                    </Typography>
                    {drawerType !== 'cash' && (
                      <Tooltip title="Inactive accounts are hidden across all pickers and forms but retained for historical records." arrow placement="top">
                        <Box sx={{ display: 'flex', gap: 0.5, p: '2.5px', bgcolor: '#F1F5F9', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
                          {[
                            { value: 'active',   label: 'Active',   color: '#10B981' },
                            { value: 'inactive', label: 'Inactive', color: '#94A3B8' },
                          ].map(opt => {
                            const selected = formFields.status === opt.value;
                            return (
                              <Box
                                key={opt.value}
                                onClick={() => setFormFields({ ...formFields, status: opt.value })}
                                sx={{
                                  px: 1.5,
                                  py: 0.5,
                                  borderRadius: '6px',
                                  bgcolor: selected ? '#fff' : 'transparent',
                                  boxShadow: selected ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 0.75,
                                }}
                              >
                                <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: selected ? opt.color : '#CBD5E1', transition: 'background 0.15s' }} />
                                <Typography sx={{ fontSize: '0.72rem', fontWeight: selected ? 700 : 500, color: selected ? COLORS.text : COLORS.muted, lineHeight: 1 }}>
                                  {opt.label}
                                </Typography>
                              </Box>
                            );
                          })}
                        </Box>
                      </Tooltip>
                    )}
                  </Box>
                  <Grid container spacing={1.5}>

                    {/* Row 1: Name + Type */}
                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Account Name"
                        variant="outlined"
                        fullWidth
                        required
                        value={formFields.account_name}
                        onChange={(e) => setFormFields({ ...formFields, account_name: e.target.value })}
                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem' }, '& .MuiInputLabel-root': { fontSize: '0.88rem' } }}
                      />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <TextField
                        label="Account Type"
                        variant="outlined"
                        fullWidth
                        placeholder={drawerType === 'bank' ? 'Current, Savings…' : 'Petty Cash…'}
                        value={formFields.account_type}
                        onChange={(e) => setFormFields({ ...formFields, account_type: e.target.value })}
                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem' }, '& .MuiInputLabel-root': { fontSize: '0.88rem' } }}
                      />
                    </Grid>

                    {/* Wallet Provider — wallet only */}
                    {drawerType === 'wallet' && (
                      <Grid item xs={12} sm={6}>
                        <TextField
                          label="Wallet Provider"
                          variant="outlined"
                          fullWidth
                          placeholder="Paytm, PhonePe, Razorpay…"
                          value={formFields.provider}
                          onChange={(e) => setFormFields({ ...formFields, provider: e.target.value })}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem' }, '& .MuiInputLabel-root': { fontSize: '0.88rem' } }}
                        />
                      </Grid>
                    )}

                    {/* Linked Bank Account — wallet only */}
                    {drawerType === 'wallet' && (
                      <Grid item xs={12} sm={6}>
                        <TextField
                          select
                          label="Linked Bank Account"
                          variant="outlined"
                          fullWidth
                          value={formFields.linked_account}
                          onChange={(e) => setFormFields({ ...formFields, linked_account: e.target.value })}
                          SelectProps={{ displayEmpty: true }}
                          InputLabelProps={{ shrink: true }}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem' }, '& .MuiInputLabel-root': { fontSize: '0.88rem' } }}
                        >
                          <MenuItem value=""><em style={{ fontStyle: 'normal', color: '#94A3B8' }}>None — no linked bank</em></MenuItem>
                          {accounts.filter(a => a.account_class === 'bank').map(a => (
                            <MenuItem key={a.id} value={a.id}>{a.account_name}</MenuItem>
                          ))}
                        </TextField>
                      </Grid>
                    )}

                  </Grid>
                </Box>

                {/* Subclass Details */}
                {drawerType === 'bank' && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    <Typography variant="caption" fontWeight="700" sx={{ color: COLORS.muted, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.68rem' }}>
                      Bank Information
                    </Typography>
                    <Grid container spacing={1.5}>
                      <Grid item xs={12} sm={6}>
                        <TextField label="Bank Name" variant="outlined" fullWidth value={formFields.bank_name}
                          onChange={(e) => setFormFields({ ...formFields, bank_name: e.target.value })}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem' }, '& .MuiInputLabel-root': { fontSize: '0.88rem' } }} />
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <TextField label="Account Number" variant="outlined" fullWidth value={formFields.account_number}
                          onChange={(e) => setFormFields({ ...formFields, account_number: e.target.value })}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem' }, '& .MuiInputLabel-root': { fontSize: '0.88rem' } }} />
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <TextField label="IFSC Code" variant="outlined" fullWidth value={formFields.ifsc}
                          onChange={(e) => setFormFields({ ...formFields, ifsc: e.target.value })}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem' }, '& .MuiInputLabel-root': { fontSize: '0.88rem' } }} />
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <TextField label="Branch" variant="outlined" fullWidth value={formFields.branch}
                          onChange={(e) => setFormFields({ ...formFields, branch: e.target.value })}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem' }, '& .MuiInputLabel-root': { fontSize: '0.88rem' } }} />
                      </Grid>
                    </Grid>
                  </Box>
                )}



                {drawerType === 'settlement' && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <Typography variant="subtitle2" fontWeight="800" color="text.secondary" sx={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.75rem', borderBottom: '1px solid #F1F5F9', pb: 1 }}>
                      Settlement Gateway Configuration
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={12} sm={6}>
                        <TextField
                          label="Gateway Provider"
                          variant="outlined"
                          fullWidth
                          placeholder="Razorpay, Stripe, Paytm, etc."
                          value={formFields.provider}
                          onChange={(e) => setFormFields({ ...formFields, provider: e.target.value })}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '10px' } }}
                        />
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <TextField
                          label="Settlement Cycle / Frequency"
                          variant="outlined"
                          fullWidth
                          placeholder="T+2 Days, Weekly, etc."
                          value={formFields.settlement_frequency}
                          onChange={(e) => setFormFields({ ...formFields, settlement_frequency: e.target.value })}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '10px' } }}
                        />
                      </Grid>
                      <Grid item xs={12}>
                        <TextField
                          select
                          label="Destination Bank Account"
                          variant="outlined"
                          fullWidth
                          value={formFields.linked_bank_account}
                          onChange={(e) => setFormFields({ ...formFields, linked_bank_account: e.target.value })}
                          SelectProps={{ displayEmpty: true }}
                          InputLabelProps={{ shrink: true }}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '10px' } }}
                        >
                          <MenuItem value="">None</MenuItem>
                          {accounts.filter(a => a.account_class === 'bank').map(a => (
                            <MenuItem key={a.id} value={a.id}>{a.account_name}</MenuItem>
                          ))}
                        </TextField>
                      </Grid>
                    </Grid>
                  </Box>
                )}

                {/* Opening Balance — hidden for cash */}
                {drawerType !== 'cash' && (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    <Typography variant="caption" fontWeight="700" sx={{ color: COLORS.muted, textTransform: 'uppercase', letterSpacing: '0.06em', fontSize: '0.68rem' }}>
                      Opening Balance
                    </Typography>
                    <Grid container spacing={1.5}>
                      <Grid item xs={12} sm={6}>
                        <TextField label="Opening Balance" variant="outlined" fullWidth type="number" required
                          disabled={!!editingAccount}
                          value={formFields.balance}
                          onChange={(e) => setFormFields({ ...formFields, balance: e.target.value })}
                          sx={{
                            '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem' },
                            '& .MuiInputLabel-root': { fontSize: '0.88rem' },
                            '& input[type=number]': { MozAppearance: 'textfield' },
                            '& input[type=number]::-webkit-outer-spin-button': { WebkitAppearance: 'none', margin: 0 },
                            '& input[type=number]::-webkit-inner-spin-button': { WebkitAppearance: 'none', margin: 0 }
                          }} />
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <TextField label="Currency" variant="outlined" fullWidth disabled value={formFields.currency}
                          sx={{ '& .MuiOutlinedInput-root': { borderRadius: '12px', fontSize: '0.88rem', bgcolor: '#F8FAFC' }, '& .MuiInputLabel-root': { fontSize: '0.88rem' } }} />
                      </Grid>
                    </Grid>
                  </Box>
                )}
              </>
            )}

            </Box>
          </DialogContent>
          <DialogActions sx={{ px: 3, py: 2.5, gap: 1.5, borderTop: '1px solid #F1F5F9', bgcolor: '#FAFBFF' }}>
            <Button
              variant="outlined"
              onClick={() => setOpenDrawer(false)}
              sx={{
                borderRadius: '10px',
                textTransform: 'none',
                borderColor: COLORS.border,
                color: COLORS.muted,
                fontWeight: 600,
                fontSize: '0.875rem',
                px: 3,
                py: 1,
                '&:hover': { bgcolor: '#F1F5F9', borderColor: '#CBD5E1', color: COLORS.text }
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="contained"
              sx={{
                borderRadius: '10px',
                textTransform: 'none',
                background: 'linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)',
                boxShadow: '0 4px 14px rgba(79,70,229,0.35)',
                fontWeight: 700,
                fontSize: '0.875rem',
                px: 4,
                py: 1,
                '&:hover': { background: 'linear-gradient(135deg, #4338CA 0%, #6D28D9 100%)', boxShadow: '0 6px 20px rgba(79,70,229,0.4)' }
              }}
            >
              {drawerType === 'group' ? 'Save Group' : 'Create Account'}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// TAB components
// ---------------------------------------------------------------------------

function OverviewTab({ data, loading, onNavigate, canViewAmounts }) {
  if (loading && !data) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
        <CircularProgress size={36} sx={{ color: COLORS.primary }} />
      </Box>
    );
  }

  if (!data) {
    return (
      <Alert severity="info" sx={{ borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, bgcolor: '#F8FAFC' }}>
        No dashboard data available. Create some accounts to get started!
      </Alert>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3.5 }}>
      {/* KPI Cards Grid */}
      <Grid container spacing={2.5}>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Total Available Funds"
            value={canViewAmounts ? fmt(data.available_funds) : '₹ ••••'}
            subtitle="Liquidity (Bank + Cash + Wallets)"
            icon={<BankIcon sx={{ color: COLORS.primary, fontSize: 20 }} />}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Bank Balances"
            value={canViewAmounts ? fmt(data.total_balance - data.cash_in_hand - data.wallet_balance - data.settlement_balance) : '₹ ••••'}
            subtitle="Corporate institution vaults"
            icon={<BankIcon sx={{ color: '#059669', fontSize: 20 }} />}
            onClick={() => onNavigate(1)}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Cash In Hand"
            value={canViewAmounts ? fmt(data.cash_in_hand) : '₹ ••••'}
            subtitle="Petty cash safe locations"
            icon={<CashIcon sx={{ color: COLORS.warning, fontSize: 20 }} />}
            onClick={() => onNavigate(2)}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <KpiCard
            title="Wallet & Gateways"
            value={canViewAmounts ? fmt(data.wallet_balance + data.settlement_balance) : '₹ ••••'}
            subtitle="Digital balances & gateway holds"
            icon={<WalletIcon sx={{ color: '#8B5CF6', fontSize: 20 }} />}
            onClick={() => onNavigate(3)}
          />
        </Grid>
      </Grid>

      {/* Visual Balance Distribution */}
      <Paper 
        sx={{ 
          p: 3.5, 
          borderRadius: COLORS.radius, 
          border: `1px solid ${COLORS.border}`, 
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -2px rgba(0, 0, 0, 0.02)',
          bgcolor: COLORS.card 
        }}
      >
        <Typography variant="subtitle1" fontWeight="800" mb={1} sx={{ color: COLORS.text, letterSpacing: '-0.02em', fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
          Portfolio Distribution
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3.5, fontWeight: 500 }}>
          Overview of asset classification across all linked accounts.
        </Typography>
        <Box sx={{ display: 'flex', height: 12, borderRadius: '6px', overflow: 'hidden', mb: 3.5, bgcolor: '#F1F5F9' }}>
          {data.type_breakdown.map((item, idx) => {
            const pct = data.total_balance > 0 ? (item.balance / data.total_balance) * 100 : 0;
            if (pct <= 0) return null;
            const colors = [COLORS.primary, '#10B981', COLORS.warning, '#8B5CF6'];
            return (
              <Tooltip key={item.class} title={`${item.label}: ${pct.toFixed(1)}%`}>
                <Box sx={{ width: `${pct}%`, bgcolor: colors[idx % colors.length], transition: 'all 0.4s' }} />
              </Tooltip>
            );
          })}
        </Box>
        <Grid container spacing={3.5}>
          {data.type_breakdown.map((item, idx) => {
            const colors = [COLORS.primary, '#10B981', COLORS.warning, '#8B5CF6'];
            return (
              <Grid item xs={6} sm={3} key={item.class}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                  <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: colors[idx % colors.length], mt: 0.75 }} />
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 700, textTransform: 'uppercase', fontSize: '0.65rem', letterSpacing: '0.05em' }}>
                      {item.label}
                    </Typography>
                    <Typography variant="body2" fontWeight="800" sx={{ color: COLORS.text, mt: 0.25 }}>
                      {canViewAmounts ? fmt(item.balance) : '₹ ••••'}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.25, fontWeight: 500 }}>
                      {item.count} active accounts
                    </Typography>
                  </Box>
                </Box>
              </Grid>
            );
          })}
        </Grid>
      </Paper>

      {/* Splits (Top Accounts & Recent Audits) */}
      <Grid container spacing={3.5}>
        <Grid item xs={12} md={6}>
          <Paper 
            sx={{ 
              p: 3.5, 
              borderRadius: COLORS.radius, 
              border: `1px solid ${COLORS.border}`, 
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -2px rgba(0, 0, 0, 0.02)',
              display: 'flex', 
              flexDirection: 'column', 
              height: '100%',
              bgcolor: COLORS.card 
            }}
          >
            <Typography variant="subtitle1" fontWeight="800" mb={1} sx={{ color: COLORS.text, letterSpacing: '-0.02em', fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
              Top Accounts by Balance
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5, fontWeight: 500 }}>
              Highest balance asset accounts in the ecosystem.
            </Typography>
            <TableContainer sx={{ flexGrow: 1 }}>
              <Table size="small">
                <TableBody>
                  {data.largest_accounts.map(acc => (
                    <TableRow key={acc.id} hover sx={{ '&:last-child td': { border: 'none' } }}>
                      <TableCell sx={{ borderBottom: `1px solid ${COLORS.border}`, py: 1.75, pl: 0 }}>
                        <Typography variant="body2" fontWeight="800" sx={{ color: COLORS.text }}>{acc.account_name}</Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>{acc.account_type}</Typography>
                      </TableCell>
                      <TableCell align="right" sx={{ borderBottom: `1px solid ${COLORS.border}`, py: 1.75, pr: 0 }}>
                        <Typography variant="body2" fontWeight="800" sx={{ color: COLORS.text }}>
                          {canViewAmounts ? fmt(acc.balance) : '₹ ••••'}
                        </Typography>
                        <Chip 
                          size="small" 
                          label={acc.status.toUpperCase()} 
                          color={acc.status === 'active' ? 'success' : 'default'} 
                          variant="outlined" 
                          sx={{ height: 18, fontSize: '0.6rem', fontWeight: 700, mt: 0.5 }} 
                        />
                      </TableCell>
                    </TableRow>
                  ))}
                  {data.largest_accounts.length === 0 && (
                    <TableRow>
                      <TableCell align="center" sx={{ border: 'none', py: 4, color: COLORS.muted }}>
                        No accounts created yet.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>
        
        <Grid item xs={12} md={6}>
          <Paper 
            sx={{ 
              p: 3.5, 
              borderRadius: COLORS.radius, 
              border: `1px solid ${COLORS.border}`, 
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -2px rgba(0, 0, 0, 0.02)',
              display: 'flex', 
              flexDirection: 'column', 
              height: '100%',
              bgcolor: COLORS.card 
            }}
          >
            <Typography variant="subtitle1" fontWeight="800" mb={1} sx={{ color: COLORS.text, letterSpacing: '-0.02em', fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
              Recent Audit Logs
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2.5, fontWeight: 500 }}>
              Recent modifications and account operations.
            </Typography>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, flexGrow: 1 }}>
              {data.recent_activity.map(act => (
                <Box key={act.id} sx={{ display: 'flex', gap: 2, pb: 2, borderBottom: `1px solid #F1F5F9`, '&:last-child': { border: 'none', pb: 0 } }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: '50%', bgcolor: '#F1F5F9', color: COLORS.muted, flexShrink: 0, mt: 0.25 }}>
                    <ActivityIcon sx={{ fontSize: 14 }} />
                  </Box>
                  <Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                      <Typography variant="body2" fontWeight="800" sx={{ color: COLORS.text }}>{act.account_name}</Typography>
                      <Chip 
                        label={act.action.toUpperCase()} 
                        size="small" 
                        color={act.action === 'created' ? 'success' : act.action === 'updated' ? 'primary' : 'default'}
                        sx={{ height: 16, fontSize: '0.55rem', fontWeight: 800 }} 
                      />
                    </Box>
                    <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5, fontWeight: 500 }}>{act.details}</Typography>
                    <Typography variant="caption" color={COLORS.muted} sx={{ fontSize: '0.7rem', display: 'block', mt: 0.25 }}>By {act.performed_by} at {new Date(act.created_at).toLocaleString()}</Typography>
                  </Box>
                </Box>
              ))}
              {data.recent_activity.length === 0 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4, color: COLORS.muted }}>
                  No recent activity recorded.
                </Box>
              )}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

function KpiCard({ title, value, subtitle, icon, onClick }) {
  return (
    <Card 
      onClick={onClick}
      sx={{ 
        borderRadius: COLORS.radius, 
        border: `1px solid ${COLORS.border}`, 
        boxShadow: 'none',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        position: 'relative',
        overflow: 'hidden',
        bgcolor: COLORS.card,
        '&:hover': onClick ? { 
          transform: 'translateY(-2px)',
          boxShadow: '0 12px 20px -10px rgba(0, 0, 0, 0.04)',
          borderColor: COLORS.primary 
        } : {}
      }}
    >
      <CardContent sx={{ p: '24px !important' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="body2" color="text.secondary" fontWeight="700" sx={{ letterSpacing: '0.01em', textTransform: 'uppercase', fontSize: '0.725rem' }}>
            {title}
          </Typography>
          <Box sx={{ bgcolor: COLORS.primaryLight, p: 1.25, borderRadius: '10px', display: 'flex', alignItems: 'center' }}>
            {icon}
          </Box>
        </Box>
        <Typography variant="h5" fontWeight="800" mb={0.5} sx={{ color: COLORS.text, letterSpacing: '-0.03em', fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
          {value}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, display: 'block', mt: 0.75 }}>
          {subtitle}
        </Typography>
      </CardContent>
    </Card>
  );
}

function AccountsListTab({ accounts, loading, onEdit, onArchive, onAdd, type, canViewAmounts, canEdit, canDelete }) {
  if (loading && accounts.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
        <CircularProgress size={36} sx={{ color: COLORS.primary }} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3.5 }}>
      {/* Header controls inside tab */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="subtitle1" fontWeight="800" sx={{ color: COLORS.text, fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
          Registered {type.toUpperCase()} Accounts ({accounts.length})
        </Typography>
        {canEdit && (
          <Button 
            variant="outlined" 
            size="small" 
            startIcon={<AddIcon />}
            onClick={onAdd}
            sx={{ 
              borderRadius: '8px', 
              textTransform: 'none', 
              borderColor: COLORS.border, 
              color: COLORS.text,
              fontWeight: 700,
              fontSize: '0.8rem',
              px: 2,
              py: 0.75,
              '&:hover': { bgcolor: '#F1F5F9' }
            }}
          >
            Add {type.toUpperCase()} Account
          </Button>
        )}
      </Box>

      {/* Cards layout */}
      <Grid container spacing={3}>
        {accounts.map(acc => (
          <Grid item xs={12} sm={6} md={4} key={acc.id}>
            <Paper 
              sx={{ 
                p: 3.5, 
                borderRadius: COLORS.radius, 
                border: `1px solid ${COLORS.border}`, 
                borderTop: `4px solid ${
                  type === 'bank' ? COLORS.primary : 
                  type === 'cash' ? COLORS.warning : 
                  type === 'wallet' ? '#8B5CF6' : COLORS.success
                }`,
                bgcolor: COLORS.card, 
                boxShadow: 'none', 
                position: 'relative',
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                '&:hover': { 
                  transform: 'translateY(-3px)',
                  boxShadow: '0 12px 20px -8px rgba(0, 0, 0, 0.05)',
                }
              }}
            >
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                  <Box sx={{ bgcolor: COLORS.primaryLight, p: 1, borderRadius: '8px', display: 'flex' }}>
                    {type === 'bank' && <BankIcon sx={{ color: COLORS.primary, fontSize: 18 }} />}
                    {type === 'cash' && <CashIcon sx={{ color: COLORS.warning, fontSize: 18 }} />}
                    {type === 'wallet' && <WalletIcon sx={{ color: '#8B5CF6', fontSize: 18 }} />}
                    {type === 'settlement' && <SettlementIcon sx={{ color: '#10B981', fontSize: 18 }} />}
                  </Box>
                  <Box>
                    <Typography variant="body2" fontWeight="800" sx={{ color: COLORS.text }}>
                      {acc.account_name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                      {acc.account_type}
                    </Typography>
                  </Box>
                </Box>
                <Chip 
                  label={acc.status.toUpperCase()} 
                  size="small" 
                  color={acc.status === 'active' ? 'success' : 'default'} 
                  variant="outlined"
                  sx={{ height: 20, fontSize: '0.625rem', fontWeight: 800 }} 
                />
              </Box>

              {/* Sub-details layout */}
              <Box sx={{ minHeight: 70, display: 'flex', flexDirection: 'column', gap: 0.75, mb: 2.5 }}>
                {type === 'bank' && (
                  <>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      Bank: <strong style={{ color: COLORS.text }}>{acc.bank_detail?.bank_name || 'N/A'}</strong>
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      A/C No: <strong style={{ color: COLORS.text }}>{acc.bank_detail?.account_number || '••••'}</strong>
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      IFSC: <strong style={{ color: COLORS.text }}>{acc.bank_detail?.ifsc || 'N/A'}</strong>
                    </Typography>
                  </>
                )}

                {type === 'cash' && (
                  <>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      Custodian: <strong style={{ color: COLORS.text }}>{acc.cash_detail?.custodian || 'N/A'}</strong>
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      Location: <strong style={{ color: COLORS.text }}>{acc.cash_detail?.location || 'N/A'}</strong>
                    </Typography>
                  </>
                )}

                {type === 'wallet' && (
                  <>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      Provider: <strong style={{ color: COLORS.text }}>{acc.wallet_detail?.provider || 'N/A'}</strong>
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      Linked A/C: <strong style={{ color: COLORS.text }}>{acc.wallet_detail?.linked_account_name || 'N/A'}</strong>
                    </Typography>
                  </>
                )}

                {type === 'settlement' && (
                  <>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      Provider: <strong style={{ color: COLORS.text }}>{acc.settlement_detail?.provider || 'N/A'}</strong>
                    </Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
                      Cycle: <strong style={{ color: COLORS.text }}>{acc.settlement_detail?.settlement_frequency || 'Daily'}</strong>
                    </Typography>
                  </>
                )}
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>Available Balance</Typography>
                  <Typography variant="h6" fontWeight="800" sx={{ color: COLORS.text, letterSpacing: '-0.02em', mt: 0.25 }}>
                    {canViewAmounts ? fmt(acc.balance) : '₹ ••••'}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  {canEdit && (
                    <IconButton size="small" onClick={() => onEdit(acc)} sx={{ border: '1px solid #F1F5F9', borderRadius: '8px' }}>
                      <EditIcon sx={{ fontSize: 16, color: COLORS.muted }} />
                    </IconButton>
                  )}
                  {canDelete && (
                    <IconButton size="small" color="error" onClick={() => onArchive(acc.id)} sx={{ border: '1px solid #FEE2E2', borderRadius: '8px' }}>
                      <DeleteIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  )}
                </Box>
              </Box>
            </Paper>
          </Grid>
        ))}

        {accounts.length === 0 && (
          <Grid item xs={12}>
            <Paper sx={{ py: 8, textAlign: 'center', border: `1px dashed ${COLORS.border}`, borderRadius: COLORS.radius, boxShadow: 'none', bgcolor: '#FFF' }}>
              <WarningIcon sx={{ fontSize: 44, color: COLORS.muted, mb: 1.5 }} />
              <Typography variant="body1" fontWeight="800" color="text.primary" mb={0.5}>
                No {type.toUpperCase()} Accounts Configured
              </Typography>
              <Typography variant="body2" color="text.secondary" display="block" mb={3.5} sx={{ fontWeight: 500 }}>
                Link your first operational financial account to start managing cashflow.
              </Typography>
              {canEdit && (
                <Button 
                  variant="outlined" 
                  size="small" 
                  onClick={onAdd}
                  sx={{ 
                    borderRadius: '8px', 
                    textTransform: 'none',
                    fontWeight: 700,
                    fontSize: '0.8rem',
                    px: 3,
                    py: 1,
                    borderColor: COLORS.border,
                    color: COLORS.text,
                    '&:hover': { bgcolor: '#F1F5F9' }
                  }}
                >
                  Add Account
                </Button>
              )}
            </Paper>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}

function GroupsTab({ groups, loading, onArchive, onAdd, canDelete }) {
  if (loading && groups.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
        <CircularProgress size={36} sx={{ color: COLORS.primary }} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3.5 }}>
      {/* Header controls inside tab */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="subtitle1" fontWeight="800" sx={{ color: COLORS.text, fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
          Account Groups ({groups.length})
        </Typography>
        <Button 
          variant="outlined" 
          size="small" 
          startIcon={<AddIcon />}
          onClick={onAdd}
          sx={{ 
            borderRadius: '8px', 
            textTransform: 'none', 
            borderColor: COLORS.border, 
            color: COLORS.text,
            fontWeight: 700,
            fontSize: '0.8rem',
            px: 2,
            py: 0.75,
            '&:hover': { bgcolor: '#F1F5F9' }
          }}
        >
          Add Custom Group
        </Button>
      </Box>

      <TableContainer component={Paper} sx={{ borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none', overflow: 'hidden' }}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: '#F8FAFC' }}>
              <TableCell sx={{ fontWeight: 800, color: COLORS.text, py: 2 }}>Group Name</TableCell>
              <TableCell sx={{ fontWeight: 800, color: COLORS.text }}>Type</TableCell>
              <TableCell sx={{ fontWeight: 800, color: COLORS.text }}>Created At</TableCell>
              <TableCell sx={{ fontWeight: 800, color: COLORS.text }} align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {groups.map(g => (
              <TableRow key={g.id} hover>
                <TableCell sx={{ fontWeight: 800, color: COLORS.text, py: 2 }}>{g.name}</TableCell>
                <TableCell>
                  <Chip 
                    label={g.is_system ? 'SYSTEM' : 'CUSTOM'} 
                    size="small" 
                    color={g.is_system ? 'primary' : 'default'} 
                    sx={{ height: 20, fontSize: '0.625rem', fontWeight: 800, borderRadius: '4px' }}
                  />
                </TableCell>
                <TableCell sx={{ fontWeight: 500, color: COLORS.muted }}>{new Date(g.created_at).toLocaleString('en-IN')}</TableCell>
                <TableCell align="right">
                  {!g.is_system && canDelete && (
                    <IconButton size="small" color="error" onClick={() => onArchive(g.id)} sx={{ border: '1px solid #FEE2E2', borderRadius: '8px' }}>
                      <DeleteIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {groups.length === 0 && (
              <TableRow>
                <TableCell colSpan={4} align="center" sx={{ py: 4, color: COLORS.muted }}>
                  No groups configured.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

function ActivityLogsTab({ logs, loading }) {
  if (loading && logs.length === 0) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 10 }}>
        <CircularProgress size={36} sx={{ color: COLORS.primary }} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3.5 }}>
      <Typography variant="subtitle1" fontWeight="800" sx={{ color: COLORS.text, fontFamily: '"Plus Jakarta Sans", sans-serif' }}>
        Audit & Modification Logs
      </Typography>

      <TableContainer component={Paper} sx={{ borderRadius: COLORS.radius, border: `1px solid ${COLORS.border}`, boxShadow: 'none', overflow: 'hidden' }}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: '#F8FAFC' }}>
              <TableCell sx={{ fontWeight: 800, color: COLORS.text, py: 2 }}>Date & Time</TableCell>
              <TableCell sx={{ fontWeight: 800, color: COLORS.text }}>Account Name</TableCell>
              <TableCell sx={{ fontWeight: 800, color: COLORS.text }}>Action</TableCell>
              <TableCell sx={{ fontWeight: 800, color: COLORS.text }}>Details</TableCell>
              <TableCell sx={{ fontWeight: 800, color: COLORS.text }}>Performed By</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {logs.map(log => (
              <TableRow key={log.id} hover>
                <TableCell sx={{ py: 2, fontWeight: 500, color: COLORS.muted }}>{new Date(log.created_at).toLocaleString('en-IN')}</TableCell>
                <TableCell sx={{ fontWeight: 800, color: COLORS.text }}>{log.account_name}</TableCell>
                <TableCell>
                  <Chip 
                    label={log.action.toUpperCase()} 
                    size="small" 
                    color={
                      log.action === 'created' ? 'success' : 
                      log.action === 'updated' ? 'primary' : 
                      log.action === 'archived' ? 'error' : 'default'
                    }
                    sx={{ height: 18, fontSize: '0.575rem', fontWeight: 800, borderRadius: '4px' }}
                  />
                </TableCell>
                <TableCell sx={{ fontWeight: 500, color: COLORS.text }}>{log.details}</TableCell>
                <TableCell sx={{ fontWeight: 700, color: COLORS.text }}>{log.performed_by || 'System'}</TableCell>
              </TableRow>
            ))}

            {logs.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} align="center" sx={{ py: 6, color: COLORS.muted, fontWeight: 500 }}>
                  No activities logged yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
