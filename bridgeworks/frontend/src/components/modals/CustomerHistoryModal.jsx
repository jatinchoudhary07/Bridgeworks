import React, { useEffect, useState } from "react";
import {
    Box, Button, Typography, Dialog, DialogTitle, DialogContent, DialogActions,
    TableContainer, Table, TableHead, TableRow, TableCell, TableBody, Chip, Alert,
    Stack, CircularProgress
} from "@mui/material";
import ShoppingBagIcon from '@mui/icons-material/ShoppingBag';
import { BACKEND_URL } from "../../config/api";
import { apiClient } from "../../apiClient";

const formatDate = (iso) => {
    if (!iso) return "-";
    return new Date(iso).toLocaleString("en-IN", {
        day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
};

export default function CustomerHistoryModal({ open, onClose, customer, canViewAmounts = true }) {
    const [historyOrders, setHistoryOrders] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    useEffect(() => {
        if (open && customer) {
            fetchHistory();
        }
    }, [open, customer]);

    const fetchHistory = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await apiClient(`${BACKEND_URL}/api/orders/history/?phone=${encodeURIComponent(customer.contact_phone)}`, { credentials: 'include' });
            if (!res.ok) throw new Error("Could not fetch history");
            const data = await res.json();
            setHistoryOrders(data);
        } catch (err) {
            console.error(err);
            setError("Failed to load history.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle sx={{ bgcolor: 'background.default', borderBottom: 1, borderColor: 'divider' }}>
                <Stack direction="row" alignItems="center" gap={1}>
                    <ShoppingBagIcon color="primary" />
                    <Typography variant="h6">
                        Order History: {customer?.customer_full_name}
                    </Typography>
                </Stack>
                <Typography variant="caption" color="text.secondary">{customer?.contact_phone}</Typography>
            </DialogTitle>
            <DialogContent sx={{ p: 0 }}>
                {loading ? (
                    <Box sx={{ p: 4, display: 'flex', justifyContent: 'center' }}><CircularProgress /></Box>
                ) : error ? (
                    <Alert severity="warning" sx={{ m: 2 }}>{error}</Alert>
                ) : historyOrders.length === 0 ? (
                    <Box sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>No previous orders found.</Box>
                ) : (
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow sx={{ bgcolor: 'action.hover' }}>
                                    <TableCell>Order #</TableCell>
                                    <TableCell>Date</TableCell>
                                    <TableCell>Status</TableCell>
                                    <TableCell>Items</TableCell>
                                    <TableCell align="right">Total</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {historyOrders.map((order) => (
                                    <TableRow key={order.id} hover>
                                        <TableCell sx={{ fontWeight: 'bold' }}>#{order.order_number}</TableCell>
                                        <TableCell>{formatDate(order.created_at)}</TableCell>
                                        <TableCell>
                                            <Chip
                                                label={order.status || order.fulfillment_status || 'Pending'}
                                                size="small"
                                                color={order.status === 'Confirmed' ? 'success' : order.status === 'Cancelled' ? 'error' : 'default'}
                                                variant="outlined"
                                                sx={{ height: 20, fontSize: '0.7rem' }}
                                            />
                                        </TableCell>
                                        <TableCell>
                                            {(order.line_items || []).map(i => `${i.title} (x${i.quantity})`).join(", ")}
                                        </TableCell>
                                        <TableCell align="right">{canViewAmounts ? `₹${order.total_price}` : "₹ ****"}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
}
