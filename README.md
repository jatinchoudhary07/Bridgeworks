# 🌐 BridgeWorks Enterprise Platform

### **Built to Connect. Designed to Perform.**

*An all-in-one unified enterprise platform combining Finance & Accounting, HR & Team Operations, and a Personal Desktop Workspace into a single, high-performance web suite.*

---

[Key Features](#-key-features) • [Tech Stack](#-tech-stack) • [Quick Start](#-quick-start--run-commands) • [Modules Overview](#-operational-modules) • [Credits](#-author--credits)

</div>

---

## ✨ Overview

**BridgeWorks** is a modern single-page enterprise web application designed to remove software fragmentation in growing organizations. Instead of managing separate tools for accounting, workforce management, and daily productivity, BridgeWorks unifies everything into **3 core operational modules** connected by a real-time reactive engine.

---

## ⚡ Key Features

* 💎 **Unified 3-Module Architecture**: Seamless instant switching between **Finance**, **HR**, and **My Desk**.
* 🚀 **Zero-Delay SPA Performance**: Pre-bundled static routing with Vite 7 and Material UI v5.
* 🏦 **Double-Entry Financial Engine**: Automated journal entries, general ledger, trial balance, P&L, balance sheet, and bank reconciliation.
* 📑 **GST Compliance Center**: Real-time GSTR-1 & GSTR-3B liability reports, Input Tax Credit (ITC) tracking, and tax diagnostics.
* 👥 **Workforce & Payroll Operations**: Centralized employee directory, geofenced attendance tracking, and monthly automated payroll run with payslip downloads.
* 🗂️ **My Desk Personal Workspace**: Personal notes knowledge base, interactive Kanban task board, workplace team chat, diary logbook, and expense claims.
* ⚡ **1-Command Platform Launcher**: Single terminal launch command running database migrations, data seeding, Django REST backend, and React frontend concurrently.

---

## 🛠️ Tech Stack

| Component | Technologies Used |
|---|---|
| **Frontend SPA** | React 18, Vite 7, Material UI (MUI v5), Recharts, React Router DOM v6 |
| **Backend REST API** | Python 3.13, Django 5.x, Django REST Framework, Daphne (ASGI) |
| **Realtime Engine** | WebSockets, Django Channels |
| **Database** | SQLite (Development) / PostgreSQL (Production) |

---

## 🚀 Quick Start & Run Commands

### Prerequisites
Make sure you have **Node.js (v18+)** and **Python 3.13+** installed on your system.

### One-Command Start (Frontend + Backend + Database)

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jatinchoudhary07/Bridgeworks.git
   cd Bridgeworks
   ```

2. **Run the platform**:
   ```bash
   npm run bridgeworks
   ```

*(This command automatically runs database migrations, seeds demo admin credentials, starts the Django API on port `8000`, and launches the Vite React App on port `5173`.)*

---

### Live Application URLs

* 🟢 **Frontend Web Application**: [`http://localhost:5173`](http://localhost:5173)
* 🟢 **Backend API Service**: [`http://localhost:8000`](http://localhost:8000)

---

## 🏢 Operational Modules

```
                        ┌──────────────────────────────┐
                        │   BridgeWorks Modules Hub    │
                        └──────────────┬───────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
┌───────────────────┐        ┌───────────────────┐        ┌───────────────────┐
│  🏦 FINANCE       │       │    👥 HR & TEAM   │        │  🗂️ MY DESK      │
│     ACCOUNTING    │        │    OPERATIONS     │        │   PERSONAL WORKSPACE│
└───────────────────┘        └───────────────────┘        └───────────────────┘
```

### 1. 🏦 Finance & Accounting
* **General Ledger & Journal**: Full double-entry debit/credit ledger system.
* **Financial Reports**: Instant trial balance, profit & loss statement, and balance sheet generation.
* **GST Compliance Center**: Automatic tax calculations, GSTR-1, GSTR-3B summary reports, and ITC utilization.
* **Bank Reconciliation**: Statement CSV parser, transaction rule matching, and exception resolution.

### 2. 👥 HR & Team Operations
* **Workforce Register**: Employee profiles, department organization, and role-based permissions.
* **Attendance & Regularizations**: Geofenced daily check-ins, shift logs, and regularization approval queues.
* **Payroll & Payslips**: Monthly salary runs, statutory deductions (PF/ESI/TDS), and downloadable payslip PDFs.
* **Recruitment Pipeline**: Job posting management, candidate applicant tracking, and interview scheduling.

### 3. 🗂️ My Desk Workspace
* **Notes Knowledge Base**: Rich-text notes editor, quick tag filters, and share options.
* **Task Manager**: Dynamic Kanban boards, priority tagging, and task assignment.
* **Workspace Team Chat**: Public team channels (`#general`, `#finance`) and direct messaging.
* **Work Diary & Expenses**: Personal daily logbook and employee expense claim reimbursements.

---

## 🔐 Default Demo Credentials

When launched via `npm run bridgeworks`, the platform automatically seeds default admin login credentials:

* **Admin Email**: `admin@local.dev`
* **Admin Password**: `localdev123`
* **Admin User**: `Jatin Choudhary`

---

## 📜 Author & Credits

Designed & Developed with ❤️ by **[Jatin Choudhary](https://github.com/jatinchoudhary07)**  
*BridgeWorks Enterprise Platform &middot; All Rights Reserved*
