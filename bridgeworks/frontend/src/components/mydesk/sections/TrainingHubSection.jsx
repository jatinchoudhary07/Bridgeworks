import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Box,
    Paper,
    Typography,
    Stack,
    Tabs,
    Tab,
    Grid,
    Card,
    CardContent,
    Button,
    Chip,
    CircularProgress,
    Alert,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    TextField,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Checkbox,
    ListItemText,
    OutlinedInput,
    TableContainer,
    Table,
    TableHead,
    TableRow,
    TableCell,
    TableBody,
    IconButton,
    LinearProgress,
    Tooltip,
    FormHelperText,
    Menu,
    ListItemIcon,
    useTheme,
    Snackbar,
    ToggleButton,
    ToggleButtonGroup
} from '@mui/material';
import {
    School as SchoolIcon,
    AssignmentTurnedIn as AssignmentIcon,
    CloudUpload as UploadIcon,
    CheckCircle as CheckCircleIcon,
    Info as InfoIcon,
    Dashboard as DashboardIcon,
    LibraryBooks as LibraryIcon,
    Send as SendIcon,
    CalendarToday as CalendarIcon,
    History as HistoryIcon,
    Close as CloseIcon,
    FileDownload as DownloadIcon,
    Warning as WarningIcon,
    MoreVert as MoreVertIcon,
    Description as DocIcon,
    VideoLibrary as VideoIcon,
    Slideshow as SlidesIcon,
    Add as AddIcon,
    Delete as DeleteIcon,
    Launch as LaunchIcon,
    Visibility as VisibilityIcon,
    Image as ImageIcon
} from '@mui/icons-material';
import { useUser } from '../../../contexts/UserContext';
import { checkActionPermission } from '../../../utils/rbac';
import {
    listTrainingFiles,
    createTrainingFile,
    updateTrainingFile,
    deleteTrainingFile,
    listTrainingPushes,
    createTrainingPush,
    listMyTrainingAssignments,
    acknowledgeTrainingAssignment,
    getTrainingFileVersions,
    getTrainingComplianceDashboard,
    fetchTeamMembers,
    listWorkforceDepartments
} from '../mydeskService';

const DEFAULT_CATEGORIES = [
    { value: 'onboarding', label: 'Onboarding' },
    { value: 'compliance', label: 'Compliance' },
    { value: 'skills', label: 'Skills' },
    { value: 'sops', label: 'SOPs' }
];

const getFileTypeLabel = (fileUrl, fileType) => {
    const ext = fileType || (fileUrl ? fileUrl.split('.').pop().toLowerCase() : '');
    if (!ext) return 'Document';
    if (ext === 'pdf') return 'PDF Document';
    if (['mp4', 'webm', 'ogg'].includes(ext)) return 'Video Tutorial';
    if (['ppt', 'pptx'].includes(ext)) return 'Presentation';
    if (['doc', 'docx'].includes(ext)) return 'Word Document';
    if (['xls', 'xlsx'].includes(ext)) return 'Spreadsheet';
    return ext.toUpperCase();
};


export default function TrainingHubSection({ members, isAdminMode = false }) {
    const { user } = useUser();
    const theme = useTheme();
    const isDarkMode = theme.palette.mode === 'dark';

    // Theme adaptive color mapping
    const colors = {
        bg: isDarkMode ? '#0a0a0c' : theme.palette.background.default,
        cardBg: isDarkMode ? '#121215' : theme.palette.background.paper,
        cardBorder: isDarkMode ? '#1e1e24' : '#e4e4e7',
        textPrimary: isDarkMode ? '#ffffff' : theme.palette.text.primary,
        textSecondary: isDarkMode ? '#71717a' : theme.palette.text.secondary,
        tableHeaderBg: isDarkMode ? '#161619' : '#f4f4f5',
        tableRowHoverBg: isDarkMode ? '#161619' : '#f9f9fb',
        checkboxColor: isDarkMode ? '#27272a' : '#d4d4d8',
        inputFieldBg: isDarkMode ? '#121214' : theme.palette.background.paper,
        progressBarBg: isDarkMode ? '#27272a' : '#e4e4e7',
        primaryBtnBg: isDarkMode ? '#ffffff' : '#18181b',
        primaryBtnText: isDarkMode ? '#09090b' : '#ffffff',
        primaryBtnHover: isDarkMode ? '#e4e4e7' : '#27272a',
        divider: isDarkMode ? '#1e1e24' : '#e4e4e7',
    };

    // Permission check - only allow HR features if in admin mode
    const isHr = isAdminMode && (checkActionPermission(user, 'human_resources', 'workforce_sheet', 'view') || user?.role === 'founder' || user?.is_superuser);

    // View mode: 'admin' or 'assignments'
    const [viewMode, setViewMode] = useState(isAdminMode ? 'admin' : 'assignments');

    // Filter states
    const [categoryFilter, setCategoryFilter] = useState('onboarding');
    const [selectedDept, setSelectedDept] = useState('all');
    const [selectedType, setSelectedType] = useState('all');
    const [searchQuery, setSearchQuery] = useState('');
    const [sortBy, setSortBy] = useState('newest');

    // State
    const [assignments, setAssignments] = useState([]);
    const [libraryFiles, setLibraryFiles] = useState([]);
    // Categories List State (supports custom categories created dynamically)
    const [categoriesList, setCategoriesList] = useState(() => {
        const deleted = JSON.parse(localStorage.getItem('deleted_training_categories') || '[]');
        return DEFAULT_CATEGORIES.filter(c => !deleted.includes(c.value));
    });
    const [dashboardData, setDashboardData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [membersList, setMembersList] = useState(members || []);
    const [departments, setDepartments] = useState([]);


    // Toast state
    const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'info' });

    // Menu state for row actions
    const [anchorEl, setAnchorEl] = useState(null);
    const [selectedMenuFile, setSelectedMenuFile] = useState(null);

    const showSnackbar = (message, severity = 'info') => {
        setSnackbar({ open: true, message, severity });
    };

    const hasFetchedMembers = useRef(false);

    // Fetch team members if not provided
    useEffect(() => {
        if (!members || members.length === 0) {
            if (!hasFetchedMembers.current) {
                hasFetchedMembers.current = true;
                fetchTeamMembers()
                    .then(data => setMembersList(data || []))
                    .catch(err => {
                        console.error('Failed to fetch team members', err);
                        hasFetchedMembers.current = false;
                    });
            }
        } else {
            setMembersList(members);
        }
    }, [members]);

    // Optimized Single loadInitialData on Mount to prevent infinite loop & throttling
    useEffect(() => {
        let active = true;
        const loadInitialData = async () => {
            setLoading(true);
            try {
                // Fetch assignments (available for any authenticated user)
                const asgData = await listMyTrainingAssignments();
                if (active) setAssignments(asgData || []);

                // Fetch departments
                try {
                    const deptsData = await listWorkforceDepartments();
                    if (active) setDepartments(deptsData || []);
                } catch (err) {
                    console.error('Failed to load departments', err);
                }

                // Fetch library files for all users (non-HR and HR)
                try {
                    const filesData = await listTrainingFiles();
                    if (active) setLibraryFiles(filesData || []);
                } catch (err) {
                    console.error('Failed to load training files library', err);
                }

                if (isHr) {
                    // Fetch compliance metrics for HR Admins only
                    const dashboard = await getTrainingComplianceDashboard();
                    if (active) setDashboardData(dashboard);
                }
            } catch (err) {
                if (active) setError(err.message || 'Failed to load training data.');
            } finally {
                if (active) setLoading(false);
            }
        };

        loadInitialData();
        return () => { active = false; };
    }, [isHr]);

    useEffect(() => {
        const deleted = JSON.parse(localStorage.getItem('deleted_training_categories') || '[]');
        const customCategoriesSet = new Set();
        libraryFiles.forEach(file => {
            if (file.category) {
                customCategoriesSet.add(file.category.trim().toLowerCase());
            }
        });
        assignments.forEach(asg => {
            const file = asg.push_training_file_detail || asg.push?.training_file_detail || {};
            if (file.category) {
                customCategoriesSet.add(file.category.trim().toLowerCase());
            }
        });

        if (customCategoriesSet.size > 0) {
            let deletedListChanged = false;
            let updatedDeleted = [...deleted];
            setCategoriesList(prev => {
                const next = [...prev];
                let changed = false;
                customCategoriesSet.forEach(val => {
                    const slug = val.replace(/\s+/g, '_');
                    if (!next.some(c => c.value === slug)) {
                        const label = val.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                        next.push({ value: slug, label });
                        changed = true;
                    }
                    if (updatedDeleted.includes(slug)) {
                        updatedDeleted = updatedDeleted.filter(d => d !== slug);
                        deletedListChanged = true;
                    }
                });
                if (deletedListChanged) {
                    localStorage.setItem('deleted_training_categories', JSON.stringify(updatedDeleted));
                }
                return changed ? next : prev;
            });
        }
    }, [libraryFiles, assignments]);

    // Modals
    const [uploadOpen, setUploadOpen] = useState(false);
    const [pushOpen, setPushOpen] = useState(false);
    const [historyOpen, setHistoryOpen] = useState(false);
    const [acknowledgeOpen, setAcknowledgeOpen] = useState(false);
    const [pushDetailsOpen, setPushDetailsOpen] = useState(false);
    const [previewOpen, setPreviewOpen] = useState(false);
    const [previewFile, setPreviewFile] = useState(null);
    const [categoryDialogOpen, setCategoryDialogOpen] = useState(false);
    const [newCategoryName, setNewCategoryName] = useState('');

    // Form inputs
    const [uploadData, setUploadData] = useState({
        title: '',
        category: 'onboarding',
        department_target: '',
        is_mandatory: false,
        expiry_date: '',
        file: null,
        video_url: '',
        resource_type: 'file' // 'file' or 'video_url'
    });
    const [selectedParentFile, setSelectedParentFile] = useState(null);
    const [pushPayload, setPushPayload] = useState({
        training_file: '',
        target_departments: [],
        target_members: [],
        is_mandatory: false
    });
    const [activeAssignment, setActiveAssignment] = useState(null);
    const [ackNotes, setAckNotes] = useState('');
    const [versionHistory, setVersionHistory] = useState([]);
    const [selectedPushDetails, setSelectedPushDetails] = useState(null);

    // Action loaders
    const loadMyAssignments = useCallback(async () => {
        try {
            const data = await listMyTrainingAssignments();
            setAssignments(data || []);
        } catch (err) {
            setError(err.message || 'Failed to load assignments.');
        }
    }, []);

    const loadLibrary = useCallback(async () => {
        try {
            const data = await listTrainingFiles();
            setLibraryFiles(data || []);
        } catch (err) {
            setError(err.message || 'Failed to load library.');
        }
    }, []);

    const loadDashboard = useCallback(async () => {
        if (!isHr) return;
        try {
            const data = await getTrainingComplianceDashboard();
            setDashboardData(data);
        } catch (err) {
            setError(err.message || 'Failed to load compliance dashboard.');
        }
    }, [isHr]);

    // Handlers
    const handleUploadSubmit = async (e) => {
        e.preventDefault();
        if (uploadData.resource_type === 'file' && !uploadData.file && !selectedParentFile) {
            setError('Please select a file.');
            return;
        }
        if (uploadData.resource_type === 'video_url' && !uploadData.video_url) {
            setError('Please enter a video URL.');
            return;
        }

        const formData = new FormData();
        formData.append('title', uploadData.title);
        formData.append('category', uploadData.category);
        formData.append('department_target', uploadData.department_target);
        formData.append('is_mandatory', uploadData.is_mandatory);
        if (uploadData.expiry_date) {
            formData.append('expiry_date', uploadData.expiry_date);
        }
        if (uploadData.resource_type === 'file' && uploadData.file) {
            formData.append('file', uploadData.file);
        }
        if (uploadData.resource_type === 'video_url' && uploadData.video_url) {
            formData.append('video_url', uploadData.video_url);
        }
        if (selectedParentFile) {
            formData.append('create_version', 'true');
        }

        try {
            setLoading(true);
            if (selectedParentFile) {
                await updateTrainingFile(selectedParentFile.id, formData);
            } else {
                await createTrainingFile(formData);
            }
            setUploadOpen(false);
            setUploadData({
                title: '',
                category: 'onboarding',
                department_target: '',
                is_mandatory: false,
                expiry_date: '',
                file: null,
                video_url: '',
                resource_type: 'file'
            });
            setSelectedParentFile(null);
            await loadLibrary();
            await loadDashboard();
            showSnackbar(selectedParentFile ? 'New version uploaded successfully!' : 'Training document uploaded successfully!', 'success');
        } catch (err) {
            setError(err.message || 'Upload failed.');
        } finally {
            setLoading(false);
        }
    };

    const handlePushSubmit = async (e) => {
        e.preventDefault();
        if (!pushPayload.training_file) {
            setError('Please select a training document.');
            return;
        }
        if (pushPayload.target_departments.length === 0 && pushPayload.target_members.length === 0) {
            setError('Please select at least one department or member.');
            return;
        }

        try {
            setLoading(true);
            await createTrainingPush(pushPayload);
            setPushOpen(false);
            setPushPayload({
                training_file: '',
                target_departments: [],
                target_members: [],
                is_mandatory: false
            });
            await loadDashboard();
            await loadMyAssignments();
            showSnackbar('Training push campaign initiated successfully!', 'success');
        } catch (err) {
            setError(err.message || 'Vault push failed.');
        } finally {
            setLoading(false);
        }
    };

    const handleAcknowledge = async () => {
        if (!activeAssignment) return;
        try {
            setLoading(true);
            await acknowledgeTrainingAssignment(activeAssignment.id, ackNotes);
            setAcknowledgeOpen(false);
            setAckNotes('');
            setActiveAssignment(null);
            await loadMyAssignments();
            await loadDashboard();
            showSnackbar('Training assignment acknowledged successfully!', 'success');
        } catch (err) {
            setError(err.message || 'Acknowledgement failed.');
        } finally {
            setLoading(false);
        }
    };

    const handleViewHistory = async (file) => {
        try {
            setLoading(true);
            const data = await getTrainingFileVersions(file.id);
            setVersionHistory(data || []);
            setHistoryOpen(true);
        } catch (err) {
            setError(err.message || 'Failed to load version history.');
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteFile = async (id) => {
        if (!window.confirm('Are you sure you want to delete this file and all its versions?')) return;
        try {
            setLoading(true);
            await deleteTrainingFile(id);
            // Immediately remove from local state so UI updates without waiting
            setLibraryFiles(prev => prev.filter(f => f.id !== id));
            // Reload library from server
            const fresh = await listTrainingFiles();
            setLibraryFiles(fresh || []);
            if (isHr) await loadDashboard();
            showSnackbar('Training document deleted.', 'info');
        } catch (err) {
            setError(err.message || 'Failed to delete file.');
        } finally {
            setLoading(false);
        }
    };

    const getTrainingComplianceDetails = (pushId) => {
        listTrainingPushes().then(data => {
            const fullPush = data.find(p => p.id === pushId);
            if (fullPush) {
                setSelectedPushDetails(fullPush);
                setPushDetailsOpen(true);
            }
        }).catch(err => {
            setError(err.message || 'Failed to load push details.');
        });
    };

    // UI Helper mapping
    const getCategoryStyles = (category) => {
        const cat = category?.toLowerCase();
        if (isDarkMode) {
            switch (cat) {
                case 'onboarding':
                    return { bg: 'rgba(56, 189, 248, 0.1)', text: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.25)', label: 'Onboarding' };
                case 'compliance':
                    return { bg: 'rgba(244, 63, 94, 0.15)', text: '#f43f5e', border: '1px solid rgba(244, 63, 94, 0.25)', label: 'Compliance' };
                case 'skills':
                    return { bg: 'rgba(34, 197, 94, 0.12)', text: '#22c55e', border: '1px solid rgba(34, 197, 94, 0.22)', label: 'Skills' };
                case 'sops':
                    return { bg: 'rgba(234, 179, 8, 0.12)', text: '#eab308', border: '1px solid rgba(234, 179, 8, 0.22)', label: 'SOPs' };
                default:
                    return { bg: 'rgba(113, 113, 122, 0.1)', text: '#a1a1aa', border: '1px solid rgba(113, 113, 122, 0.2)', label: category || 'General' };
            }
        } else {
            switch (cat) {
                case 'onboarding':
                    return { bg: 'rgba(14, 165, 233, 0.1)', text: '#0284c7', border: '1px solid rgba(14, 165, 233, 0.2)', label: 'Onboarding' };
                case 'compliance':
                    return { bg: 'rgba(225, 29, 72, 0.1)', text: '#e11d48', border: '1px solid rgba(225, 29, 72, 0.2)', label: 'Compliance' };
                case 'skills':
                    return { bg: 'rgba(22, 163, 74, 0.1)', text: '#16a34a', border: '1px solid rgba(22, 163, 74, 0.2)', label: 'Skills' };
                case 'sops':
                    return { bg: 'rgba(202, 138, 4, 0.1)', text: '#ca8a04', border: '1px solid rgba(202, 138, 4, 0.2)', label: 'SOPs' };
                default:
                    return { bg: 'rgba(120, 113, 108, 0.08)', text: '#57534e', border: '1px solid rgba(120, 113, 108, 0.15)', label: category || 'General' };
            }
        }
    };

    const getFileIcon = (fileName) => {
        const ext = fileName?.split('.').pop()?.toLowerCase();
        switch (ext) {
            case 'pdf':
                return <DocIcon sx={{ color: '#ef4444', fontSize: 20 }} />;
            case 'docx':
            case 'doc':
                return <DocIcon sx={{ color: '#3b82f6', fontSize: 20 }} />;
            case 'pptx':
            case 'ppt':
                return <SlidesIcon sx={{ color: '#f97316', fontSize: 20 }} />;
            case 'mp4':
            case 'mov':
            case 'avi':
                return <VideoIcon sx={{ color: '#8b5cf6', fontSize: 20 }} />;
            case 'png':
            case 'jpg':
            case 'jpeg':
            case 'gif':
            case 'webp':
            case 'svg':
                return <ImageIcon sx={{ color: '#ec4899', fontSize: 20 }} />;
            default:
                return <DocIcon sx={{ color: '#9ca3af', fontSize: 20 }} />;
        }
    };

    const formatExpiryDate = (dateStr) => {
        if (!dateStr) return '—';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
        } catch {
            return dateStr;
        }
    };

    // Calculate Expiring Soon
    const getExpiringSoonCount = () => {
        const now = new Date();
        const thirtyDaysLater = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

        if (viewMode === 'admin') {
            return libraryFiles.filter(f => {
                if (!f.expiry_date) return false;
                const exp = new Date(f.expiry_date);
                return exp > now && exp <= thirtyDaysLater;
            }).length;
        } else {
            return assignments.filter(a => {
                if (a.is_acknowledged) return false;
                // Support both flat field (new API) and nested (legacy)
                const file = a.push_training_file_detail || a.push?.training_file_detail;
                if (!file || !file.expiry_date) return false;
                const exp = new Date(file.expiry_date);
                return exp > now && exp <= thirtyDaysLater;
            }).length;
        }
    };

    // Helper to calculate last push campaign duration dynamically
    const getLatestPushTimeStr = () => {
        if (!dashboardData?.file_stats || dashboardData.file_stats.length === 0) {
            return 'no pushes yet';
        }
        try {
            const pushDates = dashboardData.file_stats
                .map(s => s.pushed_at ? new Date(s.pushed_at) : null)
                .filter(d => d !== null);
            if (pushDates.length === 0) return 'no pushes yet';
            const latest = new Date(Math.max(...pushDates.map(d => d.getTime())));
            const diffMs = new Date().getTime() - latest.getTime();
            const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
            if (diffDays <= 0) {
                const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
                if (diffHours <= 0) {
                    return 'just now';
                }
                return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
            }
            return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
        } catch {
            return 'recently';
        }
    };

    // Get statistics purely from live data
    const stats = {
        totalFiles: viewMode === 'admin' ? (dashboardData?.total_files || libraryFiles.length) : assignments.length,
        categoriesCount: new Set(
            (viewMode === 'admin'
                ? libraryFiles
                : assignments.map(a => a.push_training_file_detail || a.push?.training_file_detail)
            ).filter(Boolean).map(f => f.category)
        ).size,
        pushedToVaults: dashboardData?.total_pushes ?? 0,
        avgCompletion: dashboardData?.overall_compliance ?? 0,
        expiringSoon: getExpiringSoonCount()
    };

    // Row Menu handlers
    const handleMenuClick = (e, file) => {
        setAnchorEl(e.currentTarget);
        setSelectedMenuFile(file);
    };

    const handleMenuClose = () => {
        setAnchorEl(null);
        setSelectedMenuFile(null);
    };

    const handleDeleteCategory = (catValue, catLabel) => {
        const catHasFiles = libraryFiles.some(f => (f.category || '').trim().toLowerCase().replace(/\s+/g, '_') === catValue || (f.category || '').trim().toLowerCase() === catValue);
        const catHasAssignments = assignments.some(asg => {
            const file = asg.push_training_file_detail || asg.push?.training_file_detail || {};
            return (file.category || '').trim().toLowerCase().replace(/\s+/g, '_') === catValue || (file.category || '').trim().toLowerCase() === catValue;
        });

        if (catHasFiles || catHasAssignments) {
            showSnackbar(`Cannot delete category "${catLabel}" because it is not empty.`, 'error');
            return;
        }

        if (window.confirm(`Are you sure you want to delete the category "${catLabel}"?`)) {
            const updated = categoriesList.filter(c => c.value !== catValue);
            setCategoriesList(updated);
            
            // Persist deletion
            const deleted = JSON.parse(localStorage.getItem('deleted_training_categories') || '[]');
            if (!deleted.includes(catValue)) {
                deleted.push(catValue);
                localStorage.setItem('deleted_training_categories', JSON.stringify(deleted));
            }

            if (categoryFilter === catValue) {
                setCategoryFilter(updated[0]?.value || 'onboarding');
            }
            showSnackbar(`Category "${catLabel}" deleted successfully.`, 'success');
        }
    };

    // Filter library files for Admin view
    const filteredAdminFiles = libraryFiles.filter(file => {
        if (categoryFilter !== 'all' && file.category !== categoryFilter) return false;
        if (selectedDept !== 'all' && file.department_target !== selectedDept) return false;
        if (selectedType !== 'all') {
            const isMandatory = selectedType === 'mandatory';
            if (file.is_mandatory !== isMandatory) return false;
        }
        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            return file.title?.toLowerCase().includes(query) || file.file?.toLowerCase().includes(query);
        }
        return true;
    });

    // Filter assignments for Employee view
    const filteredEmployeeAssignments = assignments.filter(asg => {
        // API returns push_training_file_detail flat on the recipient object
        const file = asg.push_training_file_detail || asg.push?.training_file_detail || {};
        if (categoryFilter !== 'all' && file.category !== categoryFilter) return false;
        if (selectedDept !== 'all' && file.department_target !== selectedDept) return false;
        if (selectedType !== 'all') {
            const isMandatory = selectedType === 'mandatory';
            if (file.is_mandatory !== isMandatory) return false;
        }
        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            return file.title?.toLowerCase().includes(query) || file.file?.toLowerCase().includes(query);
        }
        return true;
    });

    const sortFiles = (filesList, isAssignment = false) => {
        return [...filesList].sort((a, b) => {
            const itemA = isAssignment ? (a.push_training_file_detail || a.push?.training_file_detail || {}) : a;
            const itemB = isAssignment ? (b.push_training_file_detail || b.push?.training_file_detail || {}) : b;

            if (sortBy === 'newest') {
                return new Date(itemB.created_at || b.pushed_at || 0) - new Date(itemA.created_at || a.pushed_at || 0);
            }
            if (sortBy === 'oldest') {
                return new Date(itemA.created_at || a.pushed_at || 0) - new Date(itemB.created_at || b.pushed_at || 0);
            }
            if (sortBy === 'title-asc') {
                return (itemA.title || '').localeCompare(itemB.title || '');
            }
            if (sortBy === 'title-desc') {
                return (itemB.title || '').localeCompare(itemA.title || '');
            }
            return 0;
        });
    };

    const sortedAdminFiles = sortFiles(filteredAdminFiles);
    const sortedEmployeeAssignments = sortFiles(filteredEmployeeAssignments, true);

    // Check if the current category has any files associated with it in library files
    const categoryHasAnyFiles = categoryFilter === 'all'
        ? libraryFiles.length > 0
        : libraryFiles.some(f => (f.category || '').toLowerCase() === categoryFilter.toLowerCase());

    // Check if the current category has any assignments for the user
    const categoryHasAnyAssignments = categoryFilter === 'all'
        ? assignments.length > 0
        : assignments.some(asg => {
            const file = asg.push_training_file_detail || asg.push?.training_file_detail || {};
            return (file.category || '').toLowerCase() === categoryFilter.toLowerCase();
        });

    const isCurrentCategoryEmpty = viewMode === 'admin' ? !categoryHasAnyFiles : !categoryHasAnyAssignments;

    // Find latest completion rate for a library file
    const getFileCompletionRate = (fileId) => {
        if (!dashboardData?.file_stats) return 0;
        const stat = dashboardData.file_stats.find(s => s.file_id === fileId);
        return stat ? stat.completion_rate : 0;
    };

    return (
        <Box sx={{
            width: '100%',
            minHeight: '100vh',
            bgcolor: colors.bg,
            color: colors.textPrimary,
            p: { xs: 2 },
            fontFamily: 'Inter, system-ui, sans-serif'
        }}>


            {/* Error alerts */}
            {error && (
                <Alert severity="error" sx={{ mb: 3, bgcolor: isDarkMode ? 'rgba(239, 68, 68, 0.1)' : 'rgba(239, 68, 68, 0.05)', color: isDarkMode ? '#f87171' : '#b91c1c', border: isDarkMode ? '1px solid rgba(239, 68, 68, 0.2)' : '1px solid rgba(239, 68, 68, 0.15)', borderRadius: '8px' }} onClose={() => setError(null)}>
                    {error}
                </Alert>
            )}

            {/* Stat Cards (4 in a row) */}
            <Grid container spacing={2} sx={{ mb: 4 }}>
                {viewMode === 'admin' ? (
                    <>
                        <Grid item xs={12} sm={6} md={3}>
                            <Card sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px' }}>
                                <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                                    <Typography variant="body2" sx={{ color: colors.textSecondary, fontWeight: 500 }}>
                                        Total files
                                    </Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 1, color: colors.textPrimary, letterSpacing: '-0.03em' }}>
                                        {stats.totalFiles}
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: colors.textSecondary, mt: 0.5, display: 'block' }}>
                                        across {stats.categoriesCount} categories
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>

                        <Grid item xs={12} sm={6} md={3}>
                            <Card sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px' }}>
                                <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                                    <Typography variant="body2" sx={{ color: colors.textSecondary, fontWeight: 500 }}>
                                        Pushed to vaults
                                    </Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 1, color: colors.textPrimary, letterSpacing: '-0.03em' }}>
                                        {stats.pushedToVaults}
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: colors.textSecondary, mt: 0.5, display: 'block' }}>
                                        last push {getLatestPushTimeStr()}
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>

                        <Grid item xs={12} sm={6} md={3}>
                            <Card sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px' }}>
                                <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                                    <Typography variant="body2" sx={{ color: colors.textSecondary, fontWeight: 500 }}>
                                        Avg. completion
                                    </Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 1, color: colors.textPrimary, letterSpacing: '-0.03em' }}>
                                        {stats.avgCompletion}%
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: colors.textSecondary, mt: 0.5, display: 'block' }}>
                                        mandatory trainings
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>

                        <Grid item xs={12} sm={6} md={3}>
                            <Card sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px' }}>
                                <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                                    <Typography variant="body2" sx={{ color: colors.textSecondary, fontWeight: 500 }}>
                                        Expiring soon
                                    </Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 1, color: stats.expiringSoon > 0 ? '#ef4444' : colors.textPrimary, letterSpacing: '-0.03em' }}>
                                        {stats.expiringSoon}
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: colors.textSecondary, mt: 0.5, display: 'block' }}>
                                        within 30 days
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>
                    </>
                ) : (
                    <>
                        <Grid item xs={12} sm={6} md={3}>
                            <Card sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px' }}>
                                <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                                    <Typography variant="body2" sx={{ color: colors.textSecondary, fontWeight: 500 }}>
                                        Library Resources
                                    </Typography>
                                    <Typography variant="h4" sx={{
                                        fontWeight: 700,
                                        mt: 1,
                                        color: colors.textPrimary,
                                        letterSpacing: '-0.03em'
                                    }}>
                                        {libraryFiles.length}
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: colors.textSecondary, mt: 0.5, display: 'block' }}>
                                        training resources
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>

                        <Grid item xs={12} sm={6} md={3}>
                            <Card sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px' }}>
                                <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                                    <Typography variant="body2" sx={{ color: colors.textSecondary, fontWeight: 500 }}>
                                        Assigned Modules
                                    </Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 1, color: colors.textPrimary, letterSpacing: '-0.03em' }}>
                                        {assignments.length}
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: colors.textSecondary, mt: 0.5, display: 'block' }}>
                                        total pushed tasks
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>

                        <Grid item xs={12} sm={6} md={3}>
                            <Card sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px' }}>
                                <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                                    <Typography variant="body2" sx={{ color: colors.textSecondary, fontWeight: 500 }}>
                                        Completed
                                    </Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 1, color: isDarkMode ? '#34d399' : '#059669', letterSpacing: '-0.03em' }}>
                                        {assignments.filter(a => a.is_acknowledged).length}
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: colors.textSecondary, mt: 0.5, display: 'block' }}>
                                        modules signed
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>

                        <Grid item xs={12} sm={6} md={3}>
                            <Card sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px' }}>
                                <CardContent sx={{ p: 2.5, '&:last-child': { pb: 2.5 } }}>
                                    <Typography variant="body2" sx={{ color: colors.textSecondary, fontWeight: 500 }}>
                                        Pending Action
                                    </Typography>
                                    <Typography variant="h4" sx={{ fontWeight: 700, mt: 1, color: assignments.filter(a => !a.is_acknowledged).length > 0 ? '#ef4444' : colors.textPrimary, letterSpacing: '-0.03em' }}>
                                        {assignments.filter(a => !a.is_acknowledged).length}
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: colors.textSecondary, mt: 0.5, display: 'block' }}>
                                        require signature
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>
                    </>
                )}
            </Grid>

            {/* Category tabs */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${colors.divider}`, mb: 3 }}>
                <Tabs
                    value={categoryFilter}
                    onChange={(e, val) => setCategoryFilter(val)}
                    textColor="inherit"
                    sx={{
                        '& .MuiTabs-indicator': {
                            bgcolor: colors.textPrimary,
                            height: '2px'
                        },
                        '& .MuiTab-root': {
                            color: colors.textSecondary,
                            textTransform: 'none',
                            fontWeight: 500,
                            fontSize: '14px',
                            minWidth: 'auto',
                            px: 1,
                            mr: 3,
                            pb: 1.5,
                            '&.Mui-selected': {
                                color: colors.textPrimary
                            }
                        }
                    }}
                >
                    {categoriesList.map((cat) => (
                        <Tab
                            key={cat.value}
                            value={cat.value}
                            label={
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <span>{cat.label}</span>
                                    {isHr && (
                                        <IconButton
                                            size="small"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDeleteCategory(cat.value, cat.label);
                                            }}
                                            sx={{
                                                p: 0.2,
                                                ml: 0.5,
                                                color: colors.textSecondary,
                                                opacity: 0.6,
                                                '&:hover': { color: '#ef4444', opacity: 1 }
                                            }}
                                        >
                                            <CloseIcon sx={{ fontSize: 13 }} />
                                        </IconButton>
                                    )}
                                </Box>
                            }
                        />
                    ))}
                </Tabs>
                {isHr && (
                    <Button
                        variant="outlined"
                        size="small"
                        onClick={() => { setNewCategoryName(''); setCategoryDialogOpen(true); }}
                        sx={{
                            borderColor: isDarkMode ? 'rgba(124,58,237,0.4)' : 'rgba(124,58,237,0.3)',
                            color: isDarkMode ? '#a78bfa' : '#7c3aed',
                            textTransform: 'none',
                            borderRadius: '7px',
                            fontWeight: 500,
                            fontSize: '13px',
                            mb: 1,
                            '&:hover': { borderColor: '#7c3aed', bgcolor: isDarkMode ? 'rgba(124,58,237,0.08)' : 'rgba(124,58,237,0.06)' }
                        }}
                    >
                        + New Category
                    </Button>
                )}
            </Box>

            {/* Filters Row */}
            {!isCurrentCategoryEmpty && (
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} sx={{ mb: 3 }} alignItems={{ xs: 'stretch', md: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <Checkbox sx={{ color: colors.checkboxColor, '&.Mui-checked': { color: colors.textPrimary }, p: 0, mr: 2 }} />
                    </Box>

                    <Stack direction="row" spacing={1.5} alignItems="center" sx={{ width: { xs: '100%', md: 'auto' } }}>
                        <TextField
                            placeholder="Search files..."
                            size="small"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            sx={{
                                width: { xs: '100%', md: '180px' },
                                '& .MuiOutlinedInput-root': {
                                    bgcolor: colors.inputFieldBg,
                                    borderRadius: '8px',
                                    color: colors.textPrimary,
                                    '& fieldset': { borderColor: colors.cardBorder },
                                    '&:hover fieldset': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                    '&.Mui-focused fieldset': { borderColor: '#7c3aed' }
                                },
                                '& .MuiInputBase-input': { py: 1, fontSize: '14px' }
                            }}
                        />
                        {isHr && (
                            <Button
                                variant="contained"
                                size="small"
                                startIcon={<AddIcon sx={{ fontSize: 16 }} />}
                                onClick={() => {
                                    setSelectedParentFile(null);
                                    setUploadData({
                                        title: '',
                                        category: categoryFilter,
                                        department_target: '',
                                        is_mandatory: false,
                                        expiry_date: '',
                                        file: null,
                                        video_url: '',
                                        resource_type: 'file'
                                    });
                                    setUploadOpen(true);
                                }}
                                sx={{
                                    bgcolor: colors.primaryBtnBg,
                                    color: colors.primaryBtnText,
                                    textTransform: 'none',
                                    borderRadius: '8px',
                                    fontWeight: 600,
                                    height: '37px',
                                    px: 2,
                                    fontSize: '13px',
                                    whiteSpace: 'nowrap',
                                    '&:hover': { bgcolor: colors.primaryBtnHover }
                                }}
                            >
                                Upload Files
                            </Button>
                        )}
                    </Stack>

                    <FormControl size="small" sx={{ minWidth: 160 }}>
                        <Select
                            value={selectedDept}
                            onChange={(e) => setSelectedDept(e.target.value)}
                            displayEmpty
                            sx={{
                                bgcolor: colors.inputFieldBg,
                                borderRadius: '8px',
                                color: colors.textPrimary,
                                fontSize: '14px',
                                '& .MuiOutlinedInput-notchedOutline': { borderColor: colors.cardBorder },
                                '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#7c3aed' }
                            }}
                        >
                            <MenuItem value="all">All departments</MenuItem>
                            {departments.map(dept => (
                                <MenuItem key={dept.id} value={dept.name}>{dept.name}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl size="small" sx={{ minWidth: 140 }}>
                        <Select
                            value={selectedType}
                            onChange={(e) => setSelectedType(e.target.value)}
                            displayEmpty
                            sx={{
                                bgcolor: colors.inputFieldBg,
                                borderRadius: '8px',
                                color: colors.textPrimary,
                                fontSize: '14px',
                                '& .MuiOutlinedInput-notchedOutline': { borderColor: colors.cardBorder },
                                '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#7c3aed' }
                            }}
                        >
                            <MenuItem value="all">All types</MenuItem>
                            <MenuItem value="mandatory">Mandatory</MenuItem>
                            <MenuItem value="optional">Optional</MenuItem>
                        </Select>
                    </FormControl>

                    <FormControl size="small" sx={{ minWidth: 150 }}>
                        <Select
                            value={sortBy}
                            onChange={(e) => setSortBy(e.target.value)}
                            displayEmpty
                            sx={{
                                bgcolor: colors.inputFieldBg,
                                borderRadius: '8px',
                                color: colors.textPrimary,
                                fontSize: '14px',
                                '& .MuiOutlinedInput-notchedOutline': { borderColor: colors.cardBorder },
                                '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#7c3aed' }
                            }}
                        >
                            <MenuItem value="newest">Newest First</MenuItem>
                            <MenuItem value="oldest">Oldest First</MenuItem>
                            <MenuItem value="title-asc">Title (A-Z)</MenuItem>
                            <MenuItem value="title-desc">Title (Z-A)</MenuItem>
                        </Select>
                    </FormControl>
                </Stack>
            )}

            {/* Main Content Area */}
            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
                    <CircularProgress sx={{ color: '#7c3aed' }} />
                </Box>
            ) : isCurrentCategoryEmpty ? (
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    py: 8,
                    px: 3,
                    bgcolor: colors.cardBg,
                    border: `1px solid ${colors.cardBorder}`,
                    borderRadius: '12px',
                    textAlign: 'center'
                }}>
                    <SchoolIcon sx={{ fontSize: 48, color: '#7c3aed', mb: 2, opacity: 0.8 }} />
                    <Typography variant="h6" sx={{ fontWeight: 600, color: colors.textPrimary, mb: 1 }}>
                        No Training Resources
                    </Typography>
                    <Typography variant="body2" sx={{ color: colors.textSecondary, mb: 3, maxWidth: 360 }}>
                        {isHr 
                            ? "There are no files uploaded to this category yet. Start by uploading a new training resource or video link."
                            : "No training files have been assigned or added to this category yet."}
                    </Typography>
                    {isHr && (
                        <Button
                            variant="contained"
                            startIcon={<UploadIcon />}
                            onClick={() => {
                                setSelectedParentFile(null);
                                const currentCat = categoryFilter !== 'all' ? categoryFilter : 'onboarding';
                                setUploadData({
                                    title: '',
                                    category: currentCat,
                                    department_target: '',
                                    is_mandatory: false,
                                    expiry_date: '',
                                    file: null,
                                    video_url: '',
                                    resource_type: 'file'
                                });
                                setUploadOpen(true);
                            }}
                            sx={{
                                bgcolor: '#7c3aed',
                                color: '#ffffff',
                                textTransform: 'none',
                                borderRadius: '8px',
                                fontWeight: 600,
                                px: 3,
                                py: 1,
                                '&:hover': { bgcolor: '#6d28d9' }
                            }}
                        >
                            Upload Files
                        </Button>
                    )}
                </Box>
            ) : viewMode === 'admin' ? (
                /* ADMIN TABLE */
                <TableContainer component={Paper} sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px', overflow: 'hidden' }}>
                    <Table>
                        <TableHead sx={{ bgcolor: colors.tableHeaderBg }}>
                            <TableRow sx={{ '& th': { borderBottom: `1px solid ${colors.cardBorder}`, color: colors.textSecondary, fontWeight: 600, fontSize: '13px' } }}>
                                <TableCell width="50"></TableCell>
                                <TableCell>FILE</TableCell>
                                <TableCell>CATEGORY</TableCell>
                                <TableCell>TYPE</TableCell>
                                <TableCell>TARGET</TableCell>
                                <TableCell align="right" width="120"></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {sortedAdminFiles.map((file) => {
                                const catStyle = getCategoryStyles(file.category);
                                const isExpiringSoon = file.expiry_date && new Date(file.expiry_date) <= new Date(new Date().getTime() + 30 * 24 * 60 * 60 * 1000);
                                const compRate = getFileCompletionRate(file.id);
                                return (
                                    <TableRow key={file.id} sx={{
                                        '& td': { borderBottom: `1px solid ${colors.cardBorder}`, py: 1.5 },
                                        '&:hover': { bgcolor: colors.tableRowHoverBg }
                                    }}>
                                        <TableCell>
                                            <Checkbox sx={{ color: colors.checkboxColor, '&.Mui-checked': { color: colors.textPrimary }, p: 0 }} />
                                        </TableCell>
                                        <TableCell>
                                            <Stack direction="row" alignItems="center" spacing={1.5}>
                                                {file.video_url ? <VideoIcon sx={{ color: '#8b5cf6', fontSize: 20 }} /> : getFileIcon(file.file)}
                                                <Box>
                                                    <Typography variant="body2" sx={{ fontWeight: 600, color: colors.textPrimary }}>
                                                        {file.title}
                                                    </Typography>
                                                    <Typography variant="caption" sx={{ color: file.video_url ? '#8b5cf6' : colors.textSecondary, display: 'block' }}>
                                                        {file.video_url ? '🔗 Video Link' : (file.file ? decodeURIComponent(file.file.split('/').pop()) : '')}
                                                    </Typography>
                                                </Box>
                                            </Stack>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={catStyle.label}
                                                size="small"
                                                sx={{
                                                    bgcolor: catStyle.bg,
                                                    color: catStyle.text,
                                                    border: catStyle.border,
                                                    fontSize: '11px',
                                                    fontWeight: 600
                                                }}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            {file.is_mandatory ? (
                                                <Chip
                                                    label="Mandatory"
                                                    size="small"
                                                    sx={{
                                                        bgcolor: isDarkMode ? 'rgba(239, 68, 68, 0.12)' : 'rgba(239, 68, 68, 0.08)',
                                                        color: isDarkMode ? '#f87171' : '#dc2626',
                                                        border: isDarkMode ? '1px solid rgba(239, 68, 68, 0.22)' : '1px solid rgba(239, 68, 68, 0.15)',
                                                        fontSize: '11px',
                                                        fontWeight: 600
                                                    }}
                                                />
                                            ) : (
                                                <Chip
                                                    label="Optional"
                                                    size="small"
                                                    sx={{
                                                        bgcolor: 'rgba(113, 113, 122, 0.1)',
                                                        color: colors.textSecondary,
                                                        border: `1px solid ${colors.cardBorder}`,
                                                        fontSize: '11px',
                                                        fontWeight: 500
                                                    }}
                                                />
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" sx={{ color: colors.textPrimary, fontSize: '13px' }}>
                                                {file.department_target || 'All departments'}
                                            </Typography>
                                        </TableCell>
                                        <TableCell align="right">
                                            <Stack direction="row" spacing={0.5} justifyContent="flex-end" alignItems="center">
                                                {(file.file || file.video_url) && (
                                                    <>
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => {
                                                                setPreviewFile(file);
                                                                setPreviewOpen(true);
                                                            }}
                                                            sx={{ color: colors.textSecondary }}
                                                            title={file.video_url ? 'Watch video' : 'View file'}
                                                        >
                                                            <VisibilityIcon fontSize="small" />
                                                        </IconButton>
                                                        {file.file && !file.video_url && (
                                                            <IconButton
                                                                size="small"
                                                                component="a"
                                                                href={file.file}
                                                                download
                                                                sx={{ color: colors.textSecondary }}
                                                                title="Download file"
                                                            >
                                                                <DownloadIcon fontSize="small" />
                                                            </IconButton>
                                                        )}
                                                    </>
                                                )}
                                                <IconButton size="small" onClick={(e) => handleMenuClick(e, file)} sx={{ color: colors.textSecondary }}>
                                                    <MoreVertIcon fontSize="small" />
                                                </IconButton>
                                            </Stack>
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                            {sortedAdminFiles.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={6} align="center" sx={{ py: 6 }}>
                                        <Typography color="text.secondary" variant="body2">
                                            No training files found matching the criteria.
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            ) : viewMode === 'assignments' ? (
                /* EMPLOYEE ASSIGNMENTS TABLE */
                <TableContainer component={Paper} sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px', overflow: 'hidden' }}>
                    <Table>
                        <TableHead sx={{ bgcolor: colors.tableHeaderBg }}>
                            <TableRow sx={{ '& th': { borderBottom: `1px solid ${colors.cardBorder}`, color: colors.textSecondary, fontWeight: 600, fontSize: '13px' } }}>
                                <TableCell>FILE</TableCell>
                                <TableCell>TYPE</TableCell>
                                <TableCell>TARGET</TableCell>
                                <TableCell>STATUS</TableCell>
                                <TableCell align="right" width="120"></TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {sortedEmployeeAssignments.map((asg) => {
                                // Support both flat API field and legacy nested path
                                const file = asg.push_training_file_detail || asg.push?.training_file_detail || {};
                                const catStyle = getCategoryStyles(file.category);
                                const isOverdue = file.expiry_date && new Date(file.expiry_date) < new Date() && !asg.is_acknowledged;
                                return (
                                    <TableRow key={asg.id} sx={{
                                        '& td': { borderBottom: `1px solid ${colors.cardBorder}`, py: 1.5 },
                                        '&:hover': { bgcolor: colors.tableRowHoverBg }
                                    }}>
                                        <TableCell>
                                            <Stack direction="row" alignItems="center" spacing={1.5}>
                                                {file.video_url ? <VideoIcon sx={{ color: '#8b5cf6', fontSize: 20 }} /> : getFileIcon(file.file)}
                                                <Box>
                                                    <Typography variant="body2" sx={{ fontWeight: 600, color: colors.textPrimary }}>
                                                        {file.title}
                                                    </Typography>
                                                    <Typography variant="caption" sx={{ color: file.video_url ? '#8b5cf6' : colors.textSecondary, display: 'block' }}>
                                                        {file.video_url ? '🔗 Video Link' : (file.file ? decodeURIComponent(file.file.split('/').pop()) : '')}
                                                    </Typography>
                                                </Box>
                                            </Stack>
                                        </TableCell>
                                        <TableCell>
                                            {file.is_mandatory ? (
                                                <Chip
                                                    label="Mandatory"
                                                    size="small"
                                                    sx={{
                                                        bgcolor: isDarkMode ? 'rgba(239, 68, 68, 0.12)' : 'rgba(239, 68, 68, 0.08)',
                                                        color: isDarkMode ? '#f87171' : '#dc2626',
                                                        border: isDarkMode ? '1px solid rgba(239, 68, 68, 0.22)' : '1px solid rgba(239, 68, 68, 0.15)',
                                                        fontSize: '11px',
                                                        fontWeight: 600
                                                    }}
                                                />
                                            ) : (
                                                <Chip
                                                    label="Optional"
                                                    size="small"
                                                    sx={{
                                                        bgcolor: 'rgba(113, 113, 122, 0.1)',
                                                        color: colors.textSecondary,
                                                        border: `1px solid ${colors.cardBorder}`,
                                                        fontSize: '11px',
                                                        fontWeight: 500
                                                    }}
                                                />
                                            )}
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" sx={{ color: colors.textPrimary, fontSize: '13px' }}>
                                                {file.department_target || 'All departments'}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            {asg.is_acknowledged ? (
                                                <Stack direction="row" alignItems="center" spacing={0.5} sx={{ color: isDarkMode ? '#34d399' : '#059669' }}>
                                                    <CheckCircleIcon sx={{ fontSize: 16 }} />
                                                    <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '13px' }}>
                                                        Completed
                                                    </Typography>
                                                </Stack>
                                            ) : (
                                                <Button
                                                    variant="contained"
                                                    size="small"
                                                    onClick={() => {
                                                        setActiveAssignment(asg);
                                                        setAcknowledgeOpen(true);
                                                    }}
                                                    sx={{
                                                        bgcolor: '#7c3aed',
                                                        color: '#ffffff',
                                                        textTransform: 'none',
                                                        borderRadius: '6px',
                                                        fontWeight: 600,
                                                        py: 0.5,
                                                        fontSize: '12px',
                                                        '&:hover': { bgcolor: '#6d28d9' }
                                                    }}
                                                >
                                                    Acknowledge
                                                </Button>
                                            )}
                                        </TableCell>

                                        <TableCell align="right">
                                            <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                                                {(file.file || file.video_url) && (
                                                    <>
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => {
                                                                setPreviewFile(file);
                                                                setPreviewOpen(true);
                                                            }}
                                                            sx={{ color: colors.textSecondary }}
                                                            title={file.video_url ? 'Watch video' : 'View file'}
                                                        >
                                                            <VisibilityIcon fontSize="small" />
                                                        </IconButton>
                                                        {file.file && !file.video_url && (
                                                            <IconButton
                                                                size="small"
                                                                component="a"
                                                                href={file.file}
                                                                download
                                                                sx={{ color: colors.textSecondary }}
                                                                title="Download file"
                                                            >
                                                                <DownloadIcon fontSize="small" />
                                                            </IconButton>
                                                        )}
                                                    </>
                                                )}
                                            </Stack>
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                            {sortedEmployeeAssignments.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={5} align="center" sx={{ py: 6 }}>
                                        <Typography color="text.secondary" variant="body2">
                                            No training assignments found.
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            ) : (
                /* RESOURCE LIBRARY TABLE (READ-ONLY) */
                <TableContainer component={Paper} sx={{ bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, borderRadius: '12px', overflow: 'hidden' }}>
                    <Table>
                        <TableHead sx={{ bgcolor: colors.tableHeaderBg }}>
                            <TableRow sx={{ '& th': { borderBottom: `1px solid ${colors.cardBorder}`, color: colors.textSecondary, fontWeight: 600, fontSize: '13px' } }}>
                                <TableCell>TITLE & FILE</TableCell>
                                <TableCell>DESCRIPTION</TableCell>
                                <TableCell>CATEGORY</TableCell>
                                <TableCell>UPLOADED BY</TableCell>
                                <TableCell>UPLOAD DATE</TableCell>
                                <TableCell>FILE TYPE</TableCell>
                                <TableCell align="right" width="120">ACTIONS</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {sortedAdminFiles.map((file) => {
                                const catStyle = getCategoryStyles(file.category);
                                const uploadDate = file.created_at ? new Date(file.created_at).toLocaleDateString() : '—';
                                return (
                                    <TableRow key={file.id} sx={{
                                        '& td': { borderBottom: `1px solid ${colors.cardBorder}`, py: 1.5 },
                                        '&:hover': { bgcolor: colors.tableRowHoverBg }
                                    }}>
                                        <TableCell>
                                            <Stack direction="row" alignItems="center" spacing={1.5}>
                                                {getFileIcon(file.file)}
                                                <Box>
                                                    <Typography variant="body2" sx={{ fontWeight: 600, color: colors.textPrimary }}>
                                                        {file.title}
                                                    </Typography>
                                                    <Typography variant="caption" sx={{ color: colors.textSecondary, display: 'block' }}>
                                                        {file.file ? decodeURIComponent(file.file.split('/').pop()) : ''}
                                                    </Typography>
                                                </Box>
                                            </Stack>
                                        </TableCell>
                                        <TableCell sx={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            <Tooltip title={file.description || ''} arrow>
                                                <Typography variant="body2" sx={{ color: colors.textSecondary, fontSize: '13px' }}>
                                                    {file.description || '—'}
                                                </Typography>
                                            </Tooltip>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={catStyle.label}
                                                size="small"
                                                sx={{
                                                    bgcolor: catStyle.bg,
                                                    color: catStyle.text,
                                                    border: catStyle.border,
                                                    fontSize: '11px',
                                                    fontWeight: 600
                                                }}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" sx={{ color: colors.textPrimary, fontSize: '13px' }}>
                                                {file.uploaded_by_detail?.full_name || file.uploaded_by_detail?.username || 'HR System'}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Typography variant="body2" sx={{ color: colors.textSecondary, fontSize: '13px' }}>
                                                {uploadDate}
                                            </Typography>
                                        </TableCell>
                                        <TableCell>
                                            <Chip
                                                label={getFileTypeLabel(file.file, file.file_type)}
                                                size="small"
                                                variant="outlined"
                                                sx={{
                                                    borderColor: colors.cardBorder,
                                                    color: colors.textSecondary,
                                                    fontSize: '11px',
                                                    fontWeight: 500
                                                }}
                                            />
                                        </TableCell>
                                        <TableCell align="right">
                                            <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                                                {file.file && (
                                                    <>
                                                        <IconButton
                                                            size="small"
                                                            onClick={() => {
                                                                setPreviewFile(file);
                                                                setPreviewOpen(true);
                                                            }}
                                                            sx={{ color: colors.textSecondary }}
                                                            title="View file"
                                                        >
                                                            <VisibilityIcon fontSize="small" />
                                                        </IconButton>
                                                        <IconButton
                                                            size="small"
                                                            component="a"
                                                            href={file.file}
                                                            download
                                                            sx={{ color: colors.textSecondary }}
                                                            title="Download file"
                                                        >
                                                            <DownloadIcon fontSize="small" />
                                                        </IconButton>
                                                    </>
                                                )}
                                            </Stack>
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                            {sortedAdminFiles.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={7} align="center" sx={{ py: 6 }}>
                                        <Typography color="text.secondary" variant="body2">
                                            No training materials found.
                                        </Typography>
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </TableContainer>
            )}

            {/* Row Actions Menu */}
            <Menu
                anchorEl={anchorEl}
                open={Boolean(anchorEl)}
                onClose={handleMenuClose}
                PaperProps={{
                    sx: {
                        bgcolor: colors.cardBg,
                        border: `1px solid ${colors.cardBorder}`,
                        color: colors.textPrimary,
                        borderRadius: '8px',
                        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.2)',
                        '& .MuiMenuItem-root': {
                            fontSize: '13px',
                            py: 1,
                            px: 2,
                            '&:hover': { bgcolor: isDarkMode ? '#1e1e24' : '#f4f4f5' }
                        }
                    }
                }}
            >
                {selectedMenuFile && (selectedMenuFile.file || selectedMenuFile.video_url) && (
                    <MenuItem onClick={() => {
                        handleMenuClose();
                        setPreviewFile(selectedMenuFile);
                        setPreviewOpen(true);
                    }}>
                        <ListItemIcon><VisibilityIcon fontSize="small" sx={{ color: colors.textPrimary }} /></ListItemIcon>
                        {selectedMenuFile.video_url ? 'Watch Video' : 'View Document'}
                    </MenuItem>
                )}
                <MenuItem onClick={() => {
                    handleMenuClose();
                    setPushPayload({
                        training_file: selectedMenuFile.id,
                        target_departments: selectedMenuFile.department_target ? [selectedMenuFile.department_target] : [],
                        target_members: [],
                        is_mandatory: selectedMenuFile.is_mandatory
                    });
                    setPushOpen(true);
                }}>
                    <ListItemIcon><SendIcon fontSize="small" sx={{ color: colors.textPrimary }} /></ListItemIcon>
                    Vault Push
                </MenuItem>
                <MenuItem onClick={() => {
                    handleMenuClose();
                    setSelectedParentFile(selectedMenuFile);
                    setUploadData({
                        title: selectedMenuFile.title,
                        category: selectedMenuFile.category,
                        department_target: selectedMenuFile.department_target,
                        is_mandatory: selectedMenuFile.is_mandatory,
                        expiry_date: selectedMenuFile.expiry_date || '',
                        file: null,
                        video_url: selectedMenuFile.video_url || '',
                        resource_type: selectedMenuFile.video_url ? 'video_url' : 'file'
                    });
                    setUploadOpen(true);
                }}>
                    <ListItemIcon><HistoryIcon fontSize="small" sx={{ color: colors.textPrimary }} /></ListItemIcon>
                    New Version
                </MenuItem>
                <MenuItem onClick={() => {
                    handleMenuClose();
                    handleViewHistory(selectedMenuFile);
                }}>
                    <ListItemIcon><HistoryIcon fontSize="small" sx={{ color: colors.textPrimary }} /></ListItemIcon>
                    Version History
                </MenuItem>
                {/* Find campaigns using dashboardData */}
                {dashboardData?.file_stats?.some(s => s.file_id === selectedMenuFile?.id) && (
                    <MenuItem onClick={() => {
                        const pushId = dashboardData.file_stats.find(s => s.file_id === selectedMenuFile.id)?.push_id;
                        handleMenuClose();
                        if (pushId) getTrainingComplianceDetails(pushId);
                    }}>
                        <ListItemIcon><InfoIcon fontSize="small" sx={{ color: colors.textPrimary }} /></ListItemIcon>
                        Push Tracking details
                    </MenuItem>
                )}
                <MenuItem onClick={() => {
                    const id = selectedMenuFile.id;
                    handleMenuClose();
                    handleDeleteFile(id);
                }} sx={{ color: isDarkMode ? '#f87171' : '#dc2626', '&:hover': { bgcolor: isDarkMode ? 'rgba(239, 68, 68, 0.1) !important' : 'rgba(239, 68, 68, 0.05) !important' } }}>
                    <ListItemIcon><DeleteIcon fontSize="small" sx={{ color: isDarkMode ? '#f87171' : '#dc2626' }} /></ListItemIcon>
                    Delete Document
                </MenuItem>
            </Menu>

            {/* Dialog: Upload / New Version */}
            <Dialog
                open={uploadOpen}
                onClose={() => setUploadOpen(false)}
                maxWidth="sm"
                fullWidth
                PaperProps={{
                    sx: { bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, color: colors.textPrimary, borderRadius: '12px' }
                }}
            >
                <form onSubmit={handleUploadSubmit}>
                    <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}`, fontWeight: 650 }}>
                        {selectedParentFile ? `Upload New Version: ${selectedParentFile.title}` : 'Upload Training Document'}
                    </DialogTitle>
                    <DialogContent dividers sx={{ borderBottom: `1px solid ${colors.divider}`, py: 3 }}>
                        <Stack spacing={2.5}>
                            <TextField
                                label="Document Title"
                                required
                                fullWidth
                                value={uploadData.title}
                                onChange={(e) => setUploadData({ ...uploadData, title: e.target.value })}
                                InputLabelProps={{ sx: { color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } } }}
                                sx={{
                                    '& .MuiOutlinedInput-root': {
                                        color: colors.textPrimary,
                                        '& fieldset': { borderColor: colors.cardBorder },
                                        '&:hover fieldset': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                        '&.Mui-focused fieldset': { borderColor: '#7c3aed' }
                                    }
                                }}
                            />
                            <FormControl fullWidth>
                                <InputLabel sx={{ color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } }}>Category</InputLabel>
                                <Select
                                    value={uploadData.category}
                                    label="Category"
                                    disabled
                                    onChange={(e) => setUploadData({ ...uploadData, category: e.target.value })}
                                    sx={{
                                        color: colors.textPrimary,
                                        '& .MuiOutlinedInput-notchedOutline': { borderColor: colors.cardBorder },
                                        '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                        '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#7c3aed' }
                                    }}
                                >
                                    {categoriesList.map((cat) => (
                                        <MenuItem key={cat.value} value={cat.value}>{cat.label}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                            <FormControl fullWidth>
                                <InputLabel sx={{ color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } }}>Target Department</InputLabel>
                                <Select
                                    value={uploadData.department_target}
                                    label="Target Department"
                                    onChange={(e) => setUploadData({ ...uploadData, department_target: e.target.value })}
                                    sx={{
                                        color: colors.textPrimary,
                                        '& .MuiOutlinedInput-notchedOutline': { borderColor: colors.cardBorder },
                                        '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                        '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#7c3aed' }
                                    }}
                                >
                                    <MenuItem value=""><em>None (General)</em></MenuItem>
                                    {departments.map((dept) => (
                                        <MenuItem key={dept.id} value={dept.name}>{dept.name}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                            <TextField
                                label="Expiry Date"
                                type="date"
                                fullWidth
                                InputLabelProps={{ shrink: true, sx: { color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } } }}
                                value={uploadData.expiry_date}
                                onChange={(e) => setUploadData({ ...uploadData, expiry_date: e.target.value })}
                                sx={{
                                    '& .MuiOutlinedInput-root': {
                                        color: colors.textPrimary,
                                        '& fieldset': { borderColor: colors.cardBorder },
                                        '&:hover fieldset': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                        '&.Mui-focused fieldset': { borderColor: '#7c3aed' }
                                    }
                                }}
                            />
                            <Stack direction="row" alignItems="center">
                                <Checkbox
                                    checked={uploadData.is_mandatory}
                                    onChange={(e) => setUploadData({ ...uploadData, is_mandatory: e.target.checked })}
                                    sx={{ color: colors.checkboxColor, '&.Mui-checked': { color: '#7c3aed' } }}
                                />
                                <ListItemText
                                    primary={<span style={{ color: colors.textPrimary, fontSize: '14px', fontWeight: 500 }}>Mark as Mandatory Reading</span>}
                                    secondary={<span style={{ color: colors.textSecondary, fontSize: '12px' }}>Will auto-assign tasks to pushed users</span>}
                                />
                            </Stack>

                            {/* Resource type toggle */}
                            <Box>
                                <Typography variant="caption" sx={{ color: colors.textSecondary, mb: 1, display: 'block', fontWeight: 600 }}>Resource Type</Typography>
                                <Stack direction="row" spacing={1}>
                                    <Button
                                        variant={uploadData.resource_type === 'file' ? 'contained' : 'outlined'}
                                        size="small"
                                        startIcon={<DocIcon sx={{ fontSize: 16 }} />}
                                        onClick={() => setUploadData({ ...uploadData, resource_type: 'file', video_url: '' })}
                                        sx={{
                                            textTransform: 'none', borderRadius: '7px', fontWeight: 500,
                                            ...(uploadData.resource_type === 'file'
                                                ? { bgcolor: '#7c3aed', color: '#fff', '&:hover': { bgcolor: '#6d28d9' } }
                                                : { borderColor: colors.cardBorder, color: colors.textSecondary })
                                        }}
                                    >File Upload</Button>
                                    <Button
                                        variant={uploadData.resource_type === 'video_url' ? 'contained' : 'outlined'}
                                        size="small"
                                        startIcon={<VideoIcon sx={{ fontSize: 16 }} />}
                                        onClick={() => setUploadData({ ...uploadData, resource_type: 'video_url', file: null })}
                                        sx={{
                                            textTransform: 'none', borderRadius: '7px', fontWeight: 500,
                                            ...(uploadData.resource_type === 'video_url'
                                                ? { bgcolor: '#7c3aed', color: '#fff', '&:hover': { bgcolor: '#6d28d9' } }
                                                : { borderColor: colors.cardBorder, color: colors.textSecondary })
                                        }}
                                    >Video URL</Button>
                                </Stack>
                            </Box>

                            {uploadData.resource_type === 'file' ? (
                                <Button
                                    variant="outlined"
                                    component="label"
                                    startIcon={<UploadIcon sx={{ color: '#7c3aed' }} />}
                                    fullWidth
                                    sx={{
                                        py: 1.5,
                                        borderColor: colors.cardBorder,
                                        color: colors.textPrimary,
                                        textTransform: 'none',
                                        borderRadius: '8px',
                                        '&:hover': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8', bgcolor: isDarkMode ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)' }
                                    }}
                                >
                                    {uploadData.file ? uploadData.file.name : 'Select File (PDF, Doc, Slides, Image)'}
                                    <input
                                        type="file"
                                        hidden
                                        accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.png,.jpg,.jpeg,.gif,.webp,.svg"
                                        onChange={(e) => setUploadData({ ...uploadData, file: e.target.files[0] })}
                                    />
                                </Button>
                            ) : (
                                <TextField
                                    label="Video URL"
                                    placeholder="https://youtube.com/watch?v=... or Vimeo, Drive, Loom link"
                                    required
                                    fullWidth
                                    value={uploadData.video_url}
                                    onChange={(e) => setUploadData({ ...uploadData, video_url: e.target.value })}
                                    InputLabelProps={{ sx: { color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } } }}
                                    helperText="Paste a YouTube, Vimeo, Google Drive, or Loom URL"
                                    FormHelperTextProps={{ sx: { color: colors.textSecondary } }}
                                    sx={{
                                        '& .MuiOutlinedInput-root': {
                                            color: colors.textPrimary,
                                            '& fieldset': { borderColor: colors.cardBorder },
                                            '&:hover fieldset': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                            '&.Mui-focused fieldset': { borderColor: '#7c3aed' }
                                        }
                                    }}
                                />
                            )}
                        </Stack>
                    </DialogContent>
                    <DialogActions sx={{ p: 2 }}>
                        <Button onClick={() => setUploadOpen(false)} sx={{ color: colors.textSecondary, textTransform: 'none' }}>Cancel</Button>
                        <Button
                            type="submit"
                            variant="contained"
                            disabled={loading}
                            sx={{
                                bgcolor: colors.primaryBtnBg,
                                color: colors.primaryBtnText,
                                fontWeight: 600,
                                textTransform: 'none',
                                borderRadius: '8px',
                                px: 3,
                                '&:hover': { bgcolor: colors.primaryBtnHover }
                            }}
                        >
                            {selectedParentFile ? 'Upload Version' : 'Save Resource'}
                        </Button>
                    </DialogActions>
                </form>
            </Dialog>

            {/* Dialog: New Category */}
            <Dialog
                open={categoryDialogOpen}
                onClose={() => setCategoryDialogOpen(false)}
                maxWidth="xs"
                fullWidth
                PaperProps={{
                    sx: { bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, color: colors.textPrimary, borderRadius: '12px' }
                }}
            >
                <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}`, fontWeight: 650 }}>New Training Category</DialogTitle>
                <DialogContent dividers sx={{ borderBottom: `1px solid ${colors.divider}`, py: 3 }}>
                    <Stack spacing={2}>
                        <Typography variant="body2" sx={{ color: colors.textSecondary }}>
                            Add a custom category label. It will be available in the category filter and upload form for this session.
                        </Typography>
                        <TextField
                            label="Category Name"
                            placeholder="e.g. Leadership, Safety, Product"
                            required
                            fullWidth
                            autoFocus
                            value={newCategoryName}
                            onChange={(e) => setNewCategoryName(e.target.value)}
                            InputLabelProps={{ sx: { color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } } }}
                            sx={{
                                '& .MuiOutlinedInput-root': {
                                    color: colors.textPrimary,
                                    '& fieldset': { borderColor: colors.cardBorder },
                                    '&:hover fieldset': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                    '&.Mui-focused fieldset': { borderColor: '#7c3aed' }
                                }
                            }}
                        />
                    </Stack>
                </DialogContent>
                <DialogActions sx={{ p: 2 }}>
                    <Button onClick={() => setCategoryDialogOpen(false)} sx={{ color: colors.textSecondary, textTransform: 'none' }}>Cancel</Button>
                    <Button
                        variant="contained"
                        disabled={!newCategoryName.trim()}
                        onClick={() => {
                            const slug = newCategoryName.trim().toLowerCase().replace(/\s+/g, '_');
                            const label = newCategoryName.trim();
                            if (!categoriesList.find(c => c.value === slug)) {
                                setCategoriesList([...categoriesList, { value: slug, label }]);
                            }
                            setCategoryFilter(slug);
                            setCategoryDialogOpen(false);
                            showSnackbar(`Category "${label}" added.`, 'success');
                        }}
                        sx={{
                            bgcolor: '#7c3aed', color: '#fff', fontWeight: 600,
                            textTransform: 'none', borderRadius: '8px', px: 3,
                            '&:hover': { bgcolor: '#6d28d9' }
                        }}
                    >
                        Add Category
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Dialog: Vault Push */}
            <Dialog
                open={pushOpen}
                onClose={() => setPushOpen(false)}
                maxWidth="sm"
                fullWidth
                PaperProps={{
                    sx: { bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, color: colors.textPrimary, borderRadius: '12px' }
                }}
            >
                <form onSubmit={handlePushSubmit}>
                    <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}`, fontWeight: 650 }}>
                        Vault Push Training Campaign
                    </DialogTitle>
                    <DialogContent dividers sx={{ borderBottom: `1px solid ${colors.divider}`, py: 3 }}>
                        <Stack spacing={2.5}>
                            <FormControl fullWidth required>
                                <InputLabel sx={{ color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } }}>Training File</InputLabel>
                                <Select
                                    value={pushPayload.training_file}
                                    label="Training File"
                                    onChange={(e) => {
                                        const selected = libraryFiles.find(f => f.id === e.target.value);
                                        setPushPayload({
                                            ...pushPayload,
                                            training_file: e.target.value,
                                            is_mandatory: selected ? selected.is_mandatory : false
                                        });
                                    }}
                                    sx={{
                                        color: colors.textPrimary,
                                        '& .MuiOutlinedInput-notchedOutline': { borderColor: colors.cardBorder },
                                        '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                        '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#7c3aed' }
                                    }}
                                >
                                    {libraryFiles.map((file) => (
                                        <MenuItem key={file.id} value={file.id}>{file.title} (v{file.version})</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>

                            <FormControl fullWidth>
                                <InputLabel sx={{ color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } }}>Target Departments</InputLabel>
                                <Select
                                    multiple
                                    value={pushPayload.target_departments}
                                    label="Target Departments"
                                    input={<OutlinedInput label="Target Departments" sx={{ color: colors.textPrimary, '& fieldset': { borderColor: colors.cardBorder } }} />}
                                    renderValue={(selected) => selected.join(', ')}
                                    onChange={(e) => setPushPayload({ ...pushPayload, target_departments: e.target.value })}
                                >
                                    {departments.map((dept) => (
                                        <MenuItem key={dept.id} value={dept.name}>
                                            <Checkbox checked={pushPayload.target_departments.indexOf(dept.name) > -1} sx={{ color: colors.checkboxColor, '&.Mui-checked': { color: '#7c3aed' } }} />
                                            <ListItemText primary={dept.name} />
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>

                            <FormControl fullWidth>
                                <InputLabel sx={{ color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } }}>Target Members</InputLabel>
                                <Select
                                    multiple
                                    value={pushPayload.target_members}
                                    label="Target Members"
                                    input={<OutlinedInput label="Target Members" sx={{ color: colors.textPrimary, '& fieldset': { borderColor: colors.cardBorder } }} />}
                                    renderValue={(selected) => selected.map(id => {
                                        const m = membersList.find(u => u.id === id);
                                        return m ? (m.full_name || m.username) : id;
                                    }).join(', ')}
                                    onChange={(e) => setPushPayload({ ...pushPayload, target_members: e.target.value })}
                                >
                                    {membersList.map((m) => (
                                        <MenuItem key={m.id} value={m.id}>
                                            <Checkbox checked={pushPayload.target_members.indexOf(m.id) > -1} sx={{ color: colors.checkboxColor, '&.Mui-checked': { color: '#7c3aed' } }} />
                                            <ListItemText primary={m.full_name || m.username} secondary={m.email} />
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>

                            <Stack direction="row" alignItems="center">
                                <Checkbox
                                    checked={pushPayload.is_mandatory}
                                    onChange={(e) => setPushPayload({ ...pushPayload, is_mandatory: e.target.checked })}
                                    sx={{ color: colors.checkboxColor, '&.Mui-checked': { color: '#7c3aed' } }}
                                />
                                <ListItemText
                                    primary={<span style={{ color: colors.textPrimary, fontSize: '14px', fontWeight: 500 }}>Mandatory Compliance Requirement</span>}
                                    secondary={<span style={{ color: colors.textSecondary, fontSize: '12px' }}>Assigned users must acknowledge reading</span>}
                                />
                            </Stack>
                        </Stack>
                    </DialogContent>
                    <DialogActions sx={{ p: 2 }}>
                        <Button onClick={() => setPushOpen(false)} sx={{ color: colors.textSecondary, textTransform: 'none' }}>Cancel</Button>
                        <Button
                            type="submit"
                            variant="contained"
                            disabled={loading}
                            startIcon={<SendIcon sx={{ fontSize: 16 }} />}
                            sx={{
                                bgcolor: colors.primaryBtnBg,
                                color: colors.primaryBtnText,
                                fontWeight: 600,
                                textTransform: 'none',
                                borderRadius: '8px',
                                px: 3,
                                '&:hover': { bgcolor: colors.primaryBtnHover }
                            }}
                        >
                            Push to Vaults
                        </Button>
                    </DialogActions>
                </form>
            </Dialog>

            {/* Dialog: Version History */}
            <Dialog
                open={historyOpen}
                onClose={() => setHistoryOpen(false)}
                maxWidth="sm"
                fullWidth
                PaperProps={{
                    sx: { bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, color: colors.textPrimary, borderRadius: '12px' }
                }}
            >
                <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}`, fontWeight: 650 }}>Document Version History</DialogTitle>
                <DialogContent dividers sx={{ borderBottom: `1px solid ${colors.divider}`, py: 3 }}>
                    <Stack spacing={2}>
                        {versionHistory.map((ver) => (
                            <Paper key={ver.id} variant="outlined" sx={{ p: 2, bgcolor: isDarkMode ? '#161619' : '#f9f9fb', borderColor: colors.cardBorder, borderRadius: '8px' }}>
                                <Stack direction="row" justifyContent="space-between" alignItems="center">
                                    <Box>
                                        <Typography variant="body2" sx={{ fontWeight: 600, color: colors.textPrimary }}>
                                            {ver.title}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            Version {ver.version} • Uploaded on {new Date(ver.created_at).toLocaleDateString()}
                                        </Typography>
                                    </Box>
                                    <Button
                                        size="small"
                                        variant="outlined"
                                        href={ver.file}
                                        target="_blank"
                                        startIcon={<DownloadIcon sx={{ fontSize: 14 }} />}
                                        sx={{ borderColor: colors.cardBorder, color: colors.textPrimary, textTransform: 'none', borderRadius: '6px', '&:hover': { borderColor: colors.cardBorder, bgcolor: isDarkMode ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)' } }}
                                    >
                                        Download
                                    </Button>
                                </Stack>
                            </Paper>
                        ))}
                        {versionHistory.length === 0 && (
                            <Typography align="center" variant="body2" color="text.secondary">No other versions found.</Typography>
                        )}
                    </Stack>
                </DialogContent>
                <DialogActions sx={{ p: 2 }}>
                    <Button onClick={() => setHistoryOpen(false)} sx={{ color: colors.textSecondary, textTransform: 'none' }}>Close</Button>
                </DialogActions>
            </Dialog>

            {/* Dialog: Acknowledge */}
            <Dialog
                open={acknowledgeOpen}
                onClose={() => setAcknowledgeOpen(false)}
                maxWidth="xs"
                fullWidth
                PaperProps={{
                    sx: { bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, color: colors.textPrimary, borderRadius: '12px' }
                }}
            >
                <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}`, fontWeight: 650 }}>Acknowledge Training Document</DialogTitle>
                <DialogContent dividers sx={{ borderBottom: `1px solid ${colors.divider}`, py: 3 }}>
                    <Stack spacing={2}>
                        <Typography variant="body2" sx={{ color: colors.textSecondary }}>
                            I verify that I have fully read and understood the training material:
                        </Typography>
                        <Typography variant="subtitle1" sx={{ fontWeight: 700, color: '#7c3aed' }}>
                            {activeAssignment?.push?.training_file_detail?.title}
                        </Typography>
                        <TextField
                            label="Acknowledgement Notes / Remarks"
                            placeholder="Optional comments..."
                            multiline
                            rows={3}
                            fullWidth
                            value={ackNotes}
                            onChange={(e) => setAckNotes(e.target.value)}
                            InputLabelProps={{ sx: { color: colors.textSecondary, '&.Mui-focused': { color: '#7c3aed' } } }}
                            sx={{
                                '& .MuiOutlinedInput-root': {
                                    color: colors.textPrimary,
                                    '& fieldset': { borderColor: colors.cardBorder },
                                    '&:hover fieldset': { borderColor: isDarkMode ? '#27272a' : '#d4d4d8' },
                                    '&.Mui-focused fieldset': { borderColor: '#7c3aed' }
                                }
                            }}
                        />
                    </Stack>
                </DialogContent>
                <DialogActions sx={{ p: 2 }}>
                    <Button onClick={() => setAcknowledgeOpen(false)} sx={{ color: colors.textSecondary, textTransform: 'none' }}>Cancel</Button>
                    <Button
                        variant="contained"
                        onClick={handleAcknowledge}
                        disabled={loading}
                        sx={{
                            bgcolor: isDarkMode ? '#34d399' : '#10b981',
                            color: isDarkMode ? '#064e3b' : '#ffffff',
                            fontWeight: 700,
                            textTransform: 'none',
                            borderRadius: '8px',
                            px: 3,
                            '&:hover': { bgcolor: isDarkMode ? '#10b981' : '#059669' }
                        }}
                    >
                        Sign & Acknowledge
                    </Button>
                </DialogActions>
            </Dialog>

            {/* Dialog: Push Details */}
            <Dialog
                open={pushDetailsOpen}
                onClose={() => setPushDetailsOpen(false)}
                maxWidth="md"
                fullWidth
                PaperProps={{
                    sx: { bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, color: colors.textPrimary, borderRadius: '12px' }
                }}
            >
                <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}`, fontWeight: 650 }}>
                    Push Campaign Details: {selectedPushDetails?.training_file_detail?.title}
                </DialogTitle>
                <DialogContent dividers sx={{ borderBottom: `1px solid ${colors.divider}`, py: 3 }}>
                    <TableContainer component={Paper} sx={{ bgcolor: isDarkMode ? '#161619' : '#f9f9fb', border: `1px solid ${colors.cardBorder}`, borderRadius: '8px' }}>
                        <Table size="small">
                            <TableHead sx={{ bgcolor: isDarkMode ? '#1d1d22' : '#f4f4f5' }}>
                                <TableRow sx={{ '& th': { borderBottom: `1px solid ${colors.cardBorder}`, color: colors.textSecondary, fontWeight: 600 } }}>
                                    <TableCell>Employee Name</TableCell>
                                    <TableCell>Email</TableCell>
                                    <TableCell>Status</TableCell>
                                    <TableCell>Acknowledged At</TableCell>
                                    <TableCell>Task ID</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {selectedPushDetails?.recipients?.map((rec) => (
                                    <TableRow key={rec.id} sx={{ '& td': { borderBottom: `1px solid ${colors.cardBorder}` } }}>
                                        <TableCell sx={{ color: colors.textPrimary }}>{rec.user_detail?.full_name || rec.user_detail?.username}</TableCell>
                                        <TableCell sx={{ color: colors.textSecondary }}>{rec.user_detail?.email}</TableCell>
                                        <TableCell>
                                            {rec.is_acknowledged ? (
                                                <Chip label="Read" size="small" sx={{ bgcolor: isDarkMode ? 'rgba(52, 211, 153, 0.12)' : 'rgba(52, 211, 153, 0.08)', color: isDarkMode ? '#34d399' : '#059669', border: isDarkMode ? '1px solid rgba(52, 211, 153, 0.22)' : '1px solid rgba(52, 211, 153, 0.15)', fontWeight: 600 }} />
                                            ) : (
                                                <Chip label="Pending" size="small" variant="outlined" sx={{ borderColor: colors.cardBorder, color: colors.textSecondary, fontWeight: 500 }} />
                                            )}
                                        </TableCell>
                                        <TableCell sx={{ color: colors.textSecondary }}>
                                            {rec.acknowledged_at ? new Date(rec.acknowledged_at).toLocaleString() : '—'}
                                        </TableCell>
                                        <TableCell sx={{ color: colors.textSecondary }}>{rec.task_id || '—'}</TableCell>
                                    </TableRow>
                                ))}
                                {(!selectedPushDetails?.recipients || selectedPushDetails.recipients.length === 0) && (
                                    <TableRow>
                                        <TableCell colSpan={5} align="center" sx={{ py: 3 }}>
                                            <Typography color="text.secondary" variant="body2">No recipients assigned.</Typography>
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </DialogContent>
                <DialogActions sx={{ p: 2 }}>
                    <Button onClick={() => setPushDetailsOpen(false)} sx={{ color: colors.textSecondary, textTransform: 'none' }}>Close</Button>
                </DialogActions>
            </Dialog>

            {/* Dialog: Media Preview / Video Viewer */}
            <Dialog
                open={previewOpen}
                onClose={() => setPreviewOpen(false)}
                maxWidth="md"
                fullWidth
                PaperProps={{
                    sx: { bgcolor: colors.cardBg, border: `1px solid ${colors.cardBorder}`, color: colors.textPrimary, borderRadius: '12px' }
                }}
            >
                <DialogTitle sx={{ borderBottom: `1px solid ${colors.divider}`, fontWeight: 650, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>{previewFile?.title}</Typography>
                    <IconButton onClick={() => setPreviewOpen(false)} sx={{ color: colors.textSecondary }}>
                        <CloseIcon />
                    </IconButton>
                </DialogTitle>
                <DialogContent dividers sx={{ borderBottom: `1px solid ${colors.divider}`, p: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', bgcolor: isDarkMode ? '#09090b' : '#f4f4f5' }}>
                    {previewFile?.video_url ? (
                        /* Video URL embed */
                        (() => {
                            let embedUrl = previewFile.video_url;
                            // YouTube
                            const ytMatch = embedUrl.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
                            if (ytMatch) embedUrl = `https://www.youtube.com/embed/${ytMatch[1]}`;
                            // Vimeo
                            const vimeoMatch = embedUrl.match(/vimeo\.com\/(\d+)/);
                            if (vimeoMatch) embedUrl = `https://player.vimeo.com/video/${vimeoMatch[1]}`;
                            // Loom
                            const loomMatch = embedUrl.match(/loom\.com\/share\/([a-zA-Z0-9]+)/);
                            if (loomMatch) embedUrl = `https://www.loom.com/embed/${loomMatch[1]}`;
                            // Google Drive
                            const driveMatch = embedUrl.match(/drive\.google\.com\/file\/d\/([a-zA-Z0-9_-]+)/);
                            if (driveMatch) embedUrl = `https://drive.google.com/file/d/${driveMatch[1]}/preview`;
                            return (
                                <Box sx={{ width: '100%', aspectRatio: '16/9' }}>
                                    <iframe
                                        src={embedUrl}
                                        width="100%"
                                        height="100%"
                                        style={{ border: 'none' }}
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                        allowFullScreen
                                        title={previewFile.title}
                                    />
                                </Box>
                            );
                        })()
                    ) : previewFile?.file ? (
                        (() => {
                            const ext = previewFile.file_type || previewFile.file.split('.').pop().toLowerCase();
                            if (['mp4', 'webm', 'ogg'].includes(ext)) {
                                return (
                                    <Box sx={{ width: '100%', aspectRatio: '16/9', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                                        <video
                                            src={previewFile.file}
                                            controls
                                            autoPlay
                                            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                                        />
                                    </Box>
                                );
                            } else if (ext === 'pdf') {
                                return (
                                    <Box sx={{ width: '100%', height: '600px' }}>
                                        <iframe
                                            src={`${previewFile.file}#toolbar=0`}
                                            width="100%"
                                            height="100%"
                                            style={{ border: 'none' }}
                                            title={previewFile.title}
                                        />
                                    </Box>
                                );
                            } else if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp'].includes(ext)) {
                                return (
                                    <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                                        <img
                                            src={previewFile.file}
                                            alt={previewFile.title}
                                            style={{ maxWidth: '100%', maxHeight: '500px', borderRadius: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
                                        />
                                    </Box>
                                );
                            } else {
                                return (
                                    <Box sx={{ p: 6, textAlign: 'center', maxWidth: 500 }}>
                                        {getFileIcon(previewFile.file)}
                                        <Typography variant="h6" sx={{ mt: 2, fontWeight: 600 }}>
                                            Preview Not Available
                                        </Typography>
                                        <Typography variant="body2" sx={{ color: colors.textSecondary, mt: 1, mb: 3 }}>
                                            This file type ({ext.toUpperCase()}) cannot be rendered directly in the browser. You can download it to view it locally.
                                        </Typography>
                                        <Button
                                            variant="contained"
                                            href={previewFile.file}
                                            download
                                            startIcon={<DownloadIcon />}
                                            sx={{
                                                bgcolor: '#7c3aed',
                                                color: '#ffffff',
                                                textTransform: 'none',
                                                borderRadius: '8px',
                                                '&:hover': { bgcolor: '#6d28d9' }
                                            }}
                                        >
                                            Download Document
                                        </Button>
                                    </Box>
                                );
                            }
                        })()
                    ) : (
                        <Box sx={{ p: 6, textAlign: 'center' }}>
                            <Typography color="text.secondary">No resource linked.</Typography>
                        </Box>
                    )}
                </DialogContent>
                <DialogActions sx={{ p: 2, justifyContent: 'space-between', bgcolor: colors.cardBg }}>
                    <Box sx={{ pl: 1 }}>
                        <Typography variant="caption" sx={{ color: colors.textSecondary, display: 'block' }}>
                            Category: <strong>{previewFile?.category_display || previewFile?.category}</strong>
                        </Typography>
                        {previewFile?.uploaded_by_detail && (
                            <Typography variant="caption" sx={{ color: colors.textSecondary }}>
                                Uploaded By: {previewFile.uploaded_by_detail.full_name || previewFile.uploaded_by_detail.username}
                            </Typography>
                        )}
                    </Box>
                    <Stack direction="row" spacing={1.5}>
                        {previewFile?.video_url && (
                            <Button
                                variant="outlined"
                                href={previewFile.video_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                startIcon={<LaunchIcon />}
                                sx={{ borderColor: colors.cardBorder, color: colors.textPrimary, textTransform: 'none', borderRadius: '8px' }}
                            >
                                Open Link
                            </Button>
                        )}
                        {previewFile?.file && !previewFile?.video_url && (
                            <Button
                                variant="outlined"
                                href={previewFile.file}
                                download
                                startIcon={<DownloadIcon />}
                                sx={{ borderColor: colors.cardBorder, color: colors.textPrimary, textTransform: 'none', borderRadius: '8px' }}
                            >
                                Download
                            </Button>
                        )}
                        <Button onClick={() => setPreviewOpen(false)} sx={{ color: colors.textSecondary, textTransform: 'none' }}>Close</Button>
                    </Stack>
                </DialogActions>
            </Dialog>

            {/* Premium Snackbar Alerts */}
            <Snackbar
                open={snackbar.open}
                autoHideDuration={4000}
                onClose={() => setSnackbar({ ...snackbar, open: false })}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            >
                <Alert severity={snackbar.severity} variant="filled" sx={{ borderRadius: '8px' }}>
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Box>
    );
}
