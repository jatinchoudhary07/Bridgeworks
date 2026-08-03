import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
    Accordion,
    AccordionDetails,
    AccordionSummary,
    Alert,
    Checkbox,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControlLabel,
    Grid,
    Box,
    Button,
    FormControl,
    InputAdornment,
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
    Tooltip,
} from '@mui/material';
import { usePagePermissions } from '../../utils/rbac';
import SearchIcon from '@mui/icons-material/Search';
import UploadIcon from '@mui/icons-material/Upload';
import PrintIcon from '@mui/icons-material/Print';
import DownloadIcon from '@mui/icons-material/Download';
import AddIcon from '@mui/icons-material/Add';
import CloseIcon from '@mui/icons-material/Close';
import IconButton from '@mui/material/IconButton';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import WorkOutlineIcon from '@mui/icons-material/WorkOutline';
import LocationOnOutlinedIcon from '@mui/icons-material/LocationOnOutlined';
import FlagOutlinedIcon from '@mui/icons-material/FlagOutlined';
import TranslateIcon from '@mui/icons-material/Translate';
import AccountBalanceOutlinedIcon from '@mui/icons-material/AccountBalanceOutlined';
import BadgeOutlinedIcon from '@mui/icons-material/BadgeOutlined';
import NotesOutlinedIcon from '@mui/icons-material/NotesOutlined';
import UploadFileOutlinedIcon from '@mui/icons-material/UploadFileOutlined';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { BACKEND_URL } from '../../config/api';
import { apiClient } from '../../apiClient';
import PresenceBadge from '../common/PresenceBadge';

const ALL_COLUMNS = [
    { key: 'full_name', label: 'Full Name', defaultVisible: true },
    { key: 'department_name', label: 'Department', defaultVisible: true },
    { key: 'category', label: 'Category', defaultVisible: true },
    { key: 'role_designation', label: 'Role / Designation', defaultVisible: true },
    { key: 'working_style', label: 'Working Style', defaultVisible: true },
    { key: 'status', label: 'Status', defaultVisible: true },
    { key: 'gender', label: 'Gender', defaultVisible: false },
    { key: 'phone', label: 'Phone', defaultVisible: true },
    { key: 'email', label: 'Email', defaultVisible: true },
    { key: 'idle_alarm', label: 'Idle Alarm', defaultVisible: true },
    { key: 'current_location', label: 'Current Location', defaultVisible: true },
    { key: 'notes', label: 'Notes', defaultVisible: false },
];

const WORKING_STYLE_OPTIONS = ['On-site', 'Remote', 'Hybrid', 'Field Work', 'Part-time', 'Contractual'];
const STATUS_OPTIONS = ['Active', 'Inactive'];
const GENDER_OPTIONS = ['Male', 'Female', 'Other'];
const TEAM_MEMBERS_URL = `${BACKEND_URL}/api/team/members/`;
const TEAM_DELETE_URL = (userId) => `${BACKEND_URL}/api/team/delete/${userId}/`;
const TEAM_PERMISSIONS_URL = (userId) => `${BACKEND_URL}/api/team/permissions/${userId}/`;
const WORKFORCE_PERMISSIONS_URL = (memberId) => `${BACKEND_URL}/api/workforce/permissions/${memberId}/`;
const PERMISSION_SCHEMA_URL = `${BACKEND_URL}/api/permissions/schema/`;
const CURRENT_USER_URL = `${BACKEND_URL}/api/current-user/`;

const INITIAL_QUICK_FORM = {
    first_name: '',
    last_name: '',
    code: '+91',
    phone: '',
    location: '',
    department: '',
    type: 'In-House',
    designation: 'Select',
    remarks: '',
};

const INITIAL_ENROLL_FORM = {
    full_name: '',
    dob: '',
    gender: '',
    email: '',
    phone: '',
    whatsapp: '',
    department: '',
    category: '',
    role_designation: '',
    working_style: '',
    status: 'Active',
    current_location: '',
    curr_address_line_1: '',
    curr_address_line_2: '',
    curr_country: '',
    curr_state: '',
    curr_city: '',
    curr_pincode: '',
    same_as_current: false,
    perm_address_line_1: '',
    perm_address_line_2: '',
    perm_country: '',
    perm_state: '',
    perm_city: '',
    perm_pincode: '',
    first_language: '',
    second_language: '',
    bank_account_name: '',
    bank_name: '',
    account_number: '',
    ifsc: '',
    aadhaar_document: '',
    pan_document: '',
    notes: '',
};

export default function MasterWorkforceSheet() {
    const [search, setSearch] = useState('');
    const [filters, setFilters] = useState({
        department: 'all',
        working_style: 'all',
        status: 'all',
        gender: 'all',
        archive_state: 'active',
    });

    const [departments, setDepartments] = useState([]);
    const [rows, setRows] = useState([]);
    const [isAdmin, setIsAdmin] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const { canViewAmounts, canExport } = usePagePermissions();

    const [selectedRows, setSelectedRows] = useState([]);
    const [columnsDialogOpen, setColumnsDialogOpen] = useState(false);
    const [quickEnrollOpen, setQuickEnrollOpen] = useState(false);
    const [fullEnrollOpen, setFullEnrollOpen] = useState(false);
    const [newDepartmentOpen, setNewDepartmentOpen] = useState(false);

    const [quickForm, setQuickForm] = useState(INITIAL_QUICK_FORM);
    const [fullForm, setFullForm] = useState(INITIAL_ENROLL_FORM);
    const [newDepartmentName, setNewDepartmentName] = useState('');
    const [saving, setSaving] = useState(false);
    const [docUploading, setDocUploading] = useState({ aadhaar: false, pan: false });
    const [editingMemberId, setEditingMemberId] = useState(null);
    const [success, setSuccess] = useState('');
    const [permissionSchema, setPermissionSchema] = useState({});
    const [permissionsDialogOpen, setPermissionsDialogOpen] = useState(false);
    const [permissionTarget, setPermissionTarget] = useState(null);
    const [formPermissions, setFormPermissions] = useState({});
    
    // Idle Settings States
    const [idleSettingsOpen, setIdleSettingsOpen] = useState(false);
    const [idleSettingsTarget, setIdleSettingsTarget] = useState(null);
    const [overrideEnabled, setOverrideEnabled] = useState(null);
    const [overrideMinutes, setOverrideMinutes] = useState(15);

    const aadhaarInputRef = useRef(null);
    const panInputRef = useRef(null);
    const bulkUploadInputRef = useRef(null);

    const [visibleColumns, setVisibleColumns] = useState(
        ALL_COLUMNS.filter((column) => column.defaultVisible).map((column) => column.key)
    );

    const visibleColumnDefs = useMemo(
        () => ALL_COLUMNS.filter((column) => visibleColumns.includes(column.key)),
        [visibleColumns]
    );

    const fetchDepartments = async () => {
        try {
            const response = await apiClient(`${BACKEND_URL}/api/workforce/departments/`, { credentials: 'include' });
            if (!response.ok) throw new Error('Failed to fetch departments');
            const data = await response.json();
            setDepartments(Array.isArray(data) ? data : []);
        } catch (fetchError) {
            setError(fetchError.message || 'Unable to load departments');
        }
    };

    const fetchMembers = async () => {
        setLoading(true);
        setError('');
        try {
            const params = new URLSearchParams();
            if (search.trim()) params.set('search', search.trim());
            if (filters.department !== 'all') params.set('department', filters.department);
            if (filters.working_style !== 'all') params.set('working_style', filters.working_style);
            if (filters.status !== 'all') params.set('status', filters.status);
            if (filters.gender !== 'all') params.set('gender', filters.gender);
            if (filters.archive_state) params.set('archive_state', filters.archive_state);

            const query = params.toString();
            const [workforceResponse, teamResponse] = await Promise.all([
                apiClient(`${BACKEND_URL}/api/workforce/members/${query ? `?${query}` : ''}`, {
                    credentials: 'include',
                }),
                apiClient(TEAM_MEMBERS_URL, { credentials: 'include' }),
            ]);

            if (!workforceResponse.ok) throw new Error('Failed to fetch workforce rows');
            if (!teamResponse.ok) throw new Error('Failed to fetch team rows');

            const workforceData = await workforceResponse.json();
            const teamData = await teamResponse.json();

            const normalizedWorkforceRows = (Array.isArray(workforceData) ? workforceData : []).map((row) => ({
                ...row,
                source: 'workforce',
                row_key: `workforce-${row.id}`,
            }));

            const normalizedTeamRows = (Array.isArray(teamData) ? teamData : [])
                .map((row) => {
                    const fullName = row.full_name || row.username || (row.email ? row.email.split('@')[0] : 'Team Member');
                    const gender = row.gender || '';
                    const matchesSearch = !search.trim()
                        || fullName.toLowerCase().includes(search.trim().toLowerCase())
                        || (row.email || '').toLowerCase().includes(search.trim().toLowerCase());
                    const matchesGender = filters.gender === 'all' || gender === filters.gender;
                    return {
                        id: row.id,
                        row_key: `team-${row.id}`,
                        source: 'team',
                        full_name: fullName,
                        department_name: row.department_name || '—',
                        category: row.category || 'Team',
                        role_designation: row.role_designation || '—',
                        working_style: row.working_style || '—',
                        status: row.status || 'Active',
                        gender,
                        phone: row.phone || '—',
                        email: row.email || '—',
                        current_location: row.current_location || '—',
                        notes: row.notes || '—',
                        idle_timeout_override_enabled: row.idle_timeout_override_enabled,
                        idle_timeout_override_minutes: row.idle_timeout_override_minutes,
                    };
                })
                .filter((row) => {
                    const matchesSearch = !search.trim()
                        || row.full_name.toLowerCase().includes(search.trim().toLowerCase())
                        || (row.email || '').toLowerCase().includes(search.trim().toLowerCase());
                    const matchesGender = filters.gender === 'all' || row.gender === filters.gender;
                    return matchesSearch && matchesGender;
                });

            const combinedRows = [...normalizedWorkforceRows, ...normalizedTeamRows];
            setRows(combinedRows);
            setSelectedRows((prev) => prev.filter((rowKey) => combinedRows.some((row) => row.row_key === rowKey)));
        } catch (fetchError) {
            setError(fetchError.message || 'Unable to load workforce sheet');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchDepartments();
    }, []);

    useEffect(() => {
        fetchMembers();
    }, [search, filters]);

    useEffect(() => {
        const fetchPermissionSchema = async () => {
            try {
                const response = await apiClient(PERMISSION_SCHEMA_URL, { credentials: 'include' });
                if (!response.ok) throw new Error('Failed to load permission schema');
                const data = await response.json();
                setPermissionSchema(data.permissions || {});
            } catch (schemaError) {
                setPermissionSchema({});
                setError(schemaError.message || 'Unable to load permission schema');
            }
        };
        fetchPermissionSchema();
    }, []);

    useEffect(() => {
        const fetchCurrentUser = async () => {
            try {
                const response = await apiClient(CURRENT_USER_URL, { credentials: 'include' });
                if (!response.ok) return;
                const data = await response.json();
                setIsAdmin(!!data?.is_admin);
            } catch (currentUserError) {
                setIsAdmin(false);
            }
        };

        fetchCurrentUser();
    }, []);

    const handleClearFilters = () => {
        setFilters({ department: 'all', working_style: 'all', status: 'all', gender: 'all', archive_state: 'active' });
    };

    const handleColumnToggle = (columnKey) => {
        setVisibleColumns((prev) => (
            prev.includes(columnKey)
                ? prev.filter((key) => key !== columnKey)
                : [...prev, columnKey]
        ));
    };

    const handleCreateDepartment = async () => {
        const name = newDepartmentName.trim();
        if (!name) return;

        setSaving(true);
        try {
            const response = await apiClient(`${BACKEND_URL}/api/workforce/departments/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ name }),
            });
            if (!response.ok) throw new Error('Failed to create department');
            const created = await response.json();
            await fetchDepartments();
            setNewDepartmentOpen(false);
            setNewDepartmentName('');
            setFilters((prev) => ({ ...prev, department: String(created.id) }));
            setQuickForm((prev) => ({ ...prev, department: String(created.id) }));
            setFullForm((prev) => ({ ...prev, department: String(created.id) }));
            setSuccess('Department created successfully.');
        } catch (saveError) {
            setError(saveError.message || 'Unable to create department');
        } finally {
            setSaving(false);
        }
    };

    const handleCreateMember = async (payload) => {
        setSaving(true);
        try {
            const response = await apiClient(`${BACKEND_URL}/api/workforce/members/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload),
            });
            if (!response.ok) throw new Error('Failed to create workforce member');
            await fetchMembers();
            setSuccess('Workforce member created successfully.');
            return true;
        } catch (saveError) {
            setError(saveError.message || 'Unable to save workforce member');
            return false;
        } finally {
            setSaving(false);
        }
    };

    const handleUpdateMember = async (memberId, payload) => {
        setSaving(true);
        try {
            const response = await apiClient(`${BACKEND_URL}/api/workforce/members/${memberId}/`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload),
            });
            if (!response.ok) throw new Error('Failed to update workforce member');
            await fetchMembers();
            setSuccess('Workforce member updated successfully.');
            return true;
        } catch (saveError) {
            setError(saveError.message || 'Unable to update workforce member');
            return false;
        } finally {
            setSaving(false);
        }
    };

    const selectedWorkforceRows = selectedRows
        .map((rowKey) => rows.find((row) => row.row_key === rowKey))
        .filter((row) => row && row.source === 'workforce');

    const canToggleArchive = selectedWorkforceRows.length > 0;
    const allSelectedArchived = canToggleArchive && selectedWorkforceRows.every((row) => !!row.is_archived);
    const archiveAction = allSelectedArchived ? 'unarchive' : 'archive';

    const handleArchiveSelected = async () => {
        const selectedWorkforceIds = selectedWorkforceRows
            .map((rowKey) => rows.find((row) => row.row_key === rowKey))
            .filter((row) => row && row.source === 'workforce')
            .map((row) => row.id);

        if (selectedWorkforceIds.length === 0) {
            setError('Select at least one workforce row to archive/unarchive.');
            return;
        }

        setSaving(true);
        try {
            const response = await apiClient(`${BACKEND_URL}/api/workforce/members/archive/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ ids: selectedWorkforceIds, action: archiveAction }),
            });
            if (!response.ok) throw new Error(`Failed to ${archiveAction} selected members`);
            await fetchMembers();
            setSelectedRows([]);
            setSuccess(`Selected members ${archiveAction}d successfully.`);
        } catch (archiveError) {
            setError(archiveError.message || `Unable to ${archiveAction} selected members`);
        } finally {
            setSaving(false);
        }
    };

    const handleExport = () => {
        if (rows.length === 0) {
            setError('No rows available to export.');
            return;
        }

        const exportColumns = ALL_COLUMNS.map((column) => column.key);
        const header = ['source', ...exportColumns, 'is_archived'];

        const toCsvValue = (value) => {
            if (value === null || value === undefined) return '';
            const text = String(value).replace(/"/g, '""');
            return `"${text}"`;
        };

        const lines = [header.join(',')];
        rows.forEach((row) => {
            const line = [
                toCsvValue(row.source),
                ...exportColumns.map((key) => toCsvValue(row[key] ?? '')),
                toCsvValue(row.is_archived ? 'true' : 'false'),
            ];
            lines.push(line.join(','));
        });

        const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `master-workforce-${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const handlePrint = () => {
        if (rows.length === 0) {
            setError('No rows available to print.');
            return;
        }

        const printWindow = window.open('', '_blank', 'width=1200,height=800');
        if (!printWindow) {
            setError('Unable to open print window. Please allow popups.');
            return;
        }

        const columns = visibleColumnDefs.length > 0 ? visibleColumnDefs : ALL_COLUMNS;
        const headerHtml = columns.map((column) => `<th>${column.label}</th>`).join('');
        const bodyHtml = rows.map((row) => {
            const cells = columns.map((column) => `<td>${row[column.key] ?? '—'}</td>`).join('');
            return `<tr>${cells}</tr>`;
        }).join('');

        printWindow.document.write(`
            <html>
                <head>
                    <title>Master Workforce Sheet</title>
                    <style>
                        body { font-family: Arial, sans-serif; padding: 16px; }
                        h2 { margin-bottom: 12px; }
                        table { width: 100%; border-collapse: collapse; }
                        th, td { border: 1px solid #ddd; padding: 8px; font-size: 12px; text-align: left; }
                        th { background: #f5f5f5; }
                    </style>
                </head>
                <body>
                    <h2>Master Workforce Sheet</h2>
                    <table>
                        <thead><tr>${headerHtml}</tr></thead>
                        <tbody>${bodyHtml}</tbody>
                    </table>
                </body>
            </html>
        `);
        printWindow.document.close();
        printWindow.focus();
        printWindow.print();
    };

    const handleUploadCsv = async (file) => {
        if (!file) return;

        try {
            const text = await file.text();
            const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
            if (lines.length < 2) {
                setError('CSV file is empty.');
                return;
            }

            const headers = lines[0].split(',').map((header) => header.trim().replace(/^"|"$/g, ''));
            const headerIndex = (name) => headers.findIndex((header) => header.toLowerCase() === name.toLowerCase());

            const nameIndex = headerIndex('full_name');
            const emailIndex = headerIndex('email');
            const phoneIndex = headerIndex('phone');
            const locationIndex = headerIndex('current_location');

            if (nameIndex === -1) {
                setError('CSV must include full_name column.');
                return;
            }

            setSaving(true);
            let createdCount = 0;

            for (let rowIndex = 1; rowIndex < lines.length; rowIndex += 1) {
                const values = lines[rowIndex].split(',').map((value) => value.trim().replace(/^"|"$/g, ''));
                const fullName = values[nameIndex] || '';
                if (!fullName) continue;

                const payload = {
                    full_name: fullName,
                    email: emailIndex >= 0 ? (values[emailIndex] || '') : '',
                    phone: phoneIndex >= 0 ? (values[phoneIndex] || '') : '',
                    current_location: locationIndex >= 0 ? (values[locationIndex] || '') : '',
                    status: 'Active',
                };

                const response = await apiClient(`${BACKEND_URL}/api/workforce/members/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(payload),
                });

                if (response.ok) createdCount += 1;
            }

            await fetchMembers();
            setSuccess(`${createdCount} members uploaded successfully.`);
        } catch (uploadError) {
            setError(uploadError.message || 'Unable to upload CSV.');
        } finally {
            setSaving(false);
            if (bulkUploadInputRef.current) bulkUploadInputRef.current.value = '';
        }
    };

    const handleDeleteSelected = async () => {
        if (!isAdmin) {
            setError('Only admin can delete members.');
            return;
        }

        const selectedMemberRows = selectedRows
            .map((rowKey) => rows.find((row) => row.row_key === rowKey))
            .filter((row) => !!row);

        if (selectedMemberRows.length === 0) {
            setError('Select at least one row to delete.');
            return;
        }

        const confirmed = window.confirm(`Delete ${selectedMemberRows.length} selected member(s)?`);
        if (!confirmed) return;

        setSaving(true);
        try {
            const results = await Promise.allSettled(
                selectedMemberRows.map(async (member) => {
                    if (member.source === 'team') {
                        const response = await apiClient(TEAM_DELETE_URL(member.id), {
                            method: 'DELETE',
                            credentials: 'include',
                        });
                        if (!response.ok) {
                            const errData = await response.json().catch(() => ({}));
                            throw new Error(errData.error || 'Failed to delete team member');
                        }
                        return true;
                    }

                    const response = await apiClient(`${BACKEND_URL}/api/workforce/members/${member.id}/`, {
                        method: 'DELETE',
                        credentials: 'include',
                    });
                    if (!response.ok) {
                        const errData = await response.json().catch(() => ({}));
                        throw new Error(errData.detail || errData.error || 'Failed to delete workforce member');
                    }
                    return true;
                })
            );

            const successCount = results.filter((result) => result.status === 'fulfilled').length;
            const failureCount = results.length - successCount;
            if (successCount === 0) throw new Error('Failed to delete selected members');

            await fetchMembers();
            setSelectedRows([]);
            if (failureCount > 0) {
                setError(`${failureCount} member(s) could not be deleted.`);
            }
            setSuccess(`${successCount} member(s) deleted successfully.`);
        } catch (deleteError) {
            setError(deleteError.message || 'Unable to delete selected members');
        } finally {
            setSaving(false);
        }
    };

    const handlePermissionChange = (area, key, checked) => {
        setFormPermissions((prev) => ({
            ...prev,
            [area]: { ...prev[area], [key]: checked },
        }));
    };

    const openPermissionsEditor = async (row) => {
        if (!isAdmin) {
            setError('Only admin can edit access.');
            return;
        }

        const targetType = row.source === 'workforce' ? 'workforce' : 'team';
        const targetId = row.id;
        if (!targetId) {
            setError('Unable to resolve member for permission editing.');
            return;
        }

        const permissionsUrl = targetType === 'workforce'
            ? WORKFORCE_PERMISSIONS_URL(targetId)
            : TEAM_PERMISSIONS_URL(targetId);

        setSaving(true);
        try {
            const response = await apiClient(permissionsUrl, { credentials: 'include' });
            if (!response.ok) throw new Error('Failed to fetch permissions.');
            const data = await response.json();
            setFormPermissions(data.permissions || {});
            setPermissionTarget({
                id: targetId,
                type: targetType,
                label: row.full_name || row.email || 'member',
            });
            setPermissionsDialogOpen(true);
        } catch (permissionError) {
            setError(permissionError.message || 'Unable to load member permissions');
        } finally {
            setSaving(false);
        }
    };

    const handleUpdatePermissions = async () => {
        if (!permissionTarget?.id || !permissionTarget?.type) return;

        const permissionsUrl = permissionTarget.type === 'workforce'
            ? WORKFORCE_PERMISSIONS_URL(permissionTarget.id)
            : TEAM_PERMISSIONS_URL(permissionTarget.id);

        setSaving(true);
        try {
            const response = await apiClient(permissionsUrl, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ permissions: formPermissions }),
            });

            if (!response.ok) throw new Error('Failed to update permissions.');

            setPermissionsDialogOpen(false);
            setPermissionTarget(null);
            setSuccess('Permissions updated successfully.');
            await fetchMembers();
        } catch (updateError) {
            setError(updateError.message || 'Unable to update permissions');
        } finally {
            setSaving(false);
        }
    };

    const handleEditSelected = () => {
        if (selectedRows.length !== 1) {
            setError('Select exactly one row to edit.');
            return;
        }

        const selectedRowKey = selectedRows[0];
        const row = rows.find((item) => item.row_key === selectedRowKey);
        if (!row) {
            setError('Selected member not found.');
            return;
        }

        if (row.source === 'team') {
            openPermissionsEditor(row);
            return;
        }

        setEditingMemberId(row.id);
        setFullForm({
            full_name: row.full_name || '',
            dob: row.extra_data?.dob || '',
            gender: row.gender || '',
            email: row.email || '',
            phone: row.phone || '',
            whatsapp: row.extra_data?.whatsapp || '',
            department: row.department ? String(row.department) : '',
            category: row.category || '',
            role_designation: row.role_designation || '',
            working_style: row.working_style || '',
            status: row.status || 'Active',
            current_location: row.current_location || '',
            curr_address_line_1: row.extra_data?.curr_address_line_1 || '',
            curr_address_line_2: row.extra_data?.curr_address_line_2 || '',
            curr_country: row.extra_data?.curr_country || '',
            curr_state: row.extra_data?.curr_state || '',
            curr_city: row.extra_data?.curr_city || '',
            curr_pincode: row.extra_data?.curr_pincode || '',
            same_as_current: !!row.extra_data?.same_as_current,
            perm_address_line_1: row.extra_data?.perm_address_line_1 || '',
            perm_address_line_2: row.extra_data?.perm_address_line_2 || '',
            perm_country: row.extra_data?.perm_country || '',
            perm_state: row.extra_data?.perm_state || '',
            perm_city: row.extra_data?.perm_city || '',
            perm_pincode: row.extra_data?.perm_pincode || '',
            first_language: row.extra_data?.first_language || '',
            second_language: row.extra_data?.second_language || '',
            bank_account_name: row.extra_data?.bank_account_name || '',
            bank_name: row.extra_data?.bank_name || '',
            account_number: row.extra_data?.account_number || '',
            ifsc: row.extra_data?.ifsc || '',
            aadhaar_document: row.extra_data?.aadhaar_document || '',
            pan_document: row.extra_data?.pan_document || '',
            notes: row.notes || '',
        });
        setFullEnrollOpen(true);
    };

    const handleUploadDocument = async (docType, file) => {
        if (!file) return;

        setDocUploading((prev) => ({ ...prev, [docType]: true }));
        setError('');
        try {
            const formData = new FormData();
            formData.append('document', file);

            const response = await apiClient(`${BACKEND_URL}/api/workforce/documents/${docType}/`, {
                method: 'POST',
                credentials: 'include',
                body: formData,
            });

            if (!response.ok) throw new Error('Failed to upload document');
            const data = await response.json();
            const uploadedUrl = data.url || '';

            if (!uploadedUrl) throw new Error('Document URL missing after upload');

            setFullForm((prev) => ({ ...prev, [`${docType}_document`]: uploadedUrl }));
            setSuccess(`${docType === 'aadhaar' ? 'Aadhaar' : 'PAN'} document uploaded successfully.`);
        } catch (uploadError) {
            setError(uploadError.message || 'Unable to upload document');
        } finally {
            setDocUploading((prev) => ({ ...prev, [docType]: false }));
        }
    };

    const handleQuickEnroll = async () => {
        const fullName = `${quickForm.first_name} ${quickForm.last_name}`.trim();
        if (!fullName || !quickForm.phone) {
            setError('First name and phone are required for quick enrollment.');
            return;
        }

        const ok = await handleCreateMember({
            full_name: fullName,
            department: quickForm.department || null,
            category: quickForm.type || '',
            role_designation: quickForm.designation || '',
            phone: quickForm.phone || '',
            current_location: quickForm.location || '',
            notes: quickForm.remarks || '',
            status: 'Active',
            extra_data: {
                first_name: quickForm.first_name,
                last_name: quickForm.last_name,
                code: quickForm.code,
            },
        });

        if (ok) {
            setQuickEnrollOpen(false);
            setQuickForm(INITIAL_QUICK_FORM);
            setError('');
            setSelectedRows([]);
        }
    };

    const handleFullEnroll = async () => {
        if (!fullForm.full_name.trim()) {
            setError('Full name is required.');
            return;
        }

        const payload = {
            full_name: fullForm.full_name,
            department: fullForm.department || null,
            category: fullForm.category || '',
            role_designation: fullForm.role_designation || '',
            working_style: fullForm.working_style || '',
            status: fullForm.status || 'Active',
            gender: fullForm.gender || '',
            phone: fullForm.phone || '',
            email: fullForm.email || '',
            current_location: fullForm.current_location || '',
            notes: fullForm.notes || '',
            extra_data: {
                dob: fullForm.dob || '',
                whatsapp: fullForm.whatsapp || '',
                curr_address_line_1: fullForm.curr_address_line_1 || '',
                curr_address_line_2: fullForm.curr_address_line_2 || '',
                curr_country: fullForm.curr_country || '',
                curr_state: fullForm.curr_state || '',
                curr_city: fullForm.curr_city || '',
                curr_pincode: fullForm.curr_pincode || '',
                same_as_current: !!fullForm.same_as_current,
                perm_address_line_1: fullForm.same_as_current ? fullForm.curr_address_line_1 : (fullForm.perm_address_line_1 || ''),
                perm_address_line_2: fullForm.same_as_current ? fullForm.curr_address_line_2 : (fullForm.perm_address_line_2 || ''),
                perm_country: fullForm.same_as_current ? fullForm.curr_country : (fullForm.perm_country || ''),
                perm_state: fullForm.same_as_current ? fullForm.curr_state : (fullForm.perm_state || ''),
                perm_city: fullForm.same_as_current ? fullForm.curr_city : (fullForm.perm_city || ''),
                perm_pincode: fullForm.same_as_current ? fullForm.curr_pincode : (fullForm.perm_pincode || ''),
                first_language: fullForm.first_language || '',
                second_language: fullForm.second_language || '',
                bank_account_name: fullForm.bank_account_name || '',
                bank_name: fullForm.bank_name || '',
                account_number: fullForm.account_number || '',
                ifsc: fullForm.ifsc || '',
                aadhaar_document: fullForm.aadhaar_document || '',
                pan_document: fullForm.pan_document || '',
            },
        };

        const ok = editingMemberId
            ? await handleUpdateMember(editingMemberId, payload)
            : await handleCreateMember(payload);

        if (ok) {
            setFullEnrollOpen(false);
            setFullForm(INITIAL_ENROLL_FORM);
            setEditingMemberId(null);
            setError('');
            setSelectedRows([]);
        }
    };

    const handleDepartmentSelect = (value, target) => {
        if (value === '__new_department__') {
            setNewDepartmentOpen(true);
            return;
        }

        if (target === 'filter') {
            setFilters((prev) => ({ ...prev, department: value }));
            return;
        }
        if (target === 'quick') {
            setQuickForm((prev) => ({ ...prev, department: value }));
            return;
        }
        setFullForm((prev) => ({ ...prev, department: value }));
    };

    const renderDepartmentMenuItems = () => (
        [
            <MenuItem key="all" value="all">All</MenuItem>,
            ...departments.map((department) => (
                <MenuItem key={department.id} value={String(department.id)}>{department.name}</MenuItem>
            )),
            <MenuItem key="new" value="__new_department__">+ New Department</MenuItem>,
        ]
    );

    const handleOpenIdleSettings = (row) => {
        setIdleSettingsTarget(row);
        if (row.idle_timeout_override_enabled === true) {
            setOverrideEnabled(true);
        } else if (row.idle_timeout_override_enabled === false) {
            setOverrideEnabled(false);
        } else {
            setOverrideEnabled(null);
        }
        setOverrideMinutes(row.idle_timeout_override_minutes || 15);
        setIdleSettingsOpen(true);
    };

    const handleSaveIdleSettings = async () => {
        if (!idleSettingsTarget) return;
        setSaving(true);
        setError('');
        setSuccess('');
        try {
            const response = await apiClient(`${BACKEND_URL}/api/hr/users/${idleSettingsTarget.id}/attendance-settings/`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({
                    idle_timeout_override_enabled: overrideEnabled,
                    idle_timeout_override_minutes: overrideMinutes
                })
            });
            if (response.ok) {
                const data = await response.json();
                setSuccess('Idle settings updated successfully.');
                // Update row state locally
                setRows(prev => prev.map(r => r.row_key === idleSettingsTarget.row_key ? {
                    ...r,
                    idle_timeout_override_enabled: data.idle_timeout_override_enabled,
                    idle_timeout_override_minutes: data.idle_timeout_override_minutes
                } : r));
                setIdleSettingsOpen(false);
            } else {
                const errData = await response.json();
                setError(errData.error || 'Failed to update idle settings.');
            }
        } catch (err) {
            setError('Connection error. Failed to update idle settings.');
        } finally {
            setSaving(false);
        }
    };

    const renderCellValue = (row, key) => {
        const value = row[key];
        
        if (key === 'idle_alarm') {
            if (row.source !== 'team') return '—';
            let label = 'Inherit';
            let color = 'default';
            if (row.idle_timeout_override_enabled === true) {
                label = `${row.idle_timeout_override_minutes}m (Override)`;
                color = 'primary';
            } else if (row.idle_timeout_override_enabled === false) {
                label = 'Disabled (Override)';
                color = 'error';
            }
            return (
                <Chip 
                    label={label}
                    color={color}
                    size="small"
                    variant="outlined"
                    onClick={() => isAdmin && handleOpenIdleSettings(row)}
                    sx={{ cursor: isAdmin ? 'pointer' : 'default', fontWeight: 600 }}
                />
            );
        }

        if (value === null || value === undefined || value === '') return '—';

        if (key === 'full_name') {
            return (
                <Stack direction="row" spacing={1} alignItems="center">
                    {row.source === 'team' && row.id && (
                        <PresenceBadge userId={row.id} size="small" />
                    )}
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {value}
                    </Typography>
                </Stack>
            );
        }

        return value;
    };

    const toggleRowSelection = (rowId) => {
        setSelectedRows((prev) => (
            prev.includes(rowId) ? prev.filter((id) => id !== rowId) : [...prev, rowId]
        ));
    };

    return (
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
            {success && <Alert severity="success" onClose={() => setSuccess('')}>{success}</Alert>}

            <Paper variant="outlined" sx={{ p: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'nowrap', overflowX: 'auto' }}>
                <TextField
                    size="small"
                    placeholder="SEARCH"
                    sx={{ minWidth: 150, flexShrink: 0 }}
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon fontSize="small" />
                            </InputAdornment>
                        ),
                    }}
                />

                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'nowrap', ml: 'auto' }}>
                    <input
                        ref={bulkUploadInputRef}
                        type="file"
                        hidden
                        accept=".csv,text/csv"
                        onChange={(event) => handleUploadCsv(event.target.files?.[0])}
                    />
                    <Button size="small" variant="outlined" startIcon={<UploadIcon />} sx={{ whiteSpace: 'nowrap' }} onClick={() => bulkUploadInputRef.current?.click()}>
                        Upload
                    </Button>
                    <Button
                        size="small"
                        variant="contained"
                        sx={{ whiteSpace: 'nowrap' }}
                        onClick={() => {
                            setEditingMemberId(null);
                            setFullForm(INITIAL_ENROLL_FORM);
                            setFullEnrollOpen(true);
                        }}
                    >
                        Enroll
                    </Button>
                    <Button size="small" variant="outlined" sx={{ whiteSpace: 'nowrap' }} onClick={handleEditSelected} disabled={saving}>Edit</Button>
                    <Button size="small" variant="outlined" color="error" sx={{ whiteSpace: 'nowrap' }} onClick={handleDeleteSelected} disabled={saving || !isAdmin}>Delete</Button>
                    <Button size="small" variant="outlined" sx={{ whiteSpace: 'nowrap' }} onClick={handleArchiveSelected} disabled={saving || !canToggleArchive}>
                        {archiveAction === 'unarchive' ? 'Unarchive' : 'Archive'}
                    </Button>
                    <Button size="small" variant="outlined" sx={{ whiteSpace: 'nowrap' }} onClick={() => setColumnsDialogOpen(true)}>Columns</Button>
                    <Tooltip title={!canExport ? "Permission Required" : ""}>
                        <span>
                            <Button size="small" variant="outlined" startIcon={<DownloadIcon />} sx={{ whiteSpace: 'nowrap' }} onClick={handleExport} disabled={!canExport}>Export</Button>
                        </span>
                    </Tooltip>
                    <Tooltip title={!canExport ? "Permission Required" : ""}>
                        <span>
                            <Button size="small" variant="outlined" startIcon={<PrintIcon />} sx={{ whiteSpace: 'nowrap' }} onClick={handlePrint} disabled={!canExport}>Print</Button>
                        </span>
                    </Tooltip>
                </Box>
            </Paper>

            <Paper variant="outlined" sx={{ p: 2 }}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end', flexWrap: 'nowrap', overflowX: 'auto' }}>
                    <Box sx={{ minWidth: 190, flexShrink: 0 }}>
                        <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontWeight: 700, textTransform: 'uppercase' }}>
                            Department
                        </Typography>
                        <FormControl size="small" fullWidth>
                            <Select
                                value={filters.department}
                                onChange={(event) => handleDepartmentSelect(event.target.value, 'filter')}
                            >
                                {renderDepartmentMenuItems()}
                            </Select>
                        </FormControl>
                    </Box>

                    <Box sx={{ minWidth: 190, flexShrink: 0 }}>
                        <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontWeight: 700, textTransform: 'uppercase' }}>
                            Working Style
                        </Typography>
                        <FormControl size="small" fullWidth>
                            <Select
                                value={filters.working_style}
                                onChange={(event) => setFilters((prev) => ({ ...prev, working_style: event.target.value }))}
                            >
                                <MenuItem value="all">All</MenuItem>
                                {WORKING_STYLE_OPTIONS.map((option) => <MenuItem key={option} value={option}>{option}</MenuItem>)}
                            </Select>
                        </FormControl>
                    </Box>

                    <Box sx={{ minWidth: 190, flexShrink: 0 }}>
                        <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontWeight: 700, textTransform: 'uppercase' }}>
                            Status
                        </Typography>
                        <FormControl size="small" fullWidth>
                            <Select
                                value={filters.status}
                                onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
                            >
                                <MenuItem value="all">All</MenuItem>
                                {STATUS_OPTIONS.map((option) => <MenuItem key={option} value={option}>{option}</MenuItem>)}
                            </Select>
                        </FormControl>
                    </Box>

                    <Box sx={{ minWidth: 190, flexShrink: 0 }}>
                        <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontWeight: 700, textTransform: 'uppercase' }}>
                            Gender
                        </Typography>
                        <FormControl size="small" fullWidth>
                            <Select
                                value={filters.gender}
                                onChange={(event) => setFilters((prev) => ({ ...prev, gender: event.target.value }))}
                            >
                                <MenuItem value="all">All</MenuItem>
                                {GENDER_OPTIONS.map((option) => <MenuItem key={option} value={option}>{option}</MenuItem>)}
                            </Select>
                        </FormControl>
                    </Box>

                    <Box sx={{ minWidth: 190, flexShrink: 0 }}>
                        <Typography variant="caption" sx={{ display: 'block', mb: 0.5, fontWeight: 700, textTransform: 'uppercase' }}>
                            Archived
                        </Typography>
                        <FormControl size="small" fullWidth>
                            <Select
                                value={filters.archive_state}
                                onChange={(event) => setFilters((prev) => ({ ...prev, archive_state: event.target.value }))}
                            >
                                <MenuItem value="active">Active Only</MenuItem>
                                <MenuItem value="archived">Archived Only</MenuItem>
                                <MenuItem value="all">All</MenuItem>
                            </Select>
                        </FormControl>
                    </Box>

                    <Button size="small" sx={{ whiteSpace: 'nowrap', flexShrink: 0 }} onClick={handleClearFilters}>Clear Filters</Button>
                </Box>
            </Paper>

            <Paper variant="outlined" sx={{ overflow: 'hidden', flex: 1, display: 'flex', flexDirection: 'column' }}>
                <TableContainer>
                    <Table size="small">
                        <TableHead>
                            <TableRow sx={{ '& th': { bgcolor: 'primary.50' } }}>
                                <TableCell padding="checkbox">
                                    <Checkbox
                                        size="small"
                                        checked={rows.length > 0 && selectedRows.length === rows.length}
                                        indeterminate={selectedRows.length > 0 && selectedRows.length < rows.length}
                                        onChange={(event) => {
                                            if (event.target.checked) {
                                                setSelectedRows(rows.map((row) => row.row_key));
                                            } else {
                                                setSelectedRows([]);
                                            }
                                        }}
                                    />
                                </TableCell>
                                {visibleColumnDefs.map((column) => (
                                    <TableCell key={column.key} sx={{ fontWeight: 700, whiteSpace: 'nowrap', minWidth: 140 }}>
                                        {column.label}
                                    </TableCell>
                                ))}
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {loading && (
                                <TableRow>
                                    <TableCell colSpan={visibleColumnDefs.length + 1} align="center" sx={{ py: 3 }}>
                                        Loading...
                                    </TableCell>
                                </TableRow>
                            )}

                            {!loading && rows.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={visibleColumnDefs.length + 1} sx={{ py: 2, borderBottom: 0 }}>
                                        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setFullEnrollOpen(true)}>Add Row</Button>
                                    </TableCell>
                                </TableRow>
                            )}

                            {!loading && rows.map((row) => {
                                const isSelected = selectedRows.includes(row.row_key);
                                return (
                                    <TableRow key={row.row_key} hover selected={isSelected}>
                                        <TableCell padding="checkbox">
                                            <Checkbox size="small" checked={isSelected} onChange={() => toggleRowSelection(row.row_key)} />
                                        </TableCell>
                                        {visibleColumnDefs.map((column) => (
                                            <TableCell key={`${row.row_key}-${column.key}`} sx={{ whiteSpace: 'nowrap' }}>
                                                {renderCellValue(row, column.key)}
                                            </TableCell>
                                        ))}
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Paper>

            <Box sx={{ px: 1, display: 'flex', justifyContent: 'space-between', color: 'text.secondary' }}>
                <Typography variant="body2">Rows per page: 100 | {rows.length > 0 ? `1-${rows.length}` : '0'} of {rows.length} | 1/1</Typography>
                <Typography variant="body2">Selected: {selectedRows.length} &nbsp;&nbsp; Archived: 0</Typography>
            </Box>

            <Dialog open={columnsDialogOpen} onClose={() => setColumnsDialogOpen(false)} fullWidth maxWidth="sm">
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    Manage Columns
                    <IconButton size="small" onClick={() => setColumnsDialogOpen(false)}>
                        <CloseIcon fontSize="small" />
                    </IconButton>
                </DialogTitle>
                <DialogContent dividers>
                    <Stack spacing={1}>
                        <FormControlLabel
                            control={(
                                <Checkbox
                                    checked={visibleColumns.length === ALL_COLUMNS.length}
                                    indeterminate={visibleColumns.length > 0 && visibleColumns.length < ALL_COLUMNS.length}
                                    onChange={(event) => {
                                        if (event.target.checked) {
                                            setVisibleColumns(ALL_COLUMNS.map((column) => column.key));
                                        } else {
                                            setVisibleColumns([]);
                                        }
                                    }}
                                />
                            )}
                            label="Select All"
                        />

                        {ALL_COLUMNS.map((column) => {
                            const isVisible = visibleColumns.includes(column.key);
                            return (
                                <Box key={column.key} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                    <FormControlLabel
                                        control={<Checkbox checked={isVisible} onChange={() => handleColumnToggle(column.key)} />}
                                        label={column.label}
                                    />
                                    <Chip
                                        size="small"
                                        color={isVisible ? 'success' : 'error'}
                                        variant="outlined"
                                        label={isVisible ? 'Visible' : 'Hidden'}
                                    />
                                </Box>
                            );
                        })}
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button color="error" onClick={() => setVisibleColumns([])}>Hide</Button>
                    <Button color="success" onClick={() => setVisibleColumns(ALL_COLUMNS.map((column) => column.key))}>Show</Button>
                </DialogActions>
            </Dialog>

            <Dialog open={quickEnrollOpen} onClose={() => setQuickEnrollOpen(false)} fullWidth maxWidth="md">
                <DialogTitle sx={{ bgcolor: 'primary.main', color: 'primary.contrastText', textAlign: 'center', fontWeight: 700, position: 'relative' }}>
                    QUICK ENROLLMENT
                    <IconButton size="small" onClick={() => setQuickEnrollOpen(false)} sx={{ color: 'primary.contrastText', position: 'absolute', right: 10, top: 8 }}>
                        <CloseIcon fontSize="small" />
                    </IconButton>
                </DialogTitle>
                <DialogContent dividers>
                    <Grid container spacing={2} sx={{ mt: 0.25 }}>
                        <Grid item xs={12} md={2.5}>
                            <Paper variant="outlined" sx={{ minHeight: 132, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center', color: 'text.secondary', borderStyle: 'dashed' }}>
                                <Box>
                                    <UploadIcon />
                                    <Typography variant="body2">Upload</Typography>
                                    <Typography variant="body2">Photo</Typography>
                                </Box>
                            </Paper>
                        </Grid>
                        <Grid item xs={12} md={9.5}>
                            <Grid container spacing={2}>
                                <Grid item xs={12} md={6}>
                                    <TextField label="First Name" fullWidth value={quickForm.first_name} onChange={(event) => setQuickForm((prev) => ({ ...prev, first_name: event.target.value }))} />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                    <TextField label="Last Name" fullWidth value={quickForm.last_name} onChange={(event) => setQuickForm((prev) => ({ ...prev, last_name: event.target.value }))} />
                                </Grid>
                                <Grid item xs={12} md={2}>
                                    <FormControl fullWidth>
                                        <InputLabel>Code</InputLabel>
                                        <Select label="Code" value={quickForm.code} onChange={(event) => setQuickForm((prev) => ({ ...prev, code: event.target.value }))}>
                                            <MenuItem value="+91">+91</MenuItem>
                                            <MenuItem value="+1">+1</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={12} md={4}>
                                    <TextField label="Phone" fullWidth value={quickForm.phone} onChange={(event) => setQuickForm((prev) => ({ ...prev, phone: event.target.value }))} />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                    <TextField label="Location" fullWidth value={quickForm.location} onChange={(event) => setQuickForm((prev) => ({ ...prev, location: event.target.value }))} />
                                </Grid>
                                <Grid item xs={12} md={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Department</InputLabel>
                                        <Select
                                            label="Department"
                                            value={quickForm.department}
                                            onChange={(event) => handleDepartmentSelect(event.target.value, 'quick')}
                                        >
                                            <MenuItem value="">Select</MenuItem>
                                            {departments.map((department) => (
                                                <MenuItem key={department.id} value={String(department.id)}>{department.name}</MenuItem>
                                            ))}
                                            <MenuItem value="__new_department__">+ New Department</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={12} md={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Type</InputLabel>
                                        <Select label="Type" value={quickForm.type} onChange={(event) => setQuickForm((prev) => ({ ...prev, type: event.target.value }))}>
                                            <MenuItem value="In-House">In-House</MenuItem>
                                            <MenuItem value="Contractual">Contractual</MenuItem>
                                            <MenuItem value="Remote">Remote</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={12} md={6}>
                                    <FormControl fullWidth>
                                        <InputLabel>Designation</InputLabel>
                                        <Select label="Designation" value={quickForm.designation} onChange={(event) => setQuickForm((prev) => ({ ...prev, designation: event.target.value }))}>
                                            <MenuItem value="Select">Select</MenuItem>
                                            <MenuItem value="Associate">Associate</MenuItem>
                                            <MenuItem value="Executive">Executive</MenuItem>
                                            <MenuItem value="Manager">Manager</MenuItem>
                                        </Select>
                                    </FormControl>
                                </Grid>
                                <Grid item xs={12}>
                                    <TextField
                                        label="Remarks"
                                        fullWidth
                                        multiline
                                        minRows={2}
                                        value={quickForm.remarks}
                                        onChange={(event) => setQuickForm((prev) => ({ ...prev, remarks: event.target.value }))}
                                    />
                                </Grid>
                            </Grid>
                        </Grid>
                    </Grid>
                </DialogContent>
                <DialogActions sx={{ p: 2, gap: 1 }}>
                    <Button variant="contained" sx={{ flex: 1 }} disabled={saving} onClick={handleQuickEnroll}>Save as Draft</Button>
                    <Button variant="contained" disabled={saving} onClick={handleQuickEnroll} sx={{ flex: 1, bgcolor: '#0c162e', '&:hover': { bgcolor: '#111f3d' } }}>ENROLL</Button>
                </DialogActions>
            </Dialog>

            <Dialog
                open={fullEnrollOpen}
                onClose={() => setFullEnrollOpen(false)}
                fullWidth
                maxWidth="sm"
                PaperProps={{
                    sx: {
                        width: '100%',
                        maxWidth: 680,
                        maxHeight: '95vh',
                        borderRadius: '10px',
                        boxShadow: '0 8px 40px rgba(0,0,0,0.18)',
                    },
                }}
            >
                {/* ── Title ── */}
                <DialogTitle
                    sx={{
                        bgcolor: '#2563eb',
                        color: '#fff',
                        textAlign: 'center',
                        fontWeight: 700,
                        fontSize: '0.85rem',
                        letterSpacing: 1.5,
                        py: 1.2,
                        px: 2,
                        position: 'relative',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        minHeight: 42,
                    }}
                >
                    {editingMemberId ? 'EDIT WORKFORCE' : 'ENROLL WORKFORCE'}
                    <IconButton
                        size="small"
                        onClick={() => setFullEnrollOpen(false)}
                        sx={{ color: '#fff', position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)' }}
                    >
                        <CloseIcon sx={{ fontSize: '0.95rem' }} />
                    </IconButton>
                </DialogTitle>

                {/* ── Content ── */}
                <DialogContent
                    dividers
                    sx={{
                        p: 0,
                        bgcolor: '#f7f8fa',
                        overflowY: 'auto',
                        '&::-webkit-scrollbar': { width: 4 },
                        '&::-webkit-scrollbar-thumb': { bgcolor: '#ccc', borderRadius: 4 },
                    }}
                >
                    <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>

                        {/* ── Personal Information ── */}
                        <Box sx={{ bgcolor: '#fff', borderRadius: '8px', p: 1.75, border: '1px solid #e8eaf0' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.7, mb: 1.25 }}>
                                <PersonOutlineIcon sx={{ fontSize: '1rem', color: '#1a237e' }} />
                                <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: '#111' }}>Personal Information</Typography>
                            </Box>
                            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.2, width: '100%' }}>
                                {/* Full Name */}
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Full Name <Box component="span" sx={{ color: 'error.main' }}>*</Box></Typography>
                                    <TextField size="small" fullWidth placeholder="Enter full name" value={fullForm.full_name} onChange={(e) => setFullForm((p) => ({ ...p, full_name: e.target.value }))}
                                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.86rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '8px', px: '10px', fontSize: '0.86rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                    />
                                </Box>
                                {/* Date of Birth */}
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Date of Birth</Typography>
                                    <TextField size="small" fullWidth type="date" InputLabelProps={{ shrink: true }} value={fullForm.dob} onChange={(e) => setFullForm((p) => ({ ...p, dob: e.target.value }))}
                                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.86rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '8px', px: '10px', fontSize: '0.86rem' } }}
                                    />
                                </Box>
                                {/* Gender */}
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Gender</Typography>
                                    <Select fullWidth displayEmpty size="small" value={fullForm.gender} onChange={(e) => setFullForm((p) => ({ ...p, gender: e.target.value }))}
                                        renderValue={(v) => v || <span style={{ color: '#aaa', fontSize: '0.86rem' }}>Select gender...</span>}
                                        sx={{ borderRadius: '6px', fontSize: '0.86rem', width: '100%', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#d0d5dd' }, '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#aab4c4' }, '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#2563eb', borderWidth: 1.5 }, '& .MuiSelect-select': { py: '8px', px: '10px', fontSize: '0.86rem', color: fullForm.gender ? '#333' : '#aaa' } }}
                                    >
                                        <MenuItem value="">Select</MenuItem>
                                        {GENDER_OPTIONS.map((o) => <MenuItem key={o} value={o}>{o}</MenuItem>)}
                                    </Select>
                                </Box>
                                {/* Email */}
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Email Address</Typography>
                                    <TextField size="small" fullWidth placeholder="e.g. name@example.com" value={fullForm.email} onChange={(e) => setFullForm((p) => ({ ...p, email: e.target.value }))}
                                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.86rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '8px', px: '10px', fontSize: '0.86rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                    />
                                </Box>
                                {/* Contact Number */}
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Contact Number <Box component="span" sx={{ color: 'error.main' }}>*</Box></Typography>
                                    <TextField size="small" fullWidth placeholder="e.g. 9876543210" value={fullForm.phone} onChange={(e) => setFullForm((p) => ({ ...p, phone: e.target.value }))}
                                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.86rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '8px', px: '10px', fontSize: '0.86rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                    />
                                </Box>
                                {/* WhatsApp */}
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>WhatsApp Number</Typography>
                                    <TextField size="small" fullWidth placeholder="e.g. 9876543210" value={fullForm.whatsapp} onChange={(e) => setFullForm((p) => ({ ...p, whatsapp: e.target.value }))}
                                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.86rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '8px', px: '10px', fontSize: '0.86rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                    />
                                </Box>
                            </Box>
                        </Box>

                        {/* ── Job Details ── */}
                        <Box sx={{ bgcolor: '#fff', borderRadius: '8px', p: 1.75, border: '1px solid #e8eaf0' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.7, mb: 1.25 }}>
                                <WorkOutlineIcon sx={{ fontSize: '1rem', color: '#1a237e' }} />
                                <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: '#111' }}>Job Details</Typography>
                            </Box>
                            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.2, width: '100%' }}>
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Department</Typography>
                                    <Select fullWidth displayEmpty size="small" value={fullForm.department} onChange={(e) => handleDepartmentSelect(e.target.value, 'full')}
                                        renderValue={(v) => { const d = departments.find((dep) => String(dep.id) === v); return d ? d.name : <span style={{ color: '#aaa', fontSize: '0.8rem' }}>Select department...</span>; }}
                                        sx={{ borderRadius: '6px', fontSize: '0.8rem', width: '100%', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#d0d5dd' }, '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#aab4c4' }, '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#2563eb', borderWidth: 1.5 }, '& .MuiSelect-select': { py: '6px', px: '10px', fontSize: '0.8rem' } }}
                                    >
                                        <MenuItem value="">Select</MenuItem>
                                        {departments.map((d) => <MenuItem key={d.id} value={String(d.id)}>{d.name}</MenuItem>)}
                                        <MenuItem value="__new_department__">+ New Department</MenuItem>
                                    </Select>
                                </Box>
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Category</Typography>
                                    <TextField size="small" fullWidth placeholder="Select a department first" value={fullForm.category} onChange={(e) => setFullForm((p) => ({ ...p, category: e.target.value }))}
                                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.8rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '6px', px: '10px', fontSize: '0.8rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                    />
                                </Box>
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Role / Designation</Typography>
                                    <TextField size="small" fullWidth placeholder="Enter role" value={fullForm.role_designation} onChange={(e) => setFullForm((p) => ({ ...p, role_designation: e.target.value }))}
                                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.8rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '6px', px: '10px', fontSize: '0.8rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                    />
                                </Box>
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Working Style</Typography>
                                    <Select fullWidth displayEmpty size="small" value={fullForm.working_style} onChange={(e) => setFullForm((p) => ({ ...p, working_style: e.target.value }))}
                                        renderValue={(v) => v || <span style={{ color: '#aaa', fontSize: '0.8rem' }}>Select working style...</span>}
                                        sx={{ borderRadius: '6px', fontSize: '0.8rem', width: '100%', '& .MuiOutlinedInput-notchedOutline': { borderColor: '#d0d5dd' }, '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#aab4c4' }, '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#2563eb', borderWidth: 1.5 }, '& .MuiSelect-select': { py: '6px', px: '10px', fontSize: '0.8rem', color: fullForm.working_style ? '#333' : '#aaa' } }}
                                    >
                                        <MenuItem value="">Select</MenuItem>
                                        {WORKING_STYLE_OPTIONS.map((o) => <MenuItem key={o} value={o}>{o}</MenuItem>)}
                                    </Select>
                                </Box>
                            </Box>
                        </Box>

                        {/* ── Current Address ── */}
                        <Box sx={{ bgcolor: '#fff', borderRadius: '8px', p: 1.75, border: '1px solid #e8eaf0' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.7, mb: 1.25 }}>
                                <LocationOnOutlinedIcon sx={{ fontSize: '1rem', color: '#1a237e' }} />
                                <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: '#111' }}>Current Address</Typography>
                            </Box>
                            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.2, width: '100%' }}>
                                {[
                                    { label: 'Address Line 1', field: 'curr_address_line_1', placeholder: 'Address Line 1' },
                                    { label: 'Address Line 2', field: 'curr_address_line_2', placeholder: 'Address Line 2' },
                                    { label: 'Country', field: 'curr_country', placeholder: 'Country' },
                                    { label: 'State / Province', field: 'curr_state', placeholder: 'State / Province' },
                                    { label: 'City', field: 'curr_city', placeholder: 'City' },
                                    { label: 'Pincode / ZIP', field: 'curr_pincode', placeholder: 'Pincode / ZIP' },
                                ].map(({ label, field, placeholder }) => (
                                    <Box key={field}>
                                        <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>{label}</Typography>
                                        <TextField size="small" fullWidth placeholder={placeholder} value={fullForm[field]} onChange={(e) => setFullForm((p) => ({ ...p, [field]: e.target.value }))}
                                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.8rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '6px', px: '10px', fontSize: '0.8rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                        />
                                    </Box>
                                ))}
                            </Box>
                        </Box>

                        {/* ── Permanent Address ── */}
                        <Box sx={{ bgcolor: '#fff', borderRadius: '8px', p: 1.75, border: '1px solid #e8eaf0' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', mb: 1.25 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.7 }}>
                                    <FlagOutlinedIcon sx={{ fontSize: '1rem', color: '#1a237e' }} />
                                    <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: '#111' }}>Permanent Address</Typography>
                                </Box>
                                <FormControlLabel
                                    control={<Checkbox size="small" checked={fullForm.same_as_current} onChange={(e) => setFullForm((p) => ({ ...p, same_as_current: e.target.checked }))} sx={{ py: 0, '& .MuiSvgIcon-root': { fontSize: '0.85rem' } }} />}
                                    label={<Typography sx={{ fontSize: '0.72rem', color: '#555' }}>Same as current address</Typography>}
                                    sx={{ m: 0 }}
                                />
                            </Box>
                            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.2, width: '100%' }}>
                                {[
                                    { label: 'Address Line 1', field: 'perm_address_line_1', currField: 'curr_address_line_1', placeholder: 'Address Line 1' },
                                    { label: 'Address Line 2', field: 'perm_address_line_2', currField: 'curr_address_line_2', placeholder: 'Address Line 2' },
                                    { label: 'Country', field: 'perm_country', currField: 'curr_country', placeholder: 'Country' },
                                    { label: 'State / Province', field: 'perm_state', currField: 'curr_state', placeholder: 'State / Province' },
                                    { label: 'City', field: 'perm_city', currField: 'curr_city', placeholder: 'City' },
                                    { label: 'Pincode / ZIP', field: 'perm_pincode', currField: 'curr_pincode', placeholder: 'Pincode / ZIP' },
                                ].map(({ label, field, currField, placeholder }) => (
                                    <Box key={field}>
                                        <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>{label}</Typography>
                                        <TextField size="small" fullWidth placeholder={placeholder} disabled={fullForm.same_as_current}
                                            value={fullForm.same_as_current ? fullForm[currField] : fullForm[field]}
                                            onChange={(e) => setFullForm((p) => ({ ...p, [field]: e.target.value }))}
                                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.8rem', bgcolor: fullForm.same_as_current ? '#f5f5f5' : '#fff', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '6px', px: '10px', fontSize: '0.8rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                        />
                                    </Box>
                                ))}
                            </Box>
                        </Box>

                        {/* ── Languages ── */}
                        <Box sx={{ bgcolor: '#fff', borderRadius: '8px', p: 1.75, border: '1px solid #e8eaf0' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.7, mb: 1.25 }}>
                                <TranslateIcon sx={{ fontSize: '1rem', color: '#1a237e' }} />
                                <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: '#111' }}>Languages</Typography>
                            </Box>
                            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.2, width: '100%' }}>
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>First Language</Typography>
                                    <TextField size="small" fullWidth placeholder="First language" value={fullForm.first_language} onChange={(e) => setFullForm((p) => ({ ...p, first_language: e.target.value }))}
                                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.8rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '6px', px: '10px', fontSize: '0.8rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                    />
                                </Box>
                                <Box>
                                    <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>Second Language</Typography>
                                    <TextField size="small" fullWidth placeholder="Second language" value={fullForm.second_language} onChange={(e) => setFullForm((p) => ({ ...p, second_language: e.target.value }))}
                                        sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.8rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '6px', px: '10px', fontSize: '0.8rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                    />
                                </Box>
                            </Box>
                        </Box>

                        {/* ── Banking Details ── */}
                        <Box sx={{ bgcolor: '#fff', borderRadius: '8px', p: 1.75, border: '1px solid #e8eaf0' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.7, mb: 1.25 }}>
                                <AccountBalanceOutlinedIcon sx={{ fontSize: '1rem', color: '#1a237e' }} />
                                <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: '#111' }}>Banking Details</Typography>
                            </Box>
                            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.2, width: '100%' }}>
                                {[
                                    { label: 'Account Name', field: 'bank_account_name', placeholder: 'Name on bank account' },
                                    { label: 'Bank Name', field: 'bank_name', placeholder: 'e.g. HDFC Bank' },
                                    { label: 'Account Number', field: 'account_number', placeholder: 'Enter account number' },
                                    { label: 'IFSC Code', field: 'ifsc', placeholder: 'e.g. HDFC0001234' },
                                ].map(({ label, field, placeholder }) => (
                                    <Box key={field}>
                                        <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.4 }}>{label}</Typography>
                                        <TextField
                                            size="small"
                                            fullWidth
                                            placeholder={placeholder}
                                            value={canViewAmounts ? fullForm[field] : "****"}
                                            onChange={(e) => setFullForm((p) => ({ ...p, [field]: e.target.value }))}
                                            disabled={!canViewAmounts}
                                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.8rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '6px', px: '10px', fontSize: '0.8rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                                        />
                                    </Box>
                                ))}
                            </Box>
                        </Box>

                        {/* ── Identity Documents ── */}
                        <Box sx={{ bgcolor: '#fff', borderRadius: '8px', p: 1.75, border: '1px solid #e8eaf0' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.7 }}>
                                <BadgeOutlinedIcon sx={{ fontSize: '1rem', color: '#1a237e' }} />
                                <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: '#111' }}>Identity Documents</Typography>
                            </Box>
                            <Typography sx={{ fontSize: '0.7rem', color: '#777', ml: 3, mb: 1.25 }}>Upload your identity documents.</Typography>
                            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.2, width: '100%' }}>
                                {[
                                    { label: 'Aadhaar Card', key: 'aadhaar', value: fullForm.aadhaar_document, inputRef: aadhaarInputRef },
                                    { label: 'PAN Card', key: 'pan', value: fullForm.pan_document, inputRef: panInputRef },
                                ].map((document) => (
                                    <Paper
                                        key={document.key}
                                        variant="outlined"
                                        onClick={() => !docUploading[document.key] && document.inputRef.current?.click()}
                                        sx={{
                                            width: '100%',
                                            p: 1.5,
                                            textAlign: 'center',
                                            color: 'text.secondary',
                                            minHeight: 90,
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            borderStyle: 'dashed',
                                            borderColor: document.value ? '#22c55e' : '#c5cad8',
                                            borderRadius: '8px',
                                            cursor: docUploading[document.key] ? 'not-allowed' : 'pointer',
                                            bgcolor: '#fafbfc',
                                            gap: 0.4,
                                            transition: 'all 0.2s',
                                            '&:hover': docUploading[document.key] ? {} : { borderColor: '#2563eb', bgcolor: '#f0f4ff' },
                                        }}
                                    >
                                        <input
                                            ref={document.inputRef}
                                            type="file"
                                            hidden
                                            accept=".pdf,.jpg,.jpeg,.png"
                                            onChange={(event) => {
                                                const file = event.target.files?.[0];
                                                if (file) handleUploadDocument(document.key, file);
                                                event.target.value = '';
                                            }}
                                        />
                                        <UploadFileOutlinedIcon sx={{ fontSize: '1.4rem', color: document.value ? '#22c55e' : '#888' }} />
                                        <Typography sx={{ fontWeight: 700, fontSize: '0.75rem', color: '#333' }}>{document.label}</Typography>
                                        {docUploading[document.key] ? (
                                            <Typography sx={{ fontSize: '0.65rem', color: '#2563eb', lineHeight: 1.4 }}>Uploading...</Typography>
                                        ) : document.value ? (
                                            <Typography sx={{ fontSize: '0.65rem', color: '#16a34a', lineHeight: 1.4 }}>
                                                Uploaded • <Box component="a" href={document.value} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()} sx={{ color: '#2563eb', textDecoration: 'underline' }}>View</Box>
                                            </Typography>
                                        ) : (
                                            <Typography sx={{ fontSize: '0.65rem', color: '#888', lineHeight: 1.4 }}>
                                                Click to upload or{' '}
                                                <Box component="span" sx={{ color: '#2563eb', textDecoration: 'underline' }}>browse</Box>
                                                <br />PDF, JPG, PNG (Max 5MB)
                                            </Typography>
                                        )}
                                    </Paper>
                                ))}
                            </Box>
                        </Box>

                        {/* ── Current Location ── */}
                        <Box sx={{ bgcolor: '#fff', borderRadius: '8px', p: 1.75, border: '1px solid #e8eaf0' }}>
                            <Typography sx={{ fontWeight: 600, fontSize: '0.72rem', color: '#222', mb: 0.5 }}>Current Location</Typography>
                            <TextField size="small" fullWidth placeholder="Enter current location" value={fullForm.current_location} onChange={(e) => setFullForm((p) => ({ ...p, current_location: e.target.value }))}
                                sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.8rem', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '6px', px: '10px', fontSize: '0.8rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                            />
                        </Box>

                        {/* ── Notes ── */}
                        <Box sx={{ bgcolor: '#fff', borderRadius: '8px', p: 1.75, border: '1px solid #e8eaf0' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.7 }}>
                                <NotesOutlinedIcon sx={{ fontSize: '1rem', color: '#1a237e' }} />
                                <Typography sx={{ fontWeight: 700, fontSize: '0.82rem', color: '#111' }}>Notes</Typography>
                            </Box>
                            <Typography sx={{ fontSize: '0.7rem', color: '#777', ml: 3, mb: 1 }}>Add any additional notes or remarks.</Typography>
                            <TextField size="small" fullWidth multiline minRows={3} placeholder="Enter your notes here..." value={fullForm.notes} onChange={(e) => setFullForm((p) => ({ ...p, notes: e.target.value }))}
                                sx={{ '& .MuiOutlinedInput-root': { borderRadius: '6px', fontSize: '0.8rem', alignItems: 'flex-start', '& fieldset': { borderColor: '#d0d5dd' }, '&:hover fieldset': { borderColor: '#aab4c4' }, '&.Mui-focused fieldset': { borderColor: '#2563eb', borderWidth: 1.5 } }, '& .MuiInputBase-input': { py: '6px', px: '10px', fontSize: '0.8rem', '&::placeholder': { color: '#aaa', opacity: 1 } } }}
                            />
                        </Box>

                    </Box>
                </DialogContent>

                {/* ── Actions ── */}
                <DialogActions sx={{ p: 1.5, gap: 1.2, bgcolor: '#fff', borderTop: '1px solid #e8eaf0' }}>
                    <Button
                        variant="outlined"
                        disabled={saving}
                        onClick={handleFullEnroll}
                        sx={{ flex: 1, height: 38, fontSize: '0.8rem', textTransform: 'none', fontWeight: 600, borderColor: '#2563eb', color: '#2563eb', borderRadius: '6px', '&:hover': { bgcolor: '#eff6ff', borderColor: '#2563eb' } }}
                    >
                        Save as Draft
                    </Button>
                    <Button
                        variant="contained"
                        disabled={saving}
                        onClick={handleFullEnroll}
                        sx={{ flex: 1, height: 38, fontSize: '0.8rem', textTransform: 'none', fontWeight: 700, bgcolor: '#0c162e', borderRadius: '6px', letterSpacing: 0.8, '&:hover': { bgcolor: '#1a2a4a' } }}
                    >
                        {editingMemberId ? 'UPDATE' : 'ENROLL'}
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog open={newDepartmentOpen} onClose={() => setNewDepartmentOpen(false)} fullWidth maxWidth="xs">
                <DialogTitle>New Department</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        label="Department Name"
                        fullWidth
                        value={newDepartmentName}
                        onChange={(event) => setNewDepartmentName(event.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setNewDepartmentOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleCreateDepartment} disabled={saving || !newDepartmentName.trim()}>
                        Create
                    </Button>
                </DialogActions>
            </Dialog>

            <Dialog open={permissionsDialogOpen} onClose={() => setPermissionsDialogOpen(false)} fullWidth maxWidth="md">
                <DialogTitle>Edit Permissions</DialogTitle>
                <DialogContent dividers>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                        Editing permissions for {permissionTarget?.label || 'member'}
                    </Typography>

                    {Object.keys(permissionSchema).length === 0 ? (
                        <Box sx={{ py: 2, display: 'flex', justifyContent: 'center' }}>
                            <CircularProgress size={24} />
                        </Box>
                    ) : (
                        Object.entries(permissionSchema).map(([area, features]) => (
                            <Accordion key={area} disableGutters sx={{ mb: 1 }}>
                                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                    <Typography fontWeight={600}>
                                        {area.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())}
                                    </Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    <Grid container spacing={1}>
                                        {Object.entries(features).map(([key, label]) => (
                                            <Grid item xs={12} sm={6} key={key}>
                                                <FormControlLabel
                                                    control={(
                                                        <Checkbox
                                                            size="small"
                                                            checked={formPermissions[area]?.[key] || false}
                                                            onChange={(event) => handlePermissionChange(area, key, event.target.checked)}
                                                        />
                                                    )}
                                                    label={<Typography variant="body2">{label}</Typography>}
                                                />
                                            </Grid>
                                        ))}
                                    </Grid>
                                </AccordionDetails>
                            </Accordion>
                        ))
                    )}
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setPermissionsDialogOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={handleUpdatePermissions} disabled={saving}>
                        {saving ? 'Updating...' : 'Update Permissions'}
                    </Button>
                </DialogActions>
            </Dialog>

            {/* User Inactivity / Idle Alarm Settings Dialog */}
            <Dialog open={idleSettingsOpen} onClose={() => setIdleSettingsOpen(false)} maxWidth="xs" fullWidth PaperProps={{ sx: { borderRadius: '12px' } }}>
                <DialogTitle sx={{ fontWeight: 800 }}>Inactivity Alarm Settings</DialogTitle>
                <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 3, pt: 2 }}>
                    <Typography variant="body2" color="text.secondary">
                        Configure custom idle inactivity timeout settings for <strong>{idleSettingsTarget?.full_name}</strong>.
                    </Typography>
                    
                    <FormControl fullWidth size="small">
                        <InputLabel id="idle-override-type-label">Override Mode</InputLabel>
                        <Select
                            labelId="idle-override-type-label"
                            value={
                                overrideEnabled === null
                                    ? 'inherit'
                                    : overrideEnabled === true
                                    ? 'custom'
                                    : 'disabled'
                            }
                            label="Override Mode"
                            onChange={(e) => {
                                const val = e.target.value;
                                if (val === 'inherit') {
                                    setOverrideEnabled(null);
                                } else if (val === 'custom') {
                                    setOverrideEnabled(true);
                                } else {
                                    setOverrideEnabled(false);
                                }
                            }}
                        >
                            <MenuItem value="inherit">Inherit (Use Office / Global Default)</MenuItem>
                            <MenuItem value="custom">Custom Timeout Limit</MenuItem>
                            <MenuItem value="disabled">Disable Idle Alarm Entirely</MenuItem>
                        </Select>
                    </FormControl>

                    {overrideEnabled === true && (
                        <TextField
                            size="small"
                            type="number"
                            label="Custom Timeout Limit (Minutes)"
                            value={overrideMinutes}
                            onChange={(e) => setOverrideMinutes(Math.max(1, parseInt(e.target.value) || 0))}
                            fullWidth
                            InputProps={{ inputProps: { min: 1 } }}
                            sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px' } }}
                        />
                    )}
                </DialogContent>
                <DialogActions sx={{ p: 2 }}>
                    <Button onClick={() => setIdleSettingsOpen(false)} sx={{ textTransform: 'none', fontWeight: 600 }}>Cancel</Button>
                    <Button 
                        onClick={handleSaveIdleSettings} 
                        variant="contained" 
                        disabled={saving}
                        sx={{ textTransform: 'none', fontWeight: 700, borderRadius: '8px' }}
                    >
                        Save Settings
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}