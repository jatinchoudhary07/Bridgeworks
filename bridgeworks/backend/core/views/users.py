from django.utils import timezone
from datetime import timedelta, datetime
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging

logger = logging.getLogger(__name__)
from django.http import HttpResponse, JsonResponse
from django.db import models
from django.db.models import Prefetch, Q, Sum, TextField, Count, F, Case, When, DecimalField, OuterRef, Prefetch, Exists
from core.utils.payment_utils import get_payment_q_objects
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.middleware.csrf import get_token
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db.models.functions import TruncDate

from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.generics import RetrieveUpdateAPIView, ListAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination

from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import close_old_connections


# Custom authentication class that exempts CSRF for session auth
class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication without CSRF enforcement for API endpoints."""
    def enforce_csrf(self, request):
        return  # Skip CSRF check


from django_q.tasks import async_task, schedule
import zoneinfo
import json
import hmac
import hashlib
import base64
import os
import requests
import re

# --- Models ---
from core.models import (
    Order, LineItem, Fulfillment, TrackingInfo, Batch, PackagingBatch,
    PackagingImage, ShopCredentials, TeamMemberSettings, Invitation, TrackingEvent, CaseFile, IssueComment,
    RTO_TRANSIT_STATUSES, RTO_DELIVERED_STATUSES, UserProfile, WorkforceMember, Role, WorkspaceMembership
)

# --- Utils ---
from core.utils import (
    _clean_shopify_url,
    _get_decrypted_credentials,
    _get_org_id_or_none,
    _get_or_create_order_from_api,
    STATUS_MAP
)
from core.utils.stage_queries import get_queryset_for_stage

# --- Serializers ---
from core.serializers import (
    OrderSerializer, BatchSerializer, PackagingBatchSerializer, 
    CaseFileSerializer, IssueCommentSerializer, SimpleOrderSerializer,
    AWBBatchSerializer
)

# --- Permissions ---
from core.permissions import (
    IsAllowedToCall, IsAllowedToBatch, IsPackagingAgent, 
    IsOrganizationOwner, IsAllowedCustomerExperience,
    _check_granular_permission,
    HasModulePermission,
    is_org_owner
)

User: type[AbstractUser] = get_user_model()  # type: ignore[assignment]


def _normalize_profile_picture_url(url):
    raw = str(url or '').strip()
    if not raw:
        return None
    if '/res.cloudinary.com/' in raw and '/media/profile_pictures/' in raw and '/raw/upload/' in raw:
        return raw.replace('/raw/upload/', '/image/upload/')
    return raw


def _abs_file_url(request, file_field, normalize_profile=False):
    if not file_field:
        return None
    try:
        url = request.build_absolute_uri(file_field.url) if request else str(file_field.url)
    except Exception:
        return None
    if normalize_profile:
        return _normalize_profile_picture_url(url)
    return url




from .helpers import _get_org_id_or_none, _filter_orders_by_org_id, _clean_shopify_url
# 3. USER & TEAM VIEWS
# ==============================================================================

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_linked_workforce_member(self, user, request):
        org_id = _get_org_id_or_none(request)
        if not org_id or not user.email:
            return None
        return WorkforceMember.objects.filter(
            org_id=org_id,
            email__iexact=user.email.strip(),
            is_archived=False,
        ).order_by('-updated_at').first()

    def _sync_workforce_from_profile(self, user, profile, request):
        member = self._get_linked_workforce_member(user, request)
        if not member:
            return

        extra_data = member.extra_data if isinstance(member.extra_data, dict) else {}

        member.full_name = profile.full_name or user.get_full_name() or user.username or member.full_name
        member.phone = profile.phone or ''
        member.current_location = profile.location or ''
        member.gender = profile.gender or ''
        member.notes = profile.about or ''

        extra_data.update({
            'dob': profile.dob.isoformat() if profile.dob else '',
            'whatsapp': profile.whatsapp or '',
            'first_language': profile.first_language or '',
            'second_language': profile.second_language or '',
            'bank_account_name': profile.bank_account_holder or '',
            'bank_name': profile.bank_name or '',
            'account_number': profile.bank_account_number or '',
            'ifsc': profile.bank_ifsc_code or '',
        })

        try:
            if profile.aadhaar_card:
                extra_data['aadhaar_document'] = request.build_absolute_uri(profile.aadhaar_card.url)
            if profile.pan_card:
                extra_data['pan_document'] = request.build_absolute_uri(profile.pan_card.url)
        except Exception:
            pass

        member.extra_data = extra_data
        member.save()

    def _get_profile_data(self, user, request=None):
        """Helper method to get user profile data."""
        profile = getattr(user, 'profile', None)
        linked_workforce_member = self._get_linked_workforce_member(user, request) if request else None
        workforce_extra = linked_workforce_member.extra_data if linked_workforce_member and isinstance(linked_workforce_member.extra_data, dict) else {}
        
        # Build absolute URLs for uploaded files
        profile_picture_url = None
        aadhaar_document_url = None
        pan_document_url = None
        
        if profile:
            if profile.profile_picture and request:
                try:
                    profile_picture_url = _normalize_profile_picture_url(request.build_absolute_uri(profile.profile_picture.url))
                except:
                    pass
            if profile.aadhaar_card and request:
                try:
                    aadhaar_document_url = request.build_absolute_uri(profile.aadhaar_card.url)
                except:
                    pass
            if profile.pan_card and request:
                try:
                    pan_document_url = request.build_absolute_uri(profile.pan_card.url)
                except:
                    pass

        if not aadhaar_document_url:
            aadhaar_document_url = workforce_extra.get('aadhaar_document') or None
        if not pan_document_url:
            pan_document_url = workforce_extra.get('pan_document') or None

        workforce_display_name = linked_workforce_member.full_name if linked_workforce_member else ''
        workforce_dob = workforce_extra.get('dob') or None
        workforce_gender = linked_workforce_member.gender if linked_workforce_member else ''
        workforce_phone = linked_workforce_member.phone if linked_workforce_member else ''
        workforce_whatsapp = workforce_extra.get('whatsapp') or ''
        workforce_location = linked_workforce_member.current_location if linked_workforce_member else ''
        workforce_first_language = workforce_extra.get('first_language') or ''
        workforce_second_language = workforce_extra.get('second_language') or ''
        workforce_about = linked_workforce_member.notes if linked_workforce_member else ''
        workforce_bank_holder = workforce_extra.get('bank_account_name') or ''
        workforce_bank_account = workforce_extra.get('account_number') or ''
        workforce_bank_ifsc = workforce_extra.get('ifsc') or ''
        workforce_bank_name = workforce_extra.get('bank_name') or ''
        
        return {
            "dob": profile.dob.isoformat() if profile and profile.dob else workforce_dob,
            "gender": profile.gender if profile and profile.gender else workforce_gender,
            "phone": profile.phone if profile and profile.phone else workforce_phone,
            "whatsapp": profile.whatsapp if profile and profile.whatsapp else workforce_whatsapp,
            "location": profile.location if profile and profile.location else workforce_location,
            "firstLanguage": profile.first_language if profile and profile.first_language else (workforce_first_language or 'Hindi'),
            "secondLanguage": profile.second_language if profile and profile.second_language else (workforce_second_language or 'English'),
            "about": profile.about if profile and profile.about else workforce_about,
            "bankAccountHolder": profile.bank_account_holder if profile and profile.bank_account_holder else workforce_bank_holder,
            "bankAccountNumber": profile.bank_account_number if profile and profile.bank_account_number else workforce_bank_account,
            "bankIfscCode": profile.bank_ifsc_code if profile and profile.bank_ifsc_code else workforce_bank_ifsc,
            "bankName": profile.bank_name if profile and profile.bank_name else workforce_bank_name,
            "profilePicture": profile_picture_url,
            "aadhaarDocument": aadhaar_document_url,
            "panDocument": pan_document_url,
            "workforceName": workforce_display_name,
        }

    def get(self, request):
        user = request.user
        org_id = _get_org_id_or_none(request)
        linked_workforce_member = self._get_linked_workforce_member(user, request)
        
        # Get display name from profile first, then fallback
        profile = getattr(user, 'profile', None)
        display_name = profile.full_name if profile and profile.full_name else None
        
        if not display_name:
            display_name = user.get_full_name() or user.username or user.email
        if not display_name and linked_workforce_member and linked_workforce_member.full_name:
            display_name = linked_workforce_member.full_name
        try:
            if not display_name and hasattr(user, "socialaccount_set"):
                sa = user.socialaccount_set.first()
                if sa:
                    display_name = sa.extra_data.get("name", user.email)
        except Exception:
            pass

        # Resolve active shop credentials
        shop_creds = None
        if hasattr(user, 'shop_credentials'):
            shop_creds = user.shop_credentials
        elif hasattr(user, 'team_settings') and user.team_settings.organization:
            shop_creds = user.team_settings.organization
        else:
            membership = WorkspaceMembership.objects.filter(user=user).select_related('workspace').first()
            if membership and membership.workspace:
                shop_creds = membership.workspace
            elif user.is_superuser:
                from core.models import ShopCredentials
                shop_creds = ShopCredentials.objects.first()

        order_prefix = ""
        currency = "INR"
        currency_locale = "en-IN"
        store_name = ""
        store_logo = None

        if shop_creds:
            order_prefix = shop_creds.shopify_order_prefix
            currency = shop_creds.currency or "INR"
            currency_locale = shop_creds.currency_locale or "en-IN"
            store_name = shop_creds.store_name
            if shop_creds.logo:
                store_logo = request.build_absolute_uri(shop_creds.logo.url)

        role_name = "No Role"
        role_permissions = []
        
        # Superusers, Founders, and Co-Founders get "Admin" role by default
        membership = WorkspaceMembership.objects.filter(user=user).select_related('role', 'workspace').first()
        user_is_co_founder = bool(membership and membership.is_co_founder)

        # Always keep the Administrator role in DB synced with the latest _MODULES.
        # This ensures any new page/tab added to the codebase is immediately available
        # to the Administrator role without any manual intervention.
        if shop_creds:
            try:
                from core.views.views_roles import _ensure_admin_role
                _ensure_admin_role(shop_creds)
            except Exception:
                pass

        if is_org_owner(user):
            role_name = "Administrator"
            role_permissions = ["*:*:*"] # Wildcard for full access
        else:
            if membership and membership.role:
                role_name = membership.role.name
                role_permissions = list(membership.role.permissions.values_list('identifier', flat=True))

        response_data = {
            "id": user.id,
            "email": user.email,
            "name": display_name,
            "org_id": org_id,
            "shopify_order_prefix": order_prefix,
            "currency": currency,
            "currency_locale": currency_locale,
            "store_name": store_name or org_id or "Shori Store",
            "store_logo": store_logo,
            "is_founder": hasattr(user, 'shop_credentials') or user_is_co_founder,
            "is_admin": is_org_owner(user),
            "is_co_founder": user_is_co_founder,
            "is_original_founder": hasattr(user, 'shop_credentials'),
            "role_name": role_name,
            "role_permissions": role_permissions
        }
        
        # Add profile data (pass request to build absolute URLs for files)
        response_data.update(self._get_profile_data(user, request))
        
        return Response(response_data)

    def put(self, request):
        """Update user profile information."""
        user = request.user
        data = request.data
        
        # Get or create the user profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Update profile fields
        if 'name' in data:
            profile.full_name = data['name']
        if 'dob' in data:
            profile.dob = data['dob'] if data['dob'] else None
        if 'gender' in data:
            profile.gender = data['gender']
        if 'phone' in data:
            profile.phone = data['phone']
        if 'whatsapp' in data:
            profile.whatsapp = data['whatsapp']
        if 'location' in data:
            profile.location = data['location']
        if 'firstLanguage' in data:
            profile.first_language = data['firstLanguage']
        if 'secondLanguage' in data:
            profile.second_language = data['secondLanguage']
        if 'about' in data:
            profile.about = data['about']
        
        profile.save()
        self._sync_workforce_from_profile(user, profile, request)
        
        # Return updated data (same format as GET)
        # Resolve active shop credentials
        shop_creds = None
        if hasattr(user, 'shop_credentials'):
            shop_creds = user.shop_credentials
        elif hasattr(user, 'team_settings') and user.team_settings.organization:
            shop_creds = user.team_settings.organization
        else:
            membership = WorkspaceMembership.objects.filter(user=user).select_related('workspace').first()
            if membership and membership.workspace:
                shop_creds = membership.workspace
            elif user.is_superuser:
                from core.models import ShopCredentials
                shop_creds = ShopCredentials.objects.first()

        org_id = shop_creds.organization_id if shop_creds else None
        display_name = profile.full_name or user.get_full_name() or user.username or user.email
        
        order_prefix = ""
        store_name = ""
        store_logo = None

        if shop_creds:
            order_prefix = shop_creds.shopify_order_prefix
            store_name = shop_creds.store_name
            if shop_creds.logo:
                store_logo = request.build_absolute_uri(shop_creds.logo.url)

        response_data = {
            "id": user.id,
            "email": user.email,
            "name": display_name,
            "org_id": org_id,
            "shopify_order_prefix": order_prefix, 
            "store_name": store_name or org_id or "Shori Store",
            "store_logo": store_logo,
            "is_founder": hasattr(user, 'shop_credentials') or WorkspaceMembership.objects.filter(user=user, is_co_founder=True).exists(),
            "is_admin": is_org_owner(user),
            "is_co_founder": WorkspaceMembership.objects.filter(user=user, is_co_founder=True).exists(),
            "is_original_founder": hasattr(user, 'shop_credentials')
        }
        
        response_data.update(self._get_profile_data(user, request))
        
        return Response(response_data)


class ShopProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_shop_creds(self, user):
        if hasattr(user, 'shop_credentials'):
            return user.shop_credentials
        
        try:
            settings = user.team_settings
            if settings.organization:
                return settings.organization
        except TeamMemberSettings.DoesNotExist:
            pass

        try:
            from core.models.users import WorkspaceMembership
            membership = WorkspaceMembership.objects.filter(user=user).select_related('workspace').first()
            if membership:
                return membership.workspace
        except Exception:
            pass

        if user.is_superuser:
            from core.models import ShopCredentials
            return ShopCredentials.objects.first()

        return None

    def get(self, request):
        user = request.user
        shop_creds = self._get_shop_creds(user)
        if not shop_creds:
            return Response({"error": "No shop credentials found for this account."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "store_name": shop_creds.store_name,
            "store_url": shop_creds.store_url,
            "phone_number": shop_creds.phone_number,
            "email": shop_creds.email,
            "license_key": shop_creds.license_key,
            "gst_registration": shop_creds.gst_registration or 'unregistered',
            "timezone": shop_creds.timezone or 'Asia/Kolkata',
            "legal_business_name": shop_creds.legal_business_name,
            "state": shop_creds.state,
            "gst_number": shop_creds.gst_number,
            "billing_address": shop_creds.billing_address,
            "logo": request.build_absolute_uri(shop_creds.logo.url) if shop_creds.logo else None,
            "global_idle_timeout_enabled": shop_creds.global_idle_timeout_enabled,
            "global_idle_timeout_minutes": shop_creds.global_idle_timeout_minutes,
        })

    def put(self, request):
        user = request.user
        membership = WorkspaceMembership.objects.filter(user=user).select_related('role', 'workspace').first()
        user_is_co_founder = bool(membership and membership.is_co_founder)
        is_founder = hasattr(user, 'shop_credentials') or user_is_co_founder
        is_admin = is_org_owner(user)

        if not (is_founder or is_admin):
            return Response({"error": "Only administrators or founders can edit the shop profile."}, status=status.HTTP_403_FORBIDDEN)

        shop_creds = self._get_shop_creds(user)
        if not shop_creds:
            return Response({"error": "No shop credentials found for this account."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        if 'store_name' in data:
            shop_creds.store_name = data['store_name']
        if 'store_url' in data:
            shop_creds.store_url = data['store_url']
        if 'phone_number' in data:
            shop_creds.phone_number = data['phone_number']
        if 'email' in data:
            shop_creds.email = data['email']
        if 'license_key' in data:
            shop_creds.license_key = data['license_key']
        if 'gst_registration' in data:
            shop_creds.gst_registration = data['gst_registration']
        if 'timezone' in data:
            shop_creds.timezone = data['timezone']
        if 'legal_business_name' in data:
            shop_creds.legal_business_name = data['legal_business_name']
        if 'state' in data:
            shop_creds.state = data['state']
        if 'gst_number' in data:
            shop_creds.gst_number = data['gst_number']
        if 'billing_address' in data:
            shop_creds.billing_address = data['billing_address']
        if 'global_idle_timeout_enabled' in data:
            val = data['global_idle_timeout_enabled']
            if isinstance(val, str):
                shop_creds.global_idle_timeout_enabled = val.lower() != 'false'
            else:
                shop_creds.global_idle_timeout_enabled = bool(val)
        if 'global_idle_timeout_minutes' in data:
            try:
                shop_creds.global_idle_timeout_minutes = int(data['global_idle_timeout_minutes'])
            except (ValueError, TypeError):
                pass

        shop_creds.save()

        return Response({
            "store_name": shop_creds.store_name,
            "store_url": shop_creds.store_url,
            "phone_number": shop_creds.phone_number,
            "email": shop_creds.email,
            "license_key": shop_creds.license_key,
            "gst_registration": shop_creds.gst_registration,
            "timezone": shop_creds.timezone,
            "legal_business_name": shop_creds.legal_business_name,
            "state": shop_creds.state,
            "gst_number": shop_creds.gst_number,
            "billing_address": shop_creds.billing_address,
            "logo": request.build_absolute_uri(shop_creds.logo.url) if shop_creds.logo else None,
            "global_idle_timeout_enabled": shop_creds.global_idle_timeout_enabled,
            "global_idle_timeout_minutes": shop_creds.global_idle_timeout_minutes,
        })


class ShopLogoUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user
        membership = WorkspaceMembership.objects.filter(user=user).select_related('role', 'workspace').first()
        user_is_co_founder = bool(membership and membership.is_co_founder)
        is_founder = hasattr(user, 'shop_credentials') or user_is_co_founder
        is_admin = is_org_owner(user)

        if not (is_founder or is_admin):
            return Response({"error": "Only administrators or founders can upload shop logo."}, status=status.HTTP_403_FORBIDDEN)

        view = ShopProfileView()
        shop_creds = view._get_shop_creds(user)
        if not shop_creds:
            return Response({"error": "No shop credentials found."}, status=status.HTTP_404_NOT_FOUND)

        if 'logo' not in request.FILES:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        logo_file = request.FILES['logo']
        from django.core.exceptions import ValidationError as DjangoValidationError
        from core.file_validation import validate_upload
        try:
            validate_upload(logo_file)
        except DjangoValidationError as e:
            raise ValidationError({"logo": e.messages})

        # Remove old logo if it exists to clean up storage
        if shop_creds.logo:
            try:
                shop_creds.logo.delete(save=False)
            except Exception:
                pass

        shop_creds.logo = logo_file
        shop_creds.save()

        return Response({
            "logo": request.build_absolute_uri(shop_creds.logo.url) if shop_creds.logo else None
        })


class UserBankDetailsView(APIView):
    """Handle bank details updates separately."""
    permission_classes = [IsAuthenticated]

    def put(self, request):
        """Update user bank details."""
        user = request.user
        data = request.data
        
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if 'accountHolder' in data:
            profile.bank_account_holder = data['accountHolder']
        if 'accountNumber' in data:
            profile.bank_account_number = data['accountNumber']
        if 'ifscCode' in data:
            profile.bank_ifsc_code = data['ifscCode']
        if 'bankName' in data:
            profile.bank_name = data['bankName']
        
        profile.save()
        CurrentUserView()._sync_workforce_from_profile(user, profile, request)
        
        return Response({
            "bankAccountHolder": profile.bank_account_holder,
            "bankAccountNumber": profile.bank_account_number,
            "bankIfscCode": profile.bank_ifsc_code,
            "bankName": profile.bank_name,
        })


class UserProfilePictureView(APIView):
    """Handle profile picture uploads."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        """Upload user profile picture."""
        user = request.user
        
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if 'profile_picture' not in request.FILES:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        pic_file = request.FILES['profile_picture']
        from django.core.exceptions import ValidationError as DjangoValidationError
        from core.file_validation import validate_upload
        try:
            validate_upload(pic_file)
        except DjangoValidationError as e:
            raise ValidationError({"profile_picture": e.messages})

        profile.profile_picture = pic_file
        profile.save()
        
        return Response({
            "profilePicture": request.build_absolute_uri(profile.profile_picture.url) if profile.profile_picture else None
        })


class UserDocumentUploadView(APIView):
    """Handle document uploads (Aadhaar, PAN)."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, doc_type):
        """Upload user documents."""
        user = request.user
        
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if 'document' not in request.FILES:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['document']
        from django.core.exceptions import ValidationError as DjangoValidationError
        from core.file_validation import validate_upload
        try:
            validate_upload(file)
        except DjangoValidationError as e:
            raise ValidationError({"document": e.messages})
        
        if doc_type == 'aadhaar':
            profile.aadhaar_card = file
            profile.save()
            CurrentUserView()._sync_workforce_from_profile(user, profile, request)
            return Response({
                "aadhaarDocument": request.build_absolute_uri(profile.aadhaar_card.url) if profile.aadhaar_card else None
            })
        elif doc_type == 'pan':
            profile.pan_card = file
            profile.save()
            CurrentUserView()._sync_workforce_from_profile(user, profile, request)
            return Response({
                "panDocument": request.build_absolute_uri(profile.pan_card.url) if profile.pan_card else None
            })
        else:
            return Response({"error": "Invalid document type"}, status=status.HTTP_400_BAD_REQUEST)


class UserPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            return Response({
                "operations_fulfillment": {"calling_sheet": True, "packaging_sheet": True, "batch_creation": True},
                "analytics_reporting": {"view_kpis": True, "view_audit_logs": True},
                "customer_experience": {"view_all_tickets": True},
                "production_module": {"view_production": True}
            })

        # Enterprise RBAC check
        try:
            from core.models.users import WorkspaceMembership
            membership = WorkspaceMembership.objects.filter(user=user).select_related('role').first()
            if membership and membership.role:
                permissions_dict = {}
                for perm in membership.role.permissions.all():
                    # identifier format: "module:page:action"
                    parts = perm.identifier.split(':')
                    if len(parts) >= 2:
                        module = parts[0]
                        page = parts[1]
                        
                        if module not in permissions_dict:
                            permissions_dict[module] = {}
                        
                        # Just indicate access to this page
                        permissions_dict[module][page] = True
                
                # If they have the wildcard, act like a superuser
                if '*' in permissions_dict:
                    return Response({
                        "operations_fulfillment": {"calling_sheet": True, "packaging_sheet": True, "batch_creation": True},
                        "analytics_reporting": {"view_kpis": True, "view_audit_logs": True},
                        "customer_experience": {"view_all_tickets": True},
                        "production_module": {"view_production": True}
                    })

                return Response(permissions_dict)
        except Exception:
            pass

        try:
            settings = user.team_settings
            return Response(settings.granular_permissions)
        except TeamMemberSettings.DoesNotExist:
            return Response({
                "operations_fulfillment": {},
                "analytics_reporting": {},
                "customer_experience": {}
            })

class TeamMemberListAPIView(ListAPIView):
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view', 'human_resources:roles_permissions:view']
    }
    
    def get_queryset(self):
        requesting_org_id = _get_org_id_or_none(self.request)
        if not requesting_org_id:
            return User.objects.none()

        queryset = User.objects.filter(
            team_settings__organization__organization_id=requesting_org_id,
            is_active=True
        ).select_related('profile', 'shop_credentials').order_by('username')
        
        return queryset
        
    def list(self, request, *args, **kwargs):
        from core.models.users import WorkspaceMembership
        queryset = self.get_queryset()
        
        # Pre-fetch co-founder status for efficiency
        co_founder_ids = set(
            WorkspaceMembership.objects.filter(
                user__in=queryset, is_co_founder=True
            ).values_list('user_id', flat=True)
        )
        
        # Pre-fetch today's attendance status
        from django.utils import timezone
        from core.models.mydesk import AttendanceEntry
        today = timezone.localdate()
        attendance_map = {
            entry.user_id: (entry.status, entry.work_mode)
            for entry in AttendanceEntry.objects.filter(
                user__in=queryset,
                entry_date=today,
                is_active=True
            )
        }
        
        users_data = []
        for user in queryset:
            profile = getattr(user, 'profile', None)
            profile_picture_url = None
            if profile and profile.profile_picture:
                try:
                    profile_picture_url = _normalize_profile_picture_url(request.build_absolute_uri(profile.profile_picture.url))
                except Exception:
                    pass
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                'profilePicture': profile_picture_url,
                'phone': profile.phone if profile else '',
                'current_location': profile.location if profile else '',
                'gender': profile.gender if profile else '',
                'notes': profile.about if profile else '',
                'role_designation': '',
                'category': 'Team',
                'department_name': '',
                'working_style': '',
                'status': 'Active',
                'is_founder': hasattr(user, 'shop_credentials') or user.id in co_founder_ids,
                'is_co_founder': user.id in co_founder_ids,
                'is_original_founder': hasattr(user, 'shop_credentials'),
                'today_status': attendance_map.get(user.id)[0] if attendance_map.get(user.id) else None,
                'work_mode': attendance_map.get(user.id)[1] if attendance_map.get(user.id) else None,
                'idle_timeout_override_enabled': profile.idle_timeout_override_enabled if profile else None,
                'idle_timeout_override_minutes': profile.idle_timeout_override_minutes if profile else None,
            })
        return Response(users_data)

class TeamMemberDetailView(APIView):
    """Return full profile data for a specific team member (same org)."""
    permission_classes = [HasModulePermission]
    required_permissions = {
        'GET': ['human_resources:team_directory:view', 'human_resources:workforce_sheet:view', 'human_resources:roles_permissions:view']
    }

    def get(self, request, user_id):
        requesting_org_id = _get_org_id_or_none(request)
        if not requesting_org_id:
            return Response({"error": "No organization found."}, status=403)

        try:
            target_user = User.objects.get(
                id=user_id,
                team_settings__organization__organization_id=requesting_org_id,
                is_active=True,
            )
        except User.DoesNotExist:
            return Response({"error": "Member not found."}, status=404)

        profile = getattr(target_user, 'profile', None)

        # Build absolute URLs for files
        display_name = (
            (profile.full_name if profile and profile.full_name else None)
            or target_user.get_full_name()
            or target_user.username
            or target_user.email
        )

        data = {
            "id": target_user.id,
            "email": target_user.email,
            "name": display_name,
            "username": target_user.username,
            "dob": profile.dob.isoformat() if profile and profile.dob else None,
            "gender": profile.gender if profile else "",
            "phone": profile.phone if profile else "",
            "whatsapp": profile.whatsapp if profile else "",
            "location": profile.location if profile else "",
            "firstLanguage": profile.first_language if profile else "",
            "secondLanguage": profile.second_language if profile else "",
            "about": profile.about if profile else "",
            "bankAccountHolder": profile.bank_account_holder if profile else "",
            "bankAccountNumber": profile.bank_account_number if profile else "",
            "bankIfscCode": profile.bank_ifsc_code if profile else "",
            "bankName": profile.bank_name if profile else "",
            "profilePicture": _abs_file_url(request, profile.profile_picture, normalize_profile=True) if profile else None,
            "aadhaarDocument": _abs_file_url(request, profile.aadhaar_card) if profile else None,
            "panDocument": _abs_file_url(request, profile.pan_card) if profile else None,
        }
        return Response(data)


class TeammatePermissionsView(APIView):
    """
    Allows Org Owners OR users with the 'human_resources:roles_permissions:edit' RBAC permission.
    """
    permission_classes = [IsAuthenticated]

    def _has_access(self, request, target_user=None):
        user = request.user
        if not user.is_authenticated:
            return False
            
        # 1. Self-edit protection: No one can edit their own permissions via this page
        if target_user and user.id == target_user.id:
            return False

        # 2. Founder protection: Non-founder admins cannot edit the original founder
        if target_user and hasattr(target_user, 'shop_credentials') and not hasattr(user, 'shop_credentials') and not user.is_superuser:
            return False

        # 3. Co-founder protection: only the original founder or superuser can edit a co-founder
        if target_user:
            target_is_co_founder = WorkspaceMembership.objects.filter(user=target_user, is_co_founder=True).exists()
            if target_is_co_founder and not hasattr(user, 'shop_credentials') and not user.is_superuser:
                return False

        # Org owners, co-founders & superusers always allowed (if not blocked by rules above)
        if is_org_owner(user):
            return True
            
        # Check via RBAC role permissions
        return _check_granular_permission(user, 'human_resources', 'roles_permissions', request.method)

    def get(self, request, user_id):
        try:
            target_user = User.objects.get(id=user_id)
            if not self._has_access(request, target_user):
                return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
            settings, created = TeamMemberSettings.objects.get_or_create(user=target_user)
            
            # Fetch explicitly assigned Role if not using legacy granular setup
            membership = WorkspaceMembership.objects.filter(user=target_user).first()
            role_id = membership.role.id if membership and membership.role else None

            return Response({
                'user_id': target_user.id,
                'email': target_user.email,
                'permissions': settings.granular_permissions,
                'role_id': role_id
            })
        except User.DoesNotExist:
            return Response({"error": "Teammate not found."}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, user_id):
        try:
            target_user = User.objects.get(id=user_id)
            if not self._has_access(request, target_user):
                return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
            
            # Handle Role Assignment
            role_id = request.data.get('role_id')
            if role_id:
                role = Role.objects.get(id=role_id)
                # Determine workspace with fallback logic
                workspace = getattr(request.user, 'shop_credentials', None)
                if not workspace:
                    from core.models.users import WorkspaceMembership as WM
                    mem = WM.objects.filter(user=request.user).select_related('workspace').first()
                    if mem:
                        workspace = mem.workspace
                if not workspace:
                    return Response({"error": "No workspace found."}, status=status.HTTP_400_BAD_REQUEST)
                WorkspaceMembership.objects.update_or_create(
                    user=target_user,
                    workspace=workspace,
                    defaults={'role': role}
                )
            
            # Keep legacy settings just in case
            settings, _ = TeamMemberSettings.objects.get_or_create(user=target_user)
            new_permissions = request.data.get('permissions', {})
            
            if isinstance(new_permissions, dict):
                settings.granular_permissions = new_permissions
                settings.save()
            
            return Response({"status": "Permissions updated successfully."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "Teammate not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error updating permissions: {e}"}, status=status.HTTP_400_BAD_REQUEST)
            
class InviteTeammateView(TeammatePermissionsView):
    # Inherit _has_access from TeammatePermissionsView
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not self._has_access(request):
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
            
        founder_org_id = _get_org_id_or_none(request)
        if not founder_org_id:
            return Response({"error": "No organization found for this account."}, status=403)

        email = request.data.get("email")
        permissions_json = request.data.get("permissions", {})
        role_id = request.data.get("role_id")

        if not email:
            return Response({"error": "Email is required."}, status=400)

        defaults_dict = {
            "org_id": founder_org_id,
            "permissions_json": permissions_json,
            "sent_by": request.user,
            "accepted_user": None,
        }
        
        # In a very rigorous system, we would store role_id on the Invite as well
        # But this suffices for backward compatibility and connecting it up.
        
        invite, created = Invitation.objects.update_or_create(
            email=email,
            defaults=defaults_dict,
        )

        from django.conf import settings as django_settings
        frontend_url = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:5173')
        signup_url = f"{frontend_url}/signup/?invite={invite.token}"

        return Response({
            "status": "Invitation created" if created else "Invitation updated",
            "invite_link": signup_url,
            "token": str(invite.token),
        })

class PermissionSchemaView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        schema = {
            "orders": {
                "all_orders": "All Orders Dashboard",
                "ndr": "NDR Management"
            },
            "operations_fulfillment": {
                "analytics": "Analytics",
                "orders": "Orders",
                "calling_sheet": "Calling Sheet Access (Confirm Orders)",
                "packaging_sheet": "Packaging Sheet Access (Fulfillment)",
                "batch_creation": "Batch Creation (Order Grouping)",
                "awb_sheet": "AWB / Tracking Lookup",
                "confirmation_sheet": "Confirmation Sheet Access",
                "pending_orders": "Pending Orders Management",
                "manifest_sheet": "Manifest / Dispatch Sheet Access",
                "unfulfilled_orders": "Unfulfilled Orders",
                "tracking_added": "Tracking Added",
                "confirmed": "Confirmed Orders"
            },
            "analytics_reporting": {
                "view_kpis": "View Analytics & KPIs",
                "view_audit_logs": "View Sensitive Audit Logs",
            },
            "customer_experience": {
                "case_file_sheet": "View Customer Case File Sheet",
            },
            "logistics": { 
                "lm_sheet": "LM Sheet",
                "analytics": "Analytics",
                "delivery_analytics": "Delivery Analytics Dashboard",
                "ndr_analytics": "NDR Analytics",
                "delivered_orders": "Delivered Orders",
                "ndr_action": "NDR / Action",
                "returns": "Returns",
                "exchanges": "Exchanges",
                "returns_scanner": "Returns Scanner",
                "ret_exc_stocking": "RET & EXC Stocking",
                "webhook_logs": "Webhook Logs",
                "warehouse_manager": "Warehouse Manager",
                "rate_card_manager": "Rate Card Manager",
                "cost_management": "Cost Management (CSV Upload, Rate Cards, COD Remittance)"
            },
            "rto_module": {
                "rto_in_transit": "RTO In-Transit",
                "rto_delivered": "RTO Delivered",
                "rto_manager": "RTO Manager",
                "rto_engine": "RTO Engine"
            },
            "marketing_growth": {
                "overview": "Overview",
                "meta_ads": "Meta Ads",
                "google_ads": "Google Ads",
                "marketing_aura": "Marketing Aura",
                "youtube_ads": "YouTube Ads",
                "pinterest_ads": "Pinterest Ads",
                "snapchat_ads": "Snapchat Ads",
                "amazon_ads": "Amazon Ads",
                "flipkart_ads": "Flipkart Ads",
                "etsy_ads": "Etsy Ads",
                "ajio_ads": "Ajio Ads",
                "tatacliq_ads": "Tata Cliq Lux",
                "myntra_ads": "Myntra",
                "nykaa_ads": "Nykaa",
                "blinkit_ads": "Blinkit Ads",
                "instamart_ads": "Instamart Ads",
                "zepto_ads": "Zepto Ads",
                "social_calendar": "Content Calendar",
                "social_posts": "Posts & Scheduling",
                "social_analytics": "Social Analytics",
                "influencer_database": "Influencer Database",
                "influencer_campaigns": "Influencer Campaigns",
                "offline_events": "Events & Exhibitions",
                "offline_leads": "Offline Leads",
                "offline_analytics": "Offline Analytics",
                "pr_coverage": "PR Coverage",
                "pr_outreach": "PR Outreach",
                "celebrity_spottings": "Celebrity Spottings",
                "celebrity_campaigns": "Celebrity Campaigns",
                "brand_monitoring": "Brand Monitoring",
                "campaigns_hub": "Campaigns Hub",
                "attribution": "Attribution",
            },
            "intelligence": {
                "rto_intelligence": "RTO Intelligence",
                "marketing_aura": "Marketing Aura AI",
                "ai_context": "AI Analytics Context",
                "ndr_escalations": "NDR Escalations"
            },
            "production_module": {
                "view_production": "Access Production / Manufacturing External Module",
            },
            "human_resources": {
                "team_directory": "Team Directory",
                "workforce_sheet": "Master Workforce Sheet",
                "roles_permissions": "Roles & Permissions",
                "attendance_dashboard": "Attendance Dashboard",
                "master_task_tracker": "Master Task Tracker",
                "meeting_manager": "Meeting Manager",
                "payroll": "Payroll",
                "expenses": "Expenses Tracker",
                "diary_logbooks": "Diary Logbooks"
            },
            "inventory": {
                "stock_management": "Stock Management",
                "purchase_orders": "Purchase Orders"
            },
            "settings": {
                "general_settings": "General Settings",
                "users_roles": "Users & Roles Management",
                "billing": "Billing & Invoices",
                "api_management": "API Management & Webhooks"
            },
            "finance_accounting": {
                "dashboard": "Finance Dashboard",
                "income": "Income",
                "expense": "Expense",
                "orders_payments": "Orders & Payments",
                "channels_fees": "Channels & Fees",
                "vendors_cogs": "Vendors & COGS",
                "shipping": "Shipping",
                "gst_tax": "GST & Tax",
                "international": "International",
                "departments": "Departments",
                "pnl_statement": "P&L Statement",
                # Sidebar page permissions (must match FinanceSidebar.jsx)
                "journal": "Journal Entry",
                "ledger": "Ledger Summary",
                "trial_balance": "Trial Balance",
                "balance_sheet": "Balance Sheet",
                "pending_expenses": "Pending Expenses",
                "finance": "Finance (Income & Expenses)",
                "payroll": "Payroll",
                "dept_expenses": "Dept Expenses"
            },
            "sales_business": {
                "overview": "Sales Overview Dashboard",
                "leads": "B2B Leads Management",
                "crm": "Wholesale CRM",
                "quotations": "Quotation Tracker",
                "funnel": "Conversion Funnel Analytics",
                "recovery": "Abandoned Cart Recovery",
                "forecasting": "Sales & Revenue Forecasting",
                "ai_recommendations": "AI Product Recommendations",
                "analytics": "Performance Analytics",
                "marketplace": "Marketplace Channel Analytics",
                "shopify": "Shopify Store Analytics",
                "retail": "Retail Store / Offline Sales Analytics",
                "draft_orders": "Create Draft Orders",
                "attribution": "Order Attribution Tracking"
            },
            "product_merch": {
                "inventory": "Product Inventory Management",
                "stock_log": "Stock Movement Logs",
                "best_selling": "Best Selling Products Analysis",
                "ai_stock_keeper": "AI-powered Stock Optimization",
                "die_inventory": "Die / Mold Inventory",
                "machines": "Machine Management",
                "tools": "Tools & Equipment",
                "packaging": "Packaging Materials",
                "miscellaneous": "Miscellaneous Items",
                "office_supplies": "Office Supplies",
                "master_table": "Master Inventory Table",
                "shopify_listed": "Listed on Shopify",
                "repair": "Repair Queue"
            },
        }
        return Response({"permissions": schema}, status=200)
    
class TeammateDeleteView(TeammatePermissionsView):
    # Inherit _has_access from TeammatePermissionsView
    permission_classes = [IsAuthenticated]

    def delete(self, request, user_id):
        try:
            user_to_delete = User.objects.get(id=user_id)
            if not self._has_access(request, user_to_delete):
                return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

            # Resolve the organization of the user to be deleted
            target_org_id = None
            if hasattr(user_to_delete, 'team_settings') and user_to_delete.team_settings.organization:
                target_org_id = user_to_delete.team_settings.organization.organization_id
            
            requesting_org_id = _get_org_id_or_none(request)
            if not target_org_id or target_org_id != requesting_org_id:
                return Response({"error": "User does not belong to your organization."}, status=403)

            user_to_delete.delete()
            return Response({"status": "Team member removed successfully."}, status=200)

        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)

# ==============================================================================


class CoFounderToggleView(APIView):
    """
    Only the original founder (shop_credentials owner) can promote/demote
    a team member to co-founder status.
    """
    permission_classes = [IsAuthenticated]

    def put(self, request, user_id):
        user = request.user

        # Only the original founder can toggle co-founder status
        if not hasattr(user, 'shop_credentials'):
            return Response(
                {"error": "Only the original founder can promote co-founders."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        # Cannot promote yourself
        if target_user.id == user.id:
            return Response({"error": "Cannot change your own co-founder status."}, status=status.HTTP_400_BAD_REQUEST)

        # Cannot promote another original founder
        if hasattr(target_user, 'shop_credentials'):
            return Response({"error": "This user is already an original founder."}, status=status.HTTP_400_BAD_REQUEST)

        is_co_founder = request.data.get('is_co_founder', False)
        workspace = user.shop_credentials

        membership, created = WorkspaceMembership.objects.get_or_create(
            user=target_user,
            workspace=workspace,
            defaults={'is_co_founder': bool(is_co_founder)}
        )

        if not created:
            membership.is_co_founder = bool(is_co_founder)
            membership.save(update_fields=['is_co_founder'])

        action = "promoted to co-founder" if is_co_founder else "removed from co-founder"
        return Response(
            {"status": f"{target_user.email} has been {action}.", "is_co_founder": bool(is_co_founder)},
            status=status.HTTP_200_OK
        )


class HRUserAttendanceSettingsView(APIView):
    """
    PATCH /api/hr/users/<int:user_id>/attendance-settings/
    Allows Org Owners OR users with the 'human_resources:workforce:edit' or 'human_resources:attendance_dashboard:edit' RBAC permission.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, user_id):
        user = request.user
        
        has_access = False
        if is_org_owner(user):
            has_access = True
        else:
            has_access = (
                _check_granular_permission(user, 'human_resources', 'workforce', 'PATCH') or
                _check_granular_permission(user, 'human_resources', 'attendance_dashboard', 'PATCH')
            )
            
        if not has_access:
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        try:
            target_user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        from core.views.helpers import _get_org_id_or_none
        requesting_org_id = _get_org_id_or_none(request) or ''
        
        target_org_id = None
        if hasattr(target_user, 'team_settings') and target_user.team_settings.organization:
            target_org_id = target_user.team_settings.organization.organization_id
        else:
            from core.models.users import WorkspaceMembership
            membership = WorkspaceMembership.objects.filter(user=target_user).select_related('workspace').first()
            if membership:
                target_org_id = membership.workspace.organization_id

        if not target_org_id or target_org_id != requesting_org_id:
            return Response({"error": "User does not belong to your organization."}, status=status.HTTP_403_FORBIDDEN)

        profile, created = UserProfile.objects.get_or_create(user=target_user)
        
        data = request.data
        if 'idle_timeout_override_enabled' in data:
            val = data['idle_timeout_override_enabled']
            if val is None or val == '' or str(val).lower() == 'null':
                profile.idle_timeout_override_enabled = None
            elif isinstance(val, str):
                profile.idle_timeout_override_enabled = val.lower() != 'false'
            else:
                profile.idle_timeout_override_enabled = bool(val)
                
        if 'idle_timeout_override_minutes' in data:
            val = data['idle_timeout_override_minutes']
            if val is None or val == '' or str(val).lower() == 'null':
                profile.idle_timeout_override_minutes = None
            else:
                try:
                    profile.idle_timeout_override_minutes = int(val)
                except (ValueError, TypeError):
                    pass

        profile.save()
        
        return Response({
            "user_id": target_user.id,
            "idle_timeout_override_enabled": profile.idle_timeout_override_enabled,
            "idle_timeout_override_minutes": profile.idle_timeout_override_minutes,
        }, status=status.HTTP_200_OK)
