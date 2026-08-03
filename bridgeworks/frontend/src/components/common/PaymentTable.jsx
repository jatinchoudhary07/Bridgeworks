import React from 'react';
import {
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Skeleton
} from '@mui/material';

// --- Helper Functions ---

// Formats number to Indian Currency (e.g., ₹1,200)
const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        maximumFractionDigits: 0
    }).format(amount || 0);
};

// Calculates Average Order Value (Amount / Qty)
const calculateAOV = (amount, qty) => {
    if (!qty || qty === 0) return formatCurrency(0);
    return formatCurrency(amount / qty);
};

export default function PaymentTable({ kpiData, isLoading, canViewAmounts = true, withSpacer = false }) {

    // 1. Safe Access to Data
    // We default to 0 to prevent crashes if API data hasn't arrived yet
    const breakdown = kpiData?.payment_breakdown || {
        prepaid: { qty: 0, amount: 0 },
        ppcod: { qty: 0, amount: 0 },
        cod: { qty: 0, amount: 0 }
    };

    // 2. Calculate Totals Dynamically
    const totalQty = (breakdown.prepaid.qty || 0) + (breakdown.ppcod.qty || 0) + (breakdown.cod.qty || 0);
    const totalAmount = (breakdown.prepaid.amount || 0) + (breakdown.ppcod.amount || 0) + (breakdown.cod.amount || 0);

    // 3. Build Rows
    const rows = [
        {
            type: 'Prepaid',
            qty: breakdown.prepaid.qty,
            amount: canViewAmounts ? formatCurrency(breakdown.prepaid.amount) : "₹ ****",
            aov: canViewAmounts ? calculateAOV(breakdown.prepaid.amount, breakdown.prepaid.qty) : "₹ ****"
        },
        {
            type: 'Partially Paid',
            qty: breakdown.ppcod.qty,
            amount: canViewAmounts ? formatCurrency(breakdown.ppcod.amount) : "₹ ****",
            aov: canViewAmounts ? calculateAOV(breakdown.ppcod.amount, breakdown.ppcod.qty) : "₹ ****"
        },
        {
            type: 'COD',
            qty: breakdown.cod.qty,
            amount: canViewAmounts ? formatCurrency(breakdown.cod.amount) : "₹ ****",
            aov: canViewAmounts ? calculateAOV(breakdown.cod.amount, breakdown.cod.qty) : "₹ ****"
        },
        {
            type: 'Total',
            qty: totalQty,
            amount: canViewAmounts ? formatCurrency(totalAmount) : "₹ ****",
            aov: canViewAmounts ? calculateAOV(totalAmount, totalQty) : "₹ ****"
        }
    ];

    // 4. Loading State
    if (isLoading) {
        return (
            <Paper 
                variant="outlined" 
                sx={{ 
                    p: withSpacer ? 1.25 : 1, 
                    borderRadius: 1.5, 
                    height: withSpacer ? 'auto' : '100%', 
                    display: 'flex', 
                    flexDirection: 'column', 
                    justifyContent: 'center',
                    border: '2px solid #cbd5e1',
                    boxShadow: 'none'
                }}
            >
                {withSpacer && <div style={{ height: '40px', marginBottom: '12px' }} />}
                <Skeleton variant="rectangular" height={30} sx={{ mb: 1 }} />
                <Skeleton variant="rectangular" height={30} sx={{ mb: 1 }} />
                <Skeleton variant="rectangular" height={30} sx={{ mb: 1 }} />
                <Skeleton variant="rectangular" height={40} />
            </Paper>
        );
    }

    return (
        <Paper 
            variant="outlined" 
            sx={{ 
                p: withSpacer ? 1.25 : 1, 
                borderRadius: 1.5, 
                height: withSpacer ? 'auto' : '100%', 
                display: 'flex', 
                flexDirection: 'column',
                border: '2px solid #cbd5e1',
                boxShadow: 'none'
            }}
        >
            {withSpacer && <div style={{ height: '40px', marginBottom: '12px' }} />}
            <TableContainer sx={{ flex: 1 }}>
                <Table size="small" sx={{ '& .MuiTableCell-root': { py: 0.5, fontSize: '0.75rem' } }}>
                    <TableHead>
                        <TableRow>
                            <TableCell sx={{ fontWeight: 'bold', borderBottom: '2px solid #94a3b8', color: 'text.primary' }}>Type</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 'bold', borderBottom: '2px solid #94a3b8', color: 'text.primary' }}>QTY</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 'bold', borderBottom: '2px solid #94a3b8', color: 'text.primary' }}>Amount</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 'bold', borderBottom: '2px solid #94a3b8', color: 'text.primary' }}>AOV</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {rows.map((row, index) => (
                            <TableRow
                                key={index}
                                sx={{
                                    backgroundColor: row.type === 'Total' ? 'action.hover' : 'inherit',
                                    '& td': {
                                        fontWeight: row.type === 'Total' ? 'bold' : 'normal',
                                        borderBottom: row.type === 'Total' ? 0 : '1.5px solid #cbd5e1',
                                        color: row.type === 'Total' ? 'text.primary' : 'text.secondary'
                                    }
                                }}
                            >
                                <TableCell>{row.type}</TableCell>
                                <TableCell align="right">{row.qty}</TableCell>
                                <TableCell align="right">{row.amount}</TableCell>
                                <TableCell align="right">{row.aov}</TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Paper>
    );
}