import React from 'react';
import {
    Box,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Tooltip,
} from '@mui/material';
import MiniCalendar from './MiniCalendar';

export default function Sidebar({
    items,
    selectedItem,
    onSelectItem,
    monthDate,
    eventsByDate,
    selectedDate,
    calendarLoading,
    onPrevMonth,
    onNextMonth,
    onSyncCalendar,
    onDayClick,
}) {
    return (
        <Box
            sx={{
                width: { xs: '100%', md: 300 },
                minWidth: { xs: '100%', md: 300 },
                flexShrink: 0,
                borderRight: { xs: 0, md: 1 },
                borderBottom: { xs: 1, md: 0 },
                borderColor: 'divider',
                bgcolor: 'background.paper',
                display: 'flex',
                flexDirection: 'column',
                maxHeight: { xs: '52vh', sm: '58vh', md: 'calc(100vh - 84px)' },
                overflow: 'hidden',
            }}
        >
            <Box sx={{ px: 1, overflowY: 'auto', maxHeight: '100%' }}>
                <List dense sx={{ pt: 0 }}>
                    {items.map((item) => {
                        const IconComponent = item.icon;
                        const inactive = Boolean(item.inactive);
                        const active = selectedItem === item.id;

                        return (
                            <ListItem key={item.id} disablePadding sx={{ mb: 0.5 }}>
                                <Tooltip title={inactive ? 'Coming Soon' : ''} arrow disableHoverListener={!inactive}>
                                    <Box sx={{ width: '100%' }}>
                                        <ListItemButton
                                            selected={active}
                                            disabled={inactive}
                                            onClick={() => {
                                                if (inactive) return;
                                                onSelectItem(item.id);
                                            }}
                                            sx={{
                                                borderRadius: 2,
                                                mx: 0.5,
                                                px: 1.25,
                                                minHeight: 40,
                                                opacity: inactive ? 0.55 : 1,
                                                bgcolor: active ? 'rgba(21, 101, 192, 0.08)' : (inactive ? 'action.hover' : undefined),
                                                border: active ? '1px solid' : '1px solid transparent',
                                                borderColor: active ? 'rgba(21, 101, 192, 0.24)' : 'transparent',
                                                boxShadow: active ? '0 1px 2px rgba(15, 23, 42, 0.08)' : 'none',
                                                '&:hover': {
                                                    bgcolor: active ? 'rgba(21, 101, 192, 0.08)' : 'action.hover',
                                                },
                                            }}
                                        >
                                            <ListItemIcon sx={{ minWidth: 34 }}>
                                                <IconComponent fontSize="small" color={inactive ? 'disabled' : active ? 'primary' : 'action'} />
                                            </ListItemIcon>
                                            <ListItemText
                                                primary={item.label}
                                                primaryTypographyProps={{
                                                    variant: 'body2',
                                                    fontWeight: active ? 700 : 500,
                                                    color: inactive ? 'text.disabled' : undefined,
                                                }}
                                            />
                                            {item.badgeCount > 0 && (
                                                <Box
                                                    sx={{
                                                        bgcolor: 'error.main',
                                                        color: 'error.contrastText',
                                                        borderRadius: '10px',
                                                        px: 1,
                                                        py: 0.2,
                                                        fontSize: '11px',
                                                        fontWeight: 'bold',
                                                        lineHeight: 1,
                                                        minWidth: '20px',
                                                        textAlign: 'center',
                                                        boxShadow: '0 2px 4px rgba(239, 68, 68, 0.3)',
                                                    }}
                                                >
                                                    {item.badgeCount}
                                                </Box>
                                            )}
                                        </ListItemButton>
                                    </Box>
                                </Tooltip>
                            </ListItem>
                        );
                    })}
                </List>

                <Box sx={{ px: 1, py: 1.5 }}>
                    <Box
                        sx={{
                            width: '100%',
                            maxWidth: { xs: 380, md: '100%' },
                            mx: 'auto',
                            borderRadius: 2,
                            border: '1px solid',
                            borderColor: 'divider',
                            bgcolor: 'background.paper',
                            boxShadow: '0 1px 2px rgba(15, 23, 42, 0.08)',
                            p: 0.5,
                        }}
                    >
                        <MiniCalendar
                            monthDate={monthDate}
                            eventsByDate={eventsByDate}
                            selectedDate={selectedDate}
                            loading={calendarLoading}
                            onPrevMonth={onPrevMonth}
                            onNextMonth={onNextMonth}
                            onSync={onSyncCalendar}
                            onDayClick={onDayClick}
                        />
                    </Box>
                </Box>
            </Box>
        </Box>
    );
}