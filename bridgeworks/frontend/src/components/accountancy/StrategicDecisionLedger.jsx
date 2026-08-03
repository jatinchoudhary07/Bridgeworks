import { useState } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Stack,
  Chip,
  TextField,
  MenuItem,
  InputAdornment,
  Tabs,
  Tab,
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import PendingIcon from '@mui/icons-material/HourglassEmpty';
import ScheduleIcon from '@mui/icons-material/Schedule';
import FilterListIcon from '@mui/icons-material/FilterList';

const COLORS = {
  bg: '#F8FAFC',
  card: '#FFFFFF',
  border: '#E2E8F0',
  primaryText: '#0F172A',
  secondaryText: '#64748B',
  accent: '#6366F1',
  success: '#10B981',
  successBg: '#E6F4EA',
  warning: '#F59E0B',
  warningBg: '#FEF9F0',
  danger: '#EF4444',
  dangerBg: '#FEE2E2',
  info: '#3B82F6',
  infoBg: '#DBEAFE',
};

const INITIAL_DECISIONS = [
  { id: 1, title: 'Approve Payroll May 2026', dept: 'Operations & Payroll', impact: '₹2.75L', deadline: 'In 4 Days', priority: 'Critical', status: 'Pending' },
  { id: 2, title: 'GST GSTR-3B Filing', dept: 'Compliance', impact: '₹42K', deadline: 'In 12 Days', priority: 'Critical', status: 'Pending' },
  { id: 3, title: 'Receivable Follow-Up (Acme Corp)', dept: 'Finance', impact: '₹85K', deadline: 'In 5 Days', priority: 'High', status: 'Pending' },
  { id: 4, title: 'Bank Reconciliation (HDFC Account)', dept: 'Banking', impact: '₹0 (Process)', deadline: 'In 2 Days', priority: 'Medium', status: 'Pending' },
  { id: 5, title: 'Asset Depreciation Run', dept: 'Assets', impact: '₹18.5K', deadline: 'In 7 Days', priority: 'Low', status: 'Pending' },
  { id: 6, title: 'Verify Capital Injection Audit', dept: 'Executive', impact: '₹15L', deadline: '3 Days Ago', priority: 'High', status: 'Overdue' },
  { id: 7, title: 'Approve Vendor Invoice INV-8991', dept: 'Operations', impact: '₹1.2L', deadline: 'Yesterday', priority: 'Medium', status: 'Completed' },
  { id: 8, title: 'Claim GST ITC Credit Q1', dept: 'Compliance', impact: '₹18.5K', deadline: '5 Days Ago', priority: 'High', status: 'Completed' },
];

export default function StrategicDecisionLedger() {
  const [decisions, setDecisions] = useState(INITIAL_DECISIONS);
  const [search, setSearch] = useState('');
  const [filterDept, setFilterDept] = useState('All');
  const [filterPriority, setFilterPriority] = useState('All');
  const [activeTab, setActiveTab] = useState(0);

  const handleAction = (id, newStatus) => {
    setDecisions(prev =>
      prev.map(item => (item.id === id ? { ...item, status: newStatus } : item))
    );
  };

  const getPriorityColor = (priority) => {
    if (priority === 'Critical') return { color: COLORS.danger, bg: COLORS.dangerBg };
    if (priority === 'High') return { color: COLORS.warning, bg: COLORS.warningBg };
    if (priority === 'Medium') return { color: COLORS.info, bg: COLORS.infoBg };
    return { color: COLORS.secondaryText, bg: '#F1F5F9' };
  };

  const getStatusColor = (status) => {
    if (status === 'Completed') return { color: COLORS.success, bg: COLORS.successBg };
    if (status === 'Overdue') return { color: COLORS.danger, bg: COLORS.dangerBg };
    if (status === 'Rejected') return { color: '#64748B', bg: '#F1F5F9' };
    if (status === 'Deferred') return { color: COLORS.accent, bg: '#EEF2FF' };
    return { color: COLORS.warning, bg: COLORS.warningBg };
  };

  // Stats calculation
  const totalPending = decisions.filter(d => d.status === 'Pending').length;
  const totalCompleted = decisions.filter(d => d.status === 'Completed').length;
  const totalOverdue = decisions.filter(d => d.status === 'Overdue').length;

  const filteredDecisions = decisions.filter(d => {
    // Search
    const matchesSearch = d.title.toLowerCase().includes(search.toLowerCase()) ||
                          d.dept.toLowerCase().includes(search.toLowerCase());
    
    // Department Filter
    const matchesDept = filterDept === 'All' || d.dept.includes(filterDept);

    // Priority Filter
    const matchesPriority = filterPriority === 'All' || d.priority === filterPriority;

    // Tab Filter
    let matchesTab = true;
    if (activeTab === 1) matchesTab = d.status === 'Pending';
    if (activeTab === 2) matchesTab = d.status === 'Completed';
    if (activeTab === 3) matchesTab = d.status === 'Overdue';

    return matchesSearch && matchesDept && matchesPriority && matchesTab;
  });

  const departments = ['All', 'Finance', 'Compliance', 'Banking', 'Assets', 'Executive', 'Operations'];

  return (
    <Box sx={{ bgcolor: COLORS.bg, minHeight: '100%', p: 3, fontFamily: 'Inter, sans-serif' }}>
      
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <Box>
          <Typography sx={{ fontSize: '24px', fontWeight: 800, color: COLORS.primaryText, lineHeight: 1.2 }}>
            Strategic Decision Ledger
          </Typography>
          <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText, mt: 0.5 }}>
            Review, authorize, and track key CFO operations and critical approvals
          </Typography>
        </Box>
        <Chip 
          label="SOX Compliance Active" 
          color="success" 
          variant="outlined" 
          size="small" 
          sx={{ fontWeight: 700, borderRadius: '6px' }}
        />
      </Box>

      {/* KPI Stats Panel */}
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 2, mb: 3 }}>
        <Box sx={{ bgcolor: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: '12px', p: 2.5, boxShadow: '0 1px 3px 0 rgba(15,23,42,0.05)' }}>
          <Typography sx={{ fontSize: '11px', fontWeight: 700, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Pending Authorization
          </Typography>
          <Typography sx={{ fontSize: '28px', fontWeight: 900, color: COLORS.warning, mt: 0.5 }}>
            {totalPending}
          </Typography>
          <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, mt: 0.5 }}>
            Requires immediate review to maintain runway
          </Typography>
        </Box>

        <Box sx={{ bgcolor: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: '12px', p: 2.5, boxShadow: '0 1px 3px 0 rgba(15,23,42,0.05)' }}>
          <Typography sx={{ fontSize: '11px', fontWeight: 700, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Completed Approvals
          </Typography>
          <Typography sx={{ fontSize: '28px', fontWeight: 900, color: COLORS.success, mt: 0.5 }}>
            {totalCompleted}
          </Typography>
          <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, mt: 0.5 }}>
            Audited & stored in blockchain general ledger
          </Typography>
        </Box>

        <Box sx={{ bgcolor: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: '12px', p: 2.5, boxShadow: '0 1px 3px 0 rgba(15,23,42,0.05)' }}>
          <Typography sx={{ fontSize: '11px', fontWeight: 700, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Overdue Decisions
          </Typography>
          <Typography sx={{ fontSize: '28px', fontWeight: 900, color: COLORS.danger, mt: 0.5 }}>
            {totalOverdue}
          </Typography>
          <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, mt: 0.5 }}>
            Exceeded deadline, causing operational risk
          </Typography>
        </Box>
      </Box>

      {/* Filter Toolbar */}
      <Box sx={{ bgcolor: COLORS.card, border: `1px solid ${COLORS.border}`, borderRadius: '12px', p: 2, mb: 3 }}>
        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="center">
          <TextField
            placeholder="Search decisions or keywords..."
            size="small"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ flexGrow: 1 }}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                  </InputAdornment>
                ),
              },
            }}
          />

          <TextField
            select
            label="Department"
            size="small"
            value={filterDept}
            onChange={(e) => setFilterDept(e.target.value)}
            sx={{ minWidth: 150 }}
          >
            {departments.map((d) => (
              <MenuItem key={d} value={d}>{d}</MenuItem>
            ))}
          </TextField>

          <TextField
            select
            label="Priority"
            size="small"
            value={filterPriority}
            onChange={(e) => setFilterPriority(e.target.value)}
            sx={{ minWidth: 130 }}
          >
            {['All', 'Critical', 'High', 'Medium', 'Low'].map((p) => (
              <MenuItem key={p} value={p}>{p}</MenuItem>
            ))}
          </TextField>
        </Stack>
      </Box>

      {/* Tabs */}
      <Tabs 
        value={activeTab} 
        onChange={(e, v) => setActiveTab(v)} 
        sx={{ 
          borderBottom: 1, 
          borderColor: 'divider', 
          mb: 2,
          '& .MuiTab-root': { textTransform: 'none', fontWeight: 700, fontSize: '13px' },
          '& .Mui-selected': { color: `${COLORS.accent} !important` },
          '& .MuiTabs-indicator': { bgcolor: COLORS.accent }
        }}
      >
        <Tab label={`All (${decisions.length})`} />
        <Tab label={`Pending (${decisions.filter(d => d.status === 'Pending').length})`} />
        <Tab label={`Completed (${decisions.filter(d => d.status === 'Completed').length})`} />
        <Tab label={`Overdue (${decisions.filter(d => d.status === 'Overdue').length})`} />
      </Tabs>

      {/* Ledger Table */}
      <TableContainer component={Paper} sx={{ borderRadius: '12px', border: `1px solid ${COLORS.border}`, boxShadow: 'none', overflow: 'hidden' }}>
        <Table>
          <TableHead sx={{ bgcolor: '#F8FAFC' }}>
            <TableRow>
              <TableCell sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.secondaryText }}>DECISION ITEM</TableCell>
              <TableCell sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.secondaryText }}>DEPARTMENT</TableCell>
              <TableCell sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.secondaryText }}>FINANCIAL IMPACT</TableCell>
              <TableCell sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.secondaryText }}>DEADLINE</TableCell>
              <TableCell sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.secondaryText }}>PRIORITY</TableCell>
              <TableCell sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.secondaryText }}>STATUS</TableCell>
              <TableCell sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.secondaryText }} align="right">ACTIONS</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredDecisions.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                  <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText }}>
                    No decisions found matching the filter criteria.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              filteredDecisions.map((row) => {
                const prio = getPriorityColor(row.priority);
                const stat = getStatusColor(row.status);
                return (
                  <TableRow key={row.id} hover sx={{ '&:last-child td, &:last-child th': { border: 0 } }}>
                    <TableCell>
                      <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>
                        {row.title}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography sx={{ fontSize: '12px', color: COLORS.secondaryText, fontWeight: 500 }}>
                        {row.dept}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography sx={{ fontSize: '12px', color: COLORS.primaryText, fontWeight: 700 }}>
                        {row.impact}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography sx={{ fontSize: '12px', color: row.status === 'Overdue' ? COLORS.danger : COLORS.secondaryText, fontWeight: 600 }}>
                        {row.deadline}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ px: 1, py: 0.3, borderRadius: '4px', bgcolor: prio.bg, color: prio.color, fontSize: '10px', fontWeight: 800, width: 'fit-content' }}>
                        {row.priority}
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ px: 1, py: 0.3, borderRadius: '4px', bgcolor: stat.bg, color: stat.color, fontSize: '10px', fontWeight: 800, width: 'fit-content' }}>
                        {row.status}
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      {row.status !== 'Completed' && row.status !== 'Rejected' ? (
                        <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                          <Button 
                            variant="contained" 
                            size="small" 
                            onClick={() => handleAction(row.id, 'Completed')}
                            sx={{ bgcolor: COLORS.success, color: '#fff', fontSize: '10px', fontWeight: 700, textTransform: 'none', px: 1.2, height: 26, minWidth: 0, '&:hover': { bgcolor: '#0D9488' } }}
                          >
                            Approve
                          </Button>
                          <Button 
                            variant="outlined" 
                            size="small" 
                            onClick={() => handleAction(row.id, 'Deferred')}
                            sx={{ borderColor: COLORS.border, color: COLORS.accent, fontSize: '10px', fontWeight: 700, textTransform: 'none', px: 1.2, height: 26, minWidth: 0 }}
                          >
                            Defer
                          </Button>
                          <Button 
                            variant="outlined" 
                            size="small" 
                            onClick={() => handleAction(row.id, 'Rejected')}
                            sx={{ borderColor: COLORS.border, color: COLORS.danger, fontSize: '10px', fontWeight: 700, textTransform: 'none', px: 1.2, height: 26, minWidth: 0, '&:hover': { borderColor: COLORS.danger, bgcolor: '#FEF2F2' } }}
                          >
                            Reject
                          </Button>
                        </Stack>
                      ) : (
                        <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, fontStyle: 'italic', pr: 1.5 }}>
                          Audit Locked
                        </Typography>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>

    </Box>
  );
}
