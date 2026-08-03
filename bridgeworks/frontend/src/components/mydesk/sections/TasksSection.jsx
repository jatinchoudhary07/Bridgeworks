import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Alert,
    alpha,
    Avatar,
    Box,
    Button,
    Checkbox,
    Chip,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    Divider,
    Drawer,
    FormControl,
    IconButton,
    InputLabel,
    List,
    ListItemAvatar,
    ListItem,
    ListItemText,
    MenuItem,
    Paper,
    Popover,
    Select,
    Snackbar,
    Stack,
    Tab,
    Tabs,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    AttachFile as AttachFileIcon,
    ChatBubbleOutline as ChatBubbleOutlineIcon,
    DeleteOutline as DeleteOutlineIcon,
    Edit as EditIcon,
    HelpOutline as HelpOutlineIcon,
    NotificationsActive as NotificationsActiveIcon,
    Check as CheckIcon,
    WarningAmber as WarningAmberIcon,
    ViewKanban as ViewKanbanIcon,
    ViewList as ViewListIcon,
    Add as AddIcon,
    Close as CloseIcon,
    Send as SendIcon,
} from '@mui/icons-material';
import { createMyDeskTodo, deleteMyDeskTodo, deleteMyDeskTodoAttachment, getMyDeskTodo, listMyDeskTodos, updateMyDeskTodo } from '../mydeskService';
import { useUser } from '../../../contexts/UserContext';
import { useLocation } from 'react-router-dom';
import ActivityLogger from '../../../utils/ActivityLogger';
import PresenceBadge from '../../common/PresenceBadge';

const statusMeta = {
    todo: { label: 'Todo', empty: 'No tasks here', color: 'info' },
    in_progress: { label: 'In Progress', empty: 'Nothing in progress', color: 'warning' },
    done: { label: 'Done', empty: 'No completed tasks', color: 'success' },
};

const TASK_ATTACHMENT_ACCEPT = [
    'image/*',
    '.pdf',
    '.doc',
    '.docx',
    '.xls',
    '.xlsx',
    '.ppt',
    '.pptx',
    '.txt',
    '.csv',
].join(',');

const COMMENT_AUTHOR_COLORS = [
    '#1e88e5',
    '#8e24aa',
    '#00897b',
    '#fb8c00',
    '#d81b60',
    '#3949ab',
    '#43a047',
    '#6d4c41',
    '#039be5',
    '#7cb342',
];

const createInitialTaskForm = () => ({
    title: '',
    dueDate: new Date().toISOString().slice(0, 10),
    dueTime: new Date().toTimeString().slice(0, 5),
    priority: 'medium',
    status: 'todo',
    assignee: ['me'],
    comment: '',
    attachments: [],
});

const getTaskCommentText = (entry) => {
    if (typeof entry === 'string') return entry.trim();
    if (entry && typeof entry === 'object') {
        return String(entry.text || entry.comment || '').trim();
    }
    return '';
};

const getTaskCommentAuthorName = (entry) => {
    if (entry && typeof entry === 'object') {
        return String(entry.author_name || entry.authorName || entry.by || '').trim();
    }
    return '';
};

const getTaskCommentAuthorId = (entry) => {
    if (entry && typeof entry === 'object') {
        const value = entry.author_id ?? entry.authorId ?? null;
        if (value === null || value === undefined || value === '') return null;
        return String(value);
    }
    return null;
};

const getTaskCommentCreatedAt = (entry) => {
    if (entry && typeof entry === 'object') {
        return String(entry.created_at || entry.createdAt || '').trim();
    }
    return '';
};

const getTaskCommentAuthorKey = (entry, fallbackName = '') => {
    const authorId = getTaskCommentAuthorId(entry);
    if (authorId) {
        return `id:${authorId}`;
    }

    const resolvedName = getTaskCommentAuthorName(entry) || String(fallbackName || '').trim();
    if (resolvedName) {
        return `name:${resolvedName.toLowerCase()}`;
    }

    return '';
};

const normalizeTaskCommentEntry = (entry) => {
    const text = getTaskCommentText(entry);
    if (!text) return null;
    return {
        text,
        author_name: getTaskCommentAuthorName(entry),
        author_id: getTaskCommentAuthorId(entry),
        created_at: getTaskCommentCreatedAt(entry),
    };
};

export default function TasksSection({ members = [] }) {
    const location = useLocation();
    const { user: currentUser } = useUser();
    const myId = currentUser?.id ? String(currentUser.id) : '';
    const myName = currentUser ? (currentUser.full_name || currentUser.name || currentUser.username) : 'Me';
    const taskRowRefs = useRef({});
    const taskCommentAnchorRefs = useRef({});
    const handledDeepLinkRef = useRef('');
    const [view, setView] = useState('kanban');
    const [category, setCategory] = useState('assigned_to_me');
    const [tasks, setTasks] = useState([]);
    const [selectedTask, setSelectedTask] = useState(null);
    const [editingTaskId, setEditingTaskId] = useState(null);
    const [commentTask, setCommentTask] = useState(null);
    const [commentAnchorEl, setCommentAnchorEl] = useState(null);
    const [commentDraft, setCommentDraft] = useState('');
    const [draggingTaskId, setDraggingTaskId] = useState(null);
    const [reminderTask, setReminderTask] = useState(null);
    const [reminderDraft, setReminderDraft] = useState('');
    const [activeReminder, setActiveReminder] = useState(null);
    const [shownReminders, setShownReminders] = useState({});
    const [highlightTaskId, setHighlightTaskId] = useState(null);
    const [highlightCommentIndex, setHighlightCommentIndex] = useState(-1);
    const [form, setForm] = useState(createInitialTaskForm);

    const normalizedMembers = useMemo(() => (
        (Array.isArray(members) ? members : [])
            .map((member) => ({
                ...member,
                id: member?.id != null ? String(member.id) : '',
                label: member?.full_name || member?.username || member?.email || '',
            }))
            .filter((member) => member.id && member.label)
    ), [members]);

    const assignableMembers = useMemo(() => {
        const myUsername = String(currentUser?.username || '').trim().toLowerCase();
        const myEmail = String(currentUser?.email || '').trim().toLowerCase();

        const uniqueMembers = normalizedMembers.filter((member, index, array) => (
            index === array.findIndex((candidate) => candidate.id === member.id)
        ));

        return uniqueMembers.filter((member) => {
            if (myId && member.id === myId) return false;

            const memberUsername = String(member?.username || '').trim().toLowerCase();
            if (myUsername && memberUsername && memberUsername === myUsername) return false;

            const memberEmail = String(member?.email || '').trim().toLowerCase();
            if (myEmail && memberEmail && memberEmail === myEmail) return false;

            return true;
        });
    }, [normalizedMembers, myId, currentUser?.username, currentUser?.email]);

    const mapTodoToTask = (item, options = {}) => {
        const detailsLoaded = Boolean(options?.detailsLoaded);
        const meta = item?.meta && typeof item.meta === 'object' ? item.meta : {};
        const title = meta.title || item.text || '';
        const resolvedStatus = meta.status || (item.is_done ? 'done' : 'todo');
        const rawComments = Array.isArray(meta.comments) ? meta.comments : [];
        const firstCommentText = rawComments.length > 0 ? getTaskCommentText(rawComments[0]) : '';
        const description = typeof meta.description === 'string'
            ? meta.description
            : (!meta.commentRequested && rawComments.length > 0 ? firstCommentText : '');
        const normalizedComments = (typeof meta.description !== 'string' && !meta.commentRequested && rawComments.length > 0)
            ? rawComments.slice(1)
            : rawComments;
        const normalizedCommentEntries = normalizedComments
            .map((comment) => normalizeTaskCommentEntry(comment))
            .filter(Boolean);

        return {
            id: item.id,
            title,
            dueDate: meta.dueDate || new Date().toISOString().slice(0, 10),
            dueTime: meta.dueTime || '',
            priority: meta.priority || 'medium',
            status: resolvedStatus,
            assignee: meta.assignee || 'Me',
            assignee_id: meta.assignee_id || null,
            assignees: Array.isArray(meta.assignees) ? meta.assignees : [],
            assignee_ids: Array.isArray(meta.assignee_ids) ? meta.assignee_ids : [],
            assignedBy: meta.assignedBy || 'Me',
            assigned_by_id: meta.assigned_by_id || null,
            description,
            comments: normalizedCommentEntries,
            escalated: Boolean(meta.escalated),
            reminders: typeof meta.reminders === 'boolean' ? meta.reminders : false,
            reminderAt: typeof meta.reminderAt === 'string' ? meta.reminderAt : '',
            helpRequested: Boolean(meta.helpRequested),
            commentRequested: Boolean(meta.commentRequested),
            attachmentName: meta.attachmentName || item.attachment_url?.split('/').pop() || '',
            attachmentUrl: item.attachment_url || null,
            taskAttachments: Array.isArray(item.task_attachments) ? item.task_attachments : [],
            sort_order: item.sort_order,
            detailsLoaded,
        };
    };

    const buildTodoPayload = (task, sortOrder = 0) => ({
        text: task.title || 'Untitled task',
        is_done: task.status === 'done',
        recurring: 'none',
        sort_order: sortOrder,
        meta: {
            type: 'task',
            title: task.title || 'Untitled task',
            dueDate: task.dueDate,
            dueTime: task.dueTime || '',
            priority: task.priority,
            status: task.status,
            assignee: task.assignee,
            assignee_id: task.assignee_id,
            assignees: Array.isArray(task.assignees) ? task.assignees : [],
            assignee_ids: Array.isArray(task.assignee_ids) ? task.assignee_ids : [],
            assignedBy: task.assignedBy || 'Me',
            assigned_by_id: task.assigned_by_id,
            description: task.description || '',
            comments: (Array.isArray(task.comments) ? task.comments : [])
                .map((comment) => normalizeTaskCommentEntry(comment))
                .filter(Boolean),
            escalated: Boolean(task.escalated),
            reminders: Boolean(task.reminders),
            reminderAt: task.reminderAt || '',
            helpRequested: Boolean(task.helpRequested),
            commentRequested: Boolean(task.commentRequested),
            attachmentName: task.attachmentName || '',
        },
    });

    useEffect(() => {
        let mounted = true;

        listMyDeskTodos({ type: 'task', includeAttachments: false })
            .then((data) => {
                if (!mounted) return;
                const items = Array.isArray(data) ? data : [];
                const normalized = items
                    .filter((entry) => (entry?.meta && typeof entry.meta === 'object' ? entry.meta.type === 'task' : false))
                    .slice()
                    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
                    .map((entry) => mapTodoToTask(entry, { detailsLoaded: false }));
                setTasks(normalized);
            })
            .catch(() => { });

        return () => {
            mounted = false;
        };
    }, []);

    const isOverdue = (task) => new Date(task.dueDate).getTime() < new Date().setHours(0, 0, 0, 0) && task.status !== 'done';

    const getTaskAssigneeNames = useCallback((task) => {
        if (Array.isArray(task.assignees) && task.assignees.length > 0) {
            return task.assignees
                .map((entry) => (entry?.label || entry?.name || '').trim())
                .filter(Boolean);
        }

        const fallback = (task.assignee || 'Me').trim();
        return fallback ? [fallback] : ['Me'];
    }, []);

    const normalizeIdentityLabel = useCallback((value) => String(value || '').trim().toLowerCase(), []);

    const matchesCurrentUserName = useCallback((value) => {
        const target = normalizeIdentityLabel(value);
        const mine = normalizeIdentityLabel(myName);
        return Boolean(target && mine && target === mine);
    }, [myName, normalizeIdentityLabel]);

    const isTaskAssignedToMe = useCallback((task) => {
        const assigneeIds = [
            ...(Array.isArray(task.assignee_ids) ? task.assignee_ids : []),
            task.assignee_id,
        ]
            .filter((value) => value !== null && value !== undefined && value !== '')
            .map((value) => String(value));

        if (myId) {
            if (assigneeIds.length > 0) {
                return assigneeIds.includes(myId);
            }
        }

        const names = getTaskAssigneeNames(task);
        if (names.some((name) => matchesCurrentUserName(name))) return true;

        if (!myId) {
            return names.some((name) => normalizeIdentityLabel(name) === 'me');
        }

        const hasLegacyMeAssignee = names.some((name) => normalizeIdentityLabel(name) === 'me');
        if (!hasLegacyMeAssignee) return false;

        if (task.assigned_by_id !== null && task.assigned_by_id !== undefined && task.assigned_by_id !== '') {
            return String(task.assigned_by_id) === myId;
        }

        return matchesCurrentUserName(task.assignedBy);
    }, [getTaskAssigneeNames, matchesCurrentUserName, myId, normalizeIdentityLabel]);

    const isTaskAssignedByMe = useCallback((task) => {
        if (myId && task.assigned_by_id !== null && task.assigned_by_id !== undefined && task.assigned_by_id !== '') {
            return String(task.assigned_by_id) === myId;
        }

        if (matchesCurrentUserName(task.assignedBy)) return true;

        const isLegacyMeAssigner = normalizeIdentityLabel(task.assignedBy) === 'me';
        if (!isLegacyMeAssigner) return false;

        if (!myId) return true;

        const assigneeIds = [
            ...(Array.isArray(task.assignee_ids) ? task.assignee_ids : []),
            task.assignee_id,
        ]
            .filter((value) => value !== null && value !== undefined && value !== '')
            .map((value) => String(value));

        if (assigneeIds.length > 0 && assigneeIds.includes(myId)) {
            return false;
        }

        return true;
    }, [matchesCurrentUserName, myId, normalizeIdentityLabel]);

    const canDeleteTask = useCallback((task) => isTaskAssignedByMe(task), [isTaskAssignedByMe]);
    const canEditTask = useCallback((task) => isTaskAssignedByMe(task) || isTaskAssignedToMe(task), [isTaskAssignedByMe, isTaskAssignedToMe]);

    const resetTaskForm = useCallback(() => {
        setForm(createInitialTaskForm());
        setEditingTaskId(null);
    }, []);

    const hasAssigneeOtherThanMe = useCallback((task) => {
        const assigneeIds = [
            ...(Array.isArray(task.assignee_ids) ? task.assignee_ids : []),
            task.assignee_id,
        ]
            .filter((value) => value !== null && value !== undefined && value !== '')
            .map((value) => String(value));

        if (myId && assigneeIds.length > 0) {
            return assigneeIds.some((value) => value !== myId);
        }

        const names = getTaskAssigneeNames(task).map((name) => normalizeIdentityLabel(name));
        if (names.length === 0) return false;

        return names.some((name) => {
            if (!name || name === 'me') return false;
            if (normalizeIdentityLabel(myName) && name === normalizeIdentityLabel(myName)) return false;
            return true;
        });
    }, [getTaskAssigneeNames, myId, myName, normalizeIdentityLabel]);

    const categoryFiltered = useMemo(() => {
        return tasks.filter((task) => {
            const isAssignedToMe = isTaskAssignedToMe(task);
            const isAssignedByMe = isTaskAssignedByMe(task);
            const isAssignedToOthersByMe = isAssignedByMe && (!isAssignedToMe || hasAssigneeOtherThanMe(task));

            if (category === 'assigned_to_me') return isAssignedToMe;
            if (category === 'all_tasks') return isAssignedToMe || isAssignedByMe;
            if (category === 'assigned_by_me') return isAssignedToOthersByMe;
            if (category === 'overdue') return isOverdue(task);
            if (category === 'completed') return task.status === 'done';
            return true;
        });
    }, [tasks, category, isTaskAssignedToMe, isTaskAssignedByMe, hasAssigneeOtherThanMe]);

    const counts = useMemo(() => ({
        assigned_to_me: tasks.filter((task) => {
            return isTaskAssignedToMe(task);
        }).length,
        all_tasks: tasks.filter((task) => {
            return isTaskAssignedToMe(task) || isTaskAssignedByMe(task);
        }).length,
        assigned_by_me: tasks.filter((task) => {
            const isAssignedToMe = isTaskAssignedToMe(task);
            const isAssignedByMe = isTaskAssignedByMe(task);
            return isAssignedByMe && (!isAssignedToMe || hasAssigneeOtherThanMe(task));
        }).length,
        overdue: tasks.filter((task) => isOverdue(task)).length,
        completed: tasks.filter((task) => task.status === 'done').length,
    }), [tasks, isTaskAssignedToMe, isTaskAssignedByMe, hasAssigneeOtherThanMe]);

    const addTask = async () => {
        const cleanTitle = form.title.trim();
        if (!cleanTitle) return;

        // Resolve assigner and assignee
        const assignerName = myName;
        const assignerId = myId || null;

        const selectedAssigneesRaw = Array.isArray(form.assignee) ? form.assignee : [form.assignee];
        const selectedAssignees = selectedAssigneesRaw
            .map((value) => String(value))
            .filter(Boolean)
            .filter((value, index, array) => index === array.indexOf(value));

        const assigneeEntries = selectedAssignees.map((value) => {
            if (value === 'me') {
                return { id: assignerId, label: assignerName };
            }

            const memberObj = normalizedMembers.find((member) => member.id === value);
            if (!memberObj) return null;
            return { id: memberObj.id, label: memberObj.label };
        }).filter(Boolean);

        const uniqueAssigneeEntries = assigneeEntries.filter((entry, index, array) => {
            const key = entry.id != null && entry.id !== ''
                ? `id:${String(entry.id)}`
                : `name:${String(entry.label || '').trim().toLowerCase()}`;
            return index === array.findIndex((candidate) => {
                const candidateKey = candidate.id != null && candidate.id !== ''
                    ? `id:${String(candidate.id)}`
                    : `name:${String(candidate.label || '').trim().toLowerCase()}`;
                return candidateKey === key;
            });
        });

        const fallbackAssignee = { id: assignerId, label: assignerName };
        const normalizedAssignees = uniqueAssigneeEntries.length > 0 ? uniqueAssigneeEntries : [fallbackAssignee];
        const assigneeIds = normalizedAssignees
            .map((entry) => (entry.id != null && entry.id !== '' ? String(entry.id) : null))
            .filter(Boolean);
        const assigneeName = normalizedAssignees.map((entry) => entry.label).filter(Boolean).join(', ');

        const pendingAttachments = Array.isArray(form.attachments) ? form.attachments : [];

        const baseTask = editingTaskId
            ? tasks.find((task) => task.id === editingTaskId)
            : null;
        if (editingTaskId && !baseTask) {
            setEditingTaskId(null);
            return;
        }

        const nextTask = {
            ...(baseTask || {}),
            id: baseTask?.id || Date.now(),
            title: cleanTitle,
            dueDate: form.dueDate,
            dueTime: form.dueTime,
            priority: form.priority,
            status: form.status,
            assignee: assigneeName,
            assignee_id: assigneeIds[0] || null,
            assignees: normalizedAssignees,
            assignee_ids: assigneeIds,
            assignedBy: assignerName,
            assigned_by_id: assignerId,
            description: form.comment || '',
            comments: Array.isArray(baseTask?.comments) ? baseTask.comments : [],
            escalated: Boolean(baseTask?.escalated),
            reminders: Boolean(baseTask?.reminders),
            reminderAt: baseTask?.reminderAt || '',
            helpRequested: Boolean(baseTask?.helpRequested),
            commentRequested: Boolean(baseTask?.commentRequested),
            attachmentName: pendingAttachments?.[0]?.name || baseTask?.attachmentName || '',
            taskAttachments: Array.isArray(baseTask?.taskAttachments) ? baseTask.taskAttachments : [],
        };

        try {
            const sortOrder = Number(baseTask?.sort_order ?? tasks.length);
            const payload = (pendingAttachments.length > 0)
                ? (() => {
                    const formData = new FormData();
                    formData.append('text', nextTask.title || 'Untitled task');
                    formData.append('is_done', String(nextTask.status === 'done'));
                    formData.append('recurring', 'none');
                    formData.append('sort_order', String(sortOrder));
                    formData.append('meta', JSON.stringify(buildTodoPayload(nextTask, sortOrder).meta));
                    pendingAttachments.forEach((file) => formData.append('attachments', file));
                    return formData;
                })()
                : buildTodoPayload(nextTask, sortOrder);

            if (editingTaskId) {
                const updated = await updateMyDeskTodo(editingTaskId, payload);
                const mapped = mapTodoToTask(updated, { detailsLoaded: true });
                setTasks((previous) => previous.map((task) => (task.id === mapped.id ? mapped : task)));
                setSelectedTask((previous) => (previous?.id === mapped.id ? mapped : previous));
                ActivityLogger.track('TASK_UPDATE', 'TasksSection', location.pathname, { taskId: mapped.id, title: cleanTitle, priority: form.priority });
            } else {
                const created = await createMyDeskTodo(payload);
                const mapped = mapTodoToTask(created, { detailsLoaded: true });
                setTasks((previous) => [mapped, ...previous]);
                ActivityLogger.track('TASK_CREATE', 'TasksSection', location.pathname, { title: cleanTitle, priority: form.priority, assignee: assigneeName });
            }
        } catch {
            return;
        }

        resetTaskForm();
    };

    const openTaskForEdit = useCallback((task) => {
        if (!task || !canEditTask(task)) return;

        const candidateIds = [
            ...(Array.isArray(task.assignee_ids) ? task.assignee_ids : []),
            task.assignee_id,
        ]
            .filter((value) => value !== null && value !== undefined && value !== '')
            .map((value) => String(value));

        const uniqueAssignees = candidateIds
            .map((value) => (myId && value === myId ? 'me' : value))
            .filter((value, index, array) => value && array.indexOf(value) === index);

        const nextAssignees = uniqueAssignees.length > 0
            ? uniqueAssignees
            : (isTaskAssignedToMe(task) ? ['me'] : ['me']);

        setForm({
            title: task.title || '',
            dueDate: task.dueDate || new Date().toISOString().slice(0, 10),
            dueTime: task.dueTime || new Date().toTimeString().slice(0, 5),
            priority: task.priority || 'medium',
            status: task.status || 'todo',
            assignee: nextAssignees,
            comment: task.description || '',
            attachments: [],
        });
        setEditingTaskId(task.id);
        setSelectedTask(null);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }, [canEditTask, myId, isTaskAssignedToMe]);

    const addPendingAttachments = (event) => {
        const incoming = Array.from(event.target.files || []);
        if (incoming.length === 0) return;

        setForm((previous) => {
            const existing = Array.isArray(previous.attachments) ? previous.attachments : [];
            const keys = new Set(existing.map((file) => `${file.name}-${file.size}-${file.lastModified}`));
            const nextAttachments = [...existing];
            incoming.forEach((file) => {
                const key = `${file.name}-${file.size}-${file.lastModified}`;
                if (!keys.has(key)) {
                    keys.add(key);
                    nextAttachments.push(file);
                }
            });
            return { ...previous, attachments: nextAttachments };
        });

        event.target.value = '';
    };

    const removePendingAttachment = (fileToRemove) => {
        setForm((previous) => ({
            ...previous,
            attachments: (previous.attachments || []).filter((file) => (
                `${file.name}-${file.size}-${file.lastModified}` !== `${fileToRemove.name}-${fileToRemove.size}-${fileToRemove.lastModified}`
            )),
        }));
    };

    const categoryPills = [
        { id: 'all_tasks', label: 'All Tasks', color: 'info' },
        { id: 'assigned_to_me', label: 'My Tasks', color: 'primary' },
        { id: 'assigned_by_me', label: 'Assigned to Others', color: 'secondary' },
        { id: 'overdue', label: 'Overdue', color: 'error' },
        { id: 'completed', label: 'Completed', color: 'success' },
    ];

    const visibleCategoryPills = categoryPills.filter((pill, index, array) => {
        const labelKey = String(pill.label || '').trim().toLowerCase();
        return index === array.findIndex((candidate) => String(candidate.label || '').trim().toLowerCase() === labelKey);
    });

    const priorityPillSx = {
        critical: { bgcolor: 'error.main', color: 'error.contrastText' },
        high: { bgcolor: 'error.dark', color: 'error.contrastText' },
        medium: { bgcolor: 'warning.main', color: 'warning.contrastText' },
        low: { bgcolor: 'success.main', color: 'success.contrastText' },
    };

    const assigneeColors = ['primary.main', 'secondary.main', 'warning.main', 'success.main', 'info.main'];

    const assigneeInitials = (name) => {
        const text = (name || 'Me').trim();
        if (!text) return 'ME';
        const parts = text.split(/\s+/).filter(Boolean);
        if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
        return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    };

    const assigneeBadgeColor = (name) => {
        const value = (name || 'Me');
        let hash = 0;
        for (let index = 0; index < value.length; index += 1) {
            hash = value.charCodeAt(index) + ((hash << 5) - hash);
        }
        return assigneeColors[Math.abs(hash) % assigneeColors.length];
    };

    const commentAuthorColorMap = useMemo(() => {
        const comments = Array.isArray(commentTask?.comments) ? commentTask.comments : [];
        const map = {};
        let cursor = 0;

        comments.forEach((comment, index) => {
            const fallbackAuthorName = getTaskCommentAuthorName(comment) || commentTask?.assignedBy || 'Member';
            const authorKey = getTaskCommentAuthorKey(comment, fallbackAuthorName) || `legacy:${index}`;
            if (!map[authorKey]) {
                map[authorKey] = COMMENT_AUTHOR_COLORS[cursor % COMMENT_AUTHOR_COLORS.length];
                cursor += 1;
            }
        });

        return map;
    }, [commentTask]);

    const getDueMeta = (dueDate) => {
        const today = new Date();
        const current = new Date(today.getFullYear(), today.getMonth(), today.getDate());
        const due = new Date(dueDate);
        const dueOnly = new Date(due.getFullYear(), due.getMonth(), due.getDate());

        const fmt = (d) => d.toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' });
        if (Number.isNaN(dueOnly.getTime())) return { label: dueDate, color: 'text.secondary', overdue: false, today: false };
        if (dueOnly.getTime() < current.getTime()) return { label: 'Overdue', color: 'error.main', overdue: true, today: false };
        if (dueOnly.getTime() === current.getTime()) return { label: 'Due Today', color: 'warning.dark', overdue: false, today: true };
        return { label: fmt(dueOnly), color: 'text.secondary', overdue: false, today: false };
    };

    const isAssignedToOthersCategory = category === 'assigned_by_me';
    const isAllTasksCategory = category === 'all_tasks';
    const assignmentColumnLabel = isAllTasksCategory
        ? 'Assigned By / To'
        : (isAssignedToOthersCategory ? 'Assigned To' : 'Assigned By');

    const getAssignmentName = (task) => {
        if (isAssignedToOthersCategory) {
            const names = getTaskAssigneeNames(task);
            return names.join(', ');
        }

        if (isAllTasksCategory) {
            const isAssignedToMe = isTaskAssignedToMe(task);
            const isAssignedByMe = isTaskAssignedByMe(task);
            if (isAssignedByMe && (!isAssignedToMe || hasAssigneeOtherThanMe(task))) {
                const names = getTaskAssigneeNames(task);
                return names.join(', ');
            }
        }

        return task.assignedBy || 'Me';
    };

    const getAssignmentText = (task) => {
        if (!isAllTasksCategory) {
            return `${assignmentColumnLabel} ${getAssignmentName(task)}`;
        }

        const isAssignedToMe = isTaskAssignedToMe(task);
        const isAssignedByMe = isTaskAssignedByMe(task);

        if (isAssignedByMe && (!isAssignedToMe || hasAssigneeOtherThanMe(task))) {
            const names = getTaskAssigneeNames(task);
            return `Assigned To ${names.join(', ')}`;
        }

        return `Assigned By ${task.assignedBy || 'Me'}`;
    };

    const getTargetUserIdForPresence = (task) => {
        if (category === 'assigned_by_me') {
            return task.assignee_id;
        }
        if (category === 'assigned_to_me') {
            return task.assigned_by_id;
        }
        // all_tasks
        const isAssignedToMe = isTaskAssignedToMe(task);
        const isAssignedByMe = isTaskAssignedByMe(task);
        if (isAssignedByMe && (!isAssignedToMe || hasAssigneeOtherThanMe(task))) {
            return task.assignee_id;
        }
        return task.assigned_by_id;
    };

    const saveTask = async (nextTask) => {
        try {
            const payload = buildTodoPayload(nextTask, nextTask.sort_order || 0);
            const updated = await updateMyDeskTodo(nextTask.id, payload);
            const mapped = mapTodoToTask(updated, { detailsLoaded: true });
            setTasks((previous) => previous.map((task) => (task.id === mapped.id ? mapped : task)));
        } catch (error) {
            console.error('Failed to save task:', error);
        }
    };

    const openTaskDetails = (task) => {
        if (!task) return;

        setSelectedTask(task);
        if (task.detailsLoaded) return;

        getMyDeskTodo(task.id, { includeAttachments: true })
            .then((item) => {
                const hydratedTask = mapTodoToTask(item, { detailsLoaded: true });
                setTasks((previous) => previous.map((entry) => (entry.id === hydratedTask.id ? hydratedTask : entry)));
                setSelectedTask((previous) => (previous?.id === hydratedTask.id ? hydratedTask : previous));
                setCommentTask((previous) => (previous?.id === hydratedTask.id ? hydratedTask : previous));
            })
            .catch(() => { });
    };

    const markTaskDone = (taskId) => {
        let updatedTask = null;
        setTasks((previous) => previous.map((task) => {
            if (task.id !== taskId) return task;
            updatedTask = { ...task, status: 'done' };
            return updatedTask;
        }));
        if (updatedTask) saveTask(updatedTask);
    };

    const deleteTask = async (taskId) => {
        const taskToDelete = tasks.find((task) => task.id === taskId);
        if (!taskToDelete || !canDeleteTask(taskToDelete)) return;

        if (!window.confirm('Delete this task? This action cannot be undone.')) {
            return;
        }

        try {
            await deleteMyDeskTodo(taskId);
            setTasks((previous) => previous.filter((task) => task.id !== taskId));
            setSelectedTask((previous) => (previous?.id === taskId ? null : previous));
            setCommentTask((previous) => (previous?.id === taskId ? null : previous));
            setCommentAnchorEl(null);
            setReminderTask((previous) => (previous?.id === taskId ? null : previous));
            setActiveReminder((previous) => (previous?.id === taskId ? null : previous));
            setHighlightTaskId((previous) => (previous === taskId ? null : previous));
            ActivityLogger.track('TASK_DELETE', 'TasksSection', location.pathname, { taskId, title: taskToDelete.title });
        } catch (error) {
            console.error('Failed to delete task:', error);
        }
    };

    const requestHelp = (taskId) => {
        if (category === 'assigned_by_me') return;
        let updatedTask = null;
        setTasks((previous) => previous.map((task) => {
            if (task.id !== taskId) return task;
            const helpComment = normalizeTaskCommentEntry({
                text: `Help requested at ${new Date().toLocaleString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}`,
                author_name: myName || 'Me',
                author_id: myId || null,
                created_at: new Date().toISOString(),
            });
            const existingComments = Array.isArray(task.comments) ? task.comments : [];
            updatedTask = {
                ...task,
                helpRequested: true,
                comments: existingComments.length > 0 ? existingComments : (helpComment ? [helpComment] : []),
            };
            return updatedTask;
        }));
        if (updatedTask) saveTask(updatedTask);
    };

    const openCommentDialog = (eventOrAnchor, task) => {
        const anchorEl = eventOrAnchor?.currentTarget
            || eventOrAnchor
            || taskCommentAnchorRefs.current[task.id]
            || document.body;
        setCommentAnchorEl(anchorEl);
        setCommentTask(task);
        setCommentDraft('');
    };

    const closeCommentDialog = () => {
        setCommentTask(null);
        setCommentAnchorEl(null);
        setCommentDraft('');
    };

    const submitComment = async () => {
        if (!commentTask || !commentDraft.trim()) return;
        const commentValue = normalizeTaskCommentEntry({
            text: commentDraft.trim(),
            author_name: myName || 'Me',
            author_id: myId || null,
            created_at: new Date().toISOString(),
        });
        if (!commentValue) return;
        let updatedTask = null;
        setTasks((previous) => previous.map((task) => {
            if (task.id !== commentTask.id) return task;
            updatedTask = {
                ...task,
                commentRequested: true,
                comments: [...(Array.isArray(task.comments) ? task.comments : []), commentValue],
            };
            return updatedTask;
        }));
        if (updatedTask) {
            await saveTask(updatedTask);
        }
        closeCommentDialog();
    };

    const openReminderDialog = (task) => {
        setReminderTask(task);
        setReminderDraft(task.reminderAt || '');
    };

    const closeReminderDialog = () => {
        setReminderTask(null);
        setReminderDraft('');
    };

    const saveReminder = async () => {
        if (!reminderTask) return;
        const value = (reminderDraft || '').trim();
        let updatedTask = null;
        setTasks((previous) => previous.map((task) => {
            if (task.id !== reminderTask.id) return task;
            updatedTask = {
                ...task,
                reminders: Boolean(value),
                reminderAt: value,
            };
            return updatedTask;
        }));
        if (updatedTask) {
            await saveTask(updatedTask);
            setShownReminders((previous) => ({ ...previous, [`${updatedTask.id}-${value}`]: false }));
        }
        closeReminderDialog();
    };

    const moveTaskToStatus = (taskId, nextStatus) => {
        let updatedTask = null;
        let changed = false;
        setTasks((previous) => previous.map((task) => {
            if (task.id !== taskId) return task;

            // Only allow moving tasks assigned to me
            const isAssignedToMe = isTaskAssignedToMe(task);

            if (!isAssignedToMe) return task;
            if (task.status === nextStatus) return task;
            changed = true;
            updatedTask = { ...task, status: nextStatus };
            return updatedTask;
        }));

        if (changed && updatedTask) {
            saveTask(updatedTask);
            setSelectedTask((previous) => {
                if (!previous || previous.id !== taskId) return previous;
                return { ...previous, status: nextStatus };
            });
        }
    };

    const handleColumnDrop = (nextStatus) => {
        if (!draggingTaskId) return;
        if (category !== 'assigned_to_me') return;
        moveTaskToStatus(draggingTaskId, nextStatus);
        setDraggingTaskId(null);
    };

    useEffect(() => {
        const intervalId = setInterval(() => {
            const now = Date.now();
            const dueTask = tasks.find((task) => {
                if (!task.reminders || !task.reminderAt) return false;
                const dueAt = new Date(task.reminderAt).getTime();
                if (Number.isNaN(dueAt) || dueAt > now) return false;
                return !shownReminders[`${task.id}-${task.reminderAt}`];
            });

            if (dueTask) {
                setActiveReminder(dueTask);
                setShownReminders((previous) => ({ ...previous, [`${dueTask.id}-${dueTask.reminderAt}`]: true }));
            }
        }, 15000);

        return () => clearInterval(intervalId);
    }, [tasks, shownReminders]);

    const reminderActionLabel = category === 'assigned_by_me' ? 'Remind Person' : 'Set Reminder';

    const deleteTaskAttachment = async (taskId, attachmentId) => {
        try {
            await deleteMyDeskTodoAttachment(attachmentId);
            setTasks((previous) => previous.map((task) => {
                if (task.id !== taskId) return task;
                return {
                    ...task,
                    taskAttachments: (task.taskAttachments || []).filter((item) => item.id !== attachmentId),
                };
            }));
            setSelectedTask((previous) => {
                if (!previous || previous.id !== taskId) return previous;
                return {
                    ...previous,
                    taskAttachments: (previous.taskAttachments || []).filter((item) => item.id !== attachmentId),
                };
            });
        } catch (error) {
            console.error('Failed to delete attachment:', error);
        }
    };

    const previewText = (text, max = 90) => {
        const value = (text || '').trim();
        if (!value) return '';
        if (value.length <= max) return value;
        return `${value.slice(0, max)}...`;
    };

    useEffect(() => {
        const params = new URLSearchParams(location.search || '');
        const taskId = (params.get('taskId') || '').trim();
        if (!taskId) return;

        const commentId = (params.get('commentId') || '').trim();
        const deepLinkKey = `${taskId}|${commentId}`;
        if (handledDeepLinkRef.current === deepLinkKey) return;

        const targetTask = tasks.find((task) => String(task.id) === String(taskId));
        if (!targetTask) return;

        handledDeepLinkRef.current = deepLinkKey;
        openTaskDetails(targetTask);
        setHighlightTaskId(targetTask.id);

        window.setTimeout(() => {
            taskRowRefs.current[targetTask.id]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 150);
        window.setTimeout(() => setHighlightTaskId(null), 5000);

        if (commentId) {
            const segments = String(commentId).split(':');
            const candidate = Number(segments.length > 1 ? segments[segments.length - 1] : commentId);
            const parsedIndex = Number.isFinite(candidate) ? Math.max(0, candidate - 1) : -1;
            if (parsedIndex >= 0) {
                setHighlightCommentIndex(parsedIndex);
                openCommentDialog(taskCommentAnchorRefs.current[targetTask.id], targetTask);
                window.setTimeout(() => setHighlightCommentIndex(-1), 5000);
            }
        }
    }, [location.search, tasks]);

    return (
        <Stack spacing={2}>
            <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                <Box
                    sx={{
                        display: 'grid',
                        gridTemplateColumns: { xs: '1fr', lg: '1fr 260px' },
                        gap: 0.75,
                        alignItems: 'center',
                    }}
                >
                    <TextField
                        size="small"
                        placeholder="Task title..."
                        value={form.title}
                        onChange={(event) => setForm({ ...form, title: event.target.value })}
                        fullWidth
                    />
                    <FormControl size="small" fullWidth>
                        <InputLabel>Assign To</InputLabel>
                        <Select
                            multiple
                            label="Assign To"
                            value={Array.isArray(form.assignee) ? form.assignee : ['me']}
                            onChange={(event) => {
                                const rawValue = event.target.value;
                                const nextValues = Array.isArray(rawValue)
                                    ? rawValue.map((value) => String(value)).filter(Boolean)
                                    : String(rawValue).split(',').map((value) => value.trim()).filter(Boolean);

                                const uniqueValues = nextValues.filter((value, index, array) => index === array.indexOf(value));

                                setForm((previous) => ({
                                    ...previous,
                                    assignee: uniqueValues.length > 0 ? uniqueValues : ['me'],
                                }));
                            }}
                            renderValue={(selected) => {
                                const selectedValues = Array.isArray(selected) ? selected : [];
                                const labels = selectedValues.map((value) => {
                                    if (value === 'me') return 'Me';
                                    const member = normalizedMembers.find((item) => item.id === String(value));
                                    return member?.label || value;
                                }).filter(Boolean);
                                return labels.join(', ');
                            }}
                        >
                            <MenuItem value="me">
                                <Checkbox size="small" checked={(Array.isArray(form.assignee) ? form.assignee : ['me']).includes('me')} />
                                <ListItemText primary="Me" />
                            </MenuItem>
                            {assignableMembers.map((member) => (
                                <MenuItem key={member.id} value={member.id}>
                                    <Checkbox size="small" checked={(Array.isArray(form.assignee) ? form.assignee : ['me']).includes(member.id)} />
                                    <ListItemText primary={member.label} />
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </Box>

                <Stack spacing={0.75} sx={{ mt: 0.9 }}>
                    <TextField
                        size="small"
                        placeholder="Task details / description..."
                        value={form.comment}
                        onChange={(event) => setForm({ ...form, comment: event.target.value })}
                        multiline
                        minRows={2}
                        maxRows={10}
                        fullWidth
                    />
                    <Stack direction={{ xs: 'column', lg: 'row' }} spacing={0.75} alignItems={{ xs: 'stretch', lg: 'center' }} sx={{ width: '100%' }}>
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={0.75} sx={{ flex: 1, flexWrap: 'wrap' }}>
                            <TextField
                                type="date"
                                size="small"
                                label="Due"
                                InputLabelProps={{ shrink: true }}
                                value={form.dueDate}
                                onChange={(event) => setForm({ ...form, dueDate: event.target.value })}
                                sx={{ minWidth: 148 }}
                            />
                            <TextField
                                type="time"
                                size="small"
                                label="Time"
                                InputLabelProps={{ shrink: true }}
                                value={form.dueTime}
                                onChange={(event) => setForm({ ...form, dueTime: event.target.value })}
                                sx={{ minWidth: 122 }}
                            />
                            <FormControl size="small" sx={{ minWidth: 116 }}>
                                <InputLabel>Priority</InputLabel>
                                <Select label="Priority" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })}>
                                    <MenuItem value="critical">Critical</MenuItem>
                                    <MenuItem value="high">High</MenuItem>
                                    <MenuItem value="medium">Medium</MenuItem>
                                    <MenuItem value="low">Low</MenuItem>
                                </Select>
                            </FormControl>
                            <FormControl size="small" sx={{ minWidth: 116 }}>
                                <InputLabel>Status</InputLabel>
                                <Select label="Status" value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value })}>
                                    <MenuItem value="todo">To Do</MenuItem>
                                    <MenuItem value="in_progress">In Progress</MenuItem>
                                    <MenuItem value="done">Done</MenuItem>
                                </Select>
                            </FormControl>
                            <Button component="label" variant="outlined" startIcon={<AttachFileIcon />}>
                                Attach
                                <input hidden multiple type="file" accept={TASK_ATTACHMENT_ACCEPT} onChange={addPendingAttachments} />
                            </Button>
                        </Stack>
                        <Stack direction="row" spacing={0.75} sx={{ ml: { lg: 'auto' }, justifyContent: { xs: 'flex-start', lg: 'flex-end' } }}>
                            <Button
                                variant="contained"
                                size="large"
                                onClick={addTask}
                                startIcon={editingTaskId ? <CheckIcon /> : <AddIcon />}
                                disabled={!form.title.trim()}
                                sx={{ whiteSpace: 'nowrap', minWidth: 138, px: 1.5 }}
                            >
                                {editingTaskId ? 'SAVE TASK' : 'ASSIGN TASK'}
                            </Button>
                            {editingTaskId && (
                                <Button variant="text" color="inherit" onClick={resetTaskForm}>
                                    Cancel
                                </Button>
                            )}
                        </Stack>
                    </Stack>
                </Stack>

                {Array.isArray(form.attachments) && form.attachments.length > 0 && (
                    <Stack direction="row" spacing={0.75} sx={{ mt: 0.9 }} flexWrap="wrap" useFlexGap>
                        {form.attachments.map((file) => (
                            <Chip
                                key={`${file.name}-${file.size}-${file.lastModified}`}
                                label={file.name}
                                onDelete={() => removePendingAttachment(file)}
                                size="small"
                                variant="outlined"
                            />
                        ))}
                    </Stack>
                )}
            </Paper>

            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} justifyContent="space-between" alignItems={{ xs: 'stretch', md: 'center' }}>
                    <Tabs value={view} onChange={(_, value) => setView(value)}>
                        <Tab icon={<ViewKanbanIcon fontSize="small" />} iconPosition="start" value="kanban" label="Kanban" />
                        <Tab icon={<ViewListIcon fontSize="small" />} iconPosition="start" value="list" label="List" />
                    </Tabs>

                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        {visibleCategoryPills.map((pill) => (
                            <Chip
                                key={pill.id}
                                clickable
                                color={category === pill.id ? pill.color : 'default'}
                                variant={category === pill.id ? 'filled' : 'outlined'}
                                label={`${pill.label}  ${counts[pill.id] || 0}`}
                                onClick={() => setCategory(pill.id)}
                            />
                        ))}
                    </Stack>
                </Stack>

                {view === 'kanban' && (
                    <Box sx={{ mt: 2, display: 'grid', gridTemplateColumns: { xs: '1fr', lg: 'repeat(3, 1fr)' }, gap: 1.5 }}>
                        {Object.keys(statusMeta).map((status) => {
                            const columnTasks = categoryFiltered.filter((task) => task.status === status);
                            return (
                                <Paper
                                    key={status}
                                    variant="outlined"
                                    onDragOver={(event) => {
                                        if (category === 'assigned_to_me') event.preventDefault();
                                    }}
                                    onDrop={() => handleColumnDrop(status)}
                                    sx={{
                                        minHeight: 320,
                                        borderRadius: 2,
                                        borderTopWidth: 4,
                                        borderTopStyle: 'solid',
                                        borderTopColor: `${statusMeta[status].color}.main`,
                                    }}
                                >
                                    <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ px: 1.25, py: 1, borderBottom: 1, borderColor: 'divider' }}>
                                        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>{statusMeta[status].label}</Typography>
                                        <Chip size="small" label={columnTasks.length} color={statusMeta[status].color} variant="outlined" />
                                    </Stack>
                                    <Box sx={{ p: 1.25 }}>
                                        {columnTasks.length === 0 ? (
                                            <Stack alignItems="center" justifyContent="center" sx={{ minHeight: 220 }}>
                                                <Typography variant="body2" color="text.secondary">{statusMeta[status].empty}</Typography>
                                            </Stack>
                                        ) : (
                                            <Stack spacing={1}>
                                                {columnTasks.map((task) => (
                                                    <Paper
                                                        key={task.id}
                                                        ref={(element) => {
                                                            if (element) taskRowRefs.current[task.id] = element;
                                                            else delete taskRowRefs.current[task.id];
                                                        }}
                                                        variant="outlined"
                                                        draggable={category === 'assigned_to_me'}
                                                        onDragStart={() => {
                                                            if (category !== 'assigned_to_me') return;
                                                            setDraggingTaskId(task.id);
                                                        }}
                                                        onDragEnd={() => setDraggingTaskId(null)}
                                                        sx={{
                                                            p: 1.25,
                                                            borderRadius: 1.5,
                                                            cursor: category === 'assigned_to_me' ? 'grab' : 'default',
                                                            borderColor: highlightTaskId === task.id ? 'primary.main' : 'divider',
                                                            boxShadow: highlightTaskId === task.id ? '0 0 0 2px rgba(25,118,210,0.16)' : 'none',
                                                            transition: 'box-shadow 0.2s ease, border-color 0.2s ease',
                                                        }}
                                                    >
                                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                                            <Typography
                                                                variant="subtitle2"
                                                                sx={{ fontWeight: 700, cursor: 'pointer' }}
                                                                onClick={() => openTaskDetails(task)}
                                                            >
                                                                {previewText(task.title || '(No title)', 48)}
                                                            </Typography>
                                                            <Chip
                                                                size="small"
                                                                label={task.priority || 'medium'}
                                                                sx={{
                                                                    height: 22,
                                                                    textTransform: 'lowercase',
                                                                    fontWeight: 600,
                                                                    ...priorityPillSx[task.priority] || priorityPillSx.medium,
                                                                }}
                                                            />
                                                        </Stack>
                                                        <Typography variant="caption" color="text.secondary">
                                                            Due {task.dueDate ? new Date(`${task.dueDate}T00:00:00`).toLocaleDateString('en-GB') : ''}{task.dueTime ? ` ${task.dueTime}` : ''}
                                                        </Typography>
                                                        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.25 }}>
                                                            <Typography variant="caption" color="text.secondary">
                                                                {getAssignmentText(task)}
                                                            </Typography>
                                                            {getTargetUserIdForPresence(task) && (
                                                                <PresenceBadge userId={getTargetUserIdForPresence(task)} size="small" />
                                                            )}
                                                        </Stack>
                                                        {task.description && (
                                                            <Typography
                                                                variant="body2"
                                                                sx={{ mt: 0.75, cursor: 'pointer' }}
                                                                color="text.secondary"
                                                                onClick={() => openTaskDetails(task)}
                                                            >
                                                                {previewText(task.description, 110)}
                                                            </Typography>
                                                        )}
                                                        <Stack direction="row" spacing={0.5} sx={{ mt: 1 }}>
                                                            <Tooltip title={reminderActionLabel}>
                                                                <IconButton size="small" color={task.reminders ? 'warning' : 'default'} onClick={() => openReminderDialog(task)}>
                                                                    <NotificationsActiveIcon fontSize="small" />
                                                                </IconButton>
                                                            </Tooltip>
                                                            <Tooltip title="Seek Help">
                                                                <span>
                                                                    <IconButton
                                                                        size="small"
                                                                        color={task.helpRequested ? 'secondary' : 'default'}
                                                                        onClick={() => requestHelp(task.id)}
                                                                        disabled={category === 'assigned_by_me'}
                                                                    >
                                                                        <HelpOutlineIcon fontSize="small" />
                                                                    </IconButton>
                                                                </span>
                                                            </Tooltip>
                                                            <Tooltip title="Comments">
                                                                <span>
                                                                    <IconButton
                                                                        ref={(element) => {
                                                                            if (element) taskCommentAnchorRefs.current[task.id] = element;
                                                                            else delete taskCommentAnchorRefs.current[task.id];
                                                                        }}
                                                                        size="small"
                                                                        color={task.commentRequested ? 'info' : 'default'}
                                                                        onClick={(event) => openCommentDialog(event, task)}
                                                                    >
                                                                        <ChatBubbleOutlineIcon fontSize="small" />
                                                                    </IconButton>
                                                                </span>
                                                            </Tooltip>
                                                            <Tooltip title="Mark Done">
                                                                <IconButton size="small" color={task.status === 'done' ? 'success' : 'default'} onClick={() => markTaskDone(task.id)}>
                                                                    <CheckIcon fontSize="small" />
                                                                </IconButton>
                                                            </Tooltip>
                                                            {canDeleteTask(task) && (
                                                                <Tooltip title="Delete Task">
                                                                    <IconButton size="small" color="error" onClick={() => deleteTask(task.id)}>
                                                                        <DeleteOutlineIcon fontSize="small" />
                                                                    </IconButton>
                                                                </Tooltip>
                                                            )}
                                                        </Stack>
                                                    </Paper>
                                                ))}
                                            </Stack>
                                        )}
                                    </Box>
                                </Paper>
                            );
                        })}
                    </Box>
                )}

                {view === 'list' && (
                    <Stack sx={{ mt: 1.25 }}>
                        <Box
                            sx={{
                                display: 'grid',
                                gridTemplateColumns: '2fr 0.75fr 0.75fr 0.75fr 1.5fr 1fr',
                                columnGap: 1,
                                px: 2,
                                py: 1,
                                borderBottom: 1,
                                borderColor: 'divider',
                                bgcolor: 'action.hover',
                            }}
                        >
                            <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>Task</Typography>
                            <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>Priority</Typography>
                            <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>Status</Typography>
                            <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>Due</Typography>
                            <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>{assignmentColumnLabel}</Typography>
                            <Typography variant="caption" sx={{ fontWeight: 700, color: 'text.secondary', textTransform: 'uppercase' }}>Actions</Typography>
                        </Box>

                        {categoryFiltered.length === 0 ? (
                            <List>
                                <ListItem>
                                    <ListItemText primary="No tasks found" />
                                </ListItem>
                            </List>
                        ) : (
                            categoryFiltered.map((task) => {
                                const due = getDueMeta(task.dueDate);
                                return (
                                    <Box
                                        key={task.id}
                                        ref={(element) => {
                                            if (element) taskRowRefs.current[task.id] = element;
                                            else delete taskRowRefs.current[task.id];
                                        }}
                                        sx={{
                                            display: 'grid',
                                            gridTemplateColumns: '2fr 0.75fr 0.75fr 0.75fr 1.5fr 1fr',
                                            columnGap: 1,
                                            alignItems: 'center',
                                            px: 2,
                                            py: 1.4,
                                            borderBottom: 1,
                                            borderColor: 'divider',
                                            bgcolor: highlightTaskId === task.id ? (theme) => alpha(theme.palette.primary.main, 0.08) : 'transparent',
                                            transition: 'background-color 0.2s ease',
                                        }}
                                    >
                                        <Typography
                                            variant="subtitle2"
                                            sx={{ fontWeight: 700, cursor: 'pointer' }}
                                            onClick={() => openTaskDetails(task)}
                                        >
                                            {previewText(task.title || '(No title)', 60)}
                                        </Typography>

                                        <Chip
                                            size="small"
                                            label={task.priority || 'medium'}
                                            sx={{
                                                height: 22,
                                                width: 'fit-content',
                                                textTransform: 'lowercase',
                                                fontWeight: 600,
                                                ...(priorityPillSx[task.priority] || priorityPillSx.medium),
                                            }}
                                        />

                                        <Stack direction="row" spacing={0.5} alignItems="center">
                                            <CheckIcon fontSize="small" color="success" />
                                            <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>{task.status.replace('_', ' ')}</Typography>
                                        </Stack>

                                        <Stack direction="row" spacing={0.5} alignItems="center">
                                            {due.overdue && <WarningAmberIcon fontSize="small" color="error" />}
                                            <Typography variant="body2" sx={{ color: due.color, fontWeight: due.overdue || due.today ? 700 : 400 }}>{due.label}</Typography>
                                        </Stack>

                                        <Stack direction="row" spacing={1} alignItems="center">
                                            {getTargetUserIdForPresence(task) ? (
                                                <PresenceBadge userId={getTargetUserIdForPresence(task)}>
                                                    <Box
                                                        sx={{
                                                            width: 24,
                                                            height: 24,
                                                            borderRadius: '50%',
                                                            display: 'grid',
                                                            placeItems: 'center',
                                                            color: 'common.white',
                                                            fontSize: 11,
                                                            fontWeight: 700,
                                                            bgcolor: assigneeBadgeColor(getAssignmentName(task)),
                                                        }}
                                                    >
                                                        {assigneeInitials(getAssignmentName(task))}
                                                    </Box>
                                                </PresenceBadge>
                                            ) : (
                                                <Box
                                                    sx={{
                                                        width: 24,
                                                        height: 24,
                                                        borderRadius: '50%',
                                                        display: 'grid',
                                                        placeItems: 'center',
                                                        color: 'common.white',
                                                        fontSize: 11,
                                                        fontWeight: 700,
                                                        bgcolor: assigneeBadgeColor(getAssignmentName(task)),
                                                    }}
                                                >
                                                    {assigneeInitials(getAssignmentName(task))}
                                                </Box>
                                            )}
                                            <Typography variant="body2" sx={{ fontWeight: 500 }}>{getAssignmentName(task)}</Typography>
                                        </Stack>

                                        <Stack direction="row" spacing={0.5}>
                                            <Tooltip title={reminderActionLabel}>
                                                <IconButton size="small" color={task.reminders ? 'warning' : 'default'} onClick={() => openReminderDialog(task)}>
                                                    <NotificationsActiveIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                            <Tooltip title="Seek Help">
                                                <span>
                                                    <IconButton
                                                        size="small"
                                                        color={task.helpRequested ? 'secondary' : 'default'}
                                                        onClick={() => requestHelp(task.id)}
                                                        disabled={category === 'assigned_by_me'}
                                                    >
                                                        <HelpOutlineIcon fontSize="small" />
                                                    </IconButton>
                                                </span>
                                            </Tooltip>
                                            <Tooltip title="Comments">
                                                <span>
                                                    <IconButton
                                                        ref={(element) => {
                                                            if (element) taskCommentAnchorRefs.current[task.id] = element;
                                                            else delete taskCommentAnchorRefs.current[task.id];
                                                        }}
                                                        size="small"
                                                        color={task.commentRequested ? 'info' : 'default'}
                                                        onClick={(event) => openCommentDialog(event, task)}
                                                    >
                                                        <ChatBubbleOutlineIcon fontSize="small" />
                                                    </IconButton>
                                                </span>
                                            </Tooltip>
                                            <Tooltip title="Mark Done">
                                                <IconButton size="small" color={task.status === 'done' ? 'success' : 'default'} onClick={() => markTaskDone(task.id)}>
                                                    <CheckIcon fontSize="small" />
                                                </IconButton>
                                            </Tooltip>
                                            {canDeleteTask(task) && (
                                                <Tooltip title="Delete Task">
                                                    <IconButton size="small" color="error" onClick={() => deleteTask(task.id)}>
                                                        <DeleteOutlineIcon fontSize="small" />
                                                    </IconButton>
                                                </Tooltip>
                                            )}
                                        </Stack>
                                    </Box>
                                );
                            })
                        )}
                    </Stack>
                )}

            </Paper>

            <Dialog open={Boolean(selectedTask)} onClose={() => setSelectedTask(null)} maxWidth="sm" fullWidth>
                <DialogTitle>{selectedTask?.title || 'Task'}</DialogTitle>
                <DialogContent>
                    <Stack spacing={1.25}>
                        {selectedTask?.description && (
                            <Typography variant="body2" color="text.secondary">{selectedTask.description}</Typography>
                        )}
                        <Button
                            variant="outlined"
                            size="small"
                            startIcon={<ChatBubbleOutlineIcon />}
                            onClick={(event) => selectedTask && openCommentDialog(event, selectedTask)}
                            sx={{ width: 'fit-content' }}
                        >
                            Comments ({Array.isArray(selectedTask?.comments) ? selectedTask.comments.length : 0})
                        </Button>
                        {selectedTask?.attachmentUrl && (
                            <Button variant="outlined" size="small" component="a" href={selectedTask.attachmentUrl} target="_blank" rel="noreferrer">Open attachment</Button>
                        )}
                        {Array.isArray(selectedTask?.taskAttachments) && selectedTask.taskAttachments.length > 0 && (
                            <Stack spacing={0.5}>
                                <Typography variant="subtitle2">Attachments</Typography>
                                {selectedTask.taskAttachments.map((attachment) => (
                                    <Stack key={attachment.id} direction="row" spacing={0.75} alignItems="center" justifyContent="space-between">
                                        <Button
                                            variant="outlined"
                                            size="small"
                                            component="a"
                                            href={attachment.file_url}
                                            target="_blank"
                                            rel="noreferrer"
                                            sx={{ textTransform: 'none', justifyContent: 'flex-start' }}
                                        >
                                            {attachment.original_name || attachment.file_url?.split('/').pop() || 'Attachment'}
                                        </Button>
                                        <IconButton size="small" color="error" onClick={() => deleteTaskAttachment(selectedTask.id, attachment.id)}>
                                            <DeleteOutlineIcon fontSize="small" />
                                        </IconButton>
                                    </Stack>
                                ))}
                            </Stack>
                        )}
                        <Stack direction="row" spacing={0.5} alignItems="center" sx={{ mt: 0.5 }}>
                            <Typography variant="caption" color="text.secondary">
                                Due {selectedTask?.dueDate ? new Date(`${selectedTask.dueDate}T00:00:00`).toLocaleDateString('en-GB') : '-'}{selectedTask?.dueTime ? ` ${selectedTask.dueTime}` : ''}
                                <br />
                                {selectedTask ? getAssignmentText(selectedTask) : 'Assigned'} • {(selectedTask?.status || 'todo').replace('_', ' ')}
                            </Typography>
                            {selectedTask && getTargetUserIdForPresence(selectedTask) && (
                                <PresenceBadge userId={getTargetUserIdForPresence(selectedTask)} size="small" />
                            )}
                        </Stack>
                    </Stack>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setSelectedTask(null)}>Close</Button>
                    {selectedTask && canEditTask(selectedTask) && (
                        <Button onClick={() => openTaskForEdit(selectedTask)} startIcon={<EditIcon />}>
                            Edit Task
                        </Button>
                    )}
                    {selectedTask && canDeleteTask(selectedTask) && (
                        <Button color="error" onClick={() => deleteTask(selectedTask.id)} startIcon={<DeleteOutlineIcon />}>
                            Delete Task
                        </Button>
                    )}
                </DialogActions>
            </Dialog>

            <Popover
                open={Boolean(commentTask)}
                anchorEl={commentAnchorEl}
                onClose={closeCommentDialog}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                transformOrigin={{ vertical: 'top', horizontal: 'center' }}
                slotProps={{
                    paper: {
                        sx: {
                            width: 280,
                            maxHeight: 350,
                            display: 'flex',
                            flexDirection: 'column',
                            borderRadius: 2,
                            boxShadow: 6,
                        },
                    },
                }}
            >
                <Box sx={{ p: 1.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Typography variant="subtitle2" fontWeight={700}>💬 Comments ({Array.isArray(commentTask?.comments) ? commentTask.comments.length : 0})</Typography>
                    <IconButton size="small" onClick={closeCommentDialog}>
                        <CloseIcon sx={{ fontSize: 16 }} />
                    </IconButton>
                </Box>

                <Box sx={{ flex: 1, overflowY: 'auto', px: 1 }}>
                    {Array.isArray(commentTask?.comments) && commentTask.comments.length > 0 ? (
                        <List dense disablePadding>
                            {commentTask.comments.map((comment, index) => {
                                const commentText = getTaskCommentText(comment);
                                const authorName = getTaskCommentAuthorName(comment) || commentTask?.assignedBy || 'Member';
                                const authorKey = getTaskCommentAuthorKey(comment, authorName) || `legacy:${index}`;
                                const authorColor = commentAuthorColorMap[authorKey] || assigneeBadgeColor(authorName);
                                return (
                                    <ListItem
                                        key={`${commentTask.id}-comment-panel-${index}`}
                                        alignItems="flex-start"
                                        disablePadding
                                        sx={{
                                            py: 0.5,
                                            px: 0.5,
                                            borderRadius: 1,
                                            bgcolor: commentTask?.id === highlightTaskId && index === highlightCommentIndex
                                                ? 'rgba(25,118,210,0.12)'
                                                : 'transparent',
                                        }}
                                    >
                                        <ListItemAvatar sx={{ minWidth: 32 }}>
                                            <Avatar
                                                sx={{
                                                    width: 24,
                                                    height: 24,
                                                    fontSize: 12,
                                                    bgcolor: authorColor,
                                                }}
                                            >
                                                {assigneeInitials(authorName)}
                                            </Avatar>
                                        </ListItemAvatar>
                                        <Box sx={{ flex: 1, minWidth: 0 }}>
                                            <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', fontWeight: 600 }}>
                                                {authorName}
                                            </Typography>
                                            <Typography variant="body2" sx={{ fontSize: 12, wordBreak: 'break-word' }}>{commentText}</Typography>
                                        </Box>
                                    </ListItem>
                                );
                            })}
                        </List>
                    ) : (
                        <Typography variant="caption" sx={{ p: 2, display: 'block', textAlign: 'center', color: 'text.secondary' }}>
                            No comments yet. Start the conversation!
                        </Typography>
                    )}
                </Box>

                <Box sx={{ p: 1, borderTop: '1px solid', borderColor: 'divider', display: 'flex', gap: 0.5, alignItems: 'center' }}>
                    <TextField
                        autoFocus
                        fullWidth
                        size="small"
                        placeholder="Type @ to mention..."
                        value={commentDraft}
                        onChange={(event) => setCommentDraft(event.target.value)}
                        onKeyDown={(event) => {
                            if (event.key === 'Enter' && !event.shiftKey) {
                                event.preventDefault();
                                submitComment();
                            }
                        }}
                        sx={{ '& .MuiInputBase-root': { fontSize: 12, borderRadius: 2 } }}
                    />
                    <IconButton size="small" color="primary" onClick={submitComment} disabled={!commentDraft.trim()}>
                        <SendIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                </Box>
            </Popover>

            <Dialog open={Boolean(reminderTask)} onClose={closeReminderDialog} maxWidth="xs" fullWidth>
                <DialogTitle>Set Reminder</DialogTitle>
                <DialogContent>
                    <TextField
                        autoFocus
                        margin="dense"
                        type="datetime-local"
                        fullWidth
                        label="Reminder date & time"
                        InputLabelProps={{ shrink: true }}
                        value={reminderDraft}
                        onChange={(event) => setReminderDraft(event.target.value)}
                    />
                </DialogContent>
                <DialogActions>
                    <Button onClick={closeReminderDialog}>Cancel</Button>
                    <Button variant="contained" onClick={saveReminder}>Save</Button>
                </DialogActions>
            </Dialog>

            <Snackbar
                open={Boolean(activeReminder)}
                autoHideDuration={7000}
                onClose={() => setActiveReminder(null)}
                anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
                <Alert onClose={() => setActiveReminder(null)} severity="info" variant="filled" sx={{ width: '100%' }}>
                    Reminder: {activeReminder?.title || 'Task'}
                </Alert>
            </Snackbar>
        </Stack>
    );
}
