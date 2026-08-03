// DeskAnalyticsPage.jsx – No sidebar · Tab switcher · Bigger fonts · Rich Achievements

import React, { useState, useMemo } from 'react';
import {
    Box, Typography, Card, CardContent, Chip, Avatar,
    Grid, Tooltip, Stack,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    ToggleButtonGroup, ToggleButton, LinearProgress, useTheme, alpha,
} from '@mui/material';
import {
    AreaChart, Area, BarChart, Bar, LineChart, Line,
    PieChart, Pie, Cell, ComposedChart,
    XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip, Legend, ResponsiveContainer,
} from 'recharts';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import LocalFireDepartmentIcon from '@mui/icons-material/LocalFireDepartment';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';
import BoltIcon from '@mui/icons-material/Bolt';
import StarIcon from '@mui/icons-material/Star';
import HandshakeIcon from '@mui/icons-material/Handshake';
import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';

// ─── DATA ────────────────────────────────────────────────────

const weeklyProductivity = [
    { week: 'W1', score: 72, tasks: 14 }, { week: 'W2', score: 68, tasks: 11 },
    { week: 'W3', score: 75, tasks: 16 }, { week: 'W4', score: 71, tasks: 13 },
    { week: 'W5', score: 79, tasks: 18 }, { week: 'W6', score: 76, tasks: 17 },
    { week: 'W7', score: 83, tasks: 21 }, { week: 'W8', score: 82, tasks: 19 },
];

const taskDistribution = [
    { name: 'Done',        value: 47, color: '#10b981' },
    { name: 'In Progress', value: 12, color: '#4f46e5' },
    { name: 'Overdue',     value: 5,  color: '#ef4444' },
    { name: 'Blocked',     value: 3,  color: '#f59e0b' },
];

const focusMeetingData = [
    { day: 'Mon', focus: 6.2, meeting: 2.1 },
    { day: 'Tue', focus: 5.8, meeting: 3.4 },
    { day: 'Wed', focus: 4.9, meeting: 4.2 },
    { day: 'Thu', focus: 6.5, meeting: 1.8 },
    { day: 'Fri', focus: 5.1, meeting: 3.6 },
];

const teamMembers = [
    { rank: 1, name: 'Priya Sharma', av: 'PS', score: 94, tasks: 28, att: 98, t: 'up' },
    { rank: 2, name: 'Rahul Verma',  av: 'RV', score: 91, tasks: 25, att: 96, t: 'up' },
    { rank: 3, name: 'Neha Gupta',   av: 'NG', score: 88, tasks: 23, att: 95, t: 'up' },
    { rank: 4, name: 'Arjun Patel',  av: 'AP', score: 85, tasks: 21, att: 94, t: 'stable', isMe: true },
    { rank: 5, name: 'Sneha Joshi',  av: 'SJ', score: 83, tasks: 20, att: 92, t: 'up' },
    { rank: 6, name: 'Vikram Singh', av: 'VS', score: 82, tasks: 19, att: 91, t: 'stable' },
    { rank: 7, name: 'Deepa Nair',   av: 'DN', score: 79, tasks: 17, att: 89, t: 'down' },
    { rank: 8, name: 'Amit Kumar',   av: 'AK', score: 76, tasks: 15, att: 88, t: 'down' },
];

const deptComparison = [
    { dept: 'Engineering', productivity: 82, attendance: 93, tasks: 87 },
    { dept: 'Marketing',   productivity: 76, attendance: 88, tasks: 79 },
    { dept: 'Finance',     productivity: 84, attendance: 95, tasks: 91 },
    { dept: 'HR',          productivity: 79, attendance: 91, tasks: 83 },
    { dept: 'Operations',  productivity: 71, attendance: 87, tasks: 75 },
    { dept: 'Sales',       productivity: 88, attendance: 90, tasks: 92 },
];

const orgTrends = [
    { month: 'Oct', output: 68, payroll: 100 }, { month: 'Nov', output: 72, payroll: 103 },
    { month: 'Dec', output: 69, payroll: 105 }, { month: 'Jan', output: 76, payroll: 107 },
    { month: 'Feb', output: 81, payroll: 112 }, { month: 'Mar', output: 84, payroll: 115 },
    { month: 'Apr', output: 79, payroll: 118 }, { month: 'May', output: 86, payroll: 128 },
];

const attritionRisk = [
    { name: 'Deepa Nair',  risk: 78, reason: 'Overtime + task backlog' },
    { name: 'Ravi Tiwari', risk: 65, reason: 'Backlog + disengagement' },
    { name: 'Pooja Mehta', risk: 54, reason: 'Disengagement signals' },
    { name: 'Arun Das',    risk: 41, reason: 'Attendance decline' },
];

const MY_ACHIEVEMENTS = [
    {
        icon: EmojiEventsIcon,
        label: 'Top Performer',
        desc: 'Ranked #4 in Engineering this month',
        earnedOn: 'May 1, 2026',
        color: '#f59e0b',
        grad: 'linear-gradient(135deg,#fef3c7,#fde68a)',
        border: '#f59e0b',
    },
    {
        icon: LocalFireDepartmentIcon,
        label: '14-Day Streak',
        desc: '14 consecutive days of full attendance',
        earnedOn: 'Ongoing – started Apr 28',
        color: '#ef4444',
        grad: 'linear-gradient(135deg,#fff1f2,#fee2e2)',
        border: '#ef4444',
        streakDays: 14,
    },
    {
        icon: BoltIcon,
        label: 'Fastest Resolver',
        desc: 'Closed 12 tickets in under 2 hrs avg',
        earnedOn: 'May 10, 2026',
        color: '#4f46e5',
        grad: 'linear-gradient(135deg,#ede9fe,#ddd6fe)',
        border: '#4f46e5',
    },
    {
        icon: HandshakeIcon,
        label: 'Most Collaborative',
        desc: 'Highest cross-team interactions this week',
        earnedOn: 'May 9, 2026',
        color: '#10b981',
        grad: 'linear-gradient(135deg,#d1fae5,#a7f3d0)',
        border: '#10b981',
    },
    {
        icon: StarIcon,
        label: 'Best Consistency',
        desc: 'Quality score above 85 for 8 straight weeks',
        earnedOn: 'May 5, 2026',
        color: '#8b5cf6',
        grad: 'linear-gradient(135deg,#ede9fe,#c4b5fd)',
        border: '#8b5cf6',
    },
];

const NEXT_BADGE = { label: 'Sprint Hero', current: 80, desc: '4 more sprints to unlock', color: '#4f46e5' };

// ─── MICRO COMPONENTS ────────────────────────────────────────

function TrendIcon({ t }) {
    if (t === 'up')   return <TrendingUpIcon   sx={{ fontSize: 14, color: 'success.main' }} />;
    if (t === 'down') return <TrendingDownIcon sx={{ fontSize: 14, color: 'error.main' }} />;
    return <Box sx={{ display: 'inline-block', width: 12, height: 2, bgcolor: 'text.disabled', borderRadius: 1, verticalAlign: 'middle' }} />;
}

function KPI({ title, value, unit = '', trend, trendLabel }) {
    return (
        <Card sx={{ borderRadius: 2, height: '100%', boxShadow: '0 1px 6px rgba(0,0,0,0.06)' }}>
            <CardContent sx={{ p: 1.75, '&:last-child': { pb: 1.75 } }}>
                <Typography sx={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 700, color: 'text.secondary', lineHeight: 1.3 }}>
                    {title}
                </Typography>
                <Typography sx={{ fontWeight: 800, fontSize: '1.45rem', lineHeight: 1.15, mt: 0.4, color: 'text.primary' }}>
                    {value}
                    {unit && <Typography component="span" sx={{ fontWeight: 400, ml: 0.5, color: 'text.secondary', fontSize: '0.78rem' }}>{unit}</Typography>}
                </Typography>
                {trendLabel && (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.4, mt: 0.3 }}>
                        <TrendIcon t={trend} />
                        <Typography sx={{
                            fontSize: '0.72rem', fontWeight: 600,
                            color: trend === 'up' ? 'success.main' : trend === 'down' ? 'error.main' : 'text.secondary',
                        }}>{trendLabel}</Typography>
                    </Box>
                )}
            </CardContent>
        </Card>
    );
}

function MiniHeatmap({ data, streakDays }) {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';
    const colors = isDark
        ? ['rgba(255, 255, 255, 0.05)', '#0e4429', '#006d32', '#26a641', '#39d353']
        : ['#f1f5f9', '#bbf7d0', '#4ade80', '#16a34a', '#14532d'];
    const days = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
    const labels = ['Absent', 'Partial', 'On Time', 'Early', 'Extra Hrs'];
    return (
        <Box>
            {streakDays > 0 && (
                <Box sx={{
                    display: 'flex', alignItems: 'center', gap: 1, mb: 1,
                    px: 1.2, py: 0.7, borderRadius: 2,
                    background: isDark
                        ? 'linear-gradient(90deg, rgba(234,88,12,0.15), rgba(251,191,36,0.15))'
                        : 'linear-gradient(90deg,#fff7ed,#ffedd5)',
                    border: '1px solid',
                    borderColor: isDark ? 'rgba(234,88,12,0.3)' : '#fed7aa',
                }}>
                    <LocalFireDepartmentIcon sx={{ color: isDark ? '#f97316' : '#ea580c', fontSize: 18 }} />
                    <Box>
                        <Typography sx={{ fontWeight: 800, fontSize: '0.9rem', color: isDark ? '#f97316' : '#c2410c', lineHeight: 1 }}>
                            {streakDays}-Day Streak!
                        </Typography>
                        <Typography sx={{ fontSize: '0.68rem', color: isDark ? '#fdba74' : '#9a3412' }}>Full attendance — keep it going</Typography>
                    </Box>
                    <Chip label="Top 15%" size="small" sx={{ ml: 'auto', bgcolor: '#ea580c', color: 'white', fontWeight: 700, fontSize: '0.65rem' }} />
                </Box>
            )}
            {days.map((d, di) => (
                <Box key={di} sx={{ display: 'flex', gap: '3px', mb: '3px', alignItems: 'center' }}>
                    <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', width: 12, flexShrink: 0 }}>{d}</Typography>
                    {data.map((week, wi) => (
                        <Tooltip key={wi} title={`W${wi + 1} ${['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][di]} – ${labels[week[di]] ?? ''}`} arrow>
                            <Box sx={{
                                width: 14, height: 14, borderRadius: '3px',
                                bgcolor: colors[week[di]] ?? colors[0],
                                cursor: 'default',
                                transition: 'transform 0.12s',
                                '&:hover': { transform: 'scale(1.25)' },
                            }} />
                        </Tooltip>
                    ))}
                </Box>
            ))}
            <Box sx={{ display: 'flex', gap: 0.5, mt: 0.8, alignItems: 'center' }}>
                <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled' }}>Less</Typography>
                {colors.map((c, i) => <Box key={i} sx={{ width: 11, height: 11, borderRadius: '3px', bgcolor: c, border: '1px solid', borderColor: 'divider' }} />)}
                <Typography sx={{ fontSize: '0.63rem', color: 'text.disabled' }}>More</Typography>
            </Box>
        </Box>
    );
}

// ─── ACHIEVEMENTS SECTION ────────────────────────────────────

function AchievementsSection() {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';

    const getAchievementBg = (a) => {
        if (!isDark) return a.grad;
        if (a.color === '#f59e0b') return 'linear-gradient(135deg, rgba(245,158,11,0.15), rgba(217,119,6,0.15))';
        if (a.color === '#ef4444') return 'linear-gradient(135deg, rgba(239,68,68,0.15), rgba(220,38,38,0.15))';
        if (a.color === '#4f46e5') return 'linear-gradient(135deg, rgba(79,70,229,0.15), rgba(67,56,202,0.15))';
        if (a.color === '#10b981') return 'linear-gradient(135deg, rgba(16,185,129,0.15), rgba(5,150,105,0.15))';
        if (a.color === '#8b5cf6') return 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(124,58,237,0.15))';
        return 'rgba(255,255,255,0.05)';
    };

    const getAchievementColor = (a) => {
        if (!isDark) return a.color;
        if (a.color === '#4f46e5') return '#818cf8';
        if (a.color === '#8b5cf6') return '#a78bfa';
        if (a.color === '#10b981') return '#34d399';
        if (a.color === '#ef4444') return '#f87171';
        if (a.color === '#f59e0b') return '#fbbf24';
        return a.color;
    };

    const getAchievementBorder = (a) => {
        return isDark ? getAchievementColor(a) : a.border;
    };

    return (
        <Card sx={{ borderRadius: 2, overflow: 'visible' }}>
            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <WorkspacePremiumIcon sx={{ color: '#f59e0b', fontSize: 20 }} />
                        <Typography sx={{ fontWeight: 800, fontSize: '0.95rem' }}>Achievements</Typography>
                    </Box>
                    <Chip label="5 Earned" size="small" sx={{
                        bgcolor: isDark ? 'rgba(250,204,21,0.15)' : '#fef9c3',
                        color: isDark ? '#fde047' : '#854d0e',
                        fontWeight: 700,
                        fontSize: '0.72rem'
                    }} />
                </Box>

                {/* Badge cards grid */}
                <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap', mb: 1.5 }}>
                    {MY_ACHIEVEMENTS.map(a => {
                        const Icon = a.icon;
                        const resolvedColor = getAchievementColor(a);
                        const resolvedBorder = getAchievementBorder(a);
                        return (
                            <Box key={a.label} sx={{
                                flex: '1 1 160px', minWidth: 148,
                                background: getAchievementBg(a),
                                border: `1.5px solid ${resolvedBorder}40`,
                                borderRadius: 2.5,
                                p: 1.5,
                                position: 'relative',
                                overflow: 'hidden',
                                transition: 'transform 0.15s, box-shadow 0.15s',
                                '&:hover': { transform: 'translateY(-2px)', boxShadow: `0 6px 20px ${resolvedBorder}30` },
                            }}>
                                {/* glow dot */}
                                <Box sx={{ position: 'absolute', top: -12, right: -12, width: 50, height: 50, borderRadius: '50%', bgcolor: `${resolvedBorder}15` }} />
                                <Icon sx={{ color: resolvedColor, fontSize: 28, mb: 0.5 }} />
                                <Typography sx={{ fontWeight: 800, fontSize: '0.88rem', color: resolvedColor, lineHeight: 1.2 }}>{a.label}</Typography>
                                <Typography sx={{ fontSize: '0.7rem', color: 'text.secondary', mt: 0.3, lineHeight: 1.4 }}>{a.desc}</Typography>
                                {a.streakDays ? (
                                    <Box sx={{ display: 'flex', gap: '2px', mt: 0.8, flexWrap: 'wrap' }}>
                                        {Array.from({ length: a.streakDays }).map((_, i) => (
                                            <Box key={i} sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: resolvedColor, opacity: 0.7 + (i / a.streakDays) * 0.3 }} />
                                        ))}
                                    </Box>
                                ) : null}
                                <Typography sx={{ fontSize: '0.62rem', color: 'text.disabled', mt: 0.5 }}>{a.earnedOn}</Typography>
                            </Box>
                        );
                    })}
                </Box>

                {/* Next badge progress */}
                <Box sx={{
                    p: 1.2, borderRadius: 2, bgcolor: 'action.hover',
                    display: 'flex', alignItems: 'center', gap: 2,
                }}>
                    <Box sx={{ flex: 1 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                            <Typography sx={{ fontSize: '0.75rem', fontWeight: 700 }}>Next: {NEXT_BADGE.label}</Typography>
                            <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, color: isDark ? 'primary.light' : NEXT_BADGE.color }}>{NEXT_BADGE.current}%</Typography>
                        </Box>
                        <LinearProgress variant="determinate" value={NEXT_BADGE.current}
                            sx={{ height: 7, borderRadius: 4, bgcolor: 'divider', '& .MuiLinearProgress-bar': { bgcolor: isDark ? 'primary.main' : NEXT_BADGE.color, borderRadius: 4 } }} />
                        <Typography sx={{ fontSize: '0.68rem', color: 'text.secondary', mt: 0.5 }}>{NEXT_BADGE.desc}</Typography>
                    </Box>
                </Box>
            </CardContent>
        </Card>
    );
}

// ─── VIEW: MY ANALYTICS ──────────────────────────────────────

function MyAnalyticsView() {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';

    const heatmap = useMemo(() => {
        const w = [0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4];
        return Array.from({ length: 12 }, () =>
            Array.from({ length: 7 }, (_, d) =>
                d >= 5 ? (Math.random() > 0.6 ? 0 : 1) : w[Math.floor(Math.random() * w.length)]
            )
        );
    }, []);

    const kpis = [
        { title: 'Attendance',    value: '91',  unit: '%',       trend: 'up',     trendLabel: '+3% this month' },
        { title: 'Tasks Done',    value: '47',  unit: 'tasks',   trend: 'up',     trendLabel: '+18% vs last mo' },
        { title: 'Focus Hours',   value: '5.2', unit: 'hrs/day', trend: 'up',     trendLabel: '+12% this week' },
        { title: 'Meetings',      value: '3.4', unit: 'hrs/day', trend: 'down',   trendLabel: '-8% this week' },
        { title: 'Work Hours',    value: '8.4', unit: 'hrs/day', trend: 'up',     trendLabel: '+0.3 hrs' },
        { title: 'Leave Balance', value: '12',  unit: 'days',    trend: 'stable', trendLabel: '0 used this mo' },
    ];

    const getAchievementBg = (a) => {
        if (!isDark) return a.grad;
        if (a.color === '#f59e0b') return 'linear-gradient(135deg, rgba(245,158,11,0.15), rgba(217,119,6,0.15))';
        if (a.color === '#ef4444') return 'linear-gradient(135deg, rgba(239,68,68,0.15), rgba(220,38,38,0.15))';
        if (a.color === '#4f46e5') return 'linear-gradient(135deg, rgba(79,70,229,0.15), rgba(67,56,202,0.15))';
        if (a.color === '#10b981') return 'linear-gradient(135deg, rgba(16,185,129,0.15), rgba(5,150,105,0.15))';
        if (a.color === '#8b5cf6') return 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(124,58,237,0.15))';
        return 'rgba(255,255,255,0.05)';
    };

    const getAchievementColor = (a) => {
        if (!isDark) return a.color;
        if (a.color === '#4f46e5') return '#818cf8';
        if (a.color === '#8b5cf6') return '#a78bfa';
        if (a.color === '#10b981') return '#34d399';
        if (a.color === '#ef4444') return '#f87171';
        if (a.color === '#f59e0b') return '#fbbf24';
        return a.color;
    };

    const getAchievementBorder = (a) => {
        return isDark ? getAchievementColor(a) : a.border;
    };

    const getThemeColor = (c) => {
        if (c === '#4f46e5') return theme.palette.primary.main;
        if (c === '#10b981') return theme.palette.success.main;
        if (c === '#f59e0b') return theme.palette.warning.main;
        if (c === '#8b5cf6') return theme.palette.secondary.main;
        if (c === '#ef4444') return theme.palette.error.main;
        return c;
    };

    const tooltipProps = {
        contentStyle: {
            backgroundColor: theme.palette.background.paper,
            borderColor: theme.palette.divider,
            color: theme.palette.text.primary,
        },
        itemStyle: {
            color: theme.palette.text.primary,
        },
    };

    const taskColors = {
        'Done': theme.palette.success.main,
        'In Progress': theme.palette.primary.main,
        'Overdue': theme.palette.error.main,
        'Blocked': theme.palette.warning.main,
    };

    const attColors = [
        theme.palette.success.main,
        theme.palette.info.main,
        theme.palette.error.main,
        isDark ? 'rgba(255,255,255,0.1)' : '#e2e8f0'
    ];

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>

            {/* ROW 1: Score hero + [compact KPIs + achievements bar] */}
            <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'stretch' }}>
                {/* Productivity Score card – unchanged */}
                <Box sx={{ flex: '0 0 220px' }}>
                    <Card sx={{ height: '100%', borderRadius: 2, background: 'linear-gradient(135deg,#4f46e5,#7c3aed)', color: 'white' }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 }, height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                            <Typography sx={{ opacity: 0.7, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: 0.8, mb: 1 }}>
                                Productivity Score
                            </Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1.5 }}>
                                <Box sx={{
                                    width: 76, height: 76, borderRadius: '50%', flexShrink: 0,
                                    background: 'conic-gradient(rgba(255,255,255,0.9) 0% 82%, rgba(255,255,255,0.15) 82% 100%)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                }}>
                                    <Box sx={{ width: 58, height: 58, borderRadius: '50%', bgcolor: '#4f46e5', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                                        <Typography sx={{ fontWeight: 800, color: 'white', fontSize: '1.3rem', lineHeight: 1 }}>82</Typography>
                                        <Typography sx={{ opacity: 0.5, color: 'white', fontSize: '0.6rem' }}>/100</Typography>
                                    </Box>
                                </Box>
                                <Stack spacing={0.6}>
                                    <Chip label="#4 in Dept" size="small" sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'white', fontWeight: 700, fontSize: '0.68rem' }} />
                                    <Chip label="Top 8% Co." size="small" sx={{ bgcolor: 'rgba(255,255,255,0.12)', color: 'white', fontWeight: 600, fontSize: '0.65rem' }} />
                                </Stack>
                            </Box>
                            {[['Attendance',91],['Task Speed',84],['Consistency',86]].map(([lbl,v]) => (
                                <Box key={lbl} sx={{ mb: 0.6 }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.2 }}>
                                        <Typography sx={{ opacity: 0.7, fontSize: '0.68rem', color: 'white' }}>{lbl}</Typography>
                                        <Typography sx={{ opacity: 0.95, fontSize: '0.68rem', fontWeight: 700, color: 'white' }}>{v}</Typography>
                                    </Box>
                                    <Box sx={{ height: 4, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.15)' }}>
                                        <Box sx={{ height: '100%', width: `${v}%`, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.8)' }} />
                                    </Box>
                                </Box>
                            ))}
                        </CardContent>
                    </Card>
                </Box>

                {/* Right column: compact KPI grid on top + achievements below */}
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    {/* Compact KPI single row */}
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        {kpis.map(k => (
                            <Card key={k.title} sx={{ flex: 1, borderRadius: 2, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', minWidth: 0 }}>
                                <CardContent sx={{ p: '8px 10px', '&:last-child': { pb: '8px' } }}>
                                    <Typography sx={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: 0.4, fontWeight: 700, color: 'text.secondary', lineHeight: 1.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                        {k.title}
                                    </Typography>
                                    <Typography sx={{ fontWeight: 800, fontSize: '1.1rem', lineHeight: 1.15, mt: 0.25 }}>
                                        {k.value}
                                        {k.unit && <Typography component="span" sx={{ fontWeight: 400, ml: 0.3, color: 'text.secondary', fontSize: '0.68rem' }}>{k.unit}</Typography>}
                                    </Typography>
                                    {k.trendLabel && (
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.3, mt: 0.15 }}>
                                            <TrendIcon t={k.trend} />
                                            <Typography sx={{
                                                fontSize: '0.62rem',
                                                fontWeight: 600,
                                                color: k.trend === 'up' ? 'success.main' : k.trend === 'down' ? 'error.main' : 'text.secondary',
                                                whiteSpace: 'nowrap',
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis'
                                            }}>{k.trendLabel}</Typography>
                                        </Box>
                                    )}
                                </CardContent>
                            </Card>
                        ))}
                    </Box>

                    {/* Achievements – fills remaining height */}
                    <Card sx={{ borderRadius: 2, flex: 1 }}>
                        <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 }, height: '100%', display: 'flex', flexDirection: 'column' }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                                    <WorkspacePremiumIcon sx={{ color: '#f59e0b', fontSize: 18 }} />
                                    <Typography sx={{ fontWeight: 800, fontSize: '0.88rem' }}>Achievements</Typography>
                                </Box>
                                <Chip label="5 Earned" size="small" sx={{
                                    bgcolor: isDark ? 'rgba(250,204,21,0.15)' : '#fef9c3',
                                    color: isDark ? '#fde047' : '#854d0e',
                                    fontWeight: 700,
                                    fontSize: '0.68rem'
                                }} />
                            </Box>
                            {/* Badge chips row */}
                            <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', flex: 1, alignContent: 'flex-start' }}>
                                {MY_ACHIEVEMENTS.map(a => {
                                    const Icon = a.icon;
                                    const resolvedColor = getAchievementColor(a);
                                    const resolvedBorder = getAchievementBorder(a);
                                    return (
                                        <Box key={a.label} sx={{
                                            display: 'flex', alignItems: 'center', gap: 0.8,
                                            px: 1.2, py: 0.7, borderRadius: 2,
                                            background: getAchievementBg(a),
                                            border: `1.5px solid ${resolvedBorder}35`,
                                            transition: 'transform 0.15s, box-shadow 0.15s',
                                            '&:hover': { transform: 'translateY(-1px)', boxShadow: `0 4px 12px ${resolvedBorder}25` },
                                            cursor: 'default',
                                        }}>
                                            <Icon sx={{ color: resolvedColor, fontSize: 18, flexShrink: 0 }} />
                                            <Box>
                                                <Typography sx={{ fontWeight: 700, fontSize: '0.78rem', color: resolvedColor, lineHeight: 1.2 }}>{a.label}</Typography>
                                                {a.streakDays ? (
                                                    <Box sx={{ display: 'flex', gap: '2px', mt: 0.3 }}>
                                                        {Array.from({ length: a.streakDays }).map((_, i) => (
                                                            <Box key={i} sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: resolvedColor, opacity: 0.5 + (i / a.streakDays) * 0.5 }} />
                                                        ))}
                                                    </Box>
                                                ) : (
                                                    <Typography sx={{ fontSize: '0.63rem', color: 'text.secondary', lineHeight: 1.3 }}>{a.earnedOn}</Typography>
                                                )}
                                            </Box>
                                        </Box>
                                    );
                                })}
                            </Box>
                            {/* Next badge progress */}
                            <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid', borderColor: 'divider' }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.4 }}>
                                    <Typography sx={{ fontSize: '0.73rem', fontWeight: 700 }}>Next: {NEXT_BADGE.label}</Typography>
                                    <Typography sx={{ fontSize: '0.7rem', fontWeight: 700, color: isDark ? 'primary.light' : NEXT_BADGE.color }}>{NEXT_BADGE.current}%  ·  {NEXT_BADGE.desc}</Typography>
                                </Box>
                                <LinearProgress variant="determinate" value={NEXT_BADGE.current}
                                    sx={{ height: 6, borderRadius: 3, bgcolor: 'divider', '& .MuiLinearProgress-bar': { bgcolor: isDark ? 'primary.main' : NEXT_BADGE.color, borderRadius: 3 } }} />
                            </Box>
                        </CardContent>
                    </Card>
                </Box>
            </Box>

            {/* ROW 2: Task donut + Focus chart + Attendance heatmap */}
            <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 3 }}>
                    <Card sx={{ borderRadius: 2, height: '100%' }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 1 }}>Task Breakdown</Typography>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <ResponsiveContainer width={100} height={100}>
                                    <PieChart>
                                        <Pie data={taskDistribution} cx="50%" cy="50%" innerRadius={28} outerRadius={47} paddingAngle={3} dataKey="value">
                                            {taskDistribution.map((e, i) => <Cell key={i} fill={taskColors[e.name] || e.color} />)}
                                        </Pie>
                                        <ReTooltip {...tooltipProps} formatter={(val, name) => {
                                            const total = taskDistribution.reduce((s, t) => s + t.value, 0);
                                            const pct = Math.round(val / total * 100);
                                            return [`${val} tasks (${pct}%)`, name];
                                        }} />
                                    </PieChart>
                                </ResponsiveContainer>
                                <Box sx={{ flex: 1 }}>
                                    {taskDistribution.map(t => (
                                        <Box key={t.name} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.6 }}>
                                                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: taskColors[t.name] || t.color, flexShrink: 0 }} />
                                                <Typography sx={{ fontSize: '0.75rem' }}>{t.name}</Typography>
                                            </Box>
                                            <Typography sx={{ fontWeight: 700, fontSize: '0.78rem' }}>{t.value}</Typography>
                                        </Box>
                                    ))}
                                    <Box sx={{ mt: 0.8, pt: 0.8, borderTop: '1px solid', borderColor: 'divider' }}>
                                        <Typography sx={{ fontSize: '0.72rem' }} color="text.secondary">Avg resolve: <b>1.8 days</b></Typography>
                                    </Box>
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 5 }}>
                    <Card sx={{ borderRadius: 2, height: '100%' }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 1 }}>Focus vs Meetings (this week)</Typography>
                            <ResponsiveContainer width="100%" height={120}>
                                <BarChart data={focusMeetingData} barSize={16} barGap={4} margin={{ top: 0, right: 4, bottom: 0, left: -20 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? 'rgba(255,255,255,0.08)' : '#f1f5f9'} />
                                    <XAxis dataKey="day" tick={{ fontSize: 11, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fontSize: 11, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} />
                                    <ReTooltip {...tooltipProps} />
                                    <Legend wrapperStyle={{ fontSize: 11 }} />
                                    <Bar dataKey="focus"   name="Focus"    fill={theme.palette.primary.main} radius={[4,4,0,0]} />
                                    <Bar dataKey="meeting" name="Meetings" fill={theme.palette.info.main} radius={[4,4,0,0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                    <Card sx={{ borderRadius: 2, height: '100%' }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                                <Typography sx={{ fontWeight: 700, fontSize: '0.85rem' }}>Attendance Heatmap</Typography>
                                <Box sx={{ display: 'flex', gap: 1 }}>
                                    {[['91%', theme.palette.success.main], ['In 9:02', theme.palette.primary.main], ['Out 18:31', theme.palette.warning.main]].map(([v,c]) => (
                                        <Typography key={v} sx={{ fontSize: '0.68rem', fontWeight: 700, color: c }}>{v}</Typography>
                                    ))}
                                </Box>
                            </Box>
                            {/* Monthly ring + heatmap side by side */}
                            <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
                                {/* Monthly donut – May 2026, mid-month (day 12) */}
                                <Box sx={{ flexShrink: 0, textAlign: 'center' }}>
                                    <Box sx={{ position: 'relative', width: 108, height: 108 }}>
                                        <ResponsiveContainer width={108} height={108}>
                                            <PieChart>
                                                <Pie
                                                    data={[
                                                        { name: 'Present',          value: 9 },
                                                        { name: 'Holiday/Weekend',  value: 7 },
                                                        { name: 'Leave',            value: 1 },
                                                        { name: 'Upcoming',         value: 13 },
                                                    ]}
                                                    cx="50%" cy="50%"
                                                    innerRadius={34} outerRadius={50}
                                                    paddingAngle={2}
                                                    dataKey="value"
                                                    startAngle={90} endAngle={-270}
                                                >
                                                    {attColors.map((c, i) => <Cell key={i} fill={c} stroke="none" />)}
                                                </Pie>
                                                <ReTooltip {...tooltipProps} formatter={(val, name) => [`${val} days`, name]} />
                                            </PieChart>
                                        </ResponsiveContainer>
                                        {/* Centre label */}
                                        <Box sx={{
                                            position: 'absolute', top: '50%', left: '50%',
                                            transform: 'translate(-50%,-50%)',
                                            textAlign: 'center', pointerEvents: 'none',
                                        }}>
                                            <Typography sx={{ fontWeight: 800, fontSize: '1.05rem', lineHeight: 1, color: theme.palette.success.main }}>12</Typography>
                                            <Typography sx={{ fontSize: '0.55rem', color: 'text.disabled', lineHeight: 1.2 }}>May</Typography>
                                        </Box>
                                    </Box>
                                    {/* Legend */}
                                    <Stack spacing={0.3} sx={{ mt: 0.5 }}>
                                        {[
                                            { label: 'Present',         val: '9d',  color: theme.palette.success.main },
                                            { label: 'Holiday/Weekend', val: '7d',  color: theme.palette.info.main },
                                            { label: 'Leave',           val: '1d',  color: theme.palette.error.main },
                                            { label: 'Upcoming',        val: '13d', color: theme.palette.text.disabled },
                                        ].map(l => (
                                            <Box key={l.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5, justifyContent: 'flex-start' }}>
                                                <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: l.color, flexShrink: 0 }} />
                                                <Typography sx={{ fontSize: '0.6rem', color: 'text.secondary', flex: 1 }}>{l.label}</Typography>
                                                <Typography sx={{ fontSize: '0.62rem', fontWeight: 700, color: l.color }}>{l.val}</Typography>
                                            </Box>
                                        ))}
                                    </Stack>
                                </Box>
                                {/* Heatmap */}
                                <Box sx={{ flex: 1, minWidth: 0 }}>
                                    <MiniHeatmap data={heatmap} streakDays={14} />
                                </Box>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* ROW 3: Trend chart + Rank + AI Insights */}
            <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 5 }}>
                    <Card sx={{ borderRadius: 2 }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 1 }}>Productivity Trend (8 wks)</Typography>
                            <ResponsiveContainer width="100%" height={125}>
                                <ComposedChart data={weeklyProductivity} margin={{ top: 2, right: 4, bottom: 0, left: -20 }}>
                                    <defs>
                                        <linearGradient id="sg2" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%"  stopColor={theme.palette.primary.main} stopOpacity={0.15} />
                                            <stop offset="95%" stopColor={theme.palette.primary.main} stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? 'rgba(255,255,255,0.08)' : '#f1f5f9'} />
                                    <XAxis dataKey="week" tick={{ fontSize: 11, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fontSize: 11, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} />
                                    <ReTooltip {...tooltipProps} />
                                    <Legend wrapperStyle={{ fontSize: 11 }} />
                                    <Area type="monotone" dataKey="score" name="Score" fill="url(#sg2)" stroke={theme.palette.primary.main} strokeWidth={2.5} />
                                    <Bar   dataKey="tasks" name="Tasks" fill={theme.palette.info.main} radius={[4,4,0,0]} barSize={9} />
                                </ComposedChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 3 }}>
                    <Card sx={{ borderRadius: 2, height: '100%' }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 1.2 }}>Rank & Patterns</Typography>
                            <Stack spacing={1}>
                                {[
                                    { label: 'Dept Rank',  value: '#4 / 17',   color: '#4f46e5' },
                                    { label: 'Company',    value: 'Top 8%',    color: '#10b981' },
                                    { label: 'Best Day',   value: 'Tuesday',   color: '#f59e0b' },
                                    { label: 'Peak Time',  value: '11 – 1 PM', color: '#8b5cf6' },
                                ].map(r => (
                                    <Box key={r.label} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 1.2, py: 0.7, borderRadius: 2, bgcolor: 'action.hover' }}>
                                        <Typography sx={{ fontSize: '0.75rem' }} color="text.secondary">{r.label}</Typography>
                                        <Typography sx={{ fontWeight: 800, color: getThemeColor(r.color), fontSize: '0.82rem' }}>{r.value}</Typography>
                                    </Box>
                                ))}
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                    <Card sx={{ borderRadius: 2, height: '100%', background: 'linear-gradient(135deg,#0f172a,#1e293b)', color: 'white' }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', color: 'white' }}>AI Insights</Typography>
                                <Chip label="6 signals" size="small" sx={{ height: 18, fontSize: '0.65rem', bgcolor: '#4f46e5', color: 'white', '& .MuiChip-label': { px: 0.8 } }} />
                            </Box>
                            <Stack spacing={0.8}>
                                {[
                                    { type: 'success', text: 'Completed 18% more tasks this week.' },
                                    { type: 'tip',     text: 'Peaks 11 AM–1 PM. Block for deep work.' },
                                    { type: 'warning', text: 'Meeting load 42% — above optimal.' },
                                    { type: 'success', text: 'Best performance on Tuesdays (94%).' },
                                    { type: 'tip',     text: '14-day streak! Top 15% consistency.' },
                                    { type: 'tip',     text: '5 tasks away from productivity score 85.' },
                                ].map((ins, i) => (
                                    <Box key={i} sx={{
                                        px: 1, py: 0.7, borderRadius: 1.5,
                                        bgcolor: ins.type === 'success' ? 'rgba(16,185,129,0.12)' : ins.type === 'warning' ? 'rgba(245,158,11,0.12)' : 'rgba(139,92,246,0.12)',
                                        borderLeft: `3px solid ${ins.type === 'success' ? '#10b981' : ins.type === 'warning' ? '#f59e0b' : '#8b5cf6'}`,
                                    }}>
                                        <Typography sx={{ fontSize: '0.75rem', opacity: 0.9, lineHeight: 1.4, color: 'white' }}>{ins.text}</Typography>
                                    </Box>
                                ))}
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

        </Box>
    );
}

// ─── VIEW: TEAM ANALYTICS ────────────────────────────────────

function TeamAnalyticsView() {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';

    const kpis = [
        { title: 'Team Productivity', value: '79', unit: '/100',    trend: 'up',     trendLabel: '+5% this month' },
        { title: 'Task Completion',   value: '84', unit: '%',       trend: 'up',     trendLabel: '+11% this month' },
        { title: 'Active Members',    value: '15', unit: '/ 17',    trend: 'stable', trendLabel: '2 on leave' },
        { title: 'Overloaded',        value: '3',  unit: 'members', trend: 'down',   trendLabel: '-1 vs last wk' },
        { title: 'Avg Response',      value: '1.4',unit: 'hrs',     trend: 'up',     trendLabel: '18% faster' },
        { title: 'Team Streak',       value: '7',  unit: 'days',    trend: 'up',     trendLabel: 'Full attendance' },
    ];

    const tooltipProps = {
        contentStyle: {
            backgroundColor: theme.palette.background.paper,
            borderColor: theme.palette.divider,
            color: theme.palette.text.primary,
        },
        itemStyle: {
            color: theme.palette.text.primary,
        },
    };

    const getWorkloadColor = (c) => {
        if (c === '#ef4444') return theme.palette.error.main;
        if (c === '#10b981') return theme.palette.success.main;
        if (c === '#f59e0b') return theme.palette.warning.main;
        return c;
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* KPI flex row */}
            <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
                {kpis.map(k => (
                    <Box key={k.title} sx={{ flex: '1 1 130px', minWidth: 120 }}>
                        <KPI {...k} />
                    </Box>
                ))}
            </Box>

            {/* Leaderboard + Workload */}
            <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 8 }}>
                    <Card sx={{ borderRadius: 2 }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 1 }}>Team Leaderboard</Typography>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            {['#','Employee','Score','Tasks','Att.',''].map(h => (
                                                <TableCell key={h} sx={{ fontWeight: 700, fontSize: '0.72rem', color: 'text.secondary', py: 0.75, px: 1 }}>{h}</TableCell>
                                            ))}
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {teamMembers.map(m => (
                                            <TableRow key={m.rank} sx={{ bgcolor: m.isMe ? alpha(theme.palette.primary.main, 0.08) : 'transparent', '&:hover': { bgcolor: 'action.hover' } }}>
                                                <TableCell sx={{ px: 1, py: 0.6 }}>
                                                    <Typography sx={{ fontWeight: 800, fontSize: '0.8rem', color: m.rank <= 3 ? theme.palette.warning.main : 'text.primary' }}>
                                                        {m.rank <= 3 ? ['🥇','🥈','🥉'][m.rank-1] : m.rank}
                                                    </Typography>
                                                </TableCell>
                                                <TableCell sx={{ px: 1, py: 0.6 }}>
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                                                        <Avatar sx={{ width: 24, height: 24, fontSize: '0.62rem', bgcolor: m.isMe ? 'primary.main' : 'action.disabledBackground' }}>{m.av}</Avatar>
                                                        <Typography sx={{ fontWeight: m.isMe ? 700 : 400, fontSize: '0.8rem' }}>
                                                            {m.name}{m.isMe ? ' (You)' : ''}
                                                        </Typography>
                                                    </Box>
                                                </TableCell>
                                                <TableCell sx={{ px: 1, py: 0.6 }}>
                                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                                                        <Box sx={{ width: 50, height: 5, borderRadius: 2, bgcolor: 'divider', overflow: 'hidden' }}>
                                                            <Box sx={{ height: '100%', width: `${m.score}%`, bgcolor: m.score >= 90 ? theme.palette.success.main : m.score >= 80 ? theme.palette.primary.main : theme.palette.warning.main, borderRadius: 2 }} />
                                                        </Box>
                                                        <Typography sx={{ fontWeight: 700, fontSize: '0.8rem' }}>{m.score}</Typography>
                                                    </Box>
                                                </TableCell>
                                                <TableCell sx={{ px: 1, py: 0.6 }}><Typography sx={{ fontSize: '0.8rem' }}>{m.tasks}</Typography></TableCell>
                                                <TableCell sx={{ px: 1, py: 0.6 }}>
                                                    <Chip label={`${m.att}%`} size="small" sx={{
                                                        height: 18, fontSize: '0.65rem', fontWeight: 700,
                                                        bgcolor: m.att >= 95
                                                            ? alpha(theme.palette.success.main, 0.15)
                                                            : m.att >= 90
                                                                ? alpha(theme.palette.warning.main, 0.15)
                                                                : alpha(theme.palette.error.main, 0.15),
                                                        color: m.att >= 95
                                                            ? (theme.palette.mode === 'dark' ? theme.palette.success.light : theme.palette.success.dark)
                                                            : m.att >= 90
                                                                ? (theme.palette.mode === 'dark' ? theme.palette.warning.light : theme.palette.warning.dark)
                                                                : (theme.palette.mode === 'dark' ? theme.palette.error.light : theme.palette.error.dark),
                                                    }} />
                                                </TableCell>
                                                <TableCell sx={{ px: 1, py: 0.6 }}><TrendIcon t={m.t} /></TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </CardContent>
                    </Card>
                </Grid>

                <Grid size={{ xs: 12, sm: 4 }}>
                    <Stack spacing={2} sx={{ height: '100%' }}>
                        <Card sx={{ borderRadius: 2, flex: 1 }}>
                            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                                <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 1 }}>Workload Distribution</Typography>
                                <ResponsiveContainer width="100%" height={100}>
                                    <PieChart>
                                        <Pie data={[{name:'Overloaded',value:3},{name:'Balanced',value:12},{name:'Underutilized',value:2}]}
                                            cx="50%" cy="50%" innerRadius={28} outerRadius={46} paddingAngle={4} dataKey="value">
                                            {[theme.palette.error.main, theme.palette.success.main, theme.palette.warning.main].map((c,i) => <Cell key={i} fill={c} />)}
                                        </Pie>
                                        <ReTooltip {...tooltipProps} />
                                    </PieChart>
                                </ResponsiveContainer>
                                {[{n:'Overloaded',v:3,c:'#ef4444'},{n:'Balanced',v:12,c:'#10b981'},{n:'Underutilized',v:2,c:'#f59e0b'}].map(w => (
                                    <Box key={w.n} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.7 }}>
                                            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: getWorkloadColor(w.c) }} />
                                            <Typography sx={{ fontSize: '0.75rem' }}>{w.n}</Typography>
                                        </Box>
                                        <Typography sx={{ fontWeight: 700, fontSize: '0.78rem' }}>{w.v}</Typography>
                                    </Box>
                                ))}
                            </CardContent>
                        </Card>
                        <Card sx={{ borderRadius: 2 }}>
                            <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
                                <Box sx={{
                                    p: 1.2,
                                    borderRadius: 2,
                                    bgcolor: alpha(theme.palette.warning.main, 0.15),
                                    border: '1px solid',
                                    borderColor: alpha(theme.palette.warning.main, 0.3)
                                }}>
                                    <Typography sx={{
                                        color: theme.palette.mode === 'dark' ? theme.palette.warning.light : theme.palette.warning.dark,
                                        fontWeight: 700,
                                        fontSize: '0.75rem',
                                        lineHeight: 1.5
                                    }}>
                                        ⚠️ Deepa Nair & Amit Kumar showing burnout signals — consider rebalancing workload
                                    </Typography>
                                </Box>
                            </CardContent>
                        </Card>
                    </Stack>
                </Grid>
            </Grid>

            {/* Team trend */}
            <Card sx={{ borderRadius: 2 }}>
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 1 }}>Team Productivity Trend</Typography>
                    <ResponsiveContainer width="100%" height={130}>
                        <ComposedChart data={weeklyProductivity} margin={{ top: 2, right: 4, bottom: 0, left: -20 }}>
                            <defs>
                                <linearGradient id="tsg2" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%"  stopColor={theme.palette.primary.main} stopOpacity={0.14} />
                                    <stop offset="95%" stopColor={theme.palette.primary.main} stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? 'rgba(255,255,255,0.08)' : '#f1f5f9'} />
                            <XAxis dataKey="week" tick={{ fontSize: 11, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} />
                            <YAxis tick={{ fontSize: 11, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} />
                            <ReTooltip {...tooltipProps} />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Area type="monotone" dataKey="score" name="Productivity Score" fill="url(#tsg2)" stroke={theme.palette.primary.main} strokeWidth={2.5} />
                            <Bar   dataKey="tasks" name="Tasks Done" fill={theme.palette.success.main} radius={[4,4,0,0]} barSize={9} />
                        </ComposedChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </Box>
    );
}

// ─── VIEW: COMPANY INSIGHTS ──────────────────────────────────

function CompanyView() {
    const theme = useTheme();
    const isDark = theme.palette.mode === 'dark';

    const tooltipProps = {
        contentStyle: {
            backgroundColor: theme.palette.background.paper,
            borderColor: theme.palette.divider,
            color: theme.palette.text.primary,
        },
        itemStyle: {
            color: theme.palette.text.primary,
        },
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Health hero */}
            <Card sx={{ borderRadius: 2, background: 'linear-gradient(135deg,#0f172a,#1e1b4b)', color: 'white' }}>
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Grid container spacing={2} alignItems="center">
                        <Grid size={{ xs: 12, sm: 2 }} sx={{ textAlign: 'center' }}>
                            <Typography sx={{ opacity: 0.5, fontSize: '0.7rem', textTransform: 'uppercase', display: 'block', mb: 0.8, color: 'white' }}>Workforce Health</Typography>
                            <Box sx={{
                                width: 80, height: 80, borderRadius: '50%', mx: 'auto',
                                background: `conic-gradient(${theme.palette.success.main} 0% 74%, rgba(255,255,255,0.1) 74% 100%)`,
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                            }}>
                                <Box sx={{ width: 62, height: 62, borderRadius: '50%', bgcolor: '#0f172a', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                                    <Typography sx={{ fontWeight: 800, color: theme.palette.success.main, fontSize: '1.3rem', lineHeight: 1 }}>74</Typography>
                                    <Typography sx={{ opacity: 0.35, color: 'white', fontSize: '0.6rem' }}>/100</Typography>
                                </Box>
                            </Box>
                            <Chip label="Good" size="small" sx={{ mt: 0.8, bgcolor: alpha(theme.palette.success.main, 0.2), color: theme.palette.success.main, fontWeight: 700, fontSize: '0.65rem' }} />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 10 }}>
                            <Box sx={{ display: 'flex', gap: 1.2, flexWrap: 'wrap' }}>
                                {[
                                    ['Active','142 / 158','#a5f3fc'],
                                    ['Avg Productivity','79 / 100','#bbf7d0'],
                                    ['Attendance','91.3%','#fde68a'],
                                    ['High Performers','28 emp','#ddd6fe'],
                                    ['Burnout Risk','12 emp','#fca5a5'],
                                    ['Attrition Risk','7 emp','#fbcfe8'],
                                ].map(([lbl,val,c]) => (
                                    <Box key={lbl} sx={{ flex: '1 1 120px', p: 1.2, borderRadius: 2, bgcolor: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.09)' }}>
                                        <Typography sx={{ opacity: 0.5, display: 'block', fontSize: '0.68rem', color: 'white', mb: 0.3 }}>{lbl}</Typography>
                                        <Typography sx={{ fontWeight: 700, color: c, fontSize: '0.85rem' }}>{val}</Typography>
                                    </Box>
                                ))}
                            </Box>
                        </Grid>
                    </Grid>
                </CardContent>
            </Card>

            {/* Dept comparison + Attrition */}
            <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 7 }}>
                    <Card sx={{ borderRadius: 2 }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 1 }}>Department Comparison</Typography>
                            <ResponsiveContainer width="100%" height={170}>
                                <BarChart data={deptComparison} barSize={10} barGap={3} margin={{ top: 2, right: 4, bottom: 0, left: -20 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? 'rgba(255,255,255,0.08)' : '#f1f5f9'} />
                                    <XAxis dataKey="dept" tick={{ fontSize: 10, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} />
                                    <YAxis tick={{ fontSize: 11, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} domain={[60,100]} />
                                    <ReTooltip {...tooltipProps} />
                                    <Legend wrapperStyle={{ fontSize: 11 }} />
                                    <Bar dataKey="productivity" name="Productivity" fill={theme.palette.primary.main} radius={[4,4,0,0]} />
                                    <Bar dataKey="attendance"   name="Attendance"   fill={theme.palette.success.main} radius={[4,4,0,0]} />
                                    <Bar dataKey="tasks"        name="Execution"    fill={theme.palette.warning.main} radius={[4,4,0,0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </CardContent>
                    </Card>
                </Grid>
                <Grid size={{ xs: 12, sm: 5 }}>
                    <Card sx={{ borderRadius: 2, height: '100%' }}>
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                            <Typography sx={{ fontWeight: 700, fontSize: '0.85rem', mb: 1.2 }}>Attrition Risk</Typography>
                            <Stack spacing={1}>
                                {attritionRisk.map(a => (
                                    <Box key={a.name} sx={{ p: 1.2, borderRadius: 2, bgcolor: 'action.hover' }}>
                                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.4 }}>
                                            <Typography sx={{ fontWeight: 700, fontSize: '0.8rem' }}>{a.name}</Typography>
                                            <Chip label={`${a.risk}%`} size="small" sx={{
                                                height: 18, fontSize: '0.65rem', fontWeight: 700,
                                                bgcolor: a.risk >= 70
                                                    ? alpha(theme.palette.error.main, 0.15)
                                                    : a.risk >= 50
                                                        ? alpha(theme.palette.warning.main, 0.15)
                                                        : alpha(theme.palette.success.main, 0.15),
                                                color: a.risk >= 70
                                                    ? (isDark ? theme.palette.error.light : theme.palette.error.dark)
                                                    : a.risk >= 50
                                                        ? (isDark ? theme.palette.warning.light : theme.palette.warning.dark)
                                                        : (isDark ? theme.palette.success.light : theme.palette.success.dark),
                                            }} />
                                        </Box>
                                        <Typography sx={{ fontSize: '0.72rem' }} color="text.secondary">{a.reason}</Typography>
                                        <Box sx={{ height: 4, borderRadius: 2, bgcolor: 'divider', mt: 0.6, overflow: 'hidden' }}>
                                            <Box sx={{ height: '100%', width: `${a.risk}%`, bgcolor: a.risk >= 70 ? theme.palette.error.main : a.risk >= 50 ? theme.palette.warning.main : theme.palette.success.main, borderRadius: 2 }} />
                                        </Box>
                                    </Box>
                                ))}
                            </Stack>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>

            {/* Cost vs Productivity */}
            <Card sx={{ borderRadius: 2 }}>
                <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1, flexWrap: 'wrap', gap: 1 }}>
                        <Typography sx={{ fontWeight: 700, fontSize: '0.85rem' }}>Cost vs Productivity (Oct 2025 – May 2026)</Typography>
                        <Chip label="Payroll +28% vs Output +12%" size="small" sx={{
                            bgcolor: alpha(theme.palette.error.main, 0.15),
                            color: isDark ? theme.palette.error.light : theme.palette.error.dark,
                            fontWeight: 600,
                            fontSize: '0.68rem'
                        }} />
                    </Box>
                    <ResponsiveContainer width="100%" height={140}>
                        <LineChart data={orgTrends} margin={{ top: 2, right: 4, bottom: 0, left: -20 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={isDark ? 'rgba(255,255,255,0.08)' : '#f1f5f9'} />
                            <XAxis dataKey="month" tick={{ fontSize: 11, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} />
                            <YAxis tick={{ fontSize: 11, fill: theme.palette.text.secondary }} axisLine={false} tickLine={false} />
                            <ReTooltip {...tooltipProps} />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Line type="monotone" dataKey="output"  name="Output Index"  stroke={theme.palette.success.main} strokeWidth={2.5} dot={{ r: 3 }} />
                            <Line type="monotone" dataKey="payroll" name="Payroll Index"  stroke={theme.palette.error.main} strokeWidth={2.5} dot={{ r: 3 }} strokeDasharray="5 3" />
                        </LineChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </Box>
    );
}

// ─── MAIN PAGE ────────────────────────────────────────────────

const VIEWS = [
    { id: 'my',      label: 'My Analytics' },
    { id: 'team',    label: 'Team'          },
    { id: 'company', label: 'Company'       },
];

export default function DeskAnalyticsPage() {
    const [view, setView] = useState('my');
    const subtitles = {
        my:      'Arjun Patel – Engineering – May 2026',
        team:    'Engineering Pod A – 17 members – May 2026',
        company: 'Organisation – 158 employees – May 2026',
    };

    return (
        <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {/* Top bar */}
            <Box sx={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                px: 2.5, py: 1.2, borderBottom: 1, borderColor: 'divider', flexShrink: 0,
            }}>
                <Box>
                    <Typography variant="subtitle1" sx={{ fontWeight: 800, fontSize: '1.05rem', lineHeight: 1.2 }}>
                        {VIEWS.find(v => v.id === view)?.label}
                    </Typography>
                    <Typography sx={{ fontSize: '0.75rem' }} color="text.secondary">
                        {subtitles[view]}
                    </Typography>
                </Box>
                <ToggleButtonGroup
                    value={view}
                    exclusive
                    onChange={(_, v) => v && setView(v)}
                    size="small"
                    sx={{
                        '& .MuiToggleButton-root': {
                            px: 2, py: 0.6, fontSize: '0.8rem', fontWeight: 600, textTransform: 'none',
                            border: '1px solid', borderColor: 'divider',
                            borderRadius: '8px !important', mx: 0.3,
                            '&.Mui-selected': { bgcolor: 'primary.main', color: 'white', borderColor: 'primary.main' },
                        },
                    }}
                >
                    {VIEWS.map(v => (
                        <ToggleButton key={v.id} value={v.id}>{v.label}</ToggleButton>
                    ))}
                </ToggleButtonGroup>
            </Box>

            {/* Scrollable content */}
            <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
                {view === 'my'      && <MyAnalyticsView />}
                {view === 'team'    && <TeamAnalyticsView />}
                {view === 'company' && <CompanyView />}
            </Box>
        </Box>
    );
}
