import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Autocomplete,
  Chip,
  Box,
  Typography,
  CircularProgress,
  Stack,
  alpha,
} from "@mui/material";
import PersonAddAltOutlinedIcon from "@mui/icons-material/PersonAddAltOutlined";
import { notesService } from "./notesService";

export default function NoteShareDialog({ open, onClose, noteId, showSnackbar }) {
  const [recipients, setRecipients] = useState([]);
  const [message, setMessage] = useState("");
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    if (!open) {
      setRecipients([]);
      setMessage("");
      setOptions([]);
      return;
    }

    // Load initial list of members
    let active = true;
    const fetchInitial = async () => {
      setLoading(true);
      try {
        const results = await notesService.listShareRecipients("");
        if (active) {
          setOptions(results || []);
        }
      } catch (err) {
        if (active) {
          showSnackbar("Failed to load members", "error");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    fetchInitial();

    return () => {
      active = false;
    };
  }, [open, showSnackbar]);

  // Search members on input changes
  useEffect(() => {
    if (!open || !inputValue.trim()) return;

    let active = true;
    const searchMembers = setTimeout(async () => {
      setLoading(true);
      try {
        const results = await notesService.listShareRecipients(inputValue);
        if (active) {
          setOptions(results || []);
        }
      } catch (err) {
        // quiet fail on type search
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }, 300);

    return () => {
      active = false;
      clearTimeout(searchMembers);
    };
  }, [inputValue, open]);

  const handleShare = async () => {
    if (recipients.length === 0 || !noteId) return;
    setSharing(true);
    try {
      const recipientIds = recipients.map((r) => r.id);
      await notesService.shareNote(noteId, recipientIds, message);
      showSnackbar(`Note shared successfully with ${recipients.length} member(s).`, "success");
      onClose();
    } catch (err) {
      showSnackbar(err.message || "Failed to share note.", "error");
    } finally {
      setSharing(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          p: 1.5,
          backgroundImage: "none",
        },
      }}
    >
      <DialogTitle sx={{ pb: 1, display: "flex", alignItems: "center", gap: 1 }}>
        <PersonAddAltOutlinedIcon sx={{ color: "primary.main" }} />
        <Typography fontSize={16} fontWeight={700}>
          Share Note
        </Typography>
      </DialogTitle>

      <DialogContent sx={{ pb: 1 }}>
        <Typography fontSize={13} color="text.secondary" mb={2}>
          Invite workspace members to view or collaborate on this note. They will receive a notification.
        </Typography>

        <Stack spacing={2}>
          <Autocomplete
            multiple
            options={options}
            getOptionLabel={(option) => option.name || option.email || ""}
            isOptionEqualToValue={(option, value) => option.id === value.id}
            value={recipients}
            onChange={(event, newValue) => {
              setRecipients(newValue);
            }}
            inputValue={inputValue}
            onInputChange={(event, newInputValue) => {
              setInputValue(newInputValue);
            }}
            loading={loading}
            filterSelectedOptions
            renderTags={(tagValue, getTagProps) =>
              tagValue.map((option, index) => (
                <Chip
                  label={option.name}
                  size="small"
                  {...getTagProps({ index })}
                  sx={{ borderRadius: 1.5, fontSize: 12 }}
                />
              ))
            }
            renderInput={(params) => (
              <TextField
                {...params}
                label="Search members"
                placeholder="Type name or email"
                variant="outlined"
                size="small"
                InputProps={{
                  ...params.InputProps,
                  endAdornment: (
                    <>
                      {loading ? <CircularProgress color="inherit" size={16} /> : null}
                      {params.InputProps.endAdornment}
                    </>
                  ),
                }}
              />
            )}
          />

          <TextField
            label="Add a message (optional)"
            multiline
            rows={3}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Write a message to include in the notification..."
            size="small"
            fullWidth
          />
        </Stack>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 1.5 }}>
        <Button onClick={onClose} disabled={sharing} sx={{ textTransform: "none", fontWeight: 600 }}>
          Cancel
        </Button>
        <Button
          onClick={handleShare}
          disabled={sharing || recipients.length === 0}
          variant="contained"
          sx={{
            textTransform: "none",
            fontWeight: 600,
            borderRadius: 2,
            boxShadow: "none",
            "&:hover": { boxShadow: "none" },
          }}
        >
          {sharing ? "Sharing..." : "Share"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
