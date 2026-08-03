import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  Stack,
  Button,
  IconButton,
  Divider,
  CircularProgress,
  TextField,
  Chip,
  alpha,
  Tooltip,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import SummarizeOutlinedIcon from "@mui/icons-material/SummarizeOutlined";
import AssignmentOutlinedIcon from "@mui/icons-material/AssignmentOutlined";
import EditNoteOutlinedIcon from "@mui/icons-material/EditNoteOutlined";
import RecordVoiceOverOutlinedIcon from "@mui/icons-material/RecordVoiceOverOutlined";
import TranslateIcon from "@mui/icons-material/Translate";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import AddCircleOutlineIcon from "@mui/icons-material/AddCircleOutline";
import SendIcon from "@mui/icons-material/Send";

// ─────────────────────────────────────────────────────────────────────────────
// Action definitions
// ─────────────────────────────────────────────────────────────────────────────
const AI_ACTIONS = [
  {
    id: "summarize",
    label: "Summarize Note",
    icon: <SummarizeOutlinedIcon sx={{ fontSize: 17 }} />,
    description: "Generate a concise summary",
    color: "#6366f1",
  },
  {
    id: "extract_tasks",
    label: "Extract Tasks",
    icon: <AssignmentOutlinedIcon sx={{ fontSize: 17 }} />,
    description: "Find all action items",
    color: "#10b981",
  },
  {
    id: "improve",
    label: "Improve Writing",
    icon: <EditNoteOutlinedIcon sx={{ fontSize: 17 }} />,
    description: "Enhance clarity & grammar",
    color: "#f59e0b",
  },
  {
    id: "meeting_minutes",
    label: "Meeting Minutes",
    icon: <RecordVoiceOverOutlinedIcon sx={{ fontSize: 17 }} />,
    description: "Format as structured minutes",
    color: "#3b82f6",
  },
  {
    id: "translate",
    label: "Translate",
    icon: <TranslateIcon sx={{ fontSize: 17 }} />,
    description: "Translate to another language",
    color: "#8b5cf6",
  },
];

const LANGUAGES = ["Hindi", "Spanish", "French", "Arabic", "German", "Japanese"];

// ─────────────────────────────────────────────────────────────────────────────
// AICopilotDialog
// ─────────────────────────────────────────────────────────────────────────────
export default function AICopilotDialog({
  open,
  onClose,
  noteId,
  noteContent,
  noteTitle,
  onInsertContent,
  showSnackbar,
}) {
  const [selectedAction, setSelectedAction] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [customPrompt, setCustomPrompt] = useState("");
  const [translateTarget, setTranslateTarget] = useState("Hindi");

  // Call notesService.aiCopilot using real backend AI engine
  const runAI = async (action, prompt) => {
    return await notesService.aiCopilot(noteId, noteTitle, noteContent, action, prompt);
  };

  const handleAction = async (actionId) => {
    setSelectedAction(actionId);
    setResult(null);
    setLoading(true);
    try {
      const text = await runAI(actionId, actionId === "translate" ? translateTarget : "");
      setResult(text);
    } catch {
      showSnackbar("AI action failed. Please try again.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleCustomPrompt = async () => {
    if (!customPrompt.trim()) return;
    setSelectedAction("custom");
    setResult(null);
    setLoading(true);
    try {
      const text = await runAI("custom", customPrompt);
      setResult(text);
    } catch {
      showSnackbar("AI action failed. Please try again.", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleInsert = () => {
    if (result) {
      onInsertContent(`\n\n${result}`);
      showSnackbar("AI content inserted into note ✓");
      handleClose();
    }
  };

  const handleCopy = () => {
    if (result) {
      navigator.clipboard.writeText(result);
      showSnackbar("Copied to clipboard");
    }
  };

  const handleClose = () => {
    setSelectedAction(null);
    setResult(null);
    setCustomPrompt("");
    onClose();
  };

  const actionColor = AI_ACTIONS.find((a) => a.id === selectedAction)?.color || "#6366f1";

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          boxShadow: "0 24px 64px rgba(0,0,0,0.2)",
          overflow: "hidden",
          maxHeight: "90vh",
        },
      }}
    >
      {/* ── Gradient header ── */}
      <DialogTitle
        sx={{
          background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
          color: "#fff",
          py: 2,
          px: 2.5,
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          flexShrink: 0,
        }}
      >
        <Box
          sx={{
            width: 34,
            height: 34,
            borderRadius: 2,
            bgcolor: "rgba(255,255,255,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <AutoAwesomeIcon sx={{ fontSize: 18 }} />
        </Box>
        <Box flex={1} minWidth={0}>
          <Typography fontWeight={700} fontSize={15} lineHeight={1.2}>
            AI Copilot
          </Typography>
          <Typography fontSize={11} sx={{ opacity: 0.8 }} noWrap>
            {noteTitle || "Untitled Note"}
          </Typography>
        </Box>
        <IconButton onClick={handleClose} size="small" sx={{ color: "rgba(255,255,255,0.8)" }}>
          <CloseIcon sx={{ fontSize: 17 }} />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <Box sx={{ overflowY: "auto", flex: 1 }}>

          {/* ── Action list ── */}
          <Box sx={{ p: 2.5 }}>
            <Typography fontSize={10} fontWeight={700} color="text.disabled" textTransform="uppercase" letterSpacing={1} mb={1.25}>
              Choose an Action
            </Typography>
            <Stack spacing={0.75}>
              {AI_ACTIONS.map((action) => {
                const isSelected = selectedAction === action.id;
                const isLoading = isSelected && loading;
                return (
                  <Box
                    key={action.id}
                    onClick={() => !loading && handleAction(action.id)}
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1.5,
                      p: 1.25,
                      borderRadius: 2,
                      cursor: loading ? "not-allowed" : "pointer",
                      border: "1px solid",
                      borderColor: isSelected ? action.color : "divider",
                      bgcolor: isSelected ? alpha(action.color, 0.07) : "background.paper",
                      "&:hover": !loading
                        ? { bgcolor: alpha(action.color, 0.06), borderColor: action.color }
                        : {},
                      transition: "all 0.15s",
                      opacity: loading && !isSelected ? 0.5 : 1,
                    }}
                  >
                    <Box
                      sx={{
                        width: 34,
                        height: 34,
                        borderRadius: 1.5,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        bgcolor: alpha(action.color, 0.12),
                        color: action.color,
                        flexShrink: 0,
                      }}
                    >
                      {action.icon}
                    </Box>
                    <Box flex={1} minWidth={0}>
                      <Typography fontSize={13} fontWeight={600} noWrap>
                        {action.label}
                      </Typography>
                      <Typography fontSize={11} color="text.secondary" noWrap>
                        {action.description}
                      </Typography>
                    </Box>
                    {isLoading && (
                      <CircularProgress size={15} sx={{ color: action.color, flexShrink: 0 }} />
                    )}
                  </Box>
                );
              })}
            </Stack>

            {/* Language selector for translate */}
            {selectedAction === "translate" && (
              <Box mt={1.25}>
                <Typography fontSize={11} color="text.secondary" mb={0.75}>
                  Target language:
                </Typography>
                <Stack direction="row" spacing={0.5} flexWrap="wrap" gap={0.5}>
                  {LANGUAGES.map((lang) => (
                    <Chip
                      key={lang}
                      label={lang}
                      size="small"
                      onClick={() => setTranslateTarget(lang)}
                      sx={{
                        fontSize: 11,
                        height: 24,
                        cursor: "pointer",
                        bgcolor: translateTarget === lang ? "primary.main" : "action.hover",
                        color: translateTarget === lang ? "#fff" : "text.secondary",
                      }}
                    />
                  ))}
                </Stack>
              </Box>
            )}
          </Box>

          <Divider />

          {/* ── Custom prompt ── */}
          <Box sx={{ p: 2.5 }}>
            <Typography fontSize={10} fontWeight={700} color="text.disabled" textTransform="uppercase" letterSpacing={1} mb={1.25}>
              Custom Prompt
            </Typography>
            <Stack direction="row" spacing={1} alignItems="flex-end">
              <TextField
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder="Ask AI anything about this note…"
                size="small"
                fullWidth
                multiline
                maxRows={3}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleCustomPrompt();
                  }
                }}
                sx={{ "& .MuiInputBase-root": { fontSize: 13, borderRadius: 1.5 } }}
              />
              <IconButton
                onClick={handleCustomPrompt}
                disabled={!customPrompt.trim() || loading}
                sx={{
                  bgcolor: "primary.main",
                  color: "#fff",
                  borderRadius: 1.5,
                  width: 36,
                  height: 36,
                  flexShrink: 0,
                  "&:hover": { bgcolor: "primary.dark" },
                  "&.Mui-disabled": { bgcolor: "action.disabledBackground" },
                }}
              >
                {loading && selectedAction === "custom"
                  ? <CircularProgress size={14} sx={{ color: "#fff" }} />
                  : <SendIcon sx={{ fontSize: 15 }} />}
              </IconButton>
            </Stack>
          </Box>

          {/* ── Result ── */}
          {result && (
            <>
              <Divider />
              <Box sx={{ p: 2.5 }}>
                <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1.25}>
                  <Typography fontSize={10} fontWeight={700} color="text.disabled" textTransform="uppercase" letterSpacing={1}>
                    AI Result
                  </Typography>
                  <Stack direction="row" spacing={0.25}>
                    <Tooltip title="Copy to clipboard">
                      <IconButton size="small" onClick={handleCopy} sx={{ color: "text.secondary" }}>
                        <ContentCopyIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Insert into note">
                      <IconButton size="small" onClick={handleInsert} sx={{ color: "primary.main" }}>
                        <AddCircleOutlineIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Tooltip>
                  </Stack>
                </Stack>

                <Box
                  sx={{
                    bgcolor: (theme) =>
                      theme.palette.mode === "dark"
                        ? alpha(actionColor, 0.08)
                        : alpha(actionColor, 0.04),
                    border: "1px solid",
                    borderColor: alpha(actionColor, 0.2),
                    borderRadius: 2,
                    p: 1.75,
                    maxHeight: 220,
                    overflowY: "auto",
                  }}
                >
                  <Typography fontSize={13} color="text.primary" lineHeight={1.8} sx={{ whiteSpace: "pre-wrap" }}>
                    {result}
                  </Typography>
                </Box>

                <Stack direction="row" spacing={1} mt={1.5}>
                  <Button
                    variant="contained"
                    size="small"
                    onClick={handleInsert}
                    startIcon={<AddCircleOutlineIcon sx={{ fontSize: 14 }} />}
                    sx={{
                      fontSize: 12,
                      textTransform: "none",
                      fontWeight: 600,
                      borderRadius: 1.5,
                      background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                      boxShadow: "none",
                      "&:hover": {
                        background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
                      },
                    }}
                  >
                    Insert into note
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={handleCopy}
                    startIcon={<ContentCopyIcon sx={{ fontSize: 14 }} />}
                    sx={{ fontSize: 12, textTransform: "none", borderRadius: 1.5 }}
                  >
                    Copy
                  </Button>
                </Stack>
              </Box>
            </>
          )}
        </Box>
      </DialogContent>
    </Dialog>
  );
}
