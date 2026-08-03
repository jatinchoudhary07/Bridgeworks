import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
    Box,
    IconButton,
    List,
    ListItem,
    ListItemButton,
    ListItemText,
    Tooltip,
} from '@mui/material';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import MenuIcon from '@mui/icons-material/Menu';

const SIDEBAR_WIDTH = 180;
const COLLAPSED_WIDTH = 40;

const navigationItems = [
    { key: 'control-tower',      label: 'Control Tower',       shortLabel: 'CT'  },
    { key: 'journal',            label: 'Journal Entry',       shortLabel: 'JE'  },
    { key: 'ledger',             label: 'Ledger Summary',      shortLabel: 'LS'  },
    { key: 'trial-balance',      label: 'Trial Balance',       shortLabel: 'TB'  },
    { key: 'profit-loss',        label: 'Profit & Loss',       shortLabel: 'PL'  },
    { key: 'balance-sheet',      label: 'Balance Sheet',       shortLabel: 'BS'  },
    { key: 'pending-expenses',   label: 'Pending Expenses',    shortLabel: 'PE'  },
    { key: 'finance',            label: 'Finance',             shortLabel: 'F'   },
    { key: 'departments',        label: 'Departments',         shortLabel: 'D'   },
    { key: 'payroll',            label: 'Payroll',             shortLabel: 'PAY' },
    { key: 'dept-expenses',      label: 'Dept Expenses',       shortLabel: 'DE'  },
    { key: 'gst',                label: 'GST Center',          shortLabel: 'GST' },
    { key: 'reconciliation',     label: 'Bank Reconciliation', shortLabel: 'BR'  },
    { key: 'accounts',           label: 'Accounts Center',     shortLabel: 'AC'  },
    { key: 'assets',             label: 'Asset Management',    shortLabel: 'AM'  },
    { key: 'decisions',          label: 'Decision Ledger',     shortLabel: 'DL'  },
    { key: 'reports',            label: 'Reports Hub',         shortLabel: 'RH'  },
];

const SidebarContent = ({ activeKey, collapsed, onSelect }) => {
    const renderItem = (item) => {
        const active = activeKey === item.key;

        if (collapsed) {
            return (
                <Tooltip key={item.key} title={item.label} placement="right" arrow>
                    <ListItem disablePadding sx={{ mb: 0.25 }}>
                        <ListItemButton
                            onClick={() => onSelect(item.key)}
                            selected={active}
                            sx={{
                                borderRadius: 1,
                                minHeight: 36,
                                justifyContent: 'center',
                                px: 0.5,
                                '&.Mui-selected': {
                                    backgroundColor: 'primary.main',
                                    color: 'primary.contrastText',
                                    '&:hover': { backgroundColor: 'primary.dark' },
                                },
                                '&:hover': { backgroundColor: 'action.hover' },
                            }}
                        >
                            <Box
                                sx={{
                                    width: 24,
                                    height: 24,
                                    borderRadius: 1,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    fontSize: '0.7rem',
                                    fontWeight: 700,
                                    bgcolor: active ? 'transparent' : 'action.hover',
                                    color: active ? 'inherit' : 'text.secondary',
                                }}
                            >
                                {item.shortLabel}
                            </Box>
                        </ListItemButton>
                    </ListItem>
                </Tooltip>
            );
        }

        return (
            <ListItem key={item.key} disablePadding sx={{ mb: 0.25 }}>
                <ListItemButton
                    onClick={() => onSelect(item.key)}
                    selected={active}
                    sx={{
                        borderRadius: 1,
                        '&.Mui-selected': {
                            backgroundColor: 'primary.main',
                            color: 'primary.contrastText',
                            '&:hover': { backgroundColor: 'primary.dark' },
                        },
                        '&:hover': { backgroundColor: 'action.hover' },
                    }}
                >
                    <ListItemText
                        primary={item.label}
                        primaryTypographyProps={{
                            fontWeight: active ? 600 : 400,
                            fontSize: '0.85rem',
                            noWrap: true,
                        }}
                    />
                </ListItemButton>
            </ListItem>
        );
    };

    return <List sx={{ pt: 0.5, px: 0.5 }}>{navigationItems.map(renderItem)}</List>;
};

// ── Sidebar derives active state from URL, pushes URL on click ────────────────
export default function FinanceSidebar() {
    const [collapsed, setCollapsed] = useState(false);
    const navigate = useNavigate();
    const { pathname } = useLocation();

    const currentWidth = collapsed ? COLLAPSED_WIDTH : SIDEBAR_WIDTH;

    // Derive active key from the URL: /finance/<key>
    const segments = pathname.split('/').filter(Boolean); // ['finance', 'payroll']
    let activeKey = segments[1] || 'control-tower';       // second segment
    if (activeKey.startsWith('gst-')) {
        activeKey = 'gst';
    }

    const handleSelect = (key) => {
        navigate(`/finance/${key}`);
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
                position: 'relative',
            }}
        >
            <Box sx={{ display: 'flex', justifyContent: collapsed ? 'center' : 'flex-end', p: 0.5 }}>
                <IconButton
                    size="small"
                    onClick={() => setCollapsed(!collapsed)}
                    sx={{ width: 28, height: 28 }}
                >
                    {collapsed ? <MenuIcon sx={{ fontSize: 18 }} /> : <ChevronLeftIcon sx={{ fontSize: 18 }} />}
                </IconButton>
            </Box>

            <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
                <SidebarContent
                    activeKey={activeKey}
                    collapsed={collapsed}
                    onSelect={handleSelect}
                />
            </Box>
        </Box>
    );
}