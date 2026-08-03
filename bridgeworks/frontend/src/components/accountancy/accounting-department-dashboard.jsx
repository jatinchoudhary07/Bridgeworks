'use client';
import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { useTheme, alpha } from '@mui/material/styles';
import { apiClient } from '../../apiClient';
import { usePagePermissions } from '../../utils/rbac';

const fmt = n => `₹${Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

function useC() {
  const theme = useTheme();
  const d = theme.palette.mode === 'dark';
  return {
    green: '#059669', greenBg: d ? alpha('#059669', 0.15) : '#ecfdf5', greenBorder: d ? alpha('#059669', 0.3) : '#a7f3d0',
    red: '#dc2626', redBg: d ? alpha('#dc2626', 0.15) : '#fef2f2', redBorder: d ? alpha('#dc2626', 0.3) : '#fecaca',
    blue: '#2563eb', blueBg: d ? alpha('#2563eb', 0.15) : '#eff6ff', blueBorder: d ? alpha('#2563eb', 0.3) : '#bfdbfe',
    amber: '#d97706', amberBg: d ? alpha('#d97706', 0.15) : '#fffbeb', amberBorder: d ? alpha('#d97706', 0.3) : '#fde68a',
    violet: '#7c3aed', violetBg: d ? alpha('#7c3aed', 0.15) : '#f5f3ff', violetBorder: d ? alpha('#7c3aed', 0.3) : '#ddd6fe',
    teal: '#0d9488', tealBg: d ? alpha('#0d9488', 0.15) : '#f0fdfa', tealBorder: d ? alpha('#0d9488', 0.3) : '#99f6e4',
    rose: '#e11d48', roseBg: d ? alpha('#e11d48', 0.15) : '#fff1f2', roseBorder: d ? alpha('#e11d48', 0.3) : '#fecdd3',
    orange: '#ea580c', orangeBg: d ? alpha('#ea580c', 0.15) : '#fff7ed', orangeBorder: d ? alpha('#ea580c', 0.3) : '#fed7aa',
    indigo: '#4338ca', indigoBg: d ? alpha('#4338ca', 0.15) : '#eef2ff', indigoBorder: d ? alpha('#4338ca', 0.3) : '#c7d2fe',
    slate: '#64748b', slateBg: d ? alpha('#ffffff', 0.04) : '#f8fafc', slateBorder: d ? alpha('#ffffff', 0.1) : '#e2e8f0',
    text: theme.palette.text.primary,
    muted: theme.palette.text.secondary,
    border: theme.palette.divider,
    surface: theme.palette.background.paper,
    inputBg: d ? alpha('#ffffff', 0.06) : '#ffffff',
    dropdownBg: theme.palette.background.paper,
  };
}

const PALETTE = [
  { key: 'blue' },
  { key: 'green' },
  { key: 'amber' },
  { key: 'violet' },
  { key: 'teal' },
  { key: 'rose' },
  { key: 'orange' },
  { key: 'indigo' },
];

const DEPT_ICONS = {
  'Leadership & Strategy': '👑',
  'Software Engineering': '💻',
  'Growth & Marketing': '📣',
  'People & Operations': '👥',
  'Finance & Accounting': '🏦',
  'Product & Merchandising': '📦',
  'Branding & Creative': '🎨',
  'E-Commerce & Website': '🛒',
  'Operations & Fulfillment': '⚙️',
  'Logistics': '🚚',
  'Customer Experience': '🤝',
};

function getStyle(index, C) {
  const item = PALETTE[index % PALETTE.length];
  return {
    color: C[item.key],
    bg: C[`${item.key}Bg`],
    border: C[`${item.key}Border`],
  };
}

function SectionLabel({ children, C }) {
  return (
    <p style={{ margin: '0 0 12px', fontSize: 11, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: 1 }}>
      {children}
    </p>
  );
}

// ── Department Card ───────────────────────────────────────────────────────────
function DeptCard({ dept, style, maxExpense, onClick, selected }) {
  const { canViewAmounts } = usePagePermissions();
  const C = useC();
  const fmtLocal = n => canViewAmounts ? fmt(n) : '****';

  const net = dept.income - dept.expense;
  const isPos = net >= 0;
  const hasData = dept.total_entries > 0;
  const [hovered, setHovered] = useState(false);

  return (
    <div
      onClick={() => onClick(dept.name)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: C.surface,
        border: `2px solid ${selected ? style.color : hovered ? '#94a3b8' : C.border}`,
        borderRadius: 14,
        padding: '18px 20px',
        cursor: 'pointer',
        transition: 'all 0.18s',
        boxShadow: selected
          ? `0 0 0 3px ${style.bg}, 0 6px 20px rgba(0,0,0,0.1)`
          : hovered ? '0 6px 18px rgba(0,0,0,0.09)'
            : '0 1px 4px rgba(0,0,0,0.05)',
        opacity: hasData ? 1 : 0.7,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 40, height: 40, borderRadius: 10, background: style.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, flexShrink: 0 }}>
            {DEPT_ICONS[dept.name] || '📋'}
          </div>
          <div>
            <p style={{ margin: 0, fontSize: 14, fontWeight: 800, color: C.text, lineHeight: 1.3 }}>{dept.name}</p>
            <p style={{ margin: '2px 0 0', fontSize: 11, color: C.muted }}>{dept.total_entries} total transactions</p>
          </div>
        </div>
        {hasData && (
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 14, fontWeight: 800, color: isPos ? C.green : C.red }}>{isPos ? '+' : '-'}{fmtLocal(Math.abs(net))}</div>
            <span style={{ fontSize: 10, fontWeight: 700, color: isPos ? C.green : C.red, background: isPos ? C.greenBg : C.redBg, padding: '2px 8px', borderRadius: 99 }}>
              {isPos ? 'Surplus' : 'Deficit'}
            </span>
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, borderTop: `1px solid ${C.border}`, paddingTop: 12 }}>
        <div style={{ paddingRight: 12, borderRight: `1px solid ${C.border}` }}>
          <p style={{ margin: '0 0 3px', fontSize: 10, fontWeight: 600, color: C.muted, textTransform: 'uppercase' }}>Income</p>
          <p style={{ margin: 0, fontSize: 15, fontWeight: 800, color: C.green }}>{fmtLocal(dept.income)}</p>
          <p style={{ margin: '1px 0 0', fontSize: 10, color: C.muted }}>{dept.income_entries} entries</p>
        </div>
        <div style={{ paddingLeft: 12 }}>
          <p style={{ margin: '0 0 3px', fontSize: 10, fontWeight: 600, color: C.muted, textTransform: 'uppercase' }}>Expense</p>
          <p style={{ margin: 0, fontSize: 15, fontWeight: 800, color: C.red }}>{fmtLocal(dept.expense)}</p>
          <p style={{ margin: '1px 0 0', fontSize: 10, color: C.muted }}>{dept.expense_entries} entries</p>
        </div>
      </div>

      {maxExpense > 0 && (
        <div style={{ height: 4, background: '#f1f5f9', borderRadius: 99, overflow: 'hidden', marginTop: 12 }}>
          <div style={{ height: '100%', width: `${Math.min(100, Math.round((dept.expense / maxExpense) * 100))}%`, background: style.color, borderRadius: 99, transition: 'width 0.4s ease' }} />
        </div>
      )}

      <div style={{ marginTop: 12, textAlign: 'center', fontSize: 11, fontWeight: 700, color: style.color }}>
        {selected ? '▼ Expanded View Active' : 'Click to View Income & Expense Breakdown →'}
      </div>
    </div>
  );
}

// ── Transaction Table ─────────────────────────────────────────────────────────
function TransactionTable({ transactions, loading, error, tabFilter }) {
  const { canViewAmounts } = usePagePermissions();
  const C = useC();
  const fmtLocal = n => canViewAmounts ? fmt(n) : '****';

  const filteredTx = useMemo(() => {
    if (tabFilter === 'income') return transactions.filter(t => t.ledger_type === 'income' || t.credit > 0);
    if (tabFilter === 'expense') return transactions.filter(t => t.ledger_type === 'expense' || t.debit > 0);
    return transactions;
  }, [transactions, tabFilter]);

  if (loading) return <p style={{ color: C.muted, fontSize: 13, padding: '24px 0', textAlign: 'center' }}>Loading department breakdown...</p>;
  if (error) return <p style={{ color: C.red, fontSize: 13, padding: '24px 0', textAlign: 'center' }}>{error}</p>;
  if (!filteredTx.length) return (
    <div style={{ padding: '36px 0', textAlign: 'center', color: C.muted, fontSize: 13 }}>
      No {tabFilter !== 'all' ? tabFilter : ''} transactions recorded for this department yet.
    </div>
  );

  return (
    <div style={{ overflowX: 'auto', borderRadius: 10, border: `1px solid ${C.border}` }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <thead>
          <tr style={{ background: '#f9fafb', borderBottom: `1px solid ${C.border}` }}>
            {['Date', 'Description / Notes', 'Ledger', 'Category', 'Debit (Expense)', 'Credit (Income)'].map(h => (
              <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.6, whiteSpace: 'nowrap' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filteredTx.map((tx, i) => (
            <tr key={tx.id || i} style={{ borderBottom: i < filteredTx.length - 1 ? `1px solid ${C.slateBg}` : 'none', background: i % 2 === 0 ? C.surface : '#fafafa' }}>
              <td style={{ padding: '10px 14px', color: C.muted, whiteSpace: 'nowrap', fontWeight: 600 }}>{tx.date}</td>
              <td style={{ padding: '10px 14px', color: C.text, maxWidth: 280 }}>
                <div style={{ fontWeight: 600, lineHeight: 1.3 }}>{tx.description || '—'}</div>
                {tx.notes && <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{tx.notes}</div>}
              </td>
              <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>
                <span style={{ padding: '3px 10px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: tx.ledger_type === 'income' ? C.greenBg : tx.ledger_type === 'expense' ? C.redBg : C.blueBg, color: tx.ledger_type === 'income' ? C.green : tx.ledger_type === 'expense' ? C.red : C.blue }}>
                  {tx.ledger}
                </span>
              </td>
              <td style={{ padding: '10px 14px', color: C.text, textTransform: 'capitalize' }}>{tx.ledger_type || 'General'}</td>
              <td style={{ padding: '10px 14px', fontWeight: 800, color: C.red, whiteSpace: 'nowrap' }}>{tx.debit > 0 ? fmtLocal(tx.debit) : '—'}</td>
              <td style={{ padding: '10px 14px', fontWeight: 800, color: C.green, whiteSpace: 'nowrap' }}>{tx.credit > 0 ? fmtLocal(tx.credit) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Expanded Department Detail Panel ──────────────────────────────────────────
const DeptDetail = React.forwardRef(({ dept, style, transactions, txLoading, txError, onClose }, ref) => {
  const { canViewAmounts } = usePagePermissions();
  const C = useC();
  const fmtLocal = n => canViewAmounts ? fmt(n) : '****';
  const [tabFilter, setTabFilter] = useState('all');

  const net = dept.income - dept.expense;
  const isPos = net >= 0;

  return (
    <div
      ref={ref}
      style={{
        background: C.surface,
        border: `2px solid ${style.color}`,
        borderRadius: 16,
        padding: '24px 28px',
        boxShadow: '0 8px 30px rgba(0,0,0,0.12)',
        marginTop: 24,
        marginBottom: 32,
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ width: 48, height: 48, borderRadius: 12, background: style.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24 }}>
            {DEPT_ICONS[dept.name] || '📋'}
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: C.text }}>{dept.name} — Expanded View</h2>
            <p style={{ margin: '3px 0 0', fontSize: 13, color: C.muted }}>
              {dept.total_entries} Total Entries &middot; Net Balance:{' '}
              <span style={{ color: isPos ? C.green : C.red, fontWeight: 800 }}>
                {fmtLocal(Math.abs(net))} {isPos ? 'Surplus' : 'Deficit'}
              </span>
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            fontSize: 13,
            color: C.muted,
            background: C.slateBg,
            border: `1px solid ${C.border}`,
            borderRadius: 8,
            padding: '6px 14px',
            cursor: 'pointer',
            fontWeight: 700,
          }}
        >
          ✕ Close Expanded View
        </button>
      </div>

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 24 }}>
        {[
          { label: 'Total Department Income', value: fmtLocal(dept.income), color: C.green, bg: C.greenBg, count: dept.income_entries },
          { label: 'Total Department Expense', value: fmtLocal(dept.expense), color: C.red, bg: C.redBg, count: dept.expense_entries },
          { label: 'Net Operating Balance', value: fmtLocal(Math.abs(net)), color: isPos ? C.green : C.red, bg: isPos ? C.greenBg : C.redBg, count: `${dept.total_entries} total` },
        ].map((k, i) => (
          <div key={i} style={{ background: k.bg, borderRadius: 12, padding: '16px 18px', border: `1px solid ${C.border}` }}>
            <p style={{ margin: '0 0 6px', fontSize: 11, fontWeight: 700, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.5 }}>{k.label}</p>
            <p style={{ margin: 0, fontSize: 22, fontWeight: 800, color: k.color }}>{k.value}</p>
            <p style={{ margin: '4px 0 0', fontSize: 11, color: C.muted }}>{k.count} items recorded</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, borderBottom: `1px solid ${C.border}`, pb: 12 }}>
        {[
          { key: 'all', label: `All Transactions (${transactions.length})` },
          { key: 'income', label: `Income (${dept.income_entries})` },
          { key: 'expense', label: `Expenses (${dept.expense_entries})` },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setTabFilter(tab.key)}
            style={{
              padding: '8px 16px',
              borderRadius: 8,
              fontSize: 13,
              fontWeight: tabFilter === tab.key ? 700 : 500,
              border: 'none',
              cursor: 'pointer',
              background: tabFilter === tab.key ? style.color : 'transparent',
              color: tabFilter === tab.key ? '#ffffff' : C.muted,
              transition: 'all 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <TransactionTable transactions={transactions} loading={txLoading} error={txError} tabFilter={tabFilter} />
    </div>
  );
});

// ── Main Component ────────────────────────────────────────────────────────────
export default function AccountingDepartmentDashboard() {
  const { canViewAmounts } = usePagePermissions();
  const C = useC();
  const fmtLocal = n => canViewAmounts ? fmt(n) : '****';

  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [selectedDept, setSelectedDept] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [txLoading, setTxLoading] = useState(false);
  const [txError, setTxError] = useState(null);

  const [sortBy, setSortBy] = useState('expense');
  const [filterDepts, setFilterDepts] = useState(new Set());
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [search, setSearch] = useState('');

  const dropdownRef = useRef(null);
  const detailRef = useRef(null);

  // Fetch department overview
  const fetchDepartments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient('/api/accounting/departments/', { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok) { setError(payload?.message || 'Failed to load departments.'); return; }
      setDepartments(payload?.data ?? payload ?? []);
    } catch {
      setError('Could not reach departments API.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDepartments(); }, [fetchDepartments]);

  // Fetch transactions for selected department
  const fetchTransactions = useCallback(async (name) => {
    setTxLoading(true);
    setTxError(null);
    setTransactions([]);
    try {
      const res = await apiClient(`/api/accounting/departments/transactions/?department=${encodeURIComponent(name)}`, { cache: 'no-store' });
      const payload = await res.json().catch(() => null);
      if (!res.ok) { setTxError(payload?.message || 'Failed to load transactions.'); return; }
      setTransactions(payload?.data ?? payload ?? []);
    } catch {
      setTxError('Could not reach transactions API.');
    } finally {
      setTxLoading(false);
    }
  }, []);

  const handleCardClick = (name) => {
    if (selectedDept === name) {
      setSelectedDept(null);
      setTransactions([]);
    } else {
      setSelectedDept(name);
      fetchTransactions(name);
    }
  };

  // Auto-scroll down to expanded view when selectedDept changes
  useEffect(() => {
    if (selectedDept && detailRef.current) {
      setTimeout(() => {
        detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }, [selectedDept]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = e => { if (dropdownRef.current && !dropdownRef.current.contains(e.target)) setDropdownOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const maxExpense = useMemo(() => Math.max(0, ...departments.map(d => d.expense)), [departments]);

  const sortedDepts = useMemo(() => {
    return departments
      .filter(d => filterDepts.size === 0 || filterDepts.has(d.name))
      .filter(d => !search || d.name.toLowerCase().includes(search.toLowerCase()))
      .sort((a, b) => {
        if (sortBy === 'expense') return b.expense - a.expense;
        if (sortBy === 'income') return b.income - a.income;
        if (sortBy === 'entries') return b.total_entries - a.total_entries;
        return a.name.localeCompare(b.name);
      });
  }, [departments, sortBy, filterDepts, search]);

  const totalIncome = departments.reduce((s, d) => s + d.income, 0);
  const totalExpense = departments.reduce((s, d) => s + d.expense, 0);
  const totalNet = totalIncome - totalExpense;
  const activeDepts = departments.filter(d => d.total_entries > 0).length;

  const activeDetail = selectedDept ? departments.find(d => d.name === selectedDept) : null;
  const activeStyle = activeDetail ? getStyle(sortedDepts.findIndex(d => d.name === selectedDept), C) : { color: C.blue, bg: C.blueBg, border: C.blueBorder };

  const sortBtnSx = active => ({
    padding: '5px 12px', borderRadius: 7, fontSize: 12, fontWeight: active ? 700 : 500,
    border: 'none', cursor: 'pointer',
    background: active ? C.blue : 'transparent',
    color: active ? '#fff' : C.muted,
    transition: 'all 0.14s',
  });

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 220, color: C.muted, fontSize: 14 }}>
      Loading departments…
    </div>
  );

  if (error) return (
    <div style={{ padding: 24, background: C.redBg, borderRadius: 12, color: C.red, fontSize: 14 }}>{error}</div>
  );

  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>

      {/* ── Overview KPIs ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <SectionLabel C={C}>Company-wide Overview</SectionLabel>
        <button onClick={fetchDepartments} style={{ fontSize: 12, color: C.blue, background: C.blueBg, border: `1px solid ${C.blueBorder}`, borderRadius: 7, padding: '4px 12px', cursor: 'pointer', fontWeight: 600 }}>
          ↺ Refresh
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 26 }}>
        {[
          { label: 'Total Income', value: fmtLocal(totalIncome), color: C.green, note: `${departments.reduce((s, d) => s + d.income_entries, 0)} income entries` },
          { label: 'Total Expense', value: fmtLocal(totalExpense), color: C.red, note: `${departments.reduce((s, d) => s + d.expense_entries, 0)} expense entries` },
          { label: 'Net Balance', value: fmtLocal(Math.abs(totalNet)), color: totalNet >= 0 ? C.green : C.red, note: totalNet >= 0 ? 'Surplus' : 'Deficit' },
          { label: 'Active Depts', value: activeDepts, color: C.blue, note: `${departments.length} total departments` },
        ].map((k, i) => (
          <div key={i} style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: '18px 20px', boxShadow: '0 1px 4px rgba(0,0,0,0.05)' }}>
            <p style={{ margin: '0 0 10px', fontSize: 11, fontWeight: 600, color: C.muted, textTransform: 'uppercase', letterSpacing: 0.8 }}>{k.label}</p>
            <p style={{ margin: 0, fontSize: 24, fontWeight: 800, color: k.color, letterSpacing: -1, lineHeight: 1 }}>{k.value}</p>
            <p style={{ margin: '7px 0 0', fontSize: 11, color: C.muted }}>{k.note}</p>
          </div>
        ))}
      </div>

      {/* ── Filter + Sort bar ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search department…"
          style={{ padding: '6px 12px', borderRadius: 8, border: `1px solid ${C.border}`, fontSize: 13, outline: 'none', minWidth: 180, color: C.text, background: C.inputBg }}
        />

        <div ref={dropdownRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setDropdownOpen(o => !o)}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', background: C.inputBg, border: `1px solid ${C.border}`, borderRadius: 8, cursor: 'pointer', fontSize: 12, fontWeight: 600, color: filterDepts.size > 0 ? C.blue : C.muted }}
          >
            🔽 {filterDepts.size === 0 ? 'All Departments' : `${filterDepts.size} selected`}
          </button>
          {dropdownOpen && (
            <div style={{ position: 'absolute', top: 'calc(100% + 6px)', left: 0, zIndex: 50, background: C.dropdownBg, border: `1px solid ${C.border}`, borderRadius: 10, boxShadow: '0 8px 24px rgba(0,0,0,0.15)', minWidth: 240, maxHeight: 320, overflowY: 'auto' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', borderBottom: `1px solid ${C.border}`, background: C.slateBg }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: C.muted, textTransform: 'uppercase' }}>Filter</span>
                {filterDepts.size > 0 && <button onClick={() => setFilterDepts(new Set())} style={{ fontSize: 11, fontWeight: 600, color: C.blue, background: 'none', border: 'none', cursor: 'pointer' }}>Clear all</button>}
              </div>
              {departments.map((dept, i) => {
                const checked = filterDepts.has(dept.name);
                const s = getStyle(i, C);
                return (
                  <div key={dept.name} onClick={() => setFilterDepts(prev => { const n = new Set(prev); checked ? n.delete(dept.name) : n.add(dept.name); return n; })}
                    style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 14px', cursor: 'pointer', background: checked ? s.bg : 'transparent', borderBottom: `1px solid ${C.slateBg}` }}
                  >
                    <div style={{ width: 16, height: 16, borderRadius: 4, border: `2px solid ${checked ? s.color : C.border}`, background: checked ? s.color : C.inputBg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                      {checked && <svg width="9" height="9" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>}
                    </div>
                    <span style={{ fontSize: 12 }}>{DEPT_ICONS[dept.name] || '📋'}</span>
                    <span style={{ fontSize: 13, fontWeight: checked ? 700 : 500, color: checked ? s.color : C.text }}>{dept.name}</span>
                    {dept.total_entries > 0 && <span style={{ marginLeft: 'auto', fontSize: 11, color: C.muted }}>{dept.total_entries}</span>}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ flex: 1 }} />

        <div style={{ display: 'flex', gap: 3, background: C.inputBg, borderRadius: 8, padding: 3, border: `1px solid ${C.border}` }}>
          {[['expense', 'By Expense'], ['income', 'By Income'], ['entries', 'By Activity'], ['name', 'A–Z']].map(([k, l]) => (
            <button key={k} onClick={() => setSortBy(k)} style={sortBtnSx(sortBy === k)}>{l}</button>
          ))}
        </div>
      </div>

      {/* ── Department Cards Grid ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 14, marginBottom: 28 }}>
        {sortedDepts.length > 0 ? sortedDepts.map((dept, i) => (
          <DeptCard
            key={dept.name}
            dept={dept}
            style={getStyle(i, C)}
            maxExpense={maxExpense}
            selected={selectedDept === dept.name}
            onClick={handleCardClick}
          />
        )) : (
          <div style={{ gridColumn: '1 / -1', padding: '40px 20px', textAlign: 'center', background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <p style={{ margin: '0 0 6px', fontSize: 15, fontWeight: 700, color: C.text }}>No departments found</p>
            <p style={{ margin: 0, fontSize: 12, color: C.muted }}>Try adjusting your filter or search term.</p>
          </div>
        )}
      </div>

      {/* ── Expanded Detail Panel (at end of page with smooth auto-scroll) ── */}
      {activeDetail && (
        <DeptDetail
          ref={detailRef}
          dept={activeDetail}
          style={activeStyle}
          transactions={transactions}
          txLoading={txLoading}
          txError={txError}
          onClose={() => { setSelectedDept(null); setTransactions([]); }}
        />
      )}

    </div>
  );
}
