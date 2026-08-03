import React, { useState, useMemo } from 'react';
import {
    Box, Grid, Paper, Typography, Select, MenuItem, FormControl, InputLabel,
    Chip, Stack, Avatar, Divider, ToggleButtonGroup, ToggleButton, Tooltip,
    LinearProgress, Card, CardContent, useTheme,
    Dialog, DialogTitle, DialogContent, IconButton,
    Table, TableHead, TableBody, TableRow, TableCell, TableContainer,
    Popover,
} from '@mui/material';
import {
    ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as ReTooltip,
    LineChart, Line, PieChart, Pie, Cell, RadarChart, Radar, PolarGrid,
    PolarAngleAxis, PolarRadiusAxis, AreaChart, Area, ScatterChart, Scatter,
    Legend,
} from 'recharts';
import PeopleAltIcon from '@mui/icons-material/PeopleAlt';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import AttachMoneyIcon from '@mui/icons-material/AttachMoney';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import LocalFireDepartmentIcon from '@mui/icons-material/LocalFireDepartment';
import SentimentSatisfiedAltIcon from '@mui/icons-material/SentimentSatisfiedAlt';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SpeedIcon from '@mui/icons-material/Speed';
import CloseIcon from '@mui/icons-material/Close';

// ─── Attendance employee lists (mock data) ──────────────────────────────────
const ATTENDANCE_LISTS = {
    lateLogin: [
        { name: 'Ravi Sharma', dept: 'Tech', loginTime: '9:47 AM' },
        { name: 'Neha Gupta', dept: 'Marketing', loginTime: '10:02 AM' },
        { name: 'Amit Verma', dept: 'Sales', loginTime: '9:38 AM' },
        { name: 'Priya Joshi', dept: 'HR', loginTime: '9:55 AM' },
        { name: 'Siddharth Rao', dept: 'Finance', loginTime: '10:15 AM' },
        { name: 'Kavita Singh', dept: 'Operations', loginTime: '9:41 AM' },
        { name: 'Deepak Nair', dept: 'Tech', loginTime: '10:30 AM' },
    ],
    lateLogout: [
        { name: 'Apoorva Dixit', dept: 'Tech', logoutTime: '8:12 PM' },
        { name: 'Rohan Mehta', dept: 'Finance', logoutTime: '7:45 PM' },
        { name: 'Ankit Kumar', dept: 'Operations', logoutTime: '9:05 PM' },
        { name: 'Sneha Patil', dept: 'Marketing', logoutTime: '7:20 PM' },
        { name: 'Vikram Bose', dept: 'Tech', logoutTime: '8:50 PM' },
        { name: 'Ritika Sharma', dept: 'Sales', logoutTime: '7:35 PM' },
    ],
    absent: [
        { name: 'Manish Tiwari', dept: 'HR', reason: 'Sick Leave' },
        { name: 'Pooja Agarwal', dept: 'Finance', reason: 'Planned Leave' },
        { name: 'Rahul Dubey', dept: 'Tech', reason: 'Personal Leave' },
        { name: 'Sunita Menon', dept: 'Operations', reason: 'Sick Leave' },
        { name: 'Gaurav Khanna', dept: 'Marketing', reason: 'Unplanned Absence' },
        { name: 'Divya Reddy', dept: 'Sales', reason: 'Sick Leave' },
        { name: 'Abhishek Pandey', dept: 'Tech', reason: 'Planned Leave' },
        { name: 'Hema Iyer', dept: 'HR', reason: 'Personal Leave' },
        { name: 'Nikhil Soni', dept: 'Finance', reason: 'Unplanned Absence' },
        { name: 'Tanvi Kulkarni', dept: 'Operations', reason: 'Sick Leave' },
        { name: 'Aakash Jain', dept: 'Marketing', reason: 'Planned Leave' },
        { name: 'Shruti Bhat', dept: 'Sales', reason: 'Sick Leave' },
    ],
    wfh: [
        { name: 'Priya Singh', dept: 'Tech', since: 'May 8' },
        { name: 'Rohit Chandra', dept: 'Finance', since: 'May 9' },
        { name: 'Meera Nambiar', dept: 'HR', since: 'May 10' },
        { name: 'Suresh Pillai', dept: 'Operations', since: 'May 7' },
        { name: 'Anjali Kapoor', dept: 'Marketing', since: 'May 11' },
        { name: 'Karan Malhotra', dept: 'Tech', since: 'May 11' },
    ],
    lateComing: [
        { name: 'Ravi Sharma', dept: 'Tech', occurrences: 4 },
        { name: 'Neha Gupta', dept: 'Marketing', occurrences: 3 },
        { name: 'Amit Verma', dept: 'Sales', occurrences: 5 },
        { name: 'Kavita Singh', dept: 'Operations', occurrences: 2 },
        { name: 'Deepak Nair', dept: 'Tech', occurrences: 6 },
        { name: 'Priya Joshi', dept: 'HR', occurrences: 2 },
        { name: 'Siddharth Rao', dept: 'Finance', occurrences: 3 },
        { name: 'Ananya Das', dept: 'Marketing', occurrences: 4 },
        { name: 'Vikash Mishra', dept: 'Sales', occurrences: 5 },
        { name: 'Leena Thomas', dept: 'Tech', occurrences: 2 },
        { name: 'Mohit Aggarwal', dept: 'Operations', occurrences: 3 },
        { name: 'Sakshi Gupta', dept: 'HR', occurrences: 1 },
        { name: 'Arjun Pillai', dept: 'Finance', occurrences: 2 },
        { name: 'Ishita Goel', dept: 'Tech', occurrences: 4 },
        { name: 'Rajat Saxena', dept: 'Marketing', occurrences: 3 },
        { name: 'Nandini Batra', dept: 'Sales', occurrences: 2 },
    ],
};

// ─── Problem area employee lists ─────────────────────────────────────────────
const RISK_EMPLOYEES = {
    Operations: {
        summary: 'Overloaded team with high task overdue rate.',
        employees: [
            { name: 'Ankit Kumar',   role: 'Ops Lead',      overdueTask: 7,  workload: '94%', status: 'Overloaded' },
            { name: 'Meena Pillai',  role: 'Coordinator',   overdueTask: 5,  workload: '88%', status: 'At Risk' },
            { name: 'Suresh Pillai', role: 'Field Manager',  overdueTask: 4,  workload: '85%', status: 'At Risk' },
            { name: 'Faisal Khan',   role: 'Analyst',       overdueTask: 3,  workload: '79%', status: 'Moderate' },
        ],
    },
    Finance: {
        summary: 'Highest number of overdue tasks across all departments.',
        employees: [
            { name: 'Amit Jain',      role: 'Finance Exec',  overdueTask: 9,  workload: '81%', status: 'Critical' },
            { name: 'Harsh Malhotra', role: 'Accountant',    overdueTask: 6,  workload: '76%', status: 'At Risk' },
            { name: 'Priya Singh',    role: 'Analyst',       overdueTask: 4,  workload: '70%', status: 'Moderate' },
            { name: 'Nikhil Soni',    role: 'Tax Consultant', overdueTask: 3, workload: '65%', status: 'Moderate' },
        ],
    },
    HR: {
        summary: 'Low productivity score with slow task turnaround times.',
        employees: [
            { name: 'Deepak Sharma', role: 'HR Exec',       overdueTask: 5,  workload: '72%', status: 'At Risk' },
            { name: 'Meera Nambiar', role: 'Recruiter',     overdueTask: 3,  workload: '68%', status: 'Moderate' },
            { name: 'Lalita Kumar',  role: 'HR Manager',    overdueTask: 2,  workload: '62%', status: 'Moderate' },
            { name: 'Sakshi Gupta',  role: 'HR Analyst',    overdueTask: 1,  workload: '55%', status: 'Low' },
        ],
    },
};

const STATUS_COLOR = { Critical: '#f43f5e', Overloaded: '#f43f5e', 'At Risk': '#fb923c', Moderate: '#f59e0b', Low: '#10b981' };

// ─── Red Zone data ────────────────────────────────────────────────────────────
const RED_ZONE = {
    lowAttendance: [
        { name: 'Meena Pillai',   dept: 'Operations', avg: 32, trend: '↓ -8% vs last month' },
        { name: 'Amit Jain',      dept: 'Finance',    avg: 49, trend: '↓ -6% vs last month' },
        { name: 'Harsh Malhotra', dept: 'Finance',    avg: 43, trend: '↓ -11% vs last month' },
        { name: 'Vikram Bose',    dept: 'Sales',      avg: 48, trend: '↓ -5% vs last month' },
        { name: 'Ankit Kumar',    dept: 'Operations', avg: 58, trend: '↓ -4% vs last month' },
        { name: 'Pooja Menon',    dept: 'Marketing',  avg: 69, trend: '↓ -7% vs last month' },
        { name: 'Deepak Sharma',  dept: 'HR',         avg: 63, trend: '→ same as last month' },
    ],
    slowTurnaround: [
        { name: 'Deepak Nair',    dept: 'Tech',       avgDays: 18.4, overdue: 6 },
        { name: 'Siddharth Rao',  dept: 'Finance',    avgDays: 16.1, overdue: 8 },
        { name: 'Pooja Agarwal',  dept: 'Finance',    avgDays: 14.7, overdue: 5 },
        { name: 'Meena Pillai',   dept: 'Operations', avgDays: 13.9, overdue: 7 },
        { name: 'Gaurav Khanna',  dept: 'Marketing',  avgDays: 12.6, overdue: 4 },
        { name: 'Ankit Kumar',    dept: 'Operations', avgDays: 11.8, overdue: 9 },
    ],
    mostOverdue: [
        { name: 'Amit Jain',      dept: 'Finance',    overdue: 9,  delayed: 14, lastActivity: '5 days ago' },
        { name: 'Ankit Kumar',    dept: 'Operations', overdue: 9,  delayed: 11, lastActivity: '3 days ago' },
        { name: 'Deepak Nair',    dept: 'Tech',       overdue: 6,  delayed: 9,  lastActivity: '2 days ago' },
        { name: 'Siddharth Rao',  dept: 'Finance',    overdue: 8,  delayed: 8,  lastActivity: '6 days ago' },
        { name: 'Meena Pillai',   dept: 'Operations', overdue: 5,  delayed: 7,  lastActivity: '4 days ago' },
        { name: 'Harsh Malhotra', dept: 'Finance',    overdue: 6,  delayed: 6,  lastActivity: '1 day ago' },
        { name: 'Gaurav Khanna',  dept: 'Marketing',  overdue: 4,  delayed: 5,  lastActivity: '7 days ago' },
    ],
    excessLeaves: [
        { name: 'Manish Tiwari',  dept: 'HR',         leaves: 9,  quota: 12, unplanned: 4 },
        { name: 'Rahul Dubey',    dept: 'Tech',       leaves: 8,  quota: 12, unplanned: 3 },
        { name: 'Nikhil Soni',    dept: 'Finance',    leaves: 8,  quota: 12, unplanned: 5 },
        { name: 'Gaurav Khanna',  dept: 'Marketing',  leaves: 7,  quota: 12, unplanned: 4 },
        { name: 'Pooja Agarwal',  dept: 'Finance',    leaves: 7,  quota: 12, unplanned: 2 },
        { name: 'Sunita Menon',   dept: 'Operations', leaves: 6,  quota: 12, unplanned: 3 },
        { name: 'Tanvi Kulkarni', dept: 'Operations', leaves: 6,  quota: 12, unplanned: 4 },
    ],
    lowProductivity: [
        { name: 'Meena Pillai',   dept: 'Operations', score: 41, tasks: 8,  completion: '44%' },
        { name: 'Vikram Bose',    dept: 'Sales',      score: 48, tasks: 11, completion: '50%' },
        { name: 'Amit Jain',      dept: 'Finance',    score: 52, tasks: 14, completion: '48%' },
        { name: 'Harsh Malhotra', dept: 'Finance',    score: 55, tasks: 12, completion: '53%' },
        { name: 'Pooja Menon',    dept: 'Marketing',  score: 57, tasks: 9,  completion: '55%' },
        { name: 'Deepak Sharma',  dept: 'HR',         score: 58, tasks: 10, completion: '57%' },
        { name: 'Ankit Kumar',    dept: 'Operations', score: 62, tasks: 16, completion: '60%' },
    ],
};

const COLORS = ['#6366f1', '#22d3ee', '#f59e0b', '#10b981', '#f43f5e', '#a78bfa', '#fb923c'];
const DEPT_COLORS = {
    Tech: '#6366f1',
    HR: '#f59e0b',
    Finance: '#10b981',
    Operations: '#f43f5e',
    Marketing: '#22d3ee',
    Sales: '#a78bfa',
};

// ─── Mock data ────────────────────────────────────────────────────────────────
const DEPARTMENTS = ['All', 'Tech', 'HR', 'Finance', 'Operations', 'Marketing', 'Sales'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const kpiData = {
    totalEmployees: 148,
    activeToday: 127,
    attendanceRate: 87,
    avgWorkingHours: 8.2,
    productivityScore: 76,
    taskCompletionRate: 82,
    payrollCost: '₹28.4L',
    attritionRisk: 9,
    burnoutRisk: 6,
    satisfactionScore: 4.1,
};

const attendanceMonthly = [
    { month: 'Jan', present: 91, absent: 6, wfh: 3 },
    { month: 'Feb', present: 88, absent: 8, wfh: 4 },
    { month: 'Mar', present: 85, absent: 10, wfh: 5 },
    { month: 'Apr', present: 90, absent: 7, wfh: 3 },
    { month: 'May', present: 87, absent: 9, wfh: 4 },
    { month: 'Jun', present: 83, absent: 12, wfh: 5 },
    { month: 'Jul', present: 89, absent: 8, wfh: 3 },
    { month: 'Aug', present: 86, absent: 10, wfh: 4 },
    { month: 'Sep', present: 88, absent: 9, wfh: 3 },
    { month: 'Oct', present: 91, absent: 6, wfh: 3 },
    { month: 'Nov', present: 84, absent: 11, wfh: 5 },
    { month: 'Dec', present: 79, absent: 15, wfh: 6 },
];

const taskTurnaround = [
    { dept: 'Tech', days: 2.4, color: DEPT_COLORS.Tech },
    { dept: 'Marketing', days: 4.8, color: DEPT_COLORS.Marketing },
    { dept: 'Sales', days: 7.1, color: DEPT_COLORS.Sales },
    { dept: 'Operations', days: 9.2, color: DEPT_COLORS.Operations },
    { dept: 'Finance', days: 11.6, color: DEPT_COLORS.Finance },
    { dept: 'HR', days: 14.3, color: DEPT_COLORS.HR },
];

const deptProductivity = [
    { dept: 'Tech', productivity: 88, workload: 72, completion: 91 },
    { dept: 'HR', productivity: 74, workload: 58, completion: 79 },
    { dept: 'Finance', productivity: 81, workload: 65, completion: 85 },
    { dept: 'Operations', productivity: 70, workload: 80, completion: 74 },
    { dept: 'Marketing', productivity: 77, workload: 61, completion: 80 },
    { dept: 'Sales', productivity: 84, workload: 76, completion: 87 },
];

const payrollVsProductivity = [
    { month: 'Jan', payroll: 22.1, productivity: 71 },
    { month: 'Feb', payroll: 22.4, productivity: 72 },
    { month: 'Mar', payroll: 23.0, productivity: 70 },
    { month: 'Apr', payroll: 23.8, productivity: 73 },
    { month: 'May', payroll: 25.2, productivity: 74 },
    { month: 'Jun', payroll: 26.0, productivity: 74 },
    { month: 'Jul', payroll: 26.5, productivity: 75 },
    { month: 'Aug', payroll: 27.0, productivity: 75 },
    { month: 'Sep', payroll: 27.6, productivity: 76 },
    { month: 'Oct', payroll: 27.9, productivity: 76 },
    { month: 'Nov', payroll: 28.1, productivity: 76 },
    { month: 'Dec', payroll: 28.4, productivity: 76 },
];

const expenseByDept = [
    { name: 'Tech', value: 34, avgSalary: 142000 },
    { name: 'HR', value: 12, avgSalary: 78000 },
    { name: 'Finance', value: 8, avgSalary: 95000 },
    { name: 'Operations', value: 22, avgSalary: 82000 },
    { name: 'Marketing', value: 15, avgSalary: 88000 },
    { name: 'Sales', value: 9, avgSalary: 91000 },
];

const expenseByCategory = [
    { month: 'Jan', Travel: 42, Food: 18, Equipment: 60, Training: 25 },
    { month: 'Feb', Travel: 38, Food: 21, Equipment: 45, Training: 30 },
    { month: 'Mar', Travel: 55, Food: 24, Equipment: 30, Training: 20 },
    { month: 'Apr', Travel: 48, Food: 19, Equipment: 70, Training: 15 },
    { month: 'May', Travel: 62, Food: 22, Equipment: 55, Training: 35 },
];

// Employee × Week attendance % (16 weeks = ~4 months)
const WEEK_LABELS = ['W1','W2','W3','W4','W5','W6','W7','W8','W9','W10','W11','W12','W13','W14','W15','W16'];

const EMPLOYEE_ATTENDANCE_DATA = [
    { name: 'Apoorva Dixit',   dept: 'Tech',       weeks: [100,100,95,100,90,100,100,95,100,100,95,100,90,100,95,100] },
    { name: 'Karan Shah',      dept: 'Tech',       weeks: [100,95,90,100,85,100,95,90,100,95,90,100,85,95,100,90] },
    { name: 'Divya Nair',      dept: 'Tech',       weeks: [95,90,100,85,90,95,100,90,85,100,90,95,100,90,85,100] },
    { name: 'Ravi Tiwari',     dept: 'Tech',       weeks: [80,75,85,70,80,75,85,65,80,70,75,80,60,70,75,65] },
    { name: 'Neha Joshi',      dept: 'Marketing',  weeks: [90,85,90,100,85,95,90,85,100,90,85,100,90,95,85,90] },
    { name: 'Pooja Menon',     dept: 'Marketing',  weeks: [75,80,70,65,75,70,80,60,75,65,70,60,55,65,70,60] },
    { name: 'Arjun Verma',     dept: 'Marketing',  weeks: [100,95,100,90,100,95,100,100,90,100,95,100,90,95,100,95] },
    { name: 'Priya Singh',     dept: 'Finance',    weeks: [95,100,90,100,95,100,90,100,95,90,100,95,100,90,100,95] },
    { name: 'Amit Jain',       dept: 'Finance',    weeks: [60,55,65,50,60,55,45,60,50,55,60,50,45,55,50,40] },
    { name: 'Sunita Rao',      dept: 'Finance',    weeks: [85,90,80,85,90,80,85,90,80,85,90,80,85,80,90,85] },
    { name: 'Ankit Kumar',     dept: 'Operations', weeks: [70,65,60,70,65,55,60,50,65,60,55,50,60,55,45,50] },
    { name: 'Meena Pillai',    dept: 'Operations', weeks: [40,35,45,30,40,35,25,40,30,35,40,30,25,35,30,20] },
    { name: 'Rohan Mehta',     dept: 'Sales',      weeks: [95,100,90,100,95,100,90,95,100,90,100,95,100,95,90,100] },
    { name: 'Sneha Gupta',     dept: 'Sales',      weeks: [80,85,75,80,85,80,75,85,80,75,85,80,75,80,85,80] },
    { name: 'Vikram Bose',     dept: 'Sales',      weeks: [55,50,60,45,55,50,40,55,45,50,55,40,50,45,40,35] },
    { name: 'Lalita Kumar',    dept: 'HR',         weeks: [90,85,95,80,90,85,90,95,80,90,85,95,80,90,85,90] },
    { name: 'Deepak Sharma',   dept: 'HR',         weeks: [65,70,60,65,70,60,65,55,70,60,65,70,55,65,60,55] },
    { name: 'Faisal Khan',     dept: 'Operations', weeks: [85,80,90,75,85,80,75,85,80,75,80,85,75,80,75,70] },
    { name: 'Tanya Batra',     dept: 'Tech',       weeks: [100,95,100,90,95,100,95,90,100,95,100,90,95,100,90,95] },
    { name: 'Harsh Malhotra',  dept: 'Finance',    weeks: [50,45,55,40,50,45,35,50,40,45,50,40,35,45,40,30] },
];

const DEPT_ATTENDANCE_DATA = Object.entries(
    EMPLOYEE_ATTENDANCE_DATA.reduce((acc, emp) => {
        if (!acc[emp.dept]) acc[emp.dept] = { weeks: Array(16).fill(0), count: 0 };
        emp.weeks.forEach((v, i) => { acc[emp.dept].weeks[i] += v; });
        acc[emp.dept].count += 1;
        return acc;
    }, {})
).map(([dept, { weeks, count }]) => ({
    name: dept,
    dept,
    weeks: weeks.map(v => Math.round(v / count)),
}));

const loginTimeData = [
    { dept: 'Tech', avgLogin: 9.1, avgLogout: 18.8 },
    { dept: 'HR', avgLogin: 9.4, avgLogout: 18.2 },
    { dept: 'Finance', avgLogin: 9.2, avgLogout: 18.5 },
    { dept: 'Operations', avgLogin: 8.8, avgLogout: 19.1 },
    { dept: 'Marketing', avgLogin: 9.6, avgLogout: 18.0 },
    { dept: 'Sales', avgLogin: 9.0, avgLogout: 19.4 },
];

const radarData = [
    { metric: 'Productivity', Tech: 88, HR: 74, Finance: 81, Operations: 70, Marketing: 77, Sales: 84 },
    { metric: 'Attendance',   Tech: 92, HR: 80, Finance: 86, Operations: 75, Marketing: 83, Sales: 89 },
    { metric: 'Task Done',    Tech: 91, HR: 79, Finance: 85, Operations: 74, Marketing: 80, Sales: 87 },
    { metric: 'Satisfaction', Tech: 82, HR: 76, Finance: 78, Operations: 68, Marketing: 80, Sales: 85 },
    { metric: 'Efficiency',   Tech: 85, HR: 70, Finance: 80, Operations: 66, Marketing: 75, Sales: 83 },
];

const topEmployees = [
    { name: 'Apoorva Dixit', dept: 'Tech', score: 94, tasks: 38 },
    { name: 'Rohan Mehta', dept: 'Sales', score: 91, tasks: 35 },
    { name: 'Priya Singh', dept: 'Finance', score: 89, tasks: 30 },
    { name: 'Ankit Kumar', dept: 'Operations', score: 87, tasks: 28 },
    { name: 'Neha Joshi', dept: 'Marketing', score: 85, tasks: 26 },
];

const aiInsights = [
    { icon: '📉', text: 'Attendance dropped 12% this week, especially on Mondays and Fridays.', severity: 'warning' },
    { icon: '⚠️', text: 'Finance department has the highest overdue tasks — 18 tasks past deadline.', severity: 'error' },
    { icon: '🌟', text: 'Apoorva Dixit shows consistently high productivity (94 score, 3 weeks running).', severity: 'success' },
    { icon: '🔥', text: '3 employees in Operations may be overloaded — workload index > 85%.', severity: 'warning' },
    { icon: '💸', text: 'Expense claims increased unusually in Operations (+34% vs last month).', severity: 'error' },
    { icon: '📈', text: 'Payroll grew 18% YoY while productivity improved only 7%. Review cost efficiency.', severity: 'info' },
];

const deptSalary = [
    { dept: 'Tech', salary: 9.8 },
    { dept: 'Sales', salary: 5.2 },
    { dept: 'Operations', salary: 4.6 },
    { dept: 'Finance', salary: 3.9 },
    { dept: 'Marketing', salary: 3.1 },
    { dept: 'HR', salary: 1.8 },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

function KpiCard({ icon, label, value, sub, color = '#6366f1', trend }) {
    return (
        <Card elevation={0} sx={{
            border: '1px solid', borderColor: 'divider',
            borderRadius: 3, height: '100%',
            background: `linear-gradient(135deg, ${color}10 0%, transparent 60%)`,
        }}>
            <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                <Stack direction="row" alignItems="flex-start" justifyContent="space-between">
                    <Box>
                        <Typography variant="caption" color="text.secondary" fontWeight={500}
                            sx={{ textTransform: 'uppercase', letterSpacing: 0.6, fontSize: 10 }}>
                            {label}
                        </Typography>
                        <Typography variant="h5" fontWeight={700} sx={{ color, mt: 0.5 }}>
                            {value}
                        </Typography>
                        {sub && (
                            <Typography variant="caption" color="text.secondary">{sub}</Typography>
                        )}
                    </Box>
                    <Avatar sx={{ bgcolor: `${color}20`, color, width: 40, height: 40, mt: 0.5 }}>
                        {icon}
                    </Avatar>
                </Stack>
                {trend !== undefined && (
                    <LinearProgress
                        variant="determinate"
                        value={trend}
                        sx={{
                            mt: 1.5, borderRadius: 4, height: 5,
                            bgcolor: `${color}20`,
                            '& .MuiLinearProgress-bar': { bgcolor: color, borderRadius: 4 },
                        }}
                    />
                )}
            </CardContent>
        </Card>
    );
}

function SectionTitle({ children }) {
    return (
        <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1.5, mt: 1 }}>
            {children}
        </Typography>
    );
}

function ChartCard({ title, children, action }) {
    return (
        <Paper elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, p: 2, height: '100%' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
                <Typography variant="subtitle2" fontWeight={700}>{title}</Typography>
                {action}
            </Stack>
            {children}
        </Paper>
    );
}

// Attendance % → green-to-red colour (high = green, low = red)
function attendanceColor(pct) {
    if (pct >= 95) return '#15803d'; // dark green
    if (pct >= 85) return '#22c55e'; // green
    if (pct >= 75) return '#84cc16'; // lime
    if (pct >= 60) return '#eab308'; // yellow
    if (pct >= 45) return '#f97316'; // orange
    return '#ef4444';                // red
}
function attendanceTextColor(pct) {
    return pct >= 60 ? '#fff' : '#fff';
}

// Cohort-style Employee × Week heatmap
function AttendanceCohortHeatmap({ rows, mode }) {
    const cellW = mode === 'dept' ? 52 : 44;
    const rowH = mode === 'dept' ? 36 : 30;
    const nameW = mode === 'dept' ? 100 : 140;
    return (
        <Box sx={{ overflowX: 'auto', overflowY: 'auto', maxHeight: 520 }}>
            {/* Header row */}
            <Box sx={{
                display: 'grid',
                gridTemplateColumns: `${nameW}px ${mode === 'dept' ? '80px ' : ''}repeat(${WEEK_LABELS.length}, ${cellW}px)`,
                gap: '2px', mb: '2px', position: 'sticky', top: 0, bgcolor: '#f8fafc', zIndex: 1,
            }}>
                <Typography variant="caption" fontWeight={700} color="text.secondary"
                    sx={{ pl: 1, alignSelf: 'center' }}>
                    {mode === 'dept' ? 'Department' : 'Employee'}
                </Typography>
                {mode === 'dept' && (
                    <Typography variant="caption" fontWeight={700} color="text.secondary" align="center"
                        sx={{ alignSelf: 'center' }}>Avg %</Typography>
                )}
                {WEEK_LABELS.map(w => (
                    <Typography key={w} variant="caption" align="center" fontWeight={700}
                        color="text.secondary" sx={{ fontSize: 10 }}>{w}</Typography>
                ))}
            </Box>

            {/* Data rows */}
            {rows.map((row, ri) => {
                const avg = Math.round(row.weeks.reduce((s, v) => s + v, 0) / row.weeks.length);
                return (
                    <Box key={ri} sx={{
                        display: 'grid',
                        gridTemplateColumns: `${nameW}px ${mode === 'dept' ? '80px ' : ''}repeat(${WEEK_LABELS.length}, ${cellW}px)`,
                        gap: '2px', mb: '2px',
                    }}>
                        {/* Row label */}
                        <Box sx={{
                            display: 'flex', flexDirection: 'column', justifyContent: 'center',
                            pl: 1, py: 0.25,
                        }}>
                            <Typography variant="caption" fontWeight={700} noWrap sx={{ fontSize: 11 }}>
                                {row.name}
                            </Typography>
                            {mode !== 'dept' && (
                                <Typography variant="caption" sx={{
                                    fontSize: 9, color: '#fff', fontWeight: 600,
                                    bgcolor: DEPT_COLORS[row.dept] || '#6366f1',
                                    borderRadius: 0.8, px: 0.6, display: 'inline-block', width: 'fit-content',
                                }}>
                                    {row.dept}
                                </Typography>
                            )}
                        </Box>

                        {/* Avg badge (dept mode) */}
                        {mode === 'dept' && (
                            <Box sx={{
                                bgcolor: attendanceColor(avg), borderRadius: 1,
                                height: rowH, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            }}>
                                <Typography sx={{ color: '#fff', fontWeight: 800, fontSize: 12 }}>
                                    {avg}%
                                </Typography>
                            </Box>
                        )}

                        {/* Week cells */}
                        {row.weeks.map((val, wi) => (
                            <Tooltip key={wi} title={`${row.name} · ${WEEK_LABELS[wi]}: ${val}% attendance`} arrow>
                                <Box sx={{
                                    bgcolor: attendanceColor(val),
                                    borderRadius: 1,
                                    height: rowH,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    cursor: 'default',
                                    transition: 'transform 0.1s',
                                    '&:hover': { transform: 'scale(1.08)', zIndex: 2, position: 'relative' },
                                }}>
                                    <Typography sx={{ color: attendanceTextColor(val), fontWeight: 700, fontSize: 10 }}>
                                        {val}%
                                    </Typography>
                                </Box>
                            </Tooltip>
                        ))}
                    </Box>
                );
            })}

            {/* Legend */}
            <Stack direction="row" spacing={1.5} mt={1.5} flexWrap="wrap" rowGap={0.5} alignItems="center">
                <Typography variant="caption" color="text.secondary" fontWeight={600}>Attendance:</Typography>
                {[
                    { label: '≥95% Excellent', color: '#15803d' },
                    { label: '85–94% Good', color: '#22c55e' },
                    { label: '75–84% Fair', color: '#84cc16' },
                    { label: '60–74% Low', color: '#eab308' },
                    { label: '45–59% Poor', color: '#f97316' },
                    { label: '<45% Critical', color: '#ef4444' },
                ].map(({ label, color }) => (
                    <Stack key={label} direction="row" spacing={0.5} alignItems="center">
                        <Box sx={{ width: 14, height: 14, borderRadius: 0.5, bgcolor: color }} />
                        <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>{label}</Typography>
                    </Stack>
                ))}
            </Stack>
        </Box>
    );
}

const INSIGHT_COLORS = { warning: '#f59e0b', error: '#f43f5e', success: '#10b981', info: '#6366f1' };
const INSIGHT_BG = { warning: '#fef9c3', error: '#fff1f2', success: '#f0fdf4', info: '#eef2ff' };

// Self-contained heatmap section with its own view-mode + dept filter
function AttendanceHeatmapSection() {
    const [heatMode, setHeatMode] = useState('employee'); // 'employee' | 'dept'
    const [heatDept, setHeatDept] = useState('All');

    const rows = useMemo(() => {
        if (heatMode === 'dept') return DEPT_ATTENDANCE_DATA;
        if (heatDept === 'All') return EMPLOYEE_ATTENDANCE_DATA;
        return EMPLOYEE_ATTENDANCE_DATA.filter(e => e.dept === heatDept);
    }, [heatMode, heatDept]);

    return (
        <Paper elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, p: 2 }}>
            <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'center' }} mb={2} spacing={1}>
                <Box>
                    <Typography variant="subtitle2" fontWeight={700}>
                        Attendance Heatmap — Employee × Week (16 weeks)
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        Green = excellent attendance · Red = poor attendance
                    </Typography>
                </Box>
                <Stack direction="row" spacing={1} flexWrap="wrap" rowGap={1}>
                    <ToggleButtonGroup
                        value={heatMode} exclusive size="small"
                        onChange={(_, v) => v && setHeatMode(v)}>
                        <ToggleButton value="employee" sx={{ px: 1.5, fontSize: 11, textTransform: 'none', fontWeight: 600 }}>
                            👤 Employee
                        </ToggleButton>
                        <ToggleButton value="dept" sx={{ px: 1.5, fontSize: 11, textTransform: 'none', fontWeight: 600 }}>
                            🏢 Department
                        </ToggleButton>
                    </ToggleButtonGroup>
                    {heatMode === 'employee' && (
                        <FormControl size="small" sx={{ minWidth: 120 }}>
                            <InputLabel>Department</InputLabel>
                            <Select value={heatDept} label="Department"
                                onChange={e => setHeatDept(e.target.value)}>
                                {DEPARTMENTS.map(d => <MenuItem key={d} value={d}>{d}</MenuItem>)}
                            </Select>
                        </FormControl>
                    )}
                </Stack>
            </Stack>
            <AttendanceCohortHeatmap rows={rows} mode={heatMode} />
        </Paper>
    );
}

// ─── Main dashboard ───────────────────────────────────────────────────────────
export default function HRAnalyticsDashboard() {
    const theme = useTheme();
    const [deptFilter, setDeptFilter] = useState('All');
    const [section, setSection] = useState('overview');
    const [attModal, setAttModal] = useState({ open: false, title: '', listKey: '' });
    const closeAttModal = () => setAttModal(m => ({ ...m, open: false }));
    const [riskAnchor, setRiskAnchor] = useState(null);
    const [riskDept, setRiskDept] = useState(null);

    // ── Filtered datasets (react to deptFilter) ───────────────────────────────
    const filtered = useMemo(() => {
        const f = deptFilter === 'All' ? null : deptFilter;
        return {
            taskTurnaround:   f ? taskTurnaround.filter(d => d.dept === f)       : taskTurnaround,
            deptProductivity: f ? deptProductivity.filter(d => d.dept === f)     : deptProductivity,
            loginTimeData:    f ? loginTimeData.filter(d => d.dept === f)        : loginTimeData,
            topEmployees:     f ? topEmployees.filter(e => e.dept === f)         : topEmployees,
            deptSalary:       f ? deptSalary.filter(d => d.dept === f)           : deptSalary,
            expenseByDept:    f ? expenseByDept.filter(d => d.name === f)        : expenseByDept,
            radarDepts:       f ? [f] : ['Tech', 'HR', 'Finance'],
            attLists: Object.fromEntries(
                Object.entries(ATTENDANCE_LISTS).map(([key, list]) => [
                    key, f ? list.filter(e => e.dept === f) : list
                ])
            ),
            redZone: Object.fromEntries(
                Object.entries(RED_ZONE).map(([key, list]) => [
                    key, f ? list.filter(e => e.dept === f) : list
                ])
            ),
        };
    }, [deptFilter]);

    const SECTIONS = [
        { key: 'overview',   label: 'Overview' },
        { key: 'attendance', label: 'Attendance' },
        { key: 'tasks',      label: 'Tasks & Productivity' },
        { key: 'payroll',    label: 'Payroll' },
        { key: 'expenses',   label: 'Expenses' },
        { key: 'insights',   label: 'AI Insights' },
        { key: 'executive',  label: 'Executive' },
        { key: 'redzone',    label: '🔴 Red Zone' },
    ];

    return (
        <Box sx={{ p: { xs: 1.5, md: 3 }, bgcolor: '#f8fafc', minHeight: '100vh' }}>
            {/* ── Header ── */}
            <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ sm: 'center' }} mb={2} spacing={1}>
                <Box>
                    <Typography variant="h5" fontWeight={800} sx={{ letterSpacing: -0.5 }}>
                        HR Analytics
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Live workforce intelligence — May 2026
                    </Typography>
                </Box>
                <Stack direction="row" spacing={1.5} flexWrap="wrap" rowGap={1}>
                    <FormControl size="small" sx={{ minWidth: 130 }}>
                        <InputLabel>Department</InputLabel>
                        <Select value={deptFilter} label="Department" onChange={e => setDeptFilter(e.target.value)}>
                            {DEPARTMENTS.map(d => <MenuItem key={d} value={d}>{d}</MenuItem>)}
                        </Select>
                    </FormControl>
                    <Chip label="May 2026" variant="outlined" size="small" sx={{ alignSelf: 'center', fontWeight: 600 }} />
                </Stack>
            </Stack>

            {/* ── Section Tabs ── */}
            <Box sx={{ mb: 2.5, overflowX: 'auto', '&::-webkit-scrollbar': { height: 4 } }}>
                <ToggleButtonGroup value={section} exclusive onChange={(_, v) => v && setSection(v)} size="small" sx={{ display: 'flex', flexWrap: 'nowrap', width: 'max-content' }}>
                    {SECTIONS.map(s => (
                        <ToggleButton key={s.key} value={s.key} sx={{ px: 1.2, py: 0.3, fontWeight: 600, fontSize: 11, textTransform: 'none', whiteSpace: 'nowrap', lineHeight: 1.4, minHeight: 28 }}>
                            {s.label}
                        </ToggleButton>
                    ))}
                </ToggleButtonGroup>
            </Box>

            {/* ══════════════════════════════════════════════════════════════════
                SECTION 1 — WORKFORCE HEALTH OVERVIEW
            ══════════════════════════════════════════════════════════════════ */}
            {section === 'overview' && (
                <>
                    {/* KPI strip — single row */}
                    <Paper elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, mb: 2.5 }}>
                        <Stack direction="row" divider={<Divider orientation="vertical" flexItem />}>
                            {[
                                { icon: <PeopleAltIcon sx={{ fontSize: 16 }} />, label: 'Employees', value: kpiData.totalEmployees, sub: 'Company size', color: '#6366f1' },
                                { icon: <CheckCircleOutlineIcon sx={{ fontSize: 16 }} />, label: 'Active Today', value: kpiData.activeToday, sub: 'Engagement', color: '#10b981' },
                                { icon: <AccessTimeIcon sx={{ fontSize: 16 }} />, label: 'Attendance', value: `${kpiData.attendanceRate}%`, sub: 'This month', color: '#22d3ee' },
                                { icon: <SpeedIcon sx={{ fontSize: 16 }} />, label: 'Avg Hrs', value: `${kpiData.avgWorkingHours}h`, sub: 'Daily avg', color: '#f59e0b' },
                                { icon: <TrendingUpIcon sx={{ fontSize: 16 }} />, label: 'Productivity', value: `${kpiData.productivityScore}`, sub: 'Efficiency', color: '#a78bfa' },
                                { icon: <CheckCircleOutlineIcon sx={{ fontSize: 16 }} />, label: 'Task Done', value: `${kpiData.taskCompletionRate}%`, sub: 'Completion', color: '#10b981' },
                                { icon: <AttachMoneyIcon sx={{ fontSize: 16 }} />, label: 'Payroll', value: kpiData.payrollCost, sub: 'This month', color: '#f43f5e' },
                                { icon: <WarningAmberIcon sx={{ fontSize: 16 }} />, label: 'Attrition', value: `${kpiData.attritionRisk}`, sub: 'At risk', color: '#fb923c' },
                                { icon: <LocalFireDepartmentIcon sx={{ fontSize: 16 }} />, label: 'Burnout', value: `${kpiData.burnoutRisk}`, sub: 'Overworked', color: '#f43f5e' },
                                { icon: <SentimentSatisfiedAltIcon sx={{ fontSize: 16 }} />, label: 'Satisfaction', value: `${kpiData.satisfactionScore}/5`, sub: 'From feedback', color: '#22d3ee' },
                            ].map((k, i) => (
                                <Box key={i} sx={{ px: 1, py: 1.2, flex: 1, minWidth: 0, background: `linear-gradient(135deg, ${k.color}0d 0%, transparent 70%)` }}>
                                    <Stack direction="row" alignItems="center" spacing={0.4} mb={0.3}>
                                        <Box sx={{ color: k.color, display: 'flex', alignItems: 'center', flexShrink: 0 }}>{k.icon}</Box>
                                        <Typography noWrap sx={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5, color: 'text.secondary', lineHeight: 1.2 }}>
                                            {k.label}
                                        </Typography>
                                    </Stack>
                                    <Typography sx={{ fontSize: 20, fontWeight: 700, color: k.color, lineHeight: 1.1 }}>
                                        {k.value}
                                    </Typography>
                                    <Typography noWrap sx={{ fontSize: 11, color: 'text.secondary', mt: 0.2 }}>{k.sub}</Typography>
                                </Box>
                            ))}
                        </Stack>
                    </Paper>

                    {/* Charts row */}
                    <Grid container spacing={2} mb={2}>
                        {/* Task turnaround by dept */}
                        <Grid size={{ xs: 12, md: 5 }}>
                            <ChartCard title="Task Turnaround by Department (days)">
                                <ResponsiveContainer width="100%" height={220}>
                                    <BarChart data={filtered.taskTurnaround} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                        <XAxis type="number" tick={{ fontSize: 11 }} unit="d" />
                                        <YAxis type="category" dataKey="dept" tick={{ fontSize: 12 }} width={70} />
                                        <ReTooltip formatter={(v) => [`${v} days`, 'Avg turnaround']} />
                                        <Bar dataKey="days" radius={[0, 6, 6, 0]}>
                                            {filtered.taskTurnaround.map((entry, i) => (
                                                <Cell key={i} fill={entry.color} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>

                        {/* Department radar */}
                        <Grid size={{ xs: 12, md: 4 }}>
                            <ChartCard title={deptFilter === 'All' ? 'Top 3 Dept Performance Radar' : `${deptFilter} — Performance Radar`}>
                                <ResponsiveContainer width="100%" height={220}>
                                    <RadarChart data={radarData}>
                                        <PolarGrid />
                                        <PolarAngleAxis dataKey="metric" tick={{ fontSize: 11 }} />
                                        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 9 }} />
                                        {filtered.radarDepts.map(dept => (
                                            <Radar key={dept} name={dept} dataKey={dept} stroke={DEPT_COLORS[dept]} fill={DEPT_COLORS[dept]} fillOpacity={0.3} />
                                        ))}
                                        <Legend iconSize={10} />
                                    </RadarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>

                        {/* Top performers */}
                        <Grid size={{ xs: 12, md: 3 }}>
                            <ChartCard title="Top Performers">
                                <Stack spacing={1}>
                                    {filtered.topEmployees.map((emp, i) => (
                                        <Stack key={i} direction="row" spacing={1.5} alignItems="center">
                                            <Avatar sx={{
                                                width: 32, height: 32, fontSize: 13, fontWeight: 700,
                                                bgcolor: COLORS[i % COLORS.length] + '20',
                                                color: COLORS[i % COLORS.length],
                                            }}>
                                                {emp.name[0]}
                                            </Avatar>
                                            <Box flex={1} minWidth={0}>
                                                <Typography variant="caption" fontWeight={700} noWrap>{emp.name}</Typography>
                                                <LinearProgress
                                                    variant="determinate"
                                                    value={emp.score}
                                                    sx={{
                                                        height: 4, borderRadius: 4, mt: 0.3,
                                                        bgcolor: COLORS[i % COLORS.length] + '20',
                                                        '& .MuiLinearProgress-bar': { bgcolor: COLORS[i % COLORS.length] },
                                                    }}
                                                />
                                            </Box>
                                            <Chip label={emp.score} size="small" sx={{
                                                fontSize: 11, fontWeight: 700, height: 20,
                                                bgcolor: COLORS[i % COLORS.length] + '15',
                                                color: COLORS[i % COLORS.length],
                                            }} />
                                        </Stack>
                                    ))}
                                </Stack>
                            </ChartCard>
                        </Grid>
                    </Grid>

                    {/* Dept productivity grouped bar */}
                    <Grid container spacing={2}>
                        <Grid size={{ xs: 12, md: 8 }}>
                            <ChartCard title="Department Productivity vs Workload vs Task Completion (%)">
                                <ResponsiveContainer width="100%" height={200}>
                                    <BarChart data={filtered.deptProductivity} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="dept" tick={{ fontSize: 11 }} />
                                        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                                        <ReTooltip />
                                        <Legend iconSize={10} />
                                        <Bar dataKey="productivity" name="Productivity" fill="#6366f1" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="workload" name="Workload" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="completion" name="Completion" fill="#10b981" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                        <Grid size={{ xs: 12, md: 4 }}>
                            <ChartCard title="Employee Distribution by Dept">
                                <ResponsiveContainer width="100%" height={200}>
                                    <PieChart>
                                        <Pie data={filtered.expenseByDept} dataKey="value" nameKey="name"
                                            cx="50%" cy="50%" innerRadius={50} outerRadius={80}
                                            paddingAngle={3}>
                                            {filtered.expenseByDept.map((entry, i) => (
                                                <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                            ))}
                                        </Pie>
                                        <ReTooltip content={({ active, payload }) => {
                                            if (!active || !payload?.length) return null;
                                            const d = payload[0].payload;
                                            return (
                                                <Box sx={{ bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider', borderRadius: 2, px: 1.5, py: 1, boxShadow: 3 }}>
                                                    <Typography sx={{ fontSize: 12, fontWeight: 700 }}>{d.name}</Typography>
                                                    <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>Share: <b style={{ color: '#6366f1' }}>{d.value}%</b></Typography>
                                                    <Typography sx={{ fontSize: 11, color: 'text.secondary' }}>Avg Salary: <b style={{ color: '#10b981' }}>₹{d.avgSalary.toLocaleString('en-IN')}</b></Typography>
                                                </Box>
                                            );
                                        }} />
                                        <Legend iconSize={10} />
                                    </PieChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                    </Grid>
                </>
            )}

            {/* ══════════════════════════════════════════════════════════════════
                SECTION 2 — ATTENDANCE INTELLIGENCE
            ══════════════════════════════════════════════════════════════════ */}
            {section === 'attendance' && (
                <>
                    {/* Attendance KPI strip — clickable cards */}
                    <Grid container spacing={1.5} mb={2.5} alignItems="stretch">
                        {[
                            { icon: <AccessTimeIcon fontSize="small" />, label: 'Avg Login Time', value: '9:11 AM', color: '#6366f1', listKey: 'lateLogin', modalTitle: 'Late Login Employees (after 9:30 AM)' },
                            { icon: <AccessTimeIcon fontSize="small" />, label: 'Avg Logout Time', value: '6:42 PM', color: '#22d3ee', listKey: 'lateLogout', modalTitle: 'Late Logout Employees (after 6:30 PM)' },
                            { icon: <WarningAmberIcon fontSize="small" />, label: 'Absenteeism %', value: '8.4%', color: '#f43f5e', listKey: 'absent', modalTitle: 'Absent Employees — May 2026' },
                            { icon: <CheckCircleOutlineIcon fontSize="small" />, label: 'WFH Rate', value: '4.1%', color: '#10b981', listKey: 'wfh', modalTitle: 'Employees on WFH' },
                            { icon: <TrendingUpIcon fontSize="small" />, label: 'Late Coming Rate', value: '11.2%', color: '#fb923c', listKey: 'lateComing', modalTitle: 'Employees with Late Coming (May 2026)' },
                        ].map((k, i) => (
                            <Grid key={i} size={{ xs: 6, sm: 4, md: 2.4 }}>
                                <Box onClick={() => setAttModal({ open: true, title: k.modalTitle, listKey: k.listKey })}
                                    sx={{ cursor: 'pointer', borderRadius: 3, height: '100%', transition: 'transform 0.15s, box-shadow 0.15s', '&:hover': { transform: 'translateY(-2px)', boxShadow: `0 0 0 2px ${k.color}50` } }}>
                                    <KpiCard {...k} />
                                </Box>
                            </Grid>
                        ))}
                    </Grid>

                    {/* Employee List Modal */}
                    {(() => {
                        const colMap = {
                            lateLogin:  [{ key: 'name', label: 'Employee' }, { key: 'dept', label: 'Department' }, { key: 'loginTime', label: 'Login Time' }],
                            lateLogout: [{ key: 'name', label: 'Employee' }, { key: 'dept', label: 'Department' }, { key: 'logoutTime', label: 'Logout Time' }],
                            absent:     [{ key: 'name', label: 'Employee' }, { key: 'dept', label: 'Department' }, { key: 'reason', label: 'Reason' }],
                            wfh:        [{ key: 'name', label: 'Employee' }, { key: 'dept', label: 'Department' }, { key: 'since', label: 'WFH Since' }],
                            lateComing: [{ key: 'name', label: 'Employee' }, { key: 'dept', label: 'Department' }, { key: 'occurrences', label: 'Occurrences (May)' }],
                        };
                        const cols = colMap[attModal.listKey] || [];
                        const employees = (filtered.attLists[attModal.listKey]) || [];
                        return (
                            <Dialog open={attModal.open} onClose={closeAttModal} maxWidth="sm" fullWidth>
                                <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
                                    <Typography fontWeight={700} fontSize={15}>{attModal.title}</Typography>
                                    <IconButton size="small" onClick={closeAttModal}><CloseIcon fontSize="small" /></IconButton>
                                </DialogTitle>
                                <DialogContent sx={{ p: 0 }}>
                                    <TableContainer>
                                        <Table size="small">
                                            <TableHead>
                                                <TableRow sx={{ bgcolor: '#f8fafc' }}>
                                                    {cols.map(c => (
                                                        <TableCell key={c.key} sx={{ fontWeight: 700, fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5, color: 'text.secondary' }}>{c.label}</TableCell>
                                                    ))}
                                                </TableRow>
                                            </TableHead>
                                            <TableBody>
                                                {employees.map((emp, idx) => (
                                                    <TableRow key={idx} hover>
                                                        {cols.map(c => (
                                                            <TableCell key={c.key} sx={{ fontSize: 13 }}>{emp[c.key]}</TableCell>
                                                        ))}
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                </DialogContent>
                            </Dialog>
                        );
                    })()}

                    <Grid container spacing={2} mb={2}>
                        {/* Monthly trend */}
                        <Grid size={{ xs: 12, md: 7 }}>
                            <ChartCard title="Monthly Attendance Trend (%)">
                                <ResponsiveContainer width="100%" height={230}>
                                    <AreaChart data={attendanceMonthly} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                        <defs>
                                            <linearGradient id="gPresent" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                            </linearGradient>
                                            <linearGradient id="gAbsent" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                                            </linearGradient>
                                            <linearGradient id="gWfh" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                                        <YAxis unit="%" tick={{ fontSize: 11 }} />
                                        <ReTooltip />
                                        <Legend iconSize={10} />
                                        <Area type="monotone" dataKey="present" name="Present" stroke="#10b981" fill="url(#gPresent)" strokeWidth={2} />
                                        <Area type="monotone" dataKey="absent" name="Absent" stroke="#f43f5e" fill="url(#gAbsent)" strokeWidth={2} />
                                        <Area type="monotone" dataKey="wfh" name="WFH" stroke="#6366f1" fill="url(#gWfh)" strokeWidth={2} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>

                        {/* Login / logout by dept */}
                        <Grid size={{ xs: 12, md: 5 }}>
                            <ChartCard title="Avg Login & Logout by Department">
                                <ResponsiveContainer width="100%" height={230}>
                                    <BarChart data={filtered.loginTimeData} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="dept" tick={{ fontSize: 11 }} />
                                        <YAxis domain={[8, 20]} tick={{ fontSize: 11 }} tickFormatter={v => `${v}:00`} />
                                        <ReTooltip formatter={(v) => [`${v}:00`, '']} />
                                        <Legend iconSize={10} />
                                        <Bar dataKey="avgLogin" name="Login" fill="#6366f1" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="avgLogout" name="Logout" fill="#22d3ee" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                    </Grid>

                    {/* Cohort Attendance Heatmap */}
                    <AttendanceHeatmapSection />
                </>
            )}

            {/* ══════════════════════════════════════════════════════════════════
                SECTION 3 — TASKS & PRODUCTIVITY
            ══════════════════════════════════════════════════════════════════ */}
            {section === 'tasks' && (
                <>
                    <Grid container spacing={2} mb={2}>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <ChartCard title="Task Turnaround by Department (days)">
                                <ResponsiveContainer width="100%" height={230}>
                                    <BarChart data={taskTurnaround} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                        <XAxis type="number" tick={{ fontSize: 11 }} unit="d" />
                                        <YAxis type="category" dataKey="dept" tick={{ fontSize: 12 }} width={70} />
                                        <ReTooltip formatter={(v) => [`${v} days`, 'Avg turnaround']} />
                                        <Bar dataKey="days" radius={[0, 6, 6, 0]}>
                                            {taskTurnaround.map((entry, i) => (
                                                <Cell key={i} fill={entry.color} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <ChartCard title="Employee Workload Distribution">
                                <ResponsiveContainer width="100%" height={230}>
                                    <BarChart data={deptProductivity} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="dept" tick={{ fontSize: 11 }} />
                                        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                                        <ReTooltip />
                                        <Bar dataKey="workload" name="Workload %" radius={[4, 4, 0, 0]}>
                                            {deptProductivity.map((entry, i) => (
                                                <Cell key={i} fill={COLORS[i % COLORS.length]} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                    </Grid>

                    <Grid container spacing={2}>
                        {/* Task delay reasons donut */}
                        <Grid size={{ xs: 12, md: 4 }}>
                            <ChartCard title="Task Delay Reasons">
                                <ResponsiveContainer width="100%" height={220}>
                                    <PieChart>
                                        <Pie
                                            data={[
                                                { name: 'Unclear brief', value: 28 },
                                                { name: 'Resource gap', value: 22 },
                                                { name: 'Dependency block', value: 19 },
                                                { name: 'Priority shift', value: 17 },
                                                { name: 'Technical issue', value: 14 },
                                            ]}
                                            dataKey="value" nameKey="name"
                                            cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                                            paddingAngle={3}>
                                            {[0, 1, 2, 3, 4].map(i => <Cell key={i} fill={COLORS[i]} />)}
                                        </Pie>
                                        <ReTooltip formatter={(v) => [`${v}%`, 'Share']} />
                                        <Legend iconSize={10} />
                                    </PieChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                        {/* Priority distribution */}
                        <Grid size={{ xs: 12, md: 8 }}>
                            <ChartCard title="Task Priority vs Completion Rate by Department">
                                <ResponsiveContainer width="100%" height={220}>
                                    <BarChart
                                        data={[
                                            { dept: 'Tech', high: 92, medium: 88, low: 79 },
                                            { dept: 'HR', medium: 74, high: 80, low: 68 },
                                            { dept: 'Finance', high: 86, medium: 82, low: 74 },
                                            { dept: 'Ops', high: 75, medium: 70, low: 62 },
                                            { dept: 'Mktg', high: 81, medium: 77, low: 70 },
                                        ]}
                                        margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="dept" tick={{ fontSize: 11 }} />
                                        <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                                        <ReTooltip />
                                        <Legend iconSize={10} />
                                        <Bar dataKey="high" name="High Priority" fill="#f43f5e" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="medium" name="Medium" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                                        <Bar dataKey="low" name="Low" fill="#10b981" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                    </Grid>
                </>
            )}

            {/* ══════════════════════════════════════════════════════════════════
                SECTION 4 — PAYROLL VS PRODUCTIVITY
            ══════════════════════════════════════════════════════════════════ */}
            {section === 'payroll' && (
                <>
                    <Grid container spacing={2} mb={2}>
                        <Grid size={{ xs: 12, md: 8 }}>
                            <ChartCard title="Payroll Cost (₹L) vs Productivity Score — 12 Month Trend">
                                <ResponsiveContainer width="100%" height={240}>
                                    <LineChart data={payrollVsProductivity} margin={{ left: 0, right: 20, top: 5, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                                        <YAxis yAxisId="left" tick={{ fontSize: 11 }} unit="L" domain={[20, 32]} />
                                        <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} domain={[60, 90]} unit="%" />
                                        <ReTooltip />
                                        <Legend iconSize={10} />
                                        <Line yAxisId="left" type="monotone" dataKey="payroll" name="Payroll ₹L" stroke="#f43f5e" strokeWidth={2.5} dot={false} />
                                        <Line yAxisId="right" type="monotone" dataKey="productivity" name="Productivity %" stroke="#6366f1" strokeWidth={2.5} dot={false} strokeDasharray="5 3" />
                                    </LineChart>
                                </ResponsiveContainer>
                                <Paper elevation={0} sx={{ mt: 1, p: 1.5, bgcolor: '#fff1f2', borderRadius: 2 }}>
                                    <Typography variant="caption" color="error" fontWeight={600}>
                                        ⚠️ Payroll grew 28.4% YoY while productivity improved only 7.0% — review cost efficiency.
                                    </Typography>
                                </Paper>
                            </ChartCard>
                        </Grid>
                        <Grid size={{ xs: 12, md: 4 }}>
                            <ChartCard title="Department Salary Distribution (₹L/month)">
                                <ResponsiveContainer width="100%" height={240}>
                                    <BarChart data={filtered.deptSalary} layout="vertical" margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                        <XAxis type="number" tick={{ fontSize: 11 }} unit="L" />
                                        <YAxis type="category" dataKey="dept" tick={{ fontSize: 12 }} width={65} />
                                        <ReTooltip formatter={(v) => [`₹${v}L`, 'Salary']} />
                                        <Bar dataKey="salary" radius={[0, 6, 6, 0]}>
                                            {filtered.deptSalary.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                    </Grid>

                    {/* Payroll vs Productivity scatter */}
                    <Grid container spacing={2}>
                        <Grid size={{ xs: 12, md: 7 }}>
                            <ChartCard title="Payroll vs Productivity (dept scatter)">
                                <ResponsiveContainer width="100%" height={220}>
                                    <ScatterChart margin={{ left: 10, right: 20, top: 5, bottom: 5 }}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="salary" name="Payroll ₹L" unit="L" tick={{ fontSize: 11 }} label={{ value: 'Payroll (₹L)', position: 'insideBottom', offset: -2, fontSize: 11 }} />
                                        <YAxis dataKey="productivity" name="Productivity %" unit="%" tick={{ fontSize: 11 }} />
                                        <ReTooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v, n) => n === 'salary' ? [`₹${v}L`, 'Payroll'] : [`${v}%`, 'Productivity']} />
                                        <Scatter
                                            name="Departments"
                                            data={[
                                                { salary: 9.8, productivity: 88, dept: 'Tech' },
                                                { salary: 5.2, productivity: 84, dept: 'Sales' },
                                                { salary: 4.6, productivity: 70, dept: 'Ops' },
                                                { salary: 3.9, productivity: 81, dept: 'Finance' },
                                                { salary: 3.1, productivity: 77, dept: 'Mktg' },
                                                { salary: 1.8, productivity: 74, dept: 'HR' },
                                            ]}
                                            fill="#6366f1"
                                        >
                                            {[0, 1, 2, 3, 4, 5].map(i => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                        </Scatter>
                                    </ScatterChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                        <Grid size={{ xs: 12, md: 5 }}>
                            <ChartCard title="Cost per Productivity Point by Dept">
                                <Stack spacing={1.5} mt={0.5}>
                                    {[
                                        { dept: 'HR', cpp: 0.024, color: DEPT_COLORS.HR },
                                        { dept: 'Operations', cpp: 0.066, color: DEPT_COLORS.Operations },
                                        { dept: 'Finance', cpp: 0.048, color: DEPT_COLORS.Finance },
                                        { dept: 'Marketing', cpp: 0.040, color: DEPT_COLORS.Marketing },
                                        { dept: 'Sales', cpp: 0.062, color: DEPT_COLORS.Sales },
                                        { dept: 'Tech', cpp: 0.111, color: DEPT_COLORS.Tech },
                                    ].map((d, i) => (
                                        <Stack key={i} direction="row" spacing={1} alignItems="center">
                                            <Typography variant="caption" fontWeight={600} sx={{ width: 70, flexShrink: 0 }}>{d.dept}</Typography>
                                            <LinearProgress variant="determinate" value={d.cpp * 900}
                                                sx={{ flex: 1, height: 8, borderRadius: 4, bgcolor: d.color + '20', '& .MuiLinearProgress-bar': { bgcolor: d.color } }} />
                                            <Typography variant="caption" fontWeight={700} sx={{ width: 45, textAlign: 'right', color: d.color }}>
                                                ₹{d.cpp}L/pt
                                            </Typography>
                                        </Stack>
                                    ))}
                                </Stack>
                            </ChartCard>
                        </Grid>
                    </Grid>
                </>
            )}

            {/* ══════════════════════════════════════════════════════════════════
                SECTION 5 — EXPENSE ANALYTICS
            ══════════════════════════════════════════════════════════════════ */}
            {section === 'expenses' && (
                <>
                    <Grid container spacing={2} mb={2}>
                        <Grid size={{ xs: 12, md: 4 }}>
                            <ChartCard title="Expense by Department (%)">
                                <ResponsiveContainer width="100%" height={240}>
                                    <PieChart>
                                        <Pie data={filtered.expenseByDept} dataKey="value" nameKey="name"
                                            cx="50%" cy="50%" outerRadius={90} paddingAngle={3}>
                                            {filtered.expenseByDept.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                        </Pie>
                                        <ReTooltip formatter={(v) => [`${v}%`, 'Share']} />
                                        <Legend iconSize={10} />
                                    </PieChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                        <Grid size={{ xs: 12, md: 8 }}>
                            <ChartCard title="Expense by Category — Monthly Trend (₹K)">
                                <ResponsiveContainer width="100%" height={240}>
                                    <BarChart data={expenseByCategory} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                                        <YAxis tick={{ fontSize: 11 }} unit="K" />
                                        <ReTooltip />
                                        <Legend iconSize={10} />
                                        <Bar dataKey="Travel" stackId="a" fill="#6366f1" />
                                        <Bar dataKey="Food" stackId="a" fill="#22d3ee" />
                                        <Bar dataKey="Equipment" stackId="a" fill="#f59e0b" />
                                        <Bar dataKey="Training" stackId="a" fill="#10b981" radius={[4, 4, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                    </Grid>
                    <Grid container spacing={2}>
                        <Grid size={{ xs: 12 }}>
                            <ChartCard title="Top Expense Claimants (Individual)">
                                <Stack spacing={1} mt={0.5}>
                                    {[
                                        { name: 'Rohan Mehta', dept: 'Operations', amount: 42400, pct: 88 },
                                        { name: 'Sneha Gupta', dept: 'Sales', amount: 38700, pct: 80 },
                                        { name: 'Arjun Verma', dept: 'Marketing', amount: 31200, pct: 65 },
                                        { name: 'Priya Singh', dept: 'Finance', amount: 28900, pct: 60 },
                                        { name: 'Apoorva Dixit', dept: 'Tech', amount: 22100, pct: 46 },
                                    ].map((e, i) => (
                                        <Stack key={i} direction="row" spacing={1.5} alignItems="center">
                                            <Avatar sx={{ width: 28, height: 28, fontSize: 12, bgcolor: COLORS[i % COLORS.length] + '20', color: COLORS[i % COLORS.length] }}>
                                                {e.name[0]}
                                            </Avatar>
                                            <Box sx={{ minWidth: 130 }}>
                                                <Typography variant="caption" fontWeight={700}>{e.name}</Typography>
                                                <Typography variant="caption" color="text.secondary" display="block">{e.dept}</Typography>
                                            </Box>
                                            <LinearProgress variant="determinate" value={e.pct}
                                                sx={{ flex: 1, height: 6, borderRadius: 4, bgcolor: COLORS[i % COLORS.length] + '20', '& .MuiLinearProgress-bar': { bgcolor: COLORS[i % COLORS.length] } }} />
                                            <Typography variant="caption" fontWeight={700} sx={{ minWidth: 60, textAlign: 'right' }}>₹{(e.amount / 1000).toFixed(1)}K</Typography>
                                        </Stack>
                                    ))}
                                </Stack>
                            </ChartCard>
                        </Grid>
                    </Grid>
                </>
            )}

            {/* ══════════════════════════════════════════════════════════════════
                SECTION 6 — AI INSIGHTS
            ══════════════════════════════════════════════════════════════════ */}
            {section === 'insights' && (
                <>
                    <Stack direction="row" spacing={1} mb={2} alignItems="center">
                        <AutoAwesomeIcon sx={{ color: '#6366f1' }} />
                        <Typography variant="subtitle1" fontWeight={700}>AI-Generated Insights</Typography>
                        <Chip label="Live" size="small" sx={{ bgcolor: '#10b98120', color: '#10b981', fontWeight: 700, fontSize: 10 }} />
                    </Stack>
                    <Grid container spacing={2} mb={2}>
                        {aiInsights.map((ins, i) => (
                            <Grid key={i} size={{ xs: 12, sm: 6, md: 4 }}>
                                <Paper elevation={0} sx={{
                                    border: '1px solid', borderColor: INSIGHT_COLORS[ins.severity] + '50',
                                    borderRadius: 3, p: 2,
                                    bgcolor: INSIGHT_BG[ins.severity],
                                }}>
                                    <Stack direction="row" spacing={1.5} alignItems="flex-start">
                                        <Typography fontSize={22}>{ins.icon}</Typography>
                                        <Typography variant="body2" fontWeight={500} color="text.primary">{ins.text}</Typography>
                                    </Stack>
                                </Paper>
                            </Grid>
                        ))}
                    </Grid>

                    {/* Feedback scores */}
                    <Grid container spacing={2}>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <ChartCard title="Employee Satisfaction & Stress — Monthly Feedback">
                                <ResponsiveContainer width="100%" height={220}>
                                    <LineChart
                                        data={[
                                            { month: 'Jan', satisfaction: 4.2, stress: 3.1, workload: 3.8 },
                                            { month: 'Feb', satisfaction: 4.0, stress: 3.3, workload: 3.9 },
                                            { month: 'Mar', satisfaction: 3.8, stress: 3.6, workload: 4.2 },
                                            { month: 'Apr', satisfaction: 4.1, stress: 3.2, workload: 3.7 },
                                            { month: 'May', satisfaction: 4.1, stress: 3.4, workload: 4.0 },
                                        ]}
                                        margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                                        <YAxis domain={[2, 5]} tick={{ fontSize: 11 }} />
                                        <ReTooltip />
                                        <Legend iconSize={10} />
                                        <Line type="monotone" dataKey="satisfaction" name="Satisfaction" stroke="#10b981" strokeWidth={2.5} dot={{ r: 4 }} />
                                        <Line type="monotone" dataKey="stress" name="Stress" stroke="#f43f5e" strokeWidth={2.5} dot={{ r: 4 }} />
                                        <Line type="monotone" dataKey="workload" name="Workload" stroke="#f59e0b" strokeWidth={2.5} dot={{ r: 4 }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <ChartCard title="Burnout Risk Index by Department">
                                <ResponsiveContainer width="100%" height={220}>
                                    <BarChart
                                        data={[
                                            { dept: 'Operations', risk: 72, color: DEPT_COLORS.Operations },
                                            { dept: 'Sales', risk: 65, color: DEPT_COLORS.Sales },
                                            { dept: 'Tech', risk: 48, color: DEPT_COLORS.Tech },
                                            { dept: 'Finance', risk: 41, color: DEPT_COLORS.Finance },
                                            { dept: 'Marketing', risk: 38, color: DEPT_COLORS.Marketing },
                                            { dept: 'HR', risk: 30, color: DEPT_COLORS.HR },
                                        ]}
                                        layout="vertical"
                                        margin={{ left: 10, right: 20, top: 0, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                        <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                                        <YAxis type="category" dataKey="dept" tick={{ fontSize: 12 }} width={70} />
                                        <ReTooltip formatter={(v) => [`${v}%`, 'Burnout Risk']} />
                                        <Bar dataKey="risk" radius={[0, 6, 6, 0]}>
                                            {[0, 1, 2, 3, 4, 5].map(i => <Cell key={i} fill={['#f43f5e', '#fb923c', '#6366f1', '#10b981', '#22d3ee', '#f59e0b'][i]} />)}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                    </Grid>
                </>
            )}

            {/* ══════════════════════════════════════════════════════════════════
                SECTION 7 — EXECUTIVE DASHBOARD (CEO VIEW)
            ══════════════════════════════════════════════════════════════════ */}
            {section === 'executive' && (
                <>
                    <Paper elevation={0} sx={{ border: '1px solid', borderColor: '#6366f140', bgcolor: '#eef2ff', borderRadius: 3, p: 2, mb: 2 }}>
                        <Stack direction="row" spacing={1} alignItems="center">
                            <Typography fontSize={20}>👔</Typography>
                            <Typography variant="subtitle2" fontWeight={700} color="#6366f1">
                                CEO / Executive View — Company-wide Snapshot, May 2026
                            </Typography>
                        </Stack>
                    </Paper>

                    {/* 4 headline metrics */}
                    <Grid container spacing={1.5} mb={2.5}>
                        {[
                            { icon: <TrendingUpIcon fontSize="small" />, label: 'Company Productivity', value: '76%', sub: '+7% YoY', color: '#6366f1', trend: 76 },
                            { icon: <AttachMoneyIcon fontSize="small" />, label: 'Total Payroll Cost', value: '₹28.4L', sub: '+28% YoY', color: '#f43f5e', trend: 57 },
                            { icon: <PeopleAltIcon fontSize="small" />, label: 'Employee Engagement', value: '82%', sub: 'Active + satisfied', color: '#10b981', trend: 82 },
                            { icon: <WarningAmberIcon fontSize="small" />, label: 'Problem Areas', value: '3', sub: 'Depts need attention', color: '#fb923c', trend: 30 },
                        ].map((k, i) => (
                            <Grid key={i} size={{ xs: 6, md: 3 }}>
                                <KpiCard {...k} />
                            </Grid>
                        ))}
                    </Grid>

                    <Grid container spacing={2} mb={2}>
                        {/* Top departments */}
                        <Grid size={{ xs: 12, md: 5 }}>
                            <ChartCard title="Top Departments — Combined Performance Score">
                                <ResponsiveContainer width="100%" height={230}>
                                    <BarChart data={deptProductivity} margin={{ left: 0, right: 10, top: 5, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="dept" tick={{ fontSize: 11 }} />
                                        <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                                        <ReTooltip />
                                        <Bar dataKey="productivity" name="Score" radius={[4, 4, 0, 0]}>
                                            {deptProductivity.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>

                        {/* Payroll trend */}
                        <Grid size={{ xs: 12, md: 7 }}>
                            <ChartCard title="Payroll Trend vs Productivity (Annual)">
                                <ResponsiveContainer width="100%" height={230}>
                                    <AreaChart data={payrollVsProductivity} margin={{ left: 0, right: 20, top: 5, bottom: 0 }}>
                                        <defs>
                                            <linearGradient id="gPayroll" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.25} />
                                                <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                                            </linearGradient>
                                            <linearGradient id="gProd" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
                                                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                                        <YAxis yAxisId="left" tick={{ fontSize: 11 }} unit="L" domain={[20, 32]} />
                                        <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} domain={[60, 90]} unit="%" />
                                        <ReTooltip />
                                        <Legend iconSize={10} />
                                        <Area yAxisId="left" type="monotone" dataKey="payroll" name="Payroll ₹L" stroke="#f43f5e" fill="url(#gPayroll)" strokeWidth={2} />
                                        <Area yAxisId="right" type="monotone" dataKey="productivity" name="Productivity %" stroke="#6366f1" fill="url(#gProd)" strokeWidth={2} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                    </Grid>

                    {/* Problem areas + cost vs output */}
                    <Grid container spacing={2}>
                        <Grid size={{ xs: 12, md: 5 }}>
                            <ChartCard title="Problem Areas — Composite Risk Score">
                                {(() => {
                                    const riskData = [
                                        { dept: 'Operations', issue: 'Overloaded + High overdue', risk: 82, color: '#f43f5e' },
                                        { dept: 'Finance', issue: 'Highest overdue tasks', risk: 70, color: '#fb923c' },
                                        { dept: 'HR', issue: 'Low productivity, slow turnaround', risk: 58, color: '#f59e0b' },
                                    ];
                                    const info = riskDept ? RISK_EMPLOYEES[riskDept] : null;
                                    return (
                                        <>
                                            <Stack spacing={1.5} mt={0.5}>
                                                {riskData.map((d, i) => (
                                                    <Paper key={i} elevation={0}
                                                        onMouseEnter={e => { setRiskAnchor(e.currentTarget); setRiskDept(d.dept); }}
                                                        onMouseLeave={() => { setRiskAnchor(null); setRiskDept(null); }}
                                                        sx={{ p: 1.5, borderRadius: 2, border: '1px solid', borderColor: d.color + '40', bgcolor: d.color + '08', cursor: 'default', transition: 'box-shadow 0.15s', '&:hover': { boxShadow: `0 0 0 2px ${d.color}50` } }}>
                                                        <Stack direction="row" justifyContent="space-between" alignItems="flex-start" mb={0.5}>
                                                            <Box>
                                                                <Typography variant="caption" fontWeight={700}>{d.dept}</Typography>
                                                                <Typography variant="caption" color="text.secondary" display="block">{d.issue}</Typography>
                                                            </Box>
                                                            <Chip label={`${d.risk}%`} size="small" sx={{ fontSize: 11, fontWeight: 700, bgcolor: d.color + '20', color: d.color }} />
                                                        </Stack>
                                                        <LinearProgress variant="determinate" value={d.risk}
                                                            sx={{ height: 6, borderRadius: 4, bgcolor: d.color + '20', '& .MuiLinearProgress-bar': { bgcolor: d.color } }} />
                                                    </Paper>
                                                ))}
                                            </Stack>

                                            <Popover
                                                open={Boolean(riskAnchor)}
                                                anchorEl={riskAnchor}
                                                onClose={() => { setRiskAnchor(null); setRiskDept(null); }}
                                                disableRestoreFocus
                                                sx={{ pointerEvents: 'none' }}
                                                anchorOrigin={{ vertical: 'center', horizontal: 'right' }}
                                                transformOrigin={{ vertical: 'center', horizontal: 'left' }}
                                                PaperProps={{ sx: { p: 2, borderRadius: 3, boxShadow: 6, minWidth: 340 } }}
                                            >
                                                {info && (
                                                    <Box>
                                                        <Stack direction="row" alignItems="center" spacing={1} mb={0.8}>
                                                            <Typography fontWeight={800} fontSize={14}>{riskDept}</Typography>
                                                            <Chip label="Risk Dept" size="small" sx={{ fontSize: 10, bgcolor: '#fef2f2', color: '#f43f5e', fontWeight: 700 }} />
                                                        </Stack>
                                                        <Typography fontSize={12} color="text.secondary" mb={1.5}>{info.summary}</Typography>
                                                        <Table size="small">
                                                            <TableHead>
                                                                <TableRow sx={{ bgcolor: '#f8fafc' }}>
                                                                    {['Employee', 'Role', 'Overdue', 'Workload', 'Status'].map(h => (
                                                                        <TableCell key={h} sx={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.4, color: 'text.secondary', py: 0.6 }}>{h}</TableCell>
                                                                    ))}
                                                                </TableRow>
                                                            </TableHead>
                                                            <TableBody>
                                                                {info.employees.map((emp, idx) => (
                                                                    <TableRow key={idx} hover>
                                                                        <TableCell sx={{ fontSize: 12, fontWeight: 600, py: 0.8 }}>{emp.name}</TableCell>
                                                                        <TableCell sx={{ fontSize: 11, color: 'text.secondary', py: 0.8 }}>{emp.role}</TableCell>
                                                                        <TableCell sx={{ fontSize: 12, fontWeight: 700, color: '#f43f5e', py: 0.8 }}>{emp.overdueTask}</TableCell>
                                                                        <TableCell sx={{ fontSize: 12, py: 0.8 }}>{emp.workload}</TableCell>
                                                                        <TableCell sx={{ py: 0.8 }}>
                                                                            <Chip label={emp.status} size="small" sx={{ fontSize: 10, fontWeight: 700, bgcolor: (STATUS_COLOR[emp.status] || '#6366f1') + '20', color: STATUS_COLOR[emp.status] || '#6366f1' }} />
                                                                        </TableCell>
                                                                    </TableRow>
                                                                ))}
                                                            </TableBody>
                                                        </Table>
                                                    </Box>
                                                )}
                                            </Popover>
                                        </>
                                    );
                                })()}
                            </ChartCard>
                        </Grid>
                        <Grid size={{ xs: 12, md: 7 }}>
                            <ChartCard title="Cost vs Output — Department Efficiency Matrix">
                                <ResponsiveContainer width="100%" height={230}>
                                    <ScatterChart margin={{ left: 10, right: 20, top: 5, bottom: 15 }}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis dataKey="salary" name="Salary Cost ₹L" unit="L" tick={{ fontSize: 11 }}
                                            label={{ value: 'Salary Cost (₹L)', position: 'insideBottom', offset: -8, fontSize: 11 }} />
                                        <YAxis dataKey="productivity" name="Productivity" unit="%" tick={{ fontSize: 11 }} />
                                        <ReTooltip cursor={{ strokeDasharray: '3 3' }} formatter={(v, n) => n === 'salary' ? [`₹${v}L`, 'Cost'] : [`${v}%`, 'Output']} />
                                        <Scatter
                                            name="Departments"
                                            data={filtered.deptSalary.map((d, i) => ({
                                                salary: d.salary,
                                                productivity: filtered.deptProductivity.find(p => p.dept === d.dept)?.productivity || 75,
                                                dept: d.dept,
                                            }))}
                                            fill="#6366f1">
                                            {filtered.deptSalary.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                                        </Scatter>
                                    </ScatterChart>
                                </ResponsiveContainer>
                            </ChartCard>
                        </Grid>
                    </Grid>
                </>
            )}

            {/* ══════════════════════════════════════════════════════════════════
                SECTION 8 — RED ZONE (At-Risk Employees)
            ══════════════════════════════════════════════════════════════════ */}
            {section === 'redzone' && (
                <>
                    {/* Header banner */}
                    <Paper elevation={0} sx={{
                        border: '1px solid', borderColor: 'divider',
                        borderRadius: 3, p: 2, mb: 2.5,
                    }}>
                        <Stack direction="row" spacing={1.5} alignItems="center">
                            <Box sx={{ fontSize: 28, lineHeight: 1 }}>🚨</Box>
                            <Box>
                                <Typography fontWeight={800} fontSize={15} color="#be123c">
                                    Red Zone — At-Risk Employees
                                </Typography>
                                <Typography variant="caption" color="#f43f5e">
                                    Employees flagged for low attendance, overdue tasks, excess leaves, slow turnaround, or very low productivity — May 2026
                                </Typography>
                            </Box>
                            <Box sx={{ ml: 'auto', display: 'flex', gap: 1, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                                {[
                                    { label: `${filtered.redZone.lowAttendance.length} low attendance`,  color: '#dc2626' },
                                    { label: `${filtered.redZone.mostOverdue.length} overdue leaders`,   color: '#b91c1c' },
                                    { label: `${filtered.redZone.excessLeaves.length} excess leaves`,    color: '#c2410c' },
                                    { label: `${filtered.redZone.slowTurnaround.length} slow turnaround`, color: '#9f1239' },
                                    { label: `${filtered.redZone.lowProductivity.length} low productivity`, color: '#be123c' },
                                ].map(b => (
                                    <Chip key={b.label} label={b.label} size="small"
                                        sx={{ fontSize: 10, fontWeight: 700, bgcolor: b.color + '18', color: b.color, border: `1px solid ${b.color}40` }} />
                                ))}
                            </Box>
                        </Stack>
                    </Paper>

                    {/* ROW 1: Low Attendance + Most Overdue */}
                    <Grid container spacing={2} mb={2}>
                        {/* Low Attendance */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, p: 2, height: '100%' }}>
                                <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
                                    <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#dc2626', flexShrink: 0 }} />
                                    <Typography fontWeight={700} fontSize={13} color="#dc2626">Least Attendance</Typography>
                                    <Chip label="Below 70%" size="small" sx={{ fontSize: 10, fontWeight: 700, bgcolor: '#fecaca', color: '#dc2626', ml: 'auto' }} />
                                </Stack>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow sx={{ bgcolor: '#f8fafc' }}>
                                                {['Employee', 'Dept', 'Avg %', 'Trend'].map(h => (
                                                    <TableCell key={h} sx={{ fontWeight: 700, fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, color: '#9f1239', py: 0.8, borderBottom: '1px solid #fecaca' }}>{h}</TableCell>
                                                ))}
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {filtered.redZone.lowAttendance.map((e, i) => (
                                                <TableRow key={i} hover>
                                                    <TableCell sx={{ fontSize: 12, fontWeight: 600, py: 0.9 }}>{e.name}</TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Chip label={e.dept} size="small" sx={{ fontSize: 10, height: 18, bgcolor: DEPT_COLORS[e.dept] + '20', color: DEPT_COLORS[e.dept] }} />
                                                    </TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                                                            <LinearProgress variant="determinate" value={e.avg}
                                                                sx={{ width: 48, height: 5, borderRadius: 3, bgcolor: 'divider', '& .MuiLinearProgress-bar': { bgcolor: e.avg < 50 ? '#dc2626' : '#f97316' } }} />
                                                            <Typography fontSize={12} fontWeight={700} color={e.avg < 50 ? '#dc2626' : '#f97316'}>{e.avg}%</Typography>
                                                        </Box>
                                                    </TableCell>
                                                    <TableCell sx={{ fontSize: 11, color: '#ef4444', py: 0.9 }}>{e.trend}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Paper>
                        </Grid>

                        {/* Most Overdue Tasks */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, p: 2, height: '100%' }}>
                                <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
                                    <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#b91c1c', flexShrink: 0 }} />
                                    <Typography fontWeight={700} fontSize={13} color="#b91c1c">Most Overdue Tasks & Delays</Typography>
                                    <Chip label="High risk" size="small" sx={{ fontSize: 10, fontWeight: 700, bgcolor: '#fecaca', color: '#b91c1c', ml: 'auto' }} />
                                </Stack>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow sx={{ bgcolor: '#f8fafc' }}>
                                                {['Employee', 'Dept', 'Overdue', 'Delayed', 'Last Active'].map(h => (
                                                    <TableCell key={h} sx={{ fontWeight: 700, fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, color: '#9f1239', py: 0.8, borderBottom: '1px solid #fecaca' }}>{h}</TableCell>
                                                ))}
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {filtered.redZone.mostOverdue.map((e, i) => (
                                                <TableRow key={i} hover>
                                                    <TableCell sx={{ fontSize: 12, fontWeight: 600, py: 0.9 }}>{e.name}</TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Chip label={e.dept} size="small" sx={{ fontSize: 10, height: 18, bgcolor: DEPT_COLORS[e.dept] + '20', color: DEPT_COLORS[e.dept] }} />
                                                    </TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Chip label={e.overdue} size="small" sx={{ fontSize: 11, fontWeight: 800, bgcolor: '#fecaca', color: '#dc2626', height: 20 }} />
                                                    </TableCell>
                                                    <TableCell sx={{ fontSize: 12, fontWeight: 700, color: '#f97316', py: 0.9 }}>{e.delayed}</TableCell>
                                                    <TableCell sx={{ fontSize: 11, color: 'text.secondary', py: 0.9 }}>{e.lastActivity}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Paper>
                        </Grid>
                    </Grid>

                    {/* ROW 2: Excess Leaves + Slow Turnaround */}
                    <Grid container spacing={2} mb={2}>
                        {/* Excess Leaves */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, p: 2, height: '100%' }}>
                                <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
                                    <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#c2410c', flexShrink: 0 }} />
                                    <Typography fontWeight={700} fontSize={13} color="#c2410c">Excess Leaves</Typography>
                                    <Chip label="Most this month" size="small" sx={{ fontSize: 10, fontWeight: 700, bgcolor: '#fed7aa', color: '#c2410c', ml: 'auto' }} />
                                </Stack>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow sx={{ bgcolor: '#f8fafc' }}>
                                                {['Employee', 'Dept', 'Leaves Used', 'Unplanned'].map(h => (
                                                    <TableCell key={h} sx={{ fontWeight: 700, fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, color: '#9f1239', py: 0.8, borderBottom: '1px solid #fecaca' }}>{h}</TableCell>
                                                ))}
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {filtered.redZone.excessLeaves.map((e, i) => (
                                                <TableRow key={i} hover>
                                                    <TableCell sx={{ fontSize: 12, fontWeight: 600, py: 0.9 }}>{e.name}</TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Chip label={e.dept} size="small" sx={{ fontSize: 10, height: 18, bgcolor: DEPT_COLORS[e.dept] + '20', color: DEPT_COLORS[e.dept] }} />
                                                    </TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                                                            <LinearProgress variant="determinate" value={(e.leaves / e.quota) * 100}
                                                                sx={{ width: 48, height: 5, borderRadius: 3, bgcolor: 'divider', '& .MuiLinearProgress-bar': { bgcolor: e.leaves >= 8 ? '#dc2626' : '#f97316' } }} />
                                                            <Typography fontSize={12} fontWeight={700} color={e.leaves >= 8 ? '#dc2626' : '#f97316'}>{e.leaves}/{e.quota}</Typography>
                                                        </Box>
                                                    </TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Chip label={`${e.unplanned} unplanned`} size="small"
                                                            sx={{ fontSize: 10, height: 18, bgcolor: e.unplanned >= 4 ? '#fecaca' : '#ffedd5', color: e.unplanned >= 4 ? '#dc2626' : '#c2410c', fontWeight: 700 }} />
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Paper>
                        </Grid>

                        {/* Slow Task Turnaround */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 3, p: 2, height: '100%' }}>
                                <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
                                    <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#9f1239', flexShrink: 0 }} />
                                    <Typography fontWeight={700} fontSize={13} color="#9f1239">Slowest Task Turnaround</Typography>
                                    <Chip label="> 10 days avg" size="small" sx={{ fontSize: 10, fontWeight: 700, bgcolor: '#fecaca', color: '#9f1239', ml: 'auto' }} />
                                </Stack>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow sx={{ bgcolor: '#f8fafc' }}>
                                                {['Employee', 'Dept', 'Avg Days', 'Overdue Tasks'].map(h => (
                                                    <TableCell key={h} sx={{ fontWeight: 700, fontSize: 10, textTransform: 'uppercase', letterSpacing: 0.5, color: '#9f1239', py: 0.8, borderBottom: '1px solid #fecaca' }}>{h}</TableCell>
                                                ))}
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {filtered.redZone.slowTurnaround.map((e, i) => (
                                                <TableRow key={i} hover>
                                                    <TableCell sx={{ fontSize: 12, fontWeight: 600, py: 0.9 }}>{e.name}</TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Chip label={e.dept} size="small" sx={{ fontSize: 10, height: 18, bgcolor: DEPT_COLORS[e.dept] + '20', color: DEPT_COLORS[e.dept] }} />
                                                    </TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8 }}>
                                                            <LinearProgress variant="determinate" value={Math.min((e.avgDays / 20) * 100, 100)}
                                                                sx={{ width: 48, height: 5, borderRadius: 3, bgcolor: 'divider', '& .MuiLinearProgress-bar': { bgcolor: e.avgDays > 15 ? '#dc2626' : '#f97316' } }} />
                                                            <Typography fontSize={12} fontWeight={700} color={e.avgDays > 15 ? '#dc2626' : '#f97316'}>{e.avgDays}d</Typography>
                                                        </Box>
                                                    </TableCell>
                                                    <TableCell sx={{ py: 0.9 }}>
                                                        <Chip label={e.overdue} size="small" sx={{ fontSize: 11, fontWeight: 800, bgcolor: '#fecaca', color: '#dc2626', height: 20 }} />
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Paper>
                        </Grid>
                    </Grid>

                    {/* ROW 3: Low Productivity (full width) */}
                    <Paper elevation={0} sx={{ border: '1px solid #fca5a5', borderRadius: 3, p: 2, bgcolor: '#fff8f8' }}>
                        <Stack direction="row" alignItems="center" spacing={1} mb={1.5}>
                            <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: '#be123c', flexShrink: 0 }} />
                            <Typography fontWeight={700} fontSize={13} color="#be123c">Very Low Productivity</Typography>
                            <Chip label="Score below 65" size="small" sx={{ fontSize: 10, fontWeight: 700, bgcolor: '#fecaca', color: '#be123c', ml: 'auto' }} />
                        </Stack>
                        <Grid container spacing={1.5}>
                            {filtered.redZone.lowProductivity.map((e, i) => (
                                <Grid key={i} size={{ xs: 12, sm: 6, md: 3 }}>
                                    <Paper elevation={0} sx={{
                                        border: '1px solid', borderColor: 'divider', borderRadius: 2,
                                        p: 1.5,
                                    }}>
                                        <Stack direction="row" alignItems="center" spacing={1} mb={1}>
                                            <Avatar sx={{ width: 30, height: 30, fontSize: 12, fontWeight: 700, bgcolor: '#f1f5f9', color: '#dc2626' }}>
                                                {e.name[0]}
                                            </Avatar>
                                            <Box flex={1} minWidth={0}>
                                                <Typography fontSize={12} fontWeight={700} noWrap>{e.name}</Typography>
                                                <Chip label={e.dept} size="small" sx={{ fontSize: 9, height: 16, bgcolor: DEPT_COLORS[e.dept] + '20', color: DEPT_COLORS[e.dept] }} />
                                            </Box>
                                            <Typography fontSize={15} fontWeight={800} color="#dc2626">{e.score}</Typography>
                                        </Stack>
                                        <LinearProgress variant="determinate" value={e.score}
                                            sx={{ height: 6, borderRadius: 3, bgcolor: '#e2e8f0', '& .MuiLinearProgress-bar': { bgcolor: e.score < 55 ? '#dc2626' : '#f97316' } }} />
                                        <Stack direction="row" justifyContent="space-between" mt={0.8}>
                                            <Typography fontSize={10} color="text.secondary">Tasks: <b>{e.tasks}</b></Typography>
                                            <Typography fontSize={10} color="#dc2626" fontWeight={700}>Completion: {e.completion}</Typography>
                                        </Stack>
                                    </Paper>
                                </Grid>
                            ))}
                        </Grid>
                    </Paper>
                </>
            )}
        </Box>
    );
}
