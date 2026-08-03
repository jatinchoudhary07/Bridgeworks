/**
 * BridgeWorks Mock Data
 * Auto-used when the backend is unavailable (e.g. Netlify demo deployment).
 * This simulates all API endpoints with realistic Indian business data.
 */

// ─── Helpers ────────────────────────────────────────────────────────────────
const today = new Date();
const fmt = (d) => d.toISOString().slice(0, 10);
const daysAgo = (n) => { const d = new Date(today); d.setDate(d.getDate() - n); return fmt(d); };
const monthAgo = (n) => { const d = new Date(today); d.setMonth(d.getMonth() - n); return fmt(d); };

// ─── Finance / Accounting ────────────────────────────────────────────────────
const FINANCE_TRANSACTIONS = [
  { id: 1, date: daysAgo(1), department: 'Sales', account_name: 'Revenue - Software', description: 'Invoice #INV-2401 - TechCorp Ltd', amount: 285000, type: 'credit' },
  { id: 2, date: daysAgo(2), department: 'Operations', account_name: 'Office Supplies', description: 'Monthly stationery & consumables', amount: 12500, type: 'debit' },
  { id: 3, date: daysAgo(3), department: 'Engineering', account_name: 'Revenue - Consulting', description: 'Invoice #INV-2402 - StartupX Pvt Ltd', amount: 175000, type: 'credit' },
  { id: 4, date: daysAgo(5), department: 'HR', account_name: 'Salaries & Wages', description: 'July 2026 Payroll Run', amount: 980000, type: 'debit' },
  { id: 5, date: daysAgo(6), department: 'Finance', account_name: 'Bank Charges', description: 'HDFC Bank — quarterly service fee', amount: 3500, type: 'debit' },
  { id: 6, date: daysAgo(7), department: 'Sales', account_name: 'Revenue - Software', description: 'Invoice #INV-2403 - GlobalRetail Inc', amount: 420000, type: 'credit' },
  { id: 7, date: daysAgo(9), department: 'Marketing', account_name: 'Advertising', description: 'Google Ads — July campaign', amount: 55000, type: 'debit' },
  { id: 8, date: daysAgo(10), department: 'Engineering', account_name: 'Cloud Infrastructure', description: 'AWS — July billing cycle', amount: 38000, type: 'debit' },
  { id: 9, date: daysAgo(12), department: 'Sales', account_name: 'Revenue - SaaS', description: 'Invoice #INV-2404 - MediCare Hospitals', amount: 320000, type: 'credit' },
  { id: 10, date: daysAgo(14), department: 'Admin', account_name: 'Rent & Utilities', description: 'Office rent — July 2026', amount: 125000, type: 'debit' },
  { id: 11, date: daysAgo(15), department: 'Sales', account_name: 'Revenue - Software', description: 'Invoice #INV-2405 - InfraBuilders Co', amount: 510000, type: 'credit' },
  { id: 12, date: daysAgo(18), department: 'Operations', account_name: 'Travel & Conveyance', description: 'Client visit — Mumbai & Pune trips', amount: 28000, type: 'debit' },
  { id: 13, date: daysAgo(20), department: 'Engineering', account_name: 'Software Licences', description: 'JetBrains All Products Pack', amount: 18500, type: 'debit' },
  { id: 14, date: daysAgo(22), department: 'Sales', account_name: 'Revenue - Consulting', description: 'Invoice #INV-2406 - UrbanFin Wealth', amount: 240000, type: 'credit' },
  { id: 15, date: daysAgo(25), department: 'Finance', account_name: 'Interest Income', description: 'FD interest — ICICI Bank', amount: 14200, type: 'credit' },
];

const JOURNAL_ENTRIES = [
  { id: 1, date: daysAgo(1), reference: 'JV-2601', description: 'Sales revenue recognition — July week 4', debit_account: 'Accounts Receivable', credit_account: 'Revenue - Software', amount: 285000, status: 'Posted' },
  { id: 2, date: daysAgo(3), reference: 'JV-2602', description: 'Payroll accrual — July 2026', debit_account: 'Salaries Expense', credit_account: 'Salaries Payable', amount: 980000, status: 'Posted' },
  { id: 3, date: daysAgo(5), reference: 'JV-2603', description: 'Depreciation — Office equipment', debit_account: 'Depreciation Expense', credit_account: 'Accumulated Depreciation', amount: 18750, status: 'Posted' },
  { id: 4, date: daysAgo(7), reference: 'JV-2604', description: 'Prepaid insurance adjustment', debit_account: 'Insurance Expense', credit_account: 'Prepaid Insurance', amount: 9500, status: 'Draft' },
  { id: 5, date: daysAgo(10), reference: 'JV-2605', description: 'Rent expense accrual', debit_account: 'Rent Expense', credit_account: 'Rent Payable', amount: 125000, status: 'Posted' },
];

const TRIAL_BALANCE = {
  accounts: [
    { account: 'Cash & Bank', debit: 2850000, credit: 0 },
    { account: 'Accounts Receivable', debit: 1245000, credit: 0 },
    { account: 'Inventory', debit: 385000, credit: 0 },
    { account: 'Prepaid Expenses', debit: 45000, credit: 0 },
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
    { account: 'Advertising Expense', debit: 385000, credit: 0 },
    { account: 'Cloud Infrastructure', debit: 228000, credit: 0 },
    { account: 'Depreciation Expense', debit: 112500, credit: 0 },
  ],
  total_debit: 12140500,
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
      { name: 'Salaries & Wages', amount: 2940000 },
      { name: 'Rent & Utilities', amount: 750000 },
      { name: 'Advertising & Marketing', amount: 385000 },
      { name: 'Cloud Infrastructure', amount: 228000 },
      { name: 'Depreciation', amount: 112500 },
      { name: 'Travel & Conveyance', amount: 168000 },
      { name: 'Office Supplies', amount: 75000 },
      { name: 'Software Licences', amount: 111000 },
      { name: 'Bank Charges', amount: 21000 },
    ],
    total: 4790500,
  },
  net_profit: 1614700,
  net_profit_margin: 25.2,
};

const BALANCE_SHEET = {
  as_of: fmt(today),
  assets: {
    current: [
      { name: 'Cash & Bank Balances', amount: 2850000 },
      { name: 'Accounts Receivable', amount: 1245000 },
      { name: 'Inventory', amount: 385000 },
      { name: 'Prepaid Expenses', amount: 45000 },
    ],
    non_current: [
      { name: 'Property, Plant & Equipment', amount: 3200000 },
      { name: 'Less: Accumulated Depreciation', amount: -480000 },
      { name: 'Intangible Assets', amount: 650000 },
      { name: 'Long-term Investments', amount: 1200000 },
    ],
    total: 9095000,
  },
  liabilities: {
    current: [
      { name: 'Accounts Payable', amount: 685000 },
      { name: 'Tax Payable', amount: 124500 },
      { name: 'Salaries Payable', amount: 246000 },
      { name: 'Short-term Loans', amount: 500000 },
    ],
    non_current: [
      { name: 'Long-term Borrowings', amount: 1800000 },
      { name: 'Deferred Tax Liability', amount: 280000 },
    ],
    total: 3635500,
  },
  equity: {
    items: [
      { name: 'Share Capital', amount: 2000000 },
      { name: 'Retained Earnings', amount: 1850000 },
      { name: 'Current Year Profit', amount: 1614700 },
      { name: 'Other Comprehensive Income', amount: -5200 },
    ],
    total: 5459500,
  },
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
  pending_invoices: 7,
  chart_data: [
    { month: 'Feb', output: 620000, input: 245000 },
    { month: 'Mar', output: 710000, input: 298000 },
    { month: 'Apr', output: 680000, input: 275000 },
    { month: 'May', output: 740000, input: 310000 },
    { month: 'Jun', output: 695000, input: 285000 },
    { month: 'Jul', output: 768624, input: 312480 },
  ],
};

const GST_TRANSACTIONS = Array.from({ length: 20 }, (_, i) => ({
  id: i + 1,
  invoice_number: `INV-${2400 + i}`,
  party_name: ['TechCorp Ltd', 'StartupX Pvt Ltd', 'GlobalRetail Inc', 'MediCare Hospitals', 'UrbanFin Wealth', 'InfraBuilders Co', 'LogiTrans Pvt Ltd', 'RetailHub India'][i % 8],
  gstin: `29ABCDE${1234 + i}F1Z5`,
  date: daysAgo(i * 2),
  taxable_value: 50000 + (i * 25000),
  cgst: (50000 + i * 25000) * 0.09,
  sgst: (50000 + i * 25000) * 0.09,
  igst: 0,
  total_gst: (50000 + i * 25000) * 0.18,
  invoice_type: i % 3 === 0 ? 'Credit Note' : 'Tax Invoice',
  status: i % 5 === 0 ? 'Pending' : 'Filed',
}));

// ─── Payroll ──────────────────────────────────────────────────────────────────
const EMPLOYEES = [
  { id: 1, employee_id: 'BW-001', name: 'Arjun Sharma', email: 'arjun.sharma@bridgeworks.in', department: 'Engineering', designation: 'Senior Developer', status: 'Active', joining_date: '2022-03-15', phone: '+91 98765 43210', location: 'Bangalore', salary: 145000 },
  { id: 2, employee_id: 'BW-002', name: 'Priya Patel', email: 'priya.patel@bridgeworks.in', department: 'Sales', designation: 'Sales Manager', status: 'Active', joining_date: '2021-07-01', phone: '+91 87654 32109', location: 'Mumbai', salary: 125000 },
  { id: 3, employee_id: 'BW-003', name: 'Rohit Verma', email: 'rohit.verma@bridgeworks.in', department: 'Finance', designation: 'Finance Analyst', status: 'Active', joining_date: '2023-01-10', phone: '+91 76543 21098', location: 'Delhi', salary: 98000 },
  { id: 4, employee_id: 'BW-004', name: 'Sneha Iyer', email: 'sneha.iyer@bridgeworks.in', department: 'HR', designation: 'HR Manager', status: 'Active', joining_date: '2020-11-05', phone: '+91 65432 10987', location: 'Chennai', salary: 110000 },
  { id: 5, employee_id: 'BW-005', name: 'Karan Mehta', email: 'karan.mehta@bridgeworks.in', department: 'Marketing', designation: 'Digital Marketing Lead', status: 'Active', joining_date: '2022-08-20', phone: '+91 54321 09876', location: 'Hyderabad', salary: 105000 },
  { id: 6, employee_id: 'BW-006', name: 'Ananya Nair', email: 'ananya.nair@bridgeworks.in', department: 'Engineering', designation: 'Frontend Developer', status: 'Active', joining_date: '2023-04-18', phone: '+91 43210 98765', location: 'Pune', salary: 92000 },
  { id: 7, employee_id: 'BW-007', name: 'Vikram Singh', email: 'vikram.singh@bridgeworks.in', department: 'Operations', designation: 'Operations Manager', status: 'Active', joining_date: '2021-02-28', phone: '+91 32109 87654', location: 'Bangalore', salary: 135000 },
  { id: 8, employee_id: 'BW-008', name: 'Meera Joshi', email: 'meera.joshi@bridgeworks.in', department: 'Sales', designation: 'Business Development', status: 'On Leave', joining_date: '2022-06-15', phone: '+91 21098 76543', location: 'Mumbai', salary: 115000 },
  { id: 9, employee_id: 'BW-009', name: 'Rahul Gupta', email: 'rahul.gupta@bridgeworks.in', department: 'Engineering', designation: 'Backend Developer', status: 'Active', joining_date: '2023-07-01', phone: '+91 10987 65432', location: 'Bangalore', salary: 118000 },
  { id: 10, employee_id: 'BW-010', name: 'Divya Krishnan', email: 'divya.krishnan@bridgeworks.in', department: 'Design', designation: 'UI/UX Designer', status: 'Active', joining_date: '2022-10-12', phone: '+91 99876 54321', location: 'Chennai', salary: 102000 },
];

const PAYROLL_RUNS = EMPLOYEES.map((emp) => ({
  id: emp.id,
  employee_id: emp.employee_id,
  employee_name: emp.name,
  department: emp.department,
  designation: emp.designation,
  basic_salary: emp.salary * 0.5,
  hra: emp.salary * 0.2,
  special_allowance: emp.salary * 0.3,
  gross_salary: emp.salary,
  pf_deduction: emp.salary * 0.12,
  esi_deduction: emp.salary * 0.0175,
  tds_deduction: emp.salary * 0.05,
  other_deductions: 0,
  net_salary: emp.salary * (1 - 0.12 - 0.0175 - 0.05),
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
  check_in: '09:' + String(Math.floor(Math.random() * 20 + 1)).padStart(2, '0') + ' AM',
  check_out: '06:' + String(Math.floor(Math.random() * 30 + 1)).padStart(2, '0') + ' PM',
  status: emp.status === 'On Leave' ? 'Absent' : 'Present',
  working_hours: 8 + (Math.random() * 2).toFixed(1),
  location: emp.location,
}));

// ─── My Desk Notes ────────────────────────────────────────────────────────────
const NOTES = [
  { id: 1, title: 'Q3 Revenue Strategy', content: 'Focus on upselling SaaS subscriptions to existing enterprise clients. Target 20% MoM growth in ARR.', tags: ['strategy', 'revenue'], created_at: daysAgo(1), updated_at: daysAgo(1), is_pinned: true },
  { id: 2, title: 'Board Meeting Notes — July 28', content: 'Key takeaways: expand to Tier-2 cities, hire 5 more backend engineers Q4, close Series A by December.', tags: ['meeting', 'board'], created_at: daysAgo(5), updated_at: daysAgo(4), is_pinned: true },
  { id: 3, title: 'AWS Cost Optimisation Ideas', content: 'Reserved instances for prod EC2, move dev to spot instances, enable S3 intelligent tiering.', tags: ['tech', 'infra'], created_at: daysAgo(7), updated_at: daysAgo(7), is_pinned: false },
  { id: 4, title: 'New Client Onboarding Checklist', content: '1. Send welcome kit 2. Schedule kickoff call 3. Share API docs 4. Assign CSM 5. First review in 30 days', tags: ['process', 'clients'], created_at: daysAgo(10), updated_at: daysAgo(9), is_pinned: false },
  { id: 5, title: 'Hiring Plan — Q4 2026', content: 'Engineering: 5 Backend, 2 Frontend, 1 DevOps. Sales: 3 BDMs. Design: 1 UX Lead.', tags: ['hr', 'hiring'], created_at: daysAgo(14), updated_at: daysAgo(12), is_pinned: false },
];

// ─── Kanban Tasks ─────────────────────────────────────────────────────────────
const KANBAN_TASKS = [
  { id: 1, title: 'Migrate auth to JWT', description: 'Replace session-based auth with JWT tokens across all API endpoints', status: 'todo', priority: 'high', assignee: 'Arjun Sharma', due_date: daysAgo(-7), tags: ['backend', 'security'] },
  { id: 2, title: 'Design new dashboard layout', description: 'Redesign the Finance Control Tower with better chart hierarchy', status: 'in_progress', priority: 'medium', assignee: 'Divya Krishnan', due_date: daysAgo(-3), tags: ['design', 'frontend'] },
  { id: 3, title: 'GST GSTR-3B report fix', description: 'Fix ITC calculation mismatch in GSTR-3B monthly summary', status: 'in_progress', priority: 'high', assignee: 'Rohit Verma', due_date: daysAgo(-2), tags: ['accounting', 'gst'] },
  { id: 4, title: 'Employee onboarding flow', description: 'Build new digital onboarding journey for new hires', status: 'todo', priority: 'medium', assignee: 'Sneha Iyer', due_date: daysAgo(-10), tags: ['hr', 'ux'] },
  { id: 5, title: 'Deploy to production', description: 'Final production deployment with Nginx + Daphne + SSL setup', status: 'done', priority: 'critical', assignee: 'Rahul Gupta', due_date: daysAgo(2), tags: ['devops', 'infra'] },
  { id: 6, title: 'Close MediCare deal', description: 'Follow up with MediCare Hospitals procurement team for PO', status: 'done', priority: 'high', assignee: 'Priya Patel', due_date: daysAgo(4), tags: ['sales', 'crm'] },
  { id: 7, title: 'Monthly payroll run', description: 'Process July 2026 payroll for all 10 employees', status: 'done', priority: 'high', assignee: 'Sneha Iyer', due_date: daysAgo(3), tags: ['hr', 'payroll'] },
  { id: 8, title: 'Set up performance review cycle', description: 'Configure bi-annual review workflows in HR module', status: 'todo', priority: 'low', assignee: 'Sneha Iyer', due_date: daysAgo(-20), tags: ['hr'] },
];

// ─── Expenses (Pending) ───────────────────────────────────────────────────────
const PENDING_EXPENSES = [
  { id: 1, employee: 'Karan Mehta', category: 'Travel', description: 'Delhi client visit — flight + hotel', amount: 28500, date: daysAgo(3), status: 'Pending', receipt: true },
  { id: 2, employee: 'Vikram Singh', category: 'Team Lunch', description: 'Quarterly team lunch — Bangalore', amount: 8750, date: daysAgo(5), status: 'Pending', receipt: true },
  { id: 3, employee: 'Priya Patel', category: 'Conference', description: 'SaaSBoomi Annual Summit — Mumbai', amount: 15000, date: daysAgo(7), status: 'Approved', receipt: true },
  { id: 4, employee: 'Arjun Sharma', category: 'Software', description: 'Personal GitHub Copilot subscription', amount: 1700, date: daysAgo(9), status: 'Rejected', receipt: false },
  { id: 5, employee: 'Ananya Nair', category: 'Equipment', description: 'USB-C hub for WFH setup', amount: 4200, date: daysAgo(11), status: 'Pending', receipt: true },
];

// ─── Assets ───────────────────────────────────────────────────────────────────
const ASSETS = [
  { id: 1, name: 'MacBook Pro 14" M3', category: 'IT Equipment', purchase_date: '2024-01-15', cost: 185000, current_value: 148000, depreciation_rate: 20, assigned_to: 'Arjun Sharma', status: 'In Use', location: 'Bangalore HQ' },
  { id: 2, name: 'Dell 27" 4K Monitor', category: 'IT Equipment', purchase_date: '2024-02-10', cost: 45000, current_value: 36000, depreciation_rate: 20, assigned_to: 'Divya Krishnan', status: 'In Use', location: 'Chennai Office' },
  { id: 3, name: 'Office Furniture — Workstation Set', category: 'Furniture', purchase_date: '2023-06-01', cost: 125000, current_value: 93750, depreciation_rate: 10, assigned_to: null, status: 'Available', location: 'Bangalore HQ' },
  { id: 4, name: 'Cisco IP Phone (10x)', category: 'IT Equipment', purchase_date: '2022-09-15', cost: 85000, current_value: 51000, depreciation_rate: 20, assigned_to: null, status: 'In Use', location: 'All Offices' },
  { id: 5, name: 'Canon DSLR Camera Kit', category: 'Equipment', purchase_date: '2023-03-20', cost: 78000, current_value: 62400, depreciation_rate: 10, assigned_to: 'Karan Mehta', status: 'In Use', location: 'Mumbai Office' },
];

// ─── Hiring ───────────────────────────────────────────────────────────────────
const JOB_POSTINGS = [
  { id: 1, title: 'Senior Backend Developer', department: 'Engineering', location: 'Bangalore', type: 'Full-time', status: 'Active', applicants: 47, posted_date: daysAgo(14), experience: '4-6 years', skills: ['Python', 'Django', 'PostgreSQL'] },
  { id: 2, title: 'UI/UX Designer', department: 'Design', location: 'Remote', type: 'Full-time', status: 'Active', applicants: 31, posted_date: daysAgo(10), experience: '3-5 years', skills: ['Figma', 'React', 'Design Systems'] },
  { id: 3, title: 'Sales Business Development Manager', department: 'Sales', location: 'Mumbai', type: 'Full-time', status: 'Active', applicants: 58, posted_date: daysAgo(21), experience: '5-8 years', skills: ['B2B Sales', 'CRM', 'Enterprise'] },
  { id: 4, title: 'DevOps Engineer', department: 'Engineering', location: 'Bangalore', type: 'Full-time', status: 'Closed', applicants: 23, posted_date: daysAgo(45), experience: '3-5 years', skills: ['AWS', 'Docker', 'Kubernetes'] },
];

// ─── Chat Messages ────────────────────────────────────────────────────────────
const CHAT_MESSAGES = [
  { id: 1, sender: 'Sneha Iyer', message: 'Hey team! July payroll has been processed. Payslips sent to everyone 🎉', channel: 'general', timestamp: daysAgo(1) + ' 10:32 AM', avatar: 'SI' },
  { id: 2, sender: 'Rohit Verma', message: 'GST returns for July are almost ready. Just waiting on 2 vendor invoices', channel: 'finance', timestamp: daysAgo(1) + ' 11:15 AM', avatar: 'RV' },
  { id: 3, sender: 'Arjun Sharma', message: 'v2.4 hotfix deployed to production. All systems green ✅', channel: 'general', timestamp: daysAgo(1) + ' 02:48 PM', avatar: 'AS' },
  { id: 4, sender: 'Priya Patel', message: 'Closed the MediCare deal! ₹3.2L annual contract signed 🚀', channel: 'general', timestamp: daysAgo(2) + ' 04:20 PM', avatar: 'PP' },
  { id: 5, sender: 'Karan Mehta', message: 'July marketing report is ready. Overall CTR improved by 18% vs last month', channel: 'general', timestamp: daysAgo(3) + ' 09:10 AM', avatar: 'KM' },
];

// ─── Activity Logs ────────────────────────────────────────────────────────────
const ACTIVITY_LOGS = [
  { id: 1, action: 'Invoice created', user: 'Priya Patel', module: 'Finance', details: 'INV-2405 for ₹5,10,000 — InfraBuilders Co', timestamp: daysAgo(0) + ' 11:42 AM' },
  { id: 2, action: 'Payroll processed', user: 'Sneha Iyer', module: 'HR', details: 'July 2026 payroll — ₹9,80,000 disbursed', timestamp: daysAgo(1) + ' 10:00 AM' },
  { id: 3, action: 'Journal entry posted', user: 'Rohit Verma', module: 'Finance', details: 'JV-2603 — Depreciation ₹18,750', timestamp: daysAgo(2) + ' 03:15 PM' },
  { id: 4, action: 'Employee record updated', user: 'Sneha Iyer', module: 'HR', details: 'Meera Joshi — marked On Leave', timestamp: daysAgo(3) + ' 09:30 AM' },
  { id: 5, action: 'GST return filed', user: 'Rohit Verma', module: 'GST', details: 'GSTR-1 for July 2026 filed successfully', timestamp: daysAgo(4) + ' 04:00 PM' },
];

// ─── Notifications ────────────────────────────────────────────────────────────
const NOTIFICATIONS = [
  { id: 1, title: 'GSTR-3B Due Soon', message: 'GSTR-3B for July 2026 is due in 5 days. ₹4,56,144 payable.', type: 'warning', read: false, created_at: daysAgo(0) },
  { id: 2, title: 'Payroll Processed', message: 'July 2026 payroll completed. ₹9,80,000 disbursed to 10 employees.', type: 'success', read: false, created_at: daysAgo(1) },
  { id: 3, title: 'Expense Pending Approval', message: '2 expense claims are pending your approval.', type: 'info', read: true, created_at: daysAgo(2) },
  { id: 4, title: 'New Job Application', message: '12 new applications received for Senior Backend Developer role.', type: 'info', read: true, created_at: daysAgo(3) },
];

// ─── Diary Entries ────────────────────────────────────────────────────────────
const DIARY_ENTRIES = [
  { id: 1, date: daysAgo(0), content: 'Focused on closing the MediCare renewal. Had a productive call with their CTO. Positive signals.', mood: 'good' },
  { id: 2, date: daysAgo(1), content: 'Reviewed the Q3 financial projections with Rohit. Revenue outlook looks strong — on track for 28% growth.', mood: 'great' },
  { id: 3, date: daysAgo(2), content: 'Had the all-hands meeting. Team morale is high after the successful Series A close announcement.', mood: 'great' },
  { id: 4, date: daysAgo(5), content: 'Long day reviewing the payroll discrepancy. Found and fixed the TDS calculation bug in the system.', mood: 'neutral' },
];

// ─── URL Routing Map ──────────────────────────────────────────────────────────
/**
 * Maps URL path patterns to mock response data.
 * Supports string prefix matching and regex patterns.
 */
export const MOCK_ROUTES = [
  // ── Finance / Transactions ───────────────────────────────────────────────
  { pattern: /\/api\/accounting\/transactions/, data: () => FINANCE_TRANSACTIONS },
  { pattern: /\/api\/accounting\/journals/, data: () => ({ results: JOURNAL_ENTRIES, count: JOURNAL_ENTRIES.length }) },
  { pattern: /\/api\/accounting\/trial-balance/, data: () => TRIAL_BALANCE },
  { pattern: /\/api\/accounting\/profit-loss/, data: () => PROFIT_LOSS },
  { pattern: /\/api\/accounting\/balance-sheet/, data: () => BALANCE_SHEET },
  { pattern: /\/api\/accounting\/dashboard/, data: () => ({
    total_revenue: 6405200,
    total_expenses: 4790500,
    net_profit: 1614700,
    cash_balance: 2850000,
    accounts_receivable: 1245000,
    accounts_payable: 685000,
    monthly_trend: [
      { month: 'Feb', revenue: 4800000, expenses: 3600000 },
      { month: 'Mar', revenue: 5200000, expenses: 3900000 },
      { month: 'Apr', revenue: 5500000, expenses: 4100000 },
      { month: 'May', revenue: 5900000, expenses: 4400000 },
      { month: 'Jun', revenue: 6100000, expenses: 4600000 },
      { month: 'Jul', revenue: 6405200, expenses: 4790500 },
    ],
    recent_transactions: FINANCE_TRANSACTIONS.slice(0, 5),
  }) },
  { pattern: /\/api\/accounting\/invoices/, data: () => ({ results: FINANCE_TRANSACTIONS.filter(t => t.type === 'credit'), count: 9 }) },
  { pattern: /\/api\/accounting\/expenses/, data: () => PENDING_EXPENSES },
  { pattern: /\/api\/accounting\/assets/, data: () => ({ results: ASSETS, count: ASSETS.length }) },
  { pattern: /\/api\/accounting\/payroll/, data: () => ({ results: PAYROLL_RUNS, count: PAYROLL_RUNS.length, total_gross: 980000, total_net: 822500 }) },
  { pattern: /\/api\/accounting\/pending-expenses/, data: () => PENDING_EXPENSES },
  { pattern: /\/api\/accounting\/department/, data: () => ({
    departments: [
      { name: 'Engineering', headcount: 3, budget: 4500000, spent: 3800000 },
      { name: 'Sales', headcount: 2, budget: 2500000, spent: 2100000 },
      { name: 'HR', headcount: 1, budget: 1500000, spent: 1200000 },
      { name: 'Marketing', headcount: 1, budget: 1800000, spent: 1550000 },
      { name: 'Finance', headcount: 1, budget: 1200000, spent: 980000 },
      { name: 'Operations', headcount: 1, budget: 2000000, spent: 1680000 },
    ],
  }) },
  { pattern: /\/api\/accounting\/reconciliation/, data: () => ({
    matched: 47,
    unmatched: 8,
    total: 55,
    bank_balance: 2850000,
    book_balance: 2835000,
    difference: 15000,
    auto_match_rate: 94,
    review_queue_count: 8,
    avg_confidence: 87,
    unmatched_count: 8,
    high_risk_count: 1,
    duplicate_count: 2,
  }) },

  { pattern: /\/api\/accounting\/ledger-summary/, data: () => ({
    accounts: [
      { account_name: 'Cash & Bank', debit_total: 5820000, credit_total: 2970000, balance: 2850000 },
      { account_name: 'Accounts Receivable', debit_total: 1245000, credit_total: 0, balance: 1245000 },
      { account_name: 'Revenue - Software', debit_total: 0, credit_total: 4250000, balance: 4250000 },
      { account_name: 'Salaries Expense', debit_total: 2940000, credit_total: 0, balance: 2940000 },
      { account_name: 'Rent Expense', debit_total: 750000, credit_total: 0, balance: 750000 },
    ],
  }) },

  // ── Finance Control Tower (main dashboard) ───────────────────────────────
  { pattern: /\/api\/finance\/control-tower/, data: () => ({
    cashPosition: 2850000,
    receivables: 1245000,
    payables: 685000,
    gstLiability: 456144,
    gstDueDays: 5,
    payrollPending: false,
    payrollTotal: 980000,
    eolAssets: 1,
    expensesGrowth: 4.2,
    incomeGrowth: 8.7,
    netWorth: 5459500,
    monthlyBurn: 798417,
    reconciliationAccuracy: 94,
    pendingMatches: 8,
    connectedAccounts: 3,
    dailyInflow: 213507,
    dailyOutflow: 159683,
    totalAssets: 9095000,
    assetHealth: 92,
    revenue: 6405200,
    profit: 1614700,
    forecastAccuracy: 100,
    decisions: [
      { id: 1, title: 'Approve Q4 Engineering Hiring Budget', amount: 4500000, priority: 'High', status: 'Pending' },
      { id: 2, title: 'Renew AWS Reserved Instance Contract', amount: 228000, priority: 'Medium', status: 'Pending' },
    ],
    actions: [
      { id: 1, text: 'File GSTR-3B before August 20', type: 'Compliance', priority: 'Critical', time: '5 days' },
      { id: 2, text: 'Approve 2 pending expense claims', type: 'Finance', priority: 'Medium', time: 'Today' },
      { id: 3, text: 'Review 8 unmatched bank transactions', type: 'Banking', priority: 'High', time: 'This week' },
    ],
    timelineGroups: {
      TODAY: [
        { id: 1, text: 'Invoice INV-2405 created — ₹5,10,000', type: 'Finance', time: '11:42 AM' },
        { id: 2, text: 'GST dashboard refreshed', type: 'Compliance', time: '10:05 AM' },
      ],
      YESTERDAY: [
        { id: 3, text: 'July payroll processed — ₹9,80,000', type: 'Finance', time: '10:00 AM' },
        { id: 4, text: 'Bank statement imported — HDFC Current', type: 'Banking', time: '09:30 AM' },
      ],
      'PAST WEEK': [
        { id: 5, text: 'GSTR-1 filed for July 2026', type: 'Compliance', time: 'Mon 4:00 PM' },
        { id: 6, text: 'Trial balance verified', type: 'Finance', time: 'Mon 2:15 PM' },
      ],
    },
    infraSystems: [
      { name: 'Banking & Reconciliation', health: 94, risk: 'Low', alerts: 0 },
      { name: 'GST Compliance Engine', health: 87, risk: 'Medium', alerts: 1 },
      { name: 'Payroll Processing', health: 100, risk: 'Low', alerts: 0 },
      { name: 'Asset Management', health: 82, risk: 'Medium', alerts: 1 },
      { name: 'Journal & Ledger', health: 98, risk: 'Low', alerts: 0 },
    ],
    accounts: [
      { id: 1, name: 'HDFC Current Account', bank: 'HDFC Bank', balance: 1850000, last_sync: 'Just now' },
      { id: 2, name: 'ICICI Savings Account', bank: 'ICICI Bank', balance: 720000, last_sync: '15 min ago' },
      { id: 3, name: 'SBI Business Account', bank: 'State Bank of India', balance: 280000, last_sync: '30 min ago' },
    ],
  }) },

  { pattern: /\/api\/finance\/executive-report/, data: () => ({
    report: `# CFO Executive Report — ${new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}\n\n## Financial Summary\n\n**Revenue:** ₹64,05,200 | **Expenses:** ₹47,90,500 | **Net Profit:** ₹16,14,700 (25.2% margin)\n\n## Key Highlights\n- Revenue grew **8.7% MoM** driven by enterprise software licences\n- Salaries remain the largest cost at ₹29,40,000 (61.4% of expenses)\n- Cash position healthy at ₹28,50,000 with **3.6 months runway**\n- GSTR-3B due in 5 days — ₹4,56,144 payable\n\n## Recommendations\n1. Accelerate receivables collection — ₹12,45,000 outstanding\n2. Review AWS costs — potential 20% reduction via reserved instances\n3. Hire 5 engineers in Q4 to support product roadmap`,
  }) },

  { pattern: /\/api\/finance\/financial-plan/, data: () => ({
    plan: `# 90-Day Financial Plan\n\n## Month 1 (August 2026)\n- **Target Revenue:** ₹70,00,000\n- File GSTR-3B by Aug 20\n- Close 2 pending enterprise deals\n\n## Month 2 (September 2026)\n- **Target Revenue:** ₹75,00,000\n- Begin Q4 engineering hiring\n- AWS reserved instance contract renewal\n\n## Month 3 (October 2026)\n- **Target Revenue:** ₹82,00,000\n- Series A deployment planning\n- Tier-2 city market expansion begins`,
  }) },

  { pattern: /\/api\/finance\/ai-chat/, data: () => ({
    reply: 'This is a demo mode response. Connect the backend API to enable live AI-powered financial analysis.',
  }) },

  // ── GST ─────────────────────────────────────────────────────────────────
  { pattern: /\/api\/accounting\/gst\/dashboard/, data: () => GST_DASHBOARD },
  { pattern: /\/api\/accounting\/gst\/summary/, data: () => GST_DASHBOARD },
  { pattern: /\/api\/accounting\/gst\/itc-reconciliation/, data: () => ({
    itc_claimed: 312480,
    itc_available: 312480,
    itc_utilized: 280000,
    itc_balance: 32480,
    mismatches: 2,
  }) },
  { pattern: /\/api\/accounting\/gst/, data: () => ({ results: GST_TRANSACTIONS, count: GST_TRANSACTIONS.length }) },

  // ── HR / Employees ───────────────────────────────────────────────────────
  { pattern: /\/api\/hr\/employees/, data: () => ({ results: EMPLOYEES, count: EMPLOYEES.length }) },
  { pattern: /\/api\/employees/, data: () => ({ results: EMPLOYEES, count: EMPLOYEES.length }) },
  { pattern: /\/api\/hr\/attendance/, data: () => ({ results: ATTENDANCE, count: ATTENDANCE.length }) },
  { pattern: /\/api\/hr\/payroll/, data: () => ({ results: PAYROLL_RUNS, count: PAYROLL_RUNS.length }) },
  { pattern: /\/api\/hr\/hiring/, data: () => ({ results: JOB_POSTINGS, count: JOB_POSTINGS.length }) },
  { pattern: /\/api\/hiring/, data: () => ({ results: JOB_POSTINGS, count: JOB_POSTINGS.length }) },
  { pattern: /\/api\/hr\/departments/, data: () => ({
    results: [
      { id: 1, name: 'Engineering', head: 'Arjun Sharma', headcount: 3 },
      { id: 2, name: 'Sales', head: 'Priya Patel', headcount: 2 },
      { id: 3, name: 'HR', head: 'Sneha Iyer', headcount: 1 },
      { id: 4, name: 'Marketing', head: 'Karan Mehta', headcount: 1 },
      { id: 5, name: 'Finance', head: 'Rohit Verma', headcount: 1 },
      { id: 6, name: 'Operations', head: 'Vikram Singh', headcount: 1 },
      { id: 7, name: 'Design', head: 'Divya Krishnan', headcount: 1 },
    ],
  }) },

  // ── Workforce (MasterWorkforceSheet uses these directly) ─────────────────
  { pattern: /\/api\/workforce\/departments/, data: () => [
    { id: 1, name: 'Engineering' },
    { id: 2, name: 'Sales' },
    { id: 3, name: 'HR' },
    { id: 4, name: 'Marketing' },
    { id: 5, name: 'Finance' },
    { id: 6, name: 'Operations' },
    { id: 7, name: 'Design' },
  ] },
  { pattern: /\/api\/workforce\/members/, data: () => EMPLOYEES.map(emp => ({
    ...emp,
    full_name: emp.name,
    role: emp.designation,
    working_style: emp.id % 2 === 0 ? 'Remote' : 'Office',
    gender: emp.id % 3 === 0 ? 'Female' : 'Male',
    category: 'Full-time',
    archived: false,
  })) },
  { pattern: /\/api\/workforce\/documents/, data: () => [] },

  // ── Team (used alongside workforce) ──────────────────────────────────────
  { pattern: /\/api\/team\/members/, data: () => EMPLOYEES.map(emp => ({
    id: emp.id,
    full_name: emp.name,
    username: emp.name.toLowerCase().replace(' ', '.'),
    email: emp.email,
    department: emp.department,
    role: emp.designation,
    status: emp.status,
    working_style: emp.id % 2 === 0 ? 'Remote' : 'Office',
    gender: emp.id % 3 === 0 ? 'Female' : 'Male',
    category: 'Full-time',
    phone: emp.phone,
    location: emp.location,
    joining_date: emp.joining_date,
    archived: false,
  })) },

  // ── Auth / Current User / Permissions ────────────────────────────────────
  { pattern: /\/api\/current-user/, data: () => ({
    id: 1,
    full_name: 'Jatin Choudhary',
    username: 'admin',
    email: 'admin@local.dev',
    is_staff: true,
    is_superuser: true,
    department: 'Engineering',
    role: 'Administrator',
    organisation: { id: 1, name: 'BridgeWorks Demo Org', gstin: '29AABCB1234C1ZV' },
  }) },
  { pattern: /\/api\/permissions\/schema/, data: () => ({
    modules: ['finance', 'hr', 'mydesk', 'reports', 'settings'],
    actions: ['view', 'create', 'edit', 'delete', 'approve'],
    roles: ['Admin', 'Manager', 'Staff', 'Viewer'],
  }) },
  { pattern: /\/api\/team\/permissions/, data: () => ({
    permissions: { finance: ['view', 'edit'], hr: ['view', 'edit'], mydesk: ['view', 'edit', 'create'] },
  }) },
  { pattern: /\/api\/workforce\/permissions/, data: () => ({
    permissions: { finance: ['view', 'edit'], hr: ['view', 'edit'], mydesk: ['view', 'edit', 'create'] },
  }) },

  // ── My Desk ──────────────────────────────────────────────────────────────
  { pattern: /\/api\/mydesk\/notes/, data: () => NOTES },
  { pattern: /\/api\/mydesk\/tasks/, data: () => KANBAN_TASKS },
  { pattern: /\/api\/mydesk\/diary/, data: () => DIARY_ENTRIES },
  { pattern: /\/api\/mydesk\/expenses/, data: () => PENDING_EXPENSES },
  { pattern: /\/api\/mydesk\/chat/, data: () => CHAT_MESSAGES },
  { pattern: /\/api\/mydesk\/profile/, data: () => ({
    id: 1,
    name: 'Jatin Choudhary',
    email: 'admin@local.dev',
    role: 'Administrator',
    department: 'Engineering',
    avatar: null,
    phone: '+91 98765 00001',
    location: 'Bangalore',
  }) },

  // ── Notifications & Activity ─────────────────────────────────────────────
  { pattern: /\/api\/notifications/, data: () => NOTIFICATIONS },
  { pattern: /\/api\/activity/, data: () => ACTIVITY_LOGS },

  // ── Auth / User ──────────────────────────────────────────────────────────
  { pattern: /\/api\/auth\/user/, data: () => ({
    id: 1,
    email: 'admin@local.dev',
    name: 'Jatin Choudhary',
    is_staff: true,
    organisation: { id: 1, name: 'BridgeWorks Demo Org', gstin: '29AABCB1234C1ZV' },
    permissions: ['finance.view', 'hr.view', 'mydesk.view', 'finance.edit', 'hr.edit'],
  }) },
  { pattern: /\/api\/auth\/login/, data: () => ({
    token: 'demo-token-bridgeworks-2026',
    user: { id: 1, email: 'admin@local.dev', name: 'Jatin Choudhary', is_staff: true },
  }) },
  { pattern: /\/accounts\/profile/, data: () => ({
    id: 1, email: 'admin@local.dev', name: 'Jatin Choudhary', is_staff: true,
    organisation: { id: 1, name: 'BridgeWorks Demo Org' },
  }) },

  // ── Catch-all: return empty success ─────────────────────────────────────
  { pattern: /.*/, data: () => ({ results: [], count: 0, detail: 'Demo mode — mock data served' }) },
];

/**
 * Finds and returns the mock data for a given URL.
 * @param {string} url - The request URL
 * @returns {any} Mock response data
 */
export function getMockData(url) {
  const path = url.replace(/^https?:\/\/[^/]+/, ''); // strip host
  for (const route of MOCK_ROUTES) {
    if (route.pattern.test(path)) {
      return route.data();
    }
  }
  return { results: [], count: 0 };
}
