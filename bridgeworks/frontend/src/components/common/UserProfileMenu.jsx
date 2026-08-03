import React, { useState } from 'react';
import {
    Box, IconButton, Avatar, Menu, MenuItem, ListItemIcon, ListItemText, Divider, Typography, Tooltip, Switch
} from '@mui/material';
import AccountCircleIcon from '@mui/icons-material/AccountCircle';
import SettingsIcon from '@mui/icons-material/Settings';
import LogoutIcon from '@mui/icons-material/Logout';
import CreditCardIcon from '@mui/icons-material/CreditCard'; // For Billing
import DarkModeIcon from '@mui/icons-material/DarkMode'; // For Dark Mode
import VpnKeyIcon from '@mui/icons-material/VpnKey'; // For API Keys

import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { apiClient, clearToken, getToken } from '../../apiClient';
import { BACKEND_URL } from '../../config/api';
import NotificationBell from './NotificationBell';
import { useTheme } from '../../contexts';
import { useUser } from '../../contexts/UserContext';
import PresenceBadge from './PresenceBadge';
import StatusSelector from './StatusSelector';

// --- User Profile Menu Component ---
export default function UserProfileMenu({ userName = "User", userEmail = "email@example.com", profilePicture = null }) {
    const [anchorEl, setAnchorEl] = useState(null); // State to manage where the menu opens
    const open = Boolean(anchorEl);
    const navigate = useNavigate();
    const { mode, toggleTheme } = useTheme(); // Get theme mode and toggle function
    const { user } = useUser();

    // Handles opening the menu when the avatar is clicked
    const handleClick = (event) => {
        setAnchorEl(event.currentTarget);
    };

    // Handles closing the menu
    const handleClose = () => {
        setAnchorEl(null);
    };

    // Handles the logout action
    const handleLogout = async () => {
        handleClose(); // Close the menu first

        // End the attendance session using apiClient to ensure automatic token refresh
        // if the access token has expired.
        try {
            await apiClient('/api/attendance/session/end/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source: 'manual' }),
                keepalive: true,
            });
        } catch (err) {
            console.error("Failed to end attendance session on logout:", err);
        }

        sessionStorage.removeItem('attendance_session_started');
        sessionStorage.removeItem('attendance_session_user_id');
        try {
            await apiClient('/api/logout/', { method: 'POST', credentials: 'include' });
        } catch (err) {
            console.error("Logout request failed:", err);
        } finally {
            clearToken();
            window.location.href = '/login';
        }
    };

    // Placeholder function for Profile page navigation
    const handleProfileClick = () => {
        handleClose();
        alert("Profile page not implemented yet.");
    };

    // Placeholder function for Billing page navigation
    const handleBillingClick = () => {
        handleClose();
        alert("Billing page not implemented yet.");
    };

    return (
        <>
            {/* The clickable avatar icon in the top bar */}
            <Tooltip title="Account settings">
                <IconButton
                    onClick={handleClick}
                    size="small"
                    sx={{ ml: 2 }} // Add some margin to the left
                    aria-controls={open ? 'account-menu' : undefined}
                    aria-haspopup="true"
                    aria-expanded={open ? 'true' : undefined}
                >
                    <PresenceBadge userId={user?.id} size="small">
                        <Avatar
                            src={profilePicture || undefined}
                            sx={{
                                width: 32,
                                height: 32,
                                bgcolor: 'secondary.main',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                '& img': {
                                    objectFit: 'cover'
                                }
                            }}
                        >
                            {!profilePicture && (userName ? userName.charAt(0).toUpperCase() : '?')}
                        </Avatar>
                    </PresenceBadge>
                </IconButton>
            </Tooltip>

            {/* The Dropdown Menu component */}
            <Menu
                anchorEl={anchorEl} // Element the menu is anchored to
                id="account-menu"
                open={open} // Controls visibility
                onClose={handleClose} // Closes when clicking outside
                onClick={(e) => {
                    // Do not close menu when clicking inside unless it's a menu item
                    if (e.target.closest('.MuiMenuItem-root')) {
                        handleClose();
                    }
                }}
                PaperProps={{ // Styling for the menu paper
                    elevation: 0,
                    sx: {
                        overflow: 'visible',
                        filter: 'drop-shadow(0px 2px 8px rgba(0,0,0,0.32))',
                        mt: 1.5, // Margin top
                        '& .MuiAvatar-root': { // Style avatar inside menu
                            width: 32,
                            height: 32,
                            ml: -0.5,
                            mr: 1,
                        },
                        // CSS trick to create the small arrow pointing up
                        '&:before': {
                            content: '""',
                            display: 'block',
                            position: 'absolute',
                            top: 0,
                            right: 14,
                            width: 10,
                            height: 10,
                            bgcolor: 'background.paper',
                            transform: 'translateY(-50%) rotate(45deg)',
                            zIndex: 0,
                        },
                    },
                }}
                transformOrigin={{ horizontal: 'right', vertical: 'top' }}
                anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
            >
                {/* User Info Displayed at the top of the menu */}
                <Box sx={{ px: 2, py: 1.5, textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <PresenceBadge userId={user?.id} size="large">
                        <Avatar
                            src={profilePicture || undefined}
                            sx={{
                                width: 48,
                                height: 48,
                                bgcolor: 'secondary.main',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                '& img': {
                                    objectFit: 'cover'
                                }
                            }}
                        >
                            {!profilePicture && (userName ? userName.charAt(0).toUpperCase() : '?')}
                        </Avatar>
                    </PresenceBadge>
                    <Typography variant="subtitle1" noWrap sx={{ mt: 1 }}>{userName}</Typography>
                    <Typography variant="body2" color="text.secondary" noWrap sx={{ mb: 1.5 }}>{userEmail}</Typography>
                    <StatusSelector />
                </Box>
                <Divider sx={{ my: 1 }} />


                {/* Menu Action Items */}
                <MenuItem onClick={() => { handleClose(); navigate('/profile'); }}>
                    <ListItemIcon><AccountCircleIcon fontSize="small" /></ListItemIcon>
                    <ListItemText>Profile</ListItemText>
                </MenuItem>
                <MenuItem onClick={handleBillingClick}>
                    <ListItemIcon><CreditCardIcon fontSize="small" /></ListItemIcon>
                    <ListItemText>Billing</ListItemText>
                </MenuItem>
                {/* Link to the Settings page (renders OnboardingForm) */}
                <MenuItem component={RouterLink} to="/settings">
                    <ListItemIcon><SettingsIcon fontSize="small" /></ListItemIcon>
                    <ListItemText>Settings</ListItemText>
                </MenuItem>
                <MenuItem component={RouterLink} to="/settings/api-keys">
                    <ListItemIcon><VpnKeyIcon fontSize="small" /></ListItemIcon>
                    <ListItemText>API Management</ListItemText>
                </MenuItem>

                {/* Dark Mode Toggle */}
                <MenuItem onClick={(e) => { e.preventDefault(); toggleTheme(); }}>
                    <ListItemIcon><DarkModeIcon fontSize="small" /></ListItemIcon>
                    <ListItemText>Dark Mode</ListItemText>
                    <Switch
                        edge="end"
                        checked={mode === 'dark'}
                        onChange={toggleTheme}
                        onClick={(e) => e.stopPropagation()}
                    />
                </MenuItem>
                <Divider sx={{ my: 1 }} />
                <MenuItem onClick={handleLogout}>
                    <ListItemIcon><LogoutIcon fontSize="small" /></ListItemIcon>
                    <ListItemText>Logout</ListItemText>
                </MenuItem>
            </Menu>
        </>
    );
}

