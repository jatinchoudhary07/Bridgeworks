import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    Alert,
    Avatar,
    Box,
    Chip,
    CircularProgress,
    Paper,
    Stack,
    Tooltip,
    Typography,
    alpha,
} from '@mui/material';
import { BACKEND_URL } from '../../config/api';
import { apiClient } from '../../apiClient';
import PresenceBadge from '../common/PresenceBadge';

const TEAM_MEMBERS_URL = `${BACKEND_URL}/api/team/members/`;
const WORKFORCE_MEMBERS_URL = `${BACKEND_URL}/api/workforce/members/?archive_state=active`;

const LEVELS = [
    { key: 'founder', label: 'Founder', chipColor: 'primary', bg: '#eef2ff', border: '#4f46e5' },
    { key: 'co_founder', label: 'Co-Founder', chipColor: 'secondary', bg: '#fdf2f8', border: '#db2777' },
    { key: 'ceo', label: 'CEO', chipColor: 'warning', bg: '#fff7ed', border: '#c2410c' },
    { key: 'leadership', label: 'Leadership', chipColor: 'info', bg: '#eff6ff', border: '#1d4ed8' },
    { key: 'director', label: 'Directors', chipColor: 'warning', bg: '#fffbeb', border: '#a16207' },
    { key: 'manager', label: 'Managers', chipColor: 'success', bg: '#ecfdf3', border: '#15803d' },
    { key: 'team', label: 'Team Members', chipColor: 'default', bg: '#f8fafc', border: '#334155' },
];

const CONNECTOR_COLOR = '#64748b';

function normalizeText(value) {
    return String(value || '').trim();
}

function normalizeEmail(value) {
    return normalizeText(value).toLowerCase();
}

function normalizeProfilePictureUrl(value) {
    const url = normalizeText(value);
    if (!url) return '';

    // If it's a chat attachment or screenshot, it's not a valid profile picture
    if (url.includes('cloudinary') && (url.includes('chat_attachments') || url.toLowerCase().includes('screenshot'))) {
        return '';
    }

    if (url.includes('/res.cloudinary.com/') && url.includes('/media/profile_pictures/') && url.includes('/raw/upload/')) {
        return url.replace('/raw/upload/', '/image/upload/');
    }

    return url;
}

function getInitials(value) {
    const source = normalizeText(value);
    if (!source) return '?';

    const words = source.split(/\s+/).filter(Boolean);
    if (words.length >= 2) {
        return `${words[0][0]}${words[1][0]}`.toUpperCase();
    }
    return source.slice(0, 2).toUpperCase();
}

function memberTitle(member) {
    if (member.isOriginalFounder) return 'Founder';
    if (member.isCoFounder) return 'Co-Founder';
    return member.roleDesignation || member.category || 'Team Member';
}

function inferHierarchyLevel(member) {
    if (member.isOriginalFounder) return 'founder';
    if (member.isCoFounder) return 'co_founder';

    const designation = `${member.roleDesignation} ${member.category}`.toLowerCase();

    if (/\bceo\b|chief executive officer|managing director|\bmd\b/.test(designation)) {
        return 'ceo';
    }

    if (/\bcto\b|\bcfo\b|\bcoo\b|\bcmo\b|\bcio\b|\bchro\b|\bcso\b|chief|\bvp\b|vice president|head of/.test(designation)) {
        return 'leadership';
    }

    if (/director|controller/.test(designation)) {
        return 'director';
    }

    if (/manager|lead\b|team lead|supervisor/.test(designation)) {
        return 'manager';
    }

    return 'team';
}

function mapTeamMember(member) {
    return {
        id: `team-${member.id}`,
        name: normalizeText(member.full_name || member.username || (member.email ? member.email.split('@')[0] : 'Team Member')),
        email: normalizeText(member.email),
        profilePicture: normalizeProfilePictureUrl(member.profilePicture),
        department: normalizeText(member.department_name),
        roleDesignation: normalizeText(member.role_designation),
        category: normalizeText(member.category || 'Team'),
        isOriginalFounder: Boolean(member.is_original_founder),
        isCoFounder: Boolean(member.is_co_founder),
        source: 'team',
    };
}

function mapWorkforceMember(member) {
    return {
        id: `workforce-${member.id}`,
        name: normalizeText(member.full_name || member.username || (member.email ? member.email.split('@')[0] : 'Member')),
        email: normalizeText(member.email),
        profilePicture: '',
        department: normalizeText(member.department_name),
        roleDesignation: normalizeText(member.role_designation),
        category: normalizeText(member.category),
        isOriginalFounder: Boolean(member.is_original_founder),
        isCoFounder: Boolean(member.is_co_founder),
        source: 'workforce',
    };
}

function mergeMembers(teamRows, workforceRows) {
    const merged = new Map();

    const upsert = (member) => {
        const emailKey = normalizeEmail(member.email);
        const key = emailKey || member.id;
        const previous = merged.get(key);

        if (!previous) {
            merged.set(key, member);
            return;
        }

        merged.set(key, {
            ...previous,
            id: previous.id || member.id,
            name: member.name || previous.name,
            email: member.email || previous.email,
            profilePicture: member.profilePicture || previous.profilePicture,
            department: member.department || previous.department,
            roleDesignation: member.roleDesignation || previous.roleDesignation,
            category: member.category || previous.category,
            isOriginalFounder: previous.isOriginalFounder || member.isOriginalFounder,
            isCoFounder: previous.isCoFounder || member.isCoFounder,
            source: previous.source === 'team' || member.source === 'team' ? 'team' : previous.source,
        });
    };

    workforceRows.forEach((row) => upsert(mapWorkforceMember(row)));
    teamRows.forEach((row) => upsert(mapTeamMember(row)));

    return Array.from(merged.values());
}

function SafeAvatar({ src, name, email, level, ...props }) {
    const [isLoaded, setIsLoaded] = useState(false);

    useEffect(() => {
        if (!src) {
            setIsLoaded(false);
            return;
        }

        let active = true;
        setIsLoaded(false);
        const img = new Image();
        img.src = src;
        img.onload = () => {
            if (active) setIsLoaded(true);
        };
        img.onerror = () => {
            if (active) setIsLoaded(false);
        };

        return () => {
            active = false;
        };
    }, [src]);

    const initials = getInitials(name || email);

    return (
        <Avatar
            {...props}
            src={isLoaded ? src : undefined}
            sx={{
                width: '100%',
                height: '100%',
                bgcolor: (theme) => theme.palette.mode === 'dark' ? alpha(level.border, 0.2) : level.bg,
                color: (theme) => theme.palette.mode === 'dark' ? level.border : 'text.primary',
                fontWeight: 700,
                ...props.sx,
            }}
        >
            {initials}
        </Avatar>
    );
}

export default function WorkforceHierarchyTree() {
    const [members, setMembers] = useState([]);
    const [search] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const loadMembers = useCallback(async () => {
        setLoading(true);
        setError('');

        try {
            const [teamResponse, workforceResponse] = await Promise.all([
                apiClient(TEAM_MEMBERS_URL, { credentials: 'include' }),
                apiClient(WORKFORCE_MEMBERS_URL, { credentials: 'include' }),
            ]);

            if (!teamResponse.ok) throw new Error('Failed to fetch team members.');
            if (!workforceResponse.ok) throw new Error('Failed to fetch workforce members.');

            const teamRows = await teamResponse.json();
            const workforceRows = await workforceResponse.json();

            const allMembers = mergeMembers(
                Array.isArray(teamRows) ? teamRows : [],
                Array.isArray(workforceRows) ? workforceRows : [],
            );

            setMembers(allMembers);
        } catch (requestError) {
            setMembers([]);
            setError(requestError?.message || 'Unable to load organization hierarchy.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadMembers();
    }, [loadMembers]);

    const groupedLevels = useMemo(() => {
        const query = normalizeText(search).toLowerCase();

        const filtered = members.filter((member) => {
            if (!query) return true;
            const haystack = [
                member.name,
                member.email,
                member.department,
                member.roleDesignation,
                member.category,
            ].join(' ').toLowerCase();
            return haystack.includes(query);
        });

        const grouped = LEVELS.map((level) => ({ ...level, members: [] }));

        filtered.forEach((member) => {
            const levelKey = inferHierarchyLevel(member);
            const level = grouped.find((item) => item.key === levelKey) || grouped[grouped.length - 1];
            level.members.push(member);
        });

        grouped.forEach((level) => {
            level.members.sort((a, b) => a.name.localeCompare(b.name));
        });

        return grouped.filter((level) => level.members.length > 0);
    }, [members, search]);

    const renderMemberTooltip = useCallback((member) => (
        <Stack spacing={0.2} sx={{ p: 0.2 }}>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.75)' }}>
                {memberTitle(member)}
            </Typography>
            <Typography variant="subtitle2" sx={{ color: '#fff', fontWeight: 700 }}>
                {member.name || 'Member'}
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.9)' }}>
                {member.email || 'No email'}
            </Typography>
        </Stack>
    ), []);

    return (
        <Box sx={{ p: { xs: 2, md: 3 }, display: 'flex', flexDirection: 'column', gap: 2 }}>
            {error ? <Alert severity="error">{error}</Alert> : null}


            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, minHeight: 240 }}>
                {loading ? (
                    <Box sx={{ py: 8, display: 'flex', justifyContent: 'center' }}>
                        <CircularProgress size={28} />
                    </Box>
                ) : groupedLevels.length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                        No members match the selected filter.
                    </Typography>
                ) : (
                    <Stack spacing={2.25} sx={{ alignItems: 'center' }}>
                        {groupedLevels.map((level) => {
                            const hasMultipleMembers = level.members.length > 1;

                            return (
                                <Box key={level.key} sx={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.25 }}>


                                    <Chip
                                        size="small"
                                        color={level.chipColor}
                                        variant="outlined"
                                        label={`${level.label} (${level.members.length})`}
                                        sx={{ fontWeight: 700, bgcolor: 'background.paper' }}
                                    />

                                    <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: hasMultipleMembers ? 1.1 : 0.9 }}>
                                        <Box sx={{ width: 3, height: 14, borderRadius: 2, bgcolor: CONNECTOR_COLOR }} />

                                        <Stack
                                            direction="row"
                                            spacing={0}
                                            useFlexGap
                                            flexWrap="wrap"
                                            justifyContent="center"
                                            sx={{
                                                columnGap: { xs: 2.2, md: 3.2 },
                                                rowGap: { xs: 1.8, md: 2.3 },
                                            }}
                                        >
                                            {level.members.map((member) => (
                                                <Tooltip
                                                    key={member.id}
                                                    arrow
                                                    title={renderMemberTooltip(member)}
                                                    placement="top"
                                                    enterTouchDelay={0}
                                                    slotProps={{
                                                        tooltip: {
                                                            sx: {
                                                                bgcolor: '#111827',
                                                                '& .MuiTooltip-arrow': { color: '#111827' },
                                                            },
                                                        },
                                                    }}
                                                >
                                                    <Box
                                                        sx={{
                                                            p: 0.4,
                                                            border: `2px solid ${level.border}66`,
                                                            bgcolor: 'background.paper',
                                                            width: { xs: 54, md: 60 },
                                                            height: { xs: 54, md: 60 },
                                                            borderRadius: '50%',
                                                            display: 'inline-flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center',
                                                            transition: 'transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease',
                                                            '&:hover': {
                                                                transform: 'translateY(-2px)',
                                                                borderColor: level.border,
                                                                boxShadow: `0 10px 22px -14px ${level.border}`,
                                                            },
                                                        }}
                                                    >
                                                        {member.source === 'team' ? (
                                                            <PresenceBadge userId={member.id.replace('team-', '')}>
                                                                <SafeAvatar
                                                                    src={member.profilePicture}
                                                                    name={member.name}
                                                                    email={member.email}
                                                                    level={level}
                                                                />
                                                            </PresenceBadge>
                                                        ) : (
                                                            <SafeAvatar
                                                                src={member.profilePicture}
                                                                name={member.name}
                                                                email={member.email}
                                                                level={level}
                                                            />
                                                        )}
                                                    </Box>
                                                </Tooltip>
                                            ))}
                                        </Stack>
                                    </Box>
                                </Box>
                            );
                        })}
                    </Stack>
                )}
            </Paper>
        </Box>
    );
}
