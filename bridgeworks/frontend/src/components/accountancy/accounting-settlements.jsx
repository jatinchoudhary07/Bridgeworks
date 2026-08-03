'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '../../apiClient';

const fmt = n => `₹${Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

const C = {
  green: '#059669', greenBg: '#ecfdf5',
  red: '#dc2626', redBg: '#fef2f2',
  blue: '#2563eb', blueBg: '#eff6ff',
  amber: '#d97706', amberBg: '#fffbeb',
  slate: '#64748b', slateBg: '#f8fafc',
  text: '#0f172a', muted: '#64748b', border: '#e2e8f0', surface: '#ffffff',
};

function MultiSelectDropdown({ label, options, selected, onChange }) {
  const [open, setOpen] = useState(false);
  const ref = useRef();
  useEffect(() => {
    const handleClick = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);
  const toggle = opt => {
    if (selected.includes(opt)) onChange(selected.filter(x => x !== opt));
    else onChange([...selected, opt]);
  };
  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button onClick={() => setOpen(!open)} style={{ padding: '6px 12px', border: 'none', borderRadius: 6, fontSize: 12, background: selected.length ? C.blueBg : '#fff', color: selected.length ? C.blue : C.muted, cursor: 'pointer', outline: 'none', fontWeight: selected.length ? 600 : 400, boxShadow: '0 1px 2px rgba(0,0,0,0.06)', display: 'flex', alignItems: 'center', gap: 6 }}>
        {label} {selected.length > 0 && `(${selected.length})`}
        <span style={{ fontSize: 10 }}>▼</span>
      </button>
      {open && (
        <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, background: '#fff', border: `1px solid ${C.border}`, borderRadius: 8, boxShadow: '0 10px 25px rgba(0,0,0,0.1)', zIndex: 100, minWidth: 180, maxHeight: 250, overflowY: 'auto', padding: 6 }}>
          {options.length === 0 ? <div style={{ padding: '8px 12px', fontSize: 12, color: C.muted }}>No options</div> : null}
          {options.map(opt => (
            <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', fontSize: 12, cursor: 'pointer', borderRadius: 4 }}>
              <input type="checkbox" checked={selected.includes(opt)} onChange={() => toggle(opt)} style={{ cursor: 'pointer' }} />
              <span style={{ color: C.text }}>{opt}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

function BulkFolder({ bulk }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden', marginBottom: 10 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', background: open ? '#fffbeb' : C.slateBg, border: 'none', cursor: 'pointer', textAlign: 'left', transition: 'background 0.15s' }}
      >
        <span style={{ fontSize: 20 }}>{open ? '📂' : '📁'}</span>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{bulk.label || `Bulk Settlement #${bulk.id}`}</span>
            <span style={{ padding: '2px 8px', background: '#fef3c7', color: '#92400e', borderRadius: 20, fontSize: 10, fontWeight: 700, textTransform: 'uppercase' }}>BULK</span>
            <span style={{ padding: '2px 8px', background: C.slateBg, border: `1px solid ${C.border}`, borderRadius: 20, fontSize: 10, fontWeight: 600, color: C.muted }}>{bulk.items_count} items</span>
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 4, fontSize: 12, color: C.muted }}>
            <span>📅 {bulk.settlement_date}</span>
            <span>🏦 {bulk.settlement_account_name || '—'}</span>
            <span style={{ fontWeight: 700, color: C.amber }}>Total: {fmt(bulk.total_amount)}</span>
          </div>
        </div>
        <span style={{ fontSize: 20, color: C.muted, transition: 'transform 0.2s', transform: open ? 'rotate(90deg)' : 'rotate(0deg)', display: 'inline-block' }}>›</span>
      </button>

      {open && (
        <div style={{ borderTop: `1px solid ${C.border}`, background: '#fff' }}>
          {(!bulk.items || bulk.items.length === 0) ? (
            <div style={{ padding: '20px', textAlign: 'center', color: C.muted, fontSize: 13 }}>No items found.</div>
          ) : bulk.items.map((item, idx) => (
            <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 18px 10px 28px', borderBottom: idx < bulk.items.length - 1 ? `1px solid ${C.slateBg}` : 'none', background: idx % 2 === 0 ? '#fff' : '#fafafa' }}>
              <div style={{ width: 24, height: 24, borderRadius: 6, background: item.type === 'receivable' ? C.blueBg : C.redBg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, color: item.type === 'receivable' ? C.blue : C.red, flexShrink: 0 }}>
                {item.type === 'receivable' ? '↓' : '↑'}
              </div>
              <div style={{ flex: 1 }}>
                <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: C.text }}>{item.party_name}</p>
                {item.department && <span style={{ fontSize: 11, color: C.muted }}>{item.department}</span>}
              </div>
              <span style={{ padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: item.type === 'receivable' ? C.blueBg : C.redBg, color: item.type === 'receivable' ? C.blue : C.red }}>
                {item.type === 'receivable' ? 'Received' : 'Paid'}
              </span>
              <span style={{ fontSize: 13, fontWeight: 800, color: item.type === 'receivable' ? C.green : C.red, minWidth: 90, textAlign: 'right' }}>{fmt(item.amount)}</span>
            </div>
          ))}
          {bulk.notes && (
            <div style={{ padding: '10px 18px', background: '#fffbeb', borderTop: `1px solid ${C.border}`, fontSize: 12, color: C.amber }}>
              📝 {bulk.notes}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function AccountingSettlements() {
  const [tab, setTab] = useState('individual');
  const [settlements, setSettlements] = useState([]);
  const [bulkSettlements, setBulkSettlements] = useState([]);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [deptFilter, setDeptFilter] = useState([]);
  const [accountFilter, setAccountFilter] = useState([]);
  const [sortBy, setSortBy] = useState('date_desc');
  const [selectedIds, setSelectedIds] = useState(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [indivRes, bulkRes] = await Promise.all([
        apiClient('/api/accounting/outstandings/?status=paid'),
        apiClient('/api/accounting/bulk-settlements/'),
      ]);
      if (indivRes.status === 401 || indivRes.status === 403) { window.dispatchEvent(new Event('auth_logout')); return; }
      const indivData = await indivRes.json();
      const bulkData = await bulkRes.json().catch(() => null);
      if (indivData.success) setSettlements(indivData.data || []);
      if (bulkData?.success) setBulkSettlements(bulkData.data || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    let rows = settlements;
    if (typeFilter) rows = rows.filter(r => r.type === typeFilter);
    if (deptFilter.length > 0) rows = rows.filter(r => deptFilter.includes(r.department || 'None'));
    if (accountFilter.length > 0) rows = rows.filter(r => accountFilter.includes(r.settlement_account_name || 'None'));
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(r =>
        (r.party_name || '').toLowerCase().includes(q) ||
        (r.description || '').toLowerCase().includes(q) ||
        (r.settlement_account_name || '').toLowerCase().includes(q)
      );
    }
    rows.sort((a, b) => {
      if (sortBy === 'date_desc') return new Date(b.updated_at) - new Date(a.updated_at);
      if (sortBy === 'date_asc') return new Date(a.updated_at) - new Date(b.updated_at);
      if (sortBy === 'amount_high') return b.amount - a.amount;
      if (sortBy === 'amount_low') return a.amount - b.amount;
      return 0;
    });
    return rows;
  }, [settlements, search, typeFilter, deptFilter, accountFilter, sortBy]);

  const filteredBulk = useMemo(() => {
    if (!search.trim()) return bulkSettlements;
    const q = search.toLowerCase();
    return bulkSettlements.filter(b => (b.label || '').toLowerCase().includes(q) || (b.settlement_account_name || '').toLowerCase().includes(q));
  }, [bulkSettlements, search]);

  const depts = [...new Set(settlements.map(i => i.department || 'None'))].sort();
  const accounts = [...new Set(settlements.map(i => i.settlement_account_name || 'None'))].sort();

  const toggleSelectAll = () => {
    if (selectedIds.size === filtered.length && filtered.length > 0) setSelectedIds(new Set());
    else setSelectedIds(new Set(filtered.map(s => s.id)));
  };
  const toggleSelect = id => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelectedIds(next);
  };
  useEffect(() => { setSelectedIds(new Set()); }, [filtered]);

  const handleExportCSV = () => {
    const toExport = selectedIds.size > 0 ? filtered.filter(s => selectedIds.has(s.id)) : filtered;
    const head = ['S.No', 'Party', 'Type', 'Department', 'Via Account', 'Date', 'Amount'];
    const csv = [head.join(','), ...toExport.map((r, idx) => [
      idx + 1,
      `"${(r.party_name || '').replace(/"/g, '""')}"`,
      r.type === 'receivable' ? 'Received' : 'Paid',
      `"${(r.department || '').replace(/"/g, '""')}"`,
      `"${(r.settlement_account_name || '').replace(/"/g, '""')}"`,
      r.updated_at ? r.updated_at.substring(0, 10) : '',
      r.amount
    ].join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const u = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = u; a.download = `settlements_${new Date().toISOString().slice(0, 10)}.csv`; a.click();
  };

  const tabBtn = k => ({
    padding: '9px 20px', fontSize: 13, fontWeight: tab === k ? 700 : 500,
    border: 'none', background: 'transparent', cursor: 'pointer',
    borderBottom: tab === k ? `2px solid ${C.blue}` : '2px solid transparent',
    color: tab === k ? C.blue : C.muted, transition: 'all 0.15s',
  });

  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
      <style>{`
        @media print {
          body * { visibility: hidden; }
          .print-area, .print-area * { visibility: visible; }
          .print-area { position: absolute; left: 0; top: 0; width: 100%; margin: 0; padding: 0; }
          .no-print { display: none !important; }
          .hide-in-print { display: none !important; }
        }
      `}</style>

      {/* Header */}
      <div className="no-print" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 3, background: '#fff', borderRadius: 8, padding: 3, boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }}>
            {[['date_desc', 'Newest'], ['date_asc', 'Oldest'], ['amount_high', 'High'], ['amount_low', 'Low']].map(([k, l]) => (
              <button key={k} onClick={() => setSortBy(k)} style={{ padding: '5px 10px', borderRadius: 7, fontSize: 12, fontWeight: sortBy === k ? 700 : 500, border: 'none', cursor: 'pointer', background: sortBy === k ? C.blue : 'transparent', color: sortBy === k ? '#fff' : C.muted }}>{l}</button>
            ))}
          </div>
          {tab === 'individual' && (
            <>
              <button onClick={handleExportCSV} style={{ padding: '8px 14px', background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 12, fontWeight: 600, color: C.text, cursor: 'pointer' }}>
                Export CSV {selectedIds.size > 0 ? `(${selectedIds.size})` : ''}
              </button>
              <button onClick={() => window.print()} style={{ padding: '8px 14px', background: C.surface, border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 12, fontWeight: 600, color: C.text, cursor: 'pointer' }}>Print</button>
            </>
          )}
        </div>
      </div>

      {/* Tab bar */}
      <div className="no-print" style={{ borderBottom: `1px solid ${C.border}`, marginBottom: 16, display: 'flex' }}>
        <button style={tabBtn('individual')} onClick={() => setTab('individual')}>Individual Settlements</button>
        <button style={tabBtn('bulk')} onClick={() => setTab('bulk')}>
          Bulk Folders
          {bulkSettlements.length > 0 && (
            <span style={{ marginLeft: 6, padding: '1px 7px', background: '#fef3c7', color: '#92400e', borderRadius: 20, fontSize: 10, fontWeight: 700 }}>{bulkSettlements.length}</span>
          )}
        </button>
      </div>

      {/* Filter bar */}
      <div className="no-print" style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '8px 12px', background: C.slateBg, border: `1px solid ${C.border}`, borderRadius: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <input type="text" placeholder={tab === 'bulk' ? 'Search batch label or account…' : 'Search party, description, or account…'} value={search} onChange={e => setSearch(e.target.value)}
          style={{ flex: '1 1 180px', minWidth: 140, padding: '6px 10px', border: 'none', borderRadius: 6, fontSize: 12, background: '#fff', outline: 'none', boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }} />
        {tab === 'individual' && (
          <>
            <div style={{ width: 1, height: 20, background: C.border }} />
            <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
              style={{ padding: '6px 8px', border: 'none', borderRadius: 6, fontSize: 12, background: typeFilter ? C.blueBg : '#fff', color: typeFilter ? C.blue : C.muted, cursor: 'pointer', outline: 'none' }}>
              <option value="">All Types</option>
              <option value="receivable">Received</option>
              <option value="payable">Paid</option>
            </select>
            <MultiSelectDropdown label="Department" options={depts} selected={deptFilter} onChange={setDeptFilter} />
            <MultiSelectDropdown label="Via Account" options={accounts} selected={accountFilter} onChange={setAccountFilter} />
          </>
        )}
        {(search || typeFilter || deptFilter.length > 0 || accountFilter.length > 0) && (
          <button onClick={() => { setSearch(''); setTypeFilter(''); setDeptFilter([]); setAccountFilter([]); }}
            style={{ padding: '4px 10px', background: 'none', border: 'none', fontSize: 11, fontWeight: 600, color: C.red, cursor: 'pointer' }}>Clear</button>
        )}
        <span style={{ marginLeft: 'auto', fontSize: 12, color: C.muted, fontWeight: 600 }}>
          {tab === 'bulk' ? `${filteredBulk.length} folder(s)` : `${filtered.length} result(s)`}
        </span>
      </div>

      {/* BULK FOLDERS TAB */}
      {tab === 'bulk' && (
        <div>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: C.muted }}>Loading…</div>
          ) : filteredBulk.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: C.muted, background: C.surface, borderRadius: 12, border: `1px solid ${C.border}` }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📁</div>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>No bulk settlements yet.</p>
              <p style={{ margin: '6px 0 0', fontSize: 13 }}>Select 2+ pending items in P&amp;R and click ⚡ Bulk Settle.</p>
            </div>
          ) : filteredBulk.map(bulk => <BulkFolder key={bulk.id} bulk={bulk} />)}
        </div>
      )}

      {/* INDIVIDUAL SETTLEMENTS TAB */}
      {tab === 'individual' && (
        <div className="print-area" style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.05)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: C.slateBg }}>
                <th className="no-print" style={{ padding: '10px 14px', width: 40, borderBottom: `1px solid ${C.border}` }}>
                  <input type="checkbox" checked={filtered.length > 0 && selectedIds.size === filtered.length} onChange={toggleSelectAll} style={{ cursor: 'pointer' }} />
                </th>
                {['Party Name', 'Type', 'Department', 'Via Account', 'Date', 'Amount'].map((h, i) => (
                  <th key={i} style={{ padding: '10px 14px', fontSize: 11, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.5, borderBottom: `1px solid ${C.border}`, textAlign: i >= 4 ? 'right' : 'left' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ padding: 28, textAlign: 'center', color: C.muted }}>Loading…</td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={7} style={{ padding: 36, textAlign: 'center', color: C.muted }}>No individual settlements found.</td></tr>
              ) : filtered.map(s => {
                const isSelected = selectedIds.has(s.id);
                return (
                  <tr key={s.id} className={selectedIds.size > 0 && !isSelected ? 'hide-in-print' : ''} style={{ borderBottom: `1px solid ${C.slateBg}`, background: isSelected ? C.blueBg : 'transparent' }}>
                    <td className="no-print" style={{ padding: '12px 14px' }}>
                      <input type="checkbox" checked={isSelected} onChange={() => toggleSelect(s.id)} style={{ cursor: 'pointer' }} />
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 28, height: 28, borderRadius: 6, background: s.type === 'receivable' ? C.blueBg : C.redBg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, color: s.type === 'receivable' ? C.blue : C.red, flexShrink: 0 }}>
                          {s.type === 'receivable' ? '↓' : '↑'}
                        </div>
                        <p style={{ margin: 0, fontSize: 13, fontWeight: 600, color: C.text }}>{s.party_name}</p>
                      </div>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700, background: s.type === 'receivable' ? C.blueBg : C.redBg, color: s.type === 'receivable' ? C.blue : C.red }}>
                        {s.type === 'receivable' ? 'Received' : 'Paid'}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      {s.department ? <span style={{ padding: '2px 9px', background: C.slateBg, borderRadius: 20, fontSize: 11, fontWeight: 600, color: C.slate }}>{s.department}</span> : <span style={{ color: C.muted, fontSize: 12 }}>—</span>}
                    </td>
                    <td style={{ padding: '12px 14px', fontSize: 12, color: C.muted }}>{s.settlement_account_name || '—'}</td>
                    <td style={{ padding: '12px 14px', fontSize: 12, color: C.muted, textAlign: 'right' }}>{s.updated_at ? s.updated_at.substring(0, 10) : '—'}</td>
                    <td style={{ padding: '12px 14px', fontSize: 14, fontWeight: 800, color: s.type === 'receivable' ? C.green : C.red, textAlign: 'right' }}>{fmt(s.amount)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
