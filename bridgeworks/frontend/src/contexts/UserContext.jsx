import React, { createContext, useContext } from 'react';

// ── Stub UserContext ──────────────────────────────────────────────────────────
// Accounting software runs without authentication.
// This stub provides a mock admin user so that components using useUser()
// (FinanceControlTower, DepartmentExpenseTracker) work without modification.

const MOCK_USER = {
  id: 1,
  email: 'admin@accounting.local',
  name: 'Admin',
  is_admin: true,
  is_founder: true,
  is_superuser: true,
  role_permissions: ['*:*:*'],
};

const UserContext = createContext({ user: MOCK_USER, loadingUser: false });

export function UserProvider({ children }) {
  return (
    <UserContext.Provider value={{ user: MOCK_USER, loadingUser: false }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return useContext(UserContext);
}

// Stub for components that import useCurrency
export function useCurrency() {
  return { currency: 'INR', symbol: '₹', formatAmount: (v) => `₹${Number(v).toLocaleString('en-IN')}` };
}

export default UserContext;
