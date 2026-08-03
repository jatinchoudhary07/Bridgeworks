"""
vault_sync.py — MyChats ↔ MyVault integration
==============================================

Whenever a ChatMessage with an attachment is saved, this service
creates (or links) a corresponding GalleryItem in the sender's vault.

It also exposes helpers used by the API view that lets a *receiver*
save an incoming chat file to their own vault.
"""

import os
import logging
import typing
from django.utils import timezone

if typing.TYPE_CHECKING:
    from core.models.mydesk import GalleryItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# File-type classification helpers
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg', 'tiff', 'ico', 'heic'}
_VIDEO_EXTS = {'mp4', 'mov', 'avi', 'webm', 'mkv', 'flv', 'wmv', 'm4v', '3gp'}
_AUDIO_EXTS = {'mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma', 'aiff'}
_DOC_EXTS   = {'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'odt', 'ods', 'odp', 'txt', 'rtf', 'csv'}
_ARCH_EXTS  = {'zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'tar.gz', 'tar.bz2'}


def classify_file(file_name: str, mime_type: str = '') -> tuple[str, str]:
    """
    Return (media_type, category) for a file based on its name/MIME type.

    media_type  : 'image' | 'video' | 'audio' | 'file'
    category    : GalleryItem.CATEGORY_* constant value
    """
    from core.models.mydesk import GalleryItem  # local import to avoid circular

    ext = os.path.splitext(str(file_name or ''))[-1].lstrip('.').lower()

    # Override with MIME when extension is ambiguous / missing
    mime = (mime_type or '').lower()
    if mime.startswith('image/'):
        return 'image', GalleryItem.CATEGORY_IMAGES
    if mime.startswith('video/'):
        return 'video', GalleryItem.CATEGORY_VIDEOS
    if mime.startswith('audio/'):
        return 'audio', GalleryItem.CATEGORY_AUDIO

    if ext in _IMAGE_EXTS:
        return 'image', GalleryItem.CATEGORY_IMAGES
    if ext in _VIDEO_EXTS:
        return 'video', GalleryItem.CATEGORY_VIDEOS
    if ext in _AUDIO_EXTS:
        return 'audio', GalleryItem.CATEGORY_AUDIO
    if ext in _DOC_EXTS:
        return 'file', GalleryItem.CATEGORY_DOCUMENTS
    if ext in _ARCH_EXTS:
        return 'file', GalleryItem.CATEGORY_ARCHIVES

    return 'file', GalleryItem.CATEGORY_SHARED


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------

def _resolve_context_name(message) -> str:
    """Return a human-readable conversation context label."""
    if message.room_id and message.room:
        return message.room.name
    if message.channel_id and message.channel:
        return f'#{message.channel.name}'
    # Direct message — no room/channel
    return 'Direct Message'


def _get_or_create_chat_album(user, org_id: str):
    """
    Return (album, created) for the special 'Chat Files' album
    that belongs to the given user.
    """
    from core.models.mydesk import GalleryAlbum
    album, created = GalleryAlbum.objects.get_or_create(
        org_id=org_id,
        user=user,
        name='Chat Files',
    )
    return album, created


def sync_attachment_to_vault(message) -> 'GalleryItem | None':
    """
    Called right after a ChatMessage with an attachment is saved.

    Creates a GalleryItem in the *sender's* vault referencing the
    same file storage path.  Returns the created item, or None if
    skipped (no attachment, or on error).

    NOTE: We store the file path directly — no physical file copy.
    """
    from core.models.mydesk import GalleryItem

    if not message.attachment:
        return None

    # Don't duplicate: if a vault item for this message already exists, skip.
    if GalleryItem.objects.filter(
        chat_message_id=message.pk,
        user=message.sender,
    ).exists():
        return None

    try:
        sender = message.sender
        org_id = ''
        try:
            if hasattr(sender, 'team_settings'):
                org_id = sender.team_settings.organization.organization_id or ''
        except Exception:
            pass

        album, _ = _get_or_create_chat_album(sender, org_id)
        context_name = _resolve_context_name(message)
        sender_name = sender.get_full_name().strip() or sender.username
        media_type, category = classify_file(
            message.attachment_name or message.attachment.name,
            message.attachment_mime_type or '',
        )

        item = GalleryItem.objects.create(
            org_id=org_id,
            user=sender,
            album=album,
            file=message.attachment,          # same FileField storage path
            media_type=media_type,
            captured_on=timezone.localdate(),
            source=GalleryItem.SOURCE_MY_CHATS,
            category=category,
            chat_message_id=message.pk,
            chat_context_name=context_name,
            chat_sender_name=sender_name,
            chat_shared_at=message.created_at or timezone.now(),
        )
        return item

    except Exception:
        logger.exception('vault_sync: Failed to sync chat attachment (message_id=%s)', message.pk)
        return None


def save_received_attachment_to_vault(message, recipient_user) -> 'GalleryItem | None':
    """
    Save a *received* chat attachment to the recipient's own vault.
    Called from the API when a user explicitly requests to save a file.

    Returns the GalleryItem (new or pre-existing) or None on error.
    """
    from core.models.mydesk import GalleryItem

    if not message.attachment:
        return None

    org_id = ''
    try:
        if hasattr(recipient_user, 'team_settings'):
            org_id = recipient_user.team_settings.organization.organization_id or ''
    except Exception:
        pass

    # Idempotent: return existing item if already saved.
    existing = GalleryItem.objects.filter(
        chat_message_id=message.pk,
        user=recipient_user,
    ).first()
    if existing:
        return existing

    try:
        album, _ = _get_or_create_chat_album(recipient_user, org_id)
        context_name = _resolve_context_name(message)
        sender_name = message.sender.get_full_name().strip() or message.sender.username
        media_type, category = classify_file(
            message.attachment_name or message.attachment.name,
            message.attachment_mime_type or '',
        )

        item = GalleryItem.objects.create(
            org_id=org_id,
            user=recipient_user,
            album=album,
            file=message.attachment,
            media_type=media_type,
            captured_on=timezone.localdate(),
            source=GalleryItem.SOURCE_MY_CHATS,
            category=category,
            chat_message_id=message.pk,
            chat_context_name=context_name,
            chat_sender_name=sender_name,
            chat_shared_at=message.created_at or timezone.now(),
        )
        return item

    except Exception:
        logger.exception(
            'vault_sync: Failed to save received attachment to vault '
            '(message_id=%s, user_id=%s)', message.pk, recipient_user.id
        )
        return None


def get_storage_stats(user, org_id: str) -> dict:
    """
    Return aggregated storage stats for the user's vault.
    Used by the storage analytics panel in the frontend.
    """
    from django.db.models import Sum, Count
    from core.models.mydesk import GalleryItem

    qs = GalleryItem.objects.filter(org_id=org_id, user=user)

    by_category = {}
    for row in qs.values('category').annotate(total=Count('id')):
        by_category[row['category']] = row['total']

    total_count = qs.count()
    chat_count  = qs.filter(source=GalleryItem.SOURCE_MY_CHATS).count()

    return {
        'total_files': total_count,
        'chat_files': chat_count,
        'by_category': by_category,
    }
