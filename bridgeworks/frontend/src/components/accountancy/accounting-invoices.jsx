'use client';
import { useState } from 'react';
import AccountingInvoicesSales from './accounting-invoices-sales';
import AccountingInvoicesPurchase from './accounting-invoices-purchase';

const C = {
  blue: '#2563eb', blueBg: '#eff6ff',
  muted: '#64748b', border: '#e2e8f0', slateBg: '#f8fafc',
};

export default function AccountingInvoices({ onRefresh, dateParams }) {
  const [sub, setSub] = useState('sales');

  const tabStyle = active => ({
    padding: '7px 18px',
    fontSize: 13,
    fontWeight: active ? 700 : 500,
    border: 'none',
    borderBottom: `2px solid ${active ? C.blue : 'transparent'}`,
    background: 'transparent',
    color: active ? C.blue : C.muted,
    cursor: 'pointer',
    transition: 'all 0.14s',
  });

  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Sub-tab bar — same style as P&R */}
      <div className="no-print" style={{ display: 'flex', gap: 0, borderBottom: `1px solid ${C.border}`, marginBottom: 22 }}>
        <button style={tabStyle(sub === 'sales')}    onClick={() => setSub('sales')}>Sales Invoices</button>
        <button style={tabStyle(sub === 'purchase')} onClick={() => setSub('purchase')}>Purchase Bills</button>
      </div>

      {sub === 'sales'    && <AccountingInvoicesSales onRefresh={onRefresh} dateParams={dateParams} />}
      {sub === 'purchase' && <AccountingInvoicesPurchase onRefresh={onRefresh} dateParams={dateParams} />}
    </div>
  );
}
