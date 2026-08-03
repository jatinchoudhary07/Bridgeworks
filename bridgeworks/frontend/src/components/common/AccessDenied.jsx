import React from 'react';
import { Box, Typography, Button, Paper } from '@mui/material';
import { LockOutlined, ArrowBack } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

const AccessDenied = () => {
    const navigate = useNavigate();

    return (
        <Box
            sx={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                p: 3,
                bgcolor: '#f8fafc'
            }}
        >
            <Paper
                elevation={0}
                sx={{
                    maxWidth: 480,
                    p: 5,
                    textAlign: 'center',
                    borderRadius: 4,
                    border: '1px solid #e2e8f0',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 3
                }}
            >
                <Box
                    sx={{
                        width: 80,
                        height: 80,
                        borderRadius: '50%',
                        bgcolor: 'error.lighter',
                        color: 'error.main',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        mb: 1
                    }}
                >
                    <LockOutlined sx={{ fontSize: 40 }} />
                </Box>

                <Box>
                    <Typography variant="h5" fontWeight={800} color="#0f172a" gutterBottom>
                        Access Restricted
                    </Typography>
                    <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
                        You don't have the required permissions to view this page. If you believe this is an error, please contact your administrator.
                    </Typography>
                </Box>

                <Box sx={{ display: 'flex', gap: 2, width: '100%' }}>
                    <Button
                        fullWidth
                        variant="contained"
                        startIcon={<ArrowBack />}
                        onClick={() => navigate(-1)}
                        sx={{
                            py: 1.5,
                            borderRadius: 2,
                            textTransform: 'none',
                            fontWeight: 700,
                            boxShadow: 'none',
                            '&:hover': { boxShadow: 'none' }
                        }}
                    >
                        Go Back
                    </Button>
                    <Button
                        fullWidth
                        variant="outlined"
                        onClick={() => navigate('/')}
                        sx={{
                            py: 1.5,
                            borderRadius: 2,
                            textTransform: 'none',
                            fontWeight: 700,
                            borderColor: '#e2e8f0',
                            color: '#475569',
                            '&:hover': { bgcolor: '#f1f5f9', borderColor: '#cbd5e1' }
                        }}
                    >
                        Home Dashboard
                    </Button>
                </Box>
            </Paper>
        </Box>
    );
};

export default AccessDenied;
