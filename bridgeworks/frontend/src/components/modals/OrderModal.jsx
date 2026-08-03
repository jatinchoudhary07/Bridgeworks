import React from "react";
import {
    Box,
    Typography,
    Paper,
    Button,
    Dialog,
    DialogContent,
    IconButton,
    Chip,
    Stack,
    Divider,
    Avatar,
    Link
} from "@mui/material";
import CloseIcon from '@mui/icons-material/Close';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import LocalShippingOutlinedIcon from '@mui/icons-material/LocalShippingOutlined';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import InventoryOutlinedIcon from '@mui/icons-material/InventoryOutlined';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import AccessTimeIcon from '@mui/icons-material/AccessTime';

// --- Helper Functions ---
const formatDate = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
};

const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 2
    }).format(amount || 0);
};

// Status Badge Component
const StatusBadge = ({ label, type }) => {
    const colors = {
        warning: { bg: '#FEF3C7', text: '#92400E', border: '#F59E0B' },
        success: { bg: '#D1FAE5', text: '#065F46', border: '#10B981' },
        error: { bg: '#FEE2E2', text: '#991B1B', border: '#EF4444' },
        info: { bg: '#DBEAFE', text: '#1E40AF', border: '#3B82F6' },
        default: { bg: '#F3F4F6', text: '#374151', border: '#9CA3AF' }
    };
    const c = colors[type] || colors.default;
    return (
        <Chip
            label={label}
            size="small"
            sx={{
                bgcolor: c.bg,
                color: c.text,
                border: `1px solid ${c.border}`,
                fontWeight: 600,
                fontSize: '0.75rem',
                height: 24,
                '& .MuiChip-label': { px: 1.5 }
            }}
        />
    );
};

// Section Card Component
const SectionCard = ({ children, sx = {} }) => (
    <Paper
        elevation={0}
        sx={{
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 2,
            p: 2,
            ...sx
        }}
    >
        {children}
    </Paper>
);

// Info Row Component
const InfoRow = ({ label, value, isBold = false }) => (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', py: 0.75 }}>
        <Typography variant="body2" color="text.secondary">{label}</Typography>
        <Typography variant="body2" fontWeight={isBold ? 600 : 400} textAlign="right">
            {value}
        </Typography>
    </Box>
);

export default function OrderModal({
    open,
    order,
    onClose,
    currentOrderIndex = 0,
    totalOrdersInList = 1,
    onPrevious = () => { },
    onNext = () => { }
}) {
    if (!open || !order) return null;

    // --- Data Extraction ---
    const customerFullName = `${order.customer_first_name || ""} ${order.customer_last_name || ""}`.trim() || "N/A";
    const paymentGateways = order.payment_gateway_names || [];
    const paymentMethod = order.payment_method ||
        (paymentGateways.some(p => p?.toLowerCase().includes('cash_on_delivery') || p?.toLowerCase().includes('cash on delivery')) ? 'COD' :
            paymentGateways.some(p => p?.toLowerCase().includes('ppcod')) ? 'Partially Paid' : 'Prepaid');

    const lineItems = order.line_items || [];
    const totalQuantity = lineItems.reduce((s, li) => s + Number(li.quantity || 0), 0);
    const shopifyExtra = order.shopify_extra || null;

    // Tracking Info
    const trackingInfo = order.tracking_info || order.fulfillments?.[0]?.tracking_info?.[0] || {};
    const awbNumber = trackingInfo.number || "Not Assigned";
    const courierName = trackingInfo.company || "N/A";
    const trackingUrl = trackingInfo.url || "";

    // Status Mappings
    const getStatusType = (status) => {
        if (!status) return 'default';
        const s = status.toLowerCase();
        if (s === 'cancelled' || s.includes('rto') || s.includes('failed')) return 'error';
        if (s === 'confirmed' || s === 'delivered' || s === 'completed') return 'success';
        if (s === 'pending' || s.includes('hold') || s.includes('ndr')) return 'warning';
        if (s.includes('transit') || s.includes('shipped') || s.includes('fulfil')) return 'info';
        return 'default';
    };

    const getFulfillmentType = (status) => {
        if (!status) return 'warning';
        const s = status.toLowerCase();
        if (s === 'fulfilled' || s === 'delivered') return 'success';
        if (s === 'unfulfilled') return 'warning';
        return 'default';
    };

    const getFinancialType = (status) => {
        if (!status) return 'default';
        const s = status.toLowerCase();
        if (s === 'paid') return 'success';
        if (s === 'pending' || s === 'partially_paid') return 'warning';
        if (s === 'refunded' || s === 'voided') return 'error';
        return 'default';
    };

    const isFirstOrder = currentOrderIndex === 0;
    const isLastOrder = currentOrderIndex === totalOrdersInList - 1;

    return (
        <Dialog
            open={open}
            onClose={onClose}
            fullWidth
            maxWidth="md"
            PaperProps={{
                sx: {
                    borderRadius: 3,
                    bgcolor: '#FAFAFA'
                }
            }}
        >
            {/* Header */}
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                px: 3,
                py: 2,
                borderBottom: '1px solid',
                borderColor: 'divider',
                bgcolor: 'background.paper'
            }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Typography variant="h6" fontWeight={700}>
                        #{order.order_number}
                    </Typography>
                    <StatusBadge
                        label={order.financial_status || 'Payment pending'}
                        type={getFinancialType(order.financial_status)}
                    />
                    <StatusBadge
                        label={order.fulfillment_status || 'Unfulfilled'}
                        type={getFulfillmentType(order.fulfillment_status)}
                    />
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                        {currentOrderIndex + 1} of {totalOrdersInList}
                    </Typography>
                    <IconButton size="small" onClick={onPrevious} disabled={isFirstOrder}>
                        <NavigateBeforeIcon />
                    </IconButton>
                    <IconButton size="small" onClick={onNext} disabled={isLastOrder}>
                        <NavigateNextIcon />
                    </IconButton>
                    <IconButton size="small" onClick={onClose}>
                        <CloseIcon />
                    </IconButton>
                </Box>
            </Box>

            {/* Subheader - Date & Channel */}
            <Box sx={{ px: 3, py: 1, bgcolor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography variant="caption" color="text.secondary">
                    {formatDate(order.created_at)} • {paymentMethod}
                </Typography>
            </Box>

            <DialogContent sx={{ p: 3 }}>
                <Stack spacing={2.5}>

                    {/* FULFILLMENT CARD */}
                    <SectionCard>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                            <StatusBadge
                                label={order.fulfillment_status || 'Unfulfilled'}
                                type={getFulfillmentType(order.fulfillment_status)}
                            />
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 1 }}>
                                <PersonOutlineIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                                <Typography variant="body2" fontWeight={500}>{customerFullName}</Typography>
                            </Box>
                        </Box>

                        {/* Tracking Info */}
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2, p: 1.5, bgcolor: '#F9FAFB', borderRadius: 1.5 }}>
                            <LocalShippingOutlinedIcon sx={{ color: 'primary.main' }} />
                            <Box sx={{ flex: 1 }}>
                                <Typography variant="body2" fontWeight={600}>
                                    {courierName}
                                </Typography>
                                {trackingUrl ? (
                                    <Link href={trackingUrl} target="_blank" underline="hover" sx={{ fontSize: '0.875rem' }}>
                                        {awbNumber}
                                    </Link>
                                ) : (
                                    <Typography variant="body2" color="text.secondary">{awbNumber}</Typography>
                                )}
                            </Box>
                            {order.current_status && (
                                <Chip
                                    label={order.current_status.replace(/_/g, ' ')}
                                    size="small"
                                    color="primary"
                                    variant="outlined"
                                />
                            )}
                        </Box>

                        {/* Line Items */}
                        {lineItems.map((item, index) => (
                            <Box key={index} sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 2,
                                py: 1.5,
                                borderBottom: index < lineItems.length - 1 ? '1px solid' : 'none',
                                borderColor: 'divider'
                            }}>
                                <Avatar
                                    variant="rounded"
                                    sx={{
                                        width: 48,
                                        height: 48,
                                        bgcolor: '#F3F4F6',
                                        border: '1px solid',
                                        borderColor: 'divider'
                                    }}
                                >
                                    <InventoryOutlinedIcon sx={{ color: 'text.secondary' }} />
                                </Avatar>
                                <Box sx={{ flex: 1 }}>
                                    <Typography variant="body2" fontWeight={500}>{item.title}</Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {item.variant_title || item.sku || 'Default'}
                                    </Typography>
                                </Box>
                                <Typography variant="body2" color="text.secondary">
                                    {formatCurrency(item.price)} × {item.quantity}
                                </Typography>
                                <Typography variant="body2" fontWeight={600}>
                                    {formatCurrency(item.price * item.quantity)}
                                </Typography>
                            </Box>
                        ))}
                    </SectionCard>

                    {/* PAYMENT SUMMARY CARD */}
                    <SectionCard>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                            <StatusBadge
                                label={order.financial_status || 'Payment pending'}
                                type={getFinancialType(order.financial_status)}
                            />
                            {order.financial_status?.toLowerCase() === 'pending' && (
                                <Typography variant="caption" color="warning.main" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                    <WarningAmberIcon sx={{ fontSize: 14 }} />
                                    Awaiting payment confirmation
                                </Typography>
                            )}
                        </Box>

                        <Divider sx={{ my: 1.5 }} />

                        <InfoRow label="Subtotal" value={`${totalQuantity} item${totalQuantity > 1 ? 's' : ''}`} />
                        <InfoRow label="Payment Method" value={paymentMethod} />
                        <InfoRow label="Shipping" value="Standard Shipping" />

                        <Divider sx={{ my: 1.5 }} />

                        <InfoRow label="Total" value={formatCurrency(order.total_price)} isBold />
                    </SectionCard>

                    {/* INTERNAL STATUS CARD */}
                    <SectionCard>
                        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2 }}>
                            Internal Status
                        </Typography>

                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                            <StatusBadge label={order.status || 'Pending'} type={getStatusType(order.status)} />
                            {order.internal_fulfillment_status && (
                                <StatusBadge label={order.internal_fulfillment_status} type={getStatusType(order.internal_fulfillment_status)} />
                            )}
                            {order.is_ndr && <StatusBadge label="NDR" type="warning" />}
                        </Box>

                        <Stack spacing={1}>
                            {order.is_auto_confirmed ? (
                                <Stack spacing={0.5}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <CheckCircleOutlineIcon sx={{ fontSize: 16, color: 'success.main' }} />
                                        <Typography variant="caption">
                                            Confirmed by 🤖 <strong>Shori</strong> on {formatDate(order.confirmed_at)}
                                        </Typography>
                                    </Box>
                                    {order.agent_reasoning && (
                                        <Box sx={{ ml: 3, p: 1, bgcolor: '#f0fdf4', borderRadius: 1.5, border: '1px solid #dcfce7' }}>
                                            <Typography variant="caption" color="text.secondary" display="block" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.7rem' }}>
                                                {order.agent_reasoning}
                                            </Typography>
                                        </Box>
                                    )}
                                </Stack>
                            ) : order.confirmed_by_username ? (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <CheckCircleOutlineIcon sx={{ fontSize: 16, color: 'success.main' }} />
                                    <Typography variant="caption">
                                        Confirmed by <strong>{order.confirmed_by_username}</strong> on {formatDate(order.confirmed_at)}
                                    </Typography>
                                </Box>
                            ) : null}
                            {order.packaged_by_username && (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <InventoryOutlinedIcon sx={{ fontSize: 16, color: 'info.main' }} />
                                    <Typography variant="caption">
                                        Packaged by <strong>{order.packaged_by_username}</strong> on {formatDate(order.packaged_at)}
                                    </Typography>
                                </Box>
                            )}
                            {order.fulfillment_reason && (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <WarningAmberIcon sx={{ fontSize: 16, color: 'warning.main' }} />
                                    <Typography variant="caption" color="warning.dark">
                                        Reason: {order.fulfillment_reason}
                                    </Typography>
                                </Box>
                            )}
                        </Stack>

                        {/* Hold History */}
                        {(order.hold_history?.length > 0) && (
                            <Box sx={{ mt: 2, p: 1.5, bgcolor: '#FEF3C7', borderRadius: 1.5, border: '1px solid #F59E0B' }}>
                                <Typography variant="caption" fontWeight={600} color="#92400E">
                                    Hold History:
                                </Typography>
                                {order.hold_history.slice(-3).map((h, i) => (
                                    <Typography key={i} variant="caption" display="block" color="#92400E">
                                        • Batch #{h.batch_id}: {h.reason}
                                    </Typography>
                                ))}
                            </Box>
                        )}
                    </SectionCard>

                    {/* TIMELINE / TRACKING EVENTS */}
                    {order.tracking_events?.length > 0 && (
                        <SectionCard>
                            <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                                <AccessTimeIcon sx={{ fontSize: 18 }} />
                                Timeline
                            </Typography>

                            <Stack spacing={1.5}>
                                {order.tracking_events.slice(0, 5).map((event, index) => (
                                    <Box key={index} sx={{
                                        display: 'flex',
                                        gap: 2,
                                        pl: 2,
                                        borderLeft: '2px solid',
                                        borderColor: index === 0 ? 'primary.main' : 'divider'
                                    }}>
                                        <Box>
                                            <Typography variant="body2" fontWeight={index === 0 ? 600 : 400}>
                                                {event.status?.replace(/_/g, ' ')}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                {formatDate(event.datetime)}
                                            </Typography>
                                            {event.details && (
                                                <Typography variant="caption" display="block" color="text.secondary">
                                                    {event.details}
                                                </Typography>
                                            )}
                                        </Box>
                                    </Box>
                                ))}
                            </Stack>
                        </SectionCard>
                    )}

                    {/* CUSTOMER INFO */}
                    <SectionCard sx={{ bgcolor: '#F9FAFB' }}>
                        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
                            Customer Details
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            <Box>
                                <Typography variant="caption" color="text.secondary">Name</Typography>
                                <Typography variant="body2" fontWeight={500}>{customerFullName}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">Phone</Typography>
                                <Typography variant="body2" fontWeight={500}>{order.contact_phone || 'N/A'}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">Email</Typography>
                                <Typography variant="body2" fontWeight={500}>{order.contact_email || 'N/A'}</Typography>
                            </Box>
                            {shopifyExtra?.customer_orders_count != null && (
                                <Box>
                                    <Typography variant="caption" color="text.secondary">Lifetime Orders</Typography>
                                    <Typography variant="body2" fontWeight={500}>{shopifyExtra.customer_orders_count}</Typography>
                                </Box>
                            )}
                            {shopifyExtra?.customer_total_spent && (
                                <Box>
                                    <Typography variant="caption" color="text.secondary">Lifetime Spent</Typography>
                                    <Typography variant="body2" fontWeight={500}>₹{shopifyExtra.customer_total_spent}</Typography>
                                </Box>
                            )}
                        </Box>
                        <Box sx={{ mt: 1.5 }}>
                            <Typography variant="caption" color="text.secondary">Shipping Address</Typography>
                            <Typography variant="body2">{order.shipping_address || 'N/A'}</Typography>
                        </Box>
                    </SectionCard>

                    {/* TAGS */}
                    {order.tags && (
                        <SectionCard>
                            <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                                Tags
                            </Typography>
                            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                {order.tags.split(',').map((tag, i) => (
                                    <Chip
                                        key={i}
                                        label={tag.trim()}
                                        size="small"
                                        variant="outlined"
                                        sx={{ fontSize: '0.75rem', height: 24 }}
                                    />
                                ))}
                            </Box>
                        </SectionCard>
                    )}

                    {/* NOTES */}
                    {shopifyExtra?.note && (
                        <SectionCard>
                            <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>
                                Notes
                            </Typography>
                            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                                {shopifyExtra.note}
                            </Typography>
                        </SectionCard>
                    )}

                    {/* ADDITIONAL DETAILS (from Shopify raw_data) */}
                    {shopifyExtra && (
                        <SectionCard>
                            <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
                                Additional Details
                            </Typography>
                            <Stack spacing={0.75}>
                                {shopifyExtra.source_name && (
                                    <Box>
                                        <Typography variant="caption" color="text.secondary" fontWeight={600}>source</Typography>
                                        <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>{shopifyExtra.source_name}</Typography>
                                    </Box>
                                )}
                                {shopifyExtra.browser_ip && (
                                    <Box>
                                        <Typography variant="caption" color="text.secondary" fontWeight={600}>browser_ip</Typography>
                                        <Typography variant="body2">{shopifyExtra.browser_ip}</Typography>
                                    </Box>
                                )}
                                {shopifyExtra.user_agent && (
                                    <Box>
                                        <Typography variant="caption" color="text.secondary" fontWeight={600}>user_agent</Typography>
                                        <Typography variant="body2" sx={{ wordBreak: 'break-all', fontSize: '0.75rem' }}>{shopifyExtra.user_agent}</Typography>
                                    </Box>
                                )}
                                {shopifyExtra.landing_site && (
                                    <Box>
                                        <Typography variant="caption" color="text.secondary" fontWeight={600}>landing_site</Typography>
                                        <Typography variant="body2" sx={{ wordBreak: 'break-all', fontSize: '0.75rem' }}>{shopifyExtra.landing_site}</Typography>
                                    </Box>
                                )}
                                {shopifyExtra.referring_site && (
                                    <Box>
                                        <Typography variant="caption" color="text.secondary" fontWeight={600}>referring_site</Typography>
                                        <Typography variant="body2" sx={{ wordBreak: 'break-all', fontSize: '0.75rem' }}>{shopifyExtra.referring_site}</Typography>
                                    </Box>
                                )}
                                {/* Note Attributes (gokwik_cid, utm_source, etc.) */}
                                {shopifyExtra.note_attributes && Object.entries(shopifyExtra.note_attributes).map(([key, value]) => (
                                    <Box key={key}>
                                        <Typography variant="caption" color="text.secondary" fontWeight={600}>{key}</Typography>
                                        <Typography variant="body2" sx={{ wordBreak: 'break-all', fontSize: '0.75rem' }}>{String(value)}</Typography>
                                    </Box>
                                ))}
                            </Stack>
                        </SectionCard>
                    )}

                </Stack>
            </DialogContent>
        </Dialog>
    );
};
