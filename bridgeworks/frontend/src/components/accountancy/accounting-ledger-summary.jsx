'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
  FormControl,
  InputAdornment,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useTheme, alpha } from '@mui/material/styles';
import SearchIcon from '@mui/icons-material/Search';
import RefreshIcon from '@mui/icons-material/Refresh';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';

const TYPE_OPTIONS = ['all', 'asset', 'liability', 'income', 'expense'];

const TYPE_META = {
  asset: {
    label: 'Asset',
    chip: { bgcolor: '#eef4ff', color: '#2563eb' },
    amount: '#dc2626',
    balance: '#2563eb',
  },
  liability: {
    label: 'Liability',
    chip: { bgcolor: '#fff7e6', color: '#b45309' },
    amount: '#dc2626',
    balance: '#2563eb',
  },
  income: {
    label: 'Income',
    chip: { bgcolor: '#ecfdf5', color: '#15803d' },
    amount: '#16a34a',
    balance: '#b45309',
  },
  expense: {
    label: 'Expense',
    chip: { bgcolor: '#fef2f2', color: '#dc2626' },
    amount: '#16a34a',
    balance: '#dc2626',
  },
};



export default function AccountingLedgerSummary() {
  const { canViewAmounts } = usePagePermissions();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const headerBg = isDark ? alpha(theme.palette.common.white, 0.04) : 'grey.50';
  const hoverBg  = isDark ? alpha(theme.palette.common.white, 0.06) : 'grey.50';
  const expandBg = isDark ? alpha(theme.palette.common.white, 0.03) : 'grey.50';

  const formatAmount = (value) => {
    if (!canViewAmounts) return '₹ ****';
    const numberValue = Number(value || 0);
    return `₹${numberValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  const formatSignedBalance = (value) => {
    if (!canViewAmounts) return '₹ ****';
    const amount = Math.abs(Number(value || 0));
    const direction = Number(value || 0) >= 0 ? 'Dr' : 'Cr';
    return `${formatAmount(amount)} ${direction}`;
  };

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [expanded, setExpanded] = useState({});

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient('/api/accounting/ledger-summary/', {
        cache: 'no-store',
        credentials: 'include',
      });
      const payload = await response.json().catch(() => null);

      const data = Array.isArray(payload) ? payload : Array.isArray(payload?.data) ? payload.data : [];
      if (!response.ok) {
        setError(payload?.message || 'Failed to load ledger summary.');
        return;
      }

      setRows(data);
    } catch {
      setError('Could not reach ledger summary API.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  const filteredRows = useMemo(() => {
    const searchTerm = query.trim().toLowerCase();
    return rows.filter((row) => {
      const matchesQuery =
        !searchTerm ||
        row.ledger?.toLowerCase().includes(searchTerm) ||
        row.type?.toLowerCase().includes(searchTerm);
      const matchesType = typeFilter === 'all' || row.type === typeFilter;
      return matchesQuery && matchesType;
    });
  }, [rows, query, typeFilter]);

  const summary = useMemo(() => {
    const totalDebit = filteredRows.reduce((sum, row) => sum + Number(row.total_debit || 0), 0);
    const totalCredit = filteredRows.reduce((sum, row) => sum + Number(row.total_credit || 0), 0);
    const netBalance = totalDebit - totalCredit;

    return {
      ledgers: filteredRows.length,
      totalDebit,
      totalCredit,
      netBalance,
    };
  }, [filteredRows]);

  const openAll = () => {
    const next = {};
    filteredRows.forEach((row) => {
      next[row.ledger_id] = true;
    });
    setExpanded(next);
  };

  const collapseAll = () => setExpanded({});

  const toggleRow = (ledgerId) => {
    setExpanded((prev) => ({ ...prev, [ledgerId]: !prev[ledgerId] }));
  };

  const panelSx = {
    borderRadius: 3,
    border: '1px solid',
    borderColor: 'divider',
    boxShadow: '0 1px 3px rgba(15, 23, 42, 0.06)',
  };

  const kpiCardSx = {
    ...panelSx,
    p: 2.25,
    minHeight: 88,
    bgcolor: 'background.paper',
  };

  if (loading) {
    return (
      <Paper sx={{ ...panelSx, p: 3, maxWidth: '100%' }}>
        <Typography variant="body2" color="text.secondary">
          Loading ledger summary...
        </Typography>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper sx={{ ...panelSx, p: 3, maxWidth: '100%' }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
        <Button variant="outlined" startIcon={<RefreshIcon />} onClick={fetchSummary}>
          Retry
        </Button>
      </Paper>
    );
  }

  return (
    <Box sx={{ width: '100%', minWidth: 0 }}>
      <Paper
        sx={{
          ...panelSx,
          p: { xs: 2, md: 2.5 },
          bgcolor: 'background.paper',
        }}
      >
        <Stack spacing={2.25}>
          <Stack
            direction={{ xs: 'column', lg: 'row' }}
            spacing={1.5}
            alignItems={{ xs: 'stretch', lg: 'center' }}
            justifyContent="space-between"
          >
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.25} flexWrap="wrap" useFlexGap>
              <TextField
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search ledger..."
                size="small"
                sx={{ minWidth: { xs: '100%', sm: 280 }, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon fontSize="small" />
                    </InputAdornment>
                  ),
                }}
              />

              <FormControl size="small" sx={{ minWidth: 140 }}>
                <Select
                  value={typeFilter}
                  onChange={(event) => setTypeFilter(event.target.value)}
                  displayEmpty
                  sx={{ borderRadius: 2, bgcolor: 'background.paper' }}
                >
                  <MenuItem value="all">All types</MenuItem>
                  <MenuItem value="asset">Asset</MenuItem>
                  <MenuItem value="liability">Liability</MenuItem>
                  <MenuItem value="income">Income</MenuItem>
                  <MenuItem value="expense">Expense</MenuItem>
                </Select>
              </FormControl>
            </Stack>

            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap justifyContent={{ xs: 'flex-start', lg: 'flex-end' }}>
              <Button variant="outlined" onClick={openAll} startIcon={<ExpandMoreIcon />} sx={{ borderRadius: 2 }}>
                Expand All
              </Button>
              <Button variant="outlined" onClick={collapseAll} startIcon={<ExpandLessIcon />} sx={{ borderRadius: 2 }}>
                Collapse All
              </Button>
              <Button variant="outlined" onClick={fetchSummary} startIcon={<RefreshIcon />} sx={{ borderRadius: 2 }}>
                Refresh
              </Button>
            </Stack>
          </Stack>

          <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
            <Box sx={kpiCardSx}>
              <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 1.1, fontWeight: 700 }}>
                Ledgers
              </Typography>
              <Typography variant="h5" sx={{ mt: 0.75, fontWeight: 800 }}>
                {summary.ledgers}
              </Typography>
            </Box>

            <Box sx={kpiCardSx}>
              <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 1.1, fontWeight: 700 }}>
                Total Debit
              </Typography>
              <Typography variant="h5" sx={{ mt: 0.75, fontWeight: 800, color: 'error.main' }}>
                {formatAmount(summary.totalDebit)}
              </Typography>
            </Box>

            <Box sx={kpiCardSx}>
              <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 1.1, fontWeight: 700 }}>
                Total Credit
              </Typography>
              <Typography variant="h5" sx={{ mt: 0.75, fontWeight: 800, color: 'success.main' }}>
                {formatAmount(summary.totalCredit)}
              </Typography>
            </Box>

            <Box sx={kpiCardSx}>
              <Typography variant="overline" sx={{ color: 'text.secondary', letterSpacing: 1.1, fontWeight: 700 }}>
                Net Balance
              </Typography>
              <Typography
                variant="h5"
                sx={{
                  mt: 0.75,
                  fontWeight: 800,
                  color: summary.netBalance >= 0 ? 'primary.main' : 'warning.dark',
                }}
              >
                {formatSignedBalance(summary.netBalance)}
              </Typography>
            </Box>
          </Stack>

          <Paper
            sx={{
              ...panelSx,
              overflow: 'hidden',
              bgcolor: 'background.paper',
            }}
          >
            <Box sx={{ overflowX: 'auto' }}>
              <Box component="table" sx={{ width: '100%', borderCollapse: 'collapse', minWidth: 980 }}>
                <Box component="thead" sx={{ bgcolor: headerBg }}>
                  <Box component="tr">
                    <Box component="th" sx={headerCellSx({ width: 46 })} />
                    <Box component="th" sx={headerCellSx({ textAlign: 'left' })}>Ledger Account</Box>
                    <Box component="th" sx={headerCellSx({ textAlign: 'left' })}>Type</Box>
                    <Box component="th" sx={headerCellSx({ textAlign: 'center', width: 90 })}>Txns</Box>
                    <Box component="th" sx={headerCellSx({ textAlign: 'right' })}>Total Debit</Box>
                    <Box component="th" sx={headerCellSx({ textAlign: 'right' })}>Total Credit</Box>
                    <Box component="th" sx={headerCellSx({ textAlign: 'right' })}>Balance</Box>
                  </Box>
                </Box>

                <Box component="tbody">
                  {filteredRows.map((row) => {
                    const balance = Number(row.total_debit || 0) - Number(row.total_credit || 0);
                    const isOpen = Boolean(expanded[row.ledger_id]);
                    const meta = TYPE_META[row.type] || TYPE_META.asset;

                    return (
                      <Fragment key={row.ledger_id}>
                        <Box
                          component="tr"
                          onClick={() => toggleRow(row.ledger_id)}
                          sx={{
                            cursor: 'pointer',
                            transition: 'background-color 0.15s ease',
                            '&:hover': { bgcolor: hoverBg },
                          }}
                        >
                          <Box component="td" sx={bodyCellSx({ width: 46, textAlign: 'center', color: 'text.secondary' })}>
                            {isOpen ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                          </Box>
                          <Box component="td" sx={bodyCellSx({ fontWeight: 700, color: 'text.primary' })}>
                            {row.ledger}
                          </Box>
                          <Box component="td" sx={bodyCellSx()}>
                            <Chip
                              label={(meta.label || row.type || '').toUpperCase()}
                              size="small"
                              sx={{
                                fontWeight: 800,
                                letterSpacing: 0.4,
                                borderRadius: 1.5,
                                ...meta.chip,
                              }}
                            />
                          </Box>
                          <Box component="td" sx={bodyCellSx({ textAlign: 'center', color: 'text.secondary' })}>
                            {Number(row.total_debit || 0) > 0 || Number(row.total_credit || 0) > 0 ? 1 : 0}
                          </Box>
                          <Box component="td" sx={bodyCellSx({ textAlign: 'right', color: meta.amount, fontWeight: 700, fontFamily: 'monospace' })}>
                            {formatAmount(row.total_debit)}
                          </Box>
                          <Box component="td" sx={bodyCellSx({ textAlign: 'right', color: '#16a34a', fontWeight: 700, fontFamily: 'monospace' })}>
                            {formatAmount(row.total_credit)}
                          </Box>
                          <Box component="td" sx={bodyCellSx({ textAlign: 'right', color: meta.balance, fontWeight: 800, fontFamily: 'monospace' })}>
                            {formatSignedBalance(balance)}
                          </Box>
                        </Box>

                        {isOpen && (
                          <Box component="tr">
                            <Box component="td" colSpan={7} sx={{ p: 0, borderTop: '1px solid', borderColor: 'divider', bgcolor: expandBg }}>
                              <Box sx={{ px: 2.5, py: 1.75 }}>
                                <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                                  This ledger summary is aggregated from journal items. Debit and credit totals are shown in the row above.
                                </Typography>
                              </Box>
                            </Box>
                          </Box>
                        )}
                      </Fragment>
                    );
                  })}
                </Box>

                <Box component="tfoot" sx={{ bgcolor: headerBg, borderTop: '1px solid', borderColor: 'divider' }}>
                  <Box component="tr">
                    <Box component="td" sx={{ ...footerCellSx({ textAlign: 'left', fontWeight: 800 }), px: 2.5 }} colSpan={4}>
                      Grand Total ({filteredRows.length} ledgers)
                    </Box>
                    <Box component="td" sx={{ ...footerCellSx({ textAlign: 'right', color: 'error.main' }), fontFamily: 'monospace' }}>
                      {formatAmount(summary.totalDebit)}
                    </Box>
                    <Box component="td" sx={{ ...footerCellSx({ textAlign: 'right', color: 'success.main' }), fontFamily: 'monospace' }}>
                      {formatAmount(summary.totalCredit)}
                    </Box>
                    <Box component="td" sx={{ ...footerCellSx({ textAlign: 'right', fontFamily: 'monospace' }) }}>
                      {formatSignedBalance(summary.netBalance)}
                    </Box>
                  </Box>
                </Box>
              </Box>
            </Box>
          </Paper>

          <Typography variant="body2" sx={{ textAlign: 'right', color: 'text.secondary' }}>
            Click any ledger row to expand its summary detail.
          </Typography>
        </Stack>
      </Paper>
    </Box>
  );
}

function headerCellSx(extra = {}) {
  return {
    px: 2.5,
    py: 1.75,
    fontSize: 12,
    fontWeight: 800,
    color: 'text.secondary',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    borderBottom: '1px solid',
    borderColor: 'divider',
    ...extra,
  };
}

function bodyCellSx(extra = {}) {
  return {
    px: 2.5,
    py: 2,
    fontSize: 14,
    borderBottom: '1px solid',
    borderColor: 'divider',
    verticalAlign: 'middle',
    ...extra,
  };
}

function footerCellSx(extra = {}) {
  return {
    px: 2.5,
    py: 1.75,
    fontSize: 13,
    borderTop: '1px solid',
    borderColor: 'divider',
    fontWeight: 700,
    ...extra,
  };
};
