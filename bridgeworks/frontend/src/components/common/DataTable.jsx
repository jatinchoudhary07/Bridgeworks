import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import {
    Box, Button, Chip, Paper, TableContainer,
    Table, TableHead, TableRow, TableCell, TableBody, TablePagination,
    CircularProgress, Checkbox, Stack, Typography, Divider, Alert,
    TextField, Tooltip
} from "@mui/material";
import DownloadIcon from '@mui/icons-material/FileDownload';
import ListAltIcon from '@mui/icons-material/ListAlt';
import SyncIcon from '@mui/icons-material/Sync';
import { OrderModal, PicklistModal, SyncOrderModal, CustomerHistoryModal } from '../modals';
import Filters from './Filters';
import { BACKEND_URL } from "../../config/api";
import { apiClient } from "../../apiClient";
import PaymentTable from "./PaymentTable";
import IntelligenceBadge from "./IntelligenceBadge";
import { usePagePermissions } from "../../utils/rbac";
import VerifiedIcon from '@mui/icons-material/Verified';

// ------------------------------------------------------
// 0. UTILS & HOOKS
// ------------------------------------------------------

function useDebounce(value, delay) {
    const [debouncedValue, setDebouncedValue] = useState(value);
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);
        return () => clearTimeout(handler);
    }, [value, delay]);
    return debouncedValue;
}

const formatDate = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
};

const getInternalFulfillmentColor = (status) => {
    if (!status) return '#9e9e9e';
    switch (status.toLowerCase()) {
        case 'pending':
            return '#9e9e9e'; // Gray
        case 'fulfilled':
            return '#1877f2'; // Meta Blue
        case 'sent for packaging':
            return '#ff9800'; // Amber/Orange
        case 'packaged':
            return '#10b981'; // Green
        case 'on hold':
            return '#f44336'; // Red
        case 'manifested':
            return '#7c3aed'; // Purple/Violet
        default:
            return '#9e9e9e';
    }
};

const getInternalFulfillmentTooltip = (order) => {
    const status = order.internal_fulfillment_status;
    if (!status) return "-";
    
    if (status.toLowerCase() === 'packaged' && order.packaged_by_username) {
        return `Packaged by ${order.packaged_by_username}${order.packaged_at ? ` on ${formatDate(order.packaged_at)}` : ''}`;
    }
    if (status.toLowerCase() === 'manifested') {
        let msg = `Manifested${order.manifested_at ? ` on ${formatDate(order.manifested_at)}` : ''}`;
        if (order.packaged_by_username) {
            msg += ` (Packaged by ${order.packaged_by_username})`;
        }
        return msg;
    }
    return `Internal Status: ${status}`;
};

const getStatusBadgeStyle = (status) => {
    if (!status) return { bg: '#F3F4F6', text: '#374151', border: '#9CA3AF' };
    switch (status.toLowerCase()) {
        case 'confirmed':
            return { bg: '#D1FAE5', text: '#065F46', border: '#10B981' }; // Soft Green
        case 'pending':
            return { bg: '#FEF3C7', text: '#92400E', border: '#F59E0B' }; // Soft Orange
        case 'batched':
            return { bg: '#DBEAFE', text: '#1E40AF', border: '#3B82F6' }; // Soft Blue
        case 'cancelled':
            return { bg: '#FEE2E2', text: '#991B1B', border: '#EF4444' }; // Soft Red
        default:
            return { bg: '#F3F4F6', text: '#374151', border: '#9CA3AF' };
    }
};

const normalizeStatus = (raw) => {
    if (!raw || typeof raw !== "string") return "";
    const s = raw.toLowerCase().trim();
    const map = {
        "delivered": "del", "delivery": "del", "out_for_delivery": "ood",
        "out for delivery": "ood", "ofd": "ood", "in_transit": "int",
        "transit": "int", "undelivered": "und", "failed_attempt": "und",
        "rto": "rto", "return_to_origin": "rto", "rtd": "rtd",
        "rto_delivered": "rtd", "returned": "rdel", "return_delivered": "rdel",
        "pickup_failed": "rpf", "pickup_fail": "rpf", "pickup_delayed": "rsmr",
        "pickup_rescheduled": "rsmr", "shipment_booked": "sch", "booked": "sch",
        "status_pending": "nfi", "pending": "nfi", "nfidrsch": "nfids",
        "return_request_cancelled": "rcan", "cancelled": "can",
        "fulfilled": "del"
    };
    return map[s] || s.replace(/_/g, "").replace(/\s+/g, "");
};

const STATUS_PRIORITY = [
    "", "sch", "nfids", "nfi", "rsmr", "rcan", "pcan", "roop",
    "rpkp", "rclo", "onh", "roth", "und", "int", "ood",
    "rto", "rtd", "rdel", "can", "del", "rpf"
];

const displayStatus = (raw = "") => {
    const ns = normalizeStatus(raw);
    const readable = {
        "del": "Delivered", "ood": "Out For Delivery", "int": "In Transit",
        "und": "Undelivered", "rto": "RTO", "rtd": "RTO Delivered",
        "rdel": "Return Delivered", "nfi": "Status Pending", "nfids": "NFIDRSCH",
        "rsmr": "Pickup Rescheduled", "rcan": "Return Request Cancelled",
        "pcan": "Pickup Cancelled", "sch": "Shipment Booked", "roop": "Out For Pickup",
        "rpkp": "Shipment Picked Up", "onh": "On Hold", "roth": "Others",
        "rpf": "Pickup Failed", "can": "Cancelled", "": "-"
    };
    return readable[ns] || raw || "-";
};

const getBestFulfillment = (order) => {
    const list = order?.fulfillments || [];
    if (!list.length) return null;

    return list
        .map((f) => ({
            ...f,
            created_at_date: new Date(f.created_at),
            ns: normalizeStatus(f.shipment_status)
        }))
        .sort((a, b) => {
            const timeDiff = b.created_at_date - a.created_at_date;
            if (timeDiff !== 0) return timeDiff;
            return STATUS_PRIORITY.indexOf(b.ns) - STATUS_PRIORITY.indexOf(a.ns);
        })[0];
};

const getShipmentStatus = (order) => {
    const best = getBestFulfillment(order);
    return best ? displayStatus(best.shipment_status) : "-";
};

const exportToCSV = (selectedIds, allRows) => {
    if (!selectedIds.length) return;

    const rowsToExport = allRows.filter(row => selectedIds.includes(row.id));
    const headers = [
        "Order #", "Status", "Customer", "Qty", "Total",
        "Fulfillment", "Payment", "Shipment Status", "Tracking Number", "Order Created"
    ];

    const csvRows = rowsToExport.map(row => {
        const trackingNumbers = (row.__tracking || []).map(t => t.number).join(", ");
        return [
            row.order_number,
            row.status,
            row.customer_full_name,
            row.total_quantity,
            row.total_price,
            row.fulfillment_status,
            (row.payment_gateway_names || []).join(", "),
            row.shipment_status,
            trackingNumbers,
            formatDate(row.created_at).replace(/,/g, '')
        ].map(str => `"${str}"`).join(",");
    });

    const csvContent = [headers.join(","), ...csvRows].join("\n");
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = `orders_export_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    document.body.removeChild(link);
};

// ------------------------------------------------------
// 1. MAIN COMPONENT
// ------------------------------------------------------

export default function DataTable() {
    // --- STATE ---
    const [orders, setOrders] = useState([]);
    const [kpiData, setKpiData] = useState(null);

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [totalCount, setTotalCount] = useState(0);

    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(25);

    const { canEdit, canDelete, canViewAmounts, canExport } = usePagePermissions();
    const [selected, setSelected] = useState(null);
    const [open, setOpen] = useState(false);
    const [selectedIds, setSelectedIds] = useState([]);
    const [isPicklistOpen, setIsPicklistOpen] = useState(false);
    const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
    const [historyCustomer, setHistoryCustomer] = useState(null);

    const [filters, setFilters] = useState({
        startDate: "",
        endDate: "",
        fulfillmentStatus: [],
        paymentGateway: [],
        deliveryPartner: [],
        shipmentStatus: [],
        financialStatus: [],
        status: [],
    });

    const [searchText, setSearchText] = useState("");
    const debouncedSearchText = useDebounce(searchText, 500);
    const abortControllerRef = useRef(null);

    // --- FETCH ---
    const fetchOrders = useCallback(async () => {
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
        }
        const controller = new AbortController();
        abortControllerRef.current = controller;

        setLoading(true);
        setError(null);

        const djangoPage = page + 1;
        const params = new URLSearchParams();
        params.append("page", djangoPage);
        params.append("limit", rowsPerPage);

        if (debouncedSearchText) params.append("search", debouncedSearchText);
        if (filters.startDate) params.append("startDate", filters.startDate);
        if (filters.endDate) params.append("endDate", filters.endDate);

        filters.status.forEach(v => params.append("status", v));
        filters.fulfillmentStatus.forEach(v => params.append("fulfillmentStatus", v));
        filters.financialStatus.forEach(v => params.append("financialStatus", v));
        filters.paymentGateway.forEach(v => params.append("paymentGateway", v));
        filters.deliveryPartner.forEach(v => params.append("deliveryPartner", v));
        filters.shipmentStatus.forEach(v => params.append("shipmentStatus", v));



        const url = `${BACKEND_URL}/api/orders/paginated/?${params.toString()}`;
        const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        try {
            const res = await apiClient(url, {
                signal: controller.signal,
                credentials: "include",
                headers: { 'X-User-Timezone': userTimezone }
            });

            if (!res.ok) {
                if (res.status === 403) throw new Error("ACCESS DENIED: You do not have general view permission.");
                if (res.status === 401) throw new Error("Session expired/unauthorized.");
                throw new Error(`Failed to fetch orders: ${res.status}`);
            }

            const data = await res.json();
            setOrders(Array.isArray(data.orders) ? data.orders : []);
            setTotalCount(data.count || 0);

            if (data.kpi) {
                setKpiData(data.kpi);
            }
        } catch (err) {
            if (err.name === 'AbortError') return;
            setError(err.message || "Unknown error fetching orders.");
            setOrders([]);
            setTotalCount(0);
        } finally {
            if (!controller.signal.aborted) {
                setLoading(false);
            }
        }
    }, [page, rowsPerPage, debouncedSearchText, filters]);

    useEffect(() => {
        fetchOrders();
    }, [fetchOrders]);

    useEffect(() => {
        setPage(0);
    }, [debouncedSearchText, filters]);

    // --- MEMOS ---
    const rows = useMemo(
        () =>
            (orders || []).map((o) => {
                const customerFirst = o.customer_first_name || "";
                const customerLast = o.customer_last_name || "";
                const best = getBestFulfillment(o);

                return {
                    ...o,
                    id: o.order_number,
                    total_quantity: (o.line_items || []).reduce(
                        (s, li) => s + (Number(li.quantity || 0) || 0),
                        0
                    ),
                    shipment_status: getShipmentStatus(o),
                    customer_full_name: `${customerFirst} ${customerLast}`.trim() || "N/A",
                    __tracking: best?.tracking_info || []
                };
            }),
        [orders]
    );

    const selectedOrdersForPicklist = useMemo(() => {
        return rows.filter(row => selectedIds.includes(row.id));
    }, [rows, selectedIds]);

    // --- HANDLERS ---
    const clearFilters = () => {
        setFilters({
            startDate: "", endDate: "", fulfillmentStatus: [], paymentGateway: [],
            deliveryPartner: [], shipmentStatus: [], financialStatus: [], status: [],
        });
        setSearchText("");
        setPage(0);
    };

    const handleExport = () => exportToCSV(selectedIds, rows);

    const currentOrderIndex = useMemo(() => {
        if (!selected) return -1;
        return rows.findIndex(row => row.id === selected.order_number);
    }, [selected, rows]);

    const handleShowPreviousOrder = () => {
        if (currentOrderIndex > 0) {
            const prev = rows[currentOrderIndex - 1];
            if (prev) setSelected(prev);
        }
    };

    const handleShowNextOrder = () => {
        if (currentOrderIndex < rows.length - 1) {
            const next = rows[currentOrderIndex + 1];
            if (next) setSelected(next);
        }
    };

    const handleSelectAllClick = (event) => {
        if (event.target.checked) {
            const newSelecteds = rows.map((n) => n.id);
            setSelectedIds(newSelecteds);
            return;
        }
        setSelectedIds([]);
    };

    const handleClick = (event, id) => {
        event.stopPropagation();
        const selectedIndex = selectedIds.indexOf(id);
        let newSelected = [];

        if (selectedIndex === -1) {
            newSelected = [...selectedIds, id];
        } else {
            newSelected = selectedIds.filter((item) => item !== id);
        }
        setSelectedIds(newSelected);
    };

    const isSelected = (id) => selectedIds.indexOf(id) !== -1;

    // --- RENDER ---
    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, height: 'calc(100vh - 80px)' }}>
            <Box sx={{ display: 'flex', gap: 0.5, flexShrink: 0, alignItems: 'stretch' }}>
                {/* LEFT: Payment Table - 33% width */}
                <Box sx={{ flex: '0 0 32.2%', flexShrink: 0 }}>
                    <PaymentTable kpiData={kpiData} isLoading={loading} canViewAmounts={canViewAmounts} />
                </Box>

                {/* RIGHT: Filters - 67% width */}
                <Paper
                    elevation={2}
                    sx={{
                        flex: '0 0 67.6%',
                        p: 1,
                        borderRadius: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 1,
                        height: '100%'
                    }}
                >
                    {/* Search and Action Buttons Row */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TextField
                            placeholder="Search Order # or Customer..."
                            variant="outlined"
                            size="small"
                            value={searchText}
                            onChange={(e) => setSearchText(e.target.value)}
                        />
                        {/* Action Buttons - aligned to right */}
                        <Box sx={{ display: 'flex', gap: 1, ml: 'auto' }}>
                            <Button
                                variant="outlined"
                                color="primary"
                                size="small"
                                startIcon={<SyncIcon />}
                                onClick={() => setIsSyncModalOpen(true)}
                            >
                                SYNC ORDERS
                            </Button>
                            <Button
                                variant="outlined"
                                size="small"
                                onClick={clearFilters}
                            >
                                CLEAR FILTERS
                            </Button>
                            <Button
                                variant="contained"
                                color="info"
                                size="small"
                                startIcon={<ListAltIcon />}
                                onClick={() => setIsPicklistOpen(true)}
                                disabled={selectedIds.length === 0}
                            >
                                PICKLIST ({selectedIds.length})
                            </Button>
                            <Tooltip title={!canExport ? "Permission Required" : (selectedIds.length === 0 ? "Select orders to export" : "")}>
                                <span>
                                    <Button
                                        variant="outlined"
                                        color="secondary"
                                        size="small"
                                        startIcon={<DownloadIcon />}
                                        onClick={handleExport}
                                        disabled={selectedIds.length === 0 || !canExport}
                                    >
                                        Export CSV ({selectedIds.length})
                                    </Button>
                                </span>
                            </Tooltip>
                        </Box>
                    </Box>

                    {/* Filters Component */}
                    <Filters
                        filters={filters}
                        setFilters={(f) => {
                            setFilters(f);
                            setPage(0);
                        }}
                        applyFilters={() => { }}
                        clearFilters={clearFilters}
                    />

                </Paper>
            </Box>

            {/* BOTTOM ROW: Data Table spanning full width */}
            <Paper
                elevation={2}
                sx={{
                    flex: 1,
                    display: "flex",
                    flexDirection: "column",
                    overflow: "hidden",
                    borderRadius: 1,
                    position: "relative",
                    minHeight: 0
                }}
            >
                {error && <Alert severity="error" sx={{ m: 2 }}>{error}</Alert>}

                {/* Table Body */}
                <Box sx={{ flexGrow: 1, overflow: "auto" }}>
                    <TableContainer>
                        <Table stickyHeader size="small" sx={{ tableLayout: 'auto' }}>
                            <TableHead>
                                <TableRow sx={{ "& th": { fontWeight: "bold", whiteSpace: "nowrap", bgcolor: 'background.paper' } }}>
                                    <TableCell padding="checkbox" sx={{ minWidth: 42 }}>
                                        <Checkbox
                                            color="primary"
                                            indeterminate={selectedIds.length > 0 && selectedIds.length < rows.length}
                                            checked={rows.length > 0 && selectedIds.length === rows.length}
                                            onChange={handleSelectAllClick}
                                        />
                                    </TableCell>
                                    <TableCell sx={{ minWidth: 80 }}>Order #</TableCell>
                                    <TableCell sx={{ minWidth: 90 }}>Status</TableCell>
                                    <TableCell sx={{ minWidth: 100 }}>Customer</TableCell>
                                    <TableCell sx={{ minWidth: 100, textAlign: 'center' }}>Prev. Orders</TableCell>
                                    <TableCell sx={{ minWidth: 50 }}>Qty</TableCell>
                                    <TableCell sx={{ minWidth: 80 }}>Total</TableCell>
                                    <TableCell sx={{ minWidth: 100 }}>Fulfillment</TableCell>
                                    <TableCell sx={{ minWidth: 120 }}>OPM</TableCell>
                                    <TableCell sx={{ minWidth: 90 }}>Payment</TableCell>
                                    <TableCell sx={{ minWidth: 100 }}>Shipment</TableCell>
                                    <TableCell sx={{ minWidth: 150 }}>Tracking</TableCell>
                                    <TableCell sx={{ minWidth: 120 }}>Intelligence</TableCell>
                                    <TableCell sx={{ minWidth: 150 }}>Order Created</TableCell>
                                </TableRow>
                            </TableHead>

                            <TableBody>
                                {loading ? (
                                    <TableRow>
                                        <TableCell colSpan={14} align="center" sx={{ py: 8 }}>
                                            <CircularProgress size={30} />
                                            <Typography variant="body2" color="textSecondary" mt={1}>
                                                Loading orders...
                                            </Typography>
                                        </TableCell>
                                    </TableRow>
                                ) : rows.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={14} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                                            No orders found matching your criteria.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    rows.map((row) => {
                                        const isItemSelected = isSelected(row.id);
                                        return (
                                            <TableRow
                                                key={row.id}
                                                hover
                                                role="checkbox"
                                                aria-checked={isItemSelected}
                                                selected={isItemSelected}
                                                onClick={() => { setSelected(row); setOpen(true); }}
                                                sx={{
                                                    cursor: "pointer",
                                                    opacity: row.status === "Cancelled" ? 0.6 : 1,
                                                    "& td": { verticalAlign: "top", whiteSpace: "nowrap" },
                                                }}
                                            >
                                                <TableCell padding="checkbox">
                                                    <Checkbox
                                                        color="primary"
                                                        checked={isItemSelected}
                                                        onClick={(e) => handleClick(e, row.id)}
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}>
                                                        <Button
                                                            variant="text"
                                                            size="small"
                                                            sx={{ padding: 0, minWidth: "auto", fontWeight: 'bold' }}
                                                            onClick={(e) => { e.stopPropagation(); setSelected(row); setOpen(true); }}
                                                        >
                                                            {row.order_number}
                                                        </Button>
                                                        {row.internal_fulfillment_status && row.internal_fulfillment_status.toLowerCase() !== 'pending' && (
                                                            <Tooltip title={getInternalFulfillmentTooltip(row)}>
                                                                <VerifiedIcon 
                                                                    sx={{ 
                                                                        color: getInternalFulfillmentColor(row.internal_fulfillment_status), 
                                                                        fontSize: 16,
                                                                        display: 'inline-block',
                                                                        verticalAlign: 'middle'
                                                                    }} 
                                                                />
                                                            </Tooltip>
                                                        )}
                                                    </Box>
                                                </TableCell>
                                                <TableCell>
                                                    {(() => {
                                                        const style = getStatusBadgeStyle(row.status);
                                                        return (
                                                            <Chip
                                                                label={row.status || "N/A"}
                                                                size="small"
                                                                sx={{ 
                                                                    bgcolor: style.bg,
                                                                    color: style.text,
                                                                    border: `1px solid ${style.border}`,
                                                                    fontWeight: 600, 
                                                                    height: 24 
                                                                }}
                                                            />
                                                        );
                                                    })()}
                                                </TableCell>
                                                <TableCell sx={{ fontSize: "13px" }}>{row.customer_full_name}</TableCell>
                                                {/* --- PREV. ORDERS (CLICKABLE) --- */}
                                                <TableCell sx={{ textAlign: 'center', whiteSpace: 'nowrap' }}>
                                                    <Chip
                                                        label={row.previous_order_count || 0}
                                                        size="small"
                                                        variant={row.previous_order_count > 0 ? "filled" : "outlined"}
                                                        color={row.previous_order_count > 0 ? "info" : "default"}
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            if (row.previous_order_count > 0) setHistoryCustomer(row);
                                                        }}
                                                        sx={{
                                                            height: 24,
                                                            fontSize: '0.75rem',
                                                            cursor: row.previous_order_count > 0 ? 'pointer' : 'default'
                                                        }}
                                                    />
                                                </TableCell>
                                                <TableCell>{row.total_quantity}</TableCell>
                                                <TableCell align="right" sx={{ fontWeight: 'bold', color: 'primary.main', whiteSpace: 'nowrap' }}>
                                                    {canViewAmounts ? `₹${row.total_price || "0.00"}` : "₹ ****"}
                                                </TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={row.fulfillment_status || "Unfulfilled"}
                                                        size="small"
                                                        variant="outlined"
                                                        sx={{ height: 24 }}
                                                    />
                                                </TableCell>

                                                <TableCell sx={{ fontSize: "12px", whiteSpace: "normal", maxWidth: 130 }}>
                                                    {(() => {
                                                        const gateways = row.payment_gateway_names || [];
                                                        const isRazorpay = gateways.some(g => g.toLowerCase() === 'razorpay');
                                                        const isPartiallyPaid = (row.financial_status || '').toLowerCase() === 'partially_paid';
                                                        if (isRazorpay && isPartiallyPaid) {
                                                            return gateways.map(g => g.toLowerCase() === 'razorpay' ? 'Razorpay (PPCOD)' : g).join(', ');
                                                        }
                                                        return gateways.join(", ") || "-";
                                                    })()}
                                                </TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={row.financial_status}
                                                        size="small"
                                                        variant="outlined"
                                                        sx={{ height: 24, textTransform: 'capitalize' }}
                                                    />
                                                </TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={row.current_status ? row.current_status.replace(/_/g, ' ') : (row.shipment_status || "-")}
                                                        size="small"
                                                        variant="outlined"
                                                        sx={{ height: 24, fontSize: "0.75rem", fontWeight: 500, textTransform: 'capitalize' }}
                                                    />
                                                </TableCell>
                                                <TableCell sx={{ fontSize: "12px" }}>
                                                    {Array.isArray(row.__tracking) && row.__tracking.length > 0 ? (
                                                        row.__tracking.map((t, i) => (
                                                            <div key={i}>
                                                                <a
                                                                    href={`https://track.shipway.com/t/${t.number}`}
                                                                    target="_blank"
                                                                    rel="noreferrer"
                                                                    style={{
                                                                        textDecoration: "underline",
                                                                        fontWeight: 600
                                                                    }}
                                                                    onClick={(e) => e.stopPropagation()}
                                                                >
                                                                    {t.number}
                                                                </a>
                                                            </div>
                                                        ))
                                                    ) : "-"}
                                                </TableCell>

                                                <TableCell>
                                                    <IntelligenceBadge
                                                        flag={row.intelligence_flag}
                                                        score={row.risk_score}
                                                        suggestion={row.system_suggestion}
                                                        reasoning={row.agent_reasoning}
                                                        confirmation_reason={row.confirmation_reason}
                                                        hold_reason={row.hold_reason}
                                                    />
                                                </TableCell>
                                                <TableCell>{formatDate(row.created_at)}</TableCell>
                                            </TableRow>
                                        );
                                    })
                                )}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </Box>

                {/* Footer */}
                <Box sx={{ borderTop: 1, borderColor: 'divider', bgcolor: 'background.paper' }}>
                    <TablePagination
                        rowsPerPageOptions={[10, 25, 50, 100]}
                        component="div"
                        count={totalCount}
                        rowsPerPage={rowsPerPage}
                        page={page}
                        onPageChange={(e, newPage) => setPage(newPage)}
                        onRowsPerPageChange={(e) => {
                            setRowsPerPage(parseInt(e.target.value, 10));
                            setPage(0);
                        }}
                    />
                </Box>

                <OrderModal
                    open={open}
                    order={selected}
                    onClose={() => { setOpen(false); setSelected(null); }}
                    currentOrderIndex={currentOrderIndex}
                    totalOrdersInList={rows.length}
                    onPrevious={handleShowPreviousOrder}
                    onNext={handleShowNextOrder}
                />

                <PicklistModal
                    open={isPicklistOpen}
                    onClose={() => setIsPicklistOpen(false)}
                    orders={selectedOrdersForPicklist}
                />

                <SyncOrderModal
                    open={isSyncModalOpen}
                    onClose={() => setIsSyncModalOpen(false)}
                    onSyncSuccess={(newOrder) => {
                        fetchOrders();
                        if (newOrder) {
                            const customerFirst = newOrder.customer_first_name || "";
                            const customerLast = newOrder.customer_last_name || "";
                            const mappedOrder = {
                                ...newOrder,
                                id: newOrder.order_number,
                                total_quantity: (newOrder.line_items || []).reduce(
                                    (s, li) => s + (Number(li.quantity || 0) || 0),
                                    0
                                ),
                                shipment_status: getShipmentStatus(newOrder),
                                customer_full_name: `${customerFirst} ${customerLast}`.trim() || "N/A",
                                __tracking: getBestFulfillment(newOrder)?.tracking_info || []
                            };
                            setSelected(mappedOrder);
                            setOpen(true);
                        }
                    }}
                />

                <CustomerHistoryModal
                    open={!!historyCustomer}
                    onClose={() => setHistoryCustomer(null)}
                    customer={historyCustomer}
                    canViewAmounts={canViewAmounts}
                />
            </Paper>
        </Box>
    );
}