from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum
from django.utils import timezone
from .models import StickyNote, PostItComment, PostItNotification, DiaryEntry, DiaryAttachment
from core.services.notifications import push_unified_notification
from core.permissions import HasModulePermission
from .utils import _get_org_id_or_none
import re
import json

User = get_user_model()

# ========================= SERIALIZERS =========================

class StickyNoteSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.first_name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.first_name', read_only=True)
    completed_by_name = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    shared_with_user_ids = serializers.SerializerMethodField()

    attachment_url = serializers.SerializerMethodField()

    def get_completed_by_name(self, obj):
        """Return the name of the user who completed the note"""
        if obj.completed_by:
            return obj.completed_by.first_name or obj.completed_by.username
        return None

    def get_attachment_url(self, obj):
        """Return full Cloudinary URL for attachment"""
        if not obj.attachment:
            return None
        try:
            url = str(obj.attachment.url or '')
        except Exception:
            return None
        request = self.context.get('request')
        if request and url.startswith('/'):
            return request.build_absolute_uri(url)
        return url or None

    def get_comment_count(self, obj):
        # Comments are public within the note thread
        root = obj.parent_note if obj.parent_note else obj
        return root.comments.count()

    def get_shared_with_user_ids(self, obj):
        """Return IDs of users this note has been shared with (via copies)"""
        return list(obj.copies.values_list('assigned_to_id', flat=True))

    class Meta:
        model = StickyNote
        fields = [
            'id', 'content', 'created_by', 'assigned_to', 
            'created_by_name', 'assigned_to_name',
            'color', 'x_position', 'y_position', 
            'is_completed', 'shared_with_names', 'parent_note',
            'attachment', 'attachment_filename', 'attachment_url',
            'sent_at', 'sent_by', 'completed_at', 'completed_by', 'completed_by_name',
            'is_deleted', 'deleted_at', 'deleted_by',
            'comment_count', 'shared_with_user_ids',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_by', 'assigned_to', 'created_at', 'updated_at', 'shared_with_names', 'attachment_url',
                            'sent_at', 'sent_by', 'completed_at', 'completed_by', 'completed_by_name', 'deleted_at', 'deleted_by']


class PostItCommentSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    def get_user_name(self, obj):
        return obj.user.first_name or obj.user.username

    class Meta:
        model = PostItComment
        fields = ['id', 'note', 'user', 'user_name', 'text', 'created_at']
        read_only_fields = ['user', 'note', 'created_at']


class PostItNotificationSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()
    note_preview = serializers.SerializerMethodField()

    def get_sender_name(self, obj):
        return obj.sender.first_name or obj.sender.username

    def get_note_preview(self, obj):
        if obj.note:
            return obj.note.content[:60] + ('...' if len(obj.note.content) > 60 else '')
        return ''

    class Meta:
        model = PostItNotification
        fields = ['id', 'recipient', 'sender', 'sender_name', 'note', 'comment', 
                  'message', 'note_preview', 'is_read', 'created_at']
        read_only_fields = ['recipient', 'sender', 'note', 'comment', 'message', 'created_at']


class DiaryAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = DiaryAttachment
        fields = ['id', 'original_name', 'mime_type', 'file_size', 'file_url', 'created_at']

    def get_file_url(self, obj):
        if not obj.file:
            return None
        try:
            url = str(obj.file.url or '')
        except Exception:
            return None
        request = self.context.get('request')
        if request and url.startswith('/'):
            return request.build_absolute_uri(url)
        return url or None


class DiaryEntrySerializer(serializers.ModelSerializer):
    attachments = DiaryAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = DiaryEntry
        fields = [
            'id',
            'title',
            'note',
            'tags',
            'hours',
            'entry_type',
            'entry_date',
            'attachments',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'attachments', 'created_at', 'updated_at']


class HRDiaryEntrySerializer(DiaryEntrySerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_name = serializers.SerializerMethodField()
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta(DiaryEntrySerializer.Meta):
        fields = DiaryEntrySerializer.Meta.fields + ['user_id', 'user_name', 'user_email']

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.first_name or obj.user.username or obj.user.email or ''


# ========================= VIEWSETS =========================

class StickyNoteViewSet(viewsets.ModelViewSet):
    serializer_class = StickyNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = StickyNote.objects.filter(
            assigned_to=self.request.user
        ).select_related('created_by', 'assigned_to', 'parent_note').order_by('-created_at')

        detail_actions = {
            'retrieve',
            'update',
            'partial_update',
            'destroy',
            'move',
            'complete',
            'unarchive',
            'delete_note',
            'permanent_delete',
            'pass_note',
            'comments',
            'add_comment',
            'mark_notifications_read',
            'remove_attachment',
        }

        if getattr(self, 'action', None) in detail_actions:
            return queryset

        view_mode = self.request.query_params.get('view', 'active')
        if view_mode == 'deleted':
            return queryset.filter(is_deleted=True)

        return queryset.filter(is_completed=False, is_deleted=False)

    def perform_update(self, serializer):
        if serializer.instance.created_by_id != self.request.user.id:
            raise PermissionDenied("Only the note creator can edit this note.")
        serializer.save()

    def perform_create(self, serializer):
        # Assign current user as creator and initially assign to self
        # Assign user's specific post-it color
        user_settings = getattr(self.request.user, 'team_settings', None)
        color = user_settings.postit_color if user_settings else '#FFFD82'
        
        attachment = self.request.FILES.get('attachment')
        if attachment:
            serializer.save(
                created_by=self.request.user,
                assigned_to=self.request.user,
                color=color,
                attachment_filename=attachment.name
            )
        else:
            serializer.save(
                created_by=self.request.user,
                assigned_to=self.request.user
            )

    @action(detail=False, methods=['get'])
    def completed(self, request):
        """List completed notes assigned to the current user"""
        notes = StickyNote.objects.filter(
            assigned_to=request.user,
            is_completed=True,
            is_deleted=False
        ).select_related('created_by', 'assigned_to', 'parent_note').order_by('-completed_at')
        serializer = self.get_serializer(notes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """Update x, y coordinates after drag"""
        note = self.get_object()

        x = request.data.get('x')
        y = request.data.get('y')
        
        if x is not None: note.x_position = x
        if y is not None: note.y_position = y
        note.save()
        
        return Response({'status': 'moved'})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark as completed with timestamp and user tracking"""
        from django.utils import timezone
        now = timezone.now()
        note = self.get_object()

        note.is_completed = True
        note.completed_at = now
        note.completed_by = request.user
        note.save()
        
        # Propagate UP: if this is a copy, mark parent (sender's original) as completed
        # AND propagate to all sibling copies (other recipients)
        if note.parent_note:
            parent = note.parent_note
            if not parent.is_completed:
                parent.is_completed = True
                parent.completed_at = now
                parent.completed_by = request.user
                parent.save()
            # Also mark all sibling copies as completed
            for sibling in parent.copies.filter(is_completed=False).exclude(id=note.id):
                sibling.is_completed = True
                sibling.completed_at = now
                sibling.completed_by = request.user
                sibling.save()
        
        # Propagate DOWN: if this is the original, mark ALL copies (recipients) as completed
        for copy in note.copies.filter(is_completed=False):
            copy.is_completed = True
            copy.completed_at = now
            copy.completed_by = request.user
            copy.save()
        
        return Response({'status': 'completed'})

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """Move a completed note back to active"""
        note = self.get_object()

        note.is_completed = False
        note.completed_at = None
        note.completed_by = None
        note.save()

        if note.parent_note:
            parent = note.parent_note
            if parent.is_completed:
                parent.is_completed = False
                parent.completed_at = None
                parent.completed_by = None
                parent.save()
            for sibling in parent.copies.filter(is_completed=True).exclude(id=note.id):
                sibling.is_completed = False
                sibling.completed_at = None
                sibling.completed_by = None
                sibling.save()

        for copy in note.copies.filter(is_completed=True):
            copy.is_completed = False
            copy.completed_at = None
            copy.completed_by = None
            copy.save()

        return Response({'status': 'unarchived'})

    @action(detail=True, methods=['post'])
    def delete_note(self, request, pk=None):
        """Mark a note as deleted"""
        from django.utils import timezone
        note = self.get_object()

        if note.created_by_id != request.user.id:
            return Response({'error': 'Only the note creator can delete this note'}, status=403)

        now = timezone.now()
        note.is_deleted = True
        note.deleted_at = now
        note.deleted_by = request.user
        note.save()

        if note.parent_note:
            parent = note.parent_note
            if not parent.is_deleted:
                parent.is_deleted = True
                parent.deleted_at = now
                parent.deleted_by = request.user
                parent.save()
            for sibling in parent.copies.filter(is_deleted=False).exclude(id=note.id):
                sibling.is_deleted = True
                sibling.deleted_at = now
                sibling.deleted_by = request.user
                sibling.save()

        for copy in note.copies.filter(is_deleted=False):
            copy.is_deleted = True
            copy.deleted_at = now
            copy.deleted_by = request.user
            copy.save()

        return Response({'status': 'deleted'})

    @action(detail=True, methods=['delete'])
    def permanent_delete(self, request, pk=None):
        """Permanently remove note(s) from the database"""
        note = self.get_object()

        if note.created_by_id != request.user.id:
            return Response({'error': 'Only the note creator can permanently delete this note'}, status=403)

        if note.parent_note:
            parent = note.parent_note
            sibling_ids = list(parent.copies.values_list('id', flat=True))
            StickyNote.objects.filter(id__in=sibling_ids).delete()
            parent.delete()
            return Response({'status': 'permanently_deleted'})

        copy_ids = list(note.copies.values_list('id', flat=True))
        StickyNote.objects.filter(id__in=copy_ids).delete()
        note.delete()
        return Response({'status': 'permanently_deleted'})

    @action(detail=True, methods=['post'])
    def pass_note(self, request, pk=None):
        """Share note with one or more users"""
        note = self.get_object()

        if note.created_by_id != request.user.id:
            return Response({'error': 'Only the note creator can share this note'}, status=403)

        target_user_ids = request.data.get('target_user_ids', [])
        
        # Support legacy single user ID (backward compatibility)
        if 'target_user_id' in request.data:
            target_user_ids = [request.data.get('target_user_id')]
        
        if not target_user_ids:
            return Response({'error': 'At least one target user ID required'}, status=400)

        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({'error': 'Organization context not found'}, status=400)

        if not isinstance(target_user_ids, list):
            target_user_ids = [target_user_ids]

        share_everyone = any(str(user_id).lower() == 'everyone' for user_id in target_user_ids)

        if share_everyone:
            org_users = User.objects.filter(
                Q(team_settings__organization__organization_id=org_id) |
                Q(shop_credentials__organization_id=org_id)
            ).exclude(id=request.user.id).distinct()
        else:
            parsed_user_ids = []
            for user_id in target_user_ids:
                try:
                    parsed_user_ids.append(int(user_id))
                except (TypeError, ValueError):
                    continue
            org_users = User.objects.filter(
                id__in=parsed_user_ids
            ).filter(
                Q(team_settings__organization__organization_id=org_id) |
                Q(shop_credentials__organization_id=org_id)
            ).exclude(id=request.user.id).distinct()

        existing_user_ids = set(note.copies.values_list('assigned_to_id', flat=True))
        target_users = [user for user in org_users if user.id not in existing_user_ids]
            
        shared_with = []
        shared_with_names = []
        for target_user in target_users:
            StickyNote.objects.create(
                content=note.content,
                created_by=note.created_by,
                assigned_to=target_user,
                color=note.color,
                x_position=note.x_position,
                y_position=note.y_position,
                attachment=note.attachment,
                attachment_filename=note.attachment_filename,
                parent_note=note
            )
            user_name = target_user.first_name or target_user.username
            shared_with.append(user_name)
            shared_with_names.append(user_name)
            root_note_id = note.parent_note_id or note.id
            push_unified_notification(
                recipient=target_user,
                actor=request.user,
                module='postits',
                action='share',
                title='PostIt shared with you',
                message=f"{request.user.first_name or request.user.username} shared a note with you",
                preview=(note.content or '')[:120],
                entity_type='sticky_note',
                entity_id=root_note_id,
                deep_link={
                    'page': '/mydesk/notes',
                    'section': 'my-notes',
                    'noteId': str(root_note_id),
                },
            )

        if share_everyone:
            shared_with_names.append('Everyone')
        
        # Update original: append new names to existing shared_with_names
        from django.utils import timezone
        existing = note.shared_with_names or ''
        existing_list = [n.strip() for n in existing.split(',') if n.strip()]
        # Add only new names (avoid duplicates)
        for name in shared_with_names:
            if name not in existing_list:
                existing_list.append(name)
        note.shared_with_names = ", ".join(existing_list)
        note.sent_at = timezone.now()
        note.sent_by = request.user
        note.save()
        
        if shared_with:
            return Response({
                'status': 'shared', 
                'shared_with': shared_with,
                'count': len(shared_with)
            })
        else:
            return Response({'status': 'no_new_recipients', 'count': 0})

    # ===================== COMMENTS =====================

    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """List all comments for the root note thread"""
        note = self.get_object()
        root = note.parent_note if note.parent_note else note

        serializer = PostItCommentSerializer(root.comments.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """Add a comment to a note. Parses @mentions and creates notifications."""
        note = self.get_object()
        root = note.parent_note if note.parent_note else note

        is_private_root_note = (
            root.parent_note is None
            and root.created_by_id == root.assigned_to_id
            and not root.copies.exists()
        )
        if is_private_root_note:
            return Response({'error': 'Comments are disabled for private notes'}, status=403)

        text = request.data.get('text', '').strip()
        if not text:
            return Response({'error': 'Comment text is required'}, status=400)

        # Create the comment on root
        comment = PostItComment.objects.create(
            note=root,
            user=request.user,
            text=text
        )

        # Parse @mentions - match @Name patterns
        mention_pattern = re.compile(r'@(\w+)')
        mentioned_names = mention_pattern.findall(text)
        
        if mentioned_names:
            from django.db.models import Q
            sender_name = request.user.first_name or request.user.username
            for name in mentioned_names:
                matched_users = User.objects.filter(
                    Q(first_name__iexact=name) | Q(username__iexact=name)
                ).exclude(id=request.user.id)
                
                for user in matched_users:
                    PostItNotification.objects.create(
                        recipient=user,
                        sender=request.user,
                        note=root,
                        comment=comment,
                        message=f"{sender_name} mentioned you: \"{text[:80]}\""
                    )
                    push_unified_notification(
                        recipient=user,
                        actor=request.user,
                        module='postits',
                        action='mention',
                        title='You were mentioned in a PostIt comment',
                        message=f"{sender_name} mentioned you in a note comment",
                        preview=text[:200],
                        entity_type='sticky_note',
                        entity_id=root.id,
                        sub_entity_type='comment',
                        sub_entity_id=comment.id,
                        deep_link={
                            'page': '/mydesk/notes',
                            'section': 'my-notes',
                            'noteId': str(root.id),
                            'commentId': str(comment.id),
                        },
                    )
        
        serializer = PostItCommentSerializer(comment)
        return Response(serializer.data, status=201)


# ========================= NOTIFICATIONS VIEWSET =========================

class PostItNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PostItNotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PostItNotification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')[:50]

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Quick count of unread notifications"""
        count = PostItNotification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        return Response({'count': count})

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a notification as read"""
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'status': 'read'})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        PostItNotification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True)
        return Response({'status': 'all_read'})


class DiaryEntryListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        entries = DiaryEntry.objects.filter(user=request.user).prefetch_related('attachments')

        query = (request.query_params.get('q') or '').strip()
        if query:
            entries = entries.filter(Q(title__icontains=query) | Q(note__icontains=query))

        entry_type = (request.query_params.get('entry_type') or '').strip().lower()
        if entry_type:
            entries = entries.filter(entry_type=entry_type)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            entries = entries.filter(entry_date__gte=start_date)
        if end_date:
            entries = entries.filter(entry_date__lte=end_date)

        order = (request.query_params.get('order') or 'newest').strip().lower()
        if order == 'oldest':
            entries = entries.order_by('entry_date', 'created_at')
        else:
            entries = entries.order_by('-entry_date', '-created_at')

        serializer = DiaryEntrySerializer(entries, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        title = (request.data.get('title') or '').strip()
        note = (request.data.get('note') or '').strip()
        entry_type = (request.data.get('entry_type') or 'work').strip().lower()
        entry_date_value = request.data.get('entry_date')
        hours_value = request.data.get('hours', 0)
        tags_value = request.data.get('tags', [])

        if not title:
            return Response({'error': 'Title is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not note:
            return Response({'error': 'Note is required'}, status=status.HTTP_400_BAD_REQUEST)

        valid_types = {choice[0] for choice in DiaryEntry.ENTRY_TYPE_CHOICES}
        if entry_type not in valid_types:
            entry_type = 'work'

        if isinstance(tags_value, str):
            parsed_tags = None
            if tags_value.strip().startswith('['):
                try:
                    loaded = json.loads(tags_value)
                    if isinstance(loaded, list):
                        parsed_tags = loaded
                except Exception:
                    parsed_tags = None
            if parsed_tags is None:
                parsed_tags = [part.strip() for part in tags_value.split(',') if part.strip()]
            tags = parsed_tags
        elif isinstance(tags_value, list):
            tags = tags_value
        else:
            tags = []

        normalized_tags = []
        for item in tags:
            text = str(item).strip()
            if text and text not in normalized_tags:
                normalized_tags.append(text)

        try:
            hours = float(hours_value)
            if hours < 0:
                hours = 0
        except (TypeError, ValueError):
            hours = 0

        if entry_date_value:
            try:
                entry_date = timezone.datetime.fromisoformat(str(entry_date_value)).date()
            except Exception:
                try:
                    entry_date = timezone.datetime.strptime(str(entry_date_value), '%Y-%m-%d').date()
                except Exception:
                    entry_date = timezone.localdate()
        else:
            entry_date = timezone.localdate()

        files = request.FILES.getlist('attachments')

        with transaction.atomic():
            entry = DiaryEntry.objects.create(
                user=request.user,
                title=title,
                note=note,
                tags=normalized_tags,
                hours=hours,
                entry_type=entry_type,
                entry_date=entry_date,
            )

            for file in files:
                DiaryAttachment.objects.create(
                    entry=entry,
                    file=file,
                    original_name=file.name,
                    mime_type=getattr(file, 'content_type', '') or '',
                    file_size=getattr(file, 'size', 0) or 0,
                )

        serializer = DiaryEntrySerializer(entry, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DiaryEntryDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def patch(self, request, pk):
        entry = get_object_or_404(DiaryEntry, pk=pk, user=request.user)

        title = request.data.get('title', entry.title)
        note = request.data.get('note', entry.note)
        entry_type = request.data.get('entry_type', entry.entry_type)
        entry_date_value = request.data.get('entry_date', entry.entry_date)
        hours_value = request.data.get('hours', entry.hours)
        tags_value = request.data.get('tags', entry.tags)

        title = (title or '').strip()
        note = (note or '').strip()
        entry_type = (entry_type or 'work').strip().lower()

        if not title:
            return Response({'error': 'Title is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not note:
            return Response({'error': 'Note is required'}, status=status.HTTP_400_BAD_REQUEST)

        valid_types = {choice[0] for choice in DiaryEntry.ENTRY_TYPE_CHOICES}
        if entry_type not in valid_types:
            entry_type = 'work'

        if isinstance(tags_value, str):
            parsed_tags = None
            if tags_value.strip().startswith('['):
                try:
                    loaded = json.loads(tags_value)
                    if isinstance(loaded, list):
                        parsed_tags = loaded
                except Exception:
                    parsed_tags = None
            if parsed_tags is None:
                parsed_tags = [part.strip() for part in tags_value.split(',') if part.strip()]
            tags = parsed_tags
        elif isinstance(tags_value, list):
            tags = tags_value
        else:
            tags = []

        normalized_tags = []
        for item in tags:
            text = str(item).strip()
            if text and text not in normalized_tags:
                normalized_tags.append(text)

        try:
            hours = float(hours_value)
            if hours < 0:
                hours = 0
        except (TypeError, ValueError):
            hours = 0

        if entry_date_value:
            if hasattr(entry_date_value, 'isoformat'):
                entry_date = entry_date_value
            else:
                try:
                    entry_date = timezone.datetime.fromisoformat(str(entry_date_value)).date()
                except Exception:
                    try:
                        entry_date = timezone.datetime.strptime(str(entry_date_value), '%Y-%m-%d').date()
                    except Exception:
                        entry_date = entry.entry_date
        else:
            entry_date = entry.entry_date

        entry.title = title
        entry.note = note
        entry.tags = normalized_tags
        entry.hours = hours
        entry.entry_type = entry_type
        entry.entry_date = entry_date
        entry.save()

        for file in request.FILES.getlist('attachments'):
            DiaryAttachment.objects.create(
                entry=entry,
                file=file,
                original_name=file.name,
                mime_type=getattr(file, 'content_type', '') or '',
                file_size=getattr(file, 'size', 0) or 0,
            )

        serializer = DiaryEntrySerializer(entry, context={'request': request})
        return Response(serializer.data)

    def delete(self, request, pk):
        entry = get_object_or_404(DiaryEntry, pk=pk, user=request.user)
        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class HRDiaryLogbookListView(APIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
    }

    def get(self, request):
        org_id = _get_org_id_or_none(request)
        if not org_id:
            return Response({
                'summary': {
                    'total_entries': 0,
                    'total_hours': 0,
                    'member_count': 0,
                },
                'members': [],
                'entries': [],
            })

        members_qs = User.objects.filter(
            Q(team_settings__organization__organization_id=org_id)
            | Q(shop_credentials__organization_id=org_id)
        ).distinct()

        user_id = (request.query_params.get('user_id') or '').strip()
        if user_id and user_id.lower() != 'all':
            try:
                selected_user_id = int(user_id)
            except (TypeError, ValueError):
                selected_user_id = None
            if selected_user_id:
                members_qs = members_qs.filter(id=selected_user_id)

        entries = DiaryEntry.objects.filter(user__in=members_qs).select_related('user').prefetch_related('attachments')

        query = (request.query_params.get('q') or '').strip()
        if query:
            entries = entries.filter(
                Q(title__icontains=query)
                | Q(note__icontains=query)
                | Q(user__first_name__icontains=query)
                | Q(user__last_name__icontains=query)
                | Q(user__username__icontains=query)
                | Q(user__email__icontains=query)
            )

        start_date = (request.query_params.get('start_date') or '').strip()
        end_date = (request.query_params.get('end_date') or '').strip()
        if start_date:
            entries = entries.filter(entry_date__gte=start_date)
        if end_date:
            entries = entries.filter(entry_date__lte=end_date)

        order = (request.query_params.get('order') or 'newest').strip().lower()
        if order == 'oldest':
            entries = entries.order_by('entry_date', 'created_at')
        else:
            entries = entries.order_by('-entry_date', '-created_at')

        entry_count = entries.count()
        total_hours = float(entries.aggregate(total=Sum('hours')).get('total') or 0)
        active_member_count = entries.values('user_id').distinct().count()

        members = []
        for member in members_qs.order_by('first_name', 'username').distinct():
            display_name = member.get_full_name() or member.first_name or member.username or member.email or ''
            members.append({
                'id': member.id,
                'name': display_name,
                'email': member.email,
            })

        serializer = HRDiaryEntrySerializer(entries, many=True, context={'request': request})

        return Response({
            'summary': {
                'total_entries': entry_count,
                'total_hours': total_hours,
                'member_count': active_member_count,
            },
            'members': members,
            'entries': serializer.data,
        })
