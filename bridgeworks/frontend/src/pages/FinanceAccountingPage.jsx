import { useState } from 'react';
import { Box } from '@mui/material';
import { Navigate, Route, Routes } from 'react-router-dom';

import AccountingJournalForm from '../components/accountancy/accounting-journal-form';
import AccountingBankImport from '../components/accountancy/accounting-bank-import';
import AccountingLedgerSummary from '../components/accountancy/accounting-ledger-summary';
import AccountingTrialBalance from '../components/accountancy/accounting-trial-balance';
import AccountingProfitLoss from '../components/accountancy/accounting-profit-loss';
import AccountingBalanceSheet from '../components/accountancy/accounting-balance-sheet';
import AccountingPendingExpenses from '../components/accountancy/accounting-pending-expenses';
import AccountingFinance from '../components/accountancy/accounting-finance';
import AccountingDepartmentDashboard from '../components/accountancy/accounting-department-dashboard';
import AccountingPayroll from '../components/accountancy/accounting-payroll';
import AccountingGST from '../components/accountancy/accounting-gst';
import AccountingBankReconciliation from '../components/accountancy/AccountingBankReconciliation';
import AccountingAccountsCenter from '../components/accountancy/AccountingAccountsCenter';
import AccountingAssetManagement from '../components/accountancy/AccountingAssetManagement';
import FinanceControlTower from '../components/accountancy/FinanceControlTower';
import StrategicDecisionLedger from '../components/accountancy/StrategicDecisionLedger';
import ReportsHub from '../components/accountancy/ReportsHub';
import { FinanceSidebar } from '../components/common';
import DepartmentExpenseTracker from '../components/common/DepartmentExpenseTracker';

// ── Journal page (has its own manual/import sub-toggle) ───────────────────────
function JournalPage() {
  const [journalMode, setJournalMode] = useState('manual');
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box
        sx={{
          display: 'inline-flex',
          gap: 0.5,
          bgcolor: 'grey.100',
          border: 1,
          borderColor: 'divider',
          borderRadius: 2,
          p: 0.5,
          width: 'fit-content',
        }}
      >
        <Box
          component="button"
          type="button"
          onClick={() => setJournalMode('manual')}
          sx={{
            px: 2, py: 0.75, border: 0, borderRadius: 1.5, cursor: 'pointer',
            fontSize: '0.875rem', fontWeight: 600,
            bgcolor: journalMode === 'manual' ? 'background.paper' : 'transparent',
            color: journalMode === 'manual' ? 'text.primary' : 'text.secondary',
            boxShadow: journalMode === 'manual' ? '0 1px 2px rgba(15, 23, 42, 0.08)' : 'none',
          }}
        >
          Manual Entry
        </Box>
        <Box
          component="button"
          type="button"
          onClick={() => setJournalMode('import')}
          sx={{
            px: 2, py: 0.75, border: 0, borderRadius: 1.5, cursor: 'pointer',
            fontSize: '0.875rem', fontWeight: 600,
            bgcolor: journalMode === 'import' ? 'background.paper' : 'transparent',
            color: journalMode === 'import' ? 'text.primary' : 'text.secondary',
            boxShadow: journalMode === 'import' ? '0 1px 2px rgba(15, 23, 42, 0.08)' : 'none',
          }}
        >
          Import Statement
        </Box>
      </Box>
      {journalMode === 'manual' ? <AccountingJournalForm /> : <AccountingBankImport />}
    </Box>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function FinanceAccountingPage() {
  return (
    <Box
      sx={{
        display: 'flex',
        height: '100vh',
        overflow: 'hidden',
        bgcolor: 'background.default',
      }}
    >
      {/* Sidebar reads active state from URL via useLocation internally */}
      <FinanceSidebar />

      <Box
        sx={{
          flexGrow: 1,
          minWidth: 0,
          overflow: 'auto',
          p: 1,
        }}
      >
        <Box
          sx={{
            bgcolor: 'background.paper',
            border: 1,
            borderColor: 'divider',
            borderRadius: 2,
            p: { xs: 2, md: 3 },
            boxShadow: '0 1px 3px rgba(15, 23, 42, 0.08)',
            minHeight: '100%',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Sub-routes inside /finance/* */}
          <Routes>
            {/* Default redirect: /finance → /finance/control-tower */}
            <Route index element={<Navigate to="control-tower" replace />} />

            <Route path="control-tower"      element={<FinanceControlTower />} />
            <Route path="journal"            element={<JournalPage />} />
            <Route path="ledger"             element={<AccountingLedgerSummary />} />
            <Route path="trial-balance"      element={<AccountingTrialBalance />} />
            <Route path="profit-loss"        element={<AccountingProfitLoss />} />
            <Route path="balance-sheet"      element={<AccountingBalanceSheet />} />
            <Route path="pending-expenses"   element={<AccountingPendingExpenses />} />
            <Route path="finance"            element={<AccountingFinance />} />
            <Route path="departments"        element={<AccountingDepartmentDashboard />} />
            <Route path="payroll"            element={<AccountingPayroll />} />
            <Route path="dept-expenses"      element={<DepartmentExpenseTracker department="Finance & Accounting" />} />
            <Route path="gst"                element={<AccountingGST defaultTab="dashboard" />} />
            <Route path="gst-transactions"   element={<AccountingGST defaultTab="transactions" />} />
            <Route path="gst-settings"       element={<AccountingGST defaultTab="settings" />} />
            <Route path="gst-summary"        element={<AccountingGST defaultTab="summary" />} />
            <Route path="gst-liability"      element={<AccountingGST defaultTab="liability" />} />
            <Route path="gst-gstr1"          element={<AccountingGST defaultTab="gstr1" />} />
            <Route path="gst-gstr3b"         element={<AccountingGST defaultTab="gstr3b" />} />
            <Route path="gst-itc"            element={<AccountingGST defaultTab="itc" />} />
            <Route path="gst-calendar"       element={<AccountingGST defaultTab="calendar" />} />
            <Route path="gst-history"        element={<AccountingGST defaultTab="history" />} />
            <Route path="gst-health"         element={<AccountingGST defaultTab="health" />} />
            <Route path="reconciliation/*"   element={<AccountingBankReconciliation />} />
            <Route path="accounts"           element={<AccountingAccountsCenter />} />
            <Route path="assets"             element={<AccountingAssetManagement />} />
            <Route path="decisions"          element={<StrategicDecisionLedger />} />
            <Route path="reports"            element={<ReportsHub />} />

            {/* Fallback: unknown sub-path → control-tower */}
            <Route path="*" element={<Navigate to="control-tower" replace />} />
          </Routes>
        </Box>
      </Box>
    </Box>
  );
}
