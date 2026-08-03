import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Chip,
    CircularProgress,
    FormControl,
    Grid,
    InputLabel,
    MenuItem,
    Paper,
    Select,
    Stack,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Typography,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    IconButton,
} from '@mui/material';
import {
    Add as AddIcon,
    DeleteOutline as DeleteOutlineIcon,
    Download as DownloadIcon,
    Edit as EditIcon,
    Paid as PaidIcon,
    Save as SaveIcon,
    Visibility as VisibilityIcon,
} from '@mui/icons-material';
import {
    executeHrPayrollRunAction,
    getHrPayrollEmployeeDetail,
    getHrPayrollRunStatus,
    listHrPayrollDashboard,
    saveHrPayrollEmployeeBreakup,
    saveHrPayrollEmployeeSalaryStructure,
} from '../mydesk/mydeskService';

const EMPTY_DASHBOARD = {
    month: '',
    month_label: '',
    count: 0,
    totals: {
        gross: 0,
        deductions: 0,
        net: 0,
    },
    rows: [],
};

const TAXABILITY_OPTIONS = [
    { value: 'yes', label: 'Taxable' },
    { value: 'partial', label: 'Partly Taxable' },
    { value: 'no', label: 'Non-Taxable' },
];

function createSalaryEditorRow(seed = {}, fallbackId = '') {
    const taxability = String(seed.taxability || 'yes').toLowerCase();
    return {
        _localId: seed.id || fallbackId || `new-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        component_name: String(seed.component_name || ''),
        monthly_amount: seed.monthly_amount ?? '',
        annual_amount: seed.annual_amount ?? '',
        taxability: TAXABILITY_OPTIONS.some((item) => item.value === taxability) ? taxability : 'yes',
        remarks: String(seed.remarks || ''),
    };
}

function buildSalaryEditorRows(rows) {
    if (!Array.isArray(rows) || rows.length === 0) {
        return [createSalaryEditorRow()];
    }

    return rows.map((row, index) => createSalaryEditorRow(row, `row-${index}-${Date.now()}`));
}

function normalizeStructureTotals(detailRow) {
    const explicitMonthly = Number(detailRow?.salary_structure_totals?.monthly);
    const explicitAnnual = Number(detailRow?.salary_structure_totals?.annual);
    if (!Number.isNaN(explicitMonthly) && !Number.isNaN(explicitAnnual)) {
        return { monthly: explicitMonthly, annual: explicitAnnual };
    }

    const rows = Array.isArray(detailRow?.salary_structure) ? detailRow.salary_structure : [];
    return rows.reduce((acc, row) => ({
        monthly: acc.monthly + Number(row.monthly_amount || 0),
        annual: acc.annual + Number(row.annual_amount || 0),
    }), { monthly: 0, annual: 0 });
}

function createBreakupEditorRow(seed = {}, fallbackId = '') {
    return {
        _localId: seed._localId || fallbackId || `breakup-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        component: String(seed.component || ''),
        amount: seed.amount ?? '',
    };
}

function buildBreakupEditorRows(rows, prefix) {
    if (!Array.isArray(rows) || rows.length === 0) {
        return [createBreakupEditorRow({}, `${prefix}-new-${Date.now()}`)];
    }

    return rows.map((row, index) => createBreakupEditorRow(row, `${prefix}-${index}-${Date.now()}`));
}

function sumBreakupAmount(rows) {
    if (!Array.isArray(rows)) return 0;
    return rows.reduce((total, row) => total + Number(row?.amount || 0), 0);
}

function formatAmount(value) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0,
    }).format(Number(value || 0));
}

function formatNullableAmount(value) {
    if (value === null || value === undefined || value === '') return '-';
    return formatAmount(value);
}

function formatNullableDate(value) {
    if (!value) return '-';
    return formatDate(value);
}

function formatDate(value) {
    if (!value) return '-';
    const parsed = new Date(`${value}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

function currentMonthToken() {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
}

function buildMonthOptions(count = 18) {
    const now = new Date();
    const items = [];
    for (let index = 0; index < count; index += 1) {
        const value = new Date(now.getFullYear(), now.getMonth() - index, 1);
        const token = `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}`;
        const label = value.toLocaleString(undefined, { month: 'short', year: 'numeric' });
        items.push({ token, label });
    }
    return items;
}

function payrollStatusColor(statusValue) {
    const value = String(statusValue || '').toLowerCase();
    if (value === 'paid') return 'success';
    if (value === 'on hold') return 'warning';
    return 'info';
}

function payrollRunStageLabel(stageValue) {
    const value = String(stageValue || '').toLowerCase();
    if (value === 'locked') return 'Payroll Locked';
    if (value === 'finance_approved') return 'Finance Approved';
    if (value === 'hr_approved') return 'HR Approved';
    if (value === 'calculated') return 'Calculation Completed';
    if (value === 'attendance_locked') return 'Attendance Locked';
    return 'Draft';
}

function payrollRunStageColor(stageValue) {
    const value = String(stageValue || '').toLowerCase();
    if (value === 'locked') return 'success';
    if (value === 'finance_approved') return 'primary';
    if (value === 'hr_approved') return 'secondary';
    if (value === 'calculated') return 'info';
    if (value === 'attendance_locked') return 'warning';
    return 'default';
}

function exportPayrollCsv(rows, monthToken) {
    if (!Array.isArray(rows) || rows.length === 0) return;

    const headers = [
        'Employee Name',
        'Employee ID',
        'Department',
        'PAN',
        'UAN',
        'Bank',
        'Working Days',
        'Present Days',
        'LOP Days',
        'Gross',
        'Deductions',
        'Net',
        'UTR',
        'Payment Date',
        'Status',
    ];

    const csvRows = [headers.join(',')];
    rows.forEach((row) => {
        const values = [
            row.employee_name,
            row.employee_id,
            row.department,
            row.pan_masked,
            row.uan,
            row.bank_account_display,
            row.working_days,
            row.present_days,
            row.lop_days,
            row.gross,
            row.deductions,
            row.net,
            row.utr,
            row.payment_date,
            row.status,
        ].map((item) => `"${String(item ?? '').replace(/"/g, '""')}"`);
        csvRows.push(values.join(','));
    });

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `hr-payroll-${monthToken}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
}

function exportBankTransferCsv(rows, monthToken) {
    if (!Array.isArray(rows) || rows.length === 0) return;

    const headers = [
        'Employee Name',
        'Employee ID',
        'Department',
        'Bank Name',
        'Account Number',
        'IFSC',
        'Amount',
        'Payment Mode',
        'UTR',
    ];

    const csvRows = [headers.join(',')];
    rows.forEach((row) => {
        const values = [
            row.employee_name,
            row.employee_id,
            row.department,
            row.bank_name,
            row.account_number,
            row.ifsc,
            row.amount,
            row.payment_mode,
            row.utr,
        ].map((item) => `"${String(item ?? '').replace(/"/g, '""')}"`);
        csvRows.push(values.join(','));
    });

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `hr-payroll-bank-file-${monthToken}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
}

export default function HRPayrollDashboard() {
    const monthOptions = useMemo(() => buildMonthOptions(18), []);
    const [month, setMonth] = useState(monthOptions[0]?.token || currentMonthToken());
    const [search, setSearch] = useState('');
    const [dashboard, setDashboard] = useState(EMPTY_DASHBOARD);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [runStatus, setRunStatus] = useState(null);
    const [runLoading, setRunLoading] = useState(false);
    const [runActionLoading, setRunActionLoading] = useState('');
    const [runError, setRunError] = useState('');

    const [detailRow, setDetailRow] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [salaryEditorOpen, setSalaryEditorOpen] = useState(false);
    const [salaryEditorRows, setSalaryEditorRows] = useState([]);
    const [salaryEditorError, setSalaryEditorError] = useState('');
    const [salarySaving, setSalarySaving] = useState(false);

    const [breakupEditorOpen, setBreakupEditorOpen] = useState(false);
    const [earningsEditorRows, setEarningsEditorRows] = useState([]);
    const [deductionsEditorRows, setDeductionsEditorRows] = useState([]);
    const [breakupEditorError, setBreakupEditorError] = useState('');
    const [breakupSaving, setBreakupSaving] = useState(false);
    const [breakupEditorMode, setBreakupEditorMode] = useState('both');

    const detailRequestIdRef = useRef(0);

    const loadDashboard = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const response = await listHrPayrollDashboard({
                month,
                search: search.trim() || undefined,
            });
            setDashboard({
                ...EMPTY_DASHBOARD,
                ...response,
                rows: Array.isArray(response?.rows) ? response.rows : [],
                totals: {
                    gross: Number(response?.totals?.gross || 0),
                    deductions: Number(response?.totals?.deductions || 0),
                    net: Number(response?.totals?.net || 0),
                },
            });
            if (response?.payroll_run) {
                setRunStatus((previous) => ({
                    ...previous,
                    month: response.month || month,
                    run: response.payroll_run,
                    stats: previous?.stats || null,
                    exceptions: previous?.exceptions || [],
                }));
            }
        } catch (requestError) {
            setDashboard(EMPTY_DASHBOARD);
            setError(requestError?.message || 'Unable to load payroll dashboard.');
        } finally {
            setLoading(false);
        }
    }, [month, search]);

    const loadRunStatus = useCallback(async () => {
        setRunLoading(true);
        setRunError('');
        try {
            const response = await getHrPayrollRunStatus({ month });
            setRunStatus(response || null);
        } catch (requestError) {
            setRunStatus(null);
            setRunError(requestError?.message || 'Unable to load payroll run status.');
        } finally {
            setRunLoading(false);
        }
    }, [month]);

    useEffect(() => {
        const timer = window.setTimeout(() => {
            loadDashboard();
        }, 250);
        return () => {
            window.clearTimeout(timer);
        };
    }, [loadDashboard]);

    useEffect(() => {
        loadRunStatus();
    }, [loadRunStatus]);

    const rows = useMemo(() => (Array.isArray(dashboard.rows) ? dashboard.rows : []), [dashboard.rows]);
    const activeRun = useMemo(
        () => runStatus?.run || dashboard?.payroll_run || {},
        [dashboard?.payroll_run, runStatus?.run],
    );
    const runStats = runStatus?.stats || null;
    const runExceptions = useMemo(
        () => (Array.isArray(runStatus?.exceptions) ? runStatus.exceptions : []),
        [runStatus?.exceptions],
    );
    const runStage = activeRun?.stage || 'draft';
    const isPayrollLocked = Boolean(activeRun?.is_locked);
    const isRunActionBusy = Boolean(runActionLoading);
    const recordsInMonth = Number(runStats?.generated_records ?? rows.filter((row) => row?.has_record).length);

    const handleRunAction = async (action) => {
        if (!action || isRunActionBusy) return;
        setRunActionLoading(action);
        setRunError('');
        try {
            const response = await executeHrPayrollRunAction({ month, action });
            setRunStatus(response || null);

            if (action === 'export_bank_file') {
                const bankRows = Array.isArray(response?.bank_file?.rows) ? response.bank_file.rows : [];
                if (bankRows.length > 0) {
                    exportBankTransferCsv(bankRows, response?.month || month);
                }
            }

            await Promise.all([loadDashboard(), loadRunStatus()]);
        } catch (requestError) {
            setRunError(requestError?.message || 'Unable to update payroll run stage.');
        } finally {
            setRunActionLoading('');
        }
    };

    const handleOpenDetails = async (userId) => {
        detailRequestIdRef.current += 1;
        const requestId = detailRequestIdRef.current;
        setDetailLoading(true);
        setError('');
        setSalaryEditorOpen(false);
        setSalaryEditorRows([]);
        setSalaryEditorError('');

        setBreakupEditorOpen(false);
        setEarningsEditorRows([]);
        setDeductionsEditorRows([]);
        setBreakupEditorError('');
        setBreakupEditorMode('both');

        try {
            const response = await getHrPayrollEmployeeDetail(userId, { month });
            if (detailRequestIdRef.current !== requestId) return;
            setDetailRow(response || null);
        } catch (requestError) {
            if (detailRequestIdRef.current !== requestId) return;
            setError(requestError?.message || 'Unable to load employee payroll details.');
        } finally {
            if (detailRequestIdRef.current === requestId) {
                setDetailLoading(false);
            }
        }
    };

    const handleCloseDetails = () => {
        detailRequestIdRef.current += 1;
        setDetailRow(null);
        setDetailLoading(false);
        setSalaryEditorOpen(false);
        setSalaryEditorRows([]);
        setSalaryEditorError('');
        setSalarySaving(false);

        setBreakupEditorOpen(false);
        setEarningsEditorRows([]);
        setDeductionsEditorRows([]);
        setBreakupEditorError('');
        setBreakupSaving(false);
        setBreakupEditorMode('both');
    };

    const salaryStructureRows = useMemo(
        () => (Array.isArray(detailRow?.salary_structure) ? detailRow.salary_structure : []),
        [detailRow],
    );

    const earningsRows = useMemo(
        () => (Array.isArray(detailRow?.earnings) ? detailRow.earnings : []),
        [detailRow],
    );

    const deductionsRows = useMemo(
        () => (Array.isArray(detailRow?.deductions_breakup) ? detailRow.deductions_breakup : []),
        [detailRow],
    );

    const salaryStructureTotals = useMemo(() => normalizeStructureTotals(detailRow), [detailRow]);
    const earningsTotal = useMemo(() => sumBreakupAmount(earningsRows), [earningsRows]);
    const deductionsTotal = useMemo(() => sumBreakupAmount(deductionsRows), [deductionsRows]);

    const hrExpensesRows = useMemo(
        () => (Array.isArray(detailRow?.hr_expenses) ? detailRow.hr_expenses : []),
        [detailRow],
    );
    const expenseTotal = useMemo(() => Number(detailRow?.expense_total || 0), [detailRow]);

    const handleOpenBreakupEditor = (mode = 'both') => {
        if (!detailRow) return;
        if (isPayrollLocked) {
            setBreakupEditorError('Payroll is locked for this month. Editing is disabled.');
            return;
        }
        setSalaryEditorOpen(false);
        setBreakupEditorError('');
        setEarningsEditorRows(buildBreakupEditorRows(earningsRows, 'earnings'));
        setDeductionsEditorRows(buildBreakupEditorRows(deductionsRows, 'deductions'));
        setBreakupEditorMode(mode);
        setBreakupEditorOpen(true);
    };

    const handleBreakupRowFieldChange = (type, localId, fieldName, value) => {
        const setter = type === 'earnings' ? setEarningsEditorRows : setDeductionsEditorRows;
        setter((prevRows) => prevRows.map((row) => {
            if (row._localId !== localId) return row;
            return {
                ...row,
                [fieldName]: value,
            };
        }));
    };

    const handleAddBreakupRow = (type) => {
        const setter = type === 'earnings' ? setEarningsEditorRows : setDeductionsEditorRows;
        setter((prevRows) => [...prevRows, createBreakupEditorRow({}, `${type}-${Date.now()}`)]);
    };

    const handleRemoveBreakupRow = (type, localId) => {
        const setter = type === 'earnings' ? setEarningsEditorRows : setDeductionsEditorRows;
        setter((prevRows) => {
            const filtered = prevRows.filter((row) => row._localId !== localId);
            return filtered.length > 0 ? filtered : [createBreakupEditorRow({}, `${type}-${Date.now()}`)];
        });
    };

    const sanitizeBreakupRows = (rows, label, requireAtLeastOne = false) => {
        const cleanedRows = rows
            .map((row) => ({
                component: String(row.component || '').trim(),
                amount: row.amount,
            }))
            .filter((row) => row.component || String(row.amount || '').trim() !== '');

        if (requireAtLeastOne && cleanedRows.length === 0) {
            return { error: `Add at least one ${label} row before saving.` };
        }

        const payloadRows = [];
        for (let index = 0; index < cleanedRows.length; index += 1) {
            const row = cleanedRows[index];
            if (!row.component) {
                return { error: `${label} component is required for row ${index + 1}.` };
            }

            const amountValue = row.amount === '' ? 0 : Number(row.amount);
            if (Number.isNaN(amountValue) || amountValue < 0) {
                return { error: `${label} amount must be a non-negative number for row ${index + 1}.` };
            }

            payloadRows.push({
                component: row.component,
                amount: amountValue,
            });
        }

        return { rows: payloadRows };
    };

    const handleSaveBreakup = async () => {
        if (isPayrollLocked) {
            setBreakupEditorError('Payroll is locked for this month. Editing is disabled.');
            return;
        }

        const employeeUserId = detailRow?.employee?.user_id;
        if (!employeeUserId) {
            setBreakupEditorError('Unable to identify employee for update.');
            return;
        }

        const sanitizedEarnings = sanitizeBreakupRows(earningsEditorRows, 'Earnings', true);
        if (sanitizedEarnings.error) {
            setBreakupEditorError(sanitizedEarnings.error);
            return;
        }

        const sanitizedDeductions = sanitizeBreakupRows(deductionsEditorRows, 'Deductions', false);
        if (sanitizedDeductions.error) {
            setBreakupEditorError(sanitizedDeductions.error);
            return;
        }

        setBreakupSaving(true);
        setBreakupEditorError('');

        try {
            const response = await saveHrPayrollEmployeeBreakup(employeeUserId, {
                month,
                earnings: sanitizedEarnings.rows,
                deductions: sanitizedDeductions.rows,
            });

            setDetailRow((previous) => {
                if (!previous) return previous;
                return {
                    ...previous,
                    has_record: true,
                    month: response?.month || previous.month,
                    month_label: response?.month_label || previous.month_label,
                    working_days: response?.working_days ?? previous.working_days,
                    present_days: response?.present_days ?? previous.present_days,
                    lop_days: response?.lop_days ?? previous.lop_days,
                    gross: response?.gross ?? previous.gross,
                    deductions: response?.deductions ?? previous.deductions,
                    net: response?.net ?? previous.net,
                    payment_date: response?.payment_date || previous.payment_date,
                    utr: response?.utr || previous.utr,
                    payment_mode: response?.payment_mode || previous.payment_mode,
                    status: response?.status || previous.status,
                    earnings: Array.isArray(response?.earnings) ? response.earnings : previous.earnings,
                    deductions_breakup: Array.isArray(response?.deductions_breakup) ? response.deductions_breakup : previous.deductions_breakup,
                };
            });

            setDashboard((previous) => {
                const previousRows = Array.isArray(previous?.rows) ? previous.rows : [];
                if (previousRows.length === 0) return previous;

                const nextRows = previousRows.map((row) => {
                    if (row.user_id !== employeeUserId) return row;
                    return {
                        ...row,
                        has_record: true,
                        working_days: response?.working_days ?? row.working_days,
                        present_days: response?.present_days ?? row.present_days,
                        lop_days: response?.lop_days ?? row.lop_days,
                        gross: Number(response?.gross ?? row.gross ?? 0),
                        deductions: Number(response?.deductions ?? row.deductions ?? 0),
                        net: Number(response?.net ?? row.net ?? 0),
                        payment_date: response?.payment_date || row.payment_date,
                        utr: response?.utr || row.utr,
                        payment_mode: response?.payment_mode || row.payment_mode,
                        status: response?.status || row.status,
                    };
                });

                const totals = {
                    gross: nextRows.reduce((sum, row) => sum + (row.has_record ? Number(row.gross || 0) : 0), 0),
                    deductions: nextRows.reduce((sum, row) => sum + (row.has_record ? Number(row.deductions || 0) : 0), 0),
                    net: nextRows.reduce((sum, row) => sum + (row.has_record ? Number(row.net || 0) : 0), 0),
                };

                return {
                    ...previous,
                    rows: nextRows,
                    totals,
                };
            });

            setBreakupEditorOpen(false);
        } catch (requestError) {
            setBreakupEditorError(requestError?.message || 'Unable to save earnings and deductions.');
        } finally {
            setBreakupSaving(false);
        }
    };

    const handleOpenSalaryEditor = () => {
        if (!detailRow) return;
        if (isPayrollLocked) {
            setSalaryEditorError('Payroll is locked for this month. Editing is disabled.');
            return;
        }
        setSalaryEditorRows(buildSalaryEditorRows(salaryStructureRows));
        setSalaryEditorError('');
        setSalaryEditorOpen(true);
    };

    const handleSalaryRowFieldChange = (localId, fieldName, value) => {
        setSalaryEditorRows((prevRows) => prevRows.map((row) => {
            if (row._localId !== localId) return row;
            return {
                ...row,
                [fieldName]: value,
            };
        }));
    };

    const handleAddSalaryRow = () => {
        setSalaryEditorRows((prevRows) => [...prevRows, createSalaryEditorRow()]);
    };

    const handleRemoveSalaryRow = (localId) => {
        setSalaryEditorRows((prevRows) => {
            const filtered = prevRows.filter((row) => row._localId !== localId);
            return filtered.length > 0 ? filtered : [createSalaryEditorRow()];
        });
    };

    const handleSaveSalaryStructure = async () => {
        if (isPayrollLocked) {
            setSalaryEditorError('Payroll is locked for this month. Editing is disabled.');
            return;
        }

        const employeeUserId = detailRow?.employee?.user_id;
        if (!employeeUserId) {
            setSalaryEditorError('Unable to identify employee for salary structure update.');
            return;
        }

        const cleanedRows = salaryEditorRows
            .map((row, index) => ({
                component_name: String(row.component_name || '').trim(),
                monthly_amount: row.monthly_amount,
                annual_amount: row.annual_amount,
                taxability: String(row.taxability || 'yes').toLowerCase(),
                remarks: String(row.remarks || '').trim(),
                sort_order: index,
            }))
            .filter((row) => (
                row.component_name
                || String(row.monthly_amount || '').trim() !== ''
                || String(row.annual_amount || '').trim() !== ''
                || row.remarks
            ));

        if (cleanedRows.length === 0) {
            setSalaryEditorError('Add at least one salary component before saving.');
            return;
        }

        const payloadRows = [];
        for (let index = 0; index < cleanedRows.length; index += 1) {
            const row = cleanedRows[index];
            if (!row.component_name) {
                setSalaryEditorError(`Component name is required for row ${index + 1}.`);
                return;
            }

            const monthlyAmount = row.monthly_amount === '' ? 0 : Number(row.monthly_amount);
            if (Number.isNaN(monthlyAmount) || monthlyAmount < 0) {
                setSalaryEditorError(`Monthly amount must be a non-negative number for row ${index + 1}.`);
                return;
            }

            const annualAmountRaw = String(row.annual_amount || '').trim();
            const annualAmount = annualAmountRaw === '' ? null : Number(row.annual_amount);
            if (annualAmount !== null && (Number.isNaN(annualAmount) || annualAmount < 0)) {
                setSalaryEditorError(`Annual amount must be a non-negative number for row ${index + 1}.`);
                return;
            }

            payloadRows.push({
                component_name: row.component_name,
                monthly_amount: monthlyAmount,
                annual_amount: annualAmount,
                taxability: TAXABILITY_OPTIONS.some((item) => item.value === row.taxability) ? row.taxability : 'yes',
                remarks: row.remarks,
                sort_order: row.sort_order,
            });
        }

        setSalarySaving(true);
        setSalaryEditorError('');
        try {
            const response = await saveHrPayrollEmployeeSalaryStructure(employeeUserId, {
                month,
                rows: payloadRows,
            });
            setDetailRow((previous) => {
                if (!previous) return previous;
                return {
                    ...previous,
                    salary_structure: Array.isArray(response?.salary_structure) ? response.salary_structure : [],
                    salary_structure_totals: response?.salary_structure_totals || previous.salary_structure_totals,
                };
            });
            setSalaryEditorOpen(false);
        } catch (requestError) {
            setSalaryEditorError(requestError?.message || 'Unable to save salary structure.');
        } finally {
            setSalarySaving(false);
        }
    };

    const detailOpen = detailLoading || Boolean(detailRow);
    const isEarningsOnlyEditor = breakupEditorMode === 'earnings';
    const isDeductionsOnlyEditor = breakupEditorMode === 'deductions';
    const breakupDialogTitlePrefix = isEarningsOnlyEditor
        ? 'Edit Earnings'
        : isDeductionsOnlyEditor
            ? 'Edit Deductions'
            : 'Edit Earnings & Deductions';
    const breakupSaveButtonLabel = isEarningsOnlyEditor
        ? 'Save Earnings'
        : isDeductionsOnlyEditor
            ? 'Save Deductions'
            : 'Save Earnings & Deductions';

    return (
        <Box sx={{ p: { xs: 2, md: 3 }, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {error ? <Alert severity="error">{error}</Alert> : null}
            {runError ? <Alert severity="error">{runError}</Alert> : null}
            {isPayrollLocked ? <Alert severity="warning">Payroll is locked for this month. Employee-level payroll edits are disabled.</Alert> : null}

            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.25} justifyContent="space-between" alignItems={{ xs: 'stretch', md: 'center' }}>


                    <Stack direction="row" spacing={1}>
                        <FormControl size="small" sx={{ minWidth: 140 }}>
                            <InputLabel>Month</InputLabel>
                            <Select value={month} label="Month" onChange={(event) => setMonth(event.target.value)}>
                                {monthOptions.map((item) => (
                                    <MenuItem key={item.token} value={item.token}>{item.label}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <TextField
                            size="small"
                            label="Search Employee"
                            placeholder="Name, ID, UTR"
                            value={search}
                            onChange={(event) => setSearch(event.target.value)}
                        />
                    </Stack>
                </Stack>
            </Paper>

            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack spacing={1.25}>
                    <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} justifyContent="space-between" alignItems={{ xs: 'flex-start', md: 'center' }}>
                        <Stack direction="row" spacing={1} alignItems="center">
                            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Payroll Run Workflow</Typography>
                            <Chip
                                size="small"
                                color={payrollRunStageColor(runStage)}
                                label={payrollRunStageLabel(runStage)}
                                variant="outlined"
                            />
                            {(runLoading || isRunActionBusy) ? <CircularProgress size={14} /> : null}
                        </Stack>
                        <Typography variant="caption" color="text.secondary">
                            {dashboard.month_label || month} run controls for attendance lock, calculation, approvals, payout export, and month lock.
                        </Typography>
                    </Stack>

                    <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
                        <Chip size="small" variant="outlined" label={`Employees: ${runStats?.employees_count ?? rows.length}`} />
                        <Chip size="small" variant="outlined" color="success" label={`Net Payout: ${formatAmount(runStats?.total_net ?? dashboard.totals?.net)}`} />
                        <Chip size="small" variant="outlined" color={Number(activeRun?.exception_count || 0) > 0 ? 'warning' : 'default'} label={`Exceptions: ${activeRun?.exception_count || 0}`} />
                    </Stack>

                    <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleRunAction('lock_attendance')}
                            disabled={isRunActionBusy || isPayrollLocked || activeRun?.attendance_locked}
                        >
                            {runActionLoading === 'lock_attendance' ? 'Locking...' : 'Lock Attendance'}
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleRunAction('run_calculation')}
                            disabled={isRunActionBusy || isPayrollLocked || !activeRun?.attendance_locked}
                        >
                            {runActionLoading === 'run_calculation' ? 'Calculating...' : 'Run Calculation'}
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleRunAction('approve_hr')}
                            disabled={isRunActionBusy || isPayrollLocked || !activeRun?.calculation_completed || activeRun?.hr_approved}
                        >
                            {runActionLoading === 'approve_hr' ? 'Approving...' : 'Approve HR'}
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleRunAction('approve_finance')}
                            disabled={isRunActionBusy || isPayrollLocked || !activeRun?.hr_approved || activeRun?.finance_approved}
                        >
                            {runActionLoading === 'approve_finance' ? 'Approving...' : 'Approve Finance'}
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleRunAction('generate_payslips')}
                            disabled={isRunActionBusy || isPayrollLocked || !activeRun?.calculation_completed || activeRun?.payslips_generated}
                        >
                            {runActionLoading === 'generate_payslips' ? 'Generating...' : 'Generate Payslips'}
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleRunAction('export_bank_file')}
                            disabled={isRunActionBusy || isPayrollLocked || !activeRun?.finance_approved}
                        >
                            {runActionLoading === 'export_bank_file' ? 'Preparing...' : 'Export Bank File'}
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={() => handleRunAction('post_gl')}
                            disabled={isRunActionBusy || isPayrollLocked || !activeRun?.finance_approved || activeRun?.gl_posted}
                        >
                            {runActionLoading === 'post_gl' ? 'Posting...' : 'Post GL'}
                        </Button>
                        <Button
                            size="small"
                            variant="contained"
                            color="success"
                            onClick={() => handleRunAction('lock_payroll')}
                            disabled={isRunActionBusy || isPayrollLocked || !activeRun?.finance_approved}
                        >
                            {runActionLoading === 'lock_payroll' ? 'Locking...' : 'Lock Payroll'}
                        </Button>
                    </Stack>

                    {runExceptions.length > 0 && (
                        <Box sx={{ p: 1.25, borderRadius: 1.5, bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(251, 146, 60, 0.15)' : '#fff7ed', border: '1px solid', borderColor: (theme) => theme.palette.mode === 'dark' ? '#fb923c' : '#fed7aa' }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 700, color: (theme) => theme.palette.mode === 'dark' ? '#fb923c' : '#9a3412' }}>
                                Payroll Exceptions ({runExceptions.length})
                            </Typography>
                            <Stack spacing={0.35} sx={{ mt: 0.75 }}>
                                {runExceptions.slice(0, 5).map((item, index) => (
                                    <Typography key={`${item.user_id || 'user'}-${index}`} variant="caption" sx={{ color: (theme) => theme.palette.mode === 'dark' ? '#fdba74' : '#7c2d12' }}>
                                        {item.employee_name || item.user_id || 'Employee'}: {item.message || item.issue_code || 'Review required'}
                                    </Typography>
                                ))}
                            </Stack>
                        </Box>
                    )}
                </Stack>
            </Paper>

            <Grid container spacing={1.25}>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                        <Typography variant="caption" color="text.secondary">Employees In Payroll</Typography>
                        <Typography variant="h5" sx={{ fontWeight: 800 }}>{recordsInMonth}</Typography>
                    </Paper>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                        <Typography variant="caption" color="text.secondary">Total Gross</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 800 }}>{formatAmount(dashboard.totals?.gross)}</Typography>
                    </Paper>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                        <Typography variant="caption" color="text.secondary">Total Deductions</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 800, color: 'error.main' }}>{formatAmount(dashboard.totals?.deductions)}</Typography>
                    </Paper>
                </Grid>
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(21, 128, 61, 0.15)' : '#ecfdf3', borderColor: (theme) => theme.palette.mode === 'dark' ? '#22c55e' : '#15803d' }}>
                        <Typography variant="caption" sx={{ color: (theme) => theme.palette.mode === 'dark' ? '#4ade80' : '#166534' }}>Total Net Payout</Typography>
                        <Typography variant="h6" sx={{ fontWeight: 900, color: (theme) => theme.palette.mode === 'dark' ? '#4ade80' : '#166534' }}>{formatAmount(dashboard.totals?.net)}</Typography>
                    </Paper>
                </Grid>
            </Grid>

            <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                <Box sx={{ px: 2, py: 1.25, borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                            {dashboard.month_label || month} Payroll Register
                        </Typography>
                        <Button
                            size="small"
                            variant="outlined"
                            startIcon={<DownloadIcon />}
                            disabled={rows.length === 0}
                            onClick={() => exportPayrollCsv(rows, month)}
                        >
                            Export Register
                        </Button>
                    </Stack>
                </Box>
                <TableContainer sx={{ maxHeight: 560 }}>
                    <Table size="small" stickyHeader>
                        <TableHead>
                            <TableRow>
                                <TableCell>Employee</TableCell>
                                <TableCell>ID</TableCell>
                                <TableCell>PAN</TableCell>
                                <TableCell>UAN</TableCell>
                                <TableCell>Bank</TableCell>
                                <TableCell align="right">Working</TableCell>
                                <TableCell align="right">Present</TableCell>
                                <TableCell align="right">LOP</TableCell>
                                <TableCell align="right">Gross</TableCell>
                                <TableCell align="right">Deductions</TableCell>
                                <TableCell align="right">Net Paid</TableCell>
                                <TableCell>UTR</TableCell>
                                <TableCell>Paid On</TableCell>
                                <TableCell>Status</TableCell>
                                <TableCell align="right">Action</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {rows.map((row) => (
                                <TableRow key={row.user_id} hover>
                                    <TableCell>
                                        <Stack spacing={0.25}>
                                            <Button
                                                variant="text"
                                                size="small"
                                                onClick={() => handleOpenDetails(row.user_id)}
                                                disabled={detailLoading}
                                                sx={{
                                                    p: 0,
                                                    minWidth: 0,
                                                    justifyContent: 'flex-start',
                                                    textTransform: 'none',
                                                    fontWeight: 600,
                                                }}
                                            >
                                                {row.employee_name}
                                            </Button>
                                            <Typography variant="caption" color="text.secondary">{row.department || '-'}</Typography>
                                        </Stack>
                                    </TableCell>
                                    <TableCell>{row.employee_id || '-'}</TableCell>
                                    <TableCell>{row.pan_masked || '-'}</TableCell>
                                    <TableCell>{row.uan || '-'}</TableCell>
                                    <TableCell>{row.bank_account_display || '-'}</TableCell>
                                    <TableCell align="right">{row.working_days}</TableCell>
                                    <TableCell align="right">{row.present_days}</TableCell>
                                    <TableCell align="right" sx={{ color: Number(row.lop_days || 0) > 0 ? 'error.main' : 'inherit' }}>
                                        {row.lop_days}
                                    </TableCell>
                                    <TableCell align="right">{formatNullableAmount(row.gross)}</TableCell>
                                    <TableCell align="right">{formatNullableAmount(row.deductions)}</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 700, color: 'success.dark' }}>
                                        {formatNullableAmount(row.net)}
                                    </TableCell>
                                    <TableCell>{row.utr || '-'}</TableCell>
                                    <TableCell>{formatNullableDate(row.payment_date)}</TableCell>
                                    <TableCell>
                                        <Chip
                                            icon={<PaidIcon />}
                                            size="small"
                                            label={row.status || (row.has_record ? 'Processed' : 'Pending')}
                                            color={payrollStatusColor(row.status)}
                                            variant="outlined"
                                        />
                                    </TableCell>
                                    <TableCell align="right">
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            startIcon={<VisibilityIcon />}
                                            onClick={() => handleOpenDetails(row.user_id)}
                                            disabled={detailLoading}
                                        >
                                            Details
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {rows.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={15}>
                                        <Typography variant="body2" color="text.secondary" sx={{ py: 1.5 }}>
                                            {loading ? 'Loading payroll register...' : 'No payroll rows found for selected filters.'}
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Paper>

            <Dialog open={detailOpen} onClose={handleCloseDetails} maxWidth="md" fullWidth>
                <DialogTitle>
                    {detailRow ? `${detailRow.employee?.employee_name || 'Employee'} • ${detailRow.month_label || month}` : 'Payroll Details'}
                </DialogTitle>
                <DialogContent dividers>
                    {detailLoading && (
                        <Box sx={{ py: 5, display: 'flex', justifyContent: 'center' }}>
                            <CircularProgress size={28} />
                        </Box>
                    )}
                    {detailRow && isPayrollLocked && (
                        <Alert severity="warning" sx={{ mb: 1.25 }}>
                            Payroll is locked for this month. You can review data but cannot edit salary structure, earnings, or deductions.
                        </Alert>
                    )}
                    {detailRow && !detailRow.has_record && (
                        <Alert severity="info" sx={{ mb: 1.25 }}>
                            Payroll record is not generated for this employee in the selected month yet. Values remain pending until calculation creates a record.
                        </Alert>
                    )}
                    {detailRow && (
                        <Grid container spacing={1.5}>
                            <Grid size={{ xs: 12 }}>
                                <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2 }}>
                                    <Grid container spacing={1.25}>
                                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                            <Typography variant="caption" color="text.secondary">Employee ID</Typography>
                                            <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                                {detailRow.employee?.employee_id || '-'}
                                            </Typography>
                                        </Grid>
                                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                            <Typography variant="caption" color="text.secondary">PAN</Typography>
                                            <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                                {detailRow.employee?.pan_masked || '-'}
                                            </Typography>
                                        </Grid>
                                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                            <Typography variant="caption" color="text.secondary">UAN</Typography>
                                            <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                                {detailRow.employee?.uan || '-'}
                                            </Typography>
                                        </Grid>
                                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                            <Typography variant="caption" color="text.secondary">Bank</Typography>
                                            <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                                {detailRow.employee?.bank_account_display || '-'}
                                            </Typography>
                                        </Grid>
                                    </Grid>
                                </Paper>
                            </Grid>
                            <Grid size={{ xs: 12, md: 6 }}>
                                <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                                    <Box sx={{ px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(59, 130, 246, 0.15)' : '#f0f9ff' }}>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Earnings</Typography>
                                            <Button
                                                size="small"
                                                startIcon={<EditIcon />}
                                                onClick={() => handleOpenBreakupEditor('earnings')}
                                                disabled={isPayrollLocked}
                                            >
                                                Edit
                                            </Button>
                                        </Stack>
                                    </Box>
                                    <Table size="small">
                                        <TableBody>
                                            {earningsRows.map((item, index) => (
                                                <TableRow key={`${item.component || 'earning'}-${index}`}>
                                                    <TableCell>{item.component}</TableCell>
                                                    <TableCell align="right">{formatAmount(item.amount)}</TableCell>
                                                </TableRow>
                                            ))}
                                            <TableRow>
                                                <TableCell sx={{ fontWeight: 800 }}>Total Earnings</TableCell>
                                                <TableCell align="right" sx={{ fontWeight: 800 }}>{formatAmount(earningsTotal)}</TableCell>
                                            </TableRow>
                                        </TableBody>
                                    </Table>
                                </Paper>
                            </Grid>
                            <Grid size={{ xs: 12, md: 6 }}>
                                <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                                    <Box sx={{ px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(251, 146, 60, 0.15)' : '#fff7ed' }}>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Deductions</Typography>
                                            <Button
                                                size="small"
                                                startIcon={<EditIcon />}
                                                onClick={() => handleOpenBreakupEditor('deductions')}
                                                disabled={isPayrollLocked}
                                            >
                                                Edit
                                            </Button>
                                        </Stack>
                                    </Box>
                                    <Table size="small">
                                        <TableBody>
                                            {deductionsRows.map((item, index) => (
                                                <TableRow key={`${item.component || 'deduction'}-${index}`}>
                                                    <TableCell>{item.component}</TableCell>
                                                    <TableCell align="right">{formatAmount(item.amount)}</TableCell>
                                                </TableRow>
                                            ))}
                                            <TableRow>
                                                <TableCell sx={{ fontWeight: 800 }}>Total Deductions</TableCell>
                                                <TableCell align="right" sx={{ fontWeight: 800 }}>{formatAmount(deductionsTotal)}</TableCell>
                                            </TableRow>
                                        </TableBody>
                                    </Table>
                                </Paper>
                            </Grid>
                            <Grid size={{ xs: 12 }}>
                                <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                                    <Box sx={{ px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'background.default' : '#f8fafc' }}>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Salary Structure</Typography>
                                            <Button size="small" startIcon={<EditIcon />} onClick={handleOpenSalaryEditor} disabled={isPayrollLocked}>
                                                Edit
                                            </Button>
                                        </Stack>
                                    </Box>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Component</TableCell>
                                                <TableCell align="right">Monthly</TableCell>
                                                <TableCell align="right">Annual</TableCell>
                                                <TableCell>Taxability</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {salaryStructureRows.map((item, index) => (
                                                <TableRow key={item.id || `${item.component_name || 'component'}-${index}`}>
                                                    <TableCell>{item.component_name || '-'}</TableCell>
                                                    <TableCell align="right">{formatAmount(item.monthly_amount)}</TableCell>
                                                    <TableCell align="right">{formatAmount(item.annual_amount)}</TableCell>
                                                    <TableCell>
                                                        {item.taxability === 'no' ? 'Non-Taxable' : item.taxability === 'partial' ? 'Partly Taxable' : 'Taxable'}
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                            {salaryStructureRows.length === 0 && (
                                                <TableRow>
                                                    <TableCell colSpan={4}>
                                                        <Typography variant="body2" color="text.secondary" sx={{ py: 1 }}>
                                                            Salary structure is not defined yet.
                                                        </Typography>
                                                    </TableCell>
                                                </TableRow>
                                            )}
                                            {salaryStructureRows.length > 0 && (
                                                <TableRow>
                                                    <TableCell sx={{ fontWeight: 800 }}>Total CTC</TableCell>
                                                    <TableCell align="right" sx={{ fontWeight: 800 }}>{formatAmount(salaryStructureTotals.monthly)}</TableCell>
                                                    <TableCell align="right" sx={{ fontWeight: 800 }}>{formatAmount(salaryStructureTotals.annual)}</TableCell>
                                                    <TableCell />
                                                </TableRow>
                                            )}
                                        </TableBody>
                                    </Table>
                                </Paper>
                            </Grid>
                            {hrExpensesRows.length > 0 && (
                                <Grid size={{ xs: 12 }}>
                                    <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2, bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(59, 130, 246, 0.15)' : '#eff6ff', borderColor: (theme) => theme.palette.mode === 'dark' ? '#60a5fa' : '#3b82f6' }}>
                                        <Typography variant="subtitle2" sx={{ fontWeight: 700, color: (theme) => theme.palette.mode === 'dark' ? '#60a5fa' : '#1d4ed8', mb: 0.75 }}>
                                            Expense Reimbursements (Auto-included in Payroll)
                                        </Typography>
                                        <Stack spacing={0.25}>
                                            {hrExpensesRows.map((item, index) => (
                                                <Stack key={`${item.component || 'exp'}-${index}`} direction="row" justifyContent="space-between">
                                                    <Typography variant="body2">{item.component}</Typography>
                                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{formatAmount(item.amount)}</Typography>
                                                </Stack>
                                            ))}
                                            <Stack direction="row" justifyContent="space-between" sx={{ pt: 0.5, borderTop: '1px solid', borderColor: 'divider' }}>
                                                <Typography variant="body2" sx={{ fontWeight: 800, color: (theme) => theme.palette.mode === 'dark' ? '#60a5fa' : '#1d4ed8' }}>Total Expense Reimbursement</Typography>
                                                <Typography variant="body2" sx={{ fontWeight: 800, color: (theme) => theme.palette.mode === 'dark' ? '#60a5fa' : '#1d4ed8' }}>{formatAmount(expenseTotal)}</Typography>
                                            </Stack>
                                        </Stack>
                                        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                                            Automatically included from HR-approved expense claims for this month (Dept Head Approved / Finance Reviewed).
                                        </Typography>
                                    </Paper>
                                </Grid>
                            )}
                            <Grid size={{ xs: 12 }}>
                                <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2, bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(21, 128, 61, 0.15)' : '#ecfdf3', borderColor: (theme) => theme.palette.mode === 'dark' ? '#22c55e' : '#15803d' }}>
                                    <Typography variant="caption" sx={{ color: (theme) => theme.palette.mode === 'dark' ? '#4ade80' : '#166534' }}>Net Pay</Typography>
                                    <Typography variant="h5" sx={{ fontWeight: 900, color: (theme) => theme.palette.mode === 'dark' ? '#4ade80' : '#166534' }}>
                                        {formatNullableAmount(detailRow.net)}
                                    </Typography>
                                    <Typography variant="body2" sx={{ color: (theme) => theme.palette.mode === 'dark' ? '#4ade80' : '#166534' }}>
                                        UTR {detailRow.utr || '-'} • Paid on {formatNullableDate(detailRow.payment_date)}
                                    </Typography>
                                </Paper>
                            </Grid>
                        </Grid>
                    )}
                </DialogContent>
                <DialogActions>
                    <Button
                        variant="outlined"
                        startIcon={<EditIcon />}
                        onClick={() => handleOpenBreakupEditor('both')}
                        disabled={!detailRow || detailLoading || isPayrollLocked}
                    >
                        Edit Earnings & Deductions
                    </Button>
                    <Button
                        variant="outlined"
                        startIcon={<EditIcon />}
                        onClick={handleOpenSalaryEditor}
                        disabled={!detailRow || detailLoading || isPayrollLocked}
                    >
                        Define Salary Structure
                    </Button>
                    <Button onClick={handleCloseDetails}>Close</Button>
                </DialogActions>
            </Dialog>

            <Dialog
                open={breakupEditorOpen}
                onClose={() => {
                    if (!breakupSaving) {
                        setBreakupEditorOpen(false);
                        setBreakupEditorError('');
                    }
                }}
                maxWidth="lg"
                fullWidth
            >
                <DialogTitle>
                    {breakupDialogTitlePrefix} {detailRow?.employee?.employee_name ? `• ${detailRow.employee.employee_name}` : ''}
                </DialogTitle>
                <DialogContent dividers>
                    {breakupEditorError ? <Alert severity="error" sx={{ mb: 1.5 }}>{breakupEditorError}</Alert> : null}

                    <Grid container spacing={1.5}>
                        {!isDeductionsOnlyEditor && (
                            <Grid size={{ xs: 12, md: isEarningsOnlyEditor ? 12 : 6 }}>
                                <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                                    <Box sx={{ px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(59, 130, 246, 0.15)' : '#f0f9ff' }}>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Earnings</Typography>
                                            <Button size="small" startIcon={<AddIcon />} onClick={() => handleAddBreakupRow('earnings')} disabled={isPayrollLocked}>
                                                Add
                                            </Button>
                                        </Stack>
                                    </Box>
                                    <TableContainer>
                                        <Table size="small">
                                            <TableHead>
                                                <TableRow>
                                                    <TableCell>Component</TableCell>
                                                    <TableCell>Amount</TableCell>
                                                    <TableCell align="right">Action</TableCell>
                                                </TableRow>
                                            </TableHead>
                                            <TableBody>
                                                {earningsEditorRows.map((row) => (
                                                    <TableRow key={row._localId}>
                                                        <TableCell>
                                                            <TextField
                                                                size="small"
                                                                fullWidth
                                                                placeholder="Basic Pay"
                                                                value={row.component}
                                                                disabled={isPayrollLocked}
                                                                onChange={(event) => handleBreakupRowFieldChange('earnings', row._localId, 'component', event.target.value)}
                                                            />
                                                        </TableCell>
                                                        <TableCell>
                                                            <TextField
                                                                size="small"
                                                                fullWidth
                                                                type="number"
                                                                inputProps={{ min: 0, step: '0.01' }}
                                                                value={row.amount}
                                                                disabled={isPayrollLocked}
                                                                onChange={(event) => handleBreakupRowFieldChange('earnings', row._localId, 'amount', event.target.value)}
                                                            />
                                                        </TableCell>
                                                        <TableCell align="right">
                                                            <IconButton
                                                                color="error"
                                                                onClick={() => handleRemoveBreakupRow('earnings', row._localId)}
                                                                disabled={isPayrollLocked}
                                                                aria-label="remove earning row"
                                                            >
                                                                <DeleteOutlineIcon fontSize="small" />
                                                            </IconButton>
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                </Paper>
                            </Grid>
                        )}

                        {!isEarningsOnlyEditor && (
                            <Grid size={{ xs: 12, md: isDeductionsOnlyEditor ? 12 : 6 }}>
                                <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                                    <Box sx={{ px: 1.5, py: 1, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => theme.palette.mode === 'dark' ? 'rgba(251, 146, 60, 0.15)' : '#fff7ed' }}>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                            <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Deductions</Typography>
                                            <Button size="small" startIcon={<AddIcon />} onClick={() => handleAddBreakupRow('deductions')} disabled={isPayrollLocked}>
                                                Add
                                            </Button>
                                        </Stack>
                                    </Box>
                                    <TableContainer>
                                        <Table size="small">
                                            <TableHead>
                                                <TableRow>
                                                    <TableCell>Component</TableCell>
                                                    <TableCell>Amount</TableCell>
                                                    <TableCell align="right">Action</TableCell>
                                                </TableRow>
                                            </TableHead>
                                            <TableBody>
                                                {deductionsEditorRows.map((row) => (
                                                    <TableRow key={row._localId}>
                                                        <TableCell>
                                                            <TextField
                                                                size="small"
                                                                fullWidth
                                                                placeholder="Provident Fund"
                                                                value={row.component}
                                                                disabled={isPayrollLocked}
                                                                onChange={(event) => handleBreakupRowFieldChange('deductions', row._localId, 'component', event.target.value)}
                                                            />
                                                        </TableCell>
                                                        <TableCell>
                                                            <TextField
                                                                size="small"
                                                                fullWidth
                                                                type="number"
                                                                inputProps={{ min: 0, step: '0.01' }}
                                                                value={row.amount}
                                                                disabled={isPayrollLocked}
                                                                onChange={(event) => handleBreakupRowFieldChange('deductions', row._localId, 'amount', event.target.value)}
                                                            />
                                                        </TableCell>
                                                        <TableCell align="right">
                                                            <IconButton
                                                                color="error"
                                                                onClick={() => handleRemoveBreakupRow('deductions', row._localId)}
                                                                disabled={isPayrollLocked}
                                                                aria-label="remove deduction row"
                                                            >
                                                                <DeleteOutlineIcon fontSize="small" />
                                                            </IconButton>
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                </Paper>
                            </Grid>
                        )}
                    </Grid>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setBreakupEditorOpen(false)} disabled={breakupSaving}>Cancel</Button>
                    <Button
                        variant="contained"
                        startIcon={<SaveIcon />}
                        onClick={handleSaveBreakup}
                        disabled={breakupSaving || isPayrollLocked}
                    >
                        {breakupSaving ? 'Saving...' : breakupSaveButtonLabel}
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog
                open={salaryEditorOpen}
                onClose={() => {
                    if (!salarySaving) {
                        setSalaryEditorOpen(false);
                        setSalaryEditorError('');
                    }
                }}
                maxWidth="lg"
                fullWidth
            >
                <DialogTitle>
                    Define Salary Structure {detailRow?.employee?.employee_name ? `• ${detailRow.employee.employee_name}` : ''}
                </DialogTitle>
                <DialogContent dividers>
                    {salaryEditorError ? <Alert severity="error" sx={{ mb: 1.5 }}>{salaryEditorError}</Alert> : null}
                    <Stack direction="row" justifyContent="flex-end" sx={{ mb: 1 }}>
                        <Button size="small" startIcon={<AddIcon />} onClick={handleAddSalaryRow} disabled={isPayrollLocked}>
                            Add Component
                        </Button>
                    </Stack>
                    <TableContainer>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell sx={{ minWidth: 220 }}>Component</TableCell>
                                    <TableCell sx={{ minWidth: 130 }}>Monthly Amount</TableCell>
                                    <TableCell sx={{ minWidth: 130 }}>Annual Amount</TableCell>
                                    <TableCell sx={{ minWidth: 140 }}>Taxability</TableCell>
                                    <TableCell sx={{ minWidth: 220 }}>Remarks</TableCell>
                                    <TableCell align="right">Action</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {salaryEditorRows.map((row) => (
                                    <TableRow key={row._localId}>
                                        <TableCell>
                                            <TextField
                                                size="small"
                                                fullWidth
                                                placeholder="Basic Salary"
                                                value={row.component_name}
                                                disabled={isPayrollLocked}
                                                onChange={(event) => handleSalaryRowFieldChange(row._localId, 'component_name', event.target.value)}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <TextField
                                                size="small"
                                                fullWidth
                                                type="number"
                                                inputProps={{ min: 0, step: '0.01' }}
                                                value={row.monthly_amount}
                                                disabled={isPayrollLocked}
                                                onChange={(event) => handleSalaryRowFieldChange(row._localId, 'monthly_amount', event.target.value)}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <TextField
                                                size="small"
                                                fullWidth
                                                type="number"
                                                inputProps={{ min: 0, step: '0.01' }}
                                                value={row.annual_amount}
                                                disabled={isPayrollLocked}
                                                onChange={(event) => handleSalaryRowFieldChange(row._localId, 'annual_amount', event.target.value)}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Select
                                                size="small"
                                                fullWidth
                                                value={row.taxability}
                                                disabled={isPayrollLocked}
                                                onChange={(event) => handleSalaryRowFieldChange(row._localId, 'taxability', event.target.value)}
                                            >
                                                {TAXABILITY_OPTIONS.map((item) => (
                                                    <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>
                                                ))}
                                            </Select>
                                        </TableCell>
                                        <TableCell>
                                            <TextField
                                                size="small"
                                                fullWidth
                                                placeholder="Optional remarks"
                                                value={row.remarks}
                                                disabled={isPayrollLocked}
                                                onChange={(event) => handleSalaryRowFieldChange(row._localId, 'remarks', event.target.value)}
                                            />
                                        </TableCell>
                                        <TableCell align="right">
                                            <IconButton
                                                color="error"
                                                onClick={() => handleRemoveSalaryRow(row._localId)}
                                                disabled={isPayrollLocked}
                                                aria-label="remove salary component"
                                            >
                                                <DeleteOutlineIcon fontSize="small" />
                                            </IconButton>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSalaryEditorOpen(false)} disabled={salarySaving}>Cancel</Button>
                    <Button
                        variant="contained"
                        startIcon={<SaveIcon />}
                        onClick={handleSaveSalaryStructure}
                        disabled={salarySaving || isPayrollLocked}
                    >
                        {salarySaving ? 'Saving...' : 'Save Structure'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}
