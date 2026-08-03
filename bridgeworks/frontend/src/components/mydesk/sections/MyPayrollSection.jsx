import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    alpha,
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
    Tab,
    Tabs,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    TextField,
    Typography,
} from '@mui/material';
import {
    CheckCircle as CheckCircleIcon,
    Download as DownloadIcon,
} from '@mui/icons-material';
import {
    getMyPayrollOverview,
    raiseMyPayrollDispute,
    saveMyPayrollDeclarations,
} from '../mydeskService';

function formatAmount(value) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0,
    }).format(Number(value || 0));
}

function formatDate(value) {
    if (!value) return '-';
    const parsed = new Date(`${value}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
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
        items.push({
            token: `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}`,
            label: value.toLocaleString(undefined, { month: 'short', year: 'numeric' }),
        });
    }
    return items;
}

function humanizeTaxability(value) {
    const normalized = String(value || '').toLowerCase();
    if (normalized === 'yes') return 'Yes';
    if (normalized === 'no') return 'No';
    if (normalized === 'partial') return 'Partly';
    return value || '-';
}

function taxabilityColor(value) {
    const normalized = String(value || '').toLowerCase();
    if (normalized === 'yes') return 'warning';
    if (normalized === 'no') return 'success';
    return 'info';
}

export default function MyPayrollSection() {
    const monthOptions = useMemo(() => buildMonthOptions(18), []);
    const [tab, setTab] = useState(0);
    const [selectedMonth, setSelectedMonth] = useState(monthOptions[0]?.token || currentMonthToken());
    const [selectedRegime, setSelectedRegime] = useState('new');
    const [overview, setOverview] = useState(null);
    const [declarations, setDeclarations] = useState([]);
    const [loading, setLoading] = useState(false);
    const [savingDeclarations, setSavingDeclarations] = useState(false);
    const [raisingDispute, setRaisingDispute] = useState(false);
    const [disputeText, setDisputeText] = useState('');
    const [error, setError] = useState('');

    const loadOverview = useCallback(async () => {
        setLoading(true);
        setError('');
        try {
            const response = await getMyPayrollOverview({
                month: selectedMonth,
                regime: selectedRegime,
            });
            setOverview(response);

            if (Array.isArray(response?.declarations)) {
                setDeclarations(response.declarations.map((item) => ({
                    ...item,
                    declared_amount: Number(item.declared_amount || 0),
                    max_limit: Number(item.max_limit || 0),
                    proof_file_name: item.proof_file_name || '',
                })));
            } else {
                setDeclarations([]);
            }

            const responseRegime = String(response?.tax_summary?.regime || '').toLowerCase();
            if (responseRegime && responseRegime !== selectedRegime) {
                setSelectedRegime(responseRegime);
            }
        } catch (requestError) {
            setOverview(null);
            setDeclarations([]);
            setError(requestError?.message || 'Unable to load payroll overview.');
        } finally {
            setLoading(false);
        }
    }, [selectedMonth, selectedRegime]);

    useEffect(() => {
        loadOverview();
    }, [loadOverview]);

    const payslip = overview?.payslip || {};
    const payslipAvailable = Boolean(payslip?.available);
    const salaryHistoryRows = Array.isArray(overview?.salary_history) ? overview.salary_history : [];
    const ctcStructureRows = Array.isArray(overview?.salary_structure) ? overview.salary_structure : [];
    const earningsRows = Array.isArray(payslip?.earnings) ? payslip.earnings : [];
    const deductionRows = Array.isArray(payslip?.deductions) ? payslip.deductions : [];
    const hrExpenseRows = Array.isArray(payslip?.hr_expenses) ? payslip.hr_expenses : [];
    const hrExpenseLabels = new Set(hrExpenseRows.map((r) => r.component));
    const hrExpenseTotal = Number(payslip?.expense_total || 0);

    const gross = Number(payslip.gross_amount || 0);
    const deductions = Number(payslip.total_deductions || 0);
    const netPay = Number(payslip.net_amount || 0);

    const renderPayslipAmount = (value) => (payslipAvailable ? formatAmount(value) : '-');
    const renderPayslipDays = (value) => (payslipAvailable ? Number(value || 0).toFixed(2) : '-');

    const updateDeclarationRow = (index, key, value) => {
        setDeclarations((previous) => previous.map((item, itemIndex) => {
            if (itemIndex !== index) return item;
            return { ...item, [key]: value };
        }));
    };

    const submitDeclarations = async () => {
        if (!overview) return;

        setSavingDeclarations(true);
        setError('');
        try {
            const response = await saveMyPayrollDeclarations({
                financial_year: overview.financial_year,
                regime: selectedRegime,
                rows: declarations.map((row) => ({
                    id: row.id,
                    declared_amount: Number(row.declared_amount || 0),
                    proof_file_name: row.proof_file_name || '',
                    status: row.status || 'draft',
                })),
                submit: true,
            });

            if (Array.isArray(response?.rows)) {
                setDeclarations(response.rows.map((item) => ({
                    ...item,
                    declared_amount: Number(item.declared_amount || 0),
                    max_limit: Number(item.max_limit || 0),
                    proof_file_name: item.proof_file_name || '',
                })));
            }

            await loadOverview();
        } catch (requestError) {
            setError(requestError?.message || 'Unable to submit declarations.');
        } finally {
            setSavingDeclarations(false);
        }
    };

    const openPayslipPdf = (url) => {
        const safeUrl = String(url || '').trim();
        if (!safeUrl) return;
        window.open(safeUrl, '_blank', 'noopener,noreferrer');
    };

    const submitDispute = async () => {
        const query = disputeText.trim();
        if (!query || !selectedMonth) return;

        setRaisingDispute(true);
        setError('');
        try {
            await raiseMyPayrollDispute({
                month: selectedMonth,
                query,
            });
            setDisputeText('');
            await loadOverview();
        } catch (requestError) {
            setError(requestError?.message || 'Unable to raise payroll dispute.');
        } finally {
            setRaisingDispute(false);
        }
    };

    return (
        <Stack spacing={2}>
            {error ? <Alert severity="error">{error}</Alert> : null}

            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} justifyContent="space-between" alignItems={{ xs: 'stretch', md: 'center' }}>

                    <Stack direction="row" spacing={1} alignItems="center">
                        <FormControl size="small" sx={{ minWidth: 150 }}>
                            <InputLabel>Month</InputLabel>
                            <Select value={selectedMonth} label="Month" onChange={(event) => setSelectedMonth(event.target.value)}>
                                {monthOptions.map((item) => (
                                    <MenuItem key={item.token} value={item.token}>{item.label}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                        <Chip
                            icon={<CheckCircleIcon />}
                            label={payslipAvailable && payslip.payment_date ? `Latest Credit: ${formatDate(payslip.payment_date)}` : 'Latest Credit: Pending'}
                            color={payslipAvailable && payslip.payment_date ? 'success' : 'default'}
                            variant="outlined"
                        />
                    </Stack>
                </Stack>
            </Paper>

            {loading && !overview ? (
                <Paper variant="outlined" sx={{ p: 4, borderRadius: 2, display: 'flex', justifyContent: 'center' }}>
                    <CircularProgress size={28} />
                </Paper>
            ) : null}

            <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable" scrollButtons="auto">
                    <Tab label="Payslip" />
                    <Tab label="Salary History" />
                    <Tab label="Salary Structure" />

                </Tabs>
            </Paper>

            {tab === 0 && (
                <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                    <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'action.hover' }}>
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ xs: 'flex-start', sm: 'center' }} justifyContent="space-between">
                            <Typography variant="body2" sx={{ mt: 0.5 }}>Payslip for {payslip.month_label || selectedMonth}</Typography>
                            <Button
                                size="small"
                                variant="outlined"
                                startIcon={<DownloadIcon />}
                                disabled={!payslipAvailable || !payslip?.payslip_pdf_url}
                                onClick={() => openPayslipPdf(payslip?.payslip_pdf_url)}
                            >
                                Download PDF
                            </Button>
                        </Stack>
                    </Box>

                    <Box sx={{ p: 2 }}>
                        {!payslipAvailable ? (
                            <Alert severity="info" sx={{ mb: 1.5 }}>
                                {payslip?.message || 'Payslip is not available for the selected month yet.'}
                            </Alert>
                        ) : null}

                        <Grid container spacing={1.25}>
                            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2 }}>
                                    <Typography variant="caption" color="text.secondary">Employee ID</Typography>
                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{overview?.employee?.employee_id || '-'}</Typography>
                                </Paper>
                            </Grid>
                            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2 }}>
                                    <Typography variant="caption" color="text.secondary">PAN</Typography>
                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{overview?.employee?.pan_masked || '-'}</Typography>
                                </Paper>
                            </Grid>
                            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2 }}>
                                    <Typography variant="caption" color="text.secondary">UAN</Typography>
                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{overview?.employee?.uan || '-'}</Typography>
                                </Paper>
                            </Grid>
                            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2 }}>
                                    <Typography variant="caption" color="text.secondary">Bank A/C</Typography>
                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{overview?.employee?.bank_account_display || '-'}</Typography>
                                </Paper>
                            </Grid>
                        </Grid>

                        <Grid container spacing={1.25} sx={{ mt: 0.25 }}>
                            <Grid size={{ xs: 4 }}>
                                <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2, textAlign: 'center' }}>
                                    <Typography variant="caption" color="text.secondary">Working Days</Typography>
                                    <Typography variant="h6" sx={{ fontWeight: 800 }}>{renderPayslipDays(payslip.working_days)}</Typography>
                                </Paper>
                            </Grid>
                            <Grid size={{ xs: 4 }}>
                                <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2, textAlign: 'center' }}>
                                    <Typography variant="caption" color="text.secondary">Present Days</Typography>
                                    <Typography variant="h6" sx={{ fontWeight: 800 }}>{renderPayslipDays(payslip.present_days)}</Typography>
                                </Paper>
                            </Grid>
                            <Grid size={{ xs: 4 }}>
                                <Paper variant="outlined" sx={{ p: 1.25, borderRadius: 2, textAlign: 'center' }}>
                                    <Typography variant="caption" color="text.secondary">LOP Days</Typography>
                                    <Typography variant="h6" sx={{ fontWeight: 800, color: 'error.main' }}>{renderPayslipDays(payslip.lop_days)}</Typography>
                                </Paper>
                            </Grid>
                        </Grid>

                        <Grid container spacing={1.5} sx={{ mt: 0.5 }}>
                            <Grid size={{ xs: 12, md: 6 }}>
                                <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                                    <Box sx={{ px: 1.5, py: 1.25, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => alpha(theme.palette.info.main, theme.palette.mode === 'dark' ? 0.12 : 0.04) }}>
                                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Earnings</Typography>
                                    </Box>
                                    <TableContainer>
                                        <Table size="small">
                                            <TableBody>
                                                {earningsRows.map((row) => (
                                                    <TableRow key={row.component}>
                                                        <TableCell>{row.component}</TableCell>
                                                        <TableCell align="right" sx={{ fontWeight: 600 }}>{renderPayslipAmount(row.amount)}</TableCell>
                                                    </TableRow>
                                                ))}
                                                <TableRow>
                                                    <TableCell sx={{ fontWeight: 800 }}>Total Earnings</TableCell>
                                                    <TableCell align="right" sx={{ fontWeight: 800 }}>{renderPayslipAmount(gross)}</TableCell>
                                                </TableRow>
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                </Paper>
                            </Grid>

                            <Grid size={{ xs: 12, md: 6 }}>
                                <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                                    <Box sx={{ px: 1.5, py: 1.25, borderBottom: '1px solid', borderColor: 'divider', bgcolor: (theme) => alpha(theme.palette.warning.main, theme.palette.mode === 'dark' ? 0.12 : 0.04) }}>
                                        <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>Deductions</Typography>
                                    </Box>
                                    <TableContainer>
                                        <Table size="small">
                                            <TableBody>
                                                {deductionRows.map((row) => (
                                                    <TableRow key={row.component}>
                                                        <TableCell>{row.component}</TableCell>
                                                        <TableCell align="right" sx={{ fontWeight: 600 }}>{renderPayslipAmount(row.amount)}</TableCell>
                                                    </TableRow>
                                                ))}
                                                <TableRow>
                                                    <TableCell sx={{ fontWeight: 800 }}>Total Deductions</TableCell>
                                                    <TableCell align="right" sx={{ fontWeight: 800 }}>{renderPayslipAmount(deductions)}</TableCell>
                                                </TableRow>
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                </Paper>
                            </Grid>
                        </Grid>

                        {hrExpenseTotal > 0 && (
                            <Paper
                                variant="outlined"
                                sx={{
                                    mt: 1.5,
                                    p: 1.5,
                                    borderRadius: 2,
                                    bgcolor: (theme) => alpha(theme.palette.info.main, theme.palette.mode === 'dark' ? 0.12 : 0.04),
                                    borderColor: 'info.main',
                                }}
                            >
                                <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'info.main', mb: 1 }}>
                                    Expense Reimbursements Included
                                </Typography>
                                {hrExpenseRows.map((row) => (
                                    <Stack key={row.component} direction="row" justifyContent="space-between" sx={{ mb: 0.25 }}>
                                        <Typography variant="body2">{row.component}</Typography>
                                        <Typography variant="body2" sx={{ fontWeight: 700 }}>
                                            {renderPayslipAmount(row.amount)}
                                        </Typography>
                                    </Stack>
                                ))}
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
                                    Auto-included from your approved company expense claims this month.
                                </Typography>
                            </Paper>
                        )}

                        <Paper
                            variant="outlined"
                            sx={{
                                mt: 1.5,
                                p: 1.5,
                                borderRadius: 2,
                                borderColor: 'success.main',
                                bgcolor: (theme) => alpha(theme.palette.success.main, theme.palette.mode === 'dark' ? 0.12 : 0.04),
                            }}
                        >
                            <Typography variant="caption" sx={{ color: 'success.main' }}>Net Pay</Typography>
                            <Typography variant="h4" sx={{ fontWeight: 900, color: 'success.main', lineHeight: 1.1 }}>
                                {renderPayslipAmount(netPay)}
                            </Typography>
                            <Typography variant="body2" sx={{ color: 'success.main' }}>
                                {payslipAvailable
                                    ? `(${formatAmount(netPay)} credited to ${overview?.employee?.bank_account_display || '-'})`
                                    : 'Net pay will appear once the payslip is generated and payroll is locked.'}
                            </Typography>
                        </Paper>

                        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, mt: 1.5 }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>Payment Metadata</Typography>
                            <Grid container spacing={1.25}>
                                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                    <Typography variant="caption" color="text.secondary">Payment Date</Typography>
                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{payslipAvailable ? formatDate(payslip.payment_date) : '-'}</Typography>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                    <Typography variant="caption" color="text.secondary">Mode</Typography>
                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{payslipAvailable ? (payslip.payment_mode || '-') : '-'}</Typography>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                    <Typography variant="caption" color="text.secondary">UTR Reference</Typography>
                                    <Typography variant="body2" sx={{ fontWeight: 700 }}>{payslipAvailable ? (payslip.utr_reference || '-') : '-'}</Typography>
                                </Grid>
                                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                    <Typography variant="caption" color="text.secondary">Status</Typography>
                                    <Typography
                                        variant="body2"
                                        sx={{
                                            fontWeight: 700,
                                            color: payslip.status === 'Pending' ? 'warning.main' : 'success.main',
                                        }}
                                    >
                                        {payslip.status || '-'}
                                    </Typography>
                                </Grid>
                            </Grid>
                        </Paper>

                        <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2, mt: 1.5 }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>Payslip Query / Dispute</Typography>
                            {payslip?.dispute_status === 'open' ? (
                                <Alert severity="warning" sx={{ mb: 1 }}>
                                    Query is open. HR/Finance will respond soon.
                                </Alert>
                            ) : null}
                            {payslip?.dispute_status === 'resolved' ? (
                                <Alert severity="success" sx={{ mb: 1 }}>
                                    Query resolved.
                                </Alert>
                            ) : null}
                            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
                                <TextField
                                    fullWidth
                                    size="small"
                                    placeholder="Raise a query for this payslip"
                                    value={disputeText}
                                    onChange={(event) => setDisputeText(event.target.value)}
                                    disabled={!payslipAvailable || raisingDispute}
                                />
                                <Button
                                    variant="outlined"
                                    disabled={!payslipAvailable || !disputeText.trim() || raisingDispute}
                                    onClick={submitDispute}
                                >
                                    {raisingDispute ? 'Submitting...' : 'Raise Query'}
                                </Button>
                            </Stack>
                            {!payslipAvailable ? (
                                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                                    Query can be raised only after payslip generation.
                                </Typography>
                            ) : null}
                        </Paper>
                    </Box>
                </Paper>
            )}

            {tab === 1 && (
                <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>

                    <TableContainer sx={{ maxHeight: 520 }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell>Month</TableCell>
                                    <TableCell align="right">Gross</TableCell>
                                    <TableCell align="right">Deductions</TableCell>
                                    <TableCell align="right">Net Paid</TableCell>
                                    <TableCell>Payment Date</TableCell>
                                    <TableCell>UTR</TableCell>
                                    <TableCell align="right">Payslip</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {salaryHistoryRows.map((row) => (
                                    <TableRow key={row.month} hover>
                                        <TableCell sx={{ fontWeight: 600 }}>{row.month_label || row.month}</TableCell>
                                        <TableCell align="right">{row.available ? formatAmount(row.gross_amount) : '-'}</TableCell>
                                        <TableCell align="right">{row.available ? formatAmount(row.total_deductions) : '-'}</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 700, color: row.available ? 'success.dark' : 'text.secondary' }}>
                                            {row.available ? formatAmount(row.net_amount) : '-'}
                                        </TableCell>
                                        <TableCell>{row.available ? formatDate(row.payment_date) : '-'}</TableCell>
                                        <TableCell>{row.available ? (row.utr_reference || '-') : '-'}</TableCell>
                                        <TableCell align="right">
                                            <Button
                                                size="small"
                                                variant="outlined"
                                                startIcon={<DownloadIcon />}
                                                disabled={!row.available || !row.payslip_pdf_url}
                                                onClick={() => openPayslipPdf(row.payslip_pdf_url)}
                                            >
                                                PDF
                                            </Button>
                                        </TableCell>
                                    </TableRow>
                                ))}
                                {salaryHistoryRows.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={7}>
                                            <Typography variant="body2" color="text.secondary" sx={{ py: 1.5 }}>
                                                {loading ? 'Loading salary history...' : 'No salary history available.'}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}



            {tab === 2 && (
                <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>

                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>Component</TableCell>
                                    <TableCell align="right">Monthly</TableCell>
                                    <TableCell align="right">Annual</TableCell>
                                    <TableCell>Taxability</TableCell>
                                    <TableCell>Remarks</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {ctcStructureRows.map((row) => (
                                    <TableRow key={row.id} hover>
                                        <TableCell sx={{ fontWeight: 600 }}>{row.component_name}</TableCell>
                                        <TableCell align="right">{formatAmount(row.monthly_amount)}</TableCell>
                                        <TableCell align="right">{formatAmount(row.annual_amount)}</TableCell>
                                        <TableCell>
                                            <Chip
                                                size="small"
                                                label={humanizeTaxability(row.taxability)}
                                                color={taxabilityColor(row.taxability)}
                                                variant="outlined"
                                            />
                                        </TableCell>
                                        <TableCell>{row.remarks}</TableCell>
                                    </TableRow>
                                ))}
                                <TableRow>
                                    <TableCell sx={{ fontWeight: 800 }}>Total CTC</TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 800 }}>
                                        {formatAmount(ctcStructureRows.reduce((sum, row) => sum + Number(row.monthly_amount || 0), 0))}
                                    </TableCell>
                                    <TableCell align="right" sx={{ fontWeight: 800 }}>
                                        {formatAmount(ctcStructureRows.reduce((sum, row) => sum + Number(row.annual_amount || 0), 0))}
                                    </TableCell>
                                    <TableCell colSpan={2} />
                                </TableRow>
                                {ctcStructureRows.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={5}>
                                            <Typography variant="body2" color="text.secondary" sx={{ py: 1.5 }}>
                                                {loading ? 'Loading salary structure...' : 'No salary structure records found.'}
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            )}


        </Stack>
    );
}
