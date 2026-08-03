'use client';

import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  MenuItem,
  Paper,
  Select,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';

const DEFAULT_DEPARTMENTS = [
  'Marketing',
  'Customer Relation Management',
  'Operations',
  'Design',
  'Logistics',
  'Purchase',
  'Sales / Business Development',
  'Finance',
  'Information Technology',
  'Human Resource',
  'Production',
  'Services',
  'House Keeping',
  'Other',
];

const FILE_TYPES = [
  { key: 'csv', label: 'CSV', accept: '.csv,text/csv', hint: 'Columns: Date, Description, Debit, Credit (or Amount)' },
  { key: 'txt', label: 'TXT', accept: '.txt,text/plain', hint: 'Tab, comma, or pipe-separated: Date, Description, Debit, Credit' },
  { key: 'xlsx', label: 'Excel', accept: '.xls,.xlsx', hint: 'Excel sheet with columns: Date, Description, Debit, Credit' },
  { key: 'pdf', label: 'PDF', accept: '.pdf,application/pdf', hint: 'PDF bank statements with a transaction table (Date, Description, Debit/Credit)' },
];

function fmt(amount) {
  const n = Number(amount);
  if (isNaN(n)) return '—';
  return n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/* ── shared sx tokens ── */
const inputSx = {
  width: '100%',
  '& .MuiOutlinedInput-root': {
    borderRadius: '8px',
    fontSize: '0.875rem',
    backgroundColor: '#fff',
    '& fieldset': { borderColor: '#e2e8f0' },
    '&:hover fieldset': { borderColor: '#93c5fd' },
    '&.Mui-focused fieldset': { borderColor: '#3b82f6', boxShadow: '0 0 0 3px rgba(59,130,246,0.1)' },
  },
};

const smallSelectSx = {
  width: '100%',
  fontSize: '0.75rem',
  '& .MuiOutlinedInput-root': {
    borderRadius: '6px',
    fontSize: '0.75rem',
    '& fieldset': { borderColor: '#e2e8f0' },
    '&:hover fieldset': { borderColor: '#93c5fd' },
    '&.Mui-focused fieldset': { borderColor: '#3b82f6' },
  },
};

const thSx = {
  fontSize: '0.7rem',
  fontWeight: 700,
  color: '#64748b',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  bgcolor: '#f8fafc',
  borderBottom: '1px solid #e2e8f0',
  py: 1,
  px: 1.5,
};

export default function AccountingBankImport() {
  const { canCreate, canViewAmounts } = usePagePermissions();

  const fmtLocal = (amount) => {
    if (!canViewAmounts) return '****';
    return fmt(amount);
  };

  const [step, setStep] = useState('upload');
  const [ledgers, setLedgers] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [bankAccountId, setBankAccountId] = useState('');
  const [csvFile, setCsvFile] = useState(null);
  const [fileType, setFileType] = useState('csv');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const fileInputRef = useRef(null);

  const [rows, setRows] = useState([]);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState('');
  const [result, setResult] = useState(null);

  const activeFileType = FILE_TYPES.find((t) => t.key === fileType) || FILE_TYPES[0];

  useEffect(() => {
    Promise.all([
      apiClient('/api/accounting/ledgers/').then((r) => r.json()).catch(() => null),
      apiClient('/api/accounting/bank-accounts/').then((r) => r.json()).catch(() => null),
    ]).then(([ledgerRes, bankRes]) => {
      const ledgerPayload = Array.isArray(ledgerRes) ? ledgerRes : Array.isArray(ledgerRes?.data) ? ledgerRes.data : [];
      const bankPayload = Array.isArray(bankRes) ? bankRes : Array.isArray(bankRes?.data) ? bankRes.data : [];
      const mappedLedgers = ledgerPayload.map((o) => ({ id: o.id, name: o.name || o.value, type: o.type || o.option_type }));
      const mappedBanks = bankPayload.length
        ? bankPayload.map((b) => ({ id: b.id, name: b.name }))
        : mappedLedgers.map((l) => ({ id: l.id, name: l.name }));
      setLedgers(mappedLedgers);
      setBankAccounts(mappedBanks);
    }).catch(() => { });
  }, []);

  async function handleUpload(e) {
    e.preventDefault();
    if (!canCreate) return;
    setUploadError('');
    if (!csvFile) { setUploadError('Please choose a file.'); return; }
    if (!bankAccountId) { setUploadError('Please select a bank account ledger.'); return; }

    const formData = new FormData();
    formData.append('file', csvFile);
    formData.append('bank_account_id', bankAccountId);
    formData.append('file_type', fileType);

    setUploading(true);
    try {
      const res = await apiClient('/api/accounting/bank-import/preview/', { method: 'POST', body: formData });
      const data = await res.json();
      if (!data?.success) { setUploadError(data?.message || 'Preview failed.'); return; }

      const mergedLedgers = data.data?.ledgers?.length ? data.data.ledgers : ledgers;
      setLedgers(mergedLedgers.map((l) => ({ id: l.id, name: l.name, type: l.type })));

      const preview = (data.data?.rows || []).map((row, idx) => ({
        ...row,
        _idx: idx,
        ledger_id: row.suggested_ledger_id ? String(row.suggested_ledger_id) : '',
        department: '',
        _remove: row.is_duplicate,
      }));
      setRows(preview);
      setStep('preview');
    } catch {
      setUploadError('Network error. Please try again.');
    } finally {
      setUploading(false);
    }
  }

  function updateRow(idx, field, value) {
    setRows((prev) => prev.map((r) => r._idx === idx ? { ...r, [field]: value } : r));
  }
  function removeRow(idx) { setRows((prev) => prev.map((r) => r._idx === idx ? { ...r, _remove: true } : r)); }
  function restoreRow(idx) { setRows((prev) => prev.map((r) => r._idx === idx ? { ...r, _remove: false } : r)); }

  async function handleConfirm() {
    if (!canCreate) return;
    setConfirmError('');
    const toImport = rows.filter((r) => !r._remove);
    if (toImport.length === 0) { setConfirmError('No rows selected for import.'); return; }

    const missing = toImport.filter((r) => !r.ledger_id);
    if (missing.length > 0) { setConfirmError(`${missing.length} row(s) have no ledger assigned.`); return; }

    const payload = {
      bank_account_id: Number(bankAccountId),
      transactions: toImport.map((r) => ({
        date: r.date, description: r.description, amount: r.amount,
        ledger_id: Number(r.ledger_id), department: r.department || '',
        import_hash: r.import_hash || '',
      })),
    };

    setConfirming(true);
    try {
      const res = await apiClient('/api/accounting/bank-import/confirm/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!data?.success) { setConfirmError(data?.message || 'Import failed.'); return; }
      setResult(data.data);
      setStep('done');
    } catch {
      setConfirmError('Network error. Please try again.');
    } finally {
      setConfirming(false);
    }
  }

  function handleReset() {
    setStep('upload'); setCsvFile(null); setFileType('csv');
    setBankAccountId(''); setRows([]); setResult(null);
    setUploadError(''); setConfirmError('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  const activeRows = rows.filter((r) => !r._remove);
  const removedRows = rows.filter((r) => r._remove);

  /* ─────────────────────────────────────────────────────────────── */
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>

      {/* ── STEP: Upload ── */}
      {step === 'upload' && (
        <Paper
          elevation={0}
          sx={{ border: '1px solid #e2e8f0', borderRadius: 3, p: { xs: 3, md: 4 }, maxWidth: 560 }}
        >
          <Typography variant="subtitle1" fontWeight={600} color="#0f172a" mb={2}>
            Import Bank Statement
          </Typography>

          <Box component="form" onSubmit={handleUpload} sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>

            {/* Bank account selector */}
            <Box>
              <Typography component="label" sx={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: '#0f172a', mb: 0.5 }}>
                Bank Account Ledger <Box component="span" color="error.main">*</Box>
              </Typography>
              <Select
                value={bankAccountId}
                onChange={(e) => setBankAccountId(e.target.value)}
                displayEmpty
                disabled={!canCreate}
                size="small"
                sx={{ ...inputSx, '& .MuiSelect-select': { py: '10px' } }}
              >
                <MenuItem value=""><em style={{ color: '#94a3b8' }}>Select bank account…</em></MenuItem>
                {bankAccounts.map((b) => <MenuItem key={b.id} value={b.id}>{b.name}</MenuItem>)}
              </Select>
            </Box>

            {/* File type selector */}
            <Box>
              <Typography component="label" sx={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: '#0f172a', mb: 1 }}>
                File Type <Box component="span" color="error.main">*</Box>
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap' }}>
                {FILE_TYPES.map((t) => {
                  const active = fileType === t.key;
                  return (
                    <Button
                      key={t.key}
                      type="button"
                      size="small"
                      variant={active ? 'contained' : 'outlined'}
                      onClick={() => {
                        setFileType(t.key);
                        setCsvFile(null);
                        if (fileInputRef.current) fileInputRef.current.value = '';
                        setUploadError('');
                      }}
                      sx={{
                        fontSize: '0.75rem',
                        fontWeight: 500,
                        textTransform: 'none',
                        borderRadius: '8px',
                        px: 1.5, py: 0.75,
                        ...(active
                          ? { bgcolor: '#3b82f6', borderColor: '#3b82f6', color: '#fff', '&:hover': { bgcolor: '#2563eb' } }
                          : { borderColor: '#e2e8f0', color: '#64748b', '&:hover': { borderColor: '#3b82f6', color: '#0f172a' } }
                        ),
                      }}
                    >
                      {t.label}
                    </Button>
                  );
                })}
              </Box>
            </Box>

            {/* File input */}
            <Box>
              <Typography component="label" sx={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: '#0f172a', mb: 0.5 }}>
                {activeFileType.label} File <Box component="span" color="error.main">*</Box>
              </Typography>
              <Box
                component="input"
                ref={fileInputRef}
                type="file"
                accept={activeFileType.accept}
                disabled={!canCreate}
                onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                sx={{
                  width: '100%', fontSize: '0.875rem', color: '#64748b',
                  '&::file-selector-button': {
                    mr: 1.5, py: '6px', px: '12px', borderRadius: '8px',
                    border: '1px solid #e2e8f0', fontSize: '0.75rem', fontWeight: 500,
                    bgcolor: '#f1f5f9', color: '#0f172a', cursor: 'pointer',
                    '&:hover': { bgcolor: '#e2e8f0' },
                  },
                }}
              />
              <Typography variant="caption" color="#64748b" mt={0.5} display="block">
                {activeFileType.hint}
              </Typography>
            </Box>

            {uploadError && <Alert severity="error" sx={{ py: 0.5 }}>{uploadError}</Alert>}

            <Button
              type="submit"
              variant="contained"
              disabled={uploading || !canCreate}
              fullWidth
              sx={{
                bgcolor: '#3b82f6', color: '#fff', fontWeight: 500, fontSize: '0.875rem',
                borderRadius: '8px', py: 1, textTransform: 'none',
                '&:hover': { bgcolor: '#1d4ed8' }, '&:disabled': { opacity: 0.5 },
              }}
            >
              {uploading ? <CircularProgress size={16} sx={{ color: '#fff', mr: 1 }} /> : null}
              {uploading ? 'Parsing…' : 'Upload & Preview'}
            </Button>
          </Box>
        </Paper>
      )}

      {/* ── STEP: Preview ── */}
      {step === 'preview' && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>

          {/* Header */}
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
            <Typography variant="subtitle1" fontWeight={600} color="#0f172a">
              Preview — {activeRows.length} row{activeRows.length !== 1 ? 's' : ''} to import
              {removedRows.length > 0 && (
                <Box component="span" sx={{ ml: 1, fontSize: '0.75rem', fontWeight: 400, color: '#64748b' }}>
                  ({removedRows.length} removed / duplicate)
                </Box>
              )}
            </Typography>
            <Button
              type="button"
              variant="text"
              onClick={handleReset}
              sx={{ fontSize: '0.875rem', color: '#64748b', textTransform: 'none', textDecoration: 'underline', '&:hover': { color: '#0f172a' } }}
            >
              ← Back
            </Button>
          </Box>

          {/* Active rows table */}
          {activeRows.length > 0 && (
            <Paper elevation={0} sx={{ border: '1px solid #e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      {['Date', 'Description', 'Ledger', 'Department', 'Amount', 'Action'].map((h, i) => (
                        <TableCell
                          key={h}
                          align={i >= 4 ? (i === 4 ? 'right' : 'center') : 'left'}
                          sx={{ ...thSx, width: i === 0 ? 112 : i === 2 ? 160 : i === 3 ? 144 : i === 4 ? 112 : i === 5 ? 80 : 'auto' }}
                        >
                          {h}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {activeRows.map((row) => (
                      <TableRow
                        key={row._idx}
                        sx={{ borderBottom: '1px solid #f1f5f9', '&:last-child td': { border: 0 }, '&:hover': { bgcolor: '#f8fafc' } }}
                      >
                        {/* Date */}
                        <TableCell sx={{ px: 1.5, py: 1, fontFamily: 'monospace', fontSize: '0.75rem', color: '#0f172a' }}>
                          {row.date}
                        </TableCell>
                        {/* Description */}
                        <TableCell sx={{ px: 1.5, py: 1, maxWidth: 240 }}>
                          <Typography
                            noWrap
                            title={row.description}
                            sx={{ fontSize: '0.875rem', color: '#0f172a', display: 'block' }}
                          >
                            {row.description}
                          </Typography>
                        </TableCell>
                        {/* Ledger select */}
                        <TableCell sx={{ px: 1.5, py: 1 }}>
                          <Select
                            value={row.ledger_id}
                            onChange={(e) => updateRow(row._idx, 'ledger_id', e.target.value)}
                            displayEmpty
                            size="small"
                            sx={{
                              ...smallSelectSx,
                              '& .MuiOutlinedInput-root fieldset': {
                                borderColor: row.ledger_id ? '#e2e8f0' : '#fca5a5',
                              },
                              '& .MuiSelect-select': {
                                bgcolor: row.ledger_id ? '#fff' : '#fff1f2',
                                py: '4px',
                              },
                            }}
                          >
                            <MenuItem value=""><em style={{ color: '#94a3b8' }}>Select ledger…</em></MenuItem>
                            {ledgers.map((l) => <MenuItem key={l.id} value={l.id} sx={{ fontSize: '0.75rem' }}>{l.name}</MenuItem>)}
                          </Select>
                        </TableCell>
                        {/* Department select */}
                        <TableCell sx={{ px: 1.5, py: 1 }}>
                          <Select
                            value={row.department}
                            onChange={(e) => updateRow(row._idx, 'department', e.target.value)}
                            displayEmpty
                            size="small"
                            sx={{ ...smallSelectSx, '& .MuiSelect-select': { py: '4px' } }}
                          >
                            <MenuItem value=""><em style={{ color: '#94a3b8' }}>No department</em></MenuItem>
                            {DEFAULT_DEPARTMENTS.map((d) => <MenuItem key={d} value={d} sx={{ fontSize: '0.75rem' }}>{d}</MenuItem>)}
                          </Select>
                        </TableCell>
                        {/* Amount */}
                        <TableCell align="right" sx={{ px: 1.5, py: 1, fontFamily: 'monospace', fontWeight: 500, fontSize: '0.875rem', color: row.amount < 0 ? '#ef4444' : '#16a34a' }}>
                          {row.amount < 0 ? '-' : '+'}₹{fmtLocal(Math.abs(row.amount))}
                        </TableCell>
                        {/* Remove */}
                        <TableCell align="center" sx={{ px: 1.5, py: 1 }}>
                          <Button
                            type="button"
                            onClick={() => removeRow(row._idx)}
                            sx={{ minWidth: 0, p: 0, fontSize: '0.75rem', color: '#f87171', '&:hover': { color: '#dc2626' } }}
                          >
                            ✕
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )}

          {/* Removed / duplicate rows */}
          {removedRows.length > 0 && (
            <Paper
              elevation={0}
              component="details"
              sx={{ border: '1px solid #e2e8f0', borderRadius: 3, overflow: 'hidden' }}
            >
              <Box
                component="summary"
                sx={{ px: 2, py: 1.5, fontSize: '0.875rem', color: '#64748b', cursor: 'pointer', userSelect: 'none' }}
              >
                {removedRows.length} removed row{removedRows.length !== 1 ? 's' : ''} (click to expand)
              </Box>
              <TableContainer>
                <Table size="small">
                  <TableBody>
                    {removedRows.map((row) => (
                      <TableRow key={row._idx} sx={{ borderTop: '1px solid #f1f5f9', opacity: 0.5 }}>
                        <TableCell sx={{ px: 1.5, py: 1, fontFamily: 'monospace', fontSize: '0.75rem', width: 112 }}>{row.date}</TableCell>
                        <TableCell sx={{ px: 1.5, py: 1, fontSize: '0.75rem', maxWidth: 240 }}>
                          <Typography noWrap title={row.description} sx={{ fontSize: '0.75rem', display: 'block' }}>
                            {row.description}
                          </Typography>
                          {row.is_duplicate && (
                            <Box component="span" sx={{ color: '#f97316', fontWeight: 500 }}> (duplicate)</Box>
                          )}
                        </TableCell>
                        <TableCell align="right" sx={{ px: 1.5, py: 1, fontFamily: 'monospace', fontSize: '0.75rem', width: 112 }}>
                          {row.amount < 0 ? '-' : '+'}₹{fmtLocal(Math.abs(row.amount))}
                        </TableCell>
                        <TableCell align="center" sx={{ px: 1.5, py: 1, width: 80 }}>
                          <Button
                            type="button"
                            onClick={() => restoreRow(row._idx)}
                            sx={{ minWidth: 0, p: 0, fontSize: '0.75rem', color: '#3b82f6', textDecoration: 'underline', textTransform: 'none' }}
                          >
                            Restore
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          )}

          {confirmError && <Alert severity="error" sx={{ py: 0.5 }}>{confirmError}</Alert>}

          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <Button
              type="button"
              variant="contained"
              onClick={handleConfirm}
              disabled={confirming || activeRows.length === 0 || !canCreate}
              sx={{
                bgcolor: '#3b82f6', color: '#fff', fontWeight: 500, fontSize: '0.875rem',
                borderRadius: '8px', px: 3, py: 1, textTransform: 'none',
                '&:hover': { bgcolor: '#1d4ed8' }, '&:disabled': { opacity: 0.5 },
              }}
            >
              {confirming && <CircularProgress size={14} sx={{ color: '#fff', mr: 1 }} />}
              {confirming ? 'Importing…' : `Confirm & Import ${activeRows.length} row${activeRows.length !== 1 ? 's' : ''}`}
            </Button>
            <Button
              type="button"
              variant="outlined"
              onClick={handleReset}
              sx={{
                borderColor: '#e2e8f0', color: '#64748b', fontSize: '0.875rem',
                borderRadius: '8px', px: 2, py: 1, textTransform: 'none',
                '&:hover': { bgcolor: '#f8fafc' },
              }}
            >
              Cancel
            </Button>
          </Box>
        </Box>
      )}

      {/* ── STEP: Done ── */}
      {step === 'done' && result && (
        <Paper
          elevation={0}
          sx={{ border: '1px solid #e2e8f0', borderRadius: 3, p: { xs: 3, md: 4 }, maxWidth: 560 }}
        >
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5, mb: 2 }}>
            <Typography fontSize="1.5rem">✅</Typography>
            <Box>
              <Typography variant="subtitle1" fontWeight={600} color="#0f172a">Import Complete</Typography>
              <Typography variant="body2" color="#64748b" mt={0.5}>
                {result.created} journal entr{result.created !== 1 ? 'ies' : 'y'} created
                {result.skipped_duplicates > 0 && `, ${result.skipped_duplicates} duplicate${result.skipped_duplicates !== 1 ? 's' : ''} skipped`}.
              </Typography>
            </Box>
          </Box>

          {result.errors?.length > 0 && (
            <Alert severity="error" sx={{ mb: 2, '& ul': { mt: 0.5, pl: 2 } }}>
              <Typography fontWeight={500} fontSize="0.875rem" mb={0.5}>Some rows had errors:</Typography>
              <ul>
                {result.errors.map((err, i) => <li key={i} style={{ fontSize: '0.875rem' }}>{err}</li>)}
              </ul>
            </Alert>
          )}

          <Button
            type="button"
            variant="outlined"
            fullWidth
            onClick={handleReset}
            sx={{
              borderColor: '#e2e8f0', color: '#0f172a', fontSize: '0.875rem',
              borderRadius: '8px', py: 1, textTransform: 'none',
              '&:hover': { bgcolor: '#f8fafc' },
            }}
          >
            Import Another File
          </Button>
        </Paper>
      )}
    </Box>
  );
}