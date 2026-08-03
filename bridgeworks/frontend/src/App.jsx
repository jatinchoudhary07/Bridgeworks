import React, { Suspense, lazy } from "react";
import { Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import {
  Box,
  CircularProgress,
  Typography,
  Tabs,
  Tab,
  AppBar,
  Toolbar,
  Button,
  Paper,
} from "@mui/material";
import AccountBalanceIcon from "@mui/icons-material/AccountBalance";
import PeopleAltIcon from "@mui/icons-material/PeopleAlt";
import DashboardIcon from "@mui/icons-material/Dashboard";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import HubIcon from "@mui/icons-material/Hub";
import "./styles/index.css";

// ── Demo Mode Banner (shown when no backend is connected) ─────────────────────
const IS_DEMO = !import.meta.env.VITE_API_URL;
function DemoBanner() {
  if (!IS_DEMO) return null;
  return (
    <Box
      sx={{
        bgcolor: "#fffbeb",
        borderBottom: "1px solid #fcd34d",
        py: 0.5,
        px: 2,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 1,
        fontSize: "0.75rem",
      }}
    >
      <span style={{ fontSize: "0.9rem", color: "#d97706" }}>●</span>
      <Typography variant="caption" sx={{ fontWeight: 700, color: "#92400e" }}>
        Demo Mode — Sample data is shown. Connect a backend to enable live data.
      </Typography>
    </Box>
  );
}

// ── Core module pages ────────────────────────────────────────────────────────
import ModulesHub from "./pages/ModulesHub";
import FinanceAccountingPage from "./pages/FinanceAccountingPage";
import TeamManagementPage from "./pages/TeamManagementPage";
import TaskManager from "./pages/TaskManager";

// ── Full-screen loader ────────────────────────────────────────────────────────
function PageLoader() {
  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        bgcolor: "rgba(248, 250, 252, 0.8)",
        backdropFilter: "blur(20px)",
      }}
    >
      <Paper
        elevation={0}
        sx={{
          p: 4,
          borderRadius: 6,
          bgcolor: "#ffffff",
          border: "1.5px solid #e2e8f0",
          boxShadow: "0 20px 50px -10px rgba(15, 23, 42, 0.08)",
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 2,
          minWidth: 280,
        }}
      >
        <CircularProgress size={48} thickness={4} sx={{ color: "#2563eb" }} />
        <Typography variant="subtitle1" fontWeight={800} sx={{ color: "#0f172a" }}>
          Loading BridgeWorks…
        </Typography>
      </Paper>
    </Box>
  );
}

const MODULES = [
  {
    label: "Finance & Accounting",
    icon: <AccountBalanceIcon sx={{ fontSize: 18 }} />,
    match: "/finance",
    href: "/finance/control-tower",
  },
  {
    label: "HR & Team",
    icon: <PeopleAltIcon sx={{ fontSize: 18 }} />,
    match: "/team",
    href: "/team",
  },
  {
    label: "My Desk",
    icon: <DashboardIcon sx={{ fontSize: 18 }} />,
    match: "/mydesk",
    href: "/mydesk/notes",
  },
];

function TopNav() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const isHome = pathname === "/" || pathname === "";
  if (isHome) return null;

  const activeIdx = MODULES.findIndex((m) => pathname.startsWith(m.match));
  const value = activeIdx === -1 ? false : activeIdx;

  return (
    <AppBar
      position="static"
      elevation={0}
      sx={{
        bgcolor: "#ffffff",
        borderBottom: "1px solid #e2e8f0",
        boxShadow: "0 1px 3px rgba(15, 23, 42, 0.05)",
        zIndex: (t) => t.zIndex.appBar,
      }}
    >
      <Toolbar
        variant="dense"
        sx={{ minHeight: 52, gap: 1.5, px: { xs: 1.5, md: 2.5 } }}
      >
        {/* Back to Modules Hub Button */}
        <Button
          size="small"
          startIcon={<ArrowBackIcon fontSize="small" />}
          onClick={() => navigate("/")}
          sx={{
            color: "#2563eb",
            bgcolor: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: 2,
            px: 1.75,
            py: 0.4,
            fontSize: "0.775rem",
            fontWeight: 700,
            textTransform: "none",
            mr: 1,
            transition: "all 0.2s ease",
            "&:hover": {
              bgcolor: "#dbeafe",
              borderColor: "#2563eb",
            },
          }}
        >
          Modules Hub
        </Button>

        {/* Brand Logo & Name */}
        <Box
          onClick={() => navigate("/")}
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1,
            cursor: "pointer",
            mr: 2,
          }}
        >
          <HubIcon sx={{ color: "#2563eb", fontSize: 22 }} />
          <Box>
            <Typography
              variant="subtitle1"
              fontWeight={900}
              letterSpacing={0.5}
              sx={{
                fontSize: "1rem",
                lineHeight: 1.1,
                background: "linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #2563eb 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              BridgeWorks
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "#64748b",
                fontSize: "0.65rem",
                fontWeight: 600,
                display: { xs: "none", sm: "block" },
                letterSpacing: 0.3,
              }}
            >
              Built to Connect. Designed to Perform.
            </Typography>
          </Box>
        </Box>

        {/* Module tabs */}
        <Tabs
          value={value}
          onChange={(_, idx) => navigate(MODULES[idx].href)}
          textColor="inherit"
          TabIndicatorProps={{
            style: {
              backgroundColor: "#2563eb",
              height: 3,
              borderRadius: "3px 3px 0 0",
            },
          }}
          sx={{
            minHeight: 52,
            "& .MuiTab-root": {
              minHeight: 52,
              color: "#64748b",
              textTransform: "none",
              fontSize: "0.825rem",
              fontWeight: 600,
              px: 2,
              gap: 0.75,
              "&.Mui-selected": {
                color: "#2563eb",
              },
            },
          }}
        >
          {MODULES.map((m) => (
            <Tab
              key={m.match}
              label={m.label}
              icon={m.icon}
              iconPosition="start"
            />
          ))}
        </Tabs>
      </Toolbar>
    </AppBar>
  );
}

// ── Root app ──────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
        bgcolor: "background.default",
      }}
    >
      <DemoBanner />
      <TopNav />

      <Box sx={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Root / → Modules Hub Landing Page */}
            <Route index element={<ModulesHub />} />

            {/* Finance / Accounting */}
            <Route path="/finance/*" element={<FinanceAccountingPage />} />

            {/* HR & Team */}
            <Route path="/team/*" element={<TeamManagementPage />} />

            {/* My Desk */}
            <Route path="/mydesk" element={<Navigate to="/mydesk/notes" replace />} />
            <Route path="/mydesk/:section" element={<TaskManager />} />

            {/* Catch-all → Modules Hub */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </Box>
    </Box>
  );
}
