from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class MyDeskNote(models.Model):
    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_notes')
    title = models.CharField(max_length=255, blank=True, default='')
    content_html = models.TextField(blank=True, default='')
    tags = models.JSONField(default=list, blank=True)
    labels = models.JSONField(default=list, blank=True)
    is_pinned = models.BooleanField(default=False)
    attachments = models.JSONField(default=list, blank=True)
    drive_links = models.JSONField(default=list, blank=True)
    ai_summary = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-is_pinned', '-updated_at']


class MyDeskNoteVersion(models.Model):
    note = models.ForeignKey(MyDeskNote, on_delete=models.CASCADE, related_name='versions')
    title = models.CharField(max_length=255, blank=True, default='')
    content_html = models.TextField(blank=True, default='')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-saved_at']


class MyDeskNoteAttachment(models.Model):
    note = models.ForeignKey(MyDeskNote, on_delete=models.CASCADE, related_name='file_attachments')
    file = models.FileField(upload_to='mydesk/notes/')
    original_name = models.CharField(max_length=255, blank=True, default='')
    mime_type = models.CharField(max_length=120, blank=True, default='')
    file_size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']


class PersonalTodoItem(models.Model):
    RECURRING_CHOICES = [
        ('none', 'None'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_todos')
    text = models.CharField(max_length=500)
    is_done = models.BooleanField(default=False)
    recurring = models.CharField(max_length=20, choices=RECURRING_CHOICES, default='none')
    sort_order = models.PositiveIntegerField(default=0)
    meta = models.JSONField(default=dict, blank=True)
    attachment = models.FileField(upload_to='mydesk/todos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['sort_order', '-created_at']


class PersonalTodoAttachment(models.Model):
    todo = models.ForeignKey(PersonalTodoItem, on_delete=models.CASCADE, related_name='task_attachments')
    file = models.FileField(upload_to='mydesk/todos/')
    original_name = models.CharField(max_length=255, blank=True, default='')
    mime_type = models.CharField(max_length=120, blank=True, default='')
    file_size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']


class ExpenseEntry(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Submitted', 'Submitted'),
        ('Dept Head Approved', 'Dept Head Approved'),
        ('Partially Approved', 'Partially Approved'),
        ('Finance Reviewed', 'Finance Reviewed'),
        ('Paid', 'Paid'),
        ('Rejected', 'Rejected'),
    ]

    CATEGORY_CHOICES = [
        ('travel', 'Travel'),
        ('food', 'Food & Meals'),
        ('office_supplies', 'Office Supplies'),
        ('equipment', 'Equipment'),
        ('client_entertainment', 'Client Entertainment'),
        ('misc', 'Misc'),
        ('other', 'Other'),
    ]

    TRANSACTION_TYPE_CHOICES = [
        ('expense', 'Expense'),
        ('income', 'Income'),
    ]

    FINANCE_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('posted', 'Posted to GL'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('upi', 'UPI'),
        ('cheque', 'Cheque'),
        ('neft', 'NEFT'),
        ('other', 'Other'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_expenses')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES, default='expense')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='misc')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    spent_on = models.DateField()
    bill_date = models.DateField(blank=True, null=True)
    department = models.CharField(max_length=120, blank=True, default='')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Draft')
    receipt = models.FileField(upload_to='expenses/receipts/', blank=True, null=True)
    notes = models.TextField(blank=True, default='')
    rejection_reason = models.TextField(blank=True, default='')

    # Approval trail
    dept_approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='dept_approved_expenses',
    )
    dept_approved_at = models.DateTimeField(blank=True, null=True)
    finance_reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='finance_reviewed_expenses',
    )
    finance_reviewed_at = models.DateTimeField(blank=True, null=True)
    paid_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='paid_expenses',
    )
    paid_at = models.DateTimeField(blank=True, null=True)

    # Payment info
    payment_date = models.DateField(blank=True, null=True)
    payment_method = models.CharField(max_length=30, choices=PAYMENT_METHOD_CHOICES, blank=True, default='')

    # Finance GL link
    finance_status = models.CharField(max_length=20, choices=FINANCE_STATUS_CHOICES, default='draft')
    finance_entry_id = models.IntegerField(blank=True, null=True)

    # Full workflow audit trail: [{step, actor, at, note}]
    workflow_steps = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-spent_on', '-created_at']
        indexes = [
            # Primary list-view access pattern: user's own expenses in date order
            models.Index(fields=['org_id', 'user', 'spent_on'], name='core_exp_org_user_date_idx'),
            # Sort-by-created_at support
            models.Index(fields=['org_id', 'user', 'created_at'], name='core_exp_org_user_creat_idx'),
            # HR tracker status filter
            models.Index(fields=['org_id', 'status'], name='core_exp_org_status_idx'),
        ]


class ExpenseShare(models.Model):
    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    expense = models.ForeignKey(ExpenseEntry, on_delete=models.CASCADE, related_name='shares')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_expense_shares')
    sent_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_expense_sent_shares')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('expense', 'recipient')
        ordering = ['-created_at']


class LeaveRequest(models.Model):
    LEAVE_TYPE_CHOICES = [
        ('casual', 'Casual'),
        ('sick', 'Sick'),
        ('earned', 'Earned'),
        ('parents_birthday', "Parent's Birthday"),
        ('comp_off', 'Comp-Off'),
        ('unpaid', 'Unpaid'),
        ('wfh', 'WFH'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    MANAGER_ACTION_CHOICES = [
        ('pre_approved', 'Pre-Approved by Manager'),
        ('flagged', 'Flagged by Manager'),
        ('passed', 'Passed to HR'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_leave_requests')
    # requested_to is now only used for manager routing (optional)
    requested_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_leave_inbox', blank=True, null=True)
    leave_type = models.CharField(max_length=30, choices=LEAVE_TYPE_CHOICES, default='casual')
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True, default='')
    decline_reason = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reminder_count = models.PositiveIntegerField(default=0)
    # Document attachment (optional – for sick leave, comp-off proofs)
    document = models.FileField(upload_to='leave_requests/documents/', blank=True, null=True)
    # Manager pre-processing
    manager_action = models.CharField(max_length=20, choices=MANAGER_ACTION_CHOICES, blank=True, default='')
    manager_note = models.TextField(blank=True, default='')
    manager_actioned_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='mydesk_leave_manager_actions')
    manager_actioned_at = models.DateTimeField(blank=True, null=True)
    # HR final decision
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='mydesk_leave_approvals')
    approved_at = models.DateTimeField(blank=True, null=True)
    google_synced = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']


class AttendanceEntry(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
        ('wfh', 'WFH'),
        ('leave', 'Leave'),
        ('on_duty', 'On Duty'),
    ]

    APPROVAL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    SOURCE_CHOICES = [
        ('self', 'Self'),
        ('hr', 'HR/Manager'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_entries')
    entry_date = models.DateField(db_index=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    work_mode = models.CharField(
        max_length=10,
        choices=[('wfo', 'Work From Office'), ('wfh', 'Work From Home'), ('unknown', 'Unknown')],
        default='unknown'
    )
    in_time = models.TimeField(blank=True, null=True)
    out_time = models.TimeField(blank=True, null=True)

    note = models.TextField(blank=True, default='')
    on_duty_detail = models.CharField(max_length=255, blank=True, default='')

    is_regularization = models.BooleanField(default=False)
    regularization_reason = models.TextField(blank=True, default='')

    approval_status = models.CharField(max_length=20, choices=APPROVAL_STATUS_CHOICES, default='pending')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='self')

    late_minutes = models.PositiveIntegerField(default=0)
    early_leave_minutes = models.PositiveIntegerField(default=0)
    hours_worked = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    # Auto-status engine fields
    auto_status = models.CharField(max_length=30, blank=True, default='',
                                   help_text='System-computed status before HR override')
    hr_override_status = models.CharField(max_length=30, blank=True, default='')
    hr_override_reason = models.TextField(blank=True, default='')
    hr_override_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='attendance_overrides',
    )
    hr_override_at = models.DateTimeField(blank=True, null=True)

    # Deduction tracking (fractional days: 0, 0.125, 0.5, 1.0)
    salary_deduction_days = models.DecimalField(max_digits=4, decimal_places=2, default=0)

    # Attendance score contribution for this entry (0–100)
    attendance_score_points = models.PositiveSmallIntegerField(default=100)

    # Shift lock (after 10 PM, entry locks for same-day edits)
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(blank=True, null=True)

    # Sunday/off-day paid flag
    is_paid_off = models.BooleanField(default=True)

    # Comp-off tracking
    comp_off_claimed = models.BooleanField(default=False)
    comp_off_approved = models.BooleanField(default=False)
    comp_off_expires_on = models.DateField(blank=True, null=True)

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='attendance_approved_entries'
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, default='')

    # Only one active approved record should be effective for a user/day.
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-entry_date', '-updated_at']
        indexes = [
            models.Index(fields=['org_id', 'user', 'entry_date']),
            models.Index(fields=['org_id', 'approval_status', 'entry_date']),
            models.Index(fields=['org_id', 'entry_date', 'is_active']),
        ]


class CompanyProfile(models.Model):
    org_id = models.CharField(max_length=64, unique=True, db_index=True)
    legal_name = models.CharField(max_length=255, blank=True, default='')
    registered_address = models.TextField(blank=True, default='')
    support_email = models.EmailField(blank=True, default='')
    support_phone = models.CharField(max_length=30, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['org_id']


class EmployeeProfile(models.Model):
    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employee_profiles')
    base_gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-updated_at']
        unique_together = ('org_id', 'user')
        indexes = [
            models.Index(fields=['org_id', 'user', 'is_active'], name='core_emppro_org_user_act_idx'),
        ]


class PayrollProfile(models.Model):
    TAX_REGIME_CHOICES = [
        ('new', 'New Regime'),
        ('old', 'Old Regime'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payroll_profiles')
    employee_code = models.CharField(max_length=40, blank=True, default='')
    pan_number = models.CharField(max_length=20, blank=True, default='')
    uan_number = models.CharField(max_length=30, blank=True, default='')
    bank_name = models.CharField(max_length=255, blank=True, default='')
    bank_account_number = models.CharField(max_length=50, blank=True, default='')
    base_monthly_gross = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_regime = models.CharField(max_length=10, choices=TAX_REGIME_CHOICES, default='new')
    payment_mode = models.CharField(max_length=30, blank=True, default='NEFT')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-updated_at']
        unique_together = ('org_id', 'user')
        indexes = [
            models.Index(fields=['org_id', 'user'], name='core_payrol_org_id_52cc3d_idx'),
        ]


class PayrollPaymentRecord(models.Model):
    STATUS_CHOICES = [
        ('Paid', 'Paid'),
        ('Processed', 'Processed'),
        ('On Hold', 'On Hold'),
    ]

    DISPUTE_STATUS_CHOICES = [
        ('none', 'None'),
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payroll_payment_records')
    month = models.DateField(db_index=True)

    working_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    present_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    lop_days = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payment_date = models.DateField(blank=True, null=True)
    utr_reference = models.CharField(max_length=120, blank=True, default='')
    payment_mode = models.CharField(max_length=30, blank=True, default='NEFT')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Paid')

    earnings_breakup = models.JSONField(default=list, blank=True)
    deductions_breakup = models.JSONField(default=list, blank=True)
    salary_structure_snapshot = models.JSONField(default=list, blank=True)
    salary_structure_version = models.PositiveIntegerField(default=0)
    remarks = models.TextField(blank=True, default='')
    payslip_pdf = models.FileField(upload_to='payroll/payslips/', blank=True, null=True)

    dispute_status = models.CharField(max_length=20, choices=DISPUTE_STATUS_CHOICES, default='none')
    dispute_query = models.TextField(blank=True, default='')
    dispute_resolution_note = models.TextField(blank=True, default='')
    dispute_raised_at = models.DateTimeField(blank=True, null=True)
    dispute_resolved_at = models.DateTimeField(blank=True, null=True)

    # Finance verification (Step 1 of Finance payroll flow)
    finance_verified = models.BooleanField(default=False, db_index=True)
    finance_verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_verified_payroll_records',
    )
    finance_verified_at = models.DateTimeField(blank=True, null=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_payroll_payment_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-month', 'user_id']
        unique_together = ('org_id', 'user', 'month')
        indexes = [
            models.Index(fields=['org_id', 'month'], name='core_payrol_org_id_3c819e_idx'),
            models.Index(fields=['org_id', 'user', 'month'], name='core_payrol_org_id_f0ddee_idx'),
        ]


class PayrollRun(models.Model):
    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    month = models.DateField(db_index=True)

    attendance_locked_at = models.DateTimeField(blank=True, null=True)
    attendance_locked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payroll_attendance_locks',
    )

    calculation_run_at = models.DateTimeField(blank=True, null=True)
    calculation_run_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payroll_calculation_runs',
    )

    exception_report = models.JSONField(default=list, blank=True)
    exception_count = models.PositiveIntegerField(default=0)

    hr_approved_at = models.DateTimeField(blank=True, null=True)
    hr_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payroll_hr_approvals',
    )

    finance_approved_at = models.DateTimeField(blank=True, null=True)
    finance_approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payroll_finance_approvals',
    )

    payslips_generated_at = models.DateTimeField(blank=True, null=True)
    payslips_generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payroll_payslip_generations',
    )

    bank_file_generated_at = models.DateTimeField(blank=True, null=True)
    bank_file_generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payroll_bank_file_generations',
    )

    gl_posted_at = models.DateTimeField(blank=True, null=True)
    gl_posted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payroll_gl_postings',
    )
    gl_reference = models.CharField(max_length=120, blank=True, default='')

    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(blank=True, null=True)
    locked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payroll_locks',
    )

    notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-month', '-updated_at']
        unique_together = ('org_id', 'month')
        indexes = [
            models.Index(fields=['org_id', 'month'], name='core_payrun_org_month_idx'),
            models.Index(fields=['org_id', 'is_locked', 'month'], name='core_payrun_org_lock_m_idx'),
        ]


class PayrollSalaryStructure(models.Model):
    TAXABILITY_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
        ('partial', 'Partly'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payroll_salary_structures')
    component_name = models.CharField(max_length=120)
    monthly_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    annual_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    taxability = models.CharField(max_length=10, choices=TAXABILITY_CHOICES, default='yes')
    remarks = models.CharField(max_length=255, blank=True, default='')
    sort_order = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['sort_order', 'id']
        indexes = [
            models.Index(fields=['org_id', 'user', 'is_active'], name='core_payrol_org_id_3438df_idx'),
            models.Index(fields=['org_id', 'user', 'effective_from'], name='core_payrol_org_eff_from_idx'),
        ]


class PayrollTaxDeclaration(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payroll_tax_declarations')
    financial_year = models.CharField(max_length=9, db_index=True)
    section_code = models.CharField(max_length=20, blank=True, default='80C')
    investment_name = models.CharField(max_length=255)
    max_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    declared_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    proof_file_name = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['sort_order', 'id']
        unique_together = ('org_id', 'user', 'financial_year', 'section_code', 'investment_name')
        indexes = [
            models.Index(fields=['org_id', 'user', 'financial_year', 'is_active'], name='core_payrol_org_id_58eb75_idx'),
        ]


class GalleryAlbum(models.Model):
    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_gallery_albums')
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        unique_together = ('org_id', 'user', 'name')
        ordering = ['name']


class GalleryItem(models.Model):
    SOURCE_UPLOAD = 'upload'
    SOURCE_MY_CHATS = 'my_chats'
    SOURCE_CHOICES = [
        (SOURCE_UPLOAD, 'Direct Upload'),
        (SOURCE_MY_CHATS, 'MyChats'),
    ]

    CATEGORY_IMAGES = 'images'
    CATEGORY_VIDEOS = 'videos'
    CATEGORY_DOCUMENTS = 'documents'
    CATEGORY_AUDIO = 'audio'
    CATEGORY_ARCHIVES = 'archives'
    CATEGORY_SHARED = 'shared_files'
    CATEGORY_CHOICES = [
        (CATEGORY_IMAGES, 'Images'),
        (CATEGORY_VIDEOS, 'Videos'),
        (CATEGORY_DOCUMENTS, 'Documents'),
        (CATEGORY_AUDIO, 'Audio'),
        (CATEGORY_ARCHIVES, 'Archives'),
        (CATEGORY_SHARED, 'Shared Files'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_gallery_items')
    album = models.ForeignKey(GalleryAlbum, on_delete=models.SET_NULL, null=True, blank=True, related_name='items')
    file = models.FileField(upload_to='gallery/items/')
    media_type = models.CharField(max_length=20, blank=True, default='file')
    is_favorite = models.BooleanField(default=False)
    is_reference = models.BooleanField(default=False)
    captured_on = models.DateField(blank=True, null=True)

    # MyVault categorisation & source tracking
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_UPLOAD, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_SHARED, db_index=True)
    download_count = models.PositiveIntegerField(default=0)

    # Chat-origin metadata (set when source == 'my_chats')
    chat_message_id = models.IntegerField(blank=True, null=True, db_index=True)
    chat_context_name = models.CharField(max_length=255, blank=True, default='',
                                         help_text='Room / channel / conversation name')
    chat_sender_name = models.CharField(max_length=150, blank=True, default='')
    chat_shared_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-created_at']


class GalleryItemShare(models.Model):
    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    item = models.ForeignKey(GalleryItem, on_delete=models.CASCADE, related_name='shares')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_gallery_shares')
    sent_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mydesk_gallery_sent_shares')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        unique_together = ('item', 'recipient')
        ordering = ['-created_at']


class HrMeetingManagerCompanyEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ('birthday', 'Birthday'),
        ('high_pressure', 'High Pressure Day'),
        ('holiday', 'Holiday'),
        ('event', 'Event'),
        ('big_sale', 'Big Sale'),
        ('annual_event', 'Annual Event'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    title = models.CharField(max_length=255, blank=True, default='')
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES, default='event')
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='hr_meeting_manager_events'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['-start_date', '-created_at']


class AttendanceRulebook(models.Model):
    """Per-employee attendance configuration rulebook. Only HR can edit."""

    EMPLOYEE_TYPE_CHOICES = [
        ('office', 'Office'),
        ('labour', 'Labour'),
        ('field', 'Field'),
    ]

    WEEKLY_OFF_CHOICES = [
        ('sunday', 'Sunday'),
        ('saturday', 'Saturday'),
        ('none', 'None'),
    ]

    SATURDAY_WORKING_CHOICES = [
        ('yes', 'Yes'),
        ('no', 'No'),
        ('alternate', 'Alternate'),
    ]

    org_id = models.CharField(max_length=64, db_index=True, blank=True, default='')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='attendance_rulebook')

    # Shift timings
    shift_start = models.TimeField(default='09:30:00')
    shift_end = models.TimeField(default='18:30:00')
    lunch_duration_minutes = models.PositiveIntegerField(default=30)

    # Late arrival thresholds (minutes)
    grace_period_minutes = models.PositiveIntegerField(default=14,
        help_text='0-N min late: Present, warning logged')
    late_deduction_threshold_minutes = models.PositiveIntegerField(default=15,
        help_text='N-39 min late: Present + 1hr salary deduct')
    half_day_late_threshold_minutes = models.PositiveIntegerField(default=40,
        help_text='N+ min late: First Half Absent + half-day deduct')

    # Early leave thresholds (minutes before shift end)
    early_leave_deduction_minutes = models.PositiveIntegerField(default=10,
        help_text='10-39 min early: Present + 1hr salary deduct')
    half_day_early_leave_minutes = models.PositiveIntegerField(default=40,
        help_text='N+ min early: Second Half Absent + half-day deduct')

    # Regularization limit per month
    regularization_limit_per_month = models.PositiveIntegerField(default=3)

    # Employee classification
    employee_type = models.CharField(max_length=20, choices=EMPLOYEE_TYPE_CHOICES, default='office')
    weekly_off = models.CharField(max_length=20, choices=WEEKLY_OFF_CHOICES, default='sunday')
    saturday_working = models.CharField(max_length=20, choices=SATURDAY_WORKING_CHOICES, default='yes')

    # Audit
    last_edited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='rulebook_edits',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        ordering = ['user_id']

