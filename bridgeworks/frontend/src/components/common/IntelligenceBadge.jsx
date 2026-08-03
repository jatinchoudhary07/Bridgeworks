import React from 'react';
import { Chip, Tooltip, Box, Typography } from '@mui/material';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';

const FLAG_CONFIG = {
    GREEN: {
        label: 'Low Risk',
        color: 'success',
        sx: { fontWeight: 600 },
    },
    YELLOW: {
        label: 'Medium Risk',
        color: 'warning',
        sx: { fontWeight: 600 },
    },
    RED: {
        label: 'High Risk',
        color: 'error',
        sx: { fontWeight: 600 },
    },
    NONE: {
        label: 'Not Analyzed',
        color: 'default',
        sx: { fontWeight: 400, opacity: 0.6 },
    },
};

/**
 * IntelligenceBadge
 * Renders a color-coded chip for the order's intelligence_flag.
 * Shows the system_suggestion and reasoning in a tooltip on hover.
 */
export default function IntelligenceBadge({ 
    flag = 'NONE', 
    score = 0, 
    suggestion = '', 
    reasoning = '',
    confirmation_reason = '',
    hold_reason = '',
    confirmationReason = '',
    holdReason = ''
}) {
    const config = FLAG_CONFIG[flag] || FLAG_CONFIG.NONE;
    const finalConfirmationReason = confirmationReason || confirmation_reason;
    const finalHoldReason = holdReason || hold_reason;

    const tooltipContent = (
        <Box sx={{ p: 0.5 }}>
            <Typography variant="caption" display="block" sx={{ fontWeight: 600 }}>
                Score: {score}/100
            </Typography>
            {suggestion && (
                <Typography variant="caption" display="block" sx={{ mt: 0.5 }}>
                    {suggestion}
                </Typography>
            )}
            {reasoning && (
                <Typography variant="caption" display="block" sx={{ mt: 0.5, opacity: 0.85, fontStyle: 'italic', whiteSpace: 'pre-wrap' }}>
                    Reasoning: {reasoning}
                </Typography>
            )}
            {finalConfirmationReason && (
                <Typography variant="caption" display="block" sx={{ mt: 0.5, color: '#81c784', fontWeight: 500 }}>
                    Confirmed because: {finalConfirmationReason}
                </Typography>
            )}
            {finalHoldReason && (
                <Typography variant="caption" display="block" sx={{ mt: 0.5, color: '#e57373', fontWeight: 500 }}>
                    Placed on hold because: {finalHoldReason}
                </Typography>
            )}
        </Box>
    );

    return (
        <Tooltip title={tooltipContent} arrow placement="top">
            <Chip
                icon={<SmartToyOutlinedIcon sx={{ fontSize: '0.85rem' }} />}
                label={`${config.label} (${score})`}
                color={config.color}
                size="small"
                variant="outlined"
                sx={{
                    ...config.sx,
                    fontSize: '0.7rem',
                    height: 22,
                    cursor: 'help',
                    '& .MuiChip-icon': { ml: '4px' },
                }}
            />
        </Tooltip>
    );
}

