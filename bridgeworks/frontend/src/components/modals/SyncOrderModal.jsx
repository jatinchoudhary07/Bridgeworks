import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  CircularProgress,
  Alert,
  Box,
  Typography,
  Tabs,
  Tab,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
} from "@mui/material";
import SyncIcon from "@mui/icons-material/Sync";
import { BACKEND_URL } from "../../config/api";
import { apiClient } from "../../apiClient";

export default function SyncOrderModal({ open, onClose, onSyncSuccess }) {
  const [tabIndex, setTabIndex] = useState(0); // 0 = Timeframe Sync, 1 = Single Order Sync
  const [timeframe, setTimeframe] = useState("today");
  const [identifier, setIdentifier] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const handleTabChange = (event, newIndex) => {
    setTabIndex(newIndex);
    setError(null);
    setSuccess(null);
  };

  const handleSync = async (e) => {
    e.preventDefault();
    
    const isSingleMode = tabIndex === 1;
    const bodyPayload = {};

    if (isSingleMode) {
      if (!identifier.trim()) {
        setError("Please enter a Shopify Order ID or Order Number.");
        return;
      }
      bodyPayload.identifier = identifier.trim();
    } else {
      bodyPayload.timeframe = timeframe;
    }

    setSyncing(true);
    setError(null);
    setSuccess(null);

    const url = `${BACKEND_URL}/api/orders/sync/`;

    try {
      const response = await apiClient(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(bodyPayload),
        credentials: "include",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Failed to sync order(s).");
      }

      setSuccess(data.message || "Synchronization completed successfully!");
      setIdentifier("");
      
      // Auto close and refresh after a short delay so user sees success state
      setTimeout(() => {
        setSuccess(null);
        if (onSyncSuccess) {
          // If bulk sync, we call onSyncSuccess with null to trigger list refresh without opening a modal.
          // If single order, we pass the returned order object to open the modal.
          onSyncSuccess(isSingleMode ? data.order : null);
        }
        onClose();
      }, 2000);

    } catch (err) {
      console.error(err);
      setError(err.message || "An error occurred during synchronization.");
    } finally {
      setSyncing(false);
    }
  };

  const handleClose = () => {
    if (syncing) return; // Prevent closing while syncing
    setError(null);
    setSuccess(null);
    setIdentifier("");
    setTimeframe("today");
    setTabIndex(0);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
      <DialogTitle sx={{ pb: 0, fontWeight: "bold", display: "flex", alignItems: "center", gap: 1 }}>
        <SyncIcon color="primary" />
        Shopify Orders Sync
      </DialogTitle>

      <Box sx={{ borderBottom: 1, borderColor: "divider", px: 2, mt: 1 }}>
        <Tabs value={tabIndex} onChange={handleTabChange} aria-label="Sync mode tabs">
          <Tab label="Sync Timeframe" />
          <Tab label="Sync Single Order" />
        </Tabs>
      </Box>
      
      <form onSubmit={handleSync}>
        <DialogContent sx={{ pt: 2 }}>
          {tabIndex === 0 ? (
            <Box>
              <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                Fetch missing orders from Shopify within a selected timeframe. Existing orders on BridgeWorks will be skipped automatically to prevent redundant processing.
              </Typography>

              <FormControl fullWidth disabled={syncing}>
                <InputLabel id="timeframe-select-label">Select Timeframe</InputLabel>
                <Select
                  labelId="timeframe-select-label"
                  id="timeframe-select"
                  value={timeframe}
                  label="Select Timeframe"
                  onChange={(e) => setTimeframe(e.target.value)}
                >
                  <MenuItem value="today">Today</MenuItem>
                  <MenuItem value="1_week">1 Week</MenuItem>
                  <MenuItem value="15_days">15 Days</MenuItem>
                  <MenuItem value="1_month">1 Month</MenuItem>
                  <MenuItem value="2_months">2 Months</MenuItem>
                </Select>
              </FormControl>
            </Box>
          ) : (
            <Box>
              <Typography variant="body2" color="textSecondary" sx={{ mb: 2 }}>
                Fetch a single order directly from Shopify and retrieve the unredacted customer name, phone number, and address from Shipway.
              </Typography>

              <TextField
                label="Shopify Order ID or Order Number"
                placeholder="e.g. 42187 or 6626150744276"
                variant="outlined"
                fullWidth
                autoFocus
                disabled={syncing}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
              />
            </Box>
          )}

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}

          {success && (
            <Alert severity="success" sx={{ mt: 2 }}>
              {success}
            </Alert>
          )}
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handleClose} disabled={syncing} color="inherit">
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={syncing || (tabIndex === 1 && !identifier.trim())}
            startIcon={syncing ? <CircularProgress size={16} color="inherit" /> : <SyncIcon />}
          >
            {syncing ? "Syncing..." : "Sync Now"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
