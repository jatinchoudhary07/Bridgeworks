"""
Gmail Integration — Backend Proxy
==================================
All Gmail API calls are proxied through Django so OAuth tokens never leave the server.

Endpoints:
  GET  /api/emails/auth/status/              – is Gmail connected?
  GET  /api/emails/auth/initiate/            – get Google OAuth redirect URL
  GET  /api/emails/auth/callback/            – OAuth2 callback (stores tokens)
  POST /api/emails/auth/disconnect/          – revoke & delete token
  GET  /api/emails/                          – list emails (folder + pagination)
  GET  /api/emails/search/                   – search with Gmail query syntax
  GET  /api/emails/<id>/                     – fetch full email detail
  POST /api/emails/send/                     – send / reply
  POST /api/emails/modify/                   – add/remove labels (read, star, archive…)
  POST /api/emails/<id>/trash/               – move to trash
  GET  /api/emails/<id>/attachments/<att_id>/ – download attachment

Uses the same Google SocialApp client_id/secret as Calendar.
"""

import base64
import datetime
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders as email_encoders

import httplib2
import pytz

from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.utils import timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google_auth_httplib2 import AuthorizedHttp

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.models import GmailAuth
from core.views_chat import CsrfExemptSessionAuthentication

User = get_user_model()

# ── CONSTANTS ─────────────────────────────────────────────────────────────────

GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
]

# Reuse the Calendar redirect URI (already registered in Google Cloud Console).
# Gmail OAuth uses state='gmail_<user_id>' so the shared callback can distinguish.
GMAIL_REDIRECT_URI = getattr(
    django_settings,
    'GOOGLE_CALENDAR_REDIRECT_URI',
    'http://localhost:8000/api/calendar/callback/'
)

FOLDER_LABEL_MAP = {
    'INBOX':   'INBOX',
    'SENT':    'SENT',
    'STARRED': 'STARRED',
    'DRAFT':   'DRAFT',
    'TRASH':   'TRASH',
}

HTTP_TIMEOUT = 15



# ── HELPERS ───────────────────────────────────────────────────────────────────

def _google_client_config():
    from allauth.socialaccount.models import SocialApp
    try:
        app = SocialApp.objects.get(provider='google')
        return {
            "web": {
                "client_id":     app.client_id,
                "client_secret": app.secret,
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": [GMAIL_REDIRECT_URI],
            }
        }
    except SocialApp.DoesNotExist:
        return None


def _get_credentials(user):
    """Return valid Credentials, refreshing if expired. None if not connected."""
    try:
        gauth = user.gmail_auth
    except GmailAuth.DoesNotExist:
        return None

    cfg = _google_client_config()
    if not cfg:
        return None

    creds = Credentials(
        token=gauth.access_token,
        refresh_token=gauth.refresh_token or None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cfg["web"]["client_id"],
        client_secret=cfg["web"]["client_secret"],
        scopes=GMAIL_SCOPES,
    )

    if gauth.token_expiry:
        exp = gauth.token_expiry
        if exp.tzinfo is None:
            exp = pytz.utc.localize(exp)
        creds.expiry = exp.replace(tzinfo=None)

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            gauth.access_token = creds.token
            if creds.expiry:
                gauth.token_expiry = timezone.make_aware(
                    creds.expiry, datetime.timezone.utc
                ) if creds.expiry.tzinfo is None else creds.expiry
            gauth.save(update_fields=['access_token', 'token_expiry'])
        except Exception:
            return None

    return creds


def _build_gmail_service(creds):
    http = httplib2.Http(timeout=HTTP_TIMEOUT)
    authed = AuthorizedHttp(creds, http=http)
    return build('gmail', 'v1', http=authed, cache_discovery=False)


def _decode_body(part):
    data = part.get('body', {}).get('data', '')
    if not data:
        return ''
    return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')


def _extract_parts(payload):
    """Recursively extract text/plain and text/html from MIME parts."""
    plain, html = '', ''
    mime = payload.get('mimeType', '')

    if mime == 'text/plain':
        plain = _decode_body(payload)
    elif mime == 'text/html':
        html = _decode_body(payload)
    elif 'parts' in payload:
        for part in payload['parts']:
            p, h = _extract_parts(part)
            plain = plain or p
            html = html or h

    return plain, html


def _parse_address(raw):
    """Return {name, email} from 'Name <email>' or just 'email'."""
    if not raw:
        return {'name': '', 'email': ''}
    m = re.match(r'^(.*?)\s*<([^>]+)>\s*$', raw.strip())
    if m:
        return {'name': m.group(1).strip(), 'email': m.group(2).strip()}
    return {'name': '', 'email': raw.strip()}


def _header(headers, name):
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return ''


def _serialize_summary(msg):
    """Compact email row for the list view."""
    headers = msg.get('payload', {}).get('headers', [])
    labels  = msg.get('labelIds', [])
    return {
        'id':        msg['id'],
        'threadId':  msg.get('threadId', ''),
        'from':      _parse_address(_header(headers, 'From')),
        'to':        [a.strip() for a in _header(headers, 'To').split(',') if a.strip()],
        'subject':   _header(headers, 'Subject') or '(no subject)',
        'date':      _header(headers, 'Date'),
        'snippet':   msg.get('snippet', ''),
        'labels':    labels,
        'isRead':    'UNREAD' not in labels,
        'isStarred': 'STARRED' in labels,
    }


def _serialize_detail(msg):
    """Full email detail including body and attachment metadata."""
    payload  = msg.get('payload', {})
    headers  = payload.get('headers', [])
    labels   = msg.get('labelIds', [])
    plain, html = _extract_parts(payload)

    attachments = []
    def _collect_attachments(parts):
        for part in parts:
            fn = part.get('filename', '')
            if fn:
                attachments.append({
                    'attachmentId': part['body'].get('attachmentId', ''),
                    'filename':     fn,
                    'mimeType':     part.get('mimeType', ''),
                    'size':         part['body'].get('size', 0),
                })
            if 'parts' in part:
                _collect_attachments(part['parts'])

    _collect_attachments(payload.get('parts', []))

    return {
        'id':        msg['id'],
        'threadId':  msg.get('threadId', ''),
        'from':      _parse_address(_header(headers, 'From')),
        'to':        [a.strip() for a in _header(headers, 'To').split(',') if a.strip()],
        'cc':        [a.strip() for a in _header(headers, 'Cc').split(',') if a.strip()],
        'subject':   _header(headers, 'Subject') or '(no subject)',
        'date':      _header(headers, 'Date'),
        'snippet':   msg.get('snippet', ''),
        'labels':    labels,
        'isRead':    'UNREAD' not in labels,
        'isStarred': 'STARRED' in labels,
        'bodyText':  plain,
        'bodyHtml':  html,
        'attachments': attachments,
    }


# ── VIEWS ─────────────────────────────────────────────────────────────────────

_AUTH = [JWTAuthentication, CsrfExemptSessionAuthentication]
_PERM = [IsAuthenticated]


class GmailAuthStatusView(APIView):
    """GET /api/emails/auth/status/"""
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def get(self, request):
        from core.views_auth import _sync_gmail_token
        _sync_gmail_token(request.user)

        creds = _get_credentials(request.user)
        if creds:
            try:
                ga = request.user.gmail_auth
                return Response({'connected': True, 'email': ga.gmail_email})
            except GmailAuth.DoesNotExist:
                pass
        return Response({'connected': False, 'email': None})


class GmailAuthInitiateView(APIView):
    """GET /api/emails/auth/initiate/ → {auth_url}

    Uses the SAME redirect_uri as Google Calendar (already registered in
    Google Cloud Console). The state is prefixed with 'gmail_' so the
    shared CalendarAuthCallbackView routes it to the Gmail handler.
    """
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def get(self, request):
        cfg = _google_client_config()
        if not cfg:
            return Response({'error': 'Google OAuth app not configured.'}, status=500)

        flow = Flow.from_client_config(cfg, scopes=GMAIL_SCOPES, redirect_uri=GMAIL_REDIRECT_URI)
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            state=f'gmail_{request.user.id}',   # 'gmail_' prefix flags this as Gmail
        )
        return Response({'auth_url': auth_url})


class GmailAuthCallbackView(APIView):
    """GET /api/emails/auth/callback/?code=...&state=<user_id>"""
    authentication_classes = []
    permission_classes     = []

    def get(self, request):
        code  = request.query_params.get('code')
        state = request.query_params.get('state')
        error = request.query_params.get('error')
        frontend = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:5173')

        if error or not code:
            return redirect(f'{frontend}/?gmail_auth=error')

        try:
            user_id = int(state)
            user    = User.objects.get(id=user_id)
        except (TypeError, ValueError, User.DoesNotExist):
            return redirect(f'{frontend}/?gmail_auth=error')

        cfg = _google_client_config()
        if not cfg:
            return redirect(f'{frontend}/?gmail_auth=error')

        try:
            flow = Flow.from_client_config(cfg, scopes=GMAIL_SCOPES,
                                           redirect_uri=GMAIL_REDIRECT_URI, state=state)
            flow.fetch_token(code=code)
            creds = flow.credentials

            expiry = None
            if creds.expiry:
                expiry = timezone.make_aware(creds.expiry, datetime.timezone.utc) \
                    if creds.expiry.tzinfo is None else creds.expiry

            # Fetch the connected email address
            gmail_email = ''
            try:
                svc = _build_gmail_service(creds)
                profile = svc.users().getProfile(userId='me').execute()
                gmail_email = profile.get('emailAddress', '')
            except Exception:
                pass

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
            print(f'[GmailCallback] error: {exc}')
            return redirect(f'{frontend}/?gmail_auth=error')

        return redirect(f'{frontend}/?gmail_auth=success')


class GmailDisconnectView(APIView):
    """POST /api/emails/auth/disconnect/"""
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def post(self, request):
        try:
            request.user.gmail_auth.delete()
        except GmailAuth.DoesNotExist:
            pass
        return Response({'disconnected': True})


class EmailListView(APIView):
    """GET /api/emails/?folder=INBOX&max_results=50&page_token=..."""
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def get(self, request):
        creds = _get_credentials(request.user)
        if not creds:
            return Response({'error': 'Gmail not connected.', 'needs_auth': True}, status=403)

        folder      = request.query_params.get('folder', 'INBOX').upper()
        max_results = min(int(request.query_params.get('max_results', 50)), 100)
        page_token  = request.query_params.get('page_token')
        label_id    = FOLDER_LABEL_MAP.get(folder, 'INBOX')

        try:
            svc    = _build_gmail_service(creds)
            params = dict(userId='me', labelIds=[label_id], maxResults=max_results)
            if page_token:
                params['pageToken'] = page_token

            result    = svc.users().messages().list(**params).execute()
            messages  = result.get('messages', [])
            next_page = result.get('nextPageToken')

            emails = []
            for m in messages:
                full = svc.users().messages().get(userId='me', id=m['id'],
                                                 format='metadata',
                                                 metadataHeaders=['From', 'To', 'Subject', 'Date']).execute()
                emails.append(_serialize_summary(full))

            # Count unread in inbox
            total_unread = 0
            if folder == 'INBOX':
                unread_res   = svc.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'],
                                                          maxResults=1).execute()
                total_unread = unread_res.get('resultSizeEstimate', 0)

            return Response({
                'emails':        emails,
                'nextPageToken': next_page,
                'totalUnread':   total_unread,
            })

        except HttpError as e:
            return Response({'error': str(e)}, status=502)


class EmailSearchView(APIView):
    """GET /api/emails/search/?q=<query>&max_results=50"""
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def get(self, request):
        creds = _get_credentials(request.user)
        if not creds:
            return Response({'error': 'Gmail not connected.', 'needs_auth': True}, status=403)

        q           = request.query_params.get('q', '')
        max_results = min(int(request.query_params.get('max_results', 50)), 100)

        try:
            svc      = _build_gmail_service(creds)
            result   = svc.users().messages().list(userId='me', q=q, maxResults=max_results).execute()
            messages = result.get('messages', [])

            emails = []
            for m in messages:
                full = svc.users().messages().get(userId='me', id=m['id'],
                                                 format='metadata',
                                                 metadataHeaders=['From', 'To', 'Subject', 'Date']).execute()
                emails.append(_serialize_summary(full))

            return Response({'emails': emails, 'nextPageToken': result.get('nextPageToken')})

        except HttpError as e:
            return Response({'error': str(e)}, status=502)


class EmailDetailView(APIView):
    """GET /api/emails/<message_id>/"""
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def get(self, request, message_id):
        creds = _get_credentials(request.user)
        if not creds:
            return Response({'error': 'Gmail not connected.', 'needs_auth': True}, status=403)

        try:
            svc  = _build_gmail_service(creds)
            msg  = svc.users().messages().get(userId='me', id=message_id, format='full').execute()
            return Response(_serialize_detail(msg))

        except HttpError as e:
            return Response({'error': str(e)}, status=502)


class EmailSendView(APIView):
    """POST /api/emails/send/"""
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def post(self, request):
        creds = _get_credentials(request.user)
        if not creds:
            return Response({'error': 'Gmail not connected.', 'needs_auth': True}, status=403)

        to        = request.data.get('to', [])
        cc        = request.data.get('cc', [])
        bcc       = request.data.get('bcc', [])
        subject   = request.data.get('subject', '')
        body      = request.data.get('body', '')
        thread_id = request.data.get('thread_id')

        if not to:
            return Response({'error': 'to is required'}, status=400)

        # Build MIME message
        msg = MIMEMultipart()
        msg['to']      = ', '.join(to) if isinstance(to, list) else to
        msg['cc']      = ', '.join(cc) if isinstance(cc, list) else cc
        msg['bcc']     = ', '.join(bcc) if isinstance(bcc, list) else bcc
        msg['subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Handle file attachments from multipart/form-data
        for f in request.FILES.getlist('attachments'):
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            email_encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{f.name}"')
            msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        body_payload = {'raw': raw}
        if thread_id:
            body_payload['threadId'] = thread_id

        try:
            svc  = _build_gmail_service(creds)
            sent = svc.users().messages().send(userId='me', body=body_payload).execute()
            return Response({'id': sent['id'], 'threadId': sent.get('threadId')}, status=201)

        except HttpError as e:
            return Response({'error': str(e)}, status=502)


class EmailModifyView(APIView):
    """POST /api/emails/modify/ — add/remove labels"""
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def post(self, request):
        creds = _get_credentials(request.user)
        if not creds:
            return Response({'error': 'Gmail not connected.', 'needs_auth': True}, status=403)

        ids           = request.data.get('ids', [])
        add_labels    = request.data.get('add_labels', [])
        remove_labels = request.data.get('remove_labels', [])

        if not ids:
            return Response({'error': 'ids required'}, status=400)

        try:
            svc = _build_gmail_service(creds)
            svc.users().messages().batchModify(
                userId='me',
                body={'ids': ids, 'addLabelIds': add_labels, 'removeLabelIds': remove_labels},
            ).execute()
            return Response({'modified': len(ids)})

        except HttpError as e:
            return Response({'error': str(e)}, status=502)


class EmailTrashView(APIView):
    """POST /api/emails/<message_id>/trash/"""
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def post(self, request, message_id):
        creds = _get_credentials(request.user)
        if not creds:
            return Response({'error': 'Gmail not connected.', 'needs_auth': True}, status=403)

        try:
            svc = _build_gmail_service(creds)
            svc.users().messages().trash(userId='me', id=message_id).execute()
            return Response({'trashed': True})

        except HttpError as e:
            return Response({'error': str(e)}, status=502)


class EmailAttachmentView(APIView):
    """GET /api/emails/<message_id>/attachments/<attachment_id>/"""
    authentication_classes = _AUTH
    permission_classes     = _PERM

    def get(self, request, message_id, attachment_id):
        creds = _get_credentials(request.user)
        if not creds:
            return Response({'error': 'Gmail not connected.', 'needs_auth': True}, status=403)

        try:
            svc  = _build_gmail_service(creds)
            att  = svc.users().messages().attachments().get(
                userId='me', messageId=message_id, id=attachment_id
            ).execute()
            data = base64.urlsafe_b64decode(att['data'] + '==')

            from django.http import HttpResponse
            response = HttpResponse(data, content_type='application/octet-stream')
            filename = request.query_params.get('filename', 'attachment')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except HttpError as e:
            return Response({'error': str(e)}, status=502)
