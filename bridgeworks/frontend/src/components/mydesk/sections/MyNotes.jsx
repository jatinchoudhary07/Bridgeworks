import React, { useState, useEffect, useCallback, useRef } from "react";
import { Box, useTheme, useMediaQuery, Snackbar, Alert } from "@mui/material";
import NotesSidebar from "./NotesSidebar";
import NoteEditor from "./NoteEditor";
import NotePropertiesPanel from "./NotePropertiesPanel";
import { notesService } from "./notesService";

const AUTOSAVE_DELAY = 30000;

export default function MyNotes() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  const [notes, setNotes] = useState([]);
  const [selectedNote, setSelectedNote] = useState(null);
  const [editorContent, setEditorContent] = useState("");
  const [editorTitle, setEditorTitle] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [snackbar, setSnackbar] = useState({ open: false, message: "", severity: "success" });
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTag, setActiveTag] = useState("All");
  const [rightPanelOpen, setRightPanelOpen] = useState(!isMobile);

  const autosaveTimer = useRef(null);
  // Keep a ref of the selected note id so autosave closure always has it
  const selectedNoteRef = useRef(null);

  useEffect(() => {
    loadNotes();
  }, []);

  const loadNotes = async () => {
    try {
      const data = await notesService.getNotes();
      setNotes(data);
      if (data.length > 0) {
        handleSelectNote(data[0]);
      }
    } catch {
      showSnackbar("Failed to load notes", "error");
    }
  };

  const handleSelectNote = (note) => {
    // Flush pending autosave before switching
    if (autosaveTimer.current) {
      clearTimeout(autosaveTimer.current);
      autosaveTimer.current = null;
    }
    selectedNoteRef.current = note;
    setSelectedNote(note);
    setEditorTitle(note.title || "");
    setEditorContent(note.content || "");
    setLastSaved(note.updated_at ? new Date(note.updated_at) : null);
  };

  const handleContentChange = useCallback((html) => {
    setEditorContent(html);
    triggerAutosave({ content: html });
  }, []);

  const handleTitleChange = useCallback((title) => {
    setEditorTitle(title);
    triggerAutosave({ title });
  }, []);

  const triggerAutosave = (partial) => {
    if (autosaveTimer.current) clearTimeout(autosaveTimer.current);
    autosaveTimer.current = setTimeout(() => {
      // Read current values from state via updater pattern
      setEditorContent((currentContent) => {
        setEditorTitle((currentTitle) => {
          saveNote({
            content: partial.content ?? currentContent,
            title: partial.title ?? currentTitle,
          });
          return currentTitle;
        });
        return currentContent;
      });
    }, AUTOSAVE_DELAY);
  };

  const saveNote = async ({ content, title }) => {
    const note = selectedNoteRef.current;
    if (!note) return;
    setIsSaving(true);
    try {
      const updated = await notesService.updateNote(note.id, { title, content });
      setLastSaved(new Date());
      setSelectedNote(updated);
      selectedNoteRef.current = updated;
      setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
    } catch {
      showSnackbar("Autosave failed", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleManualSave = async () => {
    const note = selectedNoteRef.current;
    if (!note) return;
    if (autosaveTimer.current) {
      clearTimeout(autosaveTimer.current);
      autosaveTimer.current = null;
    }
    setIsSaving(true);
    try {
      const updated = await notesService.updateNote(note.id, {
        title: editorTitle,
        content: editorContent,
      });
      setLastSaved(new Date());
      setSelectedNote(updated);
      selectedNoteRef.current = updated;
      setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
      showSnackbar("Note saved successfully.");
    } catch {
      showSnackbar("Save failed", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCreateVersion = async () => {
    const note = selectedNoteRef.current;
    if (!note) return;
    if (autosaveTimer.current) {
      clearTimeout(autosaveTimer.current);
      autosaveTimer.current = null;
    }
    setIsSaving(true);
    try {
      const updated = await notesService.updateNote(note.id, {
        title: editorTitle,
        content: editorContent,
        create_version: true,
      });
      setLastSaved(new Date());
      setSelectedNote(updated);
      selectedNoteRef.current = updated;
      setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
      showSnackbar("Version created successfully.");
    } catch {
      showSnackbar("Failed to create version", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleNewNote = async () => {
    try {
      const newNote = await notesService.createNote({
        title: "Untitled Note",
        content: "",
        tags: [],
        label: "",
      });
      setNotes((prev) => [newNote, ...prev]);
      handleSelectNote(newNote);
    } catch {
      showSnackbar("Failed to create note", "error");
    }
  };

  const handlePinNote = async (noteId) => {
    try {
      const note = notes.find((n) => n.id === noteId);
      const updated = await notesService.updateNote(noteId, {
        ...note,
        is_pinned: !note.is_pinned,
      });
      setNotes((prev) => prev.map((n) => (n.id === noteId ? updated : n)));
      if (selectedNote?.id === noteId) {
        setSelectedNote(updated);
        selectedNoteRef.current = updated;
      }
    } catch {
      showSnackbar("Failed to pin note", "error");
    }
  };

  const handleDeleteNote = async (noteId) => {
    try {
      await notesService.deleteNote(noteId);
      const remaining = notes.filter((n) => n.id !== noteId);
      setNotes(remaining);
      if (selectedNote?.id === noteId) {
        if (remaining.length > 0) handleSelectNote(remaining[0]);
        else {
          setSelectedNote(null);
          selectedNoteRef.current = null;
        }
      }
      showSnackbar("Note deleted");
    } catch {
      showSnackbar("Failed to delete note", "error");
    }
  };

  const handleAddTag = async (tag) => {
    if (!selectedNote) return;
    const currentTags = selectedNote.tags || [];
    if (currentTags.includes(tag)) return;
    try {
      const updated = await notesService.updateNote(selectedNote.id, {
        ...selectedNote,
        tags: [...currentTags, tag],
      });
      setSelectedNote(updated);
      selectedNoteRef.current = updated;
      setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
    } catch {
      showSnackbar("Failed to add tag", "error");
    }
  };

  const handleRemoveTag = async (tag) => {
    if (!selectedNote) return;
    try {
      const updated = await notesService.updateNote(selectedNote.id, {
        ...selectedNote,
        tags: (selectedNote.tags || []).filter((t) => t !== tag),
      });
      setSelectedNote(updated);
      selectedNoteRef.current = updated;
      setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
    } catch {
      showSnackbar("Failed to remove tag", "error");
    }
  };

  const handleRestoreVersion = async (versionId) => {
    if (!selectedNote) return;
    try {
      const updated = await notesService.restoreVersion(selectedNote.id, versionId);
      showSnackbar("Note restored to selected version.");
      handleSelectNote(updated);
      setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
    } catch (err) {
      showSnackbar(err.message || "Failed to restore version", "error");
    }
  };

  const handleDeleteVersion = async (versionId) => {
    if (!selectedNote) return;
    try {
      const updated = await notesService.deleteVersion(selectedNote.id, versionId);
      showSnackbar("Version deleted.");
      setSelectedNote(updated);
      selectedNoteRef.current = updated;
      setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
    } catch (err) {
      showSnackbar(err.message || "Failed to delete version", "error");
    }
  };

  const handleUpdateNote = (updated) => {
    setSelectedNote(updated);
    selectedNoteRef.current = updated;
    setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
  };

  const filteredNotes = notes.filter((note) => {
    const matchesSearch =
      !searchQuery ||
      note.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      note.content?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTag = activeTag === "All" || (note.tags || []).includes(activeTag);
    return matchesSearch && matchesTag;
  });

  const allTags = ["All", ...new Set(notes.flatMap((n) => n.tags || []))];

  const showSnackbar = (message, severity = "success") => {
    setSnackbar({ open: true, message, severity });
  };

  return (
    <Box
      sx={{
        display: "flex",
        height: "100%",
        bgcolor: "background.default",
        overflow: "hidden",
      }}
    >
      {/* Left Sidebar */}
      <NotesSidebar
        notes={filteredNotes}
        selectedNote={selectedNote}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        activeTag={activeTag}
        onTagChange={setActiveTag}
        allTags={allTags}
        onSelectNote={handleSelectNote}
        onNewNote={handleNewNote}
        onPinNote={handlePinNote}
        onDeleteNote={handleDeleteNote}
      />

      {/* Center Editor */}
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>
        {selectedNote ? (
          <NoteEditor
            note={selectedNote}
            title={editorTitle}
            content={editorContent}
            isSaving={isSaving}
            lastSaved={lastSaved}
            onTitleChange={handleTitleChange}
            onContentChange={handleContentChange}
            onToggleRightPanel={() => setRightPanelOpen((p) => !p)}
            onAddTag={handleAddTag}
            rightPanelOpen={rightPanelOpen}
            showSnackbar={showSnackbar}
            onSave={handleManualSave}
            onCreateVersion={handleCreateVersion}
          />
        ) : (
          <Box
            sx={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 1.5,
              color: "text.disabled",
            }}
          >
            <Box sx={{ fontSize: 48, lineHeight: 1 }}>📝</Box>
            <Box sx={{ fontSize: 15, fontWeight: 600, color: "text.secondary" }}>
              No note selected
            </Box>
            <Box sx={{ fontSize: 13 }}>
              Select a note from the sidebar or create a new one
            </Box>
          </Box>
        )}
      </Box>

      {/* Right Properties Panel */}
      {rightPanelOpen && selectedNote && (
        <NotePropertiesPanel
          note={selectedNote}
          onAddTag={handleAddTag}
          onRemoveTag={handleRemoveTag}
          onUpdateNote={handleUpdateNote}
          onRestoreVersion={handleRestoreVersion}
          onDeleteVersion={handleDeleteVersion}
          showSnackbar={showSnackbar}
          onClose={() => setRightPanelOpen(false)}
        />
      )}

      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity={snackbar.severity} variant="filled" sx={{ borderRadius: 2 }}>
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
