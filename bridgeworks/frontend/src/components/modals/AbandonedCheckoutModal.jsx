import React, { useState } from "react";
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
    Link,
    Tooltip
} from "@mui/material";
import CloseIcon from '@mui/icons-material/Close';
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import PersonOutlineIcon from '@mui/icons-material/PersonOutline';
import InventoryOutlinedIcon from '@mui/icons-material/InventoryOutlined';
import WhatsAppIcon from '@mui/icons-material/WhatsApp';
import EmailIcon from '@mui/icons-material/Email';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import LinkIcon from '@mui/icons-material/Link';
import ShoppingCartOutlinedIcon from '@mui/icons-material/ShoppingCartOutlined';
import PublicIcon from '@mui/icons-material/Public';
import CampaignIcon from '@mui/icons-material/Campaign';

// Helper functions
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
        maximumFractionDigits: 0
    }).format(amount || 0);
};

// Status Badge Component
const StatusBadge = ({ label, type }) => {
    const colors = {
        pending: { bg: '#FEF3C7', text: '#92400E', border: '#F59E0B' },
        email_sent: { bg: '#DBEAFE', text: '#1E40AF', border: '#3B82F6' },
        whatsapp_sent: { bg: '#D1FAE5', text: '#065F46', border: '#10B981' },
        recovered: { bg: '#D1FAE5', text: '#065F46', border: '#10B981' },
        lost: { bg: '#FEE2E2', text: '#991B1B', border: '#EF4444' },
        default: { bg: '#F3F4F6', text: '#374151', border: '#9CA3AF' }
    };
    const c = colors[type] || colors.default;
    return (
        <Chip
            label={label.toUpperCase().replace('_', ' ')}
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

import { resolveCityFromPincode } from '../../utils/pincodeHelper';

export default function AbandonedCheckoutModal({
    open,
    checkout,
    onClose,
    currentCheckoutIndex = 0,
    totalCheckoutsInList = 1,
    onPrevious = () => { },
    onNext = () => { },
    onStatusChange = () => { }
}) {
    const [copied, setCopied] = useState(false);

    if (!open || !checkout) return null;

    // Support both models with robust fallbacks
    const customerFullName = checkout.customer_name || "Guest";
    const lineItems = checkout.line_items || checkout.items_snapshot || [];
    const checkoutUrl = checkout.abandoned_checkout_url || checkout.source_url || "";
    const phone = checkout.phone || checkout.customer_phone || "";
    const email = checkout.email || checkout.customer_email || "";
    const db_id = checkout.db_id || checkout.id;
    const stage = checkout.flexype_drop_off_state || checkout.session_state || checkout.checkout_stage || "cart";

    const rawCity = checkout.city || checkout.channel_meta?.city || "";
    const province = checkout.province || checkout.channel_meta?.province || checkout.channel_meta?.state || "";
    const zip = checkout.zip || checkout.channel_meta?.zip || checkout.channel_meta?.pincode || "";
    const city = resolveCityFromPincode(zip, rawCity);

    const handleCopy = () => {
        if (checkoutUrl) {
            navigator.clipboard.writeText(checkoutUrl);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    };

    // Stage chip color helper
    const getStageColor = (s) => {
        const cleanStage = (s || '').toUpperCase();
        if (cleanStage.includes('PAYMENT')) return 'warning';
        if (cleanStage.includes('SHIP') || cleanStage.includes('ADD')) return 'info';
        if (cleanStage.includes('LOG') || cleanStage.includes('CONTACT')) return 'primary';
        return 'default';
    };

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
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
                    <Typography variant="h6" fontWeight={700}>
                        Checkout Recovery #{checkout.id || checkout.token || 'N/A'}
                    </Typography>
                    {checkout.recovery_status && (
                        <StatusBadge
                            label={checkout.recovery_status}
                            type={checkout.recovery_status}
                        />
                    )}
                    {stage && (
                        <Chip
                            label={stage.toUpperCase().replace('_', ' ')}
                            size="small"
                            color={getStageColor(stage)}
                            variant="outlined"
                            sx={{ fontWeight: 'bold', fontSize: '0.65rem' }}
                        />
                    )}
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                        {currentCheckoutIndex + 1} of {totalCheckoutsInList}
                    </Typography>
                    <IconButton size="small" onClick={onPrevious} disabled={currentCheckoutIndex === 0}>
                        <NavigateBeforeIcon />
                    </IconButton>
                    <IconButton size="small" onClick={onNext} disabled={currentCheckoutIndex === totalCheckoutsInList - 1}>
                        <NavigateNextIcon />
                    </IconButton>
                    <IconButton size="small" onClick={onClose}>
                        <CloseIcon />
                    </IconButton>
                </Box>
            </Box>

            {/* Subheader - Date & Channel */}
            <Box sx={{ px: 3, py: 1.5, bgcolor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
                <Typography variant="caption" color="text.secondary">
                    Abandoned At: {formatDate(checkout.created_at)} • Source: Shopify
                </Typography>
            </Box>

            <DialogContent sx={{ p: 3 }}>
                <Stack spacing={2.5}>

                    {/* ITEMS CARD */}
                    <SectionCard>
                        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <ShoppingCartOutlinedIcon fontSize="small" color="primary" /> Line Items in Cart
                        </Typography>

                        {lineItems.length === 0 ? (
                            <Typography variant="body2" color="text.secondary">No items found in this cart.</Typography>
                        ) : (
                            lineItems.map((item, index) => (
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
                                    </Box>
                                    <Typography variant="body2" color="text.secondary">
                                        {formatCurrency(item.price)} × {item.qty || 1}
                                    </Typography>
                                    <Typography variant="body2" fontWeight={600}>
                                        {formatCurrency((item.price || 0) * (item.qty || 1))}
                                    </Typography>
                                </Box>
                            ))
                        )}
                    </SectionCard>

                    {/* RECOVERY LINK & ACTIONS */}
                    <SectionCard>
                        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <LinkIcon fontSize="small" color="primary" /> Recovery Actions
                        </Typography>

                        <Stack spacing={2}>
                            {checkoutUrl ? (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1.5, bgcolor: '#F9FAFB', borderRadius: 1.5, border: '1px solid', borderColor: 'divider' }}>
                                    <Typography variant="caption" color="text.secondary" sx={{ minWidth: 90, fontWeight: 'bold' }}>Checkout Link:</Typography>
                                    <Typography variant="body2" sx={{ flex: 1, wordBreak: 'break-all', fontFamily: 'monospace', fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {checkoutUrl}
                                    </Typography>
                                    <Tooltip title={copied ? "Copied!" : "Copy URL"}>
                                        <IconButton size="small" onClick={handleCopy} color={copied ? "success" : "default"}>
                                            <ContentCopyIcon fontSize="small" />
                                        </IconButton>
                                    </Tooltip>
                                    <Button
                                        variant="outlined"
                                        size="small"
                                        component="a"
                                        href={checkoutUrl}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        startIcon={<PublicIcon fontSize="small" />}
                                    >
                                        Visit
                                    </Button>
                                </Box>
                            ) : (
                                <Typography variant="body2" color="text.secondary">No checkout URL available.</Typography>
                            )}

                            <Stack direction="row" spacing={2} sx={{ mt: 1 }}>
                                {phone && (
                                    <Button
                                        variant="contained"
                                        color="success"
                                        fullWidth
                                        startIcon={<WhatsAppIcon />}
                                        onClick={() => {
                                            const cleanPhone = phone.replace(/[^0-9]/g, '');
                                            const text = encodeURIComponent(`Hi ${customerFullName}, we noticed you left items in your shopping cart. You can complete your purchase here: ${checkoutUrl}`);
                                            window.open(`https://wa.me/${cleanPhone}?text=${text}`, '_blank');
                                            onStatusChange(db_id, 'whatsapp_sent');
                                        }}
                                    >
                                        WhatsApp Recovery
                                    </Button>
                                )}
                                {email && (
                                    <Button
                                        variant="contained"
                                        color="primary"
                                        fullWidth
                                        startIcon={<EmailIcon />}
                                        onClick={() => {
                                            const subject = encodeURIComponent("Complete your purchase at BridgeWorks Store");
                                            const body = encodeURIComponent(`Hi ${customerFullName},\n\nWe noticed you left items in your shopping cart. You can complete your purchase by clicking the link below:\n\n${checkoutUrl}\n\nThank you!`);
                                            window.open(`mailto:${email}?subject=${subject}&body=${body}`, '_blank');
                                            onStatusChange(db_id, 'email_sent');
                                        }}
                                    >
                                        Email Recovery
                                    </Button>
                                )}
                            </Stack>
                        </Stack>
                    </SectionCard>

                    {/* PAYMENT SUMMARY CARD */}
                    <SectionCard>
                        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
                            Cart Value Breakdown
                        </Typography>

                        <Divider sx={{ my: 1.5 }} />

                        <InfoRow label="Subtotal Items" value={`${checkout.item_count || lineItems.length} item(s)`} />
                        <InfoRow label="Drop-off Stage" value={stage.toUpperCase().replace('_', ' ')} />
                        <InfoRow label="Recovery Status" value={checkout.recovery_status || 'pending'} />

                        <Divider sx={{ my: 1.5 }} />

                        <InfoRow label="Total Value" value={formatCurrency(checkout.cart_value)} isBold />
                    </SectionCard>

                    {/* CUSTOMER DETAILS */}
                    <SectionCard sx={{ bgcolor: '#F9FAFB' }}>
                        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <PersonOutlineIcon fontSize="small" color="primary" /> Customer & Shipping Info
                        </Typography>
                        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2.5, mb: 2 }}>
                            <Box>
                                <Typography variant="caption" color="text.secondary">Name</Typography>
                                <Typography variant="body2" fontWeight={500}>{customerFullName}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">Phone</Typography>
                                <Typography variant="body2" fontWeight={500}>{phone || 'N/A'}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">Email</Typography>
                                <Typography variant="body2" fontWeight={500}>{email || 'N/A'}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">Orders Count (Lifetime)</Typography>
                                <Typography variant="body2" fontWeight={500}>{checkout.orders_count || 0}</Typography>
                            </Box>
                        </Box>

                        <Divider sx={{ my: 1.5 }} />

                        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
                            Geographic Info
                        </Typography>
                        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr 1fr' }, gap: 2 }}>
                            <Box>
                                <Typography variant="caption" color="text.secondary">City</Typography>
                                <Typography variant="body2">{city || 'N/A'}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">State / Province</Typography>
                                <Typography variant="body2">{province || 'N/A'}</Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary">Pincode / Zip</Typography>
                                <Typography variant="body2">{zip || 'N/A'}</Typography>
                            </Box>
                        </Box>
                    </SectionCard>

                    {/* TECHNICAL METADATA */}
                    <SectionCard>
                        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1.5 }}>
                            System Details
                        </Typography>
                        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2 }}>
                            <Box>
                                <Typography variant="caption" color="text.secondary" fontWeight={600}>Shopify Token</Typography>
                                <Typography variant="body2" sx={{ wordBreak: 'break-all', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                                    {checkout.token || 'N/A'}
                                </Typography>
                            </Box>
                            <Box>
                                <Typography variant="caption" color="text.secondary" fontWeight={600}>Internal DB ID</Typography>
                                <Typography variant="body2" sx={{ fontSize: '0.75rem', fontFamily: 'monospace' }}>
                                    {db_id || 'N/A'}
                                </Typography>
                            </Box>
                        </Box>
                    </SectionCard>

                    {/* MARKETING ATTRIBUTION */}
                    <SectionCard sx={{ borderColor: 'rgba(99,102,241,0.2)', bgcolor: 'rgba(99,102,241,0.02)' }}>
                        <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <CampaignIcon fontSize="small" sx={{ color: '#6366F1' }} /> Marketing Attribution
                        </Typography>

                        {/* UTM Parameters */}
                        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2, mb: 2 }}>
                            {[
                                { label: 'UTM Source', value: checkout.utm_source },
                                { label: 'UTM Medium', value: checkout.utm_medium },
                                { label: 'UTM Campaign', value: checkout.utm_campaign },
                                { label: 'UTM Content', value: checkout.utm_content },
                                { label: 'UTM Term', value: checkout.utm_term },
                                { label: 'Source Name', value: checkout.source_name },
                            ].map(f => (
                                <Box key={f.label}>
                                    <Typography variant="caption" color="text.secondary" fontWeight={600}>{f.label}</Typography>
                                    <Typography variant="body2" sx={{ wordBreak: 'break-all', color: f.value ? 'text.primary' : 'text.disabled' }}>
                                        {f.value || '—'}
                                    </Typography>
                                </Box>
                            ))}
                        </Box>

                        <Divider sx={{ my: 1.5 }} />

                        {/* Tracking / Session fields */}
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                            {[
                                { label: 'Referring Site', value: checkout.referring_site },
                                { label: 'Landing Page', value: checkout.landing_site },
                                { label: 'FlexPe Checkout URL', value: checkout.flexype_checkout_url },
                            ].map(f => (
                                <Box key={f.label}>
                                    <Typography variant="caption" color="text.secondary" fontWeight={600}>{f.label}</Typography>
                                    <Typography variant="body2" sx={{ wordBreak: 'break-all', fontSize: '0.8rem', color: f.value ? 'text.primary' : 'text.disabled' }}>
                                        {f.value || '—'}
                                    </Typography>
                                </Box>
                            ))}
                            <Box>
                                <Typography variant="caption" color="text.secondary" fontWeight={600}>fbclid</Typography>
                                <Typography variant="body2" sx={{ wordBreak: 'break-all', fontSize: '0.72rem', fontFamily: 'monospace', color: checkout.fbclid ? 'text.secondary' : 'text.disabled' }}>
                                    {checkout.fbclid || '—'}
                                </Typography>
                            </Box>
                        </Box>
                    </SectionCard>


                </Stack>
            </DialogContent>
        </Dialog>
    );
}
