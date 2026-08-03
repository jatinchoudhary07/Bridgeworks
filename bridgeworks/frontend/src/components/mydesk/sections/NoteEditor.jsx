import React, { useState, useCallback, useEffect } from "react";
import {
  Box,
  Typography,
  InputBase,
  IconButton,
  Tooltip,
  Stack,
  Chip,
  Button,
  Divider,
  CircularProgress,
  alpha,
  Popover,
} from "@mui/material";
import { useEditor, EditorContent } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Strike from "@tiptap/extension-strike";
import Link from "@tiptap/extension-link";
import TaskList from "@tiptap/extension-task-list";
import TaskItem from "@tiptap/extension-task-item";
import Highlight from "@tiptap/extension-highlight";
import Placeholder from "@tiptap/extension-placeholder";
import { Color } from "@tiptap/extension-color";
import { TextStyle } from "@tiptap/extension-text-style";

// Icons
import FormatBoldIcon from "@mui/icons-material/FormatBold";
import FormatItalicIcon from "@mui/icons-material/FormatItalic";
import FormatUnderlinedIcon from "@mui/icons-material/FormatUnderlined";
import StrikethroughSIcon from "@mui/icons-material/StrikethroughS";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import FormatListNumberedIcon from "@mui/icons-material/FormatListNumbered";
import CheckBoxOutlinedIcon from "@mui/icons-material/CheckBoxOutlined";
import CodeIcon from "@mui/icons-material/Code";
import InsertLinkIcon from "@mui/icons-material/InsertLink";
import HighlightIcon from "@mui/icons-material/Highlight";
import ShareIcon from "@mui/icons-material/Share";
import PanelRightIcon from "@mui/icons-material/ViewSidebarOutlined";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import NavigateNextIcon from "@mui/icons-material/NavigateNext";
import AddIcon from "@mui/icons-material/Add";
import FormatQuoteIcon from "@mui/icons-material/FormatQuote";
import FormatColorTextIcon from "@mui/icons-material/FormatColorText";
import FormatColorFillIcon from "@mui/icons-material/FormatColorFill";

import AICopilotDialog from "./AICopilotDialog";
import NoteShareDialog from "./NoteShareDialog";

// ─────────────────────────────────────────────────────────────────────────────
// Toolbar button
// ─────────────────────────────────────────────────────────────────────────────
function ToolbarButton({ onClick, active, title, children, label }) {
  return (
    <Tooltip title={title} placement="bottom" arrow>
      <IconButton
        onClick={onClick}
        size="small"
        sx={{
          width: 30,
          height: 30,
          borderRadius: 1.5,
          bgcolor: active ? "primary.main" : "transparent",
          color: active ? "#fff" : "text.secondary",
          "&:hover": {
            bgcolor: active ? "primary.dark" : "action.hover",
            color: active ? "#fff" : "text.primary",
          },
          transition: "all 0.12s",
        }}
      >
        {label
          ? <span style={{ fontSize: 11, fontWeight: 700, lineHeight: 1 }}>{label}</span>
          : children}
      </IconButton>
    </Tooltip>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// BubbleMenu button
// ─────────────────────────────────────────────────────────────────────────────
function BubbleBtn({ label, active, onClick }) {
  return (
    <Box
      onClick={onClick}
      sx={{
        px: 1.5,
        py: 0.6,
        fontSize: 12,
        fontWeight: active ? 700 : 500,
        cursor: "pointer",
        bgcolor: active ? "primary.main" : "transparent",
        color: active ? "#fff" : "text.primary",
        "&:hover": { bgcolor: active ? "primary.dark" : "action.hover" },
        userSelect: "none",
        transition: "background 0.1s",
      }}
    >
      {label}
    </Box>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Color Picker helper
// ─────────────────────────────────────────────────────────────────────────────
const TEXT_COLORS = [
  "#000000", // Black
  "#4b5563", // Dark Grey
  "#9ca3af", // Light Grey
  "#ef4444", // Red
  "#f97316", // Orange
  "#facc15", // Yellow
  "#22c55e", // Green
  "#3b82f6", // Blue
  "#6366f1", // Indigo
  "#a855f7", // Purple
];

const HIGHLIGHT_COLORS = [
  "#f3f4f6", // Muted Grey
  "#fee2e2", // Pastel Red
  "#ffedd5", // Pastel Orange
  "#fef9c3", // Pastel Yellow
  "#dcfce7", // Pastel Green
  "#dbeafe", // Pastel Blue
  "#e0e7ff", // Pastel Indigo
  "#f3e8ff", // Pastel Purple
  "#fce7f3", // Pastel Pink
  "#ffccd5", // Pink Highlight
];

function ColorPickerButton({ icon, title, colors, currentColor, onSelectColor, onClear }) {
  const [anchorEl, setAnchorEl] = useState(null);

  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleSelect = (color) => {
    onSelectColor(color);
    handleClose();
  };

  const handleClearClick = () => {
    onClear();
    handleClose();
  };

  const open = Boolean(anchorEl);

  return (
    <>
      <Tooltip title={title}>
        <IconButton
          onClick={handleClick}
          size="small"
          sx={{
            width: 30,
            height: 30,
            borderRadius: 1.5,
            color: "text.secondary",
            borderBottom: currentColor ? `3px solid ${currentColor}` : "none",
            "&:hover": {
              bgcolor: "action.hover",
              color: "text.primary",
            },
            transition: "all 0.12s",
          }}
        >
          {icon}
        </IconButton>
      </Tooltip>
      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "left",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "left",
        }}
        slotProps={{
          paper: {
            sx: {
              p: 1.5,
              width: 200,
              borderRadius: 2,
              boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
            }
          }
        }}
      >
        <Typography fontSize={10} fontWeight={700} color="text.disabled" textTransform="uppercase" letterSpacing={0.8} mb={1}>
          {title}
        </Typography>
        <Box
          sx={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: 1,
            mb: 1.5,
          }}
        >
          {colors.map((color) => (
            <Box
              key={color}
              onClick={() => handleSelect(color)}
              sx={{
                width: 26,
                height: 26,
                borderRadius: 1,
                bgcolor: color,
                cursor: "pointer",
                border: "1px solid",
                borderColor: currentColor === color ? "primary.main" : "divider",
                boxShadow: currentColor === color ? "0 0 0 2px rgba(99,102,241,0.2)" : "none",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                "&:hover": {
                  transform: "scale(1.1)",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                },
                transition: "all 0.1s",
              }}
            >
              {currentColor === color && (
                <Box
                  sx={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    bgcolor: "#fff",
                    boxShadow: "0 1px 2px rgba(0,0,0,0.5)",
                  }}
                />
              )}
            </Box>
          ))}
        </Box>
        <Stack direction="row" spacing={1}>
          <Button
            size="small"
            variant="outlined"
            fullWidth
            onClick={handleClearClick}
            sx={{
              fontSize: 11,
              py: 0.5,
              textTransform: "none",
              borderRadius: 1.5,
              borderColor: "divider",
              color: "text.secondary",
              "&:hover": {
                borderColor: "text.secondary",
                bgcolor: "action.hover",
                color: "text.primary",
              }
            }}
          >
            Reset
          </Button>
          <Box sx={{ position: "relative", width: "45%", flexShrink: 0 }}>
            <Button
              size="small"
              variant="outlined"
              fullWidth
              sx={{
                fontSize: 11,
                py: 0.5,
                textTransform: "none",
                borderRadius: 1.5,
                borderColor: "divider",
                color: "text.secondary",
                "&:hover": {
                  borderColor: "text.secondary",
                  bgcolor: "action.hover",
                  color: "text.primary",
                }
              }}
            >
              Custom
            </Button>
            <input
              type="color"
              value={currentColor || "#000000"}
              onChange={(e) => handleSelect(e.target.value)}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                height: "100%",
                opacity: 0,
                cursor: "pointer",
              }}
            />
          </Box>
        </Stack>
      </Popover>
    </>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// NoteEditor
// ─────────────────────────────────────────────────────────────────────────────
export default function NoteEditor({
  note,
  title,
  content,
  isSaving,
  lastSaved,
  onTitleChange,
  onContentChange,
  onToggleRightPanel,
  onAddTag,
  rightPanelOpen,
  showSnackbar,
  onSave,
  onCreateVersion,
}) {
  const [copilotOpen, setCopilotOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [addingTag, setAddingTag] = useState(false);
  const [newTag, setNewTag] = useState("");

  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      Strike,
      TextStyle,
      Color,
      Highlight.configure({ multicolor: true }),
      Link.configure({ openOnClick: false }),
      TaskList,
      TaskItem.configure({ nested: true }),
      Placeholder.configure({ placeholder: "Start writing your thoughts…" }),
    ],
    content: content || "",
    onUpdate: ({ editor }) => {
      onContentChange(editor.getHTML());
    },
  });

  // Sync content when selected note changes
  useEffect(() => {
    if (editor && content !== editor.getHTML()) {
      editor.commands.setContent(content || "", false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [note?.id]);

  const setLink = useCallback(() => {
    if (!editor) return;
    const prev = editor.getAttributes("link").href;
    const url = window.prompt("Enter URL:", prev);
    if (url === null) return;
    if (url === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
    } else {
      editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
    }
  }, [editor]);

  const handleTagSubmit = (e) => {
    if (e.key === "Enter" && newTag.trim()) {
      onAddTag(newTag.trim().replace(/^#/, ""));
      setNewTag("");
      setAddingTag(false);
    }
    if (e.key === "Escape") {
      setAddingTag(false);
      setNewTag("");
    }
  };

  const formatSaved = () => {
    if (!lastSaved) return null;
    return lastSaved.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        bgcolor: "background.default",
      }}
    >
      {/* ── Top bar ── */}
      <Box
        sx={{
          px: 3,
          py: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
          minHeight: 46,
          flexShrink: 0,
        }}
      >
        {/* Breadcrumb */}
        <Stack direction="row" alignItems="center" >
          <Typography sx={{ fontSize: 12, color: "text.primary", fontWeight: 600 }}>
            {title || "Untitled"}
          </Typography>
        </Stack>

        {/* Right actions */}
        <Stack direction="row" alignItems="center" spacing={1.5}>
          {isSaving ? (
            <Stack direction="row" alignItems="center" spacing={0.75} sx={{ mr: 1 }}>
              <CircularProgress size={10} />
              <Typography fontSize={11} color="text.disabled">Saving…</Typography>
            </Stack>
          ) : lastSaved ? (
            <Typography fontSize={11} color="success.main" fontWeight={600} sx={{ mr: 1 }}>
              ✓ Saved {formatSaved()}
            </Typography>
          ) : null}

          {onSave && (
            <Button
              size="small"
              variant="contained"
              onClick={onSave}
              disabled={isSaving}
              sx={{
                fontSize: 11,
                fontWeight: 600,
                textTransform: "none",
                borderRadius: 1.5,
                py: 0.4,
                px: 1.5,
                boxShadow: "none",
                "&:hover": { boxShadow: "none" },
              }}
            >
              Save
            </Button>
          )}

          {onCreateVersion && (
            <Button
              size="small"
              variant="outlined"
              onClick={onCreateVersion}
              disabled={isSaving}
              sx={{
                fontSize: 11,
                fontWeight: 600,
                textTransform: "none",
                borderRadius: 1.5,
                py: 0.4,
                px: 1.5,
              }}
            >
              Create Version
            </Button>
          )}

          <Tooltip title="Share">
            <IconButton size="small" onClick={() => setShareOpen(true)} sx={{ color: "text.secondary" }}>
              <ShareIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Tooltip>

          <Tooltip title={rightPanelOpen ? "Hide details" : "Show details"}>
            <IconButton
              size="small"
              onClick={onToggleRightPanel}
              sx={{
                color: rightPanelOpen ? "primary.main" : "text.secondary",
                bgcolor: rightPanelOpen
                  ? (theme) => alpha(theme.palette.primary.main, 0.1)
                  : "transparent",
                borderRadius: 1.5,
              }}
            >
              <PanelRightIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      {/* ── Toolbar ── */}
      <Box
        sx={{
          px: 3,
          py: 0.75,
          display: "flex",
          alignItems: "center",
          gap: 0.25,
          borderBottom: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
          flexWrap: "wrap",
          flexShrink: 0,
        }}
      >
        <ToolbarButton onClick={() => editor?.chain().focus().toggleBold().run()} active={editor?.isActive("bold")} title="Bold">
          <FormatBoldIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>
        <ToolbarButton onClick={() => editor?.chain().focus().toggleItalic().run()} active={editor?.isActive("italic")} title="Italic">
          <FormatItalicIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>
        <ToolbarButton onClick={() => editor?.chain().focus().toggleUnderline().run()} active={editor?.isActive("underline")} title="Underline">
          <FormatUnderlinedIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>
        <ToolbarButton onClick={() => editor?.chain().focus().toggleStrike().run()} active={editor?.isActive("strike")} title="Strikethrough">
          <StrikethroughSIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>
        <ToolbarButton onClick={() => editor?.chain().focus().toggleHighlight().run()} active={editor?.isActive("highlight")} title="Highlight">
          <HighlightIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>

        <ColorPickerButton
          icon={<FormatColorTextIcon sx={{ fontSize: 16 }} />}
          title="Text Color"
          colors={TEXT_COLORS}
          currentColor={editor?.getAttributes("textStyle").color || ""}
          onSelectColor={(color) => editor?.chain().focus().setColor(color).run()}
          onClear={() => editor?.chain().focus().unsetColor().run()}
        />

        <ColorPickerButton
          icon={<FormatColorFillIcon sx={{ fontSize: 16 }} />}
          title="Highlight Color"
          colors={HIGHLIGHT_COLORS}
          currentColor={editor?.getAttributes("highlight").color || ""}
          onSelectColor={(color) => editor?.chain().focus().toggleHighlight({ color }).run()}
          onClear={() => editor?.chain().focus().unsetHighlight().run()}
        />

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5, height: 18, alignSelf: "center" }} />

        <ToolbarButton onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()} active={editor?.isActive("heading", { level: 1 })} title="Heading 1" label="H1" />
        <ToolbarButton onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()} active={editor?.isActive("heading", { level: 2 })} title="Heading 2" label="H2" />
        <ToolbarButton onClick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()} active={editor?.isActive("heading", { level: 3 })} title="Heading 3" label="H3" />

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5, height: 18, alignSelf: "center" }} />

        <ToolbarButton onClick={() => editor?.chain().focus().toggleBulletList().run()} active={editor?.isActive("bulletList")} title="Bullet List">
          <FormatListBulletedIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>
        <ToolbarButton onClick={() => editor?.chain().focus().toggleOrderedList().run()} active={editor?.isActive("orderedList")} title="Ordered List">
          <FormatListNumberedIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>
        <ToolbarButton onClick={() => editor?.chain().focus().toggleTaskList().run()} active={editor?.isActive("taskList")} title="Checklist">
          <CheckBoxOutlinedIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>

        <Divider orientation="vertical" flexItem sx={{ mx: 0.5, height: 18, alignSelf: "center" }} />

        <ToolbarButton onClick={() => editor?.chain().focus().toggleBlockquote().run()} active={editor?.isActive("blockquote")} title="Quote">
          <FormatQuoteIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>
        <ToolbarButton onClick={() => editor?.chain().focus().toggleCodeBlock().run()} active={editor?.isActive("codeBlock")} title="Code Block">
          <CodeIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>
        <ToolbarButton onClick={setLink} active={editor?.isActive("link")} title="Insert Link">
          <InsertLinkIcon sx={{ fontSize: 16 }} />
        </ToolbarButton>

        {/* AI Copilot button — pushed to the right */}
        <Box sx={{ ml: "auto" }}>
          <Tooltip title="Ask AI Copilot for help with this note">
            <Button
              disabled
              size="small"
              variant="contained"
              onClick={() => setCopilotOpen(true)}
              startIcon={<AutoAwesomeIcon sx={{ fontSize: 13 }} />}
              sx={{
                fontSize: 12,
                fontWeight: 600,
                py: 0.5,
                px: 1.5,
                borderRadius: 2,
                textTransform: "none",
                boxShadow: "none",
              }}
            >
              AI Copilot
            </Button>
          </Tooltip>
        </Box>
      </Box>

      {/* ── Editor area ── */}
      <Box sx={{ flex: 1, overflowY: "auto", px: { xs: 2, md: 8 }, py: 4 }}>

        {/* Title */}
        <InputBase
          value={title}
          onChange={(e) => onTitleChange(e.target.value)}
          placeholder="Untitled Note"
          multiline
          fullWidth
          sx={{
            fontSize: 30,
            fontWeight: 700,
            lineHeight: 1.25,
            color: "text.primary",
            mb: 1.5,
            "& textarea": { padding: 0 },
          }}
        />

        {/* Metadata & tags row */}
        <Stack direction="row" spacing={1.5} alignItems="center" mb={2} flexWrap="wrap" gap={0.75}>
          <Typography fontSize={12} color="text.disabled">
            {note?.created_at
              ? new Date(note.created_at).toLocaleDateString("en-US", {
                month: "long", day: "numeric", year: "numeric",
              })
              : ""}
          </Typography>

          <Divider orientation="vertical" flexItem sx={{ height: 14, alignSelf: "center" }} />

          {/* Tags */}
          <Stack direction="row" spacing={0.5} alignItems="center" flexWrap="wrap" gap={0.5}>
            {(note?.tags || []).map((tag) => (
              <Chip
                key={tag}
                label={`#${tag}`}
                size="small"
                sx={{
                  fontSize: 11,
                  height: 22,
                  bgcolor: (theme) => alpha(theme.palette.primary.main, 0.1),
                  color: "primary.main",
                  fontWeight: 600,
                  borderRadius: 1,
                }}
              />
            ))}
            {addingTag ? (
              <InputBase
                autoFocus
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyDown={handleTagSubmit}
                placeholder="#tag"
                sx={{
                  fontSize: 11,
                  px: 1,
                  py: 0.25,
                  border: "1px solid",
                  borderColor: "primary.main",
                  borderRadius: 1,
                  minWidth: 80,
                  maxWidth: 120,
                }}
              />
            ) : (
              <Tooltip title="Add tag">
                <IconButton
                  size="small"
                  onClick={() => setAddingTag(true)}
                  sx={{ width: 22, height: 22, color: "text.disabled" }}
                >
                  <AddIcon sx={{ fontSize: 13 }} />
                </IconButton>
              </Tooltip>
            )}
          </Stack>
        </Stack>

        <Divider sx={{ mb: 3 }} />

        {/* TipTap editor */}
        <Box
          sx={{
            "& .ProseMirror": {
              outline: "none",
              minHeight: 360,
              fontSize: 14.5,
              lineHeight: 1.85,
              color: "text.primary",
              caretColor: "primary.main",

              "& h1": { fontSize: "1.85em", fontWeight: 700, mt: 2.5, mb: 0.75, lineHeight: 1.2 },
              "& h2": { fontSize: "1.45em", fontWeight: 600, mt: 2, mb: 0.5 },
              "& h3": { fontSize: "1.2em", fontWeight: 600, mt: 1.5, mb: 0.5 },
              "& p": { mt: 0, mb: 1 },
              "& ul, & ol": { pl: "1.5em", mb: 1 },
              "& li": { mb: 0.25 },

              "& ul[data-type='taskList']": {
                listStyle: "none",
                pl: 0,
                "& li": {
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "0.5em",
                  "& input[type='checkbox']": {
                    mt: "0.3em",
                    cursor: "pointer",
                    accentColor: "#6366f1",
                  },
                  "& > div": { flex: 1 },
                  "&[data-checked='true'] > div": {
                    textDecoration: "line-through",
                    opacity: 0.55,
                  },
                },
              },

              "& code": {
                bgcolor: "action.hover",
                px: 0.75,
                py: 0.2,
                borderRadius: 0.75,
                fontSize: "0.87em",
                fontFamily: "'Fira Code', 'Cascadia Code', monospace",
                color: "error.main",
              },
              "& pre": {
                bgcolor: (theme) =>
                  theme.palette.mode === "dark" ? "#1e1e2e" : "#f8f8fc",
                p: 2,
                borderRadius: 2,
                overflow: "auto",
                mb: 1.5,
                border: "1px solid",
                borderColor: "divider",
                "& code": {
                  bgcolor: "transparent",
                  p: 0,
                  color: "text.primary",
                  fontSize: "0.9em",
                },
              },
              "& blockquote": {
                borderLeft: "3px solid",
                borderColor: "primary.main",
                pl: 2,
                ml: 0,
                my: 1.5,
                color: "text.secondary",
                fontStyle: "italic",
                bgcolor: (theme) => alpha(theme.palette.primary.main, 0.04),
                borderRadius: "0 8px 8px 0",
                py: 0.5,
              },
              "& mark": {
                bgcolor: "rgba(251, 191, 36, 0.3)",
                color: "inherit",
                px: 0.3,
                borderRadius: 0.5,
              },
              "& a": {
                color: "primary.main",
                textDecoration: "underline",
                cursor: "pointer",
              },
              "& hr": {
                border: "none",
                borderTop: "2px solid",
                borderColor: "divider",
                my: 2,
              },
              "& p.is-editor-empty:first-of-type::before": {
                content: "attr(data-placeholder)",
                float: "left",
                color: "text.disabled",
                pointerEvents: "none",
                height: 0,
              },
            },
          }}
        >
          {/* Floating bubble menu */}
          {editor && (
            <BubbleMenu editor={editor} tippyOptions={{ duration: 120, placement: "top" }}>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  bgcolor: "background.paper",
                  border: "1px solid",
                  borderColor: "divider",
                  borderRadius: 1.5,
                  boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
                  overflow: "hidden",
                }}
              >
                <BubbleBtn label="B" active={editor.isActive("bold")} onClick={() => editor.chain().focus().toggleBold().run()} />
                <BubbleBtn label="I" active={editor.isActive("italic")} onClick={() => editor.chain().focus().toggleItalic().run()} />
                <BubbleBtn label="U" active={editor.isActive("underline")} onClick={() => editor.chain().focus().toggleUnderline().run()} />
                <BubbleBtn label="S̶" active={editor.isActive("strike")} onClick={() => editor.chain().focus().toggleStrike().run()} />
                <Box sx={{ width: 1, bgcolor: "divider", alignSelf: "stretch" }} />
                <BubbleBtn label="H" active={editor.isActive("highlight")} onClick={() => editor.chain().focus().toggleHighlight().run()} />
                <BubbleBtn label="🔗" active={editor.isActive("link")} onClick={setLink} />
              </Box>
            </BubbleMenu>
          )}

          <EditorContent editor={editor} />
        </Box>
      </Box>

      {/* AI Copilot Dialog */}
      <AICopilotDialog
        open={copilotOpen}
        onClose={() => setCopilotOpen(false)}
        noteId={note?.id}
        noteContent={content}
        noteTitle={title}
        onInsertContent={(text) => {
          if (editor) editor.chain().focus().insertContent(text).run();
        }}
        showSnackbar={showSnackbar}
      />

      {/* Note Share Dialog */}
      <NoteShareDialog
        open={shareOpen}
        onClose={() => setShareOpen(false)}
        noteId={note?.id}
        showSnackbar={showSnackbar}
      />
    </Box>
  );
}
