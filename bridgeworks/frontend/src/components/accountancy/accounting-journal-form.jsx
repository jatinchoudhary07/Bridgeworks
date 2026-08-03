'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useTheme, alpha } from '@mui/material/styles';
import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';

/* ── constants ───────────────────────────────────────────────── */
const DEFAULT_DEPARTMENTS = [
  'Leadership & Strategy',
  'Product & Merchandising',
  'Branding & Creative',
  'Marketing & Growth',
  'E-Commerce & Website',
  'Operations & Fulfillment',
  'Logistics',
  'Reverse Shipment',
  'My Desk',
  'Customer Experience',
  'Intelligence',
  'Webhooks',
  'Finance & Accounting',
  'Human Resources',
  'IT & Data',
  'Production / Manufacturing',
  'Sales and Business Development',
];

const DEFAULT_PAYMENT_METHODS = [
  'Cash', 'Bank Transfer', 'NEFT', 'RTGS', 'IMPS',
  'Cheque', 'UPI', 'Credit Card', 'Debit Card', 'Other',
];

/* ── helpers ─────────────────────────────────────────────────── */
function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

function emptyLine(id) {
  return {
    id: id || (typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString()),
    ledger: '',
    amount: '',
  };
}

/* ── AddableSelect ───────────────────────────────────────────── */
function AddableSelect({ value, onChange, options, placeholder, style, disabled }) {
  const [custom, setCustom] = useState([]);       
  const [adding, setAdding] = useState(false);    
  const [draft, setDraft] = useState('');
  const inputRef = useRef(null);

  const normalizedOptions = useMemo(() => {
    return options.map(o => typeof o === 'string' ? { value: o, label: o } : o);
  }, [options]);

  const allOptions = [...normalizedOptions, ...custom];
  const ADD_SENTINEL = '__add_new__';

  const handleChange = (e) => {
    if (e.target.value === ADD_SENTINEL) {
      setAdding(true);
      setDraft('');
      setTimeout(() => inputRef.current?.focus(), 50);
      return;
    }
    onChange(e.target.value);
  };

  const confirmNew = () => {
    const trimmed = draft.trim();
    if (!trimmed) { setAdding(false); return; }

    if (!allOptions.find(o => o.label.toLowerCase() === trimmed.toLowerCase())) {
      setCustom((p) => [...p, { value: trimmed, label: trimmed }]);
    }
    onChange(trimmed);
    setAdding(false);
    setDraft('');
  };

  if (adding) {
    return (
      <div style={{ display: 'flex', gap: 4 }}>
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); confirmNew(); } if (e.key === 'Escape') setAdding(false); }}
          placeholder="Type and press Enter…"
          style={{ ...style, flex: 1, border: '2px solid #2563eb' }}
          autoFocus
        />
        <button type="button" onClick={confirmNew}
          style={{ padding: '0 12px', background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, cursor: 'pointer', fontWeight: 700, fontSize: 13 }}>
          ✓
        </button>
        <button type="button" onClick={() => setAdding(false)}
          style={{ padding: '0 10px', background: '#f3f4f6', color: '#6b7280', border: '1px solid #e5e7eb', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
          ✕
        </button>
      </div>
    );
  }

  return (
    <select value={value} onChange={handleChange} style={style} disabled={disabled}>
      <option value="">{placeholder || '— Select —'}</option>
      {allOptions.map((opt) => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
      <option value={ADD_SENTINEL} style={{ color: '#2563eb', fontWeight: 600 }}>＋ Add new…</option>
    </select>
  );
}

/* ── sub-component: SectionLine ─────────────────────────────── */
function SectionLine({ line, index, type, ledgers, loadingLedgers, onChange, onRemove, canRemove, canViewAmounts = true, disabled = false }) {
  const isDebit = type === 'debit';
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const accent = isDebit
    ? { bg: isDark ? alpha('#2563eb', 0.12) : '#eff6ff', border: isDark ? alpha('#2563eb', 0.3) : '#bfdbfe', badge: '#2563eb', badgeTxt: '#fff' }
    : { bg: isDark ? alpha('#16a34a', 0.12) : '#f0fdf4', border: isDark ? alpha('#16a34a', 0.3) : '#bbf7d0', badge: '#16a34a', badgeTxt: '#fff' };

  const inputStyle = {
    width: '100%', padding: '9px 12px',
    border: `1px solid ${theme.palette.divider}`,
    borderRadius: 8, fontSize: 13,
    color: theme.palette.text.primary,
    background: isDark ? alpha('#ffffff', 0.06) : '#fff',
    outline: 'none', transition: 'border-color 0.15s, box-shadow 0.15s',
    boxSizing: 'border-box', minHeight: 40,
  };
  const labelStyle = {
    display: 'block', fontSize: 11, fontWeight: 700,
    color: isDark ? '#cbd5e1' : '#475569',
    textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5,
  };

  return (
    <div style={{
      background: accent.bg,
      border: `1px solid ${accent.border}`,
      borderRadius: 12,
      padding: '16px 20px',
      marginBottom: 12,
      position: 'relative',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{
          background: accent.badge, color: accent.badgeTxt,
          fontSize: 11, fontWeight: 700, padding: '3px 10px',
          borderRadius: 20, letterSpacing: 0.5, textTransform: 'uppercase',
        }}>
          {isDebit ? '▲ Debit' : '▼ Credit'} Line {index + 1}
        </span>
        {canRemove && (
          <button
            type="button"
            onClick={() => onRemove(index)}
            title="Remove line"
            disabled={disabled}
            style={{
              background: isDark ? alpha('#dc2626', 0.15) : '#fef2f2',
              border: `1px solid ${isDark ? alpha('#dc2626', 0.4) : '#fca5a5'}`,
              color: '#dc2626', borderRadius: 8, padding: '4px 12px',
              fontSize: 12, fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
              opacity: disabled ? 0.5 : 1,
            }}
          >
            ✕ Remove
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12 }}>
        <div>
          <label style={labelStyle}>Ledger Account *</label>
          <AddableSelect
            value={line.ledger}
            onChange={(val) => onChange(index, 'ledger', val)}
            options={ledgers.map((l) => ({ value: l.id, label: `${l.name} (${l.type})` }))}
            placeholder="— Select Ledger —"
            style={inputStyle}
            disabled={loadingLedgers || disabled}
          />
        </div>
        <div>
          <label style={labelStyle}>{isDebit ? 'Debit Amount (₹) *' : 'Credit Amount (₹) *'}</label>
          <input
            type="text"
            inputMode="decimal"
            placeholder="0.00"
            value={canViewAmounts ? line.amount : '****'}
            onChange={(e) => {
              let raw = e.target.value.replace(/[^0-9.]/g, '');
              const parts = raw.split('.');
              if (parts.length > 2) raw = parts[0] + '.' + parts.slice(1).join('');
              let formatted = parts[0];
              if (formatted.length > 3) {
                formatted = formatted.substring(0, formatted.length - 3).replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + formatted.substring(formatted.length - 3);
              }
              if (parts.length > 1) formatted += '.' + parts[1];
              onChange(index, 'amount', formatted);
            }}
            required
            disabled={disabled || !canViewAmounts}
            style={{ ...inputStyle, fontWeight: 600, fontSize: 15 }}
          />
        </div>
      </div>
    </div>
  );
}

/* ── shared micro-styles (static fallbacks — overridden inside components) ── */
const labelStyle = { display: 'block', fontSize: 11, fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5 };
const inputStyle = { width: '100%', padding: '9px 12px', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: 13, color: '#111827', background: '#fff', outline: 'none', transition: 'border-color 0.15s, box-shadow 0.15s', boxSizing: 'border-box', minHeight: 40 };

/* ── main component ──────────────────────────────────────────── */
export default function AccountingJournalForm() {
  const { canCreate, canViewAmounts } = usePagePermissions();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const cardSx = {
    background: theme.palette.background.paper,
    borderRadius: 14, padding: '20px 24px',
    boxShadow: '0 1px 4px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)',
    border: `1px solid ${theme.palette.divider}`, marginBottom: 16,
  };
  const [narration, setNarration] = useState('');
  const [ledgers, setLedgers] = useState([]);
  const [loadingLedgers, setLoadingLedgers] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState(null);

  // Centralized transaction details states
  const [department, setDepartment] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('');
  const [billDate, setBillDate] = useState('');
  const [refId, setRefId] = useState('');
  const [attachments, setAttachments] = useState([]);
  const fileRef = useRef(null);

  const [debitLines, setDebitLines] = useState([emptyLine('initial-debit')]);
  const [creditLines, setCreditLines] = useState([emptyLine('initial-credit')]);

  useEffect(() => {
    setBillDate(todayDate());

    (async () => {
      setLoadingLedgers(true);
      try {
        const res = await apiClient('/api/accounting/ledgers/', { cache: 'no-store' });
        const payload = await res.json().catch(() => null);
        const options = Array.isArray(payload) ? payload : Array.isArray(payload?.data) ? payload.data : [];
        if (res.ok) {
          setLedgers(
            options.map((option) => ({
              id: option.id,
              name: option.name || option.value,
              type: option.type || option.option_type,
            })),
          );
        } else {
          setLedgers([]);
          setStatus({ type: 'warning', message: 'Could not load finance options.' });
        }
      } catch {
        setLedgers([]);
        setStatus({ type: 'warning', message: 'Backend unreachable.' });
      } finally {
        setLoadingLedgers(false);
      }
    })();
  }, []);

  const totalDebit = useMemo(
    () => debitLines.reduce((s, l) => s + (Number(String(l.amount).replace(/,/g, '')) || 0), 0),
    [debitLines],
  );
  const totalCredit = useMemo(
    () => creditLines.reduce((s, l) => s + (Number(String(l.amount).replace(/,/g, '')) || 0), 0),
    [creditLines],
  );
  const isBalanced = totalDebit > 0 && totalDebit === totalCredit;
  const difference = Math.abs(totalDebit - totalCredit);

  const updateLine = (setter) => (index, field, value) => {
    setter((prev) => prev.map((l, i) => (i === index ? { ...l, [field]: value } : l)));
  };
  const addLine = (setter) => () => setter((prev) => [...prev, emptyLine()]);
  const removeLine = (setter) => (index) => setter((prev) => prev.filter((_, i) => i !== index));

  const resetForm = () => {
    setNarration('');
    setDepartment('');
    setPaymentMethod('');
    setBillDate(todayDate());
    setRefId('');
    setAttachments([]);
    setDebitLines([emptyLine()]);
    setCreditLines([emptyLine()]);
    setStatus(null);
  };

  const handleFiles = (e) => {
    const newFiles = Array.from(e.target.files || []);
    if (!newFiles.length) return;
    const newAttachments = newFiles.map((file) => ({
      id: typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(),
      file,
      name: file.name,
      url: URL.createObjectURL(file),
      type: file.type,
    }));
    setAttachments((prev) => [...prev, ...newAttachments]);
    if (fileRef.current) fileRef.current.value = '';
  };

  const removeAttachment = (id) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canCreate) return;
    setStatus(null);

    if (!isBalanced) {
      setStatus({ type: 'error', message: `Journal entry is unbalanced. Difference: ${canViewAmounts ? '₹' + difference.toFixed(2) : '****'}` });
      return;
    }

    const formData = new FormData();
    formData.append('date', billDate || todayDate());
    formData.append('narration', narration);

    const buildLineData = (lines, type) =>
      lines.map((l) => {
        const amt = Number(String(l.amount).replace(/,/g, '')) || 0;
        return {
          type,
          ledger: l.ledger ? (isNaN(Number(l.ledger)) ? l.ledger : Number(l.ledger)) : null,
          debit: type === 'debit' ? amt : 0,
          credit: type === 'credit' ? amt : 0,
          department: department || '',
          payment_method: paymentMethod || '',
          vendor_payee: '',
          bill_date: billDate || null,
          ref_id: refId || '',
          notes: narration || '',
        };
      });

    formData.append('items', JSON.stringify([
      ...buildLineData(debitLines, 'debit'),
      ...buildLineData(creditLines, 'credit'),
    ]));

    // Attach all files to the first debit line (debit_0_attachment_X)
    attachments.forEach((att, j) => {
      if (att.file) formData.append(`debit_0_attachment_${j}`, att.file, att.name);
    });

    setSubmitting(true);
    try {
      const res = await apiClient('/api/accounting/journal/create/', {
        method: 'POST',
        body: formData,
      });
      const result = await res.json().catch(() => null);

      if (!res.ok || !result?.success) {
        setStatus({ type: 'error', message: result?.message || 'Failed to create journal entry.' });
        return;
      }

      setStatus({ type: 'success', message: `✓ Journal entry created successfully.` });
      resetForm();
    } catch {
      setStatus({ type: 'error', message: 'Network error.' });
    } finally {
      setSubmitting(false);
    }
  };

  const formLabelStyle = { display: 'block', fontSize: 11, fontWeight: 700, color: isDark ? '#cbd5e1' : '#475569', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 5 };
  const formInputStyle = { width: '100%', padding: '9px 12px', border: `1px solid ${theme.palette.divider}`, borderRadius: 8, fontSize: 13, color: isDark ? '#ffffff' : '#111827', background: isDark ? alpha('#ffffff', 0.06) : '#fff', outline: 'none', transition: 'border-color 0.15s, box-shadow 0.15s', boxSizing: 'border-box', minHeight: 40 };

  return (
    <div className="journal-form-container" style={{ fontFamily: 'Inter, system-ui, sans-serif', padding: '0' }}>
      <style>{`
        .journal-form-container input, .journal-form-container select {
           color: ${isDark ? '#ffffff' : '#111827'} !important;
        }
        .journal-form-container input::placeholder {
           color: ${isDark ? '#94a3b8' : '#9ca3af'} !important;
           opacity: 1;
        }
        .journal-form-container select option {
           background: ${isDark ? '#1e293b' : '#fff'};
           color: ${isDark ? '#ffffff' : '#111827'};
        }
        .journal-form-container select option[value="__add_new__"] {
           color: ${isDark ? '#60a5fa' : '#2563eb'} !important;
        }
      `}</style>
      <div style={cardSx}>
        <h3 style={{ margin: '0 0 16px 0', fontSize: 15, fontWeight: 700, color: theme.palette.text.primary, borderBottom: `1px solid ${theme.palette.divider}`, paddingBottom: 8 }}>
          Journal Entry Details
        </h3>
        
        {/* Row 1: Bill Date & Description */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={formLabelStyle}>Bill Date *</label>
            <input
              type="date"
              value={billDate}
              onChange={(e) => setBillDate(e.target.value)}
              disabled={!canCreate}
              required
              style={formInputStyle}
            />
          </div>
          <div>
            <label style={formLabelStyle}>Description / Narration</label>
            <input
              type="text"
              placeholder="e.g. Monthly rent and utilities payment…"
              value={narration}
              onChange={(e) => setNarration(e.target.value)}
              disabled={!canCreate}
              style={formInputStyle}
            />
          </div>
        </div>

        {/* Row 2: Department, Payment Method, Reference ID */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={formLabelStyle}>Department</label>
            <AddableSelect
              value={department}
              onChange={setDepartment}
              options={DEFAULT_DEPARTMENTS}
              placeholder="— Select Department —"
              style={formInputStyle}
              disabled={!canCreate}
            />
          </div>
          <div>
            <label style={formLabelStyle}>Payment Method</label>
            <AddableSelect
              value={paymentMethod}
              onChange={setPaymentMethod}
              options={DEFAULT_PAYMENT_METHODS}
              placeholder="— Select Method —"
              style={formInputStyle}
              disabled={!canCreate}
            />
          </div>
          <div>
            <label style={formLabelStyle}>Reference ID</label>
            <input
              type="text"
              placeholder="Enter reference ID manually"
              value={refId}
              onChange={(e) => setRefId(e.target.value)}
              disabled={!canCreate}
              style={{ ...formInputStyle, fontFamily: 'monospace', fontSize: 12 }}
            />
          </div>
        </div>

        {/* Row 4: Attachments */}
        <div style={{ marginTop: 16 }}>
          <label style={formLabelStyle}>Attachments ({attachments.length})</label>
          {attachments.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
              {attachments.map((att) => (
                <div
                  key={att.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    background: isDark ? alpha('#ffffff', 0.05) : '#f9fafb',
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 8, padding: '5px 10px', maxWidth: 220,
                  }}
                >
                  {att.type?.startsWith('image/') ? (
                    <img
                      src={att.url}
                      alt={att.name}
                      onClick={() => att.url && window.open(att.url, '_blank')}
                      style={{
                        width: 32, height: 32, objectFit: 'cover',
                        borderRadius: 4, cursor: 'pointer', flexShrink: 0,
                      }}
                    />
                  ) : (
                    <span
                      onClick={() => att.url && window.open(att.url, '_blank')}
                      style={{ fontSize: 20, cursor: 'pointer', flexShrink: 0 }}
                      title="Open file"
                    >📄</span>
                  )}
                  <span
                    onClick={() => att.url && window.open(att.url, '_blank')}
                    style={{
                      flex: 1, fontSize: 11, color: isDark ? '#60a5fa' : '#2563eb',
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      cursor: 'pointer', textDecoration: 'underline',
                    }}
                    title={att.name}
                  >{att.name}</span>
                  {!(!canCreate) && (
                    <button
                      type="button"
                      onClick={() => removeAttachment(att.id)}
                      style={{ background: 'none', border: 'none', color: '#dc2626', cursor: 'pointer', fontSize: 14, padding: '0 2px', flexShrink: 0 }}
                      title="Remove"
                    >✕</button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div
            onClick={() => !(!canCreate) && fileRef.current?.click()}
            style={{
              border: `2px dashed ${theme.palette.divider}`, borderRadius: 8,
              padding: '12px 16px', cursor: !canCreate ? 'not-allowed' : 'pointer', textAlign: 'center',
              color: !canCreate ? theme.palette.text.disabled : theme.palette.text.secondary,
              fontSize: 13, background: !canCreate ? (isDark ? alpha('#ffffff',0.03) : '#f9fafb') : (isDark ? alpha('#ffffff',0.04) : '#fff'),
              transition: 'all 0.2s',
            }}
            onMouseEnter={e => { if (canCreate) { e.currentTarget.style.borderColor = isDark ? '#60a5fa' : '#2563eb'; e.currentTarget.style.color = isDark ? '#60a5fa' : '#2563eb'; } }}
            onMouseLeave={e => { if (canCreate) { e.currentTarget.style.borderColor = theme.palette.divider; e.currentTarget.style.color = theme.palette.text.secondary; } }}
          >
            📎 {attachments.length > 0 ? 'Add more files' : 'Attach receipts, invoices, or documents'}
          </div>
          <input
            ref={fileRef}
            type="file"
            accept="image/*,.pdf,.doc,.docx,.xls,.xlsx"
            multiple
            disabled={!canCreate}
            style={{ display: 'none' }}
            onChange={handleFiles}
          />
        </div>
      </div>

      <BalanceBar totalDebit={totalDebit} totalCredit={totalCredit} isBalanced={isBalanced} difference={difference} canViewAmounts={canViewAmounts} />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, alignItems: 'start', marginBottom: 0 }}>
        <SectionCard
          title="Debit Entries"
          subtitle="Assets increase / liabilities decrease"
          color="#2563eb"
          titleColor={isDark ? '#60a5fa' : '#2563eb'}
          bg={isDark ? `linear-gradient(135deg, ${alpha('#2563eb', 0.15)}, ${alpha('#2563eb', 0.05)})` : "linear-gradient(135deg, #eff6ff, #dbeafe)"}
          icon="▲"
        >
          {debitLines.map((line, i) => (
            <SectionLine
              key={line.id}
              line={line}
              index={i}
              type="debit"
              ledgers={ledgers}
              loadingLedgers={loadingLedgers}
              onChange={updateLine(setDebitLines)}
              onRemove={removeLine(setDebitLines)}
              canRemove={debitLines.length > 1}
              canViewAmounts={canViewAmounts}
              disabled={!canCreate}
            />
          ))}
          <button type="button" onClick={addLine(setDebitLines)} disabled={!canCreate} style={addLineBtn('#2563eb', !canCreate)}>
            + Add Debit Line
          </button>
          <div style={lineTotalStyle(isDark ? alpha('#2563eb',0.15) : '#dbeafe', '#2563eb')}>
            <span style={{ fontSize: 13, color: isDark ? '#93c5fd' : '#1e40af', fontWeight: 600 }}>Total Debit</span>
            <span style={{ fontSize: 20, fontWeight: 800, color: isDark ? '#60a5fa' : '#1d4ed8' }}>₹{canViewAmounts ? totalDebit.toFixed(2) : '****'}</span>
          </div>
        </SectionCard>

        <SectionCard
          title="Credit Entries"
          subtitle="Liabilities increase / assets decrease"
          color="#16a34a"
          titleColor={isDark ? '#4ade80' : '#16a34a'}
          bg={isDark ? `linear-gradient(135deg, ${alpha('#16a34a', 0.15)}, ${alpha('#16a34a', 0.05)})` : "linear-gradient(135deg, #f0fdf4, #dcfce7)"}
          icon="▼"
        >
          {creditLines.map((line, i) => (
            <SectionLine
              key={line.id}
              line={line}
              index={i}
              type="credit"
              ledgers={ledgers}
              loadingLedgers={loadingLedgers}
              onChange={updateLine(setCreditLines)}
              onRemove={removeLine(setCreditLines)}
              canRemove={creditLines.length > 1}
              canViewAmounts={canViewAmounts}
              disabled={!canCreate}
            />
          ))}
          <button type="button" onClick={addLine(setCreditLines)} disabled={!canCreate} style={addLineBtn('#16a34a', !canCreate)}>
            + Add Credit Line
          </button>
          <div style={lineTotalStyle(isDark ? alpha('#16a34a',0.15) : '#dcfce7', '#16a34a')}>
            <span style={{ fontSize: 13, color: isDark ? '#86efac' : '#166534', fontWeight: 600 }}>Total Credit</span>
            <span style={{ fontSize: 20, fontWeight: 800, color: isDark ? '#4ade80' : '#15803d' }}>₹{canViewAmounts ? totalCredit.toFixed(2) : '****'}</span>
          </div>
        </SectionCard>
      </div>

      <div style={{ ...cardSx, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <div>
          {isBalanced ? (
            <p style={{ margin: 0, color: isDark ? '#4ade80' : '#16a34a', fontWeight: 600, fontSize: 14 }}>✓ Entry is balanced — ready to submit</p>
          ) : totalDebit + totalCredit > 0 ? (
            <p style={{ margin: 0, color: isDark ? '#f87171' : '#dc2626', fontWeight: 600, fontSize: 14 }}>✗ Unbalanced — difference: {canViewAmounts ? '₹' + difference.toFixed(2) : '****'}</p>
          ) : (
            <p style={{ margin: 0, color: theme.palette.text.secondary, fontSize: 14 }}>Enter debit and credit amounts above.</p>
          )}
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button type="button" onClick={resetForm} disabled={!canCreate} style={{ padding: '11px 22px', borderRadius: 10, border: `1px solid ${theme.palette.divider}`, background: isDark ? alpha('#ffffff',0.06) : '#f9fafb', color: theme.palette.text.primary, fontSize: 14, fontWeight: 600, cursor: !canCreate ? 'not-allowed' : 'pointer', opacity: !canCreate ? 0.5 : 1 }}>
            Reset
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!isBalanced || submitting || !canCreate}
            style={{
              padding: '11px 28px', borderRadius: 10, border: 'none',
              background: !isBalanced || submitting || !canCreate ? '#9ca3af' : 'linear-gradient(135deg, #2563eb, #7c3aed)',
              color: '#fff', fontSize: 14, fontWeight: 700,
              cursor: !isBalanced || submitting || !canCreate ? 'not-allowed' : 'pointer',
              boxShadow: isBalanced && !submitting && canCreate ? '0 4px 14px rgba(37,99,235,0.35)' : 'none',
              transition: 'all 0.2s', minWidth: 160,
            }}
          >
            {submitting ? '⏳ Submitting…' : '✓ Submit Journal Entry'}
          </button>
        </div>
      </div>

      {status && (
        <div style={{
          marginTop: 12, padding: '14px 18px', borderRadius: 10, fontSize: 14, fontWeight: 500,
          background: status.type === 'success' ? (isDark ? alpha('#16a34a',0.15) : '#f0fdf4') : status.type === 'warning' ? (isDark ? alpha('#d97706',0.15) : '#fffbeb') : (isDark ? alpha('#dc2626',0.15) : '#fef2f2'),
          color: status.type === 'success' ? '#16a34a' : status.type === 'warning' ? '#b45309' : '#dc2626',
          border: `1px solid ${status.type === 'success' ? (isDark ? alpha('#16a34a',0.4) : '#86efac') : status.type === 'warning' ? (isDark ? alpha('#d97706',0.4) : '#fde68a') : (isDark ? alpha('#dc2626',0.4) : '#fca5a5')}`,
        }}>
          {status.message}
        </div>
      )}
    </div>
  );
}

function SectionCard({ title, subtitle, color, titleColor, bg, icon, children }) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const cardStyle = { background: theme.palette.background.paper, borderRadius: 14, padding: '20px 24px', boxShadow: isDark ? 'none' : '0 1px 4px rgba(0,0,0,0.07)', border: `1px solid ${theme.palette.divider}`, marginBottom: 16 };
  return (
    <div style={{ ...cardStyle, padding: 0, overflow: 'hidden', marginBottom: 16 }}>
      <div style={{
        background: bg, padding: '14px 20px',
        borderBottom: `1px solid ${theme.palette.divider}`,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <span style={{
          width: 28, height: 28, borderRadius: 8,
          background: color, color: '#fff',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 900,
        }}>{icon}</span>
        <div>
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: isDark ? (title === 'Debit Entries' ? '#60a5fa' : '#4ade80') : color }}>{title}</h3>
          <p style={{ margin: 0, fontSize: 11, color: isDark ? '#94a3b8' : '#6b7280' }}>{subtitle}</p>
        </div>
      </div>
      <div style={{ padding: '16px 20px 20px' }}>{children}</div>
    </div>
  );
}

function BalanceBar({ totalDebit, totalCredit, isBalanced, difference, canViewAmounts = true }) {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const hasValues = totalDebit + totalCredit > 0;
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '14px 24px', borderRadius: 12, marginBottom: 16,
      background: !hasValues ? (isDark ? alpha('#ffffff',0.04) : '#f9fafb') : isBalanced ? (isDark ? alpha('#16a34a',0.12) : '#f0fdf4') : (isDark ? alpha('#dc2626',0.12) : '#fef2f2'),
      border: `2px solid ${!hasValues ? theme.palette.divider : isBalanced ? (isDark ? alpha('#16a34a',0.4) : '#86efac') : (isDark ? alpha('#dc2626',0.4) : '#fca5a5')}`,
      transition: 'all 0.3s',
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 11, color: theme.palette.text.secondary, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>Total Debit</div>
        <div style={{ fontSize: 22, fontWeight: 800, color: isDark ? '#60a5fa' : '#1d4ed8' }}>₹{canViewAmounts ? totalDebit.toFixed(2) : '****'}</div>
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          fontSize: 13, fontWeight: 700,
          color: !hasValues ? theme.palette.text.secondary : isBalanced ? (isDark ? '#4ade80' : '#16a34a') : (isDark ? '#f87171' : '#dc2626'),
        }}>
          {!hasValues ? '⚖ Awaiting Input' : isBalanced ? '✓ Balanced' : `✗ Difference: ${canViewAmounts ? '₹' + difference.toFixed(2) : '****'}`}
        </div>
        {hasValues && !isBalanced && (
          <div style={{ fontSize: 11, color: isDark ? '#f87171' : '#dc2626', marginTop: 2 }}>
            {totalDebit > totalCredit ? `Add ${canViewAmounts ? '₹' + difference.toFixed(2) : '****'} to credit` : `Add ${canViewAmounts ? '₹' + difference.toFixed(2) : '****'} to debit`}
          </div>
        )}
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 11, color: theme.palette.text.secondary, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>Total Credit</div>
        <div style={{ fontSize: 22, fontWeight: 800, color: isDark ? '#4ade80' : '#15803d' }}>₹{canViewAmounts ? totalCredit.toFixed(2) : '****'}</div>
      </div>
    </div>
  );
}

// cardStyle is now computed per-component via useTheme()

const addLineBtn = (color) => ({
  display: 'flex', alignItems: 'center', gap: 6,
  padding: '9px 18px', borderRadius: 8,
  border: `1.5px dashed ${color}88`,
  background: `${color}0d`, color,
  fontSize: 13, fontWeight: 600, cursor: 'pointer',
  marginBottom: 14, transition: 'all 0.15s',
});

const lineTotalStyle = (bg, color) => ({
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  background: bg, borderRadius: 10,
  padding: '10px 16px',
  border: `1px solid ${color}33`,
});
