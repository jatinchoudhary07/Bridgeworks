import React, { useEffect, useMemo, useState, useRef } from "react";
import {
    Box, Button, Select, MenuItem, Typography, FormControl, InputLabel, TableContainer, Table, TableHead,
    TableRow, TableCell, TableBody, Checkbox, Paper, Dialog, DialogTitle,
    DialogContent, DialogActions, Grid, Chip, TextField, Snackbar, Tooltip,
    Accordion, AccordionSummary, AccordionDetails, Alert, CircularProgress, Menu, Divider,
    ListItemIcon
} from "@mui/material";
import PrintIcon from '@mui/icons-material/Print';
import ListAltIcon from '@mui/icons-material/ListAlt';
import InventoryIcon from '@mui/icons-material/Inventory';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import HistoryIcon from '@mui/icons-material/History';
import ClearIcon from '@mui/icons-material/Clear';
import QrCodeScannerIcon from '@mui/icons-material/QrCodeScanner';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import LocalShippingIcon from '@mui/icons-material/LocalShipping';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import PendingActionsIcon from '@mui/icons-material/PendingActions';
import PauseCircleOutlineIcon from '@mui/icons-material/PauseCircleOutline';

// --- CONFIGURATION ---
import { BACKEND_URL } from "../../config/api";
import { apiClient } from "../../apiClient";
import { usePagePermissions } from "../../utils/rbac";


// --- Helper Functions ---
const formatDate = (isoString) => {
    if (!isoString) return "N/A";
    return new Date(isoString).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const getLocalDate = () => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

const getTrackingNumber = (order) => order.tracking_number || order.awb_number || order?.fulfillments?.[0]?.tracking_info?.[0]?.number || "N/A";
// Returns the FIRST tracking number (for display in table)
const getDisplayTracking = (order) => order.tracking_number || order.awb_number || order?.fulfillments?.[0]?.tracking_info?.[0]?.number || "N/A";

// Checks ALL tracking numbers for a match
const isOrderMatch = (order, input) => {
    const searchStr = String(input).trim().toLowerCase();
    if (String(order.order_number) === searchStr) return true;
    if (order.tracking_number && String(order.tracking_number).trim().toLowerCase() === searchStr) return true;
    if (order.awb_number && String(order.awb_number).trim().toLowerCase() === searchStr) return true;
    if (order.fulfillments && order.fulfillments.length > 0) {
        return order.fulfillments.some(f =>
            f.tracking_info && f.tracking_info.some(t =>
                String(t.number).trim().toLowerCase() === searchStr
            )
        );
    }
    return false;
};

const reasonOptions = ["New Design", "Not in stock", "Gone for plating", "Gone for marking", "In process", "Orders Cancelled"];

const renderStatusChip = (status, work_mode) => {
    if (!status) return null;
    let label = "";
    let style = {};

    switch (status.toLowerCase()) {
        case "wfo":
        case "present":
            label = "🏢 WFO";
            style = { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' };
            break;
        case "wfh":
            label = "🏠 WFH";
            style = { backgroundColor: '#e3f2fd', color: '#1565c0', fontWeight: 'bold' };
            break;
        case "absent":
            label = "Absent";
            style = { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' };
            break;
        case "half_day":
            if (work_mode && work_mode.toLowerCase() === "wfh") {
                label = "Half Day (WFH)";
            } else if (work_mode && work_mode.toLowerCase() === "wfo") {
                label = "Half Day (WFO)";
            } else {
                label = "Half Day";
            }
            style = { backgroundColor: '#fff3e0', color: '#e65100', fontWeight: 'bold' };
            break;
        case "leave":
            label = "Leave";
            style = { backgroundColor: '#f3e5f5', color: '#4a148c', fontWeight: 'bold' };
            break;
        case "on_duty":
            label = "On Duty";
            style = { backgroundColor: '#e0f7fa', color: '#006064', fontWeight: 'bold' };
            break;
        default:
            return null;
    }

    return (
        <Chip 
            label={label} 
            size="small" 
            sx={{ 
                ml: 1, 
                height: 20, 
                fontSize: '0.65rem', 
                border: 'none',
                ...style 
            }} 
        />
    );
};

// --- Child Components ---

const getPaymentType = (order) => {
    const gateways = (order?.payment_gateway_names || []).map(g => g.toLowerCase());
    const joined = gateways.join(' ');
    const financialStatus = (order?.financial_status || '').toLowerCase();

    // 1. COD logic matching backend fallback
    if (joined.includes('cash_on_delivery') || joined.includes('cash on delivery') || financialStatus === 'pending') {
        return 'cod';
    }
    
    // 2. PPCOD / Partial logic matching backend fallback
    if (joined.includes('gokwik ppcod') || joined.includes('ppcod') || joined.includes('partially paid') || financialStatus.includes('partially')) {
        return 'ppcod';
    }

    // 3. Prepaid fallback
    return 'prepaid';
};

const PicklistModal = ({ open, onClose, orders, onApply, selectedBatchData }) => {
    const aggregatedItems = useMemo(() => {
        if (!orders || orders.length === 0) return [];
        const productMap = new Map();
        orders.forEach(order => (order.line_items || []).forEach(item => {
            const sku = item.sku || 'NO-SKU';
            if (productMap.has(sku)) {
                productMap.get(sku).totalQuantity += item.quantity;
            } else {
                productMap.set(sku, { sku: sku, title: item.title, totalQuantity: item.quantity });
            }
        }));
        return Array.from(productMap.values()).sort((a, b) => (a.sku || '').localeCompare(b.sku || ''));
    }, [orders]);

    const batchSummary = useMemo(() => {
        if (!selectedBatchData || selectedBatchData.length === 0) return [];
        return selectedBatchData.map(batch => {
            const batchOrders = batch.orders || [];
            let cod = 0, ppcod = 0, prepaid = 0;
            batchOrders.forEach(order => {
                const paymentType = getPaymentType(order);
                if (paymentType === 'cod') cod++;
                else if (paymentType === 'ppcod') ppcod++;
                else prepaid++;
            });
            return { id: batch.id, created_at: batch.created_at, total: batchOrders.length, cod, ppcod, prepaid };
        });
    }, [selectedBatchData]);

    const totals = useMemo(() => {
        return batchSummary.reduce((acc, batch) => ({
            total: acc.total + batch.total,
            cod: acc.cod + batch.cod,
            ppcod: acc.ppcod + batch.ppcod,
            prepaid: acc.prepaid + batch.prepaid
        }), { total: 0, cod: 0, ppcod: 0, prepaid: 0 });
    }, [batchSummary]);

    const [availableQuantities, setAvailableQuantities] = useState({});
    const handleQuantityChange = (sku, value) => {
        const newQuantities = { ...availableQuantities };
        const numericValue = parseInt(value, 10);
        if (!isNaN(numericValue) && numericValue >= 0) { newQuantities[sku] = numericValue; } else { delete newQuantities[sku]; }
        setAvailableQuantities(newQuantities);
    };
    const handleClose = () => { onApply(availableQuantities); onClose(); };
    const handlePrint = () => window.print();

    const handleExportWithInventory = () => {
        if (aggregatedItems.length === 0) return;
        const formatCsvField = (field) => `"${String(field || '').replace(/"/g, '""')}"`;
        const headers = ["SKU", "Product Name", "Qty Needed", "Available", "Shortfall"];
        const csvRows = [headers.join(",")];
        aggregatedItems.forEach(item => {
            const available = availableQuantities[item.sku];
            const availableStr = available !== undefined ? available : '';
            const shortfall = available !== undefined ? Math.max(0, item.totalQuantity - available) : '';
            csvRows.push([
                formatCsvField(item.sku), formatCsvField(item.title),
                item.totalQuantity, availableStr, shortfall
            ].join(","));
        });
        const blob = new Blob([csvRows.join("\n")], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.setAttribute("download", `picklist_inventory_${new Date().toISOString().split('T')[0]}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    return (
        <Dialog open={open} onClose={handleClose} fullWidth maxWidth="md" sx={{
            '@media print': {
                '& .MuiDialog-paper': { m: 0, maxWidth: '100%', width: '100%', boxShadow: 'none', overflow: 'visible', maxHeight: 'none' },
                '& .MuiBackdrop-root': { display: 'none' },
                '& .MuiDialog-container': { height: 'auto', overflow: 'visible' }
            }
        }}>
            <style type="text/css" media="print">
                {`
                    @page { size: auto; margin: 8mm; }
                    body { -webkit-print-color-adjust: exact; background-color: white !important; }
                    body * { visibility: hidden; }
                    .print-section, .print-section * { visibility: visible; }
                    .print-section { position: absolute; left: 0; top: 0; width: 100%; }
                    .no-print { display: none !important; }
                    table { page-break-inside: auto; }
                    tr { page-break-inside: avoid; page-break-after: auto; }
                    thead { display: table-header-group; }
                    /* Style tweaks for print to make it look professional */
                    .MuiTableContainer-root { box-shadow: none !important; border: 1px solid #ddd; }
                    .MuiTableCell-root { border-bottom: 1px solid #ddd !important; }
                    /* Make input box cleaner in print */
                    input[type="number"] { border: 1px solid #aaa; text-align: center; border-radius: 4px; }
                `}
            </style>
            
            <Box className="print-section">
                <DialogTitle sx={{ py: 1, px: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', borderBottom: '1px solid #eaeaea', mb: 1 }}>
                    <Typography variant="h6" sx={{ fontWeight: 700, color: '#333', mb: 0 }}>Daily Picklist - Stock Check</Typography>
                    <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 500 }}>
                        Generated: {new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </Typography>
                </DialogTitle>
                
                <DialogContent sx={{ py: 0.5, px: 2, overflow: 'visible' }}>
                    {batchSummary.length > 0 && (
                        <TableContainer component={Paper} elevation={0} sx={{ mb: 2, border: '1px solid #e0e0e0', borderRadius: '4px' }}>
                            <Typography variant="body2" sx={{ py: 0.5, px: 1, fontWeight: 700, bgcolor: 'primary.main', color: 'white', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                Batch Summary
                            </Typography>
                            <Table size="small" sx={{ '& td, & th': { py: 0.5, px: 1, fontSize: '0.8rem' } }}>
                                <TableHead>
                                    <TableRow sx={{ bgcolor: 'action.hover' }}>
                                        <TableCell sx={{ fontWeight: 700, color: 'text.primary', fontSize: '0.8rem' }}>Batch #</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 700, color: 'text.primary', fontSize: '0.8rem' }}>Total AWBs</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 700, color: 'text.primary', fontSize: '0.8rem' }}>COD</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 700, color: 'text.primary', fontSize: '0.8rem' }}>PPCOD</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 700, color: 'text.primary', fontSize: '0.8rem' }}>Prepaid</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {batchSummary.map(batch => (
                                        <TableRow key={batch.id} hover>
                                            <TableCell sx={{ fontWeight: 600, fontSize: '0.8rem' }}>
                                                Batch #{batch.id} <Typography component="span" variant="caption" sx={{ color: 'text.secondary', ml: 0.5 }}>({batch.created_at ? new Date(batch.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : ''})</Typography>
                                            </TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 500, fontSize: '0.8rem' }}>{batch.total}</TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 500, fontSize: '0.8rem' }}>{batch.cod}</TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 500, fontSize: '0.8rem' }}>{batch.ppcod}</TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 500, fontSize: '0.8rem' }}>{batch.prepaid}</TableCell>
                                        </TableRow>
                                    ))}
                                    <TableRow sx={{ bgcolor: 'action.hover' }}>
                                        <TableCell sx={{ fontWeight: 800, fontSize: '0.8rem' }}>TOTAL</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 800, fontSize: '0.8rem' }}>{totals.total}</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 800, fontSize: '0.8rem' }}>{totals.cod}</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 800, fontSize: '0.8rem' }}>{totals.ppcod}</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 800, fontSize: '0.8rem' }}>{totals.prepaid}</TableCell>
                                    </TableRow>
                                </TableBody>
                            </Table>
                        </TableContainer>
                    )}
                    
                    <Typography variant="body2" sx={{ fontWeight: 700, mb: 0.5, color: 'text.primary', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <InventoryIcon sx={{ fontSize: '1.2rem' }} color="primary" /> SKU Picklist ({aggregatedItems.length} items)
                    </Typography>
                    <TableContainer component={Paper} elevation={0} sx={{ border: '1px solid #e0e0e0', borderRadius: '4px' }}>
                        <Table size="small" sx={{ '& td, & th': { py: 0.25, px: 1 } }}>
                            <TableHead>
                                <TableRow sx={{ bgcolor: 'action.hover' }}>
                                    <TableCell sx={{ fontWeight: 700, color: 'text.primary', width: '20%', fontSize: '0.75rem' }}>SKU</TableCell>
                                    <TableCell sx={{ fontWeight: 700, color: 'text.primary', width: '50%', fontSize: '0.75rem' }}>Product</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 700, color: 'text.primary', width: '15%', fontSize: '0.75rem' }}>Needed</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 700, color: 'text.primary', width: '15%', fontSize: '0.75rem' }}>Available</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {aggregatedItems.map(item => (
                                    <TableRow key={item.sku} hover>
                                        <TableCell sx={{ fontWeight: 600, color: 'primary.dark', fontSize: '0.75rem' }}>{item.sku}</TableCell>
                                        <TableCell sx={{ color: 'text.secondary', fontWeight: 500, fontSize: '0.75rem' }}>{item.title}</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 800, fontSize: '0.85rem', color: '#d32f2f' }}>{item.totalQuantity}</TableCell>
                                        <TableCell align="center">
                                            <TextField 
                                                type="number" 
                                                size="small" 
                                                variant="outlined"
                                                sx={{ 
                                                    width: '60px', 
                                                    '& input': { py: 0.25, px: 0.5, textAlign: 'center', fontWeight: 'bold', fontSize: '0.8rem' } 
                                                }} 
                                                onChange={e => handleQuantityChange(item.sku, e.target.value)} 
                                            />
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </DialogContent>
            </Box>
            <DialogActions sx={{ py: 2, px: 3, borderTop: '1px solid #eee' }} className="no-print">
                <Button onClick={handleExportWithInventory} variant="outlined" color="secondary" startIcon={<FileDownloadIcon />} disabled={aggregatedItems.length === 0}>Export CSV</Button>
                <Button onClick={handlePrint} variant="outlined" color="primary" startIcon={<PrintIcon />}>Print Picklist</Button>
                <Box sx={{ flexGrow: 1 }} />
                <Button onClick={handleClose} variant="contained" color="primary" disableElevation>Apply Stock</Button>
            </DialogActions>
        </Dialog>
    );
};

// --- NEW COMPONENT: Scan Fulfillment Dialog (Updated with Revert Logic) ---
const ScanFulfillDialog = ({ open, onClose, users, onConfirm, onBulkAction, allBatches }) => {
    const [scannedAWB, setScannedAWB] = useState("");
    const [scannedOrders, setScannedOrders] = useState([]);
    const [lastScanned, setLastScanned] = useState(null);
    const [selectedUser, setSelectedUser] = useState("");
    const [error, setError] = useState(null);
    const [isSearching, setIsSearching] = useState(false);
    const [isReverting, setIsReverting] = useState(false);
    // Track original status and reason to restore later if cancelled
    const [originalStatuses, setOriginalStatuses] = useState({}); 

    const inputRef = useRef(null);

    useEffect(() => {
        if (open) {
            setTimeout(() => inputRef.current?.focus(), 100);
        }
    }, [open, scannedOrders]);

    const handleScan = (e) => {
        if (e.key === 'Enter') {
            processScan(scannedAWB);
        }
    };

    const processScan = async (input) => {
        const trimmed = input.trim();
        if (!trimmed) return;

        // Extract multiple AWBs
        const awbsToLookup = trimmed.split(',').map(s => s.trim()).filter(Boolean);

        // Filter out already scanned AWBs locally
        const newAwbs = awbsToLookup.filter(awb => !scannedOrders.find(o => isOrderMatch(o, awb)));

        if (newAwbs.length === 0) {
            setError("Already scanned!");
            setScannedAWB("");
            setTimeout(() => inputRef.current?.focus(), 50);
            return;
        }

        setIsSearching(true);
        setError(null);

        try {
            // FIRE BULK ACTION TO BACKEND
            const result = await onBulkAction(newAwbs, "fulfill");

            if (result && result.updated_orders) {
                // Capture original status from allBatches for newly scanned orders
                const newOriginals = {};
                result.updated_orders.forEach(order => {
                    const orderNum = String(order.order_number);
                    if (!originalStatuses[orderNum]) {
                        // Find in allBatches
                        let foundStatus = 'Pending';
                        let foundReason = '';
                        allBatches.some(batch => {
                            const match = (batch.orders || []).find(o => String(o.order_number) === orderNum);
                            if (match) {
                                foundStatus = match.internal_fulfillment_status;
                                foundReason = match.fulfillment_reason || '';
                                return true;
                            }
                            return false;
                        });
                        newOriginals[orderNum] = { status: foundStatus, reason: foundReason };
                    }
                });
                setOriginalStatuses(prev => ({ ...prev, ...newOriginals }));

                setScannedOrders(prev => [...result.updated_orders, ...prev]);
                if (result.updated_orders.length > 0) {
                    setLastScanned(result.updated_orders[0]);
                }
            }

            let errorMessages = [];
            if (result && result.already_scanned && result.already_scanned.length > 0) {
                const scannedLogs = result.already_scanned.map(o => `${o.awb_number || o.order_number} (${o.status})`).join(', ');
                errorMessages.push(`Already Scanned: ${scannedLogs}`);
            }
            if (result && result.not_found && result.not_found.length > 0) {
                errorMessages.push(`Not found: ${result.not_found.join(', ')}`);
            }
            
            if (errorMessages.length > 0) {
                setError(errorMessages.join(' | '));
            } else {
                setError(null);
            }
        } catch (e) {
            setError(`Error updating status: ${e.message}`);
        } finally {
            setIsSearching(false);
            setScannedAWB("");
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    };

    // >>> Handle Cancel / Revert Logic <<<
    const handleCancel = async () => {
        if (scannedOrders.length > 0) {
            const confirmCancel = window.confirm(`You have scanned ${scannedOrders.length} orders. Cancelling will unmark them from "Fulfilled". Are you sure?`);
            if (!confirmCancel) return;

            setIsReverting(true);
            try {
                // Revert all scanned orders back to their specific original status
                const awbsToRevert = scannedOrders.map(o => o.order_number);
                await onBulkAction(awbsToRevert, "revert", { revert_to_statuses: originalStatuses });
            } catch (e) {
                console.error("Error reverting:", e);
                alert("Some orders might not have been reverted correctly. Please check manually.");
            }
            setIsReverting(false);
        }
        // Clear state and close
        setScannedOrders([]);
        setOriginalStatuses({});
        setScannedAWB("");
        setLastScanned(null);
        onClose();
    };

    const handleComplete = async () => {
        if (!selectedUser) {
            alert("Please select a user to assign these orders to.");
            return;
        }
        const orderIds = scannedOrders.map(o => o.order_number);
        setIsSearching(true); // Reuse searching state for button loading
        try {
            await onConfirm(orderIds, selectedUser);
            // Reset local scan state after success so we don't revert them on next open
            setScannedOrders([]);
            setOriginalStatuses({});
        } catch (e) {
            console.error("Complete failed:", e);
            // Error is handled by snackbar in parent, so we just don't clear state here
        } finally {
            setIsSearching(false);
        }
    };

    return (
        <Dialog open={open} onClose={null} maxWidth="md" fullWidth> {/* Disable backdrop click close */}
            <DialogTitle>Scan Orders to Fulfill</DialogTitle>
            <DialogContent>
                {isReverting ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 4 }}>
                        <CircularProgress />
                        <Typography sx={{ mt: 2 }}>Reverting scanned orders...</Typography>
                    </Box>
                ) : (
                    <>
                        <Box sx={{ mb: 2, mt: 1 }}>
                            <TextField
                                inputRef={inputRef}
                                autoFocus
                                fullWidth
                                multiline
                                rows={4}
                                disabled={isSearching}
                                label={isSearching ? "Processing AWBs..." : "Scan AWB or Order Number"}
                                value={scannedAWB}
                                onChange={(e) => setScannedAWB(e.target.value)}
                                onKeyDown={handleScan}
                                helperText="Press Enter after scanning | Paste comma-separated AWBs for bulk processing"
                                sx={{ mb: 2 }}
                            />

                            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                            {lastScanned && (
                                <Paper elevation={3} sx={{ p: 2, bgcolor: 'rgba(76, 175, 80, 0.1)', border: '1px solid rgba(76, 175, 80, 0.3)', mb: 2 }}>
                                    <Typography variant="subtitle2" color="success.main" gutterBottom>Successfully Scanned & Fulfilled:</Typography>
                                    <Grid container spacing={2}>
                                        <Grid item xs={3}>
                                            <Typography variant="caption" display="block">Order #</Typography>
                                            <Typography variant="h6" fontWeight="bold">{lastScanned.order_number}</Typography>
                                        </Grid>
                                        <Grid item xs={3}>
                                            <Typography variant="caption" display="block">Customer</Typography>
                                            <Typography variant="body1">{lastScanned.customer_first_name} {lastScanned.customer_last_name}</Typography>
                                        </Grid>
                                        <Grid item xs={3}>
                                            <Typography variant="caption" display="block">Tracking / AWB</Typography>
                                            <Typography variant="body1" fontWeight="bold" color="primary">{getDisplayTracking(lastScanned)}</Typography>
                                        </Grid>
                                        <Grid item xs={3}>
                                            <Typography variant="caption" display="block">Items</Typography>
                                            <Typography variant="body2">
                                                {(lastScanned.line_items || []).map(i => `${i.title} (x${i.quantity})`).join(', ')}
                                            </Typography>
                                        </Grid>
                                    </Grid>
                                </Paper>
                            )}
                        </Box>

                        <Divider />

                        <Box sx={{ height: '250px', overflowY: 'auto', mt: 2, border: '1px solid #eee', borderRadius: 1 }}>
                            <Table size="small" stickyHeader>
                                <TableHead>
                                    <TableRow>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Order #</TableCell>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Customer</TableCell>
                                        <TableCell sx={{ fontWeight: 'bold' }}>AWB / Tracking</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {scannedOrders.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={3} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                                                No orders scanned yet.
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        scannedOrders.map(order => (
                                            <TableRow key={order.order_number}>
                                                <TableCell>{order.order_number}</TableCell>
                                                <TableCell>{order.customer_first_name} {order.customer_last_name}</TableCell>
                                                <TableCell>{getDisplayTracking(order)}</TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </Box>

                        <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Typography variant="body2" fontWeight="bold">Total Scanned: {scannedOrders.length}</Typography>
                            <FormControl size="small" sx={{ flex: 1 }}>
                                <InputLabel>Assign To (Packaging Agent)</InputLabel>
                                <Select
                                    value={selectedUser}
                                    label="Assign To (Packaging Agent)"
                                    onChange={(e) => setSelectedUser(e.target.value)}
                                >
                                    {users.map(u => (
                                        <MenuItem key={u.id} value={u.id} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: 1 }}>
                                            <span>{u.username}</span>
                                            {renderStatusChip(u.today_status, u.work_mode)}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Box>
                    </>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={handleCancel} disabled={isReverting}>Cancel</Button>
                <Button
                    onClick={handleComplete}
                    variant="contained"
                    color="primary"
                    disabled={scannedOrders.length === 0 || !selectedUser || isReverting}
                >
                    Send to Packaging ({scannedOrders.length})
                </Button>
            </DialogActions>
        </Dialog>
    );
};


// --- NEW COMPONENT: Bulk Scan & Accumulate Dialog ---
const BulkScanAccumulateDialog = ({ open, onClose, users, onConfirm, onBulkAction, allBatches }) => {
    const [scannedText, setScannedText] = useState("");
    const [scannedOrders, setScannedOrders] = useState([]);
    const [selectedUser, setSelectedUser] = useState("");
    const [error, setError] = useState(null);
    const [isSearching, setIsSearching] = useState(false);
    const [originalStatuses, setOriginalStatuses] = useState({});

    const inputRef = useRef(null);

    useEffect(() => {
        if (open) {
            setScannedText("");
            setScannedOrders([]);
            setOriginalStatuses({});
            setSelectedUser("");
            setError(null);
            setTimeout(() => inputRef.current?.focus(), 100);
        }
    }, [open]);

    const handleKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const val = scannedText.trim();
            if (!val) return;

            // If the trimmed text ends with a comma, it indicates the user wants to process.
            if (val.endsWith(',')) {
                processBulkFulfill();
            } else {
                // Otherwise, append a comma and space for the next scan
                setScannedText(prev => {
                    const trimmedPrev = prev.trim();
                    return trimmedPrev ? `${trimmedPrev}, ` : '';
                });
            }
        }
    };

    const processBulkFulfill = async () => {
        const trimmed = scannedText.trim();
        // Extract AWBs, filter out empty ones
        const awbsToLookup = trimmed.split(',').map(s => s.trim()).filter(Boolean);

        if (awbsToLookup.length === 0) {
            setError("No AWBs entered/scanned!");
            return;
        }

        setIsSearching(true);
        setError(null);

        try {
            // FIRE BULK ACTION TO BACKEND AT ONCE
            const result = await onBulkAction(awbsToLookup, "fulfill");

            if (result && result.updated_orders) {
                // Capture original status from allBatches for newly scanned orders
                const newOriginals = {};
                result.updated_orders.forEach(order => {
                    const orderNum = String(order.order_number);
                    if (!originalStatuses[orderNum]) {
                        let foundStatus = 'Pending';
                        let foundReason = '';
                        allBatches.some(batch => {
                            const match = (batch.orders || []).find(o => String(o.order_number) === orderNum);
                            if (match) {
                                foundStatus = match.internal_fulfillment_status;
                                foundReason = match.fulfillment_reason || '';
                                return true;
                            }
                            return false;
                        });
                        newOriginals[orderNum] = { status: foundStatus, reason: foundReason };
                    }
                });
                setOriginalStatuses(prev => ({ ...prev, ...newOriginals }));
                setScannedOrders(result.updated_orders);
            }

            let errorMessages = [];
            if (result && result.already_scanned && result.already_scanned.length > 0) {
                const scannedLogs = result.already_scanned.map(o => `${o.awb_number || o.order_number} (${o.status})`).join(', ');
                errorMessages.push(`Already Scanned: ${scannedLogs}`);
            }
            if (result && result.not_found && result.not_found.length > 0) {
                errorMessages.push(`Not found: ${result.not_found.join(', ')}`);
            }
            
            if (errorMessages.length > 0) {
                setError(errorMessages.join(' | '));
            } else {
                setError(null);
            }
        } catch (e) {
            setError(`Error updating status: ${e.message}`);
        } finally {
            setIsSearching(false);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    };

    const handleCancel = async () => {
        if (scannedOrders.length > 0) {
            const confirmCancel = window.confirm(`You have processed ${scannedOrders.length} orders. Cancelling will unmark them from "Fulfilled". Are you sure?`);
            if (!confirmCancel) return;

            setIsSearching(true);
            try {
                const awbsToRevert = scannedOrders.map(o => o.order_number);
                await onBulkAction(awbsToRevert, "revert", { revert_to_statuses: originalStatuses });
            } catch (e) {
                console.error("Error reverting:", e);
                alert("Some orders might not have been reverted correctly. Please check manually.");
            }
            setIsSearching(false);
        }
        setScannedOrders([]);
        setOriginalStatuses({});
        setScannedText("");
        onClose();
    };

    const handleComplete = async () => {
        if (!selectedUser) {
            alert("Please select a user to assign these orders to.");
            return;
        }
        const orderIds = scannedOrders.map(o => o.order_number);
        setIsSearching(true);
        try {
            await onConfirm(orderIds, selectedUser);
            setScannedOrders([]);
            setOriginalStatuses({});
            setScannedText("");
            onClose();
        } catch (e) {
            console.error("Complete failed:", e);
        } finally {
            setIsSearching(false);
        }
    };

    return (
        <Dialog open={open} onClose={null} maxWidth="md" fullWidth>
            <DialogTitle>Scan & Accumulate (Bulk Fulfill)</DialogTitle>
            <DialogContent>
                <Box sx={{ mb: 2, mt: 1 }}>
                    <TextField
                        inputRef={inputRef}
                        autoFocus
                        fullWidth
                        multiline
                        rows={4}
                        disabled={isSearching}
                        label={isSearching ? "Processing AWBs..." : "Scan AWBs (Comma separated)"}
                        value={scannedText}
                        onChange={(e) => setScannedText(e.target.value)}
                        onKeyDown={handleKeyDown}
                        helperText="Scanner will automatically append a comma after each scan. Press Enter again at the end to process all at once."
                        sx={{ mb: 2 }}
                    />

                    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                </Box>


                {scannedOrders.length > 0 && (
                    <>
                        <Divider />
                        <Typography variant="subtitle2" color="success.main" sx={{ mt: 2, mb: 1 }}>
                            Processed Orders ({scannedOrders.length}):
                        </Typography>
                        <Box sx={{ height: '200px', overflowY: 'auto', border: '1px solid #eee', borderRadius: 1 }}>
                            <Table size="small" stickyHeader>
                                <TableHead>
                                    <TableRow>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Order #</TableCell>
                                        <TableCell sx={{ fontWeight: 'bold' }}>Customer</TableCell>
                                        <TableCell sx={{ fontWeight: 'bold' }}>AWB / Tracking</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {scannedOrders.map(order => (
                                        <TableRow key={order.order_number}>
                                            <TableCell>{order.order_number}</TableCell>
                                            <TableCell>{order.customer_first_name} {order.customer_last_name}</TableCell>
                                            <TableCell>{getDisplayTracking(order)}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </Box>

                        <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
                            <FormControl size="small" sx={{ flex: 1 }}>
                                <InputLabel>Assign To (Packaging Agent)</InputLabel>
                                <Select
                                    value={selectedUser}
                                    label="Assign To (Packaging Agent)"
                                    onChange={(e) => setSelectedUser(e.target.value)}
                                >
                                    {users.map(u => (
                                        <MenuItem key={u.id} value={u.id} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: 1 }}>
                                            <span>{u.username}</span>
                                            {renderStatusChip(u.today_status, u.work_mode)}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        </Box>
                    </>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={handleCancel} disabled={isSearching}>Cancel</Button>
                <Button
                    onClick={handleComplete}
                    variant="contained"
                    color="primary"
                    disabled={scannedOrders.length === 0 || !selectedUser || isSearching}
                >
                    Send to Packaging ({scannedOrders.length})
                </Button>
            </DialogActions>
        </Dialog>
    );
};


// --- Main Component ---
export const OrderConfirmation = ({ cacheData, setCacheData }) => {
    // ... [State declarations identical to previous] ...
    const [allBatches, setAllBatches] = useState(cacheData || []);
    const [loading, setLoading] = useState(!cacheData);
    const [startDate, setStartDate] = useState(getLocalDate());
    const [endDate, setEndDate] = useState(getLocalDate());
    const [searchText, setSearchText] = useState("");
    const [isPicklistOpen, setPicklistOpen] = useState(false);
    const [availableQuantities, setAvailableQuantities] = useState({});
    const [selectedBatches, setSelectedBatches] = useState([]);
    const [agents, setAgents] = useState([]);
    const [selectedAgent, setSelectedAgent] = useState('');
    const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });
    const [error, setError] = useState(null);
    const [fulfilledSet, setFulfilledSet] = useState(new Set());
    const [scanDialogOpen, setScanDialogOpen] = useState(false);
    const [bulkScanDialogOpen, setBulkScanDialogOpen] = useState(false);
    const [dailyStats, setDailyStats] = useState({
        count: 0, amount: 0, cod_count: 0, cod_amount: 0,
        ppcod_count: 0, ppcod_amount: 0, prepaid_count: 0, prepaid_amount: 0
    });
    const [fulfillAnchorEl, setFulfillAnchorEl] = useState(null);
    const [exportAnchorEl, setExportAnchorEl] = useState(null);
    const { canViewAmounts, canExport, canCreate, canEdit } = usePagePermissions();
    const canModify = canCreate || canEdit;

    const apiFetch = async (endpoint, options = {}) => {
        const defaultOptions = { credentials: 'include', headers: { 'Content-Type': 'application/json' } };
        const mergedOptions = { ...defaultOptions, ...options };
        mergedOptions.headers = { ...defaultOptions.headers, ...options.headers };
        if (options.body) mergedOptions.body = JSON.stringify(options.body);
        const url = endpoint.startsWith('http') ? endpoint : `${BACKEND_URL}${endpoint}`;
        const res = await apiClient(url, mergedOptions);
        if (!res.ok) {
            let errorDetail = `Request failed: ${res.status}`;
            try {
                const rawText = await res.text(); // Read body ONCE as text
                try {
                    const errorData = JSON.parse(rawText);
                    errorDetail = errorData.detail || errorData.error || rawText.substring(0, 200);
                } catch {
                    errorDetail = rawText.substring(0, 200);
                }
            } catch { /* body could not be read at all */ }
            throw new Error(errorDetail);
        }
        if (res.status === 204) return { success: true };
        return res.json();
    };

    const fetchBatches = async (startDateParam = null, endDateParam = null, searchParam = null) => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            if (searchParam) params.append('search', searchParam);
            else {
                if (startDateParam) params.append('start_date', startDateParam);
                if (endDateParam) params.append('end_date', endDateParam);
            }
            const queryString = params.toString();
            const endpoint = `/api/batches/${queryString ? `?${queryString}` : ''}`;
            const data = await apiFetch(endpoint);
            if (Array.isArray(data)) { setAllBatches(data); if (setCacheData) setCacheData(data); }
            else { setAllBatches([]); }
        } catch (err) { console.error("Failed to fetch batches:", err); setError(err.message); }
        finally { setLoading(false); }
    };

    const fetchAgents = async () => {
        try { const data = await apiFetch("/api/users/"); setAgents(data); }
        catch (err) { console.error("Failed to fetch agents:", err); }
    };

    const fetchDailyStats = async () => {
        try {
            const data = await apiFetch("/api/orders/confirmation-stats/");
            if (data && data.today_stats) {
                setDailyStats(data.today_stats);
            } else if (data && data.stats) {
                setDailyStats(data.stats);
            }
        } catch (err) {
            console.error("Failed to fetch daily stats:", err);
        }
    };

    useEffect(() => { 
        fetchBatches(startDate, endDate, null); 
        fetchAgents(); 
        fetchDailyStats();
    }, []);
    useEffect(() => { if (!searchText) fetchBatches(startDate, endDate, null); }, [startDate, endDate]);
    useEffect(() => {
        const timeoutId = setTimeout(() => {
            if (searchText.trim()) fetchBatches(null, null, searchText.trim());
            else fetchBatches(startDate, endDate, null);
        }, 500);
        return () => clearTimeout(timeoutId);
    }, [searchText]);

    useEffect(() => {
        if (allBatches.length > 0) {
            setFulfilledSet(prev => {
                // IMPORTANT: Rebuild the set to reflect current state of allBatches correctly
                // This prevents "sticky" fulfilled states when an action is cancelled/reverted
                const next = new Set();
                allBatches.forEach(batch => {
                    (batch.orders || []).forEach(o => {
                        if (o.internal_fulfillment_status === 'Fulfilled') { 
                            next.add(String(o.order_number)); 
                        }
                    });
                });
                return next;
            });
        }
    }, [allBatches]);

    const updateBatchesState = (newBatches) => { setAllBatches(newBatches); if (setCacheData) setCacheData(newBatches); };

    const updateOrderOnBackend = async (orderNumber, payload) => {

        try { await apiFetch(`/api/orders/${orderNumber}/update/`, { method: 'PATCH', body: payload }); }
        catch (err) {
            console.error(`Failed to update order ${orderNumber}:`, err);
            setSnackbar({ open: true, message: `Failed to update Order #${orderNumber}: ${err.message}`, severity: 'error' });
            throw err;
        }
    };

    const performAutoFulfill = async (orderNumber) => {
        // --- Optimistic UI: update state INSTANTLY, then fire API in background ---
        setFulfilledSet(prev => new Set(prev).add(String(orderNumber)));
        const updatedBatches = allBatches.map(batch => ({
            ...batch,
            orders: batch.orders.map(order =>
                order.order_number === orderNumber
                    ? { ...order, internal_fulfillment_status: 'Fulfilled', fulfillment_reason: "" }
                    : order
            )
        }));
        updateBatchesState(updatedBatches);

        // Fire API in background — rollback on failure
        try {
            const payload = { internal_fulfillment_status: 'Fulfilled', fulfillment_reason: "" };
            await updateOrderOnBackend(orderNumber, payload);
            fetchDailyStats(); // refresh stats after successful save
        } catch (err) {
            // Rollback: undo the optimistic state
            setFulfilledSet(prev => {
                const next = new Set(prev);
                next.delete(String(orderNumber));
                return next;
            });
            const rolledBack = allBatches.map(batch => ({
                ...batch,
                orders: batch.orders.map(order =>
                    order.order_number === orderNumber
                        ? { ...order, internal_fulfillment_status: 'Pending', fulfillment_reason: "" }
                        : order
                )
            }));
            updateBatchesState(rolledBack);
        }
        return true;
    };

    const performAutoRevert = async (orderNumber) => {
        // --- Optimistic UI: update state INSTANTLY, then fire API in background ---
        setFulfilledSet(prev => {
            const next = new Set(prev);
            next.delete(String(orderNumber));
            return next;
        });
        const updatedBatches = allBatches.map(batch => ({
            ...batch,
            orders: batch.orders.map(order =>
                order.order_number === orderNumber
                    ? { ...order, internal_fulfillment_status: 'Pending', fulfillment_reason: "" }
                    : order
            )
        }));
        updateBatchesState(updatedBatches);

        // Fire API in background — rollback on failure
        try {
            const payload = { internal_fulfillment_status: 'Pending', fulfillment_reason: "" };
            await updateOrderOnBackend(orderNumber, payload);
            fetchDailyStats();
        } catch (err) {
            // Rollback: re-add to fulfilled set
            setFulfilledSet(prev => new Set(prev).add(String(orderNumber)));
            const rolledBack = allBatches.map(batch => ({
                ...batch,
                orders: batch.orders.map(order =>
                    order.order_number === orderNumber
                        ? { ...order, internal_fulfillment_status: 'Fulfilled', fulfillment_reason: "" }
                        : order
                )
            }));
            updateBatchesState(rolledBack);
        }
        return true;
    };

    const handleFulfilledChange = (orderNumber, checked) => {
        if (checked) {
            performAutoFulfill(orderNumber);
        } else {
            performAutoRevert(orderNumber);
        }
    };

    const performBulkAction = async (awbs, action, extraPayload = {}) => {
        try {
            const payload = { awbs, action, ...extraPayload };
            const data = await apiFetch(`/api/orders/bulk-scan-action/`, { method: 'POST', body: payload });

            if (data.updated_orders) {
                const updatedOrdersMap = new Map(data.updated_orders.map(o => [String(o.order_number), { status: o.internal_fulfillment_status, reason: o.fulfillment_reason }]));
                const updatedOrderNumbers = new Set(updatedOrdersMap.keys());

                setFulfilledSet(prev => {
                    const next = new Set(prev);
                    updatedOrderNumbers.forEach(num => {
                        if (action === 'fulfill') next.add(String(num));
                        else next.delete(String(num));
                    });
                    return next;
                });

                const updatedBatches = allBatches.map(batch => ({
                    ...batch,
                    orders: batch.orders.map(order =>
                        updatedOrderNumbers.has(String(order.order_number))
                            ? { ...order, internal_fulfillment_status: updatedOrdersMap.get(String(order.order_number)).status, fulfillment_reason: updatedOrdersMap.get(String(order.order_number)).reason }
                            : order
                    )
                }));
                updateBatchesState(updatedBatches);
                fetchDailyStats(); // Refresh global stats
            }
            return data;
        } catch (err) {
            console.error("Bulk action failed:", err);
            throw err;
        }
    };

    const handleReasonChange = (orderNumber, reason) => {
        const updatedBatches = allBatches.map(batch => ({ ...batch, orders: batch.orders.map(order => order.order_number === orderNumber ? { ...order, fulfillment_reason: reason } : order) }));
        updateBatchesState(updatedBatches);
        updateOrderOnBackend(orderNumber, { fulfillment_reason: reason });
    };

    const filteredBatches = useMemo(() => allBatches, [allBatches]);
    const allVisibleOrders = useMemo(() => filteredBatches.flatMap(batch => batch.orders || []), [filteredBatches]);

    const unfulfillableOrderIds = useMemo(() => {
        const unfulfillableIds = new Set();
        allVisibleOrders.forEach(order => {
            if ((order.line_items || []).some(item => {
                const needed = item.quantity;
                const available = availableQuantities[item.sku];
                return available !== undefined && available < needed;
            })) { unfulfillableIds.add(order.order_number); }
        });
        return unfulfillableIds;
    }, [allVisibleOrders, availableQuantities]);

    const ordersToPackage = useMemo(() => Array.from(fulfilledSet), [fulfilledSet]);

    const fulfillmentKpis = useMemo(() => {
        const fulfilledRows = allVisibleOrders.filter(row => row.internal_fulfillment_status === 'Fulfilled' || fulfilledSet.has(String(row.order_number)));
        const totalFulfilledAmount = fulfilledRows.reduce((sum, row) => sum + parseFloat(row.total_price || 0), 0);
        
        let codQty = 0, codAmount = 0;
        let ppcodQty = 0, ppcodAmount = 0;
        let prepaidQty = 0, prepaidAmount = 0;

        fulfilledRows.forEach(row => {
            const pt = getPaymentType(row);
            const amt = parseFloat(row.total_price || 0);
            if (pt === 'cod') {
                codQty++;
                codAmount += amt;
            } else if (pt === 'ppcod') {
                ppcodQty++;
                ppcodAmount += amt;
            } else {
                prepaidQty++;
                prepaidAmount += amt;
            }
        });

        return {
            totalOrders: allVisibleOrders.length, totalFulfilled: fulfilledRows.length, totalFulfilledAmount,
            codQty, codAmount,
            ppcodQty, ppcodAmount,
            prepaidQty, prepaidAmount,
        };
    }, [allVisibleOrders, fulfilledSet]);

    const handleBatchSelect = (batchId, checked) => setSelectedBatches(prev => checked ? [...prev, batchId] : prev.filter(id => id !== batchId));
    const ordersForPicklist = useMemo(() => selectedBatches.length === 0 ? [] : allBatches.filter(b => selectedBatches.includes(b.id)).flatMap(b => b.orders || []), [allBatches, selectedBatches]);
    const selectedBatchData = useMemo(() => allBatches.filter(b => selectedBatches.includes(b.id)), [allBatches, selectedBatches]);

    // --- Overview KPIs for the sidebar ---
    const overviewKpis = useMemo(() => {
        const ordersSource = selectedBatches.length > 0 ? ordersForPicklist : allVisibleOrders;
        let fulfilled = 0, pending = 0, onHold = 0;
        ordersSource.forEach(order => {
            const status = order.internal_fulfillment_status;
            if (status === 'Fulfilled' || fulfilledSet.has(String(order.order_number))) fulfilled++;
            else if (status === 'On Hold') onHold++;
            else pending++;
        });
        return { total: ordersSource.length, fulfilled, pending, onHold };
    }, [allVisibleOrders, ordersForPicklist, selectedBatches, fulfilledSet]);

    // --- Shipping Company Breakdown for the sidebar ---
    const shippingSummary = useMemo(() => {
        const ordersSource = selectedBatches.length > 0 ? ordersForPicklist : allVisibleOrders;
        const courierMap = new Map();
        ordersSource.forEach(order => {
            let company = 'Unknown';
            if (order.fulfillments && order.fulfillments.length > 0) {
                const tracking = order.fulfillments[0]?.tracking_info;
                if (tracking && tracking.length > 0 && tracking[0].company) {
                    company = tracking[0].company;
                }
            }
            if (!courierMap.has(company)) {
                courierMap.set(company, { company, total: 0, cod: 0, ppcod: 0, prepaid: 0 });
            }
            const entry = courierMap.get(company);
            entry.total++;
            const pt = getPaymentType(order);
            if (pt === 'cod') entry.cod++;
            else if (pt === 'ppcod') entry.ppcod++;
            else entry.prepaid++;
        });
        const rows = Array.from(courierMap.values()).sort((a, b) => b.total - a.total);
        const totals = rows.reduce((acc, r) => ({
            total: acc.total + r.total, cod: acc.cod + r.cod,
            ppcod: acc.ppcod + r.ppcod, prepaid: acc.prepaid + r.prepaid
        }), { total: 0, cod: 0, ppcod: 0, prepaid: 0 });
        return { rows, totals };
    }, [allVisibleOrders, ordersForPicklist, selectedBatches]);

    // --- Payment summary with unfulfilled counts for the sidebar ---
    const paymentSummary = useMemo(() => {
        const ordersSource = selectedBatches.length > 0 ? ordersForPicklist : allVisibleOrders;
        let codUnfulfilled = 0, ppcodUnfulfilled = 0, prepaidUnfulfilled = 0;
        ordersSource.forEach(order => {
            const isFulfilled = order.internal_fulfillment_status === 'Fulfilled' || fulfilledSet.has(String(order.order_number));
            if (!isFulfilled) {
                const pt = getPaymentType(order);
                if (pt === 'cod') codUnfulfilled++;
                else if (pt === 'ppcod') ppcodUnfulfilled++;
                else prepaidUnfulfilled++;
            }
        });
        return { codUnfulfilled, ppcodUnfulfilled, prepaidUnfulfilled, totalUnfulfilled: codUnfulfilled + ppcodUnfulfilled + prepaidUnfulfilled };
    }, [allVisibleOrders, ordersForPicklist, selectedBatches, fulfilledSet]);

    const handleCreatePackagingBatch = async () => {
        if (ordersToPackage.length === 0) return setSnackbar({ open: true, message: "No orders are marked as 'Fulfilled'.", severity: 'warning' });
        if (!selectedAgent) return setSnackbar({ open: true, message: "Please select an agent to assign the batch to.", severity: 'warning' });

        try {
            const result = await apiFetch("/api/packaging-batches/create/", { method: 'POST', body: { order_numbers: ordersToPackage, assigned_to_id: selectedAgent } });
            setSnackbar({ open: true, message: `Successfully created Batch #${result.batch_id} with ${result.orders_in_batch} orders.`, severity: 'success' });
            setFulfilledSet(new Set());
            await fetchBatches(startDate, endDate);
            await fetchDailyStats();
            setSelectedAgent('');
        } catch (err) { setSnackbar({ open: true, message: err.message, severity: 'error' }); }
    };

    const handleFulfillMenuClick = (event) => setFulfillAnchorEl(event.currentTarget);
    const handleFulfillMenuClose = () => setFulfillAnchorEl(null);
    const handleOpenScanDialog = () => { handleFulfillMenuClose(); setScanDialogOpen(true); };
    const handleOpenBulkScanDialog = () => { handleFulfillMenuClose(); setBulkScanDialogOpen(true); };

    const handleScanLookup = async (input) => {
        const params = new URLSearchParams();
        params.append('search', input);
        const endpoint = `/api/batches/?${params.toString()}`;
        console.log("Scanning Global:", endpoint);
        const data = await apiFetch(endpoint);
        if (Array.isArray(data)) {
            const flatOrders = data.flatMap(b => b.orders || []);
            const found = flatOrders.find(o => isOrderMatch(o, input));
            return found || null;
        }
        return null;
    };

    const handleScanComplete = async (orderIds, userId) => {
        try {
            const result = await apiFetch("/api/packaging-batches/create/", {
                method: 'POST',
                body: { order_numbers: orderIds, assigned_to_id: userId }
            });
            setSnackbar({ open: true, message: `Successfully created Batch #${result.batch_id} via Scan!`, severity: 'success' });
            setScanDialogOpen(false);
            setFulfilledSet(new Set());
            await fetchBatches(startDate, endDate);
        } catch (e) {
            setSnackbar({ open: true, message: e.message, severity: 'error' });
        }
    };

    // --- HELPER: aggregate SKUs from selected batches ---
    const getAggregatedItems = () => {
        const productMap = new Map();
        ordersForPicklist.forEach(order => (order.line_items || []).forEach(item => {
            const sku = item.sku || 'NO-SKU';
            if (productMap.has(sku)) {
                productMap.get(sku).totalQuantity += item.quantity;
            } else {
                productMap.set(sku, { sku: sku, title: item.title, totalQuantity: item.quantity });
            }
        }));
        return Array.from(productMap.values()).sort((a, b) => (a.sku || '').localeCompare(b.sku || ''));
    };
    const formatCsvField = (field) => `"${String(field || '').replace(/"/g, '""')}"`;
    const downloadCsv = (csvRows, filename) => {
        const blob = new Blob([csvRows.join("\n")], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.setAttribute("download", filename);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // --- EXPORT TYPE 1: Print List with Batch Info ---
    const handleExportWithBatchInfo = () => {
        if (ordersForPicklist.length === 0) return;
        setExportAnchorEl(null);
        const csvRows = [];
        // Section 1: Batch Summary
        csvRows.push("=== BATCH SUMMARY ===");
        csvRows.push(["Batch #", "Date", "Total AWBs", "COD", "PPCOD", "Prepaid"].join(","));
        const batchesData = allBatches.filter(b => selectedBatches.includes(b.id));
        let grandTotal = 0, grandCod = 0, grandPpcod = 0, grandPrepaid = 0;
        batchesData.forEach(batch => {
            const orders = batch.orders || [];
            let cod = 0, ppcod = 0, prepaid = 0;
            orders.forEach(order => {
                const pt = getPaymentType(order);
                if (pt === 'cod') cod++;
                else if (pt === 'ppcod') ppcod++;
                else prepaid++;
            });
            const dateStr = batch.created_at ? new Date(batch.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '';
            csvRows.push([`Batch #${batch.id}`, dateStr, orders.length, cod, ppcod, prepaid].join(","));
            grandTotal += orders.length; grandCod += cod; grandPpcod += ppcod; grandPrepaid += prepaid;
        });
        csvRows.push(["TOTAL", "", grandTotal, grandCod, grandPpcod, grandPrepaid].join(","));
        csvRows.push("");
        // Section 2: SKU Picklist
        csvRows.push("=== SKU PICKLIST ===");
        csvRows.push(["SKU", "Product Name", "Qty Needed"].join(","));
        getAggregatedItems().forEach(item => {
            csvRows.push([formatCsvField(item.sku), formatCsvField(item.title), item.totalQuantity].join(","));
        });
        downloadCsv(csvRows, `picklist_batch_info_${new Date().toISOString().split('T')[0]}.csv`);
    };

    // --- EXPORT TYPE 2: SKUs Only ---
    const handleExportSKUOnly = () => {
        if (ordersForPicklist.length === 0) return;
        setExportAnchorEl(null);
        const csvRows = [["SKU", "Qty Needed"].join(",")];
        getAggregatedItems().forEach(item => {
            csvRows.push([formatCsvField(item.sku), item.totalQuantity].join(","));
        });
        downloadCsv(csvRows, `picklist_sku_only_${new Date().toISOString().split('T')[0]}.csv`);
    };

    // --- EXPORT TYPE 3: Open Picklist Modal (inventory check) ---
    const handleExportWithInventory = () => {
        setExportAnchorEl(null);
        setPicklistOpen(true);
    };

    const handleSnackbarClose = () => setSnackbar(prev => ({ ...prev, open: false }));

    return (
        <Box sx={{ p: 2, display: 'flex', gap: 4, height: '100%', overflowX: 'auto', overflowY: 'hidden' }}>
            <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, minWidth: 0 }}>
                {/* Filter and Action Bars */}
                <Box sx={{ display: 'flex', gap: 1, mb: 2, alignItems: 'center', flexShrink: 0, bgcolor: 'background.paper', p: 1.5, borderRadius: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TextField label="From Date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} InputLabelProps={{ shrink: true }} size="small" sx={{ width: 150 }} />
                        <TextField label="To Date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} InputLabelProps={{ shrink: true }} size="small" sx={{ width: 150 }} />
                        <Button onClick={() => { setStartDate(''); setEndDate(''); }} sx={{ minWidth: '40px', p: 1 }} color="warning" variant="outlined" title="Clear Date Filter"><ClearIcon fontSize="small" /></Button>
                    </Box>
                    <TextField label="Search by Order #" variant="outlined" value={searchText} onChange={(e) => setSearchText(e.target.value)} size="small" sx={{ flex: 1, maxWidth: 300 }} />
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Tooltip title={!canExport ? "Permission Required" : ""}>
                            <span>
                                <Button
                                    variant="contained"
                                    color="info"
                                    onClick={() => setPicklistOpen(true)}
                                    disabled={selectedBatches.length === 0 || !canExport}
                                >
                                    Generate Picklist ({selectedBatches.length})
                                </Button>
                            </span>
                        </Tooltip>
                        <Tooltip title={!canExport ? "Permission Required" : ""}>
                            <span>
                                <Button
                                    variant="outlined"
                                    color="primary"
                                    endIcon={<ArrowDropDownIcon />}
                                    onClick={(e) => setExportAnchorEl(e.currentTarget)}
                                    disabled={selectedBatches.length === 0 || !canExport}
                                >
                                    Export Picklist
                                </Button>
                            </span>
                        </Tooltip>
                        <Menu anchorEl={exportAnchorEl} open={Boolean(exportAnchorEl)} onClose={() => setExportAnchorEl(null)}>
                            <MenuItem onClick={handleExportWithBatchInfo}>
                                <ListItemIcon><PrintIcon fontSize="small" /></ListItemIcon>
                                Print List with Batch Info
                            </MenuItem>
                            <MenuItem onClick={handleExportSKUOnly}>
                                <ListItemIcon><ListAltIcon fontSize="small" /></ListItemIcon>
                                Print Picklist (SKUs Only)
                            </MenuItem>
                            <Divider />
                            <MenuItem onClick={handleExportWithInventory}>
                                <ListItemIcon><InventoryIcon fontSize="small" /></ListItemIcon>
                                Picklist with Inventory Check
                            </MenuItem>
                        </Menu>
                    </Box>
                </Box>
                <Paper sx={{ p: 1.5, mb: 2, display: 'flex', gap: 2, alignItems: 'center', bgcolor: 'background.paper', position: 'sticky', top: '10px', zIndex: 10, flexShrink: 0 }}>
                    <Box>
                    <Tooltip title={!canModify ? "Permission Required" : ""}>
                        <span>
                            <Button variant="contained" color="primary" endIcon={<ArrowDropDownIcon />} onClick={handleFulfillMenuClick} disabled={!canModify}>Fulfill Options</Button>
                        </span>
                    </Tooltip>
                    <Menu anchorEl={fulfillAnchorEl} open={Boolean(fulfillAnchorEl)} onClose={handleFulfillMenuClose}>
                            <MenuItem onClick={() => handleFulfillMenuClose()}>Manual Selection (Use Checkboxes)</MenuItem>
                            <MenuItem onClick={handleOpenScanDialog}><Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><QrCodeScannerIcon fontSize="small" /> Scan to Fulfill & Package</Box></MenuItem>
                            <MenuItem onClick={handleOpenBulkScanDialog}><Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}><QrCodeScannerIcon fontSize="small" /> Scan & Accumulate (Bulk Fulfill)</Box></MenuItem>
                        </Menu>
                    </Box>
                    <Box sx={{ flex: 1 }} />
                    <Typography sx={{ flexShrink: 0, fontWeight: 'bold' }}>{ordersToPackage.length} order(s) selected.</Typography>
                    <FormControl size="small" sx={{ minWidth: 200 }}>
                        <InputLabel>Assign to Agent</InputLabel>
                        <Select value={selectedAgent} label="Assign to Agent" onChange={(e) => setSelectedAgent(e.target.value)}>
                            <MenuItem value=""><em>Select Agent</em></MenuItem>
                             {agents.map(agent => (
                                 <MenuItem key={agent.id} value={agent.id} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: 1 }}>
                                     <span>{agent.username}</span>
                                     {renderStatusChip(agent.today_status, agent.work_mode)}
                                 </MenuItem>
                             ))}
                        </Select>
                    </FormControl>
                     <Button variant="contained" color="secondary" onClick={handleCreatePackagingBatch} disabled={ordersToPackage.length === 0 || !selectedAgent || !canModify}>Send to Packaging</Button>
                </Paper>

                <Box sx={{ flex: 1, overflowY: 'auto' }}>
                    {loading ? (<Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 8 }}><CircularProgress size={40} /><Typography variant="body2" color="textSecondary" mt={2}>Loading Production Batches...</Typography></Box>
                    ) : error ? (<Alert severity="error" sx={{ m: 2 }}>{error}</Alert>
                    ) : filteredBatches.length === 0 ? (<Box sx={{ textAlign: 'center', p: 4 }}><Typography color="text.secondary">No batches found.</Typography>{(startDate || endDate) && <Typography variant="caption">Try clearing the date filter.</Typography>}</Box>
                    ) : (
                        filteredBatches.map(batch => {
                            const isBatchSelected = selectedBatches.includes(batch.id);
                            const ordersInBatch = batch.orders || [];
                            if (ordersInBatch.length === 0) return null;
                            return (
                                <Accordion key={batch.id}>
                                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                                        <Box sx={{ display: 'flex', width: '100%', alignItems: 'center', gap: 2 }}>
                                            <Checkbox size="small" title="Select batch for picklist" checked={isBatchSelected} onChange={(e) => handleBatchSelect(batch.id, e.target.checked)} onClick={(e) => e.stopPropagation()} />
                                            <Typography variant="h6">Batch #{batch.id}</Typography>
                                            <Chip label={`${ordersInBatch.length} Orders`} />
                                            <Typography variant="caption" color="textSecondary" sx={{ ml: 'auto' }}>{formatDate(batch.created_at)}</Typography>
                                        </Box>
                                    </AccordionSummary>
                                    <AccordionDetails sx={{ p: 0 }}>
                                        <TableContainer component={Paper}>
                                            <Table size="small">
                                                <TableHead>
                                                    <TableRow>
                                                        <TableCell>Order #</TableCell><TableCell>Total</TableCell><TableCell>Stock Status</TableCell><TableCell>Products</TableCell>
                                                        <TableCell>SKUs</TableCell><TableCell>Tracking</TableCell><TableCell>Last Hold Reason</TableCell><TableCell align="center">Fulfilled</TableCell><TableCell>Reason (If Not Fulfilled)</TableCell>
                                                    </TableRow>
                                                </TableHead>
                                                <TableBody>
                                                    {ordersInBatch.map(row => {
                                                        const isAffected = unfulfillableOrderIds.has(row.order_number);
                                                        const isFulfilled = fulfilledSet.has(String(row.order_number)) || row.internal_fulfillment_status === 'Fulfilled';
                                                        const isOnHold = row.internal_fulfillment_status === 'On Hold';
                                                        const lastHoldEntry = row.hold_history?.[row.hold_history.length - 1] || null;
                                                        
                                                        let rowBgColor = 'inherit';
                                                        if (isAffected) rowBgColor = '#fff7ed'; // warning light
                                                        if (isOnHold) rowBgColor = '#fff1f2'; // error light/reddish
                                                        
                                                        return (
                                                            <TableRow key={row.order_number} sx={{ bgcolor: rowBgColor }}>
                                                                <TableCell sx={{ fontWeight: 'bold' }}>{row.order_number}</TableCell>
                                                                <TableCell>
                                                                    {canViewAmounts ? `₹${row.total_price}` : "₹ ****"}
                                                                </TableCell>
                                                                <TableCell>
                                                                    {isOnHold ? (
                                                                        <Chip label="ON HOLD" color="error" size="small" variant="contained" sx={{ fontWeight: 'bold' }} />
                                                                    ) : (
                                                                        <Chip label={isAffected ? "Stock Shortage" : "Available"} color={isAffected ? "warning" : "success"} size="small" />
                                                                    )}
                                                                </TableCell>
                                                                <TableCell sx={{ fontSize: '13px' }}>{(row.line_items || []).map((item, index) => <div key={index}>{`${item.title} (Qty: ${item.quantity})`}</div>)}</TableCell>
                                                                <TableCell sx={{ verticalAlign: 'top' }}>{(row.line_items || []).map(item => item.sku).join(' / ')}</TableCell>
                                                                <TableCell>{getDisplayTracking(row)}</TableCell>
                                                                <TableCell>
                                                                    {isOnHold ? (
                                                                        <Typography variant="body2" color="error.main" fontWeight="bold">
                                                                            {row.fulfillment_reason || lastHoldEntry?.reason || "Reason Unspecified"}
                                                                        </Typography>
                                                                    ) : lastHoldEntry ? (
                                                                        <Tooltip title={`On: ${formatDate(lastHoldEntry.timestamp)} | By: ${lastHoldEntry.user}`}>
                                                                            <Chip icon={<HistoryIcon />} label={lastHoldEntry.reason} color="warning" size="small" variant="outlined" />
                                                                        </Tooltip>
                                                                    ) : null}
                                                                </TableCell>
                                                                <TableCell align="center"><Checkbox checked={isFulfilled} onChange={(e) => handleFulfilledChange(row.order_number, e.target.checked)} disabled={!canModify || isOnHold} /></TableCell>
                                                                <TableCell>
                                                                    <FormControl size="small" sx={{ minWidth: 180 }} disabled={isFulfilled || !canModify}>
                                                                        <Select value={row.fulfillment_reason || ""} displayEmpty onChange={(e) => handleReasonChange(row.order_number, e.target.value)}>
                                                                            <MenuItem value=""><em>Select Reason</em></MenuItem>
                                                                            {reasonOptions.map((reason) => <MenuItem key={reason} value={reason}>{reason}</MenuItem>)}
                                                                        </Select>
                                                                    </FormControl>
                                                                </TableCell>
                                                            </TableRow>
                                                        );
                                                    })}
                                                </TableBody>
                                            </Table>
                                        </TableContainer>
                                    </AccordionDetails>
                                </Accordion>
                            );
                        })
                    )}
                </Box>
            </Box>

            <Box sx={{ width: '340px', flexShrink: 0, overflowY: 'auto', maxHeight: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
                {/* --- Section 1: Overview KPIs --- */}
                <Paper elevation={2} sx={{ p: 0, bgcolor: 'background.paper', borderRadius: '8px', overflow: 'hidden' }}>
                    <Box sx={{ bgcolor: 'primary.main', px: 2, py: 1 }}>
                        <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                            {selectedBatches.length > 0 ? `Selected Batches (${selectedBatches.length})` : "Today's Summary"}
                        </Typography>
                    </Box>
                    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 0, p: 0 }}>
                        <Box sx={{ textAlign: 'center', py: 1.5, px: 1, borderRight: '1px solid #eee' }}>
                            <Typography variant="h5" sx={{ fontWeight: 800, color: 'text.primary', lineHeight: 1.2 }}>{overviewKpis.total}</Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>Total</Typography>
                        </Box>
                        <Box sx={{ textAlign: 'center', py: 1.5, px: 1, borderRight: '1px solid #eee' }}>
                            <Typography variant="h5" sx={{ fontWeight: 800, color: 'success.main', lineHeight: 1.2 }}>{overviewKpis.fulfilled}</Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>Fulfilled</Typography>
                        </Box>
                        <Box sx={{ textAlign: 'center', py: 1.5, px: 1, borderRight: '1px solid #eee' }}>
                            <Typography variant="h5" sx={{ fontWeight: 800, color: 'warning.main', lineHeight: 1.2 }}>{overviewKpis.pending}</Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>Pending</Typography>
                        </Box>
                        <Box sx={{ textAlign: 'center', py: 1.5, px: 1 }}>
                            <Typography variant="h5" sx={{ fontWeight: 800, color: 'error.main', lineHeight: 1.2 }}>{overviewKpis.onHold}</Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 600 }}>On Hold</Typography>
                        </Box>
                    </Box>
                </Paper>

                {/* --- Section 2: Shipping Company Breakdown --- */}
                <Paper elevation={2} sx={{ bgcolor: 'background.paper', borderRadius: '8px', overflow: 'hidden' }}>
                    <Box sx={{ bgcolor: '#37474f', px: 2, py: 0.75, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <LocalShippingIcon sx={{ color: 'white', fontSize: '1rem' }} />
                        <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>Shipping Partner Breakdown</Typography>
                    </Box>
                    <TableContainer>
                        <Table size="small" sx={{ '& td, & th': { py: 0.5, px: 1.5, fontSize: '0.8rem' } }}>
                            <TableHead>
                                <TableRow sx={{ bgcolor: 'action.hover' }}>
                                    <TableCell sx={{ fontWeight: 700 }}>Partner</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 700 }}>Orders</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 700 }}>COD</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 700 }}>PPCOD</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 700 }}>Prepaid</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {shippingSummary.rows.length === 0 ? (
                                    <TableRow><TableCell colSpan={5} align="center" sx={{ py: 2, color: 'text.secondary' }}>No orders</TableCell></TableRow>
                                ) : (
                                    shippingSummary.rows.map(row => (
                                        <TableRow key={row.company} hover>
                                            <TableCell sx={{ fontWeight: 600, maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.company}</TableCell>
                                            <TableCell align="center" sx={{ fontWeight: 600 }}>{row.total}</TableCell>
                                            <TableCell align="center">{row.cod}</TableCell>
                                            <TableCell align="center">{row.ppcod}</TableCell>
                                            <TableCell align="center">{row.prepaid}</TableCell>
                                        </TableRow>
                                    ))
                                )}
                                {shippingSummary.rows.length > 0 && (
                                    <TableRow sx={{ bgcolor: 'action.hover' }}>
                                        <TableCell sx={{ fontWeight: 800 }}>TOTAL</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 800 }}>{shippingSummary.totals.total}</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 800 }}>{shippingSummary.totals.cod}</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 800 }}>{shippingSummary.totals.ppcod}</TableCell>
                                        <TableCell align="center" sx={{ fontWeight: 800 }}>{shippingSummary.totals.prepaid}</TableCell>
                                    </TableRow>
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>

                {/* --- Section 3: Payment Type Summary (Fulfilled for the Day) --- */}
                <Paper elevation={2} sx={{ bgcolor: 'background.paper', borderRadius: '8px', overflow: 'hidden' }}>
                    <Box sx={{ bgcolor: '#1b5e20', px: 2, py: 0.75, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CheckCircleOutlineIcon sx={{ color: 'white', fontSize: '1rem' }} />
                        <Typography variant="subtitle2" sx={{ color: 'white', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                            {selectedBatches.length > 0 ? 'Fulfillment Status' : 'Orders Fulfilled Today'}
                        </Typography>
                    </Box>
                    <TableContainer>
                        <Table size="small" sx={{ '& td, & th': { py: 0.5, px: 1.5, fontSize: '0.8rem' } }}>
                            <TableHead>
                                <TableRow sx={{ bgcolor: 'action.hover' }}>
                                    <TableCell sx={{ fontWeight: 700 }}>Type</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 700, color: 'success.main' }}>Fulfilled</TableCell>
                                    {canViewAmounts && <TableCell align="center" sx={{ fontWeight: 700 }}>Amount</TableCell>}
                                    <TableCell align="center" sx={{ fontWeight: 700, color: 'warning.main' }}>Unfulfilled</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                <TableRow hover>
                                    <TableCell sx={{ fontWeight: 600 }}>COD</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 600, color: 'success.dark' }}>
                                        {selectedBatches.length > 0 ? fulfillmentKpis.codQty : dailyStats.cod_count}
                                    </TableCell>
                                    {canViewAmounts && <TableCell align="center">
                                        ₹{(selectedBatches.length > 0 ? fulfillmentKpis.codAmount : (dailyStats.cod_amount || 0)).toFixed(0)}
                                    </TableCell>}
                                    <TableCell align="center" sx={{ color: 'warning.dark' }}>{paymentSummary.codUnfulfilled}</TableCell>
                                </TableRow>
                                <TableRow hover>
                                    <TableCell sx={{ fontWeight: 600 }}>PPCOD</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 600, color: 'success.dark' }}>
                                        {selectedBatches.length > 0 ? fulfillmentKpis.ppcodQty : dailyStats.ppcod_count}
                                    </TableCell>
                                    {canViewAmounts && <TableCell align="center">
                                        ₹{(selectedBatches.length > 0 ? fulfillmentKpis.ppcodAmount : (dailyStats.ppcod_amount || 0)).toFixed(0)}
                                    </TableCell>}
                                    <TableCell align="center" sx={{ color: 'warning.dark' }}>{paymentSummary.ppcodUnfulfilled}</TableCell>
                                </TableRow>
                                <TableRow hover>
                                    <TableCell sx={{ fontWeight: 600 }}>Prepaid</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 600, color: 'success.dark' }}>
                                        {selectedBatches.length > 0 ? fulfillmentKpis.prepaidQty : dailyStats.prepaid_count}
                                    </TableCell>
                                    {canViewAmounts && <TableCell align="center">
                                        ₹{(selectedBatches.length > 0 ? fulfillmentKpis.prepaidAmount : (dailyStats.prepaid_amount || 0)).toFixed(0)}
                                    </TableCell>}
                                    <TableCell align="center" sx={{ color: 'warning.dark' }}>{paymentSummary.prepaidUnfulfilled}</TableCell>
                                </TableRow>
                                <TableRow sx={{ bgcolor: 'action.hover' }}>
                                    <TableCell sx={{ fontWeight: 800 }}>Total</TableCell>
                                    <TableCell align="center" sx={{ fontWeight: 800, color: 'success.dark' }}>
                                        {selectedBatches.length > 0 ? fulfillmentKpis.totalFulfilled : dailyStats.count}
                                    </TableCell>
                                    {canViewAmounts && <TableCell align="center" sx={{ fontWeight: 800 }}>
                                        ₹{(selectedBatches.length > 0 ? fulfillmentKpis.totalFulfilledAmount : (dailyStats.amount || 0)).toFixed(0)}
                                    </TableCell>}
                                    <TableCell align="center" sx={{ fontWeight: 800, color: 'warning.dark' }}>{paymentSummary.totalUnfulfilled}</TableCell>
                                </TableRow>
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Paper>
            </Box>

            <PicklistModal open={isPicklistOpen} onClose={() => setPicklistOpen(false)} orders={ordersForPicklist} onApply={setAvailableQuantities} selectedBatchData={selectedBatchData} />
            <ScanFulfillDialog
                open={scanDialogOpen}
                onClose={() => setScanDialogOpen(false)}
                users={agents}
                onConfirm={(orderNumbers, userId) => handleScanComplete(orderNumbers, userId)}
                onBulkAction={performBulkAction}
                allBatches={allBatches}
            />
            <BulkScanAccumulateDialog
                open={bulkScanDialogOpen}
                onClose={() => setBulkScanDialogOpen(false)}
                users={agents}
                onConfirm={(orderNumbers, userId) => handleScanComplete(orderNumbers, userId)}
                onBulkAction={performBulkAction}
                allBatches={allBatches}
            />
            <Snackbar open={snackbar.open} autoHideDuration={6000} onClose={handleSnackbarClose} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
                <Alert onClose={handleSnackbarClose} severity={snackbar.severity} sx={{ width: '100%', boxShadow: 6 }}>{snackbar.message}</Alert>
            </Snackbar>
        </Box>
    );
};