import {
    StickyNote2 as NotesIcon,
    TaskAlt as TasksIcon,
    Forum as ChatsIcon,
    Analytics as AnalyticsIcon,
    Person as ProfileIcon,
    Payments as ExpensesIcon,
    BeachAccess as LeaveIcon,
    FactCheck as AttendanceIcon,
    RequestQuote as PayrollIcon,
    PhotoLibrary as GalleryIcon,
    Description as LogsIcon,
    MenuBook as LogbookIcon,
    VideoCall as MeetingsIcon,
    School as SchoolIcon,
    Email as EmailIcon,
} from '@mui/icons-material';

export const MYDESK_NAV_ITEMS = [
    { id: 'my-notes', label: 'My Notes', icon: NotesIcon, path: 'notes' },
    { id: 'my-tasks', label: 'Task Manager', icon: TasksIcon, path: 'tasks' },
    { id: 'my-chats', label: 'My Chats', icon: ChatsIcon, path: 'chats' },
    { id: 'my-analytics', label: 'My Analytics', icon: AnalyticsIcon, path: 'analytics' },
    { id: 'my-profile', label: 'My Profile', icon: ProfileIcon, path: 'profile', inactive: true },
    { id: 'expenses', label: 'Expenses', icon: ExpensesIcon, path: 'expenses' },
    { id: 'my-attendance', label: 'My Attendance', icon: AttendanceIcon, path: 'attendance' },
    { id: 'my-payroll', label: 'My Payroll', icon: PayrollIcon, path: 'payroll' },
    { id: 'leave-requests', label: 'Leave Requests', icon: LeaveIcon, path: 'leave' },
    { id: 'gallery', label: 'My Vault', icon: GalleryIcon, path: 'vault' },
    { id: 'logs', label: 'Logs', icon: LogsIcon, path: 'logs' },
    { id: 'logbook', label: 'My Diary', icon: LogbookIcon, path: 'diary' },
    { id: 'my-meetings',  label: 'My Meetings',  icon: MeetingsIcon, path: 'meetings' },
    { id: 'training-hub', label: 'Training Hub',  icon: SchoolIcon,   path: 'training' },
    { id: 'my-email',     label: 'My Email',      icon: EmailIcon,    path: 'email'    },
];

/** Map URL path segment → nav item id */
export const MYDESK_PATH_TO_ID = Object.fromEntries(
    MYDESK_NAV_ITEMS.map((item) => [item.path, item.id])
);

/** Map nav item id → URL path segment */
export const MYDESK_ID_TO_PATH = Object.fromEntries(
    MYDESK_NAV_ITEMS.map((item) => [item.id, item.path])
);

export const MYDESK_SECTION_CONTENT = {
    'my-notes': {
        title: 'My Notes',
        subtitle: 'Personal knowledge space with rich editing and quick capture.',
        groups: [
            {
                title: 'Core',
                items: [
                    'Rich text editor support: bold, lists, highlights',
                    'Quick-create floating action button',
                    'Attach photos, videos, and files',
                    'Google Drive attachment support',
                ],
            },
            {
                title: 'Organization',
                items: [
                    'Tags and labels for note grouping',
                    'Pin important notes',
                    'Search and filter notes quickly',
                    'Auto-save drafts with version history',
                ],
            },
        ],
    },
    'my-tasks': {
        title: 'My Tasks',
        subtitle: 'Track execution across views, priorities, and collaborations.',
        groups: [
            {
                title: 'Views & Categories',
                items: [
                    'Views: Kanban, List, Calendar',
                    'Categories: Personal To-Do, Assigned to Others, Overdue, Completed',
                    'Priority levels: Critical, High, Medium, Low',
                ],
            },
            {
                title: 'Execution',
                items: [
                    'Consult/help threads with colleague tagging',
                    'Escalation path for blocked tasks',
                    'Due dates, reminders, subtasks, and attachments',
                ],
            },
        ],
    },
    'my-chats': {
        title: 'My Chats',
        subtitle: 'Continue conversations with your team in real time.',
        groups: [
            {
                title: 'Chat',
                items: [
                    'Same Team Chat experience as Quick Action',
                    'Messages stay synced across all chat entry points',
                    'Supports direct, group, and broadcast conversations',
                ],
            },
        ],
    },
    'my-analytics': {
        title: 'My Analytics',
        subtitle: 'Personal productivity snapshots powered by work signals.',
        groups: [
            {
                title: 'Insights',
                items: [
                    'Productivity score (completed vs created this week)',
                    'Time-on-task heatmap (most productive periods)',
                    'Task completion trend over 30/60/90 days',
                    'Notes created per week',
                ],
            },
            {
                title: 'Personal Ops',
                items: [
                    'Leave utilization: taken vs balance',
                    'Expense summary: monthly spend trend',
                ],
            },
        ],
    },
    'my-profile': {
        title: 'My Profile',
        subtitle: 'Quick access to your role profile and identity context.',
        groups: [
            {
                title: 'Profile',
                items: [
                    'View current profile details',
                    'Quick-edit shortcut',
                    'Role, team, manager, and joining date',
                    'Google Workspace avatar sync',
                ],
            },
        ],
    },
    expenses: {
        title: 'Expenses',
        subtitle: 'Track spending and approvals with receipts and exports.',
        groups: [
            {
                title: 'Expense Flow',
                items: [
                    'Log categories: travel, food, equipment, misc',
                    'Upload receipt photo or PDF',
                    'Status flow: Draft → Submitted → Approved/Rejected',
                    'Monthly budget vs spent visualization',
                    'Export to PDF/CSV',
                ],
            },
        ],
    },
    'leave-requests': {
        title: 'Leave Requests',
        subtitle: 'Apply, track, and sync leave lifecycle in one place.',
        groups: [
            {
                title: 'Leave Management',
                items: [
                    'Apply: casual, sick, earned, WFH',
                    'Leave balance by leave type',
                    'History with pending/approved/rejected status',
                    'Google Calendar sync after approval',
                    'Manager approval flow',
                ],
            },
        ],
    },
    'my-attendance': {
        title: 'My Attendance',
        subtitle: 'Mark attendance daily and track your monthly records.',
        groups: [
            {
                title: 'Attendance Flow',
                items: [
                    'Mark today as present, half-day, WFH, on-duty, leave, or absent',
                    'Submit regularization with reason and timing details',
                    'See your latest status, timings, and regularization notes',
                ],
            },
        ],
    },
    'my-payroll': {
        title: 'My Payroll',
        subtitle: 'View salary, payslips, tax declarations, and CTC structure.',
        groups: [
            {
                title: 'Payroll Workspace',
                items: [
                    'Detailed monthly payslip with earnings and deductions',
                    'Financial year salary history with month-wise PDF download',
                    'Tax regime selection and 80C declaration with proof upload',
                    'CTC component split with taxability visibility',
                ],
            },
        ],
    },
    gallery: {
        title: 'My Vault',
        subtitle: 'Personal storage for files, images, sharing, and favorites.',
        groups: [
            {
                title: 'Media & Integration',
                items: [
                    'Manual upload for photos/videos/files',
                    'Album creation and vault-style organization',
                    'Auto-sync sent files from My Chats to Vault',
                    'Save received files from conversations to Vault on-demand',
                    'Attach files from My Vault directly in chats',
                    'Mark favorites and reference images',
                    'Secure open/download for restricted files',
                ],
            },
        ],
    },
    logs: {
        title: 'Logs',
        subtitle: 'Auto-captured activity stream for traceability.',
        groups: [
            {
                title: 'Audit Trail',
                items: [
                    'Auto-capture: logins and task status changes',
                    'Track note creation and file uploads',
                    'Filters by date and action type',
                    'Export-ready for audits',
                ],
            },
        ],
    },
    logbook: {
        title: 'My Diary',
        subtitle: 'Manual daily/weekly work diary and reporting view.',
        groups: [
            {
                title: 'Work Journal',
                items: [
                    'Daily/weekly entries: what I worked on today',
                    'Rich text editor with standup and EOD templates',
                    'Shareable report for manager',
                    'Google Docs export support',
                ],
            },
        ],
    },
    'my-meetings': {
        title: 'My Meetings',
        subtitle: 'Track upcoming meetings and join with one click.',
        groups: [
            {
                title: 'Meetings',
                items: [
                    'View scheduled meeting title, details, and timing',
                    'Join meeting directly from list',
                    'Create and save new meetings from this section',
                ],
            },
        ],
    },
    'training-hub': {
        title: 'Training Hub',
        subtitle: 'Access and complete assigned training materials, SOPs, and compliance modules.',
        groups: [
            {
                title: 'Training Library',
                items: [
                    'View onboarding, compliance, and skills materials',
                    'Acknowledge assigned training pushes to log compliance',
                    'Track due dates and task integration for mandatory training',
                ],
            },
        ],
    },
    'my-email': {
        title: 'My Email',
        subtitle: 'Read, send, and manage your Gmail directly within My Desk.',
        groups: [
            {
                title: 'Gmail Integration',
                items: [
                    'Read and reply to emails without leaving the app',
                    'Compose new emails with Cc, Bcc, and attachments',
                    'Archive, star, delete, and search with Gmail query syntax',
                    'Labels and folder navigation: Inbox, Sent, Drafts, Trash',
                ],
            },
        ],
    },
};