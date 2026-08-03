import React, { useState, useEffect, useCallback } from "react";
import {
  Box,
  Typography,
  Button,
  TextField,
  CircularProgress,
  Alert,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  Avatar,
  Tooltip,
  InputAdornment,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  FormControlLabel,
  Checkbox,
  Divider,
  Grid,
  Snackbar,
  Slide,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Chip,
  Switch
} from "@mui/material";
import DeleteIcon from '@mui/icons-material/Delete';
import SearchIcon from '@mui/icons-material/Search';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import EditIcon from '@mui/icons-material/Edit';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import VisibilityIcon from '@mui/icons-material/Visibility';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import BadgeIcon from '@mui/icons-material/Badge';
import StarsIcon from '@mui/icons-material/Stars';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';

// --- CONFIGURATION ---
import { BACKEND_URL } from "../../config/api";
import { apiClient } from "../../apiClient";

// --- API Endpoints ---
const API_URLS = {
  INVITE: `${BACKEND_URL}/api/team/invite/`,
  TEAM_MEMBERS: `${BACKEND_URL}/api/team/members/`,
  WORKFORCE_MEMBERS: `${BACKEND_URL}/api/workforce/members/`,
  TEAM_MEMBER_DETAIL: (userId) => `${BACKEND_URL}/api/team/members/${userId}/`,
  WORKFORCE_MEMBER_DETAIL: (memberId) => `${BACKEND_URL}/api/workforce/members/${memberId}/`,
  WORKFORCE_MEMBER_DELETE: (memberId) => `${BACKEND_URL}/api/workforce/members/${memberId}/`,
  WORKFORCE_PERMISSIONS: (memberId) => `${BACKEND_URL}/api/workforce/permissions/${memberId}/`,
  PERMISSIONS: (userId) => `${BACKEND_URL}/api/team/permissions/${userId}/`,
  DELETE: (userId) => `${BACKEND_URL}/api/team/delete/${userId}/`,
  SCHEMA: `${BACKEND_URL}/api/permissions/schema/`,
  CURRENT_USER: `${BACKEND_URL}/api/current-user/`,
  ROLES: `${BACKEND_URL}/api/roles/`,
  CO_FOUNDER_TOGGLE: (userId) => `${BACKEND_URL}/api/team/co-founder/${userId}/`,
};

// --- Helper: Get initials from email ---
const getInitials = (value) => {
  if (!value) return "?";
  const source = String(value).trim();
  if (!source) return "?";

  if (source.includes('@')) {
    const parts = source.split('@')[0].split('.');
    if (parts.length >= 2 && parts[0] && parts[1]) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return source.substring(0, 2).toUpperCase();
  }

  const words = source.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return `${words[0][0]}${words[1][0]}`.toUpperCase();
  }
  return source.substring(0, 2).toUpperCase();
};

// --- Helper: Generate color from email ---
const getAvatarColor = (value) => {
  const colors = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A',
    '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2',
    '#F8B500', '#6C5CE7', '#00B894', '#FD79A8'
  ];
  let hash = 0;
  const source = String(value || 'user');
  for (let i = 0; i < source.length; i++) {
    hash = source.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
};

// Slide transition for Snackbar
function SlideTransition(props) {
  return <Slide {...props} direction="down" />;
}

const renderStatusChip = (status, work_mode) => {
  if (!status) return null;
  let label = "";
  let style = {};

  switch (status.toLowerCase()) {
    case "wfo":
    case "present":
      label = "🏢 WFO";
      style = { backgroundColor: '#e8f5e9', color: '#2e7d32', fontWeight: 'bold' };
      break;
    case "wfh":
      label = "🏠 WFH";
      style = { backgroundColor: '#e3f2fd', color: '#1565c0', fontWeight: 'bold' };
      break;
    case "absent":
      label = "Absent";
      style = { backgroundColor: '#ffebee', color: '#c62828', fontWeight: 'bold' };
      break;
    case "half_day":
      if (work_mode && work_mode.toLowerCase() === "wfh") {
        label = "Half Day (WFH)";
      } else if (work_mode && work_mode.toLowerCase() === "wfo") {
        label = "Half Day (WFO)";
      } else {
        label = "Half Day";
      }
      style = { backgroundColor: '#fff3e0', color: '#e65100', fontWeight: 'bold' };
      break;
    case "leave":
      label = "Leave";
      style = { backgroundColor: '#f3e5f5', color: '#4a148c', fontWeight: 'bold' };
      break;
    case "on_duty":
      label = "On Duty";
      style = { backgroundColor: '#e0f7fa', color: '#006064', fontWeight: 'bold' };
      break;
    default:
      return null;
  }

  return (
    <Chip
      label={label}
      size="small"
      sx={{
        height: 20,
        fontSize: '0.65rem',
        border: 'none',
        ...style
      }}
    />
  );
};

export default function TeamManagementPage() {
  const [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [message, setMessage] = useState({ text: "", severity: "info" });
  const [searchQuery, setSearchQuery] = useState("");

  // Modal States
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [userToDelete, setUserToDelete] = useState(null);

  // Member Detail Dialog
  const [memberDetailOpen, setMemberDetailOpen] = useState(false);
  const [memberDetailData, setMemberDetailData] = useState(null);
  const [memberDetailLoading, setMemberDetailLoading] = useState(false);

  // Form States
  const [formEmail, setFormEmail] = useState("");
  const [formPermissions, setFormPermissions] = useState({});
  const [roles, setRoles] = useState([]);
  const [selectedRoleId, setSelectedRoleId] = useState("");
  const [inviteLink, setInviteLink] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  // Snackbar notification state
  const [snackbar, setSnackbar] = useState({
    open: false,
    message: "",
    severity: "success" // success, error, info, warning
  });

  // Add ref for dialog content
  const dialogContentRef = React.useRef(null);

  // --- Load permission schema ---
  useEffect(() => {
    const fetchCurrentUser = async () => {
      try {
        const res = await apiClient(API_URLS.CURRENT_USER, { credentials: 'include' });
        if (!res.ok) return;
        const userData = await res.json();
        // Treat as admin if: is_admin flag, is_founder flag, is_superuser, OR has wildcard role permissions
        const hasAdminRole = Array.isArray(userData?.role_permissions) &&
          (userData.role_permissions.includes('*:*:*') ||
            userData.role_permissions.includes('human_resources:roles_permissions:edit'));

        const isUserAdmin = !!(userData?.is_admin || userData?.is_founder || userData?.is_superuser || hasAdminRole);
        setIsAdmin(isUserAdmin);
        setCurrentUser({
          id: userData.id,
          isFounder: !!userData.is_founder,
          isSuperuser: !!userData.is_superuser,
          isAdmin: isUserAdmin,
          isOriginalFounder: !!userData.is_original_founder,
        });
      } catch {
        setIsAdmin(false);
        setCurrentUser(null);
      }
    };

    fetchCurrentUser();

    const fetchRoles = async () => {
      try {
        const res = await apiClient(API_URLS.ROLES, { credentials: "include" });
        if (!res.ok) throw new Error("Failed to load roles.");
        const data = await res.json();
        setRoles(data.roles || []);
      } catch (err) {
        console.error("Roles load failed:", err);
        setRoles([]);
      }
    };
    fetchRoles();
  }, []);

  // --- Fetch team members ---
  const fetchTeam = useCallback(async () => {
    setLoading(true);
    try {
      const [teamRes, workforceRes] = await Promise.all([
        apiClient(API_URLS.TEAM_MEMBERS, { credentials: "include" }),
        apiClient(API_URLS.WORKFORCE_MEMBERS, { credentials: "include" }),
      ]);

      if (!teamRes.ok) throw new Error("Failed to fetch team list.");
      if (!workforceRes.ok) throw new Error("Failed to fetch workforce list.");

      const teamData = await teamRes.json();
      const workforceData = await workforceRes.json();

      const teamEmailMap = new Map(
        (Array.isArray(teamData) ? teamData : [])
          .filter((member) => member?.email)
          .map((member) => [member.email.toLowerCase().trim(), member])
      );

      const mappedTeam = (Array.isArray(teamData) ? teamData : []).map((member) => {
        // Hierarchy rules:
        // 1. Cannot edit self
        // 2. Cannot edit founder (unless you ARE a superuser or that founder)
        const isSelf = currentUser && member.id === currentUser.id;
        const isTargetFounder = !!member.is_founder;
        const canManageTarget = !isSelf && (!isTargetFounder || (currentUser?.isSuperuser || currentUser?.isFounder));

        return {
          ...member,
          source: 'team',
          sourceId: member.id,
          permissionUserId: member.id,
          canEditPermissions: canManageTarget,
          memberKey: `team-${member.id}`,
        };
      });

      const mappedWorkforce = (Array.isArray(workforceData) ? workforceData : []).map((member) => {
        const emailKey = (member.email || '').toLowerCase().trim();
        const linkedTeamMember = emailKey ? teamEmailMap.get(emailKey) : null;
        const isSelf = currentUser && linkedTeamMember && linkedTeamMember.id === currentUser.id;
        const isTargetFounder = !!(member.is_founder || linkedTeamMember?.is_founder);
        const canManageTarget = !isSelf && (!isTargetFounder || (currentUser?.isSuperuser || currentUser?.isFounder));

        return {
          ...member,
          source: 'workforce',
          sourceId: member.id,
          username: member.full_name || member.username,
          permissionUserId: linkedTeamMember?.id || null,
          canEditPermissions: canManageTarget,
          memberKey: `workforce-${member.id}`,
          today_status: linkedTeamMember?.today_status,
          work_mode: linkedTeamMember?.work_mode,
        };
      });

      const combined = [...mappedWorkforce, ...mappedTeam];
      setTeam(combined);
      setMessage({ text: "", severity: "info" });
    } catch (err) {
      setMessage({ text: `Error: ${err.message}`, severity: "error" });
    } finally {
      setLoading(false);
    }
  }, [currentUser]);

  useEffect(() => {
    if (currentUser) {
      fetchTeam();
    }
  }, [fetchTeam, currentUser]);

  // --- Handle Permission Change ---
  const handlePermissionChange = (area, key, checked) => {
    setFormPermissions((prev) => ({
      ...prev,
      [area]: { ...prev[area], [key]: checked },
    }));
  };

  // --- Handle Snackbar Close ---
  const handleSnackbarClose = (event, reason) => {
    if (reason === 'clickaway') {
      return;
    }
    setSnackbar({ ...snackbar, open: false });
  };

  // --- Handle Invite ---
  const handleInviteSubmit = async (e) => {
    e.preventDefault();
    if (!formEmail) {
      setSnackbar({
        open: true,
        message: "Please enter an email address",
        severity: "warning"
      });
      return;
    }

    setSubmitting(true);

    try {

      const res = await apiClient(API_URLS.INVITE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email: formEmail, permissions: formPermissions, role_id: selectedRoleId }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || errData.detail || "Invitation failed.");
      }

      const data = await res.json();

      // Fix invite link domain
      let finalLink = data.invite_link;
      try {
        const urlObj = new URL(finalLink);
        finalLink = `${window.location.origin}${urlObj.pathname}${urlObj.search}`;
      } catch (e) {
        console.warn("Could not parse invite link, using raw value");
      }

      setInviteLink(finalLink);
      setSnackbar({
        open: true,
        message: "Invitation created successfully!",
        severity: "success"
      });

      // Scroll to top of dialog content to show the invite link
      setTimeout(() => {
        if (dialogContentRef.current) {
          dialogContentRef.current.scrollTo({ top: 0, behavior: 'smooth' });
        }
      }, 100);

      fetchTeam();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err.message,
        severity: "error"
      });
    } finally {
      setSubmitting(false);
    }
  };

  // --- Handle Member Row Click (show detail card) ---
  const handleMemberClick = async (member) => {
    setMemberDetailOpen(true);
    setMemberDetailLoading(true);
    setMemberDetailData(null);
    try {
      const detailUrl = member.source === 'workforce'
        ? API_URLS.WORKFORCE_MEMBER_DETAIL(member.sourceId)
        : API_URLS.TEAM_MEMBER_DETAIL(member.sourceId);
      const res = await apiClient(detailUrl, { credentials: 'include' });
      if (!res.ok) throw new Error('Failed to fetch member details.');
      const data = await res.json();
      setMemberDetailData({
        ...data,
        source: member.source,
        sourceId: member.sourceId,
        permissionUserId: member.permissionUserId || null,
        canEditPermissions: !!member.canEditPermissions,
      });
    } catch (err) {
      setMemberDetailOpen(false);
      setSnackbar({ open: true, message: err.message, severity: 'error' });
    } finally {
      setMemberDetailLoading(false);
    }
  };

  // --- Handle Edit Access ---
  const handleEditAccess = async (user) => {
    if (!isAdmin) {
      setSnackbar({
        open: true,
        message: 'Only admin can edit access.',
        severity: 'error'
      });
      return;
    }

    const isStandaloneWorkforce = user.source === 'workforce' && !user.permissionUserId;
    const permissionTargetType = isStandaloneWorkforce ? 'workforce' : 'team';
    const permissionTargetId = isStandaloneWorkforce
      ? (user.sourceId || user.id)
      : (user.permissionUserId || user.id);

    if (!permissionTargetId) {
      setSnackbar({
        open: true,
        message: 'Unable to resolve member permissions target.',
        severity: 'info'
      });
      return;
    }

    setSelectedUser({ ...user, id: permissionTargetId, permissionTargetType });
    setSubmitting(true);

    try {
      const permissionUrl = permissionTargetType === 'workforce'
        ? API_URLS.WORKFORCE_PERMISSIONS(permissionTargetId)
        : API_URLS.PERMISSIONS(permissionTargetId);
      const res = await apiClient(permissionUrl, { credentials: "include" });
      if (!res.ok) throw new Error("Failed to fetch permissions.");
      const data = await res.json();
      setFormPermissions(data.permissions || {});
      setSelectedRoleId(data.role_id || "");
      setEditDialogOpen(true);
    } catch (err) {
      setSnackbar({
        open: true,
        message: err.message,
        severity: "error"
      });
    } finally {
      setSubmitting(false);
    }
  };

  // --- Handle Update Permissions ---
  const handleUpdatePermissions = async (e) => {
    e.preventDefault();
    if (!selectedUser) return;

    setSubmitting(true);
    const userEmail = selectedUser.email;

    try {
      const permissionUrl = selectedUser.permissionTargetType === 'workforce'
        ? API_URLS.WORKFORCE_PERMISSIONS(selectedUser.id)
        : API_URLS.PERMISSIONS(selectedUser.id);

      const res = await apiClient(permissionUrl, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ permissions: formPermissions, role_id: selectedRoleId }),
      });

      if (!res.ok) throw new Error("Failed to update permissions.");

      // Close dialog first
      setEditDialogOpen(false);
      setSelectedUser(null);

      // Show success notification
      setSnackbar({
        open: true,
        message: `Permissions updated successfully for ${userEmail}`,
        severity: "success"
      });

      // Refresh team list
      await fetchTeam();

    } catch (err) {
      setSnackbar({
        open: true,
        message: err.message,
        severity: "error"
      });
    } finally {
      setSubmitting(false);
    }
  };

  // --- Handle Delete ---
  const handleDeleteClick = (user) => {
    if (!isAdmin) {
      setSnackbar({
        open: true,
        message: 'Only admin can delete members.',
        severity: 'error'
      });
      return;
    }

    setUserToDelete(user);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!userToDelete) return;

    const userName = userToDelete.full_name || userToDelete.username || userToDelete.email || 'member';
    setDeleteDialogOpen(false);
    setLoading(true);

    try {
      if (userToDelete.source === 'workforce') {
        const workforceDeleteRes = await apiClient(API_URLS.WORKFORCE_MEMBER_DELETE(userToDelete.sourceId), {
          method: "DELETE",
          headers: {},
          credentials: "include"
        });

        if (!workforceDeleteRes.ok) {
          const errData = await workforceDeleteRes.json();
          throw new Error(errData.detail || errData.error || "Failed to delete workforce member.");
        }
      } else {
        const res = await apiClient(API_URLS.DELETE(userToDelete.id), {
          method: "DELETE",
          headers: {},
          credentials: "include"
        });

        if (!res.ok) {
          const errData = await res.json();
          throw new Error(errData.error || "Failed to delete user.");
        }
      }

      setSnackbar({
        open: true,
        message: `Team member ${userName} removed successfully`,
        severity: "success"
      });

      await fetchTeam();

    } catch (err) {
      setSnackbar({
        open: true,
        message: err.message,
        severity: "error"
      });
    } finally {
      setLoading(false);
      setUserToDelete(null);
    }
  };

  // --- Handle Co-Founder Promotion/Demotion ---
  const handleToggleCoFounder = async (userId, currentState) => {
    if (!currentUser?.isOriginalFounder) {
      setSnackbar({
        open: true,
        message: "Only the original account owner can manage co-founders.",
        severity: "error"
      });
      return;
    }

    setSubmitting(true);
    const newState = !currentState;

    try {
      const res = await apiClient(API_URLS.CO_FOUNDER_TOGGLE(userId), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ is_co_founder: newState }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || "Action failed.");
      }

      const data = await res.json();
      setSnackbar({
        open: true,
        message: data.status,
        severity: "success"
      });

      // Update both memberDetailData AND the main team list
      if (memberDetailData && memberDetailData.sourceId === userId) {
        setMemberDetailData(prev => ({ ...prev, is_co_founder: newState }));
      }

      await fetchTeam();
    } catch (err) {
      setSnackbar({
        open: true,
        message: err.message,
        severity: "error"
      });
    } finally {
      setSubmitting(false);
    }
  };

  // --- Copy invite link ---
  const handleCopyLink = () => {
    navigator.clipboard.writeText(inviteLink);
    setLinkCopied(true);
    setSnackbar({
      open: true,
      message: "Invite link copied to clipboard!",
      severity: "success"
    });
    setTimeout(() => setLinkCopied(false), 2000);
  };

  // --- Reset invite dialog ---
  const handleOpenInviteDialog = () => {
    setFormEmail("");
    setFormPermissions({});
    setSelectedRoleId("");
    setInviteLink("");
    setLinkCopied(false);
    setInviteDialogOpen(true);
  };

  // --- Filter team members ---
  const filteredTeam = team.filter(member =>
    (member.email || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (member.full_name || member.username || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    (member.phone || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Box sx={{ p: 3, maxWidth: 1400, margin: '0 auto' }}>
      {/* Message Alert */}
      {message.text && (
        <Alert
          severity={message.severity}
          sx={{ mb: 3, borderRadius: 2 }}
          onClose={() => setMessage({ text: "", severity: "info" })}
        >
          {message.text}
        </Alert>
      )}

      {/* Snackbar Notification */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={5000}
        onClose={handleSnackbarClose}
        TransitionComponent={SlideTransition}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert
          onClose={handleSnackbarClose}
          severity={snackbar.severity}
          variant="filled"
          icon={snackbar.severity === 'success' ? <CheckCircleIcon /> : <ErrorOutlineIcon />}
          sx={{
            width: '100%',
            minWidth: 400,
            borderRadius: 2,
            fontWeight: 500,
            boxShadow: 3,
            '& .MuiAlert-message': {
              fontSize: '0.95rem'
            }
          }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>

      {/* Search Bar and Add Member Button */}
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center' }}>
        <Paper sx={{
          flex: 1,
          maxWidth: 250,
          py: 1.5,
          px: 3,
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider'
        }}>
          <TextField
            fullWidth
            placeholder="Search members"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ color: 'text.secondary' }} />
                </InputAdornment>
              ),
              disableUnderline: true,
            }}
            variant="standard"
            size="small"
          />
        </Paper>
        <Box sx={{ flex: 1 }} />
        <Button
          variant="contained"
          startIcon={<PersonAddIcon />}
          onClick={handleOpenInviteDialog}
          sx={{
            borderRadius: 2,
            px: 3,
            py: 1.5,
            textTransform: 'none',
            fontWeight: 600
          }}
        >
          Add member
        </Button>
      </Box>

      {/* Team Statistics */}
      <Box sx={{ mb: 2 }}>
        <Typography variant="body2" color="text.secondary">
          1-{filteredTeam.length} of {team.length} items
        </Typography>
      </Box>

      {/* Members Table */}
      <Paper sx={{ borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: 'divider' }}>
        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, py: 2 }}>Member</TableCell>
                <TableCell align="right" sx={{ fontWeight: 600 }}></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={3} align="center" sx={{ py: 10 }}>
                    <CircularProgress size={40} />
                    <Typography variant="body2" sx={{ mt: 2, color: 'text.secondary' }}>
                      Loading team members...
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : filteredTeam.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} align="center" sx={{ py: 10 }}>
                    <Typography variant="body2" color="text.secondary">
                      {searchQuery ? "No members found matching your search." : "No team members yet."}
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                filteredTeam.map((member, index) => (
                  <TableRow
                    key={member.memberKey || member.id}
                    hover
                    onClick={() => handleMemberClick(member)}
                    sx={{
                      cursor: 'pointer',
                      '&:last-child td': { border: 0 },
                      bgcolor: index % 2 === 0 ? 'background.paper' : (theme) => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.03)' : 'grey.50'
                    }}
                  >
                    <TableCell>
                      <Stack direction="row" spacing={2} alignItems="center">
                        <Avatar
                          src={member.profilePicture || ''}
                          sx={{
                            bgcolor: getAvatarColor(member.email || member.full_name),
                            width: 40,
                            height: 40,
                            fontWeight: 'bold',
                            fontSize: '0.875rem'
                          }}
                        >
                          {!member.profilePicture && getInitials(member.full_name || member.email)}
                        </Avatar>
                        <Box>
                          <Typography
                            variant="body2"
                            component="div"
                            fontWeight={500}
                            sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 0.75 }}
                          >
                            <Box component="span">{member.full_name || member.username || member.email?.split('@')[0] || 'Member'}</Box>
                            {member.is_original_founder && (
                              <Chip
                                label="Founder"
                                size="small"
                                color="primary"
                                variant="outlined"
                                icon={<StarsIcon />}
                                sx={{ height: 20, fontSize: '0.65rem', fontWeight: 'bold' }}
                              />
                            )}
                            {member.is_co_founder && !member.is_original_founder && (
                              <Chip
                                label="Co-Founder"
                                size="small"
                                color="secondary"
                                variant="outlined"
                                icon={<AdminPanelSettingsIcon />}
                                sx={{ height: 20, fontSize: '0.65rem', fontWeight: 'bold' }}
                              />
                            )}
                            {renderStatusChip(member.today_status, member.work_mode)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {member.email || member.phone || 'No contact info'}
                          </Typography>
                        </Box>
                      </Stack>
                    </TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={1} justifyContent="flex-end">
                        <Tooltip title="Edit Access">
                          <span>
                            <IconButton
                              size="small"
                              onClick={(e) => { e.stopPropagation(); handleEditAccess(member); }}
                              disabled={!isAdmin || !member.canEditPermissions}
                              sx={{
                                color: 'primary.main',
                                '&:hover': { bgcolor: 'primary.lighter' }
                              }}
                            >
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                        <Tooltip title="Remove member">
                          <span>
                            <IconButton
                              size="small"
                              onClick={(e) => { e.stopPropagation(); handleDeleteClick(member); }}
                              disabled={!isAdmin}
                              sx={{
                                color: 'text.secondary',
                                '&:hover': { color: 'error.main', bgcolor: 'error.lighter' }
                              }}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </span>
                        </Tooltip>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      {/* Invite Dialog */}
      <Dialog
        open={inviteDialogOpen}
        onClose={() => setInviteDialogOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { borderRadius: 3 }
        }}
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Box>
            <Typography variant="h6" component="div" fontWeight="bold">
              Invite New Team Member
            </Typography>
          </Box>
        </DialogTitle>
        <Divider />
        <DialogContent ref={dialogContentRef} sx={{ pt: 3 }}>
          {/* Show invite link  */}
          {inviteLink && (
            <Alert
              severity="success"
              sx={{ mb: 3, borderRadius: 2 }}
              icon={<CheckCircleIcon />}
            >
              <Typography variant="body2" fontWeight="bold" gutterBottom>
                Invitation Link Generated
              </Typography>
              <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                mt: 1,
                p: 1.5,
                bgcolor: 'background.paper',
                borderRadius: 1,
                border: '1px solid',
                borderColor: 'divider'
              }}>
                <Typography
                  variant="caption"
                  sx={{
                    flex: 1,
                    wordBreak: 'break-all',
                    fontFamily: 'monospace',
                    fontSize: '0.75rem'
                  }}
                >
                  {inviteLink}
                </Typography>
                <Tooltip title={linkCopied ? "Copied!" : "Copy link"}>
                  <IconButton
                    size="small"
                    onClick={handleCopyLink}
                    color={linkCopied ? "success" : "default"}
                  >
                    {linkCopied ? <CheckCircleIcon fontSize="small" /> : <ContentCopyIcon fontSize="small" />}
                  </IconButton>
                </Tooltip>
              </Box>
            </Alert>
          )}

          <TextField
            fullWidth
            label="Employee Email"
            type="email"
            value={formEmail}
            onChange={(e) => setFormEmail(e.target.value)}
            placeholder="colleague@company.com"
            sx={{ mb: 3 }}
            autoFocus
          />

          <Typography variant="subtitle2" gutterBottom fontWeight="bold" sx={{ mb: 2 }}>
            Set Permissions
          </Typography>

          <FormControl fullWidth margin="normal">
            <InputLabel id="invite-role-label">Assign Role</InputLabel>
            <Select
              labelId="invite-role-label"
              value={selectedRoleId}
              label="Assign Role"
              onChange={(e) => setSelectedRoleId(e.target.value)}
            >
              <MenuItem value="">
                <em>None</em>
              </MenuItem>
              {roles.map((role) => (
                <MenuItem key={role.id} value={role.id}>
                  {role.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <Divider />
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button
            onClick={() => setInviteDialogOpen(false)}
            sx={{ textTransform: 'none' }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleInviteSubmit}
            variant="contained"
            disabled={submitting || !formEmail}
            sx={{
              textTransform: 'none',
              px: 3
            }}
          >
            {submitting ? <CircularProgress size={20} /> : "Generate Invite Link"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Edit Permissions Dialog */}
      <Dialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { borderRadius: 3 }
        }}
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Box>
            <Typography variant="h6" component="div" fontWeight="bold">
              Edit Permissions
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Editing permissions for {selectedUser?.email}
            </Typography>
          </Box>
        </DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 3 }}>
          <FormControl fullWidth margin="normal">
            <InputLabel id="edit-role-label">Assign Role</InputLabel>
            <Select
              labelId="edit-role-label"
              value={selectedRoleId}
              label="Assign Role"
              onChange={(e) => setSelectedRoleId(e.target.value)}
            >
              <MenuItem value="">
                <em>None (Legacy Permissions)</em>
              </MenuItem>
              {roles.map((role) => (
                <MenuItem key={role.id} value={role.id}>
                  {role.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <Divider />
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button
            onClick={() => setEditDialogOpen(false)}
            sx={{ textTransform: 'none' }}
          >
            Cancel
          </Button>
          <Button
            onClick={handleUpdatePermissions}
            variant="contained"
            disabled={submitting}
            sx={{
              textTransform: 'none',
              px: 3
            }}
          >
            {submitting ? <CircularProgress size={20} /> : "Update Permissions"}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ==================== MEMBER DETAIL DIALOG ==================== */}
      <Dialog
        open={memberDetailOpen}
        onClose={() => setMemberDetailOpen(false)}

        PaperProps={{ sx: { borderRadius: 3, width: "450px" } }}
      >
        <DialogTitle sx={{ fontWeight: 'bold', fontSize: '1.1rem' }}>Member details</DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 3 }}>
          {memberDetailLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
              <CircularProgress />
            </Box>
          ) : memberDetailData ? (
            <Box>
              {/* Profile Header */}
              {(() => {
                const extraData = memberDetailData.extra_data || {};
                const memberName = memberDetailData.full_name || memberDetailData.name || memberDetailData.username || 'Member';
                const memberContact = memberDetailData.email || memberDetailData.phone || 'No contact info';
                const displayPhone = memberDetailData.phone
                  ? `${extraData.code ? `${extraData.code} ` : ''}${memberDetailData.phone}`
                  : '—';
                const displayLocation = memberDetailData.current_location || memberDetailData.location || '—';
                const displayDob = extraData.dob ? new Date(extraData.dob).toLocaleDateString('en-GB') : (memberDetailData.dob ? new Date(memberDetailData.dob).toLocaleDateString('en-GB') : '—');
                const displayGender = memberDetailData.gender || '—';
                const aboutText = memberDetailData.notes || memberDetailData.about || 'No description provided.';
                const bankAccountHolder = extraData.bank_account_name || memberDetailData.bankAccountHolder;
                const bankName = extraData.bank_name || memberDetailData.bankName;
                const bankAccountNumber = extraData.account_number || memberDetailData.bankAccountNumber;
                const bankIfscCode = extraData.ifsc || memberDetailData.bankIfscCode;
                const aadhaarDocument = extraData.aadhaar_document || memberDetailData.aadhaarDocument;
                const panDocument = extraData.pan_document || memberDetailData.panDocument;

                return (
                  <>
                    <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
                      <Avatar
                        src={memberDetailData.profilePicture || ''}
                        sx={{
                          width: 72,
                          height: 72,
                          bgcolor: getAvatarColor(memberDetailData.email || memberName),
                          fontSize: '1.5rem',
                          fontWeight: 'bold',
                          border: '3px solid',
                          borderColor: 'primary.main',
                        }}
                      >
                        {!memberDetailData.profilePicture && getInitials(memberName)}
                      </Avatar>
                      <Box>
                        <Typography variant="h6" fontWeight="bold">
                          {memberName}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {memberContact}
                        </Typography>
                      </Box>
                    </Stack>

                    {/* Key Info Grid */}
                    <Grid container spacing={2} sx={{ mb: 2 }}>
                      {[
                        { label: 'Phone', value: displayPhone },
                        { label: 'Location', value: displayLocation },
                        { label: 'DOB', value: displayDob },
                        { label: 'Gender', value: displayGender },
                      ].map(({ label, value }) => (
                        <Grid item xs={6} key={label}>
                          <Typography variant="caption" color="text.secondary" display="block">
                            {label}
                          </Typography>
                          <Typography variant="body2" fontWeight={500}>{value}</Typography>
                        </Grid>
                      ))}
                    </Grid>

                    <Divider sx={{ my: 2 }} />

                    {/* About */}
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="subtitle2" fontWeight="bold" gutterBottom>About</Typography>
                      <Typography variant="body2" color={aboutText !== 'No description provided.' ? 'text.primary' : 'text.secondary'}>
                        {aboutText}
                      </Typography>
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    {/* Bank Account */}
                    <Box sx={{ mb: 2 }}>
                      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                        <AccountBalanceIcon fontSize="small" color="action" />
                        <Typography variant="subtitle2" fontWeight="bold">Bank Account</Typography>
                      </Stack>
                      {bankAccountNumber ? (
                        <Box>
                          <Typography variant="body2">
                            {bankAccountHolder || '—'} — {bankName || '—'}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            A/C: {bankAccountNumber} • IFSC: {bankIfscCode || '—'}
                          </Typography>
                        </Box>
                      ) : (
                        <Typography variant="body2" color="text.secondary">No bank details provided.</Typography>
                      )}
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    {/* Identity Documents */}
                    <Box>
                      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
                        <BadgeIcon fontSize="small" color="action" />
                        <Typography variant="subtitle2" fontWeight="bold">Identity Documents</Typography>
                      </Stack>
                      <Grid container spacing={2}>
                        {[
                          { label: 'Aadhaar', url: aadhaarDocument },
                          { label: 'PAN', url: panDocument },
                        ].map(({ label, url }) => (
                          <Grid item xs={6} key={label}>
                            <Box
                              sx={{
                                border: '1px solid',
                                borderColor: url ? 'success.main' : 'divider',
                                borderRadius: 2,
                                p: 1.5,
                              }}
                            >
                              <Typography variant="caption" color="text.secondary" display="block" gutterBottom>
                                {label}
                              </Typography>
                              {url ? (
                                <Stack direction="row" alignItems="center" justifyContent="space-between">
                                  <Typography variant="body2" color="success.main" fontWeight={500}>
                                    Uploaded
                                  </Typography>
                                  <Tooltip title={`View ${label}`}>
                                    <IconButton
                                      size="small"
                                      component="a"
                                      href={url}
                                      target="_blank"
                                      rel="noreferrer"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <VisibilityIcon fontSize="small" />
                                    </IconButton>
                                  </Tooltip>
                                </Stack>
                              ) : (
                                <Typography variant="body2" color="text.secondary">Not uploaded</Typography>
                              )}
                            </Box>
                          </Grid>
                        ))}
                      </Grid>
                    </Box>
                  </>
                );
              })()}
            </Box>
          ) : null}
        </DialogContent>
        <Divider />
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setMemberDetailOpen(false)} sx={{ textTransform: 'none' }}>
            Close
          </Button>
          {memberDetailData && (
            <>
              {currentUser?.isOriginalFounder && !memberDetailData.is_original_founder && memberDetailData.source === 'team' && (
                <Button
                  variant="outlined"
                  color={memberDetailData.is_co_founder ? "error" : "primary"}
                  onClick={() => handleToggleCoFounder(memberDetailData.sourceId, memberDetailData.is_co_founder)}
                  disabled={submitting}
                  startIcon={memberDetailData.is_co_founder ? <DeleteIcon /> : <StarsIcon />}
                  sx={{ textTransform: 'none', mr: 'auto' }}
                >
                  {memberDetailData.is_co_founder ? "Demote from Co-Founder" : "Promote to Co-Founder"}
                </Button>
              )}
              <Button
                variant="contained"
                onClick={() => {
                  setMemberDetailOpen(false);
                  handleEditAccess(memberDetailData);
                }}
                disabled={!isAdmin || !memberDetailData.canEditPermissions}
                sx={{ textTransform: 'none', px: 3 }}
              >
                Edit Access
              </Button>
            </>
          )}
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        PaperProps={{
          sx: { borderRadius: 3 }
        }}
      >
        <DialogTitle>
          <Typography variant="h6" component="div" fontWeight="bold">
            Confirm Removal
          </Typography>
        </DialogTitle>
        <Divider />
        <DialogContent sx={{ pt: 3 }}>
          <Typography>
            Are you sure you want to remove <strong>{userToDelete?.full_name || userToDelete?.username || 'this member'}</strong> ({userToDelete?.email || userToDelete?.phone || 'no contact info'}) from the team?
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            This action will delete their account and access immediately.
          </Typography>
        </DialogContent>
        <Divider />
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button
            onClick={() => setDeleteDialogOpen(false)}
            sx={{ textTransform: 'none' }}
          >
            Cancel
          </Button>
          <Button
            onClick={confirmDelete}
            color="error"
            variant="contained"
            sx={{ textTransform: 'none', px: 3 }}
          >
            Remove
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}