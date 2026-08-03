'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '../../apiClient';

const fmt = n => `₹${Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
const today = () => new Date().toISOString().slice(0, 10);

const C = {
  green: '#059669', greenBg: '#ecfdf5', greenBorder: '#a7f3d0',
  red: '#dc2626', redBg: '#fef2f2', redBorder: '#fecaca',
  blue: '#2563eb', blueBg: '#eff6ff', blueBorder: '#bfdbfe',
  slate: '#64748b', slateBg: '#f8fafc', slateBorder: '#e2e8f0',
  text: '#0f172a', muted: '#64748b', border: '#e2e8f0', surface: '#ffffff',
};

const DEPARTMENTS = [
  'Marketing', 'Customer Relation Management', 'Operations', 'Design',
  'Logistics', 'Purchase', 'Sales / Business Development', 'Finance',
  'Information Technology', 'Human Resource', 'Production', 'Services',
  'House Keeping', 'Other'
];

const inputStyle = {
  width: '100%', padding: '9px 12px', border: `1px solid ${C.border}`,
  borderRadius: 8, fontSize: 13, color: C.text, background: '#fff',
  outline: 'none', boxSizing: 'border-box', minHeight: 38,
};
const labelStyle = {
  display: 'block', fontSize: 11, fontWeight: 700, color: C.muted,
  textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4,
};

/* ── Custom Party Select ──────────────────────────────────────── */
function AddableSelect({ value, onChange, options, placeholder, disabled }) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState('');
  const [custom, setCustom] = useState([]);
  const ref = useRef(null);

  const all = [...options, ...custom];
  const SENTINEL = '__add__';

  const handle = e => {
    if (e.target.value === SENTINEL) { setAdding(true); setDraft(''); setTimeout(() => ref.current?.focus(), 50); return; }
    onChange(e.target.value);
  };

  const confirm = () => {
    const t = draft.trim();
    if (!t) { setAdding(false); return; }
    if (!all.includes(t)) setCustom(p => [...p, t]);
    onChange(t); setAdding(false); setDraft('');
  };

  if (adding) return (
    <div style={{ display: 'flex', gap: 4 }}>
      <input ref={ref} value={draft} onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); confirm(); } if (e.key === 'Escape') setAdding(false); }}
        placeholder="Type & press Enter…" style={{ ...inputStyle, flex: 1, borderColor: C.blue }} autoFocus />
      <button type="button" onClick={confirm} style={{ padding: '0 10px', background: C.blue, color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 700 }}>✓</button>
      <button type="button" onClick={() => setAdding(false)} style={{ padding: '0 8px', background: C.slateBg, border: `1px solid ${C.border}`, borderRadius: 6, cursor: 'pointer', color: C.muted }}>✕</button>
    </div>
  );

  return (
    <select value={value} onChange={handle} style={inputStyle} disabled={disabled}>
      <option value="">{placeholder || '— Select —'}</option>
      {all.map(o => <option key={o} value={o}>{o}</option>)}
      <option value={SENTINEL} style={{ color: C.blue, fontWeight: 600 }}>+ Add new…</option>
    </select>
  );
}

/* ── Custom Party Select ──────────────────────────────────────── */
function AddablePartySelect({ value, onChange, options, placeholder, disabled }) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState('');
  const [custom, setCustom] = useState([]);
  const ref = useRef(null);

  const all = [...options, ...custom];
  const SENTINEL = '__add__';

  const handle = e => {
    if (e.target.value === SENTINEL) { setAdding(true); setDraft(''); setTimeout(() => ref.current?.focus(), 50); return; }
    onChange(e.target.value);
  };

  const confirm = () => {
    const t = draft.trim();
    if (!t) { setAdding(false); return; }
    if (!all.includes(t)) setCustom(p => [...p, t]);
    onChange(t); setAdding(false); setDraft('');
  };

  if (adding) return (
    <div style={{ display: 'flex', gap: 4 }}>
      <input ref={ref} value={draft} onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); confirm(); } if (e.key === 'Escape') setAdding(false); }}
        placeholder="Type & press Enter…" style={{ ...inputStyle, flex: 1, borderColor: C.blue }} autoFocus />
      <button type="button" onClick={confirm} style={{ padding: '0 10px', background: C.blue, color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer', fontWeight: 700 }}>✓</button>
      <button type="button" onClick={() => setAdding(false)} style={{ padding: '0 8px', background: C.slateBg, border: `1px solid ${C.border}`, borderRadius: 6, cursor: 'pointer', color: C.muted }}>✕</button>
    </div>
  );

  return (
    <select value={value} onChange={handle} style={inputStyle} disabled={disabled}>
      <option value="">{placeholder || '— Select Party —'}</option>
      {all.map(o => <option key={o} value={o}>{o}</option>)}
      <option value={SENTINEL} style={{ color: C.blue, fontWeight: 600 }}>+ Add new…</option>
    </select>
  );
}

/* ── Create Invoice Modal ─────────────────────────────────────── */
function CreateInvoiceModal({ onClose, onSuccess, accounts }) {
  const [form, setForm] = useState({
    type: 'sales', party_name: '', amount: '', department: '', due_date: today(), description: '',
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const [partySuggestions, setPartySuggestions] = useState([]);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  useEffect(() => {
    Promise.all([
      apiClient('/api/customers?limit=100').then(r => r.json()).catch(() => null),
      apiClient('/api/workforce?limit=100').then(r => r.json()).catch(() => null)
    ]).then(([custData, wfData]) => {
      const parties = new Set();
      if (custData?.success) {
        const arr = Array.isArray(custData.data) ? custData.data : (Array.isArray(custData.data?.results) ? custData.data.results : []);
        arr.forEach(c => c.company_name && parties.add(c.company_name));
      }
      if (wfData?.success) {
        const arr = Array.isArray(wfData.data) ? wfData.data : (Array.isArray(wfData.data?.results) ? wfData.data.results : []);
        arr.forEach(w => w.full_name && parties.add(w.full_name));
      }
      setPartySuggestions([...parties].sort());
    });
  }, []);

  const handleAmountChange = e => {
    let raw = e.target.value.replace(/[^0-9.]/g, '');
    const parts = raw.split('.');
    if (parts.length > 2) raw = parts[0] + '.' + parts.slice(1).join('');
    let formatted = parts[0];
    if (formatted.length > 3) {
      formatted = formatted.substring(0, formatted.length - 3).replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + formatted.substring(formatted.length - 3);
    }
    if (parts.length > 1) formatted += '.' + parts[1];
    set('amount', formatted);
  };

  const submit = async () => {
    if (!form.party_name.trim()) return setErr('Party name is required.');
    const rawAmount = parseFloat(String(form.amount).replace(/,/g, ''));
    if (!form.amount || isNaN(rawAmount) || rawAmount <= 0) return setErr('Enter a valid amount.');
    setSaving(true); setErr('');
    try {
      const res = await apiClient('/api/accounting/invoices/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, amount: rawAmount }),
      });
      const data = await res.json();
      if (res.status === 401 || res.status === 403) {
        window.dispatchEvent(new Event('auth_logout'));
        return;
      }

      console.log('Invoice create response:', res.status, data);
      if (data?.success) { onSuccess(); onClose(); }
      else {
        // Handle both DRF error wrapper {error:{message,details}} and direct {message,errors} formats
        let msg = data?.message || data?.error?.message || 'Failed to create invoice.';
        const errors = data?.errors || data?.error?.details;
        if (errors && typeof errors === 'object') {
          const details = Object.entries(errors)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
            .join(' | ');
          if (details) msg += ` (${details})`;
        }
        setErr(msg);
      }
    } catch (e) { console.error('Invoice create error:', e); setErr('Network error.'); }
    setSaving(false);
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ background: C.surface, borderRadius: 16, padding: 28, width: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.18)', maxHeight: '90vh', overflowY: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 22 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: C.text }}>New Sales Invoice</h2>
            <p style={{ margin: '3px 0 0', fontSize: 12, color: C.muted }}>Creates a receivable. Journal entry at settlement.</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: C.muted }}>✕</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div style={{ gridColumn: '1/-1' }}>
            <label style={labelStyle}>Party Name (Customer) *</label>
            <AddablePartySelect value={form.party_name} onChange={v => set('party_name', v)} options={partySuggestions} placeholder="— Select Party —" disabled={saving} />
          </div>
          <div>
            <label style={labelStyle}>Amount (₹) *</label>
            <input style={inputStyle} type="text" inputMode="decimal" placeholder="0.00" value={form.amount} onChange={handleAmountChange} />
          </div>
          <div>
            <label style={labelStyle}>Due Date</label>
            <input style={inputStyle} type="date" lang="en-GB" value={form.due_date} onChange={e => set('due_date', e.target.value)} />
          </div>
          <div>
            <label style={labelStyle}>Department</label>
            <AddableSelect value={form.department} onChange={v => set('department', v)} options={DEPARTMENTS} placeholder="— Select Department —" disabled={saving} />
          </div>
          <div>
            <label style={labelStyle}>Description</label>
            <input style={inputStyle} placeholder="Optional note…" value={form.description} onChange={e => set('description', e.target.value)} />
          </div>
        </div>

        {err && <p style={{ margin: '14px 0 0', fontSize: 13, color: C.red, fontWeight: 600 }}>{err}</p>}

        <div style={{ display: 'flex', gap: 10, marginTop: 22, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '10px 20px', border: `1px solid ${C.border}`, background: C.slateBg, borderRadius: 9, fontSize: 13, fontWeight: 600, cursor: 'pointer', color: C.text }}>Cancel</button>
          <button onClick={submit} disabled={saving} style={{ padding: '10px 24px', background: saving ? '#9ca3af' : '#2563eb', color: '#fff', border: 'none', borderRadius: 9, fontSize: 13, fontWeight: 700, cursor: saving ? 'not-allowed' : 'pointer' }}>
            {saving ? 'Creating…' : 'Create Invoice'}
          </button>
        </div>
      </div>
    </div>
  );
}



/* ── Status Badge ─────────────────────────────────────────────── */
function StatusBadge({ status }) {
  const s = status === 'settled'
    ? { bg: C.greenBg, color: C.green, label: '✓ Settled' }
    : { bg: '#fef3c7', color: '#b45309', label: '⏳ Pending' };
  return <span style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700, background: s.bg, color: s.color }}>{s.label}</span>;
}

function MultiSelectDropdown({ label, options, selected, onChange, activeColor, activeBgColor }) {
  const [open, setOpen] = useState(false);
  const ref = useRef();
  useEffect(() => {
    const handleClick = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const toggle = (opt) => {
    if (selected.includes(opt)) onChange(selected.filter(x => x !== opt));
    else onChange([...selected, opt]);
  };

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen(!open)} style={{ padding: '6px 12px', border: 'none', borderRadius: 6, fontSize: 12, background: selected.length ? activeBgColor : '#fff', color: selected.length ? activeColor : C.muted, cursor: 'pointer', outline: 'none', fontWeight: selected.length ? 600 : 400, boxShadow: '0 1px 2px rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', gap: 6 }}>
        {label} {selected.length > 0 && `(${selected.length})`}
        <span style={{ fontSize: 10 }}>▼</span>
      </button>
      {open && (
        <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, boxShadow: '0 10px 25px rgba(0,0,0,0.1)', zIndex: 100, minWidth: 180, maxHeight: 250, overflowY: 'auto', padding: 6 }}>
          {options.length === 0 ? <div style={{ padding: '8px 12px', fontSize: 12, color: C.muted }}>No options</div> : null}
          {options.map(opt => (
            <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', fontSize: 12, cursor: 'pointer', borderRadius: 4, transition: 'background 0.1s' }} onMouseEnter={e => e.currentTarget.style.background = C.slateBg} onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
              <input type="checkbox" checked={selected.includes(opt)} onChange={() => toggle(opt)} style={{ cursor: 'pointer' }} />
              <span style={{ color: C.text }}>{opt}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

function exportCSV(rows, filename) {
  const cols = ['S.No', 'party_name', 'department', 'amount', 'due_date', 'status'];
  const header = 'S.No,Party Name,Department,Amount,Due Date,Status';
  const body = rows.map((r, i) => cols.map(k => `"${(k === 'S.No' ? (i + 1) : k === 'amount' ? Number(r[k]).toFixed(2) : (r[k] ?? '')).toString().replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([header + '\n' + body], { type: 'text/csv' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = filename; a.click();
}

/* ── Main Component ───────────────────────────────────────────── */
export default function AccountingInvoicesSales({ onRefresh, dateParams }) {
  const [invoices, setInvoices] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [deptFilter, setDeptFilter] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [sortBy, setSortBy] = useState('date_desc');

  const load = useCallback(async () => {
    setLoading(true);
    const q = dateParams ? `&${dateParams}` : '';
    const [inv, acc] = await Promise.all([
      apiClient(`/api/accounting/invoices?type=sales${q}`).then(r => r.json()).catch(() => null),
      apiClient('/api/accounting/accounts/').then(r => r.json()).catch(() => null),
    ]);
    if (inv?.success) setInvoices(inv.data || []);
    if (acc?.success) setAccounts(acc.data || []);
    setLoading(false);
  }, [dateParams]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    let rows = invoices;
    if (statusFilter) rows = rows.filter(r => r.status === statusFilter);
    if (deptFilter.length > 0) rows = rows.filter(r => deptFilter.includes(r.department || 'None'));
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(r => (r.party_name || '').toLowerCase().includes(q) || (r.description || '').toLowerCase().includes(q));
    }
    rows.sort((a, b) => {
      if (sortBy === 'date_desc') return new Date(b.date || b.due_date || b.created_at) - new Date(a.date || a.due_date || a.created_at);
      if (sortBy === 'date_asc') return new Date(a.date || a.due_date || a.created_at) - new Date(b.date || b.due_date || b.created_at);
      if (sortBy === 'amount_high') return b.amount - a.amount;
      if (sortBy === 'amount_low') return a.amount - b.amount;
      return 0;
    });
    return rows;
  }, [invoices, search, statusFilter, deptFilter, sortBy]);

  const totalPending = invoices.filter(i => i.status === 'pending').reduce((s, i) => s + Number(i.amount), 0);
  const totalSettled = invoices.filter(i => i.status === 'settled').reduce((s, i) => s + Number(i.amount), 0);
  const depts = [...new Set(invoices.map(i => i.department || 'None'))].sort();

  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length && filtered.length > 0) setSelectedIds(new Set());
    else setSelectedIds(new Set(filtered.map(s => s.id)));
  };

  const toggleSelect = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  useEffect(() => { setSelectedIds(new Set()); }, [filtered]);

  const target = selectedIds.size > 0 ? filtered.filter(s => selectedIds.has(s.id)) : filtered;

  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
      <style>{`
        @media print { 
          body * { visibility: hidden; }
          .print-area, .print-area * { visibility: visible; }
          .print-area { position: absolute; left: 0; top: 0; width: 100%; margin: 0; padding: 0; }
          .no-print { display: none !important; }
          .print-only { display: table-cell !important; }
          .hide-in-print { display: none !important; }
        }
      `}</style>
      {/* Header */}
      <div className="no-print" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: C.text }}>Sales Invoices</h3>
          <p style={{ margin: '3px 0 0', fontSize: 12, color: C.muted }}>Receivables — journal entries created only at settlement.</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 3, background: '#fff', borderRadius: 8, padding: 3, boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }}>
            {[['date_desc', 'Newest'], ['date_asc', 'Oldest'], ['amount_high', 'Amount: High to Low'], ['amount_low', 'Amount: Low to High']].map(([k, l]) => (
              <button key={k} onClick={() => setSortBy(k)} style={{
                padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: sortBy === k ? 700 : 500,
                border: 'none', cursor: 'pointer',
                background: sortBy === k ? C.blue : 'transparent',
                color: sortBy === k ? '#fff' : C.muted,
                transition: 'all 0.14s',
              }}>{l}</button>
            ))}
          </div>
          <button onClick={() => exportCSV(target, 'sales_invoices.csv')} style={{ padding: '9px 14px', background: C.surface, color: C.text, border: `1px solid ${C.border}`, borderRadius: 9, fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
            Export CSV {selectedIds.size > 0 ? `(${selectedIds.size})` : ''}
          </button>
          <button onClick={() => window.print()} style={{ padding: '9px 14px', background: C.surface, color: C.text, border: `1px solid ${C.border}`, borderRadius: 9, fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
            Print {selectedIds.size > 0 ? `(${selectedIds.size})` : ''}
          </button>
          <button onClick={() => setShowCreate(true)} style={{ padding: '8px 16px', background: '#fff', color: '#111827', border: '1px solid #e5e7eb', borderRadius: 8, fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
            + New Invoice
          </button>
        </div>
      </div>

      {/* KPI row */}
      <div className="no-print" style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12, marginBottom: 20 }}>
        {[
          { label: 'Total Invoices', value: invoices.length, color: C.text, note: 'all time' },
          { label: 'Pending', value: fmt(totalPending), color: '#b45309', note: `${invoices.filter(i => i.status === 'pending').length} invoices` },
          { label: 'Settled', value: fmt(totalSettled), color: C.green, note: `${invoices.filter(i => i.status === 'settled').length} invoices` },
        ].map((k, i) => (
          <div key={i} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '16px 18px', boxShadow: '0 1px 4px rgba(0,0,0,0.05)' }}>
            <p style={{ margin: '0 0 8px', fontSize: 11, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.7 }}>{k.label}</p>
            <p style={{ margin: 0, fontSize: 22, fontWeight: 800, color: k.color, letterSpacing: -0.5 }}>{k.value}</p>
            <p style={{ margin: '5px 0 0', fontSize: 11, color: C.muted }}>{k.note}</p>
          </div>
        ))}
      </div>

      {/* Filter bar */}
      <div className="no-print" style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '8px 12px', background: C.slateBg, border: `1px solid ${C.border}`, borderRadius: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <input type="text" placeholder="Search party or description…" value={search} onChange={e => setSearch(e.target.value)}
          style={{ flex: '1 1 180px', minWidth: 140, padding: '6px 10px', border: 'none', borderRadius: 6, fontSize: 12, background: '#fff', outline: 'none', boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }} />
        <div style={{ width: 1, height: 20, background: C.border }} />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          style={{ padding: '6px 8px', border: 'none', borderRadius: 6, fontSize: 12, background: statusFilter ? C.blueBg : '#fff', color: statusFilter ? C.blue : C.muted, cursor: 'pointer', outline: 'none', fontWeight: statusFilter ? 600 : 400, boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }}>
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="settled">Settled</option>
        </select>
        <MultiSelectDropdown label="Department" options={depts} selected={deptFilter} onChange={setDeptFilter} activeBgColor={C.blueBg} activeColor={C.blue} />
        {(search || statusFilter || deptFilter.length > 0) && (
          <button onClick={() => { setSearch(''); setStatusFilter(''); setDeptFilter([]); }}
            style={{ padding: '4px 10px', background: 'none', border: 'none', fontSize: 11, fontWeight: 600, color: C.red, cursor: 'pointer' }}>Clear</button>
        )}
        <span style={{ marginLeft: 'auto', fontSize: 12, color: C.muted, fontWeight: 600 }}>{filtered.length} result{filtered.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Table */}
      <div className="print-area" style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.05)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: C.slateBg }}>
              <th className="no-print" style={{ padding: '10px 14px', width: 40, borderBottom: `1px solid ${C.border}` }}>
                <input type="checkbox" checked={filtered.length > 0 && selectedIds.size === filtered.length} onChange={toggleSelectAll} style={{ cursor: 'pointer' }} />
              </th>
              <th className="print-only" style={{ padding: '10px 14px', fontSize: 11, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.5, borderBottom: `1px solid ${C.border}`, textAlign: 'left', display: 'none' }}>S.No</th>
              {['#', 'Party Name', 'Department', 'Amount', 'Due Date', 'Status'].map((h, i) => (
                <th key={i} className={h === '#' ? 'no-print' : ''} style={{ padding: '10px 14px', fontSize: 11, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.5, textAlign: i >= 3 ? 'right' : 'left', borderBottom: `1px solid ${C.border}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} style={{ padding: 28, textAlign: 'center', color: C.muted, fontSize: 13 }}>Loading…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={7} style={{ padding: 36, textAlign: 'center', color: C.muted, fontSize: 13 }}>No invoices found.</td></tr>
            ) : filtered.map((inv, i) => {
              const isSelected = selectedIds.has(inv.id);
              const hideInPrintClass = selectedIds.size > 0 && !isSelected ? 'hide-in-print' : '';

              return (
                <tr key={inv.id} className={hideInPrintClass} style={{ borderBottom: `1px solid ${C.slateBg}`, background: isSelected ? C.blueBg : 'transparent', transition: 'background 0.1s', cursor: 'pointer' }}
                  onClick={() => toggleSelect(inv.id)}
                  onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = C.slateBg; }}
                  onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}>
                  <td className="no-print" style={{ padding: '12px 14px' }}>
                    <input type="checkbox" checked={isSelected} onChange={() => toggleSelect(inv.id)} onClick={e => e.stopPropagation()} style={{ cursor: 'pointer' }} />
                  </td>
                  <td className="print-only" style={{ padding: '12px 14px', fontSize: 13, color: C.text, display: 'none' }}>{i + 1}</td>
                  <td className="no-print" style={{ padding: '12px 14px', fontSize: 12, color: C.muted, fontFamily: 'monospace' }}>#{inv.id}</td>
                  <td style={{ padding: '12px 14px' }}>
                    <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: C.text }}>{inv.party_name}</p>
                    {inv.description && <p style={{ margin: '2px 0 0', fontSize: 11, color: C.muted }}>{inv.description}</p>}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    {inv.department ? (
                      <span style={{ padding: '2px 9px', background: C.slateBg, borderRadius: 20, fontSize: 11, fontWeight: 600, color: C.slate }}>{inv.department}</span>
                    ) : <span style={{ color: C.muted, fontSize: 12 }}>—</span>}
                  </td>
                  <td style={{ padding: '12px 14px', textAlign: 'right', fontSize: 14, fontWeight: 800, color: C.green }}>{fmt(inv.amount)}</td>
                  <td style={{ padding: '12px 14px', textAlign: 'right', fontSize: 12, color: inv.due_date ? C.muted : C.muted }}>{inv.due_date || '—'}</td>
                  <td style={{ padding: '12px 14px', textAlign: 'right' }}><StatusBadge status={inv.status} /></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {showCreate && <CreateInvoiceModal accounts={accounts} onClose={() => setShowCreate(false)} onSuccess={() => { load(); if (onRefresh) onRefresh(); }} />}
    </div>
  );
}
