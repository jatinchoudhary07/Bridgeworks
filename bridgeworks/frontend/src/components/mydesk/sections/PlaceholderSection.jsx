import React from 'react';
import { Paper, Stack, Typography } from '@mui/material';

export default function PlaceholderSection({ title = 'Coming Soon', description = 'Coming Soon.' }) {
    return (
        <Paper variant="outlined" sx={{ p: 3, borderRadius: 2 }}>
            <Stack spacing={0.75}>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>{title}</Typography>
                <Typography variant="body2" color="text.secondary">{description}</Typography>
            </Stack>
        </Paper>
    );
}
