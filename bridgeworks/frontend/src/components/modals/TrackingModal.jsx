import React, { useState } from 'react';
import {
    Dialog, DialogTitle, DialogContent, DialogActions,
    Button, Box, Typography, Grid, Paper, Divider, Chip,
    Stepper, Step, StepLabel,
    Table, TableHead, TableRow, TableCell, TableBody,
    Alert, TextField
} from "@mui/material";
import SearchIcon from '@mui/icons-material/Search';
import InputAdornment from '@mui/material/InputAdornment';

// Helper: Format Date
const formatDateTime = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleString("en-IN", {
        year: 'numeric', month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit',
    });
};

// Helper: Step Index
const getStepIndex = (status) => {
    const statusLower = status?.toLowerCase() || '';
    if (statusLower.includes('booked') || statusLower.includes('sch')) return 0;
    if (statusLower.includes('picked') || statusLower.includes('manifest')) return 1;
    if (statusLower.includes('transit') || statusLower.includes('int')) return 2;
    if (statusLower.includes('out for delivery') || statusLower.includes('ood')) return 3;
    if (statusLower.includes('delivered') || statusLower.includes('del') || statusLower.includes('rtd')) return 4;
    return -1;
};

const steps = ['Order Booked', 'Picked Up', 'In Transit', 'Out for Delivery', 'Delivered'];

export default function TrackingModal({ open, order, onClose }) {
    const [filterText, setFilterText] = useState(""); // Local filter state

    if (!order) return null;

    const currentStatus = order.tracking_events?.[0]?.status || order.computedStatus;
    const activeStep = getStepIndex(currentStatus);
    const isCompleted = activeStep === 4;

    // Filter Logic for Tracking Events
    const events = order.tracking_events || [];
    const filteredEvents = events.filter(event => {
        if (!filterText) return true;
        const term = filterText.toLowerCase();
        return (
            (event.status && event.status.toLowerCase().includes(term)) ||
            (event.details && event.details.toLowerCase().includes(term))
        );
    });

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth="md"
            fullWidth
            scroll="paper"
        >
            <DialogTitle sx={{ fontWeight: 'bold' }}>
                Tracking Details for Order #{order.order_number}
                <Typography variant="caption" color="text.secondary" component="div">
                    AWB: {order.tracking_info?.number || "N/A"} | Courier: {order.tracking_info?.company || "N/A"}
                </Typography>
            </DialogTitle>

            <Divider />

            <DialogContent dividers>
                {/* 1. Stepper */}
                <Box sx={{ mb: 4 }}>
                    <Stepper activeStep={activeStep} alternativeLabel>
                        {steps.map((label, index) => (
                            <Step key={label} completed={isCompleted || index < activeStep}>
                                <StepLabel>{label}</StepLabel>
                            </Step>
                        ))}
                    </Stepper>
                </Box>

                {/* 2. Summary Grid */}
                <Grid container spacing={2} sx={{ mb: 3, bgcolor: 'background.default', p: 2, borderRadius: 2 }}>
                    <Grid item xs={12} sm={4}>
                        <Typography variant="subtitle2" color="text.secondary">Order Date</Typography>
                        <Typography variant="body2" fontWeight="bold">{formatDateTime(order.created_at)}</Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                        <Typography variant="subtitle2" color="text.secondary">Customer</Typography>
                        <Typography variant="body2" fontWeight="bold">{order.customer_first_name} {order.customer_last_name}</Typography>
                    </Grid>
                    <Grid item xs={12} sm={4}>
                        <Typography variant="subtitle2" color="text.secondary">Payment</Typography>
                        <Chip
                            label={order.financial_status || 'N/A'}
                            size="small"
                            color={order.financial_status === 'paid' ? 'success' : 'warning'}
                            sx={{ height: 20, fontSize: '0.7rem' }}
                        />
                    </Grid>
                </Grid>

                <Divider sx={{ mb: 2 }} />

                {/* 3. Tracking Events Section with FILTER */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="h6">Historical Tracking Events</Typography>

                    {/* THIS IS THE FILTER INSIDE THE MODAL */}
                    <TextField
                        size="small"
                        placeholder="Filter events..."
                        value={filterText}
                        onChange={(e) => setFilterText(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon fontSize="small" color="action" />
                                </InputAdornment>
                            ),
                        }}
                        sx={{ width: 200 }}
                    />
                </Box>

                {events.length > 0 ? (
                    <Paper variant="outlined" sx={{ maxHeight: 350, overflowY: 'auto' }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell sx={{ fontWeight: 'bold' }}>Time</TableCell>
                                    <TableCell sx={{ fontWeight: 'bold' }}>Status</TableCell>
                                    <TableCell sx={{ fontWeight: 'bold' }}>Location / Details</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {filteredEvents.length > 0 ? (
                                    filteredEvents.map((event, index) => (
                                        <TableRow key={index} hover>
                                            <TableCell sx={{ whiteSpace: 'nowrap', fontSize: '0.85rem' }}>
                                                {formatDateTime(event.datetime)}
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={event.status}
                                                    size="small"
                                                    color={getStepIndex(event.status) === 4 ? 'success' : 'primary'}
                                                    variant="outlined"
                                                />
                                            </TableCell>
                                            <TableCell sx={{ fontSize: '0.85rem', color: 'text.secondary' }}>
                                                {event.details || '-'}
                                            </TableCell>
                                        </TableRow>
                                    ))
                                ) : (
                                    <TableRow>
                                        <TableCell colSpan={3} align="center" sx={{ py: 2, color: 'text.secondary' }}>
                                            No events match "{filterText}"
                                        </TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </Paper>
                ) : (
                    <Alert severity="info">
                        No live tracking events found. Current status: <strong>{currentStatus}</strong>
                    </Alert>
                )}
            </DialogContent>

            <DialogActions>
                <Button onClick={onClose} color="inherit">
                    Close
                </Button>
            </DialogActions>
        </Dialog>
    );
}