import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    FormControl,
    InputLabel,
    ListItemText,
    LinearProgress,
    MenuItem,
    OutlinedInput,
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
    assignHrMasterTaskTrackerTasks,
    downloadHrMasterTaskTrackerReport,
    listHrMasterTaskTracker,
} from '../mydesk/mydeskService';

const SUMMARY_EMPTY = {
    total_tasks: 0,
    active_tasks: 0,
    completed_tasks: 0,
    overdue_tasks: 0,
    completion_rate: 0,
    avg_turnaround_days_estimate: 0,
};

const TRACKER_EMPTY = {
    generated_at: '',
    summary: SUMMARY_EMPTY,
    workload_cards: [],
    department_summary: [],
    reporting: {
        completion_by_member: [],
        completion_by_department: [],
        overdue_over_time: [],
    },
    tasks: [],
    activity_log: [],
    members: [],
    departments: [],
    display_task_count: 0,
    scope_task_count: 0,
};

const STATUS_FILTERS = [
    { value: 'all', label: 'All Statuses' },
    { value: 'active', label: 'Active' },
    { value: 'pending', label: 'Pending' },
    { value: 'in_progress', label: 'In Progress' },
    { value: 'completed', label: 'Completed' },
    { value: 'overdue', label: 'Overdue' },
];

const PRIORITY_FILTERS = [
    { value: 'all', label: 'All Priorities' },
    { value: 'low', label: 'Low' },
    { value: 'medium', label: 'Medium' },
    { value: 'high', label: 'High' },
    { value: 'critical', label: 'Critical' },
];

const STATUS_COLORS = {
    pending: 'default',
    in_progress: 'info',
    completed: 'success',
};

const PRIORITY_COLORS = {
    low: 'default',
    medium: 'primary',
    high: 'warning',
    critical: 'error',
};

function toDateInputValue(value) {
    const date = value instanceof Date ? value : new Date(value || Date.now());
    const local = new Date(date.getTime() - (date.getTimezoneOffset() * 60000));
    return local.toISOString().slice(0, 10);
}

function formatDateTime(value) {
    if (!value) return '-';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString(undefined, {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function formatDate(value) {
    if (!value) return '-';
    const parsed = new Date(`${value}T00:00:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatPercent(value) {
    return `${Number(value || 0).toFixed(1)}%`;
}

function formatNumber(value) {
    return Number(value || 0).toLocaleString();
}

function statusChipColor(status) {
    return STATUS_COLORS[String(status || '').toLowerCase()] || 'default';
}

function priorityChipColor(priority) {
    return PRIORITY_COLORS[String(priority || '').toLowerCase()] || 'default';
}

function OverviewCard({ title, value, subtitle, color = 'text.primary' }) {
    return (
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, minHeight: 118 }}>
            <Typography variant="caption" sx={{ color: 'text.secondary', letterSpacing: 0.3 }}>{title}</Typography>
            <Typography variant="h4" sx={{ fontWeight: 800, color, lineHeight: 1.1, mt: 0.5 }}>
                {value}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 1 }}>{subtitle}</Typography>
        </Paper>
    );
}

export default function HRMasterTaskTracker() {
    const today = useMemo(() => new Date(), []);
    const defaultToDate = useMemo(() => toDateInputValue(today), [today]);
    const defaultFromDate = useMemo(() => {
        const value = new Date(today);
        value.setDate(value.getDate() - 30);
        return toDateInputValue(value);
    }, [today]);

    const [searchText, setSearchText] = useState('');
    const [fromDate, setFromDate] = useState(defaultFromDate);
    const [toDate, setToDate] = useState(defaultToDate);
    const [department, setDepartment] = useState('all');
    const [priority, setPriority] = useState('all');
    const [status, setStatus] = useState('all');
    const [assigneeId, setAssigneeId] = useState('all');
    const [assignedById, setAssignedById] = useState('all');

    const [trackerData, setTrackerData] = useState(TRACKER_EMPTY);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [exporting, setExporting] = useState('');
    const [activeTab, setActiveTab] = useState(0);

    const [assignmentTitle, setAssignmentTitle] = useState('');
    const [assignmentDescription, setAssignmentDescription] = useState('');
    const [assignmentDueDate, setAssignmentDueDate] = useState(defaultToDate);
    const [assignmentPriority, setAssignmentPriority] = useState('medium');
    const [assignmentDepartment, setAssignmentDepartment] = useState('all');
    const [assignmentSearch, setAssignmentSearch] = useState('');
    const [assignmentAssigneeIds, setAssignmentAssigneeIds] = useState([]);
    const [assigningTasks, setAssigningTasks] = useState(false);
    const [assignmentError, setAssignmentError] = useState('');

    const buildFilterPayload = useCallback(() => {
        const payload = {
            search: searchText.trim() || undefined,
            from_date: fromDate || undefined,
            to_date: toDate || undefined,
            department: department !== 'all' ? department : undefined,
            priority: priority !== 'all' ? priority : undefined,
            status: status !== 'all' ? status : undefined,
            assignee_id: assigneeId !== 'all' ? assigneeId : undefined,
            assigned_by_id: assignedById !== 'all' ? assignedById : undefined,
        };
        return payload;
    }, [assigneeId, assignedById, department, fromDate, priority, searchText, status, toDate]);

    const loadTracker = useCallback(async (filters = {}) => {
        setLoading(true);
        setError('');
        try {
            const response = await listHrMasterTaskTracker(filters);
            setTrackerData({
                ...TRACKER_EMPTY,
                ...response,
                summary: {
                    ...SUMMARY_EMPTY,
                    ...(response?.summary || {}),
                },
                workload_cards: Array.isArray(response?.workload_cards) ? response.workload_cards : [],
                department_summary: Array.isArray(response?.department_summary) ? response.department_summary : [],
                tasks: Array.isArray(response?.tasks) ? response.tasks : [],
                activity_log: Array.isArray(response?.activity_log) ? response.activity_log : [],
                members: Array.isArray(response?.members) ? response.members : [],
                departments: Array.isArray(response?.departments) ? response.departments : [],
                reporting: {
                    ...TRACKER_EMPTY.reporting,
                    ...(response?.reporting || {}),
                },
            });
        } catch (requestError) {
            setError(requestError?.message || 'Unable to load master task tracker.');
            setTrackerData(TRACKER_EMPTY);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const handler = setTimeout(() => {
            loadTracker(buildFilterPayload());
        }, 300);
        return () => clearTimeout(handler);
    }, [buildFilterPayload, loadTracker]);

    const handleResetFilters = async () => {
        setSearchText('');
        setFromDate(defaultFromDate);
        setToDate(defaultToDate);
        setDepartment('all');
        setPriority('all');
        setStatus('all');
        setAssigneeId('all');
        setAssignedById('all');
        await loadTracker({
            from_date: defaultFromDate,
            to_date: defaultToDate,
        });
    };

    const handleExport = async (format) => {
        setExporting(format);
        try {
            await downloadHrMasterTaskTrackerReport(format, buildFilterPayload());
        } catch {
            // Notification is handled in the service layer.
        } finally {
            setExporting('');
        }
    };

    const assignmentMembers = useMemo(() => (
        (trackerData.members || [])
            .map((item) => ({
                id: Number(item?.id),
                name: String(item?.name || item?.email || '').trim(),
                email: String(item?.email || '').trim(),
                department: String(item?.department || '').trim() || 'Unassigned',
            }))
            .filter((item) => Number.isInteger(item.id) && item.id > 0)
    ), [trackerData.members]);

    const assignmentDepartmentOptions = useMemo(() => {
        const values = new Set();
        assignmentMembers.forEach((item) => {
            const label = String(item.department || '').trim() || 'Unassigned';
            values.add(label);
        });
        return Array.from(values).sort((left, right) => left.localeCompare(right));
    }, [assignmentMembers]);

    const filteredAssignmentMembers = useMemo(() => {
        const normalizedSearch = assignmentSearch.trim().toLowerCase();
        const normalizedDepartment = String(assignmentDepartment || 'all').trim().toLowerCase();

        return assignmentMembers.filter((item) => {
            const departmentLabel = String(item.department || 'Unassigned').trim() || 'Unassigned';

            if (normalizedDepartment !== 'all') {
                if (departmentLabel.toLowerCase() !== normalizedDepartment) {
                    return false;
                }
            }

            if (!normalizedSearch) {
                return true;
            }

            const haystack = `${item.name} ${item.email} ${departmentLabel}`.toLowerCase();
            return haystack.includes(normalizedSearch);
        });
    }, [assignmentDepartment, assignmentMembers, assignmentSearch]);

    useEffect(() => {
        const validIds = new Set(assignmentMembers.map((item) => item.id));
        setAssignmentAssigneeIds((previous) => previous.filter((value) => validIds.has(value)));
    }, [assignmentMembers]);

    const handleAssignmentAssigneesChange = (event) => {
        const rawValue = event.target.value;
        const rawList = Array.isArray(rawValue) ? rawValue : String(rawValue || '').split(',');
        const normalized = rawList
            .map((value) => Number(value))
            .filter((value) => Number.isInteger(value) && value > 0);
        setAssignmentAssigneeIds(Array.from(new Set(normalized)));
    };

    const handleSelectFilteredAssignees = () => {
        setAssignmentAssigneeIds(filteredAssignmentMembers.map((item) => item.id));
    };

    const handleClearSelectedAssignees = () => {
        setAssignmentAssigneeIds([]);
    };

    const handleAssignTasks = async () => {
        if (!assignmentTitle.trim()) {
            setAssignmentError('Task title is required.');
            return;
        }
        if (assignmentAssigneeIds.length === 0) {
            setAssignmentError('Select at least one employee to assign this task.');
            return;
        }

        setAssignmentError('');
        setAssigningTasks(true);
        try {
            await assignHrMasterTaskTrackerTasks({
                task_title: assignmentTitle.trim(),
                task_description: assignmentDescription.trim() || undefined,
                task_due_date: assignmentDueDate || undefined,
                task_priority: assignmentPriority || 'medium',
                assignee_ids: assignmentAssigneeIds,
            });

            setAssignmentTitle('');
            setAssignmentDescription('');
            setAssignmentPriority('medium');
            setAssignmentDueDate(defaultToDate);
            setAssignmentAssigneeIds([]);

            await loadTracker(buildFilterPayload());
        } catch (requestError) {
            setAssignmentError(requestError?.message || 'Unable to assign tasks.');
        } finally {
            setAssigningTasks(false);
        }
    };

    const summary = trackerData.summary || SUMMARY_EMPTY;

    return (
        <Box sx={{ p: { xs: 2, md: 3 }, display: 'flex', flexDirection: 'column', gap: 2.25 }}>

            {loading && (
                <Paper variant="outlined" sx={{ borderRadius: 2, overflow: 'hidden' }}>
                    <LinearProgress />
                </Paper>
            )}

            {error && <Alert severity="error">{error}</Alert>}

            <Box
                sx={{
                    display: 'grid',
                    gridTemplateColumns: {
                        xs: '1fr',
                        sm: 'repeat(2, minmax(0, 1fr))',
                        lg: 'repeat(4, minmax(0, 1fr))',
                    },
                    gap: 1.25,
                }}
            >
                <OverviewCard
                    title="Total Tasks"
                    value={formatNumber(summary.total_tasks)}
                    subtitle={`Visible: ${formatNumber(trackerData.display_task_count || 0)}`}
                />
                <OverviewCard
                    title="Completed"
                    value={formatNumber(summary.completed_tasks)}
                    subtitle={`Completion rate ${formatPercent(summary.completion_rate)}`}
                    color="success.main"
                />
                <OverviewCard
                    title="Active"
                    value={formatNumber(summary.active_tasks)}
                    subtitle="Open tasks in selected scope"
                    color="warning.main"
                />
                <OverviewCard
                    title="Overdue"
                    value={formatNumber(summary.overdue_tasks)}
                    subtitle={`Avg turnaround ${Number(summary.avg_turnaround_days_estimate || 0).toFixed(1)}d`}
                    color="error.main"
                />
            </Box>

            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1} flexWrap="wrap" alignItems="center">
                    <TextField
                        label="Search Tasks"
                        size="small"
                        value={searchText}
                        onChange={(event) => setSearchText(event.target.value)}
                        sx={{ minWidth: 100, flexGrow: 1 }}
                        placeholder="Title, assignee, status"
                    />

                    <TextField
                        label="From"
                        type="date"
                        size="small"
                        InputLabelProps={{ shrink: true }}
                        value={fromDate}
                        onChange={(event) => setFromDate(event.target.value)}
                        sx={{ width: 140 }}
                    />

                    <TextField
                        label="To"
                        type="date"
                        size="small"
                        InputLabelProps={{ shrink: true }}
                        value={toDate}
                        onChange={(event) => setToDate(event.target.value)}
                        sx={{ width: 140 }}
                    />

                    <FormControl size="small" sx={{ width: 130 }}>
                        <InputLabel>Priority</InputLabel>
                        <Select
                            label="Priority"
                            value={priority}
                            onChange={(event) => setPriority(event.target.value)}
                        >
                            {PRIORITY_FILTERS.map((item) => (
                                <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl size="small" sx={{ width: 130 }}>
                        <InputLabel>Status</InputLabel>
                        <Select
                            label="Status"
                            value={status}
                            onChange={(event) => setStatus(event.target.value)}
                        >
                            {STATUS_FILTERS.map((item) => (
                                <MenuItem key={item.value} value={item.value}>{item.label}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl size="small" sx={{ width: 140 }}>
                        <InputLabel>Assigned To</InputLabel>
                        <Select
                            label="Assigned To"
                            value={assigneeId}
                            onChange={(event) => setAssigneeId(event.target.value)}
                        >
                            <MenuItem value="all">All Members</MenuItem>
                            {(trackerData.members || []).map((item) => (
                                <MenuItem key={item.id} value={item.id}>
                                    {item.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl size="small" sx={{ width: 130 }}>
                        <InputLabel>Assigned By</InputLabel>
                        <Select
                            label="Assigned By"
                            value={assignedById}
                            onChange={(event) => setAssignedById(event.target.value)}
                        >
                            <MenuItem value="all">All Members</MenuItem>
                            {(trackerData.members || []).map((item) => (
                                <MenuItem key={item.id} value={item.id}>
                                    {item.name}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <Button
                        variant="text"
                        onClick={handleResetFilters}
                        disabled={loading}
                        sx={{ minWidth: 64 }}
                    >
                        Reset
                    </Button>
                </Stack>
            </Paper>

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Paper variant="outlined" sx={{ borderRadius: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', pr: 2 }}>
                    <Tabs
                        value={activeTab}
                        onChange={(_, nextTab) => setActiveTab(nextTab)}
                        variant="scrollable"
                        scrollButtons="auto"
                        sx={{ px: 1 }}
                    >
                        <Tab label="Task Register" />
                        <Tab label="Workload by Member" />
                    </Tabs>
                    <Stack direction="row" spacing={1}>
                        <Button
                            variant="outlined"
                            size="small"
                            onClick={() => handleExport('csv')}
                            disabled={Boolean(exporting) || loading}
                        >
                            {exporting === 'csv' ? 'Exporting CSV...' : 'Export CSV'}
                        </Button>
                        <Button
                            variant="contained"
                            size="small"
                            onClick={() => handleExport('pdf')}
                            disabled={Boolean(exporting) || loading}
                        >
                            {exporting === 'pdf' ? 'Exporting PDF...' : 'Export PDF'}
                        </Button>
                    </Stack>
                </Paper>

                {activeTab === 1 && (
                    <Paper variant="outlined" sx={{ p: 1, borderRadius: 2 }}>


                        {loading ? (
                            <Box sx={{ py: 2, display: 'flex', justifyContent: 'center' }}>
                                <CircularProgress size={24} />
                            </Box>
                        ) : trackerData.workload_cards.length === 0 ? (
                            <Typography sx={{ color: 'text.secondary', mt: 2 }}>No workload data for selected filters.</Typography>
                        ) : (
                            <Box
                                sx={{
                                    mt: 1.5,
                                    display: 'grid',
                                    gridTemplateColumns: {
                                        xs: '1fr',
                                        md: 'repeat(2, minmax(0, 1fr))',
                                        xl: 'repeat(3, minmax(0, 1fr))',
                                    },
                                    gap: 1,
                                }}
                            >
                                {trackerData.workload_cards.map((card) => (
                                    <Paper key={card.user_id} variant="outlined" sx={{ p: 1.5, borderRadius: 1.5 }}>
                                        <Stack direction="row" spacing={1} justifyContent="space-between" alignItems="center">
                                            <Box>
                                                <Typography sx={{ fontWeight: 700, fontSize: '0.95rem' }}>{card.name}</Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {card.department || 'Unassigned'}
                                                </Typography>
                                            </Box>
                                        </Stack>

                                        <Stack direction="row" spacing={1} sx={{ mt: 1, flexWrap: 'wrap' }}>
                                            <Chip size="small" label={`Active ${card.active_tasks || 0}`} />
                                            <Chip size="small" color="success" label={`Done ${card.completed_tasks || 0}`} />
                                            <Chip size="small" color="error" label={`Overdue ${card.overdue_tasks || 0}`} />
                                        </Stack>
                                    </Paper>
                                ))}
                            </Box>
                        )}
                    </Paper>
                )}

                {activeTab === 0 && (
                    <Stack spacing={1.5}>
                        <Paper variant="outlined" sx={{ borderRadius: 2 }}>
                            <Box sx={{ px: 2, py: 0.5, borderBottom: '1px solid', borderColor: 'divider' }}>

                                <Typography variant="caption" color="text.secondary">
                                    {formatNumber(trackerData.display_task_count || 0)} displayed of {formatNumber(trackerData.scope_task_count || 0)} in scope.
                                </Typography>
                            </Box>
                            <TableContainer sx={{ maxHeight: 500 }}>
                                <Table stickyHeader size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell sx={{ fontWeight: 700 }}>Task</TableCell>
                                            <TableCell sx={{ fontWeight: 700 }}>Assignee</TableCell>
                                            <TableCell sx={{ fontWeight: 700 }}>Department</TableCell>
                                            <TableCell sx={{ fontWeight: 700 }}>Priority</TableCell>
                                            <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                                            <TableCell sx={{ fontWeight: 700 }}>Due Date</TableCell>
                                            <TableCell sx={{ fontWeight: 700 }}>Created</TableCell>
                                            <TableCell sx={{ fontWeight: 700 }}>Open (Days)</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {(trackerData.tasks || []).map((task) => (
                                            <TableRow key={task.id} hover>
                                                <TableCell>
                                                    <Typography sx={{ fontWeight: 600, fontSize: '0.86rem' }}>{task.title}</Typography>
                                                    {task.description && (
                                                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', maxWidth: 380 }}>
                                                            {task.description}
                                                        </Typography>
                                                    )}
                                                </TableCell>
                                                <TableCell>
                                                    <Typography sx={{ fontSize: '0.83rem' }}>{task.assignee_name || '-'}</Typography>
                                                    <Typography variant="caption" color="text.secondary">{task.assignee_email || '-'}</Typography>
                                                </TableCell>
                                                <TableCell>{task.department || 'Unassigned'}</TableCell>
                                                <TableCell>
                                                    <Chip
                                                        size="small"
                                                        color={priorityChipColor(task.priority)}
                                                        label={task.priority_label || task.priority || 'Medium'}
                                                        variant="outlined"
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Stack direction="row" spacing={0.5} alignItems="center">
                                                        <Chip
                                                            size="small"
                                                            color={statusChipColor(task.status)}
                                                            label={task.status_label || task.status || 'Pending'}
                                                        />
                                                        {task.is_overdue && <Chip size="small" color="error" label="Overdue" variant="outlined" />}
                                                    </Stack>
                                                </TableCell>
                                                <TableCell>{formatDate(task.due_date)}</TableCell>
                                                <TableCell>{formatDateTime(task.created_at)}</TableCell>
                                                <TableCell>{formatNumber(task.days_open)}</TableCell>
                                            </TableRow>
                                        ))}
                                        {!loading && (trackerData.tasks || []).length === 0 && (
                                            <TableRow>
                                                <TableCell colSpan={8}>
                                                    <Typography sx={{ py: 2, color: 'text.secondary' }}>
                                                        No tasks found for selected filters.
                                                    </Typography>
                                                </TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </Paper>
                    </Stack>
                )}
            </Box>
        </Box>
    );
}
