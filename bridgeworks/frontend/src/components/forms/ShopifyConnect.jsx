import React, { useState } from 'react';
import { Box, Button, TextField, Typography, Alert } from '@mui/material';
import { BACKEND_URL } from "../../config/api";

export default function ShopifyConnect() {
    const [shopUrl, setShopUrl] = useState('');
    const [error, setError] = useState(null);

    const handleConnect = () => {
        if (!shopUrl) {
            setError("Please enter your Shop URL");
            return;
        }
        let url = shopUrl.trim().replace('https://', '').replace('http://', '');
        if (!url.includes('.myshopify.com')) {
            setError("Please enter a valid myshopify.com domain");
            return;
        }
        window.location.href = `${BACKEND_URL}/api/shopify/install/?shop=${url}`;
    };

    return (
        <Box sx={{ mb: 4, p: 3, border: 1, borderColor: 'primary.main', borderRadius: 2, bgcolor: 'primary.50' }}>
            <Typography variant="h6" color="primary.main" gutterBottom>
                Connect Shopify via OAuth (Recommended)
            </Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
                The fastest and most secure way to connect your store. No manual API keys required.
            </Typography>
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            <Box sx={{ display: 'flex', gap: 2 }}>
                <TextField
                    fullWidth
                    size="small"
                    label="Shop URL (e.g., myshop.myshopify.com)"
                    value={shopUrl}
                    onChange={(e) => {
                        setShopUrl(e.target.value);
                        setError(null);
                    }}
                />
                <Button
                    variant="contained"
                    color="primary"
                    type="button"
                    onClick={handleConnect}
                    sx={{ whiteSpace: 'nowrap' }}
                >
                    Connect Store
                </Button>
            </Box>
        </Box>
    );
}
