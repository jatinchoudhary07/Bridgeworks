"""
Hiring services — all business logic lives here, never in views.
"""

import logging
import csv
import io
import re
from typing import Any
import requests as req_lib

from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from ..models import (
    Job, Candidate, HiringStage, Application,
    ApplicationStageHistory, Interview, Offer
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------

DEFAULT_STAGES = [
    {
        'name': 'Screening',
        'slug': 'screening',
        'order': 1,
        'color': '#6366f1',
        'is_terminal': False,
    },
    {
        'name': 'Assessment',
        'slug': 'assessment',
        'order': 2,
        'color': '#f59e0b',
        'is_terminal': False,
    },
    {
        'name': 'Technical Interview',
        'slug': 'technical_interview',
        'order': 3,
        'color': '#3b82f6',
        'is_terminal': False,
    },
    {
        'name': 'HR Interview',
        'slug': 'hr_interview',
        'order': 4,
        'color': '#8b5cf6',
        'is_terminal': False,
    },
    {
        'name': 'Offer',
        'slug': 'offer',
        'order': 5,
        'color': '#10b981',
        'is_terminal': False,
    },
    {
        'name': 'Hired',
        'slug': 'hired',
        'order': 6,
        'color': '#22c55e',
        'is_terminal': True,
    },
    {
        'name': 'Rejected',
        'slug': 'rejected',
        'order': 7,
        'color': '#ef4444',
        'is_terminal': True,
    },
]


def ensure_default_stages(org_id: str):
    """Create default pipeline stages for an org if they don't exist yet."""
    for stage_data in DEFAULT_STAGES:
        HiringStage.objects.get_or_create(
            org_id=org_id,
            slug=stage_data['slug'],
            defaults={**stage_data, 'is_default': True},
        )


# ---------------------------------------------------------------------------
# Job services
# ---------------------------------------------------------------------------

def publish_job(job: Job, user) -> Job:
    if job.status == 'published':
        return job
    job.status = 'published'  # type: ignore
    job.published_at = timezone.now()  # type: ignore
    job.save(update_fields=['status', 'published_at', 'updated_at'])
    return job


def close_job(job: Job, user) -> Job:
    job.status = 'closed'  # type: ignore
    job.closed_at = timezone.now()  # type: ignore
    job.save(update_fields=['status', 'closed_at', 'updated_at'])
    return job


# ---------------------------------------------------------------------------
# Candidate / Application services
# ---------------------------------------------------------------------------

def get_or_create_candidate(
    org_id: str, data: dict, created_by=None
) -> tuple:
    """
    Return (candidate, created).
    Prevents duplicates by (org_id, email).
    """
    email = (data.get('email') or '').strip().lower()
    if not email:
        raise ValueError("Candidate email is required.")

    candidate, created = Candidate.objects.get_or_create(
        org_id=org_id,
        email=email,
        defaults={
            'name': data.get('name', ''),
            'phone': data.get('phone', ''),
            'resume_url': data.get('resume_url', ''),
            'linkedin_url': data.get('linkedin_url', ''),
            'github_url': data.get('github_url', ''),
            'skills': data.get('skills', []),
            'total_experience_years': data.get('total_experience_years'),
            'current_company': data.get('current_company', ''),
            'expected_salary': data.get('expected_salary'),
            'notice_period_days': data.get('notice_period_days'),
            'source': data.get('source', 'manual'),
            'created_by': created_by,
        }
    )
    return candidate, created


def create_application(
    candidate: Candidate,
    job: Job,
    created_by=None,
    extra_data: dict | None = None
) -> Application:
    """Create an Application (initially not placed in any stage until accepted)."""
    with transaction.atomic():  # type: ignore
        ensure_default_stages(str(job.org_id))

        application, created = Application.objects.get_or_create(
            candidate=candidate,
            job=job,
            defaults={
                'current_stage': None,
                'extra_data': extra_data or {},
            }
        )
        if created:
            ApplicationStageHistory.objects.create(
                application=application,
                from_stage=None,
                to_stage=None,
                moved_by=created_by,
                notes='Application received.',
            )
        return application


def move_candidate_stage(
    application: Application,
    to_stage: HiringStage,
    moved_by,
    notes: str = ''
) -> Application:
    """Move a candidate to a new pipeline stage and log it."""
    with transaction.atomic():  # type: ignore
        from_stage = application.current_stage
        application.current_stage = to_stage  # type: ignore
        application.save(update_fields=['current_stage', 'updated_at'])

        ApplicationStageHistory.objects.create(
            application=application,
            from_stage=from_stage,
            to_stage=to_stage,
            moved_by=moved_by,
            notes=notes,
        )
        return application


# ---------------------------------------------------------------------------
# Google Forms import
# ---------------------------------------------------------------------------

FIELD_MAP = {
    # ---- Name variants ----
    'name': 'name',
    'full_name': 'name',
    'your_name': 'name',
    'applicant_name': 'name',
    'candidate_name': 'name',
    'fullname': 'name',
    'yourname': 'name',
    # first_name / last_name combined in the loop below (sentinel values)
    'first_name': '__first_name__',
    'firstname': '__first_name__',
    'last_name': '__last_name__',
    'lastname': '__last_name__',
    'surname': '__last_name__',
    # ---- Email variants ----
    'email': 'email',
    'email_address': 'email',
    'emailaddress': 'email',
    'e_mail_address': 'email',  # covers Google Form header: "E-mail address"
    'your_email': 'email',
    'youremail': 'email',
    'mail': 'email',
    'e_mail': 'email',
    'email_id': 'email',
    'emailid': 'email',
    'personal_email': 'email',
    'work_email': 'email',
    # ---- Phone variants ----
    'phone': 'phone',
    'phone_number': 'phone',
    'mobile': 'phone',
    'contact': 'phone',
    'mobile_number': 'phone',
    'contact_number': 'phone',
    'cell': 'phone',
    'whatsapp': 'phone',
    'whatsapp_number': 'phone',
    'telephone': 'phone',
    'your_phone': 'phone',
    'your_mobile': 'phone',
    'mob': 'phone',
    # ---- Resume ----
    'resume': 'resume_url',
    'resume_link': 'resume_url',
    'resume_url': 'resume_url',
    'cv': 'resume_url',
    'cv_link': 'resume_url',
    'upload_resume': 'resume_url',
    'resume_drive_link': 'resume_url',
    'portfolio': 'resume_url',
    # ---- LinkedIn ----
    'linkedin': 'linkedin_url',
    'linkedin_profile': 'linkedin_url',
    'linkedin_url': 'linkedin_url',
    'linkedin_link': 'linkedin_url',
    'linkedinprofile': 'linkedin_url',
    # ---- GitHub ----
    'github': 'github_url',
    'github_profile': 'github_url',
    'github_url': 'github_url',
    'github_link': 'github_url',
    'githubprofile': 'github_url',
    # ---- Skills ----
    'skills': 'skills',
    'key_skills': 'skills',
    'technical_skills': 'skills',
    'skill_set': 'skills',
    'skillset': 'skills',
    'technologies': 'skills',
    # ---- Experience ----
    'experience': 'total_experience_years',
    'years_of_experience': 'total_experience_years',
    'total_experience': 'total_experience_years',
    'work_experience': 'total_experience_years',
    'experience_in_years': 'total_experience_years',
    'total_work_experience': 'total_experience_years',
    'years_experience': 'total_experience_years',
    'exp': 'total_experience_years',
    # ---- Company ----
    'current_company': 'current_company',
    'company': 'current_company',
    'employer': 'current_company',
    'current_employer': 'current_company',
    'organization': 'current_company',
    'organisation': 'current_company',
    'current_organization': 'current_company',
    # ---- Designation ----
    'current_designation': 'current_designation',
    'designation': 'current_designation',
    'role': 'current_designation',
    'current_role': 'current_designation',
    'job_title': 'current_designation',
    'position': 'current_designation',
    # ---- Salary ----
    'expected_salary': 'expected_salary',
    'expected_ctc': 'expected_salary',
    'expectedctc': 'expected_salary',
    'expected_package': 'expected_salary',
    'current_salary': 'current_salary',
    'current_ctc': 'current_salary',
    'currentctc': 'current_salary',
    'current_package': 'current_salary',
    # ---- Notice period ----
    'notice_period': 'notice_period_days',
    'notice_period_days': 'notice_period_days',
    'notice': 'notice_period_days',
}


def _resolve_csv_url(url: str) -> str:
    """
    Convert any Google Sheets URL to a direct CSV export URL.
    Raises ValueError with prefix 'FORM_URL:' if a Google Form URL is given.
    """
    # Detect a Google Forms URL — cannot be fetched as CSV directly
    if re.search(
        r'(docs\.google\.com/forms|forms\.gle|forms\.google\.com)', url
    ):
        raise ValueError('FORM_URL')
    # Already a usable CSV URL — return as-is
    if 'export?format=csv' in url or 'pub?output=csv' in url:
        return url
    # Google Sheets URL: extract sheet ID
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
    if match:
        sheet_id = match.group(1)
        return (
            "https://docs.google.com/spreadsheets/d/"
            f"{sheet_id}/export?format=csv"
        )
    raise ValueError(
        "Could not parse the URL. Please paste your Google Sheets URL "
        "(the spreadsheet linked to your Google Form responses)."
    )


def _normalise_header(header: str) -> str:
    """Normalise a CSV header for FIELD_MAP lookup.

    Steps:
    1. Strip leading/trailing whitespace.
    2. Lowercase.
    3. Replace spaces, hyphens, dots, slashes, parentheses, question marks,
       asterisks, colons and other punctuation with underscores.
    4. Collapse consecutive underscores to one.
    5. Strip leading/trailing underscores.
    """
    h = header.strip().lower()
    h = re.sub(r'[\s\-\.\(\)\/\?\*:\[\]#@!,;]+', '_', h)
    h = re.sub(r'_+', '_', h)
    h = h.strip('_')
    return h


def _make_placeholder_email(
    candidate_data: dict, row: dict, row_index: int
) -> str:
    """Try to derive a usable (placeholder) email when none was supplied.

    Priority:
      1. phone → phone@noemail.form
      2. name  → slugified-name@noemail.form
      3. row_index → row{n}@noemail.form
    Returns None if nothing at all is available.
    """
    phone = (candidate_data.get('phone') or '').strip()
    if phone:
        digits = re.sub(r'\D', '', phone)
        if digits:
            return f"{digits}@noemail.form"

    name = (candidate_data.get('name') or '').strip()
    if name:
        slug = re.sub(r'[^a-z0-9]+', '.', name.lower()).strip('.')
        if slug:
            return f"{slug}@noemail.form"

    return f"row{row_index}@noemail.form"


def sync_google_form_csv(org_id: str, job_id: int, created_by=None) -> dict:
    """
    Pull the entire Google Sheet and import every row — header-agnostic.

    Strategy
    ────────
    1.  Fetch the raw CSV regardless of what the column headers say.
    2.  Store the FULL row (all columns, original header names) in
        Application.extra_data — nothing is ever thrown away.
    3.  Auto-detect email / phone by scanning every cell value with
        regex, so it doesn't matter what the column is called.
    4.  FIELD_MAP + _normalise_header run as a bonus pass on top —
        forms with standard headers also get clean Candidate fields.
    5.  First name + Last name columns are joined into a single name.
    6.  No row is ever skipped — if email is still not found after all
        the above, a placeholder derived from phone → name → row index
        is used. Flagged with _email_missing=True in extra_data.

    Returns {'imported': int, 'skipped': int, 'errors': list,
             'columns': list, 'auto_detected': dict}.
    """
    # ── Regex for value-based auto-detection (works for ANY header name) ──
    EMAIL_RE = re.compile(r'^[\w.+\-]+@[\w\-]+\.[a-zA-Z]{2,}$')
    PHONE_RE = re.compile(r'^[\+]?[\d\s\-\(\)]{7,15}$')
    # Name-like: 2–5 space-separated words, only letters/apostrophe/hyphen/dot
    NAME_RE = re.compile(
        r"^[A-Za-z][A-Za-z'\-\.]{1,29}"
        r"(\s+[A-Za-z][A-Za-z'\-\.]{0,29}){0,4}$"
    )

    def _detect_from_values(row: dict) -> dict:
        """Scan all cell values; return detected email / phone / name."""
        detected = {}
        name_candidates = []
        for value in row.values():
            v = (value or '').strip()
            if not v:
                continue
            if 'email' not in detected and EMAIL_RE.match(v):
                detected['email'] = v
            elif (
                'phone' not in detected
                and PHONE_RE.match(v)
                and len(re.sub(r'\D', '', v)) >= 7
            ):
                detected['phone'] = v
            elif NAME_RE.match(v) and 3 <= len(v) <= 60:
                name_candidates.append(v)
        if name_candidates and 'name' not in detected:
            detected['name'] = max(name_candidates, key=len)
        return detected

    # ── Fetch sheet ────────────────────────────────────────────────────────
    job = Job.objects.get(pk=job_id, org_id=org_id)
    if not job.google_form_url:
        raise ValueError("No Google Form URL configured for this job.")

    try:
        url = _resolve_csv_url(job.google_form_url.strip())
    except ValueError:
        raise

    sheet_id_match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
    urls_to_try = [url]
    if sheet_id_match:
        sid = sheet_id_match.group(1)
        urls_to_try = [
            f'https://docs.google.com/spreadsheets/d/{sid}/export?format=csv',
            (
                "https://docs.google.com/spreadsheets/d/"
                f"{sid}/gviz/tq?tqx=out:csv"
            ),
        ]

    raw = None
    last_error = None
    for attempt_url in urls_to_try:
        try:
            resp = req_lib.get(
                attempt_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1)',
                    'Accept': 'text/csv,text/plain,*/*',
                },
                timeout=15,
                allow_redirects=True,
            )
            if resp.status_code == 200:
                content = resp.text
                stripped = content.strip().lower()
                is_html = (
                    stripped.startswith('<!doctype')
                    or stripped.startswith('<html')
                )
                if not is_html:
                    raw = content
                    break
            last_error = f'HTTP {resp.status_code}'
        except Exception as exc:
            last_error = str(exc)

    if raw is None:
        raise ValueError(
            "The Google Sheet is not publicly accessible or "
            "returned an error. "
            "Please open the sheet → Share → set 'Anyone with the link' "
            "→ Viewer → Done, then try again. "
            f"(Last error: {last_error})"
        )

    # ── Parse CSV ──────────────────────────────────────────────────────────
    reader = csv.DictReader(io.StringIO(raw))
    headers = reader.fieldnames or []
    if not headers:
        return {
            'imported': 0,
            'skipped': 0,
            'errors': ['No columns found in sheet.'],
            'columns': [],
            'auto_detected': {},
        }

    # Pre-build normalisation map for FIELD_MAP bonus pass
    norm = {h: _normalise_header(h) for h in headers}

    imported, skipped = 0, 0
    new_count = 0
    errors = []
    auto_detected_count = {'email': 0, 'phone': 0, 'name': 0}

    for row_index, row in enumerate(reader, start=1):
        try:
            # ── 1. Store the entire raw row in extra_data (always) ─────────
            extra_data = {k: v for k, v in row.items() if v is not None}
            extra_data['_row_index'] = row_index

            # ── 2. FIELD_MAP pass (header-based, best effort) ──────────────
            candidate_data: dict[str, Any] = {'source': 'google_form'}
            for raw_header, value in row.items():
                norm_key = norm.get(raw_header, _normalise_header(raw_header))
                mapped = FIELD_MAP.get(norm_key)
                if mapped and mapped not in (
                    '__first_name__', '__last_name__'
                ):
                    candidate_data[mapped] = value
                elif mapped == '__first_name__':
                    candidate_data['__first_name__'] = value
                elif mapped == '__last_name__':
                    candidate_data['__last_name__'] = value

            # Combine first + last name
            if not candidate_data.get('name'):
                first = (
                    candidate_data.pop('__first_name__', '') or ''
                ).strip()
                last = (
                    candidate_data.pop('__last_name__', '') or ''
                ).strip()
                full = ' '.join(filter(None, [first, last]))
                if full:
                    candidate_data['name'] = full
            else:
                candidate_data.pop('__first_name__', None)
                candidate_data.pop('__last_name__', None)

            # ── 3. Value-scan auto-detection (fills any gaps left) ─────────
            detected = _detect_from_values(row)
            for field in ('email', 'phone', 'name'):
                has_val = bool((candidate_data.get(field) or '').strip())
                if not has_val and detected.get(field):
                    candidate_data[field] = detected[field]
                    auto_detected_count[field] += 1
                    extra_data[f'_auto_detected_{field}'] = detected[field]

            # ── 4. Email fallback — NEVER skip any row ────────────────────
            if not (candidate_data.get('email') or '').strip():
                placeholder = _make_placeholder_email(
                    candidate_data, row, row_index
                )
                candidate_data['email'] = placeholder
                extra_data['_email_missing'] = True
                extra_data['_placeholder_email'] = placeholder
                logger.warning(
                    "Row %d: no email found — imported with placeholder '%s'",
                    row_index, placeholder,
                )

            # ── 5. Clean numeric fields ────────────────────────────────────
            numeric_fields = (
                'total_experience_years',
                'expected_salary',
                'current_salary',
                'notice_period_days',
            )
            for field in numeric_fields:
                raw_val = candidate_data.get(field)
                if raw_val is not None and isinstance(raw_val, str):
                    cleaned = re.sub(r'[^\d.]', '', raw_val)
                    if cleaned:
                        candidate_data[field] = cleaned
                    else:
                        candidate_data.pop(field, None)

            if isinstance(candidate_data.get('skills'), str):
                candidate_data['skills'] = [
                    s.strip()
                    for s in candidate_data['skills'].split(',')
                    if s.strip()
                ]

            # ── 6. Save ───────────────────────────────────────────────────
            candidate, _ = get_or_create_candidate(
                org_id, candidate_data, created_by=created_by
            )
            app_exists = Application.objects.filter(
                candidate=candidate, job=job
            ).exists()
            app = create_application(
                candidate, job, created_by=created_by, extra_data=extra_data
            )
            if app.extra_data != extra_data:
                app.extra_data = extra_data  # type: ignore
                app.save(update_fields=['extra_data'])
            if not app_exists:
                new_count += 1
            imported += 1

        except Exception as exc:
            logger.exception(
                "Error importing row %d from Google Sheet CSV", row_index
            )
            errors.append({'row': row_index, 'error': str(exc)})

    return {
        'imported': imported,
        'new_count': new_count,
        'skipped': skipped,
        'errors': errors,
        'columns': headers,
        'auto_detected': auto_detected_count,
    }


def import_google_form_candidates(
    org_id: str,
    job_id: int,
    spreadsheet_id: str,
    credentials_json: dict,
    created_by=None
) -> dict:
    """
    Sync candidates from a Google Sheet (backed by a Google Form).
    Requires: google-auth, google-api-python-client in requirements.
    Returns {'created': int, 'updated': int, 'errors': list}.
    """
    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials
    except ImportError:
        raise ImportError(
            "Install google-api-python-client and google-auth "
            "to use this feature."
        )

    job = Job.objects.get(pk=job_id, org_id=org_id)
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets.readonly'
    ]
    creds = Credentials.from_service_account_info(
        credentials_json, scopes=scopes
    )
    service = build('sheets', 'v4', credentials=creds)

    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range='Sheet1',
    ).execute()

    rows = result.get('values', [])
    if not rows:
        return {'created': 0, 'updated': 0, 'errors': []}

    headers = [h.strip().lower().replace(' ', '_') for h in rows[0]]
    created_count = 0
    errors = []

    local_field_map = {
        'name': 'name',
        'full_name': 'name',
        'email': 'email',
        'email_address': 'email',
        'phone': 'phone',
        'phone_number': 'phone',
        'mobile': 'phone',
        'resume': 'resume_url',
        'resume_link': 'resume_url',
        'resume_url': 'resume_url',
        'linkedin': 'linkedin_url',
        'linkedin_profile': 'linkedin_url',
        'github': 'github_url',
        'github_profile': 'github_url',
        'skills': 'skills',
        'experience': 'total_experience_years',
        'years_of_experience': 'total_experience_years',
        'current_company': 'current_company',
        'company': 'current_company',
        'expected_salary': 'expected_salary',
        'expected_ctc': 'expected_salary',
        'notice_period': 'notice_period_days',
    }

    for row in rows[1:]:
        try:
            row_data = dict(zip(headers, row))
            candidate_data: dict[str, Any] = {'source': 'google_form'}
            for col, value in row_data.items():
                if col in local_field_map:
                    candidate_data[local_field_map[col]] = value

            if not candidate_data.get('email'):
                errors.append({'row': row_data, 'error': 'Missing email'})
                continue

            # Parse skills to list
            if isinstance(candidate_data.get('skills'), str):
                candidate_data['skills'] = [
                    s.strip()
                    for s in candidate_data['skills'].split(',')
                    if s.strip()
                ]

            candidate, _ = get_or_create_candidate(
                org_id, candidate_data, created_by=created_by
            )
            create_application(
                candidate, job, created_by=created_by
            )
            created_count += 1
        except Exception as exc:
            logger.exception("Error importing row from Google Sheet")
            errors.append({'error': str(exc)})

    return {'created': created_count, 'updated': 0, 'errors': errors}


# ---------------------------------------------------------------------------
# Interview services
# ---------------------------------------------------------------------------

def schedule_interview(
    application: Application, data: dict, created_by
) -> Interview:
    with transaction.atomic():  # type: ignore
        interview = Interview.objects.create(
            application=application,
            title=data.get('title', 'Interview'),
            scheduled_at=data['scheduled_at'],
            duration_minutes=data.get('duration_minutes', 60),
            mode=data.get('mode', 'google_meet'),
            meeting_link=data.get('meeting_link', ''),
            location=data.get('location', ''),
            notes=data.get('notes', ''),
            status='scheduled',
            created_by=created_by,
        )
        interviewer_ids = data.get('interviewer_ids', [])
        if interviewer_ids:
            User = get_user_model()
            interviewers = User.objects.filter(pk__in=interviewer_ids)
            interview.interviewers.set(interviewers)
        return interview


def reschedule_interview(
    interview: Interview, scheduled_at, notes: str = ''
) -> Interview:
    interview.scheduled_at = scheduled_at  # type: ignore
    interview.status = 'rescheduled'  # type: ignore
    if notes:
        interview.notes = notes  # type: ignore
    interview.save(
        update_fields=['scheduled_at', 'status', 'notes', 'updated_at']
    )
    return interview


# ---------------------------------------------------------------------------
# Feedback services
# ---------------------------------------------------------------------------

def submit_feedback(interview: Interview, interviewer, data: dict):
    from ..models import InterviewFeedback
    feedback, _ = InterviewFeedback.objects.update_or_create(
        interview=interview,
        interviewer=interviewer,
        defaults={
            'overall_rating': data.get('overall_rating', 3),
            'strengths': data.get('strengths', ''),
            'weaknesses': data.get('weaknesses', ''),
            'notes': data.get('notes', ''),
            'recommendation': data.get('recommendation', 'neutral'),
        }
    )
    return feedback


# ---------------------------------------------------------------------------
# Offer services
# ---------------------------------------------------------------------------

def create_offer(application: Application, data: dict, created_by) -> Offer:
    with transaction.atomic():  # type: ignore
        offer = Offer.objects.create(
            application=application,
            offered_salary=data['offered_salary'],
            currency=data.get('currency', 'INR'),
            joining_date=data.get('joining_date'),
            offer_letter_url=data.get('offer_letter_url', ''),
            status='pending',
            valid_until=data.get('valid_until'),
            notes=data.get('notes', ''),
            created_by=created_by,
        )
        # Move application to 'offer' stage
        offer_stage = HiringStage.objects.filter(
            org_id=application.job.org_id, slug='offer'
        ).first()
        if offer_stage:
            move_candidate_stage(
                application,
                offer_stage,
                moved_by=created_by,
                notes='Offer created.',
            )
        return offer


def update_offer_status(offer: Offer, status: str) -> Offer:
    offer.status = status  # type: ignore
    if status in ('accepted', 'rejected'):
        offer.responded_at = timezone.now()  # type: ignore
        # Move application stage accordingly
        org_id = offer.application.job.org_id
        slug = 'hired' if status == 'accepted' else 'rejected'
        stage = HiringStage.objects.filter(org_id=org_id, slug=slug).first()
        if stage:
            offer.application.current_stage = stage  # type: ignore
            offer.application.save(
                update_fields=['current_stage', 'updated_at']
            )
    offer.save()
    return offer


# ---------------------------------------------------------------------------
# Employee conversion
# ---------------------------------------------------------------------------

def convert_candidate_to_employee(
    application: Application, converted_by
) -> dict:
    """
    Convert a hired candidate into a WorkforceMember (existing HR model).
    Returns the created member instance.
    """
    with transaction.atomic():  # type: ignore
        from core.models import WorkforceMember, WorkforceDepartment

        candidate = application.candidate
        job = application.job

        # Resolve or create department
        department = None
        if job.department:
            department, _ = WorkforceDepartment.objects.get_or_create(
                org_id=job.org_id,
                name=job.department,
            )

        # Avoid duplicates
        existing = WorkforceMember.objects.filter(
            org_id=job.org_id,
            email__iexact=candidate.email,
        ).first()

        if existing:
            return {'member': existing, 'created': False}

        member = WorkforceMember.objects.create(
            org_id=job.org_id,
            full_name=candidate.name,
            email=candidate.email,
            phone=candidate.phone,
            department=department,
            role_designation=job.title,
            status='Active',
            created_by=converted_by,
        )

        # Move to hired stage
        hired_stage = HiringStage.objects.filter(
            org_id=job.org_id, slug='hired'
        ).first()
        if hired_stage:
            move_candidate_stage(
                application,
                hired_stage,
                moved_by=converted_by,
                notes='Converted to employee.',
            )

        return {'member': member, 'created': True}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def get_hiring_analytics(org_id: str) -> dict:
    from django.db.models import Count
    from ..models import Application, Offer

    applications = Application.objects.filter(
        job__org_id=org_id, is_deleted=False
    )
    total_applications = applications.count()

    stage_funnel = list(
        applications.filter(current_stage__isnull=False)
        .values('current_stage__name', 'current_stage__slug')
        .annotate(count=Count('id'))
        .order_by('current_stage__order')
    )

    offers = Offer.objects.filter(application__job__org_id=org_id)
    total_offers = offers.count()
    accepted_offers = offers.filter(status='accepted').count()
    offer_acceptance_rate = (
        round(accepted_offers / total_offers * 100, 1)
        if total_offers
        else 0
    )

    hired = applications.filter(current_stage__slug='hired').count()
    hire_rate = (
        round(hired / total_applications * 100, 1)
        if total_applications
        else 0
    )

    dept_breakdown = list(
        applications.values('job__department')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    source_breakdown = list(
        applications.values('candidate__source')
        .annotate(count=Count('id'))
        .order_by('-count')
    )

    return {
        'total_applications': total_applications,
        'total_hired': hired,
        'hire_rate': hire_rate,
        'total_offers': total_offers,
        'offer_acceptance_rate': offer_acceptance_rate,
        'stage_funnel': stage_funnel,
        'department_breakdown': dept_breakdown,
        'source_breakdown': source_breakdown,
    }
