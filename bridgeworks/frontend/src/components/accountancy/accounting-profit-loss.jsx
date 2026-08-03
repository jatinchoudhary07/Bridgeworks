import { Fragment, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableFooter,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { useTheme, alpha } from '@mui/material/styles';
import RefreshIcon from '@mui/icons-material/Refresh';
import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';

export default function AccountingProfitLoss() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const { canViewAmounts } = usePagePermissions();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // expanded state per section: { income: {}, expenses: {} }
  const [expanded, setExpanded] = useState({ income: {}, expenses: {} });

  const fetchPL = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient('/api/accounting/profit-loss/', { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) { setError(payload?.message || 'Failed to load Profit & Loss report.'); return; }
      setData(payload?.data ?? payload);
    } catch {
      setError('Could not reach Profit & Loss API.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPL(); }, []);

  const fmt = (n) => {
    if (!canViewAmounts) return '****';
    return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const toggleRow = (section, id) => setExpanded((p) => ({ ...p, [section]: { ...p[section], [id]: !p[section][id] } }));
  const expandAll = (section, items) => { const n = {}; items.forEach((i) => { n[i.ledger_id] = true; }); setExpanded((p) => ({ ...p, [section]: n })); };
  const collapseAll = (section) => setExpanded((p) => ({ ...p, [section]: {} }));

  /* ── loading ── */
  if (loading) {
    return (
      <Box display="flex" justifyContent="center" py={10}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  /* ── error ── */
  if (error) {
    return (
      <Box>
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
        <Button variant="outlined" onClick={fetchPL}>Retry</Button>
      </Box>
    );
  }

  /* ── empty ── */
  if (!data || (!data.income?.length && !data.expenses?.length)) {
    return (
      <Typography variant="body2" color="text.secondary" textAlign="center" py={6}>
        No income or expense entries found. Create journal entries with income/expense ledgers first.
      </Typography>
    );
  }

  const { income, expenses, total_income, total_expense, profit } = data;
  const isProfit = profit >= 0;

  const thSx = {
    fontSize: '0.68rem',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.07em',
    color: 'text.secondary',
    bgcolor: 'background.paper',
    borderBottom: `1px solid ${theme.palette.divider}`,
    py: 1.25,
    px: 2,
  };

  /* ── section renderer ── */
  const renderSection = (title, sectionKey, items, total, accentColor, lightBg) => {
    const sectionExpanded = expanded[sectionKey] || {};
    return (
      <Paper
        elevation={0}
        sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 2, overflow: 'hidden', mb: 3, bgcolor: 'background.paper' }}
      >
        {/* Coloured header banner */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            px: 2,
            py: 1.25,
            bgcolor: lightBg,
            borderBottom: `1px solid ${theme.palette.divider}`,
          }}
        >
          <Typography
            variant="caption"
            fontWeight={700}
            textTransform="uppercase"
            letterSpacing="0.09em"
            fontSize="0.8rem"
            color={accentColor}
          >
            {title}
          </Typography>

          {items.length > 0 && (
            <Box display="flex" gap={1}>
              {[
                { label: 'Expand All', onClick: () => expandAll(sectionKey, items) },
                { label: 'Collapse', onClick: () => collapseAll(sectionKey) },
              ].map(({ label, onClick }) => (
                <Button
                  key={label}
                  size="small"
                  variant="outlined"
                  onClick={onClick}
                  sx={{
                    fontSize: '0.7rem', fontWeight: 500, textTransform: 'none',
                    borderRadius: '6px', px: 1.25, py: 0.3, minWidth: 0,
                    borderColor: accentColor, color: accentColor,
                    '&:hover': { bgcolor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)', borderColor: accentColor },
                  }}
                >
                  {label}
                </Button>
              ))}
            </Box>
          )}
        </Box>

        {/* Table */}
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ ...thSx, width: 32, px: 1 }} />
                <TableCell sx={{ ...thSx }}>Ledger Account</TableCell>
                <TableCell sx={{ ...thSx, textAlign: 'center', width: 80 }}>Txns</TableCell>
                <TableCell sx={{ ...thSx, textAlign: 'right' }}>Amount (₹)</TableCell>
              </TableRow>
            </TableHead>

            <TableBody>
              {items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center" sx={{ py: 3, fontSize: '0.8rem', color: 'text.secondary', border: 0 }}>
                    No entries found.
                  </TableCell>
                </TableRow>
              ) : (
                items.map((item) => {
                  const isOpen = Boolean(sectionExpanded[item.ledger_id]);
                  return (
                    <Fragment key={item.ledger_id}>
                      <TableRow
                        onClick={() => toggleRow(sectionKey, item.ledger_id)}
                        sx={{
                          cursor: 'pointer',
                          borderTop: `1px solid ${theme.palette.divider}`,
                          '&:hover': { bgcolor: isDark ? 'rgba(255,255,255,0.04)' : '#f8fafc' },
                        }}
                      >
                        {/* chevron */}
                        <TableCell sx={{ px: 1.5, py: 1.75, color: 'text.secondary', fontSize: '0.7rem', border: 0, width: 32 }}>
                          {isOpen ? '▾' : '▸'}
                        </TableCell>
                        {/* name */}
                        <TableCell sx={{ px: 2, py: 1.75, fontWeight: 500, fontSize: '0.875rem', color: 'text.primary', border: 0 }}>
                          {item.ledger}
                        </TableCell>
                        {/* txns */}
                        <TableCell sx={{ px: 2, py: 1.75, textAlign: 'center', fontSize: '0.875rem', color: 'text.secondary', border: 0 }}>
                          {item.txn_count ?? 0}
                        </TableCell>
                        {/* amount */}
                        <TableCell sx={{ px: 2, py: 1.75, textAlign: 'right', fontFamily: 'monospace', fontSize: '0.875rem', color: accentColor, border: 0 }}>
                          ₹{fmt(item.amount)}
                        </TableCell>
                      </TableRow>

                      {isOpen && (
                        <TableRow sx={{ bgcolor: isDark ? 'rgba(255,255,255,0.02)' : '#f9fafb' }}>
                          <TableCell colSpan={4} sx={{ px: 2, py: 1, border: 0 }}>
                            <Typography variant="caption" color="text.disabled">
                              Click any ledger row to expand its transaction detail.
                            </Typography>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })
              )}
            </TableBody>

            <TableFooter>
              <TableRow sx={{ borderTop: `2px solid ${theme.palette.divider}`, bgcolor: 'background.paper' }}>
                <TableCell sx={{ border: 0, width: 32 }} />
                <TableCell sx={{ px: 2, py: 1.75, fontWeight: 700, fontSize: '0.875rem', color: 'text.primary', border: 0 }} colSpan={2}>
                  Total {title}
                </TableCell>
                <TableCell sx={{ px: 2, py: 1.75, textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, fontSize: '0.875rem', color: accentColor, border: 0 }}>
                  ₹{fmt(total)}
                </TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        </TableContainer>
      </Paper>
    );
  };

  return (
    <Box width="100%">

      {/* Title row */}
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
        <Typography variant="subtitle1" fontWeight={700} color="text.primary" letterSpacing="-0.01em">
          Profit &amp; Loss Statement
        </Typography>
        <Button
          size="small"
          variant="outlined"
          startIcon={<RefreshIcon sx={{ fontSize: 14 }} />}
          onClick={fetchPL}
          sx={{
            fontSize: '0.72rem', fontWeight: 500, textTransform: 'none',
            borderRadius: '8px', px: 1.5, py: 0.5,
            borderColor: theme.palette.divider, color: theme.palette.text.secondary,
            '&:hover': { bgcolor: isDark ? 'rgba(255,255,255,0.05)' : '#f8fafc', borderColor: isDark ? '#555' : '#94a3b8' },
          }}
        >
          Refresh
        </Button>
      </Box>

      {/* Income */}
      {renderSection('Income', 'income', income ?? [], total_income, isDark ? '#4ade80' : '#15803d', isDark ? alpha('#4ade80', 0.1) : '#f0fdf4')}

      {/* Expenses */}
      {renderSection('Expenses', 'expenses', expenses ?? [], total_expense, isDark ? '#f87171' : '#b91c1c', isDark ? alpha('#f87171', 0.1) : '#fff7f7')}

      {/* Summary card */}
      <Paper
        elevation={0}
        sx={{
          border: `2px solid ${isProfit ? (isDark ? '#4ade80' : '#86efac') : (isDark ? '#f87171' : '#fca5a5')}`,
          bgcolor: isProfit ? (isDark ? alpha('#4ade80', 0.1) : '#f0fdf4') : (isDark ? alpha('#f87171', 0.1) : '#fff7f7'),
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
        <Box px={2.5} py={2.5}>
          {/* Income vs Expense */}
          <Box display="flex" justifyContent="space-between" mb={2}>
            <Box>
              <Typography variant="caption" fontWeight={700} textTransform="uppercase" letterSpacing="0.07em" color="text.secondary" display="block" mb={0.5}>
                Total Income
              </Typography>
              <Typography fontWeight={700} fontSize="1.25rem" fontFamily="monospace" color={isDark ? '#4ade80' : '#15803d'}>
                ₹{fmt(total_income)}
              </Typography>
            </Box>
            <Box textAlign="right">
              <Typography variant="caption" fontWeight={700} textTransform="uppercase" letterSpacing="0.07em" color="text.secondary" display="block" mb={0.5}>
                Total Expense
              </Typography>
              <Typography fontWeight={700} fontSize="1.25rem" fontFamily="monospace" color={isDark ? '#f87171' : '#b91c1c'}>
                ₹{fmt(total_expense)}
              </Typography>
            </Box>
          </Box>

          {/* Dashed divider */}
          <Box sx={{ borderTop: '2px dashed', borderColor: isProfit ? (isDark ? '#4ade80' : '#86efac') : (isDark ? '#f87171' : '#fca5a5'), my: 1.5 }} />

          {/* Net result */}
          <Box display="flex" alignItems="center" justifyContent="space-between">
            <Typography fontWeight={700} fontSize="0.8rem" textTransform="uppercase" letterSpacing="0.07em" color={isProfit ? (isDark ? '#4ade80' : '#15803d') : (isDark ? '#f87171' : '#b91c1c')}>
              {isProfit ? 'Net Profit ✅' : 'Net Loss ❌'}
            </Typography>
            <Typography fontWeight={800} fontSize="1.5rem" fontFamily="monospace" color={isProfit ? (isDark ? '#4ade80' : '#15803d') : (isDark ? '#f87171' : '#b91c1c')}>
              {isProfit ? '' : '−'}₹{fmt(Math.abs(profit))}
            </Typography>
          </Box>
        </Box>
      </Paper>

      {/* Footer hint */}
      <Typography variant="caption" color="text.disabled" display="block" textAlign="right" mt={1.5}>
        Click any ledger row to expand its transaction detail.
      </Typography>
    </Box>
  );
}