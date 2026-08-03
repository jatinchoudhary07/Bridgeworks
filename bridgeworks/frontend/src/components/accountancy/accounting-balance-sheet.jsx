import { Fragment, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Chip,
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

export default function AccountingBalanceSheet() {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const { canViewAmounts } = usePagePermissions();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({ assets: {}, liabilities: {} });

  const fetchBS = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient('/api/accounting/balance-sheet/', { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) { setError(payload?.message || 'Failed to load Balance Sheet.'); return; }
      setData(payload?.data ?? payload);
    } catch {
      setError('Could not reach Balance Sheet API.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchBS(); }, []);

  const fmt = (n) => {
    if (!canViewAmounts) return '****';
    return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const toggleRow = (sec, id) => setExpanded((p) => ({ ...p, [sec]: { ...p[sec], [id]: !p[sec][id] } }));
  const expandAll = (sec, items) => { const n = {}; items.forEach((i) => { n[i.ledger_id] = true; }); setExpanded((p) => ({ ...p, [sec]: n })); };
  const collapseAll = (sec) => setExpanded((p) => ({ ...p, [sec]: {} }));

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
        <Button variant="outlined" onClick={fetchBS}>Retry</Button>
      </Box>
    );
  }

  /* ── empty ── */
  if (!data || (!data.assets?.length && !data.liabilities?.length && data.equity === 0)) {
    return (
      <Typography variant="body2" color="text.secondary" textAlign="center" py={6}>
        No asset or liability entries found. Create journal entries with asset/liability ledgers first.
      </Typography>
    );
  }

  const { assets, liabilities, equity, total_assets, total_liabilities, is_balanced } = data;
  const liabPlusEquity = Math.round((total_liabilities + equity) * 100) / 100;

  /* ── shared header cell sx ── */
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

  /* ── panel renderer ── */
  const renderPanel = (title, sectionKey, items, footerLabel, footerTotal, accentColor, lightBg) => {
    const secExpanded = expanded[sectionKey] || {};
    return (
      <Paper
        elevation={0}
        sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 2, overflow: 'hidden', flex: 1, bgcolor: 'background.paper' }}
      >
        {/* Panel header banner */}
        <Box
          sx={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            px: 2, py: 1.25, bgcolor: lightBg, borderBottom: `1px solid ${theme.palette.divider}`,
          }}
        >
          <Typography variant="caption" fontWeight={700} textTransform="uppercase" letterSpacing="0.09em" fontSize="0.8rem" color={accentColor}>
            {title}
          </Typography>

          {items.length > 0 && (
            <Box display="flex" gap={1}>
              {[
                { label: 'Expand', onClick: () => expandAll(sectionKey, items) },
                { label: 'Collapse', onClick: () => collapseAll(sectionKey) },
              ].map(({ label, onClick }) => (
                <Button
                  key={label}
                  size="small"
                  variant="outlined"
                  onClick={onClick}
                  sx={{
                    fontSize: '0.68rem', fontWeight: 500, textTransform: 'none',
                    borderRadius: '6px', px: 1.25, py: 0.25, minWidth: 0,
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
                <TableCell sx={{ ...thSx }}>Account</TableCell>
                <TableCell sx={{ ...thSx, textAlign: 'center', width: 80 }}>Txns</TableCell>
                <TableCell sx={{ ...thSx, textAlign: 'right' }}>Amount (₹)</TableCell>
              </TableRow>
            </TableHead>

            <TableBody>
              {items.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center" sx={{ py: 3, fontSize: '0.8rem', color: 'text.secondary', border: 0 }}>
                    No entries.
                  </TableCell>
                </TableRow>
              ) : (
                items.map((item) => {
                  const isOpen = Boolean(secExpanded[item.ledger_id]);
                  return (
                    <Fragment key={item.ledger_id}>
                      <TableRow
                        onClick={() => toggleRow(sectionKey, item.ledger_id)}
                        sx={{ cursor: 'pointer', borderTop: `1px solid ${theme.palette.divider}`, '&:hover': { bgcolor: isDark ? 'rgba(255,255,255,0.04)' : '#f8fafc' } }}
                      >
                        <TableCell sx={{ px: 1.5, py: 1.75, color: 'text.secondary', fontSize: '0.7rem', border: 0, width: 32 }}>
                          {isOpen ? '▾' : '▸'}
                        </TableCell>
                        <TableCell sx={{ px: 2, py: 1.75, fontWeight: 500, fontSize: '0.875rem', color: 'text.primary', border: 0 }}>
                          {item.ledger}
                        </TableCell>
                        <TableCell sx={{ px: 2, py: 1.75, textAlign: 'center', fontSize: '0.875rem', color: 'text.secondary', border: 0 }}>
                          {item.txn_count ?? 0}
                        </TableCell>
                        <TableCell sx={{ px: 2, py: 1.75, textAlign: 'right', fontFamily: 'monospace', fontSize: '0.875rem', fontWeight: 600, color: accentColor, border: 0 }}>
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
                <TableCell colSpan={2} sx={{ px: 2, py: 1.75, fontWeight: 700, fontSize: '0.875rem', color: 'text.primary', border: 0 }}>
                  {footerLabel}
                </TableCell>
                <TableCell sx={{ px: 2, py: 1.75, textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, fontSize: '0.875rem', color: accentColor, border: 0 }}>
                  ₹{fmt(footerTotal)}
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

      {/* ── Title row ── */}
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
        <Typography variant="subtitle1" fontWeight={700} color="text.primary" letterSpacing="-0.01em">
          Balance Sheet
        </Typography>

        <Box display="flex" alignItems="center" gap={1.5}>
          {/* Balanced / Mismatch chip */}
          <Chip
            label={is_balanced ? '✅ Balanced' : '❌ Mismatch'}
            size="small"
            sx={{
              fontWeight: 700,
              fontSize: '0.72rem',
              bgcolor: is_balanced ? (isDark ? alpha('#4ade80', 0.15) : '#f0fdf4') : (isDark ? alpha('#f87171', 0.15) : '#fff7f7'),
              color: is_balanced ? (isDark ? '#4ade80' : '#15803d') : (isDark ? '#f87171' : '#b91c1c'),
              border: `1px solid ${is_balanced ? (isDark ? alpha('#4ade80', 0.3) : '#86efac') : (isDark ? alpha('#f87171', 0.3) : '#fca5a5')}`,
              borderRadius: '999px',
              height: 26,
            }}
          />
          <Button
            size="small"
            variant="outlined"
            startIcon={<RefreshIcon sx={{ fontSize: 14 }} />}
            onClick={fetchBS}
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
      </Box>

      {/* ── Two-column panels ── */}
      <Box display="flex" gap={2.5} mb={3} sx={{ flexDirection: { xs: 'column', md: 'row' } }}>

        {/* Assets panel */}
        {renderPanel(
          'Assets', 'assets', assets ?? [],
          'Total Assets', total_assets,
          isDark ? '#60a5fa' : '#1d4ed8', isDark ? alpha('#60a5fa', 0.1) : '#eff6ff',
        )}

        {/* Liabilities & Equity panel */}
        {renderPanel(
          'Liabilities & Equity', 'liabilities', liabilities ?? [],
          'Total Liabilities & Equity', liabPlusEquity,
          isDark ? '#fbbf24' : '#b45309', isDark ? alpha('#fbbf24', 0.1) : '#fffbeb',
        )}
      </Box>

      {/* ── Accounting Equation card ── */}
      <Paper
        elevation={0}
        sx={{
          border: `2px solid ${is_balanced ? (isDark ? alpha('#4ade80', 0.3) : '#86efac') : (isDark ? alpha('#f87171', 0.3) : '#fca5a5')}`,
          bgcolor: is_balanced ? (isDark ? alpha('#4ade80', 0.1) : '#f0fdf4') : (isDark ? alpha('#f87171', 0.1) : '#fff7f7'),
          borderRadius: 2,
          px: 2.5,
          py: 2,
          mb: 1,
        }}
      >
        <Typography
          variant="caption"
          fontWeight={700}
          textTransform="uppercase"
          letterSpacing="0.09em"
          color="text.secondary"
          display="block"
          mb={1}
        >
          Accounting Equation
        </Typography>

        <Box display="flex" alignItems="center" gap={1} flexWrap="wrap">
          <Typography fontWeight={700} fontFamily="monospace" fontSize="0.95rem" color={isDark ? '#60a5fa' : '#1d4ed8'}>
            Assets: ₹{fmt(total_assets)}
          </Typography>
          <Typography fontWeight={700} color="text.secondary" fontSize="0.95rem">=</Typography>
          <Typography fontWeight={700} fontFamily="monospace" fontSize="0.95rem" color={isDark ? '#fbbf24' : '#b45309'}>
            Liabilities: ₹{fmt(total_liabilities)}
          </Typography>
          <Typography fontWeight={700} color="text.secondary" fontSize="0.95rem">+</Typography>
          <Typography fontWeight={700} fontFamily="monospace" fontSize="0.95rem" color="text.primary">
            Equity: ₹{fmt(equity)}
          </Typography>

          {!is_balanced && (
            <>
              <Typography fontWeight={700} color="error.main" fontSize="0.8rem" ml={1}>
                (Diff: ₹{fmt(Math.abs(total_assets - liabPlusEquity))})
              </Typography>
            </>
          )}
        </Box>
      </Paper>

      {/* Footer hint */}
      <Typography variant="caption" color="text.disabled" display="block" textAlign="right" mt={1}>
        Click any ledger row to expand its transaction detail.
      </Typography>
    </Box>
  );
}