import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
    Avatar,
    Box,
    Button,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    IconButton,
    InputAdornment,
    MenuItem,
    Paper,
    Select,
    Stack,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import {
    ArticleOutlined as ArticleOutlinedIcon,
    CloudUploadOutlined as CloudUploadOutlinedIcon,
    CollectionsBookmark as CollectionsBookmarkIcon,
    CollectionsBookmarkOutlined as CollectionsBookmarkOutlinedIcon,
    DeleteOutline as DeleteOutlineIcon,
    Download as DownloadIcon,
    InsertDriveFileOutlined as InsertDriveFileOutlinedIcon,
    PictureAsPdfOutlined as PictureAsPdfOutlinedIcon,
    Search as SearchIcon,
    ShareOutlined as ShareOutlinedIcon,
    Star as StarIcon,
    StarBorder as StarBorderIcon,
    TableChartOutlined as TableChartOutlinedIcon,
    VisibilityOutlined as VisibilityOutlinedIcon,
    VideocamOutlined as VideocamOutlinedIcon,
    ChatOutlined as ChatOutlinedIcon,
} from '@mui/icons-material';
import {
    createMyDeskGalleryAlbum,
    createMyDeskGalleryItem,
    deleteMyDeskGalleryItem,
    getMyDeskGalleryItemDownloadLink,
    listMyDeskGalleryAlbums,
    listMyDeskGalleryItems,
    updateMyDeskGalleryItem,
    getVaultStorageStats,
} from '../mydeskService';
import { useLocation, useNavigate } from 'react-router-dom';
import { alpha, useTheme as useMuiTheme } from '@mui/material/styles';
import { emitMyDeskNotification } from '../mydeskNotifications';


function getMemberId(member) {
    return member?.id ?? member?.user_id ?? member?.value ?? null;
}

function getMemberName(member) {
    const fullName = [member?.first_name, member?.last_name].filter(Boolean).join(' ').trim();
    return member?.full_name || member?.name || fullName || member?.username || member?.email || 'Member';
}

function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (!Number.isFinite(value) || value <= 0) return '0 B';

    if (value < 1024) return `${value.toFixed(0)} B`;
    const kb = value / 1024;
    if (kb < 1024) return `${kb.toFixed(1)} KB`;
    const mb = kb / 1024;
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    const gb = mb / 1024;
    return `${gb.toFixed(1)} GB`;
}

function formatMonthDay(value) {
    if (!value) return '--';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return '--';
    return parsed.toLocaleDateString('en-GB', { month: 'short', day: 'numeric' });
}

function normalizeText(value) {
    return String(value || '').trim().toLowerCase();
}

function getExtension(fileName) {
    const normalized = String(fileName || '').trim();
    if (normalized.includes('.')) {
        const ext = normalized.split('.').pop();
        return String(ext || '').toLowerCase();
    }

    return '';
}

function resolveMediaTypeFromItem(item, extension) {
    if (item?.media_type && item.media_type !== 'file') return item.media_type;

    const url = String(item?.file_url || item?.download_url || '').toLowerCase();
    if (url.includes('/image/upload/') || url.includes('/image/fetch/')) return 'image';
    if (url.includes('/video/upload/') || url.includes('/video/fetch/')) return 'video';

    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'].includes(extension)) return 'image';
    if (['mp4', 'mov', 'avi', 'webm', 'mkv'].includes(extension)) return 'video';
    return 'file';
}

function getExtensionFromUrl(url) {
    const cleanUrl = String(url || '').split('?')[0].split('#')[0].trim();
    if (!cleanUrl) return '';
    const segment = cleanUrl.substring(cleanUrl.lastIndexOf('/') + 1);
    if (!segment || !segment.includes('.')) return '';
    const ext = segment.split('.').pop();
    return String(ext || '').toLowerCase();
}

function inferPreviewKind(item, sourceUrl) {
    const url = String(sourceUrl || '').toLowerCase();
    const ext = String(item?.extension || getExtensionFromUrl(url) || '').toLowerCase();

    if (item?.mediaType === 'image') return 'image';
    if (item?.mediaType === 'video') return 'video';

    if (url.includes('/image/upload/') || url.includes('/image/fetch/')) return 'image';
    if (url.includes('/video/upload/') || url.includes('/video/fetch/')) return 'video';

    if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'].includes(ext)) return 'image';
    if (['mp4', 'mov', 'avi', 'webm', 'mkv'].includes(ext)) return 'video';
    if (ext === 'pdf') return 'pdf';

    return '';
}

function getFileName(item) {
    const explicit = String(item?.file_name || '').trim();
    if (explicit) return explicit;

    const fallbackUrl = String(item?.file_url || '');
    if (!fallbackUrl) return 'File';

    const cleanUrl = fallbackUrl.split('?')[0];
    const segment = cleanUrl.substring(cleanUrl.lastIndexOf('/') + 1);
    if (!segment) return 'File';
    try {
        return decodeURIComponent(segment);
    } catch {
        return segment;
    }
}

function getSharedToLabel(sharedWith) {
    const members = Array.isArray(sharedWith) ? sharedWith : [];
    if (members.length === 0) return '';

    const recipients = members
        .map((member) => getMemberName(member))
        .filter((name) => Boolean(name && name !== 'Member'));

    if (recipients.length === 0) {
        return members.length === 1 ? 'Shared to: 1 teammate' : `Shared to: ${members.length} teammates`;
    }

    const preview = recipients.slice(0, 2).join(', ');
    const remaining = recipients.length - 2;
    return remaining > 0 ? `Shared to: ${preview} +${remaining}` : `Shared to: ${preview}`;
}

export default function GallerySection({ members = [] }) {
    const location = useLocation();
    const navigate = useNavigate();
    const muiTheme = useMuiTheme();
    const isDarkMode = muiTheme.palette.mode === 'dark';
    const itemRefs = useRef({});
    const uploadInputRef = useRef(null);

    const [albums, setAlbums] = useState([]);
    const [selectedAlbumId, setSelectedAlbumId] = useState(null);
    const [items, setItems] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [storageStats, setStorageStats] = useState(null);
    const [isUploading, setIsUploading] = useState(false);
    const [isDragActive, setIsDragActive] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [activeSectionTab, setActiveSectionTab] = useState('recent');
    const [sortBy, setSortBy] = useState('date');
    const [mediaFilter, setMediaFilter] = useState('all');
    const [showAllRecent, setShowAllRecent] = useState(false);
    const [previewUrls, setPreviewUrls] = useState({});
    const [busyItemId, setBusyItemId] = useState(null);
    const [highlightItemId, setHighlightItemId] = useState(null);
    const [shareDialogItem, setShareDialogItem] = useState(null);
    const [shareSelection, setShareSelection] = useState([]);
    const [isSavingShares, setIsSavingShares] = useState(false);
    const previewRequestedRef = useRef(new Set());

    const vaultColors = useMemo(() => {
        const primary = muiTheme.palette.primary.main;
        return {
            shellBg: muiTheme.palette.background.paper,
            shellBorder: muiTheme.palette.divider,
            shellText: muiTheme.palette.text.primary,
            mutedText: muiTheme.palette.text.secondary,
            searchBg: isDarkMode
                ? alpha(muiTheme.palette.background.default, 0.65)
                : alpha(muiTheme.palette.background.default, 0.46),
            panelBg: isDarkMode
                ? alpha(muiTheme.palette.background.default, 0.46)
                : alpha(muiTheme.palette.background.default, 0.26),
            panelBorder: alpha(muiTheme.palette.divider, 0.95),
            activeTab: primary,
            dropBorder: alpha(primary, isDarkMode ? 0.55 : 0.35),
            dropBgIdle: alpha(primary, isDarkMode ? 0.09 : 0.035),
            dropBgActive: alpha(primary, isDarkMode ? 0.17 : 0.11),
            hintChipBg: isDarkMode
                ? alpha(muiTheme.palette.common.white, 0.08)
                : alpha(muiTheme.palette.common.black, 0.03),
            hintChipBorder: alpha(muiTheme.palette.divider, 0.9),
            hintChipText: muiTheme.palette.text.secondary,
            link: muiTheme.palette.primary.main,
            iconMuted: muiTheme.palette.text.secondary,
            iconDanger: muiTheme.palette.error.main,
            iconWarning: muiTheme.palette.warning.main,
            iconInfo: muiTheme.palette.info.main,
            previewBg: isDarkMode
                ? alpha(muiTheme.palette.background.default, 0.7)
                : alpha(muiTheme.palette.background.default, 0.42),
            avatarBg: alpha(muiTheme.palette.primary.main, isDarkMode ? 0.26 : 0.12),
            avatarFg: muiTheme.palette.primary.main,
            highlightBorder: alpha(muiTheme.palette.primary.main, 0.85),
            highlightShadow: `0 0 0 1px ${alpha(muiTheme.palette.primary.main, 0.45)}`,
            cardShadow: isDarkMode
                ? '0 10px 24px rgba(0,0,0,0.26)'
                : '0 8px 20px rgba(15,23,42,0.05)',
        };
    }, [isDarkMode, muiTheme]);

    const memberOptions = useMemo(() => {
        return members
            .map((member) => ({ id: getMemberId(member), label: getMemberName(member) }))
            .filter((member) => member.id !== null && member.id !== undefined);
    }, [members]);

    const loadItems = useCallback(async () => {
        const response = await listMyDeskGalleryItems({
            sort_by: 'created_at',
            sort_order: 'desc',
        });
        setItems(Array.isArray(response) ? response : []);
    }, []);

    const loadStats = useCallback(async () => {
        try {
            const stats = await getVaultStorageStats();
            setStorageStats(stats);
        } catch (err) {
            console.error('Failed to load storage stats', err);
        }
    }, []);

    useEffect(() => {
        let mounted = true;

        (async () => {
            try {
                let albumList = await listMyDeskGalleryAlbums();
                if (!Array.isArray(albumList)) albumList = [];

                if (albumList.length === 0) {
                    const created = await createMyDeskGalleryAlbum({ name: 'General' });
                    albumList = [created];
                }

                const queryAlbumId = (new URLSearchParams(location.search || '').get('albumId') || '').trim();
                const preferredAlbum = albumList.find((item) => String(item.id) === queryAlbumId) || albumList[0] || null;

                if (mounted) {
                    setAlbums(albumList);
                    setSelectedAlbumId(preferredAlbum?.id || null);
                }

                await loadItems();
                if (mounted) {
                    await loadStats();
                }
            } catch {
            } finally {
                if (mounted) {
                    setIsLoading(false);
                }
            }
        })();

        return () => {
            mounted = false;
        };
    }, [loadItems, loadStats, location.search]);

    const ensureUploadAlbumId = async () => {
        if (selectedAlbumId) return selectedAlbumId;

        if (albums.length > 0) {
            const fallbackId = albums[0].id;
            setSelectedAlbumId(fallbackId);
            return fallbackId;
        }

        const created = await createMyDeskGalleryAlbum({ name: 'General' });
        setAlbums((previous) => [...previous, created]);
        setSelectedAlbumId(created.id);
        return created.id;
    };

    const uploadFiles = async (fileList) => {
        const files = Array.from(fileList || []);
        if (files.length === 0) return;

        setIsUploading(true);
        try {
            const albumId = await ensureUploadAlbumId();

            for (const file of files) {
                const payload = new FormData();
                payload.append('album', String(albumId));
                payload.append('file', file);
                payload.append('captured_on', new Date().toISOString().slice(0, 10));
                await createMyDeskGalleryItem(payload);
            }

            await loadItems();
            await loadStats();
        } catch {
        } finally {
            setIsUploading(false);
            if (uploadInputRef.current) {
                uploadInputRef.current.value = '';
            }
        }
    };

    const updateItemInState = (updatedItem) => {
        if (!updatedItem?.id) return;
        setItems((previous) => previous.map((entry) => (entry.id === updatedItem.id ? updatedItem : entry)));
    };

    const patchVaultItem = async (item, payload) => {
        if (!item?.id) return null;
        setBusyItemId(item.id);
        try {
            const updated = await updateMyDeskGalleryItem(item.id, payload);
            updateItemInState(updated);
            return updated;
        } catch (err) {
            emitMyDeskNotification(err?.message || 'Failed to update vault item', 'error');
            return null;
        } finally {
            setBusyItemId(null);
        }
    };

    const resolveItemUrl = useCallback(async (item, options = {}) => {
        if (!item?.id) return item?.file_url || null;
        try {
            const payload = await getMyDeskGalleryItemDownloadLink(item.id, options);
            return payload?.url || item?.download_url || item?.file_url || null;
        } catch {
            return item?.download_url || item?.file_url || null;
        }
    }, []);

    const openItem = async (item) => {
        const url = await resolveItemUrl(item, { download: false });
        if (!url) return;
        window.open(url, '_blank', 'noopener,noreferrer');
    };

    const downloadItem = async (item, fileName) => {
        const url = await resolveItemUrl(item, { download: true });
        if (!url) return;

        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noreferrer';
        link.download = fileName || 'download';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    const openShareDialog = (item) => {
        const selectedIds = Array.isArray(item?.shared_with)
            ? item.shared_with.map((member) => String(member.id)).filter(Boolean)
            : [];
        setShareSelection(selectedIds);
        setShareDialogItem(item);
    };

    const closeShareDialog = () => {
        if (isSavingShares) return;
        setShareDialogItem(null);
    };

    const saveShareDialog = async () => {
        if (!shareDialogItem?.id) return;
        setIsSavingShares(true);
        try {
            const recipientIds = shareSelection
                .map((value) => Number(value))
                .filter((value) => Number.isInteger(value) && value > 0);
            const updatedItem = await patchVaultItem(shareDialogItem, { shared_with_ids: recipientIds });
            if (updatedItem) {
                setShareDialogItem(null);
            }
        } finally {
            setIsSavingShares(false);
        }
    };

    const toggleFavorite = async (item) => {
        await patchVaultItem(item, { is_favorite: !item.is_favorite });
    };

    const toggleReference = async (item) => {
        if (item.mediaType !== 'image') return;
        await patchVaultItem(item, { is_reference: !item.is_reference });
    };

    const removeItem = async (item) => {
        if (!item?.id) return;
        setBusyItemId(item.id);
        try {
            await deleteMyDeskGalleryItem(item.id);
            setItems((previous) => previous.filter((entry) => entry.id !== item.id));
            await loadStats();
            emitMyDeskNotification('Item removed from Vault successfully', 'success');
        } catch (err) {
            emitMyDeskNotification(err?.message || 'Failed to delete vault item', 'error');
        } finally {
            setBusyItemId(null);
        }
    };

    const itemsWithMeta = useMemo(() => {
        return (Array.isArray(items) ? items : []).map((item) => {
            const fileName = getFileName(item);
            const extension = getExtension(fileName)
                || getExtensionFromUrl(item?.file_url)
                || getExtensionFromUrl(item?.download_url);
            const mediaType = resolveMediaTypeFromItem(item, extension);
            const createdAt = item?.created_at ? new Date(item.created_at) : null;
            const timestamp = createdAt && !Number.isNaN(createdAt.getTime()) ? createdAt.getTime() : 0;
            const fileSizeBytes = Number.isFinite(Number(item?.file_size_bytes)) ? Number(item.file_size_bytes) : null;
            return {
                ...item,
                fileName,
                extension,
                mediaType,
                timestamp,
                fileSizeBytes,
            };
        });
    }, [items]);

    const filteredItems = useMemo(() => {
        const query = normalizeText(searchTerm);

        return itemsWithMeta
            .filter((item) => {
                if (!query) return true;
                const searchable = `${normalizeText(item.fileName)} ${normalizeText(item.album_name)} ${normalizeText(item.chat_context_name)} ${normalizeText(item.chat_sender_name)}`;
                return searchable.includes(query);
            })
            .filter((item) => {
                if (mediaFilter === 'images') return item.mediaType === 'image';
                if (mediaFilter === 'pdf') return item.extension === 'pdf';
                return true;
            })
            .sort((a, b) => b.timestamp - a.timestamp);
    }, [itemsWithMeta, mediaFilter, searchTerm]);

    const sortedItems = useMemo(() => {
        const source = [...filteredItems];

        if (sortBy === 'name') {
            source.sort((a, b) => a.fileName.localeCompare(b.fileName, undefined, { sensitivity: 'base', numeric: true }));
            return source;
        }

        if (sortBy === 'size') {
            source.sort((a, b) => (Number(b.fileSizeBytes) || 0) - (Number(a.fileSizeBytes) || 0));
            return source;
        }

        source.sort((a, b) => b.timestamp - a.timestamp);
        return source;
    }, [filteredItems, sortBy]);

    const pinnedItems = useMemo(() => {
        return sortedItems.filter((item) => item.is_favorite || item.is_reference);
    }, [sortedItems]);

    const chatItems = useMemo(() => {
        return sortedItems.filter((item) => item.source === 'my_chats');
    }, [sortedItems]);

    const recentItems = useMemo(() => {
        return showAllRecent ? sortedItems : sortedItems.slice(0, 5);
    }, [showAllRecent, sortedItems]);

    const visibleItems = useMemo(() => {
        if (activeSectionTab === 'pinned') return pinnedItems;
        if (activeSectionTab === 'all') return sortedItems;
        if (activeSectionTab === 'chat_files') return chatItems;
        return recentItems;
    }, [activeSectionTab, pinnedItems, chatItems, recentItems, sortedItems]);

    useEffect(() => {
        const candidates = visibleItems
            .filter((item) => Boolean(item?.id))
            .slice(0, 24)
            .filter((item) => !previewUrls[item.id] && !previewRequestedRef.current.has(item.id));

        if (candidates.length === 0) return;

        let cancelled = false;

        (async () => {
            for (const item of candidates) {
                previewRequestedRef.current.add(item.id);
                const url = await resolveItemUrl(item, { download: false });
                if (!cancelled && url) {
                    setPreviewUrls((previous) => {
                        if (previous[item.id]) return previous;
                        return { ...previous, [item.id]: url };
                    });
                }
            }
        })();

        return () => {
            cancelled = true;
        };
    }, [previewUrls, resolveItemUrl, visibleItems]);

    useEffect(() => {
        const params = new URLSearchParams(location.search || '');
        const itemId = (params.get('itemId') || '').trim();
        if (!itemId) return;

        const target = itemsWithMeta.find((item) => String(item.id) === itemId);
        if (!target) return;

        setActiveSectionTab('recent');
        setSearchTerm('');
        setShowAllRecent(true);
        setHighlightItemId(target.id);

        window.setTimeout(() => {
            itemRefs.current[target.id]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 130);

        const timer = window.setTimeout(() => {
            setHighlightItemId(null);
        }, 5000);

        return () => {
            clearTimeout(timer);
        };
    }, [itemsWithMeta, location.search]);

    const handleDropZone = async (event) => {
        event.preventDefault();
        setIsDragActive(false);
        await uploadFiles(event.dataTransfer.files);
    };

    const handleDropAreaClick = () => {
        if (uploadInputRef.current) {
            uploadInputRef.current.click();
        }
    };

    const renderFileVisual = (item, previewUrl) => {
        const sourceUrl = String(previewUrl || item?.file_url || item?.download_url || '');
        const previewKind = inferPreviewKind(item, sourceUrl);
        const effectiveExtension = String(item?.extension || getExtensionFromUrl(sourceUrl) || '').toLowerCase();

        if (previewKind === 'image' && sourceUrl) {
            return (
                <img
                    src={sourceUrl}
                    alt={item.fileName}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
            );
        }

        if (previewKind === 'video' && sourceUrl) {
            return (
                <video
                    src={sourceUrl}
                    muted
                    playsInline
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
            );
        }

        if (previewKind === 'pdf' && sourceUrl) {
            return (
                <iframe
                    title={`preview-${item.id}`}
                    src={`${sourceUrl}#page=1&toolbar=0&navpanes=0&scrollbar=0`}
                    style={{ width: '100%', height: '100%', border: 0 }}
                />
            );
        }

        if (previewKind === 'video') {
            return <VideocamOutlinedIcon sx={{ fontSize: 26, color: 'info.main' }} />;
        }

        if (previewKind === 'pdf') {
            return <PictureAsPdfOutlinedIcon sx={{ fontSize: 26, color: 'error.main' }} />;
        }

        if (['doc', 'docx'].includes(effectiveExtension)) {
            return <ArticleOutlinedIcon sx={{ fontSize: 26, color: 'primary.main' }} />;
        }

        if (['xls', 'xlsx', 'csv'].includes(effectiveExtension)) {
            return <TableChartOutlinedIcon sx={{ fontSize: 26, color: 'success.main' }} />;
        }

        return <InsertDriveFileOutlinedIcon sx={{ fontSize: 26, color: 'text.secondary' }} />;
    };

    const renderVaultCard = (item, keyPrefix) => {
        const isBusy = busyItemId === item.id;
        const highlighted = highlightItemId === item.id;
        const sharedLabel = getSharedToLabel(item.shared_with);
        const cardPreviewUrl = previewUrls[item.id] || item.file_url || item.download_url;

        return (
            <Paper
                key={`${keyPrefix}-${item.id}`}
                ref={(node) => {
                    if (node) itemRefs.current[item.id] = node;
                }}
                variant="outlined"
                sx={{
                    p: 1,
                    borderRadius: 1.5,
                    backgroundColor: vaultColors.panelBg,
                    borderColor: highlighted ? vaultColors.highlightBorder : vaultColors.panelBorder,
                    borderTopWidth: 2,
                    borderTopColor: item.mediaType === 'image' ? 'info.main' : item.extension === 'pdf' ? 'error.main' : 'primary.main',
                    boxShadow: highlighted ? vaultColors.highlightShadow : 'none',
                }}
            >
                <Box
                    onClick={() => openItem(item)}
                    sx={{
                        height: 84,
                        borderRadius: 1,
                        bgcolor: vaultColors.previewBg,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        overflow: 'hidden',
                        cursor: 'pointer',
                    }}
                >
                    {renderFileVisual(item, cardPreviewUrl)}
                </Box>

                <Typography sx={{ mt: 0.8, fontSize: '0.74rem', fontWeight: 600 }} noWrap>
                    {item.fileName}
                </Typography>
                <Typography sx={{ mt: 0.2, fontSize: '0.66rem', color: vaultColors.mutedText }}>
                    {formatMonthDay(item.created_at)} • {formatBytes(item.fileSizeBytes)}
                </Typography>
                {item.source === 'my_chats' && (
                    <Typography sx={{ mt: 0.2, fontSize: '0.64rem', color: vaultColors.mutedText, fontWeight: 500 }} noWrap>
                        Chat: {item.chat_context_name || 'DM'} • {item.chat_sender_name}
                    </Typography>
                )}
                {sharedLabel && (
                    <Typography sx={{ mt: 0.2, fontSize: '0.64rem', color: vaultColors.link }} noWrap>
                        {sharedLabel}
                    </Typography>
                )}

                <Stack direction="row" spacing={0.3} sx={{ mt: 0.45 }}>
                    <Tooltip title={item.is_favorite ? 'Unpin' : 'Pin'}>
                        <span>
                            <IconButton size="small" onClick={() => toggleFavorite(item)} disabled={isBusy}>
                                {item.is_favorite ? <StarIcon sx={{ fontSize: 16, color: vaultColors.iconWarning }} /> : <StarBorderIcon sx={{ fontSize: 16, color: vaultColors.iconMuted }} />}
                            </IconButton>
                        </span>
                    </Tooltip>

                    <Tooltip title="Share">
                        <span>
                            <IconButton size="small" onClick={() => openShareDialog(item)} disabled={isBusy}>
                                <ShareOutlinedIcon sx={{ fontSize: 16, color: vaultColors.iconMuted }} />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title="View">
                        <span>
                            <IconButton size="small" onClick={() => openItem(item)} disabled={isBusy}>
                                <VisibilityOutlinedIcon sx={{ fontSize: 16, color: vaultColors.iconMuted }} />
                            </IconButton>
                        </span>
                    </Tooltip>
                    <Tooltip title="Download">
                        <span>
                            <IconButton size="small" onClick={() => downloadItem(item, item.fileName)} disabled={isBusy}>
                                <DownloadIcon sx={{ fontSize: 16, color: vaultColors.iconMuted }} />
                            </IconButton>
                        </span>
                    </Tooltip>
                    {item.source === 'my_chats' && item.chat_message_id && (
                        <Tooltip title="Open in Chat">
                            <span>
                                <IconButton
                                    size="small"
                                    onClick={() => navigate(`/mydesk/chats?messageId=${item.chat_message_id}`)}
                                    disabled={isBusy}
                                >
                                    <ChatOutlinedIcon sx={{ fontSize: 16, color: vaultColors.iconMuted }} />
                                </IconButton>
                            </span>
                        </Tooltip>
                    )}
                    <Tooltip title="Delete">
                        <span>
                            <IconButton size="small" onClick={() => removeItem(item)} disabled={isBusy}>
                                <DeleteOutlineIcon sx={{ fontSize: 16, color: vaultColors.iconDanger }} />
                            </IconButton>
                        </span>
                    </Tooltip>
                </Stack>
            </Paper>
        );
    };

    return (
        <Paper
            variant="outlined"
            sx={{
                p: 2,
                borderRadius: 2,
                backgroundColor: vaultColors.shellBg,
                borderColor: vaultColors.shellBorder,
                color: vaultColors.shellText,
                boxShadow: vaultColors.cardShadow,
                width: '100%',
            }}
        >
            <input
                ref={uploadInputRef}
                hidden
                multiple
                type="file"
                onChange={(event) => uploadFiles(event.target.files)}
            />

            <Stack spacing={1.5}>
                {storageStats && (
                    <Paper
                        variant="outlined"
                        sx={{
                            p: 1.5,
                            borderRadius: 1.5,
                            bgcolor: vaultColors.panelBg,
                            borderColor: vaultColors.panelBorder,
                        }}
                    >
                        <Typography variant="subtitle2" sx={{ fontWeight: 700, fontSize: '0.8rem', mb: 1 }}>
                            Storage Analytics & Usage
                        </Typography>
                        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={3} alignItems="center" justifyContent="space-between">
                            <Box sx={{ width: '100%', maxWidth: 400 }}>
                                <Stack direction="row" justifyContent="space-between" sx={{ mb: 0.5 }}>
                                    <Typography sx={{ fontSize: '0.74rem', color: vaultColors.mutedText }}>
                                        Total Files: {storageStats.total_files}
                                    </Typography>
                                    <Typography sx={{ fontSize: '0.74rem', fontWeight: 600 }}>
                                        {storageStats.chat_files} from Chat ({Math.round((storageStats.chat_files / (storageStats.total_files || 1)) * 100)}%)
                                    </Typography>
                                </Stack>
                                <Box sx={{ height: 6, bgcolor: vaultColors.hintChipBg, borderRadius: 3, overflow: 'hidden', display: 'flex' }}>
                                    <Box
                                        sx={{
                                            width: `${(storageStats.chat_files / (storageStats.total_files || 1)) * 100}%`,
                                            bgcolor: 'primary.main',
                                            height: '100%',
                                            transition: 'width 0.3s ease',
                                        }}
                                    />
                                </Box>
                            </Box>

                            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mt: { xs: 1, sm: 0 } }}>
                                {[
                                    { key: 'images', label: 'Images', color: 'info.main' },
                                    { key: 'videos', label: 'Videos', color: 'secondary.main' },
                                    { key: 'documents', label: 'Docs', color: 'error.main' },
                                    { key: 'audio', label: 'Audio', color: 'warning.main' },
                                    { key: 'archives', label: 'Archives', color: 'success.main' },
                                    { key: 'shared_files', label: 'Shared', color: 'text.secondary' },
                                ].map((cat) => {
                                    const count = storageStats.by_category?.[cat.key] || 0;
                                    if (count === 0) return null;
                                    return (
                                        <Chip
                                            key={cat.key}
                                            size="small"
                                            label={`${cat.label}: ${count}`}
                                            sx={{
                                                fontSize: '0.68rem',
                                                height: 22,
                                                bgcolor: vaultColors.hintChipBg,
                                                borderColor: vaultColors.hintChipBorder,
                                                '& .MuiChip-label': { px: 1 },
                                            }}
                                        />
                                    );
                                })}
                            </Stack>
                        </Stack>
                    </Paper>
                )}

                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.25} justifyContent="space-between" alignItems={{ xs: 'stretch', md: 'center' }}>


                    <Stack direction={{ xs: 'column', sm: 'row' }} spacing={0.9} sx={{ width: { xs: '100%', md: 'auto' } }}>
                        <TextField
                            size="small"
                            placeholder="Search files..."
                            value={searchTerm}
                            onChange={(event) => setSearchTerm(event.target.value)}
                            sx={{
                                width: { xs: '100%', sm: 230 },
                                '& .MuiOutlinedInput-root': {
                                    height: 34,
                                    color: 'text.primary',
                                    backgroundColor: vaultColors.searchBg,
                                    borderRadius: 1.5,
                                },
                                '& .MuiOutlinedInput-notchedOutline': {
                                    borderColor: vaultColors.panelBorder,
                                },
                            }}
                            InputProps={{
                                startAdornment: (
                                    <InputAdornment position="start">
                                        <SearchIcon sx={{ fontSize: 16, color: vaultColors.mutedText }} />
                                    </InputAdornment>
                                ),
                            }}
                        />
                        <Button
                            component="label"
                            variant="contained"
                            size="small"
                            disabled={isUploading}
                            sx={{
                                height: 34,
                                px: 1.8,
                                borderRadius: 1.4,
                                textTransform: 'none',
                                fontWeight: 600,
                            }}
                        >
                            {isUploading ? 'Uploading...' : 'Upload'}
                            <input hidden multiple type="file" onChange={(event) => uploadFiles(event.target.files)} />
                        </Button>
                    </Stack>
                </Stack>

                <Box
                    role="button"
                    tabIndex={0}
                    onClick={handleDropAreaClick}
                    onDragOver={(event) => {
                        event.preventDefault();
                        if (!isDragActive) setIsDragActive(true);
                    }}
                    onDragLeave={(event) => {
                        event.preventDefault();
                        setIsDragActive(false);
                    }}
                    onDrop={handleDropZone}
                    sx={{
                        p: 2,
                        borderRadius: 1.8,
                        border: '1px dashed',
                        borderColor: isDragActive ? vaultColors.activeTab : vaultColors.dropBorder,
                        backgroundColor: isDragActive ? vaultColors.dropBgActive : vaultColors.dropBgIdle,
                        textAlign: 'center',
                        cursor: 'pointer',
                        transition: 'border-color 0.2s ease, background-color 0.2s ease',
                    }}
                >
                    <Avatar
                        sx={{
                            width: 36,
                            height: 36,
                            bgcolor: alpha(muiTheme.palette.primary.main, isDarkMode ? 0.22 : 0.12),
                            color: muiTheme.palette.primary.main,
                            mx: 'auto',
                            mb: 1,
                        }}
                    >
                        <CloudUploadOutlinedIcon />
                    </Avatar>
                    <Typography sx={{ fontSize: '0.82rem', fontWeight: 600 }}>Drop files here or click to browse</Typography>


                </Box>

                <Stack
                    direction={{ xs: 'column', md: 'row' }}
                    spacing={1}
                    justifyContent="space-between"
                    alignItems={{ xs: 'stretch', md: 'center' }}
                >
                    <Stack direction="row" spacing={0.4} flexWrap="wrap" useFlexGap>
                        {[
                            { key: 'recent', label: 'Recent' },
                            { key: 'all', label: 'All files' },
                            { key: 'chat_files', label: 'Chat Files' },
                            { key: 'pinned', label: 'Pinned' },
                        ].map((tab) => {
                            const active = activeSectionTab === tab.key;
                            return (
                                <Button
                                    key={tab.key}
                                    size="small"
                                    onClick={() => setActiveSectionTab(tab.key)}
                                    sx={{
                                        px: 0.7,
                                        py: 0.2,
                                        minWidth: 0,
                                        textTransform: 'none',
                                        fontSize: '0.76rem',
                                        color: active ? vaultColors.activeTab : vaultColors.mutedText,
                                        fontWeight: active ? 700 : 500,
                                        borderBottom: active ? `2px solid ${vaultColors.activeTab}` : '2px solid transparent',
                                        borderRadius: 0,
                                    }}
                                >
                                    {tab.label}
                                </Button>
                            );
                        })}
                    </Stack>

                    <Stack direction="row" spacing={0.8} alignItems="center" sx={{ flexWrap: 'wrap' }}>
                        <Select
                            size="small"
                            value={mediaFilter}
                            onChange={(event) => setMediaFilter(event.target.value)}
                            sx={{
                                minWidth: 118,
                                height: 32,
                                fontSize: '0.76rem',
                                bgcolor: vaultColors.searchBg,
                                '& .MuiOutlinedInput-notchedOutline': {
                                    borderColor: vaultColors.panelBorder,
                                },
                                '& .MuiSelect-select': {
                                    py: 0.75,
                                },
                            }}
                        >
                            <MenuItem value="all">All types</MenuItem>
                            <MenuItem value="images">Images</MenuItem>
                            <MenuItem value="pdf">PDF</MenuItem>
                        </Select>

                        <Select
                            size="small"
                            value={sortBy}
                            onChange={(event) => setSortBy(event.target.value)}
                            sx={{
                                minWidth: 112,
                                height: 32,
                                fontSize: '0.76rem',
                                bgcolor: vaultColors.searchBg,
                                '& .MuiOutlinedInput-notchedOutline': {
                                    borderColor: vaultColors.panelBorder,
                                },
                                '& .MuiSelect-select': {
                                    py: 0.75,
                                },
                            }}
                        >
                            <MenuItem value="date">Date</MenuItem>
                            <MenuItem value="name">Name</MenuItem>
                            <MenuItem value="size">Size</MenuItem>
                        </Select>
                    </Stack>
                </Stack>

                {activeSectionTab === 'recent' && (
                    <Stack direction="row" alignItems="center" justifyContent="space-between">

                        <Button
                            size="small"
                            onClick={() => setShowAllRecent((previous) => !previous)}
                            sx={{
                                minWidth: 0,
                                textTransform: 'none',
                                fontSize: '0.70rem',
                                color: vaultColors.link,
                                px: 0.2,
                            }}
                        >

                        </Button>
                    </Stack>
                )}

                {isLoading && (
                    <Stack alignItems="center" justifyContent="center" sx={{ py: 2.5 }}>
                        <CircularProgress size={22} />
                    </Stack>
                )}

                {!isLoading && activeSectionTab === 'recent' && (
                    <Stack spacing={0.65}>
                        {recentItems.length === 0 ? (
                            <Typography sx={{ fontSize: '0.74rem', color: vaultColors.mutedText }}>
                                No recent files for this view.
                            </Typography>
                        ) : (
                            recentItems.map((item) => {
                                const isBusy = busyItemId === item.id;
                                const highlighted = highlightItemId === item.id;
                                const sharedLabel = getSharedToLabel(item.shared_with);
                                return (
                                    <Paper
                                        key={`recent-${item.id}`}
                                        ref={(node) => {
                                            if (node) itemRefs.current[item.id] = node;
                                        }}
                                        variant="outlined"
                                        sx={{
                                            p: 0.75,
                                            borderRadius: 1,
                                            bgcolor: vaultColors.previewBg,
                                            borderColor: highlighted ? vaultColors.highlightBorder : vaultColors.panelBorder,
                                            boxShadow: highlighted ? vaultColors.highlightShadow : 'none',
                                        }}
                                    >
                                        <Stack direction="row" alignItems="center" spacing={0.9}>
                                            <Avatar sx={{ width: 22, height: 22, bgcolor: vaultColors.panelBg }}>
                                                {renderFileVisual(item, previewUrls[item.id] || item.file_url || item.download_url)}
                                            </Avatar>

                                            <Box sx={{ minWidth: 0, flex: 1, cursor: 'pointer' }} onClick={() => openItem(item)}>
                                                <Typography sx={{ fontSize: '0.73rem', fontWeight: 500 }} noWrap>
                                                    {item.fileName}
                                                </Typography>
                                                {item.source === 'my_chats' && (
                                                    <Typography sx={{ fontSize: '0.64rem', color: vaultColors.mutedText, mt: 0.1 }} noWrap>
                                                        Chat: {item.chat_context_name || 'DM'} • {item.chat_sender_name}
                                                    </Typography>
                                                )}
                                                {sharedLabel && (
                                                    <Typography sx={{ fontSize: '0.64rem', color: vaultColors.link, mt: 0.2 }} noWrap>
                                                        {sharedLabel}
                                                    </Typography>
                                                )}
                                            </Box>

                                            <Typography sx={{ fontSize: '0.67rem', color: vaultColors.mutedText, minWidth: 42, textAlign: 'right' }}>
                                                {formatMonthDay(item.created_at)}
                                            </Typography>
                                            <Typography sx={{ fontSize: '0.67rem', color: vaultColors.mutedText, minWidth: 62, textAlign: 'right' }}>
                                                {formatBytes(item.fileSizeBytes)}
                                            </Typography>

                                            <Stack direction="row" spacing={0.2}>
                                                <IconButton size="small" onClick={() => openItem(item)} disabled={isBusy}>
                                                    <VisibilityOutlinedIcon sx={{ fontSize: 15, color: vaultColors.iconMuted }} />
                                                </IconButton>
                                                <IconButton size="small" onClick={() => toggleFavorite(item)} disabled={isBusy}>
                                                    {item.is_favorite ? <StarIcon sx={{ fontSize: 15, color: vaultColors.iconWarning }} /> : <StarBorderIcon sx={{ fontSize: 15, color: vaultColors.iconMuted }} />}
                                                </IconButton>
                                                {item.source === 'my_chats' && item.chat_message_id && (
                                                    <IconButton size="small" onClick={() => navigate(`/mydesk/chats?messageId=${item.chat_message_id}`)} disabled={isBusy}>
                                                        <ChatOutlinedIcon sx={{ fontSize: 15, color: vaultColors.iconMuted }} />
                                                    </IconButton>
                                                )}
                                                <IconButton size="small" onClick={() => openShareDialog(item)} disabled={isBusy}>
                                                    <ShareOutlinedIcon sx={{ fontSize: 15, color: vaultColors.iconMuted }} />
                                                </IconButton>
                                            </Stack>
                                        </Stack>
                                    </Paper>
                                );
                            })
                        )}
                    </Stack>
                )}

                {!isLoading && activeSectionTab === 'all' && (
                    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' }, gap: 1 }}>
                        {filteredItems.length === 0 ? (
                            <Paper
                                variant="outlined"
                                sx={{
                                    gridColumn: '1 / -1',
                                    p: 1.25,
                                    borderRadius: 1.4,
                                    backgroundColor: vaultColors.panelBg,
                                    borderColor: vaultColors.panelBorder,
                                }}
                            >
                                <Typography sx={{ fontSize: '0.75rem', color: vaultColors.mutedText }}>
                                    No files found for this search.
                                </Typography>
                            </Paper>
                        ) : (
                            sortedItems.map((item) => renderVaultCard(item, 'all'))
                        )}
                    </Box>
                )}

                {!isLoading && activeSectionTab === 'chat_files' && (
                    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' }, gap: 1 }}>
                        {chatItems.length === 0 ? (
                            <Paper
                                variant="outlined"
                                sx={{
                                    gridColumn: '1 / -1',
                                    p: 1.25,
                                    borderRadius: 1.4,
                                    backgroundColor: vaultColors.panelBg,
                                    borderColor: vaultColors.panelBorder,
                                }}
                            >
                                <Typography sx={{ fontSize: '0.75rem', color: vaultColors.mutedText }}>
                                    No chat files found.
                                </Typography>
                            </Paper>
                        ) : (
                            chatItems.map((item) => renderVaultCard(item, 'chat'))
                        )}
                    </Box>
                )}

                {!isLoading && activeSectionTab === 'pinned' && (
                    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' }, gap: 1 }}>
                        {pinnedItems.length === 0 ? (
                            <Paper
                                variant="outlined"
                                sx={{
                                    gridColumn: '1 / -1',
                                    p: 1.25,
                                    borderRadius: 1.4,
                                    backgroundColor: vaultColors.panelBg,
                                    borderColor: vaultColors.panelBorder,
                                }}
                            >
                                <Typography sx={{ fontSize: '0.75rem', color: vaultColors.mutedText }}>
                                    No pinned files yet.
                                </Typography>
                            </Paper>
                        ) : (
                            pinnedItems.map((item) => renderVaultCard(item, 'pinned'))
                        )}
                    </Box>
                )}
            </Stack>

            <Dialog open={Boolean(shareDialogItem)} onClose={closeShareDialog} fullWidth maxWidth="sm">
                <DialogTitle>Share Vault Item</DialogTitle>
                <DialogContent dividers>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                        {shareDialogItem ? getFileName(shareDialogItem) : ''}
                    </Typography>
                    <Select
                        multiple
                        fullWidth
                        size="small"
                        value={shareSelection}
                        displayEmpty
                        onChange={(event) => {
                            const nextValue = event.target.value;
                            setShareSelection(Array.isArray(nextValue) ? nextValue : String(nextValue).split(','));
                        }}
                        renderValue={(selected) => {
                            if (!selected || selected.length === 0) {
                                return 'Select teammates';
                            }
                            return (
                                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                                    {selected.map((memberId) => {
                                        const member = memberOptions.find((entry) => String(entry.id) === String(memberId));
                                        return <Chip key={memberId} size="small" label={member ? member.label : String(memberId)} />;
                                    })}
                                </Stack>
                            );
                        }}
                    >
                        {memberOptions.map((member) => (
                            <MenuItem key={member.id} value={String(member.id)}>
                                {member.label}
                            </MenuItem>
                        ))}
                    </Select>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShareSelection([])} disabled={isSavingShares}>Clear</Button>
                    <Button onClick={closeShareDialog} disabled={isSavingShares}>Cancel</Button>
                    <Button variant="contained" onClick={saveShareDialog} disabled={isSavingShares}>
                        {isSavingShares ? 'Saving...' : 'Save'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Paper>
    );
}
