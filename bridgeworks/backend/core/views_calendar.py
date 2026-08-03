"""
Google Calendar & Meet Integration
===================================
Endpoints:
  GET  /api/calendar/status/         – is Calendar connected for this user?
  GET  /api/calendar/auth/           – get redirect URL to connect Calendar
  GET  /api/calendar/callback/       – OAuth2 callback (stores tokens)
  POST /api/calendar/schedule/       – create a Calendar event + Meet link
                                       + fan-out team-chat message
  GET  /api/calendar/events/         – list upcoming Calendar events

Uses the same Google client_id / client_secret stored in allauth's SocialApp.
Tokens are persisted in GoogleCalendarAuth (separate from the login token).
"""

import json
import datetime
import hashlib
import time
import httplib2
import typing
from django.db.models import Q
from django.core.cache import cache

from django.conf import settings as django_settings
from django.utils import timezone
from django.shortcuts import redirect
from django.contrib.auth import get_user_model

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.tasks.chat_broadcast import broadcast_new_message_task
from core.services.notifications import push_unified_notification
from .models import GoogleCalendarAuth, ChatMessage, ChatMessageRecipient, TeamMemberSettings, UnifiedNotification
from .views_chat import _get_org_id, _org_members, _broadcast_new_message, CsrfExemptSessionAuthentication
from .views_auth import _sync_gcal_token

User = get_user_model()


# ── CONSTANTS ────────────────────────────────────────────────────────────────

SCOPES = django_settings.GOOGLE_CALENDAR_SCOPES
REDIRECT_URI = django_settings.GOOGLE_CALENDAR_REDIRECT_URI
CALENDAR_EVENTS_CACHE_TTL_SECONDS = 120
GOOGLE_CALENDAR_HTTP_TIMEOUT_SECONDS = 15


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _get_google_client_config():
    """Load client_id and client_secret from allauth's SocialApp."""
    from allauth.socialaccount.models import SocialApp
    try:
        app = SocialApp.objects.get(provider='google')
        return {
            "web": {
                "client_id": app.client_id,
                "client_secret": app.secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [REDIRECT_URI],
            }
        }
    except SocialApp.DoesNotExist:
        return None


def _calendar_cache_revision_key(org_id, user_id):
    return f'calendar:events:rev:org:{org_id}:user:{user_id}'


def _calendar_cache_key(org_id, user_id, time_min, time_max):
    revision_key = _calendar_cache_revision_key(org_id, user_id)
    revision = cache.get(revision_key, 0) or 0
    digest = hashlib.sha1(f'{time_min}|{time_max}'.encode('utf-8')).hexdigest()
    return f'calendar:events:org:{org_id}:user:{user_id}:rev:{revision}:{digest}'


def _invalidate_calendar_cache(org_id, user_id):
    if not org_id or not user_id:
        return
    revision_key = _calendar_cache_revision_key(org_id, user_id)
    if cache.get(revision_key) is None:
        cache.set(revision_key, 1, None)
        return
    try:
        cache.incr(revision_key)
    except Exception:
        current = cache.get(revision_key, 0) or 0
        cache.set(revision_key, int(current) + 1, None)


def _invalidate_calendar_cache_for_users(org_id, user_ids):
    if not org_id or not user_ids:
        return
    seen = set()
    for user_id in user_ids:
        try:
            normalized_id = int(user_id)
        except (TypeError, ValueError):
            continue
        if normalized_id in seen:
            continue
        seen.add(normalized_id)
        _invalidate_calendar_cache(org_id, normalized_id)


class _TimeoutRefreshRequest:
    """Use a shorter timeout when refreshing Google OAuth tokens."""

    def __init__(self, timeout=GOOGLE_CALENDAR_HTTP_TIMEOUT_SECONDS):
        self._request = Request()
        self._timeout = timeout

    def __call__(self, url, method='GET', body=None, headers=None, timeout=None, **kwargs):
        effective_timeout = self._timeout if timeout is None else timeout
        return self._request(
            url=url,
            method=method,
            body=body,
            headers=headers,
            timeout=effective_timeout,
            **kwargs,
        )


def _build_calendar_service(creds):
    """
    Build a Google Calendar client with a bounded network timeout while using
    modern google.oauth2 credentials.
    """
    http = httplib2.Http(timeout=GOOGLE_CALENDAR_HTTP_TIMEOUT_SECONDS)
    authed_http = AuthorizedHttp(creds, http=http)
    return build('calendar', 'v3', http=authed_http, cache_discovery=False)


def _get_credentials(user):
    """
    Return valid google.oauth2.credentials.Credentials for this user,
    refreshing the access token if it's expired. Returns None if the user
    hasn't connected Calendar yet.
    """
    try:
        gcal = user.gcal_auth
    except GoogleCalendarAuth.DoesNotExist:
        return None

    client_config = _get_google_client_config()
    if not client_config:
        return None

    creds = Credentials(
        token=gcal.access_token,
        refresh_token=gcal.refresh_token or None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_config["web"]["client_id"],
        client_secret=client_config["web"]["client_secret"],
        scopes=SCOPES,
    )

    # Force-set an expiry so google-auth knows whether to refresh
    if gcal.token_expiry:
        import pytz
        exp = gcal.token_expiry
        if exp.tzinfo is None:
            exp = pytz.utc.localize(exp)
        creds.expiry = exp.replace(tzinfo=None)  # google-auth wants naïve UTC

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(_TimeoutRefreshRequest())
            # Persist refreshed token
            gcal.access_token = creds.token
            if creds.expiry:
                gcal.token_expiry = timezone.make_aware(
                    creds.expiry, datetime.timezone.utc
                ) if creds.expiry.tzinfo is None else creds.expiry
            gcal.save(update_fields=['access_token', 'token_expiry'])
        except Exception:
            return None

    return creds


def _fan_out_chat_message(sender, org_id, recipient_ids=None, **kwargs):
    """
    Create a ChatMessage and fan it out.
    If recipient_ids is provided, only those users receive it.
    Otherwise, all org members (except sender) receive it.
    """
    msg = ChatMessage.objects.create(sender=sender, **kwargs)
    if recipient_ids:
        members = User.objects.filter(id__in=recipient_ids).exclude(id=sender.id)
    else:
        members = _org_members(org_id).exclude(id=sender.id)
    ChatMessageRecipient.objects.bulk_create(
        [ChatMessageRecipient(message=msg, recipient=m) for m in members],
        ignore_conflicts=True,
    )
    return msg


def _parse_google_iso(value):
    if not value:
        return None
    try:
        cleaned = value.replace('Z', '+00:00') if isinstance(value, str) else value
        return datetime.datetime.fromisoformat(cleaned)
    except Exception:
        return None


def _parse_reminders(payload):
    mode = (payload.get('notification_before') or payload.get('reminder_mode') or '').strip().lower()
    custom_minutes = payload.get('custom_notification_minutes') or payload.get('custom_minutes')
    channels = payload.get('reminder_channels') or payload.get('channels') or ['push']
    if not isinstance(channels, list):
        channels = ['push']

    reminder_minutes = None
    if isinstance(mode, str):
        if mode in ('10m', '10min', '10_min', '10 minutes'):
            reminder_minutes = 10
        elif mode in ('1h', '1hr', '1 hour', '60m', '60min'):
            reminder_minutes = 60
        elif mode in ('custom',):
            try:
                reminder_minutes = max(1, int(custom_minutes))
            except (TypeError, ValueError):
                reminder_minutes = None

    if reminder_minutes is None:
        reminder_minutes = 10

    google_methods = []
    if any((c or '').lower() == 'email' for c in channels):
        google_methods.append('email')
    if any((c or '').lower() in ('push', 'popup') for c in channels):
        google_methods.append('popup')
    if not google_methods:
        google_methods = ['popup']

    return {
        'useDefault': False,
        'overrides': [{'method': method, 'minutes': reminder_minutes} for method in google_methods],
    }


def _serialize_google_event(ev):
    start = ev.get('start', {})
    end = ev.get('end', {})
    meet_link = ''
    for ep in ev.get('conferenceData', {}).get('entryPoints', []):
        if ep.get('entryPointType') == 'video':
            meet_link = ep.get('uri', '')
            break

    event_type = (
        ev.get('extendedProperties', {})
        .get('private', {})
        .get('bridgeworks_type')
    ) or 'meeting'

    return {
        'id': ev.get('id'),
        'title': ev.get('summary', '(No title)'),
        'start': start.get('dateTime') or start.get('date'),
        'end': end.get('dateTime') or end.get('date'),
        'meet_link': meet_link,
        'html_link': ev.get('htmlLink', ''),
        'description': ev.get('description', ''),
        'attendees': [
            a.get('email') for a in ev.get('attendees', [])
            if not a.get('self')
        ],
        'event_type': event_type,
        'source': 'google',
        'status': ev.get('status', 'confirmed'),
    }


def _build_google_patch_body(payload):
    title = payload.get('title')
    description = payload.get('description')
    start = payload.get('start')
    end = payload.get('end')
    timezone_name = payload.get('timezone', 'Asia/Kolkata')
    event_type = (payload.get('event_type') or '').strip().lower() or None

    body = {}
    if title is not None:
        body['summary'] = str(title).strip() or '(No title)'
    if description is not None:
        body['description'] = str(description).strip()

    if start and end:
        start_dt = _parse_google_iso(start)
        end_dt = _parse_google_iso(end)
        if start_dt and end_dt:
            body['start'] = {'dateTime': start_dt.isoformat(), 'timeZone': timezone_name}
            body['end'] = {'dateTime': end_dt.isoformat(), 'timeZone': timezone_name}
        else:
            body['start'] = {'date': start}
            body['end'] = {'date': end}

    if event_type:
        body['extendedProperties'] = {
            'private': {
                'bridgeworks_type': event_type
            }
        }

    if any(k in payload for k in ('notification_before', 'reminder_mode', 'custom_notification_minutes', 'custom_minutes', 'reminder_channels', 'channels')):
        body['reminders'] = _parse_reminders(payload)

    return body


# ── VIEWS ─────────────────────────────────────────────────────────────────────

class CalendarAuthStatusView(APIView):
    """GET /api/calendar/status/ → { connected: bool }"""
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Always try to sync – handles first login AND token rotation
        _sync_gcal_token(request.user)

        connected = GoogleCalendarAuth.objects.filter(user=request.user).exists()
        return Response({'connected': connected})


class CalendarAuthInitView(APIView):
    """
    GET /api/calendar/auth/
    Returns the Google OAuth2 redirect URL that the frontend should open.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        client_config = _get_google_client_config()
        if not client_config:
            return Response({'error': 'Google OAuth app not configured.'}, status=500)

        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI,
        )
        auth_url, state = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            include_granted_scopes='true',
            state=str(request.user.id),  # embed user_id so callback knows who
            # Disable PKCE: we don't persist code_verifier between requests
            # (server-side redirect flow — PKCE not needed here)
            code_challenge=None,
            code_challenge_method=None,
        )
        return Response({'auth_url': auth_url})


class CalendarAuthCallbackView(APIView):
    """
    GET /api/calendar/callback/?code=...&state=<user_id>
    Exchanges the code for tokens and stores them.
    Redirects back to the frontend.

    Also handles Gmail OAuth flows when state='gmail_<user_id>'.
    This lets Gmail reuse the already-registered redirect URI.
    """
    # No auth required – this is the callback from Google
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        code  = request.query_params.get('code')
        state = request.query_params.get('state', '')  # user_id OR 'gmail_<user_id>'
        error = request.query_params.get('error')

        frontend_url = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:5173')

        # ── Detect Gmail flow ─────────────────────────────────────────────
        is_gmail = isinstance(state, str) and state.startswith('gmail_')
        if is_gmail:
            if error or not code:
                return redirect(f'{frontend_url}/?gmail_auth=error')
            return self._handle_gmail(request, code, state, frontend_url)

        # ── Calendar flow (original logic) ────────────────────────────────
        if error or not code:
            return redirect(f'{frontend_url}/?calendar_auth=error')

        try:
            user_id = int(state)
            user = User.objects.get(id=user_id)
        except (TypeError, ValueError, User.DoesNotExist):
            return redirect(f'{frontend_url}/?calendar_auth=error')

        client_config = _get_google_client_config()
        if not client_config:
            return redirect(f'{frontend_url}/?calendar_auth=error')

        try:
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=REDIRECT_URI,
                state=state,
            )
            flow.fetch_token(code=code)
            creds = flow.credentials

            expiry = None
            if creds.expiry:
                expiry = timezone.make_aware(creds.expiry, datetime.timezone.utc) \
                    if creds.expiry.tzinfo is None else creds.expiry

            GoogleCalendarAuth.objects.update_or_create(
                user=user,
                defaults={
                    'access_token': creds.token,
                    'refresh_token': creds.refresh_token or '',
                    'token_expiry': expiry,
                    'scopes': ' '.join(creds.scopes or SCOPES),
                },
            )
        except Exception as exc:
            print(f'[CalendarCallback] error: {exc}')
            return redirect(f'{frontend_url}/?calendar_auth=error')

        return redirect(f'{frontend_url}/?calendar_auth=success')

    def _handle_gmail(self, request, code, state, frontend_url):
        """Handle Gmail-specific OAuth callback (state='gmail_<user_id>').

        NOTE: We intentionally do NOT pass 'state' to Flow.from_client_config.
        Passing state to the Flow enables google-auth-oauthlib CSRF validation,
        which requires the full authorization_response URL — not just the code.
        We already use the 'gmail_' prefix as our own CSRF guard.
        """
        import urllib.parse
        from core.models import GmailAuth
        from core.views_gmail import GMAIL_SCOPES, _build_gmail_service

        def _error(reason=''):
            params = urllib.parse.urlencode({'gmail_auth': 'error', 'reason': reason})
            return redirect(f'{frontend_url}/?{params}')

        try:
            user_id = int(state.split('_', 1)[1])
            user    = User.objects.get(id=user_id)
        except (IndexError, ValueError, User.DoesNotExist) as exc:
            print(f'[GmailCallback] bad state: {exc}')
            return _error('invalid_state')

        client_config = _get_google_client_config()
        if not client_config:
            return _error('no_oauth_app')

        try:
            flow = Flow.from_client_config(
                client_config,
                scopes=GMAIL_SCOPES,
                redirect_uri=REDIRECT_URI,   # same URI as Calendar (already registered)
                # state= deliberately omitted — see docstring
            )
            flow.fetch_token(code=code)
            creds = flow.credentials

            expiry = None
            if creds.expiry:
                expiry = timezone.make_aware(creds.expiry, datetime.timezone.utc) \
                    if creds.expiry.tzinfo is None else creds.expiry

            # Fetch connected Gmail address (best-effort)
            gmail_email = ''
            try:
                svc         = _build_gmail_service(creds)
                profile     = svc.users().getProfile(userId='me').execute()
                gmail_email = profile.get('emailAddress', '')
            except Exception as profile_exc:
                print(f'[GmailCallback] profile fetch skipped: {profile_exc}')

            GmailAuth.objects.update_or_create(
                user=user,
                defaults={
                    'access_token':  creds.token,
                    'refresh_token': creds.refresh_token or '',
                    'token_expiry':  expiry,
                    'scopes':        ' '.join(creds.scopes or GMAIL_SCOPES),
                    'gmail_email':   gmail_email,
                },
            )
        except Exception as exc:
            import traceback
            traceback.print_exc()
            safe_reason = str(exc)[:200].replace('\n', ' ')
            print(f'[GmailCallback] token exchange error: {safe_reason}')
            return _error(urllib.parse.quote(safe_reason))

        return redirect(f'{frontend_url}/?gmail_auth=success')


class ScheduleMeetingView(APIView):
    """
    POST /api/calendar/schedule/
    Body:
      {
        "title": "Sprint Planning",
        "start": "2026-03-12T14:00:00",   // ISO, local time
        "end":   "2026-03-12T15:00:00",   // ISO, local time (optional)
        "timezone": "Asia/Kolkata",
        "tagged_user_ids": [3, 7],         // org members to invite
        "description": "..."              // optional
      }
    Response: { message_id, meet_link, event_id, event_link }
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({'error': 'No organisation found.'}, status=400)

        creds = _get_credentials(request.user)
        if not creds:
            return Response(
                {'error': 'Google Calendar not connected.', 'needs_auth': True},
                status=403,
            )

        title = (request.data.get('title') or 'Team Meeting').strip()
        start_str = request.data.get('start')
        end_str = request.data.get('end')
        tz = request.data.get('timezone', 'Asia/Kolkata')
        raw_tagged_ids = request.data.get('tagged_user_ids', [])
        if not isinstance(raw_tagged_ids, list):
            raw_tagged_ids = [raw_tagged_ids] if raw_tagged_ids not in (None, '', []) else []
        tagged_ids = []
        for raw_id in raw_tagged_ids:
            try:
                tagged_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue
        tagged_ids = sorted(set(tagged_ids))
        description = (request.data.get('description') or '').strip()
        reminders = _parse_reminders(request.data)

        if not start_str:
            return Response({'error': 'start datetime is required.'}, status=400)

        # Derive end = start + 60 min if not provided
        try:
            start_dt = datetime.datetime.fromisoformat(start_str)
            end_dt = (
                datetime.datetime.fromisoformat(end_str)
                if end_str
                else start_dt + datetime.timedelta(hours=1)
            )
        except ValueError:
            return Response({'error': 'Invalid datetime format. Use ISO 8601.'}, status=400)

        # Build attendees list
        attendee_emails = []
        tagged_names = []
        tagged_member_ids = []
        if tagged_ids:
            members = User.objects.filter(
                id__in=tagged_ids,
                team_settings__organization__organization_id=org_id,
            )
            for m in typing.cast(typing.Any, members):
                tagged_member_ids.append(m.pk)
                if m.email:
                    attendee_emails.append({'email': m.email})
                name = m.get_full_name().strip() or m.username
                tagged_names.append(name)

        # Create Google Calendar event with conferenceData (→ auto Meet link)
        try:
            service = _build_calendar_service(creds)
            event_body = {
                'summary': title,
                'description': description,
                'start': {'dateTime': start_dt.isoformat(), 'timeZone': tz},
                'end':   {'dateTime': end_dt.isoformat(),   'timeZone': tz},
                'attendees': attendee_emails,
                'reminders': reminders,
                'extendedProperties': {
                    'private': {
                        'bridgeworks_type': 'meeting'
                    }
                },
                'conferenceData': {
                    'createRequest': {
                        'requestId': f"bridgeworks-{request.user.id}-{int(datetime.datetime.now().timestamp())}",
                        'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                    }
                },
            }
            created_event = service.events().insert(
                calendarId='primary',
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates='all',
            ).execute()
        except HttpError as e:
            return Response({'error': f'Google Calendar error: {e}'}, status=502)

        meet_link = ''
        conf = created_event.get('conferenceData', {})
        for ep in conf.get('entryPoints', []):
            if ep.get('entryPointType') == 'video':
                meet_link = ep.get('uri', '')
                break

        event_link = created_event.get('htmlLink', '')
        event_id = created_event.get('id', '')

        formatted_start = start_dt.strftime('%a, %d %b %Y · %I:%M %p')
        formatted_end = end_dt.strftime('%I:%M %p')
        timezone_label = tz or 'Local time'
        join_reference = meet_link or event_link or 'Not available'
        meeting_purpose = description or 'No description provided.'
        content_lines = [
            '📅 Meeting Scheduled',
            f'Subject: {title}',
            f'Date & Time: {formatted_start} - {formatted_end} ({timezone_label})',
            f'Join: {join_reference}',
            f'Description: {meeting_purpose}',
        ]
        message_content = '\n'.join(content_lines)

        # Fan-out as a team chat message so everyone sees it in the Task Manager
        tagged_names_str = ', '.join(tagged_names) if tagged_names else 'All team'
        chat_msg = _fan_out_chat_message(
            sender=request.user,
            org_id=org_id,
            recipient_ids=tagged_member_ids if tagged_member_ids else None,  # Only notify tagged members
            content=message_content,
            is_event=True,
            event_title=title,
            meet_link=meet_link,
            event_tagged_names=tagged_names_str,
        )

        response_ready_epoch_ms = int(time.time() * 1000)
        try:
            broadcast_new_message_task.delay(org_id, chat_msg.pk, response_ready_epoch_ms)
        except Exception:
            _broadcast_new_message(org_id, chat_msg, queue_delay_ms=0.0)

        recipient_user_ids = list(
            ChatMessageRecipient.objects.filter(message=chat_msg).values_list('recipient_id', flat=True)
        )
        _invalidate_calendar_cache_for_users(org_id, [request.user.id, *recipient_user_ids])

        # ── Instant in-app notifications to every tagged member ───────────────
        if tagged_member_ids:
            actor_name = request.user.get_full_name().strip() or request.user.username
            formatted_time = f"{formatted_start} – {formatted_end} ({tz})"
            tagged_members_qs = User.objects.filter(id__in=tagged_member_ids)
            for member in tagged_members_qs:
                try:
                    push_unified_notification(
                        recipient=member,
                        actor=request.user,
                        module=UnifiedNotification.MODULE_MEETINGS,
                        action='meeting_scheduled',
                        title='Meeting Scheduled',
                        message=f"{actor_name} scheduled a meeting: {title}",
                        preview=formatted_time,
                        entity_type='calendar_event',
                        entity_id=event_id,
                        deep_link={
                            'page': '/mydesk/meetings',
                            'section': 'my-meetings',
                            'eventId': event_id,
                        },
                        metadata={
                            'meet_link': meet_link,
                            'event_link': event_link,
                            'start': start_dt.isoformat(),
                            'end': end_dt.isoformat(),
                        },
                        sound_category='general',
                    )
                except Exception:
                    pass  # Never let notification failures break the meeting creation

        return Response({
            'message_id': chat_msg.pk,
            'meet_link': meet_link,
            'event_id': event_id,
            'event_link': event_link,
            'start': start_dt.isoformat(),
            'end': end_dt.isoformat(),
        }, status=201)


class CalendarEventsView(APIView):
    """
        GET /api/calendar/events/?days=7
        GET /api/calendar/events/?start=2026-03-01&end=2026-03-31
        Returns events from the user's primary calendar for either:
            - explicit [start, end] date range (inclusive), or
            - next N days (default 7) when start/end are not provided.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        creds = _get_credentials(request.user)
        if not creds:
            return Response(
                {'error': 'Google Calendar not connected.', 'needs_auth': True},
                status=403,
            )

        start_param = request.query_params.get('start')
        end_param = request.query_params.get('end')

        start_date = None
        end_date = None

        if start_param and end_param:
            try:
                start_date = datetime.date.fromisoformat(start_param)
                end_date = datetime.date.fromisoformat(end_param)
            except ValueError:
                return Response({'error': 'Invalid start/end. Use YYYY-MM-DD.'}, status=400)

            if end_date < start_date:
                return Response({'error': 'end must be on or after start.'}, status=400)

            max_span_days = 180
            if (end_date - start_date).days > max_span_days:
                return Response({'error': f'Date range too large (max {max_span_days + 1} days).'}, status=400)

            time_min = datetime.datetime.combine(start_date, datetime.time.min).isoformat() + 'Z'
            time_max = datetime.datetime.combine(end_date + datetime.timedelta(days=1), datetime.time.min).isoformat() + 'Z'
        else:
            days = min(int(request.query_params.get('days', 7)), 30)
            now = datetime.datetime.utcnow()
            future = now + datetime.timedelta(days=days)
            time_min = now.isoformat() + 'Z'
            time_max = future.isoformat() + 'Z'

        cache_key = None
        if org_id:
            cache_key = _calendar_cache_key(org_id, request.user.id, time_min, time_max)
            cached_events = cache.get(cache_key)
            if cached_events is not None:
                return Response(cached_events)

        try:
            service = _build_calendar_service(creds)
            result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime',
                maxResults=50,
            ).execute()
        except HttpError as e:
            return Response({'error': f'Google Calendar error: {e}'}, status=502)
        except Exception as e:
            err = str(e).lower()
            if 'timeout' in err or 'timed out' in err:
                return Response({'error': 'Google Calendar request timed out. Please try again.'}, status=504)
            return Response({'error': 'Failed to fetch calendar events.'}, status=502)

        events = []
        for ev in result.get('items', []):
            events.append(_serialize_google_event(ev))

        if org_id:
            task_qs = ChatMessage.objects.filter(
                is_task=True,
                sender__team_settings__organization__organization_id=org_id,
                task_status__in=['pending', 'in_progress'],
            ).filter(
                Q(sender=request.user) |
                Q(task_assignee=request.user) |
                Q(recipient_entries__recipient=request.user)
            ).distinct()

            if start_param and end_param:
                task_qs = task_qs.filter(
                    task_due_date__gte=start_date,
                    task_due_date__lte=end_date,
                )
            else:
                start_date_dyn = datetime.date.fromisoformat(time_min[:10])
                end_date_dyn = datetime.date.fromisoformat(time_max[:10])
                task_qs = task_qs.filter(
                    task_due_date__gte=start_date_dyn,
                    task_due_date__lte=end_date_dyn,
                )

            for task in task_qs:
                if not task.task_due_date:
                    continue
                task_start = task.task_due_date.isoformat()
                task_end = (task.task_due_date + datetime.timedelta(days=1)).isoformat()
                inferred_type = 'deadline' if task.task_priority in {'high', 'critical'} else 'task'
                events.append({
                    'id': f'task-{task.pk}',
                    'title': task.task_title or task.content or 'Task',
                    'start': task_start,
                    'end': task_end,
                    'meet_link': '',
                    'html_link': '',
                    'description': task.task_description or task.content or '',
                    'attendees': [task.task_assignee.email] if task.task_assignee and task.task_assignee.email else [],
                    'event_type': inferred_type,
                    'source': 'task',
                    'task_priority': task.task_priority,
                    'task_status': task.task_status,
                    'task_assignee_id': task.task_assignee.pk if task.task_assignee else None,
                    'task_assignee_name': task.task_assignee.get_full_name() or task.task_assignee.username if task.task_assignee else None,
                })

        events.sort(key=lambda item: str(item.get('start') or ''))

        if cache_key:
            cache.set(cache_key, events, CALENDAR_EVENTS_CACHE_TTL_SECONDS)

        return Response(events)

    def post(self, request):
        org_id = _get_org_id(request)
        creds = _get_credentials(request.user)
        if not creds:
            return Response(
                {'error': 'Google Calendar not connected.', 'needs_auth': True},
                status=403,
            )

        title = (request.data.get('title') or '').strip() or '(No title)'
        event_type = (request.data.get('event_type') or 'meeting').strip().lower()
        description = (request.data.get('description') or '').strip()
        tz = request.data.get('timezone', 'Asia/Kolkata')
        start_str = request.data.get('start')
        end_str = request.data.get('end')
        if not start_str:
            return Response({'error': 'start is required.'}, status=400)

        if not end_str:
            start_dt = _parse_google_iso(start_str)
            if start_dt:
                end_str = (start_dt + datetime.timedelta(hours=1)).isoformat()
            else:
                end_str = (datetime.date.fromisoformat(start_str) + datetime.timedelta(days=1)).isoformat()

        attendees = request.data.get('attendees') or []
        tagged_ids = request.data.get('tagged_user_ids') or []
        if tagged_ids and not attendees:
            members = User.objects.filter(id__in=tagged_ids)
            attendees = [{'email': m.email} for m in members if m.email]  # type: ignore
        elif isinstance(attendees, list):
            attendees = [
                {'email': value.get('email')} if isinstance(value, dict) else {'email': str(value)}
                for value in attendees if value
            ]
        else:
            attendees = []

        body = {
            'summary': title,
            'description': description,
            'attendees': attendees,
            'extendedProperties': {
                'private': {
                    'bridgeworks_type': event_type,
                }
            },
            'reminders': _parse_reminders(request.data),
        }

        start_dt = _parse_google_iso(start_str)
        end_dt = _parse_google_iso(end_str)
        if start_dt and end_dt:
            body['start'] = {'dateTime': start_dt.isoformat(), 'timeZone': tz}
            body['end'] = {'dateTime': end_dt.isoformat(), 'timeZone': tz}
        else:
            body['start'] = {'date': start_str}
            body['end'] = {'date': end_str}

        if event_type == 'meeting':
            body['conferenceData'] = {
                'createRequest': {
                    'requestId': f"bridgeworks-{request.user.id}-{int(datetime.datetime.now().timestamp())}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                }
            }

        try:
            service = _build_calendar_service(creds)
            created_event = service.events().insert(
                calendarId='primary',
                body=body,
                conferenceDataVersion=1 if event_type == 'meeting' else 0,
                sendUpdates='all',
            ).execute()
        except HttpError as e:
            return Response({'error': f'Google Calendar error: {e}'}, status=502)

        _invalidate_calendar_cache(org_id, request.user.id)

        return Response(_serialize_google_event(created_event), status=201)


class CalendarEventDetailView(APIView):
    """
    PATCH /api/calendar/events/<event_id>/
    DELETE /api/calendar/events/<event_id>/
    Supports both Google events and internal task IDs in format task-<id>.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, event_id):
        org_id = _get_org_id(request)
        if str(event_id).startswith('task-'):
            raw_id = str(event_id).split('task-', 1)[-1]
            try:
                task_id = int(raw_id)
            except ValueError:
                return Response({'error': 'Invalid task id.'}, status=400)

            task = ChatMessage.objects.filter(id=task_id, is_task=True).first()
            if not task:
                return Response({'error': 'Task not found.'}, status=404)

            new_title = request.data.get('title')
            new_description = request.data.get('description')
            new_priority = request.data.get('task_priority') or request.data.get('priority')
            new_start = request.data.get('start')
            assignee_provided = 'task_assignee_id' in request.data or 'assignee_id' in request.data
            new_assignee_id = request.data.get('task_assignee_id')
            if new_assignee_id is None:
                new_assignee_id = request.data.get('assignee_id')

            updated_fields = []
            if new_title is not None:
                task.task_title = str(new_title).strip()
                updated_fields.append('task_title')
            if new_description is not None:
                task.task_description = str(new_description).strip()
                updated_fields.append('task_description')
            if new_priority in ('low', 'medium', 'high', 'critical'):
                task.task_priority = new_priority
                updated_fields.append('task_priority')
            if new_start:
                try:
                    task.task_due_date = datetime.date.fromisoformat(str(new_start)[:10])
                    updated_fields.append('task_due_date')
                except ValueError:
                    return Response({'error': 'Invalid start date.'}, status=400)

            if assignee_provided:
                if new_assignee_id in (None, '', 'null'):
                    task.task_assignee = None
                    updated_fields.append('task_assignee')
                else:
                    try:
                        assignee_id_int = int(new_assignee_id)
                    except (TypeError, ValueError):
                        return Response({'error': 'Invalid assignee id.'}, status=400)

                    assignee = User.objects.filter(
                        id=assignee_id_int,
                        team_settings__organization__organization_id=org_id,
                    ).first()
                    if not assignee:
                        return Response({'error': 'Assignee not found in your organization.'}, status=400)
                    task.task_assignee = assignee
                    updated_fields.append('task_assignee')

            if updated_fields:
                task.save(update_fields=updated_fields)
                _invalidate_calendar_cache(org_id, request.user.id)

            return Response({
                'id': f'task-{task.pk}',
                'title': task.task_title or task.content or 'Task',
                'start': task.task_due_date.isoformat() if task.task_due_date else None,
                'end': (task.task_due_date + datetime.timedelta(days=1)).isoformat() if task.task_due_date else None,
                'description': task.task_description or task.content or '',
                'event_type': 'deadline' if task.task_priority in {'high', 'critical'} else 'task',
                'source': 'task',
                'task_priority': task.task_priority,
                'task_status': task.task_status,
                'task_assignee_id': task.task_assignee.pk if task.task_assignee else None,
                'task_assignee_name': (task.task_assignee.get_full_name() or task.task_assignee.username) if task.task_assignee else None,
            })

        creds = _get_credentials(request.user)
        if not creds:
            return Response(
                {'error': 'Google Calendar not connected.', 'needs_auth': True},
                status=403,
            )

        body = _build_google_patch_body(request.data)
        if not body:
            return Response({'error': 'No update fields provided.'}, status=400)

        try:
            service = _build_calendar_service(creds)
            updated = service.events().patch(
                calendarId='primary',
                eventId=event_id,
                body=body,
                sendUpdates='all',
                conferenceDataVersion=1,
            ).execute()
        except HttpError as e:
            return Response({'error': f'Google Calendar error: {e}'}, status=502)

        _invalidate_calendar_cache(org_id, request.user.id)

        return Response(_serialize_google_event(updated))

    def delete(self, request, event_id):
        org_id = _get_org_id(request)
        if str(event_id).startswith('task-'):
            raw_id = str(event_id).split('task-', 1)[-1]
            try:
                task_id = int(raw_id)
            except ValueError:
                return Response({'error': 'Invalid task id.'}, status=400)

            task = ChatMessage.objects.filter(id=task_id, is_task=True).first()
            if not task:
                return Response({'error': 'Task not found.'}, status=404)
            task.task_status = 'completed'
            task.save(update_fields=['task_status'])
            _invalidate_calendar_cache(org_id, request.user.id)
            return Response(status=204)

        creds = _get_credentials(request.user)
        if not creds:
            return Response(
                {'error': 'Google Calendar not connected.', 'needs_auth': True},
                status=403,
            )

        try:
            service = _build_calendar_service(creds)
            service.events().delete(calendarId='primary', eventId=event_id, sendUpdates='all').execute()
        except HttpError as e:
            return Response({'error': f'Google Calendar error: {e}'}, status=502)

        _invalidate_calendar_cache(org_id, request.user.id)

        return Response(status=204)


class CalendarSyncView(APIView):
    """
    POST /api/calendar/sync/
    Pulls latest Google events for a date range. This provides an explicit sync trigger.
    """
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        creds = _get_credentials(request.user)
        if not creds:
            return Response(
                {'error': 'Google Calendar not connected.', 'needs_auth': True},
                status=403,
            )
        return Response({'synced': True})
