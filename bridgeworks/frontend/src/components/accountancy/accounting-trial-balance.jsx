'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableFooter,
  TableHead,
  TableRow,
  Typography,
  Paper,
  Alert,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useTheme, alpha } from '@mui/material/styles';
import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';

export default function AccountingTrialBalance() {
  const { canViewAmounts } = usePagePermissions();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState({});

  const fetchTrialBalance = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient('/api/accounting/trial-balance/', { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok || payload?.success === false) { setError(payload?.message || 'Failed to load trial balance.'); return; }
      setData(payload?.data ?? payload);
    } catch {
      setError('Could not reach trial balance API.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTrialBalance(); }, []);

  const fmt = (n) => {
    if (!canViewAmounts) return '****';
    return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  const rows = useMemo(() => {
    const entries = data?.entries ?? [];
    return entries.map((row) => ({ ...row, txns: Number(row.txn_count || row.txns || 0) }));
  }, [data?.entries]);

  /* ── type chip colours ── */
  const typeChipSx = (type) => {
    const map = {
      asset:     { bgcolor: isDark ? alpha('#3b82f6', 0.2) : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8' },
      liability: { bgcolor: isDark ? alpha('#eab308', 0.2) : '#fef9c3', color: isDark ? '#fde047' : '#a16207' },
      income:    { bgcolor: isDark ? alpha('#22c55e', 0.2) : '#dcfce7', color: isDark ? '#86efac' : '#15803d' },
      expense:   { bgcolor: isDark ? alpha('#ef4444', 0.2) : '#fee2e2', color: isDark ? '#fca5a5' : '#b91c1c' },
      equity:    { bgcolor: isDark ? alpha('#a855f7', 0.2) : '#ede9fe', color: isDark ? '#d8b4fe' : '#6d28d9' },
    };
    return map[type?.toLowerCase()] ?? { bgcolor: isDark ? alpha('#6b7280', 0.2) : '#f3f4f6', color: 'text.secondary' };
  };

  const toggleRow  = (id) => setExpanded((p) => ({ ...p, [id]: !p[id] }));
  const expandAll  = () => { const n = {}; rows.forEach((r) => { n[r.ledger_id] = true; }); setExpanded(n); };
  const collapseAll = () => setExpanded({});

  const thSx = {
    fontWeight: 700,
    fontSize: '0.68rem',
    letterSpacing: '0.07em',
    textTransform: 'uppercase',
    color: 'text.secondary',
    borderBottom: '1px solid',
    borderColor: 'divider',
    py: 1.5,
    bgcolor: isDark ? alpha(theme.palette.common.white, 0.04) : 'grey.50',
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" py={10}>
        <CircularProgress size={32} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box maxWidth={600}>
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
        <Button variant="outlined" onClick={fetchTrialBalance}>Retry</Button>
      </Box>
    );
  }

  if (!data || !rows.length) {
    return (
      <Typography variant="body2" color="text.secondary" textAlign="center" py={6}>
        No journal entries found. Create journal entries first.
      </Typography>
    );
  }

  const { total_debit, total_credit, is_balanced } = data;

  const bannerBg     = is_balanced
    ? isDark ? alpha('#22c55e', 0.12) : '#f0fdf4'
    : isDark ? alpha('#ef4444', 0.12) : '#fff7f7';
  const bannerBorder = is_balanced
    ? isDark ? alpha('#22c55e', 0.3) : '#bbf7d0'
    : isDark ? alpha('#ef4444', 0.3) : '#fecaca';
  const bannerColor  = is_balanced ? 'success.main' : 'error.main';
  const footerBg     = bannerBg;
  const totalColor   = is_balanced ? 'success.main' : 'error.main';

  return (
    <Box width="100%">
      <Paper elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, overflow: 'hidden' }}>
        {/* ── Banner ── */}
        <Box
          display="flex" flexWrap="wrap" alignItems="center" justifyContent="space-between"
          gap={1.5} px={2.5} py={1.5}
          sx={{ bgcolor: bannerBg, borderBottom: `1px solid ${bannerBorder}` }}
        >
          <Typography variant="body2" fontWeight={500} color={bannerColor} display="flex" alignItems="center" gap={1}>
            <span>{is_balanced ? '✅' : '⚠️'}</span>
            {is_balanced ? 'Trial balance is balanced.' : 'Trial balance is NOT balanced — mismatch detected.'}
          </Typography>

          <Box display="flex" gap={1}>
            {[
              { label: 'Expand All', onClick: expandAll, icon: null },
              { label: 'Collapse',   onClick: collapseAll, icon: null },
              { label: 'Refresh',    onClick: fetchTrialBalance, icon: <RefreshIcon sx={{ fontSize: 14 }} /> },
            ].map(({ label, onClick, icon }) => (
              <Button
                key={label} size="small" variant="outlined" onClick={onClick} startIcon={icon}
                sx={{
                  fontSize: '0.72rem', py: 0.4, px: 1.5, minWidth: 0,
                  borderColor: bannerColor, color: bannerColor, textTransform: 'none', fontWeight: 500,
                  '&:hover': { bgcolor: is_balanced ? alpha('#22c55e', 0.12) : alpha('#ef4444', 0.12), borderColor: bannerColor },
                }}
              >
                {label}
              </Button>
            ))}
          </Box>
        </Box>

        {/* ── Table ── */}
        <TableContainer>
          <Table size="medium">
            <TableHead>
              <TableRow>
                <TableCell sx={{ ...thSx, width: 32, px: 2 }} />
                <TableCell sx={{ ...thSx, px: 2 }}>Ledger Account</TableCell>
                <TableCell sx={{ ...thSx, px: 2 }}>Type</TableCell>
                <TableCell sx={{ ...thSx, px: 2, textAlign: 'center', width: 80 }}>Txns</TableCell>
                <TableCell sx={{ ...thSx, px: 2, textAlign: 'right' }}>Debit (₹)</TableCell>
                <TableCell sx={{ ...thSx, px: 2, textAlign: 'right' }}>Credit (₹)</TableCell>
              </TableRow>
            </TableHead>

            <TableBody>
              {rows.map((row) => {
                const isOpen  = Boolean(expanded[row.ledger_id]);
                const chipSx  = typeChipSx(row.type);
                return (
                  <Fragment key={row.ledger_id}>
                    <TableRow
                      onClick={() => toggleRow(row.ledger_id)}
                      hover
                      sx={{ cursor: 'pointer', borderBottom: '1px solid', borderColor: 'divider' }}
                    >
                      <TableCell sx={{ px: 2, py: 2, color: 'text.disabled', fontSize: '0.7rem', width: 32, border: 0 }}>
                        {isOpen ? '▾' : '▸'}
                      </TableCell>
                      <TableCell sx={{ px: 2, py: 2, fontWeight: 500, color: 'text.primary', fontSize: '0.875rem', border: 0 }}>
                        {row.ledger}
                      </TableCell>
                      <TableCell sx={{ px: 2, py: 2, border: 0 }}>
                        <Chip
                          label={row.type?.toUpperCase()}
                          size="small"
                          sx={{ ...chipSx, fontWeight: 700, fontSize: '0.65rem', letterSpacing: '0.05em', height: 22, borderRadius: '999px', '& .MuiChip-label': { px: 1.2 } }}
                        />
                      </TableCell>
                      <TableCell sx={{ px: 2, py: 2, textAlign: 'center', color: 'text.secondary', fontSize: '0.875rem', border: 0 }}>
                        {row.txns || 0}
                      </TableCell>
                      <TableCell sx={{ px: 2, py: 2, textAlign: 'right', border: 0 }}>
                        {row.debit > 0
                          ? <Typography component="span" fontFamily="monospace" color="error.main" fontSize="0.875rem">{fmt(row.debit)}</Typography>
                          : <Typography component="span" color="text.disabled" fontSize="0.875rem">—</Typography>}
                      </TableCell>
                      <TableCell sx={{ px: 2, py: 2, textAlign: 'right', border: 0 }}>
                        {row.credit > 0
                          ? <Typography component="span" fontFamily="monospace" color="success.main" fontSize="0.875rem">{fmt(row.credit)}</Typography>
                          : <Typography component="span" color="text.disabled" fontSize="0.875rem">—</Typography>}
                      </TableCell>
                    </TableRow>

                    {isOpen && (
                      <TableRow sx={{ bgcolor: isDark ? alpha(theme.palette.common.white, 0.03) : 'grey.50' }}>
                        <TableCell colSpan={6} sx={{ px: 2, py: 1, border: 0 }}>
                          <Typography variant="caption" color="text.disabled">
                            Click any ledger row to expand transactions.
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                );
              })}
            </TableBody>

            {/* ── Footer ── */}
            <TableFooter>
              <TableRow sx={{ bgcolor: footerBg, borderTop: `2px solid ${bannerBorder}` }}>
                <TableCell colSpan={4} sx={{ px: 2, py: 2, fontWeight: 700, fontSize: '0.875rem', color: 'text.primary', border: 0 }}>
                  Grand Total
                </TableCell>
                <TableCell sx={{ px: 2, py: 2, textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, fontSize: '0.875rem', color: totalColor, border: 0 }}>
                  ₹{fmt(total_debit)}
                </TableCell>
                <TableCell sx={{ px: 2, py: 2, textAlign: 'right', fontFamily: 'monospace', fontWeight: 700, fontSize: '0.875rem', color: totalColor, border: 0 }}>
                  ₹{fmt(total_credit)}
                </TableCell>
              </TableRow>

              {!is_balanced && (
                <TableRow sx={{ bgcolor: isDark ? alpha('#ef4444', 0.08) : '#fff7f7' }}>
                  <TableCell colSpan={6} sx={{ px: 2, py: 1, fontSize: '0.72rem', color: 'error.main', border: 0 }}>
                    Difference: ₹{fmt(Math.abs(total_debit - total_credit))} — check for missing or duplicate journal items.
                  </TableCell>
                </TableRow>
              )}
            </TableFooter>
          </Table>
        </TableContainer>
      </Paper>

      <Typography variant="caption" color="text.disabled" display="block" textAlign="right" mt={1}>
        {rows.length} ledger{rows.length !== 1 ? 's' : ''} · Click a row to expand transactions.
      </Typography>
    </Box>
  );
}