import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import {
  Box, Typography, Button, Chip, TextField, MenuItem, Select, FormControl, InputLabel,
  Drawer, IconButton, Divider, CircularProgress, Alert, Tabs, Tab, Tooltip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper,
  Dialog, DialogTitle, DialogContent, DialogActions, LinearProgress, Menu,
  Autocomplete, Avatar, Stack, Collapse,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import InventoryIcon from '@mui/icons-material/Inventory';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import DeleteSweepIcon from '@mui/icons-material/DeleteSweep';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import FileUploadOutlinedIcon from '@mui/icons-material/FileUploadOutlined';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import FilterListIcon from '@mui/icons-material/FilterList';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import VisibilityIcon from '@mui/icons-material/Visibility';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import AttachFileIcon from '@mui/icons-material/AttachFile';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CalendarTodayIcon from '@mui/icons-material/CalendarToday';
import HistoryIcon from '@mui/icons-material/History';
import AssignmentIcon from '@mui/icons-material/Assignment';
import ReceiptLongIcon from '@mui/icons-material/ReceiptLong';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import BusinessIcon from '@mui/icons-material/Business';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
  ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar, Label,
} from 'recharts';
import { apiClient } from '../../apiClient';

const API = '/api/accounting';

const CATEGORY_LABELS = {
  computer: 'Computer & IT',
  furniture: 'Furniture & Fixtures',
  vehicle: 'Vehicle',
  machinery: 'Machinery & Equipment',
  building: 'Building & Property',
  other: 'Other',
};

const STATUS_COLORS = {
  active: { bg: '#F0FDF4', color: '#16A34A', label: 'Active' },
  disposed: { bg: '#FEF2F2', color: '#DC2626', label: 'Disposed' },
  under_repair: { bg: '#FFFBEB', color: '#D97706', label: 'Under Repair' },
  fully_depreciated: { bg: '#F8FAFC', color: '#64748B', label: 'Fully Depreciated' },
};

const CATEGORY_COLORS = ['#6366F1', '#0EA5E9', '#10B981', '#F59E0B', '#EC4899', '#8B5CF6'];
const DEPT_COLORS = ['#6366F1', '#0EA5E9', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#14B8A6', '#F97316', '#06B6D4', '#EF4444'];

const DEPARTMENTS = [
  'Marketing', 'Customer Relation Management', 'Operations', 'Design', 'Logistics',
  'Purchase', 'Sales / Business Development', 'Finance', 'Information Technology',
  'Human Resource', 'Production', 'Services', 'House Keeping', 'Other',
];

const DEPT_SHORT = {
  'Marketing': 'Marketing', 'Customer Relation Management': 'CRM', 'Operations': 'Operations',
  'Design': 'Design', 'Logistics': 'Logistics', 'Purchase': 'Purchase',
  'Sales / Business Development': 'Sales', 'Finance': 'Finance',
  'Information Technology': 'IT', 'Human Resource': 'HR', 'Production': 'Production',
  'Services': 'Services', 'House Keeping': 'HouseKeeping', 'Other': 'Other',
};

const fmt = (n) => `₹${Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
const fmtDec = (n) => `₹${Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// ─── KPI Card ─────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, subColor, trend, icon }) {
  return (
    <Box sx={{
      bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px',
      p: 2.5, flex: 1, minWidth: 160, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      boxShadow: '0 1px 2px rgba(15, 23, 42, 0.02)'
    }}>
      <Box>
        <Typography sx={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500, mb: 1.5, letterSpacing: '0.02em' }}>
          {label}
        </Typography>
        <Typography sx={{ fontSize: '1.5rem', fontWeight: 700, color: '#0F172A', lineHeight: 1, mb: 1 }}>
          {value}
        </Typography>
      {sub && (
        <Typography sx={{ fontSize: '0.72rem', color: subColor || '#94A3B8', fontWeight: 500 }}>
          {sub}
        </Typography>
      )}
      </Box>
      {icon && (
        <Box sx={{
          p: 1.25,
          borderRadius: '12px',
          bgcolor: subColor ? `${subColor}10` : '#F1F5F9',
          color: subColor || '#64748B',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}>
          {icon}
        </Box>
      )}
    </Box>
  );
}

// ─── Status Badge ─────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const s = STATUS_COLORS[status] || STATUS_COLORS.active;
  return (
    <Box sx={{
      display: 'inline-flex', alignItems: 'center', gap: 0.5,
      px: 1.5, py: 0.5, bgcolor: s.bg, color: s.color,
      borderRadius: '100px', fontSize: '0.72rem', fontWeight: 600,
    }}>
      <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: s.color }} />
      {s.label}
    </Box>
  );
}

// ─── Department Tag ───────────────────────────────────────────────────────────
function DeptTag({ dept }) {
  if (!dept) return <Typography sx={{ fontSize: '0.75rem', color: '#CBD5E1' }}>—</Typography>;
  const idx = DEPARTMENTS.indexOf(dept) % DEPT_COLORS.length;
  const color = DEPT_COLORS[Math.max(0, idx)];
  return (
    <Box sx={{
      display: 'inline-flex', px: 1.5, py: 0.4,
      bgcolor: `${color}14`, color, borderRadius: '6px',
      fontSize: '0.71rem', fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {DEPT_SHORT[dept] || dept}
    </Box>
  );
}

// ─── Category Pill ────────────────────────────────────────────────────────────
function CategoryPill({ category }) {
  const label = CATEGORY_LABELS[category] || category;
  const colors = {
    computer: { bg: '#EEF2FF', color: '#4F46E5' },
    furniture: { bg: '#F0FDF4', color: '#16A34A' },
    vehicle: { bg: '#FFF7ED', color: '#EA580C' },
    machinery: { bg: '#FDF4FF', color: '#A21CAF' },
    building: { bg: '#FFFBEB', color: '#D97706' },
    other: { bg: '#F8FAFC', color: '#64748B' },
  };
  const c = colors[category] || colors.other;
  return (
    <Box sx={{
      display: 'inline-flex', px: 1.5, py: 0.4,
      bgcolor: c.bg, color: c.color, borderRadius: '6px',
      fontSize: '0.71rem', fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {label}
    </Box>
  );
}

// ─── Asset Avatar ─────────────────────────────────────────────────────────────
function AssetAvatar({ category }) {
  const icons = { computer: '💻', furniture: '🪑', vehicle: '🚗', machinery: '⚙️', building: '🏢', other: '📦' };
  const colors = {
    computer: '#EEF2FF', furniture: '#F0FDF4', vehicle: '#FFF7ED',
    machinery: '#FDF4FF', building: '#FFFBEB', other: '#F8FAFC',
  };
  return (
    <Box sx={{
      width: 36, height: 36, borderRadius: '10px',
      bgcolor: colors[category] || '#F8FAFC',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: '1rem', flexShrink: 0,
    }}>
      {icons[category] || '📦'}
    </Box>
  );
}

// ─── Add Asset Drawer ─────────────────────────────────────────────────────────
function AddAssetDrawer({ open, onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '', category: 'computer', description: '', serial_number: '', vendor: '',
    location: '', department: '', purchase_date: '', purchase_cost: '',
    salvage_value: '0', useful_life_years: '5', depreciation_method: 'slm', depreciation_rate: '20',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showAdditional, setShowAdditional] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!open) {
      setAttachments([]);
      setDragOver(false);
    }
  }, [open]);

  const handleChange = (e) => setForm(f => ({ ...f, [e.target.name]: e.target.value }));

  const handleFileChange = (e) => {
    if (e.target.files) {
      const filesArray = Array.from(e.target.files);
      setAttachments(prev => [...prev, ...filesArray]);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files) {
      const filesArray = Array.from(e.dataTransfer.files);
      setAttachments(prev => [...prev, ...filesArray]);
    }
  };

  const handleSubmit = async () => {
    if (!form.name || !form.purchase_date || !form.purchase_cost) {
      setError('Name, Purchase Date and Purchase Cost are required.');
      return;
    }
    setLoading(true); setError('');
    try {
      const res = await apiClient(`${API}/assets/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Failed to create asset.');
      onCreated(); onClose();
      setForm({ name: '', category: 'computer', description: '', serial_number: '', vendor: '', location: '', department: '', purchase_date: '', purchase_cost: '', salvage_value: '0', useful_life_years: '5', depreciation_method: 'slm', depreciation_rate: '20' });
      setAttachments([]);
      setShowAdditional(false);
    } catch (e) { setError(e.message || 'Failed to create asset.'); }
    finally { setLoading(false); }
  };

  const cost = Number(form.purchase_cost || 0);
  const salvage = Number(form.salvage_value || 0);
  const years = Number(form.useful_life_years || 5);
  const method = form.depreciation_method;
  const rate = Number(form.depreciation_rate || 20);

  let monthlyDep = 0;
  if (method === 'slm') {
    monthlyDep = years > 0 ? (cost - salvage) / years / 12 : 0;
  } else {
    monthlyDep = (cost * (rate / 100)) / 12;
  }
  if (monthlyDep < 0 || isNaN(monthlyDep)) monthlyDep = 0;

  const cardStyle = {
    bgcolor: '#FFFFFF',
    border: '1px solid #F1F5F9',
    borderRadius: '12px',
    p: 2,
  };

  const inputStyle = {
    '& .MuiOutlinedInput-root': {
      height: 40,
      borderRadius: '8px',
      backgroundColor: '#FFFFFF',
      '& fieldset': { borderColor: '#E2E8F0', borderWidth: '1px' },
      '&:hover fieldset': { borderColor: '#CBD5E1' },
      '&.Mui-focused fieldset': { borderColor: '#6D5DF6', borderWidth: '1.5px' },
    },
    '& .MuiInputLabel-root': {
      color: '#64748B',
      fontSize: '0.82rem',
      transform: 'translate(14px, 10px) scale(1)',
      '&.MuiInputLabel-shrink': {
        transform: 'translate(14px, -6px) scale(0.75)',
      },
      '&.Mui-focused': { color: '#6D5DF6' },
    },
    '& .MuiOutlinedInput-input': { fontSize: '0.85rem', color: '#0F172A', py: 0 },
  };

  const textareaStyle = {
    ...inputStyle,
    '& .MuiOutlinedInput-root': {
      height: 'auto',
      borderRadius: '8px',
      backgroundColor: '#FFFFFF',
      '& fieldset': { borderColor: '#E2E8F0' },
      '&:hover fieldset': { borderColor: '#CBD5E1' },
      '&.Mui-focused fieldset': { borderColor: '#6D5DF6' },
    },
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        backdrop: {
          sx: {
            backdropFilter: 'blur(4px)',
            backgroundColor: 'rgba(15, 23, 42, 0.15)',
          }
        }
      }}
      PaperProps={{ sx: { width: { xs: '100%', md: '25vw' }, minWidth: { md: '380px' }, maxWidth: '90vw', p: 0, bgcolor: '#FFFFFF', borderLeft: '1px solid #F1F5F9' } }}
    >
      {/* Header */}
      <Box sx={{ p: 2, pb: 1.5, bgcolor: '#FFFFFF', borderBottom: '1px solid #F1F5F9', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography sx={{ fontWeight: 700, fontSize: '20px', color: '#0F172A', lineHeight: 1.2 }}>Add New Asset</Typography>
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ color: '#94A3B8', mt: 0.5 }}><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
      </Box>

      {/* Body */}
      <Box sx={{
        p: 2,
        pt: 1.5,
        overflowY: 'auto',
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        bgcolor: '#FAFAFA',
        '&::-webkit-scrollbar': { display: 'none' },
        msOverflowStyle: 'none',
        scrollbarWidth: 'none',
      }}>
        {error && <Alert severity="error" sx={{ borderRadius: '8px' }}>{error}</Alert>}

        <Stack spacing={1.5}>
          {/* Section 1: Asset Information */}
          <Box sx={cardStyle}>
            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A', mb: 1.5 }}>Asset Information</Typography>
            <Stack spacing={1.5}>
              <TextField label="Asset Name" name="name" value={form.name} onChange={handleChange} fullWidth sx={inputStyle} placeholder="e.g. MacBook Pro M4" />
              <Box sx={{ display: 'flex', gap: 1.5 }}>
                <FormControl fullWidth sx={inputStyle}>
                  <InputLabel>Category</InputLabel>
                  <Select name="category" value={form.category} label="Category" onChange={handleChange}>
                    {Object.entries(CATEGORY_LABELS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
                  </Select>
                </FormControl>
                <FormControl fullWidth sx={inputStyle}>
                  <InputLabel>Department</InputLabel>
                  <Select name="department" value={form.department} label="Department" onChange={handleChange}>
                    <MenuItem value="">None / Unassigned</MenuItem>
                    {DEPARTMENTS.map(d => <MenuItem key={d} value={d}>{d}</MenuItem>)}
                  </Select>
                </FormControl>
              </Box>
              <Box sx={{ display: 'flex', gap: 1.5 }}>
                <TextField label="Purchase Date" name="purchase_date" type="date" value={form.purchase_date} onChange={handleChange} fullWidth sx={inputStyle} InputLabelProps={{ shrink: true }} />
                <TextField label="Purchase Cost (₹)" name="purchase_cost" type="number" value={form.purchase_cost} onChange={handleChange} fullWidth sx={inputStyle} />
              </Box>
              <TextField label="Vendor / Supplier" name="vendor" value={form.vendor} onChange={handleChange} fullWidth sx={inputStyle} placeholder="e.g. Apple Store India" />
            </Stack>
          </Box>

          {/* Section 3: Depreciation Settings */}
          <Box sx={cardStyle}>
            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A', mb: 1.5 }}>Depreciation Settings</Typography>
            <Stack spacing={1.5}>
              <Box sx={{ display: 'flex', gap: 1.5 }}>
                <TextField label="Useful Life (Years)" name="useful_life_years" type="number" value={form.useful_life_years} onChange={handleChange} fullWidth sx={inputStyle} />
                <FormControl fullWidth sx={inputStyle}>
                  <InputLabel>Depreciation Method</InputLabel>
                  <Select name="depreciation_method" value={form.depreciation_method} label="Depreciation Method" onChange={handleChange}>
                    <MenuItem value="slm">Straight Line (SLM)</MenuItem>
                    <MenuItem value="wdv">Written Down Value (WDV)</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Box sx={{ display: 'flex', gap: 1.5 }}>
                <TextField label="Rate (%/year)" name="depreciation_rate" type="number" value={form.depreciation_rate} onChange={handleChange} fullWidth sx={inputStyle} />
                <TextField label="Salvage Value (₹)" name="salvage_value" type="number" value={form.salvage_value} onChange={handleChange} fullWidth sx={inputStyle} />
              </Box>
            </Stack>
          </Box>

          {/* Section 4: Tracking Information */}
          <Box sx={cardStyle}>
            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A', mb: 1.5 }}>Tracking Information</Typography>
            <Stack spacing={1.5}>
              <Box sx={{ display: 'flex', gap: 1.5 }}>
                <TextField label="Serial Number" name="serial_number" value={form.serial_number} onChange={handleChange} fullWidth sx={inputStyle} placeholder="e.g. C02GL5..." />
                <TextField label="Location" name="location" value={form.location} onChange={handleChange} fullWidth sx={inputStyle} placeholder="e.g. Headquarters - Floor 2" />
              </Box>
            </Stack>
          </Box>

          {/* Section 5: Additional Information (Collapsible) */}
          <Box sx={{ ...cardStyle, p: 1.5 }}>
            <Button
              onClick={() => setShowAdditional(!showAdditional)}
              fullWidth
              sx={{
                justifyContent: 'space-between',
                textTransform: 'none',
                fontWeight: 700,
                color: '#0F172A',
                fontSize: '0.85rem',
                p: 0.5,
                '&:hover': { bgcolor: '#F8FAFC' }
              }}
            >
              <span>Additional Information & Description</span>
              <span style={{ fontSize: '1rem', color: '#64748B' }}>{showAdditional ? '−' : '+'}</span>
            </Button>
            <Collapse in={showAdditional}>
              <Box sx={{ pt: 1.2, px: 0.5, display: 'flex', flexDirection: 'column', gap: 1.2 }}>
                <TextField
                  label="Description"
                  name="description"
                  value={form.description}
                  onChange={handleChange}
                  fullWidth
                  sx={textareaStyle}
                  multiline
                  rows={2}
                  placeholder="Enter detailed description of the asset..."
                />
                
                <input
                  type="file"
                  ref={fileInputRef}
                  multiple
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                />

                <Box
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOver(true);
                  }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleDrop}
                  sx={{
                    border: '1px dashed',
                    borderColor: dragOver ? '#6D5DF6' : '#E2E8F0',
                    borderRadius: '8px',
                    py: 1,
                    px: 2,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 1,
                    bgcolor: dragOver ? '#EEF2FF' : '#F8FAFC',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease-in-out',
                    '&:hover': {
                      bgcolor: '#F1F5F9',
                      borderColor: '#6D5DF6',
                    }
                  }}
                >
                  <FileUploadOutlinedIcon sx={{ fontSize: 16, color: dragOver ? '#6D5DF6' : '#64748B' }} />
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#475569' }}>
                    Upload Invoice / Attachment
                  </Typography>
                </Box>

                {attachments.length > 0 && (
                  <Box sx={{ mt: 0.5 }}>
                    <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: '#475569', mb: 1, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Uploaded Files ({attachments.length})
                    </Typography>
                    <Stack spacing={1}>
                      {attachments.map((file, idx) => (
                        <Box
                          key={idx}
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            p: 1,
                            px: 1.2,
                            bgcolor: '#F8FAFC',
                            border: '1px solid #E2E8F0',
                            borderRadius: '8px',
                          }}
                        >
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, overflow: 'hidden' }}>
                            <AttachFileIcon sx={{ fontSize: 16, color: '#64748B', flexShrink: 0 }} />
                            <Box sx={{ overflow: 'hidden' }}>
                              <Typography noWrap sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#0F172A', maxWidth: '180px' }}>
                                {file.name}
                              </Typography>
                              <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8' }}>
                                {file.size > 1024 * 1024 
                                  ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` 
                                  : `${(file.size / 1024).toFixed(0)} KB`}
                              </Typography>
                            </Box>
                          </Box>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
                            <Tooltip title="View File">
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  window.open(URL.createObjectURL(file), '_blank');
                                }}
                                sx={{ color: '#64748B', '&:hover': { color: '#6D5DF6', bgcolor: '#EEF2FF' } }}
                              >
                                <VisibilityIcon sx={{ fontSize: 16 }} />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Remove">
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setAttachments(prev => prev.filter((_, i) => i !== idx));
                                }}
                                sx={{ color: '#94A3B8', '&:hover': { color: '#EF4444', bgcolor: '#FEF2F2' } }}
                              >
                                <DeleteOutlineIcon sx={{ fontSize: 16 }} />
                              </IconButton>
                            </Tooltip>
                          </Box>
                        </Box>
                      ))}
                    </Stack>
                    
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
                      <Button
                        size="small"
                        onClick={() => fileInputRef.current?.click()}
                        startIcon={<AddIcon sx={{ fontSize: 14 }} />}
                        sx={{
                          textTransform: 'none',
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          color: '#6D5DF6',
                          p: 0.5,
                          '&:hover': { bgcolor: '#EEF2FF' }
                        }}
                      >
                        Add another invoice
                      </Button>
                    </Box>
                  </Box>
                )}
              </Box>
            </Collapse>
          </Box>
        </Stack>
      </Box>

      {/* Sticky Footer */}
      <Box sx={{ p: 2, px: 2, bgcolor: '#FFFFFF', borderTop: '1px solid #F1F5F9', display: 'flex', gap: 1.5, position: 'sticky', bottom: 0, zIndex: 10 }}>
        <Button variant="outlined" onClick={onClose} fullWidth disabled={loading}
          sx={{ borderRadius: '8px', height: 40, textTransform: 'none', fontWeight: 600, borderColor: '#E2E8F0', color: '#64748B', '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' } }}>
          Cancel
        </Button>
        <Button variant="contained" onClick={handleSubmit} fullWidth disabled={loading}
          sx={{ bgcolor: '#6D5DF6', '&:hover': { bgcolor: '#5A4ED8' }, borderRadius: '8px', height: 40, textTransform: 'none', fontWeight: 600, boxShadow: 'none' }}>
          {loading ? <CircularProgress size={18} color="inherit" /> : 'Add Asset'}
        </Button>
      </Box>
    </Drawer>
  );
}

// ─── Asset Context Card Helper ───────────────────────────────────────────────
function AssetContextCard({ asset }) {
  if (!asset) return null;
  const val = asset.current_value ?? asset.purchase_cost ?? 0;
  return (
    <Box sx={{
      bgcolor: '#F8FAFC',
      border: '1px solid #F1F5F9',
      borderRadius: '12px',
      p: 1.5,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Box>
          <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', color: '#0F172A' }}>
            {asset.name}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.3 }}>
            <Typography sx={{ fontSize: '0.72rem', color: '#64748B', fontFamily: 'monospace', fontWeight: 600 }}>
              {asset.asset_code}
            </Typography>
            <Box sx={{ width: 4, height: 4, borderRadius: '50%', bgcolor: '#CBD5E1' }} />
            <Typography sx={{ fontSize: '0.72rem', color: '#64748B' }}>
              {CATEGORY_LABELS[asset.category] || asset.category}
            </Typography>
          </Box>
        </Box>
      </Box>
      <Box sx={{ textAlign: 'right' }}>
        <Typography sx={{ fontSize: '0.68rem', color: '#94A3B8', fontWeight: 600, letterSpacing: '0.02em', textTransform: 'uppercase' }}>
          Current Book Value
        </Typography>
        <Typography sx={{ fontSize: '1rem', fontWeight: 700, color: '#0F172A', mt: 0.2 }}>
          {fmt(val)}
        </Typography>
        <Box sx={{ mt: 0.3 }}>
          <StatusBadge status={asset.status} />
        </Box>
      </Box>
    </Box>
  );
}

// ─── Assign Asset Drawer ──────────────────────────────────────────────────────
function AssignAssetDrawer({ open, onClose, asset, onDone }) {
  const [form, setForm] = useState({ action: 'assign', assigned_to: '', department: '', assigned_date: '', returned_date: '', notes: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [employees, setEmployees] = useState([]);
  const [fetchingEmployees, setFetchingEmployees] = useState(false);
  const [customDepartments, setCustomDepartments] = useState(DEPARTMENTS);
  const [condition, setCondition] = useState('good');

  const fetchEmployees = async () => {
    setFetchingEmployees(true);
    try {
      const [teamRes, workforceRes] = await Promise.all([
        apiClient('/api/team/members/', { credentials: 'include' }),
        apiClient('/api/workforce/members/', { credentials: 'include' }),
      ]);
      const teamData = teamRes.ok ? await teamRes.json() : [];
      const workforceData = workforceRes.ok ? await workforceRes.json() : [];

      const list = [];
      const seen = new Set();

      const addEmployee = (name, email, dept) => {
        const key = (email || name || '').toLowerCase().trim();
        if (!key || seen.has(key)) return;
        seen.add(key);
        list.push({
          name: name,
          email: email || '',
          department: dept || '',
        });
      };

      if (Array.isArray(workforceData)) {
        workforceData.forEach(w => {
          if (w.is_archived) return;
          addEmployee(w.full_name, w.email, w.department_name);
        });
      }

      if (Array.isArray(teamData)) {
        teamData.forEach(t => {
          const name = t.full_name || t.username || (t.email ? t.email.split('@')[0] : '');
          addEmployee(name, t.email, t.department_name);
        });
      }

      setEmployees(list);
    } catch (err) {
      console.error('Error fetching employees:', err);
    } finally {
      setFetchingEmployees(false);
    }
  };

  useEffect(() => {
    if (open) {
      const hasActive = asset?.current_assignment;
      setForm({ action: hasActive ? 'return' : 'assign', assigned_to: '', department: '', assigned_date: '', returned_date: '', notes: '' });
      setError('');
      setCondition('good');
      setCustomDepartments(DEPARTMENTS);
      fetchEmployees();
    }
  }, [open, asset]);

  const handleSubmit = async () => {
    setLoading(true); setError('');
    try {
      const finalNotes = isReturn 
        ? `Condition: ${condition.toUpperCase().replace('_', ' ')}. ${form.notes}`.trim()
        : form.notes;
      
      const payload = {
        ...form,
        notes: finalNotes,
      };

      const res = await apiClient(`${API}/assets/${asset.id}/assign/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Action failed.');
      onDone(); onClose();
    } catch (e) { setError(e.message || 'Action failed.'); }
    finally { setLoading(false); }
  };

  const isReturn = form.action === 'return';

  const cardStyle = {
    bgcolor: '#FFFFFF',
    border: '1px solid #F1F5F9',
    borderRadius: '12px',
    p: 2,
  };

  const inputStyle = {
    '& .MuiOutlinedInput-root': {
      height: 40,
      borderRadius: '8px',
      backgroundColor: '#FFFFFF',
      '& fieldset': { borderColor: '#E2E8F0', borderWidth: '1px' },
      '&:hover fieldset': { borderColor: '#CBD5E1' },
      '&.Mui-focused fieldset': { borderColor: '#6D5DF6', borderWidth: '1.5px' },
    },
    '& .MuiInputLabel-root': {
      color: '#64748B',
      fontSize: '0.82rem',
      transform: 'translate(14px, 10px) scale(1)',
      '&.MuiInputLabel-shrink': {
        transform: 'translate(14px, -6px) scale(0.75)',
      },
      '&.Mui-focused': { color: '#6D5DF6' },
    },
    '& .MuiOutlinedInput-input': { fontSize: '0.85rem', color: '#0F172A', py: 0 },
  };

  const textareaStyle = {
    ...inputStyle,
    '& .MuiOutlinedInput-root': {
      height: 'auto',
      borderRadius: '8px',
      backgroundColor: '#FFFFFF',
      '& fieldset': { borderColor: '#E2E8F0' },
      '&:hover fieldset': { borderColor: '#CBD5E1' },
      '&.Mui-focused fieldset': { borderColor: '#6D5DF6' },
    },
  };

  const impactListStyle = {
    listStyleType: 'none',
    padding: 0,
    margin: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        backdrop: {
          sx: {
            backdropFilter: 'blur(4px)',
            backgroundColor: 'rgba(15, 23, 42, 0.15)',
          }
        }
      }}
      PaperProps={{ sx: { width: { xs: '100%', md: '25vw' }, minWidth: { md: '380px' }, maxWidth: '90vw', p: 0, bgcolor: '#FFFFFF', borderLeft: '1px solid #F1F5F9' } }}
    >
      {/* Header */}
      <Box sx={{ p: 2, pb: 1.5, bgcolor: '#FFFFFF', borderBottom: '1px solid #F1F5F9', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography sx={{ fontWeight: 700, fontSize: '20px', color: '#0F172A', lineHeight: 1.2 }}>
            {isReturn ? 'Return Asset' : 'Assign Asset'}
          </Typography>
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ color: '#94A3B8', mt: 0.5 }}><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
      </Box>

      {/* Body */}
      <Box sx={{
        p: 2,
        pt: 1.5,
        overflowY: 'auto',
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        bgcolor: '#FAFAFA',
        '&::-webkit-scrollbar': { display: 'none' },
        msOverflowStyle: 'none',
        scrollbarWidth: 'none',
      }}>
        {error && <Alert severity="error" sx={{ borderRadius: '8px' }}>{error}</Alert>}

        {/* Asset Context Card */}
        <AssetContextCard asset={asset} />

        <Stack spacing={1.5}>
          {isReturn && (
            <>
              {/* Section 1: Current Assignment Card */}
              {asset?.current_assignment && (
                <Box sx={cardStyle}>
                  <Typography sx={{ fontSize: '0.68rem', color: '#94A3B8', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', mb: 1.5 }}>
                    Currently Assigned To
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box>
                      <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', color: '#0F172A' }}>
                        {asset.current_assignment.assigned_to}
                      </Typography>
                      <Typography sx={{ fontSize: '0.75rem', color: '#64748B', mt: 0.2 }}>
                        {asset.current_assignment.department || 'No department'}
                      </Typography>
                    </Box>
                  </Box>
                  <Box sx={{ borderTop: '1px solid #F1F5F9', mt: 1.5, pt: 1.5, display: 'flex', justifyContent: 'space-between' }}>
                    <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Assigned Since</Typography>
                    <Typography sx={{ fontSize: '0.75rem', fontWeight: 600, color: '#0F172A' }}>
                      {asset.current_assignment.assigned_date ? new Date(asset.current_assignment.assigned_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                    </Typography>
                  </Box>
                </Box>
              )}

              {/* Section 2: Return Information */}
              <Box sx={cardStyle}>
                <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A', mb: 1.5 }}>Return Information</Typography>
                <Stack spacing={1.5}>
                  <TextField label="Return Date" type="date" value={form.returned_date} onChange={e => setForm(f => ({ ...f, returned_date: e.target.value }))} fullWidth sx={inputStyle} InputLabelProps={{ shrink: true }} />

                  {/* Condition Segmented Control */}
                  <FormControl fullWidth>
                    <Typography sx={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 600, mb: 0.5 }}>Condition upon Return</Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      {[
                        { key: 'excellent', label: 'Excellent' },
                        { key: 'good', label: 'Good' },
                        { key: 'maintenance', label: 'Needs Maintenance' },
                        { key: 'damaged', label: 'Damaged' },
                      ].map(c => {
                        const active = condition === c.key;
                        return (
                          <Button
                            key={c.key}
                            variant={active ? 'contained' : 'outlined'}
                            onClick={() => setCondition(c.key)}
                            sx={{
                              flex: 1,
                              minWidth: 80,
                              height: 32,
                              borderRadius: '6px',
                              textTransform: 'none',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              bgcolor: active ? '#6D5DF6' : 'transparent',
                              color: active ? '#FFFFFF' : '#64748B',
                              borderColor: active ? '#6D5DF6' : '#E2E8F0',
                              boxShadow: 'none',
                              '&:hover': {
                                bgcolor: active ? '#5A4ED8' : '#F8FAFC',
                                borderColor: active ? '#5A4ED8' : '#CBD5E1',
                                boxShadow: 'none',
                              }
                            }}
                          >
                            {c.label}
                          </Button>
                        );
                      })}
                    </Box>
                  </FormControl>

                  <TextField label="Notes" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} fullWidth sx={inputStyle} placeholder="Enter return notes..." />
                </Stack>
              </Box>


            </>
          )}

          {!isReturn && (
            <>
              {/* Section 1: Assignment Details */}
              <Box sx={cardStyle}>
                <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A', mb: 1.5 }}>Assignment Details</Typography>
                <Stack spacing={1.5}>
                  <Autocomplete
                    freeSolo
                    options={employees}
                    getOptionLabel={(option) => {
                      if (typeof option === 'string') return option;
                      if (option.name) return option.name;
                      return '';
                    }}
                    value={
                      employees.find(e => e.name === form.assigned_to) || 
                      (form.assigned_to ? { name: form.assigned_to } : null)
                    }
                    onChange={(event, value) => {
                      if (typeof value === 'string') {
                        setForm(f => ({ ...f, assigned_to: value }));
                      } else if (value) {
                        const deptName = value.department || '';
                        if (deptName && !customDepartments.includes(deptName)) {
                          setCustomDepartments(prev => [...prev, deptName]);
                        }
                        setForm(f => ({
                          ...f,
                          assigned_to: value.name,
                          department: deptName || f.department,
                        }));
                      } else {
                        setForm(f => ({ ...f, assigned_to: '' }));
                      }
                    }}
                    onInputChange={(event, newInputValue) => {
                      setForm(f => ({ ...f, assigned_to: newInputValue }));
                    }}
                    renderOption={(props, option) => {
                      const { key, ...optionProps } = props;
                      return (
                        <Box component="li" key={option.email || option.name} {...optionProps} sx={{ p: 1.2, display: 'flex', alignItems: 'center', gap: 1.2 }}>
                          <Avatar sx={{ width: 28, height: 28, bgcolor: '#6D5DF6', fontSize: '0.75rem', fontWeight: 700 }}>
                            {option.name?.charAt(0)?.toUpperCase()}
                          </Avatar>
                          <Box>
                            <Typography sx={{ fontSize: '0.8rem', fontWeight: 600, color: '#0F172A' }}>
                              {option.name}
                            </Typography>
                            {option.email && (
                              <Typography sx={{ fontSize: '0.68rem', color: '#64748B' }}>
                                {option.email} {option.department ? `• ${option.department}` : ''}
                              </Typography>
                            )}
                          </Box>
                        </Box>
                      );
                    }}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Assign To"
                        size="small"
                        fullWidth
                        sx={inputStyle}
                        InputProps={{
                          ...params.InputProps,
                          endAdornment: (
                            <>
                              {fetchingEmployees ? <CircularProgress color="inherit" size={14} /> : null}
                              {params.InputProps.endAdornment}
                            </>
                          ),
                        }}
                      />
                    )}
                  />
                  <Box sx={{ display: 'flex', gap: 1.5 }}>
                    <FormControl fullWidth sx={inputStyle}>
                      <InputLabel>Department</InputLabel>
                      <Select value={form.department} label="Department" onChange={e => setForm(f => ({ ...f, department: e.target.value }))}>
                        <MenuItem value="">None / Unassigned</MenuItem>
                        {customDepartments.map(d => <MenuItem key={d} value={d}>{d}</MenuItem>)}
                      </Select>
                    </FormControl>
                    <TextField label="Assignment Date" type="date" value={form.assigned_date} onChange={e => setForm(f => ({ ...f, assigned_date: e.target.value }))} fullWidth sx={inputStyle} InputLabelProps={{ shrink: true }} />
                  </Box>
                  <TextField label="Notes" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} fullWidth sx={inputStyle} placeholder="Enter assignment notes..." />
                </Stack>
              </Box>
            </>
          )}
        </Stack>
      </Box>

      {/* Sticky Footer */}
      <Box sx={{ p: 2, px: 2, bgcolor: '#FFFFFF', borderTop: '1px solid #F1F5F9', display: 'flex', gap: 1.5, position: 'sticky', bottom: 0, zIndex: 10 }}>
        <Button variant="outlined" onClick={onClose} fullWidth disabled={loading}
          sx={{ borderRadius: '8px', height: 40, textTransform: 'none', fontWeight: 600, borderColor: '#E2E8F0', color: '#64748B', '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' } }}>
          Cancel
        </Button>
        <Button variant="contained" onClick={handleSubmit} fullWidth disabled={loading}
          sx={{ bgcolor: '#6D5DF6', '&:hover': { bgcolor: '#5A4ED8' }, borderRadius: '8px', height: 40, textTransform: 'none', fontWeight: 600, boxShadow: 'none' }}>
          {loading ? <CircularProgress size={18} color="inherit" /> : (isReturn ? 'Return Asset' : 'Assign Asset')}
        </Button>
      </Box>
    </Drawer>
  );
}

function ViewAssetDrawer({ open, onClose, asset }) {
  const cardStyle = {
    bgcolor: '#FFFFFF',
    border: '1px solid #F1F5F9',
    borderRadius: '12px',
    p: 2,
  };

  const labelValueRowStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    py: 0.9,
    borderBottom: '1px solid #F8FAFC',
    '&:last-child': { borderBottom: 'none' },
  };

  const labelStyle = { fontSize: '0.75rem', color: '#64748B', fontWeight: 500 };
  const valueStyle = { fontSize: '0.78rem', color: '#0F172A', fontWeight: 600, textAlign: 'right', maxWidth: '55%' };

  const depPct = asset && asset.purchase_cost > 0
    ? ((asset.current_value / asset.purchase_cost) * 100).toFixed(1)
    : '100.0';

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        backdrop: {
          sx: { backdropFilter: 'blur(4px)', backgroundColor: 'rgba(15, 23, 42, 0.15)' }
        }
      }}
      PaperProps={{
        sx: {
          width: { xs: '100%', md: '26vw' },
          minWidth: { md: '390px' },
          maxWidth: '92vw',
          p: 0,
          bgcolor: '#F8FAFC',
          borderLeft: '1px solid #F1F5F9',
          display: 'flex',
          flexDirection: 'column',
        }
      }}
    >
      {/* Gradient Header */}
      <Box sx={{
        background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
        p: 2.5,
        pb: 2,
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Decorative circles */}
        <Box sx={{ position: 'absolute', top: -20, right: -20, width: 100, height: 100, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.08)' }} />
        <Box sx={{ position: 'absolute', bottom: -30, right: 40, width: 70, height: 70, borderRadius: '50%', bgcolor: 'rgba(255,255,255,0.06)' }} />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', position: 'relative', zIndex: 1 }}>
          <Box sx={{ flex: 1, pr: 1 }}>
            <Typography sx={{ fontSize: '0.65rem', color: 'rgba(255,255,255,0.7)', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', mb: 0.5 }}>
              Asset Details
            </Typography>
            <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', color: '#FFFFFF', lineHeight: 1.25, mb: 0.8 }}>
              {asset?.name || '—'}
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.75, alignItems: 'center', flexWrap: 'wrap' }}>
              <Box sx={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.85)', fontFamily: 'monospace', fontWeight: 700, bgcolor: 'rgba(255,255,255,0.15)', px: 0.9, py: 0.25, borderRadius: '5px' }}>
                {asset?.asset_code}
              </Box>
              {asset && <StatusBadge status={asset.status} />}
              {asset && <CategoryPill category={asset.category} />}
            </Box>
          </Box>
          <IconButton onClick={onClose} size="small"
            sx={{ color: 'rgba(255,255,255,0.8)', bgcolor: 'rgba(255,255,255,0.12)', borderRadius: '8px', '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' }, flexShrink: 0 }}>
            <CloseIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Box>
      </Box>

      {/* Body */}
      <Box sx={{
        flex: 1,
        overflowY: 'auto',
        p: 2,
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        '&::-webkit-scrollbar': { display: 'none' },
        msOverflowStyle: 'none',
        scrollbarWidth: 'none',
      }}>
        {!asset ? (
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, color: '#94A3B8', fontSize: '0.85rem' }}>
            No asset selected.
          </Box>
        ) : (
          <>
            {/* Financial Summary — value tiles */}
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
              {[
                { label: 'Purchase Cost', value: fmtDec(asset.purchase_cost), color: '#0F172A', bg: '#FFFFFF' },
                { label: 'Current Value', value: fmtDec(asset.current_value), color: '#10B981', bg: '#F0FDF4' },
                { label: 'Depreciation', value: fmtDec(asset.accumulated_depreciation), color: '#EA580C', bg: '#FFF7ED' },
                { label: 'Remaining Life', value: `${depPct}%`, color: '#6366F1', bg: '#EEF2FF' },
              ].map(({ label, value, color, bg }) => (
                <Box key={label} sx={{ bgcolor: bg, border: '1px solid #F1F5F9', borderRadius: '10px', p: 1.5 }}>
                  <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em', mb: 0.4 }}>{label}</Typography>
                  <Typography sx={{ fontSize: '0.9rem', fontWeight: 700, color }}>{value}</Typography>
                </Box>
              ))}
            </Box>

            {/* Depreciation Progress Bar */}
            <Box sx={{ ...cardStyle, p: 1.5 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.8 }}>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: '#0F172A' }}>Asset Value Remaining</Typography>
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: '#6366F1' }}>{depPct}%</Typography>
              </Box>
              <Box sx={{ bgcolor: '#F1F5F9', borderRadius: '99px', height: 6, overflow: 'hidden' }}>
                <Box sx={{
                  width: `${depPct}%`,
                  height: '100%',
                  borderRadius: '99px',
                  background: `linear-gradient(90deg, #6366F1, #10B981)`,
                  transition: 'width 0.5s ease',
                }} />
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.6 }}>
                <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8' }}>Depreciated</Typography>
                <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8' }}>Original cost</Typography>
              </Box>
            </Box>

            {/* Depreciation Settings */}
            <Box sx={cardStyle}>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1 }}>Depreciation</Typography>
              <Box sx={labelValueRowStyle}>
                <Typography sx={labelStyle}>Method</Typography>
                <Typography sx={valueStyle}>{asset.depreciation_method === 'slm' ? 'Straight Line (SLM)' : 'Written Down Value (WDV)'}</Typography>
              </Box>
              <Box sx={labelValueRowStyle}>
                <Typography sx={labelStyle}>Rate</Typography>
                <Typography sx={valueStyle}>{asset.depreciation_rate}% / yr</Typography>
              </Box>
              <Box sx={labelValueRowStyle}>
                <Typography sx={labelStyle}>Useful Life</Typography>
                <Typography sx={valueStyle}>{asset.useful_life_years} Years</Typography>
              </Box>
              <Box sx={labelValueRowStyle}>
                <Typography sx={labelStyle}>Salvage Value</Typography>
                <Typography sx={valueStyle}>{fmtDec(asset.salvage_value)}</Typography>
              </Box>
              <Box sx={labelValueRowStyle}>
                <Typography sx={labelStyle}>Purchase Date</Typography>
                <Typography sx={valueStyle}>
                  {asset.purchase_date ? new Date(asset.purchase_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                </Typography>
              </Box>
            </Box>

            {/* Tracking */}
            <Box sx={cardStyle}>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1 }}>Tracking</Typography>
              <Box sx={labelValueRowStyle}>
                <Typography sx={labelStyle}>Serial No.</Typography>
                <Typography sx={{ ...valueStyle, fontFamily: 'monospace', fontSize: '0.72rem' }}>{asset.serial_number || '—'}</Typography>
              </Box>
              <Box sx={labelValueRowStyle}>
                <Typography sx={labelStyle}>Location</Typography>
                <Typography sx={valueStyle}>{asset.location || '—'}</Typography>
              </Box>
              <Box sx={labelValueRowStyle}>
                <Typography sx={labelStyle}>Vendor</Typography>
                <Typography sx={valueStyle}>{asset.vendor || '—'}</Typography>
              </Box>
              {asset.department && (
                <Box sx={labelValueRowStyle}>
                  <Typography sx={labelStyle}>Department</Typography>
                  <DeptTag dept={asset.department} />
                </Box>
              )}
            </Box>

            {/* Assignment */}
            <Box sx={cardStyle}>
              <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1 }}>Assignment</Typography>
              {asset.current_assignment ? (
                <>
                  <Box sx={labelValueRowStyle}>
                    <Typography sx={labelStyle}>Assigned To</Typography>
                    <Typography sx={{ ...valueStyle, color: '#6366F1' }}>{asset.current_assignment.assigned_to}</Typography>
                  </Box>
                  <Box sx={labelValueRowStyle}>
                    <Typography sx={labelStyle}>Department</Typography>
                    <Typography sx={valueStyle}>{asset.current_assignment.department || '—'}</Typography>
                  </Box>
                  <Box sx={labelValueRowStyle}>
                    <Typography sx={labelStyle}>Since</Typography>
                    <Typography sx={valueStyle}>
                      {asset.current_assignment.assigned_date
                        ? new Date(asset.current_assignment.assigned_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
                        : '—'}
                    </Typography>
                  </Box>
                </>
              ) : (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#10B981', flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '0.78rem', color: '#10B981', fontWeight: 600 }}>Available — not assigned</Typography>
                </Box>
              )}
            </Box>

            {/* Description */}
            {asset.description && (
              <Box sx={cardStyle}>
                <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', mb: 0.8 }}>Notes</Typography>
                <Typography sx={{ fontSize: '0.78rem', color: '#475569', lineHeight: 1.6 }}>{asset.description}</Typography>
              </Box>
            )}
          </>
        )}
      </Box>

      {/* Footer */}
      <Box sx={{ p: 2, bgcolor: '#FFFFFF', borderTop: '1px solid #F1F5F9' }}>
        <Button variant="outlined" onClick={onClose} fullWidth
          sx={{ borderRadius: '8px', height: 38, textTransform: 'none', fontWeight: 600, fontSize: '0.82rem', borderColor: '#E2E8F0', color: '#64748B', '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' } }}>
          Close
        </Button>
      </Box>
    </Drawer>
  );
}

// ─── Dispose Asset Drawer ─────────────────────────────────────────────────────
function DisposeDialog({ open, onClose, asset, onDone }) {
  const [form, setForm] = useState({ disposal_date: '', method: 'sold', sale_proceeds: '0', notes: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [step, setStep] = useState('form'); // 'form' | 'confirm' | 'success'
  const [disposalResult, setDisposalResult] = useState(null);

  useEffect(() => {
    if (open) {
      const todayStr = new Date().toISOString().split('T')[0];
      setForm({ disposal_date: todayStr, method: 'sold', sale_proceeds: '0', notes: '' });
      setError('');
      setStep('form');
      setDisposalResult(null);
    }
  }, [open]);

  const handleSubmit = async () => {
    setLoading(true); setError('');
    try {
      const res = await apiClient(`${API}/assets/${asset.id}/dispose/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Disposal failed.');
      setDisposalResult(data.data || data);
      setStep('success');
      onDone();
    } catch (e) {
      setError(e.message || 'Disposal failed.');
      setStep('form');
    } finally {
      setLoading(false);
    }
  };

  if (!asset) return null;

  const bookValue = Number(asset.current_value || 0);
  const saleProceeds = form.method === 'sold' ? Number(form.sale_proceeds || 0) : 0;
  const gainLoss = saleProceeds - bookValue;
  const accumulatedDep = Number(asset.accumulated_depreciation || 0);

  const cardStyle = {
    bgcolor: '#FFFFFF',
    border: '1px solid #F1F5F9',
    borderRadius: '16px',
    p: 3,
  };

  const inputStyle = {
    '& .MuiOutlinedInput-root': {
      height: 40,
      borderRadius: '8px',
      backgroundColor: '#FFFFFF',
      '& fieldset': { borderColor: '#E2E8F0', borderWidth: '1px' },
      '&:hover fieldset': { borderColor: '#CBD5E1' },
      '&.Mui-focused fieldset': { borderColor: '#0F172A', borderWidth: '1.5px' },
    },
    '& .MuiInputLabel-root': {
      color: '#64748B',
      fontSize: '0.82rem',
      transform: 'translate(14px, 10px) scale(1)',
      '&.MuiInputLabel-shrink': {
        transform: 'translate(14px, -6px) scale(0.75)',
      },
      '&.Mui-focused': { color: '#0F172A' },
    },
    '& .MuiOutlinedInput-input': { fontSize: '0.85rem', color: '#0F172A', py: 0 },
  };

  const textareaStyle = {
    ...inputStyle,
    '& .MuiOutlinedInput-root': {
      height: 'auto',
      borderRadius: '8px',
      backgroundColor: '#FFFFFF',
      '& fieldset': { borderColor: '#E2E8F0' },
      '&:hover fieldset': { borderColor: '#CBD5E1' },
      '&.Mui-focused fieldset': { borderColor: '#0F172A' },
    },
  };

  const CATEGORY_EMOJIS = {
    computer: '💻',
    furniture: '🪑',
    vehicle: '🚗',
    machinery: '⚙️',
    building: '🏢',
    other: '📦',
  };

  const getMethodLabel = (m) => {
    switch (m) {
      case 'sold': return 'Sold';
      case 'scrapped': return 'Scrapped';
      case 'donated': return 'Donated';
      case 'stolen': return 'Lost / Stolen';
      case 'replaced': return 'Replaced';
      default: return m;
    }
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        backdrop: { sx: { backdropFilter: 'blur(4px)', backgroundColor: 'rgba(15, 23, 42, 0.15)' } }
      }}
      PaperProps={{
        sx: {
          width: { xs: '100%', md: '25vw' },
          minWidth: { md: '380px' },
          maxWidth: '90vw',
          p: 0,
          bgcolor: '#FFFFFF',
          borderLeft: '1px solid #F1F5F9',
          display: 'flex',
          flexDirection: 'column',
        }
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: '1px solid #F1F5F9', display: 'flex', justifyContent: 'space-between', alignItems: 'center', bgcolor: '#FFFFFF' }}>
        <Box>
          <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', color: '#0F172A' }}>Dispose Asset</Typography>
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ color: '#94A3B8' }}><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
      </Box>

      {/* Body */}
      <Box sx={{
        flex: 1,
        overflowY: 'auto',
        p: 2,
        bgcolor: '#FAFAFA',
        display: 'flex',
        flexDirection: 'column',
        gap: 1.8,
        '&::-webkit-scrollbar': { display: 'none' },
        msOverflowStyle: 'none',
        scrollbarWidth: 'none',
      }}>
        {error && <Alert severity="error" sx={{ borderRadius: '12px' }}>{error}</Alert>}

        {step === 'form' && (
          <>
            {/* Asset Summary Card */}
            <Box sx={cardStyle}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1.5 }}>
                <Box>
                  <Typography sx={{ fontSize: '0.9rem', fontWeight: 700, color: '#0F172A', display: 'flex', alignItems: 'center', gap: 0.8 }}>
                    <span>{CATEGORY_EMOJIS[asset.category] || '📦'}</span>
                    <span>{asset.name}</span>
                  </Typography>
                  <Typography sx={{ fontSize: '0.7rem', color: '#64748B', fontFamily: 'monospace', fontWeight: 600, mt: 0.3 }}>
                    {asset.asset_code}
                  </Typography>
                </Box>
                <Chip
                  label={asset.status === 'active' ? 'Active' : asset.status}
                  size="small"
                  sx={{
                    bgcolor: asset.status === 'active' ? '#ECFDF5' : '#F1F5F9',
                    color: asset.status === 'active' ? '#059669' : '#64748B',
                    fontWeight: 600,
                    fontSize: '0.68rem',
                    textTransform: 'capitalize',
                  }}
                />
              </Box>

              <Divider sx={{ my: 1.2, borderColor: '#F1F5F9' }} />

              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
                <Box>
                  <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Category</Typography>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#0F172A', mt: 0.3 }}>{CATEGORY_LABELS[asset.category] || asset.category}</Typography>
                </Box>
                <Box>
                  <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Purchase Date</Typography>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#0F172A', mt: 0.3 }}>
                    {asset.purchase_date ? new Date(asset.purchase_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                  </Typography>
                </Box>
                <Box sx={{ gridColumn: 'span 2' }}>
                  <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Serial Number</Typography>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#0F172A', mt: 0.3, fontFamily: 'monospace' }}>{asset.serial_number || '—'}</Typography>
                </Box>
              </Box>
            </Box>

            {/* Financial Impact (Hero Metric Cards in 2x2 grid) */}
            <Box>
              <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.06em', mb: 1 }}>Financial Impact</Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
                {[
                  { label: 'Purchase Value', value: fmtDec(asset.purchase_cost), color: '#0F172A' },
                  { label: 'Current Book Value', value: fmtDec(asset.current_value), color: '#64748B' },
                  { label: 'Accumulated Dep.', value: fmtDec(asset.accumulated_depreciation), color: '#EA580C' },
                  {
                    label: 'Estimated Gain/Loss',
                    value: gainLoss === 0 ? '₹0.00' : (gainLoss > 0 ? `+${fmtDec(gainLoss)}` : fmtDec(gainLoss)),
                    color: gainLoss === 0 ? '#64748B' : (gainLoss > 0 ? '#10B981' : '#EF4444'),
                    fontWeight: 700,
                  },
                ].map(({ label, value, color, fontWeight }) => (
                  <Box key={label} sx={{ bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '12px', p: 1.5, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                    <Typography sx={{ fontSize: '0.62rem', color: '#94A3B8', fontWeight: 600, mb: 0.5 }}>{label}</Typography>
                    <Typography sx={{ fontSize: '0.82rem', fontWeight: fontWeight || 600, color }}>{value}</Typography>
                  </Box>
                ))}
              </Box>
            </Box>

            {/* Disposal Details */}
            <Box sx={cardStyle}>
              <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A', mb: 1.5 }}>Disposal Information</Typography>
              <Stack spacing={2}>
                {/* Date Selection */}
                <TextField
                  label="Disposal Date"
                  type="date"
                  value={form.disposal_date}
                  onChange={e => setForm(f => ({ ...f, disposal_date: e.target.value }))}
                  fullWidth
                  sx={inputStyle}
                  InputLabelProps={{ shrink: true }}
                />

                {/* Disposal Type Selector Cards (wrapping flex buttons) */}
                <Box>
                  <Typography sx={{ fontSize: '0.68rem', color: '#64748B', fontWeight: 600, mb: 0.8 }}>Disposal Type</Typography>
                  <Box sx={{ display: 'flex', gap: 0.8, flexWrap: 'wrap' }}>
                    {[
                      { key: 'sold', label: 'Sold' },
                      { key: 'scrapped', label: 'Scrapped' },
                      { key: 'stolen', label: 'Lost' },
                      { key: 'donated', label: 'Donated' },
                      { key: 'replaced', label: 'Replaced' },
                    ].map(type => {
                      const active = form.method === type.key;
                      return (
                        <Button
                          key={type.key}
                          onClick={() => setForm(f => ({ ...f, method: type.key, sale_proceeds: type.key === 'sold' ? f.sale_proceeds : '0' }))}
                          sx={{
                            border: `1px solid ${active ? '#0F172A' : '#E2E8F0'}`,
                            borderRadius: '8px',
                            px: 1.2,
                            py: 0.5,
                            minWidth: 70,
                            height: 32,
                            textTransform: 'none',
                            bgcolor: active ? '#F8FAFC' : 'transparent',
                            color: active ? '#0F172A' : '#64748B',
                            '&:hover': {
                              borderColor: active ? '#0F172A' : '#CBD5E1',
                              bgcolor: active ? '#F8FAFC' : '#F8FAFC',
                            }
                          }}
                        >
                          <Typography sx={{ fontSize: '0.72rem', fontWeight: 700 }}>{type.label}</Typography>
                        </Button>
                      );
                    })}
                  </Box>
                </Box>

                {/* Sale Proceeds - conditional */}
                {form.method === 'sold' && (
                  <TextField
                    label="Sale Proceeds (₹)"
                    type="number"
                    value={form.sale_proceeds}
                    onChange={e => setForm(f => ({ ...f, sale_proceeds: e.target.value }))}
                    fullWidth
                    sx={inputStyle}
                  />
                )}

                <TextField
                  label="Notes"
                  value={form.notes}
                  onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
                  fullWidth
                  sx={textareaStyle}
                  multiline
                  rows={2}
                  placeholder="Enter details about this disposal..."
                />
              </Stack>
            </Box>

            {/* Live Calculation Panel */}
            <Box sx={{
              bgcolor: '#F8FAFC',
              border: '1px solid #E2E8F0',
              borderRadius: '16px',
              p: 3,
            }}>
              <Typography sx={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase', mb: 2, letterSpacing: '0.04em' }}>Disposal Summary</Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography sx={{ fontSize: '0.82rem', color: '#64748B' }}>Current Book Value</Typography>
                  <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, color: '#0F172A' }}>{fmtDec(bookValue)}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography sx={{ fontSize: '0.82rem', color: '#64748B' }}>Sale Value</Typography>
                  <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, color: '#0F172A' }}>
                    {form.method === 'sold' ? fmtDec(saleProceeds) : `₹0.00 (${getMethodLabel(form.method)})`}
                  </Typography>
                </Box>
                <Divider sx={{ borderColor: '#E2E8F0', my: 0.5 }} />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: '#0F172A' }}>
                    {gainLoss >= 0 ? 'Realized Profit' : 'Realized Loss'}
                  </Typography>
                  <Typography sx={{ fontSize: '0.95rem', fontWeight: 800, color: gainLoss >= 0 ? '#10B981' : '#EF4444' }}>
                    {fmtDec(Math.abs(gainLoss))}
                  </Typography>
                </Box>
              </Box>
            </Box>


            {/* Risk Warning Alert */}
            {asset.current_assignment && (
              <Box sx={{
                bgcolor: '#FFFBEB',
                border: '1px solid #FDE68A',
                borderRadius: '16px',
                p: 3,
                display: 'flex',
                gap: 1.5,
                alignItems: 'flex-start',
              }}>
                <WarningIcon sx={{ color: '#D97706', fontSize: 20, mt: 0.2 }} />
                <Box>
                  <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: '#B45309' }}>Warning</Typography>
                  <Typography sx={{ fontSize: '0.78rem', color: '#D97706', mt: 0.5, lineHeight: 1.5 }}>
                    This asset is currently assigned to <strong>{asset.current_assignment.assigned_to}</strong>.
                    Disposing this asset will automatically remove ownership and terminate the assignment.
                  </Typography>
                </Box>
              </Box>
            )}
          </>
        )}

        {step === 'confirm' && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, pt: 1 }}>
            <Box>
              <Typography sx={{ fontSize: '1rem', fontWeight: 700, color: '#0F172A' }}>Review & Confirm Disposal</Typography>
              <Typography sx={{ fontSize: '0.82rem', color: '#64748B', mt: 0.5 }}>
                Please review the financial impact details carefully before writing off the asset.
              </Typography>
            </Box>

            {/* Impact Details Card */}
            <Box sx={cardStyle}>
              <Stack spacing={2.5}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', pb: 1.5 }}>
                  <Typography sx={{ fontSize: '0.82rem', color: '#64748B' }}>Asset to Dispose</Typography>
                  <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: '#0F172A' }}>{asset.name} ({asset.asset_code})</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', pb: 1.5 }}>
                  <Typography sx={{ fontSize: '0.82rem', color: '#64748B' }}>Disposal Type</Typography>
                  <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: '#0F172A' }}>{getMethodLabel(form.method)}</Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', pb: 1.5 }}>
                  <Typography sx={{ fontSize: '0.82rem', color: '#64748B' }}>Disposal Date</Typography>
                  <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: '#0F172A' }}>
                    {form.disposal_date ? new Date(form.disposal_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', pb: 1.5 }}>
                  <Typography sx={{ fontSize: '0.82rem', color: '#64748B' }}>Book Value Write-Off</Typography>
                  <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: '#EF4444' }}>-{fmtDec(bookValue)}</Typography>
                </Box>
                {form.method === 'sold' && (
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #F1F5F9', pb: 1.5 }}>
                    <Typography sx={{ fontSize: '0.82rem', color: '#64748B' }}>Sale Value</Typography>
                    <Typography sx={{ fontSize: '0.82rem', fontWeight: 700, color: '#10B981' }}>+{fmtDec(saleProceeds)}</Typography>
                  </Box>
                )}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', pt: 0.5 }}>
                  <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: '#0F172A' }}>Disposal Gain/Loss</Typography>
                  <Typography sx={{ fontSize: '0.9rem', fontWeight: 800, color: gainLoss >= 0 ? '#10B981' : '#EF4444' }}>
                    {gainLoss >= 0 ? 'Profit: ' : 'Loss: '}{fmtDec(Math.abs(gainLoss))}
                  </Typography>
                </Box>
              </Stack>
            </Box>

            {/* Bullet Warnings */}
            <Box sx={{ bgcolor: '#FFF1F2', border: '1px solid #FFE4E6', borderRadius: '16px', p: 3 }}>
              <Typography sx={{ fontSize: '0.72rem', color: '#E11D48', fontWeight: 700, textTransform: 'uppercase', mb: 1.5, letterSpacing: '0.04em' }}>Critical Notice</Typography>
              <Stack spacing={1.5}>
                {[
                  'This action is final and cannot be reversed or undone.',
                  'All active tracking, ledger logging, and depreciation calculations will cease.',
                  'A general ledger journal entry will be automatically posted to record the transaction.',
                ].map(line => (
                  <Box key={line} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                    <Typography sx={{ color: '#E11D48', fontSize: '0.8rem', fontWeight: 700, mt: -0.1 }}>•</Typography>
                    <Typography sx={{ color: '#E11D48', fontSize: '0.78rem', fontWeight: 500, lineHeight: 1.4 }}>{line}</Typography>
                  </Box>
                ))}
              </Stack>
            </Box>
          </Box>
        )}

        {step === 'success' && (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', py: 6, px: 2, gap: 3 }}>
            <Box sx={{ width: 64, height: 64, borderRadius: '50%', bgcolor: '#ECFDF5', display: 'flex', alignItems: 'center', justify: 'center', color: '#10B981', mb: 1 }}>
              <CheckCircleIcon sx={{ fontSize: 48 }} />
            </Box>
            <Box>
              <Typography sx={{ fontSize: '1.25rem', fontWeight: 700, color: '#0F172A' }}>Asset Disposed Successfully</Typography>
              <Typography sx={{ fontSize: '0.82rem', color: '#64748B', mt: 1, maxWidth: '420px', lineHeight: 1.6 }}>
                The asset status has been updated to <strong>Disposed</strong>, and its remaining book value has been written off.
              </Typography>
            </Box>

            {/* Info Summary Box */}
            <Box sx={{
              bgcolor: '#F8FAFC',
              border: '1px solid #E2E8F0',
              borderRadius: '16px',
              p: 3,
              width: '100%',
              maxWidth: '460px',
              textAlign: 'left',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              mt: 1,
            }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography sx={{ fontSize: '0.78rem', color: '#64748B' }}>Asset Code</Typography>
                <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#0F172A', fontFamily: 'monospace' }}>{asset.asset_code}</Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography sx={{ fontSize: '0.78rem', color: '#64748B' }}>Disposal Method</Typography>
                <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#0F172A' }}>{getMethodLabel(form.method)}</Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography sx={{ fontSize: '0.78rem', color: '#64748B' }}>Journal Entry ID</Typography>
                <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: '#6366F1' }}>
                  JV #{disposalResult?.journal_entry || 'N/A'}
                </Typography>
              </Box>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography sx={{ fontSize: '0.78rem', color: '#64748B' }}>Realized Gain/Loss</Typography>
                <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: gainLoss >= 0 ? '#10B981' : '#EF4444' }}>
                  {gainLoss >= 0 ? '+' : ''}{fmtDec(gainLoss)}
                </Typography>
              </Box>
            </Box>
          </Box>
        )}
      </Box>

      {/* Footer */}
      <Box sx={{ p: 2.5, px: 3, bgcolor: '#FFFFFF', borderTop: '1px solid #F1F5F9', display: 'flex', gap: 1.5, position: 'sticky', bottom: 0, zIndex: 10 }}>
        {step === 'form' && (
          <>
            <Button variant="outlined" onClick={onClose} fullWidth
              sx={{ borderRadius: '8px', height: 40, textTransform: 'none', fontWeight: 600, fontSize: '0.82rem', borderColor: '#E2E8F0', color: '#64748B', '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' } }}>
              Cancel
            </Button>
            <Button variant="contained" onClick={() => setStep('confirm')} fullWidth
              sx={{ bgcolor: '#0F172A', '&:hover': { bgcolor: '#1E293B' }, borderRadius: '8px', height: 40, textTransform: 'none', fontWeight: 600, boxShadow: 'none' }}>
              Review Disposal
            </Button>
          </>
        )}

        {step === 'confirm' && (
          <>
            <Button variant="outlined" onClick={() => setStep('form')} fullWidth disabled={loading}
              sx={{ borderRadius: '8px', height: 40, textTransform: 'none', fontWeight: 600, fontSize: '0.82rem', borderColor: '#E2E8F0', color: '#64748B', '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' } }}>
              Back to Edit
            </Button>
            <Button variant="contained" color="error" onClick={handleSubmit} fullWidth disabled={loading}
              sx={{ bgcolor: '#DC2626', '&:hover': { bgcolor: '#B91C1C' }, borderRadius: '8px', height: 40, textTransform: 'none', fontWeight: 600, boxShadow: 'none' }}>
              {loading ? <CircularProgress size={18} color="inherit" /> : 'Confirm Permanent Disposal'}
            </Button>
          </>
        )}

        {step === 'success' && (
          <Button variant="contained" onClick={onClose} fullWidth
            sx={{ bgcolor: '#0F172A', '&:hover': { bgcolor: '#1E293B' }, borderRadius: '8px', height: 40, textTransform: 'none', fontWeight: 600, boxShadow: 'none' }}>
            Done
          </Button>
        )}
      </Box>
    </Drawer>
  );
}

// ─── Run Depreciation Dialog ──────────────────────────────────────────────────
function RunDepreciationDialog({ open, onClose, onDone }) {
  const today = new Date();
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [year, setYear] = useState(today.getFullYear());
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState('');

  const handleRun = async () => {
    setLoading(true); setError(''); setResults(null);
    try {
      const res = await apiClient(`${API}/assets/run-depreciation/`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ month, year }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Depreciation run failed.');
      setResults(data.data.results || []);
      onDone();
    } catch (e) { setError(e.message || 'Depreciation run failed.'); }
    finally { setLoading(false); }
  };

  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const processed = results ? results.filter(r => !r.skipped).length : 0;
  const skipped = results ? results.filter(r => r.skipped).length : 0;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth PaperProps={{ sx: { borderRadius: '16px' } }}>
      <DialogTitle sx={{ fontWeight: 700, color: '#0F172A' }}>Run Monthly Depreciation</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2, borderRadius: '10px' }}>{error}</Alert>}
        {!results && (
          <Box>
            <Typography sx={{ color: '#64748B', fontSize: '0.9rem', mb: 2 }}>
              This will calculate and post monthly depreciation journal entries for all active assets for the selected period.
            </Typography>
            <Box sx={{ display: 'flex', gap: 2 }}>
              <FormControl sx={{ minWidth: 140 }} size="small">
                <InputLabel>Month</InputLabel>
                <Select value={month} label="Month" onChange={e => setMonth(e.target.value)}>
                  {months.map((m, i) => <MenuItem key={i} value={i + 1}>{m}</MenuItem>)}
                </Select>
              </FormControl>
              <TextField label="Year" type="number" value={year} onChange={e => setYear(Number(e.target.value))} sx={{ width: 100 }} size="small" />
            </Box>
          </Box>
        )}
        {results && (
          <Box>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <Box sx={{ flex: 1, bgcolor: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: '12px', p: 2, textAlign: 'center' }}>
                <Typography sx={{ fontWeight: 700, fontSize: '1.5rem', color: '#16A34A' }}>{processed}</Typography>
                <Typography sx={{ fontSize: '0.8rem', color: '#16A34A' }}>Processed</Typography>
              </Box>
              <Box sx={{ flex: 1, bgcolor: '#F8FAFC', border: '1px solid #F1F5F9', borderRadius: '12px', p: 2, textAlign: 'center' }}>
                <Typography sx={{ fontWeight: 700, fontSize: '1.5rem', color: '#64748B' }}>{skipped}</Typography>
                <Typography sx={{ fontSize: '0.8rem', color: '#64748B' }}>Skipped</Typography>
              </Box>
            </Box>
            <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: '10px' }}>
              <Table size="small">
                <TableHead sx={{ bgcolor: '#F8FAFC' }}>
                  <TableRow>
                    {['Asset', 'Status', 'Depreciation', 'Book Value After'].map(h => (
                      <TableCell key={h} sx={{ fontWeight: 600, fontSize: '0.75rem', color: '#64748B' }}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {results.map((r, i) => (
                    <TableRow key={i}>
                      <TableCell sx={{ fontSize: '0.82rem', fontWeight: 500 }}>{r.asset_code}</TableCell>
                      <TableCell>
                        {r.skipped
                          ? <Box sx={{ display: 'inline-flex', px: 1.5, py: 0.3, bgcolor: '#F8FAFC', color: '#64748B', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 600 }}>{r.reason || 'Skipped'}</Box>
                          : <Box sx={{ display: 'inline-flex', px: 1.5, py: 0.3, bgcolor: '#F0FDF4', color: '#16A34A', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 600 }}>✓ Done</Box>
                        }
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.82rem' }}>{r.depreciation_amount ? fmtDec(r.depreciation_amount) : '—'}</TableCell>
                      <TableCell sx={{ fontSize: '0.82rem' }}>{r.book_value_after ? fmtDec(r.book_value_after) : '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ p: 2, gap: 1 }}>
        <Button onClick={onClose} sx={{ borderRadius: '10px', textTransform: 'none', fontWeight: 600, color: '#64748B' }}>Close</Button>
        {!results && (
          <Button variant="contained" onClick={handleRun} disabled={loading}
            sx={{ bgcolor: '#0F172A', '&:hover': { bgcolor: '#1E293B' }, borderRadius: '10px', textTransform: 'none', fontWeight: 600 }}>
            {loading ? <CircularProgress size={18} color="inherit" /> : 'Run Depreciation'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

// ─── Category Distribution Bars ───────────────────────────────────────────────
function CategoryDistributionCard({ data }) {
  const max = Math.max(...data.map(d => d.value), 1);
  const catColors = {
    'Computer & IT': '#6366F1',
    'Vehicle': '#0EA5E9',
    'Furniture & Fixtures': '#10B981',
    'Machinery & Equipment': '#8B5CF6',
    'Building & Property': '#F59E0B',
    'Other': '#94A3B8',
  };
  return (
    <Box sx={{ bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', p: 3, flex: 1, minWidth: 280 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2.5 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', color: '#0F172A' }}>Asset Distribution by Category</Typography>
        <Typography sx={{ fontSize: '0.75rem', color: '#6366F1', fontWeight: 600, cursor: 'pointer' }}>View all</Typography>
      </Box>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {data.map((d, i) => {
          const pct = (d.value / max) * 100;
          const color = catColors[d.name] || CATEGORY_COLORS[i % CATEGORY_COLORS.length];
          return (
            <Box key={i}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: color }} />
                  <Typography sx={{ fontSize: '0.8rem', fontWeight: 500, color: '#0F172A' }}>{d.name}</Typography>
                </Box>
                <Typography sx={{ fontSize: '0.78rem', color: '#94A3B8' }}>{d.value} Assets</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Box sx={{ flex: 1, height: 6, bgcolor: '#F1F5F9', borderRadius: '100px', overflow: 'hidden' }}>
                  <Box sx={{ width: `${pct}%`, height: '100%', bgcolor: color, borderRadius: '100px', transition: 'width 0.5s ease' }} />
                </Box>
                <Typography sx={{ fontSize: '0.72rem', color: '#94A3B8', minWidth: 80, textAlign: 'right' }}>{fmt(d.amount)}</Typography>
              </Box>
            </Box>
          );
        })}
        {data.length === 0 && (
          <Typography sx={{ color: '#CBD5E1', fontSize: '0.82rem', textAlign: 'center', py: 3 }}>No data yet</Typography>
        )}
      </Box>
    </Box>
  );
}

// ─── Asset Value Trend ────────────────────────────────────────────────────────
function AssetValueTrendCard({ assets }) {
  // Build a simple bar by purchase month from assets
  const monthMap = {};
  (assets || []).forEach(a => {
    if (!a.purchase_date) return;
    const d = new Date(a.purchase_date);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    if (!monthMap[key]) monthMap[key] = { month: key, originalValue: 0, bookValue: 0 };
    monthMap[key].originalValue += Number(a.purchase_cost || 0);
    monthMap[key].bookValue += Number(a.current_value || 0);
  });
  const trendData = Object.values(monthMap).sort((a, b) => a.month.localeCompare(b.month)).slice(-8);

  return (
    <Box sx={{ bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', p: 3, flex: 1, minWidth: 280 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2.5 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', color: '#0F172A' }}>Asset Value Trend</Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 8, height: 2, bgcolor: '#6366F1', borderRadius: 1 }} />
            <Typography sx={{ fontSize: '0.7rem', color: '#94A3B8' }}>Original Value</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 8, height: 2, bgcolor: '#10B981', borderRadius: 1 }} />
            <Typography sx={{ fontSize: '0.7rem', color: '#94A3B8' }}>Book Value</Typography>
          </Box>
        </Box>
      </Box>
      {trendData.length > 0 ? (
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={trendData} margin={{ top: 0, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
            <YAxis tickFormatter={v => { const val = v / 100000; return `₹${val % 1 === 0 ? val.toFixed(0) : val.toFixed(1)}L`; }} tick={{ fontSize: 10, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
            <RechartsTooltip formatter={v => fmtDec(v)} contentStyle={{ borderRadius: '10px', border: '1px solid #F1F5F9', boxShadow: '0 4px 20px rgba(0,0,0,0.06)' }} />
            <Line type="monotone" dataKey="originalValue" stroke="#6366F1" strokeWidth={1.5} dot={{ r: 3, fill: '#6366F1', strokeWidth: 0 }} name="Original Value" />
            <Line type="monotone" dataKey="bookValue" stroke="#10B981" strokeWidth={1.5} dot={{ r: 3, fill: '#10B981', strokeWidth: 0 }} name="Book Value" strokeDasharray="4 2" />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <Box sx={{ height: 160, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Typography sx={{ color: '#CBD5E1', fontSize: '0.82rem' }}>No assets to trend</Typography>
        </Box>
      )}
    </Box>
  );
}

// ─── Assets by Department Donut ───────────────────────────────────────────────
function DepartmentDonutCard({ data }) {
  const total = data.reduce((s, d) => s + d.value, 0);

  // Show top 4, group the rest as "Others"
  const MAX_SHOWN = 4;
  const sorted = [...data].sort((a, b) => b.value - a.value);
  const topItems = sorted.slice(0, MAX_SHOWN);
  const othersValue = sorted.slice(MAX_SHOWN).reduce((s, d) => s + d.value, 0);
  const chartData = othersValue > 0
    ? [...topItems, { name: 'Others', value: othersValue }]
    : topItems;
  const legendData = chartData;
  const chartColors = [...DEPT_COLORS.slice(0, MAX_SHOWN), '#CBD5E1'];

  return (
    <Box sx={{ bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', p: 3, flex: 1, minWidth: 320 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography sx={{ fontWeight: 700, fontSize: '0.9rem', color: '#0F172A' }}>Assets by Department</Typography>
        <Typography sx={{ fontSize: '0.75rem', color: '#6366F1', fontWeight: 600, cursor: 'pointer' }}>View all</Typography>
      </Box>
      {data.length === 0 ? (
        <Box sx={{ height: 190, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Typography sx={{ color: '#CBD5E1', fontSize: '0.82rem' }}>No department data yet</Typography>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
          {/* Donut with CSS-positioned center label */}
          <Box sx={{ flex: '0 0 190px', position: 'relative', width: 190, height: 190 }}>
            <PieChart width={190} height={190}>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={56}
                outerRadius={88}
                strokeWidth={2}
                stroke="#FFFFFF"
                startAngle={90}
                endAngle={-270}
              >
                {chartData.map((_, i) => (
                  <Cell key={i} fill={chartColors[i]} />
                ))}
              </Pie>
              <RechartsTooltip
                formatter={(v, n) => [`${v} assets`, n]}
                contentStyle={{ borderRadius: '10px', border: '1px solid #F1F5F9', boxShadow: '0 4px 12px rgba(0,0,0,0.06)' }}
              />
            </PieChart>
            {/* Absolutely centered label — guaranteed center */}
            <Box sx={{
              position: 'absolute',
              top: '50%', left: '50%',
              transform: 'translate(-50%, -50%)',
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              pointerEvents: 'none',
            }}>
              <Typography sx={{ fontSize: '1.5rem', fontWeight: 700, color: '#0F172A', lineHeight: 1 }}>
                {total}
              </Typography>
              <Typography sx={{ fontSize: '0.7rem', color: '#94A3B8', fontWeight: 500, mt: 0.3 }}>
                Total
              </Typography>
            </Box>
          </Box>

          {/* Legend */}
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1.2 }}>
            {legendData.map((d, i) => (
              <Box key={i} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: chartColors[i], flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '0.78rem', color: '#475569', fontWeight: 500 }}>
                    {DEPT_SHORT[d.name] || d.name}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, ml: 1 }}>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: '#0F172A', minWidth: 20, textAlign: 'right' }}>
                    {d.value}
                  </Typography>
                  <Typography sx={{ fontSize: '0.72rem', color: '#94A3B8' }}>
                    ({Math.round((d.value / total) * 100)}%)
                  </Typography>
                </Box>
              </Box>
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}

// ─── Asset Row Actions Menu ───────────────────────────────────────────────────
function AssetActionsMenu({ asset, onView, onAssign, onDispose }) {
  const [anchor, setAnchor] = useState(null);
  const open = Boolean(anchor);
  return (
    <>
      <IconButton size="small" onClick={e => { e.stopPropagation(); setAnchor(e.currentTarget); }}
        sx={{ color: '#94A3B8', borderRadius: '8px', '&:hover': { bgcolor: '#F8FAFC', color: '#0F172A' } }}>
        <MoreHorizIcon sx={{ fontSize: 18 }} />
      </IconButton>
      <Menu anchorEl={anchor} open={open} onClose={() => setAnchor(null)}
        PaperProps={{ sx: { borderRadius: '12px', border: '1px solid #F1F5F9', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', minWidth: 140 } }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}>
        <MenuItem onClick={() => { setAnchor(null); onView(); }}
          sx={{ fontSize: '0.82rem', color: '#0F172A', fontWeight: 500, py: 1 }}>
          View
        </MenuItem>
        <MenuItem onClick={() => { setAnchor(null); onAssign(); }}
          sx={{ fontSize: '0.82rem', color: '#0F172A', fontWeight: 500, py: 1 }}
          disabled={asset.status === 'disposed'}>
          {asset.current_assignment ? 'Return' : 'Assign'}
        </MenuItem>
        <Divider sx={{ my: 0.5 }} />
        <MenuItem onClick={() => { setAnchor(null); onDispose(); }}
          sx={{ fontSize: '0.82rem', color: '#DC2626', fontWeight: 500, py: 1 }}
          disabled={asset.status === 'disposed'}>
          Dispose
        </MenuItem>
      </Menu>
    </>
  );
}

// ─── Asset Register Tab ───────────────────────────────────────────────────────
function AssetRegisterTab({ assets, dashboard, loading, onRefresh }) {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [addDrawer, setAddDrawer] = useState(false);
  const [assignDrawer, setAssignDrawer] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [disposeDialog, setDisposeDialog] = useState(false);
  const [viewDrawer, setViewDrawer] = useState(false);

  const filteredAssets = useMemo(() => {
    return (assets || []).filter(asset => {
      if (statusFilter && asset.status !== statusFilter) return false;
      if (categoryFilter && asset.category !== categoryFilter) return false;
      if (departmentFilter && asset.department !== departmentFilter) return false;
      if (search) {
        const term = search.toLowerCase();
        const nameMatch = asset.name?.toLowerCase().includes(term);
        const codeMatch = asset.asset_code?.toLowerCase().includes(term);
        const serialMatch = asset.serial_number?.toLowerCase().includes(term);
        if (!nameMatch && !codeMatch && !serialMatch) return false;
      }
      return true;
    });
  }, [assets, search, statusFilter, categoryFilter, departmentFilter]);

  const displayedAssets = filteredAssets;
  const fetchAll = onRefresh;

  const categoryChartData = dashboard?.category_breakdown?.map(c => ({
    name: CATEGORY_LABELS[c.category] || c.category,
    value: c.count,
    amount: c.total_value,
  })) || [];

  const departmentChartData = dashboard?.department_breakdown
    ?.filter(d => d.count > 0)
    ?.map(d => ({ name: d.department || 'Unassigned', value: d.count, amount: d.total_value })) || [];

  const assignedCount = dashboard?.assigned_assets_count ?? assets.filter(a => a.current_assignment).length;
  const unassignedCount = (dashboard?.total_assets ?? assets.length) - assignedCount;
  const depRate = dashboard?.depreciation_rate ?? 0;

  return (
    <Box>
      {/* KPI Row */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <KpiCard label="Total Assets" value={dashboard?.total_assets ?? '—'} sub={`+${dashboard?.active_count ?? 0} active`} subColor="#10B981" />
        <KpiCard label="Total Asset Value" value={dashboard ? fmt(dashboard.total_purchase_cost) : '—'} sub="Original Purchase Cost" />
        <KpiCard label="Current Book Value" value={dashboard ? fmt(dashboard.total_current_value) : '—'} sub="After Depreciation" />
        <KpiCard label="Total Depreciation" value={dashboard ? fmt(dashboard.total_accumulated_depreciation) : '—'}
          sub={`${depRate}% of original value`} subColor="#F59E0B" />
        <KpiCard label="Assigned Assets" value={assignedCount} sub={`${dashboard ? Math.round((assignedCount / Math.max(dashboard.total_assets, 1)) * 100) : 0}% of total`} />
        <KpiCard label="Unassigned Assets" value={unassignedCount} sub={`${dashboard ? Math.round((unassignedCount / Math.max(dashboard.total_assets, 1)) * 100) : 0}% of total`} />
      </Box>

      {/* Charts Row */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <CategoryDistributionCard data={categoryChartData} />
        <AssetValueTrendCard assets={assets} />
        <DepartmentDonutCard data={departmentChartData} />
      </Box>

      {/* Asset Registry Card */}
      <Box sx={{ bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', overflow: 'hidden' }}>
        {/* Registry Header */}
        <Box sx={{ p: 3, pb: 2, borderBottom: '1px solid #F8FAFC' }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Box>
              <Typography sx={{ fontWeight: 700, fontSize: '1rem', color: '#0F172A' }}>Asset Registry</Typography>
              <Typography sx={{ fontSize: '0.8rem', color: '#94A3B8', mt: 0.3 }}>Manage and track all registered company assets.</Typography>
            </Box>
            <Tooltip title="Refresh">
              <IconButton onClick={fetchAll} size="small" sx={{ color: '#94A3B8' }}><RefreshIcon sx={{ fontSize: 16 }} /></IconButton>
            </Tooltip>
          </Box>

          {/* Filter Toolbar */}
          <Box sx={{ display: 'flex', gap: 1.5, mt: 2, alignItems: 'center', flexWrap: 'wrap' }}>
            <TextField
              placeholder="Search assets..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              size="small"
              sx={{ minWidth: 220, '& .MuiOutlinedInput-root': { borderRadius: '10px', bgcolor: '#F8FAFC', '& fieldset': { borderColor: '#F1F5F9' } } }}
              InputProps={{ startAdornment: <SearchIcon sx={{ color: '#CBD5E1', mr: 0.5, fontSize: 16 }} /> }}
            />
            <Select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} size="small" displayEmpty
              sx={{ minWidth: 130, borderRadius: '10px', bgcolor: '#F8FAFC', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#F1F5F9' } }}>
              <MenuItem value="">All Status</MenuItem>
              {Object.entries(STATUS_COLORS).map(([k, v]) => <MenuItem key={k} value={k}>{v.label}</MenuItem>)}
            </Select>
            <Select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} size="small" displayEmpty
              sx={{ minWidth: 160, borderRadius: '10px', bgcolor: '#F8FAFC', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#F1F5F9' } }}>
              <MenuItem value="">All Categories</MenuItem>
              {Object.entries(CATEGORY_LABELS).map(([k, v]) => <MenuItem key={k} value={k}>{v}</MenuItem>)}
            </Select>
            <Select value={departmentFilter} onChange={e => setDepartmentFilter(e.target.value)} size="small" displayEmpty
              sx={{ minWidth: 170, borderRadius: '10px', bgcolor: '#F8FAFC', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#F1F5F9' } }}>
              <MenuItem value="">All Departments</MenuItem>
              {DEPARTMENTS.map(d => <MenuItem key={d} value={d}>{d}</MenuItem>)}
            </Select>
            <Button size="small" startIcon={<FilterListIcon sx={{ fontSize: 14 }} />}
              sx={{ borderRadius: '10px', textTransform: 'none', fontWeight: 600, color: '#64748B', border: '1px solid #F1F5F9', bgcolor: '#F8FAFC', px: 2, py: 0.8 }}>
              Filter
            </Button>
          </Box>
        </Box>

        {/* Table */}
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress size={24} sx={{ color: '#6366F1' }} /></Box>
        ) : (
          <Table>
            <TableHead>
              <TableRow sx={{ '& th': { borderBottom: '1px solid #F1F5F9', bgcolor: '#F8FAFC', py: 1.5 } }}>
                {['Asset', 'Category', 'Asset Tag', 'Purchase Date', 'Purchase Value', 'Current Value', 'Assigned To', 'Department', 'Status', 'Actions'].map(h => (
                  <TableCell key={h} sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#94A3B8', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{h}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {displayedAssets.length === 0 && (
                <TableRow>
                  <TableCell colSpan={10} align="center" sx={{ py: 6, color: '#CBD5E1', fontSize: '0.88rem', border: 'none' }}>
                    No assets found. Add your first asset to get started.
                  </TableCell>
                </TableRow>
              )}
              {displayedAssets.map(asset => {
                const depPct = asset.purchase_cost > 0
                  ? ((asset.current_value / asset.purchase_cost) * 100).toFixed(1)
                  : '100.0';
                return (
                  <TableRow key={asset.id} hover sx={{
                    '&:hover': { bgcolor: '#FAFAFA' },
                    '& td': { borderBottom: '1px solid #F8FAFC', py: 1.5 },
                  }}>
                    {/* Asset */}
                    <TableCell>
                      <Box>
                        <Typography sx={{ fontWeight: 600, fontSize: '0.82rem', color: '#0F172A' }}>{asset.name}</Typography>
                        <Typography sx={{ fontSize: '0.72rem', color: '#94A3B8' }}>{CATEGORY_LABELS[asset.category] || asset.category}</Typography>
                      </Box>
                    </TableCell>
                    {/* Category */}
                    <TableCell><CategoryPill category={asset.category} /></TableCell>
                    {/* Tag */}
                    <TableCell>
                      <Typography sx={{ fontSize: '0.78rem', color: '#64748B', fontFamily: 'monospace', fontWeight: 600 }}>{asset.asset_code}</Typography>
                    </TableCell>
                    {/* Purchase Date */}
                    <TableCell>
                      <Typography sx={{ fontSize: '0.78rem', color: '#64748B' }}>
                        {asset.purchase_date ? new Date(asset.purchase_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                      </Typography>
                    </TableCell>
                    {/* Purchase Value */}
                    <TableCell>
                      <Typography sx={{ fontSize: '0.82rem', fontWeight: 500, color: '#0F172A' }}>{fmtDec(asset.purchase_cost)}</Typography>
                    </TableCell>
                    {/* Current Value */}
                    <TableCell>
                      <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, color: '#0F172A' }}>{fmtDec(asset.current_value)}</Typography>
                      <Typography sx={{ fontSize: '0.7rem', color: '#10B981', fontWeight: 500 }}>{depPct}%</Typography>
                    </TableCell>
                    {/* Assigned To */}
                    <TableCell>
                      {asset.current_assignment ? (
                        <Box>
                          <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#0F172A' }}>{asset.current_assignment.assigned_to}</Typography>
                          <Typography sx={{ fontSize: '0.68rem', color: '#94A3B8' }}>{asset.current_assignment.department || 'No dept'}</Typography>
                        </Box>
                      ) : (
                        <Typography sx={{ fontSize: '0.75rem', color: '#CBD5E1' }}>Unassigned</Typography>
                      )}
                    </TableCell>
                    {/* Department */}
                    <TableCell><DeptTag dept={asset.department} /></TableCell>
                    {/* Status */}
                    <TableCell><StatusBadge status={asset.status} /></TableCell>
                    {/* Actions */}
                    <TableCell>
                      <AssetActionsMenu
                        asset={asset}
                        onView={() => { setSelectedAsset(asset); setViewDrawer(true); }}
                        onAssign={() => { setSelectedAsset(asset); setAssignDrawer(true); }}
                        onDispose={() => { setSelectedAsset(asset); setDisposeDialog(true); }}
                      />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}

        {displayedAssets.length > 0 && (
          <Box sx={{ px: 3, py: 2, borderTop: '1px solid #F8FAFC', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography sx={{ fontSize: '0.78rem', color: '#94A3B8' }}>
              Showing 1 to {displayedAssets.length} of {displayedAssets.length} assets
            </Typography>
          </Box>
        )}
      </Box>

      <AddAssetDrawer open={addDrawer} onClose={() => setAddDrawer(false)} onCreated={fetchAll} />
      <AssignAssetDrawer open={assignDrawer} onClose={() => setAssignDrawer(false)} asset={selectedAsset} onDone={fetchAll} />
      <DisposeDialog open={disposeDialog} onClose={() => setDisposeDialog(false)} asset={selectedAsset} onDone={fetchAll} />
      <ViewAssetDrawer open={viewDrawer} onClose={() => setViewDrawer(false)} asset={selectedAsset} />
    </Box>
  );
}

// ─── Circular Health Indicator Component ──────────────────────────────────────
function CircularHealthIndicator({ pct, color }) {
  const radius = 16;
  const strokeWidth = 3.5;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (pct / 100) * circumference;

  return (
    <svg width="38" height="38" style={{ transform: 'rotate(-90deg)', flexShrink: 0 }}>
      <circle cx="19" cy="19" r={radius} fill="transparent" stroke="#F1F5F9" strokeWidth={strokeWidth} />
      <circle cx="19" cy="19" r={radius} fill="transparent" stroke={color} strokeWidth={strokeWidth}
        strokeDasharray={circumference} strokeDashoffset={strokeDashoffset} strokeLinecap="round" />
    </svg>
  );
}

// ─── Journal Entries Dialog Component ─────────────────────────────────────────
function JournalEntriesDialog({ open, onClose, assets }) {
  const [depreciations, setDepreciations] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && assets.length > 0) {
      setLoading(true);
      Promise.all(assets.map(a => apiClient(`${API}/assets/${a.id}/depreciation/`).then(r => r.json())))
        .then(results => {
          const all = [];
          results.forEach((res, idx) => {
            const asset = assets[idx];
            if (res.data) {
              res.data.forEach(d => {
                all.push({ ...d, asset_code: asset.asset_code, asset_name: asset.name });
              });
            }
          });
          all.sort((a, b) => {
            const dateA = new Date(a.period_year, a.period_month - 1);
            const dateB = new Date(b.period_year, b.period_month - 1);
            return dateB - dateA;
          });
          setDepreciations(all);
        })
        .catch(err => console.error(err))
        .finally(() => setLoading(false));
    }
  }, [open, assets]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth PaperProps={{ sx: { borderRadius: '16px', p: 1 } }}>
      <DialogTitle sx={{ fontWeight: 700, color: '#0F172A', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography sx={{ fontWeight: 700, fontSize: '1.1rem' }}>Depreciation Journal Entries</Typography>
        <IconButton size="small" onClick={onClose} sx={{ color: '#94A3B8' }}><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
      </DialogTitle>
      <DialogContent>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress size={24} /></Box>
        ) : depreciations.length === 0 ? (
          <Box sx={{ py: 6, textAlign: 'center', color: '#94A3B8' }}>No depreciation journal entries found.</Box>
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow sx={{ '& th': { bgcolor: '#F8FAFC', fontWeight: 600, fontSize: '0.72rem', color: '#94A3B8' } }}>
                <TableCell>Date</TableCell>
                <TableCell>Reference</TableCell>
                <TableCell>Asset</TableCell>
                <TableCell>Method</TableCell>
                <TableCell align="right">Amount</TableCell>
                <TableCell>Ledger Accounts Impact</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {depreciations.map(d => (
                <TableRow key={d.id} hover sx={{ '& td': { py: 1.5, fontSize: '0.78rem' } }}>
                  <TableCell sx={{ fontWeight: 500, color: '#0F172A' }}>
                    {new Date(d.period_year, d.period_month - 1).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })}
                  </TableCell>
                  <TableCell sx={{ fontFamily: 'monospace', color: '#64748B' }}>DEP-{d.id}</TableCell>
                  <TableCell>
                    <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#6366F1' }}>{d.asset_code}</Typography>
                    <Typography sx={{ fontSize: '0.7rem', color: '#94A3B8' }}>{d.asset_name}</Typography>
                  </TableCell>
                  <TableCell sx={{ textTransform: 'uppercase', color: '#64748B', fontWeight: 600 }}>{d.method}</TableCell>
                  <TableCell align="right" sx={{ fontWeight: 700, color: '#EF4444' }}>−{fmtDec(d.depreciation_amount)}</TableCell>
                  <TableCell>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, fontSize: '0.68rem' }}>
                      <Box sx={{ color: '#16A34A', fontWeight: 600 }}>Dr. Depreciation Expense Ledger ({fmtDec(d.depreciation_amount)})</Box>
                      <Box sx={{ color: '#475569' }}>Cr. Accumulated Depreciation Ledger ({fmtDec(d.depreciation_amount)})</Box>
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </DialogContent>
    </Dialog>
  );
}

// ─── Asset Depreciation Drawer Component ──────────────────────────────────────
function AssetDepreciationDrawer({ open, onClose, asset }) {
  const [depreciations, setDepreciations] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && asset) {
      setLoading(true);
      apiClient(`${API}/assets/${asset.id}/depreciation/`)
        .then(r => r.json())
        .then(data => setDepreciations(data.data || []))
        .catch(() => setDepreciations([]))
        .finally(() => setLoading(false));
    }
  }, [open, asset]);

  if (!asset) return null;

  const usefulLife = Number(asset.useful_life_years || 5);
  const remainingLife = Math.max(0, usefulLife - ((asset.depreciations_count || 0) / 12)).toFixed(1);
  const depPct = asset.purchase_cost > 0
    ? ((asset.accumulated_depreciation / asset.purchase_cost) * 100).toFixed(1)
    : '0.0';

  const cardStyle = {
    bgcolor: '#FAFAFA',
    border: '1px solid #F1F5F9',
    borderRadius: '12px',
    p: 2,
    mb: 1.5,
  };

  const labelValueRowStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    py: 0.8,
    borderBottom: '1px solid #F8FAFC',
    '&:last-child': { borderBottom: 'none' },
  };

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      slotProps={{
        backdrop: { sx: { backdropFilter: 'blur(4px)', backgroundColor: 'rgba(15, 23, 42, 0.15)' } }
      }}
      PaperProps={{
        sx: {
          width: { xs: '100%', md: '25vw' },
          minWidth: { md: '380px' },
          maxWidth: '90vw',
          p: 0,
          bgcolor: '#FFFFFF',
          borderLeft: '1px solid #F1F5F9',
          display: 'flex',
          flexDirection: 'column',
        }
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: '1px solid #F1F5F9', display: 'flex', justifyContent: 'space-between', alignItems: 'center', bgcolor: '#FFFFFF' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton size="small" onClick={onClose} sx={{ color: '#64748B', '&:hover': { bgcolor: '#F1F5F9' } }}>
            <ArrowBackIcon sx={{ fontSize: 18 }} />
          </IconButton>
          <Box>
            <Typography sx={{ fontWeight: 700, fontSize: '0.95rem', color: '#0F172A' }}>Asset Schedule Details</Typography>
            <Typography sx={{ fontSize: '0.72rem', color: '#64748B', fontFamily: 'monospace' }}>{asset.asset_code}</Typography>
          </Box>
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ color: '#94A3B8' }}><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
      </Box>

      {/* Body */}
      <Box sx={{
        flex: 1,
        overflowY: 'auto',
        p: 2,
        '&::-webkit-scrollbar': { display: 'none' },
        msOverflowStyle: 'none',
        scrollbarWidth: 'none',
      }}>
        {/* Asset Summary */}
        <Box sx={cardStyle}>
          <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1 }}>Asset Summary</Typography>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Asset Name</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 600 }}>{asset.name}</Typography>
          </Box>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Category</Typography>
            <CategoryPill category={asset.category} />
          </Box>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Purchase Date</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 600 }}>
              {asset.purchase_date ? new Date(asset.purchase_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
            </Typography>
          </Box>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Purchase Cost</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 700 }}>{fmtDec(asset.purchase_cost)}</Typography>
          </Box>
        </Box>

        {/* Depreciation Details */}
        <Box sx={cardStyle}>
          <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1 }}>Depreciation Details</Typography>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Method</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 600, textTransform: 'uppercase' }}>{asset.depreciation_method}</Typography>
          </Box>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Rate</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 600 }}>{asset.depreciation_rate}% / year</Typography>
          </Box>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Useful Life</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 600 }}>{asset.useful_life_years} Years</Typography>
          </Box>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Remaining Life</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#10B981', fontWeight: 700 }}>{remainingLife} Years</Typography>
          </Box>
        </Box>

        {/* Accounting Impact */}
        <Box sx={cardStyle}>
          <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1 }}>Accounting Impact</Typography>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Total Depreciation Posted</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#EA580C', fontWeight: 700 }}>{fmtDec(asset.accumulated_depreciation)}</Typography>
          </Box>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Associated Journal Entries</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 600 }}>{asset.depreciations_count || 0} Entries</Typography>
          </Box>
          <Box sx={labelValueRowStyle}>
            <Typography sx={{ fontSize: '0.75rem', color: '#64748B' }}>Last Posting Date</Typography>
            <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 600 }}>{asset.last_depreciation_date || '—'}</Typography>
          </Box>
        </Box>

        {/* Depreciation Schedule */}
        <Box sx={cardStyle}>
          <Typography sx={{ fontSize: '0.68rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1.5 }}>Posted Monthly Schedule</Typography>
          {loading ? (
            <Box sx={{ py: 2, display: 'flex', justifyContent: 'center' }}><CircularProgress size={20} /></Box>
          ) : depreciations.length === 0 ? (
            <Typography sx={{ fontSize: '0.78rem', color: '#CBD5E1', textAlign: 'center', py: 2 }}>No entries posted yet.</Typography>
          ) : (
            depreciations.map(d => (
              <Box key={d.id} sx={{ display: 'flex', justifyContent: 'space-between', py: 1.25, borderBottom: '1px solid #F8FAFC', alignItems: 'center' }}>
                <Box>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 600, color: '#0F172A' }}>{d.period_month}/{d.period_year}</Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8' }}>{d.method?.toUpperCase()}</Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: '#EF4444' }}>−{fmtDec(d.depreciation_amount)}</Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8' }}>{fmtDec(d.book_value_after)}</Typography>
                </Box>
              </Box>
            ))
          )}
        </Box>
      </Box>

      {/* Footer */}
      <Box sx={{ p: 2, borderTop: '1px solid #F1F5F9' }}>
        <Button variant="outlined" onClick={onClose} fullWidth sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600 }}>
          Close
        </Button>
      </Box>
    </Drawer>
  );
}

// ─── Depreciation Center Tab ─────────────────────────────────────────────────
function DepreciationCenterTab({ assets, dashboard, loading, onRefresh }) {
  const [runDialog, setRunDialog] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [activeAsset, setActiveAsset] = useState(null);
  const [depreciations, setDepreciations] = useState([]);
  const [deprLoading, setDeprLoading] = useState(false);

  // New expansion states
  const [detailDrawerAsset, setDetailDrawerAsset] = useState(null);
  const [journalEntriesOpen, setJournalEntriesOpen] = useState(false);

  useEffect(() => {
    if (selectedAsset) {
      setActiveAsset(selectedAsset);
    } else {
      const timer = setTimeout(() => {
        setActiveAsset(null);
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [selectedAsset]);

  const fetchAll = onRefresh;

  const loadDepreciations = async (asset) => {
    setSelectedAsset(asset);
    setDeprLoading(true);
    try {
      const res = await apiClient(`${API}/assets/${asset.id}/depreciation/`);
      const resData = await res.json();
      setDepreciations(resData.data || []);
    } catch (e) { setDepreciations([]); }
    finally { setDeprLoading(false); }
  };

  const getHistoricalData = () => {
    if (!dashboard || !assets.length) return [];
    const monthlyDep = dashboard.monthly_depreciation || {};
    const now = new Date();
    
    const months = [];
    for (let i = 11; i >= 0; i--) {
      months.push(new Date(now.getFullYear(), now.getMonth() - i, 1));
    }
    
    let rollingCurrent = dashboard.total_current_value || 0;
    let rollingOriginal = dashboard.total_purchase_cost || 0;
    
    const points = [];
    for (let i = months.length - 1; i >= 0; i--) {
      const d = months[i];
      const year = d.getFullYear();
      const monthNum = d.getMonth() + 1;
      const monthKey = `${year}-${String(monthNum).padStart(2, '0')}`;
      
      const assetsPurchasedAfter = assets.filter(a => {
        if (!a.purchase_date) return false;
        const pDate = new Date(a.purchase_date);
        return pDate > new Date(year, monthNum - 1, 31);
      });
      const costAfter = assetsPurchasedAfter.reduce((sum, a) => sum + Number(a.purchase_cost || 0), 0);
      
      let depAfter = 0;
      Object.entries(monthlyDep).forEach(([key, val]) => {
        const [y, m] = key.split('-').map(Number);
        if (y > year || (y === year && m > monthNum)) {
          depAfter += val;
        }
      });
      
      const valOriginal = Math.max(0, rollingOriginal - costAfter);
      const valCurrent = Math.max(0, rollingCurrent + depAfter - costAfter);
      
      points.push({
        monthKey,
        label: d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' }),
        original: Math.round(valOriginal),
        current: Math.round(valCurrent),
      });
    }
    
    return points.reverse();
  };

  const getMonthlyAmountToPost = () => {
    let total = 0;
    assets.filter(a => a.status === 'active').forEach(a => {
      const rate = Number(a.depreciation_rate || 0) / 100;
      const cost = Number(a.purchase_cost || 0);
      const salvage = Number(a.salvage_value || 0);
      const current = Number(a.current_value || 0);
      if (a.depreciation_method === 'slm') {
        total += (cost - salvage) * rate / 12;
      } else {
        total += current * rate / 12;
      }
    });
    return total;
  };

  const getLastRunDate = () => {
    const dates = assets
      .map(a => a.last_depreciation_date)
      .filter(Boolean)
      .sort();
    if (dates.length === 0) return '—';
    const d = new Date(dates[dates.length - 1]);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const getNextScheduledRun = () => {
    const dates = assets
      .map(a => a.last_depreciation_date)
      .filter(Boolean)
      .sort();
    const baseDate = dates.length > 0 ? new Date(dates[dates.length - 1]) : new Date();
    const next = new Date(baseDate.getFullYear(), baseDate.getMonth() + 1, 1);
    return next.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const getHealthCounts = () => {
    let healthy = 0;
    let mid = 0;
    let nearEnd = 0;
    let healthyPcts = [];
    let midPcts = [];
    let nearEndPcts = [];
    
    const activeAssets = assets.filter(a => a.status !== 'disposed');
    activeAssets.forEach(a => {
      const usefulLife = Number(a.useful_life_years || 5);
      const depCount = a.depreciations_count || 0;
      const remaining = Math.max(0, usefulLife - (depCount / 12));
      const pct = (remaining / usefulLife) * 100;
      
      if (pct > 60) {
        healthy++;
        healthyPcts.push(pct);
      } else if (pct >= 30) {
        mid++;
        midPcts.push(pct);
      } else {
        nearEnd++;
        nearEndPcts.push(pct);
      }
    });
    
    const avg = (arr, def) => arr.length > 0 ? Math.round(arr.reduce((s, x) => s + x, 0) / arr.length) : def;
    
    return {
      healthy,
      mid,
      nearEnd,
      total: activeAssets.length,
      healthyAvg: avg(healthyPcts, 85),
      midAvg: avg(midPcts, 45),
      nearEndAvg: avg(nearEndPcts, 15),
    };
  };

  const getQuickInsights = () => {
    const activeAssets = assets.filter(a => a.status !== 'disposed');
    if (activeAssets.length === 0) return { mostDepr: null, highestVal: null, nextSalvage: null };
    
    const mostDepr = [...activeAssets].sort((a, b) => Number(b.accumulated_depreciation || 0) - Number(a.accumulated_depreciation || 0))[0];
    const highestVal = [...activeAssets].sort((a, b) => Number(b.current_value || 0) - Number(a.current_value || 0))[0];
    
    const nextSalvage = [...activeAssets].filter(a => a.status === 'active').sort((a, b) => {
      const lifeA = Number(a.useful_life_years || 5) - ((a.depreciations_count || 0) / 12);
      const lifeB = Number(b.useful_life_years || 5) - ((b.depreciations_count || 0) / 12);
      return lifeA - lifeB;
    })[0];
    
    return { mostDepr, highestVal, nextSalvage };
  };

  const renderScheduleContent = (isDrawer = false) => {
    const assetToRender = isDrawer ? selectedAsset : activeAsset;
    if (!assetToRender) return null;
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: '#FFFFFF' }}>
        {/* Header */}
        <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid #F8FAFC', display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton size="small" onClick={() => setSelectedAsset(null)} sx={{ color: '#64748B', '&:hover': { bgcolor: '#F1F5F9' } }}>
            <ArrowBackIcon sx={{ fontSize: 18 }} />
          </IconButton>
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: '#0F172A', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {assetToRender.asset_code} — Schedule
            </Typography>
            <Typography sx={{ fontSize: '0.75rem', color: '#94A3B8', mt: 0.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {assetToRender.name}
            </Typography>
          </Box>
          <IconButton size="small" onClick={() => setSelectedAsset(null)} sx={{ color: '#94A3B8', '&:hover': { bgcolor: '#F1F5F9' } }}>
            <CloseIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Box>

        {/* Schedule List */}
        <Box sx={{
          p: 2,
          flex: 1,
          overflowY: 'auto',
          maxHeight: isDrawer ? 'none' : 380,
          '&::-webkit-scrollbar': { display: 'none' },
          msOverflowStyle: 'none',
          scrollbarWidth: 'none',
        }}>
          {deprLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}><CircularProgress size={20} /></Box>
          ) : (
            depreciations.length === 0 ? (
              <Typography sx={{ fontSize: '0.82rem', color: '#CBD5E1', textAlign: 'center', py: 3 }}>
                No depreciation posted yet.
              </Typography>
            ) : (
              depreciations.map(d => (
                <Box key={d.id} sx={{ display: 'flex', justifyContent: 'space-between', py: 1.5, borderBottom: '1px solid #F8FAFC', alignItems: 'center' }}>
                  <Box>
                    <Typography sx={{ fontSize: '0.8rem', fontWeight: 600, color: '#0F172A' }}>{d.period_month}/{d.period_year}</Typography>
                    <Typography sx={{ fontSize: '0.68rem', color: '#94A3B8' }}>{d.method?.toUpperCase()}</Typography>
                  </Box>
                  <Box sx={{ textAlign: 'right' }}>
                    <Typography sx={{ fontSize: '0.8rem', fontWeight: 700, color: '#EF4444' }}>−{fmtDec(d.depreciation_amount)}</Typography>
                    <Typography sx={{ fontSize: '0.68rem', color: '#94A3B8' }}>{fmtDec(d.book_value_after)}</Typography>
                  </Box>
                </Box>
              ))
            )
          )}
        </Box>

        {/* Footer Close Button */}
        <Box sx={{ p: 1.5, borderTop: '1px solid #F1F5F9', bgcolor: '#F8FAFC' }}>
          <Button
            variant="outlined"
            size="small"
            fullWidth
            onClick={() => setSelectedAsset(null)}
            sx={{
              borderRadius: '8px',
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.78rem',
              borderColor: '#E2E8F0',
              color: '#64748B',
              bgcolor: '#FFFFFF',
              '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' }
            }}
          >
            Close Schedule
          </Button>
        </Box>
      </Box>
    );
  };

  if (loading) return <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}><CircularProgress size={28} /></Box>;

  if (assets.length === 0) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 12, bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', px: 4, textAlign: 'center' }}>
        <Box sx={{ p: 2, bgcolor: '#EEF2FF', color: '#6366F1', borderRadius: '50%', mb: 2, display: 'flex' }}>
          <TrendingDownIcon sx={{ fontSize: 32 }} />
        </Box>
        <Typography sx={{ fontWeight: 700, fontSize: '1.1rem', color: '#0F172A', mb: 1 }}>No assets are currently depreciating.</Typography>
        <Typography sx={{ fontSize: '0.85rem', color: '#64748B', maxWidth: 380, mb: 3 }}>Add assets with depreciation settings to begin tracking value changes.</Typography>
      </Box>
    );
  }

  const health = getHealthCounts();
  const insights = getQuickInsights();
  const chartPoints = getHistoricalData();
  const currentErosion = chartPoints.length > 0 && chartPoints[0].original > 0
    ? (((chartPoints[0].original - dashboard.total_current_value) / chartPoints[0].original) * 100).toFixed(2)
    : '0.00';

  return (
    <Box>
      {/* KPI Row */}
      {dashboard && (
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <KpiCard label="Total Depreciated" value={fmtDec(dashboard.total_accumulated_depreciation)} sub="Across all assets" subColor="#16A34A" icon={<TrendingDownIcon />} />
          <KpiCard label="Current Portfolio Value" value={fmtDec(dashboard.total_current_value)} sub="Net asset value after depreciation" subColor="#64748B" icon={<AccountBalanceWalletIcon />} />
          <KpiCard label="Fully Depreciated" value={dashboard.fully_depreciated_count} sub="Assets at book value = salvage" subColor="#EA580C" icon={<WarningIcon />} />
          <KpiCard label="Assets Depreciating" value={dashboard.active_count} sub="Active assets" subColor="#6366F1" icon={<BusinessIcon />} />
        </Box>
      )}

      {/* Main Charts & Processing Rework */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap', flexDirection: { xs: 'column', lg: 'row' } }}>
        {/* Left Card: Portfolio Value Trend */}
        <Box sx={{ flex: 1.6, bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', p: 3, minWidth: { lg: 600 } }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.95rem', color: '#0F172A' }}>Portfolio Value Trend</Typography>
          <Typography sx={{ fontSize: '0.78rem', color: '#64748B', mb: 3 }}>Track how asset value changes over time due to depreciation.</Typography>
          
          <Box sx={{ display: 'flex', gap: 3, flexDirection: { xs: 'column', md: 'row' } }}>
            <Box sx={{ flex: 1.7, minHeight: 200 }}>
              {chartPoints.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={chartPoints} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F8FAFC" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={v => { const val = v / 1000; return `₹${val % 1 === 0 ? val.toFixed(0) : val.toFixed(1)}K`; }} tick={{ fontSize: 9, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <RechartsTooltip formatter={v => fmtDec(v)} contentStyle={{ borderRadius: '10px', border: '1px solid #F1F5F9', boxShadow: '0 4px 6px rgba(0,0,0,0.02)', fontSize: '0.8rem' }} />
                    <Line type="monotone" dataKey="original" stroke="#6366F1" strokeWidth={1.5} dot={{ r: 2.5, strokeWidth: 1 }} activeDot={{ r: 4 }} name="Original Value" />
                    <Line type="monotone" dataKey="current" stroke="#10B981" strokeWidth={1.5} dot={{ r: 2.5, strokeWidth: 1 }} activeDot={{ r: 4 }} name="Current Value" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: '#CBD5E1' }}>No historical trend data.</Box>
              )}
            </Box>
            
            {/* Trend Values Side-Panel */}
            <Box sx={{ flex: 0.8, display: 'flex', flexDirection: 'column', gap: 1.5, justifyContent: 'center' }}>
              <Box sx={{ bgcolor: '#EEF2FF', p: 1.5, borderRadius: '12px', border: '1px solid rgba(99, 102, 241, 0.08)' }}>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: '#4F46E5', mb: 0.2 }}>Original Value</Typography>
                <Typography sx={{ fontSize: '1.05rem', fontWeight: 700, color: '#4F46E5' }}>{fmt(dashboard?.total_purchase_cost)}</Typography>
              </Box>
              <Box sx={{ bgcolor: '#F0FDF4', p: 1.5, borderRadius: '12px', border: '1px solid rgba(16, 185, 129, 0.08)' }}>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: '#10B981', mb: 0.2 }}>Current Value</Typography>
                <Typography sx={{ fontSize: '1.05rem', fontWeight: 700, color: '#10B981' }}>{fmt(dashboard?.total_current_value)}</Typography>
              </Box>
              <Box sx={{ bgcolor: '#FFF1F2', p: 1.5, borderRadius: '12px', border: '1px solid rgba(244, 63, 94, 0.08)' }}>
                <Typography sx={{ fontSize: '0.65rem', fontWeight: 600, color: '#F43F5E', mb: 0.2 }}>Value Erosion</Typography>
                <Typography sx={{ fontSize: '1.05rem', fontWeight: 700, color: '#F43F5E' }}>{currentErosion}%</Typography>
                <Typography sx={{ fontSize: '0.62rem', color: '#94A3B8', mt: 0.2 }}>Since {chartPoints.length > 0 ? chartPoints[0].label : 'start'}</Typography>
              </Box>
            </Box>
          </Box>
        </Box>

        {/* Right Card: Depreciation Processing Panel */}
        <Box sx={{ flex: 1, bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', p: 3, display: 'flex', flexDirection: 'column', minWidth: { lg: 380 } }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.95rem', color: '#0F172A' }}>Depreciation Processing</Typography>
          <Typography sx={{ fontSize: '0.78rem', color: '#64748B', mb: 2.5 }}>Run and manage monthly depreciation for your assets.</Typography>

          <Box sx={{ display: 'flex', flex: 1, gap: 3, alignItems: 'stretch', flexDirection: { xs: 'column', md: 'row' } }}>

            {/* Left: Stat rows */}
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
              {[
                { label: 'Last Run Date',       value: getLastRunDate(),                                icon: <HistoryIcon sx={{ fontSize: 13 }} /> },
                { label: 'Assets Eligible',     value: assets.filter(a => a.status === 'active').length, icon: <BusinessIcon sx={{ fontSize: 13 }} /> },
                { label: 'Pending Entries',     value: 0,                                               icon: <WarningIcon sx={{ fontSize: 13 }} /> },
                { label: 'Monthly To Post',     value: fmtDec(getMonthlyAmountToPost()),                icon: <ReceiptLongIcon sx={{ fontSize: 13 }} /> },
                { label: 'Next Scheduled Run',  value: getNextScheduledRun(),                           icon: <CalendarTodayIcon sx={{ fontSize: 13 }} /> },
              ].map((item, i, arr) => (
                <Box key={item.label} sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1.25,
                  py: 1.1,
                  borderBottom: i < arr.length - 1 ? '1px solid #F8FAFC' : 'none',
                }}>
                  <Box sx={{ color: '#CBD5E1', display: 'flex', alignItems: 'center', width: 16, flexShrink: 0 }}>{item.icon}</Box>
                  <Typography noWrap sx={{ fontSize: '0.74rem', color: '#64748B', fontWeight: 500, flex: 1 }}>{item.label}</Typography>
                  <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, color: '#0F172A', flexShrink: 0 }}>{item.value}</Typography>
                </Box>
              ))}
            </Box>

            {/* Divider */}
            <Box sx={{ width: '1px', bgcolor: '#F1F5F9', display: { xs: 'none', md: 'block' }, flexShrink: 0 }} />

            {/* Right: Action buttons */}
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, justifyContent: 'center', minWidth: 160 }}>
              <Button
                variant="contained"
                onClick={() => setRunDialog(true)}
                startIcon={<PlayArrowIcon sx={{ fontSize: 13 }} />}
                sx={{
                  bgcolor: '#6366F1',
                  '&:hover': { bgcolor: '#4F46E5', boxShadow: '0 4px 12px rgba(99,102,241,0.25)' },
                  borderRadius: '8px',
                  textTransform: 'none',
                  fontWeight: 600,
                  fontSize: '0.76rem',
                  height: 34,
                  boxShadow: 'none',
                  px: 2,
                  letterSpacing: '0.01em',
                  transition: 'all 0.18s ease',
                  whiteSpace: 'nowrap',
                }}
              >
                Run Depreciation
              </Button>
              <Button
                variant="outlined"
                onClick={() => setJournalEntriesOpen(true)}
                startIcon={<AssignmentIcon sx={{ fontSize: 13 }} />}
                sx={{
                  borderColor: '#E2E8F0',
                  color: '#64748B',
                  borderRadius: '8px',
                  textTransform: 'none',
                  fontWeight: 600,
                  fontSize: '0.76rem',
                  height: 34,
                  px: 2,
                  whiteSpace: 'nowrap',
                  '&:hover': { borderColor: '#C7D2FE', bgcolor: '#EEF2FF', color: '#6366F1' },
                  transition: 'all 0.18s ease',
                }}
              >
                Journal Entries
              </Button>
            </Box>
          </Box>
        </Box>
      </Box>

      {/* Asset Health Overview & Quick Insights */}
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap', flexDirection: { xs: 'column', lg: 'row' } }}>
        {/* Left Column: Asset Health Overview */}
        <Box sx={{ flex: 1.6, bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', p: 3 }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.95rem', color: '#0F172A' }}>Asset Health Overview</Typography>
          <Typography sx={{ fontSize: '0.78rem', color: '#64748B', mb: 3.5 }}>Understand lifecycle status and remaining useful life of your assets.</Typography>
          
          <Box sx={{ display: 'flex', gap: 2, flexDirection: { xs: 'column', sm: 'row' } }}>
            {[
              { title: 'Healthy Assets', count: health.healthy, pct: health.healthyAvg, color: '#10B981', sub: 'More than 60% useful life remaining' },
              { title: 'Mid-Life Assets', count: health.mid, pct: health.midAvg, color: '#F59E0B', sub: 'Between 30% and 60% life remaining' },
              { title: 'Near End Of Life', count: health.nearEnd, pct: health.nearEndAvg, color: '#EF4444', sub: 'Less than 30% life remaining' },
            ].map(card => (
              <Box key={card.title} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', bgcolor: '#FAFAFA', border: '1px solid #F1F5F9', borderRadius: '12px', p: 2, flex: 1 }}>
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: card.color }} />
                    <Typography sx={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748B' }}>{card.title}</Typography>
                  </Box>
                  <Typography sx={{ fontSize: '1.2rem', fontWeight: 800, color: '#0F172A', mb: 0.5 }}>
                    {card.count} {card.count === 1 ? 'Asset' : 'Assets'}
                  </Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8', lineHeight: 1.25 }}>{card.sub}</Typography>
                </Box>
                <CircularHealthIndicator pct={card.pct} color={card.color} />
              </Box>
            ))}
          </Box>
        </Box>

        {/* Right Column: Quick Insights */}
        <Box sx={{ flex: 1, bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', p: 3, display: 'flex', flexDirection: 'column' }}>
          <Typography sx={{ fontWeight: 700, fontSize: '0.95rem', color: '#0F172A', mb: 0.5 }}>Quick Insights</Typography>
          <Typography sx={{ fontSize: '0.78rem', color: '#64748B', mb: 2 }}>Intelligent statistics from active asset logs.</Typography>
          
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, flex: 1, justifyContent: 'center' }}>
            {[
              {
                label: 'Most Depreciated Asset',
                name: insights.mostDepr?.name || '—',
                value: insights.mostDepr ? fmtDec(insights.mostDepr.accumulated_depreciation) : '—',
                sub: 'Depreciated',
              },
              {
                label: 'Highest Current Value',
                name: insights.highestVal?.name || '—',
                value: insights.highestVal ? fmtDec(insights.highestVal.current_value) : '—',
                sub: 'Current Value',
              },
              {
                label: 'Next Asset to Reach Salvage',
                name: insights.nextSalvage?.name || '—',
                value: insights.nextSalvage ? `Est. in ${(Number(insights.nextSalvage.useful_life_years || 5) - ((insights.nextSalvage.depreciations_count || 0) / 12)).toFixed(1)} years` : '—',
                sub: 'Estimated Time',
              },
            ].map((item, idx) => (
              <Box key={idx} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1.25, borderBottom: idx < 2 ? '1px solid #F8FAFC' : 'none' }}>
                <Box>
                  <Typography sx={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 600, textTransform: 'uppercase', mb: 0.3 }}>{item.label}</Typography>
                  <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 700 }}>{item.name}</Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography sx={{ fontSize: '0.8rem', fontWeight: 800, color: '#0F172A' }}>{item.value}</Typography>
                  <Typography sx={{ fontSize: '0.65rem', color: '#94A3B8' }}>{item.sub}</Typography>
                </Box>
              </Box>
            ))}
          </Box>
        </Box>
      </Box>

      {/* Depreciation Schedule Table Section */}
      <Box sx={{ display: 'flex', gap: 2 }}>
        <Box sx={{ flex: 1, bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', overflow: 'hidden' }}>
          <Box sx={{ p: 3, pb: 2, borderBottom: '1px solid #F8FAFC' }}>
            <Typography sx={{ fontWeight: 700, fontSize: '1.05rem', color: '#0F172A' }}>Depreciation Schedule</Typography>
            <Typography sx={{ fontSize: '0.8rem', color: '#94A3B8', mt: 0.3 }}>Review calculated values, life remaining, and current book value.</Typography>
          </Box>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress size={24} sx={{ color: '#6366F1' }} /></Box>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow sx={{ '& th': { borderBottom: '1px solid #F1F5F9', bgcolor: '#F8FAFC', py: 1.5 } }}>
                    {['Asset', 'Method', 'Remaining Life', 'Depreciation Progress', 'Cost', 'Accum. Depr.', 'Book Value', 'Actions'].map(h => (
                      <TableCell key={h} sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#94A3B8', letterSpacing: '0.04em', textTransform: 'uppercase' }}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {assets.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8} align="center" sx={{ py: 6, color: '#CBD5E1', fontSize: '0.88rem', border: 'none' }}>
                        No assets found.
                      </TableCell>
                    </TableRow>
                  )}
                  {assets.map(asset => {
                    const usefulLife = Number(asset.useful_life_years || 5);
                    const depCount = Number(asset.depreciations_count || 0);
                    const remainingLife = Math.max(0, usefulLife - (depCount / 12));
                    
                    const cost = Number(asset.purchase_cost || 0);
                    const accum = Number(asset.accumulated_depreciation || 0);
                    const progressPct = cost > 0 ? Math.min(100, (accum / cost) * 100) : 0;
                    
                    const isSelected = selectedAsset?.id === asset.id;

                    return (
                      <TableRow 
                        key={asset.id} 
                        hover 
                        onClick={() => loadDepreciations(asset)}
                        sx={{
                          cursor: 'pointer',
                          bgcolor: isSelected ? '#F8FAFC' : 'transparent',
                          '&:hover': { bgcolor: '#FAFAFA' },
                          '& td': { borderBottom: '1px solid #F8FAFC', py: 1.5 },
                        }}
                      >
                        {/* Asset name + code */}
                        <TableCell>
                          <Box>
                            <Typography sx={{ fontWeight: 600, fontSize: '0.82rem', color: '#0F172A' }}>{asset.name}</Typography>
                            <Typography sx={{ fontSize: '0.72rem', color: '#94A3B8', fontFamily: 'monospace' }}>{asset.asset_code}</Typography>
                          </Box>
                        </TableCell>
                        {/* Method */}
                        <TableCell>
                          <Typography sx={{ fontSize: '0.78rem', color: '#64748B', fontWeight: 600, textTransform: 'uppercase' }}>
                            {asset.depreciation_method}
                          </Typography>
                        </TableCell>
                        {/* Remaining Life */}
                        <TableCell>
                          <Typography sx={{ fontSize: '0.78rem', color: '#0F172A', fontWeight: 600 }}>
                            {remainingLife.toFixed(1)} yrs
                          </Typography>
                          <Typography sx={{ fontSize: '0.68rem', color: '#94A3B8' }}>
                            of {usefulLife} yrs
                          </Typography>
                        </TableCell>
                        {/* Depreciation Progress */}
                        <TableCell sx={{ minWidth: 140 }}>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                            <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: '#475569' }}>
                              {progressPct.toFixed(1)}%
                            </Typography>
                          </Box>
                          <Box sx={{ bgcolor: '#F1F5F9', borderRadius: '99px', height: 4, overflow: 'hidden' }}>
                            <Box sx={{
                              width: `${progressPct}%`,
                              height: '100%',
                              borderRadius: '99px',
                              bgcolor: '#6366F1',
                              transition: 'width 0.3s ease',
                            }} />
                          </Box>
                        </TableCell>
                        {/* Cost */}
                        <TableCell>
                          <Typography sx={{ fontSize: '0.82rem', fontWeight: 500, color: '#0F172A' }}>{fmtDec(asset.purchase_cost)}</Typography>
                        </TableCell>
                        {/* Accum. Depr */}
                        <TableCell>
                          <Typography sx={{ fontSize: '0.82rem', fontWeight: 500, color: '#EA580C' }}>{fmtDec(asset.accumulated_depreciation)}</Typography>
                        </TableCell>
                        {/* Book Value */}
                        <TableCell>
                          <Typography sx={{ fontSize: '0.82rem', fontWeight: 600, color: '#10B981' }}>{fmtDec(asset.current_value)}</Typography>
                        </TableCell>
                        {/* Actions */}
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Button
                            size="small"
                            onClick={() => setDetailDrawerAsset(asset)}
                            sx={{
                              textTransform: 'none',
                              fontSize: '0.75rem',
                              fontWeight: 600,
                              color: '#6366F1',
                              '&:hover': { bgcolor: '#EEF2FF' },
                              px: 1.5,
                              py: 0.5,
                              borderRadius: '6px'
                            }}
                          >
                            Details &gt;
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>

        <Box sx={{
          width: selectedAsset ? 320 : 0,
          opacity: selectedAsset ? 1 : 0,
          transition: 'width 300ms cubic-bezier(0.4, 0, 0.2, 1), opacity 250ms cubic-bezier(0.4, 0, 0.2, 1), border-color 300ms ease',
          bgcolor: '#FFFFFF',
          border: '1px solid',
          borderColor: selectedAsset ? '#F1F5F9' : 'transparent',
          borderRadius: '16px',
          overflow: 'hidden',
          flexShrink: 0,
          display: { xs: 'none', md: 'block' }
        }}>
          {activeAsset && renderScheduleContent(false)}
        </Box>
      </Box>

      {/* Mobile/Tablet schedule drawer */}
      <Drawer
        anchor="right"
        open={Boolean(selectedAsset)}
        onClose={() => setSelectedAsset(null)}
        slotProps={{
          backdrop: { sx: { backdropFilter: 'blur(4px)', backgroundColor: 'rgba(15, 23, 42, 0.15)' } }
        }}
        sx={{
          display: { xs: 'block', md: 'none' }
        }}
        PaperProps={{
          sx: {
            width: { xs: '100%', sm: 360 },
            p: 0,
            bgcolor: '#FFFFFF',
            display: 'flex',
            flexDirection: 'column',
          }
        }}
      >
        {renderScheduleContent(true)}
      </Drawer>

      <RunDepreciationDialog open={runDialog} onClose={() => setRunDialog(false)} onDone={fetchAll} />
      <JournalEntriesDialog open={journalEntriesOpen} onClose={() => setJournalEntriesOpen(false)} assets={assets} />
      <AssetDepreciationDrawer open={Boolean(detailDrawerAsset)} onClose={() => setDetailDrawerAsset(null)} asset={detailDrawerAsset} />
    </Box>
  );
}

// ─── Disposal & Audit Tab ─────────────────────────────────────────────────────
function DisposalAuditTab({ activeSubTab, setActiveSubTab, disposals, auditLogs, loading, onRefresh }) {
  const fetchAll = onRefresh;

  const totalGain = disposals.filter(d => d.gain_loss >= 0).reduce((s, d) => s + Number(d.gain_loss), 0);
  const totalLoss = disposals.filter(d => d.gain_loss < 0).reduce((s, d) => s + Math.abs(Number(d.gain_loss)), 0);

  const ACTION_COLORS = {
    created: { bg: '#F0FDF4', color: '#16A34A' }, assigned: { bg: '#EFF6FF', color: '#2563EB' },
    returned: { bg: '#FFFBEB', color: '#D97706' }, depreciated: { bg: '#FFF7ED', color: '#EA580C' },
    disposed: { bg: '#FEF2F2', color: '#DC2626' }, updated: { bg: '#F8FAFC', color: '#64748B' },
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <KpiCard label="Total Disposals" value={disposals.length} sub="All time" />
        <KpiCard label="Total Gain" value={fmtDec(totalGain)} sub="Proceeds > Book Value" subColor="#16A34A" />
        <KpiCard label="Total Loss" value={fmtDec(totalLoss)} sub="Book Value > Proceeds" subColor="#DC2626" />
      </Box>

      <Box sx={{ bgcolor: '#FFFFFF', border: '1px solid #F1F5F9', borderRadius: '16px', overflow: 'hidden' }}>
        <Box sx={{ borderBottom: '1px solid #F1F5F9' }}>
          <Tabs value={activeSubTab} onChange={(_, v) => setActiveSubTab(v)}
            sx={{ px: 3, '& .MuiTab-root': { textTransform: 'none', fontWeight: 600, fontSize: '0.85rem', minHeight: 48 }, '& .MuiTabs-indicator': { bgcolor: '#6366F1' } }}>
            <Tab label="Disposal Records" />
            <Tab label="Audit Trail" />
          </Tabs>
        </Box>

        {loading ? <Box sx={{ py: 6, display: 'flex', justifyContent: 'center' }}><CircularProgress size={24} /></Box> : (
          <>
            {activeSubTab === 0 && (
              <Table>
                <TableHead>
                  <TableRow sx={{ '& th': { bgcolor: '#F8FAFC', borderBottom: '1px solid #F1F5F9' } }}>
                    {['Asset', 'Disposal Date', 'Method', 'Sale Proceeds', 'Book Value', 'Gain / Loss', 'Notes'].map(h => (
                      <TableCell key={h} sx={{ fontWeight: 600, fontSize: '0.7rem', color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {disposals.length === 0 && (
                    <TableRow><TableCell colSpan={7} align="center" sx={{ py: 6, color: '#CBD5E1', border: 'none' }}>No disposals recorded yet.</TableCell></TableRow>
                  )}
                  {disposals.map(d => (
                    <TableRow key={d.id} hover sx={{ '& td': { borderBottom: '1px solid #F8FAFC', py: 1.5 } }}>
                      <TableCell sx={{ fontWeight: 600, fontSize: '0.78rem', color: '#6366F1' }}>#{d.asset}</TableCell>
                      <TableCell sx={{ fontSize: '0.78rem', color: '#64748B' }}>{d.disposal_date}</TableCell>
                      <TableCell>
                        <Box sx={{ display: 'inline-flex', px: 1.5, py: 0.3, bgcolor: '#F8FAFC', color: '#64748B', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 600, textTransform: 'capitalize' }}>{d.method}</Box>
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.82rem', fontWeight: 500, color: '#0F172A' }}>{fmtDec(d.sale_proceeds)}</TableCell>
                      <TableCell sx={{ fontSize: '0.82rem', color: '#64748B' }}>{fmtDec(d.book_value_at_disposal)}</TableCell>
                      <TableCell>
                        <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: Number(d.gain_loss) >= 0 ? '#16A34A' : '#DC2626' }}>
                          {Number(d.gain_loss) >= 0 ? '+' : ''}{fmtDec(d.gain_loss)}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ fontSize: '0.78rem', color: '#94A3B8' }}>{d.notes || '—'}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            {activeSubTab === 1 && (
              <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 1 }}>
                {auditLogs.length === 0 && <Typography sx={{ color: '#CBD5E1', textAlign: 'center', py: 4 }}>No audit logs yet.</Typography>}
                {auditLogs.map(log => {
                  const ac = ACTION_COLORS[log.action] || ACTION_COLORS.updated;
                  return (
                    <Box key={log.id} sx={{ display: 'flex', gap: 2, p: 2, border: '1px solid #F1F5F9', borderRadius: '12px', alignItems: 'flex-start', '&:hover': { bgcolor: '#FAFAFA' } }}>
                      <Box sx={{ px: 1.5, py: 0.5, borderRadius: '6px', fontSize: '0.7rem', fontWeight: 700, bgcolor: ac.bg, color: ac.color, whiteSpace: 'nowrap', mt: 0.3 }}>
                        {log.action}
                      </Box>
                      <Box sx={{ flex: 1 }}>
                        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                          <Typography sx={{ fontWeight: 600, fontSize: '0.8rem', color: '#6366F1' }}>{log.asset_code}</Typography>
                          <Typography sx={{ fontSize: '0.8rem', color: '#0F172A' }}>{log.asset_name}</Typography>
                        </Box>
                        <Typography sx={{ fontSize: '0.75rem', color: '#94A3B8', mt: 0.3 }}>{log.notes}</Typography>
                      </Box>
                      <Box sx={{ textAlign: 'right', flexShrink: 0 }}>
                        <Typography sx={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 500 }}>{log.performed_by}</Typography>
                        <Typography sx={{ fontSize: '0.68rem', color: '#CBD5E1', mt: 0.3 }}>
                          {new Date(log.created_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </Typography>
                      </Box>
                    </Box>
                  );
                })}
              </Box>
            )}
          </>
        )}
      </Box>
    </Box>
  );
}


// Global memory cache for assets data to prevent loading on remount
let assetsCache = {
  assets: null,
  dashboard: null,
  disposals: null,
  auditLogs: null,
};


// ─── Main Component ───────────────────────────────────────────────────────────
export default function AccountingAssetManagement() {
  const [tab, setTab] = useState(0);
  const [addDrawer, setAddDrawer] = useState(false);
  const [exportAnchor, setExportAnchor] = useState(null);
  const [disposalSubTab, setDisposalSubTab] = useState(0);

  const TAB_LABELS = ['Asset Register', 'Depreciation Center', 'Disposal & Audit'];

  const [assets, setAssets] = useState(assetsCache.assets || []);
  const [dashboard, setDashboard] = useState(assetsCache.dashboard || null);
  const [disposals, setDisposals] = useState(assetsCache.disposals || []);
  const [auditLogs, setAuditLogs] = useState(assetsCache.auditLogs || []);
  const [loading, setLoading] = useState(!assetsCache.assets);

  const fetchAllData = useCallback(async (showLoading = true) => {
    const shouldShowLoading = showLoading && !assetsCache.assets;
    if (shouldShowLoading) setLoading(true);
    try {
      const [assetsRes, dashRes, dispRes, auditRes] = await Promise.all([
        apiClient(`${API}/assets/`).then(r => r.json()),
        apiClient(`${API}/assets/dashboard/`).then(r => r.json()),
        apiClient(`${API}/assets/disposals/`).then(r => r.json()),
        apiClient(`${API}/assets/audit/`).then(r => r.json()),
      ]);
      const fetchedAssets = assetsRes.data || [];
      const fetchedDashboard = dashRes.data || null;
      const fetchedDisposals = dispRes.data || [];
      const fetchedAuditLogs = auditRes.data || [];

      // Update cache
      assetsCache = {
        assets: fetchedAssets,
        dashboard: fetchedDashboard,
        disposals: fetchedDisposals,
        auditLogs: fetchedAuditLogs,
      };

      setAssets(fetchedAssets);
      setDashboard(fetchedDashboard);
      setDisposals(fetchedDisposals);
      setAuditLogs(fetchedAuditLogs);
    } catch (e) {
      console.error("Failed to load asset management data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData(true);
  }, [fetchAllData]);

  const fetchExportData = (mainTab, subTab) => {
    if (mainTab === 2) {
      return subTab === 1 ? auditLogs : disposals;
    }
    return assets;
  };

  // ── Build export spec from data ──────────────────────────────────────────────
  const buildSpec = (data, mainTab, subTab) => {
    const date = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
    const safeDate = new Date().toISOString().slice(0, 10);
    if (mainTab === 0) {
      return {
        title: 'Asset Register', subtitle: 'Fixed Asset Management · Shori',
        filename: `asset_register_${safeDate}`, count: data.length, date,
        headers: ['Asset Code','Name','Category','Department','Purchase Date','Cost (₹)','Book Value (₹)','Accumulated Dep. (₹)','Salvage (₹)','Useful Life','Method','Rate (%)','Status','Assigned To','Vendor','Location','Serial No.'],
        rows: data.map(a => [
          a.asset_code, (a.name||'').replace(/,/g,' '),
          CATEGORY_LABELS[a.category]||a.category, a.department||'',
          a.purchase_date||'', Number(a.purchase_cost||0).toFixed(2),
          Number(a.current_value||0).toFixed(2), Number(a.accumulated_depreciation||0).toFixed(2),
          Number(a.salvage_value||0).toFixed(2), a.useful_life_years||'',
          (a.depreciation_method||'').toUpperCase(), a.depreciation_rate||'',
          STATUS_COLORS[a.status]?.label||a.status, a.current_assignment?.assigned_to||'',
          a.vendor||'', a.location||'', a.serial_number||'',
        ]),
      };
    }
    if (mainTab === 1) {
      return {
        title: 'Depreciation Summary', subtitle: 'Depreciation Center · Shori',
        filename: `depreciation_summary_${safeDate}`, count: data.length, date,
        headers: ['Asset Code','Name','Category','Purchase Date','Cost (₹)','Book Value (₹)','Accumulated Dep. (₹)','Method','Rate (%)','Useful Life','Status'],
        rows: data.map(a => [
          a.asset_code, (a.name||'').replace(/,/g,' '),
          CATEGORY_LABELS[a.category]||a.category, a.purchase_date||'',
          Number(a.purchase_cost||0).toFixed(2), Number(a.current_value||0).toFixed(2),
          Number(a.accumulated_depreciation||0).toFixed(2),
          (a.depreciation_method||'').toUpperCase(), a.depreciation_rate||'',
          a.useful_life_years||'', STATUS_COLORS[a.status]?.label||a.status,
        ]),
      };
    }
    if (mainTab === 2 && subTab === 0) {
      return {
        title: 'Disposal Records', subtitle: 'Disposal & Audit · Shori',
        filename: `disposal_records_${safeDate}`, count: data.length, date,
        headers: ['Asset ID','Disposal Date','Method','Sale Proceeds (₹)','Book Value (₹)','Gain / Loss (₹)','Notes'],
        rows: data.map(d => [
          d.asset, d.disposal_date||'', (d.method||'').toUpperCase(),
          Number(d.sale_proceeds||0).toFixed(2), Number(d.book_value_at_disposal||0).toFixed(2),
          Number(d.gain_loss||0).toFixed(2), (d.notes||'').replace(/,/g,' '),
        ]),
      };
    }
    // mainTab === 2 && subTab === 1 (Audit Trail)
    return {
      title: 'Audit Trail', subtitle: 'Disposal & Audit · Shori',
      filename: `audit_trail_${safeDate}`, count: data.length, date,
      headers: ['Date & Time', 'Action', 'Asset Code', 'Asset Name', 'Notes', 'Performed By'],
      rows: data.map(log => [
        new Date(log.created_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }),
        (log.action||'').toUpperCase(),
        log.asset_code||'',
        (log.asset_name||'').replace(/,/g,' '),
        (log.notes||'').replace(/,/g,' '),
        log.performed_by||'',
      ]),
    };
  };

  const triggerPrint = (html) => {
    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'position:fixed;top:-9999px;left:-9999px;width:1px;height:1px;border:none;';
    document.body.appendChild(iframe);
    const doc = iframe.contentDocument || iframe.contentWindow.document;
    doc.open(); doc.write(html); doc.close();
    requestAnimationFrame(() => {
      iframe.contentWindow.focus();
      iframe.contentWindow.print();
      setTimeout(() => { try { document.body.removeChild(iframe); } catch(_) {} }, 500);
    });
  };

  const exportCSV = async () => {
    setExportAnchor(null);
    try {
      const data = await fetchExportData(tab, disposalSubTab);
      if (!data) return;
      const spec = buildSpec(data, tab, disposalSubTab);
      const csv = [spec.headers.join(','), ...spec.rows.map(r => r.map(c => `"${String(c??'').replace(/"/g,'""')}"`).join(','))].join('\n');
      const url = URL.createObjectURL(new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' }));
      const link = document.createElement('a');
      link.href = url; link.download = `${spec.filename}.csv`;
      document.body.appendChild(link); link.click(); document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch(e) { console.error('CSV export failed:', e); }
  };

  const exportPDF = async () => {
    setExportAnchor(null);
    try {
      const data = await fetchExportData(tab, disposalSubTab);
      if (!data) return;
      const spec = buildSpec(data, tab, disposalSubTab);
      triggerPrint(`<!DOCTYPE html><html><head><title>${spec.title}</title>
        <style>
          *{box-sizing:border-box;margin:0;padding:0}
          body{font-family:'Segoe UI',Arial,sans-serif;color:#0F172A;background:#fff;padding:32px;font-size:10px}
          .hdr{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid #6366F1}
          h1{font-size:18px;font-weight:700;color:#0F172A;letter-spacing:-0.02em}
          .sub{font-size:9px;color:#64748B;margin-top:4px}
          .meta{font-size:9px;color:#64748B;text-align:right;line-height:1.8}
          .meta strong{color:#0F172A}
          table{width:100%;border-collapse:collapse;margin-top:4px}
          thead tr{background:#6366F1}
          th{color:#fff;font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.02em;padding:5px 4px;text-align:left;vertical-align:top;word-wrap:break-word}
          td{padding:5px 4px;font-size:7.5px;color:#1E293B;border-bottom:1px solid #F1F5F9;vertical-align:top;word-wrap:break-word}
          tr:nth-child(even) td{background:#F8FAFC}
          td:first-child{font-weight:700;color:#6366F1}
          .ftr{margin-top:20px;font-size:9px;color:#94A3B8;text-align:center}
          @page{size:A4 portrait;margin:12mm 10mm}
          @media print{body{padding:0}}
        </style>
      </head><body>
        <div class="hdr">
          <div><h1>${spec.title}</h1><div class="sub">${spec.subtitle}</div></div>
          <div class="meta">
            <div>Exported on <strong>${spec.date}</strong></div>
            <div>Records: <strong>${spec.count}</strong></div>
          </div>
        </div>
        <table>
          <thead><tr>${spec.headers.map(c=>`<th>${c}</th>`).join('')}</tr></thead>
          <tbody>${spec.rows.length === 0
            ? `<tr><td colspan="${spec.headers.length}" style="text-align:center;color:#94A3B8;padding:24px 0;font-size:9px;border-bottom:1px solid #F1F5F9;">No records found</td></tr>`
            : spec.rows.map(r=>`<tr>${r.map(c=>`<td>${c??'—'}</td>`).join('')}</tr>`).join('')}</tbody>
        </table>
        <div class="ftr">Generated by Shori · Confidential</div>
      </body></html>`);
    } catch(e) { console.error('PDF export failed:', e); }
  };

  return (
    <Box sx={{ bgcolor: '#FAFAFA', minHeight: '100%', p: 0 }}>
      {/* Tab Navigation + Action Buttons */}
      <Box sx={{ borderBottom: '1px solid #F1F5F9', mb: 3, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{
          '& .MuiTab-root': { textTransform: 'none', fontWeight: 600, fontSize: '0.85rem', minHeight: 44, color: '#94A3B8', px: 0, mr: 3 },
          '& .MuiTab-root.Mui-selected': { color: '#0F172A' },
          '& .MuiTabs-indicator': { bgcolor: '#0F172A', height: 2 },
        }}>
          {TAB_LABELS.map((label, i) => <Tab key={i} label={label} />)}
        </Tabs>

        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', pb: 0.5 }}>
          {/* Export dropdown */}
          <Button
            startIcon={<FileDownloadOutlinedIcon sx={{ fontSize: 14 }} />}
            onClick={e => setExportAnchor(e.currentTarget)}
            sx={{ borderRadius: '8px', textTransform: 'none', fontWeight: 600, fontSize: '0.78rem', color: '#64748B', border: '1px solid #E2E8F0', bgcolor: '#FFFFFF', px: 1.75, height: 32, '&:hover': { bgcolor: '#F8FAFC', borderColor: '#CBD5E1' } }}>
            Export
          </Button>
          <Menu
            anchorEl={exportAnchor}
            open={Boolean(exportAnchor)}
            onClose={() => setExportAnchor(null)}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            PaperProps={{ sx: { borderRadius: '12px', border: '1px solid #F1F5F9', boxShadow: '0 4px 20px rgba(0,0,0,0.08)', minWidth: 180, mt: 0.5 } }}
          >
            <MenuItem onClick={exportCSV} sx={{ fontSize: '0.82rem', fontWeight: 500, color: '#0F172A', py: 1.25, gap: 1.5 }}>
              <FileDownloadOutlinedIcon sx={{ fontSize: 16, color: '#64748B' }} />
              Export as CSV
            </MenuItem>
            <MenuItem onClick={exportPDF} sx={{ fontSize: '0.82rem', fontWeight: 500, color: '#0F172A', py: 1.25, gap: 1.5 }}>
              <AssignmentIcon sx={{ fontSize: 16, color: '#64748B' }} />
              Export as PDF
            </MenuItem>
          </Menu>

          {/* Add Asset */}
          <Button
            variant="contained"
            startIcon={<AddIcon sx={{ fontSize: 15 }} />}
            onClick={() => setAddDrawer(true)}
            sx={{ bgcolor: '#6366F1', '&:hover': { bgcolor: '#4F46E5', boxShadow: '0 4px 12px rgba(99,102,241,0.2)' }, borderRadius: '8px', textTransform: 'none', fontWeight: 600, fontSize: '0.78rem', px: 1.75, height: 32, boxShadow: 'none' }}>
            Add Asset
          </Button>
        </Box>
      </Box>

      {/* Tab Content */}
      <Box sx={{ display: tab === 0 ? 'block' : 'none' }}>
        <AssetRegisterTab assets={assets} dashboard={dashboard} loading={loading} onRefresh={() => fetchAllData(false)} />
      </Box>
      <Box sx={{ display: tab === 1 ? 'block' : 'none' }}>
        <DepreciationCenterTab assets={assets} dashboard={dashboard} loading={loading} onRefresh={() => fetchAllData(false)} />
      </Box>
      <Box sx={{ display: tab === 2 ? 'block' : 'none' }}>
        <DisposalAuditTab activeSubTab={disposalSubTab} setActiveSubTab={setDisposalSubTab} disposals={disposals} auditLogs={auditLogs} loading={loading} onRefresh={() => fetchAllData(false)} />
      </Box>

      <AddAssetDrawer open={addDrawer} onClose={() => setAddDrawer(false)} onCreated={() => { fetchAllData(false); setTab(0); }} />
    </Box>
  );
}
