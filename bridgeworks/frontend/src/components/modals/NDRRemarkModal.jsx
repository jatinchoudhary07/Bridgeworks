import React, { useState, useEffect } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField } from '@mui/material';

export default function NDRRemarkModal({ open, onClose, order, onSave }) {
    const [remark, setRemark] = useState("");

    useEffect(() => {
        if (order) setRemark(order.ndr_remarks || "");
    }, [order]);

    const handleSave = () => {
        onSave(order.id, remark);
        onClose();
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <DialogTitle>Update Remark - Order #{order?.order_number}</DialogTitle>
            <DialogContent>
                <TextField
                    autoFocus
                    margin="dense"
                    label="NDR Remark"
                    type="text"
                    fullWidth
                    multiline
                    rows={3}
                    variant="outlined"
                    value={remark}
                    onChange={(e) => setRemark(e.target.value)}
                    placeholder="E.g., Customer requested delivery on Monday..."
                />
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Cancel</Button>
                <Button onClick={handleSave} variant="contained" color="primary">Save Remark</Button>
            </DialogActions>
        </Dialog>
    );
}