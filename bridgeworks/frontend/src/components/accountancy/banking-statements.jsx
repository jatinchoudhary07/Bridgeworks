import { useCallback, useEffect, useMemo, useState } from 'react';
import { apiClient } from '../../apiClient';

const COLORS = {
  blue: '#2563eb',
  green: '#16a34a',
  red: '#dc2626',
  text: '#0f172a',
  muted: '#64748b',
  border: '#e2e8f0',
  surface: '#ffffff',
};

const fmt = (value) => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function getDateBoundsFromParams(dateParams) {
  if (!dateParams) {
    return { from: '', to: '' };
  }
  const parsed = new URLSearchParams(dateParams);
  return {
    from: parsed.get('date_from') || '',
    to: parsed.get('date_to') || '',
  };
}

export default function BankingStatements({ dateParams = '' }) {
  const initialBounds = useMemo(() => getDateBoundsFromParams(dateParams), [dateParams]);

  const [rows, setRows] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [bankAccount, setBankAccount] = useState('');
  const [status, setStatus] = useState('');
  const [dateFrom, setDateFrom] = useState(initialBounds.from);
  const [dateTo, setDateTo] = useState(initialBounds.to);
  const [search, setSearch] = useState('');

  const [totalRows, setTotalRows] = useState(0);
  const [unprocessed, setUnprocessed] = useState(0);

  const loadAccounts = useCallback(async () => {
    try {
      const response = await apiClient('/api/accounting/bank-accounts/', { credentials: 'include' });
      const data = await response.json().catch(() => null);
      if (response.ok && data?.success) {
        setAccounts(Array.isArray(data.data) ? data.data : []);
      }
    } catch (err) {
      // Keep silent to avoid blocking transactions table.
    }
  }, []);

  const loadTransactions = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const query = new URLSearchParams();
      if (bankAccount) query.set('bank_account', bankAccount);
      if (status) query.set('status', status);
      if (dateFrom) query.set('date_from', dateFrom);
      if (dateTo) query.set('date_to', dateTo);
      if (search.trim()) query.set('search', search.trim());

      const suffix = query.toString() ? `?${query.toString()}` : '';
      const response = await apiClient(`/api/accounting/bank-transactions/${suffix}`, { credentials: 'include' });
      const data = await response.json().catch(() => null);

      if (!response.ok || !data?.success) {
        setError(data?.message || 'Unable to load imported transactions.');
        setRows([]);
        setTotalRows(0);
        setUnprocessed(0);
        setLoading(false);
        return;
      }

      const payload = data.data || {};
      setRows(Array.isArray(payload.transactions) ? payload.transactions : []);
      setTotalRows(Number(payload.total || 0));
      setUnprocessed(Number(payload.unprocessed || 0));
    } catch (err) {
      setError('Network error while loading imported transactions.');
      setRows([]);
      setTotalRows(0);
      setUnprocessed(0);
    }

    setLoading(false);
  }, [bankAccount, status, dateFrom, dateTo, search]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions]);

  const filteredLabel = rows.length === 1 ? 'transaction' : 'transactions';

  return (
    <div>
      <div style={{ marginBottom: 8, color: COLORS.muted, fontSize: 13 }}>
        {loading ? 'Loading transactions...' : `${rows.length} ${filteredLabel}`}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 8, marginBottom: 10 }}>
        <select
          value={bankAccount}
          onChange={(event) => setBankAccount(event.target.value)}
          style={{ padding: '8px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 13, background: '#fff' }}
        >
          <option value="">All accounts</option>
          {accounts.map((account) => (
            <option key={account.id} value={String(account.id)}>
              {account.name}
            </option>
          ))}
        </select>

        <select
          value={status}
          onChange={(event) => setStatus(event.target.value)}
          style={{ padding: '8px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 13, background: '#fff' }}
        >
          <option value="">All statuses</option>
          <option value="unprocessed">Unprocessed</option>
          <option value="processed">Processed</option>
          <option value="ignored">Ignored</option>
        </select>

        <input
          type="date"
          value={dateFrom}
          onChange={(event) => setDateFrom(event.target.value)}
          style={{ padding: '8px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 13 }}
        />

        <input
          type="date"
          value={dateTo}
          onChange={(event) => setDateTo(event.target.value)}
          style={{ padding: '8px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 13 }}
        />

        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search description..."
          style={{ padding: '8px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 13 }}
        />
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 10 }}>
        <div style={{ padding: '4px 9px', borderRadius: 18, background: '#eff6ff', color: COLORS.blue, fontSize: 11, fontWeight: 700 }}>
          Total: {totalRows}
        </div>
        <div style={{ padding: '4px 9px', borderRadius: 18, background: unprocessed > 0 ? '#fef2f2' : '#ecfdf5', color: unprocessed > 0 ? COLORS.red : COLORS.green, fontSize: 11, fontWeight: 700 }}>
          Unprocessed: {unprocessed}
        </div>
      </div>

      {error ? (
        <div style={{ marginBottom: 10, border: '1px solid #fecaca', background: '#fef2f2', color: COLORS.red, borderRadius: 8, padding: '8px 10px', fontSize: 12, fontWeight: 600 }}>
          {error}
        </div>
      ) : null}

      <div style={{ border: `1px solid ${COLORS.border}`, borderRadius: 12, overflow: 'hidden', background: COLORS.surface }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#f8fafc' }}>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>Date</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>Description</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>Type</th>
              <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>Amount</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>Status</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>Account</th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', letterSpacing: 0.4 }}>Department</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ padding: '20px 12px', textAlign: 'center', color: COLORS.muted, fontSize: 13 }}>
                  Loading imported transactions...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: '20px 12px', textAlign: 'center', color: COLORS.muted, fontSize: 13 }}>
                  No transactions found.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id} style={{ borderTop: `1px solid ${COLORS.border}` }}>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: COLORS.text }}>{row.date || '-'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: COLORS.text }}>{row.description || '-'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: COLORS.text }}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: 999,
                        background: row.type === 'credit' ? '#ecfdf5' : '#fef2f2',
                        color: row.type === 'credit' ? COLORS.green : COLORS.red,
                        fontWeight: 700,
                        fontSize: 11,
                        textTransform: 'uppercase',
                      }}
                    >
                      {row.type || '-'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: row.type === 'credit' ? COLORS.green : COLORS.red, textAlign: 'right', fontWeight: 700 }}>
                    {fmt(row.amount)}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 12, color: COLORS.text }}>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: 999,
                        background:
                          row.status === 'processed'
                            ? '#dcfce7'
                            : row.status === 'ignored'
                              ? '#e2e8f0'
                              : '#fef3c7',
                        color:
                          row.status === 'processed'
                            ? '#166534'
                            : row.status === 'ignored'
                              ? '#334155'
                              : '#92400e',
                        fontWeight: 700,
                        fontSize: 11,
                        textTransform: 'capitalize',
                      }}
                    >
                      {row.status || 'unprocessed'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: COLORS.text }}>{row.bank_account_name || '-'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 13, color: COLORS.muted }}>{row.department || '-'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
