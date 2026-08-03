import React from "react";
import {
    Box,
    TextField,
    MenuItem,
    Button,
    FormControl,
    InputLabel,
    Select,
    Chip
} from "@mui/material";

export default function Filters({ filters, setFilters, applyFilters, clearFilters }) {
    const fulfillmentOptions = ["fulfilled", "unfulfilled", "partial", "Tracking_added"];
    const paymentGatewayOptions = ["Gokwik PPCOD", "Gokwik UPI", "cash_on_delivery", "Cash on Delivery (COD)", "Razorpay", "Razorpay PPCOD", "PayPal"];
    const deliveryPartnerOptions = ["BlueDart", "Delhivery", "Shiprocket", "DHL", "FedEx"];
    const shipmentStatusOptions = [
        "Shipment Booked", "AWB Assigned", "Picked Up", "In Transit",
        "Out for Delivery", "Delivered", "Undelivered", "RTO Initiated",
        "RTO In Transit", "RTO Delivered", "Reached Destination", "NDR", "OFP", "Pending", "0"
    ];
    const financialStatusOptions = ["paid", "pending", "refunded", "authorized", "voided", "partially_paid", "partially_refunded"];
    const statusOptions = ["Pending", "Confirmed", "Cancelled", "Batched"];

    const handleDateChange = (event) => {
        const { name, value } = event.target;
        setFilters((prevFilters) => ({
            ...prevFilters,
            [name]: value,
        }));
    };

    const handleMultiSelectChange = (event) => {
        const { name, value } = event.target;
        setFilters(prev => ({
            ...prev,
            [name]: typeof value === 'string' ? value.split(',') : value,
        }));
    };

    const renderSelectedValues = (selected) => (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {selected.map((value) => <Chip key={value} label={value} size="small" />)}
        </Box>
    );

    return (
        <Box
            sx={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: 0.5,
                width: "100%",
            }}
        >
            <TextField
                name="startDate"
                label="Start date"
                type="date"
                InputLabelProps={{ shrink: true }}
                value={filters.startDate || ""}
                onChange={handleDateChange}
                size="small"
            />

            <TextField
                name="endDate"
                label="End date"
                type="date"
                InputLabelProps={{ shrink: true }}
                value={filters.endDate || ""}
                onChange={handleDateChange}
                size="small"
            />

            <FormControl size="small">
                <InputLabel>Status</InputLabel>
                <Select
                    multiple
                    name="status"
                    value={filters.status || []}
                    onChange={handleMultiSelectChange}
                    label="Status"
                    renderValue={renderSelectedValues}
                >
                    {statusOptions.map((option) => (
                        <MenuItem key={option} value={option}>{option}</MenuItem>
                    ))}
                </Select>
            </FormControl>

            <FormControl size="small">
                <InputLabel>Fulfillment</InputLabel>
                <Select
                    multiple
                    name="fulfillmentStatus"
                    value={filters.fulfillmentStatus || []}
                    onChange={handleMultiSelectChange}
                    label="Fulfillment"
                    renderValue={renderSelectedValues}
                >
                    {fulfillmentOptions.map((option) => (
                        <MenuItem key={option} value={option}>{option}</MenuItem>
                    ))}
                </Select>
            </FormControl>

            <FormControl size="small">
                <InputLabel>Payment Status</InputLabel>
                <Select
                    multiple
                    name="financialStatus"
                    value={filters.financialStatus || []}
                    onChange={handleMultiSelectChange}
                    label="Payment Status"
                    renderValue={renderSelectedValues}
                >
                    {financialStatusOptions.map((status) => (
                        <MenuItem key={status} value={status}>{status}</MenuItem>
                    ))}
                </Select>
            </FormControl>

            <FormControl size="small">
                <InputLabel>Payment Gateway</InputLabel>
                <Select
                    multiple
                    name="paymentGateway"
                    value={filters.paymentGateway || []}
                    onChange={handleMultiSelectChange}
                    label="Payment Gateway"
                    renderValue={renderSelectedValues}
                >
                    {paymentGatewayOptions.map((option) => (
                        <MenuItem key={option} value={option}>{option}</MenuItem>
                    ))}
                </Select>
            </FormControl>

            <FormControl size="small">
                <InputLabel>Delivery Partner</InputLabel>
                <Select
                    multiple
                    name="deliveryPartner"
                    value={filters.deliveryPartner || []}
                    onChange={handleMultiSelectChange}
                    label="Delivery Partner"
                    renderValue={renderSelectedValues}
                >
                    {deliveryPartnerOptions.map((option) => (
                        <MenuItem key={option} value={option}>{option}</MenuItem>
                    ))}
                </Select>
            </FormControl>

            <FormControl size="small">
                <InputLabel>Shipment Status</InputLabel>
                <Select
                    multiple
                    name="shipmentStatus"
                    value={filters.shipmentStatus || []}
                    onChange={handleMultiSelectChange}
                    label="Shipment Status"
                    renderValue={renderSelectedValues}
                >
                    {shipmentStatusOptions.map((option) => (
                        <MenuItem key={option} value={option}>{option}</MenuItem>
                    ))}
                </Select>
            </FormControl>
        </Box>
    );
}
