/**
 * BridgeWorks Mock Data
 * Auto-used when the backend is unavailable (e.g. Netlify demo deployment).
 */

// ─── Helpers ────────────────────────────────────────────────────────────────
const today = new Date();
const fmt = (d) => d.toISOString().slice(0, 10);
const daysAgo = (n) => { const d = new Date(today); d.setDate(d.getDate() - n); return fmt(d); };

// ─── Team (6 people max, proper hierarchy) ───────────────────────────────────
// Jatin = Founder, Arjun = Engineering Manager, Priya = Sales Manager,
// Sneha = HR Manager, Rohit = Finance Staff, Divya = Design Worker
const EMPLOYEES = [
  {
    id: 1, employee_id: 'BW-001',
    name: 'Jatin Choudhary', full_name: 'Jatin Choudhary',
    username: 'jatin.choudhary',
    email: 'jatin@bridgeworks.in',
    department: 'Leadership', department_name: 'Leadership',
    designation: 'Founder & CEO', role: 'Founder & CEO',
    role_designation: 'Founder & CEO',
    category: 'Founder',
    status: 'Active', joining_date: '2020-01-01',
    phone: '+91 98765 00001', location: 'Bangalore',
    salary: 250000, working_style: 'Office', gender: 'Male',
    is_original_founder: true, is_co_founder: false, archived: false,
  },
  {
    id: 2, employee_id: 'BW-002',
    name: 'Arjun Sharma', full_name: 'Arjun Sharma',
    username: 'arjun.sharma',
    email: 'arjun@bridgeworks.in',
    department: 'Engineering', department_name: 'Engineering',
    designation: 'Engineering Manager', role: 'Engineering Manager',
    role_designation: 'Engineering Manager',
    category: 'Manager',
    status: 'Active', joining_date: '2021-03-15',
    phone: '+91 98765 43210', location: 'Bangalore',
    salary: 145000, working_style: 'Office', gender: 'Male',
    is_original_founder: false, is_co_founder: false, archived: false,
  },
  {
    id: 3, employee_id: 'BW-003',
    name: 'Priya Patel', full_name: 'Priya Patel',
    username: 'priya.patel',
    email: 'priya@bridgeworks.in',
    department: 'Sales', department_name: 'Sales',
    designation: 'Sales Manager', role: 'Sales Manager',
    role_designation: 'Sales Manager',
    category: 'Manager',
    status: 'Active', joining_date: '2021-07-01',
    phone: '+91 87654 32109', location: 'Mumbai',
    salary: 125000, working_style: 'Remote', gender: 'Female',
    is_original_founder: false, is_co_founder: false, archived: false,
  },
  {
    id: 4, employee_id: 'BW-004',
    name: 'Sneha Iyer', full_name: 'Sneha Iyer',
    username: 'sneha.iyer',
    email: 'sneha@bridgeworks.in',
    department: 'HR', department_name: 'HR',
    designation: 'HR Manager', role: 'HR Manager',
    role_designation: 'HR Manager',
    category: 'Manager',
    status: 'Active', joining_date: '2021-11-05',
    phone: '+91 76543 21098', location: 'Chennai',
    salary: 110000, working_style: 'Office', gender: 'Female',
    is_original_founder: false, is_co_founder: false, archived: false,
  },
  {
    id: 5, employee_id: 'BW-005',
    name: 'Rohit Verma', full_name: 'Rohit Verma',
    username: 'rohit.verma',
    email: 'rohit@bridgeworks.in',
    department: 'Finance', department_name: 'Finance',
    designation: 'Finance Analyst', role: 'Finance Analyst',
    role_designation: 'Finance Analyst',
    category: 'Staff',
    status: 'Active', joining_date: '2022-01-10',
    phone: '+91 65432 10987', location: 'Bangalore',
    salary: 98000, working_style: 'Office', gender: 'Male',
    is_original_founder: false, is_co_founder: false, archived: false,
  },
  {
    id: 6, employee_id: 'BW-006',
    name: 'Divya Krishnan', full_name: 'Divya Krishnan',
    username: 'divya.krishnan',
    email: 'divya@bridgeworks.in',
    department: 'Design', department_name: 'Design',
    designation: 'UI/UX Designer', role: 'UI/UX Designer',
    role_designation: 'UI/UX Designer',
    category: 'Staff',
    status: 'Active', joining_date: '2022-10-12',
    phone: '+91 54321 09876', location: 'Hyderabad',
    salary: 102000, working_style: 'Remote', gender: 'Female',
    is_original_founder: false, is_co_founder: false, archived: false,
  },
];

// ─── Finance / Accounting ────────────────────────────────────────────────────
const FINANCE_TRANSACTIONS = [
  { id: 1, date: daysAgo(1), department: 'Sales', account_name: 'Revenue - Software', description: 'Invoice #INV-2401 - TechCorp Ltd', amount: 285000, type: 'credit' },
  { id: 2, date: daysAgo(2), department: 'Operations', account_name: 'Office Supplies', description: 'Monthly stationery & consumables', amount: 12500, type: 'debit' },
  { id: 3, date: daysAgo(3), department: 'Engineering', account_name: 'Revenue - Consulting', description: 'Invoice #INV-2402 - StartupX Pvt Ltd', amount: 175000, type: 'credit' },
  { id: 4, date: daysAgo(5), department: 'HR', account_name: 'Salaries & Wages', description: 'July 2026 Payroll Run', amount: 580000, type: 'debit' },
  { id: 5, date: daysAgo(6), department: 'Finance', account_name: 'Bank Charges', description: 'HDFC Bank — quarterly service fee', amount: 3500, type: 'debit' },
  { id: 6, date: daysAgo(7), department: 'Sales', account_name: 'Revenue - Software', description: 'Invoice #INV-2403 - GlobalRetail Inc', amount: 420000, type: 'credit' },
  { id: 7, date: daysAgo(9), department: 'Marketing', account_name: 'Advertising', description: 'Google Ads — July campaign', amount: 55000, type: 'debit' },
  { id: 8, date: daysAgo(10), department: 'Engineering', account_name: 'Cloud Infrastructure', description: 'AWS — July billing cycle', amount: 38000, type: 'debit' },
  { id: 9, date: daysAgo(12), department: 'Sales', account_name: 'Revenue - SaaS', description: 'Invoice #INV-2404 - MediCare Hospitals', amount: 320000, type: 'credit' },
  { id: 10, date: daysAgo(14), department: 'Admin', account_name: 'Rent & Utilities', description: 'Office rent — July 2026', amount: 125000, type: 'debit' },
];

const JOURNAL_ENTRIES = [
  { id: 1, date: daysAgo(1), reference: 'JV-2601', description: 'Sales revenue recognition — July week 4', debit_account: 'Accounts Receivable', credit_account: 'Revenue - Software', amount: 285000, status: 'Posted' },
  { id: 2, date: daysAgo(3), reference: 'JV-2602', description: 'Payroll accrual — July 2026', debit_account: 'Salaries Expense', credit_account: 'Salaries Payable', amount: 580000, status: 'Posted' },
  { id: 3, date: daysAgo(5), reference: 'JV-2603', description: 'Depreciation — Office equipment', debit_account: 'Depreciation Expense', credit_account: 'Accumulated Depreciation', amount: 18750, status: 'Posted' },
  { id: 4, date: daysAgo(7), reference: 'JV-2604', description: 'Prepaid insurance adjustment', debit_account: 'Insurance Expense', credit_account: 'Prepaid Insurance', amount: 9500, status: 'Draft' },
  { id: 5, date: daysAgo(10), reference: 'JV-2605', description: 'Rent expense accrual', debit_account: 'Rent Expense', credit_account: 'Rent Payable', amount: 125000, status: 'Posted' },
];

const TRIAL_BALANCE = {
  accounts: [
    { account: 'Cash & Bank', debit: 2850000, credit: 0 },
    { account: 'Accounts Receivable', debit: 1245000, credit: 0 },
    { account: 'Inventory', debit: 385000, credit: 0 },
    { account: 'Fixed Assets', debit: 3200000, credit: 0 },
    { account: 'Accumulated Depreciation', debit: 0, credit: 480000 },
    { account: 'Accounts Payable', debit: 0, credit: 685000 },
    { account: 'Tax Payable', debit: 0, credit: 124500 },
    { account: 'Share Capital', debit: 0, credit: 2000000 },
    { account: 'Retained Earnings', debit: 0, credit: 1850000 },
    { account: 'Revenue - Software', debit: 0, credit: 4250000 },
    { account: 'Revenue - Consulting', debit: 0, credit: 1180000 },
    { account: 'Salaries Expense', debit: 2940000, credit: 0 },
    { account: 'Rent Expense', debit: 750000, credit: 0 },
  ],
  total_debit: 11370000,
  total_credit: 10569500,
};

const PROFIT_LOSS = {
  period: 'July 2026',
  revenue: {
    items: [
      { name: 'Revenue - Software Licences', amount: 4250000 },
      { name: 'Revenue - Consulting Services', amount: 1180000 },
      { name: 'Revenue - SaaS Subscriptions', amount: 890000 },
      { name: 'Interest Income', amount: 85200 },
    ],
    total: 6405200,
  },
  expenses: {
    items: [
      { name: 'Salaries & Wages', amount: 830000 },
      { name: 'Rent & Utilities', amount: 125000 },
      { name: 'Advertising & Marketing', amount: 55000 },
      { name: 'Cloud Infrastructure', amount: 38000 },
      { name: 'Depreciation', amount: 18750 },
      { name: 'Bank Charges', amount: 3500 },
    ],
    total: 1070250,
  },
  net_profit: 5334950,
  net_profit_margin: 83.3,
};

// Balance sheet — flat arrays as expected by accounting-balance-sheet.jsx
const BALANCE_SHEET = {
  as_of: fmt(today),
  assets: [
    { ledger_id: 1, name: 'Cash & Bank Balances', balance: 2850000, children: [] },
    { ledger_id: 2, name: 'Accounts Receivable', balance: 1245000, children: [] },
    { ledger_id: 3, name: 'Inventory', balance: 385000, children: [] },
    { ledger_id: 4, name: 'Property, Plant & Equipment', balance: 2720000, children: [
      { ledger_id: 41, name: 'Office Equipment', balance: 1500000 },
      { ledger_id: 42, name: 'Computers & Servers', balance: 1220000 },
    ]},
    { ledger_id: 5, name: 'Intangible Assets', balance: 650000, children: [] },
  ],
  liabilities: [
    { ledger_id: 10, name: 'Accounts Payable', balance: 685000, children: [] },
    { ledger_id: 11, name: 'Tax Payable', balance: 124500, children: [] },
    { ledger_id: 12, name: 'Salaries Payable', balance: 97000, children: [] },
    { ledger_id: 13, name: 'Long-term Borrowings', balance: 1800000, children: [] },
  ],
  equity: 6143500,
  total_assets: 7850000,
  total_liabilities: 2706500,
};

// ─── GST ─────────────────────────────────────────────────────────────────────
const GST_DASHBOARD = {
  month: today.getMonth() + 1,
  year: today.getFullYear(),
  output_gst: 768624,
  input_credit: 312480,
  net_liability: 456144,
  gstr1_filed: true,
  gstr3b_filed: false,
  itc_available: 312480,
  itc_utilized: 280000,
  pending_invoices: 3,
  chart_data: [
    { month: 'Feb', output: 620000, input: 245000 },
    { month: 'Mar', output: 710000, input: 298000 },
    { month: 'Apr', output: 680000, input: 275000 },
    { month: 'May', output: 740000, input: 310000 },
    { month: 'Jun', output: 695000, input: 285000 },
    { month: 'Jul', output: 768624, input: 312480 },
  ],
};

const GST_TRANSACTIONS = Array.from({ length: 10 }, (_, i) => ({
  id: i + 1,
  invoice_number: `INV-${2400 + i}`,
  party_name: ['TechCorp Ltd', 'StartupX Pvt Ltd', 'GlobalRetail Inc', 'MediCare Hospitals', 'UrbanFin Wealth'][i % 5],
  gstin: `29ABCDE${1234 + i}F1Z5`,
  date: daysAgo(i * 3),
  taxable_value: 50000 + (i * 30000),
  cgst: (50000 + i * 30000) * 0.09,
  sgst: (50000 + i * 30000) * 0.09,
  igst: 0,
  total_gst: (50000 + i * 30000) * 0.18,
  invoice_type: i % 3 === 0 ? 'Credit Note' : 'Tax Invoice',
  status: i % 4 === 0 ? 'Pending' : 'Filed',
}));

// ─── Payroll ──────────────────────────────────────────────────────────────────
const PAYROLL_RUNS = EMPLOYEES.map((emp) => ({
  id: emp.id,
  employee_id: emp.employee_id,
  employee_name: emp.name,
  department: emp.department,
  designation: emp.designation,
  basic_salary: Math.round(emp.salary * 0.5),
  hra: Math.round(emp.salary * 0.2),
  special_allowance: Math.round(emp.salary * 0.3),
  gross_salary: emp.salary,
  pf_deduction: Math.round(emp.salary * 0.12),
  esi_deduction: Math.round(emp.salary * 0.0175),
  tds_deduction: Math.round(emp.salary * 0.05),
  other_deductions: 0,
  net_salary: Math.round(emp.salary * (1 - 0.12 - 0.0175 - 0.05)),
  month: today.getMonth() + 1,
  year: today.getFullYear(),
  status: 'Processed',
  payment_date: daysAgo(3),
}));

// ─── Attendance ───────────────────────────────────────────────────────────────
const ATTENDANCE = EMPLOYEES.map((emp) => ({
  id: emp.id,
  employee_id: emp.employee_id,
  employee_name: emp.name,
  department: emp.department,
  date: fmt(today),
  check_in: '09:15 AM',
  check_out: '06:30 PM',
  status: 'Present',
  working_hours: 9.25,
  location: emp.location,
}));

// ─── Assets ───────────────────────────────────────────────────────────────────
const ASSETS = [
  { id: 1, name: 'MacBook Pro 14" M3', category: 'IT Equipment', purchase_date: '2024-01-15', cost: 185000, current_value: 148000, depreciation_rate: 20, assigned_to: 'Arjun Sharma', status: 'In Use', location: 'Bangalore HQ' },
  { id: 2, name: 'Dell 27" 4K Monitor', category: 'IT Equipment', purchase_date: '2024-02-10', cost: 45000, current_value: 36000, depreciation_rate: 20, assigned_to: 'Divya Krishnan', status: 'In Use', location: 'Hyderabad Office' },
  { id: 3, name: 'Office Workstation Set (6 seats)', category: 'Furniture', purchase_date: '2022-06-01', cost: 185000, current_value: 148000, depreciation_rate: 10, assigned_to: null, status: 'In Use', location: 'Bangalore HQ' },
];

// ─── Pending Expenses ─────────────────────────────────────────────────────────
const PENDING_EXPENSES = [
  { id: 1, employee: 'Arjun Sharma', category: 'Travel', description: 'Delhi client visit — flight + hotel', amount: 28500, date: daysAgo(3), status: 'Pending', receipt: true },
  { id: 2, employee: 'Priya Patel', category: 'Conference', description: 'SaaSBoomi Annual Summit — Mumbai', amount: 15000, date: daysAgo(7), status: 'Approved', receipt: true },
  { id: 3, employee: 'Rohit Verma', category: 'Software', description: 'GitHub Copilot subscription', amount: 1700, date: daysAgo(9), status: 'Rejected', receipt: false },
];

// ─── Hiring ───────────────────────────────────────────────────────────────────
const JOB_POSTINGS = [
  { id: 1, title: 'Senior Backend Developer', department: 'Engineering', location: 'Bangalore', type: 'Full-time', status: 'Active', applicants: 47, posted_date: daysAgo(14), experience: '4-6 years', skills: ['Python', 'Django', 'PostgreSQL'] },
  { id: 2, title: 'UI/UX Designer', department: 'Design', location: 'Remote', type: 'Full-time', status: 'Active', applicants: 31, posted_date: daysAgo(10), experience: '3-5 years', skills: ['Figma', 'React', 'Design Systems'] },
  { id: 3, title: 'Sales BDM', department: 'Sales', location: 'Mumbai', type: 'Full-time', status: 'Closed', applicants: 58, posted_date: daysAgo(45), experience: '5-8 years', skills: ['B2B Sales', 'CRM'] },
];

// ─── My Desk ──────────────────────────────────────────────────────────────────
const NOTES = [
  { id: 1, title: 'Q3 Revenue Strategy', content: 'Focus on upselling SaaS subscriptions to existing enterprise clients. Target 20% MoM growth.', tags: ['strategy', 'revenue'], created_at: daysAgo(1), updated_at: daysAgo(1), is_pinned: true },
  { id: 2, title: 'Board Meeting Notes — July 28', content: 'Expand to Tier-2 cities, hire 3 more engineers Q4, close Series A by December.', tags: ['meeting', 'board'], created_at: daysAgo(5), updated_at: daysAgo(4), is_pinned: true },
  { id: 3, title: 'AWS Cost Optimisation', content: 'Reserved instances for prod EC2, move dev to spot instances, enable S3 intelligent tiering.', tags: ['tech', 'infra'], created_at: daysAgo(7), updated_at: daysAgo(7), is_pinned: false },
  { id: 4, title: 'New Client Onboarding Checklist', content: '1. Welcome kit 2. Kickoff call 3. API docs 4. Assign CSM 5. 30-day review', tags: ['process', 'clients'], created_at: daysAgo(10), updated_at: daysAgo(9), is_pinned: false },
];

const KANBAN_TASKS = [
  { id: 1, title: 'Migrate auth to JWT', description: 'Replace session auth with JWT across all API endpoints', status: 'todo', priority: 'high', assignee: 'Arjun Sharma', due_date: daysAgo(-7), tags: ['backend', 'security'] },
  { id: 2, title: 'Design new dashboard layout', description: 'Redesign Finance Control Tower with better chart hierarchy', status: 'in_progress', priority: 'medium', assignee: 'Divya Krishnan', due_date: daysAgo(-3), tags: ['design', 'frontend'] },
  { id: 3, title: 'GST GSTR-3B report fix', description: 'Fix ITC calculation mismatch in GSTR-3B monthly summary', status: 'in_progress', priority: 'high', assignee: 'Rohit Verma', due_date: daysAgo(-2), tags: ['accounting', 'gst'] },
  { id: 4, title: 'Deploy to production', description: 'Final production deployment with Nginx + Daphne + SSL', status: 'done', priority: 'critical', assignee: 'Arjun Sharma', due_date: daysAgo(2), tags: ['devops'] },
  { id: 5, title: 'Monthly payroll run', description: 'Process July 2026 payroll for all 6 employees', status: 'done', priority: 'high', assignee: 'Sneha Iyer', due_date: daysAgo(3), tags: ['hr', 'payroll'] },
];

const CHAT_MESSAGES = [
  { id: 1, sender: 'Sneha Iyer', message: 'July payroll processed. Payslips sent to everyone!', channel: 'general', timestamp: daysAgo(1) + ' 10:32 AM', avatar: 'SI' },
  { id: 2, sender: 'Rohit Verma', message: 'GST returns for July are almost ready. Waiting on 2 vendor invoices.', channel: 'finance', timestamp: daysAgo(1) + ' 11:15 AM', avatar: 'RV' },
  { id: 3, sender: 'Arjun Sharma', message: 'v2.4 deployed to production. All systems green ✅', channel: 'general', timestamp: daysAgo(1) + ' 02:48 PM', avatar: 'AS' },
  { id: 4, sender: 'Priya Patel', message: 'Closed the MediCare deal! ₹3.2L annual contract signed.', channel: 'general', timestamp: daysAgo(2) + ' 04:20 PM', avatar: 'PP' },
];

const DIARY_ENTRIES = [
  { id: 1, date: daysAgo(0), content: 'Focused on closing the MediCare renewal. Positive signals from their CTO.', mood: 'good' },
  { id: 2, date: daysAgo(1), content: 'Reviewed Q3 financial projections with Rohit. Revenue outlook strong — on track for 28% growth.', mood: 'great' },
  { id: 3, date: daysAgo(2), content: 'All-hands meeting. Team morale is high after the Series A announcement.', mood: 'great' },
];

const NOTIFICATIONS = [
  { id: 1, title: 'GSTR-3B Due Soon', message: 'GSTR-3B for July 2026 is due in 5 days. ₹4,56,144 payable.', type: 'warning', read: false, created_at: daysAgo(0) },
  { id: 2, title: 'Payroll Processed', message: 'July 2026 payroll completed. Disbursed to 6 employees.', type: 'success', read: false, created_at: daysAgo(1) },
  { id: 3, title: 'Expense Pending Approval', message: '1 expense claim is pending your approval.', type: 'info', read: true, created_at: daysAgo(2) },
];

const DEPARTMENTS = [
  { id: 1, name: 'Leadership', head: 'Jatin Choudhary', headcount: 1, budget: 3000000, spent: 2500000 },
  { id: 2, name: 'Engineering', head: 'Arjun Sharma', headcount: 1, budget: 2000000, spent: 1450000 },
  { id: 3, name: 'Sales', head: 'Priya Patel', headcount: 1, budget: 1500000, spent: 1250000 },
  { id: 4, name: 'HR', head: 'Sneha Iyer', headcount: 1, budget: 1200000, spent: 980000 },
  { id: 5, name: 'Finance', head: 'Rohit Verma', headcount: 1, budget: 1000000, spent: 780000 },
  { id: 6, name: 'Design', head: 'Divya Krishnan', headcount: 1, budget: 1200000, spent: 950000 },
];

// ─── URL Routing Map ──────────────────────────────────────────────────────────
export const MOCK_ROUTES = [
  // ── Finance / Accounting ─────────────────────────────────────────────────
  { pattern: /\/api\/accounting\/transactions/, data: () => FINANCE_TRANSACTIONS },
  { pattern: /\/api\/accounting\/journals/, data: () => ({ results: JOURNAL_ENTRIES, count: JOURNAL_ENTRIES.length }) },
  { pattern: /\/api\/accounting\/trial-balance/, data: () => TRIAL_BALANCE },
  { pattern: /\/api\/accounting\/profit-loss/, data: () => PROFIT_LOSS },
  { pattern: /\/api\/accounting\/balance-sheet/, data: () => BALANCE_SHEET },
  { pattern: /\/api\/accounting\/dashboard/, data: () => ({
    total_revenue: 6405200,
    total_expenses: 1070250,
    net_profit: 5334950,
    cash_balance: 2850000,
    accounts_receivable: 1245000,
    accounts_payable: 685000,
    monthly_trend: [
      { month: 'Feb', revenue: 4800000, expenses: 850000 },
      { month: 'Mar', revenue: 5200000, expenses: 920000 },
      { month: 'Apr', revenue: 5500000, expenses: 980000 },
      { month: 'May', revenue: 5900000, expenses: 1020000 },
      { month: 'Jun', revenue: 6100000, expenses: 1045000 },
      { month: 'Jul', revenue: 6405200, expenses: 1070250 },
    ],
    recent_transactions: FINANCE_TRANSACTIONS.slice(0, 5),
  }) },
  { pattern: /\/api\/accounting\/invoices/, data: () => ({ results: FINANCE_TRANSACTIONS.filter(t => t.type === 'credit'), count: 5 }) },
  { pattern: /\/api\/accounting\/expenses/, data: () => PENDING_EXPENSES },
  { pattern: /\/api\/accounting\/assets/, data: () => ({ results: ASSETS, count: ASSETS.length }) },
  { pattern: /\/api\/accounting\/payroll/, data: () => ({ results: PAYROLL_RUNS, count: PAYROLL_RUNS.length, total_gross: 830000, total_net: 697000 }) },
  { pattern: /\/api\/accounting\/pending-expenses/, data: () => PENDING_EXPENSES },
  { pattern: /\/api\/accounting\/department/, data: () => ({ departments: DEPARTMENTS }) },
  { pattern: /\/api\/accounting\/reconciliation/, data: () => ({
    matched: 47, unmatched: 3, total: 50,
    bank_balance: 2850000, book_balance: 2840000, difference: 10000,
    auto_match_rate: 94, review_queue_count: 3, avg_confidence: 87,
    unmatched_count: 3, high_risk_count: 1, duplicate_count: 1,
  }) },
  { pattern: /\/api\/accounting\/ledger-summary/, data: () => ({
    accounts: [
      { account_name: 'Cash & Bank', debit_total: 5820000, credit_total: 2970000, balance: 2850000 },
      { account_name: 'Accounts Receivable', debit_total: 1245000, credit_total: 0, balance: 1245000 },
      { account_name: 'Revenue - Software', debit_total: 0, credit_total: 4250000, balance: 4250000 },
      { account_name: 'Salaries Expense', debit_total: 830000, credit_total: 0, balance: 830000 },
    ],
  }) },
  { pattern: /\/api\/accounting\/settlements/, data: () => ({ results: [], count: 0 }) },

  // ── Finance Control Tower ─────────────────────────────────────────────────
  { pattern: /\/api\/finance\/control-tower/, data: () => ({
    cashPosition: 2850000, receivables: 1245000, payables: 685000,
    gstLiability: 456144, gstDueDays: 5,
    payrollPending: false, payrollTotal: 830000,
    eolAssets: 0, expensesGrowth: 2.4, incomeGrowth: 8.7,
    netWorth: 6143500, monthlyBurn: 178375,
    reconciliationAccuracy: 94, pendingMatches: 3, connectedAccounts: 2,
    dailyInflow: 213507, dailyOutflow: 35675,
    totalAssets: 7850000, assetHealth: 96, revenue: 6405200, profit: 5334950,
    forecastAccuracy: 100,
    decisions: [
      { id: 1, title: 'Approve Q4 Engineering Hiring Budget', amount: 2000000, priority: 'High', status: 'Pending' },
    ],
    actions: [
      { id: 1, text: 'File GSTR-3B before August 20', type: 'Compliance', priority: 'Critical', time: '5 days' },
      { id: 2, text: 'Approve 1 pending expense claim', type: 'Finance', priority: 'Medium', time: 'Today' },
    ],
    timelineGroups: {
      TODAY: [
        { id: 1, text: 'Invoice INV-2401 created — ₹2,85,000', type: 'Finance', time: '11:42 AM' },
      ],
      YESTERDAY: [
        { id: 2, text: 'July payroll processed — ₹8,30,000', type: 'Finance', time: '10:00 AM' },
      ],
      'PAST WEEK': [
        { id: 3, text: 'GSTR-1 filed for July 2026', type: 'Compliance', time: 'Mon 4:00 PM' },
      ],
    },
    infraSystems: [
      { name: 'Banking & Reconciliation', health: 94, risk: 'Low', alerts: 0 },
      { name: 'GST Compliance Engine', health: 87, risk: 'Medium', alerts: 1 },
      { name: 'Payroll Processing', health: 100, risk: 'Low', alerts: 0 },
    ],
    accounts: [
      { id: 1, name: 'HDFC Current Account', bank: 'HDFC Bank', balance: 2100000, last_sync: 'Just now' },
      { id: 2, name: 'ICICI Savings Account', bank: 'ICICI Bank', balance: 750000, last_sync: '15 min ago' },
    ],
  }) },
  { pattern: /\/api\/finance\/executive-report/, data: () => ({
    report: `# CFO Executive Report — ${new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}\n\n## Financial Summary\n\n**Revenue:** ₹64,05,200 | **Expenses:** ₹10,70,250 | **Net Profit:** ₹53,34,950 (83.3% margin)\n\n## Key Highlights\n- Revenue grew **8.7% MoM** driven by enterprise software licences\n- Lean team of 6 — low burn rate of ₹1,78,375/month\n- Cash position healthy at ₹28,50,000 with 16-month runway\n- GSTR-3B due in 5 days — ₹4,56,144 payable\n\n## Recommendations\n1. Accelerate receivables collection — ₹12,45,000 outstanding\n2. Consider hiring 2 engineers in Q4 to accelerate product roadmap\n3. File GSTR-3B before August 20 deadline`,
  }) },
  { pattern: /\/api\/finance\/financial-plan/, data: () => ({
    plan: `# 90-Day Financial Plan\n\n## Month 1 (August 2026)\n- **Target Revenue:** ₹70,00,000\n- File GSTR-3B by Aug 20\n- Close 2 enterprise deals in pipeline\n\n## Month 2 (September 2026)\n- **Target Revenue:** ₹75,00,000\n- Begin engineering hiring (2 roles)\n\n## Month 3 (October 2026)\n- **Target Revenue:** ₹82,00,000\n- Series A deployment planning\n- Tier-2 city market expansion`,
  }) },
  { pattern: /\/api\/finance\/ai-chat/, data: () => ({
    reply: 'Demo mode — connect the backend to enable live AI-powered financial analysis.',
  }) },

  // ── GST ──────────────────────────────────────────────────────────────────
  { pattern: /\/api\/accounting\/gst\/dashboard/, data: () => GST_DASHBOARD },
  { pattern: /\/api\/accounting\/gst\/summary/, data: () => GST_DASHBOARD },
  { pattern: /\/api\/accounting\/gst\/itc-reconciliation/, data: () => ({
    itc_claimed: 312480, itc_available: 312480, itc_utilized: 280000, itc_balance: 32480, mismatches: 1,
  }) },
  { pattern: /\/api\/accounting\/gst/, data: () => ({ results: GST_TRANSACTIONS, count: GST_TRANSACTIONS.length }) },

  // ── HR / Employees ────────────────────────────────────────────────────────
  { pattern: /\/api\/hr\/employees/, data: () => ({ results: EMPLOYEES, count: EMPLOYEES.length }) },
  { pattern: /\/api\/employees/, data: () => ({ results: EMPLOYEES, count: EMPLOYEES.length }) },
  { pattern: /\/api\/hr\/attendance/, data: () => ({ results: ATTENDANCE, count: ATTENDANCE.length }) },
  { pattern: /\/api\/hr\/payroll/, data: () => ({ results: PAYROLL_RUNS, count: PAYROLL_RUNS.length }) },
  { pattern: /\/api\/hr\/hiring/, data: () => ({ results: JOB_POSTINGS, count: JOB_POSTINGS.length }) },
  { pattern: /\/api\/hiring/, data: () => ({ results: JOB_POSTINGS, count: JOB_POSTINGS.length }) },
  { pattern: /\/api\/hr\/departments/, data: () => ({ results: DEPARTMENTS }) },

  // ── Workforce (MasterWorkforceSheet) ─────────────────────────────────────
  { pattern: /\/api\/workforce\/departments/, data: () => DEPARTMENTS.map(d => ({ id: d.id, name: d.name })) },
  { pattern: /\/api\/workforce\/members/, data: () => EMPLOYEES },
  { pattern: /\/api\/workforce\/documents/, data: () => [] },
  { pattern: /\/api\/workforce\/permissions/, data: () => ({
    permissions: { finance: ['view', 'edit'], hr: ['view', 'edit'], mydesk: ['view', 'edit', 'create'] },
  }) },

  // ── Team (WorkforceHierarchyTree & TeamDirectory) ─────────────────────────
  { pattern: /\/api\/team\/members/, data: () => EMPLOYEES },
  { pattern: /\/api\/team\/permissions/, data: () => ({
    permissions: { finance: ['view', 'edit'], hr: ['view', 'edit'], mydesk: ['view', 'edit', 'create'] },
  }) },
  { pattern: /\/api\/team\/delete/, data: () => ({ success: true }) },

  // ── Auth / User ───────────────────────────────────────────────────────────
  { pattern: /\/api\/current-user/, data: () => ({
    id: 1,
    full_name: 'Jatin Choudhary', username: 'jatin.choudhary',
    email: 'admin@local.dev', is_staff: true, is_superuser: true,
    department: 'Leadership', role: 'Founder & CEO',
    organisation: { id: 1, name: 'BridgeWorks', gstin: '29AABCB1234C1ZV' },
  }) },
  { pattern: /\/api\/permissions\/schema/, data: () => ({
    modules: ['finance', 'hr', 'mydesk', 'reports', 'settings'],
    actions: ['view', 'create', 'edit', 'delete', 'approve'],
    roles: ['Founder', 'Manager', 'Staff', 'Viewer'],
  }) },
  { pattern: /\/api\/auth\/user/, data: () => ({
    id: 1, email: 'admin@local.dev', name: 'Jatin Choudhary', is_staff: true,
    organisation: { id: 1, name: 'BridgeWorks', gstin: '29AABCB1234C1ZV' },
    permissions: ['finance.view', 'hr.view', 'mydesk.view', 'finance.edit', 'hr.edit'],
  }) },
  { pattern: /\/api\/auth\/login/, data: () => ({
    token: 'demo-token-bridgeworks-2026',
    user: { id: 1, email: 'admin@local.dev', name: 'Jatin Choudhary', is_staff: true },
  }) },
  { pattern: /\/accounts\/profile/, data: () => ({
    id: 1, email: 'admin@local.dev', name: 'Jatin Choudhary', is_staff: true,
    organisation: { id: 1, name: 'BridgeWorks' },
  }) },

  // ── My Desk ───────────────────────────────────────────────────────────────
  { pattern: /\/api\/mydesk\/notes/, data: () => NOTES },
  { pattern: /\/api\/mydesk\/tasks/, data: () => KANBAN_TASKS },
  { pattern: /\/api\/mydesk\/diary/, data: () => DIARY_ENTRIES },
  { pattern: /\/api\/mydesk\/expenses/, data: () => PENDING_EXPENSES },
  { pattern: /\/api\/mydesk\/chat/, data: () => CHAT_MESSAGES },
  { pattern: /\/api\/mydesk\/profile/, data: () => ({
    id: 1, name: 'Jatin Choudhary', email: 'admin@local.dev',
    role: 'Founder & CEO', department: 'Leadership',
    phone: '+91 98765 00001', location: 'Bangalore',
  }) },

  // ── Notifications & Activity ──────────────────────────────────────────────
  { pattern: /\/api\/notifications/, data: () => NOTIFICATIONS },
  { pattern: /\/api\/activity/, data: () => [
    { id: 1, action: 'Invoice created', user: 'Priya Patel', module: 'Finance', details: 'INV-2401 — ₹2,85,000', timestamp: daysAgo(0) + ' 11:42 AM' },
    { id: 2, action: 'Payroll processed', user: 'Sneha Iyer', module: 'HR', details: 'July 2026 — ₹8,30,000 disbursed', timestamp: daysAgo(1) + ' 10:00 AM' },
    { id: 3, action: 'GST return filed', user: 'Rohit Verma', module: 'GST', details: 'GSTR-1 for July 2026', timestamp: daysAgo(4) + ' 04:00 PM' },
  ] },

  // ── Presence ──────────────────────────────────────────────────────────────
  { pattern: /\/api\/presence/, data: () => EMPLOYEES.map(emp => ({
    user_id: emp.id, resolved_status: 'online', manual_status: null,
  })) },

  // ── Catch-all ─────────────────────────────────────────────────────────────
  { pattern: /.*/, data: () => ({ results: [], count: 0, success: true }) },
];

export function getMockData(url) {
  const path = url.replace(/^https?:\/\/[^/]+/, '');
  for (const route of MOCK_ROUTES) {
    if (route.pattern.test(path)) {
      return route.data();
    }
  }
  return { results: [], count: 0 };
}
