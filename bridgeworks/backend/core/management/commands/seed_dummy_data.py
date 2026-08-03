"""
Management command: seed_dummy_data
====================================
Populates rich, realistic dummy data across Accounting, HR & Team, and My Desk.
Enables all dashboards, GST compliance, ledgers, payroll, attendance, and tasks
to load full interactive metrics instantly.

Usage:
    python manage.py seed_dummy_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, date, datetime
import decimal

User = get_user_model()

class Command(BaseCommand):
    help = "Seed rich dummy data for Accounting, HR & Team, and My Desk"

    def handle(self, *args, **options):
        self.stdout.write("Seeding rich dummy data...")

        user = User.objects.filter(email="admin@local.dev").first()
        if not user:
            self.stdout.write(self.style.ERROR("Local dev user not found. Run seed_local_dev first!"))
            return

        from core.models import ShopCredentials
        shop = ShopCredentials.objects.filter(owner=user).first()
        org_id = shop.organization_id if shop else "org-1"

        now = timezone.now()
        today = date.today()

        # ----------------------------------------------------------------------
        # 1. GST SETTINGS & TRANSACTIONS & SUMMARY
        # ----------------------------------------------------------------------
        self.stdout.write("1. Seeding GST Compliance Data...")
        try:
            from accounting.models import GSTSettings, GSTTransaction, GSTSummary
            gst_settings, _ = GSTSettings.objects.get_or_create(
                org_id=org_id,
                defaults={
                    "gstin": "07AAAAA0000A1Z5",
                    "legal_name": "BridgeWorks ERP Pvt Ltd",
                    "state": "07-Delhi",
                    "registration_type": "regular",
                    "filing_frequency": "monthly",
                    "default_gst_rate": decimal.Decimal("18.00"),
                }
            )

            GSTTransaction.objects.filter(org_id=org_id).delete()
            sample_txns = [
                ("INV-2026-001", "B2B_SALE", "Sales Module", decimal.Decimal("150000.00"), decimal.Decimal("18.00"), decimal.Decimal("27000.00"), "OUTPUT_IGST", "filed"),
                ("INV-2026-002", "B2C_SALE", "Sales Module", decimal.Decimal("45000.00"), decimal.Decimal("18.00"), decimal.Decimal("8100.00"), "OUTPUT_CGST_SGST", "filed"),
                ("PUR-2026-089", "B2B_PURCHASE", "Purchase Module", decimal.Decimal("80000.00"), decimal.Decimal("18.00"), decimal.Decimal("14400.00"), "INPUT_IGST", "reconciled"),
                ("EXP-2026-012", "EXPENSE", "Expense Tracker", decimal.Decimal("25000.00"), decimal.Decimal("18.00"), decimal.Decimal("4500.00"), "INPUT_CGST_SGST", "reconciled"),
                ("INV-2026-003", "B2B_SALE", "Sales Module", decimal.Decimal("220000.00"), decimal.Decimal("18.00"), decimal.Decimal("39600.00"), "OUTPUT_IGST", "pending"),
                ("PUR-2026-092", "B2B_PURCHASE", "Purchase Module", decimal.Decimal("110000.00"), decimal.Decimal("18.00"), decimal.Decimal("19800.00"), "INPUT_IGST", "pending"),
            ]

            for idx, (ref, ttype, smodule, taxable, rate, gst_amt, gtype, status) in enumerate(sample_txns, 1):
                GSTTransaction.objects.create(
                    org_id=org_id,
                    transaction_id=f"TXN-GST-{idx:04d}",
                    reference_number=ref,
                    transaction_type=ttype,
                    source_module=smodule,
                    taxable_amount=taxable,
                    gst_rate=rate,
                    gst_amount=gst_amt,
                    gst_type=gtype,
                    status=status,
                    created_at=now - timedelta(days=idx * 3),
                )

            GSTSummary.objects.filter(org_id=org_id).delete()
            for m in [5, 6, 7, 8]:
                GSTSummary.objects.create(
                    org_id=org_id,
                    month=str(m),
                    year="2026",
                    input_gst=decimal.Decimal("38700.00"),
                    output_gst=decimal.Decimal("74700.00"),
                    net_gst=decimal.Decimal("36000.00"),
                )
            self.stdout.write(self.style.SUCCESS("   GST Data seeded."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   GST error: {e}"))

        # ----------------------------------------------------------------------
        # 2. LEDGERS, ACCOUNTS, EXPENSES, INCOME & JOURNAL ENTRIES
        # ----------------------------------------------------------------------
        self.stdout.write("2. Seeding Ledgers, Expenses, Income & Financial Statements...")
        try:
            from accounting.models import (
                Ledger, Account, JournalEntry, JournalItem, PendingExpense,
                Expense, Income, Outstanding, Invoice, FinancialAccount,
                Asset, ReconciliationRule
            )

            # Cleanup
            Expense.objects.filter(org_id=org_id).delete()
            Income.objects.filter(org_id=org_id).delete()
            Outstanding.objects.filter(org_id=org_id).delete()
            Invoice.objects.filter(org_id=org_id).delete()
            PendingExpense.objects.filter(org_id=org_id).delete()
            JournalItem.objects.all().delete()
            JournalEntry.objects.filter(org_id=org_id).delete()
            Ledger.objects.filter(org_id=org_id).delete()
            Account.objects.filter(org_id=org_id).delete()
            FinancialAccount.objects.filter(org_id=org_id).delete()

            # Financial Accounts
            fa_hdfc = FinancialAccount.objects.create(org_id=org_id, account_name="HDFC Bank Current Account", account_class="asset", account_type="bank", balance=decimal.Decimal("845000.00"), status="active")
            fa_sbi  = FinancialAccount.objects.create(org_id=org_id, account_name="SBI Tax Reserve Account", account_class="asset", account_type="bank", balance=decimal.Decimal("320000.00"), status="active")

            # Ledgers (Use LOWERCASE types: asset, liability, income, expense)
            l_sales = Ledger.objects.create(org_id=org_id, name="Sales Revenue", type="income")
            l_consulting = Ledger.objects.create(org_id=org_id, name="Consulting Revenue", type="income")
            l_purchases = Ledger.objects.create(org_id=org_id, name="Cost of Goods Sold", type="expense")
            l_bank = Ledger.objects.create(org_id=org_id, name="HDFC Operating Bank Account", type="asset")
            l_rent = Ledger.objects.create(org_id=org_id, name="Office Rent Expense", type="expense")
            l_salaries = Ledger.objects.create(org_id=org_id, name="Payroll Salaries Expense", type="expense")
            l_hosting = Ledger.objects.create(org_id=org_id, name="Cloud Server & Software Expense", type="expense")
            l_mkt = Ledger.objects.create(org_id=org_id, name="Marketing & Ad Campaign Expense", type="expense")
            l_gst_out = Ledger.objects.create(org_id=org_id, name="GST Output Tax Payable", type="liability")
            l_gst_in = Ledger.objects.create(org_id=org_id, name="GST Input Tax Credit", type="asset")

            # Accounts
            ac_bank = Account.objects.create(org_id=org_id, name="HDFC Main Account", type="bank", balance=decimal.Decimal("845000.00"), financial_account=fa_hdfc)
            ac_sales = Account.objects.create(org_id=org_id, name="Product Sales Revenue", type="revenue", balance=decimal.Decimal("1250000.00"))
            ac_rent = Account.objects.create(org_id=org_id, name="Building & Space Rent", type="expense", balance=decimal.Decimal("180000.00"))
            ac_payroll = Account.objects.create(org_id=org_id, name="Employee Payroll", type="expense", balance=decimal.Decimal("450000.00"))

            # Journal Entries & Items (Pass org_id to JournalItem so tenant filtering works)
            je1 = JournalEntry.objects.create(org_id=org_id, date=today - timedelta(days=15), description="Monthly Office Rent Payment")
            JournalItem.objects.create(org_id=org_id, entry=je1, ledger=l_rent, debit=decimal.Decimal("90000.00"), credit=decimal.Decimal("0.00"), department="Finance & Accounting")
            JournalItem.objects.create(org_id=org_id, entry=je1, ledger=l_bank, debit=decimal.Decimal("0.00"), credit=decimal.Decimal("90000.00"), department="Finance & Accounting")

            je2 = JournalEntry.objects.create(org_id=org_id, date=today - timedelta(days=10), description="B2B Enterprise License Invoice")
            JournalItem.objects.create(org_id=org_id, entry=je2, ledger=l_bank, debit=decimal.Decimal("177000.00"), credit=decimal.Decimal("0.00"), department="Software Engineering")
            JournalItem.objects.create(org_id=org_id, entry=je2, ledger=l_sales, debit=decimal.Decimal("0.00"), credit=decimal.Decimal("150000.00"), department="Software Engineering")
            JournalItem.objects.create(org_id=org_id, entry=je2, ledger=l_gst_out, debit=decimal.Decimal("0.00"), credit=decimal.Decimal("27000.00"), department="Software Engineering")

            je3 = JournalEntry.objects.create(org_id=org_id, date=today - timedelta(days=5), description="July Payroll Salary Disbursement")
            JournalItem.objects.create(org_id=org_id, entry=je3, ledger=l_salaries, debit=decimal.Decimal("225000.00"), credit=decimal.Decimal("0.00"), department="People & Operations")
            JournalItem.objects.create(org_id=org_id, entry=je3, ledger=l_bank, debit=decimal.Decimal("0.00"), credit=decimal.Decimal("225000.00"), department="People & Operations")

            # Direct Expenses (Populates P&L, Department Expenses, Finance Dashboard)
            expense_items = [
                (decimal.Decimal("90000.00"), l_rent, ac_bank, today - timedelta(days=15), "July Office Space Lease Rent", "Leadership & Strategy"),
                (decimal.Decimal("45000.00"), l_hosting, ac_bank, today - timedelta(days=12), "AWS Cloud Hosting Infrastructure", "Software Engineering"),
                (decimal.Decimal("32000.00"), l_mkt, ac_bank, today - timedelta(days=8), "Google Ads Digital Marketing Campaign", "Growth & Marketing"),
                (decimal.Decimal("225000.00"), l_salaries, ac_bank, today - timedelta(days=5), "July Team Salary Payout", "People & Operations"),
                (decimal.Decimal("15000.00"), l_purchases, ac_bank, today - timedelta(days=3), "Office Coffee & Refreshment Supplies", "Finance & Accounting"),
            ]
            for amt, cat, acc, dt, desc, dept in expense_items:
                Expense.objects.create(
                    org_id=org_id,
                    amount=amt,
                    category=cat,
                    account=acc,
                    date=dt,
                    description=desc,
                    department=dept,
                )

            # Direct Incomes (Populates P&L, Finance Dashboard, Revenue Charts)
            income_items = [
                (decimal.Decimal("350000.00"), l_sales, ac_sales, today - timedelta(days=20), "Annual Software License Renewal - Client A", "Software Engineering"),
                (decimal.Decimal("280000.00"), l_sales, ac_sales, today - timedelta(days=14), "Enterprise ERP Deployment Milestone 1", "Software Engineering"),
                (decimal.Decimal("120000.00"), l_consulting, ac_sales, today - timedelta(days=7), "Q3 Architecture Consulting Services", "Leadership & Strategy"),
            ]
            for amt, cat, acc, dt, desc, dept in income_items:
                Income.objects.create(
                    org_id=org_id,
                    amount=amt,
                    category=cat,
                    account=acc,
                    date=dt,
                    description=desc,
                    department=dept,
                )

            # Pending Expenses
            PendingExpense.objects.create(
                org_id=org_id,
                source_id="SRC-EXP-001",
                employee_name="AWS Cloud Services",
                category=l_hosting,
                amount=decimal.Decimal("34500.00"),
                status="PENDING_APPROVAL",
                description="Monthly infrastructure and database hosting server bill",
            )
            PendingExpense.objects.create(
                org_id=org_id,
                source_id="SRC-EXP-002",
                employee_name="Staples India",
                category=l_purchases,
                amount=decimal.Decimal("12400.00"),
                status="PENDING_APPROVAL",
                description="Stationery, printer ink cartridges and paper reams",
            )

            # Outstandings & Invoices
            Outstanding.objects.create(
                org_id=org_id,
                type="RECEIVABLE",
                party_name="Acme Corporation Ltd",
                amount=decimal.Decimal("177000.00"),
                status="UNSETTLED",
                department="Software Engineering",
                due_date=today + timedelta(days=15),
                description="Unpaid Invoice for Custom Software Development",
            )
            Outstanding.objects.create(
                org_id=org_id,
                type="PAYABLE",
                party_name="DLF Office Properties",
                amount=decimal.Decimal("90000.00"),
                status="UNSETTLED",
                department="Finance & Accounting",
                due_date=today + timedelta(days=10),
                description="Upcoming Office Space Lease Payment",
            )

            Invoice.objects.create(
                org_id=org_id,
                type="SALE",
                party_name="Acme Corporation Ltd",
                amount=decimal.Decimal("177000.00"),
                department="Software Engineering",
                due_date=today + timedelta(days=15),
                description="Enterprise Software License",
                status="UNPAID",
            )

            # Assets
            Asset.objects.filter(org_id=org_id).delete()
            Asset.objects.create(
                org_id=org_id,
                name="MacBook Pro M3 Max (Developer Unit)",
                asset_code="AST-LAP-001",
                category="IT Equipment",
                purchase_date=today - timedelta(days=120),
                purchase_cost=decimal.Decimal("245000.00"),
                current_value=decimal.Decimal("210000.00"),
                salvage_value=decimal.Decimal("25000.00"),
                useful_life_years=4,
                depreciation_method="STRAIGHT_LINE",
                status="ACTIVE",
                location="Delhi Tech HQ",
            )

            ReconciliationRule.objects.all().delete()
            ReconciliationRule.objects.create(
                rule_name="Auto-match Customer Invoice References",
                confidence_score=95,
                is_active=True,
            )

            self.stdout.write(self.style.SUCCESS("   Accounting Ledgers, Expenses, Income & Financials seeded."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   Accounting error: {e}"))

        # ----------------------------------------------------------------------
        # 3. HR & WORKFORCE & ATTENDANCE & PAYROLL & HIRING
        # ----------------------------------------------------------------------
        self.stdout.write("3. Seeding HR & Team Data...")
        try:
            from core.models import (
                WorkforceDepartment, WorkforceMember,
                AttendanceEntry, OfficeLocation,
                LeaveRequest, PayrollRun, PayrollPaymentRecord,
                HrMeetingManagerCompanyEvent
            )
            from hiring.models import Job, Candidate, Application, HiringStage

            WorkforceDepartment.objects.filter(org_id=org_id).delete()
            d_eng = WorkforceDepartment.objects.create(org_id=org_id, name="Software Engineering")
            d_fin = WorkforceDepartment.objects.create(org_id=org_id, name="Finance & Accounting")
            d_hr  = WorkforceDepartment.objects.create(org_id=org_id, name="People & Operations")

            WorkforceMember.objects.filter(org_id=org_id).delete()
            employees = [
                ("Jatin Choudhary", d_eng, "Head of Engineering", "jatin.choudhary@bridgeworks.dev"),
                ("Priya Nair", d_fin, "Lead Chartered Accountant", "priya@bridgeworks.dev"),
                ("Rahul Verma", d_hr, "Senior HR Business Partner", "rahul@bridgeworks.dev"),
                ("Ananya Deshmukh", d_eng, "Senior Full-Stack Engineer", "ananya@bridgeworks.dev"),
            ]

            wm_list = []
            for name, dept_obj, role, email in employees:
                wm = WorkforceMember.objects.create(
                    org_id=org_id,
                    full_name=name,
                    department=dept_obj,
                    role_designation=role,
                    email=email,
                    status="ACTIVE",
                    date_of_joining=today - timedelta(days=365),
                )
                wm_list.append(wm)

            OfficeLocation.objects.filter(org_id=org_id).delete()
            OfficeLocation.objects.create(
                org_id=org_id,
                name="Delhi HQ Office",
                address="Connaught Place, New Delhi",
                latitude=28.6139,
                longitude=77.2090,
                geofence_radius_meters=300,
            )

            AttendanceEntry.objects.filter(org_id=org_id).delete()
            for wm in wm_list:
                for i in range(1, 8):
                    att_date = today - timedelta(days=i)
                    if att_date.weekday() < 5:
                        in_time = datetime.combine(att_date, datetime.strptime("09:30", "%H:%M").time())
                        out_time = datetime.combine(att_date, datetime.strptime("18:30", "%H:%M").time())
                        AttendanceEntry.objects.create(
                            org_id=org_id,
                            user=user,
                            entry_date=att_date,
                            status="PRESENT",
                            in_time=in_time,
                            out_time=out_time,
                            work_mode="OFFICE",
                        )

            LeaveRequest.objects.filter(org_id=org_id).delete()
            LeaveRequest.objects.create(
                org_id=org_id,
                user=user,
                leave_type="CASUAL",
                start_date=today + timedelta(days=3),
                end_date=today + timedelta(days=4),
                reason="Personal family commitment",
                status="APPROVED",
            )

            PayrollRun.objects.filter(org_id=org_id).delete()
            pr = PayrollRun.objects.create(
                org_id=org_id,
                month=date(2026, 7, 1),
                notes="July 2026 Monthly Payroll Disbursed",
            )

            PayrollPaymentRecord.objects.filter(org_id=org_id).delete()
            for idx, wm in enumerate(wm_list):
                PayrollPaymentRecord.objects.create(
                    org_id=org_id,
                    user=user,
                    month=f"2026-0{idx+1:d}-01",
                    gross_amount=decimal.Decimal("144000.00"),
                    total_deductions=decimal.Decimal("17280.00"),
                    net_amount=decimal.Decimal("126720.00"),
                    status="PAID",
                )

            HrMeetingManagerCompanyEvent.objects.filter(org_id=org_id).delete()
            HrMeetingManagerCompanyEvent.objects.create(
                org_id=org_id,
                title="Q3 Strategic All-Hands Town Hall",
                description="Quarterly performance review, product roadmap and Q3 objectives alignment",
                start_date=now + timedelta(days=5),
            )

            HiringStage.objects.filter(org_id=org_id).delete()
            hstage = HiringStage.objects.create(
                org_id=org_id,
                name="Interview Round",
                order=1,
            )

            Job.objects.filter(org_id=org_id).delete()
            j1 = Job.objects.create(
                org_id=org_id,
                title="Senior React & Node.js Engineer",
                department="Engineering",
                location="Delhi / Remote",
                status="OPEN",
            )

            Candidate.objects.filter(org_id=org_id).delete()
            c1 = Candidate.objects.create(
                org_id=org_id,
                name="Karan Malhotra",
                email="karan.m@gmail.com",
                phone="+919876543210",
                current_company="TechCorp Solutions",
            )
            Application.objects.create(
                job=j1,
                candidate=c1,
                current_stage=hstage,
            )

            self.stdout.write(self.style.SUCCESS("   HR & Team Data seeded."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   HR error: {e}"))

        # ----------------------------------------------------------------------
        # 4. MY DESK (NOTES, DIARY, TODOS, EXPENSES)
        # ----------------------------------------------------------------------
        self.stdout.write("4. Seeding My Desk Personal Workspace...")
        try:
            from core.models import MyDeskNote, DiaryEntry, PersonalTodoItem, ExpenseEntry

            MyDeskNote.objects.filter(user=user).delete()
            MyDeskNote.objects.create(
                org_id=org_id,
                user=user,
                title="BridgeWorks ERP 3-Module Architecture Notes",
                content_html="<p>Architecture plan for bridgeworksing Finance & Accounting, HR & Team, and My Desk into a seamless desktop application.</p>",
                is_pinned=True,
            )
            MyDeskNote.objects.create(
                org_id=org_id,
                user=user,
                title="Q3 Finance & GST Reconciliation Checklist",
                content_html="<p>1. Verify GSTR-1 vs 3B sales figures.<br/>2. Reconcile Input Tax Credit (ITC) with supplier portal.<br/>3. Approve pending AWS cloud expenses.</p>",
                is_pinned=False,
            )

            DiaryEntry.objects.filter(user=user).delete()
            DiaryEntry.objects.create(
                user=user,
                entry_date=today,
                title="Productive System Deployment Day",
                note="Successfully migrated to local SQLite database with zero cloud latency. Configured all 3 core modules for instant performance.",
            )

            PersonalTodoItem.objects.filter(user=user).delete()
            PersonalTodoItem.objects.create(
                org_id=org_id,
                user=user,
                text="Review and sign July 2026 GST Return GSTR-3B",
                is_done=False,
            )
            PersonalTodoItem.objects.create(
                org_id=org_id,
                user=user,
                text="Approve AWS Cloud infrastructure pending expense invoice",
                is_done=True,
            )
            PersonalTodoItem.objects.create(
                org_id=org_id,
                user=user,
                text="Schedule Q3 Town Hall meeting with HR team",
                is_done=False,
            )

            ExpenseEntry.objects.filter(user=user).delete()
            ExpenseEntry.objects.create(
                org_id=org_id,
                user=user,
                category="MEALS",
                amount=decimal.Decimal("4850.00"),
                spent_on=today - timedelta(days=2),
                status="APPROVED",
            )

            self.stdout.write(self.style.SUCCESS("   My Desk Data seeded."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   My Desk error: {e}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("All dummy data successfully seeded across Finance, HR, and My Desk!"))
