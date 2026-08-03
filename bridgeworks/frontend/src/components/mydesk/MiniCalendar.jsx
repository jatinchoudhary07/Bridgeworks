import React, { useMemo } from 'react';
import { Box, IconButton, Stack, Tooltip, Typography } from '@mui/material';
import {
    ChevronLeft as ChevronLeftIcon,
    ChevronRight as ChevronRightIcon,
    Sync as SyncIcon,
} from '@mui/icons-material';
import { toDateKey } from './calendarUtils';

const EVENT_DOT_COLORS = {
    task: 'success.main',
    meeting: 'info.main',
    call: 'warning.main',
    leave: 'secondary.main',
    birthday: 'secondary.main',
    high_pressure: 'error.main',
    holiday: 'success.main',
    company_event: 'info.main',
    big_sale: 'warning.main',
    annual_event: 'primary.main',
};

function buildMonthCells(monthDate) {
    if (!monthDate) return [];
    const monthStart = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    const daysInMonth = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0).getDate();
    const mondayIndex = (monthStart.getDay() + 6) % 7;
    const prevMonthDays = new Date(monthDate.getFullYear(), monthDate.getMonth(), 0).getDate();

    const cells = [];

    for (let index = 0; index < mondayIndex; index += 1) {
        const dayNum = prevMonthDays - mondayIndex + index + 1;
        cells.push({
            date: new Date(monthDate.getFullYear(), monthDate.getMonth() - 1, dayNum),
            outside: true,
        });
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
        cells.push({
            date: new Date(monthDate.getFullYear(), monthDate.getMonth(), day),
            outside: false,
        });
    }

    while (cells.length % 7 !== 0) {
        const nextDay = cells.length - (mondayIndex + daysInMonth) + 1;
        cells.push({
            date: new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, nextDay),
            outside: true,
        });
    }

    return cells;
}

export default function MiniCalendar({
    monthDate,
    eventsByDate,
    selectedDate,
    loading,
    onPrevMonth,
    onNextMonth,
    onSync,
    onDayClick,
}) {
    const todayKey = useMemo(() => toDateKey(new Date()), []);
    const dayCells = useMemo(() => buildMonthCells(monthDate), [monthDate]);

    if (!monthDate) return null;

    return (
        <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, p: { xs: 1, sm: 1.25, md: 1.5 } }}>
            <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ mb: 1 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: { xs: '0.8rem', sm: '0.875rem' } }}>
                    {monthDate.toLocaleDateString([], { month: 'long', year: 'numeric' })}
                </Typography>

                <Stack direction="row" spacing={0.25}>
                    <IconButton size="small" onClick={onPrevMonth}>
                        <ChevronLeftIcon fontSize="small" />
                    </IconButton>
                    <Tooltip title="Sync calendar">
                        <span>
                            <IconButton size="small" onClick={onSync} disabled={loading}>
                                <SyncIcon fontSize="small" />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <IconButton size="small" onClick={onNextMonth}>
                        <ChevronRightIcon fontSize="small" />
                    </IconButton>
                </Stack>
            </Stack>

            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: { xs: 0.35, sm: 0.5 }, mb: 0.5 }}>
                {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((label, index) => (
                    <Typography key={`${label}-${index}`} variant="caption" color="text.secondary" sx={{ textAlign: 'center', fontWeight: 700 }}>
                        {label}
                    </Typography>
                ))}
            </Box>

            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: { xs: 0.35, sm: 0.5 } }}>
                {dayCells.map((cell) => {
                    const dateKey = toDateKey(cell.date);
                    const dayEvents = eventsByDate[dateKey] || [];
                    const dayTypes = [...new Set(dayEvents.map((event) => event.calendarType))].slice(0, 4);
                    const isToday = dateKey === todayKey;
                    const isSelected = dateKey === selectedDate;

                    return (
                        <Box
                            key={dateKey}
                            onClick={(clickEvent) => onDayClick(dateKey, clickEvent.currentTarget)}
                            sx={{
                                minHeight: { xs: 36, sm: 42, md: 48 },
                                border: 1,
                                borderColor: isSelected ? 'primary.main' : 'divider',
                                borderRadius: 1.25,
                                px: 0.25,
                                pt: 0.35,
                                pb: 0.5,
                                cursor: 'pointer',
                                opacity: cell.outside ? 0.5 : 1,
                                bgcolor: isToday ? 'action.selected' : 'background.paper',
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                '&:hover': { bgcolor: 'action.hover' },
                            }}
                        >
                            <Typography variant="caption" sx={{ fontWeight: isToday ? 700 : 500 }}>
                                {cell.date.getDate()}
                            </Typography>

                            <Stack direction="row" spacing={0.25}>
                                {dayTypes.map((type) => (
                                    <Box
                                        key={`${dateKey}-${type}`}
                                        sx={{
                                            width: 6,
                                            height: 6,
                                            borderRadius: '50%',
                                            bgcolor: EVENT_DOT_COLORS[type] || 'text.disabled',
                                        }}
                                    />
                                ))}
                            </Stack>
                        </Box>
                    );
                })}
            </Box>
        </Box>
    );
}