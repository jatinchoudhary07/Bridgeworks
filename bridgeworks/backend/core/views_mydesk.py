import csv
import json
import io
import logging
import os
import re
import time
from urllib.parse import urlparse
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from django.db import connection, transaction
from django.db.models import Q, Sum
from django.http import FileResponse, HttpResponse, HttpResponseRedirect
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.models import (
    MyDeskNote,
    MyDeskNoteVersion,
    MyDeskNoteAttachment,
    PersonalTodoItem,
    PersonalTodoAttachment,
    ExpenseEntry,
    ExpenseShare,
    LeaveRequest,
    AttendanceEntry,
    AttendanceRulebook,
    CompanyProfile,
    EmployeeProfile,
    PayrollProfile,
    PayrollPaymentRecord,
    PayrollSalaryStructure,
    PayrollTaxDeclaration,
    PayrollRun,
    WorkforceMember,
    GalleryAlbum,
    GalleryItem,
    GalleryItemShare,
    HrMeetingManagerCompanyEvent,
)
from core.serializers import (
    MyDeskNoteSerializer,
    PersonalTodoItemSerializer,
    ExpenseEntrySerializer,
    LeaveRequestSerializer,
    AttendanceEntrySerializer,
    PayrollSalaryStructureSerializer,
    PayrollTaxDeclarationSerializer,
    GalleryAlbumSerializer,
    GalleryItemSerializer,
)
from core.views.helpers import _get_org_id_or_none
from core.services.notifications import push_unified_notification
from core.permissions import HasModulePermission
from core.cloudinary_utils import get_cloudinary_file_url, build_file_access_url as _cloudinary_build_file_access_url

User = get_user_model()
LOGGER = logging.getLogger(__name__)
MENTION_PATTERN = re.compile(r'@(\w+)')
SHARED_MEMBER_PREFIX = 'shared:member:'
# Legacy default shift (overridden per-employee by AttendanceRulebook)
ATTENDANCE_SHIFT_START_HOUR = 9
ATTENDANCE_SHIFT_START_MINUTE = 30
ATTENDANCE_SHIFT_END_HOUR = 18
ATTENDANCE_SHIFT_END_MINUTE = 30
PAYROLL_PRESENT_STATUSES = {'present', 'wfh', 'on_duty', 'leave'}
# Shift lock hour (after 22:00 same day, no more same-day edits)
ATTENDANCE_LOCK_HOUR = 22
# Deduction types
DEDUCTION_NONE = 0
DEDUCTION_ONE_HOUR = 0.125  # 1hr out of 8hr shift ≈ 0.125 day
DEDUCTION_HALF_DAY = 0.5
DEDUCTION_FULL_DAY = 1.0
EXPENSE_TRACKER_PENDING_STATUSES = {'Submitted'}
EXPENSE_TRACKER_RESUBMITTABLE_STATUSES = {'Draft', 'Rejected'}
EXPENSE_TRACKER_SEND_OPTIONS = [
    {'key': 'whatsapp', 'label': 'WhatsApp'},
    {'key': 'email', 'label': 'Email'},
    {'key': 'slack', 'label': 'Slack'},
    {'key': 'pdf', 'label': 'PDF'},
    {'key': 'excel', 'label': 'Excel'},
]
EXPENSE_TRACKER_MEMBER_SEND_OPTIONS = [
    {'key': 'whatsapp', 'label': 'WhatsApp'},
    {'key': 'email_hr', 'label': 'Email HR'},
    {'key': 'hr_portal', 'label': 'HR Portal'},
    {'key': 'pdf', 'label': 'Export PDF'},
]

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except Exception:
    A4 = None
    canvas = None
    REPORTLAB_AVAILABLE = False

try:
    import cloudinary.api as cloudinary_api
    from cloudinary.utils import private_download_url as cloudinary_private_download_url
    CLOUDINARY_SIGNED_DOWNLOAD_AVAILABLE = True
except Exception:
    cloudinary_api = None
    cloudinary_private_download_url = None
    CLOUDINARY_SIGNED_DOWNLOAD_AVAILABLE = False

try:
    from cloudinary.exceptions import Error as CloudinaryUploadError
except Exception:
    CloudinaryUploadError = RuntimeError


def _round2(value):
    return float(Decimal(str(value or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def _cloudinary_private_download_link(file_field, attachment=False):
    """Safe Cloudinary URL resolution — delegates to cloudinary_utils.

    The old implementation made up to 6 synchronous blocking HTTP calls
    per file to brute-force the resource type, which caused connection-pool
    exhaustion and cascading server crashes.  The new implementation uses
    extension-based inference, Django cache, and a 3-second timeout guard.
    """
    return get_cloudinary_file_url(file_field, attachment=attachment)


def _parse_bool_query_param(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    raw_value = str(value).strip().lower()
    if raw_value in {'1', 'true', 'yes', 'on'}:
        return True
    if raw_value in {'0', 'false', 'no', 'off'}:
        return False
    return None


def _normalize_todo_type_filter(value):
    normalized = str(value or '').strip().lower()
    if normalized in {'task', 'personal'}:
        return normalized
    return ''


def _parse_shared_with_ids_payload(payload):
    values = []
    if hasattr(payload, 'getlist'):
        values.extend(payload.getlist('shared_with_ids'))

    single_value = payload.get('shared_with_ids') if hasattr(payload, 'get') else None
    if single_value and single_value not in values:
        values.append(single_value)

    parsed_ids = []
    for raw in values:
        if isinstance(raw, (list, tuple)):
            for item in raw:
                try:
                    parsed_ids.append(int(item))
                except (TypeError, ValueError):
                    continue
            continue

        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                continue
            if raw.startswith('['):
                try:
                    parsed_json = json.loads(raw)
                    if isinstance(parsed_json, list):
                        for item in parsed_json:
                            try:
                                parsed_ids.append(int(item))
                            except (TypeError, ValueError):
                                continue
                        continue
                except Exception:
                    pass
            try:
                parsed_ids.append(int(raw))
            except (TypeError, ValueError):
                continue
            continue

        try:
            parsed_ids.append(int(raw))
        except (TypeError, ValueError):
            continue

    return sorted(set(parsed_ids))


def _parse_int_ids_payload(payload, field_name):
    values = []
    if hasattr(payload, 'getlist'):
        values.extend(payload.getlist(field_name))

    single_value = payload.get(field_name) if hasattr(payload, 'get') else None
    if single_value not in (None, '', []) and single_value not in values:
        values.append(single_value)

    parsed_ids = []
    for raw in values:
        if isinstance(raw, (list, tuple)):
            for item in raw:
                try:
                    parsed_ids.append(int(item))
                except (TypeError, ValueError):
                    continue
            continue

        if isinstance(raw, str):
            raw = raw.strip()
            if not raw:
                continue

            if raw.startswith('['):
                try:
                    parsed_json = json.loads(raw)
                    if isinstance(parsed_json, list):
                        for item in parsed_json:
                            try:
                                parsed_ids.append(int(item))
                            except (TypeError, ValueError):
                                continue
                        continue
                except Exception:
                    pass

            try:
                parsed_ids.append(int(raw))
            except (TypeError, ValueError):
                continue
            continue

        try:
            parsed_ids.append(int(raw))
        except (TypeError, ValueError):
            continue

    return sorted(set(parsed_ids))


def _resolve_gallery_share_recipients(org_id, recipient_ids, actor_user_id=None):
    if not recipient_ids:
        return []

    recipients = User.objects.filter(id__in=recipient_ids)
    if org_id:
        recipients = recipients.filter(
            Q(team_settings__organization__organization_id=org_id) |
            Q(shop_credentials__organization_id=org_id)
        )
    if actor_user_id is not None:
        recipients = recipients.exclude(id=actor_user_id)

    return list(recipients.distinct())


def _sync_gallery_item_shares(item, actor, recipient_ids):
    org_id = str(getattr(item, 'org_id', '') or '')
    recipients = _resolve_gallery_share_recipients(org_id, recipient_ids, actor_user_id=actor.id)
    recipient_by_id = {int(recipient.id): recipient for recipient in recipients}
    target_ids = set(recipient_by_id.keys())

    existing_qs = GalleryItemShare.objects.filter(item=item)
    existing_ids = set(existing_qs.values_list('recipient_id', flat=True))

    to_remove_ids = sorted(existing_ids - target_ids)
    if to_remove_ids:
        existing_qs.filter(recipient_id__in=to_remove_ids).delete()

    to_add_ids = sorted(target_ids - existing_ids)
    shares_to_add = [
        GalleryItemShare(
            org_id=org_id,
            item=item,
            recipient=recipient_by_id[recipient_id],
            sent_by=actor,
        )
        for recipient_id in to_add_ids
    ]

    if not shares_to_add:
        return

    GalleryItemShare.objects.bulk_create(shares_to_add, ignore_conflicts=True)
    for share in shares_to_add:
        push_unified_notification(
            recipient=share.recipient,
            actor=actor,
            module='gallery',
            action='share',
            title='Vault file shared with you',
            message=f"{actor.first_name or actor.username} shared a vault file with you",
            entity_type='gallery_item',
            entity_id=item.id,
            deep_link={
                'page': '/mydesk/vault',
                'section': 'gallery',
                'itemId': str(item.id),
                'albumId': str(item.album_id or ''),
            },
        )


def _month_label(day_value):
    if not isinstance(day_value, date):
        return ''
    return day_value.strftime('%b %Y')


def _financial_year_label(reference_date):
    if not isinstance(reference_date, date):
        reference_date = timezone.localdate()
    start_year = reference_date.year if reference_date.month >= 4 else reference_date.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def _financial_year_bounds(financial_year=None, reference_date=None):
    if financial_year:
        try:
            start_year = int(str(financial_year).split('-', 1)[0])
            start_day = date(start_year, 4, 1)
            end_day = date(start_year + 1, 3, 31)
            return start_day, end_day, _financial_year_label(start_day)
        except Exception:
            pass

    if not isinstance(reference_date, date):
        reference_date = timezone.localdate()

    start_year = reference_date.year if reference_date.month >= 4 else reference_date.year - 1
    start_day = date(start_year, 4, 1)
    end_day = date(start_year + 1, 3, 31)
    return start_day, end_day, _financial_year_label(reference_date)


def _month_start_from_value(month_value):
    first_day, _ = _parse_month_bounds(month_value)
    return first_day


def _month_starts(first_day, last_day):
    values = []
    current = date(first_day.year, first_day.month, 1)
    while current <= last_day:
        values.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return values


def _mask_pan_number(value):
    raw = str(value or '').strip().upper()
    if len(raw) < 10:
        return raw
    return f"{raw[:5]}****{raw[-1:]}"


def _mask_bank_account(value):
    raw = str(value or '').strip()
    if not raw:
        return '-'
    digits = ''.join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 4:
        return f"•••• {digits[-4:]}"
    return raw


def _default_employee_code(user_id):
    return f"UFY-{int(user_id):04d}"


def _default_pan_number(user_id):
    suffix = str(int(user_id)).zfill(4)[-4:]
    return f"UFYPA{suffix}Q"


def _default_uan_number(user_id):
    return str(100000000000 + int(user_id))[-12:]


def _strip_generated_identity_value(value, generated_value):
    raw = str(value or '').strip()
    if not raw:
        return ''
    generated = str(generated_value or '').strip()
    if generated and raw.upper() == generated.upper():
        return ''
    return raw


def _user_full_name(user):
    return user.get_full_name() or user.first_name or user.username or user.email


def _get_user_profile_object(user):
    profile = getattr(user, 'profile', None)
    return profile if profile else None


def _company_payload(org_id):
    profile = CompanyProfile.objects.filter(org_id=org_id).first()
    if not profile:
        return {
            'name': '',
            'address': '',
            'support_email': '',
            'support_phone': '',
        }
    return {
        'name': str(profile.legal_name or '').strip(),
        'address': str(profile.registered_address or '').strip(),
        'support_email': str(profile.support_email or '').strip(),
        'support_phone': str(profile.support_phone or '').strip(),
    }


def _employee_base_gross_value(org_id, user, payroll_profile=None):
    employee_profile = EmployeeProfile.objects.filter(
        org_id=org_id,
        user=user,
        is_active=True,
    ).first()
    if employee_profile and employee_profile.base_gross is not None:
        value = _round2(employee_profile.base_gross)
        if value > 0:
            return value

    fallback = _round2(getattr(payroll_profile, 'base_monthly_gross', 0) or 0)
    return max(0.0, fallback)


def _effective_salary_structures(org_id, user, month_start=None):
    if not isinstance(month_start, date):
        today = timezone.localdate()
        month_start = date(today.year, today.month, 1)

    queryset = PayrollSalaryStructure.objects.filter(
        org_id=org_id,
        user=user,
        is_active=True,
        effective_from__lte=month_start,
    ).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=month_start)
    )

    rows = list(queryset.order_by('-version', 'sort_order', 'id'))
    if not rows:
        return []

    active_version = max(int(getattr(item, 'version', 1) or 1) for item in rows)
    selected = [item for item in rows if int(getattr(item, 'version', 1) or 1) == active_version]
    return sorted(selected, key=lambda item: (int(getattr(item, 'sort_order', 0) or 0), int(item.id or 0)))


def _salary_structure_version(rows):
    if not rows:
        return 0
    return max(int(getattr(item, 'version', 1) or 1) for item in rows)


def _salary_structure_rows_to_snapshot(rows):
    snapshot_rows = []
    for item in rows or []:
        snapshot_rows.append({
            'component_name': str(getattr(item, 'component_name', '') or ''),
            'monthly_amount': _round2(getattr(item, 'monthly_amount', 0) or 0),
            'annual_amount': _round2(getattr(item, 'annual_amount', 0) or 0),
            'taxability': str(getattr(item, 'taxability', 'yes') or 'yes'),
            'remarks': str(getattr(item, 'remarks', '') or ''),
            'sort_order': int(getattr(item, 'sort_order', 0) or 0),
            'version': int(getattr(item, 'version', 1) or 1),
            'effective_from': getattr(item, 'effective_from', None).isoformat() if getattr(item, 'effective_from', None) else None,
            'effective_to': getattr(item, 'effective_to', None).isoformat() if getattr(item, 'effective_to', None) else None,
        })
    return snapshot_rows


def _salary_snapshot_to_earnings(snapshot_rows, ratio=1.0):
    normalized_ratio = max(0.0, min(1.0, float(ratio or 0)))
    rows = []
    for item in snapshot_rows if isinstance(snapshot_rows, list) else []:
        if not isinstance(item, dict):
            continue
        component = str(item.get('component_name') or item.get('component') or '').strip()
        if not component:
            continue
        monthly_amount = _round2(item.get('monthly_amount') or item.get('amount') or 0)
        rows.append({
            'component': component,
            'amount': _round2(monthly_amount * normalized_ratio),
        })
    return rows


def _get_or_create_payroll_profile(org_id, user):
    profile = PayrollProfile.objects.filter(org_id=org_id, user=user).first()
    if profile:
        return profile

    user_profile = _get_user_profile_object(user)
    bank_name = getattr(user_profile, 'bank_name', '') if user_profile else ''
    bank_account = getattr(user_profile, 'bank_account_number', '') if user_profile else ''
    base_gross = Decimal(str(_employee_base_gross_value(org_id, user) or 0)).quantize(Decimal('0.01'))

    return PayrollProfile.objects.create(
        org_id=org_id,
        user=user,
        employee_code='',
        pan_number='',
        uan_number='',
        bank_name=bank_name,
        bank_account_number=bank_account,
        base_monthly_gross=base_gross,
        tax_regime='new',
        payment_mode='NEFT',
        is_active=True,
    )


def _build_transient_payroll_profile(org_id, user):
    user_profile = _get_user_profile_object(user)
    bank_name = getattr(user_profile, 'bank_name', '') if user_profile else ''
    bank_account = getattr(user_profile, 'bank_account_number', '') if user_profile else ''
    base_gross = Decimal(str(_employee_base_gross_value(org_id, user) or 0)).quantize(Decimal('0.01'))
    return PayrollProfile(
        org_id=org_id,
        user=user,
        employee_code='',
        pan_number='',
        uan_number='',
        bank_name=bank_name,
        bank_account_number=bank_account,
        base_monthly_gross=base_gross,
        tax_regime='new',
        payment_mode='NEFT',
        is_active=True,
    )


def _build_workforce_department_map(org_id, users):
    if not org_id or not users:
        return {}

    members = list(
        WorkforceMember.objects.select_related('department').filter(
            org_id=org_id,
            is_archived=False,
        )
    )
    by_email = {}
    by_name = {}
    for member in members:
        member_email = str(member.email or '').strip().lower()
        member_name = str(member.full_name or '').strip().lower()
        if member_email and member_email not in by_email:
            by_email[member_email] = member
        if member_name and member_name not in by_name:
            by_name[member_name] = member

    mapping = {}
    for user in users:
        matched = None
        user_email = str(user.email or '').strip().lower()
        if user_email:
            matched = by_email.get(user_email)
        if matched is None:
            user_name = str(_user_full_name(user) or '').strip().lower()
            if user_name:
                matched = by_name.get(user_name)
        department_name = ''
        if matched and matched.department:
            department_name = matched.department.name
        mapping[user.id] = department_name
    return mapping


def _build_workforce_member_map(org_id, users):
    if not org_id or not users:
        return {}

    members = list(
        WorkforceMember.objects.select_related('department').filter(
            org_id=org_id,
            is_archived=False,
        )
    )

    by_email = {}
    by_name = {}
    for member in members:
        member_email = str(member.email or '').strip().lower()
        member_name = str(member.full_name or '').strip().lower()
        if member_email and member_email not in by_email:
            by_email[member_email] = member
        if member_name and member_name not in by_name:
            by_name[member_name] = member

    mapping = {}
    for user in users:
        matched = None
        user_email = str(user.email or '').strip().lower()
        if user_email:
            matched = by_email.get(user_email)
        if matched is None:
            user_name = str(_user_full_name(user) or '').strip().lower()
            if user_name:
                matched = by_name.get(user_name)
        mapping[user.id] = matched
    return mapping


def _attendance_month_summary(org_id, user, month_start):
    from django.conf import settings
    from core.models import WorkforceMember

    first_day, last_day = _parse_month_bounds(month_start.strftime('%Y-%m'))
    month_days = _month_days(first_day, last_day)

    # 1. Fetch user's joining & leaving dates from WorkforceMember
    joining_date = None
    leaving_date = None
    if user.email:
        member = WorkforceMember.objects.filter(org_id=org_id, email__iexact=user.email, is_archived=False).first()
    else:
        member = None

    if not member:
        full_name = f"{user.first_name} {user.last_name}".strip()
        if not full_name and hasattr(user, 'profile') and user.profile.full_name:
            full_name = user.profile.full_name.strip()
        if full_name:
            member = WorkforceMember.objects.filter(org_id=org_id, full_name__iexact=full_name, is_archived=False).first()

    if member:
        joining_date = member.date_of_joining
        leaving_date = member.date_of_leaving

    # Default fallbacks
    if not joining_date:
        joining_date = user.date_joined.date() if user.date_joined else first_day

    # 2. Fetch approved entries
    entries = list(
        AttendanceEntry.objects.filter(
            org_id=org_id,
            user=user,
            entry_date__gte=first_day,
            entry_date__lte=last_day,
            approval_status='approved',
            is_active=True,
        ).order_by('-updated_at')
    )
    effective = _pick_effective_entries(entries)
    rb = _effective_rulebook(user)

    payable_days = 0.0
    for day_value in month_days:
        # Check mid-month joiner/leaver bounds
        if day_value < joining_date:
            continue
        if leaving_date and day_value > leaving_date:
            continue

        entry = effective.get((user.id, day_value))
        status_value = entry.status if entry else 'absent'

        # Non-working day overrides (if missing entry)
        if status_value == 'absent':
            # Check Saturday policy (weekends)
            if getattr(settings, 'USE_SATURDAY_POLICY', False):
                if not _is_working_day(day_value, rb):
                    status_value = 'present'
            # Check Public Holiday calendar
            if status_value == 'absent' and getattr(settings, 'USE_HOLIDAY_CALENDAR', False):
                if is_holiday(org_id, day_value):
                    status_value = 'present'

        if status_value in PAYROLL_PRESENT_STATUSES:
            payable_days += 1.0
        elif status_value == 'half_day':
            payable_days += 0.5

    # Apply granular late deductions if flag is active
    if getattr(settings, 'USE_GRANULAR_DEDUCTIONS', False):
        total_deductions_days = sum(
            float(e.salary_deduction_days or 0)
            for e in entries
            if e.status not in ('absent', 'half_day') and joining_date <= e.entry_date <= (leaving_date or last_day)
        )
        payable_days = max(0.0, payable_days - total_deductions_days)

    working_days = float(len(month_days))
    present_days = _round2(payable_days)
    lop_days = _round2(max(0.0, working_days - payable_days))
    return working_days, present_days, lop_days


def _normalize_breakup_rows(raw_rows):
    rows = []
    values = raw_rows if isinstance(raw_rows, list) else []
    for item in values:
        if not isinstance(item, dict):
            continue
        component = str(item.get('component') or item.get('name') or item.get('label') or '').strip()
        if not component:
            continue
        amount_value = item.get('amount') if item.get('amount') is not None else item.get('value')
        rows.append({'component': component, 'amount': _round2(amount_value or 0)})
    return rows




def _fetch_approved_expense_earnings(org_id, user, month_start):
    """Return a single consolidated Expense Reimbursement row for all approved HR expenses in the payroll month."""
    first_day = month_start
    if first_day.month == 12:
        last_day = date(first_day.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(first_day.year, first_day.month + 1, 1) - timedelta(days=1)

    expenses = ExpenseEntry.objects.filter(
        org_id=org_id,
        user=user,
        status__in=['Dept Head Approved', 'Finance Reviewed'],
        transaction_type='expense',
        spent_on__gte=first_day,
        spent_on__lte=last_day,
    ).values('amount')

    total = _round2(sum(_round2(item.get('amount') or 0) for item in expenses))
    if total <= 0:
        return []
    return [{'component': 'Expense Reimbursement', 'amount': total, 'is_expense': True}]


def _default_breakups(gross_amount, total_deductions):
    gross_amount = _round2(gross_amount)
    total_deductions = _round2(total_deductions)

    basic = _round2(gross_amount * 0.50)
    hra = _round2(gross_amount * 0.25)
    conveyance = _round2(gross_amount * 0.04)
    medical = _round2(gross_amount * 0.03)
    special = _round2(max(0.0, gross_amount - basic - hra - conveyance - medical))

    earnings = [
        {'component': 'Basic Pay', 'amount': basic},
        {'component': 'House Rent Allowance', 'amount': hra},
        {'component': 'Special Allowance', 'amount': special},
        {'component': 'Conveyance', 'amount': conveyance},
        {'component': 'Medical Allowance', 'amount': medical},
    ]

    remaining = total_deductions
    pf = _round2(min(remaining, basic * 0.12))
    remaining = _round2(max(0.0, remaining - pf))
    professional_tax = _round2(min(remaining, 200 if gross_amount > 0 else 0))
    remaining = _round2(max(0.0, remaining - professional_tax))
    tds = _round2(remaining)

    deductions = [
        {'component': 'Provident Fund', 'amount': pf},
        {'component': 'Professional Tax', 'amount': professional_tax},
        {'component': 'TDS', 'amount': tds},
    ]
    return earnings, deductions


def _compute_default_monthly_payroll(org_id, user, month_start, payroll_profile):
    working_days, present_days, lop_days = _attendance_month_summary(org_id, user, month_start)
    salary_structure = _ensure_default_salary_structures(
        org_id,
        user,
        payroll_profile,
        month_start=month_start,
    )
    salary_snapshot = _salary_structure_rows_to_snapshot(salary_structure)
    salary_version = _salary_structure_version(salary_structure)

    proration_ratio = (present_days / working_days) if working_days > 0 else 0.0
    monthly_structure_total = _salary_structure_totals(salary_structure).get('monthly', 0)
    base_gross = monthly_structure_total if monthly_structure_total > 0 else _employee_base_gross_value(
        org_id,
        user,
        payroll_profile,
    )
    base_gross = _round2(base_gross)

    salary_gross = _round2(base_gross * proration_ratio) if working_days > 0 else 0.0

    # Include approved HR expense reimbursements in total earnings
    expense_earnings = _fetch_approved_expense_earnings(org_id, user, month_start)
    expense_total = _round2(sum(float(item.get('amount') or 0) for item in expense_earnings))

    gross_amount = _round2(salary_gross + expense_total)

    estimated_deductions = _round2((salary_gross * 0.12) + (salary_gross * 0.02) + (200 if salary_gross > 0 else 0))
    total_deductions = _round2(min(salary_gross, estimated_deductions))
    net_amount = _round2(max(0.0, gross_amount - total_deductions))

    fallback_earnings, deductions = _default_breakups(salary_gross, total_deductions)
    salary_earnings = _salary_snapshot_to_earnings(salary_snapshot, ratio=proration_ratio) or fallback_earnings
    earnings = salary_earnings + expense_earnings

    return {
        'month': month_start.isoformat(),
        'month_label': _month_label(month_start),
        'working_days': _round2(working_days),
        'present_days': _round2(present_days),
        'lop_days': _round2(lop_days),
        'gross_amount': _round2(gross_amount),
        'total_deductions': _round2(total_deductions),
        'net_amount': _round2(net_amount),
        'payment_date': None,
        'utr_reference': '',
        'payment_mode': getattr(payroll_profile, 'payment_mode', 'NEFT') or 'NEFT',
        'status': 'Processed' if net_amount > 0 else 'On Hold',
        'earnings': earnings,
        'deductions': deductions,
        'salary_structure_snapshot': salary_snapshot,
        'salary_structure_version': salary_version,
        'payslip_pdf_url': None,
        'dispute_status': 'none',
        'dispute_query': '',
        'dispute_raised_at': None,
        'dispute_resolved_at': None,
        'dispute_resolution_note': '',
        'hr_expenses': expense_earnings,
        'expense_total': expense_total,
    }


def _empty_payroll_snapshot(org_id, user, month_start, payroll_profile):
    working_days, present_days, lop_days = _attendance_month_summary(org_id, user, month_start)
    return {
        'month': month_start.isoformat(),
        'month_label': _month_label(month_start),
        'working_days': _round2(working_days),
        'present_days': _round2(present_days),
        'lop_days': _round2(lop_days),
        'gross_amount': None,
        'total_deductions': None,
        'net_amount': None,
        'payment_date': None,
        'utr_reference': '',
        'payment_mode': getattr(payroll_profile, 'payment_mode', 'NEFT') or 'NEFT',
        'status': 'Pending',
        'earnings': [],
        'deductions': [],
        'salary_structure_snapshot': [],
        'salary_structure_version': 0,
        'payslip_pdf_url': None,
        'dispute_status': 'none',
        'dispute_query': '',
        'dispute_raised_at': None,
        'dispute_resolved_at': None,
        'dispute_resolution_note': '',
    }


def _serialize_payroll_record(org_id, user, month_start, payroll_profile, payment_record):
    if payment_record is None:
        return _compute_default_monthly_payroll(org_id, user, month_start, payroll_profile)

    salary_snapshot = payment_record.salary_structure_snapshot if isinstance(payment_record.salary_structure_snapshot, list) else []
    base_earnings = _normalize_breakup_rows(payment_record.earnings_breakup)
    if not base_earnings and salary_snapshot:
        base_earnings = _salary_snapshot_to_earnings(salary_snapshot, ratio=1.0)

    deductions = _normalize_breakup_rows(payment_record.deductions_breakup)

    if not base_earnings or not deductions:
        fallback_earnings, fallback_deductions = _default_breakups(
            payment_record.gross_amount,
            payment_record.total_deductions,
        )
        base_earnings = base_earnings or fallback_earnings
        deductions = deductions or fallback_deductions

    # Fetch approved HR expense reimbursements for the month and append to earnings
    expense_earnings = _fetch_approved_expense_earnings(org_id, user, month_start)
    expense_total = _round2(sum(float(item.get('amount') or 0) for item in expense_earnings))

    # Strip any previously persisted 'Expense Reimbursement' row to avoid duplication, then re-append fresh
    base_earnings = [row for row in base_earnings if row.get('component') != 'Expense Reimbursement']
    earnings = base_earnings + expense_earnings

    # Adjust stored gross to include current expense total
    stored_gross = _round2(payment_record.gross_amount)
    base_salary_gross = _round2(sum(float(r.get('amount') or 0) for r in base_earnings))
    effective_gross = _round2(base_salary_gross + expense_total)
    # If no expense rows exist, fall back to the stored gross
    if expense_total <= 0:
        effective_gross = stored_gross

    effective_net = _round2(max(0.0, effective_gross - _round2(payment_record.total_deductions)))

    payslip_pdf_url = None
    if getattr(payment_record, 'payslip_pdf', None):
        try:
            payslip_pdf_url = payment_record.payslip_pdf.url
        except Exception:
            payslip_pdf_url = None

    payment_date_value = payment_record.payment_date.isoformat() if payment_record.payment_date else None

    return {
        'month': month_start.isoformat(),
        'month_label': _month_label(month_start),
        'working_days': _round2(payment_record.working_days),
        'present_days': _round2(payment_record.present_days),
        'lop_days': _round2(payment_record.lop_days),
        'gross_amount': effective_gross,
        'total_deductions': _round2(payment_record.total_deductions),
        'net_amount': effective_net,
        'payment_date': payment_date_value,
        'utr_reference': payment_record.utr_reference or '',
        'payment_mode': payment_record.payment_mode or 'NEFT',
        'status': payment_record.status or 'Processed',
        'earnings': earnings,
        'deductions': deductions,
        'salary_structure_snapshot': salary_snapshot,
        'salary_structure_version': int(payment_record.salary_structure_version or 0),
        'payslip_pdf_url': payslip_pdf_url,
        'dispute_status': payment_record.dispute_status or 'none',
        'dispute_query': payment_record.dispute_query or '',
        'dispute_raised_at': _to_iso_datetime(payment_record.dispute_raised_at),
        'dispute_resolved_at': _to_iso_datetime(payment_record.dispute_resolved_at),
        'dispute_resolution_note': payment_record.dispute_resolution_note or '',
        'hr_expenses': expense_earnings,
        'expense_total': expense_total,
    }


def _ensure_default_salary_structures(org_id, user, payroll_profile, month_start=None):
    # Salary structure should come from HR-defined rows only.
    _ = payroll_profile
    return _effective_salary_structures(org_id, user, month_start)


def _salary_structure_totals(rows):
    monthly_total = 0.0
    annual_total = 0.0

    for row in rows or []:
        if isinstance(row, dict):
            monthly_total += float(row.get('monthly_amount') or 0)
            annual_total += float(row.get('annual_amount') or 0)
        else:
            monthly_total += float(getattr(row, 'monthly_amount', 0) or 0)
            annual_total += float(getattr(row, 'annual_amount', 0) or 0)

    return {
        'monthly': _round2(monthly_total),
        'annual': _round2(annual_total),
    }


def _ensure_default_tax_declarations(org_id, user, financial_year):
    return list(
        PayrollTaxDeclaration.objects.filter(
        org_id=org_id,
        user=user,
        financial_year=financial_year,
        is_active=True,
        ).order_by('sort_order', 'id')
    )


def _payroll_identity_payload(user, payroll_profile, department_name=''):
    profile_obj = _get_user_profile_object(user)
    bank_name = (getattr(payroll_profile, 'bank_name', '') or getattr(profile_obj, 'bank_name', '') or '').strip()
    bank_account_number = (
        getattr(payroll_profile, 'bank_account_number', '')
        or getattr(profile_obj, 'bank_account_number', '')
        or ''
    ).strip()
    pan_number = _strip_generated_identity_value(
        getattr(payroll_profile, 'pan_number', ''),
        _default_pan_number(user.id),
    )
    uan_number = _strip_generated_identity_value(
        getattr(payroll_profile, 'uan_number', ''),
        _default_uan_number(user.id),
    )
    employee_code = _strip_generated_identity_value(
        getattr(payroll_profile, 'employee_code', ''),
        _default_employee_code(user.id),
    )

    bank_account_masked = _mask_bank_account(bank_account_number)
    bank_display = bank_account_masked if not bank_name else f"{bank_name} {bank_account_masked}"

    return {
        'user_id': user.id,
        'employee_name': _user_full_name(user),
        'employee_id': employee_code,
        'department': department_name or '',
        'pan_masked': _mask_pan_number(pan_number),
        'uan': uan_number,
        'bank_name': bank_name,
        'bank_account_masked': bank_account_masked,
        'bank_account_display': bank_display.strip(),
    }


def _payroll_tax_summary(history_rows, declarations, regime):
    annual_gross = _round2(sum(float(item.get('gross_amount') or 0) for item in history_rows))
    annual_deductions = _round2(sum(float(item.get('total_deductions') or 0) for item in history_rows))

    declared_80c = 0.0
    for item in declarations:
        if str(item.section_code or '').strip().upper() != '80C':
            continue
        declared_80c += float(item.declared_amount or 0)
    declared_80c = _round2(declared_80c)

    taxable_income = _round2(max(0.0, annual_gross - min(150000.0, declared_80c)))
    tax_rate = 0.09 if regime == 'new' else 0.13
    estimated_annual_tds = _round2(taxable_income * tax_rate)

    tds_paid = 0.0
    for row in history_rows:
        for deduction in row.get('deductions', []):
            component_name = str(deduction.get('component') or '').strip().lower()
            if 'tds' in component_name:
                tds_paid += float(deduction.get('amount') or 0)
    tds_paid = _round2(tds_paid)

    return {
        'regime': regime,
        'annual_gross': annual_gross,
        'annual_deductions': annual_deductions,
        'declared_80c': declared_80c,
        'taxable_income': taxable_income,
        'estimated_annual_tds': estimated_annual_tds,
        'tds_paid_till_date': tds_paid,
        'projected_remaining_tds': _round2(max(0.0, estimated_annual_tds - tds_paid)),
    }


def _parse_month_bounds(month_value):
    today = timezone.localdate()
    if month_value:
        try:
            year, month = str(month_value).split('-', 1)
            first_day = date(int(year), int(month), 1)
        except Exception:
            first_day = date(today.year, today.month, 1)
    else:
        first_day = date(today.year, today.month, 1)

    if first_day.month == 12:
        next_month = date(first_day.year + 1, 1, 1)
    else:
        next_month = date(first_day.year, first_day.month + 1, 1)
    last_day = next_month - timedelta(days=1)
    return first_day, last_day


def _month_days(first_day, last_day):
    days = []
    current = first_day
    while current <= last_day:
        days.append(current)
        current += timedelta(days=1)
    return days


def is_holiday(org_id, date):
    from core.models import PublicHoliday
    return PublicHoliday.objects.filter(org_id=org_id, date=date).exists()


def _is_working_day(date, rulebook):
    weekday = date.weekday()  # 0=Monday, ..., 5=Saturday, 6=Sunday

    # Check weekly off first
    if rulebook.weekly_off == 'sunday' and weekday == 6:
        return False
    if rulebook.weekly_off == 'saturday' and weekday == 5:
        return False

    # Check Saturday working options if it is Saturday and not already excluded by weekly_off
    if weekday == 5:
        if rulebook.saturday_working == 'no':
            return False
        elif rulebook.saturday_working == 'alternate':
            week_of_month = (date.day - 1) // 7 + 1
            return week_of_month % 2 == 1  # Odd weeks working, even weeks off

    return True


def _get_rulebook(user):
    """Return the AttendanceRulebook for a user, or a default dict if none exists."""
    try:
        return user.attendance_rulebook
    except AttendanceRulebook.DoesNotExist:
        return None


def _rulebook_defaults():
    """Return a namespace-like object with default rulebook values."""
    class _Defaults:
        shift_start = datetime.strptime('09:30', '%H:%M').time()
        shift_end = datetime.strptime('18:30', '%H:%M').time()
        lunch_duration_minutes = 30
        grace_period_minutes = 14
        late_deduction_threshold_minutes = 15
        half_day_late_threshold_minutes = 40
        early_leave_deduction_minutes = 10
        half_day_early_leave_minutes = 40
        regularization_limit_per_month = 3
        employee_type = 'office'
        weekly_off = 'sunday'
        saturday_working = 'yes'
        last_edited_by = None
        updated_at = None
    return _Defaults()


def _effective_rulebook(user):
    """Return the user's rulebook or default if none set."""
    rb = _get_rulebook(user)
    return rb if rb is not None else _rulebook_defaults()


def _compute_attendance_metrics(in_time, out_time, rulebook=None):
    """
    Calculate late_minutes, early_leave_minutes, and hours_worked.
    Uses per-employee rulebook if provided, otherwise global defaults.
    """
    late_minutes = 0
    early_leave_minutes = 0
    hours_worked = 0

    if rulebook is not None:
        shift_start_time = rulebook.shift_start
        shift_end_time = rulebook.shift_end
    else:
        shift_start_time = datetime.strptime(
            f'{ATTENDANCE_SHIFT_START_HOUR:02d}:{ATTENDANCE_SHIFT_START_MINUTE:02d}', '%H:%M'
        ).time()
        shift_end_time = datetime.strptime(
            f'{ATTENDANCE_SHIFT_END_HOUR:02d}:{ATTENDANCE_SHIFT_END_MINUTE:02d}', '%H:%M'
        ).time()

    ref_date = date.today()

    if in_time:
        shift_start_dt = datetime.combine(ref_date, shift_start_time)
        marked_in_dt = datetime.combine(ref_date, in_time)
        delta = (marked_in_dt - shift_start_dt).total_seconds() // 60
        late_minutes = max(0, int(delta))

    if out_time:
        shift_end_dt = datetime.combine(ref_date, shift_end_time)
        marked_out_dt = datetime.combine(ref_date, out_time)
        delta = (shift_end_dt - marked_out_dt).total_seconds() // 60
        early_leave_minutes = max(0, int(delta))

    if in_time and out_time and out_time > in_time:
        marked_in_dt = datetime.combine(ref_date, in_time)
        marked_out_dt = datetime.combine(ref_date, out_time)
        hours_worked = round((marked_out_dt - marked_in_dt).total_seconds() / 3600, 2)

    return late_minutes, early_leave_minutes, hours_worked


def _calculate_net_worked_hours(user, target_date):
    """
    Calculate the sum of durations of all AttendanceSessions for the user on target_date.
    Includes both completed sessions and the currently active session (measured up to now).
    """
    from core.models import AttendanceSession, ShopCredentials
    from django.utils import timezone
    from datetime import datetime
    import pytz

    org_id = ''
    try:
        org_id = user.team_settings.organization.organization_id
    except Exception as e:
        print("EXC TEAM_SETTINGS:", e)
        try:
            org_id = user.shop_credentials.organization_id
        except Exception as e2:
            print("EXC SHOP_CREDS:", e2)
            pass

    tz_name = 'Asia/Kolkata'
    if org_id:
        try:
            org = ShopCredentials.objects.filter(organization_id=org_id).first()
            if org and org.timezone:
                tz_name = org.timezone
        except Exception:
            pass

    try:
        tz = pytz.timezone(tz_name)
    except Exception:
        tz = pytz.timezone('Asia/Kolkata')

    local_start = tz.localize(datetime.combine(target_date, datetime.min.time()))
    local_end = tz.localize(datetime.combine(target_date, datetime.max.time()))

    utc_start = local_start.astimezone(pytz.utc)
    utc_end = local_end.astimezone(pytz.utc)

    sessions = AttendanceSession.objects.filter(
        user=user,
        login_at__gte=utc_start,
        login_at__lte=utc_end
    )

    print("--- DEBUG NET WORKED ---")
    print("USER:", user, "DATE:", target_date, "ORG:", org_id, "TZ:", tz_name)
    print("UTC START:", utc_start, "UTC END:", utc_end)
    print("SESSIONS FILTERED COUNT:", sessions.count())
    for s in AttendanceSession.objects.filter(user=user):
        print("ALL SESSIONS FOR USER:", s.login_at, s.logout_at)

    total_seconds = 0.0
    now = timezone.now()

    for session in sessions:
        start = session.login_at
        end = session.logout_at or now
        if end > start:
            total_seconds += (end - start).total_seconds()

    return round(total_seconds / 3600.0, 2)


def _auto_compute_status(in_time, out_time, rulebook=None, hours_worked=None):
    """
    Auto-Status Engine — determine status + deduction based on rulebook rules.

    Rule Matrix:
      No attendance       → Absent, full deduct
      0–grace min late    → Present, warning (no deduct)
      grace+1–39 min late → Present, 1hr deduct
      40+ min late        → half_day (first half absent), half deduct
      Left 0–9 min early  → Present, no deduct
      Left 10–39 min early → Present, 1hr deduct
      Left 40+ min early  → half_day (second half absent), half deduct

    Returns: (status, deduction_days, late_minutes, early_leave_minutes, hours_worked, score_points)
    """
    rb = rulebook if rulebook is not None else _rulebook_defaults()

    # No punch-in/out → Absent
    if not in_time and not out_time:
        return 'absent', DEDUCTION_FULL_DAY, 0, 0, 0, 0

    late_minutes, early_leave_minutes, calculated_hours = _compute_attendance_metrics(
        in_time, out_time, rulebook=rb
    )

    if hours_worked is None:
        hours_worked = calculated_hours

    # Determine arrival-based rule
    arrival_status = 'present'
    arrival_deduction = DEDUCTION_NONE
    if late_minutes > rb.half_day_late_threshold_minutes:
        arrival_status = 'half_day'
        arrival_deduction = DEDUCTION_HALF_DAY
    elif late_minutes > rb.grace_period_minutes:
        arrival_deduction = DEDUCTION_ONE_HOUR

    # Determine departure-based rule
    departure_status = 'present'
    departure_deduction = DEDUCTION_NONE
    if early_leave_minutes >= rb.half_day_early_leave_minutes:
        departure_status = 'half_day'
        departure_deduction = DEDUCTION_HALF_DAY
    elif early_leave_minutes >= rb.early_leave_deduction_minutes:
        departure_deduction = DEDUCTION_ONE_HOUR

    # Merge: if either says half_day, result is half_day; deductions accumulate (cap at 1.0)
    if arrival_status == 'half_day' or departure_status == 'half_day':
        final_status = 'half_day'
    else:
        final_status = 'present'

    total_deduction = min(1.0, arrival_deduction + departure_deduction)

    if total_deduction >= 1.0 and final_status == 'half_day':
        final_status = 'absent'

    # Attendance score (100 base, deduct for issues)
    score = 100
    if final_status == 'absent':
        score = 0
    elif final_status == 'half_day':
        score = 50
    elif total_deduction == DEDUCTION_ONE_HOUR:
        score = 85  # minor deduction
    elif late_minutes > 0 and late_minutes <= rb.grace_period_minutes:
        score = 95  # warning only

    # Enforce minimum hours worked rule if checkout occurred (out_time is not None)
    if out_time is not None:
        if hours_worked < 3.0:
            final_status = 'absent'
            total_deduction = DEDUCTION_FULL_DAY
            score = 0
        elif hours_worked < 6.0:
            if final_status != 'absent':
                final_status = 'half_day'
                total_deduction = max(total_deduction, DEDUCTION_HALF_DAY)
                score = min(score, 50)

    return final_status, total_deduction, late_minutes, early_leave_minutes, hours_worked, score


def _should_lock_entry(entry_date):
    """Return True if it's past 10PM on the same day as entry_date (shift lock)."""
    now_local = timezone.localtime(timezone.now())
    today = now_local.date()
    if entry_date == today and now_local.hour >= ATTENDANCE_LOCK_HOUR:
        return True
    return False


def _pick_effective_entries(entries):
    # Select one effective row per (user, date): prefer approved, otherwise latest pending.
    selected = {}
    for entry in entries:
        key = (entry.user_id, entry.entry_date)
        current = selected.get(key)
        if current is None:
            selected[key] = entry
            continue

        if current.approval_status == 'approved':
            if entry.approval_status == 'approved' and entry.updated_at > current.updated_at:
                selected[key] = entry
            continue

        if entry.approval_status == 'approved':
            selected[key] = entry
            continue

        if entry.updated_at > current.updated_at:
            selected[key] = entry

    return selected


def _status_payable_value(status_value):
    if status_value in {'present', 'wfh', 'on_duty', 'leave'}:
        return 1.0
    if status_value == 'half_day':
        return 0.5
    return 0.0


def _organization_users(org_id):
    if not org_id:
        return User.objects.none()
    return User.objects.filter(is_active=True).filter(
        Q(team_settings__organization__organization_id=org_id)
        | Q(shop_credentials__organization_id=org_id)
    ).distinct().order_by('first_name', 'username', 'id')


def _parse_date_value(raw_value):
    if isinstance(raw_value, date):
        return raw_value
    if not raw_value:
        return None
    try:
        return date.fromisoformat(str(raw_value))
    except Exception:
        return None


def _parse_time_value(raw_value):
    if raw_value in (None, ''):
        return None
    if hasattr(raw_value, 'hour') and hasattr(raw_value, 'minute'):
        return raw_value

    raw_text = str(raw_value).strip()
    if not raw_text:
        return None

    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(raw_text, fmt).time()
        except ValueError:
            continue
    return None


def _to_iso_datetime(value):
    return value.isoformat() if value else None


def _actor_display_name(user):
    if not user:
        return ''
    return user.get_full_name() or user.first_name or user.username or user.email or ''


def _expense_status_label(status_value):
    normalized = str(status_value or '').strip()
    # Pass through valid model status values directly
    _VALID_STATUSES = {'Draft', 'Submitted', 'Dept Head Approved', 'Partially Approved', 'Finance Reviewed', 'Paid', 'Rejected'}
    if normalized in _VALID_STATUSES:
        return normalized
    # Legacy lowercase / underscore handling
    lower = normalized.lower()
    if lower in ('dept_head_approved', 'dept head approved', 'approved'):
        return 'Dept Head Approved'
    if lower in ('partially_approved', 'partially approved'):
        return 'Partially Approved'
    if lower in ('finance_reviewed', 'finance reviewed'):
        return 'Finance Reviewed'
    if lower == 'paid':
        return 'Paid'
    if lower == 'rejected':
        return 'Rejected'
    if lower == 'submitted':
        return 'Submitted'
    return 'Draft'


def _is_effectively_rejected(item):
    """
    Mirrors the frontend isEffectivelyRejected() logic:
      • DB status is 'Rejected' (any casing), OR
      • rejection_reason field is non-empty, OR
      • the last workflow step label contains 'reject'
    This prevents the mismatch where the DB status is still 'Submitted'
    but the expense has been functionally rejected via the workflow trail.
    """
    status_label = _expense_status_label(item.status)
    if status_label == 'Rejected':
        return True
    if str(getattr(item, 'rejection_reason', '') or '').strip():
        return True
    workflow_steps = item.workflow_steps if isinstance(item.workflow_steps, list) else []
    if workflow_steps:
        last_step = workflow_steps[-1]
        step_label = str(
            last_step.get('step') or last_step.get('action') or last_step.get('status') or ''
        ).lower()
        if 'reject' in step_label:
            return True
    return False


def _expense_amount_value(amount_value):
    return _round2(amount_value or 0)


def _expense_receipt_url(request, expense):
    if not getattr(expense, 'receipt', None):
        return None
    try:
        url = _cloudinary_private_download_link(expense.receipt, attachment=False)
        if url:
            return url
        raw_url = expense.receipt.url
        return request.build_absolute_uri(raw_url) if request else raw_url
    except Exception:
        LOGGER.debug("Failed to resolve receipt URL for expense %s", getattr(expense, 'id', '?'))
        return None


def _expense_entry_payload(request, expense, user_obj=None, department_name=''):
    user_ref = user_obj or getattr(expense, 'user', None)
    user_name = _user_full_name(user_ref) if user_ref else ''
    user_email = str(getattr(user_ref, 'email', '') or '').strip() if user_ref else ''

    workflow_steps = expense.workflow_steps if isinstance(expense.workflow_steps, list) else []

    return {
        'id': expense.id,
        'user_id': expense.user_id,
        'member_name': user_name,
        'member_email': user_email,
        'department': expense.department or department_name or '',
        'transaction_type': expense.transaction_type,
        'category': expense.category,
        'amount': _expense_amount_value(expense.amount),
        'approved_amount': _expense_amount_value(expense.approved_amount) if expense.approved_amount is not None else None,
        'spent_on': expense.spent_on.isoformat() if expense.spent_on else None,
        'bill_date': expense.bill_date.isoformat() if expense.bill_date else None,
        'status': _expense_status_label(expense.status),
        'receipt_url': _expense_receipt_url(request, expense),
        'notes': str(expense.notes or '').strip(),
        'rejection_reason': str(expense.rejection_reason or '').strip(),
        # Approval trail
        'dept_approved_by': _actor_display_name(getattr(expense, 'dept_approved_by', None)),
        'dept_approved_at': _to_iso_datetime(expense.dept_approved_at) if expense.dept_approved_at else None,
        'finance_reviewed_by': _actor_display_name(getattr(expense, 'finance_reviewed_by', None)),
        'finance_reviewed_at': _to_iso_datetime(expense.finance_reviewed_at) if expense.finance_reviewed_at else None,
        'paid_by': _actor_display_name(getattr(expense, 'paid_by', None)),
        'paid_at': _to_iso_datetime(expense.paid_at) if expense.paid_at else None,
        # Payment
        'payment_date': expense.payment_date.isoformat() if expense.payment_date else None,
        'payment_method': str(expense.payment_method or '').strip(),
        # Finance GL
        'finance_status': str(expense.finance_status or 'draft'),
        'finance_entry_id': expense.finance_entry_id,
        # Full audit trail
        'workflow_steps': workflow_steps,
        'created_at': _to_iso_datetime(expense.created_at),
        'updated_at': _to_iso_datetime(expense.updated_at),
    }


def _expense_manager_name(workforce_member):
    if not workforce_member:
        return ''
    extra_data = workforce_member.extra_data if isinstance(workforce_member.extra_data, dict) else {}
    manager_name = (
        extra_data.get('manager_name')
        or extra_data.get('manager')
        or extra_data.get('reporting_to')
        or extra_data.get('reporting_manager')
        or ''
    )
    return str(manager_name or '').strip()


def _expense_employee_code(user_obj, workforce_member):
    if workforce_member:
        extra_data = workforce_member.extra_data if isinstance(workforce_member.extra_data, dict) else {}
        candidate = (
            extra_data.get('employee_id')
            or extra_data.get('employee_code')
            or extra_data.get('emp_id')
            or ''
        )
        candidate = str(candidate or '').strip()
        if candidate:
            return candidate
    return f"EMP-{int(user_obj.id):04d}"


def _get_or_create_payroll_run(org_id, month_start):
    run, _ = PayrollRun.objects.get_or_create(
        org_id=org_id,
        month=month_start,
    )
    return run


def _serialize_payroll_run_state(run):
    if run.is_locked:
        stage = 'locked'
    elif run.finance_approved_at:
        stage = 'finance_approved'
    elif run.hr_approved_at:
        stage = 'hr_approved'
    elif run.calculation_run_at:
        stage = 'calculated'
    elif run.attendance_locked_at:
        stage = 'attendance_locked'
    else:
        stage = 'draft'

    return {
        'stage': stage,
        'is_locked': bool(run.is_locked),
        'attendance_locked': bool(run.attendance_locked_at),
        'calculation_completed': bool(run.calculation_run_at),
        'hr_approved': bool(run.hr_approved_at),
        'finance_approved': bool(run.finance_approved_at),
        'payslips_generated': bool(run.payslips_generated_at),
        'bank_file_generated': bool(run.bank_file_generated_at),
        'gl_posted': bool(run.gl_posted_at),
        'gl_reference': run.gl_reference or '',
        'exception_count': int(run.exception_count or 0),
        'attendance_locked_at': _to_iso_datetime(run.attendance_locked_at),
        'calculation_run_at': _to_iso_datetime(run.calculation_run_at),
        'hr_approved_at': _to_iso_datetime(run.hr_approved_at),
        'finance_approved_at': _to_iso_datetime(run.finance_approved_at),
        'payslips_generated_at': _to_iso_datetime(run.payslips_generated_at),
        'bank_file_generated_at': _to_iso_datetime(run.bank_file_generated_at),
        'gl_posted_at': _to_iso_datetime(run.gl_posted_at),
        'locked_at': _to_iso_datetime(run.locked_at),
        'attendance_locked_by': _actor_display_name(run.attendance_locked_by),
        'calculation_run_by': _actor_display_name(run.calculation_run_by),
        'hr_approved_by': _actor_display_name(run.hr_approved_by),
        'finance_approved_by': _actor_display_name(run.finance_approved_by),
        'payslips_generated_by': _actor_display_name(run.payslips_generated_by),
        'bank_file_generated_by': _actor_display_name(run.bank_file_generated_by),
        'gl_posted_by': _actor_display_name(run.gl_posted_by),
        'locked_by': _actor_display_name(run.locked_by),
    }


def _payslip_file_url(payment_record):
    if not payment_record or not getattr(payment_record, 'payslip_pdf', None):
        return None
    try:
        return payment_record.payslip_pdf.url
    except Exception:
        return None


def _build_payslip_pdf_bytes(company, employee, snapshot):
    if not REPORTLAB_AVAILABLE or not canvas or not A4:
        raise RuntimeError('reportlab package is not available for payslip PDF generation.')

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4

    company_name = str((company or {}).get('name') or '').strip() or 'Company'
    company_address = str((company or {}).get('address') or '').strip()
    employee_name = str((employee or {}).get('employee_name') or '').strip() or 'Employee'
    employee_id = str((employee or {}).get('employee_id') or '').strip() or '-'

    y = page_height - 48
    pdf.setFont('Helvetica-Bold', 15)
    pdf.drawString(40, y, 'Payslip')
    pdf.setFont('Helvetica', 10)
    pdf.drawRightString(page_width - 40, y, str(snapshot.get('month_label') or snapshot.get('month') or ''))

    y -= 24
    pdf.setFont('Helvetica-Bold', 12)
    pdf.drawString(40, y, company_name)
    y -= 14
    pdf.setFont('Helvetica', 9)
    if company_address:
        pdf.drawString(40, y, company_address[:110])

    y -= 24
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(40, y, 'Employee')
    pdf.drawString(250, y, employee_name[:45])
    y -= 14
    pdf.drawString(40, y, 'Employee ID')
    pdf.setFont('Helvetica', 10)
    pdf.drawString(250, y, employee_id[:40])

    y -= 22
    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(40, y, 'Earnings')
    pdf.drawRightString(page_width / 2 - 20, y, 'Amount')
    pdf.drawString(page_width / 2 + 20, y, 'Deductions')
    pdf.drawRightString(page_width - 40, y, 'Amount')

    y -= 10
    pdf.line(40, y, page_width - 40, y)
    y -= 14

    earnings = snapshot.get('earnings') if isinstance(snapshot.get('earnings'), list) else []
    deductions = snapshot.get('deductions') if isinstance(snapshot.get('deductions'), list) else []
    row_count = max(len(earnings), len(deductions), 1)

    for index in range(row_count):
        earning_row = earnings[index] if index < len(earnings) else {}
        deduction_row = deductions[index] if index < len(deductions) else {}

        if y < 120:
            pdf.showPage()
            y = page_height - 60
            pdf.setFont('Helvetica', 9)

        pdf.setFont('Helvetica', 9)
        pdf.drawString(40, y, str(earning_row.get('component') or '-')[:28])
        pdf.drawRightString(page_width / 2 - 20, y, f"{_round2(earning_row.get('amount') or 0):.2f}")
        pdf.drawString(page_width / 2 + 20, y, str(deduction_row.get('component') or '-')[:28])
        pdf.drawRightString(page_width - 40, y, f"{_round2(deduction_row.get('amount') or 0):.2f}")
        y -= 14

    y -= 6
    pdf.line(40, y, page_width - 40, y)
    y -= 16

    pdf.setFont('Helvetica-Bold', 10)
    pdf.drawString(40, y, f"Gross: {_round2(snapshot.get('gross_amount') or 0):.2f}")
    pdf.drawString(220, y, f"Deductions: {_round2(snapshot.get('total_deductions') or 0):.2f}")
    pdf.drawRightString(page_width - 40, y, f"Net: {_round2(snapshot.get('net_amount') or 0):.2f}")

    y -= 18
    pdf.setFont('Helvetica', 9)
    pdf.drawString(40, y, f"Payment Date: {snapshot.get('payment_date') or '-'}")
    pdf.drawString(220, y, f"UTR: {snapshot.get('utr_reference') or '-'}")
    pdf.drawRightString(page_width - 40, y, f"Mode: {snapshot.get('payment_mode') or '-'}")

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


def _generate_payslip_pdf_for_record(org_id, payment_record, payroll_profile, department_name=''):
    company = _company_payload(org_id)
    employee = _payroll_identity_payload(payment_record.user, payroll_profile, department_name)
    snapshot = _serialize_payroll_record(
        org_id,
        payment_record.user,
        payment_record.month,
        payroll_profile,
        payment_record,
    )

    pdf_bytes = _build_payslip_pdf_bytes(company, employee, snapshot)
    filename = f"payslip_{payment_record.user_id}_{payment_record.month.strftime('%Y_%m')}.pdf"
    payment_record.payslip_pdf.save(filename, ContentFile(pdf_bytes), save=False)
    payment_record.save(update_fields=['payslip_pdf', 'updated_at'])
    return _payslip_file_url(payment_record)


def _send_payslip_notification(record, actor_user):
    month_label = _month_label(record.month)
    message = f"Payslip for {month_label} is now available."

    try:
        push_unified_notification(
            recipient=record.user,
            actor=actor_user,
            module='notes',
            action='reminder',
            title='Payslip Generated',
            message=message,
            entity_type='payroll',
            entity_id=str(record.id),
            deep_link={
                'page': '/mydesk/payroll',
                'section': 'payroll',
                'month': record.month.strftime('%Y-%m'),
            },
            metadata={
                'month': record.month.strftime('%Y-%m'),
                'payslip_pdf_url': _payslip_file_url(record),
            },
        )
    except Exception:
        pass

    if record.user and record.user.email:
        sender = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        send_mail(
            subject=f'Payslip generated for {month_label}',
            message=(
                f"Hello {(_user_full_name(record.user) or '').strip()},\n\n"
                f"Your payslip for {month_label} is now available in MyDesk payroll."
            ),
            from_email=sender,
            recipient_list=[record.user.email],
            fail_silently=True,
        )


def _upsert_payroll_payment_record_from_snapshot(
    org_id,
    user,
    month_start,
    snapshot,
    actor_user,
    existing_record=None,
    default_status='Processed',
):
    earnings_rows = _normalize_breakup_rows(snapshot.get('earnings'))
    deduction_rows = _normalize_breakup_rows(snapshot.get('deductions'))
    salary_snapshot_rows = snapshot.get('salary_structure_snapshot') if isinstance(snapshot.get('salary_structure_snapshot'), list) else []
    salary_structure_version = int(snapshot.get('salary_structure_version') or 0)

    if not earnings_rows or not deduction_rows:
        fallback_earnings, fallback_deductions = _default_breakups(
            snapshot.get('gross_amount'),
            snapshot.get('total_deductions'),
        )
        earnings_rows = earnings_rows or fallback_earnings
        deduction_rows = deduction_rows or fallback_deductions

    if not salary_snapshot_rows:
        salary_rows = _effective_salary_structures(org_id, user, month_start)
        salary_snapshot_rows = _salary_structure_rows_to_snapshot(salary_rows)
        if salary_structure_version <= 0:
            salary_structure_version = _salary_structure_version(salary_rows)

    status_value = str(snapshot.get('status') or '').strip() or default_status
    allowed_statuses = {choice[0] for choice in PayrollPaymentRecord.STATUS_CHOICES}
    if status_value not in allowed_statuses:
        status_value = default_status if default_status in allowed_statuses else 'Processed'

    payment_date = _parse_date_value(snapshot.get('payment_date'))

    payload = {
        'working_days': Decimal(str(snapshot.get('working_days') or 0)),
        'present_days': Decimal(str(snapshot.get('present_days') or 0)),
        'lop_days': Decimal(str(snapshot.get('lop_days') or 0)),
        'gross_amount': Decimal(str(snapshot.get('gross_amount') or 0)),
        'total_deductions': Decimal(str(snapshot.get('total_deductions') or 0)),
        'net_amount': Decimal(str(snapshot.get('net_amount') or 0)),
        'payment_date': payment_date,
        'utr_reference': str(snapshot.get('utr_reference') or '')[:120],
        'payment_mode': str(snapshot.get('payment_mode') or 'NEFT')[:30],
        'status': status_value,
        'earnings_breakup': earnings_rows,
        'deductions_breakup': deduction_rows,
        'salary_structure_snapshot': salary_snapshot_rows,
        'salary_structure_version': max(0, salary_structure_version),
    }

    if existing_record:
        for key, value in payload.items():
            setattr(existing_record, key, value)
        existing_record.save()
        return existing_record, False

    created = PayrollPaymentRecord.objects.create(
        org_id=org_id,
        user=user,
        month=month_start,
        created_by=actor_user,
        remarks='',
        **payload,
    )
    return created, True


def _build_payroll_exception_report(month_start, users, record_map, profile_map, workforce_member_map):
    first_day, last_day = _parse_month_bounds(month_start.strftime('%Y-%m'))
    exceptions = []

    for user in users:
        employee_name = _user_full_name(user)
        payroll_profile = profile_map.get(user.id)
        employee_code = _strip_generated_identity_value(
            getattr(payroll_profile, 'employee_code', '') if payroll_profile else '',
            _default_employee_code(user.id),
        ) or '-'
        record = record_map.get(user.id)

        if not record:
            exceptions.append({
                'user_id': user.id,
                'employee_name': employee_name,
                'employee_id': employee_code,
                'issue_code': 'missing_record',
                'severity': 'high',
                'message': 'Payroll record missing for the selected month.',
            })
            continue

        gross_amount = float(record.gross_amount or 0)
        net_amount = float(record.net_amount or 0)
        working_days = float(record.working_days or 0)
        present_days = float(record.present_days or 0)
        lop_days = float(record.lop_days or 0)

        if net_amount < 0:
            exceptions.append({
                'user_id': user.id,
                'employee_name': employee_name,
                'employee_id': employee_code,
                'issue_code': 'negative_salary',
                'severity': 'high',
                'message': f'Net salary is negative ({_round2(net_amount)}).',
            })

        expected_lop = _round2(max(0.0, working_days - present_days))
        if abs(expected_lop - _round2(lop_days)) > 0.05:
            exceptions.append({
                'user_id': user.id,
                'employee_name': employee_name,
                'employee_id': employee_code,
                'issue_code': 'lop_mismatch',
                'severity': 'medium',
                'message': f'LOP mismatch. Expected {expected_lop}, found {_round2(lop_days)}.',
            })

        if present_days > 0 and gross_amount <= 0:
            exceptions.append({
                'user_id': user.id,
                'employee_name': employee_name,
                'employee_id': employee_code,
                'issue_code': 'zero_pay_with_presence',
                'severity': 'high',
                'message': 'Present days exist but gross pay is zero.',
            })

        profile_obj = _get_user_profile_object(user)
        bank_account_number = (
            (getattr(payroll_profile, 'bank_account_number', '') if payroll_profile else '')
            or getattr(profile_obj, 'bank_account_number', '')
            or ''
        ).strip()
        if not bank_account_number:
            exceptions.append({
                'user_id': user.id,
                'employee_name': employee_name,
                'employee_id': employee_code,
                'issue_code': 'bank_details_missing',
                'severity': 'medium',
                'message': 'Bank account number missing for payout.',
            })

        join_date = getattr(user, 'date_joined', None)
        if join_date:
            join_day = join_date.date() if hasattr(join_date, 'date') else join_date
            if first_day <= join_day <= last_day:
                exceptions.append({
                    'user_id': user.id,
                    'employee_name': employee_name,
                    'employee_id': employee_code,
                    'issue_code': 'new_joiner',
                    'severity': 'info',
                    'message': f'Joined during this month on {join_day.isoformat()}.',
                })

        member = workforce_member_map.get(user.id)
        if member and str(member.status or '').strip().lower() == 'inactive':
            exceptions.append({
                'user_id': user.id,
                'employee_name': employee_name,
                'employee_id': employee_code,
                'issue_code': 'separation',
                'severity': 'medium',
                'message': 'Employee is marked inactive in workforce master.',
            })

    return sorted(exceptions, key=lambda item: (
        str(item.get('employee_name') or '').lower(),
        str(item.get('issue_code') or '').lower(),
    ))


def _materialize_payroll_month(org_id, month_start, actor_user):
    users = list(_organization_users(org_id))
    user_ids = [user.id for user in users]

    profile_map = {
        item.user_id: item
        for item in PayrollProfile.objects.filter(org_id=org_id, user_id__in=user_ids)
    }
    existing_record_map = {
        item.user_id: item
        for item in PayrollPaymentRecord.objects.filter(org_id=org_id, user_id__in=user_ids, month=month_start)
    }

    finalized_record_map = {}
    created_count = 0
    updated_count = 0

    with transaction.atomic():
        for user in users:
            payroll_profile = profile_map.get(user.id) or _build_transient_payroll_profile(org_id, user)
            existing_record = existing_record_map.get(user.id)
            snapshot = _serialize_payroll_record(
                org_id,
                user,
                month_start,
                payroll_profile,
                existing_record,
            )

            default_status = existing_record.status if existing_record else 'Processed'
            payment_record, created = _upsert_payroll_payment_record_from_snapshot(
                org_id=org_id,
                user=user,
                month_start=month_start,
                snapshot=snapshot,
                actor_user=actor_user,
                existing_record=existing_record,
                default_status=default_status,
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

            finalized_record_map[user.id] = payment_record

    workforce_member_map = _build_workforce_member_map(org_id, users)
    exception_report = _build_payroll_exception_report(
        month_start=month_start,
        users=users,
        record_map=finalized_record_map,
        profile_map=profile_map,
        workforce_member_map=workforce_member_map,
    )

    return {
        'users': users,
        'records': finalized_record_map,
        'created_count': created_count,
        'updated_count': updated_count,
        'exception_report': exception_report,
    }


def _build_bank_transfer_rows(org_id, month_start):
    users = list(_organization_users(org_id))
    user_ids = [item.id for item in users]

    profile_map = {
        item.user_id: item
        for item in PayrollProfile.objects.filter(org_id=org_id, user_id__in=user_ids)
    }
    record_map = {
        item.user_id: item
        for item in PayrollPaymentRecord.objects.filter(org_id=org_id, user_id__in=user_ids, month=month_start)
    }
    department_map = _build_workforce_department_map(org_id, users)

    rows = []
    for user in users:
        record = record_map.get(user.id)
        if not record:
            continue

        amount = _round2(record.net_amount)
        if amount <= 0:
            continue

        payroll_profile = profile_map.get(user.id) or _build_transient_payroll_profile(org_id, user)
        profile_obj = _get_user_profile_object(user)
        bank_name = (
            getattr(payroll_profile, 'bank_name', '')
            or getattr(profile_obj, 'bank_name', '')
            or ''
        ).strip()
        account_number = (
            getattr(payroll_profile, 'bank_account_number', '')
            or getattr(profile_obj, 'bank_account_number', '')
            or ''
        ).strip()
        ifsc_code = (
            getattr(profile_obj, 'bank_ifsc_code', '')
            or getattr(profile_obj, 'ifsc', '')
            or ''
        ).strip()

        identity = _payroll_identity_payload(user, payroll_profile, department_map.get(user.id, ''))
        rows.append({
            'user_id': user.id,
            'employee_name': identity['employee_name'],
            'employee_id': identity['employee_id'],
            'department': identity['department'],
            'bank_name': bank_name,
            'account_number': account_number,
            'ifsc': ifsc_code,
            'amount': amount,
            'payment_mode': record.payment_mode or 'NEFT',
            'utr': record.utr_reference or '',
        })

    return sorted(rows, key=lambda item: str(item.get('employee_name') or '').lower())


def _parse_mention_targets(text, org_id, actor_id):
    mentioned_names = MENTION_PATTERN.findall(text or '')
    if not mentioned_names:
        return User.objects.none()

    query = Q()
    for name in mentioned_names:
        query |= Q(username__iexact=name) | Q(first_name__iexact=name)

    users = User.objects.filter(query).exclude(id=actor_id)
    if org_id:
        users = users.filter(
            Q(team_settings__organization__organization_id=org_id)
            | Q(shop_credentials__organization_id=org_id)
        )
    return users.distinct()


def _extract_shared_member_ids(labels):
    ids = []
    values = labels if isinstance(labels, list) else []
    for label in values:
        if not isinstance(label, str):
            continue
        if not label.startswith(SHARED_MEMBER_PREFIX):
            continue
        try:
            ids.append(int(label.replace(SHARED_MEMBER_PREFIX, '', 1)))
        except (TypeError, ValueError):
            continue
    return sorted(set(ids))


def _extract_task_assignee_ids(meta):
    parsed_ids = []
    values = meta if isinstance(meta, dict) else {}

    assignee_ids = values.get('assignee_ids') if isinstance(values.get('assignee_ids'), list) else []
    for value in assignee_ids:
        try:
            parsed_ids.append(int(value))
        except (TypeError, ValueError):
            continue

    assignee_id = values.get('assignee_id')
    if assignee_id not in (None, ''):
        try:
            parsed_ids.append(int(assignee_id))
        except (TypeError, ValueError):
            pass

    return sorted(set(parsed_ids))


def _extract_task_assigner_id(item):
    meta = item.meta if isinstance(item.meta, dict) else {}
    raw_assigned_by_id = meta.get('assigned_by_id')

    if raw_assigned_by_id not in (None, ''):
        try:
            return int(raw_assigned_by_id)
        except (TypeError, ValueError):
            pass

    return item.user_id


def _normalize_task_priority(raw_value):
    value = str(raw_value or '').strip().lower()
    if value in {'low', 'medium', 'high', 'critical'}:
        return value
    return 'medium'


def _task_priority_from_meta(meta):
    values = meta if isinstance(meta, dict) else {}
    return _normalize_task_priority(values.get('priority') or values.get('task_priority'))


def _task_comment_text(entry):
    if isinstance(entry, str):
        return entry.strip()
    if isinstance(entry, dict):
        return str(entry.get('text') or entry.get('comment') or '').strip()
    return ''


def _notify_task_assigned(item, actor, org_id, previous_assignee_ids=None):
    meta = item.meta if isinstance(item.meta, dict) else {}
    current_assignee_ids = set(_extract_task_assignee_ids(meta))
    if not current_assignee_ids:
        return

    if previous_assignee_ids is None:
        target_ids = current_assignee_ids
    else:
        previous_ids = set()
        for value in previous_assignee_ids:
            try:
                previous_ids.add(int(value))
            except (TypeError, ValueError):
                continue
        target_ids = current_assignee_ids - previous_ids

    if not target_ids:
        return

    recipients = User.objects.filter(id__in=sorted(target_ids), is_active=True)
    if org_id:
        recipients = recipients.filter(
            Q(team_settings__organization__organization_id=org_id)
            | Q(shop_credentials__organization_id=org_id)
        )

    sender_name = actor.first_name or actor.username or 'A teammate'
    task_title = (meta.get('title') or item.text or 'Task').strip() or 'Task'
    task_priority = _task_priority_from_meta(meta)

    for recipient in recipients.exclude(id=actor.id).distinct():
        push_unified_notification(
            recipient=recipient,
            actor=actor,
            module='tasks',
            action='share',
            title='Task assigned to you',
            message=f"{sender_name} assigned you a task",
            preview=task_title[:160],
            entity_type='personal_todo',
            entity_id=item.id,
            deep_link={
                'page': '/mydesk/tasks',
                'section': 'my-tasks',
                'taskId': str(item.id),
            },
            task_priority=task_priority,
        )


def _upsert_task_google_calendar_event(item):
    try:
        meta = item.meta if isinstance(item.meta, dict) else {}
        if meta.get('type') != 'task':
            return

        due_date = meta.get('dueDate')
        if not due_date:
            return
            
        assignee_id = meta.get('assignee_id')
        if assignee_id:
            user_to_sync = User.objects.filter(id=assignee_id).first()
        else:
            user_to_sync = item.user
            
        if not user_to_sync:
            return

        parsed_due = date.fromisoformat(str(due_date))
        due_time = (meta.get('dueTime') or '').strip()

        event_timezone = 'Asia/Kolkata'
        event_start_date = parsed_due.isoformat()
        event_end_date = (parsed_due + timedelta(days=1)).isoformat()

        event_start_datetime = None
        event_end_datetime = None
        if due_time:
            try:
                due_hour, due_minute = str(due_time).split(':')[:2]
                due_hour = int(due_hour)
                due_minute = int(due_minute)
                event_start_datetime = datetime.combine(parsed_due, datetime.min.time()).replace(
                    hour=due_hour,
                    minute=due_minute,
                    second=0,
                    microsecond=0,
                )
                event_end_datetime = event_start_datetime + timedelta(hours=1)
            except Exception:
                event_start_datetime = None
                event_end_datetime = None

        from core.views_calendar import _get_credentials, _invalidate_calendar_cache
        from googleapiclient.discovery import build

        creds = _get_credentials(user_to_sync)
        if not creds:
            return

        comments = meta.get('comments') if isinstance(meta.get('comments'), list) else []
        first_comment = _task_comment_text(comments[0]) if comments else ''

        base_title = (meta.get('title') or item.text or 'Task').strip() or 'Task'
        status_value = (meta.get('status') or '').strip().lower()
        calendar_title = f'Done: {base_title}' if status_value == 'done' else base_title

        event_body = {
            'summary': calendar_title,
            'description': first_comment,
            'extendedProperties': {
                'private': {
                    'bridgeworks_type': 'task',
                    'todo_id': str(item.id),
                }
            },
        }

        if event_start_datetime and event_end_datetime:
            event_body['start'] = {
                'dateTime': event_start_datetime.isoformat(),
                'timeZone': event_timezone,
            }
            event_body['end'] = {
                'dateTime': event_end_datetime.isoformat(),
                'timeZone': event_timezone,
            }
        else:
            event_body['start'] = {'date': event_start_date}
            event_body['end'] = {'date': event_end_date}

        reminder_value = (meta.get('reminderAt') or '').strip()
        if reminder_value:
            reminder_minutes = None
            try:
                normalized_reminder = reminder_value.replace('Z', '+00:00')
                reminder_dt = datetime.fromisoformat(normalized_reminder)
                if reminder_dt.tzinfo is not None:
                    reminder_dt = reminder_dt.replace(tzinfo=None)
                if event_start_datetime:
                    baseline = event_start_datetime
                else:
                    baseline = datetime.combine(parsed_due, datetime.min.time())
                minutes_delta = int((baseline - reminder_dt).total_seconds() // 60)
                reminder_minutes = max(0, min(40320, minutes_delta))
            except Exception:
                reminder_minutes = None

            if reminder_minutes is not None:
                event_body['reminders'] = {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': reminder_minutes},
                        {'method': 'email', 'minutes': reminder_minutes},
                    ],
                }
            else:
                event_body['reminders'] = {'useDefault': True}
        else:
            event_body['reminders'] = {'useDefault': True}

        service = build('calendar', 'v3', credentials=creds)
        google_event_id = meta.get('google_event_id')

        if google_event_id:
            updated_event = service.events().patch(
                calendarId='primary',
                eventId=google_event_id,
                sendUpdates='none',
                body=event_body,
            ).execute()
            meta['google_event_id'] = updated_event.get('id') or google_event_id
        else:
            created_event = service.events().insert(
                calendarId='primary',
                sendUpdates='none',
                body=event_body,
            ).execute()
            meta['google_event_id'] = created_event.get('id')

        meta['google_synced'] = bool(meta.get('google_event_id'))
        item.meta = meta
        item.save(update_fields=['meta'])
        _invalidate_calendar_cache(item.org_id, item.user_id)
    except Exception:
        return


def _delete_task_google_calendar_event(item):
    try:
        meta = item.meta if isinstance(item.meta, dict) else {}
        if meta.get('type') != 'task':
            return

        event_id = meta.get('google_event_id')
        if not event_id:
            return
            
        assignee_id = meta.get('assignee_id')
        if assignee_id:
            user_to_sync = User.objects.filter(id=assignee_id).first()
        else:
            user_to_sync = item.user
            
        if not user_to_sync:
            return

        from core.views_calendar import _get_credentials, _invalidate_calendar_cache
        from googleapiclient.discovery import build

        creds = _get_credentials(user_to_sync)
        if not creds:
            return

        service = build('calendar', 'v3', credentials=creds)
        service.events().delete(calendarId='primary', eventId=event_id, sendUpdates='none').execute()
        _invalidate_calendar_cache(item.org_id, item.user_id)
    except Exception:
        return


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


class OrgScopedBaseAPIView(APIView):
    authentication_classes = [JWTAuthentication, CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_org_id(self):
        return _get_org_id_or_none(self.request) or ''

    def scope_queryset(self, queryset, include_all_org=False):
        org_id = self.get_org_id()
        if org_id:
            return queryset.filter(org_id=org_id)
        if include_all_org:
            return queryset
        return queryset.filter(user=self.request.user, org_id='')


def _personal_todo_visible_queryset(request, todo_type=''):
    started_at = time.perf_counter()
    org_id = _get_org_id_or_none(request) or ''
    requester_id = request.user.id
    requester_id_str = str(requester_id)
    normalized_todo_type = _normalize_todo_type_filter(todo_type)

    base = PersonalTodoItem.objects.filter(org_id=org_id)
    if normalized_todo_type == 'task':
        base = base.filter(meta__type='task')
    elif normalized_todo_type == 'personal':
        base = base.filter(Q(meta__type='personal') | Q(meta__type__isnull=True))

    direct_matches = base.filter(
        Q(user=request.user)
        | Q(meta__assignee_id=requester_id)
        | Q(meta__assignee_id=requester_id_str)
    )

    assignee_array_matches = None
    if connection.vendor == 'postgresql':
        assignee_array_matches = base.filter(
            Q(meta__assignee_ids__contains=[requester_id])
            | Q(meta__assignee_ids__contains=[requester_id_str])
        )
    elif connection.vendor == 'sqlite':
        table_name = PersonalTodoItem._meta.db_table
        assignee_array_matches = base.extra(
            where=[
                (
                    'EXISTS ('
                    f"SELECT 1 FROM json_each({table_name}.meta, '$.assignee_ids') AS assignee "
                    'WHERE CAST(assignee.value AS TEXT) = %s'
                    ')'
                )
            ],
            params=[requester_id_str],
        )

    if assignee_array_matches is not None:
        try:
            queryset = (direct_matches | assignee_array_matches).distinct()
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            log_fn = LOGGER.warning if elapsed_ms >= 500 else LOGGER.info
            log_fn(
                'mydesk.todos.visibility user_id=%s org_id=%s type=%s vendor=%s path=db elapsed_ms=%.2f',
                requester_id,
                org_id,
                normalized_todo_type or 'all',
                connection.vendor,
                elapsed_ms,
            )
            return queryset
        except Exception as exc:
            LOGGER.warning(
                'mydesk.todos.visibility user_id=%s org_id=%s type=%s vendor=%s path=db-failed error=%s',
                requester_id,
                org_id,
                normalized_todo_type or 'all',
                connection.vendor,
                exc,
                exc_info=True,
            )

    assignee_ids_matches = []
    scanned_count = 0
    fallback_candidates = base.exclude(
        Q(user=request.user)
        | Q(meta__assignee_id=requester_id)
        | Q(meta__assignee_id=requester_id_str)
    )

    for item in fallback_candidates.only('id', 'meta').iterator(chunk_size=200):
        scanned_count += 1
        meta = item.meta if isinstance(item.meta, dict) else {}
        values = meta.get('assignee_ids')
        if not isinstance(values, list):
            continue
        if any(str(value) == requester_id_str for value in values if value not in (None, '')):
            assignee_ids_matches.append(item.id)

    if not assignee_ids_matches:
        queryset = direct_matches.distinct()
    else:
        queryset = (direct_matches | base.filter(id__in=assignee_ids_matches)).distinct()

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    LOGGER.warning(
        'mydesk.todos.visibility user_id=%s org_id=%s type=%s vendor=%s path=fallback scanned=%s matched=%s elapsed_ms=%.2f',
        requester_id,
        org_id,
        normalized_todo_type or 'all',
        connection.vendor,
        scanned_count,
        len(assignee_ids_matches),
        elapsed_ms,
    )
    return queryset


def _mydesk_note_visible_queryset(request):
    org_id = _get_org_id_or_none(request) or ''
    user_id = request.user.id
    shared_label = f"{SHARED_MEMBER_PREFIX}{user_id}"

    base = MyDeskNote.objects.prefetch_related('file_attachments').filter(org_id=org_id)
    
    from django.db import connection
    
    direct_matches = base.filter(user=request.user)
    
    shared_matches = None
    if connection.vendor == 'postgresql':
        shared_matches = base.filter(labels__contains=[shared_label])
    elif connection.vendor == 'sqlite':
        table_name = MyDeskNote._meta.db_table
        shared_matches = base.extra(
            where=[
                (
                    'EXISTS ('
                    f"SELECT 1 FROM json_each({table_name}.labels) AS lbl "
                    'WHERE CAST(lbl.value AS TEXT) = %s'
                    ')'
                )
            ],
            params=[shared_label],
        )

    if shared_matches is not None:
        try:
            return (direct_matches | shared_matches).distinct()
        except Exception:
            pass

    # Fallback to python list comprehension for safety
    all_notes = list(base.all())
    visible_ids = []
    for note in all_notes:
        if note.user_id == user_id:
            visible_ids.append(note.id)
        else:
            note_labels = note.labels if isinstance(note.labels, list) else []
            if shared_label in note_labels:
                visible_ids.append(note.id)
    return base.filter(id__in=visible_ids)


class MyDeskNoteListCreateView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _normalize_payload(self, request):
        data = request.data
        payload = {
            'title': data.get('title', ''),
            'content_html': data.get('content_html', ''),
        }

        if 'is_pinned' in data:
            raw_value = data.get('is_pinned')
            if isinstance(raw_value, bool):
                payload['is_pinned'] = raw_value
            elif isinstance(raw_value, str):
                payload['is_pinned'] = raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}

        for field in ['tags', 'labels', 'attachments', 'drive_links']:
            value = data.get(field)
            if value is None:
                payload[field] = []
                continue

            if isinstance(value, list):
                payload[field] = value
                continue

            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    payload[field] = parsed if isinstance(parsed, list) else []
                except Exception:
                    payload[field] = []
                continue

            payload[field] = []

        return payload

    def get(self, request):
        queryset = _mydesk_note_visible_queryset(request)
        search = (request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(title__icontains=search)
        serializer = MyDeskNoteSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        serializer = MyDeskNoteSerializer(data=self._normalize_payload(request), context={'request': request})
        serializer.is_valid(raise_exception=True)
        note = serializer.save(user=request.user, org_id=self.get_org_id())

        for uploaded in request.FILES.getlist('files'):
            MyDeskNoteAttachment.objects.create(
                note=note,
                file=uploaded,
                original_name=getattr(uploaded, 'name', '') or '',
                mime_type=getattr(uploaded, 'content_type', '') or '',
                file_size=getattr(uploaded, 'size', 0) or 0,
            )

        MyDeskNoteVersion.objects.create(
            note=note,
            title=note.title,
            content_html=note.content_html,
        )
        return Response(MyDeskNoteSerializer(note, context={'request': request}).data, status=status.HTTP_201_CREATED)


class MyDeskNoteDetailView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _normalize_payload(self, request):
        data = request.data
        payload = {}

        if 'title' in data:
            payload['title'] = data.get('title', '')
        if 'content_html' in data:
            payload['content_html'] = data.get('content_html', '')

        if 'is_pinned' in data:
            raw_value = data.get('is_pinned')
            if isinstance(raw_value, bool):
                payload['is_pinned'] = raw_value
            elif isinstance(raw_value, str):
                payload['is_pinned'] = raw_value.strip().lower() in {'1', 'true', 'yes', 'on'}

        for field in ['tags', 'labels', 'attachments', 'drive_links']:
            if field not in data:
                continue

            value = data.get(field)
            if isinstance(value, list):
                payload[field] = value
                continue

            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    payload[field] = parsed if isinstance(parsed, list) else []
                except Exception:
                    payload[field] = []
                continue

            payload[field] = []

        return payload

    def get_object(self, pk):
        queryset = _mydesk_note_visible_queryset(self.request)
        return generics.get_object_or_404(queryset, pk=pk)

    def get(self, request, pk):
        note = self.get_object(pk)
        return Response(MyDeskNoteSerializer(note, context={'request': request}).data)

    def patch(self, request, pk):
        note = self.get_object(pk)
        previous_labels = list(note.labels) if isinstance(note.labels, list) else []
        serializer = MyDeskNoteSerializer(note, data=self._normalize_payload(request), partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        for uploaded in request.FILES.getlist('files'):
            MyDeskNoteAttachment.objects.create(
                note=note,
                file=uploaded,
                original_name=getattr(uploaded, 'name', '') or '',
                mime_type=getattr(uploaded, 'content_type', '') or '',
                file_size=getattr(uploaded, 'size', 0) or 0,
            )

        if any(field in request.data for field in ['title', 'content_html']):
            create_version = request.data.get('create_version')
            if create_version is True or str(create_version).lower() in {'1', 'true', 'yes'}:
                MyDeskNoteVersion.objects.create(
                    note=note,
                    title=note.title,
                    content_html=note.content_html,
                )

        next_labels = list(note.labels) if isinstance(note.labels, list) else []
        previous_shared_ids = set(_extract_shared_member_ids(previous_labels))
        next_shared_ids = set(_extract_shared_member_ids(next_labels))
        added_shared_ids = next_shared_ids - previous_shared_ids
        if added_shared_ids:
            recipients = User.objects.filter(id__in=added_shared_ids).exclude(id=request.user.id)
            for recipient in recipients:
                push_unified_notification(
                    recipient=recipient,
                    actor=request.user,
                    module='notes',
                    action='share',
                    title='A note was shared with you',
                    message=f"{request.user.first_name or request.user.username} shared a note with you",
                    preview=(note.title or note.content_html or '')[:160],
                    entity_type='mydesk_note',
                    entity_id=note.id,
                    deep_link={
                        'page': '/mydesk/notes',
                        'section': 'my-notes',
                        'noteId': str(note.id),
                    },
                )

        return Response(MyDeskNoteSerializer(note, context={'request': request}).data)

    def delete(self, request, pk):
        note = self.get_object(pk)
        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyDeskNoteAttachmentDetailView(OrgScopedBaseAPIView):
    parser_classes = [JSONParser]

    def get_object(self, pk):
        note_queryset = _mydesk_note_visible_queryset(self.request)
        queryset = MyDeskNoteAttachment.objects.filter(note__in=note_queryset)
        return generics.get_object_or_404(queryset, pk=pk)

    def delete(self, request, pk):
        attachment = self.get_object(pk)
        try:
            if attachment.file:
                attachment.file.delete(save=False)
        except Exception:
            pass
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyDeskNoteShareView(OrgScopedBaseAPIView):
    """POST /api/mydesk/notes/<pk>/share/
    Body: { "recipient_ids": [1, 2], "message": "optional text" }
    Sends in-app notifications to each recipient.
    """
    parser_classes = [JSONParser]

    def get_note(self, pk):
        queryset = _mydesk_note_visible_queryset(self.request)
        return generics.get_object_or_404(queryset, pk=pk)

    def post(self, request, pk):
        note = self.get_note(pk)
        data = request.data or {}
        recipient_ids = data.get('recipient_ids') or []
        message = str(data.get('message') or '').strip()

        if not isinstance(recipient_ids, list) or not recipient_ids:
            return Response({'detail': 'Provide at least one recipient_id.'}, status=status.HTTP_400_BAD_REQUEST)

        org_id = self.get_org_id()
        recipients = User.objects.filter(id__in=recipient_ids).exclude(id=request.user.id)
        if org_id:
            recipients = recipients.filter(
                Q(team_settings__organization__organization_id=org_id) |
                Q(shop_credentials__organization_id=org_id)
            )
        recipients = list(recipients.distinct())

        actor_name = request.user.first_name or request.user.username or 'Someone'
        note_preview = (note.title or note.content_html or '')[:160]
        notification_message = message if message else f"{actor_name} shared a note with you"

        for recipient in recipients:
            push_unified_notification(
                recipient=recipient,
                actor=request.user,
                module='notes',
                action='share',
                title='A note was shared with you',
                message=notification_message,
                preview=note_preview,
                entity_type='mydesk_note',
                entity_id=note.id,
                deep_link={
                    'page': '/mydesk/notes',
                    'section': 'my-notes',
                    'noteId': str(note.id),
                },
            )

        # Update note labels to include the shared members
        current_labels = list(note.labels) if isinstance(note.labels, list) else []
        updated_labels = set(current_labels)
        for recipient in recipients:
            updated_labels.add(f"shared:member:{recipient.id}")
        note.labels = list(updated_labels)
        note.save()

        return Response({
            'shared_with': [r.id for r in recipients],
            'count': len(recipients),
        })


class MyDeskNoteVersionRestoreView(OrgScopedBaseAPIView):
    """POST /api/mydesk/notes/<pk>/versions/<vid>/restore/
    Restores the note to the content of that version and creates a new version snapshot.
    """
    parser_classes = [JSONParser]

    def get_note(self, pk):
        queryset = _mydesk_note_visible_queryset(self.request)
        return generics.get_object_or_404(queryset, pk=pk)

    def post(self, request, pk, vid):
        note = self.get_note(pk)
        version = generics.get_object_or_404(MyDeskNoteVersion, pk=vid, note=note)

        # Restore content
        note.title = version.title
        note.content_html = version.content_html
        note.save(update_fields=['title', 'content_html', 'updated_at'])

        # Snapshot the restore itself as a new version
        MyDeskNoteVersion.objects.create(
            note=note,
            title=note.title,
            content_html=note.content_html,
        )

        return Response(MyDeskNoteSerializer(note, context={'request': request}).data)


class MyDeskNoteVersionDetailView(OrgScopedBaseAPIView):
    """DELETE /api/mydesk/notes/<pk>/versions/<vid>/
    Deletes a specific note version.
    """
    def delete(self, request, pk, vid):
        queryset = _mydesk_note_visible_queryset(request)
        note = generics.get_object_or_404(queryset, pk=pk)
        version = generics.get_object_or_404(MyDeskNoteVersion, pk=vid, note=note)
        version.delete()
        return Response(MyDeskNoteSerializer(note, context={'request': request}).data)


class MyDeskNoteShareRecipientsView(OrgScopedBaseAPIView):
    """GET /api/mydesk/notes/share-recipients/?q=name
    Returns a list of org members the current user can share notes with.
    """

    def get(self, request):
        org_id = self.get_org_id()
        search = (request.query_params.get('q') or '').strip()

        users = User.objects.exclude(id=request.user.id)
        if org_id:
            users = users.filter(
                Q(team_settings__organization__organization_id=org_id) |
                Q(shop_credentials__organization_id=org_id)
            ).distinct()

        if search:
            users = users.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search)
            )

        users = users[:50]
        results = []
        for u in users:
            name = (u.get_full_name() or u.first_name or u.username or u.email or '').strip()
            results.append({'id': u.id, 'name': name, 'email': u.email or ''})

        return Response(results)


class MyDeskNoteAISummaryView(OrgScopedBaseAPIView):
    """POST /api/mydesk/notes/<pk>/ai-summary/
    Generates a concise summary of the note content using Gemini, saves it in the database, and returns it.
    """
    def post(self, request, pk):
        queryset = _mydesk_note_visible_queryset(request)
        note = generics.get_object_or_404(queryset, pk=pk)

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return Response({'detail': 'Gemini API key is not configured.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Build content for summarization
        title = note.title or 'Untitled Note'
        content = note.content_html or ''

        # Strip html tags
        from bs4 import BeautifulSoup
        try:
            clean_text = BeautifulSoup(content, 'html.parser').get_text(separator='\n')
        except Exception:
            clean_text = content

        prompt = (
            "You are an expert AI note assistant. Summarize the following note "
            "content concisely in 2-3 sentences. Focus on key details, decisions, "
            "and action items. Return only the summary text.\n\n"
            f"Note Title: {title}\n"
            f"Note Content:\n{clean_text}"
        )

        try:
            from google import genai
            from core.utils.gemini_fallback import generate_content_with_fallback
            client = genai.Client(api_key=api_key)
            response = generate_content_with_fallback(
                client=client,
                model='gemini-2.5-flash-lite',
                contents=prompt,
            )
            summary = (response.text or '').strip()
        except Exception as e:
            return Response({'detail': f'Failed to generate summary: {str(e)}'}, status=status.HTTP_502_BAD_GATEWAY)

        # Save summary
        note.ai_summary = summary
        note.save(update_fields=['ai_summary', 'updated_at'])

        return Response({'summary': summary})


class MyDeskNoteAICopilotView(OrgScopedBaseAPIView):
    """POST /api/mydesk/notes/ai-copilot/
    Accepts note title, content, custom prompt, and selected action, processes using Gemini, and returns the result.
    """
    def post(self, request):
        action = request.data.get('action', 'custom')
        prompt_arg = request.data.get('prompt', '')
        title = request.data.get('title', '')
        content = request.data.get('content', '')

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return Response({'detail': 'Gemini API key is not configured.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        from bs4 import BeautifulSoup
        try:
            clean_text = BeautifulSoup(content, 'html.parser').get_text(separator='\n')
        except Exception:
            clean_text = content

        # Map action to prompt instructions
        instructions = ""
        if action == "summarize":
            instructions = "Summarize the note content concisely."
        elif action == "extract_tasks":
            instructions = "Extract all tasks, action items, and next steps from the note content, formatting them as a clean bulleted list."
        elif action == "improve":
            instructions = "Improve the writing of this note. Fix grammar, punctuation, flow, and sentence structure, while preserving the original meaning."
        elif action == "meeting_minutes":
            instructions = "Format the note content as structured meeting minutes, including Date/Time, Attendees, Discussion Points, Decisions, and Action Items using markdown."
        elif action == "translate":
            target_lang = prompt_arg or "Hindi"
            instructions = f"Translate the note content accurately into {target_lang}."
        else: # custom
            instructions = f"Follow this instruction: {prompt_arg}"

        # Build full prompt
        system_prompt = (
            "You are a helpful AI note assistant. Follow the instruction on the provided "
            "note content. Return only the resulting formatted note text without extra conversational filler. "
            "If returning HTML or formatted text, make it look clean and well-structured."
        )

        full_prompt = (
            f"Instruction: {instructions}\n\n"
            f"Note Title: {title}\n"
            f"Note Content:\n{clean_text}"
        )

        try:
            from google import genai
            from google.genai import types
            from core.utils.gemini_fallback import generate_content_with_fallback
            client = genai.Client(api_key=api_key)
            response = generate_content_with_fallback(
                client=client,
                model='gemini-2.5-flash-lite',
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                )
            )
            result = (response.text or '').strip()
        except Exception as e:
            return Response({'detail': f'Failed to call AI Copilot: {str(e)}'}, status=status.HTTP_524_A_TIMEOUT)

        return Response({'result': result})


class PersonalTodoListCreateView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _visible_queryset(self, todo_type=''):
        return _personal_todo_visible_queryset(self.request, todo_type=todo_type)

    def _normalize_payload(self, request):
        data = request.data
        payload = {
            'text': data.get('text', ''),
            'is_done': data.get('is_done', False),
            'recurring': data.get('recurring', 'none'),
            'sort_order': data.get('sort_order', 0),
        }

        meta_value = data.get('meta', {})
        if isinstance(meta_value, str):
            try:
                payload['meta'] = json.loads(meta_value)
            except Exception:
                payload['meta'] = {}
        elif isinstance(meta_value, dict):
            payload['meta'] = meta_value
        else:
            payload['meta'] = {}

        return payload

    def get(self, request):
        request_started_at = time.perf_counter()
        todo_type = _normalize_todo_type_filter(request.query_params.get('type'))
        include_attachments = _parse_bool_query_param(request.query_params.get('include_attachments'))
        if include_attachments is None:
            include_attachments = True

        visibility_started_at = time.perf_counter()
        queryset = self._visible_queryset(todo_type=todo_type)
        visibility_elapsed_ms = (time.perf_counter() - visibility_started_at) * 1000

        if include_attachments:
            queryset = queryset.prefetch_related('task_attachments')

        serialize_started_at = time.perf_counter()
        payload = PersonalTodoItemSerializer(
            queryset,
            many=True,
            context={
                'request': request,
                'include_task_attachments': include_attachments,
            },
        ).data
        serialize_elapsed_ms = (time.perf_counter() - serialize_started_at) * 1000
        total_elapsed_ms = (time.perf_counter() - request_started_at) * 1000

        log_fn = LOGGER.warning if total_elapsed_ms >= 1000 else LOGGER.info
        log_fn(
            'mydesk.todos.list user_id=%s org_id=%s type=%s include_attachments=%s rows=%s visibility_ms=%.2f serialize_ms=%.2f total_ms=%.2f',
            request.user.id,
            self.get_org_id(),
            todo_type or 'all',
            include_attachments,
            len(payload),
            visibility_elapsed_ms,
            serialize_elapsed_ms,
            total_elapsed_ms,
        )
        return Response(payload)

    def post(self, request):
        org_id = self.get_org_id()
        serializer = PersonalTodoItemSerializer(data=self._normalize_payload(request), context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                item = serializer.save(
                    user=request.user,
                    org_id=org_id,
                    attachment=request.FILES.get('attachment') if request.FILES else None,
                )
                for uploaded in request.FILES.getlist('attachments'):
                    PersonalTodoAttachment.objects.create(
                        todo=item,
                        file=uploaded,
                        original_name=getattr(uploaded, 'name', '') or '',
                        mime_type=getattr(uploaded, 'content_type', '') or '',
                        file_size=getattr(uploaded, 'size', 0) or 0,
                    )
        except CloudinaryUploadError as exc:
            return Response(
                {'detail': f'Attachment upload failed: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _notify_task_assigned(item, request.user, org_id)
        _upsert_task_google_calendar_event(item)
        return Response(PersonalTodoItemSerializer(item, context={'request': request}).data, status=status.HTTP_201_CREATED)


class PersonalTodoDetailView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _visible_queryset(self):
        return _personal_todo_visible_queryset(self.request)

    def _normalize_payload(self, request):
        data = request.data
        payload = {}

        for field in ['text', 'is_done', 'recurring', 'sort_order']:
            if field in data:
                payload[field] = data.get(field)

        if 'meta' in data:
            meta_value = data.get('meta', {})
            if isinstance(meta_value, str):
                try:
                    payload['meta'] = json.loads(meta_value)
                except Exception:
                    payload['meta'] = {}
            elif isinstance(meta_value, dict):
                payload['meta'] = meta_value
            else:
                payload['meta'] = {}

        return payload

    def get_object(self, pk):
        queryset = self._visible_queryset()
        return generics.get_object_or_404(queryset, pk=pk)

    def get(self, request, pk):
        item = self.get_object(pk)
        include_attachments = _parse_bool_query_param(request.query_params.get('include_attachments'))
        if include_attachments is None:
            include_attachments = True
        serializer = PersonalTodoItemSerializer(
            item,
            context={
                'request': request,
                'include_task_attachments': include_attachments,
            },
        )
        return Response(serializer.data)

    def patch(self, request, pk):
        item = self.get_object(pk)
        previous_meta = item.meta if isinstance(item.meta, dict) else {}
        previous_assignee_ids = _extract_task_assignee_ids(previous_meta)
        previous_comments = previous_meta.get('comments') if isinstance(previous_meta.get('comments'), list) else []
        previous_reminder = str(previous_meta.get('reminderAt') or '').strip()
        serializer = PersonalTodoItemSerializer(item, data=self._normalize_payload(request), partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                saved_item = serializer.save()
                if request.FILES and request.FILES.get('attachment'):
                    saved_item.attachment = request.FILES.get('attachment')
                    saved_item.save(update_fields=['attachment'])
                for uploaded in request.FILES.getlist('attachments'):
                    PersonalTodoAttachment.objects.create(
                        todo=saved_item,
                        file=uploaded,
                        original_name=getattr(uploaded, 'name', '') or '',
                        mime_type=getattr(uploaded, 'content_type', '') or '',
                        file_size=getattr(uploaded, 'size', 0) or 0,
                    )
        except CloudinaryUploadError as exc:
            return Response(
                {'detail': f'Attachment upload failed: {exc}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_meta = saved_item.meta if isinstance(saved_item.meta, dict) else {}
        current_comments = current_meta.get('comments') if isinstance(current_meta.get('comments'), list) else []
        current_reminder = str(current_meta.get('reminderAt') or '').strip()
        task_priority = _task_priority_from_meta(current_meta)
        org_id = self.get_org_id()

        _notify_task_assigned(saved_item, request.user, org_id, previous_assignee_ids=previous_assignee_ids)

        added_comments = current_comments[len(previous_comments):] if len(current_comments) >= len(previous_comments) else []
        sender_name = request.user.first_name or request.user.username
        participant_ids = set(_extract_task_assignee_ids(current_meta))
        assigner_id = _extract_task_assigner_id(saved_item)
        if assigner_id:
            participant_ids.add(assigner_id)
        if saved_item.user_id:
            participant_ids.add(saved_item.user_id)

        participant_queryset = User.objects.filter(id__in=sorted(participant_ids), is_active=True)
        if org_id:
            participant_queryset = participant_queryset.filter(
                Q(team_settings__organization__organization_id=org_id)
                | Q(shop_credentials__organization_id=org_id)
            )
        participants = list(participant_queryset.exclude(id=request.user.id).distinct())

        for offset, comment in enumerate(added_comments, start=1):
            comment_text = _task_comment_text(comment)
            if not comment_text:
                continue

            comment_index = len(previous_comments) + offset
            mentioned_ids = set()
            mentioned_users = _parse_mention_targets(comment_text, org_id, request.user.id)
            for mentioned_user in mentioned_users:
                mentioned_ids.add(mentioned_user.id)
                push_unified_notification(
                    recipient=mentioned_user,
                    actor=request.user,
                    module='tasks',
                    action='mention',
                    title='You were mentioned in a task comment',
                    message=f"{sender_name} mentioned you in a task comment",
                    preview=comment_text[:200],
                    entity_type='personal_todo',
                    entity_id=saved_item.id,
                    sub_entity_type='comment',
                    sub_entity_id=f"{saved_item.id}:{comment_index}",
                    deep_link={
                        'page': '/mydesk/tasks',
                        'section': 'my-tasks',
                        'taskId': str(saved_item.id),
                    },
                    task_priority=task_priority,
                    sound_category='general',
                )

            for recipient in participants:
                if recipient.id in mentioned_ids:
                    continue
                push_unified_notification(
                    recipient=recipient,
                    actor=request.user,
                    module='tasks',
                    action='comment',
                    title='New comment on task',
                    message=f"{sender_name} added a comment",
                    preview=comment_text[:200],
                    entity_type='personal_todo',
                    entity_id=saved_item.id,
                    sub_entity_type='comment',
                    sub_entity_id=f"{saved_item.id}:{comment_index}",
                    deep_link={
                        'page': '/mydesk/tasks',
                        'section': 'my-tasks',
                        'taskId': str(saved_item.id),
                    },
                    task_priority=task_priority,
                    sound_category='general',
                )

        if current_reminder and current_reminder != previous_reminder:
            reminder_recipients = []
            assignee_ids = current_meta.get('assignee_ids') if isinstance(current_meta.get('assignee_ids'), list) else []
            for value in assignee_ids:
                try:
                    reminder_recipients.append(int(value))
                except (TypeError, ValueError):
                    continue
            if not reminder_recipients and current_meta.get('assignee_id') not in (None, ''):
                try:
                    reminder_recipients.append(int(current_meta.get('assignee_id')))
                except (TypeError, ValueError):
                    pass

            for recipient in User.objects.filter(id__in=sorted(set(reminder_recipients))).exclude(id=request.user.id):
                push_unified_notification(
                    recipient=recipient,
                    actor=request.user,
                    module='tasks',
                    action='reminder',
                    title='Task reminder set',
                    message=f"{sender_name} set a reminder on a task",
                    preview=(current_meta.get('title') or saved_item.text or 'Task')[:160],
                    entity_type='personal_todo',
                    entity_id=saved_item.id,
                    deep_link={
                        'page': '/mydesk/tasks',
                        'section': 'my-tasks',
                        'taskId': str(saved_item.id),
                    },
                    metadata={'reminderAt': current_reminder},
                    task_priority=task_priority,
                )

        _upsert_task_google_calendar_event(saved_item)
        return Response(PersonalTodoItemSerializer(saved_item, context={'request': request}).data)

    def delete(self, request, pk):
        item = self.get_object(pk)
        assigner_id = _extract_task_assigner_id(item)
        if assigner_id and assigner_id != request.user.id:
            return Response(
                {'detail': 'Only the user who assigned this task can delete it.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        _delete_task_google_calendar_event(item)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PersonalTodoAttachmentDetailView(OrgScopedBaseAPIView):
    parser_classes = [JSONParser]

    def get_object(self, pk):
        queryset = PersonalTodoAttachment.objects.filter(todo__in=_personal_todo_visible_queryset(self.request))
        return generics.get_object_or_404(queryset, pk=pk)

    def delete(self, request, pk):
        attachment = self.get_object(pk)
        try:
            if attachment.file:
                attachment.file.delete(save=False)
        except Exception:
            pass
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpenseListCreateView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def _parse_shared_with_ids(self, request):
        values = []

        if hasattr(request.data, 'getlist'):
            values.extend(request.data.getlist('shared_with_ids'))

        single_value = request.data.get('shared_with_ids')
        if single_value and single_value not in values:
            values.append(single_value)

        parsed_ids = []
        for raw in values:
            if isinstance(raw, (list, tuple)):
                for item in raw:
                    try:
                        parsed_ids.append(int(item))
                    except (TypeError, ValueError):
                        continue
                continue

            if isinstance(raw, str):
                raw = raw.strip()
                if not raw:
                    continue
                if raw.startswith('['):
                    try:
                        parsed_json = json.loads(raw)
                        if isinstance(parsed_json, list):
                            for item in parsed_json:
                                try:
                                    parsed_ids.append(int(item))
                                except (TypeError, ValueError):
                                    continue
                            continue
                    except Exception:
                        pass
                try:
                    parsed_ids.append(int(raw))
                except (TypeError, ValueError):
                    continue
                continue

            try:
                parsed_ids.append(int(raw))
            except (TypeError, ValueError):
                continue

        return sorted(set(parsed_ids))

    def get(self, request):
        org_id = self.get_org_id()

        # ── Build queryset ───────────────────────────────────────────────────
        # Fast path: own expenses (the 99% case) – single equality filter that
        # hits the composite index (org_id, user_id, spent_on) with no JOIN.
        if org_id:
            own_qs = ExpenseEntry.objects.filter(org_id=org_id, user=request.user)
            shared_ids = list(
                ExpenseEntry.objects.filter(
                    org_id=org_id, shares__recipient=request.user
                ).exclude(user=request.user).values_list('id', flat=True).distinct()
            )
            if shared_ids:
                from django.db.models import Q as _Q
                base_qs = ExpenseEntry.objects.filter(
                    _Q(org_id=org_id, user=request.user) | _Q(id__in=shared_ids)
                )
            else:
                base_qs = own_qs
        else:
            base_qs = ExpenseEntry.objects.filter(user=request.user, org_id='')

        # Pre-fetch shares so the serializer's get_shared_with runs in zero
        # extra DB queries (it iterates the prefetch cache via obj.shares.all()).
        queryset = base_qs.prefetch_related('shares__recipient')

        # ── Timeline / date filters ──────────────────────────────────────────
        month = request.query_params.get('month')
        if month:
            queryset = queryset.filter(spent_on__month=month)

        timeline = (request.query_params.get('timeline') or '').strip().lower()
        today = timezone.localdate()
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if timeline == 'today':
            queryset = queryset.filter(spent_on=today)
        elif timeline == '7d':
            queryset = queryset.filter(spent_on__gte=today - timedelta(days=6), spent_on__lte=today)
        elif timeline == '30d':
            queryset = queryset.filter(spent_on__gte=today - timedelta(days=29), spent_on__lte=today)
        elif timeline == 'this_month':
            queryset = queryset.filter(spent_on__year=today.year, spent_on__month=today.month)
        elif timeline == 'last_month':
            first_of_this_month = today.replace(day=1)
            last_of_prev_month = first_of_this_month - timedelta(days=1)
            queryset = queryset.filter(
                spent_on__year=last_of_prev_month.year,
                spent_on__month=last_of_prev_month.month,
            )
        elif timeline == 'custom':
            if start_date:
                queryset = queryset.filter(spent_on__gte=start_date)
            if end_date:
                queryset = queryset.filter(spent_on__lte=end_date)

        # ── Sorting ──────────────────────────────────────────────────────────
        sort_by = (request.query_params.get('sort_by') or 'spent_on').strip().lower()
        sort_order = (request.query_params.get('sort_order') or 'desc').strip().lower()
        allowed_sort_fields = {
            'spent_on': 'spent_on',
            'amount': 'amount',
            'created_at': 'created_at',
            'category': 'category',
            'transaction_type': 'transaction_type',
        }
        sort_field = allowed_sort_fields.get(sort_by, 'spent_on')
        order_prefix = '' if sort_order == 'asc' else '-'
        queryset = queryset.order_by(f'{order_prefix}{sort_field}', '-created_at')

        # ── Pagination ───────────────────────────────────────────────────────
        # Default page_size=100; capped at 500 to protect the server.
        # Clients may pass ?page=2&page_size=50 for explicit pagination.
        try:
            page_size = min(int(request.query_params.get('page_size') or 100), 500)
        except (TypeError, ValueError):
            page_size = 100
        try:
            page = max(int(request.query_params.get('page') or 1), 1)
        except (TypeError, ValueError):
            page = 1

        offset = (page - 1) * page_size
        total_count = queryset.count()
        page_qs = queryset[offset: offset + page_size]

        serializer = ExpenseEntrySerializer(page_qs, many=True, context={'request': request})
        return Response({
            'results': serializer.data,
            'count': total_count,
            'page': page,
            'page_size': page_size,
            'has_more': (offset + page_size) < total_count,
        })

    def post(self, request):
        serializer = ExpenseEntrySerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save(user=request.user, org_id=self.get_org_id())

        shared_with_ids = self._parse_shared_with_ids(request)
        if shared_with_ids:
            org_id = self.get_org_id()
            recipients = User.objects.filter(id__in=shared_with_ids)
            if org_id:
                recipients = recipients.filter(
                    Q(team_settings__organization__organization_id=org_id) |
                    Q(shop_credentials__organization_id=org_id)
                )
            recipients = recipients.exclude(id=request.user.id).distinct()

            shares = [
                ExpenseShare(
                    org_id=org_id,
                    expense=item,
                    recipient=recipient,
                    sent_by=request.user,
                )
                for recipient in recipients
            ]
            if shares:
                ExpenseShare.objects.bulk_create(shares, ignore_conflicts=True)
                for share in shares:
                    push_unified_notification(
                        recipient=share.recipient,
                        actor=request.user,
                        module='expenses',
                        action='share',
                        title='Expense shared with you',
                        message=f"{request.user.first_name or request.user.username} shared an expense with you",
                        preview=(item.notes or '')[:180],
                        entity_type='expense',
                        entity_id=item.id,
                        deep_link={
                            'page': '/mydesk/expenses',
                            'section': 'expenses',
                            'expenseId': str(item.id),
                        },
                    )

        return Response(ExpenseEntrySerializer(item, context={'request': request}).data, status=status.HTTP_201_CREATED)


class ExpenseDetailView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, pk):
        queryset = self.scope_queryset(ExpenseEntry.objects.all())
        return generics.get_object_or_404(queryset, pk=pk)

    def patch(self, request, pk):
        item = self.get_object(pk)
        serializer = ExpenseEntrySerializer(item, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ExpenseEntrySerializer(item, context={'request': request}).data)

    def delete(self, request, pk):
        item = self.get_object(pk)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpenseSendToHrView(OrgScopedBaseAPIView):
    parser_classes = [JSONParser]

    def post(self, request):
        org_id = self.get_org_id()
        expense_ids = _parse_int_ids_payload(request.data, 'expense_ids')

        queryset = ExpenseEntry.objects.filter(
            user=request.user,
            transaction_type='expense',
        )
        if org_id:
            queryset = queryset.filter(org_id=org_id)
        else:
            queryset = queryset.filter(org_id='')

        if expense_ids:
            queryset = queryset.filter(id__in=expense_ids)

        entries = list(queryset.only('id', 'status'))
        eligible_ids = [
            item.id
            for item in entries
            if _expense_status_label(item.status) in EXPENSE_TRACKER_RESUBMITTABLE_STATUSES
        ]

        if eligible_ids:
            ExpenseEntry.objects.filter(id__in=eligible_ids).update(
                status='Submitted',
                updated_at=timezone.now(),
            )

        updated_count = len(eligible_ids)
        skipped_count = max(0, len(entries) - updated_count)
        return Response({
            'updated_count': updated_count,
            'updated_ids': eligible_ids,
            'skipped_count': skipped_count,
            'detail': f'{updated_count} expense entries sent to HR.',
        })


class HrExpenseTrackerOverviewView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
    }
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        users = list(_organization_users(org_id))
        if not users:
            return Response({
                'summary': {
                    'total_submitted_amount': 0,
                    'pending_approval_amount': 0,
                    'approved_amount': 0,
                    'paid_amount': 0,
                    'rejected_amount': 0,
                    'total_entries': 0,
                    'pending_entries': 0,
                    'approved_entries': 0,
                    'paid_entries': 0,
                    'rejected_entries': 0,
                    'member_count': 0,
                },
                'departments': [{'value': 'all', 'label': 'All Departments'}],
                'members': [],
                'recent_submissions': [],
                'send_options': EXPENSE_TRACKER_SEND_OPTIONS,
                'updated_at': _to_iso_datetime(timezone.now()),
            })

        workforce_map = _build_workforce_member_map(org_id, users)

        all_departments = []
        for user_obj in users:
            workforce_member = workforce_map.get(user_obj.id)
            if workforce_member and workforce_member.department:
                all_departments.append(str(workforce_member.department.name or '').strip())
        all_departments = sorted({name for name in all_departments if name})

        requested_department = str(request.query_params.get('department') or '').strip()
        requested_department_lc = requested_department.lower()

        filtered_users = []
        for user_obj in users:
            workforce_member = workforce_map.get(user_obj.id)
            department_name = ''
            if workforce_member and workforce_member.department:
                department_name = str(workforce_member.department.name or '').strip()

            if requested_department_lc and requested_department_lc not in {'all', 'any'}:
                if department_name.lower() != requested_department_lc:
                    continue
            filtered_users.append(user_obj)

        filtered_user_ids = [user_obj.id for user_obj in filtered_users]
        department_by_user_id = {}
        for user_obj in filtered_users:
            workforce_member = workforce_map.get(user_obj.id)
            if workforce_member and workforce_member.department:
                department_by_user_id[user_obj.id] = str(workforce_member.department.name or '').strip()
            else:
                department_by_user_id[user_obj.id] = ''

        expense_entries = []
        if filtered_user_ids:
            expense_entries = list(
                ExpenseEntry.objects.select_related('user').filter(
                    org_id=org_id,
                    user_id__in=filtered_user_ids,
                    transaction_type='expense',
                ).order_by('-spent_on', '-created_at')
            )

        member_rows = {}
        for user_obj in filtered_users:
            department_name = department_by_user_id.get(user_obj.id, '')
            member_rows[user_obj.id] = {
                'user_id': user_obj.id,
                'member_name': _user_full_name(user_obj),
                'email': str(user_obj.email or '').strip(),
                'department': department_name,
                'amount_spent': 0,
                'unpaid_amount': 0,
                'pending_approval_amount': 0,
                'entries_count': 0,
                'approved_count': 0,
                'paid_count': 0,
                'pending_count': 0,
                'rejected_count': 0,
                'last_submitted_on': None,
            }

        total_amount = 0.0
        pending_amount = 0.0
        approved_amount = 0.0
        paid_amount = 0.0
        rejected_amount = 0.0
        pending_entries = 0
        approved_entries = 0
        paid_entries = 0
        rejected_entries = 0

        recent_submissions = []
        for item in expense_entries:
            row = member_rows.get(item.user_id)
            if not row:
                continue

            amount_value = _expense_amount_value(item.amount)
            approved_amount_value = _expense_amount_value(item.approved_amount) if item.approved_amount is not None else amount_value
            status_label = _expense_status_label(item.status)
            effectively_rejected = _is_effectively_rejected(item)

            row['amount_spent'] = _round2(float(row['amount_spent']) + (approved_amount_value if status_label in {'Paid', 'Dept Head Approved', 'Partially Approved', 'Finance Reviewed'} else amount_value))
            row['entries_count'] += 1

            if effectively_rejected:
                row['rejected_count'] += 1
                rejected_amount = _round2(rejected_amount + amount_value)
                rejected_entries += 1
            elif status_label in EXPENSE_TRACKER_PENDING_STATUSES:
                row['pending_count'] += 1
                row['pending_approval_amount'] = _round2(float(row['pending_approval_amount']) + amount_value)
                row['unpaid_amount'] = _round2(float(row['unpaid_amount']) + amount_value)
                row['last_submitted_on'] = item.spent_on.isoformat() if item.spent_on else None
                pending_amount = _round2(pending_amount + amount_value)
                pending_entries += 1
            elif status_label == 'Paid':
                row['paid_count'] += 1
                paid_amount = _round2(paid_amount + approved_amount_value)
                paid_entries += 1
            elif status_label in {'Dept Head Approved', 'Partially Approved', 'Finance Reviewed'}:
                row['approved_count'] += 1
                row['unpaid_amount'] = _round2(float(row['unpaid_amount']) + approved_amount_value)
                approved_amount = _round2(approved_amount + approved_amount_value)
                approved_entries += 1

            total_amount = _round2(total_amount + (approved_amount_value if status_label in {'Paid', 'Dept Head Approved', 'Partially Approved', 'Finance Reviewed'} else amount_value))

            if status_label != 'Draft' and len(recent_submissions) < 120:
                recent_submissions.append(
                    _expense_entry_payload(
                        request,
                        item,
                        user_obj=item.user,
                        department_name=department_by_user_id.get(item.user_id, ''),
                    )
                )

        members = sorted(
            member_rows.values(),
            key=lambda value: (
                int(value.get('pending_count') or 0),
                float(value.get('amount_spent') or 0),
                str(value.get('member_name') or '').lower(),
            ),
            reverse=True,
        )

        departments_payload = [{'value': 'all', 'label': 'All Departments'}]
        departments_payload.extend(
            {'value': name, 'label': name}
            for name in all_departments
        )

        return Response({
            'summary': {
                'total_submitted_amount': _round2(total_amount),
                'pending_approval_amount': _round2(pending_amount),
                'approved_amount': _round2(approved_amount),
                'paid_amount': _round2(paid_amount),
                'rejected_amount': _round2(rejected_amount),
                'total_entries': len(expense_entries),
                'pending_entries': pending_entries,
                'approved_entries': approved_entries,
                'paid_entries': paid_entries,
                'rejected_entries': rejected_entries,
                'member_count': len(members),
            },
            'departments': departments_payload,
            'members': members,
            'recent_submissions': recent_submissions,
            'send_options': EXPENSE_TRACKER_SEND_OPTIONS,
            'updated_at': _to_iso_datetime(timezone.now()),
        })


class HrExpenseTrackerMemberDetailView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
    }
    parser_classes = [JSONParser]

    def get(self, request, user_id):
        org_id = self.get_org_id()
        target_user = _organization_users(org_id).filter(id=user_id).first()
        if not target_user:
            return Response({'detail': 'Member not found in your organization.'}, status=status.HTTP_404_NOT_FOUND)

        workforce_member = _build_workforce_member_map(org_id, [target_user]).get(target_user.id)
        profile = _get_user_profile_object(target_user)
        department_name = ''
        if workforce_member and workforce_member.department:
            department_name = str(workforce_member.department.name or '').strip()

        manager_name = _expense_manager_name(workforce_member)
        employee_code = _expense_employee_code(target_user, workforce_member)

        all_entries = list(
            ExpenseEntry.objects.select_related('user').filter(
                org_id=org_id,
                user_id=target_user.id,
                transaction_type='expense',
            ).order_by('-spent_on', '-created_at')
        )

        total_amount = 0.0
        unpaid_amount = 0.0
        dept_approved_amount = 0.0
        pending_amount = 0.0
        approved_count = 0
        paid_amount = 0.0
        paid_count = 0
        pending_count = 0
        rejected_count = 0
        rejected_amount = 0.0
        category_aggregate = {}

        for item in all_entries:
            amount_value = _expense_amount_value(item.amount)
            approved_amount_value = _expense_amount_value(item.approved_amount) if item.approved_amount is not None else amount_value
            status_label = _expense_status_label(item.status)
            category_key = str(item.category or 'misc').strip().lower() or 'misc'

            total_amount = _round2(total_amount + (approved_amount_value if status_label in {'Paid', 'Dept Head Approved', 'Partially Approved', 'Finance Reviewed'} else amount_value))

            effectively_rejected = _is_effectively_rejected(item)

            if effectively_rejected:
                rejected_count += 1
                rejected_amount = _round2(rejected_amount + amount_value)
            elif status_label == 'Paid':
                paid_count += 1
                paid_amount = _round2(paid_amount + approved_amount_value)
            elif status_label in {'Dept Head Approved', 'Partially Approved', 'Finance Reviewed'}:
                approved_count += 1
                dept_approved_amount = _round2(dept_approved_amount + approved_amount_value)
                unpaid_amount = _round2(unpaid_amount + approved_amount_value)
            elif status_label in EXPENSE_TRACKER_PENDING_STATUSES:
                pending_count += 1
                pending_amount = _round2(pending_amount + amount_value)
                unpaid_amount = _round2(unpaid_amount + amount_value)

            current = category_aggregate.get(category_key)
            if current is None:
                current = {
                    'category': category_key,
                    'label': category_key.replace('_', ' ').title(),
                    'amount': 0,
                    'count': 0,
                    'percentage': 0,
                }
                category_aggregate[category_key] = current

            current['amount'] = _round2(float(current['amount']) + (approved_amount_value if status_label in {'Paid', 'Dept Head Approved', 'Partially Approved', 'Finance Reviewed'} else amount_value))
            current['count'] += 1
        total_unpaid_amount = unpaid_amount

        total_for_percentage = float(total_amount or 0)
        if total_for_percentage <= 0:
            total_for_percentage = 1.0

        category_breakdown = sorted(
            category_aggregate.values(),
            key=lambda value: float(value.get('amount') or 0),
            reverse=True,
        )
        for row in category_breakdown:
            row['percentage'] = _round2((float(row.get('amount') or 0) / total_for_percentage) * 100)

        available_categories = ['all']
        available_categories.extend(
            row['category']
            for row in category_breakdown
            if row.get('category') and row['category'] != 'all'
        )

        category_filter = str(request.query_params.get('category') or 'all').strip().lower() or 'all'
        status_filter_raw = str(request.query_params.get('status') or 'all').strip().lower() or 'all'
        status_filter = _expense_status_label(status_filter_raw) if status_filter_raw != 'all' else ''

        timeline = (request.query_params.get('timeline') or 'all').strip().lower()
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')

        from datetime import date as _date
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = _date.fromisoformat(start_date_str)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = _date.fromisoformat(end_date_str)
            except ValueError:
                pass

        today = timezone.localdate()

        filtered_entries = []
        for item in all_entries:
            item_category = str(item.category or '').strip().lower()
            item_status = _expense_status_label(item.status)

            if category_filter != 'all' and item_category != category_filter:
                continue
            if status_filter and item_status != status_filter:
                continue

            spent_date = item.spent_on
            if spent_date:
                if timeline == 'today':
                    if spent_date != today:
                        continue
                elif timeline == '7d':
                    if not (today - timedelta(days=6) <= spent_date <= today):
                        continue
                elif timeline == '30d':
                    if not (today - timedelta(days=29) <= spent_date <= today):
                        continue
                elif timeline == 'this_month':
                    if not (spent_date.year == today.year and spent_date.month == today.month):
                        continue
                elif timeline == 'last_month':
                    first_of_this_month = today.replace(day=1)
                    last_of_prev_month = first_of_this_month - timedelta(days=1)
                    if not (spent_date.year == last_of_prev_month.year and spent_date.month == last_of_prev_month.month):
                        continue
                elif timeline == 'custom':
                    if start_date and spent_date < start_date:
                        continue
                    if end_date and spent_date > end_date:
                        continue
            elif timeline != 'all':
                continue

            filtered_entries.append(item)

        sort_by = (request.query_params.get('sort_by') or 'spent_on').strip().lower()
        sort_order = (request.query_params.get('sort_order') or 'desc').strip().lower()
        reverse_sort = (sort_order == 'desc')

        def get_sort_key(item):
            if sort_by == 'spent_on':
                val = item.spent_on
                if val is None:
                    return (_date.min if reverse_sort else _date.max, item.created_at or timezone.now())
                return (val, item.created_at or timezone.now())
            elif sort_by == 'amount':
                val = _expense_amount_value(item.amount)
                return (val, item.spent_on or _date.min, item.created_at or timezone.now())
            elif sort_by == 'created_at':
                val = item.created_at
                if val is None:
                    return (timezone.now() if reverse_sort else timezone.now(),)
                return (val,)
            elif sort_by == 'category':
                val = str(item.category or '').lower()
                return (val, item.spent_on or _date.min, item.created_at or timezone.now())
            elif sort_by == 'transaction_type':
                val = str(item.transaction_type or '').lower()
                return (val, item.spent_on or _date.min, item.created_at or timezone.now())
            else:
                val = item.spent_on
                if val is None:
                    return (_date.min if reverse_sort else _date.max, item.created_at or timezone.now())
                return (val, item.created_at or timezone.now())

        filtered_entries.sort(key=get_sort_key, reverse=reverse_sort)

        rows = [
            _expense_entry_payload(
                request,
                item,
                user_obj=target_user,
                department_name=department_name,
            )
            for item in filtered_entries
        ]

        return Response({
            'profile': {
                'user_id': target_user.id,
                'employee_name': _user_full_name(target_user),
                'employee_id': employee_code,
                'email': str(target_user.email or '').strip(),
                'phone': (
                    str(getattr(profile, 'phone', '') or '').strip()
                    or str(getattr(workforce_member, 'phone', '') or '').strip()
                ),
                'joining_date': target_user.date_joined.date().isoformat() if target_user.date_joined else None,
                'manager': manager_name,
                'department': department_name,
                'designation': str(getattr(workforce_member, 'role_designation', '') or '').strip(),
            },
            'quick_stats': {
                'total_amount': _round2(total_amount),
                'paid_amount': _round2(paid_amount),
                'total_unpaid_amount': _round2(total_unpaid_amount),
                'unpaid_amount': _round2(unpaid_amount),
                'dept_approved_amount': _round2(dept_approved_amount),
                'pending_amount': _round2(pending_amount),
                'rejected_amount': _round2(rejected_amount),
                'entries': len(all_entries),
                'approved': approved_count,
                'paid': paid_count,
                'pending': pending_count,
                'rejected': rejected_count,
            },
            'category_breakdown': category_breakdown,
            'available_categories': available_categories,
            'status_options': ['all', 'Draft', 'Submitted', 'Dept Head Approved', 'Finance Reviewed', 'Paid', 'Rejected'],
            'filters': {
                'category': category_filter,
                'status': status_filter_raw,
                'timeline': timeline,
                'start_date': start_date_str or '',
                'end_date': end_date_str or '',
                'sort_by': sort_by,
                'sort_order': sort_order,
            },
            'expenses': rows,
            'send_options': EXPENSE_TRACKER_MEMBER_SEND_OPTIONS,
        })


class HrExpenseTrackerApprovalActionView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'PUT': 'human_resources:attendance_dashboard:edit',
    }
    parser_classes = [JSONParser]

    # Map incoming status string → canonical model value
    VALID_TRANSITIONS = {
        'dept_head_approved': 'Dept Head Approved',
        'partially_approved': 'Partially Approved',
        'finance_reviewed': 'Finance Reviewed',
        'paid': 'Paid',
        'rejected': 'Rejected',
        'approved': 'Dept Head Approved',  # legacy compat
    }

    def put(self, request, expense_id):
        org_id = self.get_org_id()
        raw_action = str(request.data.get('status') or '').strip().lower()
        target_status = self.VALID_TRANSITIONS.get(raw_action)
        if not target_status:
            return Response(
                {'status': f'Invalid action. Allowed: {list(self.VALID_TRANSITIONS.keys())}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expense = ExpenseEntry.objects.select_related(
            'user', 'dept_approved_by', 'finance_reviewed_by', 'paid_by',
        ).filter(org_id=org_id, id=expense_id, transaction_type='expense').first()
        if not expense:
            return Response({'detail': 'Expense entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        previous_status = expense.status
        if str(previous_status or '').strip().lower() == 'rejected':
            return Response(
                {'detail': 'This expense has already been rejected and no further actions are allowed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        now = timezone.now()
        actor_name = _actor_display_name(request.user)
        note = str(request.data.get('note') or request.data.get('approval_note') or '').strip()
        update_fields = ['status', 'updated_at', 'workflow_steps']

        # Build workflow step record
        workflow_steps = expense.workflow_steps if isinstance(expense.workflow_steps, list) else []
        step_record = {
            'step': target_status,
            'actor': actor_name,
            'actor_id': request.user.id,
            'at': now.isoformat(),
            'note': note,
        }

        if target_status == 'Rejected':
            rejection_reason = str(request.data.get('rejection_reason') or note).strip()
            expense.rejection_reason = rejection_reason
            step_record['rejection_reason'] = rejection_reason
            update_fields.append('rejection_reason')

        elif target_status == 'Dept Head Approved':
            expense.dept_approved_by = request.user
            expense.dept_approved_at = now
            update_fields += ['dept_approved_by', 'dept_approved_at']

        elif target_status == 'Partially Approved':
            approved_amount_raw = request.data.get('approved_amount')
            if approved_amount_raw is None:
                return Response({'detail': 'Approved amount is required for partial approval.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                approved_amount = Decimal(str(approved_amount_raw))
            except Exception:
                return Response({'detail': 'Invalid approved amount.'}, status=status.HTTP_400_BAD_REQUEST)
            if approved_amount <= 0 or approved_amount > expense.amount:
                return Response({'detail': 'Approved amount must be positive and less than or equal to the requested amount.'}, status=status.HTTP_400_BAD_REQUEST)

            expense.approved_amount = approved_amount
            expense.dept_approved_by = request.user
            expense.dept_approved_at = now
            update_fields += ['approved_amount', 'dept_approved_by', 'dept_approved_at']
            step_record['approved_amount'] = float(approved_amount)

        elif target_status == 'Finance Reviewed':
            expense.finance_reviewed_by = request.user
            expense.finance_reviewed_at = now
            update_fields += ['finance_reviewed_by', 'finance_reviewed_at']

        elif target_status == 'Paid':
            # Require payment details
            payment_date_raw = request.data.get('payment_date')
            payment_method = str(request.data.get('payment_method') or 'bank_transfer').strip()
            payment_date = None
            if payment_date_raw:
                from datetime import date as _date
                try:
                    payment_date = _date.fromisoformat(str(payment_date_raw))
                except ValueError:
                    pass
            if not payment_date:
                payment_date = now.date()

            expense.paid_by = request.user
            expense.paid_at = now
            expense.payment_date = payment_date
            expense.payment_method = payment_method
            expense.finance_status = 'submitted'
            update_fields += ['paid_by', 'paid_at', 'payment_date', 'payment_method', 'finance_status']

            step_record['payment_date'] = payment_date.isoformat()
            step_record['payment_method'] = payment_method

            # Create a journal entry in the accounting module
            finance_entry_id = _create_expense_journal_entry(expense, payment_date, payment_method, request.user)
            if finance_entry_id:
                expense.finance_entry_id = finance_entry_id
                expense.finance_status = 'posted'
                update_fields += ['finance_entry_id', 'finance_status']
                step_record['finance_entry_id'] = finance_entry_id

        expense.status = target_status
        workflow_steps.append(step_record)
        expense.workflow_steps = workflow_steps
        expense.save(update_fields=sorted(set(update_fields)))

        department_name = expense.department or ''
        if not department_name:
            workforce_member = _build_workforce_member_map(org_id, [expense.user]).get(expense.user_id)
            if workforce_member and workforce_member.department:
                department_name = str(workforce_member.department.name or '').strip()

        return Response({
            'detail': f'Expense marked as {target_status}.',
            'previous_status': previous_status,
            'row': _expense_entry_payload(
                request,
                expense,
                user_obj=expense.user,
                department_name=department_name,
            ),
        })


def _create_expense_journal_entry(expense, payment_date, payment_method, actor_user):
    """
    Create a double-entry journal in the accounting module when an expense is paid:
      Debit  → <Category> Expense ledger
      Credit → Cash / Bank (based on payment_method)
    Returns the JournalEntry PK, or None if it fails.
    """
    try:
        from accounting.models import JournalEntry, JournalItem, Ledger

        category_label = dict(ExpenseEntry.CATEGORY_CHOICES).get(expense.category, expense.category.title())
        expense_ledger_name = f'{category_label} Expense'
        expense_ledger, _ = Ledger.objects.get_or_create(
            name=expense_ledger_name,
            defaults={'type': 'expense'},
        )

        credit_method = str(payment_method or '').lower()
        if 'upi' in credit_method or 'transfer' in credit_method or 'neft' in credit_method:
            credit_name = 'Bank'
        else:
            credit_name = 'Cash'
        credit_ledger, _ = Ledger.objects.get_or_create(
            name=credit_name,
            defaults={'type': 'asset'},
        )

        employee_name = expense.user.get_full_name() or str(expense.user.email)
        description = f'Reimbursement: {employee_name} — {category_label} ({expense.spent_on})'

        effective_amount = expense.approved_amount if expense.approved_amount is not None else expense.amount

        with transaction.atomic():
            entry = JournalEntry.objects.create(
                date=payment_date,
                description=description,
            )
            JournalItem.objects.create(
                entry=entry,
                ledger=expense_ledger,
                debit=effective_amount,
                credit=0,
                department=expense.department or '',
                notes=description,
            )
            JournalItem.objects.create(
                entry=entry,
                ledger=credit_ledger,
                debit=0,
                credit=effective_amount,
                department=expense.department or '',
                notes=description,
            )
        return entry.pk
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error('Failed to create expense journal entry: %s', exc)
        return None




class HrExpenseTrackerRequestApprovalView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'human_resources:attendance_dashboard:edit',
    }
    parser_classes = [JSONParser]

    def post(self, request, user_id):
        org_id = self.get_org_id()
        target_user = _organization_users(org_id).filter(id=user_id).first()
        if not target_user:
            return Response({'detail': 'Member not found in your organization.'}, status=status.HTTP_404_NOT_FOUND)

        updated_count = ExpenseEntry.objects.filter(
            org_id=org_id,
            user_id=target_user.id,
            transaction_type='expense',
            status__in=sorted(EXPENSE_TRACKER_RESUBMITTABLE_STATUSES),
        ).update(
            status='Submitted',
            updated_at=timezone.now(),
        )

        return Response({
            'detail': f'{updated_count} entries moved to pending approval.',
            'user_id': target_user.id,
            'updated_count': updated_count,
        })


class LeaveRequestListCreateView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        queryset = LeaveRequest.objects.select_related('user', 'requested_to', 'approved_by').all()
        if org_id:
            queryset = queryset.filter(org_id=org_id, user=request.user)
        else:
            queryset = queryset.filter(user=request.user, org_id='')
        serializer = LeaveRequestSerializer(queryset.distinct(), many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        org_id = self.get_org_id()

        # requested_to is now optional – if not provided leave goes straight to HR
        requested_to_id = request.data.get('requested_to') or None
        recipient = None
        if requested_to_id not in (None, '', 'null'):
            try:
                requested_to_id = int(requested_to_id)
            except (TypeError, ValueError):
                return Response({'requested_to': 'Invalid recipient'}, status=status.HTTP_400_BAD_REQUEST)

            if requested_to_id == request.user.id:
                return Response({'requested_to': 'You cannot send a leave request to yourself'}, status=status.HTTP_400_BAD_REQUEST)

            recipient_qs = User.objects.filter(id=requested_to_id)
            if org_id:
                recipient_qs = recipient_qs.filter(
                    Q(team_settings__organization__organization_id=org_id) |
                    Q(shop_credentials__organization_id=org_id)
                )
            recipient = recipient_qs.distinct().first()
            if not recipient:
                return Response({'requested_to': 'Recipient is not part of your organization'}, status=status.HTTP_400_BAD_REQUEST)

        leave = LeaveRequest(
            org_id=org_id or '',
            user=request.user,
            requested_to=recipient,
            leave_type=request.data.get('leave_type', 'casual'),
            start_date=request.data.get('start_date') or request.data.get('from_date'),
            end_date=request.data.get('end_date') or request.data.get('to_date'),
            reason=request.data.get('reason', ''),
            status='pending',
        )
        if 'document' in request.FILES:
            leave.document = request.FILES['document']
        leave.save()

        requester_name = request.user.get_full_name() or request.user.first_name or request.user.username
        # Notify manager if specified, else notify HR (everyone with human_resources perm in org)
        if recipient:
            push_unified_notification(
                recipient=recipient,
                actor=request.user,
                module='leave_requests',
                action='share',
                title='New leave request',
                message=f"{requester_name} submitted a {leave.leave_type} leave request",
                preview=(leave.reason or f"{leave.start_date} to {leave.end_date}")[:180],
                entity_type='leave_request',
                entity_id=leave.id,
                deep_link={'page': '/team/attendance', 'section': 'leave-requests'},
                metadata={'status': leave.status},
            )
        else:
            # Notify HR managers in org
            hr_users = []
            if org_id:
                from core.permissions import _check_granular_permission, is_org_owner
                for u in _organization_users(org_id):
                    if u.is_superuser or is_org_owner(u) or _check_granular_permission(u, 'human_resources', 'workforce', 'GET'):
                        hr_users.append(u)
            for hr_user in hr_users[:10]:
                push_unified_notification(
                    recipient=hr_user,
                    actor=request.user,
                    module='leave_requests',
                    action='share',
                    title='New leave request',
                    message=f"{requester_name} submitted a {leave.leave_type} leave request",
                    preview=(leave.reason or f"{leave.start_date} to {leave.end_date}")[:180],
                    entity_type='leave_request',
                    entity_id=leave.id,
                    deep_link={'page': '/team/attendance', 'section': 'leave-requests'},
                    metadata={'status': leave.status},
                )

        return Response(LeaveRequestSerializer(leave, context={'request': request}).data, status=status.HTTP_201_CREATED)


class LeaveRequestDetailView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, pk):
        org_id = self.get_org_id()
        queryset = LeaveRequest.objects.select_related('user', 'requested_to', 'approved_by').all()
        if org_id:
            queryset = queryset.filter(org_id=org_id, user=self.request.user)
        else:
            queryset = queryset.filter(user=self.request.user, org_id='')
        return generics.get_object_or_404(queryset, pk=pk)

    def patch(self, request, pk):
        leave = self.get_object(pk)
        action = (request.data.get('action') or '').strip().lower()

        if action == 'remind':
            if leave.status != 'pending':
                return Response({'detail': 'Reminders can only be sent for pending requests.'}, status=status.HTTP_400_BAD_REQUEST)
            leave.reminder_count = (leave.reminder_count or 0) + 1
            leave.save(update_fields=['reminder_count', 'updated_at'])
            return Response(LeaveRequestSerializer(leave, context={'request': request}).data)

        # Employee can only edit pending leaves
        if leave.status != 'pending':
            return Response({'detail': 'Only pending requests can be edited.'}, status=status.HTTP_400_BAD_REQUEST)

        if leave.user_id != request.user.id:
            return Response({'detail': 'Only the requester can edit this leave request.'}, status=status.HTTP_403_FORBIDDEN)

        leave.leave_type = request.data.get('leave_type', leave.leave_type)
        leave.start_date = request.data.get('start_date', leave.start_date)
        leave.end_date = request.data.get('end_date', leave.end_date)
        leave.reason = request.data.get('reason', leave.reason)
        if 'document' in request.FILES:
            leave.document = request.FILES['document']
        leave.save()
        return Response(LeaveRequestSerializer(leave, context={'request': request}).data)

    def delete(self, request, pk):
        leave = self.get_object(pk)
        if leave.user_id != request.user.id:
            return Response({'detail': 'Only the requester can delete this leave request.'}, status=status.HTTP_403_FORBIDDEN)
        if leave.status != 'pending':
            return Response({'detail': 'Only pending requests can be deleted.'}, status=status.HTTP_400_BAD_REQUEST)
        leave.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def _apply_leave_to_attendance(leave):
    """Auto-create / update attendance entries for approved leave dates."""
    from datetime import timedelta
    current = leave.start_date
    while current <= leave.end_date:
        # Skip Sundays (weekday 6)
        if current.weekday() != 6:
            entry, _ = AttendanceEntry.objects.get_or_create(
                org_id=leave.org_id,
                user=leave.user,
                entry_date=current,
                defaults={'status': 'leave', 'source': 'hr', 'approval_status': 'approved'},
            )
            if entry.status != 'leave':
                entry.status = 'leave'
                entry.source = 'hr'
                entry.approval_status = 'approved'
                entry.save(update_fields=['status', 'source', 'approval_status', 'updated_at'])
        current += timedelta(days=1)


class HrLeaveRequestView(OrgScopedBaseAPIView):
    """HR-facing view: list all org leaves + approve/reject with attendance update."""
    parser_classes = [JSONParser]

    def _check_hr(self, request):
        if request.user.is_staff or request.user.is_superuser:
            return True
        from core.permissions import _check_granular_permission
        return _check_granular_permission(request.user, 'human_resources', 'workforce', request.method)

    def get(self, request):
        if not self._check_hr(request):
            return Response({'detail': 'HR permission required.'}, status=status.HTTP_403_FORBIDDEN)
        org_id = self.get_org_id()
        qs = LeaveRequest.objects.select_related('user', 'requested_to', 'approved_by', 'manager_actioned_by').all()
        if org_id:
            qs = qs.filter(org_id=org_id)
        else:
            return Response({'rows': []})

        # Optional filters
        status_f = request.query_params.get('status')
        leave_type_f = request.query_params.get('leave_type')
        user_id_f = request.query_params.get('user_id')
        month_f = request.query_params.get('month')  # YYYY-MM

        if status_f:
            qs = qs.filter(status=status_f)
        if leave_type_f:
            qs = qs.filter(leave_type=leave_type_f)
        if user_id_f:
            qs = qs.filter(user_id=user_id_f)
        if month_f:
            try:
                year, mon = [int(x) for x in month_f.split('-')]
                import calendar
                last_day = calendar.monthrange(year, mon)[1]
                from datetime import date
                qs = qs.filter(start_date__lte=date(year, mon, last_day), end_date__gte=date(year, mon, 1))
            except Exception:
                pass

        data = LeaveRequestSerializer(qs.order_by('-created_at')[:200], many=True, context={'request': request}).data
        return Response({'rows': data})

    def patch(self, request, pk):
        if not self._check_hr(request):
            return Response({'detail': 'HR permission required.'}, status=status.HTTP_403_FORBIDDEN)
        org_id = self.get_org_id()
        leave = generics.get_object_or_404(LeaveRequest.objects.select_related('user'), org_id=org_id, pk=pk)

        action = (request.data.get('action') or '').strip().lower()  # 'approve' | 'reject'
        decline_reason = (request.data.get('decline_reason') or '').strip()

        if action not in ('approve', 'reject'):
            return Response({'detail': 'action must be approve or reject.'}, status=status.HTTP_400_BAD_REQUEST)

        if action == 'reject' and not decline_reason:
            return Response({'decline_reason': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        leave.status = 'approved' if action == 'approve' else 'rejected'
        leave.approved_by = request.user
        leave.approved_at = timezone.now()
        leave.decline_reason = decline_reason if action == 'reject' else ''
        leave.save(update_fields=['status', 'approved_by', 'approved_at', 'decline_reason', 'updated_at'])

        if action == 'approve':
            _apply_leave_to_attendance(leave)

        # Notify employee
        approver_name = request.user.get_full_name() or request.user.first_name or request.user.username
        status_label = 'approved' if action == 'approve' else 'rejected'
        push_unified_notification(
            recipient=leave.user,
            actor=request.user,
            module='leave_requests',
            action='share',
            title=f'Leave request {status_label}',
            message=f"{approver_name} {status_label} your leave request ({leave.leave_type})",
            preview=decline_reason or (leave.reason or '')[:180],
            entity_type='leave_request',
            entity_id=leave.id,
            deep_link={'page': '/mydesk/leave', 'section': 'leave-requests'},
            metadata={'status': leave.status, 'decline_reason': decline_reason},
        )

        return Response(LeaveRequestSerializer(leave, context={'request': request}).data)


class MyDeskAttendanceOverviewView(OrgScopedBaseAPIView):
    parser_classes = [JSONParser]

    def get(self, request):
        first_day, last_day = _parse_month_bounds(request.query_params.get('month'))
        org_id = self.get_org_id()

        queryset = AttendanceEntry.objects.filter(
            user=request.user,
            entry_date__gte=first_day,
            entry_date__lte=last_day,
            is_active=True,
        )
        if org_id:
            queryset = queryset.filter(org_id=org_id)
        else:
            queryset = queryset.filter(org_id='')

        entries = list(queryset.order_by('-updated_at'))
        effective_entries = _pick_effective_entries(entries)
        month_days = _month_days(first_day, last_day)

        summary = {
            'present': 0,
            'wfh': 0,
            'on_duty': 0,
            'half_day': 0,
            'leave': 0,
            'absent': 0,
        }
        calendar = []

        for day in month_days:
            entry = effective_entries.get((request.user.id, day))
            status_value = entry.status if entry else 'not_marked'
            if status_value in summary:
                summary[status_value] += 1
            calendar.append({
                'date': day.isoformat(),
                'status': status_value,
                'approval_status': entry.approval_status if entry else None,
                'late_minutes': int(entry.late_minutes or 0) if entry else 0,
                'hours_worked': float(entry.hours_worked or 0) if entry else 0,
                'is_regularization': bool(entry.is_regularization) if entry else False,
            })

        recent_entries = sorted(
            [
                entry for (user_id, _), entry in effective_entries.items()
                if user_id == request.user.id
            ],
            key=lambda item: (item.entry_date, item.updated_at),
            reverse=True,
        )[:12]

        today_entry = effective_entries.get((request.user.id, timezone.localdate()))

        return Response({
            'month': first_day.strftime('%Y-%m'),
            'server_today': timezone.localdate().isoformat(),
            'calendar': calendar,
            'summary': summary,
            'recent_entries': AttendanceEntrySerializer(recent_entries, many=True, context={'request': request}).data,
            'today_entry': AttendanceEntrySerializer(today_entry, context={'request': request}).data if today_entry else None,
        })


class MyDeskAttendanceEntryCreateView(OrgScopedBaseAPIView):
    parser_classes = [JSONParser]

    def post(self, request):
        org_id = self.get_org_id()
        today = timezone.localdate()

        entry_date = _parse_date_value(request.data.get('entry_date')) or today
        if entry_date > today:
            return Response({'entry_date': 'Future date attendance cannot be submitted.'}, status=status.HTTP_400_BAD_REQUEST)

        # Shift lock: after 10 PM same day, employee must use regularization
        if entry_date == today and _should_lock_entry(entry_date):
            return Response(
                {'entry_date': 'Attendance for today is locked after 10 PM. Use regularization.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        in_time = _parse_time_value(request.data.get('in_time'))
        out_time = _parse_time_value(request.data.get('out_time'))
        if in_time and out_time and out_time <= in_time:
            return Response({'out_time': 'Out time must be later than in time.'}, status=status.HTTP_400_BAD_REQUEST)

        is_regularization = bool(entry_date < today)
        regularization_reason = (request.data.get('regularization_reason') or '').strip()

        if is_regularization and not regularization_reason:
            return Response({'regularization_reason': 'Reason is required for regularization.'}, status=status.HTTP_400_BAD_REQUEST)

        # Regularization limit check (same calendar month only)
        if is_regularization:
            current_month_start = date(today.year, today.month, 1)
            if entry_date.year != today.year or entry_date.month != today.month:
                return Response(
                    {'entry_date': 'Regularization is only allowed within the current calendar month.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            rb = _effective_rulebook(request.user)
            used_this_month = AttendanceEntry.objects.filter(
                org_id=org_id,
                user=request.user,
                is_regularization=True,
                entry_date__gte=current_month_start,
                entry_date__lte=today,
                is_active=True,
            ).exclude(entry_date=entry_date).exclude(approval_status='rejected').count()
            if used_this_month >= rb.regularization_limit_per_month:
                return Response(
                    {'regularization_reason': f'Regularization limit of {rb.regularization_limit_per_month} days/month reached.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        note = (request.data.get('note') or '').strip()
        on_duty_detail = (request.data.get('on_duty_detail') or '').strip()

        # Auto-status engine: compute status from In/Out times + rulebook
        rb = _effective_rulebook(request.user)
        auto_status, deduction_days, late_minutes, early_leave_minutes, hours_worked, score_points = _auto_compute_status(
            in_time, out_time, rulebook=rb
        )

        # Allow explicit WFH / Leave override from employee (but not Present/Absent/Half-Day)
        requested_status = str(request.data.get('status') or '').strip().lower()
        if requested_status in ('wfh', 'leave'):
            # Employee explicitly marking WFH or Leave — trust it, no deduction
            final_status = requested_status
            deduction_days = 0
            score_points = 100
        else:
            final_status = auto_status

        work_mode_val = str(request.data.get('work_mode') or '').strip().lower()
        if work_mode_val not in ('wfo', 'wfh', 'unknown'):
            if final_status == 'wfh':
                work_mode_val = 'wfh'
            elif final_status in ('present', 'half_day'):
                work_mode_val = 'wfo'
            else:
                work_mode_val = 'unknown'

        # Approval status: regularizations go to pending (HR must approve), today goes approved
        if is_regularization:
            approval_status_val = 'pending'
        else:
            approval_status_val = 'approved'

        existing_entry = AttendanceEntry.objects.filter(
            org_id=org_id,
            user=request.user,
            entry_date=entry_date,
            is_active=True,
        ).order_by('-updated_at').first()

        if existing_entry:
            item = existing_entry
            item.in_time = in_time
            item.out_time = out_time
            item.status = final_status
            item.auto_status = auto_status
            item.work_mode = work_mode_val
            item.note = note
            item.on_duty_detail = on_duty_detail
            item.is_regularization = is_regularization
            item.regularization_reason = regularization_reason
            item.approval_status = approval_status_val
            item.source = 'self'
            item.late_minutes = late_minutes
            item.early_leave_minutes = early_leave_minutes
            item.hours_worked = hours_worked
            item.salary_deduction_days = deduction_days
            item.attendance_score_points = score_points
            item.hr_override_status = ''
            item.hr_override_reason = ''
            item.hr_override_by = None
            item.hr_override_at = None
            item.rejection_reason = ''
            item.is_active = True
            if not is_regularization:
                item.approved_by = None
                item.approved_at = timezone.now()
            item.save()
        else:
            item = AttendanceEntry.objects.create(
                org_id=org_id,
                user=request.user,
                entry_date=entry_date,
                in_time=in_time,
                out_time=out_time,
                status=final_status,
                auto_status=auto_status,
                work_mode=work_mode_val,
                note=note,
                on_duty_detail=on_duty_detail,
                is_regularization=is_regularization,
                regularization_reason=regularization_reason,
                approval_status=approval_status_val,
                source='self',
                late_minutes=late_minutes,
                early_leave_minutes=early_leave_minutes,
                hours_worked=hours_worked,
                salary_deduction_days=deduction_days,
                attendance_score_points=score_points,
                approved_by=None,
                approved_at=timezone.now() if not is_regularization else None,
                rejection_reason='',
                is_active=True,
            )

        AttendanceEntry.objects.filter(
            org_id=org_id,
            user=request.user,
            entry_date=entry_date,
            is_active=True,
        ).exclude(id=item.id).update(is_active=False)

        status_code = status.HTTP_200_OK if existing_entry else status.HTTP_201_CREATED
        return Response(AttendanceEntrySerializer(item, context={'request': request}).data, status=status_code)


class HrAttendanceTodayView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
        'PUT': 'human_resources:attendance_dashboard:edit',
    }
    parser_classes = [JSONParser]

    def _resolve_date(self, value):
        return _parse_date_value(value) or timezone.localdate()

    def _build_rows(self, target_date):
        org_id = self.get_org_id()
        users = list(_organization_users(org_id))
        user_ids = [user.id for user in users]

        entries = AttendanceEntry.objects.select_related('user').filter(
            org_id=org_id,
            entry_date=target_date,
            user_id__in=user_ids,
            is_active=True,
        ).order_by('-updated_at')

        effective_by_user = {}
        for entry in entries:
            current = effective_by_user.get(entry.user_id)
            if current is None:
                effective_by_user[entry.user_id] = entry
                continue
            if current.approval_status != 'approved' and entry.approval_status == 'approved':
                effective_by_user[entry.user_id] = entry
                continue
            if current.approval_status == entry.approval_status and entry.updated_at > current.updated_at:
                effective_by_user[entry.user_id] = entry

        rows = []
        for user in users:
            entry = effective_by_user.get(user.id)
            rows.append({
                'user_id': user.id,
                'employee_name': user.get_full_name() or user.first_name or user.username or user.email,
                'email': user.email,
                'status': entry.status if entry else 'absent',
                'in_time': entry.in_time.strftime('%H:%M') if entry and entry.in_time else '',
                'out_time': entry.out_time.strftime('%H:%M') if entry and entry.out_time else '',
                'note': entry.note if entry else '',
                'on_duty_detail': entry.on_duty_detail if entry else '',
                'late_minutes': int(entry.late_minutes or 0) if entry else 0,
                'approval_status': entry.approval_status if entry else 'approved',
                'record_id': entry.id if entry else None,
                'auto_status': entry.auto_status if entry else '',
                'hr_override_status': entry.hr_override_status if entry else '',
                'salary_deduction_days': float(entry.salary_deduction_days or 0) if entry else 0,
                'attendance_score_points': entry.attendance_score_points if entry else 100,
                'work_mode': entry.work_mode if entry else 'unknown',
            })

        return rows

    def get(self, request):
        target_date = self._resolve_date(request.query_params.get('date'))
        return Response({
            'date': target_date.isoformat(),
            'rows': self._build_rows(target_date),
        })

    def put(self, request):
        org_id = self.get_org_id()
        target_date = self._resolve_date(request.data.get('date'))
        rows = request.data.get('rows')
        if not isinstance(rows, list):
            return Response({'rows': 'rows must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

        allowed_statuses = {choice[0] for choice in AttendanceEntry.STATUS_CHOICES}
        allowed_user_ids = set(_organization_users(org_id).values_list('id', flat=True))
        saved_count = 0

        # Pre-load rulebooks for all users in batch
        rulebook_map = {
            rb.user_id: rb
            for rb in AttendanceRulebook.objects.filter(
                org_id=org_id,
                user_id__in=list(allowed_user_ids),
            )
        }

        for row in rows:
            try:
                user_id = int(row.get('user_id'))
            except (TypeError, ValueError):
                continue
            if user_id not in allowed_user_ids:
                continue

            in_time = _parse_time_value(row.get('in_time'))
            out_time = _parse_time_value(row.get('out_time'))
            if in_time and out_time and out_time <= in_time:
                continue

            # Use auto-status engine for HR bulk marking too
            rb = rulebook_map.get(user_id) or _rulebook_defaults()
            auto_status, deduction_days, late_minutes, early_leave_minutes, hours_worked, score_points = _auto_compute_status(
                in_time, out_time, rulebook=rb,
            )

            # HR can override status explicitly from the UI
            status_value = str(row.get('status') or '').strip().lower()
            incoming_work_mode = None
            if status_value == 'half_day_wfo':
                status_value = 'half_day'
                incoming_work_mode = 'wfo'
            elif status_value == 'half_day_wfh':
                status_value = 'half_day'
                incoming_work_mode = 'wfh'

            if status_value in allowed_statuses:
                final_status = status_value
                # If HR explicitly sets status, record it as an override
                hr_override = status_value != auto_status
            else:
                final_status = auto_status
                hr_override = False

            # ── Fix: recalculate score_points & deduction_days when HR overrides ──
            if hr_override:
                if final_status == 'absent':
                    score_points = 0
                    deduction_days = DEDUCTION_FULL_DAY
                elif final_status == 'half_day':
                    score_points = 50
                    deduction_days = DEDUCTION_HALF_DAY
                elif final_status == 'leave':
                    score_points = 0
                    deduction_days = DEDUCTION_FULL_DAY
                elif final_status in ('present', 'wfh', 'on_duty'):
                    score_points = 100
                    deduction_days = DEDUCTION_NONE

            item = AttendanceEntry.objects.filter(
                org_id=org_id,
                user_id=user_id,
                entry_date=target_date,
                approval_status='approved',
                is_active=True,
            ).order_by('-updated_at').first()

            if item is None:
                item = AttendanceEntry(
                    org_id=org_id,
                    user_id=user_id,
                    entry_date=target_date,
                )

            item.status = final_status
            item.auto_status = auto_status
            item.in_time = in_time
            item.out_time = out_time
            item.note = (row.get('note') or '').strip()
            item.on_duty_detail = (row.get('on_duty_detail') or '').strip() if final_status == 'on_duty' else ''
            item.is_regularization = False
            item.regularization_reason = ''
            item.approval_status = 'approved'
            item.source = 'hr'
            item.late_minutes = late_minutes
            item.early_leave_minutes = early_leave_minutes
            item.hours_worked = hours_worked
            item.salary_deduction_days = deduction_days
            item.attendance_score_points = score_points
            item.approved_by = request.user
            item.approved_at = timezone.now()
            item.rejection_reason = ''
            item.is_active = True
            if incoming_work_mode:
                item.work_mode = incoming_work_mode
            elif final_status == 'present':
                item.work_mode = 'wfo'
            elif final_status == 'wfh':
                item.work_mode = 'wfh'

            if hr_override:
                item.hr_override_status = final_status
                item.hr_override_reason = (row.get('override_reason') or 'HR bulk marking').strip()
                item.hr_override_by = request.user
                item.hr_override_at = timezone.now()
            item.save()

            AttendanceEntry.objects.filter(
                org_id=org_id,
                user_id=user_id,
                entry_date=target_date,
                is_active=True,
            ).exclude(id=item.id).update(is_active=False)

            saved_count += 1

        return Response({
            'date': target_date.isoformat(),
            'saved_count': saved_count,
            'rows': self._build_rows(target_date),
        })


class HrAttendanceMonthlyRegisterView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
    }
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        first_day, last_day = _parse_month_bounds(request.query_params.get('month'))
        month_days = _month_days(first_day, last_day)

        users = list(_organization_users(org_id))
        user_ids = [user.id for user in users]

        entries = list(
            AttendanceEntry.objects.select_related('user').filter(
                org_id=org_id,
                user_id__in=user_ids,
                entry_date__gte=first_day,
                entry_date__lte=last_day,
                approval_status='approved',
                is_active=True,
            ).order_by('-updated_at')
        )
        effective_entries = _pick_effective_entries(entries)

        rows = []
        for user in users:
            totals = {
                'present': 0,
                'absent': 0,
                'wfh': 0,
                'half_day': 0,
                'on_duty': 0,
                'leave': 0,
            }
            late_marks = 0
            payable_days = 0.0
            cells = []

            for day in month_days:
                entry = effective_entries.get((user.id, day))
                status_value = entry.status if entry else 'absent'
                if status_value in totals:
                    totals[status_value] += 1
                payable_days += _status_payable_value(status_value)
                if entry and int(entry.late_minutes or 0) > 0:
                    late_marks += 1

                cells.append({
                    'date': day.isoformat(),
                    'status': status_value,
                    'work_mode': entry.work_mode if entry else 'unknown',
                    'late_minutes': int(entry.late_minutes or 0) if entry else 0,
                })

            rows.append({
                'user_id': user.id,
                'employee_name': user.get_full_name() or user.first_name or user.username or user.email,
                'cells': cells,
                'totals': {
                    **totals,
                    'late_marks': late_marks,
                    'payable_days': round(payable_days, 2),
                },
            })

        return Response({
            'month': first_day.strftime('%Y-%m'),
            'days': [day.isoformat() for day in month_days],
            'rows': rows,
        })


class HrAttendanceEmployeeSummaryView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
    }
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        first_day, last_day = _parse_month_bounds(request.query_params.get('month'))
        month_days = _month_days(first_day, last_day)

        users = list(_organization_users(org_id))
        user_ids = [user.id for user in users]

        entries = list(
            AttendanceEntry.objects.select_related('user').filter(
                org_id=org_id,
                user_id__in=user_ids,
                entry_date__gte=first_day,
                entry_date__lte=last_day,
                approval_status='approved',
                is_active=True,
            ).order_by('-updated_at')
        )
        effective_entries = _pick_effective_entries(entries)

        rows = []
        for user in users:
            present_days = 0
            wfh_days = 0
            absent_days = 0
            half_days = 0
            leave_days = 0
            on_duty_days = 0
            late_marks = 0
            total_hours = 0.0

            # Fetch workforce member details
            from core.models import WorkforceMember
            workforce_member = None
            if user.email:
                workforce_member = WorkforceMember.objects.filter(org_id=org_id, email__iexact=user.email, is_archived=False).first()
            if not workforce_member:
                full_name = f"{user.first_name} {user.last_name}".strip()
                if not full_name and hasattr(user, 'profile') and user.profile.full_name:
                    full_name = user.profile.full_name.strip()
                if full_name:
                    workforce_member = WorkforceMember.objects.filter(org_id=org_id, full_name__iexact=full_name, is_archived=False).first()

            joining_date = workforce_member.date_of_joining if workforce_member else None
            leaving_date = workforce_member.date_of_leaving if workforce_member else None
            if not joining_date:
                joining_date = user.date_joined.date() if user.date_joined else first_day

            rb = _effective_rulebook(user)

            for day in month_days:
                # Check mid-month joiner/leaver bounds
                if day < joining_date:
                    absent_days += 1
                    continue
                if leaving_date and day > leaving_date:
                    absent_days += 1
                    continue

                entry = effective_entries.get((user.id, day))
                status_value = entry.status if entry else 'absent'

                # Override for non-working days if missing entry
                if status_value == 'absent':
                    if getattr(settings, 'USE_SATURDAY_POLICY', False):
                        if not _is_working_day(day, rb):
                            status_value = 'present'
                    if status_value == 'absent' and getattr(settings, 'USE_HOLIDAY_CALENDAR', False):
                        if is_holiday(org_id, day):
                            status_value = 'present'

                if status_value == 'present':
                    present_days += 1
                elif status_value == 'wfh':
                    wfh_days += 1
                elif status_value == 'half_day':
                    half_days += 1
                elif status_value == 'leave':
                    leave_days += 1
                elif status_value == 'on_duty':
                    on_duty_days += 1
                else:
                    absent_days += 1

                if entry:
                    total_hours += float(entry.hours_worked or 0)
                    if int(entry.late_minutes or 0) > 0:
                        late_marks += 1

            payable_days = present_days + wfh_days + on_duty_days + leave_days + (half_days * 0.5)
            deduction_days = absent_days + (half_days * 0.5)
            expected_hours = payable_days * 8
            ot_comp_off = max(0.0, round(total_hours - expected_hours, 2))

            final_payable_days = payable_days
            if getattr(settings, 'USE_GRANULAR_DEDUCTIONS', False):
                user_entries = [effective_entries.get((user.id, d)) for d in month_days]
                user_entries = [e for e in user_entries if e is not None]
                total_deductions_days = sum(
                    float(e.salary_deduction_days or 0)
                    for e in user_entries
                    if e.status not in ('absent', 'half_day') and joining_date <= e.entry_date <= (leaving_date or last_day)
                )
                final_payable_days = max(0.0, final_payable_days - total_deductions_days)

            rows.append({
                'user_id': user.id,
                'employee_name': user.get_full_name() or user.first_name or user.username or user.email,
                'present_days': present_days,
                'wfh_days': wfh_days,
                'absent_days': absent_days,
                'half_days': half_days,
                'leave_days': leave_days,
                'on_duty_days': on_duty_days,
                'late_marks': late_marks,
                'deduction_days': round(deduction_days, 2),
                'ot_comp_off': ot_comp_off,
                'total_hours': round(total_hours, 2),
                'payable_days': round(payable_days, 2),
                'final_payable_days': round(final_payable_days, 3),
            })

        return Response({
            'month': first_day.strftime('%Y-%m'),
            'rows': rows,
        })


# ─────────────────────────────────────────────────────────────────────────────
# NEW: Attendance Rulebook Views
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceRulebookView(OrgScopedBaseAPIView):
    """
    GET  /api/mydesk/attendance/rulebook/      → employee views own rulebook
    GET  /api/hr/attendance/rulebook/<user_id>/ → HR views any employee's rulebook
    PUT  /api/hr/attendance/rulebook/<user_id>/ → HR edits any employee's rulebook
    """
    parser_classes = [JSONParser]

    def _serialize_rulebook(self, rb):
        return {
            'shift_start': rb.shift_start.strftime('%H:%M'),
            'shift_end': rb.shift_end.strftime('%H:%M'),
            'lunch_duration_minutes': rb.lunch_duration_minutes,
            'grace_period_minutes': rb.grace_period_minutes,
            'late_deduction_threshold_minutes': rb.late_deduction_threshold_minutes,
            'half_day_late_threshold_minutes': rb.half_day_late_threshold_minutes,
            'early_leave_deduction_minutes': rb.early_leave_deduction_minutes,
            'half_day_early_leave_minutes': rb.half_day_early_leave_minutes,
            'regularization_limit_per_month': rb.regularization_limit_per_month,
            'employee_type': rb.employee_type,
            'weekly_off': rb.weekly_off,
            'saturday_working': rb.saturday_working,
            'last_edited_by': _actor_display_name(rb.last_edited_by) if rb.last_edited_by else '',
            'last_edited_on': rb.updated_at.isoformat() if rb.updated_at else '',
        }

    def get(self, request, user_id=None):
        org_id = self.get_org_id()
        target_user = request.user

        if user_id is not None:
            # HR path
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        rb = _get_rulebook(target_user)
        if rb is None:
            # Return defaults
            rb = _rulebook_defaults()
            return Response({**self._serialize_rulebook(rb), 'is_default': True})
        return Response({**self._serialize_rulebook(rb), 'is_default': False})

    def put(self, request, user_id=None):
        """HR-only: edit a user's rulebook."""
        org_id = self.get_org_id()
        if user_id is None:
            return Response({'detail': 'HR user_id required to edit rulebook.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        rb, _ = AttendanceRulebook.objects.get_or_create(
            org_id=org_id,
            user=target_user,
            defaults={
                'last_edited_by': request.user,
            }
        )

        data = request.data
        TIME_FMT = ['%H:%M', '%H:%M:%S']

        def _parse_time_str(val):
            for fmt in TIME_FMT:
                try:
                    return datetime.strptime(str(val or '').strip(), fmt).time()
                except ValueError:
                    continue
            return None

        def _safe_int(val, default):
            try:
                return max(0, int(val))
            except (TypeError, ValueError):
                return default

        if 'shift_start' in data:
            t = _parse_time_str(data['shift_start'])
            if t:
                rb.shift_start = t
        if 'shift_end' in data:
            t = _parse_time_str(data['shift_end'])
            if t:
                rb.shift_end = t

        rb.lunch_duration_minutes = _safe_int(data.get('lunch_duration_minutes'), rb.lunch_duration_minutes)
        rb.grace_period_minutes = _safe_int(data.get('grace_period_minutes'), rb.grace_period_minutes)
        rb.late_deduction_threshold_minutes = _safe_int(data.get('late_deduction_threshold_minutes'), rb.late_deduction_threshold_minutes)
        rb.half_day_late_threshold_minutes = _safe_int(data.get('half_day_late_threshold_minutes'), rb.half_day_late_threshold_minutes)
        rb.early_leave_deduction_minutes = _safe_int(data.get('early_leave_deduction_minutes'), rb.early_leave_deduction_minutes)
        rb.half_day_early_leave_minutes = _safe_int(data.get('half_day_early_leave_minutes'), rb.half_day_early_leave_minutes)
        rb.regularization_limit_per_month = _safe_int(data.get('regularization_limit_per_month'), rb.regularization_limit_per_month)

        et = str(data.get('employee_type') or rb.employee_type).strip()
        if et in {c[0] for c in AttendanceRulebook.EMPLOYEE_TYPE_CHOICES}:
            rb.employee_type = et

        wo = str(data.get('weekly_off') or rb.weekly_off).strip()
        if wo in {c[0] for c in AttendanceRulebook.WEEKLY_OFF_CHOICES}:
            rb.weekly_off = wo

        sw = str(data.get('saturday_working') or rb.saturday_working).strip()
        if sw in {c[0] for c in AttendanceRulebook.SATURDAY_WORKING_CHOICES}:
            rb.saturday_working = sw

        rb.last_edited_by = request.user
        rb.save()

        return Response({**self._serialize_rulebook(rb), 'is_default': False})


class MyAttendanceRulebookView(OrgScopedBaseAPIView):
    """Employee view of their own rulebook (read-only)."""
    parser_classes = [JSONParser]

    def get(self, request):
        rb = _get_rulebook(request.user)
        defaults = _rulebook_defaults()
        if rb is None:
            return Response({
                'shift_start': defaults.shift_start.strftime('%H:%M'),
                'shift_end': defaults.shift_end.strftime('%H:%M'),
                'lunch_duration_minutes': defaults.lunch_duration_minutes,
                'grace_period_minutes': defaults.grace_period_minutes,
                'late_deduction_threshold_minutes': defaults.late_deduction_threshold_minutes,
                'half_day_late_threshold_minutes': defaults.half_day_late_threshold_minutes,
                'early_leave_deduction_minutes': defaults.early_leave_deduction_minutes,
                'half_day_early_leave_minutes': defaults.half_day_early_leave_minutes,
                'regularization_limit_per_month': defaults.regularization_limit_per_month,
                'employee_type': defaults.employee_type,
                'weekly_off': defaults.weekly_off,
                'saturday_working': defaults.saturday_working,
                'last_edited_by': '',
                'last_edited_on': '',
                'is_default': True,
            })
        return Response({
            'shift_start': rb.shift_start.strftime('%H:%M'),
            'shift_end': rb.shift_end.strftime('%H:%M'),
            'lunch_duration_minutes': rb.lunch_duration_minutes,
            'grace_period_minutes': rb.grace_period_minutes,
            'late_deduction_threshold_minutes': rb.late_deduction_threshold_minutes,
            'half_day_late_threshold_minutes': rb.half_day_late_threshold_minutes,
            'early_leave_deduction_minutes': rb.early_leave_deduction_minutes,
            'half_day_early_leave_minutes': rb.half_day_early_leave_minutes,
            'regularization_limit_per_month': rb.regularization_limit_per_month,
            'employee_type': rb.employee_type,
            'weekly_off': rb.weekly_off,
            'saturday_working': rb.saturday_working,
            'last_edited_by': _actor_display_name(rb.last_edited_by) if rb.last_edited_by else '',
            'last_edited_on': rb.updated_at.isoformat() if rb.updated_at else '',
            'is_default': False,
        })


class HrRegularizationQueueView(OrgScopedBaseAPIView):
    """
    GET  /api/hr/attendance/regularizations/   → list pending regularizations
    PUT  /api/hr/attendance/regularizations/<id>/  → approve/reject
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
        'PUT': 'human_resources:attendance_dashboard:edit',
    }
    parser_classes = [JSONParser]

    def _serialize_regularization(self, entry):
        user = entry.user
        return {
            'id': entry.id,
            'user_id': user.id,
            'employee_name': user.get_full_name() or user.first_name or user.username or user.email,
            'email': user.email,
            'entry_date': entry.entry_date.isoformat(),
            'in_time': entry.in_time.strftime('%H:%M') if entry.in_time else '',
            'out_time': entry.out_time.strftime('%H:%M') if entry.out_time else '',
            'auto_status': entry.auto_status or entry.status,
            'current_status': entry.status,
            'regularization_reason': entry.regularization_reason,
            'approval_status': entry.approval_status,
            'rejection_reason': entry.rejection_reason,
            'late_minutes': int(entry.late_minutes or 0),
            'hours_worked': float(entry.hours_worked or 0),
            'created_at': _to_iso_datetime(entry.created_at),
        }

    def get(self, request):
        org_id = self.get_org_id()
        first_day, last_day = _parse_month_bounds(request.query_params.get('month'))
        approval_filter = request.query_params.get('approval_status', 'pending')

        qs = AttendanceEntry.objects.select_related('user').filter(
            org_id=org_id,
            is_regularization=True,
            is_active=True,
        )
        if approval_filter in ('pending', 'approved', 'rejected'):
            qs = qs.filter(approval_status=approval_filter)

        if request.query_params.get('month'):
            qs = qs.filter(entry_date__gte=first_day, entry_date__lte=last_day)

        qs = qs.order_by('-entry_date', '-created_at')[:100]
        return Response({
            'rows': [self._serialize_regularization(e) for e in qs],
        })

    def put(self, request, entry_id=None):
        if entry_id is None:
            return Response({'detail': 'entry_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        org_id = self.get_org_id()

        try:
            entry = AttendanceEntry.objects.select_related('user').get(
                id=entry_id,
                org_id=org_id,
                is_regularization=True,
            )
        except AttendanceEntry.DoesNotExist:
            return Response({'detail': 'Regularization entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        action = str(request.data.get('action') or '').strip().lower()
        if action == 'approve':
            entry.approval_status = 'approved'
            entry.rejection_reason = ''
            entry.approved_by = request.user
            entry.approved_at = timezone.now()
            # Recalculate status with rulebook
            rb = _effective_rulebook(entry.user)
            auto_status, deduction_days, late_minutes, early_leave_minutes, hours_worked, score_points = _auto_compute_status(
                entry.in_time, entry.out_time, rulebook=rb,
            )
            entry.status = auto_status
            entry.auto_status = auto_status
            entry.late_minutes = late_minutes
            entry.early_leave_minutes = early_leave_minutes
            entry.hours_worked = hours_worked
            entry.salary_deduction_days = deduction_days
            entry.attendance_score_points = score_points
            entry.save()

            # Push Notification
            try:
                from core.services.notifications import push_unified_notification
                from core.models import UnifiedNotification
                push_unified_notification(
                    recipient=entry.user,
                    actor=request.user,
                    module=UnifiedNotification.MODULE_LEAVE,
                    action=UnifiedNotification.ACTION_REMINDER,
                    title="Regularization Approved",
                    message=f"Your attendance regularization request for {entry.entry_date.strftime('%b %d, %Y')} has been approved.",
                    entity_type='attendance_regularization',
                    entity_id=str(entry.id),
                    priority='high',
                )
            except Exception as e:
                LOGGER.error(f"Failed to send regularization approval notification: {e}")

        elif action == 'reject':
            reason = str(request.data.get('reason') or '').strip()
            entry.approval_status = 'rejected'
            entry.rejection_reason = reason or 'Rejected by HR'
            entry.save()

            # Push Notification
            try:
                from core.services.notifications import push_unified_notification
                from core.models import UnifiedNotification
                push_unified_notification(
                    recipient=entry.user,
                    actor=request.user,
                    module=UnifiedNotification.MODULE_LEAVE,
                    action=UnifiedNotification.ACTION_REMINDER,
                    title="Regularization Rejected",
                    message=f"Your attendance regularization request for {entry.entry_date.strftime('%b %d, %Y')} was rejected. Reason: {entry.rejection_reason}",
                    entity_type='attendance_regularization',
                    entity_id=str(entry.id),
                    priority='high',
                )
            except Exception as e:
                LOGGER.error(f"Failed to send regularization rejection notification: {e}")

        else:
            return Response({'action': 'Must be approve or reject.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self._serialize_regularization(entry))


class HrAttendanceOverrideView(OrgScopedBaseAPIView):
    """
    PUT /api/hr/attendance/override/<entry_id>/
    HR can override the status of any attendance entry with a reason.
    Override is logged + visible to employee (transparency).
    """
    permission_classes = [HasModulePermission]
    required_permissions = {
        'PUT': 'human_resources:attendance_dashboard:edit',
    }
    parser_classes = [JSONParser]

    def put(self, request, entry_id):
        org_id = self.get_org_id()
        try:
            entry = AttendanceEntry.objects.select_related('user').get(
                id=entry_id,
                org_id=org_id,
                is_active=True,
            )
        except AttendanceEntry.DoesNotExist:
            return Response({'detail': 'Attendance entry not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_status = str(request.data.get('status') or '').strip().lower()
        allowed_statuses = {choice[0] for choice in AttendanceEntry.STATUS_CHOICES}
        if new_status not in allowed_statuses:
            return Response({'status': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)

        reason = str(request.data.get('reason') or '').strip()
        if not reason:
            return Response({'reason': 'Override reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Recompute deduction based on overridden status
        if new_status in ('absent', 'leave'):
            deduction = DEDUCTION_FULL_DAY
            score = 0
        elif new_status == 'half_day':
            deduction = DEDUCTION_HALF_DAY
            score = 50
        elif new_status in ('present', 'wfh', 'on_duty'):
            deduction = 0
            score = 100
        else:
            deduction = entry.salary_deduction_days
            score = entry.attendance_score_points
        entry.status = new_status
        entry.hr_override_status = new_status
        entry.hr_override_reason = reason
        entry.hr_override_by = request.user
        entry.hr_override_at = timezone.now()
        entry.salary_deduction_days = deduction
        entry.attendance_score_points = score
        entry.approval_status = 'approved'

        # Update work mode based on HR override
        work_mode_val = str(request.data.get('work_mode') or '').strip().lower()
        if work_mode_val in ('wfo', 'wfh', 'unknown'):
            entry.work_mode = work_mode_val
        else:
            if new_status == 'wfh':
                entry.work_mode = 'wfh'
            elif new_status == 'present':
                entry.work_mode = 'wfo'

        entry.save()

        return Response({
            'id': entry.id,
            'status': entry.status,
            'auto_status': entry.auto_status,
            'hr_override_status': entry.hr_override_status,
            'hr_override_reason': entry.hr_override_reason,
            'hr_override_by': _actor_display_name(entry.hr_override_by),
            'hr_override_at': _to_iso_datetime(entry.hr_override_at),
            'salary_deduction_days': float(entry.salary_deduction_days),
            'attendance_score_points': entry.attendance_score_points,
        })


class AttendanceScoreView(OrgScopedBaseAPIView):
    """
    GET /api/mydesk/attendance/score/         → employee's own monthly score
    GET /api/hr/attendance/score/?month=YYYY-MM → all employees' scores (HR)
    """
    parser_classes = [JSONParser]

    def _compute_score_for_user(self, user, org_id, first_day, last_day, month_days):
        entries = list(
            AttendanceEntry.objects.filter(
                org_id=org_id,
                user=user,
                entry_date__gte=first_day,
                entry_date__lte=last_day,
                approval_status='approved',
                is_active=True,
            ).order_by('-updated_at')
        )
        effective = _pick_effective_entries(entries)

        total_score = 0
        working_days = 0

        for day in month_days:
            entry = effective.get((user.id, day))
            if entry is None:
                # Not marked = absent = 0 score
                total_score += 0
                working_days += 1
            else:
                total_score += int(entry.attendance_score_points if entry.attendance_score_points is not None else 100)
                working_days += 1

        if working_days == 0:
            return 100.0
        return round((total_score / (working_days * 100)) * 100, 1)

    def get(self, request, user_id=None):
        org_id = self.get_org_id()
        first_day, last_day = _parse_month_bounds(request.query_params.get('month'))
        month_days = _month_days(first_day, last_day)

        if user_id is not None:
            # HR: single user score
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)
            score = self._compute_score_for_user(target_user, org_id, first_day, last_day, month_days)
            return Response({'user_id': user_id, 'score': score, 'month': first_day.strftime('%Y-%m')})

        # Employee: own score
        score = self._compute_score_for_user(request.user, org_id, first_day, last_day, month_days)
        return Response({'score': score, 'month': first_day.strftime('%Y-%m')})


class HrAttendanceScoreListView(OrgScopedBaseAPIView):
    """GET /api/hr/attendance/scores/ → all employees' attendance scores for a month."""
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
    }
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        first_day, last_day = _parse_month_bounds(request.query_params.get('month'))
        month_days = _month_days(first_day, last_day)

        users = list(_organization_users(org_id))
        user_ids = [u.id for u in users]

        entries = list(
            AttendanceEntry.objects.filter(
                org_id=org_id,
                user_id__in=user_ids,
                entry_date__gte=first_day,
                entry_date__lte=last_day,
                approval_status='approved',
                is_active=True,
            ).order_by('-updated_at')
        )
        effective = _pick_effective_entries(entries)

        rows = []
        for user in users:
            total_score = 0
            working_days = len(month_days)
            late_count = 0
            absent_count = 0

            for day in month_days:
                entry = effective.get((user.id, day))
                if entry is None:
                    total_score += 0
                    absent_count += 1
                else:
                    total_score += int(entry.attendance_score_points if entry.attendance_score_points is not None else 100)
                    if entry.status == 'absent':
                        absent_count += 1
                    if int(entry.late_minutes or 0) > 0:
                        late_count += 1

            score = round((total_score / (working_days * 100)) * 100, 1) if working_days else 100.0
            rows.append({
                'user_id': user.id,
                'employee_name': user.get_full_name() or user.first_name or user.username or user.email,
                'score': score,
                'late_count': late_count,
                'absent_count': absent_count,
            })

        return Response({
            'month': first_day.strftime('%Y-%m'),
            'rows': sorted(rows, key=lambda r: r['score']),
        })


TASK_TRACKER_STATUS_LABELS = {
    'pending': 'Pending',
    'in_progress': 'In Progress',
    'completed': 'Completed',
}


def _parse_int(value):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError):
        return None


def _task_due_date_from_meta(meta):
    values = meta if isinstance(meta, dict) else {}
    return _parse_date_value(
        values.get('dueDate')
        or values.get('due_date')
        or values.get('task_due_date')
    )


def _task_status_from_item(item):
    meta = item.meta if isinstance(item.meta, dict) else {}
    raw_status = str(meta.get('status') or '').strip().lower()

    if item.is_done or raw_status in {'done', 'completed', 'complete'}:
        return 'completed'
    if raw_status in {'in_progress', 'in-progress', 'progress'}:
        return 'in_progress'
    return 'pending'


def _task_priority_label(priority):
    normalized = str(priority or '').strip().lower() or 'medium'
    if normalized == 'critical':
        return 'Critical'
    if normalized == 'high':
        return 'High'
    if normalized == 'low':
        return 'Low'
    return 'Medium'


def _task_status_label(status_value):
    return TASK_TRACKER_STATUS_LABELS.get(status_value, 'Pending')


def _task_reference_date(row):
    if row.get('due_date_obj'):
        return row['due_date_obj']
    created_at = row.get('created_at_obj')
    return created_at.date() if created_at else None


def _build_hr_master_task_tracker_dataset(org_id):
    users = list(_organization_users(org_id))
    user_map = {user.id: user for user in users}
    department_map = _build_workforce_department_map(org_id, users)
    today = timezone.localdate()

    rows = []
    queryset = PersonalTodoItem.objects.select_related('user').filter(org_id=org_id, meta__type='task').order_by('-created_at')

    for item in queryset:
        meta = item.meta if isinstance(item.meta, dict) else {}
        assignee_ids = _extract_task_assignee_ids(meta)
        assignee_id = _parse_int(meta.get('assignee_id')) or (assignee_ids[0] if assignee_ids else None) or item.user_id
        assignee_user = user_map.get(assignee_id)

        assignee_name = (
            (assignee_user.get_full_name() or assignee_user.first_name or assignee_user.username or assignee_user.email)
            if assignee_user
            else str(meta.get('assignee') or '').strip()
        )
        assignee_email = (assignee_user.email if assignee_user else '') or str(meta.get('assignee_email') or '').strip()
        department_name = str(department_map.get(assignee_id, '') or '').strip()

        status_value = _task_status_from_item(item)
        priority_value = _task_priority_from_meta(meta)
        due_date = _task_due_date_from_meta(meta)
        is_overdue = bool(due_date and due_date < today and status_value != 'completed')

        created_at = item.created_at
        created_date = created_at.date() if created_at else today
        days_open = max((today - created_date).days, 0)

        rows.append({
            'id': item.id,
            'title': str(meta.get('title') or item.text or 'Untitled Task').strip() or 'Untitled Task',
            'description': str(meta.get('description') or '').strip(),
            'assignee_id': assignee_id,
            'assignee_name': assignee_name,
            'assignee_email': assignee_email,
            'department': department_name,
            'priority': priority_value,
            'priority_label': _task_priority_label(priority_value),
            'status': status_value,
            'status_label': _task_status_label(status_value),
            'due_date_obj': due_date,
            'due_date': due_date.isoformat() if due_date else '',
            'created_at_obj': created_at,
            'created_at': created_at.isoformat() if created_at else None,
            'updated_at_obj': item.updated_at,
            'updated_at': item.updated_at.isoformat() if item.updated_at else None,
            'days_open': days_open,
            'is_overdue': is_overdue,
            'assigned_by_id': _parse_int(meta.get('assigned_by_id')),
        })

    members = []
    for user in users:
        members.append({
            'id': user.id,
            'name': user.get_full_name() or user.first_name or user.username or user.email,
            'email': user.email,
            'department': str(department_map.get(user.id, '') or '').strip(),
        })

    departments = sorted({str(entry.get('department') or '').strip() for entry in members if str(entry.get('department') or '').strip()})
    return rows, members, departments


def _apply_hr_master_task_tracker_filters(
    rows,
    *,
    search_text='',
    from_date=None,
    to_date=None,
    department='',
    priority='',
    status='',
    assignee_id=None,
    assigned_by_id=None,
):
    scoped_rows = []
    for row in rows:
        reference_date = _task_reference_date(row)
        if from_date and reference_date and reference_date < from_date:
            continue
        if to_date and reference_date and reference_date > to_date:
            continue

        department_value = str(row.get('department') or '').strip()
        if department and department_value.lower() != department.lower():
            continue

        if priority and str(row.get('priority') or '').strip().lower() != priority:
            continue

        if assignee_id and row.get('assignee_id') != assignee_id:
            continue

        if assigned_by_id and row.get('assigned_by_id') != assigned_by_id:
            continue

        if status:
            if status == 'overdue':
                if not row.get('is_overdue'):
                    continue
            elif status == 'active':
                if row.get('status') == 'completed':
                    continue
            elif row.get('status') != status:
                continue

        scoped_rows.append(row)

    normalized_search = str(search_text or '').strip().lower()
    if not normalized_search:
        return scoped_rows, list(scoped_rows)

    display_rows = []
    for row in scoped_rows:
        haystack = ' '.join([
            str(row.get('title') or ''),
            str(row.get('description') or ''),
            str(row.get('assignee_name') or ''),
            str(row.get('assignee_email') or ''),
            str(row.get('department') or ''),
            str(row.get('priority_label') or row.get('priority') or ''),
            str(row.get('status_label') or row.get('status') or ''),
        ]).lower()
        if normalized_search in haystack:
            display_rows.append(row)

    return scoped_rows, display_rows


def _hr_master_task_tracker_payload(scoped_rows, display_rows, members, departments):
    total_tasks = len(scoped_rows)
    completed_tasks = sum(1 for row in scoped_rows if row.get('status') == 'completed')
    overdue_tasks = sum(1 for row in scoped_rows if row.get('is_overdue'))
    active_tasks = total_tasks - completed_tasks
    completion_rate = round((completed_tasks / total_tasks) * 100, 1) if total_tasks else 0

    completed_days_open = [row.get('days_open', 0) for row in scoped_rows if row.get('status') == 'completed']
    if completed_days_open:
        avg_turnaround = round(sum(completed_days_open) / len(completed_days_open), 2)
    else:
        avg_turnaround = 0

    workload_by_user = {}
    for row in display_rows:
        user_id = row.get('assignee_id')
        if not user_id:
            continue
        if user_id not in workload_by_user:
            workload_by_user[user_id] = {
                'user_id': user_id,
                'name': row.get('assignee_name') or f'Member #{user_id}',
                'department': row.get('department') or '',
                'active_tasks': 0,
                'completed_tasks': 0,
                'overdue_tasks': 0,
            }

        bucket = workload_by_user[user_id]
        if row.get('status') == 'completed':
            bucket['completed_tasks'] += 1
        else:
            bucket['active_tasks'] += 1
        if row.get('is_overdue'):
            bucket['overdue_tasks'] += 1

    workload_cards = sorted(
        workload_by_user.values(),
        key=lambda value: (
            -(value.get('active_tasks', 0) + value.get('overdue_tasks', 0)),
            str(value.get('name') or '').lower(),
        ),
    )

    department_totals = {}
    for row in scoped_rows:
        department_name = str(row.get('department') or '').strip() or 'Unassigned'
        if department_name not in department_totals:
            department_totals[department_name] = {
                'department': department_name,
                'total_tasks': 0,
                'active_tasks': 0,
                'completed_tasks': 0,
                'overdue_tasks': 0,
            }

        bucket = department_totals[department_name]
        bucket['total_tasks'] += 1
        if row.get('status') == 'completed':
            bucket['completed_tasks'] += 1
        else:
            bucket['active_tasks'] += 1
        if row.get('is_overdue'):
            bucket['overdue_tasks'] += 1

    department_summary = sorted(department_totals.values(), key=lambda value: value['department'].lower())

    completion_by_member = []
    for card in workload_cards:
        member_total = int(card.get('active_tasks', 0)) + int(card.get('completed_tasks', 0))
        completion_by_member.append({
            'user_id': card.get('user_id'),
            'name': card.get('name'),
            'total_tasks': member_total,
            'completed_tasks': int(card.get('completed_tasks', 0)),
            'completion_rate': round((int(card.get('completed_tasks', 0)) / member_total) * 100, 1) if member_total else 0,
        })

    completion_by_department = []
    for item in department_summary:
        dept_total = int(item.get('total_tasks', 0))
        completion_by_department.append({
            'department': item.get('department'),
            'total_tasks': dept_total,
            'completed_tasks': int(item.get('completed_tasks', 0)),
            'completion_rate': round((int(item.get('completed_tasks', 0)) / dept_total) * 100, 1) if dept_total else 0,
        })

    overdue_by_day = {}
    for row in scoped_rows:
        if not row.get('is_overdue'):
            continue
        due_date = row.get('due_date_obj')
        if not due_date:
            continue
        key = due_date.isoformat()
        overdue_by_day[key] = overdue_by_day.get(key, 0) + 1
    overdue_over_time = [
        {'day': day_key, 'count': overdue_by_day[day_key]}
        for day_key in sorted(overdue_by_day.keys())
    ]

    activity_log = []
    for row in display_rows:
        event_type = 'created'
        detail = f"Task assigned to {row.get('assignee_name') or 'Unknown'}"
        event_at = row.get('created_at')

        if row.get('status') == 'completed':
            event_type = 'completed'
            detail = f"Task completed by {row.get('assignee_name') or 'Unknown'}"
            event_at = row.get('updated_at') or row.get('created_at')
        elif row.get('is_overdue'):
            event_type = 'overdue'
            detail = f"Task is overdue for {row.get('assignee_name') or 'Unknown'}"
            event_at = row.get('due_date')

        activity_log.append({
            'task_id': row.get('id'),
            'event_type': event_type,
            'event_at': event_at,
            'task_title': row.get('title'),
            'detail': detail,
        })

    activity_log.sort(key=lambda entry: str(entry.get('event_at') or ''), reverse=True)

    serialized_tasks = []
    for row in display_rows:
        serialized_tasks.append({
            'id': row.get('id'),
            'title': row.get('title'),
            'description': row.get('description'),
            'assignee_name': row.get('assignee_name'),
            'assignee_email': row.get('assignee_email'),
            'department': row.get('department'),
            'priority': row.get('priority'),
            'priority_label': row.get('priority_label'),
            'status': row.get('status'),
            'status_label': row.get('status_label'),
            'due_date': row.get('due_date'),
            'created_at': row.get('created_at'),
            'days_open': row.get('days_open', 0),
            'is_overdue': bool(row.get('is_overdue')),
        })

    return {
        'generated_at': timezone.now().isoformat(),
        'summary': {
            'total_tasks': total_tasks,
            'active_tasks': active_tasks,
            'completed_tasks': completed_tasks,
            'overdue_tasks': overdue_tasks,
            'completion_rate': completion_rate,
            'avg_turnaround_days_estimate': avg_turnaround,
        },
        'workload_cards': workload_cards,
        'department_summary': department_summary,
        'reporting': {
            'completion_by_member': completion_by_member,
            'completion_by_department': completion_by_department,
            'overdue_over_time': overdue_over_time,
        },
        'tasks': serialized_tasks,
        'activity_log': activity_log[:150],
        'members': members,
        'departments': departments,
        'display_task_count': len(display_rows),
        'scope_task_count': len(scoped_rows),
    }


class HrMasterTaskTrackerView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:master_task_tracker:view',
    }
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()

        search_text = (request.query_params.get('search') or '').strip()
        from_date = _parse_date_value(request.query_params.get('from_date'))
        to_date = _parse_date_value(request.query_params.get('to_date'))
        if from_date and to_date and from_date > to_date:
            from_date, to_date = to_date, from_date

        department = str(request.query_params.get('department') or '').strip()
        if department.lower() == 'all':
            department = ''

        priority = str(request.query_params.get('priority') or '').strip().lower()
        if priority == 'all':
            priority = ''

        status_value = str(request.query_params.get('status') or '').strip().lower()
        if status_value == 'all':
            status_value = ''

        assignee_id = _parse_int(request.query_params.get('assignee_id'))
        assigned_by_id = _parse_int(request.query_params.get('assigned_by_id'))

        rows, members, departments = _build_hr_master_task_tracker_dataset(org_id)
        scoped_rows, display_rows = _apply_hr_master_task_tracker_filters(
            rows,
            search_text=search_text,
            from_date=from_date,
            to_date=to_date,
            department=department,
            priority=priority,
            status=status_value,
            assignee_id=assignee_id,
            assigned_by_id=assigned_by_id,
        )

        payload = _hr_master_task_tracker_payload(scoped_rows, display_rows, members, departments)
        return Response(payload)


class HrMasterTaskTrackerAssignView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'POST': 'human_resources:master_task_tracker:edit',
    }
    parser_classes = [JSONParser]

    def post(self, request):
        org_id = self.get_org_id()
        title = str(request.data.get('task_title') or '').strip()
        if not title:
            return Response({'task_title': 'Task title is required.'}, status=status.HTTP_400_BAD_REQUEST)

        description = str(request.data.get('task_description') or '').strip()
        priority = _normalize_task_priority(request.data.get('task_priority'))
        due_date = _parse_date_value(request.data.get('task_due_date'))

        raw_assignee_ids = request.data.get('assignee_ids')
        if not isinstance(raw_assignee_ids, list):
            return Response({'assignee_ids': 'assignee_ids must be a non-empty list.'}, status=status.HTTP_400_BAD_REQUEST)

        requested_assignee_ids = []
        for value in raw_assignee_ids:
            parsed = _parse_int(value)
            if parsed:
                requested_assignee_ids.append(parsed)
        requested_assignee_ids = sorted(set(requested_assignee_ids))
        if not requested_assignee_ids:
            return Response({'assignee_ids': 'Select at least one valid employee.'}, status=status.HTTP_400_BAD_REQUEST)

        users = list(_organization_users(org_id).filter(id__in=requested_assignee_ids))
        users_by_id = {user.id: user for user in users}
        if len(users_by_id) != len(requested_assignee_ids):
            return Response({'assignee_ids': 'One or more selected employees are invalid for this organization.'}, status=status.HTTP_400_BAD_REQUEST)

        actor_name = request.user.get_full_name() or request.user.first_name or request.user.username or request.user.email or 'Manager'
        created_ids = []

        with transaction.atomic():
            for assignee_id in requested_assignee_ids:
                assignee = users_by_id[assignee_id]
                assignee_label = assignee.get_full_name() or assignee.first_name or assignee.username or assignee.email
                assignee_email = assignee.email or ''

                meta_payload = {
                    'type': 'task',
                    'title': title,
                    'description': description,
                    'priority': priority,
                    'status': 'todo',
                    'dueDate': due_date.isoformat() if due_date else '',
                    'assignee': assignee_label,
                    'assignee_id': assignee.id,
                    'assignee_ids': [assignee.id],
                    'assignees': [{'id': assignee.id, 'label': assignee_label, 'name': assignee_label, 'email': assignee_email}],
                    'assignedBy': actor_name,
                    'assigned_by_id': request.user.id,
                    'comments': [],
                    'helpRequested': False,
                    'commentRequested': False,
                }

                todo_item = PersonalTodoItem.objects.create(
                    org_id=org_id,
                    user=request.user,
                    text=title,
                    is_done=False,
                    recurring='none',
                    sort_order=0,
                    meta=meta_payload,
                )
                _notify_task_assigned(todo_item, request.user, org_id)
                _upsert_task_google_calendar_event(todo_item)
                created_ids.append(todo_item.id)

        return Response({'created_count': len(created_ids), 'task_ids': created_ids}, status=status.HTTP_201_CREATED)


class HrMasterTaskTrackerExportView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:master_task_tracker:view',
    }
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()

        search_text = (request.query_params.get('search') or '').strip()
        from_date = _parse_date_value(request.query_params.get('from_date'))
        to_date = _parse_date_value(request.query_params.get('to_date'))
        if from_date and to_date and from_date > to_date:
            from_date, to_date = to_date, from_date

        department = str(request.query_params.get('department') or '').strip()
        if department.lower() == 'all':
            department = ''

        priority = str(request.query_params.get('priority') or '').strip().lower()
        if priority == 'all':
            priority = ''

        status_value = str(request.query_params.get('status') or '').strip().lower()
        if status_value == 'all':
            status_value = ''

        assignee_id = _parse_int(request.query_params.get('assignee_id'))
        assigned_by_id = _parse_int(request.query_params.get('assigned_by_id'))
        export_format = str(request.query_params.get('format') or 'csv').strip().lower()
        if export_format not in {'csv', 'pdf'}:
            export_format = 'csv'

        rows, _, _ = _build_hr_master_task_tracker_dataset(org_id)
        _, display_rows = _apply_hr_master_task_tracker_filters(
            rows,
            search_text=search_text,
            from_date=from_date,
            to_date=to_date,
            department=department,
            priority=priority,
            status=status_value,
            assignee_id=assignee_id,
            assigned_by_id=assigned_by_id,
        )

        if export_format == 'pdf':
            if not REPORTLAB_AVAILABLE or not canvas or not A4:
                return Response(
                    {'detail': 'PDF export is unavailable. Install reportlab in backend requirements.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            buffer = io.BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            y = height - 40

            pdf.setFont('Helvetica-Bold', 12)
            pdf.drawString(32, y, 'HR Master Task Tracker')
            y -= 18
            pdf.setFont('Helvetica', 9)
            pdf.drawString(32, y, f'Generated at: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}')
            y -= 22

            pdf.setFont('Helvetica-Bold', 8)
            pdf.drawString(32, y, 'Task')
            pdf.drawString(250, y, 'Assignee')
            pdf.drawString(360, y, 'Priority')
            pdf.drawString(425, y, 'Status')
            pdf.drawString(485, y, 'Due')
            y -= 12
            pdf.setFont('Helvetica', 8)

            for row in display_rows:
                if y < 45:
                    pdf.showPage()
                    y = height - 40
                    pdf.setFont('Helvetica', 8)

                task_title = str(row.get('title') or '')[:45]
                assignee_name = str(row.get('assignee_name') or '-')[:24]
                priority_label = str(row.get('priority_label') or row.get('priority') or 'Medium')
                status_label = str(row.get('status_label') or row.get('status') or 'Pending')
                due_date = str(row.get('due_date') or '-')

                pdf.drawString(32, y, task_title)
                pdf.drawString(250, y, assignee_name)
                pdf.drawString(360, y, priority_label)
                pdf.drawString(425, y, status_label)
                pdf.drawString(485, y, due_date)
                y -= 11

            pdf.save()
            buffer.seek(0)

            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="hr-master-task-tracker.pdf"'
            return response

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="hr-master-task-tracker.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Task', 'Description', 'Assignee', 'Assignee Email', 'Department',
            'Priority', 'Status', 'Due Date', 'Created At', 'Days Open', 'Overdue',
        ])

        for row in display_rows:
            writer.writerow([
                row.get('title') or '',
                row.get('description') or '',
                row.get('assignee_name') or '',
                row.get('assignee_email') or '',
                row.get('department') or '',
                row.get('priority_label') or row.get('priority') or '',
                row.get('status_label') or row.get('status') or '',
                row.get('due_date') or '',
                row.get('created_at') or '',
                row.get('days_open') or 0,
                'yes' if row.get('is_overdue') else 'no',
            ])

        return response


MEETING_MANAGER_EVENT_TYPE_OPTIONS = [
    {'value': 'birthday', 'label': 'Birthday'},
    {'value': 'high_pressure', 'label': 'High Pressure Day'},
    {'value': 'holiday', 'label': 'Holiday'},
    {'value': 'event', 'label': 'Event'},
    {'value': 'big_sale', 'label': 'Big Sale'},
    {'value': 'annual_event', 'label': 'Annual Event'},
]


def _join_member_label(user, department_map=None):
    return {
        'id': user.id,
        'name': user.get_full_name() or user.first_name or user.username or user.email,
        'email': user.email,
        'department': str(department_map.get(user.id) or '').strip() if department_map else '',
    }


class HrMeetingManagerOverviewView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:master_task_tracker:view',
        'POST': 'human_resources:master_task_tracker:edit',
    }
    parser_classes = [JSONParser]

    @staticmethod
    def _company_from_email(email_value):
        email = str(email_value or '').strip().lower()
        if '@' not in email:
            return ''
        domain = email.split('@', 1)[1]
        company = domain.split('.', 1)[0]
        return company.replace('-', ' ').replace('_', ' ').title()

    @staticmethod
    def _meeting_day_key(start_value):
        raw_start = str(start_value or '').strip()
        if not raw_start:
            return ''

        if re.match(r'^\d{4}-\d{2}-\d{2}$', raw_start):
            return raw_start

        if len(raw_start) >= 10 and re.match(r'^\d{4}-\d{2}-\d{2}', raw_start):
            return raw_start[:10]

        try:
            parsed = datetime.fromisoformat(raw_start.replace('Z', '+00:00'))
            return parsed.date().isoformat()
        except Exception:
            return ''

    def _serialize_google_meeting(self, event_data, owner, department_map=None):
        if not isinstance(event_data, dict):
            return None

        if str(event_data.get('status') or '').strip().lower() == 'cancelled':
            return None

        organizer = event_data.get('organizer') if isinstance(event_data.get('organizer'), dict) else {}
        organizer_email = str(organizer.get('email') or '').strip().lower()
        owner_email = str(getattr(owner, 'email', '') or '').strip().lower()
        is_owner_organizer = bool(organizer.get('self')) or (organizer_email and organizer_email == owner_email)
        if not is_owner_organizer:
            return None

        start_info = event_data.get('start') if isinstance(event_data.get('start'), dict) else {}
        end_info = event_data.get('end') if isinstance(event_data.get('end'), dict) else {}
        start_value = start_info.get('dateTime') or start_info.get('date')
        end_value = end_info.get('dateTime') or end_info.get('date')
        day_key = self._meeting_day_key(start_value)
        if not day_key:
            return None

        meet_link = ''
        conference_data = event_data.get('conferenceData') if isinstance(event_data.get('conferenceData'), dict) else {}
        entry_points = conference_data.get('entryPoints') if isinstance(conference_data.get('entryPoints'), list) else []
        for entry in entry_points:
            if not isinstance(entry, dict):
                continue
            if entry.get('entryPointType') == 'video':
                meet_link = str(entry.get('uri') or '').strip()
                if meet_link:
                    break

        private_props = (
            event_data.get('extendedProperties', {})
            .get('private', {})
            if isinstance(event_data.get('extendedProperties'), dict)
            else {}
        )
        bridgeworks_type = str(private_props.get('bridgeworks_type') or '').strip().lower()
        if bridgeworks_type and bridgeworks_type != 'meeting' and not meet_link:
            return None
        if not bridgeworks_type and not meet_link:
            return None

        attendee_rows = []
        seen_attendees = set()
        attendees = event_data.get('attendees') if isinstance(event_data.get('attendees'), list) else []
        for attendee in attendees:
            if not isinstance(attendee, dict):
                continue
            attendee_email = str(attendee.get('email') or '').strip()
            if not attendee_email:
                continue

            normalized_email = attendee_email.lower()
            if normalized_email in seen_attendees:
                continue
            seen_attendees.add(normalized_email)

            attendee_name = str(attendee.get('displayName') or '').strip() or attendee_email
            attendee_rows.append({
                'name': attendee_name,
                'email': attendee_email,
                'company': self._company_from_email(attendee_email),
            })

        owner_name = _actor_display_name(owner)
        owner_company = self._company_from_email(owner_email)
        event_id = str(event_data.get('id') or '').strip()
        dedupe_key = str(event_data.get('iCalUID') or '').strip() or f'{owner.id}:{event_id}:{day_key}'

        return {
            'id': f'{owner.id}:{event_id}' if event_id else dedupe_key,
            'dedupe_key': dedupe_key,
            'day_key': day_key,
            'title': str(event_data.get('summary') or '').strip() or '(No title)',
            'start': start_value,
            'end': end_value,
            'agenda': str(event_data.get('description') or '').strip(),
            'company': owner_company or 'Internal',
            'attendees': attendee_rows,
            'created_by': {
                'id': owner.id,
                'name': owner_name,
                'email': owner_email,
                'department': str(department_map.get(owner.id) or '').strip() if department_map else '',
            },
            'meet_link': meet_link,
        }

    def _serialize_event(self, event):
        return {
            'id': event.id,
            'title': event.title,
            'event_type': event.event_type,
            'start_date': event.start_date.isoformat(),
            'end_date': (event.end_date or event.start_date).isoformat(),
            'description': event.description,
            'created_by': _actor_display_name(event.created_by),
        }

    def get(self, request):
        org_id = self.get_org_id()
        start = _parse_date_value(request.query_params.get('start')) or timezone.localdate()
        end = _parse_date_value(request.query_params.get('end')) or start
        if start > end:
            start, end = end, start

        users = list(_organization_users(org_id))
        department_map = _build_workforce_department_map(org_id, users)
        meetings = []
        meeting_days = set()
        seen_meeting_keys = set()
        connected_calendars = 0

        try:
            from core.views_calendar import _get_credentials
            from googleapiclient.discovery import build
        except Exception:
            _get_credentials = None
            build = None

        if _get_credentials and build:
            time_min = datetime.combine(start, datetime.min.time()).isoformat() + 'Z'
            time_max = datetime.combine(end + timedelta(days=1), datetime.min.time()).isoformat() + 'Z'

            for user in users:
                creds = _get_credentials(user)
                if not creds:
                    continue

                connected_calendars += 1

                try:
                    service = build('calendar', 'v3', credentials=creds)
                except Exception:
                    continue

                page_token = None
                while True:
                    try:
                        result = service.events().list(
                            calendarId='primary',
                            timeMin=time_min,
                            timeMax=time_max,
                            singleEvents=True,
                            orderBy='startTime',
                            maxResults=250,
                            pageToken=page_token,
                        ).execute()
                    except Exception:
                        break

                    for item in result.get('items', []):
                        serialized = self._serialize_google_meeting(item, user, department_map)
                        if not serialized:
                            continue

                        dedupe_key = str(serialized.get('dedupe_key') or '').strip() or str(serialized.get('id') or '').strip()
                        if dedupe_key in seen_meeting_keys:
                            continue
                        seen_meeting_keys.add(dedupe_key)

                        day_key = str(serialized.get('day_key') or '').strip()
                        if day_key:
                            meeting_days.add(day_key)

                        meetings.append(serialized)

                    page_token = result.get('nextPageToken')
                    if not page_token:
                        break

        meetings.sort(key=lambda row: str(row.get('start') or ''))

        company_events = []

        queryset = HrMeetingManagerCompanyEvent.objects.filter(org_id=org_id, start_date__lte=end)
        for event in queryset.order_by('start_date'):
            event_end = event.end_date or event.start_date
            if event_end < start:
                continue
            company_events.append(self._serialize_event(event))

        return Response({
            'generated_at': timezone.now().isoformat(),
            'range': {'start': start.isoformat(), 'end': end.isoformat()},
            'default_selected_date': start.isoformat(),
            'summary': {
                'team_members': len(users),
                'calendar_connected_members': connected_calendars,
                'total_meetings': len(meetings),
                'meeting_days': len(meeting_days),
                'company_events': len(company_events),
            },
            'event_type_options': MEETING_MANAGER_EVENT_TYPE_OPTIONS,
            'members': [_join_member_label(user, department_map) for user in users],
            'meetings': meetings,
            'company_events': company_events,
        })

    def post(self, request):
        org_id = self.get_org_id()
        title = (request.data.get('title') or '').strip() or 'Company Event'
        event_type = (request.data.get('event_type') or 'event').strip().lower()
        if event_type not in {item['value'] for item in MEETING_MANAGER_EVENT_TYPE_OPTIONS}:
            event_type = 'event'

        start_date = _parse_date_value(request.data.get('start_date'))
        if not start_date:
            return Response({'start_date': 'A valid start date is required.'}, status=status.HTTP_400_BAD_REQUEST)

        end_date = _parse_date_value(request.data.get('end_date')) or start_date
        if end_date < start_date:
            return Response({'end_date': 'End date must be on or after start date.'}, status=status.HTTP_400_BAD_REQUEST)

        description = (request.data.get('description') or '').strip()

        event = HrMeetingManagerCompanyEvent.objects.create(
            org_id=org_id,
            title=title,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            description=description,
            created_by=request.user,
        )

        return Response({'id': event.id}, status=status.HTTP_201_CREATED)


class HrMeetingManagerCompanyEventDetailView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'PATCH': 'human_resources:master_task_tracker:edit',
        'DELETE': 'human_resources:master_task_tracker:edit',
    }
    parser_classes = [JSONParser]

    def _get_event(self, org_id, event_id):
        return generics.get_object_or_404(
            HrMeetingManagerCompanyEvent.objects.filter(org_id=org_id),
            id=event_id,
        )

    def patch(self, request, event_id):
        org_id = self.get_org_id()
        event = self._get_event(org_id, event_id)

        title = request.data.get('title')
        if title is not None:
            event.title = str(title).strip() or event.title

        event_type = request.data.get('event_type')
        if event_type is not None:
            event_type = str(event_type).strip().lower()
            if event_type in {item['value'] for item in MEETING_MANAGER_EVENT_TYPE_OPTIONS}:
                event.event_type = event_type

        start_date = _parse_date_value(request.data.get('start_date'))
        if start_date:
            event.start_date = start_date

        end_date = _parse_date_value(request.data.get('end_date'))
        event.end_date = end_date

        description = request.data.get('description')
        if description is not None:
            event.description = str(description).strip()

        if event.end_date and event.end_date < event.start_date:
            return Response({'end_date': 'End date must be on or after start date.'}, status=status.HTTP_400_BAD_REQUEST)

        event.save()
        return Response({'id': event.id})

    def delete(self, request, event_id):
        org_id = self.get_org_id()
        event = self._get_event(org_id, event_id)
        event.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyDeskPayrollOverviewView(OrgScopedBaseAPIView):
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        month_start = _month_start_from_value(request.query_params.get('month'))
        fy_start, fy_end, financial_year = _financial_year_bounds(
            request.query_params.get('financial_year'),
            month_start,
        )

        payroll_profile = _get_or_create_payroll_profile(org_id, request.user)

        regime = str(request.query_params.get('regime') or payroll_profile.tax_regime or 'new').strip().lower()
        if regime not in {'new', 'old'}:
            regime = 'new'

        department_map = _build_workforce_department_map(org_id, [request.user])
        employee = _payroll_identity_payload(
            request.user,
            payroll_profile,
            department_map.get(request.user.id, ''),
        )

        payment_records = {
            item.month: item
            for item in PayrollPaymentRecord.objects.filter(
                org_id=org_id,
                user=request.user,
                month__gte=fy_start,
                month__lte=fy_end,
            )
        }

        locked_months = set(
            PayrollRun.objects.filter(
                org_id=org_id,
                month__gte=fy_start,
                month__lte=fy_end,
                is_locked=True,
            ).values_list('month', flat=True)
        )

        selected_record = payment_records.get(month_start)
        selected_available = bool(selected_record and month_start in locked_months)
        if selected_available:
            selected_payslip = _serialize_payroll_record(
                org_id,
                request.user,
                month_start,
                payroll_profile,
                selected_record,
            )
            selected_payslip['available'] = True
            selected_payslip['message'] = ''
        else:
            selected_payslip = {
                'month': month_start.isoformat(),
                'month_label': _month_label(month_start),
                'working_days': None,
                'present_days': None,
                'lop_days': None,
                'gross_amount': None,
                'total_deductions': None,
                'net_amount': None,
                'payment_date': None,
                'utr_reference': '',
                'payment_mode': '',
                'status': 'Pending',
                'earnings': [],
                'deductions': [],
                'salary_structure_snapshot': [],
                'salary_structure_version': 0,
                'payslip_pdf_url': None,
                'dispute_status': 'none',
                'dispute_query': '',
                'dispute_raised_at': None,
                'dispute_resolved_at': None,
                'dispute_resolution_note': '',
                'available': False,
                'message': 'Payslip is available only after payroll is locked for this month.',
            }

        history_snapshots = []
        salary_history = []
        for month_value in _month_starts(fy_start, fy_end):
            monthly_record = payment_records.get(month_value)
            is_available = bool(monthly_record and month_value in locked_months)
            if not is_available:
                salary_history.append({
                    'month': month_value.isoformat(),
                    'month_label': _month_label(month_value),
                    'gross_amount': None,
                    'total_deductions': None,
                    'net_amount': None,
                    'payment_date': None,
                    'utr_reference': '',
                    'status': 'Pending',
                    'available': False,
                    'payslip_pdf_url': None,
                    'dispute_status': 'none',
                })
                continue

            snapshot = _serialize_payroll_record(
                org_id,
                request.user,
                month_value,
                payroll_profile,
                monthly_record,
            )
            history_snapshots.append(snapshot)
            salary_history.append({
                'month': snapshot['month'],
                'month_label': snapshot['month_label'],
                'gross_amount': snapshot['gross_amount'],
                'total_deductions': snapshot['total_deductions'],
                'net_amount': snapshot['net_amount'],
                'payment_date': snapshot['payment_date'],
                'utr_reference': snapshot['utr_reference'],
                'status': snapshot['status'],
                'available': True,
                'payslip_pdf_url': snapshot.get('payslip_pdf_url'),
                'dispute_status': snapshot.get('dispute_status') or 'none',
            })

        declarations = _ensure_default_tax_declarations(org_id, request.user, financial_year)
        salary_structure = _ensure_default_salary_structures(
            org_id,
            request.user,
            payroll_profile,
            month_start=month_start,
        )
        tax_summary = _payroll_tax_summary(history_snapshots, declarations, regime)

        declaration_data = PayrollTaxDeclarationSerializer(declarations, many=True).data
        structure_data = PayrollSalaryStructureSerializer(salary_structure, many=True).data

        documents = [
            {
                'code': 'form16',
                'label': f'Form 16 FY {financial_year}',
                'available': True,
            },
            {
                'code': 'salary_policy',
                'label': 'Payroll Policy Acknowledgement',
                'available': True,
            },
        ]

        return Response({
            'company': _company_payload(org_id),
            'employee': employee,
            'month': month_start.strftime('%Y-%m'),
            'financial_year': financial_year,
            'payslip': selected_payslip,
            'salary_history': salary_history,
            'tax_summary': tax_summary,
            'declarations': declaration_data,
            'salary_structure': structure_data,
            'documents': documents,
        })


class MyDeskPayrollDeclarationsView(OrgScopedBaseAPIView):
    parser_classes = [JSONParser]

    def put(self, request):
        org_id = self.get_org_id()
        profile = _get_or_create_payroll_profile(org_id, request.user)

        regime = str(request.data.get('regime') or profile.tax_regime or 'new').strip().lower()
        if regime in {'new', 'old'} and profile.tax_regime != regime:
            profile.tax_regime = regime
            profile.save(update_fields=['tax_regime', 'updated_at'])

        financial_year_raw = request.data.get('financial_year')
        _, _, financial_year = _financial_year_bounds(financial_year_raw, timezone.localdate())
        declarations = _ensure_default_tax_declarations(org_id, request.user, financial_year)
        declaration_map = {item.id: item for item in declarations}

        rows = request.data.get('rows')
        if rows is not None and not isinstance(rows, list):
            return Response({'rows': 'rows must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

        for row in rows or []:
            if not isinstance(row, dict):
                continue
            row_id = row.get('id')
            try:
                row_id = int(row_id)
            except (TypeError, ValueError):
                continue
            item = declaration_map.get(row_id)
            if not item:
                continue

            update_fields = ['updated_at']

            if 'declared_amount' in row:
                try:
                    declared_amount = Decimal(str(row.get('declared_amount') or 0))
                except Exception:
                    return Response(
                        {'declared_amount': f'Invalid value for declaration id {row_id}.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if declared_amount < 0:
                    declared_amount = Decimal('0')
                if declared_amount > item.max_limit:
                    return Response(
                        {'declared_amount': f'Declared amount exceeds max limit for declaration id {row_id}.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                item.declared_amount = declared_amount
                update_fields.append('declared_amount')

            if 'proof_file_name' in row:
                item.proof_file_name = str(row.get('proof_file_name') or '').strip()
                update_fields.append('proof_file_name')

            row_status = str(row.get('status') or '').strip().lower()
            if row_status in {'draft', 'submitted', 'verified'}:
                item.status = row_status
                update_fields.append('status')
                if row_status in {'submitted', 'verified'}:
                    item.submitted_at = item.submitted_at or timezone.now()
                    update_fields.append('submitted_at')

            item.save(update_fields=sorted(set(update_fields)))

        submit_all = bool(request.data.get('submit'))
        if submit_all:
            PayrollTaxDeclaration.objects.filter(
                org_id=org_id,
                user=request.user,
                financial_year=financial_year,
                is_active=True,
            ).update(status='submitted', submitted_at=timezone.now())

        refreshed = PayrollTaxDeclaration.objects.filter(
            org_id=org_id,
            user=request.user,
            financial_year=financial_year,
            is_active=True,
        ).order_by('sort_order', 'id')

        return Response({
            'financial_year': financial_year,
            'regime': profile.tax_regime,
            'rows': PayrollTaxDeclarationSerializer(refreshed, many=True).data,
        })


class MyDeskPayrollDisputeView(OrgScopedBaseAPIView):
    parser_classes = [JSONParser]

    def post(self, request):
        org_id = self.get_org_id()
        month_start = _month_start_from_value(
            request.data.get('month') or request.query_params.get('month')
        )
        query_text = str(request.data.get('query') or request.data.get('message') or '').strip()

        if not query_text:
            return Response({'query': 'Query text is required.'}, status=status.HTTP_400_BAD_REQUEST)

        payroll_run = PayrollRun.objects.filter(
            org_id=org_id,
            month=month_start,
            is_locked=True,
        ).first()
        if not payroll_run:
            return Response(
                {'detail': 'Disputes can only be raised for locked payroll months.'},
                status=status.HTTP_409_CONFLICT,
            )

        payment_record = PayrollPaymentRecord.objects.filter(
            org_id=org_id,
            user=request.user,
            month=month_start,
        ).first()
        if not payment_record:
            return Response(
                {'detail': 'No payslip record found for selected month.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        now = timezone.now()
        payment_record.dispute_status = 'open'
        payment_record.dispute_query = query_text[:4000]
        payment_record.dispute_resolution_note = ''
        payment_record.dispute_raised_at = now
        payment_record.dispute_resolved_at = None
        payment_record.save(
            update_fields=[
                'dispute_status',
                'dispute_query',
                'dispute_resolution_note',
                'dispute_raised_at',
                'dispute_resolved_at',
                'updated_at',
            ]
        )

        recipients = []
        for user_obj in [
            payroll_run.calculation_run_by,
            payroll_run.hr_approved_by,
            payroll_run.finance_approved_by,
            payroll_run.locked_by,
        ]:
            if not user_obj:
                continue
            if user_obj.id == request.user.id:
                continue
            if any(existing.id == user_obj.id for existing in recipients):
                continue
            recipients.append(user_obj)

        for recipient in recipients:
            try:
                push_unified_notification(
                    recipient=recipient,
                    actor=request.user,
                    module='notes',
                    action='reminder',
                    title='Payroll Dispute Raised',
                    message=(
                        f"{_user_full_name(request.user)} raised a payslip dispute "
                        f"for {_month_label(month_start)}."
                    ),
                    entity_type='payroll_dispute',
                    entity_id=str(payment_record.id),
                    deep_link={
                        'path': '/human-resources/payroll',
                        'month': month_start.strftime('%Y-%m'),
                        'user_id': request.user.id,
                    },
                    metadata={
                        'month': month_start.strftime('%Y-%m'),
                        'query': payment_record.dispute_query,
                        'status': payment_record.dispute_status,
                    },
                )
            except Exception:
                pass

        return Response({
            'detail': 'Payroll dispute submitted successfully.',
            'month': month_start.strftime('%Y-%m'),
            'dispute_status': payment_record.dispute_status,
            'dispute_query': payment_record.dispute_query,
            'dispute_raised_at': _to_iso_datetime(payment_record.dispute_raised_at),
        })


class HrPayrollRunControlView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
        'PUT': 'human_resources:attendance_dashboard:edit',
    }
    parser_classes = [JSONParser]

    ALLOWED_ACTIONS = {
        'lock_attendance',
        'run_calculation',
        'approve_hr',
        'approve_finance',
        'generate_payslips',
        'export_bank_file',
        'post_gl',
        'lock_payroll',
        'verify_finance',
    }

    def _resolve_month_start(self, request):
        return _month_start_from_value(
            request.query_params.get('month')
            or request.data.get('month')
        )

    def _summary_stats(self, org_id, month_start):
        users = list(_organization_users(org_id))
        records = list(
            PayrollPaymentRecord.objects.filter(
                org_id=org_id,
                month=month_start,
            )
        )

        paid_count = 0
        processed_count = 0
        on_hold_count = 0
        for item in records:
            status_value = str(item.status or '').strip()
            if status_value == 'Paid':
                paid_count += 1
            elif status_value == 'On Hold':
                on_hold_count += 1
            else:
                processed_count += 1

        return {
            'employees_count': len(users),
            'generated_records': len(records),
            'paid_count': paid_count,
            'processed_count': processed_count,
            'on_hold_count': on_hold_count,
            'total_gross': _round2(sum(float(item.gross_amount or 0) for item in records)),
            'total_deductions': _round2(sum(float(item.total_deductions or 0) for item in records)),
            'total_net': _round2(sum(float(item.net_amount or 0) for item in records)),
        }

    def _response_payload(self, org_id, month_start, run, detail=''):
        exceptions = run.exception_report if isinstance(run.exception_report, list) else []
        stats = self._summary_stats(org_id, month_start)
        stats['exception_count'] = int(run.exception_count or 0)

        payload = {
            'month': month_start.strftime('%Y-%m'),
            'month_label': _month_label(month_start),
            'run': _serialize_payroll_run_state(run),
            'stats': stats,
            'exceptions': exceptions,
        }
        if detail:
            payload['detail'] = detail
        return payload

    def get(self, request):
        org_id = self.get_org_id()
        month_start = self._resolve_month_start(request)
        run = _get_or_create_payroll_run(org_id, month_start)
        return Response(self._response_payload(org_id, month_start, run))

    def put(self, request):
        org_id = self.get_org_id()
        month_start = self._resolve_month_start(request)
        run = _get_or_create_payroll_run(org_id, month_start)

        action = str(request.data.get('action') or '').strip().lower()
        if action not in self.ALLOWED_ACTIONS:
            return Response(
                {
                    'detail': 'Invalid payroll run action.',
                    'allowed_actions': sorted(self.ALLOWED_ACTIONS),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if run.is_locked and action != 'export_bank_file':
            return Response(
                {'detail': 'Payroll for this month is locked and cannot be modified.'},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        detail = ''

        if action == 'lock_attendance':
            if run.attendance_locked_at:
                detail = 'Attendance was already locked for this payroll month.'
            else:
                run.attendance_locked_at = now
                run.attendance_locked_by = request.user
                run.save(update_fields=['attendance_locked_at', 'attendance_locked_by', 'updated_at'])
                detail = 'Attendance locked for payroll processing.'

        elif action == 'run_calculation':
            if not run.attendance_locked_at:
                return Response(
                    {'detail': 'Lock attendance before running payroll calculations.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            result = _materialize_payroll_month(org_id, month_start, request.user)
            run.calculation_run_at = now
            run.calculation_run_by = request.user
            run.exception_report = result['exception_report']
            run.exception_count = len(result['exception_report'])
            run.save(
                update_fields=[
                    'calculation_run_at',
                    'calculation_run_by',
                    'exception_report',
                    'exception_count',
                    'updated_at',
                ]
            )
            detail = (
                f"Payroll calculated for {len(result['users'])} employees "
                f"({result['created_count']} created, {result['updated_count']} updated)."
            )

        elif action == 'approve_hr':
            if not run.calculation_run_at:
                return Response(
                    {'detail': 'Run payroll calculation before HR approval.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            run.hr_approved_at = now
            run.hr_approved_by = request.user
            run.save(update_fields=['hr_approved_at', 'hr_approved_by', 'updated_at'])
            detail = 'Payroll approved by HR.'

        elif action == 'approve_finance':
            if not run.hr_approved_at:
                return Response(
                    {'detail': 'HR approval is required before Finance approval.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            run.finance_approved_at = now
            run.finance_approved_by = request.user
            run.save(update_fields=['finance_approved_at', 'finance_approved_by', 'updated_at'])
            detail = 'Payroll approved by Finance.'

        elif action == 'generate_payslips':
            if not run.calculation_run_at:
                return Response(
                    {'detail': 'Run payroll calculation before generating payslips.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not run.finance_approved_at:
                return Response(
                    {'detail': 'Finance approval is required before generating payslips.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not REPORTLAB_AVAILABLE:
                return Response(
                    {'detail': 'Payslip PDF generation is not available. Install reportlab in backend dependencies.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            records = list(
                PayrollPaymentRecord.objects.select_related('user').filter(
                    org_id=org_id,
                    month=month_start,
                )
            )
            if not records:
                return Response(
                    {'detail': 'No payroll records found for selected month. Run payroll calculation first.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            users = [record.user for record in records if record.user]
            user_ids = [user.id for user in users]
            profile_map = {
                item.user_id: item
                for item in PayrollProfile.objects.filter(org_id=org_id, user_id__in=user_ids)
            }
            department_map = _build_workforce_department_map(org_id, users)

            generated_count = 0
            failed_rows = []

            for record in records:
                payroll_profile = profile_map.get(record.user_id) or _build_transient_payroll_profile(org_id, record.user)
                department_name = department_map.get(record.user_id, '')
                try:
                    _ = _generate_payslip_pdf_for_record(
                        org_id,
                        record,
                        payroll_profile,
                        department_name,
                    )
                    _send_payslip_notification(record, request.user)
                    generated_count += 1
                except Exception as exc:
                    failed_rows.append({
                        'user_id': record.user_id,
                        'employee_name': _user_full_name(record.user),
                        'error': str(exc),
                    })

            run.payslips_generated_at = now
            run.payslips_generated_by = request.user
            run.save(update_fields=['payslips_generated_at', 'payslips_generated_by', 'updated_at'])
            detail = f'Payslips generated for {generated_count} employees.'
            if failed_rows:
                detail = f"{detail} {len(failed_rows)} generation failures recorded."

            payload = self._response_payload(org_id, month_start, run, detail=detail)
            payload['payslip_generation'] = {
                'generated_count': generated_count,
                'failed_count': len(failed_rows),
                'failed_rows': failed_rows,
            }
            return Response(payload)

        elif action == 'export_bank_file':
            if not run.finance_approved_at and not run.is_locked:
                return Response(
                    {'detail': 'Finance approval is required before bank file export.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            bank_rows = _build_bank_transfer_rows(org_id, month_start)
            run.bank_file_generated_at = now
            run.bank_file_generated_by = request.user
            run.save(update_fields=['bank_file_generated_at', 'bank_file_generated_by', 'updated_at'])
            detail = f'Bank transfer file prepared with {len(bank_rows)} rows.'

            payload = self._response_payload(org_id, month_start, run, detail=detail)
            payload['bank_file'] = {
                'headers': [
                    'Employee Name',
                    'Employee ID',
                    'Department',
                    'Bank Name',
                    'Account Number',
                    'IFSC',
                    'Amount',
                    'Payment Mode',
                    'UTR',
                ],
                'rows': bank_rows,
            }
            return Response(payload)

        elif action == 'verify_finance':
            # Toggle or set finance_verified for a specific employee's record in this month
            target_user_id = request.data.get('user_id') or request.data.get('employee_id')
            if not target_user_id:
                return Response(
                    {'detail': 'user_id is required for verify_finance action.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                target_user_id = int(target_user_id)
            except (TypeError, ValueError):
                return Response({'detail': 'user_id must be a number.'}, status=status.HTTP_400_BAD_REQUEST)

            record = PayrollPaymentRecord.objects.filter(
                org_id=org_id, user_id=target_user_id, month=month_start
            ).first()
            if not record:
                return Response(
                    {'detail': 'No payroll record found for this employee in the selected month. Run payroll calculation first.'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            record.finance_verified = not record.finance_verified
            if record.finance_verified:
                record.finance_verified_by = request.user
                record.finance_verified_at = now
            else:
                record.finance_verified_by = None
                record.finance_verified_at = None
            record.save(update_fields=['finance_verified', 'finance_verified_by', 'finance_verified_at', 'updated_at'])
            verified_count = PayrollPaymentRecord.objects.filter(
                org_id=org_id, month=month_start, finance_verified=True
            ).count()
            total_count = PayrollPaymentRecord.objects.filter(org_id=org_id, month=month_start).count()
            detail = f'Record {"verified" if record.finance_verified else "unverified"}. {verified_count}/{total_count} verified.'
            payload = self._response_payload(org_id, month_start, run, detail=detail)
            payload['verified_record'] = {
                'user_id': target_user_id,
                'finance_verified': record.finance_verified,
                'verified_count': verified_count,
                'total_count': total_count,
            }
            return Response(payload)

        elif action == 'post_gl':
            if not run.finance_approved_at:
                return Response(
                    {'detail': 'Finance approval is required before GL posting.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not run.gl_reference:
                run.gl_reference = f"GL-PAY-{month_start.strftime('%Y%m')}-{int(now.timestamp())}"
            run.gl_posted_at = now
            run.gl_posted_by = request.user
            run.save(update_fields=['gl_reference', 'gl_posted_at', 'gl_posted_by', 'updated_at'])
            detail = f'Payroll posted to GL reference {run.gl_reference}.'

        elif action == 'lock_payroll':
            if not run.finance_approved_at:
                return Response(
                    {'detail': 'Finance approval is required before locking payroll.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            run.is_locked = True
            run.locked_at = now
            run.locked_by = request.user
            run.save(update_fields=['is_locked', 'locked_at', 'locked_by', 'updated_at'])
            detail = 'Payroll month locked. Further edits are disabled.'

        return Response(self._response_payload(org_id, month_start, run, detail=detail))


class HrPayrollDashboardView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
    }
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        month_start = _month_start_from_value(request.query_params.get('month'))
        search_text = str(request.query_params.get('search') or '').strip().lower()

        users = list(_organization_users(org_id))
        user_ids = [item.id for item in users]

        profile_map = {
            item.user_id: item
            for item in PayrollProfile.objects.filter(org_id=org_id, user_id__in=user_ids)
        }
        record_map = {
            item.user_id: item
            for item in PayrollPaymentRecord.objects.filter(org_id=org_id, user_id__in=user_ids, month=month_start)
        }
        department_map = _build_workforce_department_map(org_id, users)

        # Batch-fetch approved expense totals for all employees in the payroll month
        if month_start.month == 12:
            _last_day_of_month = date(month_start.year + 1, 1, 1) - timedelta(days=1)
        else:
            _last_day_of_month = date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)

        expense_total_map = {}
        if user_ids:
            _exp_qs = ExpenseEntry.objects.filter(
                org_id=org_id,
                user_id__in=user_ids,
                status__in=['Dept Head Approved', 'Finance Reviewed'],
                transaction_type='expense',
                spent_on__gte=month_start,
                spent_on__lte=_last_day_of_month,
            ).values('user_id').annotate(_total=Sum('amount'))
            expense_total_map = {
                item['user_id']: _round2(float(item['_total'] or 0))
                for item in _exp_qs
            }

        rows = []
        for user in users:
            payroll_profile = profile_map.get(user.id) or _build_transient_payroll_profile(org_id, user)
            payment_record = record_map.get(user.id)
            snapshot = (
                _serialize_payroll_record(
                    org_id,
                    user,
                    month_start,
                    payroll_profile,
                    payment_record,
                )
                if payment_record
                else _empty_payroll_snapshot(org_id, user, month_start, payroll_profile)
            )
            identity = _payroll_identity_payload(user, payroll_profile, department_map.get(user.id, ''))

            row = {
                'user_id': user.id,
                'has_record': bool(payment_record),
                'employee_name': identity['employee_name'],
                'employee_id': identity['employee_id'],
                'department': identity['department'],
                'pan_masked': identity['pan_masked'],
                'uan': identity['uan'],
                'bank_account_display': identity['bank_account_display'],
                'working_days': snapshot['working_days'],
                'present_days': snapshot['present_days'],
                'lop_days': snapshot['lop_days'],
                'gross': snapshot['gross_amount'],
                'deductions': snapshot['total_deductions'],
                'net': snapshot['net_amount'],
                'status': snapshot['status'],
                'payment_date': snapshot['payment_date'],
                'utr': snapshot['utr_reference'],
                'payment_mode': snapshot['payment_mode'],
                'finance_verified': bool(payment_record.finance_verified) if payment_record else False,
                'finance_verified_at': _to_iso_datetime(payment_record.finance_verified_at) if payment_record else None,
                'finance_verified_by': _actor_display_name(payment_record.finance_verified_by) if payment_record else None,
                'earnings_breakup': payment_record.earnings_breakup if payment_record else [],
                'deductions_breakup': payment_record.deductions_breakup if payment_record else [],
            }

            _exp_total = expense_total_map.get(user.id, 0.0)
            row['expense_total'] = _exp_total
            row['hr_expenses'] = [{'component': 'Expense Reimbursement', 'amount': _exp_total, 'is_expense': True}] if _exp_total > 0 else []

            if search_text:
                haystack = ' '.join([
                    str(row.get('employee_name') or ''),
                    str(row.get('employee_id') or ''),
                    str(row.get('department') or ''),
                    str(row.get('utr') or ''),
                ]).lower()
                if search_text not in haystack:
                    continue

            rows.append(row)

        rows = sorted(rows, key=lambda item: str(item.get('employee_name') or '').lower())

        totals = {
            'gross': _round2(sum(float(item.get('gross') or 0) for item in rows if item.get('has_record'))),
            'deductions': _round2(sum(float(item.get('deductions') or 0) for item in rows if item.get('has_record'))),
            'net': _round2(sum(float(item.get('net') or 0) for item in rows if item.get('has_record'))),
        }

        payroll_run = _get_or_create_payroll_run(org_id, month_start)

        return Response({
            'month': month_start.strftime('%Y-%m'),
            'month_label': _month_label(month_start),
            'count': len(rows),
            'totals': totals,
            'rows': rows,
            'payroll_run': _serialize_payroll_run_state(payroll_run),
            'exception_count': int(payroll_run.exception_count or 0),
            'verified_count': PayrollPaymentRecord.objects.filter(
                org_id=org_id, month=month_start, finance_verified=True
            ).count(),
        })


class FinancePayrollLedgerView(OrgScopedBaseAPIView):
    """List all payroll runs ever processed — used by Finance Payroll ledger page."""
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
    }
    parser_classes = [JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        runs = PayrollRun.objects.filter(org_id=org_id).order_by('-month')[:24]
        result = []
        for run in runs:
            month_start = run.month
            stats_qs = PayrollPaymentRecord.objects.filter(org_id=org_id, month=month_start)
            total_gross = float(stats_qs.aggregate(s=Sum('gross_amount'))['s'] or 0)
            total_deductions = float(stats_qs.aggregate(s=Sum('total_deductions'))['s'] or 0)
            total_net = float(stats_qs.aggregate(s=Sum('net_amount'))['s'] or 0)
            employee_count = stats_qs.count()
            verified_count = stats_qs.filter(finance_verified=True).count()
            state = _serialize_payroll_run_state(run)
            result.append({
                'month': month_start.strftime('%Y-%m'),
                'month_label': _month_label(month_start),
                'stage': state['stage'],
                'is_locked': state['is_locked'],
                'hr_approved': state['hr_approved'],
                'finance_approved': state['finance_approved'],
                'gl_posted': state['gl_posted'],
                'gl_reference': state['gl_reference'],
                'employee_count': employee_count,
                'verified_count': verified_count,
                'total_gross': _round2(total_gross),
                'total_deductions': _round2(total_deductions),
                'total_net': _round2(total_net),
                'finance_approved_at': state['finance_approved_at'],
                'finance_approved_by': state['finance_approved_by'],
                'gl_posted_at': state['gl_posted_at'],
            })
        return Response({'runs': result, 'count': len(result)})


class HrPayrollEmployeeDetailView(OrgScopedBaseAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': 'human_resources:attendance_dashboard:view',
        'PUT': 'human_resources:attendance_dashboard:edit',
    }
    parser_classes = [JSONParser]

    def _resolve_employee(self, org_id, user_id):
        user = generics.get_object_or_404(_organization_users(org_id), id=user_id)
        payroll_profile = PayrollProfile.objects.filter(org_id=org_id, user=user).first() or _build_transient_payroll_profile(org_id, user)
        department_map = _build_workforce_department_map(org_id, [user])
        identity = _payroll_identity_payload(user, payroll_profile, department_map.get(user.id, ''))
        return user, payroll_profile, identity

    def get(self, request, user_id):
        org_id = self.get_org_id()
        month_start = _month_start_from_value(request.query_params.get('month'))

        user, payroll_profile, identity = self._resolve_employee(org_id, user_id)

        payment_record = PayrollPaymentRecord.objects.filter(
            org_id=org_id,
            user=user,
            month=month_start,
        ).first()
        snapshot = (
            _serialize_payroll_record(org_id, user, month_start, payroll_profile, payment_record)
            if payment_record
            else _empty_payroll_snapshot(org_id, user, month_start, payroll_profile)
        )
        salary_structure = _ensure_default_salary_structures(
            org_id,
            user,
            payroll_profile,
            month_start=month_start,
        )
        salary_rows = PayrollSalaryStructureSerializer(salary_structure, many=True).data
        payroll_run = _get_or_create_payroll_run(org_id, month_start)

        return Response({
            'month': month_start.strftime('%Y-%m'),
            'month_label': snapshot['month_label'],
            'employee': identity,
            'working_days': snapshot['working_days'],
            'present_days': snapshot['present_days'],
            'lop_days': snapshot['lop_days'],
            'gross': snapshot['gross_amount'],
            'deductions': snapshot['total_deductions'],
            'net': snapshot['net_amount'],
            'payment_date': snapshot['payment_date'],
            'utr': snapshot['utr_reference'],
            'payment_mode': snapshot['payment_mode'],
            'status': snapshot['status'],
            'earnings': snapshot['earnings'],
            'deductions_breakup': snapshot['deductions'],
            'salary_structure': salary_rows,
            'salary_structure_totals': _salary_structure_totals(salary_structure),
            'payroll_run': _serialize_payroll_run_state(payroll_run),
            'is_locked': bool(payroll_run.is_locked),
            'has_record': bool(payment_record),
            'hr_expenses': snapshot.get('hr_expenses', []),
            'expense_total': snapshot.get('expense_total', 0),
        })

    def put(self, request, user_id):
        org_id = self.get_org_id()
        month_start = _month_start_from_value(request.data.get('month') or request.query_params.get('month'))
        payroll_run = _get_or_create_payroll_run(org_id, month_start)
        if payroll_run.is_locked:
            return Response(
                {'detail': 'Payroll month is locked. Edits are disabled.'},
                status=status.HTTP_409_CONFLICT,
            )

        user, payroll_profile, identity = self._resolve_employee(org_id, user_id)

        rows = request.data.get('rows')
        if isinstance(rows, list):
            allowed_taxability = {choice[0] for choice in PayrollSalaryStructure.TAXABILITY_CHOICES}
            normalized_rows = []
            effective_from = _parse_date_value(request.data.get('effective_from')) or month_start
            effective_to = _parse_date_value(request.data.get('effective_to'))

            if effective_to and effective_to < effective_from:
                return Response(
                    {'effective_to': 'effective_to must be on or after effective_from.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    return Response(
                        {'rows': f'Invalid row at index {index}. Expected object.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                component_name = str(row.get('component_name') or '').strip()
                if not component_name:
                    return Response(
                        {'component_name': f'Component name is required for row {index + 1}.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                try:
                    monthly_amount = Decimal(str(row.get('monthly_amount', 0) or 0))
                except Exception:
                    return Response(
                        {'monthly_amount': f'Invalid monthly amount for row {index + 1}.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if monthly_amount < 0:
                    monthly_amount = Decimal('0')
                monthly_amount = monthly_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                annual_input = row.get('annual_amount')
                if annual_input in (None, ''):
                    annual_amount = (monthly_amount * Decimal('12')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                else:
                    try:
                        annual_amount = Decimal(str(annual_input))
                    except Exception:
                        return Response(
                            {'annual_amount': f'Invalid annual amount for row {index + 1}.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if annual_amount < 0:
                        annual_amount = Decimal('0')
                    annual_amount = annual_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                taxability = str(row.get('taxability') or 'yes').strip().lower()
                if taxability not in allowed_taxability:
                    return Response(
                        {'taxability': f'Invalid taxability for row {index + 1}.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                normalized_rows.append({
                    'component_name': component_name[:120],
                    'monthly_amount': monthly_amount,
                    'annual_amount': annual_amount,
                    'taxability': taxability,
                    'remarks': str(row.get('remarks') or '').strip()[:255],
                    'sort_order': index,
                })

            if not normalized_rows:
                return Response(
                    {'rows': 'At least one salary structure row is required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with transaction.atomic():
                latest_version = (
                    PayrollSalaryStructure.objects.filter(org_id=org_id, user=user)
                    .order_by('-version')
                    .values_list('version', flat=True)
                    .first()
                    or 0
                )
                new_version = int(latest_version) + 1
                previous_end = effective_from - timedelta(days=1)

                PayrollSalaryStructure.objects.filter(
                    org_id=org_id,
                    user=user,
                    is_active=True,
                ).filter(
                    Q(effective_to__isnull=True) | Q(effective_to__gte=effective_from)
                ).update(
                    effective_to=previous_end,
                    updated_at=timezone.now(),
                )

                PayrollSalaryStructure.objects.bulk_create([
                    PayrollSalaryStructure(
                        org_id=org_id,
                        user=user,
                        component_name=item['component_name'],
                        monthly_amount=item['monthly_amount'],
                        annual_amount=item['annual_amount'],
                        taxability=item['taxability'],
                        remarks=item['remarks'],
                        sort_order=item['sort_order'],
                        version=new_version,
                        effective_from=effective_from,
                        effective_to=effective_to,
                        is_active=True,
                    )
                    for item in normalized_rows
                ])

            refreshed = PayrollSalaryStructure.objects.filter(
                org_id=org_id,
                user=user,
                version=new_version,
            ).order_by('sort_order', 'id')

            return Response({
                'user_id': user.id,
                'employee': identity,
                'version': new_version,
                'effective_from': effective_from.isoformat(),
                'effective_to': effective_to.isoformat() if effective_to else None,
                'salary_structure': PayrollSalaryStructureSerializer(refreshed, many=True).data,
                'salary_structure_totals': _salary_structure_totals(refreshed),
                'payroll_run': _serialize_payroll_run_state(payroll_run),
            })

        if 'earnings' not in request.data and 'deductions' not in request.data:
            return Response(
                {'detail': 'Provide either rows for salary structure or earnings/deductions for payroll breakup.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def parse_breakup_rows(raw_rows, label):
            if raw_rows is None:
                return []
            if not isinstance(raw_rows, list):
                raise ValueError(f'{label} must be a list.')

            normalized = []
            for index, item in enumerate(raw_rows):
                if not isinstance(item, dict):
                    raise ValueError(f'Invalid {label} row at index {index}. Expected object.')

                component = str(
                    item.get('component')
                    or item.get('name')
                    or item.get('label')
                    or ''
                ).strip()
                if not component:
                    raise ValueError(f'Component name is required for {label} row {index + 1}.')

                amount_value = item.get('amount')
                if amount_value is None:
                    amount_value = item.get('value')

                try:
                    amount = Decimal(str(amount_value or 0))
                except Exception as exc:
                    raise ValueError(f'Invalid amount for {label} row {index + 1}.') from exc

                if amount < 0:
                    amount = Decimal('0')

                normalized.append({
                    'component': component[:120],
                    'amount': _round2(amount),
                })

            return normalized

        try:
            earnings_rows = parse_breakup_rows(request.data.get('earnings'), 'earnings')
            deduction_rows = parse_breakup_rows(request.data.get('deductions'), 'deductions')
        except ValueError as parse_error:
            return Response({'detail': str(parse_error)}, status=status.HTTP_400_BAD_REQUEST)

        if not earnings_rows:
            return Response(
                {'earnings': 'At least one earnings row is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_record = PayrollPaymentRecord.objects.filter(
            org_id=org_id,
            user=user,
            month=month_start,
        ).first()

        snapshot = (
            _serialize_payroll_record(org_id, user, month_start, payroll_profile, payment_record)
            if payment_record
            else _empty_payroll_snapshot(org_id, user, month_start, payroll_profile)
        )

        gross_amount = _round2(sum(float(item.get('amount') or 0) for item in earnings_rows))
        total_deductions = _round2(sum(float(item.get('amount') or 0) for item in deduction_rows))
        net_amount = _round2(max(0.0, gross_amount - total_deductions))

        payment_date = _parse_date_value(request.data.get('payment_date')) or _parse_date_value(snapshot.get('payment_date'))
        payment_mode = str(
            request.data.get('payment_mode')
            or (payment_record.payment_mode if payment_record else snapshot.get('payment_mode'))
            or 'NEFT'
        ).strip()[:30] or 'NEFT'

        utr_reference = str(
            request.data.get('utr')
            or request.data.get('utr_reference')
            or (payment_record.utr_reference if payment_record else snapshot.get('utr_reference'))
            or ''
        ).strip()[:120]

        requested_status = str(request.data.get('status') or '').strip()
        allowed_statuses = {choice[0] for choice in PayrollPaymentRecord.STATUS_CHOICES}
        if requested_status in allowed_statuses:
            status_value = requested_status
        elif payment_record and payment_record.status in allowed_statuses:
            status_value = payment_record.status
        else:
            status_value = 'Processed'

        salary_snapshot_rows = snapshot.get('salary_structure_snapshot') if isinstance(snapshot.get('salary_structure_snapshot'), list) else []
        salary_structure_version = int(snapshot.get('salary_structure_version') or 0)
        if not salary_snapshot_rows:
            effective_rows = _effective_salary_structures(org_id, user, month_start)
            salary_snapshot_rows = _salary_structure_rows_to_snapshot(effective_rows)
            if salary_structure_version <= 0:
                salary_structure_version = _salary_structure_version(effective_rows)

        common_payload = {
            'working_days': Decimal(str(snapshot.get('working_days') or 0)),
            'present_days': Decimal(str(snapshot.get('present_days') or 0)),
            'lop_days': Decimal(str(snapshot.get('lop_days') or 0)),
            'gross_amount': Decimal(str(gross_amount)),
            'total_deductions': Decimal(str(total_deductions)),
            'net_amount': Decimal(str(net_amount)),
            'payment_date': payment_date,
            'utr_reference': utr_reference,
            'payment_mode': payment_mode,
            'status': status_value,
            'earnings_breakup': earnings_rows,
            'deductions_breakup': deduction_rows,
            'salary_structure_snapshot': salary_snapshot_rows,
            'salary_structure_version': max(0, salary_structure_version),
            'remarks': payment_record.remarks if payment_record else '',
        }

        if payment_record:
            for key, value in common_payload.items():
                setattr(payment_record, key, value)
            payment_record.save()
        else:
            payment_record = PayrollPaymentRecord.objects.create(
                org_id=org_id,
                user=user,
                month=month_start,
                created_by=request.user,
                **common_payload,
            )

        refreshed_snapshot = _serialize_payroll_record(org_id, user, month_start, payroll_profile, payment_record)

        return Response({
            'user_id': user.id,
            'employee': identity,
            'month': month_start.strftime('%Y-%m'),
            'month_label': refreshed_snapshot['month_label'],
            'working_days': refreshed_snapshot['working_days'],
            'present_days': refreshed_snapshot['present_days'],
            'lop_days': refreshed_snapshot['lop_days'],
            'gross': refreshed_snapshot['gross_amount'],
            'deductions': refreshed_snapshot['total_deductions'],
            'net': refreshed_snapshot['net_amount'],
            'payment_date': refreshed_snapshot['payment_date'],
            'utr': refreshed_snapshot['utr_reference'],
            'payment_mode': refreshed_snapshot['payment_mode'],
            'status': refreshed_snapshot['status'],
            'earnings': refreshed_snapshot['earnings'],
            'deductions_breakup': refreshed_snapshot['deductions'],
            'payroll_run': _serialize_payroll_run_state(payroll_run),
        })


class GalleryAlbumListCreateView(OrgScopedBaseAPIView):
    parser_classes = [JSONParser]

    def get(self, request):
        queryset = self.scope_queryset(GalleryAlbum.objects.all())
        return Response(GalleryAlbumSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = GalleryAlbumSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        album = serializer.save(user=request.user, org_id=self.get_org_id())
        return Response(GalleryAlbumSerializer(album).data, status=status.HTTP_201_CREATED)


class GalleryItemListCreateView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        org_id = self.get_org_id()
        queryset = GalleryItem.objects.select_related('album').prefetch_related('shares__recipient').all()
        if org_id:
            queryset = queryset.filter(org_id=org_id).filter(
                Q(user=request.user) | Q(shares__recipient=request.user)
            )
        else:
            queryset = queryset.filter(user=request.user, org_id='')

        album_id = request.query_params.get('album_id')
        if album_id:
            queryset = queryset.filter(album_id=album_id)

        media_type = (request.query_params.get('media_type') or '').strip().lower()
        if media_type in {'image', 'video', 'file'}:
            queryset = queryset.filter(media_type=media_type)

        favorite_filter = _parse_bool_query_param(request.query_params.get('favorites'))
        if favorite_filter is not None:
            queryset = queryset.filter(is_favorite=favorite_filter)

        reference_filter = _parse_bool_query_param(request.query_params.get('references'))
        if reference_filter is not None:
            queryset = queryset.filter(is_reference=reference_filter)

        # MyVault / Chat integration filters
        source_filter = (request.query_params.get('source') or '').strip().lower()
        if source_filter in {'upload', 'my_chats'}:
            queryset = queryset.filter(source=source_filter)

        category_filter = (request.query_params.get('category') or '').strip().lower()
        valid_categories = {'images', 'videos', 'documents', 'audio', 'archives', 'shared_files'}
        if category_filter in valid_categories:
            queryset = queryset.filter(category=category_filter)

        search_query = (request.query_params.get('search') or '').strip()
        if search_query:
            queryset = queryset.filter(
                Q(file__icontains=search_query) |
                Q(album__name__icontains=search_query) |
                Q(chat_context_name__icontains=search_query) |
                Q(chat_sender_name__icontains=search_query)
            )

        sort_by = (request.query_params.get('sort_by') or 'created_at').strip().lower()
        sort_order = (request.query_params.get('sort_order') or 'desc').strip().lower()
        allowed_sort_fields = {
            'created_at': 'created_at',
            'captured_on': 'captured_on',
            'updated_at': 'updated_at',
        }
        sort_field = allowed_sort_fields.get(sort_by, 'created_at')
        if sort_order == 'asc':
            queryset = queryset.order_by(sort_field, 'id')
        else:
            queryset = queryset.order_by(f'-{sort_field}', '-id')

        queryset = queryset.distinct()
        serializer = GalleryItemSerializer(queryset, many=True, context={'request': request})

        # Merge Training Files if applicable
        import os
        from hr.training.models import TrainingFile, TrainingPushRecipient
        from hr.training.views import is_hr_admin
        
        training_items = []
        if org_id and not album_id and favorite_filter is not True and reference_filter is not True:
            tf_qs = TrainingFile.objects.filter(org_id=org_id)
            if not is_hr_admin(request.user):
                pushed_file_ids = TrainingPushRecipient.objects.filter(
                    user=request.user,
                    push__org_id=org_id
                ).values_list('push__training_file_id', flat=True)
                tf_qs = tf_qs.filter(id__in=pushed_file_ids)
                
            for tf in tf_qs:
                file_name = os.path.basename(tf.file.name) if tf.file else tf.title
                lowered = file_name.lower()
                
                # Infer media type
                t_media_type = 'file'
                if lowered.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg')):
                    t_media_type = 'image'
                elif lowered.endswith(('.mp4', '.mov', '.avi', '.webm')):
                    t_media_type = 'video'
                    
                # Filter by media_type
                if media_type in {'image', 'video', 'file'} and t_media_type != media_type:
                    continue
                    
                # Filter by search_query
                if search_query:
                    q_lower = search_query.lower()
                    if q_lower not in tf.title.lower() and q_lower not in file_name.lower():
                        continue
                
                # Category mapping
                t_vault_category = 'documents'
                if t_media_type == 'image':
                    t_vault_category = 'images'
                elif t_media_type == 'video':
                    t_vault_category = 'videos'
                
                if category_filter and category_filter != t_vault_category:
                    continue
                    
                # Build URLs
                relative_path = f"/api/mydesk/gallery/items/training_{tf.id}/download/?serve=1"
                file_url = request.build_absolute_uri(relative_path) if request else relative_path
                
                relative_download = f"/api/mydesk/gallery/items/training_{tf.id}/download/?serve=1&download=1"
                download_url = request.build_absolute_uri(relative_download) if request else relative_download
                
                try:
                    file_size = tf.file.size if tf.file else 0
                except Exception:
                    file_size = 0
                    
                training_items.append({
                    'id': f"training_{tf.id}",
                    'album': None,
                    'album_name': 'Training Hub',
                    'file': tf.file.name if tf.file else '',
                    'file_name': file_name,
                    'file_size_bytes': file_size,
                    'file_url': file_url,
                    'download_url': download_url,
                    'media_type': t_media_type,
                    'is_favorite': False,
                    'is_reference': False,
                    'captured_on': None,
                    'source': 'upload',
                    'category': t_vault_category,
                    'download_count': 0,
                    'chat_message_id': None,
                    'chat_context_name': '',
                    'chat_sender_name': '',
                    'chat_shared_at': None,
                    'shared_with': [],
                    'created_at': tf.created_at.isoformat() if tf.created_at else None,
                    'updated_at': tf.updated_at.isoformat() if tf.updated_at else None,
                })
                
        combined_data = list(serializer.data) + training_items
        
        # Sort combined list
        reverse = (sort_order != 'asc')
        def get_sort_key(item):
            val = item.get(sort_field)
            if not val:
                return ""
            return str(val)
        combined_data.sort(key=get_sort_key, reverse=reverse)
        
        return Response(combined_data)

    def post(self, request):
        serializer = GalleryItemSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        item = serializer.save(user=request.user, org_id=self.get_org_id())

        if item.file and (not item.media_type or item.media_type == 'file'):
            upload = request.FILES.get('file') if hasattr(request, 'FILES') else None
            content_type = str(getattr(upload, 'content_type', '') or '').lower()
            name = (item.file.name or '').lower()
            if content_type.startswith('image/') or name.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                item.media_type = 'image'
            elif content_type.startswith('video/') or name.endswith(('.mp4', '.mov', '.avi', '.webm')):
                item.media_type = 'video'
            else:
                item.media_type = 'file'
            item.save(update_fields=['media_type'])

        if item.media_type != 'image' and item.is_reference:
            item.is_reference = False
            item.save(update_fields=['is_reference'])

        shared_with_ids = _parse_shared_with_ids_payload(request.data)
        if shared_with_ids:
            _sync_gallery_item_shares(item, request.user, shared_with_ids)

        return Response(GalleryItemSerializer(item, context={'request': request}).data, status=status.HTTP_201_CREATED)


class GalleryItemDetailView(OrgScopedBaseAPIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, pk):
        if str(pk).startswith('training_'):
            return pk
        org_id = self.get_org_id()
        queryset = GalleryItem.objects.select_related('album').prefetch_related('shares__recipient').all()
        if org_id:
            queryset = queryset.filter(org_id=org_id).filter(
                Q(user=self.request.user) | Q(shares__recipient=self.request.user)
            )
        else:
            queryset = queryset.filter(user=self.request.user, org_id='')
        return generics.get_object_or_404(queryset, pk=pk)

    def patch(self, request, pk):
        item = self.get_object(pk)
        if isinstance(item, str) and item.startswith('training_'):
            return Response({'detail': 'Training files cannot be modified from the Vault.'}, status=status.HTTP_400_BAD_REQUEST)

        if item.user_id != request.user.id:
            return Response({'detail': 'Only the owner can edit this vault item.'}, status=status.HTTP_403_FORBIDDEN)

        if hasattr(request.data, 'copy'):
            payload = request.data.copy()
        else:
            payload = dict(request.data)
        if hasattr(payload, 'pop'):
            payload.pop('shared_with_ids', None)

        shared_with_ids_provided = False
        if hasattr(request.data, 'keys'):
            shared_with_ids_provided = 'shared_with_ids' in request.data.keys()
        elif isinstance(request.data, dict):
            shared_with_ids_provided = 'shared_with_ids' in request.data

        serializer = GalleryItemSerializer(item, data=payload, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if item.media_type != 'image' and item.is_reference:
            item.is_reference = False
            item.save(update_fields=['is_reference'])

        if shared_with_ids_provided:
            shared_with_ids = _parse_shared_with_ids_payload(request.data)
            _sync_gallery_item_shares(item, request.user, shared_with_ids)

        return Response(GalleryItemSerializer(item, context={'request': request}).data)

    def delete(self, request, pk):
        item = self.get_object(pk)
        if isinstance(item, str) and item.startswith('training_'):
            return Response({'detail': 'Training files cannot be deleted from the Vault.'}, status=status.HTTP_400_BAD_REQUEST)

        if item.user_id != request.user.id:
            return Response({'detail': 'Only the owner can delete this gallery item.'}, status=status.HTTP_403_FORBIDDEN)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GalleryItemDownloadView(OrgScopedBaseAPIView):
    def get_object(self, pk):
        if str(pk).startswith('training_'):
            return pk
        org_id = self.get_org_id()
        queryset = GalleryItem.objects.select_related('album').prefetch_related('shares__recipient').all()
        if org_id:
            queryset = queryset.filter(org_id=org_id).filter(
                Q(user=self.request.user) | Q(shares__recipient=self.request.user)
            )
        else:
            queryset = queryset.filter(user=self.request.user, org_id='')
        return generics.get_object_or_404(queryset, pk=pk)

    def get(self, request, pk):
        item = self.get_object(pk)
        if isinstance(item, str) and item.startswith('training_'):
            from hr.training.models import TrainingFile
            training_file_id = int(item.replace('training_', ''))
            org_id = self.get_org_id()
            training_file = generics.get_object_or_404(TrainingFile, pk=training_file_id, org_id=org_id)
            if not training_file.file:
                return Response({'detail': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)

            force_download = str(request.query_params.get('download') or '').strip().lower() in {'1', 'true', 'yes'}
            serve_direct = str(request.query_params.get('serve') or '').strip().lower() in {'1', 'true', 'yes'}
            if serve_direct:
                cloudinary_url = _cloudinary_private_download_link(training_file.file, attachment=force_download)
                if cloudinary_url:
                    return HttpResponseRedirect(cloudinary_url)

                try:
                    file_handle = training_file.file.open('rb')
                except Exception:
                    return Response({'detail': 'Unable to open file.'}, status=status.HTTP_404_NOT_FOUND)

                content_type = None
                file_name = str(getattr(training_file.file, 'name', '') or '')
                lowered = file_name.lower()
                if lowered.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg')):
                    if lowered.endswith('.png'):
                        content_type = 'image/png'
                    elif lowered.endswith('.gif'):
                        content_type = 'image/gif'
                    elif lowered.endswith('.webp'):
                        content_type = 'image/webp'
                    elif lowered.endswith('.svg'):
                        content_type = 'image/svg+xml'
                    else:
                        content_type = 'image/jpeg'
                elif lowered.endswith('.pdf'):
                    content_type = 'application/pdf'

                from django.http import FileResponse
                response = FileResponse(file_handle, content_type=content_type)
                download_name = file_name.split('/')[-1] if file_name else f'training-file-{training_file.id}'
                disposition = 'attachment' if force_download else 'inline'
                response['Content-Disposition'] = f'{disposition}; filename="{download_name}"'
                return response

            cloudinary_url = _cloudinary_private_download_link(training_file.file, attachment=force_download)
            if cloudinary_url:
                return Response({'url': cloudinary_url})

            relative_url = f"/api/mydesk/gallery/items/{pk}/download/?serve=1"
            if force_download:
                relative_url += "&download=1"
            absolute_url = request.build_absolute_uri(relative_url)
            return Response({'url': absolute_url})

        # Regular GalleryItem
        if not item.file:
            return Response({'detail': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)

        force_download = str(request.query_params.get('download') or '').strip().lower() in {'1', 'true', 'yes'}
        serve_direct = str(request.query_params.get('serve') or '').strip().lower() in {'1', 'true', 'yes'}
        if serve_direct:
            cloudinary_url = _cloudinary_private_download_link(item.file, attachment=force_download)
            if cloudinary_url:
                return HttpResponseRedirect(cloudinary_url)

            try:
                file_handle = item.file.open('rb')
            except Exception:
                return Response({'detail': 'Unable to open file.'}, status=status.HTTP_404_NOT_FOUND)

            content_type = None
            file_name = str(getattr(item.file, 'name', '') or '')
            lowered = file_name.lower()
            if lowered.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg')):
                if lowered.endswith('.png'):
                    content_type = 'image/png'
                elif lowered.endswith('.gif'):
                    content_type = 'image/gif'
                elif lowered.endswith('.webp'):
                    content_type = 'image/webp'
                elif lowered.endswith('.svg'):
                    content_type = 'image/svg+xml'
                else:
                    content_type = 'image/jpeg'
            elif lowered.endswith('.pdf'):
                content_type = 'application/pdf'

            from django.http import FileResponse
            response = FileResponse(file_handle, content_type=content_type)
            download_name = file_name.split('/')[-1] if file_name else f'gallery-file-{item.id}'
            disposition = 'attachment' if force_download else 'inline'
            response['Content-Disposition'] = f'{disposition}; filename="{download_name}"'
            return response

        cloudinary_url = _cloudinary_private_download_link(item.file, attachment=force_download)
        if cloudinary_url:
            return Response({'url': cloudinary_url})

        relative_url = f"/api/mydesk/gallery/items/{pk}/download/?serve=1"
        if force_download:
            relative_url += "&download=1"
        absolute_url = request.build_absolute_uri(relative_url)
        return Response({'url': absolute_url})


class VaultSaveFromChatView(OrgScopedBaseAPIView):
    """
    POST /api/mydesk/vault/save-from-chat/
    Body: { "message_id": <int> }

    Lets a chat-message recipient save an attachment from any message they
    can access into their own MyVault — without duplicating the physical file.
    Returns the resulting GalleryItem on success.
    """
    parser_classes = [JSONParser]

    def post(self, request):
        from core.models.chat import ChatMessage, ChatMessageRecipient, ChatRoomMember, ChatChannelMember
        from core.services.vault_sync import save_received_attachment_to_vault

        message_id = request.data.get('message_id')
        if not message_id:
            return Response({'error': 'message_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            message = ChatMessage.objects.select_related('sender', 'room', 'channel').get(id=message_id)
        except ChatMessage.DoesNotExist:
            return Response({'error': 'Message not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not message.attachment:
            return Response({'error': 'This message has no attachment.'}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        # Authorisation: sender, direct recipient, room member, or channel member
        is_sender = message.sender_id == user.id
        is_direct_recipient = ChatMessageRecipient.objects.filter(
            message=message, recipient=user
        ).exists()
        is_room_member = (
            message.room_id and
            ChatRoomMember.objects.filter(room_id=message.room_id, user=user).exists()
        )
        is_channel_member = (
            message.channel_id and
            ChatChannelMember.objects.filter(channel_id=message.channel_id, user=user).exists()
        )

        if not (is_sender or is_direct_recipient or is_room_member or is_channel_member):
            return Response({'error': 'You do not have access to this message.'}, status=status.HTTP_403_FORBIDDEN)

        item = save_received_attachment_to_vault(message, user)
        if item is None:
            return Response(
                {'error': 'Unable to save file to vault. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            GalleryItemSerializer(item, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class VaultStorageStatsView(OrgScopedBaseAPIView):
    """
    GET /api/mydesk/vault/stats/
    Returns storage analytics (file counts by category and source) for the
    current user's vault.
    """
    def get(self, request):
        from core.services.vault_sync import get_storage_stats
        org_id = self.get_org_id()
        stats = get_storage_stats(request.user, org_id)
        return Response(stats)
