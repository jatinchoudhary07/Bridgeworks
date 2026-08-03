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
  slate: '#f8fafc',
};

const fmt = (value) => `₹${Number(value || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function CreateBankAccountModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '',
    bank_name: '',
    account_number: '',
    opening_balance: '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const submit = async (event) => {
    event.preventDefault();
    setError('');

    if (!form.name.trim()) {
      setError('Account name is required.');
      return;
    }

    const opening = form.opening_balance === '' ? 0 : Number(form.opening_balance);
    if (Number.isNaN(opening)) {
      setError('Opening balance must be a valid number.');
      return;
    }

    setSaving(true);
    try {
      const response = await apiClient('/api/accounting/bank-accounts/', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          bank_name: form.bank_name.trim(),
          account_number: form.account_number.trim(),
          opening_balance: opening,
        }),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data?.success) {
        setError(data?.message || 'Unable to create bank account.');
        setSaving(false);
        return;
      }
      onCreated();
    } catch (err) {
      setError('Network error while creating account.');
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1450,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        background: 'rgba(15, 23, 42, 0.45)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 520,
          background: COLORS.surface,
          borderRadius: 14,
          border: `1px solid ${COLORS.border}`,
          padding: 22,
          boxShadow: '0 20px 50px rgba(15, 23, 42, 0.2)',
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: 18, color: COLORS.text }}>Add Bank Account</h3>
          <button
            type="button"
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              border: `1px solid ${COLORS.border}`,
              background: '#fff',
              color: COLORS.muted,
              cursor: 'pointer',
            }}
          >
            x
          </button>
        </div>

        {error ? (
          <div
            style={{
              marginBottom: 10,
              border: '1px solid #fecaca',
              background: '#fef2f2',
              color: COLORS.red,
              borderRadius: 8,
              padding: '8px 10px',
              fontSize: 12,
              fontWeight: 600,
            }}
          >
            {error}
          </div>
        ) : null}

        <form onSubmit={submit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600, gridColumn: '1 / -1' }}>
            Account Label *
            <input
              value={form.name}
              onChange={(event) => setField('name', event.target.value)}
              placeholder="Example: HDFC Current"
              style={{ width: '100%', marginTop: 4, padding: '9px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 13 }}
            />
          </label>
          <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600 }}>
            Bank Name
            <input
              value={form.bank_name}
              onChange={(event) => setField('bank_name', event.target.value)}
              placeholder="Example: HDFC"
              style={{ width: '100%', marginTop: 4, padding: '9px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 13 }}
            />
          </label>
          <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600 }}>
            Account Number
            <input
              value={form.account_number}
              onChange={(event) => setField('account_number', event.target.value)}
              placeholder="Last 4 or full number"
              style={{ width: '100%', marginTop: 4, padding: '9px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 13 }}
            />
          </label>
          <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600, gridColumn: '1 / -1' }}>
            Opening Balance
            <input
              value={form.opening_balance}
              onChange={(event) => setField('opening_balance', event.target.value.replace(/[^0-9.-]/g, ''))}
              inputMode="decimal"
              placeholder="0"
              style={{ width: '100%', marginTop: 4, padding: '9px 10px', border: `1px solid ${COLORS.border}`, borderRadius: 8, fontSize: 13 }}
            />
          </label>

          <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 6 }}>
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              style={{
                borderRadius: 8,
                border: `1px solid ${COLORS.border}`,
                background: '#fff',
                color: COLORS.muted,
                padding: '8px 14px',
                fontWeight: 600,
                cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              style={{
                borderRadius: 8,
                border: 'none',
                background: COLORS.blue,
                color: '#fff',
                padding: '8px 14px',
                fontWeight: 700,
                cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >
              {saving ? 'Creating...' : 'Create Account'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function BankingAccounts() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await apiClient('/api/accounting/bank-accounts/', { credentials: 'include' });
      const data = await response.json().catch(() => null);
      if (!response.ok || !data?.success) {
        setError(data?.message || 'Unable to load bank accounts.');
        setLoading(false);
        return;
      }
      setAccounts(Array.isArray(data.data) ? data.data : []);
    } catch (err) {
      setError('Network error while loading bank accounts.');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  const hasAccounts = accounts.length > 0;

  const summary = useMemo(() => {
    return accounts.reduce(
      (acc, item) => {
        acc.balance += Number(item.balance || 0);
        acc.unprocessed += Number(item.unprocessed_count || 0);
        acc.totalTransactions += Number(item.transaction_count || 0);
        return acc;
      },
      { balance: 0, unprocessed: 0, totalTransactions: 0 }
    );
  }, [accounts]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <h3 style={{ margin: 0, fontSize: 28, fontWeight: 800, color: COLORS.text }}>Bank Accounts</h3>
        <button
          type="button"
          onClick={() => setCreating(true)}
          style={{
            border: 'none',
            borderRadius: 10,
            padding: '8px 14px',
            background: COLORS.blue,
            color: '#fff',
            fontWeight: 700,
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          + Add Bank Account
        </button>
      </div>

      {error ? (
        <div style={{ marginBottom: 10, border: '1px solid #fecaca', background: '#fef2f2', color: COLORS.red, borderRadius: 8, padding: '8px 10px', fontSize: 12, fontWeight: 600 }}>
          {error}
        </div>
      ) : null}

      {loading ? (
        <div style={{ border: `1px solid ${COLORS.border}`, borderRadius: 12, background: '#fff', padding: '18px 16px', color: COLORS.muted, fontSize: 13 }}>
          Loading bank accounts...
        </div>
      ) : !hasAccounts ? (
        <div style={{ border: `1px solid ${COLORS.border}`, borderRadius: 12, background: '#fff', padding: '36px 18px', color: COLORS.muted, fontSize: 16, textAlign: 'center' }}>
          No bank accounts yet. Click "+ Add Bank Account" to create one.
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10, marginBottom: 12 }}>
            <div style={{ border: `1px solid ${COLORS.border}`, borderRadius: 10, background: '#fff', padding: '10px 12px' }}>
              <div style={{ fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', fontWeight: 700 }}>Total Balance</div>
              <div style={{ marginTop: 3, fontSize: 23, fontWeight: 800, color: COLORS.text }}>{fmt(summary.balance)}</div>
            </div>
            <div style={{ border: `1px solid ${COLORS.border}`, borderRadius: 10, background: '#fff', padding: '10px 12px' }}>
              <div style={{ fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', fontWeight: 700 }}>Total Transactions</div>
              <div style={{ marginTop: 3, fontSize: 23, fontWeight: 800, color: COLORS.text }}>{summary.totalTransactions}</div>
            </div>
            <div style={{ border: `1px solid ${COLORS.border}`, borderRadius: 10, background: '#fff', padding: '10px 12px' }}>
              <div style={{ fontSize: 11, color: COLORS.muted, textTransform: 'uppercase', fontWeight: 700 }}>Unprocessed</div>
              <div style={{ marginTop: 3, fontSize: 23, fontWeight: 800, color: summary.unprocessed > 0 ? COLORS.red : COLORS.green }}>{summary.unprocessed}</div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 10 }}>
            {accounts.map((account) => (
              <div key={account.id} style={{ border: `1px solid ${COLORS.border}`, borderRadius: 12, background: '#fff', padding: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', gap: 8 }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: COLORS.text }}>{account.name || 'Unnamed account'}</div>
                    <div style={{ marginTop: 2, fontSize: 12, color: COLORS.muted }}>
                      {(account.bank_name || 'Bank').trim()}
                      {account.account_number ? ` • ${account.account_number}` : ''}
                    </div>
                  </div>
                  <div style={{ borderRadius: 20, background: COLORS.slate, padding: '2px 8px', fontSize: 10, fontWeight: 700, color: COLORS.muted }}>
                    ID {account.id}
                  </div>
                </div>
                <div style={{ marginTop: 10, fontSize: 12, color: COLORS.muted }}>Current Balance</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: COLORS.text }}>{fmt(account.balance)}</div>
                <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <div style={{ border: `1px solid ${COLORS.border}`, borderRadius: 8, padding: 8, background: '#fff' }}>
                    <div style={{ fontSize: 10, color: COLORS.muted, textTransform: 'uppercase', fontWeight: 700 }}>Credits</div>
                    <div style={{ marginTop: 2, color: COLORS.green, fontSize: 13, fontWeight: 700 }}>{fmt(account.total_credits)}</div>
                  </div>
                  <div style={{ border: `1px solid ${COLORS.border}`, borderRadius: 8, padding: 8, background: '#fff' }}>
                    <div style={{ fontSize: 10, color: COLORS.muted, textTransform: 'uppercase', fontWeight: 700 }}>Debits</div>
                    <div style={{ marginTop: 2, color: COLORS.red, fontSize: 13, fontWeight: 700 }}>{fmt(account.total_debits)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {creating ? (
        <CreateBankAccountModal
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            loadAccounts();
          }}
        />
      ) : null}
    </div>
  );
}
