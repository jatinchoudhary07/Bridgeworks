import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Typography, Grid, Chip, CircularProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Button, Stack, Tooltip,
} from '@mui/material';
import CurrencyRupeeIcon from '@mui/icons-material/CurrencyRupee';
import LocalShippingIcon from '@mui/icons-material/LocalShipping';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import RefreshIcon from '@mui/icons-material/Refresh';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { apiClient } from '../../apiClient';

const STATUS_CONFIG = {
  Received:   { color: '#059669', bg: 'rgba(5,150,105,0.08)',  label: 'Received'  },
  Pending:    { color: '#B45309', bg: 'rgba(245,158,11,0.08)', label: 'Pending'   },
  Overdue:    { color: '#DC2626', bg: 'rgba(239,68,68,0.08)',  label: 'Overdue'   },
  Mismatch:   { color: '#7C3AED', bg: 'rgba(124,58,237,0.08)', label: 'Mismatch'  },
  Seized:     { color: '#1E3A5F', bg: 'rgba(30,58,95,0.08)',   label: 'Seized'    },
  'No Record':{ color: '#64748B', bg: 'rgba(100,116,139,0.08)','label': 'No Record' },
};

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG['No Record'];
  return (
    <Box sx={{ display: 'inline-flex', px: 1, py: 0.3, borderRadius: '6px', bgcolor: cfg.bg }}>
      <Typography sx={{ fontSize: '9px', fontWeight: 800, color: cfg.color, letterSpacing: '0.04em' }}>
        {cfg.label}
      </Typography>
    </Box>
  );
}

function KpiTile({ icon, label, value, subtext, color, COLORS }) {
  return (
    <Box sx={{
      flex: 1, p: 2, borderRadius: '12px',
      bgcolor: '#F8FAFC', border: '1px solid #E2E8F0',
      display: 'flex', flexDirection: 'column', gap: 0.5,
      minWidth: 0,
    }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6, mb: 0.3 }}>
        <Box sx={{ color: color || COLORS.accent, display: 'flex', fontSize: '14px' }}>{icon}</Box>
        <Typography sx={{ fontSize: '8.5px', fontWeight: 700, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {label}
        </Typography>
      </Box>
      <Typography sx={{ fontSize: '18px', fontWeight: 900, color: COLORS.primaryText, lineHeight: 1 }}>
        {value}
      </Typography>
      {subtext && (
        <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 600 }}>
          {subtext}
        </Typography>
      )}
    </Box>
  );
}

export default function CodRemittanceDashboard({ cardStyle, COLORS, formatRupee }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [loaded, setLoaded]   = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient(`/api/finance/cod-remittance/?limit=10`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setLoaded(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Lazy load on first mount
  useEffect(() => { fetchData(); }, [fetchData]);

  const summary = data?.summary || {};
  const orders  = data?.orders  || [];

  // Courier breakdown derived from orders
  const courierMap = {};
  orders.forEach(o => {
    if (!courierMap[o.courier]) courierMap[o.courier] = { total: 0, count: 0 };
    courierMap[o.courier].total += o.order_value || 0;
    courierMap[o.courier].count += 1;
  });
  const couriers = Object.entries(courierMap).sort((a, b) => b[1].total - a[1].total);
  const maxCourierTotal = couriers.length > 0 ? couriers[0][1].total : 1;

  const COURIER_COLORS = {
    Bluedart: '#E11D48',
    Delhivery: '#2563EB',
    Aggregator: '#7C3AED',
    Other: '#64748B',
  };

  return (
    <Box sx={{ ...cardStyle, p: 2.5, mb: 2 }}>

      {/* ── Header ── */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.2 }}>
          <Box sx={{
            width: 32, height: 32, borderRadius: '9px',
            bgcolor: 'rgba(37,99,235,0.08)', color: '#2563EB',
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <LocalShippingIcon sx={{ fontSize: 16 }} />
          </Box>
          <Box>
            <Typography sx={{ fontSize: '13px', fontWeight: 800, color: COLORS.primaryText }}>
              COD Remittance
            </Typography>
            <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 600 }}>
              Cash on delivery settlement tracker · Live
            </Typography>
          </Box>
        </Box>
        <Stack direction="row" spacing={1} alignItems="center">
          <Tooltip title="Refresh">
            <Box
              onClick={fetchData}
              sx={{
                width: 28, height: 28, borderRadius: '8px', border: '1px solid #E2E8F0',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                cursor: 'pointer', color: COLORS.secondaryText,
                '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' }
              }}
            >
              <RefreshIcon sx={{ fontSize: 14 }} />
            </Box>
          </Tooltip>
          <Button
            variant="outlined"
            size="small"
            endIcon={<OpenInNewIcon sx={{ fontSize: 11 }} />}
            href="/logistics/cod-remittance"
            sx={{
              textTransform: 'none', fontSize: '10px', fontWeight: 700,
              borderColor: '#E2E8F0', color: COLORS.primaryText,
              borderRadius: '8px', py: 0.5, px: 1.5,
              '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' }
            }}
          >
            Full Report
          </Button>
        </Stack>
      </Box>

      {/* ── Loading / Error ── */}
      {loading && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, py: 3, justifyContent: 'center' }}>
          <CircularProgress size={18} sx={{ color: '#2563EB' }} />
          <Typography sx={{ fontSize: '12px', color: COLORS.secondaryText, fontWeight: 600 }}>
            Loading COD remittance data...
          </Typography>
        </Box>
      )}
      {error && !loading && (
        <Box sx={{ py: 2, px: 2, bgcolor: '#FEF2F2', borderRadius: '10px', border: '1px solid #FEE2E2' }}>
          <Typography sx={{ fontSize: '11px', color: '#DC2626', fontWeight: 700 }}>
            Error: Could not load COD data: {error}
          </Typography>
        </Box>
      )}

      {/* ── Content (only after load) ── */}
      {loaded && !loading && (
        <>
          {/* ── KPI Tiles ── */}
          <Box sx={{ display: 'flex', gap: 1.5, mb: 2, flexWrap: 'wrap' }}>
            <KpiTile
              COLORS={COLORS}
              icon={<CurrencyRupeeIcon sx={{ fontSize: 14 }} />}
              label="Total COD Value"
              value={formatRupee(summary.total_cod_value || 0)}
              subtext="Delivered COD orders"
              color="#2563EB"
            />
            <KpiTile
              COLORS={COLORS}
              icon={<LocalShippingIcon sx={{ fontSize: 14 }} />}
              label="Expected Remittance"
              value={formatRupee(summary.net_expected_remittance || 0)}
              subtext="From courier partners"
              color="#7C3AED"
            />
            <KpiTile
              COLORS={COLORS}
              icon={<CheckCircleOutlineIcon sx={{ fontSize: 14 }} />}
              label="Received"
              value={formatRupee(summary.total_received || 0)}
              subtext={summary.net_expected_remittance > 0 ? `${Math.round((summary.total_received / summary.net_expected_remittance) * 100)}% recovered` : '—'}
              color="#059669"
            />
            <KpiTile
              COLORS={COLORS}
              icon={<PendingActionsIcon sx={{ fontSize: 14 }} />}
              label="Pending"
              value={summary.pending_count || 0}
              subtext="Awaiting settlement"
              color="#B45309"
            />
            <KpiTile
              COLORS={COLORS}
              icon={<WarningAmberIcon sx={{ fontSize: 14 }} />}
              label="Overdue"
              value={summary.overdue_count || 0}
              subtext="Past expected date"
              color="#DC2626"
            />
          </Box>

          {/* ── Courier Breakdown ── */}
          {couriers.length > 0 && (
            <Box sx={{ mb: 2, p: 1.5, bgcolor: '#F8FAFC', borderRadius: '12px', border: '1px solid #E2E8F0' }}>
              <Typography sx={{ fontSize: '9px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1.2 }}>
                Courier Breakdown
              </Typography>
              <Stack spacing={1}>
                {couriers.map(([courier, stats]) => (
                  <Box key={courier} sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Typography sx={{ fontSize: '10px', fontWeight: 700, color: COLORS.primaryText, minWidth: 80 }}>
                      {courier}
                    </Typography>
                    <Box sx={{ flex: 1, height: 7, bgcolor: '#E2E8F0', borderRadius: '4px', overflow: 'hidden' }}>
                      <Box sx={{
                        height: '100%',
                        width: `${Math.round((stats.total / maxCourierTotal) * 100)}%`,
                        bgcolor: COURIER_COLORS[courier] || '#64748B',
                        borderRadius: '4px',
                        transition: 'width 0.6s ease',
                      }} />
                    </Box>
                    <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText, minWidth: 32, textAlign: 'right', fontWeight: 600 }}>
                      {stats.count}
                    </Typography>
                  </Box>
                ))}
              </Stack>
            </Box>
          )}

          {/* ── Recent Orders Table ── */}
          {orders.length > 0 ? (
            <Box>
              <Typography sx={{ fontSize: '9px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.05em', mb: 1 }}>
                Recent COD Orders
              </Typography>
              <TableContainer sx={{ borderRadius: '10px', border: '1px solid #E2E8F0', maxHeight: 280, overflowY: 'auto' }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      {['Order #', 'AWB', 'Courier', 'Delivered', 'Order Value', 'Expected', 'Received', 'Delay', 'Status'].map(h => (
                        <TableCell key={h} sx={{ fontSize: '8px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.04em', py: 1, bgcolor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', whiteSpace: 'nowrap' }}>
                          {h}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {orders.map((o, idx) => (
                      <TableRow key={o.id || idx} sx={{ '&:hover': { bgcolor: '#F8FAFC' }, '&:last-child td': { border: 0 } }}>
                        <TableCell sx={{ fontSize: '10px', fontWeight: 700, color: COLORS.primaryText, py: 1 }}>
                          {o.order_number}
                        </TableCell>
                        <TableCell sx={{ fontSize: '9.5px', color: COLORS.secondaryText, py: 1, fontFamily: 'monospace' }}>
                          {o.awb_number || '—'}
                        </TableCell>
                        <TableCell sx={{ py: 1 }}>
                          <Typography sx={{ fontSize: '9.5px', color: COURIER_COLORS[o.courier] || COLORS.secondaryText, fontWeight: 700 }}>
                            {o.courier}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ fontSize: '9.5px', color: COLORS.secondaryText, py: 1 }}>
                          {o.delivery_date || '—'}
                        </TableCell>
                        <TableCell sx={{ fontSize: '10px', fontWeight: 700, color: COLORS.primaryText, py: 1 }}>
                          {formatRupee(o.order_value || 0)}
                        </TableCell>
                        <TableCell sx={{ fontSize: '10px', color: COLORS.primaryText, py: 1 }}>
                          {formatRupee(o.net_remittance || 0)}
                        </TableCell>
                        <TableCell sx={{ fontSize: '10px', color: '#059669', fontWeight: 700, py: 1 }}>
                          {o.received_amount > 0 ? formatRupee(o.received_amount) : '—'}
                        </TableCell>
                        <TableCell sx={{ py: 1 }}>
                          {o.delay_days > 0 ? (
                            <Typography sx={{ fontSize: '9.5px', color: '#DC2626', fontWeight: 700 }}>
                              +{o.delay_days}d
                            </Typography>
                          ) : (
                            <Typography sx={{ fontSize: '9.5px', color: '#059669', fontWeight: 700 }}>On time</Typography>
                          )}
                        </TableCell>
                        <TableCell sx={{ py: 1 }}>
                          <StatusBadge status={o.remittance_status} />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          ) : (
            <Box sx={{ py: 3, textAlign: 'center' }}>
              <Typography sx={{ fontSize: '12px', color: COLORS.secondaryText, fontWeight: 600 }}>
                No COD orders found for the selected period.
              </Typography>
            </Box>
          )}
        </>
      )}
    </Box>
  );
}
