import React, { useState } from "react";
import {
  Box,
  Typography,
  InputBase,
  IconButton,
  Chip,
  Stack,
  Tooltip,
  Menu,
  MenuItem,
  Divider,
  alpha,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import AddIcon from "@mui/icons-material/Add";
import PushPinIcon from "@mui/icons-material/PushPin";
import PushPinOutlinedIcon from "@mui/icons-material/PushPinOutlined";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import NoteAltOutlinedIcon from "@mui/icons-material/NoteAltOutlined";

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
const stripHtml = (html) => {
  if (!html) return "";
  return html.replace(/<[^>]*>/g, "").slice(0, 100);
};

const formatDate = (dateStr) => {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return d.toLocaleDateString("en-US", { weekday: "short" });
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
};

// ─────────────────────────────────────────────────────────────────────────────
// NoteCard
// ─────────────────────────────────────────────────────────────────────────────
function NoteCard({ note, selected, onSelect, onMenu }) {
  return (
    <Box
      onClick={onSelect}
      sx={{
        mx: 1,
        mb: 0.5,
        px: 1.5,
        py: 1.25,
        borderRadius: 2,
        cursor: "pointer",
        position: "relative",
        border: "1px solid",
        borderColor: selected ? "primary.main" : "transparent",
        bgcolor: selected ? (theme) => alpha(theme.palette.primary.main, 0.08) : "transparent",
        "&:hover": {
          bgcolor: selected
            ? (theme) => alpha(theme.palette.primary.main, 0.1)
            : "action.hover",
          borderColor: selected ? "primary.main" : "divider",
          "& .note-menu-btn": { opacity: 1 },
        },
        transition: "all 0.15s ease",
      }}
    >
      {/* Title row */}
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 0.5 }}>
        <Typography
          fontWeight={600}
          sx={{
            fontSize: 13,
            lineHeight: 1.4,
            flex: 1,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            color: selected ? "primary.main" : "text.primary",
          }}
        >
          {note.is_pinned && (
            <PushPinIcon sx={{ fontSize: 10, mr: 0.5, opacity: 0.6, verticalAlign: "middle" }} />
          )}
          {note.title || "Untitled"}
        </Typography>
        <IconButton
          className="note-menu-btn"
          size="small"
          onClick={(e) => onMenu(e, note)}
          sx={{
            opacity: 0,
            p: 0.25,
            color: "text.secondary",
            flexShrink: 0,
            "&:hover": { bgcolor: "action.selected" },
            transition: "opacity 0.15s",
          }}
        >
          <MoreVertIcon sx={{ fontSize: 14 }} />
        </IconButton>
      </Box>

      {/* Preview */}
      <Typography
        sx={{
          fontSize: 11.5,
          color: "text.secondary",
          mt: 0.25,
          overflow: "hidden",
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
          lineHeight: 1.55,
        }}
      >
        {stripHtml(note.content) || "No content yet…"}
      </Typography>

      {/* Tags */}
      {note.tags?.length > 0 && (
        <Stack direction="row" spacing={0.5} mt={0.75} flexWrap="wrap">
          {note.tags.slice(0, 3).map((tag) => (
            <Box
              key={tag}
              component="span"
              sx={{
                fontSize: 10,
                px: 0.75,
                py: 0.15,
                borderRadius: 1,
                bgcolor: selected
                  ? (theme) => alpha(theme.palette.primary.main, 0.12)
                  : "action.selected",
                color: selected ? "primary.main" : "text.secondary",
                fontWeight: 500,
              }}
            >
              #{tag}
            </Box>
          ))}
        </Stack>
      )}

      {/* Footer */}
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mt: 0.75 }}>
        {note.label && !note.label.toLowerCase().startsWith("shared") && (
          <Typography
            sx={{
              fontSize: 10,
              color: "text.disabled",
              textTransform: "capitalize",
              fontWeight: 500,
            }}
          >
            {note.label}
          </Typography>
        )}
        <Typography sx={{ fontSize: 10, color: "text.disabled", ml: "auto" }}>
          {formatDate(note.updated_at)}
        </Typography>
      </Box>
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SectionLabel
// ─────────────────────────────────────────────────────────────────────────────
function SectionLabel({ children }) {
  return (
    <Typography
      sx={{
        px: 2,
        pt: 1,
        pb: 0.5,
        fontSize: 10,
        fontWeight: 700,
        color: "text.disabled",
        textTransform: "uppercase",
        letterSpacing: 1.2,
      }}
    >
      {children}
    </Typography>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// NotesSidebar
// ─────────────────────────────────────────────────────────────────────────────
export default function NotesSidebar({
  notes,
  selectedNote,
  searchQuery,
  onSearchChange,
  activeTag,
  onTagChange,
  allTags,
  onSelectNote,
  onNewNote,
  onPinNote,
  onDeleteNote,
}) {
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [menuNote, setMenuNote] = useState(null);

  const pinnedNotes = notes.filter((n) => n.is_pinned);
  const unpinnedNotes = notes.filter((n) => !n.is_pinned);

  const openMenu = (e, note) => {
    e.stopPropagation();
    setMenuAnchor(e.currentTarget);
    setMenuNote(note);
  };

  const closeMenu = () => {
    setMenuAnchor(null);
    setMenuNote(null);
  };

  return (
    <Box
      sx={{
        width: 264,
        minWidth: 264,
        height: "100%",
        borderRight: "1px solid",
        borderColor: "divider",
        display: "flex",
        flexDirection: "column",
        bgcolor: "background.paper",
      }}
    >
      {/* ── Search and New Note ── */}
      <Box
        sx={{
          px: 2,
          pt: 2,
          pb: 1.25,
          display: "flex",
          alignItems: "center",
          gap: 1,
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            bgcolor: "action.hover",
            borderRadius: 2,
            px: 1.25,
            py: 0.6,
            gap: 0.75,
            border: "1px solid transparent",
            flex: 1,
            "&:focus-within": {
              borderColor: "primary.main",
              bgcolor: "background.default",
            },
            transition: "all 0.15s",
          }}
        >
          <SearchIcon sx={{ fontSize: 15, color: "text.disabled", flexShrink: 0 }} />
          <InputBase
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search notes…"
            sx={{ fontSize: 12.5, flex: 1 }}
          />
        </Box>
        <Tooltip title="New note" placement="right">
          <IconButton
            size="small"
            onClick={onNewNote}
            sx={{
              bgcolor: "primary.main",
              color: "#fff",
              width: 28,
              height: 28,
              borderRadius: 1.5,
              "&:hover": { bgcolor: "primary.dark" },
              boxShadow: "0 2px 8px rgba(99,102,241,0.35)",
              flexShrink: 0,
            }}
          >
            <AddIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      </Box>

      {/* ── Tag filter ── */}
      {allTags.length > 1 && (
        <Box sx={{ px: 2, pb: 1.25 }}>
          <Stack direction="row" spacing={0.5} flexWrap="wrap" gap={0.5}>
            {allTags.map((tag) => (
              <Chip
                key={tag}
                label={tag === "All" ? "All" : `#${tag}`}
                size="small"
                onClick={() => onTagChange(tag)}
                sx={{
                  fontSize: 11,
                  height: 22,
                  borderRadius: 1.5,
                  bgcolor: activeTag === tag ? "primary.main" : "action.hover",
                  color: activeTag === tag ? "#fff" : "text.secondary",
                  fontWeight: activeTag === tag ? 600 : 400,
                  cursor: "pointer",
                  "&:hover": {
                    bgcolor: activeTag === tag ? "primary.dark" : "action.selected",
                  },
                }}
              />
            ))}
          </Stack>
        </Box>
      )}

      <Divider />

      {/* ── Notes list ── */}
      <Box sx={{ flex: 1, overflowY: "auto", py: 0.75 }}>
        {/* Pinned */}
        {pinnedNotes.length > 0 && (
          <>
            <SectionLabel>📌 Pinned</SectionLabel>
            {pinnedNotes.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                selected={selectedNote?.id === note.id}
                onSelect={() => onSelectNote(note)}
                onMenu={openMenu}
              />
            ))}
            {unpinnedNotes.length > 0 && (
              <Divider sx={{ my: 0.75, mx: 2 }} />
            )}
          </>
        )}

        {/* Recents */}
        {unpinnedNotes.length > 0 && (
          <>
            {pinnedNotes.length > 0 && <SectionLabel>Recent</SectionLabel>}
            {unpinnedNotes.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                selected={selectedNote?.id === note.id}
                onSelect={() => onSelectNote(note)}
                onMenu={openMenu}
              />
            ))}
          </>
        )}

        {/* Empty */}
        {notes.length === 0 && (
          <Box sx={{ px: 2, pt: 6, textAlign: "center", color: "text.disabled" }}>
            <Box sx={{ fontSize: 36, mb: 1 }}>📝</Box>
            <Typography fontSize={13} fontWeight={500} color="text.secondary">
              No notes yet
            </Typography>
            <Typography fontSize={12} mt={0.5}>
              Click + to create your first note
            </Typography>
          </Box>
        )}
      </Box>

      {/* Count footer */}
      <Box
        sx={{
          px: 2,
          py: 1,
          borderTop: "1px solid",
          borderColor: "divider",
          bgcolor: "background.default",
        }}
      >
        <Typography fontSize={11} color="text.disabled">
          {notes.length} {notes.length === 1 ? "note" : "notes"}
        </Typography>
      </Box>

      {/* ── Context Menu ── */}
      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={closeMenu}
        transformOrigin={{ horizontal: "right", vertical: "top" }}
        anchorOrigin={{ horizontal: "right", vertical: "bottom" }}
        PaperProps={{
          sx: { minWidth: 170, boxShadow: "0 8px 24px rgba(0,0,0,0.12)", borderRadius: 2 },
        }}
      >
        <MenuItem
          onClick={() => { onPinNote(menuNote.id); closeMenu(); }}
          sx={{ fontSize: 13, gap: 1.25, py: 1 }}
        >
          {menuNote?.is_pinned ? (
            <PushPinIcon sx={{ fontSize: 15, color: "primary.main" }} />
          ) : (
            <PushPinOutlinedIcon sx={{ fontSize: 15, color: "text.secondary" }} />
          )}
          {menuNote?.is_pinned ? "Unpin note" : "Pin note"}
        </MenuItem>
        <Divider />
        <MenuItem
          onClick={() => { onDeleteNote(menuNote.id); closeMenu(); }}
          sx={{ fontSize: 13, gap: 1.25, py: 1, color: "error.main" }}
        >
          <DeleteOutlineIcon sx={{ fontSize: 15 }} />
          Delete
        </MenuItem>
      </Menu>
    </Box>
  );
}
