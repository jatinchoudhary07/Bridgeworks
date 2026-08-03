import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
    Drawer,
    Box,
    Typography,
    IconButton,
    Tabs,
    Tab,
    Stack,
    TextField,
    MenuItem,
    Select,
    FormControl,
    InputLabel,
    Button,
    Chip,
    Checkbox,
    Avatar,
    Divider,
    Paper,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    List,
    ListItem,
    ListItemButton,
    ListItemText,
    CircularProgress,
    Tooltip,
    Grid,
    LinearProgress,
    Alert,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
} from '@mui/material';
import {
    Close as CloseIcon,
    Phone as PhoneIcon,
    Email as EmailIcon,
    Event as MeetingIcon,
    SwapHoriz as StageIcon,
    Add as AddIcon,
    CheckCircle as CompleteIcon,
    RadioButtonUnchecked as PendingIcon,
    Delete as DeleteIcon,
    Notes as NotesIcon,
    Assignment as TaskIcon,
    Edit as EditIcon,
    AttachFile as AttachmentIcon,
    CloudUpload as UploadIcon,
    Download as DownloadIcon,
    Business as BusinessIcon,
    ShoppingCart as OrderIcon,
    TrendingUp as TrendingUpIcon,
    AssignmentTurnedIn as ActiveTasksIcon,
    Description as DescriptionIcon,
} from '@mui/icons-material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../apiClient';
import { BACKEND_URL } from '../../config/api';
import { formatCurrency } from '../../utils/currency';
import { useTheme } from '@mui/material/styles';

// --- Lazy Load Tab Panel Wrapper ---
function LazyTabPanel({ children, value, index }) {
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`entity-tabpanel-${index}`}
            style={{ height: '100%' }}
        >
            {value === index && (
                <Box sx={{ py: 3, height: '100%', overflowY: 'auto' }}>
                    {children}
                </Box>
            )}
        </div>
    );
}

export default function EntityDetailDrawer({
    open,
    onClose,
    entityType = 'lead', // 'lead' | 'customer' | 'company' | 'quote'
    entityId,
    title,
    subtitle,
    extraTabs = [], // Custom tabs: [{ label: 'Custom', icon: <Icon />, component: <Comp /> }]
    apiPaths = {}, // Paths override
    onUpdate, // Callback when fields save successfully
}) {
    const theme = useTheme();
    const queryClient = useQueryClient();
    const [activeTab, setActiveTab] = useState(0);

    // Reset tab selection when changing entities
    useEffect(() => {
        setActiveTab(0);
    }, [entityId]);

    // Timeline dialog state
    const [logActivityOpen, setLogActivityOpen] = useState(false);
    const [activityForm, setActivityForm] = useState({ type: 'call', description: '' });

    // Task state
    const [addTaskOpen, setAddTaskOpen] = useState(false);
    const [taskForm, setTaskForm] = useState({ title: '', description: '', priority: 'medium', due_date: '' });

    // Notes mentions state
    const [noteContent, setNoteContent] = useState('');
    const [mentionAnchor, setMentionAnchor] = useState(null);
    const [mentionFilter, setMentionFilter] = useState('');
    const noteInputRef = useRef(null);

    // Attachments state (local mockup)
    const [attachments, setAttachments] = useState([]);
    const [uploadProgress, setUploadProgress] = useState(null);

    const isCompany = entityType.toLowerCase() === 'lead' || entityType.toLowerCase() === 'company' || entityType.toLowerCase() === 'wholesale-lead';
    
    // Resolve dynamic tab labels
    const tabLabels = useMemo(() => {
        if (isCompany) {
            return ['Overview', 'Contacts', 'Activities', 'Tasks', 'Notes', 'Attachments', 'Quotes', 'Orders'];
        }
        return ['Properties', 'Timeline', 'Notes', 'Tasks', 'Attachments'];
    }, [isCompany]);

    // Resolve REST Endpoints
    const resolvedPaths = useMemo(() => {
        const type = entityType.toLowerCase();
        let base = '';
        if (type === 'lead' || type === 'wholesale-lead') base = 'wholesale-leads';
        else if (type === 'quote' || type === 'quotation') base = 'quotations';
        else if (type === 'customer') base = 'retail-store-customers';
        else if (type === 'company' || type === 'store') base = 'retail-stores';
        else base = `${type}s`;

        return {
            details: apiPaths.details || `${BACKEND_URL}/api/sales/${base}/${entityId}/`,
            activities: apiPaths.activities || `${BACKEND_URL}/api/sales/${base}/${entityId}/activities/`,
            tasks: apiPaths.tasks || `${BACKEND_URL}/api/sales/${base}/${entityId}/tasks/`,
            notes: apiPaths.notes || `${BACKEND_URL}/api/sales/${base}/${entityId}/notes/`,
            quotes: apiPaths.quotes || `${BACKEND_URL}/api/sales/${base}/${entityId}/quotes/`,
            orders: apiPaths.orders || `${BACKEND_URL}/api/sales/${base}/${entityId}/orders/`,
            timeline: apiPaths.timeline || `${BACKEND_URL}/api/sales/${base}/${entityId}/crm-timeline/`,
        };
    }, [entityType, entityId, apiPaths]);

    // --- React Query Queries ---
    const { data: entityData, isLoading: detailsLoading } = useQuery({
        queryKey: ['entityDetails', entityType, entityId],
        queryFn: () => apiClient(resolvedPaths.details).then(res => res.json()),
        enabled: open && !!entityId,
    });

    const isOverviewActive = open && !!entityId && activeTab === tabLabels.indexOf('Overview');
    const isTimelineActive = open && !!entityId && activeTab === tabLabels.indexOf(isCompany ? 'Activities' : 'Timeline');
    const isNotesActive = open && !!entityId && activeTab === tabLabels.indexOf('Notes');
    const isTasksActive = open && !!entityId && activeTab === tabLabels.indexOf('Tasks');
    const isQuotesActive = open && !!entityId && activeTab === tabLabels.indexOf('Quotes');
    const isOrdersActive = open && !!entityId && activeTab === tabLabels.indexOf('Orders');

    // Aggregate sub-resources query
    const { data: timeline = [], isLoading: timelineLoading, refetch: refetchTimeline } = useQuery({
        queryKey: ['entityTimeline', entityType, entityId],
        queryFn: () => apiClient(resolvedPaths.activities).then(res => res.json()),
        enabled: isTimelineActive,
    });

    const { data: notes = [], isLoading: notesLoading, refetch: refetchNotes } = useQuery({
        queryKey: ['entityNotes', entityType, entityId],
        queryFn: () => apiClient(resolvedPaths.notes).then(res => res.json()),
        enabled: isNotesActive,
    });

    const { data: tasks = [], isLoading: tasksLoading, refetch: refetchTasks } = useQuery({
        queryKey: ['entityTasks', entityType, entityId],
        queryFn: () => apiClient(resolvedPaths.tasks).then(res => res.json()),
        enabled: isTasksActive || isOverviewActive,
    });

    const { data: teamMembers = [] } = useQuery({
        queryKey: ['teamMembers'],
        queryFn: () => apiClient(`${BACKEND_URL}/api/team/members/`).then(res => res.json()),
        enabled: isNotesActive,
    });

    // Company specific queries
    const { data: companyTimeline = [], isLoading: companyTimelineLoading, refetch: refetchCompanyTimeline } = useQuery({
        queryKey: ['companyTimeline', entityId],
        queryFn: () => apiClient(resolvedPaths.timeline).then(res => res.json()),
        enabled: isOverviewActive && isCompany,
    });

    const { data: companyQuotes = [], isLoading: companyQuotesLoading, refetch: refetchCompanyQuotes } = useQuery({
        queryKey: ['companyQuotes', entityId],
        queryFn: () => apiClient(resolvedPaths.quotes).then(res => res.json()),
        enabled: (isOverviewActive || isQuotesActive) && isCompany,
    });

    const { data: companyOrders = [], isLoading: companyOrdersLoading, refetch: refetchCompanyOrders } = useQuery({
        queryKey: ['companyOrders', entityId],
        queryFn: () => apiClient(resolvedPaths.orders).then(res => res.json()),
        enabled: (isOverviewActive || isOrdersActive) && isCompany,
    });

    // --- Metrics calculations ---
    const companyMetrics = useMemo(() => {
        if (!isCompany) return null;
        const totalRevenue = companyOrders.reduce((sum, o) => sum + parseFloat(o.total_price || 0), 0);
        const openQuotesCount = companyQuotes.filter(q => q.status !== 'rejected' && q.status !== 'expired').length;
        const activeTasksCount = tasks.filter(t => t.status === 'pending').length;
        return {
            revenue: totalRevenue,
            openQuotes: openQuotesCount,
            orders: companyOrders.length,
            activeTasks: activeTasksCount
        };
    }, [isCompany, companyQuotes, companyOrders, tasks]);

    // --- Mutations ---
    const updateEntityMutation = useMutation({
        mutationFn: (updates) => apiClient(resolvedPaths.details, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        }).then(res => res.json()),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ['entityDetails', entityType, entityId] });
            if (onUpdate) onUpdate(data);
        }
    });

    const addActivityMutation = useMutation({
        mutationFn: (newAct) => apiClient(resolvedPaths.activities, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newAct),
        }).then(res => res.json()),
        onSuccess: () => {
            if (isCompany) refetchCompanyTimeline();
            refetchTimeline();
            setLogActivityOpen(false);
            setActivityForm({ type: 'call', description: '' });
        }
    });

    const addNoteMutation = useMutation({
        mutationFn: (newNote) => apiClient(resolvedPaths.notes, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newNote),
        }).then(res => res.json()),
        onSuccess: () => {
            if (isCompany) refetchCompanyTimeline();
            refetchNotes();
            setNoteContent('');
        }
    });

    const addTaskMutation = useMutation({
        mutationFn: (newTask) => apiClient(resolvedPaths.tasks, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newTask),
        }).then(res => res.json()),
        onSuccess: () => {
            refetchTasks();
            setAddTaskOpen(false);
            setTaskForm({ title: '', description: '', priority: 'medium', due_date: '' });
        }
    });

    const updateTaskMutation = useMutation({
        mutationFn: ({ id, updates }) => apiClient(`${resolvedPaths.tasks}${id}/`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates),
        }).then(res => res.json()),
        onSuccess: () => {
            if (isCompany) refetchCompanyTimeline();
            refetchTasks();
        }
    });

    const deleteTaskMutation = useMutation({
        mutationFn: (id) => apiClient(`${resolvedPaths.tasks}${id}/`, {
            method: 'DELETE',
        }),
        onSuccess: () => {
            refetchTasks();
        }
    });

    // --- LocalStorage Attachments Simulation ---
    const localAttachmentsKey = useMemo(() => {
        return `bridgeworks_attachments_${entityType}_${entityId}`;
    }, [entityType, entityId]);

    useEffect(() => {
        if (open && entityId) {
            const saved = localStorage.getItem(localAttachmentsKey);
            setAttachments(saved ? JSON.parse(saved) : []);
        }
    }, [open, entityId, localAttachmentsKey]);

    const handleUploadFile = (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setUploadProgress(0);
        let progress = 0;
        const interval = setInterval(() => {
            progress += 20;
            setUploadProgress(progress);
            if (progress >= 100) {
                clearInterval(interval);
                
                const newAttachment = {
                    id: Date.now(),
                    name: file.name,
                    size: `${(file.size / 1024).toFixed(1)} KB`,
                    type: file.type,
                    uploadedAt: new Date().toISOString(),
                };

                const updatedList = [...attachments, newAttachment];
                setAttachments(updatedList);
                localStorage.setItem(localAttachmentsKey, JSON.stringify(updatedList));
                setUploadProgress(null);
            }
        }, 150);
    };

    const handleDeleteAttachment = (attId) => {
        const updatedList = attachments.filter(a => a.id !== attId);
        setAttachments(updatedList);
        localStorage.setItem(localAttachmentsKey, JSON.stringify(updatedList));
    };

    // --- Mentions Autocomplete handlers ---
    const handleNoteTextChange = (e) => {
        const text = e.target.value;
        setNoteContent(text);
        const cursor = e.target.selectionStart;
        const lastAt = text.lastIndexOf('@', cursor - 1);

        if (lastAt !== -1 && !text.substring(lastAt, cursor).includes(' ')) {
            setMentionFilter(text.substring(lastAt + 1, cursor));
            setMentionAnchor(e.target);
        } else {
            setMentionAnchor(null);
        }
    };

    const insertMention = (member) => {
        const input = noteInputRef.current;
        if (!input) return;
        const cursor = input.selectionStart;
        const lastAt = noteContent.lastIndexOf('@', cursor - 1);
        if (lastAt === -1) return;

        const before = noteContent.substring(0, lastAt);
        const after = noteContent.substring(cursor);
        const inserted = `@${member.username} `;
        setNoteContent(before + inserted + after);
        setMentionAnchor(null);
        setTimeout(() => {
            input.focus();
            const newCursor = lastAt + inserted.length;
            input.setSelectionRange(newCursor, newCursor);
        }, 50);
    };

    const filteredMembers = useMemo(() => {
        return teamMembers.filter((m) =>
            m.username.toLowerCase().includes(mentionFilter.toLowerCase()) ||
            m.full_name.toLowerCase().includes(mentionFilter.toLowerCase())
        );
    }, [teamMembers, mentionFilter]);

    const handleFieldChange = (field, val) => {
        updateEntityMutation.mutate({ [field]: val });
    };

    // Dynamic fields renderer
    const renderProperties = () => {
        if (!entityData) return null;
        const type = entityType.toLowerCase();

        if (type === 'lead' || type === 'wholesale-lead' || type === 'company') {
            return (
                <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Company Name"
                            defaultValue={entityData.company_name || ''}
                            onBlur={(e) => handleFieldChange('company_name', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Primary Contact"
                            defaultValue={entityData.contact_person || ''}
                            onBlur={(e) => handleFieldChange('contact_person', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Email"
                            defaultValue={entityData.email || ''}
                            onBlur={(e) => handleFieldChange('email', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Phone"
                            defaultValue={entityData.phone || ''}
                            onBlur={(e) => handleFieldChange('phone', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="City"
                            defaultValue={entityData.city || ''}
                            onBlur={(e) => handleFieldChange('city', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Industry"
                            defaultValue={entityData.industry || ''}
                            onBlur={(e) => handleFieldChange('industry', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Est. Value / mo"
                            type="number"
                            defaultValue={entityData.estimated_monthly_value || ''}
                            onBlur={(e) => handleFieldChange('estimated_monthly_value', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                </Grid>
            );
        }

        if (type === 'quote' || type === 'quotation') {
            return (
                <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Quote Number"
                            defaultValue={entityData.quote_number || ''}
                            onBlur={(e) => handleFieldChange('quote_number', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Client Name"
                            defaultValue={entityData.client_name || ''}
                            onBlur={(e) => handleFieldChange('client_name', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Client Email"
                            defaultValue={entityData.client_email || ''}
                            onBlur={(e) => handleFieldChange('client_email', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Total Value"
                            type="number"
                            defaultValue={entityData.total_value || ''}
                            onBlur={(e) => handleFieldChange('total_value', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Valid Until"
                            type="date"
                            defaultValue={entityData.valid_until || ''}
                            onChange={(e) => handleFieldChange('valid_until', e.target.value)}
                            InputLabelProps={{ shrink: true }}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                </Grid>
            );
        }

        if (type === 'customer') {
            return (
                <Grid container spacing={2}>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Customer Name"
                            defaultValue={entityData.name || ''}
                            onBlur={(e) => handleFieldChange('name', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Email"
                            defaultValue={entityData.email || ''}
                            onBlur={(e) => handleFieldChange('email', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <TextField
                            label="Phone"
                            defaultValue={entityData.phone || ''}
                            onBlur={(e) => handleFieldChange('phone', e.target.value)}
                            size="small"
                            fullWidth
                        />
                    </Grid>
                    <Grid item xs={12} sm={6}>
                        <FormControl size="small" fullWidth>
                            <InputLabel>Funnel Stage</InputLabel>
                            <Select
                                value={entityData.funnel_stage || 'view_only'}
                                label="Funnel Stage"
                                onChange={(e) => handleFieldChange('funnel_stage', e.target.value)}
                            >
                                <MenuItem value="view_only">View Only</MenuItem>
                                <MenuItem value="purchase_intent">Purchase Intent</MenuItem>
                                <MenuItem value="asked_pricing">Asked Pricing</MenuItem>
                                <MenuItem value="initiated_billing">Initiated Billing</MenuItem>
                                <MenuItem value="purchased">Purchased</MenuItem>
                            </Select>
                        </FormControl>
                    </Grid>
                </Grid>
            );
        }

        return null;
    };

    if (!entityId) return null;

    return (
        <Drawer
            anchor="right"
            open={open}
            onClose={onClose}
            slotProps={{
                backdrop: { style: { backgroundColor: 'rgba(0, 0, 0, 0.3)', backdropFilter: 'blur(2px)' } },
            }}
            PaperProps={{
                sx: {
                    width: { xs: '100%', sm: 540, md: 600 },
                    bgcolor: 'background.paper',
                    borderLeft: '1px solid',
                    borderColor: 'divider',
                    boxShadow: '-10px 0 30px rgba(0, 0, 0, 0.1)',
                    p: 0,
                },
            }}
        >
            {detailsLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', flexDirection: 'column', gap: 2 }}>
                    <CircularProgress size={32} />
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>Loading details...</Typography>
                </Box>
            ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    
                    {/* Header Banner */}
                    <Box sx={{ p: 2.5, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.default' }}>
                        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1.5}>
                            <Box>
                                <Typography variant="h5" sx={{ fontWeight: 800, color: 'text.primary', letterSpacing: '-0.01em' }}>
                                    {title || entityData?.company_name || entityData?.name || entityData?.quote_number || 'Details Panel'}
                                </Typography>
                                <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>
                                    {subtitle || `${entityType.toUpperCase()} Workspace`}
                                </Typography>
                            </Box>
                            <IconButton onClick={onClose} sx={{ color: 'text.secondary', '&:hover': { color: 'text.primary' } }}>
                                <CloseIcon />
                            </IconButton>
                        </Stack>
                    </Box>

                    {/* Navigation Tabs */}
                    <Box sx={{ borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'background.default' }}>
                        <Tabs
                            value={activeTab}
                            onChange={(_, val) => setActiveTab(val)}
                            textColor="primary"
                            indicatorColor="primary"
                            variant="scrollable"
                            scrollButtons="auto"
                            sx={{ px: 2 }}
                        >
                            {tabLabels.map((lbl, idx) => (
                                <Tab key={idx} label={lbl} sx={{ fontSize: '0.8rem', textTransform: 'none' }} />
                            ))}
                            {extraTabs.map((custom, idx) => (
                                <Tab key={idx} label={custom.label} icon={custom.icon} iconPosition="start" sx={{ fontSize: '0.8rem', textTransform: 'none' }} />
                            ))}
                        </Tabs>
                    </Box>

                    {/* Content Area with Lazy Load Panels */}
                    <Box sx={{ flex: 1, overflowY: 'hidden', px: 3 }}>
                        
                        {/* Tab: Overview (Company Mode Only) */}
                        {isCompany && (
                            <LazyTabPanel value={activeTab} index={tabLabels.indexOf('Overview')}>
                                <Stack spacing={3}>
                                    {/* Company KPI Header */}
                                    <Grid container spacing={1.5}>
                                        <Grid item xs={6}>
                                            <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center', borderRadius: 2 }}>
                                                <TrendingUpIcon fontSize="small" color="success" />
                                                <Typography variant="caption" color="text.secondary" display="block">REVENUE</Typography>
                                                <Typography variant="subtitle1" fontWeight={800}>
                                                    {companyMetrics ? formatCurrency(companyMetrics.revenue, 'INR', 'en-IN', { maximumFractionDigits: 0 }) : '₹0'}
                                                </Typography>
                                            </Paper>
                                        </Grid>
                                        <Grid item xs={6}>
                                            <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center', borderRadius: 2 }}>
                                                <DescriptionIcon fontSize="small" color="primary" sx={{ display: 'none' }} />
                                                <Avatar sx={{ width: 20, height: 20, bgcolor: 'primary.main', display: 'inline-flex', mb: 0.5 }}>Q</Avatar>
                                                <Typography variant="caption" color="text.secondary" display="block">OPEN QUOTES</Typography>
                                                <Typography variant="subtitle1" fontWeight={800}>
                                                    {companyMetrics?.openQuotes || 0}
                                                </Typography>
                                            </Paper>
                                        </Grid>
                                        <Grid item xs={6}>
                                            <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center', borderRadius: 2 }}>
                                                <OrderIcon fontSize="small" color="info" />
                                                <Typography variant="caption" color="text.secondary" display="block">ORDERS</Typography>
                                                <Typography variant="subtitle1" fontWeight={800}>
                                                    {companyMetrics?.orders || 0}
                                                </Typography>
                                            </Paper>
                                        </Grid>
                                        <Grid item xs={6}>
                                            <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center', borderRadius: 2 }}>
                                                <ActiveTasksIcon fontSize="small" color="warning" />
                                                <Typography variant="caption" color="text.secondary" display="block">ACTIVE TASKS</Typography>
                                                <Typography variant="subtitle1" fontWeight={800}>
                                                    {companyMetrics?.activeTasks || 0}
                                                </Typography>
                                            </Paper>
                                        </Grid>
                                    </Grid>

                                    <Divider />

                                    {/* Company Timeline */}
                                    <Typography variant="subtitle2" fontWeight={700} color="text.secondary">
                                        Company Workspace Timeline
                                    </Typography>

                                    {companyTimelineLoading ? (
                                        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
                                    ) : companyTimeline.length === 0 ? (
                                        <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', py: 2 }}>
                                            No workspace timeline events.
                                        </Typography>
                                    ) : (
                                        <Stack spacing={2.5} sx={{ borderLeft: '2px solid', borderColor: 'divider', pl: 2.5, ml: 1, position: 'relative' }}>
                                            {companyTimeline.map((evt) => (
                                                <Box key={evt.id} sx={{ position: 'relative' }}>
                                                    <Box sx={{
                                                        position: 'absolute', left: -32, top: 4, width: 12, height: 12, borderRadius: '50%',
                                                        bgcolor: evt.event_type === 'order_created' ? 'success.main' : evt.event_type === 'quote_created' ? 'primary.main' : evt.event_type === 'task_completed' ? 'warning.main' : 'text.secondary',
                                                        border: '2px solid', borderColor: 'background.paper'
                                                    }} />
                                                    <Typography variant="body2" fontWeight={700}>
                                                        {evt.title}
                                                    </Typography>
                                                    <Typography variant="caption" color="text.secondary" display="block">
                                                        {new Date(evt.timestamp).toLocaleString()} by {evt.user}
                                                    </Typography>
                                                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                                        {evt.description}
                                                    </Typography>
                                                </Box>
                                            ))}
                                        </Stack>
                                    )}
                                </Stack>
                            </LazyTabPanel>
                        )}

                        {/* Tab: Properties / Contacts */}
                        <LazyTabPanel value={activeTab} index={tabLabels.indexOf(isCompany ? 'Contacts' : 'Properties')}>
                            <Stack spacing={3}>
                                <Typography variant="subtitle2" fontWeight={700} color="text.secondary">
                                    Entity Properties
                                </Typography>
                                {renderProperties()}
                                <Alert severity="info" sx={{ fontSize: '0.75rem', py: 0 }}>
                                    Properties automatically save on blur (when clicking away).
                                </Alert>
                            </Stack>
                        </LazyTabPanel>

                        {/* Tab: Activities / Timeline */}
                        <LazyTabPanel value={activeTab} index={tabLabels.indexOf(isCompany ? 'Activities' : 'Timeline')}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
                                <Typography variant="subtitle2" fontWeight={700} color="text.secondary">
                                    Communication History
                                </Typography>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    startIcon={<AddIcon />}
                                    onClick={() => setLogActivityOpen(true)}
                                >
                                    Log Activity
                                </Button>
                            </Stack>

                            {timelineLoading ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
                            ) : timeline.length === 0 ? (
                                <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', py: 4 }}>
                                    No recorded activities yet.
                                </Typography>
                            ) : (
                                <Stack spacing={2.5} sx={{ borderLeft: '2px solid', borderColor: 'divider', pl: 2.5, ml: 1, position: 'relative' }}>
                                    {timeline.map((act) => (
                                        <Box key={act.id} sx={{ position: 'relative' }}>
                                            <Box sx={{ position: 'absolute', left: -32, top: 4, width: 10, height: 10, borderRadius: '50%', bgcolor: 'primary.main', border: '2px solid', borderColor: 'background.paper' }} />
                                            <Typography variant="body2" fontWeight={700}>
                                                {act.activity_type === 'call' && '📞 Call Logged'}
                                                {act.activity_type === 'email' && '✉️ Email Sent'}
                                                {act.activity_type === 'meeting' && '🤝 Meeting Scheduled'}
                                                {act.activity_type === 'stage_change' && '🔄 Stage Changed'}
                                                {!['call', 'email', 'meeting', 'stage_change'].includes(act.activity_type) && act.activity_type_display}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary" display="block">
                                                {new Date(act.created_at).toLocaleString()} by {act.created_by_details?.full_name || 'System'}
                                            </Typography>
                                            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                                {act.description}
                                            </Typography>
                                        </Box>
                                    ))}
                                </Stack>
                            )}
                        </LazyTabPanel>

                        {/* Tab: Notes */}
                        <LazyTabPanel value={activeTab} index={tabLabels.indexOf('Notes')}>
                            <Typography variant="subtitle2" fontWeight={700} color="text.secondary" sx={{ mb: 2 }}>
                                Notes Feed
                            </Typography>
                            <Box sx={{ mb: 3, position: 'relative' }}>
                                <TextField
                                    ref={noteInputRef}
                                    inputRef={(el) => { noteInputRef.current = el; }}
                                    placeholder="Write a note... Type @ to mention team"
                                    multiline
                                    rows={3}
                                    fullWidth
                                    value={noteContent}
                                    onChange={handleNoteTextChange}
                                />
                                <Button
                                    variant="contained"
                                    size="small"
                                    disabled={!noteContent.trim() || addNoteMutation.isPending}
                                    onClick={() => addNoteMutation.mutate({ content: noteContent })}
                                    sx={{ mt: 1, float: 'right' }}
                                >
                                    Post Note
                                </Button>
                                <Box sx={{ clear: 'both' }} />

                                {mentionAnchor && filteredMembers.length > 0 && (
                                    <Paper
                                        sx={{
                                            position: 'absolute',
                                            top: '100%',
                                            left: 0,
                                            right: 0,
                                            zIndex: 1000,
                                            maxHeight: 150,
                                            overflowY: 'auto',
                                            mt: 0.5,
                                            border: '1px solid',
                                            borderColor: 'divider',
                                        }}
                                    >
                                        <List dense disablePadding>
                                            {filteredMembers.map(m => (
                                                <ListItemButton key={m.id} onClick={() => insertMention(m)}>
                                                    <ListItemText primary={m.full_name} secondary={`@${m.username}`} />
                                                </ListItemButton>
                                            ))}
                                        </List>
                                    </Paper>
                                )}
                            </Box>

                            {notesLoading ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
                            ) : notes.length === 0 ? (
                                <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', py: 4 }}>
                                    No notes captured yet.
                                </Typography>
                            ) : (
                                <Stack spacing={2}>
                                    {notes.map(note => (
                                        <Paper key={note.id} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                                            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 1 }}>
                                                <Avatar sx={{ width: 20, height: 20, fontSize: '0.6rem', bgcolor: 'primary.main' }}>
                                                    {(note.created_by_details?.full_name || 'U')[0]}
                                                </Avatar>
                                                <Typography variant="body2" fontWeight={700}>
                                                    {note.created_by_details?.full_name || note.created_by_details?.username}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    {new Date(note.created_at).toLocaleString()}
                                                </Typography>
                                            </Stack>
                                            <Typography variant="body2">
                                                {note.content.split(/(\s+)/).map((word, wIdx) => {
                                                    if (word.startsWith('@')) {
                                                        return <span key={wIdx} style={{ color: theme.palette.primary.main, fontWeight: 700 }}>{word}</span>;
                                                    }
                                                    return word;
                                                })}
                                            </Typography>
                                        </Paper>
                                    ))}
                                </Stack>
                            )}
                        </LazyTabPanel>

                        {/* Tab: Tasks */}
                        <LazyTabPanel value={activeTab} index={tabLabels.indexOf('Tasks')}>
                            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
                                <Typography variant="subtitle2" fontWeight={700} color="text.secondary">
                                    Action Checklists
                                </Typography>
                                <Button
                                    variant="outlined"
                                    size="small"
                                    startIcon={<AddIcon />}
                                    onClick={() => setAddTaskOpen(true)}
                                >
                                    New Task
                                </Button>
                            </Stack>

                            {tasksLoading ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
                            ) : tasks.length === 0 ? (
                                <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', py: 4 }}>
                                    No checklists assigned.
                                </Typography>
                            ) : (
                                <Stack spacing={1.5}>
                                    {tasks.map(task => (
                                        <Paper key={task.id} variant="outlined" sx={{ p: 1.5, display: 'flex', alignItems: 'center', justifyItems: 'space-between', gap: 1.5 }}>
                                            <Checkbox
                                                checked={task.status === 'completed'}
                                                onChange={(e) => updateTaskMutation.mutate({ id: task.id, updates: { status: e.target.checked ? 'completed' : 'pending' } })}
                                                icon={<PendingIcon sx={{ color: 'text.disabled' }} />}
                                                checkedIcon={<CompleteIcon sx={{ color: 'success.main' }} />}
                                            />
                                            <Box sx={{ flex: 1, minWidth: 0 }}>
                                                <Typography
                                                    variant="body2"
                                                    fontWeight={600}
                                                    sx={{
                                                        textDecoration: task.status === 'completed' ? 'line-through' : 'none',
                                                        color: task.status === 'completed' ? 'text.disabled' : 'text.primary',
                                                    }}
                                                >
                                                    {task.title}
                                                </Typography>
                                                {task.due_date && (
                                                    <Typography variant="caption" color="text.secondary">
                                                        Due: {task.due_date}
                                                    </Typography>
                                                )}
                                            </Box>
                                            <Stack direction="row" spacing={1} alignItems="center">
                                                <Chip
                                                    label={task.priority}
                                                    size="small"
                                                    color={task.priority === 'high' ? 'error' : task.priority === 'medium' ? 'warning' : 'default'}
                                                    sx={{ height: 16, fontSize: '9px' }}
                                                />
                                                <IconButton size="small" color="error" onClick={() => deleteTaskMutation.mutate(task.id)}>
                                                    <DeleteIcon fontSize="small" />
                                                </IconButton>
                                            </Stack>
                                        </Paper>
                                    ))}
                                </Stack>
                            )}
                        </LazyTabPanel>

                        {/* Tab: Attachments */}
                        <LazyTabPanel value={activeTab} index={tabLabels.indexOf('Attachments')}>
                            <Typography variant="subtitle2" fontWeight={700} color="text.secondary" sx={{ mb: 2 }}>
                                Document Attachments
                            </Typography>
                            
                            <Paper
                                variant="outlined"
                                sx={{
                                    p: 3,
                                    borderStyle: 'dashed',
                                    borderWidth: 2,
                                    borderColor: 'divider',
                                    borderRadius: 3,
                                    textAlign: 'center',
                                    cursor: 'pointer',
                                    bgcolor: 'action.hover',
                                    mb: 3,
                                    position: 'relative',
                                }}
                                component="label"
                            >
                                <input
                                    type="file"
                                    style={{ display: 'none' }}
                                    onChange={handleUploadFile}
                                />
                                <UploadIcon sx={{ fontSize: 32, color: 'text.secondary', mb: 1 }} />
                                <Typography variant="body2" color="text.primary" fontWeight={600}>
                                    Drag & drop or click to upload attachment
                                </Typography>
                                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                                    Supports PDF, XLSX, Images, Docx (Max 10MB)
                                </Typography>
                            </Paper>

                            {uploadProgress !== null && (
                                <Box sx={{ mb: 3 }}>
                                    <Typography variant="caption" color="text.secondary">Uploading file...</Typography>
                                    <LinearProgress variant="determinate" value={uploadProgress} />
                                </Box>
                            )}

                            {attachments.length === 0 ? (
                                <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', py: 4 }}>
                                    No uploaded documents yet.
                                </Typography>
                            ) : (
                                <Stack spacing={1.5}>
                                    {attachments.map(file => (
                                        <Paper key={file.id} variant="outlined" sx={{ p: 1.5, display: 'flex', alignItems: 'center', gap: 2 }}>
                                            <AttachmentIcon sx={{ color: 'text.secondary' }} />
                                            <Box sx={{ flex: 1, minWidth: 0 }}>
                                                <Typography variant="body2" fontWeight={600} noWrap>
                                                    {file.name}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary" display="block">
                                                    {file.size} • Uploaded {new Date(file.uploadedAt).toLocaleDateString()}
                                                </Typography>
                                            </Box>
                                            <Stack direction="row" spacing={0.5}>
                                                <IconButton size="small" color="primary" onClick={() => alert(`Simulated download of ${file.name}`)}>
                                                    <DownloadIcon fontSize="small" />
                                                </IconButton>
                                                <IconButton size="small" color="error" onClick={() => handleDeleteAttachment(file.id)}>
                                                    <DeleteIcon fontSize="small" />
                                                </IconButton>
                                            </Stack>
                                        </Paper>
                                    ))}
                                </Stack>
                            )}
                        </LazyTabPanel>

                        {/* Tab: Quotes */}
                        {isCompany && (
                            <LazyTabPanel value={activeTab} index={tabLabels.indexOf('Quotes')}>
                                <Typography variant="subtitle2" fontWeight={700} color="text.secondary" sx={{ mb: 2 }}>
                                    Quotations
                                </Typography>
                                {companyQuotesLoading ? (
                                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
                                ) : companyQuotes.length === 0 ? (
                                    <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', py: 4 }}>
                                        No quotations found.
                                    </Typography>
                                ) : (
                                    <TableContainer component={Paper} variant="outlined">
                                        <Table size="small">
                                            <TableHead>
                                                <TableRow>
                                                    <TableCell>Quote #</TableCell>
                                                    <TableCell align="right">Value</TableCell>
                                                    <TableCell>Status</TableCell>
                                                </TableRow>
                                            </TableHead>
                                            <TableBody>
                                                {companyQuotes.map((q) => (
                                                    <TableRow key={q.id}>
                                                        <TableCell sx={{ fontWeight: 600 }}>{q.quote_number}</TableCell>
                                                        <TableCell align="right">{formatCurrency(q.total_value, 'INR', 'en-IN', { maximumFractionDigits: 0 })}</TableCell>
                                                        <TableCell>
                                                            <Chip label={q.status} size="small" variant="outlined" sx={{ height: 18, fontSize: '10px' }} />
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                )}
                            </LazyTabPanel>
                        )}

                        {/* Tab: Orders */}
                        {isCompany && (
                            <LazyTabPanel value={activeTab} index={tabLabels.indexOf('Orders')}>
                                <Typography variant="subtitle2" fontWeight={700} color="text.secondary" sx={{ mb: 2 }}>
                                    Orders
                                </Typography>
                                {companyOrdersLoading ? (
                                    <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}><CircularProgress size={20} /></Box>
                                ) : companyOrders.length === 0 ? (
                                    <Typography variant="body2" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', py: 4 }}>
                                        No Shopify or Marketplace orders.
                                    </Typography>
                                ) : (
                                    <TableContainer component={Paper} variant="outlined">
                                        <Table size="small">
                                            <TableHead>
                                                <TableRow>
                                                    <TableCell>Order #</TableCell>
                                                    <TableCell>Channel</TableCell>
                                                    <TableCell align="right">Total</TableCell>
                                                    <TableCell>Fulfillment</TableCell>
                                                </TableRow>
                                            </TableHead>
                                            <TableBody>
                                                {companyOrders.map((o) => (
                                                    <TableRow key={o.id}>
                                                        <TableCell sx={{ fontWeight: 600 }}>#{o.order_number}</TableCell>
                                                        <TableCell>{o.source}</TableCell>
                                                        <TableCell align="right">{formatCurrency(o.total_price, 'INR', 'en-IN', { maximumFractionDigits: 0 })}</TableCell>
                                                        <TableCell>
                                                            <Chip label={o.fulfillment_status || 'Unfulfilled'} size="small" variant="outlined" sx={{ height: 18, fontSize: '10px' }} />
                                                        </TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                )}
                            </LazyTabPanel>
                        )}

                        {/* Custom Extra Tabs */}
                        {extraTabs.map((custom, idx) => (
                            <LazyTabPanel key={idx} value={activeTab} index={tabLabels.length + idx}>
                                {custom.component}
                            </LazyTabPanel>
                        ))}

                    </Box>
                </Box>
            )}

            {/* --- TIMELINE LOG ACTIVITY DIALOG --- */}
            <Dialog open={logActivityOpen} onClose={() => setLogActivityOpen(false)} fullWidth maxWidth="xs">
                <DialogTitle>Log Communication Activity</DialogTitle>
                <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1.5 }}>
                    <FormControl size="small" fullWidth>
                        <InputLabel>Type</InputLabel>
                        <Select
                            value={activityForm.type}
                            label="Type"
                            onChange={(e) => setActivityForm({ ...activityForm, type: e.target.value })}
                        >
                            <MenuItem value="call">Call Logged</MenuItem>
                            <MenuItem value="email">Email Sent</MenuItem>
                            <MenuItem value="meeting">Meeting Scheduled</MenuItem>
                        </Select>
                    </FormControl>
                    <TextField
                        label="Log description / outcome..."
                        multiline
                        rows={3}
                        value={activityForm.description}
                        onChange={(e) => setActivityForm({ ...activityForm, description: e.target.value })}
                        fullWidth
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setLogActivityOpen(false)}>Cancel</Button>
                    <Button variant="contained" disabled={!activityForm.description.trim()} onClick={() => addActivityMutation.mutate({ activity_type: activityForm.type, description: activityForm.description })}>
                        Log Activity
                    </Button>
                </DialogActions>
            </Dialog>

            {/* --- ADD CHECKLIST TASK DIALOG --- */}
            <Dialog open={addTaskOpen} onClose={() => setAddTaskOpen(false)} fullWidth maxWidth="xs">
                <DialogTitle>Create Checklist Task</DialogTitle>
                <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1.5 }}>
                    <TextField
                        label="Task Title"
                        value={taskForm.title}
                        onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
                        size="small"
                        required
                        fullWidth
                    />
                    <FormControl size="small" fullWidth>
                        <InputLabel>Priority</InputLabel>
                        <Select
                            value={taskForm.priority}
                            label="Priority"
                            onChange={(e) => setTaskForm({ ...taskForm, priority: e.target.value })}
                        >
                            <MenuItem value="low">Low</MenuItem>
                            <MenuItem value="medium">Medium</MenuItem>
                            <MenuItem value="high">High</MenuItem>
                        </Select>
                    </FormControl>
                    <TextField
                        label="Due Date"
                        type="date"
                        value={taskForm.due_date}
                        onChange={(e) => setTaskForm({ ...taskForm, due_date: e.target.value })}
                        InputLabelProps={{ shrink: true }}
                        size="small"
                        fullWidth
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setAddTaskOpen(false)}>Cancel</Button>
                    <Button variant="contained" disabled={!taskForm.title.trim()} onClick={() => addTaskMutation.mutate(taskForm)}>
                        Save Task
                    </Button>
                </DialogActions>
            </Dialog>

        </Drawer>
    );
}
