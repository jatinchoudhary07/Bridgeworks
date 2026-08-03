# Unify Finance Module: The Master Technical Blueprint

This document represents the deepest, most exhaustive technical breakdown of the Unify Finance Module. It is designed for senior engineers, architects, and product managers to understand exactly how the frontend tabs map to the backend Django code, how the database schemas interlock, the mathematical aggregation flows for financial statements, and a brutally honest assessment of the current code bugs and architectural debt.

---

## 1. Architectural Philosophy & Overview

The Finance Module in Unify is designed as the central hub where all monetary data eventually settles. It operates on a hybrid model:
1. **Direct Entry (Journal Entries)**: Users manually input Income or Expenses.
2. **Automated Sub-ledgers**: Other modules (HR/MyDesk, Logistics/Returns, Inventory) calculate financial impact and "push" them into Finance.

Instead of a strict Double-Entry Accounting system (where every transaction requires balancing Debits and Credits upon creation), Unify currently uses a **Categorized Single-Entry System**. Debits and Credits are derived retroactively based on the `entry_type` (`income` = Credit, `expense` = Debit) during report generation.

---

## 2. Database Schemas & Models (Deep Dive)

The Finance module is built on top of a few core database models residing in `core/models/finance.py` and `core/models/mydesk.py`.

### A. `FinanceTransaction`
The absolute core of the General Ledger. Every posted transaction lives here.
*   **`entry_type`**: `CharField` (choices: `income`, `expense`). This is the most critical field, as it dictates whether the amount is treated as a Credit or Debit.
*   **`amount`**: `DecimalField(max_digits=12, decimal_places=2)`. *Note: While stored as Decimal in DB, the backend views frequently cast this to `float()` during aggregations, which is a known bug (see Section 6).*
*   **`category` & `department` & `nature` & `payment_type`**: `CharField` (max_length=120). These are free-text strings used for grouping in the P&L and Ledger. 
*   **`reference_id` & `invoice_no`**: Used for search and auditing. Indexed for fast lookup.
*   **`status`**: Currently defaults to 'Draft', but usually effectively acts as 'Posted' when viewed in the ledger.

### B. `FinanceOption`
This model powers the dropdown menus in the UI for categorizing transactions.
*   **`option_type`**: Determines what dropdown this belongs to (e.g., `department`, `category`, `payment_type`).
*   **`value`**: The actual string value (e.g., "Marketing").
*   **Constraint**: Unique per `org_id`, `option_type`, `value`, and `parent_value`.

### C. `ExpenseEntry` (Originates in MyDesk/HR)
This model handles the complex approval workflows for employee/department expenses before they reach the general ledger.
*   **`status`**: Ranges from `Draft` -> `Submitted` -> `Dept Head Approved` -> `Partially Approved` -> `Finance Reviewed` -> `Paid` -> `Rejected`.
*   **`amount` vs `approved_amount`**: The employee asks for `amount`. The manager can override it via `approved_amount`. The backend dynamically calculates the "effective amount" using `expense.approved_amount if expense.approved_amount is not None else expense.amount`.
*   **`workflow_steps`**: A `JSONField` storing a list of every action taken on the expense (Who, When, Action, Notes).

### D. `PayrollPaymentRecord` (Originates in HR)
When payroll is processed, the resulting salaries must hit the finance ledger.
*   Contains `gross_amount`, `total_deductions`, `net_amount`.
*   **`finance_verified`**: A boolean flag marking if the Finance team has cleared the payroll run for disbursement.

---

## 3. Core APIs & Request Lifecycle

### The `FinanceBaseAPIView` & `apply_filters()`
Almost all Finance lists inherit from `FinanceBaseAPIView`. This base class enforces security (`IsAuthenticated`, `HasModulePermission`) and handles multi-tenant data isolation via `org_id`.

**The Filtering Engine (`apply_filters`)**:
When the frontend sends a `GET` request to `/api/finance/income/`, the `apply_filters` method parses the query string:
1.  **Search**: It searches `reference_id`, `particular`, and `invoice_no` using `__icontains`.
2.  **Exact Matches**: `category`, `department`, `nature`, `payment_type`, `status`. (If value is 'all', it bypasses the filter).
3.  **Date Bounds**: `from_date` (`entry_date__gte`) and `to_date` (`entry_date__lte`).

---

## 4. UI Tabs: Code Mappings & Sub-Ledger Logic

Here is an exact mapping of what happens when a user navigates the tabs in the Frontend UI:

### 4.1 Dashboard / Income / Expenses (Journal Entries)
*   **Views**: `FinanceIncomeListCreateView`, `FinanceExpenseListCreateView`.
*   **Logic**: Simple CRUD. Creating an entry posts directly to `FinanceTransaction`. 
*   **Backend Hook**: The `entry_type` is hardcoded in the View (`entry_type = 'income'`), so users cannot accidentally submit an Expense via the Income endpoint.

### 4.2 Pending Expenses / Dept Expenses
*   **Views**: `FinancePendingExpenseListView`, `FinancePendingExpenseMemberDetailView`.
*   **Visibility Threshold**: An expense is entirely invisible to the Finance module until its status moves past `Submitted`. Only statuses in `_FIN_UNPAID_STATUSES` (`Dept Head Approved`, `Partially Approved`, `Finance Reviewed`) appear as actionable items.
*   **Grouping Logic**: The backend fetches all valid expenses and manually constructs a dictionary `member_rows = {}` grouped by `user_id`. It calculates `unpaid_amount`, `paid_amount`, and `rejected_amount` dynamically in Python memory.

### 4.3 Settlements (Returns Engine)
*   **View Location**: `core/views_returns_engine.py` -> `_calculate_exchange_settlement(case)`
*   **Logic Flow**: When an order is exchanged, the system checks the original order line items against the replacement items. 
    *   If `Difference > 0`: The customer owes money. Settlement type = `payment_link`.
    *   If `Difference < 0`: The company owes the customer. Settlement type = `refund`.
    *   These settlements eventually map to Finance `Income` or `Expense` records to balance the COGS and revenue loss.

### 4.4 Payroll
*   **View Location**: `core/views_mydesk.py` -> `FinancePayrollLedgerView`
*   **Logic Flow**: Provides a read-only view for the Finance team to see approved payroll runs. Once Finance marks `finance_verified = True` on a `PayrollPaymentRecord`, they execute the bank transfer. This total outflow is then recorded as a massive single Expense transaction in `FinanceTransaction` categorized as "Payroll".

---

## 5. Financial Statements & Aggregation Math

The reporting views (`Ledger Summary`, `Trial Balance`, `Profit & Loss`, `Balance Sheet`) are read-only endpoints that run heavy aggregations on `FinanceTransaction`.

### The Aggregation Query
Every report starts with this exact Django ORM QuerySet aggregation:
```python
summary = (
    queryset
    .values('category', 'entry_type')
    .annotate(total_amount=Sum('amount'))
    .order_by('category', 'entry_type')
)
```
This offloads the heavy lifting to the PostgreSQL database, returning a list of dictionaries like:
`[{'category': 'Marketing', 'entry_type': 'expense', 'total_amount': Decimal('5000.00')}, ...]`

### 5.1 Ledger Summary & Trial Balance
*   **Mapping**: It loops over the `summary`. 
*   If `entry_type == 'expense'`, `debit_value = total_amount`.
*   If `entry_type == 'income'`, `credit_value = total_amount`.
*   **Balancing**: The Trial Balance verifies arithmetic integrity by checking `is_balanced = round(total_debit, 2) == round(total_credit, 2)`.

### 5.2 Profit & Loss (P&L)
*   **Mapping**: Pushes `income` rows to an `income` array, and `expense` rows to an `expenses` array.
*   **Math**: `profit = round(total_income - total_expense, 2)`.

### 5.3 Balance Sheet
*   **Mapping**: Strips away categories completely: `totals = queryset.values('entry_type').annotate(total_amount=Sum('amount'))`.
*   **Math**: Calculates Net Equity (`total_income - total_expense`).
*   **The Cheat**: It forces `total_assets = equity` and `total_liabilities = 0` to create a perfectly balanced sheet.

---

## 6. Known Code Bugs & Architectural Debt (CRITICAL)

This section outlines the immediate dangers and logical flaws currently residing in the codebase.

### 🚨 Bug 1: The Missing Date Filters (Severity: Critical)
**The Flaw**: `FinanceLedgerSummaryView`, `FinanceTrialBalanceView`, `FinanceProfitLossView`, and `FinanceBalanceSheetView` bypass `self.apply_filters()`. They execute `FinanceTransaction.objects.all()`.
**The Impact**: When a user clicks the UI filter for "This Month" or "Last 30 Days", the UI sends `?from_date=X&to_date=Y`. The backend completely ignores these query parameters and returns the **all-time financial history** of the company. 
**The Fix Required**: Inject the date parsing logic into the `get()` methods of these four views:
```python
from_date = request.query_params.get('from_date')
if from_date: queryset = queryset.filter(entry_date__gte=from_date)
# (and similarly for to_date)
```

### 🚨 Bug 2: The Pending Expense Memory Leak (Severity: High)
**The Flaw**: In `FinancePendingExpenseListView`, the backend does not use Database-level aggregation. It fetches every single non-draft expense object into a Python list:
```python
qs = ExpenseEntry.objects.exclude(status__in=['Draft', 'Submitted'])
for item in qs:
    # 50 lines of Python math and string manipulation per row
```
**The Impact**: O(N) memory complexity and serialization time. For an organization with 20,000 historical expenses, the server will load thousands of objects into RAM, loop them, and likely timeout or crash the worker process.
**The Fix Required**: Rewrite the view to use `.values('user_id', 'user__first_name', 'status').annotate(total=Sum('amount'), count=Count('id'))`.

### 🚨 Bug 3: Float Precision Degradation (Severity: Medium)
**The Flaw**: Financial amounts are stored safely as `DecimalField(max_digits=12, decimal_places=2)` in the Database. However, during the aggregation loops in python, the code explicitly casts them to floats:
```python
amount = float(row.get('total_amount') or 0)
total_income += amount
```
**The Impact**: Floating-point arithmetic in Python cannot accurately represent base-10 decimals (e.g., `0.1 + 0.2 = 0.30000000000000004`). In a ledger processing millions of dollars across thousands of rows, this will result in penny-loss or penny-gain anomalies, throwing off the Trial Balance.
**The Fix Required**: Remove `float()` casting. Import `from decimal import Decimal` and execute all arithmetic using `Decimal` objects.

### 🚨 Bug 4: The Category String Grouping Trap (Severity: Medium)
**The Flaw**: In the P&L and Ledger aggregations, it groups by `category` string. 
```python
category = (row.get('category') or 'Uncategorized').strip() or 'Uncategorized'
```
**The Impact**: The DB `.annotate(Sum('amount'))` groups by exact string matches *before* Python strips whitespace. If the database contains `"Marketing"` and `"Marketing "`, the DB returns two separate rows. The Python code then strips both to `"Marketing"`, resulting in the frontend displaying two identical `"Marketing"` rows in the P&L instead of combining their totals.
**The Fix Required**: Clean the data on insertion (always strip categories when saving `FinanceTransaction`), or aggregate in Python *after* standardizing the strings.

### 🚨 Bug 5: Fragile Workflow Step Parsing (Severity: Low)
**The Flaw**: To check if a rejected expense reached Finance before being rejected, the code parses the JSON workflow:
```python
s = str(step.get('step') or step.get('status') or '').lower()
if s in ['dept head approved', 'partially approved', 'finance reviewed']:
```
**The Impact**: If an HR developer changes the label "Dept Head Approved" to "Department Head Approved" in the MyDesk module, the string match fails. Finance will suddenly stop seeing rejected expenses in their history.
**The Fix Required**: Use strictly defined enums or constant codes (e.g., `DEPT_HEAD_APPROVED = 'step_2'`) rather than relying on human-readable strings.

---

## 7. Refactoring & Future Roadmap

To elevate the Finance Module from a basic income/expense tracker to a true enterprise ERP system, the following architectural shifts are necessary:

1. **Implement Double-Entry Journal Architecture**: Instead of `FinanceTransaction` having an `entry_type`, it should be split into `JournalEntry` (the header) and `JournalEntryLineItem` (the debits and credits). This enforces strict balancing at the database level.
2. **True Chart of Accounts**: The `category` string field must be replaced with a Foreign Key to a `ChartOfAccount` model, which strictly categorizes accounts as `Asset`, `Liability`, `Equity`, `Revenue`, or `Expense`. This will allow the Balance Sheet to automatically populate Assets and Liabilities legitimately, rather than mocking them.
3. **Automated Sub-ledger Posting Engine**: Create a robust signal/celery-task architecture so that when `PayrollPaymentRecord.status` changes to 'Paid', or `ReturnExchangeCase` issues a refund, the system automatically writes the corresponding `JournalEntry` without manual Finance team intervention.
