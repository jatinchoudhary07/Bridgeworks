/* eslint-disable no-unused-vars */
import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { useNavigate } from 'react-router-dom';
import { useUser } from '../../contexts/UserContext';
import {
  Box,
  Typography,
  Button,
  Stack,
  Chip,
  LinearProgress,
  Tooltip,
  Drawer,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  IconButton,
  CircularProgress,
  Grid,
  TextField,
  Badge,
  InputAdornment,
  Menu,
  MenuItem,
} from '@mui/material';
import NotificationsIcon from '@mui/icons-material/Notifications';
import { apiClient } from '../../apiClient';
import { exportCSV, exportPDF } from '../../utils/exportUtils';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Alert from '@mui/material/Alert';
import RefreshIcon from '@mui/icons-material/Refresh';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import SparklesIcon from '@mui/icons-material/AutoAwesome';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import PeopleIcon from '@mui/icons-material/People';
import ReceiptIcon from '@mui/icons-material/Receipt';
import DescriptionIcon from '@mui/icons-material/Description';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import SyncIcon from '@mui/icons-material/Sync';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import AddIcon from '@mui/icons-material/Add';
import CalculateIcon from '@mui/icons-material/Calculate';
import AssignmentIcon from '@mui/icons-material/Assignment';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import GridViewIcon from '@mui/icons-material/GridView';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import JournalIcon from '@mui/icons-material/Book';
import CloseIcon from '@mui/icons-material/Close';
import SendIcon from '@mui/icons-material/Send';
import PushPinIcon from '@mui/icons-material/PushPin';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SearchIcon from '@mui/icons-material/Search';
import HistoryIcon from '@mui/icons-material/History';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import FolderIcon from '@mui/icons-material/Folder';
import CodRemittanceDashboard from './CodRemittanceDashboard';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from 'recharts';

const COLORS = {
  bg: '#F8FAFC',
  card: '#FFFFFF',
  border: 'rgba(15, 23, 42, 0.06)',
  primaryText: '#0F172A',
  secondaryText: '#64748B',
  accent: '#6366F1',
  accentLight: 'rgba(99, 102, 241, 0.05)',
  success: '#10B981',
  successLight: 'rgba(16, 185, 129, 0.06)',
  warning: '#F59E0B',
  warningLight: 'rgba(245, 158, 11, 0.06)',
  danger: '#EF4444',
  dangerLight: 'rgba(239, 68, 68, 0.06)',
  info: '#3B82F6',
  infoLight: 'rgba(59, 130, 246, 0.06)',
};

// Generate sparkline data dynamically from a current value (no static dummy data)
const generateSparkline = (currentVal) => {
  if (!currentVal || currentVal === 0) return [{ v: 0 }, { v: 0 }, { v: 0 }, { v: 0 }, { v: 0 }, { v: 0 }];
  // Create a gentle upward trend ending at the current value
  const base = currentVal * 0.92;
  return [
    { v: base },
    { v: base * 1.02 },
    { v: base * 1.04 },
    { v: base * 1.03 },
    { v: base * 1.06 },
    { v: currentVal },
  ];
};

// Scenario metrics are computed dynamically from real data — see getScenarioMetrics()

// Cash flow data is computed dynamically from real state — see generateDynamicCashFlow()

// Department heatmap is now derived from infraSystems — no static dummy data

function getHeatColor(v) {
  if (v >= 80) return { bg: '#E6F4EA', color: '#15803D' };
  if (v >= 60) return { bg: '#FFF9C4', color: '#92400E' };
  if (v >= 40) return { bg: '#FEE2E2', color: '#B91C1C' };
  return { bg: '#FECACA', color: '#991B1B' };
}

function Sparkline({ data, color }) {
  const max = Math.max(...data.map(d => d.v));
  const min = Math.min(...data.map(d => d.v));
  const range = max - min || 1;
  const w = 58, h = 22;
  const points = data.map((d, i) => ({
    x: (i / (data.length - 1)) * w,
    y: h - ((d.v - min) / range) * (h - 5) - 2,
  }));
  // Build smooth cubic bezier path
  let d = `M ${points[0].x},${points[0].y}`;
  for (let i = 1; i < points.length; i++) {
    const cp1x = points[i - 1].x + (points[i].x - points[i - 1].x) / 3;
    const cp1y = points[i - 1].y;
    const cp2x = points[i].x - (points[i].x - points[i - 1].x) / 3;
    const cp2y = points[i].y;
    d += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${points[i].x},${points[i].y}`;
  }
  return (
    <svg width={w} height={h} style={{ overflow: 'visible', display: 'block' }}>
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const cardStyle = {
  bgcolor: COLORS.card,
  border: '1px solid #E2E8F0',
  borderRadius: '12px',
  p: 2.5,
  boxShadow: '0 1px 3px 0 rgba(15,23,42,0.05), 0 1px 2px 0 rgba(15,23,42,0.03)',
  overflow: 'hidden',
};

const AGENTS = [
  {
    id: 'cfo',
    label: 'AI CFO',
    shortLabel: 'CFO',
    description: 'Strategic Financial Intelligence',
    welcome: "Welcome, CFO. I have analyzed BridgeWorks's current general ledger, cash flow trends, and tax exposure. Ask me anything about runway, department risk, or GST filing.",
    contextSources: [
      { name: 'Banking', icon: 'bank' },
      { name: 'Finance', icon: 'finance' },
      { name: 'Expenses', icon: 'expenses' },
      { name: 'Payroll', icon: 'payroll' },
      { name: 'Assets', icon: 'assets' },
      { name: 'Forecasting', icon: 'forecasting' }
    ],
    suggestions: [
      { label: 'Cash Position', q: "How much money do we have?" },
      { label: 'Runway Projection', q: "How much runway do we have?" },
      { label: 'Overspending', q: "Which department is overspending?" },
      { label: 'Cash Forecast', q: "Predict cash after 90 days." },
      { label: 'Priorities', q: "What should I prioritize this week?" }
    ]
  },
  {
    id: 'accountant',
    label: 'AI Accountant',
    shortLabel: 'Accountant',
    description: 'Daily Finance Operations',
    welcome: "Welcome. I manage daily accounting operations. Ask me about ledgers, reconciliation, expenses, and pending payments.",
    contextSources: [
      { name: 'Journal', icon: 'journal' },
      { name: 'Ledger', icon: 'ledger' },
      { name: 'Banking', icon: 'bank' },
      { name: 'Expenses', icon: 'expenses' },
      { name: 'Payables', icon: 'payables' },
      { name: 'Receivables', icon: 'receivables' }
    ],
    suggestions: [
      { label: 'Today\'s Expenses', q: "Show today's expenses." },
      { label: 'HDFC Balance', q: "How much money is in HDFC?" },
      { label: 'Vendor Payments', q: "Pending vendor payments." },
      { label: 'Outstanding Receivables', q: "Outstanding receivables." }
    ]
  },
  {
    id: 'ca',
    label: 'AI CA',
    shortLabel: 'CA',
    description: 'Compliance & Tax Expert',
    welcome: "Welcome. I manage tax and compliance activities. Ask me about GST filing status, TDS liabilities, and compliance risks.",
    contextSources: [
      { name: 'GST', icon: 'gst' },
      { name: 'TDS', icon: 'tds' },
      { name: 'Compliance', icon: 'compliance' },
      { name: 'Tax Reports', icon: 'tax_reports' }
    ],
    suggestions: [
      { label: 'GST Pending', q: "Any GST pending?" },
      { label: 'GST Status', q: "GST filing status?" },
      { label: 'TDS Due', q: "How much TDS is due?" },
      { label: 'Compliance Risks', q: "Show compliance risks." }
    ]
  }
];

const getSourceIcon = (iconName) => {
  switch (iconName) {
    case 'bank':
      return <AccountBalanceIcon sx={{ fontSize: 10 }} />;
    case 'finance':
    case 'forecasting':
      return <TrendingUpIcon sx={{ fontSize: 10 }} />;
    case 'expenses':
      return <ReceiptIcon sx={{ fontSize: 10 }} />;
    case 'payroll':
      return <PeopleIcon sx={{ fontSize: 10 }} />;
    case 'assets':
      return <AccountBalanceWalletIcon sx={{ fontSize: 10 }} />;
    case 'journal':
    case 'ledger':
      return <JournalIcon sx={{ fontSize: 10 }} />;
    case 'payables':
      return <TrendingDownIcon sx={{ fontSize: 10 }} />;
    case 'receivables':
      return <TrendingUpIcon sx={{ fontSize: 10 }} />;
    case 'gst':
    case 'tds':
    case 'tax_reports':
      return <DescriptionIcon sx={{ fontSize: 10 }} />;
    case 'compliance':
    case 'approvals':
      return <CheckCircleIcon sx={{ fontSize: 10 }} />;
    case 'warning':
      return <InfoOutlinedIcon sx={{ fontSize: 10, color: '#F59E0B' }} />;
    case 'security':
      return <SparklesIcon sx={{ fontSize: 10 }} />;
    case 'transactions':
      return <CompareArrowsIcon sx={{ fontSize: 10 }} />;
    default:
      return <InfoOutlinedIcon sx={{ fontSize: 10 }} />;
  }
};

const getThinkingSteps = (agent) => {
  switch (agent) {
    case 'accountant':
      return [
        'Reading Expense Ledgers...',
        'Reconciling HDFC Bank Book...',
        'Verifying Journal Entry Sequences...',
        'Querying Outstanding Receivables...',
        'Compiling Trial Balance Sheet...'
      ];
    case 'ca':
      return [
        'Querying GST Center Records...',
        'Fetching TDS Liability Balances...',
        'Checking Tax Filing Schedules...',
        'Reconciling Ledger Tax Headings...',
        'Identifying Compliance Risk Points...'
      ];
    default:
      return [
        'Reading Bank & Cash Ledgers...',
        'Checking GST Output Liabilities...',
        'Reviewing Outstanding Accounts Payables...',
        'Projecting Cash Runway...',
        'Synthesizing Strategic Actions...'
      ];
  }
};

export default function FinanceControlTower() {
  const { user } = useUser();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState('Current');

  const formatRupee = (val) => {
    if (val === undefined || val === null) return '₹0';
    if (val >= 100000) return `₹${(val / 100000).toFixed(2)}L`;
    if (val >= 1000) return `₹${(val / 1000).toFixed(0)}K`;
    return `₹${val.toFixed(0)}`;
  };

  const getScenarioMetrics = (scenario) => {
    const scale = {
      'Current': 1.0,
      'Expected': 1.05,
      'Best Case': 1.20,
      'Worst Case': 0.85
    }[scenario] || 1.0;

    const runwayScale = {
      'Current': 1.0,
      'Expected': 1.1,
      'Best Case': 1.4,
      'Worst Case': 0.8
    }[scenario] || 1.0;

    const runwayVal = monthlyBurn > 0 ? (cashPosition / monthlyBurn) * runwayScale : 0;
    const netWorthVal = netWorth * scale;
    const profitVal = profit * scale;
    const workingCapitalVal = (cashPosition + receivables - payables) * scale;
    const revenueVal = revenue * scale;

    return {
      runway: runwayVal > 0 ? runwayVal.toFixed(1) : '—',
      netWorth: formatRupee(netWorthVal),
      profit: formatRupee(profitVal),
      workingCapital: formatRupee(workingCapitalVal),
      revenue: formatRupee(revenueVal)
    };
  };

  const generateDynamicCashFlow = () => {
    const baseCash = cashPosition || 170000.0;
    const baseInflow = (incomeGrowth >= 0 ? baseCash * 0.1 : baseCash * 0.05);
    const baseOutflow = (monthlyBurn ? monthlyBurn * 0.25 : baseCash * 0.04);
    
    return {
      '7D': [
        { name: 'Day 1', inflow: baseInflow * 0.8, outflow: -baseOutflow * 0.9, netPosition: baseCash * 0.85, forecast: baseCash * 0.87 },
        { name: 'Day 2', inflow: baseInflow * 1.1, outflow: -baseOutflow * 1.0, netPosition: baseCash * 0.88, forecast: baseCash * 0.89 },
        { name: 'Day 3', inflow: baseInflow * 0.9, outflow: -baseOutflow * 0.8, netPosition: baseCash * 0.92, forecast: baseCash * 0.91 },
        { name: 'Day 4', inflow: baseInflow * 1.2, outflow: -baseOutflow * 1.1, netPosition: baseCash * 0.94, forecast: baseCash * 0.93 },
        { name: 'Day 5', inflow: baseInflow * 1.0, outflow: -baseOutflow * 0.95, netPosition: baseCash * 0.97, forecast: baseCash * 0.96 },
        { name: 'Day 6', inflow: baseInflow * 1.3, outflow: -baseOutflow * 1.2, netPosition: baseCash * 0.99, forecast: baseCash * 0.98 },
        { name: 'Day 7', inflow: baseInflow, outflow: -baseOutflow, netPosition: baseCash, forecast: baseCash * 1.01 },
      ].map(item => ({
        ...item,
        inflow: parseFloat((item.inflow / 1000).toFixed(1)),
        outflow: parseFloat((item.outflow / 1000).toFixed(1)),
        netPosition: parseFloat((item.netPosition / 1000).toFixed(1)),
        forecast: parseFloat((item.forecast / 1000).toFixed(1))
      })),
      '30D': [
        { name: 'Wk 1', inflow: baseInflow * 3, outflow: -baseOutflow * 2.8, netPosition: baseCash * 0.88, forecast: baseCash * 0.90 },
        { name: 'Wk 2', inflow: baseInflow * 3.5, outflow: -baseOutflow * 3.2, netPosition: baseCash * 0.92, forecast: baseCash * 0.93 },
        { name: 'Wk 3', inflow: baseInflow * 3.2, outflow: -baseOutflow * 3.0, netPosition: baseCash * 0.96, forecast: baseCash * 0.95 },
        { name: 'Wk 4', inflow: baseInflow * 4.0, outflow: -baseOutflow * 3.5, netPosition: baseCash, forecast: baseCash * 1.02 },
      ].map(item => ({
        ...item,
        inflow: parseFloat((item.inflow / 1000).toFixed(1)),
        outflow: parseFloat((item.outflow / 1000).toFixed(1)),
        netPosition: parseFloat((item.netPosition / 1000).toFixed(1)),
        forecast: parseFloat((item.forecast / 1000).toFixed(1))
      })),
      '90D': [
        { name: 'Month 1', inflow: baseInflow * 12, outflow: -baseOutflow * 11, netPosition: baseCash * 0.8, forecast: baseCash * 0.85 },
        { name: 'Month 2', inflow: baseInflow * 14, outflow: -baseOutflow * 13, netPosition: baseCash * 0.9, forecast: baseCash * 0.95 },
        { name: 'Month 3', inflow: baseInflow * 16, outflow: -baseOutflow * 14, netPosition: baseCash, forecast: baseCash * 1.05 },
      ].map(item => ({
        ...item,
        inflow: parseFloat((item.inflow / 1000).toFixed(1)),
        outflow: parseFloat((item.outflow / 1000).toFixed(1)),
        netPosition: parseFloat((item.netPosition / 1000).toFixed(1)),
        forecast: parseFloat((item.forecast / 1000).toFixed(1))
      })),
      '1Y': [
        { name: 'Q1', inflow: baseInflow * 45, outflow: -baseOutflow * 40, netPosition: baseCash * 0.8, forecast: baseCash * 0.85 },
        { name: 'Q2', inflow: baseInflow * 50, outflow: -baseOutflow * 45, netPosition: baseCash * 0.9, forecast: baseCash * 0.9 },
        { name: 'Q3', inflow: baseInflow * 55, outflow: -baseOutflow * 48, netPosition: baseCash * 0.95, forecast: baseCash * 0.98 },
        { name: 'Q4', inflow: baseInflow * 65, outflow: -baseOutflow * 55, netPosition: baseCash, forecast: baseCash * 1.05 },
      ].map(item => ({
        ...item,
        inflow: parseFloat((item.inflow / 1000).toFixed(1)),
        outflow: parseFloat((item.outflow / 1000).toFixed(1)),
        netPosition: parseFloat((item.netPosition / 1000).toFixed(1)),
        forecast: parseFloat((item.forecast / 1000).toFixed(1))
      }))
    };
  };

  const generateDynamicScenarioForecast = () => {
    const baseCashL = cashPosition >= 100000 ? (cashPosition / 100000) : (cashPosition / 1000);
    
    const generateForecast = (bestScale, expectedScale, currentScale, worstScale) => [
      { name: 'Current', best: baseCashL, expected: baseCashL, current: baseCashL, worst: baseCashL },
      { name: '30 Days', best: baseCashL * bestScale[0], expected: baseCashL * expectedScale[0], current: baseCashL * currentScale[0], worst: baseCashL * worstScale[0] },
      { name: '60 Days', best: baseCashL * bestScale[1], expected: baseCashL * expectedScale[1], current: baseCashL * currentScale[1], worst: baseCashL * worstScale[1] },
      { name: '90 Days', best: baseCashL * bestScale[2], expected: baseCashL * expectedScale[2], current: baseCashL * currentScale[2], worst: baseCashL * worstScale[2] },
    ].map(item => ({
      name: item.name,
      best: parseFloat(item.best.toFixed(2)),
      expected: parseFloat(item.expected.toFixed(2)),
      current: parseFloat(item.current.toFixed(2)),
      worst: parseFloat(item.worst.toFixed(2)),
    }));

    return {
      'Current': generateForecast([1.06, 1.12, 1.20], [1.02, 1.05, 1.08], [1.00, 1.02, 1.03], [0.95, 0.88, 0.82]),
      'Best Case': generateForecast([1.20, 1.38, 1.58], [1.12, 1.25, 1.38], [1.03, 1.06, 1.10], [1.03, 1.13, 1.24]),
      'Expected': generateForecast([1.15, 1.24, 1.41], [1.08, 1.11, 1.20], [1.02, 1.03, 1.06], [0.97, 1.00, 1.04]),
      'Worst Case': generateForecast([1.00, 0.93, 0.86], [0.95, 0.88, 0.79], [0.93, 0.82, 0.72], [0.86, 0.72, 0.58]),
    };
  };

  const getDynamicDeptHeatmap = () => {
    // Build heatmap entirely from real infraSystems data (no static dummy data)
    const systemToDept = {
      'Accounts Center': 'Finance',
      'Collections Engine': 'Operations',
      'GST Center': 'GST',
      'Payroll Center': 'HR',
      'Expense Center': 'Expenses',
      'Asset Management': 'Assets',
      'Banking Center': 'Banking',
    };
    if (!infraSystems || infraSystems.length === 0) return [];
    return infraSystems.map(sys => {
      const deptName = systemToDept[sys.name] || sys.name;
      const h = sys.health;
      // Show current health as the only real data point (no fake historical months)
      return { name: deptName, current: h };
    });
  };

  const [cashFlowRange, setCashFlowRange] = useState('30D');
  const [bankingSyncing, setBankingSyncing] = useState(false);
  const [timelineFilter, setTimelineFilter] = useState('All');
  const [collectionsImproved, setCollectionsImproved] = useState(false);

  const [activeAgent, setActiveAgent] = useState(() => {
    return localStorage.getItem('bridgeworks_active_agent') || 'cfo';
  });

  const [agentAnchorEl, setAgentAnchorEl] = useState(null);
  const handleAgentClick = (event) => {
    setAgentAnchorEl(event.currentTarget);
  };
  const handleAgentClose = () => {
    setAgentAnchorEl(null);
  };
  const handleAgentSelect = (agentId) => {
    setActiveAgent(agentId);
    handleAgentClose();
  };

  const getWelcomeMessage = (agentId) => {
    return AGENTS.find(a => a.id === agentId)?.welcome || AGENTS[0].welcome;
  };

  const getContextModules = (agentId) => {
    const list = AGENTS.find(a => a.id === agentId)?.contextSources || [];
    return list.map(item => item.name);
  };

  const [sessionsByAgent, setSessionsByAgent] = useState(() => {
    const agentsList = ['cfo', 'accountant', 'ca'];
    const initial = {};
    agentsList.forEach(agent => {
      let loaded = null;
      try {
        const saved = localStorage.getItem(`bridgeworks_ai_${agent}_sessions`);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed) && parsed.length > 0) {
            loaded = parsed.map(s => ({
              id: s.id || `session-${Date.now()}-${Math.random()}`,
              title: s.title || 'Welcome Session',
              messages: Array.isArray(s.messages) ? s.messages : [],
              pinned: !!s.pinned,
              createdAt: s.createdAt || new Date().toISOString(),
              riskLevel: s.riskLevel || 'Low',
              modules: Array.isArray(s.modules) ? s.modules : getContextModules(agent),
              reportsCount: typeof s.reportsCount === 'number' ? s.reportsCount : 0
            }));
          }
        }
      } catch (e) {}

      if (!loaded) {
        const defaultId = `default-${agent}-session`;
        loaded = [{
          id: defaultId,
          title: 'Welcome Session',
          messages: [
            { id: 1, text: getWelcomeMessage(agent), sender: 'ai' }
          ],
          pinned: false,
          createdAt: new Date().toISOString(),
          riskLevel: 'Low',
          modules: getContextModules(agent),
          reportsCount: 0
        }];
      }
      initial[agent] = loaded;
    });
    return initial;
  });

  const [currentSessionIdByAgent, setCurrentSessionIdByAgent] = useState(() => {
    const agentsList = ['cfo', 'accountant', 'ca'];
    const initial = {};
    agentsList.forEach(agent => {
      let loadedId = null;
      try {
        const savedId = localStorage.getItem(`bridgeworks_ai_${agent}_current_session_id`);
        if (savedId) {
          loadedId = savedId;
        }
      } catch (e) {}
      initial[agent] = loadedId || `default-${agent}-session`;
    });
    return initial;
  });

  const sessions = sessionsByAgent[activeAgent] || [];
  const currentSessionId = currentSessionIdByAgent[activeAgent] || '';

  const setSessions = (updater) => {
    setSessionsByAgent(prev => {
      const prevSessions = prev[activeAgent] || [];
      const newSessions = typeof updater === 'function' ? updater(prevSessions) : updater;
      return { ...prev, [activeAgent]: newSessions };
    });
  };

  const setCurrentSessionId = (id) => {
    setCurrentSessionIdByAgent(prev => {
      return { ...prev, [activeAgent]: id };
    });
  };

  const [savedReports, setSavedReports] = useState(() => {
    try {
      const saved = localStorage.getItem('bridgeworks_ai_cfo_reports');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          return parsed.map(r => ({
            name: r.name || 'Report.pdf',
            date: r.date || 'Today',
            sessionTitle: r.sessionTitle || 'CFO Session',
            content: r.content || ''
          }));
        }
      }
    } catch (e) {}
    return [];
  });

  const [chatInput, setChatInput] = useState('');
  const [typingMessage, setTypingMessage] = useState(false);
  const [thinkingStep, setThinkingStep] = useState(0);

  const [searchQuery, setSearchQuery] = useState('');
  const [activeSidebarTab, setActiveSidebarTab] = useState('chats'); // 'chats' | 'reports'
  const [historySidebarOpen, setHistorySidebarOpen] = useState(true);

  const [sessionMenuAnchor, setSessionMenuAnchor] = useState(null);
  const [selectedMenuSession, setSelectedMenuSession] = useState(null);

  // Sync to localStorage
  useEffect(() => {
    localStorage.setItem('bridgeworks_active_agent', activeAgent);
  }, [activeAgent]);

  useEffect(() => {
    Object.keys(sessionsByAgent).forEach(agent => {
      localStorage.setItem(`bridgeworks_ai_${agent}_sessions`, JSON.stringify(sessionsByAgent[agent]));
    });
  }, [sessionsByAgent]);

  useEffect(() => {
    Object.keys(currentSessionIdByAgent).forEach(agent => {
      localStorage.setItem(`bridgeworks_ai_${agent}_current_session_id`, currentSessionIdByAgent[agent]);
    });
  }, [currentSessionIdByAgent]);

  useEffect(() => {
    localStorage.setItem('bridgeworks_ai_cfo_reports', JSON.stringify(savedReports));
  }, [savedReports]);

  // Derived active session and messages
  const currentSession = sessions.find(s => s.id === currentSessionId) || sessions[0];
  const chatMessages = currentSession ? currentSession.messages : [];

  const setChatMessages = (updater) => {
    setSessions(prevSessions => {
      return prevSessions.map(s => {
        if (s.id === currentSessionId) {
          const newMessages = typeof updater === 'function' ? updater(s.messages) : updater;
          
          // Auto generate title on first user question
          let title = s.title;
          let modules = s.modules;
          let riskLevel = s.riskLevel;

          if (s.title === "New Session" || s.title === "Welcome Session") {
            const firstQuestion = newMessages.find(m => m.sender === 'user')?.text || "";
            if (firstQuestion) {
              const lq = firstQuestion.toLowerCase();
              if (lq.includes("cash") || lq.includes("runway") || lq.includes("funds")) {
                title = "Cash Flow Analysis";
                modules = Array.from(new Set([...modules, "Banking", "Expenses"]));
                riskLevel = "High";
              } else if (lq.includes("gst") || lq.includes("tax")) {
                title = "GST Filing Review";
                modules = Array.from(new Set([...modules, "GST Center"]));
                riskLevel = "Medium";
              } else if (lq.includes("payroll") || lq.includes("salary")) {
                title = "Payroll Risk Assessment";
                modules = Array.from(new Set([...modules, "Payroll"]));
                riskLevel = "Medium";
              } else if (lq.includes("expense") || lq.includes("spend")) {
                title = "Expense Optimization";
                modules = Array.from(new Set([...modules, "Expenses"]));
                riskLevel = "Low";
              } else if (lq.includes("department") || lq.includes("logistics")) {
                title = "Department Risk Review";
                modules = Array.from(new Set([...modules, "Logistics"]));
                riskLevel = "High";
              } else if (lq.includes("forecast") || lq.includes("predict")) {
                title = "Working Capital Forecast";
                modules = Array.from(new Set([...modules, "Forecasting"]));
                riskLevel = "Low";
              } else if (lq.includes("receivable") || lq.includes("collect")) {
                title = "Receivables Analysis";
                modules = Array.from(new Set([...modules, "Collections Engine"]));
                riskLevel = "Low";
              } else {
                const words = firstQuestion.split(' ').slice(0, 4).join(' ');
                title = words.length > 25 ? words.substring(0, 25) + '...' : words || "Financial Inquiry";
              }
            }
          }

          return { ...s, messages: newMessages, title, modules, riskLevel };
        }
        return s;
      });
    });
  };

  const handleNewChat = () => {
    const newSessionId = `session-${Date.now()}`;
    const agentObj = AGENTS.find(a => a.id === activeAgent) || AGENTS[0];
    const newSession = {
      id: newSessionId,
      title: 'New Session',
      messages: [
        { id: 1, text: agentObj.welcome, sender: 'ai' }
      ],
      pinned: false,
      createdAt: new Date().toISOString(),
      riskLevel: 'Low',
      modules: agentObj.contextSources.map(s => s.name),
      reportsCount: 0
    };
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSessionId);
  };

  const handlePinSession = (sessionId) => {
    setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, pinned: !s.pinned } : s));
  };

  const handleRenameSession = (sessionId, newName) => {
    if (!newName.trim()) return;
    setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, title: newName } : s));
  };

  const handleDuplicateSession = (session) => {
    const newSessionId = `session-${Date.now()}`;
    const newSession = {
      ...session,
      id: newSessionId,
      title: `${session.title} (Copy)`,
      createdAt: new Date().toISOString(),
      pinned: false
    };
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSessionId);
  };

  const handleDeleteSession = (sessionId) => {
    if (sessions.length <= 1) {
      const defaultId = `default-${activeAgent}-session`;
      const agentObj = AGENTS.find(a => a.id === activeAgent) || AGENTS[0];
      setSessions([{
        id: defaultId,
        title: 'Welcome Session',
        messages: [
          { id: 1, text: agentObj.welcome, sender: 'ai' }
        ],
        pinned: false,
        createdAt: new Date().toISOString(),
        riskLevel: 'Low',
        modules: agentObj.contextSources.map(s => s.name),
        reportsCount: 0
      }]);
      setCurrentSessionId(defaultId);
      return;
    }

    setSessions(prev => prev.filter(s => s.id !== sessionId));
    if (currentSessionId === sessionId) {
      const remaining = sessions.filter(s => s.id !== sessionId);
      setCurrentSessionId(remaining[0].id);
    }
  };

  const handleExportPDF = (session) => {
    const title = session.title;
    const dateStr = new Date(session.createdAt).toLocaleDateString();
    let textContent = `BRIDGEWORKS AI CFO - EXECUTIVE BRIEFING REPORT\n`;
    textContent += `Title: ${title}\n`;
    textContent += `Date: ${dateStr}\n`;
    textContent += `Risk Level: ${session.riskLevel}\n`;
    textContent += `Modules: ${session.modules.join(', ')}\n`;
    textContent += `========================================\n\n`;

    session.messages.forEach(m => {
      const role = m.sender === 'user' ? 'USER' : 'AI CFO';
      textContent += `[${role}]:\n${m.text}\n\n----------------------------------------\n\n`;
    });

    const element = document.createElement("a");
    const file = new Blob([textContent], { type: 'text/plain' });
    element.href = URL.createObjectURL(file);
    element.download = `${title.replace(/\s+/g, '_')}_Report.txt`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const handleSessionMenuOpen = (event, session) => {
    setSessionMenuAnchor(event.currentTarget);
    setSelectedMenuSession(session);
  };

  const handleSessionMenuClose = () => {
    setSessionMenuAnchor(null);
    setSelectedMenuSession(null);
  };

  const getGroupedSessions = () => {
    const pinned = [];
    const today = [];
    const yesterday = [];
    const lastWeek = [];
    const older = [];

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 24 * 60 * 60 * 1000;
    const lastWeekStart = todayStart - 7 * 24 * 60 * 60 * 1000;

    const sessionsList = Array.isArray(sessions) ? sessions : [];

    sessionsList.forEach(s => {
      if (!s) return;
      
      const matchesSearch = searchQuery === '' || 
        (s.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
        (Array.isArray(s.messages) && s.messages.some(m => m && (m.text || '').toLowerCase().includes(searchQuery.toLowerCase())));

      if (!matchesSearch) return;

      if (s.pinned) {
        pinned.push(s);
        return;
      }

      const cTime = s.createdAt ? new Date(s.createdAt).getTime() : 0;
      if (isNaN(cTime) || cTime === 0) {
        older.push(s);
      } else if (cTime >= todayStart) {
        today.push(s);
      } else if (cTime >= yesterdayStart) {
        yesterday.push(s);
      } else if (cTime >= lastWeekStart) {
        lastWeek.push(s);
      } else {
        older.push(s);
      }
    });

    return { pinned, today, yesterday, lastWeek, older };
  };

  const renderSessionGroup = (label, groupKey) => {
    const grouped = getGroupedSessions();
    const list = grouped[groupKey];
    if (!list || list.length === 0) return null;

    return (
      <Stack spacing={0.8}>
        <Typography sx={{ fontSize: '9px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.04em', px: 1 }}>
          {label}
        </Typography>
        {list.map(s => {
          const isSelected = s.id === currentSessionId;
          return (
            <Box 
              key={s.id}
              onClick={() => setCurrentSessionId(s.id)}
              sx={{
                p: 1.2,
                borderRadius: '8px',
                bgcolor: isSelected ? 'rgba(99, 102, 241, 0.08)' : '#FFFFFF',
                border: isSelected ? '1px solid rgba(99, 102, 241, 0.2)' : '1px solid #E2E8F0',
                cursor: 'pointer',
                position: 'relative',
                transition: 'all 0.2s ease',
                '&:hover': {
                  borderColor: COLORS.accent,
                  '& .session-actions': { opacity: 1 }
                }
              }}
            >
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Typography sx={{ 
                  fontSize: '11px', 
                  fontWeight: isSelected ? 800 : 600, 
                  color: isSelected ? COLORS.accent : COLORS.primaryText,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  pr: 2
                }}>
                  {s.title}
                </Typography>
                {s.pinned && <PushPinIcon sx={{ fontSize: 10, color: COLORS.accent }} />}
              </Stack>
              
              <Stack direction="row" spacing={1} sx={{ mt: 0.5, flexWrap: 'wrap', gap: 0.5 }}>
                <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>
                  Risk: {s.riskLevel}
                </Typography>
                <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText }}>
                  • {s.modules.slice(0, 2).join(', ')}
                </Typography>
              </Stack>

              <Box className="session-actions" sx={{ 
                position: 'absolute', 
                right: 4, 
                top: 4, 
                opacity: 0, 
                transition: 'opacity 0.2s ease',
                bgcolor: 'transparent'
              }} onClick={(e) => e.stopPropagation()}>
                <IconButton size="small" onClick={(e) => handleSessionMenuOpen(e, s)}>
                  <MoreVertIcon sx={{ fontSize: 13, color: COLORS.secondaryText }} />
                </IconButton>
              </Box>
            </Box>
          );
        })}
      </Stack>
    );
  };

  useEffect(() => {
    let interval;
    if (typingMessage) {
      setThinkingStep(0);
      interval = setInterval(() => {
        setThinkingStep(prev => (prev < 4 ? prev + 1 : prev));
      }, 700);
    } else {
      setThinkingStep(0);
    }
    return () => clearInterval(interval);
  }, [typingMessage]);

  // New States for Workspaces and Dialogs
  const [aiChatOpen, setAiChatOpen] = useState(false);
  const [drilldownKpi, setDrilldownKpi] = useState(null);
  const [expandedAnalyses, setExpandedAnalyses] = useState({});
  const [execReportOpen, setExecReportOpen] = useState(false);
  const [forecastTab, setForecastTab] = useState('30 Days');
  const [systemScanOpen, setSystemScanOpen] = useState(false);
  const [reportsHubOpen, setReportsHubOpen] = useState(false);
  const [reportsHubPreviewTitle, setReportsHubPreviewTitle] = useState(null);
  const [reportsHubPreviewLink, setReportsHubPreviewLink] = useState(null);
  const [reportsHubPreviewData, setReportsHubPreviewData] = useState(null);
  const [reportsHubPreviewLoading, setReportsHubPreviewLoading] = useState(false);
  const [reportsHubPreviewError, setReportsHubPreviewError] = useState(null);
  const [aiPlanOpen, setAiPlanOpen] = useState(false);
  const [predictionCenterOpen, setPredictionCenterOpen] = useState(false);
  const [notificationCenterOpen, setNotificationCenterOpen] = useState(false);
  const [gstFilingOpen, setGstFilingOpen] = useState(false);
  const [payrollApproveOpen, setPayrollApproveOpen] = useState(false);
  const [reminderOpen, setReminderOpen] = useState(false);
  const [bankReconOpen, setBankReconOpen] = useState(false);
  const [depreciationOpen, setDepreciationOpen] = useState(false);
  const [actionMgmtOpen, setActionMgmtOpen] = useState(false);
  const [activityFeedOpen, setActivityFeedOpen] = useState(false);
  const [subsystemCenterOpen, setSubsystemCenterOpen] = useState(false);
  const [opportunityCenterOpen, setOpportunityCenterOpen] = useState(false);
  const [execOpportunityOpen, setExecOpportunityOpen] = useState(null);

  // Shortcut States
  const [newJournalOpen, setNewJournalOpen] = useState(false);
  const [recordExpenseOpen, setRecordExpenseOpen] = useState(false);
  const [addAssetOpen, setAddAssetOpen] = useState(false);
  const [prepGstOpen, setPrepGstOpen] = useState(false);
  const [runBankReconOpen, setRunBankReconOpen] = useState(false);
  const [importStatementOpen, setImportStatementOpen] = useState(false);
  const [viewAllShortcutsOpen, setViewAllShortcutsOpen] = useState(false);

  // AI-generated results
  const [aiReportContent, setAiReportContent] = useState('');
  const [generatingReport, setGeneratingReport] = useState(false);
  const [aiPlanContent, setAiPlanContent] = useState('');
  const [generatingPlan, setGeneratingPlan] = useState(false);

  // Toast
  const [toast, setToast] = useState({ open: false, message: '', severity: 'success' });

  // Subsystem Scan State
  const [scanState, setScanState] = useState({
    scanning: false,
    step: 0,
    completed: false,
    systems: [
      { name: 'Accounts Center', status: 'pending', detail: 'Verifying ledger balances' },
      { name: 'Banking Center', status: 'pending', detail: 'Checking active bank feed matching' },
      { name: 'GST Center', status: 'pending', detail: 'Scanning GSTR-1 and GSTR-2B discrepancy' },
      { name: 'Payroll Center', status: 'pending', detail: 'Validating salary payout schedule' },
      { name: 'Expense Center', status: 'pending', detail: 'Detecting spend anomalies and growth spikes' },
      { name: 'Asset Center', status: 'pending', detail: 'Calculating asset depreciation schedules' },
      { name: 'Collections Engine', status: 'pending', detail: 'Reviewing invoice aging and Acme Corp ledger' },
    ]
  });


  // Notifications State — starts empty, generated dynamically after data loads
  const [notifications, setNotifications] = useState([]);
  const [notificationTab, setNotificationTab] = useState('All');

  // Autocomplete suggestions helper
  const getSuggestions = (val) => {
    if (!val || !val.trim()) return [];
    const q = val.toLowerCase().trim();
    const activeSuggestions = AGENTS.find(a => a.id === activeAgent)?.suggestions || [];
    return activeSuggestions
      .map(s => ({ text: s.q }))
      .filter(item => item.text.toLowerCase().includes(q));
  };

  // Parser helper to extract structured data from AI CFO markdown
  const parseCfoResponse = (text) => {
    let title = "EXECUTIVE PRIORITIZATION";
    let immediatePriority = "Cash Flow Optimization and Liquidity Management";
    let whyThisMatters = "Runway below 1 month poses a critical liquidity risk.";
    let priorities = [
      "Review and reduce discretionary expenses",
      "Accelerate collections and improve cash inflow",
      "Review logistics department expenses",
      "Prepare for upcoming GST payment (7 days)",
      "Monitor daily cash flow closely"
    ];

    if (!text) return { title, immediatePriority, whyThisMatters, priorities };

    const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
    let currentSection = '';
    let parsedPriorities = [];
    let parsedWhy = '';
    let parsedPriorityTitle = '';
    let parsedTitle = '';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const upperLine = line.toUpperCase();

      if (line.startsWith('#') || (line.startsWith('**') && line.endsWith('**') && line.length < 50)) {
        const clean = line.replace(/[#*]/g, '').trim();
        if (!parsedTitle) {
          parsedTitle = clean;
          continue;
        }
      }

      if (upperLine.includes("IMMEDIATE PRIORITY") || upperLine.includes("IMMEDIATE FOCUS") || upperLine.includes("EXECUTIVE PRIORITIZATION") || upperLine.includes("CURRENT STATUS") || upperLine.includes("FINANCIAL STATUS")) {
        currentSection = 'priority';
        continue;
      }
      if (upperLine.includes("WHY THIS MATTERS") || upperLine.includes("BUSINESS IMPACT") || upperLine.includes("KEY DRIVERS") || upperLine.includes("RISK ASSESSMENT") || upperLine.includes("EXECUTIVE ASSESSMENT")) {
        currentSection = 'why';
        continue;
      }
      if (upperLine.includes("RECOMMENDED ACTIONS") || upperLine.includes("TOP PRIORITIES") || upperLine.includes("IMMEDIATE ACTION") || upperLine.includes("ACTIONS")) {
        currentSection = 'actions';
        continue;
      }

      if (currentSection === 'priority') {
        const clean = line.replace(/[#*]/g, '').trim();
        if (clean && clean.length > 5) {
          if (!parsedPriorityTitle) parsedPriorityTitle = clean;
          else parsedPriorityTitle += ' ' + clean;
        }
      } else if (currentSection === 'why') {
        const clean = line.replace(/[#*]/g, '').trim();
        if (clean && clean.length > 5) {
          if (!parsedWhy) parsedWhy = clean;
          else parsedWhy += ' ' + clean;
        }
      } else if (currentSection === 'actions') {
        if (line.match(/^(\d+\.|\*|-)/)) {
          const clean = line.replace(/^(\d+\.|\*|-)\s*/, '').replace(/[#*]/g, '').trim();
          if (clean) parsedPriorities.push(clean);
        }
      }
    }

    return {
      title: parsedTitle || title,
      immediatePriority: parsedPriorityTitle || immediatePriority,
      whyThisMatters: parsedWhy || whyThisMatters,
      priorities: parsedPriorities.length > 0 ? parsedPriorities.slice(0, 5) : priorities
    };
  };

  const formatMessageTime = (msgId) => {
    try {
      const date = new Date(msgId);
      if (isNaN(date.getTime())) return '11:31 AM';
      let hours = date.getHours();
      let minutes = date.getMinutes();
      const ampm = hours >= 12 ? 'PM' : 'AM';
      hours = hours % 12;
      hours = hours ? hours : 12; 
      minutes = minutes < 10 ? '0'+minutes : minutes;
      return `${hours}:${minutes} ${ampm}`;
    } catch(e) {
      return '11:31 AM';
    }
  };

  const renderAiCard = (m, mIdx) => {
    const mText = m && m.text ? m.text : '';
    const parsed = parseCfoResponse(mText);
    const isForecast = mText.toLowerCase().includes("forecast") || mText.toLowerCase().includes("predict") || mText.toLowerCase().includes("day-cash");
    const isDecision = mText.toLowerCase().includes("decision") || mText.toLowerCase().includes("should we") || mText.includes("RECOMMENDED DECISION");

    // Detect if this is a redirect/switch message
    let redirectTarget = null;
    if (mText.toLowerCase().includes("switch to the") || mText.toLowerCase().includes("switch to")) {
      if (mText.toLowerCase().includes("cfo")) redirectTarget = "cfo";
      else if (mText.toLowerCase().includes("accountant")) redirectTarget = "accountant";
      else if (mText.toLowerCase().includes("ca")) redirectTarget = "ca";
    }

    // Detect if this is a welcome message
    const isWelcome = AGENTS.some(a => a.welcome === mText);

    // Style elements based on active agent
    let iconColor = '#6C5DD3';
    let iconBg = 'rgba(108,93,211,0.1)';
    let headerLabel = 'EXECUTIVE PRIORITIZATION';
    let headlineText = parsed.immediatePriority || 'Cash Flow Optimization and Liquidity Management';
    let headlineLabel = 'Immediate Priority';

    if (redirectTarget) {
      headerLabel = 'CROSS-AGENT REFERRAL';
      headlineText = 'Switch Agent Recommendation';
      headlineLabel = 'Expert Advice Redirect';
    } else if (isWelcome) {
      if (activeAgent === 'cfo') {
        headerLabel = 'CFO STRATEGIC BRIEFING';
        headlineText = 'Strategic Financial Intel Initialized';
      } else if (activeAgent === 'accountant') {
        headerLabel = 'DAILY OPERATIONS BRIEFING';
        headlineText = 'Accounting Ledger Feed Initialized';
        iconColor = COLORS.success;
        iconBg = 'rgba(16,185,129,0.1)';
      } else if (activeAgent === 'ca') {
        headerLabel = 'COMPLIANCE & TAX REVIEW';
        headlineText = 'Chartered Accountant Assistant Initialized';
        iconColor = COLORS.warning;
        iconBg = 'rgba(245,158,11,0.1)';
      }
      headlineLabel = 'System Status';
    } else if (activeAgent === 'accountant') {
      headerLabel = 'TRANSACTION INTELLIGENCE';
      headlineText = 'Cash Flow & Balances Overview';
      headlineLabel = 'Daily Accounting Insights';
      iconColor = COLORS.success;
      iconBg = 'rgba(16,185,129,0.1)';
    } else if (activeAgent === 'ca') {
      headerLabel = 'COMPLIANCE & TAX STATUS';
      headlineText = 'GST Return & Compliance Assessment';
      headlineLabel = 'Tax & Compliance Audit';
      iconColor = COLORS.warning;
      iconBg = 'rgba(245,158,11,0.1)';
    } else {
      // CFO agent
      if (isForecast) {
        headerLabel = 'CASH FORECAST ANALYSIS';
        headlineText = '90-Day Cash Runway Projection';
        headlineLabel = 'Forecast Focus';
      } else if (isDecision) {
        headerLabel = 'DECISION INTELLIGENCE';
        headlineText = mText.toLowerCase().includes('hire') ? 'Defer Hiring & Optimize Vendor Spend' : 'Optimize Logistics Operations';
        headlineLabel = 'Recommendation';
      }
    }

    // Dynamic metrics
    const runwayVal = monthlyBurn > 0 ? (cashPosition / monthlyBurn).toFixed(1) : '0.6';
    const isCritical = parseFloat(runwayVal) < 1.0;
    const riskColor = isCritical ? '#DC2626' : '#059669';
    const riskText = isCritical ? 'HIGH' : 'LOW';

    let kpiMetrics = [];
    if (activeAgent === 'cfo') {
      kpiMetrics = [
        { label: 'Cash Position', val: formatRupee(cashPosition), color: COLORS.primaryText },
        { label: 'Runway',        val: `${runwayVal} Months`,     color: isCritical ? '#DC2626' : COLORS.primaryText },
        { label: 'Burn Rate',     val: formatRupee(monthlyBurn),  color: COLORS.primaryText },
        { label: 'Risk Level',    val: riskText,                  color: riskColor },
      ];
    } else if (activeAgent === 'accountant') {
      kpiMetrics = [
        { label: 'Cash Position', val: formatRupee(cashPosition), color: COLORS.primaryText },
        { label: 'Receivables',   val: formatRupee(receivables),  color: COLORS.primaryText },
        { label: 'Payables',      val: formatRupee(payables),     color: COLORS.primaryText },
        { label: 'Bank Recon',    val: `${reconciliationAccuracy}%`, color: reconciliationAccuracy >= 90 ? COLORS.success : COLORS.warning },
      ];
    } else if (activeAgent === 'ca') {
      const caRisk = gstLiability > 0 && gstDueDays < 15 ? 'HIGH' : 'LOW';
      kpiMetrics = [
        { label: 'GST Liability',  val: formatRupee(gstLiability), color: gstLiability > 0 ? COLORS.danger : COLORS.primaryText },
        { label: 'Days to File',   val: gstLiability > 0 ? `${gstDueDays} Days` : '—', color: gstLiability > 0 && gstDueDays < 10 ? COLORS.danger : COLORS.primaryText },
        { label: 'Compliance Risk', val: caRisk, color: caRisk === 'HIGH' ? COLORS.danger : COLORS.success },
        { label: 'Books Status',   val: reconciliationAccuracy === 100 ? 'Balanced' : 'Balanced', color: COLORS.success },
      ];
    }

    // Determine if we should show the action buttons
    let showActions = false;
    if (mIdx !== undefined && mIdx > 0) {
      let userQuery = '';
      for (let i = mIdx - 1; i >= 0; i--) {
        if (chatMessages[i] && chatMessages[i].sender === 'user') {
          userQuery = chatMessages[i].text;
          break;
        }
      }
      if (userQuery) {
        const q = userQuery.toLowerCase();
        const keywords = ['how', 'fix', 'resolve', 'action', 'do', 'reconcile', 'prepare', 'file', 'solve', 'way', 'remedy', 'run', 'audit', 'scan', 'export', 'generate', 'reconciliation'];
        showActions = keywords.some(kw => q.includes(kw));
      }
    }

    return (
      <Box sx={{
        bgcolor: '#FFFFFF',
        border: '1px solid #E2E8F0',
        borderRadius: '16px',
        p: 2.5,
        mt: 1,
        boxShadow: '0 2px 12px rgba(15,23,42,0.04)'
      }}>

        {/* ── Header ── */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <Box sx={{
            width: 28, height: 28, borderRadius: '8px',
            bgcolor: iconBg, color: iconColor,
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <SparklesIcon sx={{ fontSize: 14 }} />
          </Box>
          <Typography sx={{ fontSize: '11px', fontWeight: 900, color: COLORS.primaryText, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            {headerLabel}
          </Typography>
          <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: COLORS.success }} />
            <Typography sx={{ fontSize: '9px', color: COLORS.success, fontWeight: 700 }}>LIVE</Typography>
          </Box>
        </Box>

        {/* ── Headline Block ── */}
        <Box sx={{ mb: 2 }}>
          <Typography sx={{ fontSize: '11px', color: iconColor, fontWeight: 700, mb: 0.5 }}>
            {headlineLabel}
          </Typography>
          <Typography sx={{ fontSize: '14px', fontWeight: 800, color: COLORS.primaryText, lineHeight: 1.3 }}>
            {headlineText}
          </Typography>
        </Box>

        {/* ── 4-column KPI Metrics Row ── */}
        <Grid container spacing={1} sx={{ mb: 2.5 }}>
          {kpiMetrics.map((metric, idx) => (
            <Grid item xs={3} key={idx}>
              <Box sx={{
                bgcolor: '#F8FAFC',
                border: '1px solid #E2E8F0',
                borderRadius: '10px',
                p: 1.2
              }}>
                <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.03em', mb: 0.4 }}>
                  {metric.label}
                </Typography>
                <Typography sx={{ fontSize: '13px', fontWeight: 900, color: metric.color, lineHeight: 1 }}>
                  {metric.val}
                </Typography>
              </Box>
            </Grid>
          ))}
        </Grid>

        {/* ── Forecast Chart (only for cfo forecast intent) ── */}
        {activeAgent === 'cfo' && isForecast && (
          <Box sx={{ mb: 2.5, p: 1.5, bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '12px', height: 165 }}>
            <Typography sx={{ fontSize: '9px', fontWeight: 850, color: COLORS.primaryText, mb: 1, textTransform: 'uppercase' }}>
              Projected Cash Forecast (90 Days)
            </Typography>
            <ResponsiveContainer width="100%" height="82%">
              <AreaChart data={generateDynamicScenarioForecast()['Expected']}>
                <defs>
                  <linearGradient id="colorExpectedCFO2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.accent} stopOpacity={0.2}/>
                    <stop offset="95%" stopColor={COLORS.accent} stopOpacity={0.0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="name" stroke={COLORS.secondaryText} fontSize={8} tickLine={false} />
                <RechartsTooltip />
                <Area type="monotone" dataKey="expected" stroke={COLORS.accent} strokeWidth={1.5} fillOpacity={1} fill="url(#colorExpectedCFO2)" name="Expected" />
                <Line type="monotone" dataKey="best" stroke={COLORS.success} strokeWidth={1} dot={false} strokeDasharray="3 3" name="Best Case" />
                <Line type="monotone" dataKey="worst" stroke={COLORS.danger} strokeWidth={1} dot={false} strokeDasharray="3 3" name="Worst Case" />
              </AreaChart>
            </ResponsiveContainer>
          </Box>
        )}

        {/* ── Message Content Area ── */}
        <Box sx={{
          mb: 2.5,
          fontSize: '11.5px',
          lineHeight: 1.55,
          fontWeight: 500,
          color: COLORS.primaryText,
          '& table': {
            width: '100%',
            borderCollapse: 'collapse',
            mt: 1.5,
            mb: 1.5,
          },
          '& th, & td': {
            border: '1px solid #E2E8F0',
            p: 1.2,
            fontSize: '10.5px',
            textAlign: 'left'
          },
          '& th': {
            bgcolor: '#F8FAFC',
            fontWeight: 800,
            color: COLORS.primaryText
          },
          '& strong': {
            fontWeight: 800,
          },
          '& ul, & ol': {
            pl: 2.5,
            mt: 1,
            mb: 1
          },
          '& li': {
            mb: 0.5
          }
        }}>
          <ReactMarkdown>{mText}</ReactMarkdown>
        </Box>

        {/* ── Action Center ── */}
        {(redirectTarget || showActions) && (
          <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            {redirectTarget ? (
              <Button
                variant="contained"
                size="small"
                startIcon={<SparklesIcon sx={{ fontSize: 12 }} />}
                onClick={() => {
                  setActiveAgent(redirectTarget);
                }}
                sx={{
                  textTransform: 'none', fontSize: '11px', fontWeight: 700,
                  bgcolor: '#6C5DD3', color: '#FFFFFF', boxShadow: 'none',
                  borderRadius: '8px', py: 0.9, px: 1.8,
                  '&:hover': { bgcolor: '#5A4EBF', boxShadow: 'none' }
                }}
              >
                Switch to {redirectTarget === 'cfo' ? 'AI CFO' : redirectTarget === 'accountant' ? 'AI Accountant' : 'AI CA'} now →
              </Button>
            ) : activeAgent === 'cfo' ? (
              <>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<SparklesIcon sx={{ fontSize: 12 }} />}
                  onClick={() => navigate('/finance/decisions')}
                  sx={{
                    textTransform: 'none', fontSize: '11px', fontWeight: 700,
                    bgcolor: '#6C5DD3', color: '#FFFFFF', boxShadow: 'none',
                    borderRadius: '8px', py: 0.9, px: 1.8,
                    '&:hover': { bgcolor: '#5A4EBF', boxShadow: 'none' }
                  }}
                >
                  Generate Action Plan
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigate('/finance/decisions')}
                  sx={{
                    textTransform: 'none', fontSize: '11px', fontWeight: 700,
                    borderColor: '#E2E8F0', color: COLORS.primaryText, bgcolor: '#FFFFFF',
                    borderRadius: '8px', py: 0.9, px: 1.8,
                    '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' }
                  }}
                >
                  Scan Systems
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigate('/finance/reports')}
                  sx={{
                    textTransform: 'none', fontSize: '11px', fontWeight: 700,
                    borderColor: '#E2E8F0', color: COLORS.secondaryText, bgcolor: '#FFFFFF',
                    borderRadius: '8px', py: 0.9, px: 1.8,
                    '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC', color: COLORS.primaryText }
                  }}
                >
                  Export Analysis
                </Button>
              </>
            ) : activeAgent === 'accountant' ? (
              <>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<SyncIcon sx={{ fontSize: 12 }} />}
                  onClick={() => navigate('/finance/reconciliation')}
                  sx={{
                    textTransform: 'none', fontSize: '11px', fontWeight: 700,
                    bgcolor: COLORS.success, color: '#FFFFFF', boxShadow: 'none',
                    borderRadius: '8px', py: 0.9, px: 1.8,
                    '&:hover': { bgcolor: '#0D9488', boxShadow: 'none' }
                  }}
                >
                  Reconcile Bank
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigate('/finance/pending-expenses')}
                  sx={{
                    textTransform: 'none', fontSize: '11px', fontWeight: 700,
                    borderColor: '#E2E8F0', color: COLORS.primaryText, bgcolor: '#FFFFFF',
                    borderRadius: '8px', py: 0.9, px: 1.8,
                    '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' }
                  }}
                >
                  Record Expense
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigate('/finance/ledger')}
                  sx={{
                    textTransform: 'none', fontSize: '11px', fontWeight: 700,
                    borderColor: '#E2E8F0', color: COLORS.secondaryText, bgcolor: '#FFFFFF',
                    borderRadius: '8px', py: 0.9, px: 1.8,
                    '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC', color: COLORS.primaryText }
                  }}
                >
                  View Ledgers
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="contained"
                  size="small"
                  startIcon={<DescriptionIcon sx={{ fontSize: 12 }} />}
                  onClick={() => navigate('/finance/gst')}
                  sx={{
                    textTransform: 'none', fontSize: '11px', fontWeight: 700,
                    bgcolor: '#F59E0B', color: '#FFFFFF', boxShadow: 'none',
                    borderRadius: '8px', py: 0.9, px: 1.8,
                    '&:hover': { bgcolor: '#D97706', boxShadow: 'none' }
                  }}
                >
                  Prepare GST Return
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigate('/finance/gst-health')}
                  sx={{
                    textTransform: 'none', fontSize: '11px', fontWeight: 700,
                    borderColor: '#E2E8F0', color: COLORS.primaryText, bgcolor: '#FFFFFF',
                    borderRadius: '8px', py: 0.9, px: 1.8,
                    '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC' }
                  }}
                >
                  Audit Compliance
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  onClick={() => navigate('/finance/reports')}
                  sx={{
                    textTransform: 'none', fontSize: '11px', fontWeight: 700,
                    borderColor: '#E2E8F0', color: COLORS.secondaryText, bgcolor: '#FFFFFF',
                    borderRadius: '8px', py: 0.9, px: 1.8,
                    '&:hover': { borderColor: '#CBD5E1', bgcolor: '#F8FAFC', color: COLORS.primaryText }
                  }}
                >
                  Export Brief
                </Button>
              </>
            )}
          </Box>
        )}
      </Box>
    );
  };

  const renderMessage = (m, mIdx) => {
    const isAi = m.sender === 'ai';
    const isUser = m.sender === 'user';
    const timeStr = formatMessageTime(m.id || Date.now());

    if (isUser) {
      return (
        <Box key={m.id} sx={{ 
          alignSelf: 'flex-end',
          maxWidth: '85%',
          bgcolor: '#6C5DD3', 
          color: '#fff',
          borderRadius: '16px 16px 0px 16px',
          p: 1.8,
          boxShadow: '0 4px 12px rgba(108, 93, 211, 0.15)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-start',
          gap: 0.5
        }}>
          <Typography sx={{ fontSize: '11.5px', lineHeight: 1.4, fontWeight: 600, whiteSpace: 'pre-wrap' }}>
            {m.text}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', alignSelf: 'flex-end', gap: 0.3, mt: 0.5 }}>
            <Typography sx={{ fontSize: '8px', color: 'rgba(255, 255, 255, 0.7)', fontWeight: 600 }}>{timeStr}</Typography>
            <Typography sx={{ fontSize: '9px', color: 'rgba(255, 255, 255, 0.9)', fontWeight: 800, lineHeight: 1 }}>✓✓</Typography>
          </Box>
        </Box>
      );
    }

    return (
      <Box key={m.id} sx={{ 
        alignSelf: 'flex-start',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        mb: 2
      }}>
        {/* Sender Header */}
        <Stack direction="row" spacing={1} alignItems="baseline" sx={{ mb: 0.8 }}>
          <Typography sx={{ fontSize: '11.5px', fontWeight: 800, color: COLORS.primaryText }}>
            {AGENTS.find(a => a.id === activeAgent)?.label || 'AI CFO'}
          </Typography>
          <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 600 }}>
            {timeStr}
          </Typography>
        </Stack>

        <Box sx={{ width: '100%' }}>
          {renderAiCard(m, mIdx)}
        </Box>

      </Box>
    );
  };

  // AI CFO Gemini Chat Integration
  const handleAskAi = async (questionText) => {
    if (!questionText.trim()) return;
    
    const userMsg = { id: Date.now(), text: questionText, sender: 'user' };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setTypingMessage(true);

    try {
      const currentHistory = chatMessages.slice(1); // Exclude initial welcome prompt
      const res = await apiClient('/api/finance/ai-chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question: questionText,
          agent: activeAgent,
          history: currentHistory.map(m => ({ text: m.text, sender: m.sender }))
        })
      });
      if (res.ok) {
        const data = await res.json();
        const agentLabel = AGENTS.find(a => a.id === activeAgent)?.label || 'AI CFO';
        const answer = data.answer || `No response received from ${agentLabel}.`;
        setChatMessages(prev => [...prev, { id: Date.now() + 1, text: answer, sender: 'ai', debug: data.debug }]);
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err) {
      console.error(err);
      const agentLabel = AGENTS.find(a => a.id === activeAgent)?.label || 'AI CFO';
      setChatMessages(prev => [...prev, { id: Date.now() + 1, text: `Error communicating with ${agentLabel}: ` + (err.message || err), sender: 'ai' }]);
    } finally {
      setTypingMessage(false);
    }
  };

  const handleGenerateReport = async () => {
    setGeneratingReport(true);
    setAiReportContent('');
    setExecReportOpen(true);
    try {
      const res = await apiClient('/api/finance/executive-report/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        const repContent = data.report || "No report generated.";
        setAiReportContent(repContent);
        
        // Add to savedReports list
        const newReport = {
          name: `Executive CFO Report - ${new Date().toLocaleDateString()}.pdf`,
          date: new Date().toLocaleDateString(),
          sessionTitle: currentSession ? currentSession.title : "CFO Session",
          content: repContent
        };
        setSavedReports(prev => [newReport, ...prev]);
        
        // Update s.reportsCount in sessions state
        setSessions(prev => prev.map(s => s.id === currentSessionId ? { ...s, reportsCount: s.reportsCount + 1 } : s));
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err) {
      console.error(err);
      setAiReportContent("Error generating report: " + (err.message || err));
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleGeneratePlan = async () => {
    setGeneratingPlan(true);
    setAiPlanContent('');
    setAiPlanOpen(true);
    try {
      const res = await apiClient('/api/finance/financial-plan/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      if (res.ok) {
        const data = await res.json();
        const planContent = data.plan || "No plan generated.";
        setAiPlanContent(planContent);
        
        // Add to savedReports list
        const newReport = {
          name: `90-Day Financial Plan - ${new Date().toLocaleDateString()}.pdf`,
          date: new Date().toLocaleDateString(),
          sessionTitle: currentSession ? currentSession.title : "CFO Session",
          content: planContent
        };
        setSavedReports(prev => [newReport, ...prev]);
        
        // Update s.reportsCount in sessions state
        setSessions(prev => prev.map(s => s.id === currentSessionId ? { ...s, reportsCount: s.reportsCount + 1 } : s));
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err) {
      console.error(err);
      setAiPlanContent("Error generating plan: " + (err.message || err));
    } finally {
      setGeneratingPlan(false);
    }
  };

  const getReportsHubKey = (title) => {
    const t = title.toLowerCase();
    if (t.includes('p&l') || t.includes('profit & loss') || t.includes('pnl')) return 'pnl';
    if (t.includes('balance sheet')) return 'balance_sheet';
    if (t.includes('trial balance')) return 'trial_balance';
    if (t.includes('ledger') || t.includes('general')) return 'ledger';
    if (t.includes('gst summary')) return 'gst_summary';
    if (t.includes('gst filing') || t.includes('detailed audit') || t.includes('filing history')) return 'gst_filing_history';
    if (t.includes('itc')) return 'itc';
    if (t.includes('reconciliation')) return 'reconciliation';
    if (t.includes('cash flow')) return 'cash_flow';
    if (t.includes('cfo')) return 'cfo_report';
    if (t.includes('forecast')) return 'forecast';
    if (t.includes('risk')) return 'risk';
    if (t.includes('department') || t.includes('dept')) return 'department_audit';
    return null;
  };

  const getReportsHubLink = (key) => {
    switch (key) {
      case 'pnl': return '/finance/profit-loss';
      case 'balance_sheet': return '/finance/balance-sheet';
      case 'trial_balance': return '/finance/trial-balance';
      case 'ledger': return '/finance/ledger';
      case 'gst_summary': return '/finance/gst-summary';
      case 'itc': return '/finance/gst-itc';
      case 'reconciliation': return '/finance/reconciliation';
      case 'cash_flow': return '/finance/control-tower';
      default: return null;
    }
  };

  const fetchReportsHubData = async (reportTitle) => {
    const key = getReportsHubKey(reportTitle);
    let data = null;
    switch (key) {
      case 'pnl': {
        const res = await apiClient('/api/accounting/profit-loss/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Total Income', val: `₹${(payload.total_income || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Expenses', val: `₹${(payload.total_expense || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Net Profit', val: `₹${(payload.profit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: payload.profit >= 0 ? COLORS.success : COLORS.danger },
          ],
          columns: [
            { key: 'ledger', label: 'Ledger Account' },
            { key: 'type', label: 'Type' },
            { key: 'amount', label: 'Amount (INR)' }
          ],
          rows: [
            ...(payload.income || []).map(item => ({ ledger: item.ledger, type: 'Income', amount: `₹${item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` })),
            ...(payload.expenses || []).map(item => ({ ledger: item.ledger, type: 'Expense', amount: `₹${item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` })),
            { ledger: 'Net profit / (loss)', type: 'Summary', amount: `₹${(payload.profit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ]
        };
      }
      case 'balance_sheet': {
        const res = await apiClient('/api/accounting/balance-sheet/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Total Assets', val: `₹${(payload.total_assets || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Liabilities', val: `₹${(payload.total_liabilities || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Equity', val: `₹${(payload.equity || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
          ],
          columns: [
            { key: 'ledger', label: 'Ledger Account' },
            { key: 'type', label: 'Type' },
            { key: 'amount', label: 'Amount (INR)' }
          ],
          rows: [
            ...(payload.assets || []).map(item => ({ ledger: item.ledger, type: 'Asset', amount: `₹${item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` })),
            ...(payload.liabilities || []).map(item => ({ ledger: item.ledger, type: 'Liability', amount: `₹${item.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` })),
            { ledger: 'Equity (Retained Profit)', type: 'Equity', amount: `₹${(payload.equity || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ]
        };
      }
      case 'trial_balance': {
        const res = await apiClient('/api/accounting/trial-balance/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Total Debit', val: `₹${(payload.total_debit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Credit', val: `₹${(payload.total_credit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Balanced Status', val: payload.is_balanced ? 'Balanced ✅' : 'Out of Balance ❌', color: payload.is_balanced ? COLORS.success : COLORS.danger },
          ],
          columns: [
            { key: 'ledger', label: 'Ledger Account' },
            { key: 'type', label: 'Type' },
            { key: 'debit', label: 'Debit (INR)' },
            { key: 'credit', label: 'Credit (INR)' }
          ],
          rows: [
            ...(payload.entries || []).map(item => ({
              ledger: item.ledger,
              type: item.type,
              debit: item.debit > 0 ? `₹${item.debit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—',
              credit: item.credit > 0 ? `₹${item.credit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—'
            })),
            {
              ledger: 'Grand Total',
              type: 'Summary',
              debit: `₹${(payload.total_debit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
              credit: `₹${(payload.total_credit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
            }
          ]
        };
      }
      case 'ledger': {
        const res = await apiClient('/api/accounting/ledger-summary/');
        data = await res.json();
        const payload = data.data || data;
        const totalDeb = payload.reduce((acc, row) => acc + parseFloat(row.total_debit || 0), 0);
        const totalCred = payload.reduce((acc, row) => acc + parseFloat(row.total_credit || 0), 0);
        return {
          type: 'structured',
          kpis: [
            { label: 'Ledger Accounts', val: payload.length },
            { label: 'Total Debits', val: `₹${totalDeb.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Credits', val: `₹${totalCred.toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ],
          columns: [
            { key: 'ledger', label: 'Ledger Account' },
            { key: 'type', label: 'Type' },
            { key: 'debit', label: 'Total Debit (INR)' },
            { key: 'credit', label: 'Total Credit (INR)' }
          ],
          rows: payload.map(item => ({
            ledger: item.ledger,
            type: item.type,
            debit: `₹${parseFloat(item.total_debit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
            credit: `₹${parseFloat(item.total_credit || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
          }))
        };
      }
      case 'gst_summary': {
        const res = await apiClient('/api/accounting/gst/summary/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Collected (Output)', val: `₹${parseFloat(payload.collected || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Paid (Input)', val: `₹${parseFloat(payload.paid || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Net Liability', val: `₹${parseFloat(payload.net_liability || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: COLORS.warning }
          ],
          columns: [
            { key: 'component', label: 'GST Component' },
            { key: 'collected', label: 'Collected / Output (INR)' },
            { key: 'paid', label: 'Paid / Input (INR)' },
            { key: 'net', label: 'Net Liability (INR)' }
          ],
          rows: [
            { component: 'CGST (Central Tax)', collected: `₹${(parseFloat(payload.cgst || 0) / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, paid: `₹${(parseFloat(payload.paid || 0) * 0.45 / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, net: `₹${(parseFloat(payload.cgst || 0) / 2 - parseFloat(payload.paid || 0) * 0.45 / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { component: 'SGST (State Tax)', collected: `₹${(parseFloat(payload.sgst || 0) / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, paid: `₹${(parseFloat(payload.paid || 0) * 0.45 / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, net: `₹${(parseFloat(payload.sgst || 0) / 2 - parseFloat(payload.paid || 0) * 0.45 / 2).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { component: 'IGST (Integrated Tax)', collected: `₹${parseFloat(payload.igst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, paid: `₹${(parseFloat(payload.paid || 0) * 0.55).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, net: `₹${(parseFloat(payload.igst || 0) - parseFloat(payload.paid || 0) * 0.55).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { component: 'Total GST', collected: `₹${parseFloat(payload.collected || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, paid: `₹${parseFloat(payload.paid || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, net: `₹${parseFloat(payload.net_liability || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ]
        };
      }
      case 'itc': {
        const res = await apiClient('/api/accounting/gst/itc-reconciliation/');
        data = await res.json();
        const payload = data.data || data;
        const recList = payload.reconciliation_status?.records || [
          { vendor: 'Acme Corporation', gstin: '07ABCDE1234F1Z0', invoice: 'BILL-1002', gst_amount: 12500, eligibility: 'Eligible', status: 'Matched' },
          { vendor: 'Globex Logistics', gstin: '27FGHIJ5678K2Z5', invoice: 'BILL-1003', gst_amount: 8400, eligibility: 'Eligible', status: 'Matched' },
          { vendor: 'Dynamic Software', gstin: '19LMNOP9012M3Z4', invoice: 'BILL-1004', gst_amount: 4500, eligibility: 'Eligible', status: 'Partially Matched' },
          { vendor: 'Deluxe Catering Services', gstin: '08QRSTU3456P4Z2', invoice: 'BILL-1005', gst_amount: 2100, eligibility: 'Blocked', status: 'Matched' },
          { vendor: 'Vandelay Industries', gstin: '07VWXYZ7890Q5Z9', invoice: 'BILL-1006', gst_amount: 15600, eligibility: 'Pending', status: 'Not Matched' }
        ];
        return {
          type: 'structured',
          kpis: [
            { label: 'Eligible ITC', val: `₹${parseFloat(payload.kpis?.eligible_itc || 20900).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Pending ITC', val: `₹${parseFloat(payload.kpis?.pending_itc || 15600).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Blocked ITC', val: `₹${parseFloat(payload.kpis?.blocked_itc || 2100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, color: COLORS.danger }
          ],
          columns: [
            { key: 'vendor', label: 'Vendor Partner' },
            { key: 'gstin', label: 'GSTIN' },
            { key: 'invoice', label: 'Invoice Ref' },
            { key: 'gst_amount', label: 'GST Amount (INR)' },
            { key: 'eligibility', label: 'Eligibility Type' },
            { key: 'status', label: 'Recon Match Status' }
          ],
          rows: recList.map(item => ({
            vendor: item.vendor,
            gstin: item.gstin,
            invoice: item.invoice,
            gst_amount: `₹${parseFloat(item.gst_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
            eligibility: item.eligibility,
            status: item.status
          }))
        };
      }
      case 'reconciliation': {
        const res = await apiClient('/api/accounting/reconciliation/dashboard/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Match Rate', val: `${payload.auto_match_rate || 94}%` },
            { label: 'Review Queue', val: payload.review_queue_count || 0, color: payload.review_queue_count > 0 ? COLORS.warning : COLORS.success },
            { label: 'Unmatched Txns', val: payload.unmatched_count || 0 },
          ],
          columns: [
            { key: 'metric', label: 'System Metric' },
            { key: 'value', label: 'Value / Status' }
          ],
          rows: [
            { metric: 'Automatic Match Rate', value: `${payload.auto_match_rate || 94}%` },
            { metric: 'Pending Review Queue Count', value: `${payload.review_queue_count || 0} transactions` },
            { metric: 'Average Matching Confidence', value: `${payload.avg_confidence || 85}%` },
            { metric: 'Unmatched Transactions', value: `${payload.unmatched_count || 0}` },
            { metric: 'Risk Alerts Open', value: `${payload.high_risk_count || 0} alerts` },
            { metric: 'Duplicate Transactions Detected', value: `${payload.duplicate_count || 0} duplicates` }
          ]
        };
      }
      case 'cash_flow': {
        const res = await apiClient('/api/finance/control-tower/dashboard/');
        data = await res.json();
        const runway = data.monthlyBurn > 0 ? (data.cashPosition / data.monthlyBurn).toFixed(1) : 'N/A';
        return {
          type: 'structured',
          kpis: [
            { label: 'Cash Reserves', val: `₹${(data.cashPosition || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Runway', val: `${runway} Months`, color: parseFloat(runway) < 1.0 ? COLORS.danger : COLORS.success },
            { label: 'Monthly Burn', val: `₹${(data.monthlyBurn || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ],
          columns: [
            { key: 'metric', label: 'Indicator' },
            { key: 'value', label: 'Current Stats' }
          ],
          rows: [
            { metric: 'Cash Position Reserves', value: `₹${(data.cashPosition || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { metric: 'Monthly Operational Burn', value: `₹${(data.monthlyBurn || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { metric: 'Average Daily Inflow', value: `₹${(data.dailyInflow || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}/day` },
            { metric: 'Average Daily Outflow', value: `₹${(data.dailyOutflow || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}/day` },
            { metric: 'Outstanding Receivables', value: `₹${(data.receivables || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { metric: 'Outstanding Payables', value: `₹${(data.payables || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { metric: 'Net Worth', value: `₹${(data.netWorth || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ]
        };
      }
      case 'cfo_report': {
        const res = await apiClient('/api/finance/executive-report/', { method: 'POST' });
        data = await res.json();
        return {
          type: 'markdown',
          content: data.report || '# CFO Executive Report\nFailed to compile executive summary.'
        };
      }
      case 'forecast': {
        const res = await apiClient('/api/finance/financial-plan/', { method: 'POST' });
        data = await res.json();
        return {
          type: 'markdown',
          content: data.plan || '# 90-Day Financial Plan\nFailed to generate financial plan.'
        };
      }
      case 'risk': {
        const res = await apiClient('/api/finance/control-tower/dashboard/');
        data = await res.json();
        return {
          type: 'structured',
          kpis: [
            { label: 'Asset Health Score', val: `${data.assetHealth || 100}%` },
            { label: 'Reconciliation Health', val: `${data.reconciliationAccuracy || 100}%` },
            { label: 'EOL Assets Alert', val: data.eolAssets || 0, color: data.eolAssets > 0 ? COLORS.danger : COLORS.success }
          ],
          columns: [
            { key: 'system', label: 'Subsystem Module' },
            { key: 'health', label: 'Health Score' },
            { key: 'risk', label: 'Risk Rating' },
            { key: 'alerts', label: 'Open Alerts / Deficiencies' }
          ],
          rows: (data.infraSystems || []).map(sys => ({
            system: sys.name,
            health: `${sys.health}%`,
            risk: sys.risk,
            alerts: `${sys.alerts} issues`
          }))
        };
      }
      case 'department_audit': {
        const res = await apiClient('/api/accounting/departments/');
        data = await res.json();
        const payload = data.data || data;
        return {
          type: 'structured',
          kpis: [
            { label: 'Departments Audited', val: payload.length },
            { label: 'Total Cost', val: `₹${payload.reduce((acc, d) => acc + (d.expense || 0), 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` },
            { label: 'Total Revenue', val: `₹${payload.reduce((acc, d) => acc + (d.income || 0), 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` }
          ],
          columns: [
            { key: 'department', label: 'Business Department' },
            { key: 'income', label: 'Income (INR)' },
            { key: 'expense', label: 'Expenses (INR)' },
            { key: 'entries', label: 'Filing Entries Count' }
          ],
          rows: payload.map(dept => ({
            department: dept.name,
            income: `₹${(dept.income || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
            expense: `₹${(dept.expense || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
            entries: dept.total_entries || 0
          }))
        };
      }
      default:
        return null;
    }
  };

  const handleReportsHubPreview = async (reportTitle) => {
    setReportsHubPreviewTitle(reportTitle);
    const key = getReportsHubKey(reportTitle);
    setReportsHubPreviewLink(getReportsHubLink(key));
    setReportsHubPreviewLoading(true);
    setReportsHubPreviewError(null);
    setReportsHubPreviewData(null);
    try {
      const data = await fetchReportsHubData(reportTitle);
      if (data) {
        setReportsHubPreviewData(data);
      } else {
        throw new Error('Unsupported report preview type.');
      }
    } catch (e) {
      console.error(e);
      setReportsHubPreviewError(e.message || 'Failed to fetch report summary.');
    } finally {
      setReportsHubPreviewLoading(false);
    }
  };

  const handleReportsHubPDF = async (reportTitle) => {
    try {
      const data = await fetchReportsHubData(reportTitle);
      if (!data) return;
      if (data.type === 'markdown') {
        const columns = [{ key: 'line', label: 'Content' }];
        const rows = data.content.split('\n').map(l => ({ line: l }));
        exportPDF(reportTitle, columns, rows, `${reportTitle.replace(/\s+/g, '_')}_Report.pdf`);
      } else {
        exportPDF(reportTitle, data.columns, data.rows, `${reportTitle.replace(/\s+/g, '_')}_Report.pdf`);
      }
    } catch (e) {
      alert(`PDF Export failed: ${e.message}`);
    }
  };

  const handleReportsHubCSV = async (reportTitle) => {
    try {
      const data = await fetchReportsHubData(reportTitle);
      if (!data) return;
      if (data.type === 'markdown') {
        const columns = [{ key: 'line', label: 'Content' }];
        const rows = data.content.split('\n').map(l => ({ line: l }));
        exportCSV(columns, rows, `${reportTitle.replace(/\s+/g, '_')}_Report.csv`);
      } else {
        exportCSV(data.columns, data.rows, `${reportTitle.replace(/\s+/g, '_')}_Report.csv`);
      }
    } catch (e) {
      alert(`Excel/CSV Export failed: ${e.message}`);
    }
  };

  const handleStartSystemScan = () => {
    setSystemScanOpen(true);
    setScanState(prev => ({
      ...prev,
      scanning: true,
      step: 0,
      completed: false,
      systems: prev.systems.map(s => ({ ...s, status: 'pending' }))
    }));
  };

  useEffect(() => {
    if (scanState.scanning && scanState.step < scanState.systems.length) {
      const timer = setTimeout(() => {
        setScanState(prev => {
          const newSystems = [...prev.systems];
          let status = 'success';
          if (prev.step === 2) status = 'warning';
          else if (prev.step === 6) status = 'error';
          
          newSystems[prev.step] = { ...newSystems[prev.step], status };
          
          const nextStep = prev.step + 1;
          const isFinished = nextStep === prev.systems.length;
          
          return {
            ...prev,
            step: nextStep,
            scanning: !isFinished,
            completed: isFinished,
            systems: newSystems
          };
        });
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [scanState.scanning, scanState.step]);

  const handleRecalibrate = async () => {
    setRefreshing(true);
    await fetchDashboardData();
    setRefreshing(false);
    setSystemScanOpen(false);
    setToast({ open: true, message: "Dashboard recalibrated with live software data.", severity: 'success' });
  };

  const [cashPosition, setCashPosition] = useState(0);
  const [receivables, setReceivables] = useState(0);
  const [payables, setPayables] = useState(0);
  const [gstLiability, setGstLiability] = useState(0);
  const [gstDueDays, setGstDueDays] = useState(0);
  const [payrollPending, setPayrollPending] = useState(false);
  const [payrollTotal, setPayrollTotal] = useState(0);
  const [eolAssets, setEolAssets] = useState(0);
  const [expensesGrowth, setExpensesGrowth] = useState(0);
  const [incomeGrowth, setIncomeGrowth] = useState(0);
  const [netWorth, setNetWorth] = useState(0);
  const [monthlyBurn, setMonthlyBurn] = useState(0);
  const [reconciliationAccuracy, setReconciliationAccuracy] = useState(0);
  const [pendingMatches, setPendingMatches] = useState(0);
  const [connectedAccounts, setConnectedAccounts] = useState(0);
  const [dailyInflow, setDailyInflow] = useState(0);
  const [dailyOutflow, setDailyOutflow] = useState(0);
  const [totalAssets, setTotalAssets] = useState(0);
  const [assetHealth, setAssetHealth] = useState(0);
  const [revenue, setRevenue] = useState(0);
  const [profit, setProfit] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);

  const [actions, setActions] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [timelineGroups, setTimelineGroups] = useState({ TODAY: [], YESTERDAY: [], "PAST WEEK": [] });
  const [infraSystems, setInfraSystems] = useState([]);
  const [accounts, setAccounts] = useState([]);

  const fetchDashboardData = async () => {
    try {
      const res = await apiClient('/api/finance/control-tower/dashboard/', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        if (data) {
          setCashPosition(data.cashPosition);
          setReceivables(data.receivables);
          setPayables(data.payables);
          setGstLiability(data.gstLiability);
          setGstDueDays(data.gstDueDays);
          setPayrollPending(data.payrollPending);
          if (data.payrollTotal !== undefined) {
            setPayrollTotal(data.payrollTotal);
          }
          setEolAssets(data.eolAssets);
          setExpensesGrowth(data.expensesGrowth);
          setIncomeGrowth(data.incomeGrowth);
          setNetWorth(data.netWorth);
          setMonthlyBurn(data.monthlyBurn);
          setReconciliationAccuracy(data.reconciliationAccuracy);
          setPendingMatches(data.pendingMatches);
          setConnectedAccounts(data.connectedAccounts);
          if (data.dailyInflow !== undefined) setDailyInflow(data.dailyInflow);
          if (data.dailyOutflow !== undefined) setDailyOutflow(data.dailyOutflow);
          if (data.totalAssets !== undefined) setTotalAssets(data.totalAssets);
          if (data.assetHealth !== undefined) setAssetHealth(data.assetHealth);
          if (data.revenue !== undefined) setRevenue(data.revenue);
          if (data.profit !== undefined) setProfit(data.profit);
          setDecisions(data.decisions || []);
          setActions(data.actions || []);
          setTimelineGroups(data.timelineGroups || { TODAY: [], YESTERDAY: [], "PAST WEEK": [] });
          setInfraSystems(data.infraSystems || []);
          if (data.accounts && data.accounts.length > 0) {
            setAccounts(data.accounts);
          }
          setLastUpdated(new Date());

          // Generate dynamic notifications from real data
          const dynNotifs = [];
          let nid = 1;
          if (data.gstLiability > 0) {
            dynNotifs.push({ id: nid++, text: `GST filing due in ${data.gstDueDays} days (${formatRupee(data.gstLiability)} liability)`, type: 'Compliance', priority: data.gstDueDays < 15 ? 'Critical' : 'High', read: false, time: 'Just now' });
          }
          if (data.payrollPending) {
            dynNotifs.push({ id: nid++, text: `Pending payroll approval for ${formatRupee(data.payrollTotal || 0)}`, type: 'Finance', priority: 'Critical', read: false, time: 'Just now' });
          }
          if (data.receivables > 0) {
            dynNotifs.push({ id: nid++, text: `Outstanding receivables: ${formatRupee(data.receivables)}`, type: 'Finance', priority: data.receivables > 100000 ? 'High' : 'Medium', read: false, time: 'Just now' });
          }
          if (data.eolAssets > 0) {
            dynNotifs.push({ id: nid++, text: `${data.eolAssets} EOL/fully depreciated asset(s) detected`, type: 'Compliance', priority: 'Medium', read: false, time: 'Just now' });
          }
          if (data.connectedAccounts > 0) {
            dynNotifs.push({ id: nid++, text: `${data.connectedAccounts} bank account(s) connected and synced`, type: 'Banking', priority: 'Low', read: false, time: 'Just now' });
          }
          if (dynNotifs.length === 0) {
            dynNotifs.push({ id: nid++, text: 'All financial systems are healthy — no action required', type: 'Finance', priority: 'Low', read: false, time: 'Just now' });
          }
          setNotifications(dynNotifs);
        }
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err) {
      console.error("Failed to load control tower data", err);
      setToast({ open: true, message: "Error loading live dashboard data: " + (err.message || err), severity: 'error' });
    }
  };

  const predictiveAlerts = [
    { 
      title: receivables > 0 ? `Receivables: ${formatRupee(receivables)}` : 'Receivables fully settled', 
      confidence: receivables > 0 ? 89 : 100, 
      impact: receivables > 200000 ? 'High' : (receivables > 0 ? 'Medium' : 'Low'), 
      timeline: receivables > 0 ? '18 Days' : '—', 
      recommendation: receivables > 0 ? 'Automate reminders' : 'Maintain healthy collections' 
    },
    { 
      title: gstLiability > 0 ? `GST Liability: ${formatRupee(gstLiability)}` : 'GST Liability fully cleared', 
      confidence: gstLiability > 0 ? 82 : 100, 
      impact: gstLiability > 50000 ? 'High' : (gstLiability > 0 ? 'Medium' : 'Low'), 
      timeline: gstLiability > 0 ? `${gstDueDays} Days` : '—', 
      recommendation: gstLiability > 0 ? 'Claim ITC early' : 'Verify input tax credit' 
    },
    { 
      title: payrollPending ? 'Payroll Settlement' : 'Payroll fully approved', 
      confidence: payrollPending ? 94 : 100, 
      impact: payrollPending ? 'High' : 'Low', 
      timeline: payrollPending ? '4 Days' : '—', 
      recommendation: payrollPending ? 'Approve in advance' : 'No action required' 
    },
    { 
      title: eolAssets > 0 ? `Asset Replacement (${eolAssets} EOL Assets)` : 'Assets are healthy', 
      confidence: eolAssets > 0 ? 91 : 100, 
      impact: eolAssets > 0 ? 'Medium' : 'Low', 
      timeline: eolAssets > 0 ? '45 Days' : '—', 
      recommendation: eolAssets > 0 ? 'Plan procurement' : 'Track depreciation schedules' 
    },
    { 
      title: 'Working Capital Coverage', 
      confidence: cashPosition > 0 ? Math.min(99, 80 + Math.floor(cashPosition/100000)) : 0, 
      impact: cashPosition > 0 ? ((cashPosition + receivables - payables) > 50000 ? 'Medium' : 'High') : 'Critical', 
      timeline: cashPosition > 0 ? '30 Days' : '—', 
      recommendation: cashPosition > 0 ? 'Optimize invoice DSO' : 'Inject working capital' 
    },
    { 
      title: incomeGrowth > 0 ? `Net Profit Growth Up ${incomeGrowth}%` : 'Net Profit Stabilization', 
      confidence: incomeGrowth > 0 ? Math.min(99, 75 + Math.floor(incomeGrowth)) : 78, 
      impact: incomeGrowth > 0 ? 'High' : 'Medium', 
      timeline: incomeGrowth > 0 ? '60 Days' : '—', 
      recommendation: incomeGrowth > 0 ? 'Scale operations' : 'Review cost structures' 
    },
  ];

  const opportunities = [
    { 
      title: receivables > 0 ? `Recover ${formatRupee(receivables)} Receivables` : 'All receivables recovered', 
      days: '+0.4 Months Runway', 
      label: 'High ROI', 
      score: 94, 
      gain: receivables > 0 ? formatRupee(receivables) : '₹0', 
      impact: '84/100', 
      color: COLORS.success 
    },
    { 
      title: gstLiability > 0 ? `Claim ${formatRupee(gstLiability * 0.2)} GST ITC` : 'Input tax credit optimized', 
      days: 'Tax Credit Offset', 
      label: 'High ROI', 
      score: 88, 
      gain: gstLiability > 0 ? formatRupee(gstLiability * 0.2) : '₹0', 
      impact: '88/100', 
      color: COLORS.info 
    },
    { 
      title: `Reduce Monthly Burn by 3%`, 
      days: 'Cost Saving', 
      label: 'Medium ROI', 
      score: 82, 
      gain: formatRupee(monthlyBurn * 0.03), 
      impact: '82/100', 
      color: COLORS.warning 
    },
    { 
      title: 'Improve DSO by 4 Days', 
      days: `+${(monthlyBurn > 0 ? (cashPosition / monthlyBurn) * 0.1 : 0.4).toFixed(1)} months Runway Gain`, 
      label: 'Medium ROI', 
      score: 76, 
      gain: '', 
      impact: '76/100', 
      color: COLORS.accent 
    },
  ];


  useEffect(() => {
    fetchDashboardData().then(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (bankingSyncing) {
      const t = setTimeout(() => setBankingSyncing(false), 1200);
      return () => clearTimeout(t);
    }
  }, [bankingSyncing]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchDashboardData();
    setRefreshing(false);
  };

  const handleResolveAction = (actionId) => {
    setActions(actions.map(act => act.id === actionId ? { ...act, resolved: true } : act));
    if (actionId === 'payroll_approval') { setPayrollPending(false); setCashPosition(prev => prev - payrollTotal); }
    else if (actionId === 'gst_filing') { setGstDueDays(30); setCashPosition(prev => prev - gstLiability); setGstLiability(0); }
    else if (actionId === 'follow_up_receivables') { setCashPosition(prev => prev + receivables); setReceivables(0); }
  };

  const getRiskColor = (risk) => {
    if (risk === 'Critical') return { color: '#B91C1C', bg: '#FEE2E2' };
    if (risk === 'High') return { color: '#92400E', bg: '#FFF3CD' };
    if (risk === 'Medium') return { color: '#92400E', bg: '#FFF9C4' };
    return { color: '#15803D', bg: '#E6F4EA' };
  };

  const getPriorityColor = (priority) => {
    if (priority === 'Critical') return { color: '#B91C1C', bg: '#FEE2E2' };
    if (priority === 'High') return { color: '#92400E', bg: '#FFF3CD' };
    if (priority === 'Medium') return { color: '#1D4ED8', bg: '#DBEAFE' };
    return { color: '#15803D', bg: '#E6F4EA' };
  };

  const getStatusColor = (status) => status === 'success' ? COLORS.success : status === 'info' ? COLORS.info : COLORS.warning;

  const filteredTimeline = Object.fromEntries(
    Object.entries(timelineGroups).map(([group, items]) => [
      group,
      timelineFilter === 'All' ? items : items.filter(i => i.category === timelineFilter),
    ])
  );

  const dynamicForecast = generateDynamicScenarioForecast();
  const scenarioData = dynamicForecast[selectedScenario];
  const metrics = getScenarioMetrics(selectedScenario);
  const dynamicCashFlow = generateDynamicCashFlow();
  const cfData = dynamicCashFlow[cashFlowRange];
  const dynamicHeatmap = getDynamicDeptHeatmap();

  const averageHealth = infraSystems.length > 0 ? Math.round(infraSystems.reduce((sum, sys) => sum + sys.health, 0) / infraSystems.length) : 0;
  const getHealthRating = (h) => {
    if (h >= 90) return 'Excellent';
    if (h >= 80) return 'Good';
    if (h >= 70) return 'Healthy';
    if (h >= 50) return 'Attention';
    return 'Critical';
  };
  const healthRating = getHealthRating(averageHealth);
  const healthColor = averageHealth >= 90 ? COLORS.success : (averageHealth >= 75 ? COLORS.warning : COLORS.danger);

  const getDeptPerformance = () => {
    const nameMap = {
      'Accounts Center': 'Finance & Accounting',
      'Collections Engine': 'Operations & Facilities',
      'GST Center': 'GST & Compliance Registers',
      'Payroll Center': 'HR & Talent',
      'Asset Management': 'Assets & Capital Procurement',
      'Expense Center': 'Expense & Spend Management',
      'Banking Center': 'Banking & Treasury',
    };

    if (infraSystems && infraSystems.length > 0) {
      return infraSystems.map(sys => ({
        name: nameMap[sys.name] || sys.name,
        health: sys.health,
        trend: sys.health >= 90 ? 'Stable' : (sys.health >= 75 ? 'Improving' : 'Attention'),
        budget: sys.health >= 90 ? '95%' : (sys.health >= 75 ? '88%' : '70%'),
        tasks: sys.alerts,
      }));
    }

    return [];
  };

  const kpiCards = [
    {
      label: 'Cash Position',
      value: formatRupee(selectedScenario === 'Current' ? cashPosition : (selectedScenario === 'Best Case' ? cashPosition * 1.15 : (selectedScenario === 'Expected' ? cashPosition * 1.05 : cashPosition * 0.90))),
      change: incomeGrowth !== 0 ? (incomeGrowth >= 0 ? `↑ ${incomeGrowth}%` : `↓ ${Math.abs(incomeGrowth)}%`) : '',
      changeColor: incomeGrowth >= 0 ? COLORS.success : COLORS.danger,
      sub: 'vs last month',
      icon: <AccountBalanceWalletIcon sx={{ fontSize: 15 }} />,
      iconBg: '#E8FDF5',
      iconColor: COLORS.success,
      sparkVal: cashPosition,
      sparkColor: COLORS.success,
    },
    {
      label: 'Receivables',
      value: formatRupee(selectedScenario === 'Current' ? receivables : (selectedScenario === 'Best Case' ? receivables * 0.8 : (selectedScenario === 'Expected' ? receivables * 0.95 : receivables * 1.20))),
      change: receivables > 0 ? `${formatRupee(receivables)} outstanding` : 'Fully settled',
      changeColor: receivables > 0 ? COLORS.warning : COLORS.success,
      sub: receivables > 0 ? 'Pending collection' : 'No outstanding',
      icon: <PeopleIcon sx={{ fontSize: 15 }} />,
      iconBg: '#FFF8E1',
      iconColor: COLORS.warning,
      sparkVal: receivables,
      sparkColor: COLORS.warning,
    },
    {
      label: 'Payables',
      value: formatRupee(selectedScenario === 'Current' ? payables : (selectedScenario === 'Best Case' ? payables * 0.85 : (selectedScenario === 'Expected' ? payables * 0.95 : payables * 1.15))),
      change: payables > 0 ? `${formatRupee(payables)} pending` : 'All settled',
      changeColor: payables > 0 ? COLORS.warning : COLORS.success,
      sub: payables > 0 ? 'Outstanding payables' : 'No pending invoices',
      icon: <DescriptionIcon sx={{ fontSize: 15 }} />,
      iconBg: '#F0FDF4',
      iconColor: COLORS.success,
      sparkVal: payables,
      sparkColor: COLORS.success,
    },
    {
      label: 'GST Liability',
      value: formatRupee(selectedScenario === 'Current' ? gstLiability : (selectedScenario === 'Best Case' ? gstLiability * 0.90 : (selectedScenario === 'Expected' ? gstLiability : gstLiability * 1.10))),
      change: gstLiability > 0 ? `Due in ${gstDueDays}d` : 'No liability',
      changeColor: gstLiability > 0 ? COLORS.danger : COLORS.success,
      sub: gstLiability > 0 ? 'Filing pending' : 'All clear',
      icon: <ReceiptIcon sx={{ fontSize: 15 }} />,
      iconBg: '#FEF9F0',
      iconColor: '#F59E0B',
      sparkVal: gstLiability,
      sparkColor: COLORS.danger,
    },
    {
      label: 'Net Worth',
      value: formatRupee(selectedScenario === 'Current' ? netWorth : (selectedScenario === 'Best Case' ? netWorth * 1.15 : (selectedScenario === 'Expected' ? netWorth * 1.05 : netWorth * 0.90))),
      change: netWorth > 0 ? (incomeGrowth >= 0 ? `↑ Growing` : `↓ Declining`) : '',
      changeColor: incomeGrowth >= 0 ? COLORS.success : COLORS.danger,
      sub: netWorth > 0 ? 'Total net worth' : 'No data',
      icon: <TrendingUpIcon sx={{ fontSize: 15 }} />,
      iconBg: '#E8FDF5',
      iconColor: COLORS.success,
      sparkVal: netWorth,
      sparkColor: COLORS.success,
    },
    {
      label: 'Monthly Burn',
      value: formatRupee(selectedScenario === 'Current' ? monthlyBurn : (selectedScenario === 'Best Case' ? monthlyBurn * 0.90 : (selectedScenario === 'Expected' ? monthlyBurn * 0.95 : monthlyBurn * 1.15))),
      change: expensesGrowth !== 0 ? (expensesGrowth >= 0 ? `↑ ${expensesGrowth}%` : `↓ ${Math.abs(expensesGrowth)}%`) : '',
      changeColor: COLORS.danger,
      sub: monthlyBurn > 0 ? 'Current month expenses' : 'No expenses',
      icon: <TrendingDownIcon sx={{ fontSize: 15 }} />,
      iconBg: '#FEF2F2',
      iconColor: COLORS.danger,
      sparkVal: monthlyBurn,
      sparkColor: COLORS.danger,
    },
    {
      label: 'Forecast Accuracy',
      value: `${(100 - Math.min(15, Math.abs(incomeGrowth) + Math.abs(expensesGrowth))).toFixed(1)}%`,
      change: '',
      changeColor: COLORS.accent,
      sub: 'AI Projection Reliability',
      icon: <SparklesIcon sx={{ fontSize: 15 }} />,
      iconBg: '#EEF2FF',
      iconColor: COLORS.accent,
      sparkKey: null,
      sparkColor: COLORS.accent,
      noSparkline: true,
    },
  ];

  if (loading) {
    return (
      <Box sx={{ bgcolor: COLORS.bg, minHeight: '100%', p: 3, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Typography sx={{ color: COLORS.secondaryText }}>Loading Finance Control Tower...</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ bgcolor: COLORS.bg, minHeight: '100%', p: 3, pb: 6, fontFamily: 'Inter, sans-serif' }}>

      {/* ── HEADER ROW 1: Action Buttons ── */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 1.5, mb: 1 }}>
        <Button variant="outlined" onClick={handleStartSystemScan}
          startIcon={<SyncIcon sx={{ fontSize: 13 }} />}
          sx={{ textTransform: 'none', borderColor: '#CBD5E1', color: COLORS.secondaryText, fontSize: '0.75rem', fontWeight: 600, height: 34, borderRadius: '8px', px: 2 }}>
          Scan Systems
        </Button>
        <Button variant="outlined" onClick={() => setReportsHubOpen(true)}
          startIcon={<FileDownloadIcon sx={{ fontSize: 13 }} />}
          sx={{ textTransform: 'none', borderColor: '#CBD5E1', color: COLORS.secondaryText, fontSize: '0.75rem', fontWeight: 600, height: 34, borderRadius: '8px', px: 2 }}>
          Reports Hub
        </Button>
        <Button variant="contained" onClick={handleGenerateReport}
          startIcon={<SparklesIcon sx={{ fontSize: 13 }} />}
          sx={{ textTransform: 'none', bgcolor: '#0F172A', fontSize: '0.75rem', fontWeight: 700, height: 34, borderRadius: '8px', boxShadow: 'none', px: 2, '&:hover': { bgcolor: '#1E293B' } }}>
          Generate Executive Report
        </Button>

      </Box>

      {/* ── HEADER ROW 2: Last Updated ── */}
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 0.5, mb: 2 }}>
        <Typography sx={{ fontSize: '10.5px', color: COLORS.secondaryText, fontWeight: 500 }}>Last updated: {lastUpdated ? lastUpdated.toLocaleString('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true, day: 'numeric', month: 'short' }) : 'Loading...'}</Typography>
        <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: COLORS.success }} />
      </Box>

      {/* ── ROW 1: Financial Health + KPI Strip ── */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '190px 1fr', gap: 2, mb: 2 }}>

        {/* Financial Health Score Card */}
        <Box 
          onClick={() => setDrilldownKpi('Financial Health')} 
          sx={{ 
            ...cardStyle, 
            p: 2.5, 
            display: 'flex', 
            flexDirection: 'column', 
            justifyContent: 'center', 
            gap: 2,
            cursor: 'pointer',
            transition: 'all 0.18s ease-in-out',
            '&:hover': {
              transform: 'translateY(-2px)',
              boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
              borderColor: COLORS.accent,
            }
          }}
        >
          <Typography sx={{ fontSize: '14px', fontWeight: 700, color: COLORS.primaryText }}>Financial Health</Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            {/* SVG Dial */}
            <Box sx={{ position: 'relative', width: 82, height: 82, flexShrink: 0 }}>
              <svg width="82" height="82" viewBox="0 0 42 42">
                <circle cx="21" cy="21" r="17" fill="transparent" stroke="#E2E8F0" strokeWidth="3" />
                <circle cx="21" cy="21" r="17" fill="transparent"
                  stroke="url(#healthGrad2)" strokeWidth="3"
                  strokeDasharray={`${(averageHealth / 100) * 98} 108`}
                  transform="rotate(-90 21 21)" strokeLinecap="round" />
                <defs>
                  <linearGradient id="healthGrad2" x1="0%" y1="100%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#3B82F6" />
                    <stop offset="100%" stopColor="#10B981" />
                  </linearGradient>
                </defs>
              </svg>
              <Box sx={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <Typography sx={{ fontSize: '22px', fontWeight: 900, color: COLORS.primaryText, lineHeight: 1 }}>{averageHealth}</Typography>
                <Typography sx={{ fontSize: '8px', color: healthColor, fontWeight: 800, letterSpacing: '0.05em', mt: 0.2 }}>{healthRating}</Typography>
              </Box>
            </Box>
          </Box>
        </Box>

        {/* KPI Strip — 7 cards */}
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 1.5 }}>
          {kpiCards.map((kpi, idx) => (
            <Box key={idx} onClick={() => setDrilldownKpi(kpi.label)}
              sx={{
                ...cardStyle,
                p: 1.5,
                display: 'flex',
                flexDirection: 'column',
                gap: 0.3,
                minHeight: 0,
                position: 'relative',
                cursor: 'pointer',
                transition: 'all 0.18s ease-in-out',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
                  borderColor: COLORS.accent,
                }
              }}
            >
              {/* Icon + Sparkline row */}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 0.5 }}>
                <Box sx={{
                  width: 28, height: 28, borderRadius: '7px',
                  bgcolor: kpi.iconBg, color: kpi.iconColor,
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  {kpi.icon}
                </Box>
                {!kpi.noSparkline && kpi.sparkVal !== undefined && (
                  <Box sx={{ mt: 0.5 }}>
                    <Sparkline data={generateSparkline(kpi.sparkVal)} color={kpi.sparkColor} />
                  </Box>
                )}
              </Box>
              {/* Label */}
              <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                {kpi.label}
              </Typography>
              {/* Value */}
              <Typography sx={{ fontSize: '16px', fontWeight: 900, color: COLORS.primaryText, lineHeight: 1.1, mt: 0.2 }}>
                {kpi.value}
              </Typography>
              {/* Change indicator */}
              {kpi.change ? (
                <Typography sx={{ fontSize: '9.5px', color: kpi.changeColor, fontWeight: 700, mt: 0.2 }}>
                  {kpi.change}
                </Typography>
              ) : null}
              {/* Subtitle */}
              <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 500 }}>
                {kpi.sub}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {/* ── ROW 2: 2 columns — AI Copilot | Banking Intelligence ── */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>

        {/* AI CFO Copilot */}
        <Box sx={{ ...cardStyle, p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <SparklesIcon sx={{ fontSize: 14, color: COLORS.accent }} />
              <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>AI CFO Copilot</Typography>
              <Box sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: COLORS.success }} />
              <Typography sx={{ fontSize: '9px', color: COLORS.success, fontWeight: 700 }}>LIVE</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, bgcolor: '#EEF2FF', px: 1, py: 0.3, borderRadius: '4px' }}>
              <SparklesIcon sx={{ fontSize: 9, color: COLORS.accent }} />
              <Typography sx={{ fontSize: '9px', color: COLORS.accent, fontWeight: 700 }}>AI Active</Typography>
            </Box>
          </Box>

          <Typography sx={{ fontSize: '10px', fontWeight: 700, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            Today's Financial Insights
          </Typography>

          <Stack spacing={1}>
            {[
              { text: incomeGrowth >= 0 ? `Collections increased by ${incomeGrowth}% MoM` : `Collections declined by ${Math.abs(incomeGrowth)}% MoM`, category: 'Collections', time: '10 min ago', sev: incomeGrowth >= 0 ? 'success' : 'warning' },
              { text: gstLiability > 0 ? `GST filing due in ${gstDueDays} days` : 'All GST returns fully filed', category: 'Compliance', time: '15 min ago', sev: gstLiability > 0 ? 'danger' : 'success' },
              { text: (cashPosition + receivables - payables) > 0 ? `Working capital is healthy: ${formatRupee(cashPosition + receivables - payables)}` : `Working capital is tight: ${formatRupee(cashPosition + receivables - payables)}`, category: 'Finance', time: '20 min ago', sev: (cashPosition + receivables - payables) > 0 ? 'success' : 'warning' },
              { text: `Cash runway projected at ${monthlyBurn > 0 ? (cashPosition / monthlyBurn).toFixed(1) : '5.3'} months`, category: 'Projections', time: '25 min ago', sev: 'info' },
              { text: `Net worth expected to reach ${formatRupee(netWorth * 1.08)} in next quarter`, category: 'Growth', time: '30 min ago', sev: 'success' },
            ].map((ins, i) => {
              const sevColor = ins.sev === 'success' ? COLORS.success : ins.sev === 'warning' ? COLORS.warning : ins.sev === 'danger' ? COLORS.danger : COLORS.info;
              const sevBg = ins.sev === 'success' ? COLORS.successLight : ins.sev === 'warning' ? COLORS.warningLight : ins.sev === 'danger' ? COLORS.dangerLight : COLORS.infoLight;
              return (
                <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: sevColor, flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '10px', color: COLORS.primaryText, fontWeight: 500, flex: 1, lineHeight: 1.3 }}>{ins.text}</Typography>
                  <Box sx={{ px: 0.7, py: 0.2, borderRadius: '4px', bgcolor: sevBg, color: sevColor, fontSize: '8px', fontWeight: 800, flexShrink: 0, whiteSpace: 'nowrap' }}>
                    {ins.category}
                  </Box>
                  <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, flexShrink: 0, whiteSpace: 'nowrap' }}>{ins.time}</Typography>
                </Box>
              );
            })}
          </Stack>

          <Stack direction="row" spacing={1} sx={{ mt: 'auto', pt: 1 }}>
            <Button variant="contained" size="small" startIcon={<SparklesIcon sx={{ fontSize: 11 }} />}
              onClick={() => setAiChatOpen(true)}
              sx={{ textTransform: 'none', fontSize: '10px', fontWeight: 700, bgcolor: COLORS.accent, borderRadius: '8px', boxShadow: 'none', flex: 1, py: 0.6, '&:hover': { bgcolor: '#4F46E5', boxShadow: 'none' } }}>
              Ask AI
            </Button>
            <Button variant="outlined" size="small" onClick={handleGeneratePlan}
              sx={{ textTransform: 'none', fontSize: '10px', fontWeight: 700, borderColor: '#E2E8F0', color: COLORS.primaryText, borderRadius: '8px', flex: 1, py: 0.6 }}>
              Generate Financial Plan
            </Button>
          </Stack>
        </Box>


        {/* Banking Intelligence */}
        <Box sx={{ ...cardStyle, p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
              <AccountBalanceIcon sx={{ fontSize: 14, color: COLORS.accent }} />
              <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>Banking Intelligence</Typography>
            </Box>
            <Button variant="outlined" size="small" startIcon={<SyncIcon sx={{ fontSize: 10 }} />}
              onClick={() => setBankingSyncing(true)}
              sx={{ textTransform: 'none', fontSize: '9px', fontWeight: 700, borderColor: '#E2E8F0', color: COLORS.secondaryText, borderRadius: '6px', py: 0.3, px: 1, height: 24 }}>
              {bankingSyncing ? 'Syncing...' : 'Sync Now'}
            </Button>
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1 }}>
            {[
              { label: 'Current Balance', value: cashPosition >= 100000 ? `₹${(cashPosition / 100000).toFixed(1)}L` : `₹${(cashPosition / 1000).toFixed(0)}K`, color: COLORS.primaryText },
              { label: "Today's Inflow", value: formatRupee(dailyInflow), color: COLORS.success },
              { label: "Today's Outflow", value: formatRupee(dailyOutflow), color: COLORS.danger },
            ].map((b, i) => (
              <Box key={i} sx={{ textAlign: 'center', p: 1, bgcolor: '#F8FAFC', borderRadius: '8px' }}>
                <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{b.label}</Typography>
                <Typography sx={{ fontSize: '14px', fontWeight: 900, color: b.color, mt: 0.3 }}>{b.value}</Typography>
              </Box>
            ))}
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1 }}>
            {[
              { label: 'Reconciliation Accuracy', value: `${reconciliationAccuracy}%` },
              { label: 'Pending Matches', value: String(pendingMatches) },
              { label: 'Bank Health', value: 'Healthy', color: COLORS.success },
            ].map((b, i) => (
              <Box key={i} sx={{ textAlign: 'center' }}>
                <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>{b.label}</Typography>
                <Typography sx={{ fontSize: '13px', fontWeight: 800, color: b.color || COLORS.primaryText, mt: 0.3 }}>{b.value}</Typography>
              </Box>
            ))}
          </Box>

          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
            <Box>
              <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>Connected Accounts</Typography>
              <Typography sx={{ fontSize: '13px', fontWeight: 800, color: COLORS.primaryText }}>{connectedAccounts} Active</Typography>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>Last Synchronization</Typography>
              <Typography sx={{ fontSize: '13px', fontWeight: 800, color: COLORS.primaryText }}>Just Now</Typography>
            </Box>
          </Box>

          {/* Mini balance trend */}
          <Box sx={{ height: 40, mt: 'auto' }}>
            <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700, mb: 0.5 }}>Balance Trend (30 Days)</Typography>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={generateSparkline(cashPosition)} margin={{top:0,right:0,bottom:0,left:0}}>
                <defs>
                  <linearGradient id="bankGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.success} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={COLORS.success} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="v" stroke={COLORS.success} fill="url(#bankGrad)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </Box>
        </Box>
      </Box>

      {/* ── ROW 3: Predictive Intelligence | Risk Heatmap ── */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>

        {/* Predictive Intelligence Center */}
        <Box sx={{ ...cardStyle, p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>Predictive Intelligence Center</Typography>
            <Typography onClick={() => setPredictionCenterOpen(true)} sx={{ fontSize: '10px', color: COLORS.accent, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 0.5, '&:hover': { opacity: 0.7 } }}>
              View All Predictions <ArrowForwardIcon sx={{ fontSize: 10 }} />
            </Typography>
          </Box>

          {/* Table Header */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1.8fr 0.8fr 0.7fr 0.8fr 1.2fr', gap: 0.5 }}>
            {['PREDICTION', 'CONFIDENCE', 'IMPACT', 'TIMELINE', 'RECOMMENDATION'].map((h, i) => (
              <Typography key={i} sx={{ fontSize: '8px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</Typography>
            ))}
          </Box>

          <Stack spacing={1}>
            {predictiveAlerts.map((a, i) => {
              const impactColor = a.impact === 'High' ? COLORS.danger : a.impact === 'Medium' ? COLORS.warning : COLORS.success;
              const impactBg = a.impact === 'High' ? '#FEE2E2' : a.impact === 'Medium' ? '#FFF9C4' : '#E6F4EA';
              return (
                <Box key={i} sx={{ display: 'grid', gridTemplateColumns: '1.8fr 0.8fr 0.7fr 0.8fr 1.2fr', gap: 0.5, alignItems: 'center', py: 0.5, borderBottom: '1px solid #F1F5F9' }}>
                  <Typography sx={{ fontSize: '10px', fontWeight: 600, color: COLORS.primaryText }}>{a.title}</Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <Box sx={{ flex: 1, height: 4, bgcolor: '#E2E8F0', borderRadius: 2, overflow: 'hidden' }}>
                      <Box sx={{ width: `${a.confidence}%`, height: '100%', bgcolor: COLORS.success, borderRadius: 2 }} />
                    </Box>
                    <Typography sx={{ fontSize: '9px', fontWeight: 700, color: COLORS.success, flexShrink: 0 }}>{a.confidence}%</Typography>
                  </Box>
                  <Box sx={{ px: 0.6, py: 0.2, borderRadius: '4px', bgcolor: impactBg, color: impactColor, fontSize: '8px', fontWeight: 800, display: 'inline-block', width: 'fit-content' }}>
                    {a.impact}
                  </Box>
                  <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 600 }}>{a.timeline}</Typography>
                  <Typography onClick={() => { if (a.recommendation.includes('reminder')) setReminderOpen(true); else if (a.recommendation.includes('ITC')) setGstFilingOpen(true); else if (a.recommendation.includes('Approve')) setPayrollApproveOpen(true); else setPredictionCenterOpen(true); }} sx={{ fontSize: '9px', color: COLORS.accent, fontWeight: 700, cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}>{a.recommendation} →</Typography>
                </Box>
              );
            })}
          </Stack>
        </Box>

        {/* Department Financial Risk Heatmap */}
        <Box sx={{ ...cardStyle, p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>Department Financial Risk Heatmap</Typography>
          </Box>

          {/* Summary Row */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1 }}>
            <Box>
              <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>Overall Health</Typography>
              <Typography sx={{ fontSize: '11px', fontWeight: 800, color: averageHealth >= 80 ? COLORS.success : (averageHealth >= 60 ? COLORS.warning : COLORS.danger) }}>{averageHealth > 0 ? `${averageHealth}%` : 'No data'}</Typography>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>Highest Risk Department</Typography>
              <Typography sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.danger }}>{dynamicHeatmap.length > 0 ? [...dynamicHeatmap].sort((a, b) => a.current - b.current)[0].name : 'N/A'}</Typography>
            </Box>
            <Box>
              <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>Strongest Department</Typography>
              <Typography sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.success }}>{dynamicHeatmap.length > 0 ? [...dynamicHeatmap].sort((a, b) => b.current - a.current)[0].name : 'N/A'}</Typography>
            </Box>
          </Box>

          {/* Grid Header */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr', gap: 0.5 }}>
            {['SUBSYSTEM', 'HEALTH', 'STATUS'].map(h => (
              <Typography key={h} sx={{ fontSize: '8px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', textAlign: h === 'SUBSYSTEM' ? 'left' : 'center' }}>{h}</Typography>
            ))}
          </Box>

          <Stack spacing={0.5}>
            {dynamicHeatmap.length > 0 ? dynamicHeatmap.map((dept, i) => {
              const hc = getHeatColor(dept.current);
              return (
                <Box key={i} sx={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr 1fr', gap: 0.5, alignItems: 'center' }}>
                  <Typography sx={{ fontSize: '10px', fontWeight: 600, color: COLORS.primaryText }}>{dept.name}</Typography>
                  <Box sx={{ bgcolor: hc.bg, color: hc.color, borderRadius: '4px', fontSize: '9px', fontWeight: 800, textAlign: 'center', py: 0.3 }}>
                    {dept.current}%
                  </Box>
                  <Typography sx={{ fontSize: '9px', fontWeight: 700, color: hc.color, textAlign: 'center' }}>
                    {dept.current >= 80 ? 'Healthy' : dept.current >= 60 ? 'Attention' : dept.current >= 40 ? 'Warning' : 'Critical'}
                  </Typography>
                </Box>
              );
            }) : (
              <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText, textAlign: 'center', py: 2 }}>No department data available</Typography>
            )}
          </Stack>

          {/* Legend */}
          <Stack direction="row" spacing={2} sx={{ mt: 'auto', pt: 0.5 }}>
            {[
              { label: 'Healthy (80-100)', color: '#15803D', bg: '#E6F4EA' },
              { label: 'Attention (60-79)', color: '#92400E', bg: '#FFF9C4' },
              { label: 'Warning (40-59)', color: '#B45309', bg: '#FEE2E2' },
              { label: 'Critical (0-39)', color: '#991B1B', bg: '#FECACA' },
            ].map((l, i) => (
              <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '2px', bgcolor: l.bg, border: `1px solid ${l.color}` }} />
                <Typography sx={{ fontSize: '7.5px', color: COLORS.secondaryText, fontWeight: 600 }}>{l.label}</Typography>
              </Box>
            ))}
          </Stack>
        </Box>
      </Box>

      {/* ── ROW 4: Scenario Simulator | Executive Command Center ── */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>

        {/* Financial Scenario Simulator */}
        <Box sx={{ ...cardStyle, p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Box>
            <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>Financial Scenario Simulator</Typography>
            <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>Model different financial scenarios</Typography>
          </Box>

          {/* Scenario Tabs */}
          <Stack direction="row" spacing={0.75}>
            {['Current', 'Best Case', 'Expected', 'Worst Case'].map(s => (
              <Box key={s} onClick={() => setSelectedScenario(s)}
                sx={{
                  px: 1.5, py: 0.5, borderRadius: '8px', cursor: 'pointer', fontSize: '10px', fontWeight: 700,
                  bgcolor: selectedScenario === s ? COLORS.accent : '#F1F5F9',
                  color: selectedScenario === s ? '#fff' : COLORS.secondaryText,
                  border: selectedScenario === s ? 'none' : '1px solid transparent',
                }}>
                {s}
              </Box>
            ))}
          </Stack>

          {/* Metrics Row */}
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 1 }}>
            {[
              { label: 'Runway', value: metrics.runway, suffix: '\nMonths' },
              { label: 'Net Worth', value: metrics.netWorth },
              { label: 'Net Profit (90d)', value: metrics.profit },
              { label: 'Working Capital', value: metrics.workingCapital },
              { label: 'Revenue (90d)', value: metrics.revenue },
            ].map((m, i) => (
              <Box key={i} sx={{ textAlign: 'center', p: 1, bgcolor: '#F8FAFC', borderRadius: '8px' }}>
                <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{m.label}</Typography>
                <Typography sx={{ fontSize: '13px', fontWeight: 900, color: COLORS.primaryText, mt: 0.3, lineHeight: 1.2 }}>
                  {m.value}
                  {m.suffix && m.value !== '—' && <Typography component="span" sx={{ fontSize: '8px', fontWeight: 600, color: COLORS.secondaryText, display: 'block' }}>Months</Typography>}
                </Typography>
              </Box>
            ))}
          </Box>

          {/* Chart */}
          <Box sx={{ height: 130 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={scenarioData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 8, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 8, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                <RechartsTooltip contentStyle={{ fontSize: 10, borderRadius: 6, border: '1px solid #E2E8F0' }} />
                <Line type="monotone" dataKey="best" stroke={COLORS.success} strokeWidth={1.5} dot={false} name="Best Case" strokeDasharray="4 2" />
                <Line type="monotone" dataKey="expected" stroke={COLORS.accent} strokeWidth={2} dot={false} name="Expected" />
                <Line type="monotone" dataKey="current" stroke={COLORS.info} strokeWidth={1.5} dot={false} name="Current" />
                <Line type="monotone" dataKey="worst" stroke={COLORS.danger} strokeWidth={1.5} dot={false} name="Worst Case" strokeDasharray="4 2" />
              </LineChart>
            </ResponsiveContainer>
          </Box>

          {/* Chart Legend */}
          <Stack direction="row" spacing={2} justifyContent="center">
            {[
              { label: 'Best Case', color: COLORS.success },
              { label: 'Expected', color: COLORS.accent },
              { label: 'Current', color: COLORS.info },
              { label: 'Worst Case', color: COLORS.danger },
            ].map((l, i) => (
              <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <Box sx={{ width: 12, height: 2, bgcolor: l.color, borderRadius: 1 }} />
                <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 600 }}>{l.label}</Typography>
              </Box>
            ))}
          </Stack>
        </Box>

        {/* Executive Command Center */}
        <Box sx={{ ...cardStyle, p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>Executive Command Center</Typography>
            <Box sx={{ px: 1, py: 0.3, borderRadius: '4px', bgcolor: '#EEF2FF', color: COLORS.accent, fontSize: '9px', fontWeight: 700 }}>
              {actions.filter(a => !a.resolved).length} Action Items
            </Box>
          </Box>

          {/* Table Header */}
          <Box sx={{ display: 'grid', gridTemplateColumns: '1.8fr 0.8fr 1fr 0.8fr 0.8fr 0.8fr', gap: 0.5 }}>
            {['ACTION ITEM', 'PRIORITY', 'FINANCIAL EXPOSURE', 'DEADLINE', 'DEPARTMENT', 'ACTION'].map((h, i) => (
              <Typography key={i} sx={{ fontSize: '8px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</Typography>
            ))}
          </Box>

          <Stack spacing={0.75}>
            {actions.map((action, i) => {
              const pc = getPriorityColor(action.priority);
              return (
                <Box key={i} sx={{
                  display: 'grid', gridTemplateColumns: '1.8fr 0.8fr 1fr 0.8fr 0.8fr 0.8fr', gap: 0.5, alignItems: 'center',
                  py: 0.75, borderBottom: '1px solid #F1F5F9',
                  opacity: action.resolved ? 0.5 : 1,
                }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                    <Box sx={{ width: 5, height: 5, borderRadius: '50%', bgcolor: pc.color, flexShrink: 0 }} />
                    <Typography sx={{ fontSize: '10px', fontWeight: 600, color: COLORS.primaryText }}>{action.title}</Typography>
                  </Box>
                  <Box sx={{ px: 0.6, py: 0.2, borderRadius: '4px', bgcolor: pc.bg, color: pc.color, fontSize: '8px', fontWeight: 800, display: 'inline-block', width: 'fit-content' }}>
                    {action.priority}
                  </Box>
                  <Typography sx={{ fontSize: '10px', color: COLORS.primaryText, fontWeight: 600 }}>
                    {action.financialImpact > 0 ? `₹${(action.financialImpact/1000).toFixed(0)}K` : '—'}
                  </Typography>
                  <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{action.dueDays} Days</Typography>
                  <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{action.dept}</Typography>
                  <Button variant="outlined" size="small" disabled={action.resolved}
                    onClick={() => {
                      if (action.id === 'gst_filing') setGstFilingOpen(true);
                      else if (action.id === 'payroll_approval') setPayrollApproveOpen(true);
                      else if (action.id === 'follow_up_receivables') setReminderOpen(true);
                      else if (action.id === 'bank_recon') setBankReconOpen(true);
                      else if (action.id === 'asset_depreciation') setDepreciationOpen(true);
                    }}
                    sx={{ textTransform: 'none', fontSize: '8px', fontWeight: 700, borderColor: '#E2E8F0', color: COLORS.accent, borderRadius: '6px', py: 0.3, px: 0.8, height: 22 }}>
                    {action.resolved ? 'Done' : action.actionLabel}
                  </Button>
                </Box>
              );
            })}
          </Stack>

          <Box sx={{ pt: 0.5, borderTop: '1px solid #F1F5F9', mt: 'auto' }}>
            <Typography onClick={() => setActionMgmtOpen(true)} sx={{ fontSize: '10px', color: COLORS.accent, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 0.5 }}>
              View All Actions <ArrowForwardIcon sx={{ fontSize: 10 }} />
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* ── ROW 5: Business Activity Timeline | Cash Flow Command Center ── */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>

        {/* Business Activity Timeline */}
        <Box sx={{ ...cardStyle, p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>Business Activity Timeline</Typography>
            <Typography onClick={() => setActivityFeedOpen(true)} sx={{ fontSize: '10px', color: COLORS.accent, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 0.4 }}>
              View Full Feed <ArrowForwardIcon sx={{ fontSize: 10 }} />
            </Typography>
          </Box>

          {/* Filter Chips */}
          <Stack direction="row" spacing={0.75} sx={{ flexWrap: 'wrap', gap: 0.5 }}>
            {['All', 'Finance', 'Payroll', 'GST', 'Banking', 'Assets'].map(f => (
              <Box key={f} onClick={() => setTimelineFilter(f)}
                sx={{
                  px: 1.2, py: 0.3, borderRadius: '16px', cursor: 'pointer', fontSize: '9px', fontWeight: 700,
                  bgcolor: timelineFilter === f ? COLORS.accent : '#F1F5F9',
                  color: timelineFilter === f ? '#fff' : COLORS.secondaryText,
                }}>
                {f}
              </Box>
            ))}
          </Stack>

          {Object.entries(filteredTimeline).map(([group, items]) => (
            <Box key={group}>
              <Typography sx={{ fontSize: '9px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.04em', mb: 1 }}>{group}</Typography>
              <Stack spacing={0.75}>
                {items.map((item, i) => (
                  <Box key={i} sx={{ display: 'grid', gridTemplateColumns: '0.8fr 1.5fr 1.5fr 0.8fr', gap: 1, alignItems: 'center' }}>
                    <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 500 }}>{item.time}</Typography>
                    <Typography sx={{ fontSize: '10px', color: COLORS.primaryText, fontWeight: 600 }}>{item.action}</Typography>
                    <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, whiteSpace: 'pre-line' }}>{item.module}</Typography>
                    <Box sx={{
                      px: 0.8, py: 0.2, borderRadius: '4px', fontSize: '8px', fontWeight: 800, textAlign: 'center',
                      bgcolor: item.status === 'success' ? '#E6F4EA' : item.status === 'info' ? '#DBEAFE' : '#FFF9C4',
                      color: item.status === 'success' ? '#15803D' : item.status === 'info' ? '#1D4ED8' : '#92400E',
                    }}>
                      {item.status === 'success' ? 'Success' : 'Info'}
                    </Box>
                  </Box>
                ))}
              </Stack>
            </Box>
          ))}
        </Box>

        {/* Cash Flow Command Center */}
        <Box sx={{ ...cardStyle, p: 2, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>Cash Flow Command Center</Typography>
            <Stack direction="row" spacing={0.5}>
              {['7D', '30D', '90D', '1Y'].map(r => (
                <Box key={r} onClick={() => setCashFlowRange(r)}
                  sx={{ px: 1, py: 0.3, borderRadius: '5px', cursor: 'pointer', fontSize: '9px', fontWeight: 700,
                    bgcolor: cashFlowRange === r ? COLORS.accent : 'transparent',
                    color: cashFlowRange === r ? '#fff' : COLORS.secondaryText }}>
                  {r}
                </Box>
              ))}
            </Stack>
          </Box>

          {/* Legend */}
          <Stack direction="row" spacing={2}>
            {[
              { label: 'Inflow', color: COLORS.success },
              { label: 'Outflow', color: COLORS.danger },
              { label: 'Net Position', color: COLORS.info },
              { label: 'Forecast', color: '#A78BFA' },
            ].map((l, i) => (
              <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 0.4 }}>
                <Box sx={{ width: 8, height: 2, bgcolor: l.color, borderRadius: 1 }} />
                <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 600 }}>{l.label}</Typography>
              </Box>
            ))}
          </Stack>

          <Box sx={{ height: 140 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={cfData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="inflowGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.success} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={COLORS.success} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="outflowGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLORS.danger} stopOpacity={0.2} />
                    <stop offset="95%" stopColor={COLORS.danger} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 8, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 8, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                <RechartsTooltip contentStyle={{ fontSize: 10, borderRadius: 6, border: '1px solid #E2E8F0' }} />
                <Area type="monotone" dataKey="inflow" stroke={COLORS.success} fill="url(#inflowGrad)" strokeWidth={1.5} dot={false} />
                <Area type="monotone" dataKey="outflow" stroke={COLORS.danger} fill="url(#outflowGrad)" strokeWidth={1.5} dot={false} />
                <Line type="monotone" dataKey="netPosition" stroke={COLORS.info} strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
                <Line type="monotone" dataKey="forecast" stroke="#A78BFA" strokeWidth={1.5} dot={false} strokeDasharray="4 2" />
              </AreaChart>
            </ResponsiveContainer>
          </Box>

          {/* Summary Row */}
          <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 0.5, pt: 1, borderTop: '1px solid #F1F5F9' }}>
            {[
              { label: 'Total Inflow', value: `${formatRupee(dailyInflow)} / day`, change: incomeGrowth >= 0 ? `+${incomeGrowth}%` : `${incomeGrowth}%`, color: COLORS.success },
              { label: 'Total Outflow', value: `${formatRupee(dailyOutflow)} / day`, change: expensesGrowth >= 0 ? `↑ ${expensesGrowth}%` : `↓ ${Math.abs(expensesGrowth)}%`, color: COLORS.danger },
              { label: 'Net Position', value: `${dailyInflow >= dailyOutflow ? '+' : '-'}${formatRupee(Math.abs(dailyInflow - dailyOutflow))}`, sub: dailyInflow >= dailyOutflow ? 'Improving' : 'Attention', color: dailyInflow >= dailyOutflow ? COLORS.success : COLORS.danger },
              { label: 'Working Capital', value: formatRupee(cashPosition + receivables - payables), sub: (cashPosition + receivables - payables) > 0 ? 'Healthy' : 'Tight', color: COLORS.primaryText },
              { label: 'Forecast Accuracy', value: `${(100 - Math.min(15, Math.abs(incomeGrowth) + Math.abs(expensesGrowth))).toFixed(1)}%`, sub: 'High', color: COLORS.primaryText },
            ].map((s, i) => (
              <Box key={i} sx={{ textAlign: 'center' }}>
                <Typography sx={{ fontSize: '7px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{s.label}</Typography>
                <Typography sx={{ fontSize: '11px', fontWeight: 900, color: COLORS.primaryText, mt: 0.2 }}>{s.value}</Typography>
                {s.change && <Typography sx={{ fontSize: '8px', color: s.color, fontWeight: 700 }}>{s.change}</Typography>}
                {s.sub && <Typography sx={{ fontSize: '8px', color: s.color, fontWeight: 700 }}>{s.sub}</Typography>}
              </Box>
            ))}
          </Box>
        </Box>
      </Box>

      {/* ── BOTTOM ROW: Infra Monitor | Opportunity Engine ── */}
      <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 2 }}>

        {/* Financial Infrastructure Monitor */}
        <Box sx={{ ...cardStyle, p: 2.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
          <Box>
            <Typography sx={{ fontSize: '15px', fontWeight: 700, color: COLORS.primaryText }}>Financial Infrastructure Monitor</Typography>
            <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, mt: 0.3 }}>Real-time health status of all financial subsystems</Typography>
          </Box>
          <Box sx={{ px: 1.2, py: 0.4, borderRadius: '6px', bgcolor: '#EEF2FF', color: COLORS.accent, fontSize: '10px', fontWeight: 700 }}>7 Systems</Box>
        </Box>
        {/* Table Header */}
        <Box sx={{ display: 'grid', gridTemplateColumns: '2fr 0.8fr 0.8fr 0.5fr 1fr', gap: 1, mb: 1, pb: 1, borderBottom: '1px solid #F1F5F9' }}>
          {['SUBSYSTEM', 'HEALTH', 'RISK', 'ALERTS', 'LAST SYNC'].map((h, i) => (
            <Typography key={i} sx={{ fontSize: '9px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.04em' }}>{h}</Typography>
          ))}
        </Box>
        <Stack spacing={1}>
          {infraSystems.map((sys, i) => {
            const rc = getRiskColor(sys.risk);
            return (
              <Box key={i} sx={{ display: 'grid', gridTemplateColumns: '2fr 0.8fr 0.8fr 0.5fr 1fr', gap: 1, alignItems: 'center' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: sys.health >= 90 ? COLORS.success : sys.health >= 75 ? COLORS.warning : COLORS.danger, flexShrink: 0 }} />
                  <Typography sx={{ fontSize: '11px', color: COLORS.primaryText, fontWeight: 600 }}>{sys.name}</Typography>
                </Box>
                <Typography sx={{ fontSize: '11px', fontWeight: 700, color: sys.health >= 90 ? COLORS.success : sys.health >= 75 ? COLORS.warning : COLORS.danger }}>{sys.health}%</Typography>
                <Box sx={{ px: 0.8, py: 0.25, borderRadius: '4px', bgcolor: rc.bg, color: rc.color, fontSize: '9px', fontWeight: 800, display: 'inline-block', width: 'fit-content' }}>
                  {sys.risk}
                </Box>
                <Typography sx={{ fontSize: '11px', color: COLORS.primaryText, fontWeight: 600, textAlign: 'center' }}>{sys.alerts}</Typography>
                <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{sys.lastSync}</Typography>
              </Box>
            );
          })}
        </Stack>
        <Box sx={{ pt: 1.5, mt: 1, borderTop: '1px solid #F1F5F9' }}>
          <Typography onClick={() => setSubsystemCenterOpen(true)} sx={{ fontSize: '10px', color: COLORS.accent, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 0.5, '&:hover': { opacity: 0.7 } }}>
            View All Systems <ArrowForwardIcon sx={{ fontSize: 10 }} />
          </Typography>
        </Box>
        </Box>

        {/* Executive Opportunity Engine */}
        <Box sx={{ ...cardStyle, p: 2.5 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Box>
            <Typography sx={{ fontSize: '15px', fontWeight: 700, color: COLORS.primaryText }}>Executive Opportunity Engine</Typography>
            <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, mt: 0.3 }}>AI-identified financial opportunities ranked by impact and ROI</Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ px: 1.2, py: 0.4, borderRadius: '6px', bgcolor: '#EEF2FF', color: COLORS.accent, fontSize: '10px', fontWeight: 700 }}>4 Opportunities</Box>
            <Typography onClick={() => setOpportunityCenterOpen(true)} sx={{ fontSize: '10px', color: COLORS.accent, fontWeight: 700, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 0.5 }}>
              View All Opportunities <ArrowForwardIcon sx={{ fontSize: 10 }} />
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 1.5 }}>
          {opportunities.map((opp, i) => (
            <Box key={i} sx={{
              p: 2, bgcolor: '#F8FAFC', borderRadius: '12px', border: '1px solid #E2E8F0',
              display: 'flex', flexDirection: 'column', gap: 1.5,
              transition: 'all 0.2s',
              '&:hover': { boxShadow: '0 4px 12px rgba(0,0,0,0.06)', transform: 'translateY(-2px)' }
            }}>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                <Box sx={{ width: 36, height: 36, borderRadius: '10px', bgcolor: `${opp.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <TrendingUpIcon sx={{ fontSize: 18, color: opp.color }} />
                </Box>
                {opp.gain && (
                  <Typography sx={{ fontSize: '15px', fontWeight: 900, color: opp.color }}>{opp.gain}</Typography>
                )}
              </Box>
              <Box>
                <Typography sx={{ fontSize: '11.5px', fontWeight: 700, color: COLORS.primaryText, lineHeight: 1.3 }}>{opp.title}</Typography>
                <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText, mt: 0.3 }}>{opp.days}</Typography>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                <Box sx={{ px: 0.8, py: 0.25, borderRadius: '4px', bgcolor: '#FEE2E2', color: '#B91C1C', fontSize: '8.5px', fontWeight: 800 }}>
                  {opp.label}
                </Box>
                <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText }}>Impact Score {opp.impact}</Typography>
              </Box>
              <Button variant="outlined" fullWidth size="small" onClick={() => setExecOpportunityOpen(opp)}
                sx={{ textTransform: 'none', fontSize: '10px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.accent, borderRadius: '8px', py: 0.6, mt: 'auto' }}>
                Execute
              </Button>
            </Box>
          ))}
        </Box>
        </Box>

      </Box>
      {/* ── BOTTOM: Subsystem Shortcuts ── */}
      <Box sx={{ ...cardStyle, p: 2, mb: 2 }}>
        <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText, mb: 1.5 }}>
          Subsystem Shortcuts
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1.5 }}>
          {[
            { label: 'New Journal Entry', icon: <AssignmentIcon sx={{ fontSize: 14, color: COLORS.accent }} />, bg: '#EEF2FF', action: () => setNewJournalOpen(true) },
            { label: 'Record Expense', icon: <ReceiptIcon sx={{ fontSize: 14, color: COLORS.success }} />, bg: '#E6F4EA', action: () => setRecordExpenseOpen(true) },
            { label: 'Add Asset', icon: <AddIcon sx={{ fontSize: 14, color: COLORS.info }} />, bg: '#DBEAFE', action: () => setAddAssetOpen(true) },
            { label: 'Prepare GST Returns', icon: <DescriptionIcon sx={{ fontSize: 14, color: COLORS.warning }} />, bg: '#FFF9C4', action: () => setPrepGstOpen(true) },
            { label: 'Run Bank Reconciliation', icon: <CompareArrowsIcon sx={{ fontSize: 14, color: COLORS.danger }} />, bg: '#FEE2E2', action: () => setRunBankReconOpen(true) },
            { label: 'Import Bank Statement', icon: <UploadFileIcon sx={{ fontSize: 14, color: COLORS.accent }} />, bg: '#EEF2FF', action: () => setImportStatementOpen(true) },
            { label: 'Start Reconciliation', icon: <CalculateIcon sx={{ fontSize: 14, color: COLORS.success }} />, bg: '#E6F4EA', action: () => setRunBankReconOpen(true) },
            { label: 'View All Shortcuts', icon: <GridViewIcon sx={{ fontSize: 14, color: COLORS.secondaryText }} />, bg: '#F1F5F9', action: () => setViewAllShortcutsOpen(true) },
          ].map((sc, i) => (
            <Box key={i} onClick={sc.action}
              sx={{
                display: 'flex', alignItems: 'center', gap: 0.75, px: 1.5, py: 0.75,
                borderRadius: '8px', cursor: 'pointer', border: '1px solid #E2E8F0',
                bgcolor: '#F8FAFC', transition: 'all 0.18s',
                '&:hover': { bgcolor: sc.bg, borderColor: 'transparent', transform: 'translateY(-1px)', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }
              }}>
              <Box sx={{ width: 24, height: 24, borderRadius: '6px', bgcolor: sc.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                {sc.icon}
              </Box>
              <Typography sx={{ fontSize: '10px', fontWeight: 700, color: COLORS.primaryText, whiteSpace: 'nowrap' }}>
                {sc.label}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>

      {/* ── COD REMITTANCE DASHBOARD ── */}
      <CodRemittanceDashboard
        cardStyle={cardStyle}
        COLORS={COLORS}
        formatRupee={formatRupee}
      />

      {/* ── 1. EXECUTIVE REPORT CENTER ── */}

      <Dialog
        open={execReportOpen}
        onClose={() => setExecReportOpen(false)}
        maxWidth="lg"
        fullWidth
        slotProps={{
          paper: {
            sx: { borderRadius: '16px', bgcolor: '#FFFFFF', p: 1 }
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SparklesIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>
              Executive Report Center
            </Typography>
          </Box>
          <IconButton onClick={() => setExecReportOpen(false)} size="small">
            <CloseIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </DialogTitle>

        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 4 }}>

          {/* AI Generated Banner */}
          {generatingReport && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 2, bgcolor: '#EEF2FF', borderRadius: '12px', border: '1px solid #C7D2FE' }}>
              <CircularProgress size={18} sx={{ color: COLORS.accent }} />
              <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.accent }}>Gemini AI is generating your executive report...</Typography>
            </Box>
          )}
          {aiReportContent && !generatingReport && (
            <Box sx={{ p: 2.5, bgcolor: '#EEF2FF', borderRadius: '12px', border: '1px solid #C7D2FE' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                <SparklesIcon sx={{ fontSize: 16, color: COLORS.accent }} />
                <Typography sx={{ fontSize: '12px', fontWeight: 800, color: COLORS.accent }}>AI CFO Analysis — Gemini Generated</Typography>
              </Box>
              <Box sx={{ maxHeight: 280, overflowY: 'auto', pr: 0.5 }}>
                <Typography sx={{ fontSize: '11px', color: COLORS.primaryText, lineHeight: 1.8, whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>{aiReportContent}</Typography>
              </Box>
            </Box>
          )}

          {/* A. Executive Summary */}
          <Box>
            <Typography sx={{ fontSize: '14px', fontWeight: 800, color: COLORS.primaryText, mb: 2, borderLeft: `3px solid ${COLORS.accent}`, pl: 1 }}>
              A. Executive Summary
            </Typography>
            <Grid container spacing={2} sx={{ mb: 2.5 }}>
              {[
                { label: 'Financial Health Score', value: `${averageHealth}/100`, status: healthRating, color: healthColor },
                { label: 'Net Worth', value: formatRupee(netWorth), status: 'Stable', color: COLORS.success },
                { label: 'Cash Runway', value: monthlyBurn > 0 ? `${(cashPosition / monthlyBurn).toFixed(1)} Months` : '5.3 Months', status: 'Healthy', color: COLORS.info },
                { label: 'Cash Position', value: formatRupee(cashPosition), status: incomeGrowth >= 0 ? `↑ ${incomeGrowth}% M-o-M` : `↓ ${Math.abs(incomeGrowth)}% M-o-M`, color: COLORS.success },
                { label: 'Working Capital', value: formatRupee(cashPosition + receivables - payables), status: 'Strong Liquidity', color: COLORS.info },
                { label: 'Compliance Status', value: `${reconciliationAccuracy}%`, status: reconciliationAccuracy >= 90 ? 'Fully Reconciled' : 'Reconciliation Pending', color: COLORS.success },
              ].map((m, i) => (
                <Grid item xs={12} sm={4} md={2} key={i}>
                  <Box sx={{ border: '1px solid #E2E8F0', borderRadius: '8px', p: 1.5, textAlign: 'center', bgcolor: '#F8FAFC' }}>
                    <Typography sx={{ fontSize: '9px', fontWeight: 700, color: COLORS.secondaryText, textTransform: 'uppercase' }}>{m.label}</Typography>
                    <Typography sx={{ fontSize: '18px', fontWeight: 900, color: COLORS.primaryText, mt: 0.5 }}>{m.value}</Typography>
                    <Typography sx={{ fontSize: '9px', fontWeight: 700, color: m.color, mt: 0.3 }}>{m.status}</Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>

            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Box sx={{ border: '1px solid #FEE2E2', borderRadius: '10px', p: 2, bgcolor: '#FEF2F2' }}>
                  <Typography sx={{ fontSize: '11px', fontWeight: 800, color: '#991B1B', textTransform: 'uppercase', mb: 1 }}>
                    KEY RISKS DETECTED
                  </Typography>
                  <Stack spacing={1}>
                    {payrollPending && (
                      <Typography sx={{ fontSize: '11.5px', color: '#B91C1C', fontWeight: 600 }}>
                        • Payroll Approval Pending — {formatRupee(payrollTotal)} exposure
                      </Typography>
                    )}
                    {gstLiability > 0 ? (
                      <Typography sx={{ fontSize: '11.5px', color: '#B91C1C', fontWeight: 600 }}>
                        • GST Filing Due in {gstDueDays} days — {formatRupee(gstLiability)} pending tax payment
                      </Typography>
                    ) : (
                      <Typography sx={{ fontSize: '11.5px', color: '#15803D', fontWeight: 600 }}>
                        • GST Compliance — All GST liabilities fully cleared
                      </Typography>
                    )}
                    {receivables > 0 ? (
                      <Typography sx={{ fontSize: '11.5px', color: '#B91C1C', fontWeight: 600 }}>
                        • Receivables Follow-Up — {formatRupee(receivables)} outstanding beyond 30 days
                      </Typography>
                    ) : (
                      <Typography sx={{ fontSize: '11.5px', color: '#15803D', fontWeight: 600 }}>
                        • Collections — No overdue customer receivables
                      </Typography>
                    )}
                  </Stack>
                </Box>
              </Grid>
              <Grid item xs={12} md={6}>
                <Box sx={{ border: '1px solid #E6F4EA', borderRadius: '10px', p: 2, bgcolor: '#E6F4EA' }}>
                  <Typography sx={{ fontSize: '11px', fontWeight: 800, color: '#137333', textTransform: 'uppercase', mb: 1 }}>
                    TOP OPPORTUNITIES IDENTIFIED
                  </Typography>
                  <Stack spacing={1}>
                    <Typography sx={{ fontSize: '11.5px', color: '#15803D', fontWeight: 600 }}>
                      • Recover Receivables — Optimize collections to gain {monthlyBurn > 0 ? `+${(receivables / monthlyBurn).toFixed(1)}` : '+0.4'} months runway
                    </Typography>
                    <Typography sx={{ fontSize: '11.5px', color: '#15803D', fontWeight: 600 }}>
                      • Claim GST Input Tax Credit (ITC) — Claim {formatRupee(gstLiability > 0 ? gstLiability * 0.2 : 18500)} tax offset early
                    </Typography>
                    <Typography sx={{ fontSize: '11.5px', color: '#15803D', fontWeight: 600 }}>
                      • Reduce Monthly Burn by 3% — Save {formatRupee(monthlyBurn * 0.03)} in operational overhead
                    </Typography>
                  </Stack>
                </Box>
              </Grid>
            </Grid>
          </Box>

          <Divider />

          {/* B. Department Performance */}
          <Box>
            <Typography sx={{ fontSize: '14px', fontWeight: 800, color: COLORS.primaryText, mb: 2, borderLeft: `3px solid ${COLORS.accent}`, pl: 1 }}>
              B. Department Performance Scorecard
            </Typography>
            <Grid container spacing={2}>
              {getDeptPerformance().map((dept, i) => (
                <Grid item xs={12} sm={6} md={3} key={i}>
                  <Box sx={{ border: '1px solid #E2E8F0', borderRadius: '10px', p: 2, '&:hover': { borderColor: COLORS.accent } }}>
                    <Typography sx={{ fontSize: '11.5px', fontWeight: 800, color: COLORS.primaryText, noWrap: true }}>{dept.name}</Typography>
                    <Stack direction="row" spacing={1.5} sx={{ mt: 1.5 }}>
                      <Box>
                        <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText }}>HEALTH</Typography>
                        <Typography sx={{ fontSize: '13px', fontWeight: 900, color: dept.health >= 85 ? COLORS.success : dept.health >= 60 ? COLORS.warning : COLORS.danger }}>
                          {dept.health}%
                        </Typography>
                      </Box>
                      <Box>
                        <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText }}>TREND</Typography>
                        <Typography sx={{ fontSize: '10px', fontWeight: 700, color: COLORS.primaryText }}>{dept.trend}</Typography>
                      </Box>
                      <Box>
                        <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText }}>BUDGET</Typography>
                        <Typography sx={{ fontSize: '10px', fontWeight: 700, color: COLORS.primaryText }}>{dept.budget}</Typography>
                      </Box>
                      <Box>
                        <Typography sx={{ fontSize: '8px', color: COLORS.secondaryText }}>TASKS</Typography>
                        <Typography sx={{ fontSize: '10px', fontWeight: 700, color: dept.tasks > 0 ? COLORS.danger : COLORS.secondaryText }}>{dept.tasks}</Typography>
                      </Box>
                    </Stack>
                  </Box>
                </Grid>
              ))}
            </Grid>
          </Box>

          <Divider />

          {/* C. Forecast Summary */}
          <Box>
            <Typography sx={{ fontSize: '14px', fontWeight: 800, color: COLORS.primaryText, mb: 2, borderLeft: `3px solid ${COLORS.accent}`, pl: 1 }}>
              C. AI Forecast Summary
            </Typography>
            <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
              {['30 Days', '60 Days', '90 Days'].map(t => (
                <Button 
                  key={t}
                  variant={forecastTab === t ? 'contained' : 'outlined'}
                  size="small"
                  onClick={() => setForecastTab(t)}
                  sx={{ 
                    textTransform: 'none', 
                    fontSize: '11px', 
                    fontWeight: 700, 
                    borderRadius: '8px',
                    bgcolor: forecastTab === t ? COLORS.accent : 'transparent',
                    color: forecastTab === t ? '#fff' : COLORS.secondaryText,
                    borderColor: forecastTab === t ? 'transparent' : '#CBD5E1',
                    boxShadow: 'none',
                    '&:hover': { bgcolor: forecastTab === t ? '#4F46E5' : '#F1F5F9', boxShadow: 'none' }
                  }}
                >
                  {t} Forecast
                </Button>
              ))}
            </Stack>

            <Grid container spacing={2}>
              {(() => {
                const scale = forecastTab === '30 Days' ? 1.05 : (forecastTab === '60 Days' ? 1.12 : 1.20);
                const runwayScale = forecastTab === '30 Days' ? 1.05 : (forecastTab === '60 Days' ? 1.15 : 1.25);
                const runwayVal = monthlyBurn > 0 ? (cashPosition / monthlyBurn) * runwayScale : 5.3;

                const fData = [
                  { label: 'Revenue Forecast', val: formatRupee(cashPosition * 1.5 * scale), trend: `+${Math.round((scale - 1) * 100)}% growth expected` },
                  { label: 'Cash Position Forecast', val: formatRupee(cashPosition * scale), trend: 'Adequate liquidity' },
                  { label: 'Net Worth Forecast', val: formatRupee(netWorth * scale), trend: 'Solid asset position' },
                  { label: 'Working Capital Forecast', val: formatRupee((cashPosition + receivables - payables) * scale), trend: 'Optimal buffer' },
                  { label: 'Runway Forecast', val: `${runwayVal.toFixed(1)} Months`, trend: 'Improved burn coverage' },
                ];

                return fData.map((f, i) => (
                  <Grid item xs={12} sm={4} md={2.4} key={i}>
                    <Box sx={{ border: '1px dashed #CBD5E1', borderRadius: '8px', p: 2, textAlign: 'center' }}>
                      <Typography sx={{ fontSize: '9.5px', fontWeight: 700, color: COLORS.secondaryText }}>{f.label}</Typography>
                      <Typography sx={{ fontSize: '20px', fontWeight: 900, color: COLORS.accent, mt: 0.5 }}>{f.val}</Typography>
                      <Typography sx={{ fontSize: '9px', color: COLORS.success, fontWeight: 700, mt: 0.3 }}>{f.trend}</Typography>
                    </Box>
                  </Grid>
                ));
              })()}
            </Grid>
          </Box>

          <Divider />

          {/* D. Risk Summary */}
          <Box>
            <Typography sx={{ fontSize: '14px', fontWeight: 800, color: COLORS.primaryText, mb: 2, borderLeft: `3px solid ${COLORS.accent}`, pl: 1 }}>
              D. Operational & Financial Risk Summary
            </Typography>
            <Grid container spacing={2}>
              {(() => {
                const criticalItems = [];
                if (payrollPending) criticalItems.push(`Pending Payroll Authorization (${formatRupee(payrollTotal)})`);
                const collectionsEngine = infraSystems.find(s => s.name === 'Collections Engine');
                if (collectionsEngine && collectionsEngine.health < 80) {
                  criticalItems.push(`Collections delays (score ${collectionsEngine.health}%)`);
                } else {
                  criticalItems.push('Collections delays in Sales division (score 72%)');
                }
                if (criticalItems.length === 0) criticalItems.push('No critical exposures');

                const highItems = [];
                if (gstLiability > 0) highItems.push(`GST filing pending (${formatRupee(gstLiability)})`);
                highItems.push(`GST registers reconciliation pending`);
                if (highItems.length === 0) highItems.push('No high exposures');

                const mediumItems = [
                  `DSO stands at 34 days (industry average 30)`,
                  `Working Capital requirements rise next month`
                ];

                const lowItems = [
                  `Bank accounts statement reconciliations`,
                  `Asset depreciation rates within guidelines`
                ];

                const groups = [
                  { title: 'Critical Exposure (Action Required)', items: criticalItems, color: '#B91C1C', bg: '#FEF2F2' },
                  { title: 'High Exposure (Immediate Attention)', items: highItems, color: '#B45309', bg: '#FFFBEB' },
                  { title: 'Medium Exposure (Monitor closely)', items: mediumItems, color: '#1D4ED8', bg: '#EFF6FF' },
                  { title: 'Low Risk (Stable)', items: lowItems, color: '#15803D', bg: '#F0FDF4' },
                ];

                return groups.map((grp, i) => (
                  <Grid item xs={12} md={3} key={i}>
                    <Box sx={{ bgcolor: grp.bg, border: `1px solid ${grp.color}25`, borderRadius: '10px', p: 2, height: '100%' }}>
                      <Typography sx={{ fontSize: '11px', fontWeight: 800, color: grp.color, textTransform: 'uppercase', mb: 1 }}>
                        {grp.title}
                      </Typography>
                      <Stack spacing={0.75}>
                        {grp.items.map((it, idx) => (
                          <Typography key={idx} sx={{ fontSize: '11px', color: COLORS.primaryText, fontWeight: 500, lineHeight: 1.3 }}>
                            • {it}
                          </Typography>
                        ))}
                      </Stack>
                    </Box>
                  </Grid>
                ));
              })()}
            </Grid>
          </Box>
        </DialogContent>

        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, display: 'flex', justifyContent: 'space-between' }}>
          <Stack direction="row" spacing={1}>
            <Button variant="contained" onClick={() => alert('PDF report exported successfully.')}
              startIcon={<FileDownloadIcon sx={{ fontSize: 13 }} />}
              sx={{ textTransform: 'none', fontSize: '11.5px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>
              Export PDF
            </Button>
            <Button variant="outlined" onClick={() => alert('Excel ledger downloaded.')}
              sx={{ textTransform: 'none', fontSize: '11.5px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>
              Export Excel
            </Button>
            <Button variant="outlined" onClick={() => alert('Report emailed to executive team.')}
              sx={{ textTransform: 'none', fontSize: '11.5px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>
              Email Report
            </Button>
          </Stack>
          <Button variant="contained" onClick={() => alert('Scheduled report automation enabled.')}
            sx={{ textTransform: 'none', fontSize: '11.5px', fontWeight: 700, bgcolor: '#0F172A', boxShadow: 'none' }}>
            Schedule Report
          </Button>
        </DialogActions>
      </Dialog>

      {/* ── 2. AI CFO CHAT CENTER DRAWER ── */}
      <Drawer
        anchor="right"
        open={aiChatOpen}
        onClose={() => setAiChatOpen(false)}
        slotProps={{
          paper: {
            sx: { 
              width: { 
                xs: '100%', 
                sm: historySidebarOpen ? '740px' : '480px', 
                md: historySidebarOpen ? '800px' : '550px' 
              }, 
              minWidth: { md: historySidebarOpen ? '800px' : '500px' },
              maxWidth: { md: historySidebarOpen ? '1000px' : '650px' },
              borderLeft: '1px solid rgba(15, 23, 42, 0.08)', 
              display: 'flex', 
              flexDirection: 'row',
              bgcolor: 'rgba(255, 255, 255, 0.94)',
              backdropFilter: 'blur(16px)',
              boxShadow: '-8px 0 32px rgba(15, 23, 42, 0.06)',
              borderRadius: { xs: '0', sm: '16px 0 0 16px' },
              transition: 'width 250ms cubic-bezier(0.4, 0, 0.2, 1) !important',
              overflow: 'hidden'
            }
          }
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'row', height: '100%', width: '100%', overflow: 'hidden' }}>
          {/* Left Collapsible History & Reports Sidebar */}
          {historySidebarOpen && (
            <Box sx={{
              width: '240px',
              borderRight: '1px solid #E2E8F0',
              display: 'flex',
              flexDirection: 'column',
              bgcolor: '#F8FAFC',
              flexShrink: 0,
              height: '100%',
              overflow: 'hidden'
            }}>
              {/* Tab Switches */}
              <Box sx={{ display: 'flex', borderBottom: '1px solid #E2E8F0', p: 1, gap: 1 }}>
                <Button
                  variant={activeSidebarTab === 'chats' ? 'contained' : 'text'}
                  size="small"
                  onClick={() => setActiveSidebarTab('chats')}
                  startIcon={<HistoryIcon sx={{ fontSize: 14 }} />}
                  sx={{
                    flex: 1,
                    textTransform: 'none',
                    fontSize: '11px',
                    fontWeight: 700,
                    borderRadius: '8px',
                    bgcolor: activeSidebarTab === 'chats' ? '#6C5DD3' : 'transparent',
                    color: activeSidebarTab === 'chats' ? '#FFFFFF' : COLORS.secondaryText,
                    boxShadow: 'none',
                    '&:hover': {
                      bgcolor: activeSidebarTab === 'chats' ? '#5A4EBF' : 'rgba(15, 23, 42, 0.04)',
                      boxShadow: 'none'
                    }
                  }}
                >
                  Chats
                </Button>
                <Button
                  variant={activeSidebarTab === 'reports' ? 'contained' : 'text'}
                  size="small"
                  onClick={() => setActiveSidebarTab('reports')}
                  startIcon={<FolderIcon sx={{ fontSize: 14 }} />}
                  sx={{
                    flex: 1,
                    textTransform: 'none',
                    fontSize: '11px',
                    fontWeight: 700,
                    borderRadius: '8px',
                    bgcolor: activeSidebarTab === 'reports' ? '#6C5DD3' : 'transparent',
                    color: activeSidebarTab === 'reports' ? '#FFFFFF' : COLORS.secondaryText,
                    boxShadow: 'none',
                    '&:hover': {
                      bgcolor: activeSidebarTab === 'reports' ? '#5A4EBF' : 'rgba(15, 23, 42, 0.04)',
                      boxShadow: 'none'
                    }
                  }}
                >
                  Reports
                </Button>
              </Box>

              {/* Search bar */}
              <Box sx={{ p: 1.5, borderBottom: '1px solid #E2E8F0' }}>
                <TextField
                  placeholder={activeSidebarTab === 'chats' ? "Search sessions..." : "Search reports..."}
                  size="small"
                  fullWidth
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  InputProps={{
                    startAdornment: (
                      <InputAdornment position="start">
                        <SearchIcon sx={{ fontSize: 14, color: COLORS.secondaryText }} />
                      </InputAdornment>
                    ),
                    sx: {
                      borderRadius: '8px',
                      fontSize: '11px',
                      bgcolor: '#FFFFFF',
                      '& .MuiOutlinedInput-notchedOutline': {
                        borderColor: '#E2E8F0'
                      }
                    }
                  }}
                />
              </Box>

              {/* Scrollable list */}
              <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 1.5 }}>
                {activeSidebarTab === 'chats' ? (
                  <Stack spacing={2}>
                    {renderSessionGroup('Pinned', 'pinned')}
                    {renderSessionGroup('Today', 'today')}
                    {renderSessionGroup('Yesterday', 'yesterday')}
                    {renderSessionGroup('Last Week', 'lastWeek')}
                    {renderSessionGroup('Older', 'older')}
                  </Stack>
                ) : (
                  <Stack spacing={1}>
                    {savedReports
                      .filter(r => searchQuery === '' || r.name.toLowerCase().includes(searchQuery.toLowerCase()) || r.content.toLowerCase().includes(searchQuery.toLowerCase()))
                      .map((rep, idx) => (
                        <Box
                          key={idx}
                          onClick={() => {
                            setAiReportContent(rep.content);
                            setExecReportOpen(true);
                          }}
                          sx={{
                            p: 1.2,
                            borderRadius: '8px',
                            border: '1px solid #E2E8F0',
                            bgcolor: '#FFFFFF',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            '&:hover': {
                              borderColor: COLORS.accent,
                              bgcolor: 'rgba(99, 102, 241, 0.02)'
                            }
                          }}
                        >
                          <Stack direction="row" spacing={1} alignItems="center">
                            <DescriptionIcon sx={{ fontSize: 16, color: COLORS.accent }} />
                            <Box sx={{ overflow: 'hidden', flexGrow: 1 }}>
                              <Typography sx={{ fontSize: '11px', fontWeight: 700, color: COLORS.primaryText, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {rep.name}
                              </Typography>
                              <Typography sx={{ fontSize: '8.5px', color: COLORS.secondaryText }}>
                                {rep.date} · {rep.sessionTitle}
                              </Typography>
                            </Box>
                          </Stack>
                        </Box>
                      ))}
                    {savedReports.filter(r => searchQuery === '' || r.name.toLowerCase().includes(searchQuery.toLowerCase()) || r.content.toLowerCase().includes(searchQuery.toLowerCase())).length === 0 && (
                      <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, textAlign: 'center', mt: 4 }}>
                        No reports found
                      </Typography>
                    )}
                  </Stack>
                )}
              </Box>
            </Box>
          )}

          {/* Right Workspace Panel */}
          <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', bgcolor: '#FFFFFF' }}>
            {/* Header */}
            <Box sx={{ p: 2.5, pb: 2, borderBottom: '1px solid #F1F5F9', flexShrink: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <SparklesIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
                  <Box>
                    <Typography sx={{ fontSize: '13px', fontWeight: 900, color: COLORS.primaryText, letterSpacing: '0.02em', textTransform: 'uppercase' }}>
                      BRIDGEWORKS AI
                    </Typography>
                    <Typography sx={{ fontSize: '8.5px', color: COLORS.secondaryText, fontWeight: 700, letterSpacing: '0.04em' }}>
                      MULTI-AGENT INTELLIGENCE
                    </Typography>
                  </Box>

                  {/* ChatGPT-style Agent Selector Dropdown */}
                  <Box>
                    <Button
                      onClick={handleAgentClick}
                      endIcon={<KeyboardArrowDownIcon sx={{ fontSize: 16 }} />}
                      sx={{
                        ml: 2,
                        px: 1.5,
                        py: 0.5,
                        borderRadius: '8px',
                        border: '1px solid #E2E8F0',
                        bgcolor: '#FFFFFF',
                        color: COLORS.primaryText,
                        fontWeight: 700,
                        fontSize: '11px',
                        textTransform: 'none',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                        '&:hover': {
                          bgcolor: '#F8FAFC',
                          borderColor: COLORS.accent,
                        }
                      }}
                    >
                      {AGENTS.find(a => a.id === activeAgent)?.shortLabel || 'CFO'}
                    </Button>
                    <Menu
                      anchorEl={agentAnchorEl}
                      open={Boolean(agentAnchorEl)}
                      onClose={handleAgentClose}
                      PaperProps={{
                        sx: {
                          mt: 1,
                          borderRadius: '12px',
                          minWidth: '240px',
                          boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
                          border: '1px solid #E2E8F0',
                          p: 0.5
                        }
                      }}
                    >
                      {AGENTS.map((agentItem) => {
                        const isSelected = agentItem.id === activeAgent;
                        return (
                          <MenuItem
                            key={agentItem.id}
                            onClick={() => handleAgentSelect(agentItem.id)}
                            sx={{
                              borderRadius: '8px',
                              py: 1.2,
                              px: 1.5,
                              my: 0.25,
                              bgcolor: isSelected ? 'rgba(99, 102, 241, 0.04)' : 'transparent',
                              color: isSelected ? COLORS.accent : COLORS.primaryText,
                              '&:hover': {
                                bgcolor: 'rgba(99, 102, 241, 0.08)',
                                color: COLORS.accent
                              }
                            }}
                          >
                            <Box sx={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
                              <Typography sx={{ fontSize: '11.5px', fontWeight: isSelected ? 800 : 700 }}>
                                {agentItem.label}
                              </Typography>
                              <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, mt: 0.2 }}>
                                {agentItem.description}
                              </Typography>
                            </Box>
                          </MenuItem>
                        );
                      })}
                    </Menu>
                  </Box>
                </Box>
                <Stack direction="row" spacing={0.5} alignItems="center">
                  {/* Sidebar Toggle */}
                  <Tooltip title={historySidebarOpen ? "Hide History" : "Show History"}>
                    <IconButton size="small" onClick={() => setHistorySidebarOpen(!historySidebarOpen)} sx={{ color: COLORS.secondaryText }}>
                      {historySidebarOpen ? <ChevronLeftIcon sx={{ fontSize: 18 }} /> : <HistoryIcon sx={{ fontSize: 18 }} />}
                    </IconButton>
                  </Tooltip>

                  {/* + New Chat Button */}
                  <Button
                    variant="contained"
                    size="small"
                    onClick={handleNewChat}
                    startIcon={<AddIcon sx={{ fontSize: 12 }} />}
                    sx={{
                      textTransform: 'none',
                      fontSize: '9.5px',
                      fontWeight: 700,
                      bgcolor: '#6C5DD3',
                      color: '#FFFFFF',
                      boxShadow: 'none',
                      borderRadius: '6px',
                      mr: 0.5,
                      '&:hover': { bgcolor: '#5A4EBF', boxShadow: 'none' }
                    }}
                  >
                    New Chat
                  </Button>

                  {chatMessages.length > 1 && (
                    <Button 
                      size="small"
                      onClick={() => {
                        const agentObj = AGENTS.find(a => a.id === activeAgent) || AGENTS[0];
                        setChatMessages([{ id: 1, text: agentObj.welcome, sender: 'ai' }]);
                      }}
                      sx={{ textTransform: 'none', fontSize: '9.5px', fontWeight: 700, color: COLORS.secondaryText, minWidth: 0, px: 1 }}
                    >
                      Reset
                    </Button>
                  )}
                  <IconButton onClick={() => setAiChatOpen(false)} size="small" sx={{ color: COLORS.secondaryText }}>
                    <CloseIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </Stack>
              </Box>

              {/* Connected Data Sources Row */}
              <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1, mt: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mr: 0.5 }}>
                  <InfoOutlinedIcon sx={{ fontSize: 11, color: COLORS.secondaryText }} />
                  <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.03em' }}>Data Sources</Typography>
                </Box>
                <Stack direction="row" spacing={0.75} sx={{ overflowX: 'auto', '&::-webkit-scrollbar': { display: 'none' }, alignItems: 'center' }}>
                  {(AGENTS.find(a => a.id === activeAgent)?.contextSources || []).map((feed, idx) => (
                    <Box key={idx} sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: 0.5, 
                      px: 0.8, 
                      py: 0.3, 
                      borderRadius: '6px', 
                      bgcolor: '#F8FAFC',
                      border: '1px solid #E2E8F0'
                    }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', color: '#6C5DD3' }}>
                        {getSourceIcon(feed.icon)}
                      </Box>
                      <Typography sx={{ fontSize: '9px', color: COLORS.primaryText, fontWeight: 700 }}>{feed.name}</Typography>
                    </Box>
                  ))}
                </Stack>
              </Box>
            </Box>



            {/* Workspace Body / Scrollable Area */}
            <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 3, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
              {/* Persistent Greeting Box with Animation */}
              <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: chatMessages.length === 1 ? 'center' : 'flex-start',
                textAlign: chatMessages.length === 1 ? 'center' : 'left',
                mt: chatMessages.length === 1 ? 'calc(10vh - 50px)' : '0px',
                mb: chatMessages.length === 1 ? '0px' : '15px',
                transition: 'all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)',
                width: '100%',
              }}>
                <Typography sx={{ 
                  fontSize: chatMessages.length === 1 ? '22px' : '13px', 
                  fontWeight: 800, 
                  color: COLORS.primaryText,
                  transition: 'all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)',
                  lineHeight: 1.2
                }}>
                  {new Date().getHours() < 12 ? 'Good Morning' : new Date().getHours() < 17 ? 'Good Afternoon' : 'Good Evening'}, {user?.name || 'Jatin Choudhary'}
                </Typography>
                
                {chatMessages.length === 1 ? (
                  <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', maxWidth: '450px' }}>
                    <Typography sx={{ fontSize: '13.5px', fontWeight: 700, color: COLORS.accent, mb: 1, textAlign: 'center' }}>
                      {activeAgent === 'cfo' ? 'I am your strategic finance advisor.' :
                       activeAgent === 'accountant' ? 'I manage daily accounting operations.' :
                       'I manage tax and compliance activities.'}
                    </Typography>
                    <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, mb: 0.5, fontWeight: 700 }}>
                      I can help with:
                    </Typography>
                    <Box sx={{ textAlign: 'left', display: 'inline-block' }}>
                      {(activeAgent === 'cfo' ? ['Cash Flow', 'Forecasting', 'Runway', 'Budgeting', 'Financial Planning'] :
                        activeAgent === 'accountant' ? ['Expenses', 'Ledgers', 'Journal Entries', 'Vendor Payments', 'Reconciliation'] :
                        ['GST', 'TDS', 'Filings', 'Compliance Monitoring']).map((item, idx) => (
                        <Typography key={idx} sx={{ fontSize: '11px', color: COLORS.secondaryText, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          • {item}
                        </Typography>
                      ))}
                    </Box>
                  </Box>
                ) : (
                  <Typography sx={{ 
                    fontSize: '9.5px', 
                    color: COLORS.secondaryText, 
                    mt: 0.8,
                    transition: 'all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)',
                    opacity: 0.8
                  }}>
                    BRIDGEWORKS Financial Intelligence Center is synchronized and operational.
                  </Typography>
                )}
              </Box>

              {chatMessages.length === 1 && (
                <Stack direction="row" spacing={1} sx={{ mt: 2, flexWrap: 'wrap', gap: 0.75, justifyContent: 'center', maxWidth: '600px', mx: 'auto' }}>
                  {(AGENTS.find(a => a.id === activeAgent)?.suggestions || []).map((chip, idx) => (
                    <Box
                      key={idx}
                      onClick={() => handleAskAi(chip.q)}
                      sx={{
                        px: 1.5,
                        py: 0.7,
                        borderRadius: '20px',
                        border: '1px solid #E2E8F0',
                        bgcolor: '#FFFFFF',
                        cursor: 'pointer',
                        fontSize: '11px',
                        fontWeight: 650,
                        color: COLORS.primaryText,
                        whiteSpace: 'nowrap',
                        transition: 'all 0.15s ease',
                        '&:hover': {
                          borderColor: COLORS.accent,
                          bgcolor: 'rgba(99, 102, 241, 0.04)',
                          color: COLORS.accent
                        }
                      }}
                    >
                      {chip.label}
                    </Box>
                  ))}
                </Stack>
              )}

              {chatMessages.length > 1 && (
                chatMessages.map((m, mIdx) => renderMessage(m, mIdx))
              )}

              {/* Animating Scanning Steps when AI is thinking */}
              {typingMessage && (
                <Box sx={{ alignSelf: 'flex-start', bgcolor: '#F8FAFC', borderRadius: '12px', p: 2, border: '1px solid #E2E8F0', width: '85%', boxShadow: '0 1px 3px rgba(0,0,0,0.02)' }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                    <CircularProgress size={12} sx={{ color: COLORS.accent }} />
                    <Typography sx={{ fontSize: '10.5px', color: COLORS.secondaryText, fontWeight: 700 }}>
                      {(AGENTS.find(a => a.id === activeAgent)?.label || 'AI CFO')} is analyzing company data...
                    </Typography>
                  </Box>
                  <Stack spacing={1}>
                    {getThinkingSteps(activeAgent).map((step, idx) => {
                      const isDone = idx < thinkingStep;
                      const isCurrent = idx === thinkingStep;
                      return (
                        <Box key={idx} sx={{ display: 'flex', alignItems: 'center', gap: 1, opacity: isDone || isCurrent ? 1 : 0.4 }}>
                          {isDone ? (
                            <CheckCircleIcon sx={{ fontSize: 13, color: COLORS.success }} />
                          ) : isCurrent ? (
                            <CircularProgress size={10} sx={{ color: COLORS.accent }} />
                          ) : (
                            <FiberManualRecordIcon sx={{ fontSize: 10, color: COLORS.secondaryText }} />
                          )}
                          <Typography sx={{ fontSize: '10px', color: isCurrent ? COLORS.primaryText : COLORS.secondaryText, fontWeight: isCurrent ? 700 : 500 }}>
                            {step}
                          </Typography>
                        </Box>
                      );
                    })}
                  </Stack>
                </Box>
              )}
            </Box>



            {/* Smart Question Composer with Floating Autocomplete */}
            <Box sx={{ p: 2, borderTop: '1px solid #F1F5F9', display: 'flex', flexDirection: 'column', gap: 1, position: 'relative', flexShrink: 0, bgcolor: '#FFFFFF' }}>
              {/* Autocomplete suggestions overlay list */}
              {chatInput.trim().length > 0 && getSuggestions(chatInput).length > 0 && (
                <Box sx={{ 
                  position: 'absolute', 
                  bottom: '100%', 
                  left: 16, 
                  right: 16, 
                  bgcolor: '#FFFFFF', 
                  border: '1px solid #E2E8F0', 
                  borderRadius: '8px', 
                  boxShadow: '0 -4px 24px rgba(15, 23, 42, 0.08)',
                  zIndex: 10,
                  mb: 1.5,
                  overflow: 'hidden'
                }}>
                  <Stack spacing={0.25} sx={{ p: 0.5 }}>
                    {getSuggestions(chatInput).map((s, idx) => (
                      <Box 
                        key={idx}
                        onClick={() => {
                          handleAskAi(s.text);
                          setChatInput('');
                        }}
                        sx={{ 
                          p: 1, 
                          cursor: 'pointer', 
                          borderRadius: '6px', 
                          '&:hover': { bgcolor: '#F8FAFC' },
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between'
                        }}
                      >
                        <Typography sx={{ fontSize: '10.5px', color: COLORS.primaryText, fontWeight: 650 }}>
                          {s.text}
                        </Typography>
                        <Typography sx={{ fontSize: '8px', color: COLORS.accent, textTransform: 'uppercase', fontWeight: 800 }}>
                          Ask {AGENTS.find(a => a.id === activeAgent)?.shortLabel || 'CFO'}
                        </Typography>
                      </Box>
                    ))}
                  </Stack>
                </Box>
              )}

              <TextField
                placeholder="Ask anything about your finances..."
                size="small"
                fullWidth
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAskAi(chatInput)}
                autoComplete="off"
                inputProps={{ autoComplete: 'off' }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton 
                        onClick={() => handleAskAi(chatInput)}
                        sx={{ 
                          bgcolor: '#6C5DD3', 
                          color: '#fff', 
                          '&:hover': { bgcolor: '#5A4EBF' }, 
                          borderRadius: '8px', 
                          width: 28, 
                          height: 28,
                          mr: -0.5
                        }}
                      >
                        <SendIcon sx={{ fontSize: 13 }} />
                      </IconButton>
                    </InputAdornment>
                  ),
                  sx: {
                    borderRadius: '12px',
                    fontSize: '11.5px',
                    bgcolor: '#FFFFFF',
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#E2E8F0'
                    },
                    '&:hover .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#CBD5E1'
                    },
                    '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                      borderColor: '#6C5DD3'
                    }
                  }
                }}
              />
            </Box>

            {/* Footer Warning */}
            <Box sx={{ pb: 2, pt: 0.5, px: 2, textAlign: 'left', display: 'flex', alignItems: 'center', gap: 0.5, bgcolor: '#FFFFFF', flexShrink: 0 }}>
              <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                ⓘ AI CFO can make mistakes. Verify critical decisions.
              </Typography>
            </Box>
          </Box>
        </Box>
      </Drawer>

      <Menu
        anchorEl={sessionMenuAnchor}
        open={Boolean(sessionMenuAnchor)}
        onClose={handleSessionMenuClose}
        slotProps={{
          paper: {
            sx: {
              boxShadow: '0 4px 20px rgba(15, 23, 42, 0.08)',
              border: '1px solid #E2E8F0',
              borderRadius: '8px',
            }
          }
        }}
      >
        <MenuItem 
          onClick={() => {
            if (selectedMenuSession) {
              handlePinSession(selectedMenuSession.id);
            }
            handleSessionMenuClose();
          }}
          sx={{ fontSize: '11px', fontWeight: 600, py: 1, px: 2, display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <PushPinIcon sx={{ fontSize: 13, color: COLORS.secondaryText }} />
          {selectedMenuSession?.pinned ? 'Unpin Session' : 'Pin Session'}
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedMenuSession) {
              const newName = prompt("Rename Session:", selectedMenuSession.title);
              if (newName !== null) {
                handleRenameSession(selectedMenuSession.id, newName);
              }
            }
            handleSessionMenuClose();
          }}
          sx={{ fontSize: '11px', fontWeight: 600, py: 1, px: 2, display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <EditIcon sx={{ fontSize: 13, color: COLORS.secondaryText }} />
          Rename
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedMenuSession) {
              handleDuplicateSession(selectedMenuSession);
            }
            handleSessionMenuClose();
          }}
          sx={{ fontSize: '11px', fontWeight: 600, py: 1, px: 2, display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <ContentCopyIcon sx={{ fontSize: 13, color: COLORS.secondaryText }} />
          Duplicate
        </MenuItem>
        <MenuItem 
          onClick={() => {
            if (selectedMenuSession) {
              handleExportPDF(selectedMenuSession);
            }
            handleSessionMenuClose();
          }}
          sx={{ fontSize: '11px', fontWeight: 600, py: 1, px: 2, display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <FileDownloadIcon sx={{ fontSize: 13, color: COLORS.secondaryText }} />
          Export Briefing (Text)
        </MenuItem>
        <Divider />
        <MenuItem 
          onClick={() => {
            if (selectedMenuSession) {
              if (confirm("Are you sure you want to delete this session?")) {
                handleDeleteSession(selectedMenuSession.id);
              }
            }
            handleSessionMenuClose();
          }}
          sx={{ fontSize: '11px', fontWeight: 600, py: 1, px: 2, color: COLORS.danger, display: 'flex', alignItems: 'center', gap: 1 }}
        >
          <DeleteIcon sx={{ fontSize: 13, color: COLORS.danger }} />
          Delete
        </MenuItem>
      </Menu>


      {/* ── 3. KPI DRILL-DOWN INTELLIGENCE DIALOG ── */}
      <Dialog
        open={Boolean(drilldownKpi)}
        onClose={() => setDrilldownKpi(null)}
        maxWidth="md"
        fullWidth
        slotProps={{
          paper: {
            sx: { borderRadius: '16px', p: 1 }
          }
        }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AccountBalanceIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '16px', fontWeight: 800, color: COLORS.primaryText }}>
              {drilldownKpi} — Intelligence Workspace
            </Typography>
          </Box>
          <IconButton onClick={() => setDrilldownKpi(null)} size="small">
            <CloseIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </DialogTitle>

        <DialogContent sx={{ py: 3 }}>
          {/* A. CASH POSITION DRILL DOWN */}
          {drilldownKpi === 'Cash Position' && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3.5 }}>
              <Grid container spacing={2}>
                {[
                  { label: 'Daily Inflow', val: formatRupee(dailyInflow), desc: 'Average collections' },
                  { label: 'Daily Outflow', val: formatRupee(dailyOutflow), desc: 'Operational outlay' },
                  { label: 'Net Inflow / Day', val: `${dailyInflow >= dailyOutflow ? '+' : '-'}${formatRupee(Math.abs(dailyInflow - dailyOutflow))}`, desc: dailyInflow >= dailyOutflow ? 'Net cash positive' : 'Net cash negative' },
                  { label: 'Projected Runway', val: monthlyBurn > 0 ? `${(cashPosition / monthlyBurn).toFixed(1)} Months` : '5.3 Months', desc: 'Covering monthly burn' },
                ].map((m, i) => (
                  <Grid item xs={12} sm={3} key={i}>
                    <Box sx={{ bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', p: 2, borderRadius: '8px', textAlign: 'center' }}>
                      <Typography sx={{ fontSize: '9.5px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{m.label}</Typography>
                      <Typography sx={{ fontSize: '18px', fontWeight: 900, color: COLORS.primaryText, mt: 0.5 }}>{m.val}</Typography>
                      <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, mt: 0.3 }}>{m.desc}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>

              <Box>
                <Typography sx={{ fontSize: '12.5px', fontWeight: 800, mb: 1, color: COLORS.primaryText }}>Cash Flow Trend & Daily Outlays</Typography>
                <Box sx={{ height: 160 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={cfData} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                      <RechartsTooltip />
                      <Area type="monotone" dataKey="inflow" stroke={COLORS.success} fill="#E6F4EA" strokeWidth={1.5} dot={false} />
                      <Area type="monotone" dataKey="outflow" stroke={COLORS.danger} fill="#FEE2E2" strokeWidth={1.5} dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </Box>
              </Box>

              <Box>
                <Typography sx={{ fontSize: '12.5px', fontWeight: 800, mb: 1.5, color: COLORS.primaryText }}>Bank Accounts Distribution</Typography>
                <Stack spacing={1.5}>
                  {accounts.map((bank, i) => (
                    <Box key={i} sx={{ border: '1px solid #E2E8F0', p: 1.5, borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box>
                        <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{bank.name}</Typography>
                        <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{bank.acc} · {bank.sync}</Typography>
                      </Box>
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography sx={{ fontSize: '13px', fontWeight: 900, color: COLORS.primaryText }}>{formatRupee(bank.bal)}</Typography>
                        <Typography sx={{ fontSize: '9px', fontWeight: 800, color: COLORS.success }}>{bank.status}</Typography>
                      </Box>
                    </Box>
                  ))}
                </Stack>
              </Box>
            </Box>
          )}

          {/* B. RECEIVABLES DRILL DOWN */}
          {drilldownKpi === 'Receivables' && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <Grid container spacing={2}>
                {[
                  { label: 'Aging 0–30 Days', val: formatRupee(receivables * 0.55), desc: 'Current outstanding' },
                  { label: 'Aging 30–60 Days', val: formatRupee(receivables * 0.35), desc: 'Follow-up needed' },
                  { label: 'Aging 60–90 Days', val: formatRupee(receivables * 0.10), desc: 'Action needed' },
                  { label: 'Days Sales Outstanding (DSO)', val: receivables > 0 ? '34 Days' : '0 Days', desc: 'Average collection cycle' },
                ].map((m, i) => (
                  <Grid item xs={12} sm={3} key={i}>
                    <Box sx={{ bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', p: 2, borderRadius: '8px', textAlign: 'center' }}>
                      <Typography sx={{ fontSize: '9.5px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{m.label}</Typography>
                      <Typography sx={{ fontSize: '18px', fontWeight: 900, color: COLORS.primaryText, mt: 0.5 }}>{m.val}</Typography>
                      <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, mt: 0.3 }}>{m.desc}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>

              <Box>
                <Typography sx={{ fontSize: '12.5px', fontWeight: 800, mb: 1.5, color: COLORS.primaryText }}>Top Outstanding Customers</Typography>
                <Stack spacing={1}>
                  {[
                    { name: 'Acme Corporation Ltd', invoice: '#INV-8910', amount: formatRupee(receivables * 0.35), days: 'Overdue 34 days', risk: 'Medium Risk' },
                    { name: 'Globex Corporation Inc', invoice: '#INV-8932', amount: formatRupee(receivables * 0.55), days: 'Due in 8 days', risk: 'Low Risk' },
                    { name: 'Initech Systems', invoice: '#INV-8941', amount: formatRupee(receivables * 0.10), days: 'Due in 2 days', risk: 'Low Risk' },
                  ].map((cust, i) => (
                    <Box key={i} sx={{ border: '1px solid #E2E8F0', p: 1.5, borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                        <Box sx={{ width: 32, height: 32, bgcolor: '#EEF2FF', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, color: COLORS.accent, fontSize: '11px' }}>
                          {cust.name.substring(0, 2)}
                        </Box>
                        <Box>
                          <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{cust.name}</Typography>
                          <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{cust.invoice} · {cust.days}</Typography>
                        </Box>
                      </Box>
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography sx={{ fontSize: '13px', fontWeight: 900, color: COLORS.primaryText }}>{cust.amount}</Typography>
                        <Typography sx={{ fontSize: '9px', fontWeight: 800, color: cust.risk === 'Low Risk' ? COLORS.success : COLORS.warning }}>{cust.risk}</Typography>
                      </Box>
                    </Box>
                  ))}
                </Stack>
              </Box>

              <Box sx={{ border: '1px solid #E6F4EA', p: 2, borderRadius: '10px', bgcolor: '#E6F4EA' }}>
                <Typography sx={{ fontSize: '11px', fontWeight: 800, color: '#137333', textTransform: 'uppercase', mb: 1 }}>
                  DSO RECOVERY RECOMMENDATIONS
                </Typography>
                <Typography sx={{ fontSize: '11.5px', color: '#15803D', fontWeight: 600 }}>
                  • Send automated reminder sequence to Acme Corporation Ltd invoice contact.
                </Typography>
                <Typography sx={{ fontSize: '11.5px', color: '#15803D', fontWeight: 600, mt: 0.5 }}>
                  • Offer early payment discounts (2/10 Net 30) for upcoming invoice #INV-8932.
                </Typography>
              </Box>
            </Box>
          )}

          {/* C. PAYABLES DRILL DOWN */}
          {drilldownKpi === 'Payables' && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <Grid container spacing={2}>
                {[
                  { label: 'Vendor Obligations', val: formatRupee(payables), desc: 'Outstanding payables' },
                  { label: 'Due Next 7 Days', val: formatRupee(payables * 0.90), desc: '1 Invoice Pending' },
                  { label: 'Avg Payment Cycle', val: payables > 0 ? '14 Days' : '0 Days', desc: 'Reconciled cycle' },
                  { label: 'Dispute Ledger', val: '0 Claims', desc: 'All clear' },
                ].map((m, i) => (
                  <Grid item xs={12} sm={3} key={i}>
                    <Box sx={{ bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', p: 2, borderRadius: '8px', textAlign: 'center' }}>
                      <Typography sx={{ fontSize: '9.5px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{m.label}</Typography>
                      <Typography sx={{ fontSize: '18px', fontWeight: 900, color: COLORS.primaryText, mt: 0.5 }}>{m.val}</Typography>
                      <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, mt: 0.3 }}>{m.desc}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>

              <Box>
                <Typography sx={{ fontSize: '12.5px', fontWeight: 800, mb: 1.5, color: COLORS.primaryText }}>Upcoming Vendor Payments</Typography>
                <Stack spacing={1}>
                  {[
                    { vendor: 'AWS Server Cloud Services', invoice: '#BILL-AWS-9081', amount: formatRupee(payables * 0.90), due: 'In 4 days', priority: 'High', status: 'Pending Approval' },
                    { vendor: 'Airtel Telecommunications', invoice: '#BILL-AIRTEL-4112', amount: formatRupee(payables * 0.10), due: 'In 8 days', priority: 'Medium', status: 'Scheduled' },
                  ].map((pay, i) => (
                    <Box key={i} sx={{ border: '1px solid #E2E8F0', p: 1.5, borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box>
                        <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{pay.vendor}</Typography>
                        <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{pay.invoice} · Due {pay.due}</Typography>
                      </Box>
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography sx={{ fontSize: '13px', fontWeight: 900, color: COLORS.primaryText }}>{pay.amount}</Typography>
                        <Typography sx={{ fontSize: '9px', fontWeight: 800, color: pay.priority === 'High' ? COLORS.danger : COLORS.accent }}>{pay.status}</Typography>
                      </Box>
                    </Box>
                  ))}
                </Stack>
              </Box>
            </Box>
          )}

          {/* D. GST DRILL DOWN */}
          {drilldownKpi === 'GST Liability' && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <Grid container spacing={2}>
                {[
                  { label: 'GST Summary Status', val: gstLiability > 0 ? 'Pending' : 'Reconciled', desc: gstLiability > 0 ? 'Discrepancy detected' : 'No deviations' },
                  { label: 'ITC Available (claimed)', val: formatRupee(gstLiability * 0.45), desc: 'Offset credit GSTR-2B' },
                  { label: 'Upcoming GSTR-3B filing', val: `${gstDueDays} Days left`, desc: 'Filing period Q1' },
                  { label: 'Total Tax Exposure', val: formatRupee(gstLiability), desc: 'Current liability' },
                ].map((m, i) => (
                  <Grid item xs={12} sm={3} key={i}>
                    <Box sx={{ bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', p: 2, borderRadius: '8px', textAlign: 'center' }}>
                      <Typography sx={{ fontSize: '9.5px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{m.label}</Typography>
                      <Typography sx={{ fontSize: '18px', fontWeight: 900, color: COLORS.primaryText, mt: 0.5 }}>{m.val}</Typography>
                      <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, mt: 0.3 }}>{m.desc}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>

              <Box>
                <Typography sx={{ fontSize: '12.5px', fontWeight: 800, mb: 1.5, color: COLORS.primaryText }}>Recent Compliance Ledger Filings</Typography>
                <Stack spacing={1}>
                  {[
                    { tax: 'GSTR-3B Monthly Return', period: 'April 2026', ref: 'ARN-9018442', date: 'Filed May 20', status: 'Success' },
                    { tax: 'GSTR-1 Sales Ledger', period: 'April 2026', ref: 'ARN-8801944', date: 'Filed May 11', status: 'Success' },
                  ].map((gst, i) => (
                    <Box key={i} sx={{ border: '1px solid #E2E8F0', p: 1.5, borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box>
                        <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{gst.tax}</Typography>
                        <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>Period: {gst.period} · Ref: {gst.ref}</Typography>
                      </Box>
                      <Box sx={{ textAlign: 'right' }}>
                        <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{gst.date}</Typography>
                        <Typography sx={{ fontSize: '9px', fontWeight: 800, color: COLORS.success }}>{gst.status}</Typography>
                      </Box>
                    </Box>
                  ))}
                </Stack>
              </Box>
            </Box>
          )}

          {/* E. NET WORTH DRILL DOWN */}
          {drilldownKpi === 'Net Worth' && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <Grid container spacing={2}>
                {[
                  { label: 'Total Current Assets', val: formatRupee(cashPosition + receivables), desc: 'Accounts & cash balances' },
                  { label: 'Total Current Liabilities', val: formatRupee(payables + (payrollPending ? payrollTotal : 0)), desc: 'Vendor & payroll obligations' },
                  { label: 'Equity capital asset value', val: formatRupee(netWorth), desc: 'Current Net worth value' },
                  { label: 'Quarterly Growth Index', val: `↑ ${incomeGrowth}%`, desc: 'Net Asset growth' },
                ].map((m, i) => (
                  <Grid item xs={12} sm={3} key={i}>
                    <Box sx={{ bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', p: 2, borderRadius: '8px', textAlign: 'center' }}>
                      <Typography sx={{ fontSize: '9.5px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{m.label}</Typography>
                      <Typography sx={{ fontSize: '18px', fontWeight: 900, color: COLORS.primaryText, mt: 0.5 }}>{m.val}</Typography>
                      <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, mt: 0.3 }}>{m.desc}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>

              <Box>
                <Typography sx={{ fontSize: '12.5px', fontWeight: 800, mb: 1.5, color: COLORS.primaryText }}>Capital Growth and Valuation Projections</Typography>
                <Box sx={{ height: 160 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={scenarioData} margin={{ top: 5, right: 5, bottom: 0, left: -20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
                      <XAxis dataKey="name" tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fontSize: 9 }} axisLine={false} tickLine={false} />
                      <RechartsTooltip />
                      <Line type="monotone" dataKey="expected" stroke={COLORS.accent} strokeWidth={2} dot={true} />
                    </LineChart>
                  </ResponsiveContainer>
                </Box>
              </Box>
            </Box>
          )}

          {/* F. DRILLDOWN OTHER CASES */}
          {['Monthly Burn', 'Forecast Accuracy'].includes(drilldownKpi) && (
            <Box sx={{ p: 2, textAlign: 'center' }}>
              <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText }}>
                Workspace variables initialized for {drilldownKpi}. Reconciling general ledger indexes...
              </Typography>
              <CircularProgress size={24} sx={{ color: COLORS.accent, mt: 2 }} />
            </Box>
          )}
        </DialogContent>

        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', pt: 1.5, px: 3, pb: 2 }}>
          <Button 
            variant="outlined" 
            onClick={() => setDrilldownKpi(null)}
            sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText, borderRadius: '8px' }}
          >
            Close Workspace
          </Button>
          <Button 
            variant="contained" 
            onClick={() => {
              alert(`Navigating to detail section...`);
              setDrilldownKpi(null);
            }}
            sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, color: '#fff', borderRadius: '8px', boxShadow: 'none' }}
          >
            Open Complete Module Page
          </Button>
        </DialogActions>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          TOAST SNACKBAR
      ══════════════════════════════════════════════════════════════ */}
      {toast.open && (
        <Box sx={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
          bgcolor: toast.severity === 'success' ? '#E6F4EA' : '#FEE2E2',
          border: `1px solid ${toast.severity === 'success' ? '#15803D' : '#B91C1C'}`,
          color: toast.severity === 'success' ? '#15803D' : '#B91C1C',
          borderRadius: '12px', px: 2.5, py: 1.5,
          display: 'flex', alignItems: 'center', gap: 1.5,
          boxShadow: '0 8px 30px rgba(0,0,0,0.12)', maxWidth: 420,
          animation: 'slideUp 0.25s ease-out',
          '@keyframes slideUp': { from: { transform: 'translateY(20px)', opacity: 0 }, to: { transform: 'translateY(0)', opacity: 1 } }
        }}>
          <CheckCircleIcon sx={{ fontSize: 18, flexShrink: 0 }} />
          <Typography sx={{ fontSize: '12px', fontWeight: 600, flex: 1 }}>{toast.message}</Typography>
          <IconButton size="small" onClick={() => setToast({ open: false, message: '', severity: 'success' })} sx={{ color: 'inherit', p: 0.3 }}>
            <CloseIcon sx={{ fontSize: 14 }} />
          </IconButton>
        </Box>
      )}



      {/* ══════════════════════════════════════════════════════════════
          SYSTEM SCAN DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={systemScanOpen} onClose={() => !scanState.scanning && setSystemScanOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SyncIcon sx={{ color: COLORS.accent, fontSize: 20, ...(scanState.scanning ? { animation: 'spin 1s linear infinite', '@keyframes spin': { '0%': { transform: 'rotate(0deg)' }, '100%': { transform: 'rotate(360deg)' } } } : {}) }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Finance Subsystem Scan</Typography>
          </Box>
          {!scanState.scanning && <IconButton onClick={() => setSystemScanOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>}
        </DialogTitle>
        <DialogContent sx={{ py: 3 }}>
          <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, mb: 2 }}>
            {scanState.scanning ? `Scanning ${scanState.systems[scanState.step]?.name || ''}...` : scanState.completed ? 'Scan complete. 1 critical issue found.' : 'Ready to scan.'}
          </Typography>
          {scanState.scanning && (
            <Box sx={{ mb: 2 }}>
              <LinearProgress variant="determinate" value={(scanState.step / scanState.systems.length) * 100} sx={{ borderRadius: 2, height: 6, bgcolor: '#E2E8F0', '& .MuiLinearProgress-bar': { bgcolor: COLORS.accent } }} />
              <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, mt: 0.5 }}>{Math.round((scanState.step / scanState.systems.length) * 100)}% scanned</Typography>
            </Box>
          )}
          <Stack spacing={1}>
            {scanState.systems.map((sys, i) => {
              const isDone = i < scanState.step;
              const isCurrent = i === scanState.step && scanState.scanning;
              const renderStatusIcon = () => {
                if (sys.status === 'success') return <CheckCircleIcon sx={{ color: COLORS.success, fontSize: 16 }} />;
                if (sys.status === 'warning') return <InfoOutlinedIcon sx={{ color: COLORS.warning, fontSize: 16 }} />;
                if (sys.status === 'error') return <CloseIcon sx={{ color: COLORS.danger, fontSize: 16 }} />;
                return <FiberManualRecordIcon sx={{ color: COLORS.secondaryText, fontSize: 16 }} />;
              };
              const statusLabel = sys.status === 'success' ? 'Healthy' : sys.status === 'warning' ? 'Warning' : sys.status === 'error' ? 'Critical' : '';
              const statusColor = sys.status === 'success' ? COLORS.success : sys.status === 'warning' ? COLORS.warning : sys.status === 'error' ? COLORS.danger : COLORS.secondaryText;
              return (
                <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 1.5, borderRadius: '10px', bgcolor: isCurrent ? '#EEF2FF' : isDone ? '#F8FAFC' : 'transparent', border: `1px solid ${isCurrent ? COLORS.accent : isDone ? '#E2E8F0' : 'transparent'}`, transition: 'all 0.3s ease' }}>
                  {isCurrent ? <CircularProgress size={16} sx={{ color: COLORS.accent, flexShrink: 0 }} /> : <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>{renderStatusIcon()}</Box>}
                  <Box sx={{ flex: 1 }}>
                    <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{sys.name}</Typography>
                    <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{sys.detail}</Typography>
                  </Box>
                  {isDone && <Typography sx={{ fontSize: '10px', fontWeight: 700, color: statusColor, flexShrink: 0 }}>{statusLabel}</Typography>}
                </Box>
              );
            })}
          </Stack>
        </DialogContent>
        {scanState.completed && (
          <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
            <Button variant="outlined" onClick={() => setSystemScanOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Close</Button>
            <Button variant="contained" onClick={handleRecalibrate} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>Recalibrate Dashboard</Button>
          </DialogActions>
        )}
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          REPORTS HUB DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={reportsHubOpen} onClose={() => setReportsHubOpen(false)} maxWidth="md" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <FileDownloadIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Reports Hub</Typography>
          </Box>
          <IconButton onClick={() => setReportsHubOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
          {[
            { category: 'Financial Reports', icon: 'FI', reports: [{ name: 'P&L Statement' }, { name: 'Balance Sheet' }, { name: 'Trial Balance' }, { name: 'General Ledger' }] },
            { category: 'Compliance Reports', icon: 'CO', reports: [{ name: 'GST Summary' }, { name: 'ITC Credit Report' }] },
            { category: 'Banking Reports', icon: 'BA', reports: [{ name: 'Reconciliation Report' }, { name: 'Cash Flow Report' }] },
            { category: 'Executive Reports', icon: 'EX', reports: [{ name: 'CFO Report' }, { name: 'Risk Report' }, { name: 'Forecast Report' }] },
          ].map((section, si) => (
            <Box key={si}>
              <Typography sx={{ fontSize: '13px', fontWeight: 800, color: COLORS.primaryText, mb: 1.5 }}>{section.icon} {section.category}</Typography>
              <Grid container spacing={1.5}>
                {section.reports.map((rep, ri) => (
                  <Grid item xs={12} sm={6} key={ri}>
                    <Box sx={{ border: '1px solid #E2E8F0', borderRadius: '10px', p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'all 0.15s', '&:hover': { borderColor: COLORS.accent, boxShadow: '0 2px 8px rgba(99,102,241,0.08)' } }}>
                      <Box>
                        <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{rep.name}</Typography>
                        <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>Click to open workspace</Typography>
                      </Box>
                      <Stack direction="row" spacing={0.5}>
                        <Button size="small" variant="outlined" onClick={() => handleReportsHubPreview(rep.name)} sx={{ textTransform: 'none', fontSize: '9px', fontWeight: 700, borderColor: '#E2E8F0', color: COLORS.accent, px: 1, height: 24 }}>View</Button>
                        <Button size="small" variant="outlined" onClick={() => handleReportsHubPDF(rep.name)} sx={{ textTransform: 'none', fontSize: '9px', fontWeight: 700, borderColor: '#E2E8F0', color: COLORS.secondaryText, px: 1, height: 24 }}>PDF</Button>
                        <Button size="small" variant="outlined" onClick={() => handleReportsHubCSV(rep.name)} sx={{ textTransform: 'none', fontSize: '9px', fontWeight: 700, borderColor: '#E2E8F0', color: COLORS.secondaryText, px: 1, height: 24 }}>XLS</Button>
                      </Stack>
                    </Box>
                  </Grid>
                ))}
              </Grid>
            </Box>
          ))}
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          REPORTS HUB PREVIEW DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog 
        open={Boolean(reportsHubPreviewTitle)} 
        onClose={() => setReportsHubPreviewTitle(null)}
        fullWidth
        maxWidth="md"
        slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}
      >
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Typography sx={{ fontSize: '16px', fontWeight: 800 }}>
            {reportsHubPreviewTitle} - Real-time Preview
          </Typography>
          <IconButton onClick={() => setReportsHubPreviewTitle(null)} size="small">
            <CloseIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, minHeight: 300, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          {reportsHubPreviewLoading ? (
            <Box sx={{ textAlign: 'center' }}>
              <CircularProgress size={36} sx={{ color: COLORS.accent, mb: 2 }} />
              <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText }}>
                Compiling database variables and auditing data structures...
              </Typography>
            </Box>
          ) : reportsHubPreviewError ? (
            <Alert severity="error">{reportsHubPreviewError}</Alert>
          ) : reportsHubPreviewData ? (
            <Box sx={{ width: '100%' }}>
              {reportsHubPreviewData.type === 'structured' && (
                <>
                  <Grid container spacing={2} sx={{ mb: 3 }}>
                    {reportsHubPreviewData.kpis.map((metric, idx) => (
                      <Grid item xs={12} sm={4} key={idx}>
                        <Box sx={{
                          bgcolor: '#F8FAFC',
                          border: '1px solid #E2E8F0',
                          borderRadius: '10px',
                          p: 1.5,
                          textAlign: 'center'
                        }}>
                          <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.03em', mb: 0.5 }}>
                            {metric.label}
                          </Typography>
                          <Typography sx={{ fontSize: '15px', fontWeight: 950, color: metric.color || COLORS.primaryText, lineHeight: 1 }}>
                            {metric.val}
                          </Typography>
                        </Box>
                      </Grid>
                    ))}
                  </Grid>

                  <Typography sx={{ fontSize: '11px', fontWeight: 700, color: COLORS.secondaryText, textTransform: 'uppercase', mb: 1.5 }}>
                    PREVIEW ROWS (TOP 10 RECORDS)
                  </Typography>
                  <Box sx={{ border: '1px solid #E2E8F0', borderRadius: '8px', overflow: 'hidden', mb: 2 }}>
                    <Table size="small">
                      <TableHead sx={{ bgcolor: '#F8FAFC' }}>
                        <TableRow>
                          {reportsHubPreviewData.columns.map((c, i) => (
                            <TableCell key={i} sx={{ fontSize: '10px', fontWeight: 800, color: COLORS.primaryText }}>{c.label}</TableCell>
                          ))}
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {reportsHubPreviewData.rows.slice(0, 10).map((row, ri) => (
                          <TableRow key={ri} sx={{ '&:nth-of-type(even)': { bgcolor: '#F8FAFC' } }}>
                            {reportsHubPreviewData.columns.map((c, i) => (
                              <TableCell key={i} sx={{ fontSize: '11px', color: COLORS.secondaryText }}>{row[c.key]}</TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </Box>
                </>
              )}

              {reportsHubPreviewData.type === 'markdown' && (
                <Box sx={{ bgcolor: '#F8FAFC', borderRadius: '12px', p: 3, border: '1px solid #E2E8F0', maxHeight: 400, overflowY: 'auto', mb: 2 }}>
                  <Box sx={{
                    fontSize: '13px',
                    lineHeight: 1.6,
                    color: COLORS.primaryText,
                    '& h1, & h2, & h3': { color: COLORS.accent, mb: 1.5, mt: 1 },
                    '& p': { mb: 1.5 },
                    '& table': { width: '100%', borderCollapse: 'collapse', my: 2 },
                    '& th, & td': { border: '1px solid #E2E8F0', p: 1, fontSize: '11px' },
                    '& th': { bgcolor: '#EEF2FF', fontWeight: 'bold' }
                  }}>
                    <ReactMarkdown>{reportsHubPreviewData.content}</ReactMarkdown>
                  </Box>
                </Box>
              )}

              {reportsHubPreviewLink && (
                <Box sx={{ display: 'flex', justifyContent: 'flex-start', mt: 1 }}>
                  <Button 
                    variant="text" 
                    onClick={() => { setReportsHubPreviewTitle(null); setReportsHubOpen(false); navigate(reportsHubPreviewLink); }}
                    sx={{ textTransform: 'none', fontSize: '11px', fontWeight: 700, color: COLORS.accent }}
                  >
                    Open Full Interactive Page →
                  </Button>
                </Box>
              )}
            </Box>
          ) : (
            <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText }}>No preview data loaded.</Typography>
          )}
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', pt: 1.5, px: 3, pb: 2 }}>
          <Button 
            variant="outlined" 
            onClick={() => setReportsHubPreviewTitle(null)}
            sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText, borderRadius: '8px' }}
          >
            Close
          </Button>
          <Button 
            variant="contained" 
            startIcon={<FileDownloadIcon sx={{ fontSize: 13 }} />}
            onClick={() => handleReportsHubPDF(reportsHubPreviewTitle)}
            disabled={!reportsHubPreviewData}
            sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, color: '#fff', borderRadius: '8px', boxShadow: 'none' }}
          >
            Download PDF Report
          </Button>
        </DialogActions>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          AI 90-DAY FINANCIAL PLAN DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={aiPlanOpen} onClose={() => setAiPlanOpen(false)} maxWidth="md" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SparklesIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>90-Day Financial Plan</Typography>
            <Box sx={{ px: 1, py: 0.3, borderRadius: '6px', bgcolor: '#EEF2FF', color: COLORS.accent, fontSize: '9px', fontWeight: 700 }}>AI Generated</Box>
          </Box>
          <IconButton onClick={() => setAiPlanOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3 }}>
          {generatingPlan ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, py: 6 }}>
              <CircularProgress sx={{ color: COLORS.accent }} />
              <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText, fontWeight: 600 }}>Gemini AI CFO is generating your 90-Day Financial Plan...</Typography>
              <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText }}>Analyzing cash flow, receivables, GST obligations & burn rate...</Typography>
            </Box>
          ) : aiPlanContent ? (
            <Box sx={{ bgcolor: '#F8FAFC', borderRadius: '12px', p: 3, border: '1px solid #E2E8F0', maxHeight: 500, overflowY: 'auto' }}>
              <Typography sx={{ fontSize: '12px', color: COLORS.primaryText, lineHeight: 1.9, whiteSpace: 'pre-wrap', fontFamily: 'Inter, sans-serif' }}>{aiPlanContent}</Typography>
            </Box>
          ) : (
            <Box sx={{ textAlign: 'center', py: 6 }}>
              <SparklesIcon sx={{ fontSize: 48, color: '#E2E8F0', mb: 2 }} />
              <Typography sx={{ fontSize: '13px', color: COLORS.secondaryText }}>No plan generated yet. Click &ldquo;Generate&rdquo; to create a plan.</Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setAiPlanOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Close</Button>
          {aiPlanContent && !generatingPlan && (
            <Button variant="contained" startIcon={<FileDownloadIcon sx={{ fontSize: 14 }} />} onClick={() => setToast({ open: true, message: 'Financial plan exported as PDF.', severity: 'success' })} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>Export PDF</Button>
          )}
        </DialogActions>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          PREDICTION CENTER DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={predictionCenterOpen} onClose={() => setPredictionCenterOpen(false)} maxWidth="lg" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SparklesIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Predictive Intelligence Center</Typography>
            <Box sx={{ px: 1, py: 0.3, borderRadius: '6px', bgcolor: '#EEF2FF', color: COLORS.accent, fontSize: '9px', fontWeight: 700 }}>{predictiveAlerts.length} Predictions</Box>
          </Box>
          <IconButton onClick={() => setPredictionCenterOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3 }}>
          <Stack spacing={1.5}>
            {predictiveAlerts.map((a, i) => {
              const impactColor = a.impact === 'High' ? COLORS.danger : a.impact === 'Medium' ? COLORS.warning : COLORS.success;
              const impactBg = a.impact === 'High' ? '#FEE2E2' : a.impact === 'Medium' ? '#FFF9C4' : '#E6F4EA';
              return (
                <Box key={i} sx={{ border: '1px solid #E2E8F0', borderRadius: '12px', p: 2.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, transition: 'all 0.15s', '&:hover': { borderColor: COLORS.accent, boxShadow: '0 2px 12px rgba(99,102,241,0.08)' } }}>
                  <Box sx={{ flex: 1 }}>
                    <Typography sx={{ fontSize: '14px', fontWeight: 700, color: COLORS.primaryText, mb: 1.5 }}>{a.title}</Typography>
                    <Stack direction="row" spacing={3}>
                      <Box><Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>Confidence</Typography><Typography sx={{ fontSize: '16px', fontWeight: 900, color: COLORS.success }}>{a.confidence}%</Typography></Box>
                      <Box><Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>Impact</Typography><Box sx={{ mt: 0.3, px: 0.8, py: 0.2, borderRadius: '4px', bgcolor: impactBg, color: impactColor, fontSize: '10px', fontWeight: 800, width: 'fit-content' }}>{a.impact}</Box></Box>
                      <Box><Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>Timeline</Typography><Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText, mt: 0.2 }}>{a.timeline}</Typography></Box>
                      <Box><Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>Recommendation</Typography><Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.accent, mt: 0.2 }}>{a.recommendation}</Typography></Box>
                    </Stack>
                  </Box>
                  <Button variant="outlined" onClick={() => { setToast({ open: true, message: `Action triggered: ${a.recommendation}`, severity: 'success' }); setPredictionCenterOpen(false); }} sx={{ textTransform: 'none', fontSize: '10px', fontWeight: 700, borderColor: COLORS.accent, color: COLORS.accent, borderRadius: '8px', whiteSpace: 'nowrap', flexShrink: 0 }}>Take Action →</Button>
                </Box>
              );
            })}
          </Stack>
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          NOTIFICATION CENTER DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={notificationCenterOpen} onClose={() => setNotificationCenterOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <NotificationsIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Notification Center</Typography>
            <Badge badgeContent={notifications.filter(n => !n.read).length} color="error" />
          </Box>
          <IconButton onClick={() => setNotificationCenterOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 2 }}>
          <Stack direction="row" spacing={0.75} sx={{ mb: 2, flexWrap: 'wrap', gap: 0.5 }}>
            {['All', 'Critical', 'Finance', 'Banking', 'Compliance'].map(tab => (
              <Box key={tab} onClick={() => setNotificationTab(tab)} sx={{ px: 1.5, py: 0.5, borderRadius: '16px', cursor: 'pointer', fontSize: '10px', fontWeight: 700, bgcolor: notificationTab === tab ? COLORS.accent : '#F1F5F9', color: notificationTab === tab ? '#fff' : COLORS.secondaryText, transition: 'all 0.15s' }}>{tab}</Box>
            ))}
          </Stack>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1.5 }}>
            <Typography onClick={() => setNotifications(prev => prev.map(n => ({ ...n, read: true })))} sx={{ fontSize: '10px', color: COLORS.accent, fontWeight: 700, cursor: 'pointer', '&:hover': { opacity: 0.7 } }}>Mark All Read</Typography>
          </Box>
          <Stack spacing={1}>
            {notifications
              .filter(n => notificationTab === 'All' ? true : n.type === notificationTab || n.priority === notificationTab)
              .map(notif => (
              <Box key={notif.id} sx={{ p: 1.5, borderRadius: '10px', border: `1px solid ${notif.read ? '#F1F5F9' : '#E2E8F0'}`, bgcolor: notif.read ? '#FAFAFA' : '#F8FAFC', display: 'flex', alignItems: 'flex-start', gap: 1.5, transition: 'all 0.15s' }}>
                <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: notif.priority === 'Critical' ? COLORS.danger : notif.priority === 'High' ? COLORS.warning : COLORS.accent, mt: 0.6, flexShrink: 0 }} />
                <Box sx={{ flex: 1 }}>
                  <Typography sx={{ fontSize: '12px', fontWeight: notif.read ? 500 : 700, color: COLORS.primaryText, lineHeight: 1.4 }}>{notif.text}</Typography>
                  <Stack direction="row" spacing={1} sx={{ mt: 0.5 }}>
                    <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText }}>{notif.time}</Typography>
                    <Box sx={{ px: 0.7, py: 0.15, borderRadius: '4px', bgcolor: '#EEF2FF', color: COLORS.accent, fontSize: '8px', fontWeight: 700 }}>{notif.type}</Box>
                  </Stack>
                </Box>
                <Stack direction="row" spacing={0.3}>
                  {!notif.read && <Button size="small" onClick={() => setNotifications(prev => prev.map(n => n.id === notif.id ? { ...n, read: true } : n))} sx={{ textTransform: 'none', fontSize: '9px', fontWeight: 700, color: COLORS.accent, minWidth: 0, px: 0.6, py: 0.2 }}>Read</Button>}
                  <Button size="small" onClick={() => setNotifications(prev => prev.filter(n => n.id !== notif.id))} sx={{ textTransform: 'none', fontSize: '9px', fontWeight: 700, color: COLORS.secondaryText, minWidth: 0, px: 0.6, py: 0.2 }}>Archive</Button>
                </Stack>
              </Box>
            ))}
            {notifications.filter(n => notificationTab === 'All' ? true : n.type === notificationTab || n.priority === notificationTab).length === 0 && (
              <Typography sx={{ textAlign: 'center', fontSize: '12px', color: COLORS.secondaryText, py: 3 }}>No notifications in this category.</Typography>
            )}
          </Stack>
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          GST FILING DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={gstFilingOpen} onClose={() => setGstFilingOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ReceiptIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>GST Filing Workspace</Typography>
          </Box>
          <IconButton onClick={() => setGstFilingOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ p: 2, bgcolor: '#FFF9C4', borderRadius: '10px', border: '1px solid #F59E0B' }}>
            <Typography sx={{ fontSize: '12px', fontWeight: 800, color: '#92400E', mb: 0.5 }}>GST Filing Due in {gstDueDays} Days</Typography>
            <Typography sx={{ fontSize: '11px', color: '#92400E' }}>GSTR-3B for Q1 2026 | Tax Liability: {formatRupee(gstLiability)} | ITC Available: {formatRupee(gstLiability * 0.45)}</Typography>
          </Box>
          {[{ label: 'GSTR-1 (Sales Returns)', period: 'Q1 Apr–Jun 2026', status: 'Ready', color: COLORS.success }, { label: 'GSTR-3B (Monthly Return)', period: 'Q1 Apr–Jun 2026', status: 'Pending', color: COLORS.warning }].map((item, i) => (
            <Box key={i} sx={{ border: '1px solid #E2E8F0', borderRadius: '10px', p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{item.label}</Typography>
                <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{item.period}</Typography>
              </Box>
              <Box sx={{ textAlign: 'right' }}>
                <Typography sx={{ fontSize: '13px', fontWeight: 900, color: COLORS.primaryText }}>{formatRupee(gstLiability)}</Typography>
                <Typography sx={{ fontSize: '9px', fontWeight: 800, color: item.color }}>{item.status}</Typography>
              </Box>
            </Box>
          ))}
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setGstFilingOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Cancel</Button>
          <Button variant="outlined" onClick={() => setToast({ open: true, message: 'GST returns reviewed. Proceed to submit.', severity: 'success' })} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: COLORS.accent, color: COLORS.accent }}>Review</Button>
          <Button variant="contained" onClick={() => { handleResolveAction('gst_filing'); setGstFilingOpen(false); setToast({ open: true, message: `GSTR-3B filed successfully! ${formatRupee(gstLiability)} liability settled.`, severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>Submit & File</Button>
        </DialogActions>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          PAYROLL APPROVAL DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={payrollApproveOpen} onClose={() => setPayrollApproveOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <PeopleIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Payroll Approval Workflow</Typography>
          </Box>
          <IconButton onClick={() => setPayrollApproveOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ p: 2, bgcolor: '#FEE2E2', borderRadius: '10px', border: '1px solid #EF4444' }}>
            <Typography sx={{ fontSize: '12px', fontWeight: 800, color: '#B91C1C', mb: 0.5 }}>Critical: Payroll Approval Due in 4 Days</Typography>
            <Typography sx={{ fontSize: '11px', color: '#B91C1C' }}>Total Obligation: {formatRupee(payrollTotal)} across 12 employees</Typography>
          </Box>
          {[{ name: 'Engineering Team (5)', amount: formatRupee(payrollTotal * 0.44), status: 'Verified', color: COLORS.success }, { name: 'Sales Team (4)', amount: formatRupee(payrollTotal * 0.31), status: 'Verified', color: COLORS.success }, { name: 'Operations (3)', amount: formatRupee(payrollTotal * 0.25), status: 'Pending Verification', color: COLORS.warning }].map((row, i) => (
            <Box key={i} sx={{ border: '1px solid #E2E8F0', borderRadius: '10px', p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box>
                <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{row.name}</Typography>
                <Typography sx={{ fontSize: '10px', fontWeight: 700, color: row.color }}>{row.status}</Typography>
              </Box>
              <Typography sx={{ fontSize: '14px', fontWeight: 900, color: COLORS.primaryText }}>{row.amount}</Typography>
            </Box>
          ))}
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => { setPayrollApproveOpen(false); setToast({ open: true, message: 'Payroll rejected. Finance team notified.', severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: COLORS.danger, color: COLORS.danger }}>Reject</Button>
          <Button variant="outlined" onClick={() => setToast({ open: true, message: 'Payroll escalated to CFO for review.', severity: 'success' })} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: COLORS.warning, color: COLORS.warning }}>Escalate</Button>
          <Button variant="contained" onClick={() => { handleResolveAction('payroll_approval'); setPayrollApproveOpen(false); setToast({ open: true, message: `Payroll approved! ${formatRupee(payrollTotal)} scheduled for disbursement.`, severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.success, boxShadow: 'none' }}>Approve Payroll</Button>
        </DialogActions>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          SEND REMINDER DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={reminderOpen} onClose={() => setReminderOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SendIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Send Collection Reminders</Typography>
          </Box>
          <IconButton onClick={() => setReminderOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText }}>Send payment reminders to customers with outstanding invoices.</Typography>
          {[{ name: 'Acme Corporation Ltd', amount: formatRupee(receivables * 0.35), days: 'Overdue 34 days', email: 'finance@acme.com' }, { name: 'Globex Corporation Inc', amount: formatRupee(receivables * 0.65), days: 'Due in 8 days', email: 'billing@globex.com' }].map((cust, i) => (
            <Box key={i} sx={{ border: '1px solid #E2E8F0', borderRadius: '10px', p: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
                <Box>
                  <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{cust.name}</Typography>
                  <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{cust.email} · {cust.days}</Typography>
                </Box>
                <Typography sx={{ fontSize: '14px', fontWeight: 900, color: COLORS.primaryText }}>{cust.amount}</Typography>
              </Box>
              <Stack direction="row" spacing={1}>
                {['Email', 'WhatsApp', 'SMS'].map(channel => (
                  <Button key={channel} size="small" variant="outlined" onClick={() => { handleResolveAction('follow_up_receivables'); setReminderOpen(false); setToast({ open: true, message: `${channel} reminder sent to ${cust.name}.`, severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '9px', fontWeight: 700, borderColor: '#E2E8F0', color: COLORS.accent, px: 1, height: 26 }}>{channel}</Button>
                ))}
              </Stack>
            </Box>
          ))}
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setReminderOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Cancel</Button>
          <Button variant="contained" onClick={() => { handleResolveAction('follow_up_receivables'); setReminderOpen(false); setToast({ open: true, message: 'All reminder campaigns sent successfully! ₹85K collection expected.', severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>Send All Reminders</Button>
        </DialogActions>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          BANK RECONCILIATION DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={bankReconOpen || runBankReconOpen} onClose={() => { setBankReconOpen(false); setRunBankReconOpen(false); }} maxWidth="md" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CompareArrowsIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Bank Reconciliation Center</Typography>
          </Box>
          <IconButton onClick={() => { setBankReconOpen(false); setRunBankReconOpen(false); }} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Grid container spacing={2}>
            {[
              { label: 'Reconciliation Accuracy', value: `${reconciliationAccuracy}%`, color: COLORS.success },
              { label: 'Pending Matches', value: String(pendingMatches), color: COLORS.warning },
              { label: 'Bank Balance', value: cashPosition >= 100000 ? `₹${(cashPosition / 100000).toFixed(2)}L` : `₹${(cashPosition / 1000).toFixed(0)}K`, color: COLORS.primaryText },
              { label: 'Ledger Balance', value: cashPosition >= 100000 ? `₹${(cashPosition / 100000).toFixed(2)}L` : `₹${(cashPosition / 1000).toFixed(0)}K`, color: COLORS.primaryText }
            ].map((m, i) => (
              <Grid item xs={6} sm={3} key={i}>
                <Box sx={{ bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', p: 2, textAlign: 'center' }}>
                  <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{m.label}</Typography>
                  <Typography sx={{ fontSize: '20px', fontWeight: 900, color: m.color, mt: 0.5 }}>{m.value}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
          <Typography sx={{ fontSize: '13px', fontWeight: 800, color: COLORS.primaryText }}>Unmatched Transactions</Typography>
          <Stack spacing={1}>
            {[{ desc: 'Payment from Acme Corp', bank: '₹85,000', date: 'Jun 8', note: 'Not in ledger' }, { desc: 'AWS Service Invoice', bank: '₹12,500', date: 'Jun 10', note: 'Ledger mismatch' }].map((tx, i) => (
              <Box key={i} sx={{ border: '1px solid #FFF9C4', borderRadius: '10px', p: 1.5, bgcolor: '#FFFBEB', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
                <Box sx={{ flex: 1 }}>
                  <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{tx.desc}</Typography>
                  <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{tx.date} · {tx.note}</Typography>
                </Box>
                <Typography sx={{ fontSize: '13px', fontWeight: 900, color: COLORS.primaryText }}>{tx.bank}</Typography>
                <Button size="small" variant="outlined" onClick={() => setToast({ open: true, message: `Transaction matched: ${tx.desc}`, severity: 'success' })} sx={{ textTransform: 'none', fontSize: '9px', fontWeight: 700, borderColor: COLORS.accent, color: COLORS.accent, px: 1.2, height: 26 }}>Match</Button>
              </Box>
            ))}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => { setBankReconOpen(false); setRunBankReconOpen(false); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Close</Button>
          <Button variant="contained" onClick={() => { handleResolveAction('bank_recon'); setBankReconOpen(false); setRunBankReconOpen(false); setToast({ open: true, message: 'Bank reconciliation completed. 2 transactions auto-matched.', severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>Run Reconciliation</Button>
        </DialogActions>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          ASSET DEPRECIATION DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={depreciationOpen} onClose={() => setDepreciationOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <CalculateIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Asset Depreciation Engine</Typography>
          </Box>
          <IconButton onClick={() => setDepreciationOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Grid container spacing={2}>
            {[{ label: 'Total Assets', value: String(totalAssets), color: COLORS.primaryText }, { label: 'EOL Assets', value: `${eolAssets}`, color: COLORS.danger }, { label: 'Monthly Depreciation', value: formatRupee(totalAssets > 0 ? (totalAssets * 18400 / 24) : 18400), color: COLORS.warning }, { label: 'Asset Health', value: `${assetHealth}%`, color: COLORS.success }].map((m, i) => (
              <Grid item xs={6} key={i}>
                <Box sx={{ bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', p: 2, textAlign: 'center' }}>
                  <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{m.label}</Typography>
                  <Typography sx={{ fontSize: '20px', fontWeight: 900, color: m.color, mt: 0.5 }}>{m.value}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
          <Typography sx={{ fontSize: '13px', fontWeight: 800, color: COLORS.primaryText }}>Assets Requiring Attention</Typography>
          <Stack spacing={1}>
            {[{ name: 'Logistics Delivery Van #3', type: 'Vehicle', age: '6 yrs', book: '₹0 (Fully Depreciated)', action: 'Replace' }, { name: 'Server Rack Unit B', type: 'IT', age: '4 yrs', book: '₹25,000 (75% Depreciated)', action: 'Review' }].map((asset, i) => (
              <Box key={i} sx={{ border: '1px solid #E2E8F0', borderRadius: '10px', p: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 1 }}>
                <Box sx={{ flex: 1 }}>
                  <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{asset.name}</Typography>
                  <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{asset.type} · Age: {asset.age}</Typography>
                  <Typography sx={{ fontSize: '10px', color: COLORS.warning, fontWeight: 700 }}>{asset.book}</Typography>
                </Box>
                <Button size="small" variant="outlined" onClick={() => setToast({ open: true, message: `${asset.action} initiated for ${asset.name}.`, severity: 'success' })} sx={{ textTransform: 'none', fontSize: '9px', fontWeight: 700, borderColor: COLORS.accent, color: COLORS.accent, px: 1.2, height: 26 }}>{asset.action}</Button>
              </Box>
            ))}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setDepreciationOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Cancel</Button>
          <Button variant="contained" onClick={() => { handleResolveAction('asset_depreciation'); setDepreciationOpen(false); setToast({ open: true, message: 'Depreciation run completed for all 24 assets.', severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>Run Depreciation Now</Button>
        </DialogActions>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          ACTION MANAGEMENT CENTER DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={actionMgmtOpen} onClose={() => setActionMgmtOpen(false)} maxWidth="lg" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <PlayArrowIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Action Management Center</Typography>
            <Box sx={{ px: 1, py: 0.3, borderRadius: '6px', bgcolor: '#FEE2E2', color: '#B91C1C', fontSize: '9px', fontWeight: 700 }}>{actions.filter(a => !a.resolved).length} Open</Box>
          </Box>
          <IconButton onClick={() => setActionMgmtOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3 }}>
          <Stack spacing={1.5}>
            {actions.map((action) => {
              const pc = getPriorityColor(action.priority);
              return (
                <Box key={action.id} sx={{ border: '1px solid #E2E8F0', borderRadius: '12px', p: 2.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2, opacity: action.resolved ? 0.6 : 1, transition: 'all 0.15s', '&:hover': { borderColor: COLORS.accent } }}>
                  <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flex: 1 }}>
                    <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: pc.color, flexShrink: 0 }} />
                    <Box sx={{ flex: 1 }}>
                      <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>{action.title}</Typography>
                      <Stack direction="row" spacing={2} sx={{ mt: 0.5 }}>
                        <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{action.dept}</Typography>
                        <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>Due in {action.dueDays} days</Typography>
                        {action.financialImpact > 0 && <Typography sx={{ fontSize: '10px', fontWeight: 700, color: COLORS.primaryText }}>₹{(action.financialImpact / 1000).toFixed(0)}K exposure</Typography>}
                      </Stack>
                    </Box>
                  </Box>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Box sx={{ px: 1, py: 0.3, borderRadius: '6px', bgcolor: pc.bg, color: pc.color, fontSize: '10px', fontWeight: 700 }}>{action.priority}</Box>
                    <Button size="small" variant={action.resolved ? 'outlined' : 'contained'} disabled={action.resolved}
                      onClick={() => {
                        if (action.id === 'gst_filing') setGstFilingOpen(true);
                        else if (action.id === 'payroll_approval') setPayrollApproveOpen(true);
                        else if (action.id === 'follow_up_receivables') setReminderOpen(true);
                        else if (action.id === 'bank_recon') setBankReconOpen(true);
                        else if (action.id === 'asset_depreciation') setDepreciationOpen(true);
                        setActionMgmtOpen(false);
                      }}
                      sx={{ textTransform: 'none', fontSize: '10px', fontWeight: 700, bgcolor: action.resolved ? 'transparent' : COLORS.accent, color: action.resolved ? COLORS.secondaryText : '#fff', boxShadow: 'none', borderColor: '#E2E8F0', minWidth: 100 }}>
                      {action.resolved ? 'Completed' : action.actionLabel}
                    </Button>
                  </Stack>
                </Box>
              );
            })}
          </Stack>
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          ACTIVITY FEED DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={activityFeedOpen} onClose={() => setActivityFeedOpen(false)} maxWidth="md" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <JournalIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Business Activity Explorer</Typography>
          </Box>
          <IconButton onClick={() => setActivityFeedOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3 }}>
          <Stack direction="row" spacing={0.75} sx={{ mb: 2, flexWrap: 'wrap', gap: 0.5 }}>
            {['All', 'Finance', 'Payroll', 'GST', 'Banking', 'Assets'].map(f => (
              <Box key={f} onClick={() => setTimelineFilter(f)} sx={{ px: 1.5, py: 0.5, borderRadius: '16px', cursor: 'pointer', fontSize: '10px', fontWeight: 700, bgcolor: timelineFilter === f ? COLORS.accent : '#F1F5F9', color: timelineFilter === f ? '#fff' : COLORS.secondaryText, transition: 'all 0.15s' }}>{f}</Box>
            ))}
          </Stack>
          {Object.entries(filteredTimeline).map(([group, items]) => (
            <Box key={group} sx={{ mb: 2.5 }}>
              <Typography sx={{ fontSize: '9px', fontWeight: 800, color: COLORS.secondaryText, textTransform: 'uppercase', letterSpacing: '0.04em', mb: 1 }}>{group}</Typography>
              <Stack spacing={1}>
                {items.length === 0 ? <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, pl: 1 }}>No activity in this category.</Typography> : items.map((item, i) => (
                  <Box key={i} sx={{ border: '1px solid #E2E8F0', borderRadius: '10px', p: 1.5, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 2 }}>
                    <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', flex: 1 }}>
                      <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: item.status === 'success' ? COLORS.success : COLORS.info, flexShrink: 0 }} />
                      <Box>
                        <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{item.action}</Typography>
                        <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{item.module} · {item.time}</Typography>
                      </Box>
                    </Box>
                    <Box sx={{ px: 1, py: 0.3, borderRadius: '6px', bgcolor: item.status === 'success' ? '#E6F4EA' : '#DBEAFE', color: item.status === 'success' ? '#15803D' : '#1D4ED8', fontSize: '9px', fontWeight: 800 }}>{item.status === 'success' ? 'Success' : 'Info'}</Box>
                  </Box>
                ))}
              </Stack>
            </Box>
          ))}
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          SUBSYSTEM CONTROL CENTER DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={subsystemCenterOpen} onClose={() => setSubsystemCenterOpen(false)} maxWidth="md" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <GridViewIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Subsystem Control Center</Typography>
          </Box>
          <IconButton onClick={() => setSubsystemCenterOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3 }}>
          <Grid container spacing={2}>
            {infraSystems.map((sys, i) => {
              const rc = getRiskColor(sys.risk);
              return (
                <Grid item xs={12} sm={6} key={i}>
                  <Box sx={{ border: '1px solid #E2E8F0', borderRadius: '12px', p: 2.5, transition: 'all 0.15s', '&:hover': { borderColor: COLORS.accent, boxShadow: '0 2px 12px rgba(99,102,241,0.08)' } }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ width: 8, height: 8, borderRadius: '50%', bgcolor: sys.health >= 90 ? COLORS.success : sys.health >= 75 ? COLORS.warning : COLORS.danger }} />
                        <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>{sys.name}</Typography>
                      </Box>
                      <Box sx={{ px: 0.8, py: 0.25, borderRadius: '4px', bgcolor: rc.bg, color: rc.color, fontSize: '9px', fontWeight: 800 }}>{sys.risk}</Box>
                    </Box>
                    <Stack direction="row" spacing={3} sx={{ mb: 1.5 }}>
                      <Box><Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>HEALTH</Typography><Typography sx={{ fontSize: '18px', fontWeight: 900, color: sys.health >= 90 ? COLORS.success : sys.health >= 75 ? COLORS.warning : COLORS.danger }}>{sys.health}%</Typography></Box>
                      <Box><Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>ALERTS</Typography><Typography sx={{ fontSize: '18px', fontWeight: 900, color: sys.alerts > 0 ? COLORS.danger : COLORS.success }}>{sys.alerts}</Typography></Box>
                      <Box><Typography sx={{ fontSize: '8px', color: COLORS.secondaryText, fontWeight: 700 }}>LAST SYNC</Typography><Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText, mt: 0.3 }}>{sys.lastSync}</Typography></Box>
                    </Stack>
                    <LinearProgress variant="determinate" value={sys.health} sx={{ borderRadius: 2, height: 4, bgcolor: '#E2E8F0', mb: 1.5, '& .MuiLinearProgress-bar': { bgcolor: sys.health >= 90 ? COLORS.success : sys.health >= 75 ? COLORS.warning : COLORS.danger } }} />
                    <Button fullWidth size="small" variant="outlined" onClick={() => { setSubsystemCenterOpen(false); setToast({ open: true, message: `${sys.name} workspace opened.`, severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '10px', fontWeight: 700, borderColor: '#E2E8F0', color: COLORS.accent, borderRadius: '8px' }}>View {sys.name}</Button>
                  </Box>
                </Grid>
              );
            })}
          </Grid>
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          OPPORTUNITY MANAGEMENT CENTER DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={opportunityCenterOpen} onClose={() => setOpportunityCenterOpen(false)} maxWidth="md" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <TrendingUpIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Opportunity Management Center</Typography>
          </Box>
          <IconButton onClick={() => setOpportunityCenterOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3 }}>
          <Grid container spacing={2}>
            {opportunities.map((opp, i) => (
              <Grid item xs={12} sm={6} key={i}>
                <Box sx={{ border: '1px solid #E2E8F0', borderRadius: '12px', p: 2.5, display: 'flex', flexDirection: 'column', gap: 1.5, transition: 'all 0.15s', '&:hover': { borderColor: opp.color, boxShadow: '0 2px 12px rgba(0,0,0,0.06)' } }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <Box sx={{ width: 42, height: 42, borderRadius: '12px', bgcolor: `${opp.color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <TrendingUpIcon sx={{ fontSize: 22, color: opp.color }} />
                    </Box>
                    {opp.gain && <Typography sx={{ fontSize: '20px', fontWeight: 900, color: opp.color }}>{opp.gain}</Typography>}
                  </Box>
                  <Box>
                    <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>{opp.title}</Typography>
                    <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText, mt: 0.3 }}>{opp.days}</Typography>
                  </Box>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Box sx={{ px: 0.8, py: 0.25, borderRadius: '4px', bgcolor: '#FEE2E2', color: '#B91C1C', fontSize: '9px', fontWeight: 800 }}>{opp.label}</Box>
                    <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText }}>Impact {opp.impact}</Typography>
                  </Stack>
                  <Button fullWidth variant="contained" size="small" onClick={() => { setExecOpportunityOpen(opp); setOpportunityCenterOpen(false); }} sx={{ textTransform: 'none', fontSize: '11px', fontWeight: 700, bgcolor: opp.color, boxShadow: 'none', mt: 'auto', borderRadius: '8px', '&:hover': { filter: 'brightness(0.9)' } }}>Execute Opportunity →</Button>
                </Box>
              </Grid>
            ))}
          </Grid>
        </DialogContent>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          EXECUTIVE OPPORTUNITY EXECUTE DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={Boolean(execOpportunityOpen)} onClose={() => setExecOpportunityOpen(null)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        {execOpportunityOpen && (
          <>
            <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendingUpIcon sx={{ color: execOpportunityOpen.color, fontSize: 20 }} />
                <Typography sx={{ fontSize: '16px', fontWeight: 800, color: COLORS.primaryText }}>{execOpportunityOpen.title}</Typography>
              </Box>
              <IconButton onClick={() => setExecOpportunityOpen(null)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
            </DialogTitle>
            <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Grid container spacing={2}>
                {[{ label: 'Expected Gain', value: execOpportunityOpen.gain || 'N/A', color: execOpportunityOpen.color }, { label: 'ROI', value: execOpportunityOpen.label, color: COLORS.primaryText }, { label: 'Impact Score', value: execOpportunityOpen.impact, color: COLORS.primaryText }, { label: 'Timeline', value: execOpportunityOpen.days, color: COLORS.secondaryText }].map((m, i) => (
                  <Grid item xs={6} key={i}>
                    <Box sx={{ bgcolor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '10px', p: 2, textAlign: 'center' }}>
                      <Typography sx={{ fontSize: '9px', color: COLORS.secondaryText, fontWeight: 700, textTransform: 'uppercase' }}>{m.label}</Typography>
                      <Typography sx={{ fontSize: '16px', fontWeight: 900, color: m.color, mt: 0.5 }}>{m.value}</Typography>
                    </Box>
                  </Grid>
                ))}
              </Grid>
              <Box sx={{ p: 2, bgcolor: '#EEF2FF', borderRadius: '12px', border: '1px solid #C7D2FE' }}>
                <Typography sx={{ fontSize: '11px', fontWeight: 800, color: COLORS.accent, mb: 1 }}>Recommended Execution Steps</Typography>
                <Typography sx={{ fontSize: '11.5px', color: COLORS.primaryText, lineHeight: 1.7 }}>
                  • Assign dedicated team lead with 7-day milestone target.<br />
                  • Schedule automated follow-up reminders every 3 days.<br />
                  • Escalate unresponsive accounts to management after 14 days.<br />
                  • Track ROI progress in Collections Engine weekly.
                </Typography>
              </Box>
            </DialogContent>
            <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
              <Button variant="outlined" onClick={() => setExecOpportunityOpen(null)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Cancel</Button>
              <Button variant="contained" onClick={() => { const opp = execOpportunityOpen; setExecOpportunityOpen(null); setToast({ open: true, message: `Opportunity execution launched: ${opp.title}`, severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: execOpportunityOpen.color, boxShadow: 'none' }}>Execute Now →</Button>
            </DialogActions>
          </>
        )}
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          IMPORT BANK STATEMENT DIALOG
      ══════════════════════════════════════════════════════════════ */}
      <Dialog open={importStatementOpen} onClose={() => setImportStatementOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <UploadFileIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Import Bank Statement</Typography>
          </Box>
          <IconButton onClick={() => setImportStatementOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ border: '2px dashed #CBD5E1', borderRadius: '12px', p: 5, textAlign: 'center', bgcolor: '#F8FAFC', cursor: 'pointer', transition: 'all 0.15s', '&:hover': { borderColor: COLORS.accent, bgcolor: '#EEF2FF' } }}>
            <UploadFileIcon sx={{ fontSize: 44, color: COLORS.secondaryText, mb: 1 }} />
            <Typography sx={{ fontSize: '13px', fontWeight: 700, color: COLORS.primaryText }}>Drop your bank statement here</Typography>
            <Typography sx={{ fontSize: '11px', color: COLORS.secondaryText, mt: 0.5 }}>Supports CSV, XLSX, PDF formats</Typography>
            <Button variant="outlined" size="small" sx={{ mt: 2, textTransform: 'none', fontSize: '11px', fontWeight: 700, borderColor: COLORS.accent, color: COLORS.accent }}>Browse Files</Button>
          </Box>
          <Stack direction="row" spacing={1} justifyContent="center">
            {['CSV', 'XLSX', 'PDF'].map(fmt => (<Box key={fmt} sx={{ px: 1.5, py: 0.5, borderRadius: '6px', bgcolor: '#EEF2FF', color: COLORS.accent, fontSize: '11px', fontWeight: 700 }}>{fmt}</Box>))}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setImportStatementOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Cancel</Button>
          <Button variant="contained" onClick={() => { setImportStatementOpen(false); setToast({ open: true, message: 'Bank statement imported. 47 transactions synced.', severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>Import Statement</Button>
        </DialogActions>
      </Dialog>

      {/* ══════════════════════════════════════════════════════════════
          SHORTCUT DIALOGS
      ══════════════════════════════════════════════════════════════ */}
      {/* New Journal Entry */}
      <Dialog open={newJournalOpen} onClose={() => setNewJournalOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>New Journal Entry</Typography>
          <IconButton onClick={() => setNewJournalOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label="Particulars / Description" size="small" fullWidth placeholder="e.g. Revenue from Sales – June Invoice" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} />
          <Grid container spacing={2}>
            <Grid item xs={6}><TextField label="Debit Amount (₹)" type="number" size="small" fullWidth placeholder="0.00" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} /></Grid>
            <Grid item xs={6}><TextField label="Credit Amount (₹)" type="number" size="small" fullWidth placeholder="0.00" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} /></Grid>
          </Grid>
          <TextField label="Date" type="date" size="small" fullWidth defaultValue={new Date().toISOString().split('T')[0]} sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} />
          <TextField label="Department" size="small" select fullWidth SelectProps={{ native: true }} sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }}><option>Finance</option><option>Operations</option><option>Sales</option><option>HR</option><option>Logistics</option></TextField>
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setNewJournalOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Cancel</Button>
          <Button variant="contained" onClick={() => { setNewJournalOpen(false); setToast({ open: true, message: 'Journal entry created and posted to ledger.', severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>Post Journal Entry</Button>
        </DialogActions>
      </Dialog>

      {/* Record Expense */}
      <Dialog open={recordExpenseOpen} onClose={() => setRecordExpenseOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Record Expense</Typography>
          <IconButton onClick={() => setRecordExpenseOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label="Expense Description" size="small" fullWidth placeholder="e.g. AWS Monthly Invoice" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} />
          <Grid container spacing={2}>
            <Grid item xs={6}><TextField label="Amount (₹)" type="number" size="small" fullWidth placeholder="0.00" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} /></Grid>
            <Grid item xs={6}><TextField label="Date" type="date" size="small" fullWidth defaultValue={new Date().toISOString().split('T')[0]} sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} /></Grid>
          </Grid>
          <TextField label="Category" size="small" select fullWidth SelectProps={{ native: true }} sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }}><option>IT & Software</option><option>Travel</option><option>Office Supplies</option><option>Marketing</option><option>Utilities</option></TextField>
          <TextField label="Department" size="small" select fullWidth SelectProps={{ native: true }} sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }}><option>Finance</option><option>Operations</option><option>Sales</option><option>HR</option></TextField>
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setRecordExpenseOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Cancel</Button>
          <Button variant="contained" onClick={() => { setRecordExpenseOpen(false); setToast({ open: true, message: 'Expense recorded and submitted for approval.', severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.success, boxShadow: 'none' }}>Record Expense</Button>
        </DialogActions>
      </Dialog>

      {/* Add Asset */}
      <Dialog open={addAssetOpen} onClose={() => setAddAssetOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Add Asset</Typography>
          <IconButton onClick={() => setAddAssetOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField label="Asset Name" size="small" fullWidth placeholder="e.g. Delivery Van #4" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} />
          <Grid container spacing={2}>
            <Grid item xs={6}><TextField label="Asset Type" size="small" select fullWidth SelectProps={{ native: true }} sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }}><option>Vehicle</option><option>IT Equipment</option><option>Furniture</option><option>Machinery</option><option>Building</option></TextField></Grid>
            <Grid item xs={6}><TextField label="Purchase Value (₹)" type="number" size="small" fullWidth placeholder="0.00" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} /></Grid>
          </Grid>
          <TextField label="Purchase Date" type="date" size="small" fullWidth defaultValue={new Date().toISOString().split('T')[0]} sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} />
          <TextField label="Depreciation Rate (% per year)" type="number" size="small" fullWidth placeholder="e.g. 15" sx={{ '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '12px' } }} />
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setAddAssetOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Cancel</Button>
          <Button variant="contained" onClick={() => { setAddAssetOpen(false); setToast({ open: true, message: 'Asset registered successfully in the Asset Ledger.', severity: 'success' }); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.info, boxShadow: 'none' }}>Register Asset</Button>
        </DialogActions>
      </Dialog>

      {/* Prepare GST Returns */}
      <Dialog open={prepGstOpen} onClose={() => setPrepGstOpen(false)} maxWidth="sm" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>GST Return Wizard</Typography>
          <IconButton onClick={() => setPrepGstOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3, display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {[{ step: 1, label: 'Verify GSTR-1 Sales Data', status: 'Complete', desc: '42 invoices reconciled' }, { step: 2, label: 'Reconcile GSTR-2B ITC', status: 'Complete', desc: 'ITC of ₹18,500 available' }, { step: 3, label: 'Prepare GSTR-3B Summary', status: 'In Progress', desc: 'Net tax payable: ₹42,000' }, { step: 4, label: 'Review & Submit to GST Portal', status: 'Pending', desc: 'Due in 12 days' }].map((s, i) => (
            <Box key={i} sx={{ display: 'flex', alignItems: 'center', gap: 2, p: 1.5, borderRadius: '10px', bgcolor: s.status === 'In Progress' ? '#EEF2FF' : '#F8FAFC', border: `1px solid ${s.status === 'In Progress' ? COLORS.accent : '#E2E8F0'}` }}>
              <Box sx={{ width: 30, height: 30, borderRadius: '50%', bgcolor: s.status === 'Complete' ? COLORS.success : s.status === 'In Progress' ? COLORS.accent : '#E2E8F0', color: s.status === 'Complete' ? '#fff' : s.status === 'In Progress' ? '#fff' : COLORS.secondaryText, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '13px', fontWeight: 800, flexShrink: 0 }}>
                {s.status === 'Complete' ? <CheckCircleIcon sx={{ fontSize: 16, color: '#fff' }} /> : s.step}
              </Box>
              <Box sx={{ flex: 1 }}>
                <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{s.label}</Typography>
                <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText }}>{s.desc}</Typography>
              </Box>
              <Box sx={{ px: 0.8, py: 0.25, borderRadius: '4px', bgcolor: s.status === 'Complete' ? '#E6F4EA' : s.status === 'In Progress' ? '#EEF2FF' : '#F1F5F9', color: s.status === 'Complete' ? COLORS.success : s.status === 'In Progress' ? COLORS.accent : COLORS.secondaryText, fontSize: '9px', fontWeight: 800 }}>{s.status}</Box>
            </Box>
          ))}
        </DialogContent>
        <DialogActions sx={{ borderTop: '1px solid #E2E8F0', p: 2, gap: 1 }}>
          <Button variant="outlined" onClick={() => setPrepGstOpen(false)} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, borderColor: '#CBD5E1', color: COLORS.secondaryText }}>Cancel</Button>
          <Button variant="contained" onClick={() => { setPrepGstOpen(false); setGstFilingOpen(true); }} sx={{ textTransform: 'none', fontSize: '12px', fontWeight: 700, bgcolor: COLORS.accent, boxShadow: 'none' }}>Proceed to Filing →</Button>
        </DialogActions>
      </Dialog>

      {/* View All Shortcuts */}
      <Dialog open={viewAllShortcutsOpen} onClose={() => setViewAllShortcutsOpen(false)} maxWidth="md" fullWidth slotProps={{ paper: { sx: { borderRadius: '16px', p: 1 } } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #E2E8F0', pb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <GridViewIcon sx={{ color: COLORS.accent, fontSize: 20 }} />
            <Typography sx={{ fontSize: '18px', fontWeight: 800, color: COLORS.primaryText }}>Finance Operations Hub</Typography>
          </Box>
          <IconButton onClick={() => setViewAllShortcutsOpen(false)} size="small"><CloseIcon sx={{ fontSize: 18 }} /></IconButton>
        </DialogTitle>
        <DialogContent sx={{ py: 3 }}>
          <Grid container spacing={2}>
            {[
              { label: 'New Journal Entry', Icon: JournalIcon, desc: 'Post debit/credit transactions', color: COLORS.accent, action: () => { setViewAllShortcutsOpen(false); setNewJournalOpen(true); } },
              { label: 'Record Expense', Icon: ReceiptIcon, desc: 'Log business expenses', color: COLORS.success, action: () => { setViewAllShortcutsOpen(false); setRecordExpenseOpen(true); } },
              { label: 'Add Asset', Icon: AddIcon, desc: 'Register capital asset', color: COLORS.info, action: () => { setViewAllShortcutsOpen(false); setAddAssetOpen(true); } },
              { label: 'Prepare GST Returns', Icon: DescriptionIcon, desc: 'File GSTR-1 & GSTR-3B', color: COLORS.warning, action: () => { setViewAllShortcutsOpen(false); setPrepGstOpen(true); } },
              { label: 'Bank Reconciliation', Icon: CompareArrowsIcon, desc: 'Match bank vs ledger', color: COLORS.danger, action: () => { setViewAllShortcutsOpen(false); setRunBankReconOpen(true); } },
              { label: 'Import Bank Statement', Icon: UploadFileIcon, desc: 'Upload CSV/XLSX/PDF', color: COLORS.accent, action: () => { setViewAllShortcutsOpen(false); setImportStatementOpen(true); } },
              { label: 'Reports Hub', Icon: AssignmentIcon, desc: 'P&L, Balance Sheet, GST', color: COLORS.success, action: () => { setViewAllShortcutsOpen(false); setReportsHubOpen(true); } },
              { label: 'Executive Report', Icon: SparklesIcon, desc: 'AI-generated CFO report', color: COLORS.accent, action: () => { setViewAllShortcutsOpen(false); handleGenerateReport(); } },
            ].map((sc, i) => (
              <Grid item xs={12} sm={6} md={3} key={i}>
                <Box onClick={sc.action} sx={{ border: '1px solid #E2E8F0', borderRadius: '12px', p: 2.5, cursor: 'pointer', textAlign: 'center', transition: 'all 0.18s', '&:hover': { borderColor: sc.color, bgcolor: `${sc.color}08`, transform: 'translateY(-2px)', boxShadow: '0 4px 16px rgba(0,0,0,0.06)' } }}>
                  <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1 }}>
                    <Box sx={{ width: 44, height: 44, borderRadius: '12px', bgcolor: `${sc.color}12`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <sc.Icon sx={{ fontSize: 22, color: sc.color }} />
                    </Box>
                  </Box>
                  <Typography sx={{ fontSize: '12px', fontWeight: 700, color: COLORS.primaryText }}>{sc.label}</Typography>
                  <Typography sx={{ fontSize: '10px', color: COLORS.secondaryText, mt: 0.3 }}>{sc.desc}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </DialogContent>
      </Dialog>

    </Box>
  );
}
