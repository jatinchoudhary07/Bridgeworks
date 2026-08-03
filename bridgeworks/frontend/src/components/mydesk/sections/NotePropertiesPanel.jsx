import React, { useState, useRef, useEffect } from "react";
import {
  Box,
  Typography,
  Stack,
  Chip,
  Divider,
  IconButton,
  Tooltip,
  LinearProgress,
  Collapse,
  Button,
  alpha,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import AddIcon from "@mui/icons-material/Add";
import HistoryIcon from "@mui/icons-material/History";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
import PictureAsPdfOutlinedIcon from "@mui/icons-material/PictureAsPdfOutlined";
import RestoreIcon from "@mui/icons-material/Restore";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import LabelOutlinedIcon from "@mui/icons-material/LabelOutlined";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import AttachFileIcon from "@mui/icons-material/AttachFile";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { notesService } from "./notesService";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function formatFileSize(bytes) {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function fileIcon(filename) {
  if (!filename) return <InsertDriveFileOutlinedIcon sx={{ fontSize: 15, color: "text.secondary" }} />;
  if (filename.toLowerCase().endsWith(".pdf"))
    return <PictureAsPdfOutlinedIcon sx={{ fontSize: 15, color: "error.main" }} />;
  return <InsertDriveFileOutlinedIcon sx={{ fontSize: 15, color: "primary.main" }} />;
}

// ─────────────────────────────────────────────────────────────────────────────
// Section header (collapsible)
// ─────────────────────────────────────────────────────────────────────────────
function SectionHeader({ label, open, onToggle, action, icon }) {
  return (
    <Box
      onClick={onToggle}
      sx={{
        px: 2,
        py: 0.9,
        display: "flex",
        alignItems: "center",
        cursor: "pointer",
        "&:hover": { bgcolor: "action.hover" },
        userSelect: "none",
      }}
    >
      {open
        ? <ExpandMoreIcon sx={{ fontSize: 14, color: "text.disabled", mr: 0.5, flexShrink: 0 }} />
        : <ChevronRightIcon sx={{ fontSize: 14, color: "text.disabled", mr: 0.5, flexShrink: 0 }} />}
      {icon && <Box mr={0.5} sx={{ display: "flex" }}>{icon}</Box>}
      <Typography
        flex={1}
        fontSize={10}
        fontWeight={700}
        color="text.disabled"
        textTransform="uppercase"
        letterSpacing={1}
      >
        {label}
      </Typography>
      {action && (
        <Box onClick={(e) => e.stopPropagation()}>{action}</Box>
      )}
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Detail row
// ─────────────────────────────────────────────────────────────────────────────
function DetailRow({ icon, label, value, tooltip }) {
  const displayTooltip = tooltip || (typeof value === "string" ? value : "");
  const content = (
    <Typography fontSize={12} color="text.primary" fontWeight={500} textAlign="right" maxWidth={120} noWrap>
      {value}
    </Typography>
  );

  return (
    <Stack direction="row" alignItems="center" justifyContent="space-between" mb={1}>
      <Stack direction="row" alignItems="center" spacing={0.75}>
        {icon}
        <Typography fontSize={11} color="text.secondary">{label}</Typography>
      </Stack>
      {displayTooltip ? (
        <Tooltip title={displayTooltip}>
          {content}
        </Tooltip>
      ) : (
        content
      )}
    </Stack>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// NotePropertiesPanel
// ─────────────────────────────────────────────────────────────────────────────
export default function NotePropertiesPanel({
  note,
  onAddTag,
  onRemoveTag,
  onUpdateNote,
  onRestoreVersion,
  onDeleteVersion,
  showSnackbar,
  onClose,
}) {
  const [aiSummary, setAiSummary] = useState(note?.ai_summary || null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(true);
  const [attachOpen, setAttachOpen] = useState(true);
  const [historyOpen, setHistoryOpen] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    setAiSummary(note?.ai_summary || null);
  }, [note?.id, note?.ai_summary]);

  const generateSummary = async () => {
    if (!note?.id) return;
    setLoadingSummary(true);
    try {
      const result = await notesService.generateAISummary(note.id);
      const newSummary = result.summary || "";
      setAiSummary(newSummary);
      if (onUpdateNote) {
        onUpdateNote({ ...note, ai_summary: newSummary });
      }
    } catch {
      showSnackbar("Failed to generate summary", "error");
    } finally {
      setLoadingSummary(false);
    }
  };

  const handleTriggerUpload = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file || !note?.id) return;
    try {
      const updatedNote = await notesService.uploadAttachment(note.id, file);
      if (onUpdateNote) {
        onUpdateNote(updatedNote);
      }
      showSnackbar("Attachment uploaded successfully.", "success");
    } catch (err) {
      showSnackbar(err.message || "Failed to upload attachment.", "error");
    } finally {
      if (e.target) e.target.value = "";
    }
  };

  const handleDeleteAttachment = async (attachmentId) => {
    if (!note?.id) return;
    try {
      await notesService.deleteAttachment(attachmentId);
      const updatedNote = await notesService.getNote(note.id);
      if (onUpdateNote) {
        onUpdateNote(updatedNote);
      }
      showSnackbar("Attachment deleted.", "success");
    } catch (err) {
      showSnackbar(err.message || "Failed to delete attachment.", "error");
    }
  };

  const versions = note?.versions?.length
    ? note.versions
    : [
        {
          label:
            "Today, " +
            (note?.updated_at
              ? new Date(note.updated_at).toLocaleTimeString("en-US", {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—"),
          current: true,
        },
      ];

  return (
    <Box
      sx={{
        width: 256,
        minWidth: 256,
        height: "100%",
        borderLeft: "1px solid",
        borderColor: "divider",
        bgcolor: "background.paper",
        display: "flex",
        flexDirection: "column",
        overflowY: "auto",
      }}
    >
      {/* ── Panel header ── */}
      <Box
        sx={{
          px: 2,
          py: 1.25,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid",
          borderColor: "divider",
          position: "sticky",
          top: 0,
          bgcolor: "background.paper",
          zIndex: 2,
        }}
      >
        <Typography fontSize={13} fontWeight={700} color="text.primary">
          Note Details
        </Typography>
        <Tooltip title="Close">
          <IconButton size="small" onClick={onClose} sx={{ color: "text.secondary" }}>
            <CloseIcon sx={{ fontSize: 15 }} />
          </IconButton>
        </Tooltip>
      </Box>

      {/* ── AI Summary ── */}
      <Box
        sx={{
          px: 2,
          py: 1.75,
          borderBottom: "1px solid",
          borderColor: "divider",
          bgcolor: (theme) =>
            theme.palette.mode === "dark"
              ? alpha("#8b5cf6", 0.06)
              : alpha("#8b5cf6", 0.03),
        }}
      >
        <Stack direction="row" alignItems="center" spacing={0.75} mb={1}>
          <AutoAwesomeIcon sx={{ fontSize: 13, color: "#8b5cf6" }} />
          <Typography fontSize={10} fontWeight={700} color="#8b5cf6" textTransform="uppercase" letterSpacing={1}>
            AI Assistant
          </Typography>
        </Stack>

        {loadingSummary && (
          <Box mb={1}>
            <Typography fontSize={11} color="text.secondary" mb={0.75}>
              Generating summary…
            </Typography>
            <LinearProgress sx={{ borderRadius: 1, height: 3 }} />
          </Box>
        )}

        {aiSummary && !loadingSummary && (
          <Box
            sx={{
              bgcolor: (theme) => alpha("#8b5cf6", 0.07),
              border: "1px solid",
              borderColor: (theme) => alpha("#8b5cf6", 0.2),
              borderRadius: 1.5,
              p: 1.25,
              mb: 1,
            }}
          >
            <Typography fontSize={10} fontWeight={700} color="#8b5cf6" mb={0.5}>
              ✨ Summary
            </Typography>
            <Typography fontSize={12} color="text.primary" lineHeight={1.65}>
              {aiSummary}
            </Typography>
          </Box>
        )}

        {!aiSummary && !loadingSummary && (
          <Typography fontSize={12} color="text.secondary" mb={1} lineHeight={1.5}>
            Generate an AI summary of this note's content.
          </Typography>
        )}

        <Tooltip title={aiSummary ? "Regenerate summary with Gemini" : "Generate summary with Gemini"}>
          <Button
            disabled
            size="small"
            variant="outlined"
            onClick={generateSummary}
            startIcon={<AutoAwesomeIcon sx={{ fontSize: 12 }} />}
            sx={{
              fontSize: 11,
              textTransform: "none",
              fontWeight: 600,
              borderRadius: 1.5,
              py: 0.4,
            }}
          >
            {aiSummary ? "Regenerate" : "Generate Summary"}
          </Button>
        </Tooltip>
      </Box>

      {/* ── Note details ── */}
      <SectionHeader
        label="Note Details"
        open={detailsOpen}
        onToggle={() => setDetailsOpen((p) => !p)}
      />
      {detailsOpen && (
        <Box sx={{ px: 2, pb: 2, borderBottom: "1px solid", borderColor: "divider" }}>
          <DetailRow
            icon={<PersonOutlineIcon sx={{ fontSize: 13, color: "text.secondary" }} />}
            label="Created By"
            value={note?.created_by_name || "You"}
          />
          <DetailRow
            icon={<AccessTimeIcon sx={{ fontSize: 13, color: "text.secondary" }} />}
            label="Last Edited"
            value={
              note?.updated_at
                ? new Date(note.updated_at).toLocaleTimeString("en-US", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "—"
            }
          />
          {note?.label && note.label.toLowerCase().startsWith("shared") ? (
            !note.is_owner ? (
              <DetailRow
                icon={<PersonOutlineIcon sx={{ fontSize: 13, color: "text.secondary" }} />}
                label="Shared With"
                value={
                  note.shared_with && note.shared_with.length > 0
                    ? note.shared_with.map((u) => u.name || u.email).join(", ")
                    : "—"
                }
              />
            ) : (
              <DetailRow
                icon={<PersonOutlineIcon sx={{ fontSize: 13, color: "text.secondary" }} />}
                label="Shared By"
                value={note.created_by_name || "Other"}
              />
            )
          ) : (
            <DetailRow
              icon={<LabelOutlinedIcon sx={{ fontSize: 13, color: "text.secondary" }} />}
              label="Label"
              value={note?.label ? note.label.charAt(0).toUpperCase() + note.label.slice(1) : "—"}
            />
          )}
          <DetailRow
            icon={<FiberManualRecordIcon sx={{ fontSize: 10, color: "success.main" }} />}
            label="Status"
            value={
              <Typography component="span" fontSize={12} color="success.main" fontWeight={600}>
                Auto-saved
              </Typography>
            }
          />

          {/* Tags */}
          <Box mt={1.5}>
            <Typography fontSize={10} fontWeight={700} color="text.disabled" textTransform="uppercase" letterSpacing={0.9} mb={0.75}>
              Tags
            </Typography>
            <Stack direction="row" spacing={0.5} flexWrap="wrap" gap={0.5}>
              {(note?.tags || []).length === 0 && (
                <Typography fontSize={12} color="text.disabled">No tags</Typography>
              )}
              {(note?.tags || []).map((tag) => (
                <Chip
                  key={tag}
                  label={`#${tag}`}
                  size="small"
                  onDelete={() => onRemoveTag(tag)}
                  sx={{
                    fontSize: 11,
                    height: 22,
                    borderRadius: 1,
                    bgcolor: (theme) => alpha(theme.palette.primary.main, 0.08),
                    color: "primary.main",
                    "& .MuiChip-deleteIcon": { fontSize: 13, color: "primary.main" },
                  }}
                />
              ))}
              <Tooltip title="Add tag">
                <IconButton
                  size="small"
                  onClick={() => {
                    const tag = window.prompt("Tag name (without #):");
                    if (tag?.trim()) onAddTag(tag.trim().replace(/^#/, ""));
                  }}
                  sx={{ width: 22, height: 22, color: "text.disabled", borderRadius: 1 }}
                >
                  <AddIcon sx={{ fontSize: 13 }} />
                </IconButton>
              </Tooltip>
            </Stack>
          </Box>
        </Box>
      )}

      {/* ── Attachments ── */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        style={{ display: "none" }}
      />
      <SectionHeader
        label="Attachments"
        open={attachOpen}
        onToggle={() => setAttachOpen((p) => !p)}
        icon={<AttachFileIcon sx={{ fontSize: 12, color: "text.disabled" }} />}
        action={
          <Tooltip title="Add attachment">
            <IconButton size="small" onClick={handleTriggerUpload} sx={{ color: "text.secondary" }}>
              <AddIcon sx={{ fontSize: 13 }} />
            </IconButton>
          </Tooltip>
        }
      />
      {attachOpen && (
        <Box sx={{ px: 2, pb: 1.5, borderBottom: "1px solid", borderColor: "divider" }}>
          {note?.attachments?.length > 0 ? (
            note.attachments.map((att, i) => (
              <Box
                key={i}
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 1,
                  py: 0.75,
                  px: 0.5,
                  borderRadius: 1.5,
                  "&:hover": {
                    bgcolor: "action.hover",
                    "& .delete-att-btn": { opacity: 1 },
                  },
                }}
              >
                <Stack
                  direction="row"
                  spacing={1}
                  alignItems="center"
                  flex={1}
                  minWidth={0}
                  onClick={() => att.url && window.open(att.url, "_blank")}
                  sx={{ cursor: "pointer" }}
                >
                  {fileIcon(att.filename)}
                  <Box flex={1} minWidth={0}>
                    <Typography fontSize={12} fontWeight={500} noWrap color="text.primary">
                      {att.filename}
                    </Typography>
                    <Typography fontSize={10} color="text.disabled">
                      {formatFileSize(att.size)}
                    </Typography>
                  </Box>
                </Stack>
                <IconButton
                  className="delete-att-btn"
                  size="small"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteAttachment(att.id);
                  }}
                  sx={{ opacity: 0, color: "text.secondary", transition: "opacity 0.15s" }}
                >
                  <DeleteOutlineIcon sx={{ fontSize: 14 }} />
                </IconButton>
              </Box>
            ))
          ) : (
            <Typography fontSize={12} color="text.disabled" py={0.5}>
              No attachments
            </Typography>
          )}
        </Box>
      )}

      {/* ── Version history ── */}
      <SectionHeader
        label="Version History"
        open={historyOpen}
        onToggle={() => setHistoryOpen((p) => !p)}
        icon={<HistoryIcon sx={{ fontSize: 12, color: "text.disabled" }} />}
      />
      {historyOpen && (
        <Box sx={{ px: 2, pb: 1.5 }}>
          {versions.map((v, i) => (
            <Box
              key={i}
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                py: 0.75,
                px: 0.5,
                borderRadius: 1.5,
                "&:hover": {
                  bgcolor: "action.hover",
                  "& .version-actions-btn": { opacity: 1 },
                },
              }}
            >
              <Stack direction="row" spacing={1} alignItems="center" flex={1} minWidth={0}>
                <FiberManualRecordIcon
                  sx={{ fontSize: 8, color: v.current ? "success.main" : "text.disabled", flexShrink: 0 }}
                />
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography
                    fontSize={12}
                    color={v.current ? "text.primary" : "text.secondary"}
                    fontWeight={v.current ? 600 : 400}
                    noWrap
                  >
                    {v.label}
                    {v.current && (
                      <Box component="span" sx={{ ml: 0.5, fontSize: 10, color: "success.main" }}>
                        (Current)
                      </Box>
                    )}
                  </Typography>
                  {v.author && (
                    <Typography fontSize={10} color="text.disabled" noWrap>{v.author}</Typography>
                  )}
                </Box>
              </Stack>
              {!v.current && (
                <Stack direction="row" spacing={0.5} sx={{ flexShrink: 0 }}>
                  {onRestoreVersion && (
                    <Tooltip title="Restore this version">
                      <IconButton
                        className="version-actions-btn"
                        size="small"
                        onClick={() => onRestoreVersion(v.id)}
                        sx={{ opacity: 0, color: "primary.main", transition: "opacity 0.15s" }}
                      >
                        <RestoreIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Tooltip>
                  )}
                  {onDeleteVersion && (
                    <Tooltip title="Delete this version">
                      <IconButton
                        className="version-actions-btn"
                        size="small"
                        onClick={() => {
                          if (window.confirm("Are you sure you want to delete this version?")) {
                            onDeleteVersion(v.id);
                          }
                        }}
                        sx={{ opacity: 0, color: "error.main", transition: "opacity 0.15s" }}
                      >
                        <DeleteOutlineIcon sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Stack>
              )}
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}
