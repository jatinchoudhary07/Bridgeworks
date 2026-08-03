import { useState } from 'react';
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

const ACCOUNT_TYPES = [
  { value: 'bank', label: 'Bank' },
  { value: 'cash', label: 'Cash' },
  { value: 'wallet', label: 'Wallet' },
];

const LEDGER_TYPES = [
  { value: 'asset', label: 'Asset' },
  { value: 'liability', label: 'Liability' },
  { value: 'income', label: 'Income' },
  { value: 'expense', label: 'Expense' },
];

const inlineInputStyle = {
  flex: 1,
  padding: '6px 8px',
  borderRadius: 6,
  border: `1px solid #e2e8f0`,
  fontSize: 12,
  background: '#fff',
  minWidth: 0,
};

const inlineSelectStyle = {
  padding: '6px 8px',
  borderRadius: 6,
  border: `1px solid #e2e8f0`,
  fontSize: 12,
  background: '#fff',
  flexShrink: 0,
};

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

const toToday = () => new Date().toISOString().slice(0, 10);

function normalizeAmount(value) {
  const cleaned = String(value || '').replace(/[^0-9.]/g, '');
  const parts = cleaned.split('.');
  if (parts.length <= 2) {
    return cleaned;
  }
  return `${parts[0]}.${parts.slice(1).join('')}`;
}

export default function FinanceEntryModal({
  type = 'income',
  ledgers = [],
  accounts = [],
  onClose,
  onSuccess,
}) {
  const isIncome = type === 'income';
  const [form, setForm] = useState({
    amount: '',
    date: toToday(),
    account: '',
    category: ledgers[0]?.value ? String(ledgers[0].value) : '',
    department: '',
    description: '',
  });
  const [receipt, setReceipt] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Local items created inline this session
  const [localAccounts, setLocalAccounts] = useState([]);
  const [localLedgers, setLocalLedgers] = useState([]);

  // Inline "Add New Account" form state
  const [showNewAccount, setShowNewAccount] = useState(false);
  const [newAccountName, setNewAccountName] = useState('');
  const [newAccountType, setNewAccountType] = useState('bank');
  const [addingAccount, setAddingAccount] = useState(false);
  const [accountAddError, setAccountAddError] = useState('');

  // Inline "Add New Ledger" form state
  const [showNewLedger, setShowNewLedger] = useState(false);
  const [newLedgerName, setNewLedgerName] = useState('');
  const [newLedgerType, setNewLedgerType] = useState('asset');
  const [addingLedger, setAddingLedger] = useState(false);
  const [ledgerAddError, setLedgerAddError] = useState('');

  const allAccounts = [...accounts, ...localAccounts];
  const allLedgers = [...ledgers, ...localLedgers];

  const endpoint = isIncome ? '/api/accounting/income/create/' : '/api/accounting/expenses/create/';

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const createAccount = async () => {
    const name = newAccountName.trim();
    if (!name) { setAccountAddError('Name is required.'); return; }
    setAddingAccount(true);
    setAccountAddError('');
    try {
      const res = await apiClient('/api/accounting/accounts/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, type: newAccountType }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.success) {
        setAccountAddError(data?.message || 'Failed to create account.');
        setAddingAccount(false);
        return;
      }
      const newItem = { value: String(data.data.id), label: `${data.data.name} (${data.data.type})` };
      setLocalAccounts((prev) => [...prev, newItem]);
      setField('account', newItem.value);
      setNewAccountName('');
      setNewAccountType('bank');
      setShowNewAccount(false);
    } catch {
      setAccountAddError('Network error.');
    }
    setAddingAccount(false);
  };

  const createLedger = async () => {
    const name = newLedgerName.trim();
    if (!name) { setLedgerAddError('Name is required.'); return; }
    setAddingLedger(true);
    setLedgerAddError('');
    try {
      const res = await apiClient('/api/accounting/ledgers/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, type: newLedgerType }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.success) {
        setLedgerAddError(data?.message || 'Failed to create ledger.');
        setAddingLedger(false);
        return;
      }
      const newItem = { value: String(data.data.id), label: `${data.data.name} (${data.data.type})` };
      setLocalLedgers((prev) => [...prev, newItem]);
      setField('category', newItem.value);
      setNewLedgerName('');
      setNewLedgerType('asset');
      setShowNewLedger(false);
    } catch {
      setLedgerAddError('Network error.');
    }
    setAddingLedger(false);
  };

  const submit = async (event) => {
    event.preventDefault();
    setError('');

    const parsedAmount = parseFloat(String(form.amount).replace(/,/g, ''));
    if (!parsedAmount || Number.isNaN(parsedAmount) || parsedAmount <= 0) {
      setError('Enter a valid amount greater than 0.');
      return;
    }
    if (!form.date) {
      setError('Date is required.');
      return;
    }
    if (!form.account) {
      setError('Account is required.');
      return;
    }
    if (!form.department.trim()) {
      setError('Department is required.');
      return;
    }

    setSaving(true);
    try {
      const payload = new FormData();
      payload.append('amount', String(parsedAmount));
      payload.append('date', form.date);
      payload.append('account', form.account);
      payload.append('department', form.department.trim());
      payload.append('description', form.description || '');
      if (form.category) payload.append('category', form.category);
      if (receipt) payload.append('receipt', receipt);

      const response = await apiClient(endpoint, {
        method: 'POST',
        body: payload,
        credentials: 'include',
      });
      const data = await response.json().catch(() => null);

      if (!response.ok || !data?.success) {
        setError(data?.message || 'Failed to save entry.');
        setSaving(false);
        return;
      }

      if (onSuccess) onSuccess(data);
    } catch (err) {
      setError('Network error while saving entry.');
      setSaving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1400,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(15, 23, 42, 0.45)',
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 560,
          background: COLORS.surface,
          border: `1px solid ${COLORS.border}`,
          borderRadius: 16,
          padding: 24,
          boxShadow: '0 24px 64px rgba(15, 23, 42, 0.25)',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
        onClick={(event) => event.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: 20, color: COLORS.text }}>
              {isIncome ? 'Add Income' : 'Add Expense'}
            </h3>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: COLORS.muted }}>
              This entry will create a linked journal record automatically.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              border: `1px solid ${COLORS.border}`,
              borderRadius: 8,
              width: 32,
              height: 32,
              background: '#fff',
              cursor: 'pointer',
              color: COLORS.muted,
              fontSize: 16,
            }}
          >
            x
          </button>
        </div>

        {error ? (
          <div
            style={{
              marginBottom: 14,
              borderRadius: 8,
              border: '1px solid #fecaca',
              background: '#fef2f2',
              color: COLORS.red,
              padding: '9px 12px',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {error}
          </div>
        ) : null}

        <form onSubmit={submit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600 }}>
              Amount (INR) *
              <input
                value={form.amount}
                onChange={(event) => setField('amount', normalizeAmount(event.target.value))}
                placeholder="0.00"
                inputMode="decimal"
                style={{
                  width: '100%',
                  marginTop: 4,
                  padding: '9px 10px',
                  borderRadius: 8,
                  border: `1px solid ${COLORS.border}`,
                  fontSize: 13,
                }}
              />
            </label>

            <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600 }}>
              Date *
              <input
                type="date"
                value={form.date}
                onChange={(event) => setField('date', event.target.value)}
                style={{
                  width: '100%',
                  marginTop: 4,
                  padding: '9px 10px',
                  borderRadius: 8,
                  border: `1px solid ${COLORS.border}`,
                  fontSize: 13,
                }}
              />
            </label>

            <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600 }}>
              Account *
              <select
                value={form.account}
                onChange={(event) => setField('account', event.target.value)}
                style={{
                  width: '100%',
                  marginTop: 4,
                  padding: '9px 10px',
                  borderRadius: 8,
                  border: `1px solid ${COLORS.border}`,
                  fontSize: 13,
                  background: '#fff',
                }}
              >
                <option value="">Select account</option>
                {allAccounts.map((account) => (
                  <option key={String(account.value)} value={String(account.value)}>
                    {account.label}
                  </option>
                ))}
              </select>
              {!showNewAccount ? (
                <button
                  type="button"
                  onClick={() => { setShowNewAccount(true); setAccountAddError(''); }}
                  style={{ marginTop: 5, background: 'none', border: 'none', padding: 0, fontSize: 11, color: COLORS.blue, cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 3 }}
                >
                  + Add new account
                </button>
              ) : (
                <div style={{ marginTop: 6, padding: '8px 10px', borderRadius: 8, border: `1px solid ${COLORS.border}`, background: '#f8fafc' }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <input
                      autoFocus
                      value={newAccountName}
                      onChange={(e) => setNewAccountName(e.target.value)}
                      placeholder="Account name"
                      style={inlineInputStyle}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); createAccount(); } }}
                    />
                    <select value={newAccountType} onChange={(e) => setNewAccountType(e.target.value)} style={inlineSelectStyle}>
                      {ACCOUNT_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </select>
                  </div>
                  {accountAddError && <p style={{ margin: '4px 0 0', fontSize: 11, color: COLORS.red }}>{accountAddError}</p>}
                  <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    <button
                      type="button"
                      onClick={createAccount}
                      disabled={addingAccount}
                      style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: COLORS.blue, color: '#fff', fontSize: 11, fontWeight: 700, cursor: addingAccount ? 'not-allowed' : 'pointer' }}
                    >
                      {addingAccount ? 'Creating…' : 'Create'}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowNewAccount(false); setNewAccountName(''); setAccountAddError(''); }}
                      style={{ padding: '4px 10px', borderRadius: 6, border: `1px solid ${COLORS.border}`, background: '#fff', color: COLORS.muted, fontSize: 11, cursor: 'pointer' }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </label>

            <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600 }}>
              Ledger Category
              <select
                value={form.category}
                onChange={(event) => setField('category', event.target.value)}
                style={{
                  width: '100%',
                  marginTop: 4,
                  padding: '9px 10px',
                  borderRadius: 8,
                  border: `1px solid ${COLORS.border}`,
                  fontSize: 13,
                  background: '#fff',
                }}
              >
                <option value="">Auto (by department)</option>
                {allLedgers.map((ledger) => (
                  <option key={String(ledger.value)} value={String(ledger.value)}>
                    {ledger.label}
                  </option>
                ))}
              </select>
              {!showNewLedger ? (
                <button
                  type="button"
                  onClick={() => { setShowNewLedger(true); setLedgerAddError(''); }}
                  style={{ marginTop: 5, background: 'none', border: 'none', padding: 0, fontSize: 11, color: COLORS.blue, cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 3 }}
                >
                  + Add new ledger
                </button>
              ) : (
                <div style={{ marginTop: 6, padding: '8px 10px', borderRadius: 8, border: `1px solid ${COLORS.border}`, background: '#f8fafc' }}>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <input
                      autoFocus
                      value={newLedgerName}
                      onChange={(e) => setNewLedgerName(e.target.value)}
                      placeholder="Ledger name"
                      style={inlineInputStyle}
                      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); createLedger(); } }}
                    />
                    <select value={newLedgerType} onChange={(e) => setNewLedgerType(e.target.value)} style={inlineSelectStyle}>
                      {LEDGER_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </select>
                  </div>
                  {ledgerAddError && <p style={{ margin: '4px 0 0', fontSize: 11, color: COLORS.red }}>{ledgerAddError}</p>}
                  <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    <button
                      type="button"
                      onClick={createLedger}
                      disabled={addingLedger}
                      style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: COLORS.blue, color: '#fff', fontSize: 11, fontWeight: 700, cursor: addingLedger ? 'not-allowed' : 'pointer' }}
                    >
                      {addingLedger ? 'Creating…' : 'Create'}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowNewLedger(false); setNewLedgerName(''); setLedgerAddError(''); }}
                      style={{ padding: '4px 10px', borderRadius: 6, border: `1px solid ${COLORS.border}`, background: '#fff', color: COLORS.muted, fontSize: 11, cursor: 'pointer' }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </label>

            <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600, gridColumn: '1 / -1' }}>
              Department *
              <select
                value={form.department}
                onChange={(event) => setField('department', event.target.value)}
                style={{
                  width: '100%',
                  marginTop: 4,
                  padding: '9px 10px',
                  borderRadius: 8,
                  border: `1px solid ${COLORS.border}`,
                  fontSize: 13,
                  background: '#fff',
                }}
              >
                <option value="">Select department</option>
                {DEFAULT_DEPARTMENTS.map((department) => (
                  <option key={department} value={department}>
                    {department}
                  </option>
                ))}
              </select>
            </label>

            <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600, gridColumn: '1 / -1' }}>
              Description
              <textarea
                value={form.description}
                onChange={(event) => setField('description', event.target.value)}
                placeholder={isIncome ? 'Example: payment received from client' : 'Example: vendor payment for logistics'}
                rows={3}
                style={{
                  width: '100%',
                  marginTop: 4,
                  padding: '9px 10px',
                  borderRadius: 8,
                  border: `1px solid ${COLORS.border}`,
                  fontSize: 13,
                  resize: 'vertical',
                }}
              />
            </label>

            <label style={{ fontSize: 12, color: COLORS.text, fontWeight: 600, gridColumn: '1 / -1' }}>
              Receipt (optional)
              <input
                type="file"
                onChange={(event) => setReceipt(event.target.files?.[0] || null)}
                style={{ width: '100%', marginTop: 4, fontSize: 13 }}
              />
            </label>
          </div>

          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              style={{
                padding: '8px 14px',
                border: `1px solid ${COLORS.border}`,
                borderRadius: 8,
                background: '#fff',
                color: COLORS.muted,
                cursor: saving ? 'not-allowed' : 'pointer',
                fontWeight: 600,
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              style={{
                padding: '8px 14px',
                border: 'none',
                borderRadius: 8,
                background: isIncome ? COLORS.green : COLORS.blue,
                color: '#fff',
                cursor: saving ? 'not-allowed' : 'pointer',
                fontWeight: 700,
              }}
            >
              {saving ? 'Saving...' : isIncome ? 'Save Income' : 'Save Expense'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
