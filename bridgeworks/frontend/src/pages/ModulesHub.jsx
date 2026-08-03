import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Typography,
  Card,
  Button,
  Chip,
  Container,
  Paper,
  CircularProgress,
  LinearProgress,
  alpha,
} from "@mui/material";
import AccountBalanceIcon from "@mui/icons-material/AccountBalance";
import PeopleAltIcon from "@mui/icons-material/PeopleAlt";
import DashboardIcon from "@mui/icons-material/Dashboard";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import FavoriteIcon from "@mui/icons-material/Favorite";
import HubIcon from "@mui/icons-material/Hub";
import BoltIcon from "@mui/icons-material/Bolt";

const MODULE_CARDS = [
  {
    id: "finance",
    title: "Finance & Accounting",
    badge: "Financial Control & Compliance",
    path: "/finance/control-tower",
    accentColor: "#2563eb",
    bgSoft: "#eff6ff",
    borderSoft: "#bfdbfe",
    gradient: "linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%)",
    icon: <AccountBalanceIcon sx={{ fontSize: 24, color: "#2563eb" }} />,
    stat: "Real-time P&L & GST Engine",
    features: [
      "Double-Entry Journal & Ledger Summaries",
      "Trial Balance, Profit & Loss & Balance Sheet",
      "GST Compliance, GSTR-1/3B & ITC Reconciliation",
      "Bank Account Management & Auto-Matching",
    ],
  },
  {
    id: "team",
    title: "HR & Team",
    badge: "Workforce & Talent Operations",
    path: "/team",
    accentColor: "#059669",
    bgSoft: "#ecfdf5",
    borderSoft: "#a7f3d0",
    gradient: "linear-gradient(135deg, #047857 0%, #10b981 100%)",
    icon: <PeopleAltIcon sx={{ fontSize: 24, color: "#059669" }} />,
    stat: "Workforce & Payroll System",
    features: [
      "Master Employee Register & Role Management",
      "Daily Attendance Tracking & Regularizations",
      "Monthly Payroll Runs & Employee Payslips",
      "Recruitment Pipeline & Candidate Applications",
    ],
  },
  {
    id: "mydesk",
    title: "My Desk",
    badge: "Personal Desktop Workspace",
    path: "/mydesk/notes",
    accentColor: "#7c3aed",
    bgSoft: "#f5f3ff",
    borderSoft: "#ddd6fe",
    gradient: "linear-gradient(135deg, #6d28d9 0%, #8b5cf6 100%)",
    icon: <DashboardIcon sx={{ fontSize: 24, color: "#7c3aed" }} />,
    stat: "Personal Desktop Workspace",
    features: [
      "Rich Notes Knowledge Base & Quick Capture",
      "Kanban & List View Task Manager",
      "Team Channels & Direct Messaging",
      "Work Diary, Personal Expenses & Gmail Sync",
    ],
  },
];

export default function ModulesHub() {
  const navigate = useNavigate();
  const [launchingCard, setLaunchingCard] = useState(null);

  const handleLaunch = (card) => {
    setLaunchingCard(card);
    setTimeout(() => {
      navigate(card.path);
    }, 420);
  };

  return (
    <Box
      sx={{
        height: "100vh",
        maxHeight: "100vh",
        width: "100%",
        bgcolor: "#f8fafc",
        color: "#0f172a",
        position: "relative",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        py: { xs: 1.5, md: 2 },
        px: { xs: 2, sm: 3 },
        boxSizing: "border-box",
        overflow: "hidden",
      }}
    >
      {/* ── Top Neon Progress Shimmer Bar & Floating Capsule HUD ───────────── */}
      {launchingCard && (
        <>
          <LinearProgress
            sx={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              zIndex: 99999,
              height: 4,
              bgcolor: "transparent",
              "& .MuiLinearProgress-bar": {
                background: launchingCard.gradient,
                borderRadius: 99,
              },
            }}
          />

          <Box
            sx={{
              position: "fixed",
              top: 20,
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 99999,
              bgcolor: "rgba(255, 255, 255, 0.94)",
              backdropFilter: "blur(16px)",
              border: `1.5px solid ${launchingCard.accentColor}`,
              boxShadow: `0 12px 32px ${alpha(launchingCard.accentColor, 0.25)}`,
              borderRadius: 99,
              px: 3,
              py: 1,
              display: "flex",
              alignItems: "center",
              gap: 1.5,
            }}
          >
            <BoltIcon sx={{ color: launchingCard.accentColor, fontSize: 20 }} />
            <Typography variant="subtitle2" fontWeight={800} sx={{ color: "#0f172a", fontSize: "0.85rem", letterSpacing: 0.3 }}>
              INITIALIZING {launchingCard.title.toUpperCase()} ENGINE...
            </Typography>
          </Box>
        </>
      )}

      {/* ── Soft Ambient Mesh Gradients ───────────────────────────────────── */}
      <Box
        sx={{
          position: "absolute",
          top: "-10%",
          left: "15%",
          width: 500,
          height: 500,
          background: "radial-gradient(circle, rgba(37, 99, 235, 0.06) 0%, rgba(255, 255, 255, 0) 70%)",
          pointerEvents: "none",
        }}
      />
      <Box
        sx={{
          position: "absolute",
          bottom: "-10%",
          right: "15%",
          width: 550,
          height: 550,
          background: "radial-gradient(circle, rgba(124, 58, 237, 0.06) 0%, rgba(255, 255, 255, 0) 70%)",
          pointerEvents: "none",
        }}
      />

      <Container maxWidth="xl" sx={{ zIndex: 1, height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", py: 0.5 }}>
        {/* ── Hero Section (Expanded Space for Prominent Branding) ──────────── */}
        <Box sx={{ textAlign: "center", pt: { xs: 0.5, md: 1 }, mb: { xs: 1.5, md: 2 } }}>
          {/* Status Badge */}
          <Box
            sx={{
              display: "inline-flex",
              alignItems: "center",
              gap: 0.85,
              px: 1.75,
              py: 0.35,
              borderRadius: 99,
              bgcolor: "#ffffff",
              border: "1px solid #e2e8f0",
              boxShadow: "0 2px 6px rgba(15, 23, 42, 0.03)",
              mb: 1.25,
            }}
          >
            <Box
              sx={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                bgcolor: "#10b981",
                boxShadow: "0 0 6px #10b981",
              }}
            />
            <Typography variant="caption" sx={{ fontSize: "0.68rem", fontWeight: 700, letterSpacing: 1.1, color: "#475569" }}>
              ENTERPRISE CORE ONLINE
            </Typography>
          </Box>

          {/* Software Title — Larger & Clipless Descender (Fixes 'g' clipping) */}
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 1.25, mb: 0.25 }}>
            <HubIcon sx={{ fontSize: { xs: 34, md: 44 }, color: "#2563eb" }} />
            <Typography
              variant="h1"
              fontWeight={900}
              letterSpacing={-1.5}
              sx={{
                fontSize: { xs: "2.35rem", sm: "3.25rem", md: "3.85rem" },
                background: "linear-gradient(135deg, #0f172a 0%, #1e3a5f 40%, #2563eb 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                lineHeight: 1.28,
                pb: "0.1em",
                display: "inline-block",
              }}
            >
              BridgeWorks
            </Typography>
          </Box>

          {/* Tagline */}
          <Typography
            variant="h4"
            fontWeight={800}
            sx={{
              fontSize: { xs: "1.05rem", sm: "1.25rem", md: "1.45rem" },
              letterSpacing: 0.2,
              color: "#1e3a5f",
              mb: 0.75,
            }}
          >
            Built to Connect. Designed to Perform.
          </Typography>

          <Typography
            variant="body2"
            sx={{
              maxWidth: 640,
              mx: "auto",
              color: "#64748b",
              fontSize: { xs: "0.825rem", md: "0.9rem" },
              lineHeight: 1.45,
            }}
          >
            Select a specialized core module below to launch your live financial control tower, workforce administration, or personal desktop workspace.
          </Typography>
        </Box>

        {/* ── 3 Module Cards Grid (Compact Spacing to Transfer Height to Hero) ── */}
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" },
            gap: { xs: 2, md: 2.25 },
            alignItems: "stretch",
            flex: 1,
            mb: 1,
          }}
        >
          {MODULE_CARDS.map((card) => {
            const isLaunching = launchingCard?.id === card.id;

            return (
              <Card
                key={card.id}
                onClick={() => handleLaunch(card)}
                sx={{
                  bgcolor: "#ffffff",
                  border: `1.5px solid ${isLaunching ? card.accentColor : "#e2e8f0"}`,
                  borderRadius: 3.5,
                  p: { xs: 1.75, md: 2.25 },
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  cursor: "pointer",
                  position: "relative",
                  overflow: "hidden",
                  boxShadow: isLaunching
                    ? `0 0 35px ${alpha(card.accentColor, 0.35)}, 0 12px 28px -4px rgba(15, 23, 42, 0.12)`
                    : "0 3px 14px -2px rgba(15, 23, 42, 0.04)",
                  transform: isLaunching ? "scale(1.02)" : "none",
                  transition: "all 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                  "&:hover": {
                    transform: isLaunching ? "scale(1.02)" : "translateY(-4px)",
                    borderColor: card.accentColor,
                    boxShadow: `0 14px 28px -6px ${alpha(card.accentColor, 0.18)}`,
                    "& .launch-button": {
                      background: card.gradient,
                      color: "#ffffff",
                      boxShadow: `0 3px 12px ${alpha(card.accentColor, 0.25)}`,
                    },
                  },
                }}
              >
                {/* Accent Top Strip */}
                <Box
                  sx={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: 3.5,
                    background: card.gradient,
                  }}
                />

                <Box>
                  {/* Header Row */}
                  <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1.25 }}>
                    <Box
                      sx={{
                        p: 1,
                        borderRadius: 2,
                        bgcolor: card.bgSoft,
                        border: `1px solid ${card.borderSoft}`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {card.icon}
                    </Box>

                    <Chip
                      label={card.stat}
                      size="small"
                      sx={{
                        fontSize: "0.68rem",
                        fontWeight: 700,
                        bgcolor: card.bgSoft,
                        color: card.accentColor,
                        border: `1px solid ${card.borderSoft}`,
                      }}
                    />
                  </Box>

                  {/* Title & Subtitle */}
                  <Typography variant="h4" fontWeight={800} sx={{ fontSize: "1.2rem", color: "#0f172a", mb: 0.35 }}>
                    {card.title}
                  </Typography>

                  <Typography variant="body2" sx={{ color: "#64748b", fontSize: "0.76rem", mb: 1.5 }}>
                    {card.badge}
                  </Typography>

                  {/* Features List */}
                  <Box sx={{ display: "flex", flexDirection: "column", gap: 0.85, mb: 1.75 }}>
                    {card.features.map((feat, idx) => (
                      <Box key={idx} sx={{ display: "flex", alignItems: "flex-start", gap: 0.85 }}>
                        <CheckCircleIcon sx={{ fontSize: 15, color: card.accentColor, mt: 0.15, flexShrink: 0 }} />
                        <Typography variant="body2" sx={{ color: "#334155", fontSize: "0.78rem", fontWeight: 500, lineHeight: 1.35 }}>
                          {feat}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </Box>

                {/* Launch Button */}
                <Button
                  className="launch-button"
                  variant="outlined"
                  fullWidth
                  endIcon={<ArrowForwardIcon />}
                  sx={{
                    py: 0.85,
                    borderRadius: 2.25,
                    borderColor: isLaunching ? card.accentColor : card.borderSoft,
                    color: isLaunching ? "#ffffff" : card.accentColor,
                    background: isLaunching ? card.gradient : card.bgSoft,
                    fontWeight: 700,
                    fontSize: "0.825rem",
                    textTransform: "none",
                    transition: "all 0.2s ease",
                  }}
                >
                  {isLaunching ? "Connecting Engine..." : `Launch ${card.title}`}
                </Button>
              </Card>
            );
          })}
        </Box>

        {/* ── Footer Credit ─────────────────────────────────────────────────── */}
        <Box sx={{ textAlign: "center", pt: 0.5, pb: 0.75 }}>
          <Typography
            variant="body2"
            sx={{
              color: "#475569",
              fontSize: "0.825rem",
              fontWeight: 700,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 0.6,
            }}
          >
            Made with <FavoriteIcon sx={{ fontSize: 15, color: "#ef4444" }} /> by Jatin
          </Typography>
          <Typography variant="caption" sx={{ color: "#94a3b8", fontSize: "0.725rem", mt: 0.2, display: "block" }}>
            BridgeWorks Enterprise Platform &middot; All Rights Reserved
          </Typography>
        </Box>
      </Container>
    </Box>
  );
}
