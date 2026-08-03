import React, { useState, useEffect } from 'react';
import { Box, List, ListItem, ListItemButton, ListItemText, IconButton, Tooltip, Collapse } from '@mui/material';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import MenuIcon from '@mui/icons-material/Menu';
import { ExpandLess, ExpandMore } from '@mui/icons-material';

import { checkActionPermission } from '../../utils/rbac';

const SIDEBAR_WIDTH = 220;
const COLLAPSED_WIDTH = 44;

const navigationItems = [
    {
        path: '/team',
        label: 'Team Directory',
        exact: true,
        permission: { area: 'human_resources', feature: 'team_directory' }
    },
    {
        path: '/team/master-workforce-sheet',
        label: 'Master Workforce Sheet',
        permission: { area: 'human_resources', feature: 'workforce_sheet' }
    },
    {
        path: '/team/master-task-tracker',
        label: 'Master Task Manager',
        permission: { area: 'human_resources', feature: 'master_task_tracker' }
    },
    {
        path: '/team/meeting-manager',
        label: 'Meeting Manager',
        permission: { area: 'human_resources', feature: 'meeting_manager' }
    },
    {
        path: '/team/role-editor',
        label: 'Roles & Permissions',
        permission: { area: 'human_resources', feature: 'roles_permissions' }
    },
    {
        path: '/team/attendance',
        label: 'Attendance Dashboard',
        permission: { area: 'human_resources', feature: 'attendance_dashboard' }
    },
    {
        path: '/team/org-hierarchy',
        label: 'Org Hierarchy',
        permission: { area: 'human_resources', feature: 'team_directory' }
    },
    {
        path: '/team/payroll',
        label: 'Payroll',
        permission: { area: 'human_resources', feature: 'payroll' }
    },
    {
        path: '/team/expenses',
        label: 'Expenses',
        permission: { area: 'human_resources', feature: 'expenses' }
    },
    {
        path: '/team/dept-expenses',
        label: 'Dept Expenses',
        permission: { area: 'human_resources', feature: 'expenses' }
    },
    {
        path: '/team/diary',
        label: 'Diary',
        permission: { area: 'human_resources', feature: 'diary_logbooks' }
    },
    {
        path: '/team/analytics',
        label: 'Analytics',
        permission: { area: 'human_resources', feature: 'team_directory' }
    },
    {
        path: '/team/training',
        label: 'Training Hub',
        permission: { area: 'human_resources', feature: 'team_directory' }
    },
    {
        path: '/team/hiring',
        label: 'Jobs Board',
        permission: { area: 'human_resources', feature: 'team_directory' },
        exact: true,
    },
];

export default function HumanResourcesSidebar() {
    const location = useLocation();
    const { user } = useUser();
    const [collapsed, setCollapsed] = useState(false);
    const [openSubmenus, setOpenSubmenus] = useState({});

    // Auto-open submenu if a child route is active
    useEffect(() => {
        navigationItems.forEach(item => {
            if (item.children) {
                const isChildActive = item.children.some(child =>
                    child.exact ? location.pathname === child.path : location.pathname.startsWith(child.path)
                );
                if (isChildActive) {
                    setOpenSubmenus(prev => ({ ...prev, [item.label]: true }));
                }
            }
        });
    }, [location.pathname]);

    const handleSubmenuClick = (label) => {
        setOpenSubmenus(prev => ({ ...prev, [label]: !prev[label] }));
    };

    const isActive = (item) => {
        if (!item.path) return false;
        if (item.exact) return location.pathname === item.path;
        return location.pathname.startsWith(item.path);
    };

    const currentWidth = collapsed ? COLLAPSED_WIDTH : SIDEBAR_WIDTH;

    const renderItem = (item, depth = 0) => {
        if (item.permission && !checkActionPermission(user, item.permission.area, item.permission.feature, 'view')) {
            return null;
        }

        const pl = 1 + depth;

        // ── Group with children ──────────────────────────────────────────
        if (item.children) {
            const isOpen = openSubmenus[item.label];
            const isChildActive = item.children.some(child => isActive(child));

            if (collapsed) {
                return (
                    <Tooltip key={item.label} title={item.label} placement="right" arrow>
                        <ListItem disablePadding sx={{ mb: 0.25 }}>
                            <ListItemButton
                                onClick={() => handleSubmenuClick(item.label)}
                                sx={{
                                    borderRadius: 1, minHeight: 36, justifyContent: 'center', px: 0.5,
                                    bgcolor: isChildActive ? 'primary.main' : 'transparent',
                                    color: isChildActive ? 'primary.contrastText' : 'inherit',
                                    '&:hover': { bgcolor: isChildActive ? 'primary.dark' : 'action.hover' },
                                }}
                            >
                                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: isChildActive ? 'currentColor' : 'text.disabled' }} />
                            </ListItemButton>
                        </ListItem>
                    </Tooltip>
                );
            }

            return (
                <React.Fragment key={item.label}>
                    <ListItem disablePadding sx={{ mb: 0.25 }}>
                        <ListItemButton
                            onClick={() => handleSubmenuClick(item.label)}
                            sx={{
                                borderRadius: 1, pl, pr: 1,
                                bgcolor: isChildActive ? 'rgba(0,0,0,0.04)' : 'transparent',
                            }}
                        >
                            <ListItemText
                                primary={item.label}
                                primaryTypographyProps={{ fontWeight: 600, fontSize: '0.9rem', noWrap: true }}
                            />
                            {isOpen ? <ExpandLess sx={{ fontSize: 18 }} /> : <ExpandMore sx={{ fontSize: 18 }} />}
                        </ListItemButton>
                    </ListItem>
                    <Collapse in={isOpen} timeout="auto" unmountOnExit>
                        <List component="div" disablePadding>
                            {item.children.map(child => renderItem(child, depth + 1))}
                        </List>
                    </Collapse>
                </React.Fragment>
            );
        }

        // ── Leaf item ────────────────────────────────────────────────────
        const active = isActive(item);

        if (collapsed) {
            return (
                <Tooltip key={item.path} title={item.label} placement="right" arrow>
                    <ListItem disablePadding sx={{ mb: 0.25 }}>
                        <ListItemButton
                            component={RouterLink}
                            to={item.path}
                            selected={active}
                            sx={{
                                borderRadius: 1, minHeight: 36, justifyContent: 'center', px: 0.5,
                                '&.Mui-selected': { backgroundColor: 'primary.main', color: 'primary.contrastText', '&:hover': { backgroundColor: 'primary.dark' } },
                                '&:hover': { backgroundColor: 'action.hover' },
                            }}
                        >
                            <Box sx={{ width: 24, height: 24, borderRadius: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem', fontWeight: 700, bgcolor: active ? 'transparent' : 'action.hover', color: active ? 'inherit' : 'text.secondary' }}>
                                {item.label.trim().charAt(0)}
                            </Box>
                        </ListItemButton>
                    </ListItem>
                </Tooltip>
            );
        }

        return (
            <ListItem key={item.path} disablePadding sx={{ mb: 0.25 }}>
                <ListItemButton
                    component={RouterLink}
                    to={item.path}
                    selected={active}
                    sx={{
                        borderRadius: 1, pl, pr: 1,
                        '&.Mui-selected': { backgroundColor: 'primary.main', color: 'primary.contrastText', '&:hover': { backgroundColor: 'primary.dark' } },
                        '&:hover': { backgroundColor: 'action.hover' },
                    }}
                >
                    <ListItemText
                        primary={item.label}
                        primaryTypographyProps={{ fontWeight: active ? 600 : 400, fontSize: '0.9rem', noWrap: true }}
                    />
                </ListItemButton>
            </ListItem>
        );
    };

    return (
        <Box
            sx={{
                width: currentWidth,
                minWidth: currentWidth,
                flexShrink: 0,
                transition: 'width 0.2s ease, min-width 0.2s ease',
                borderRight: 1,
                borderColor: 'divider',
                bgcolor: 'background.paper',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
            }}
        >
            <Box sx={{ display: 'flex', justifyContent: collapsed ? 'center' : 'flex-end', p: 0.5, flexShrink: 0 }}>
                <IconButton size="small" onClick={() => setCollapsed(!collapsed)} sx={{ width: 28, height: 28 }}>
                    {collapsed ? <MenuIcon sx={{ fontSize: 18 }} /> : <ChevronLeftIcon sx={{ fontSize: 18 }} />}
                </IconButton>
            </Box>

            <List sx={{ pt: 0.5, px: 0.5, overflowY: 'auto', overflowX: 'hidden', flex: 1 }}>
                {navigationItems.map(item => renderItem(item))}
            </List>
        </Box>
    );
}
