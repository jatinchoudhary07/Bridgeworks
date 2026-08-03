import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from core.models import MarketingCredential, ShopCredentials, GoogleAdsCredential, ProductionSoftwareCredential

logger = logging.getLogger(__name__)


def _get_shop(user):
    """Helper to resolve the shop for a user (founder or team member)."""
    if hasattr(user, 'shop_credentials'):
        return user.shop_credentials
    if hasattr(user, 'team_settings') and user.team_settings.organization:
        return user.team_settings.organization
    return None


class MarketingCredentialView(APIView):
    """
    GET  /api/marketing/credentials/  — load existing creds for this shop (masked)
    POST /api/marketing/credentials/  — save/update creds for this shop
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = _get_shop(request.user)
        if not shop:
            return Response({'error': 'No organization found.'}, status=400)

        try:
            cred = MarketingCredential.objects.get(shop=shop, platform='Meta')
            return Response({
                'ad_account_id': cred.ad_account_id,
                # Mask sensitive fields — return masked placeholders so the form
                # shows that they are already saved without revealing the raw value.
                'access_token':  '••••••••' if cred.access_token_encrypted else '',
                'app_id':        '••••••••' if cred.app_id_encrypted else '',
                'app_secret':    '••••••••' if cred.app_secret_encrypted else '',
                'is_active':     cred.is_active,
            })
        except MarketingCredential.DoesNotExist:
            return Response({
                'ad_account_id': '',
                'access_token': '',
                'app_id': '',
                'app_secret': '',
                'is_active': True,
            })

    def post(self, request):
        shop = _get_shop(request.user)
        if not shop:
            return Response({'error': 'No organization found.'}, status=400)

        data = request.data
        ad_account_id = data.get('ad_account_id', '').strip()
        access_token  = data.get('access_token', '').strip()
        app_id        = data.get('app_id', '').strip()
        app_secret    = data.get('app_secret', '').strip()
        is_active     = data.get('is_active', True)

        if not ad_account_id:
            return Response({'error': 'Ad Account ID is required.'}, status=400)

        # Prefix with act_ if the user didn't include it
        if not ad_account_id.startswith('act_'):
            ad_account_id = f'act_{ad_account_id}'

        cred, created = MarketingCredential.objects.get_or_create(
            shop=shop,
            platform='Meta',
            defaults={'ad_account_id': ad_account_id}
        )

        # Always update ad_account_id and is_active
        cred.ad_account_id = ad_account_id
        cred.is_active = is_active

        # Only overwrite encrypted fields if the user provided a non-masked value
        PLACEHOLDER = '••••••••'
        if access_token and access_token != PLACEHOLDER:
            cred.set_access_token(access_token)
        if app_id and app_id != PLACEHOLDER:
            cred.set_app_id(app_id)
        if app_secret and app_secret != PLACEHOLDER:
            cred.set_app_secret(app_secret)

        cred.save()

        action = 'created' if created else 'updated'
        logger.info(f"Marketing credential {action} for shop {shop.organization_id}")
        return Response({'detail': f'Meta credentials {action} successfully.'}, status=200)


class GoogleAdsCredentialView(APIView):
    """
    GET  /api/marketing/credentials/google/  — load existing Google Ads creds (masked)
    POST /api/marketing/credentials/google/  — save/update Google Ads creds
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = _get_shop(request.user)
        if not shop:
            return Response({'error': 'No organization found.'}, status=400)

        try:
            cred = GoogleAdsCredential.objects.get(shop=shop)
            return Response({
                'client_id': cred.client_id or '',
                'login_customer_id': cred.login_customer_id or '',
                'customer_id': cred.customer_id or '',
                # Mask sensitive fields
                'developer_token': '••••••••' if cred.developer_token_encrypted else '',
                'client_secret': '••••••••' if cred.client_secret_encrypted else '',
                'refresh_token': '••••••••' if cred.refresh_token_encrypted else '',
                'is_active': cred.is_active,
            })
        except GoogleAdsCredential.DoesNotExist:
            return Response({
                'client_id': '',
                'login_customer_id': '',
                'customer_id': '',
                'developer_token': '',
                'client_secret': '',
                'refresh_token': '',
                'is_active': True,
            })

    def post(self, request):
        shop = _get_shop(request.user)
        if not shop:
            return Response({'error': 'No organization found.'}, status=400)

        data = request.data
        client_id         = data.get('client_id', '').strip()
        login_customer_id = data.get('login_customer_id', '').strip()
        customer_id       = data.get('customer_id', '').strip()
        developer_token   = data.get('developer_token', '').strip()
        client_secret     = data.get('client_secret', '').strip()
        refresh_token     = data.get('refresh_token', '').strip()
        is_active         = data.get('is_active', True)

        if not customer_id:
            return Response({'error': 'Target Customer ID is required.'}, status=400)

        cred, created = GoogleAdsCredential.objects.get_or_create(
            shop=shop,
            customer_id=customer_id
        )

        cred.client_id = client_id
        cred.login_customer_id = login_customer_id
        cred.is_active = is_active

        PLACEHOLDER = '••••••••'
        if developer_token and developer_token != PLACEHOLDER:
            cred.set_developer_token(developer_token)
        if client_secret and client_secret != PLACEHOLDER:
            cred.set_client_secret(client_secret)
        if refresh_token and refresh_token != PLACEHOLDER:
            cred.set_refresh_token(refresh_token)

        cred.save()

        action = 'created' if created else 'updated'
        logger.info(f"Google Ads credential {action} for shop {shop.organization_id}")
        return Response({'detail': f'Google Ads credentials {action} successfully.'}, status=200)


class ProductionSoftwareCredentialView(APIView):
    """
    GET  /api/settings/production-software/  — load existing config (API key masked)
    POST /api/settings/production-software/  — save/update config
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = _get_shop(request.user)
        if not shop:
            return Response({'error': 'No organization found.'}, status=400)

        try:
            cred = ProductionSoftwareCredential.objects.get(shop=shop)
            return Response({
                'api_url': cred.api_url,
                'api_key': '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022' if cred.api_key_encrypted else '',
            })
        except ProductionSoftwareCredential.DoesNotExist:
            return Response({'api_url': '', 'api_key': ''})

    def post(self, request):
        shop = _get_shop(request.user)
        if not shop:
            return Response({'error': 'No organization found.'}, status=400)

        api_url = request.data.get('api_url', '').strip()
        api_key = request.data.get('api_key', '').strip()

        if not api_url:
            return Response({'error': 'API URL is required.'}, status=400)

        cred, created = ProductionSoftwareCredential.objects.get_or_create(shop=shop)
        cred.api_url = api_url

        PLACEHOLDER = '\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022'
        if api_key and api_key != PLACEHOLDER:
            cred.set_api_key(api_key)

        cred.save()

        action = 'created' if created else 'updated'
        logger.info(f"Production software credential {action} for shop {shop.organization_id}")
        return Response({'detail': f'Production software credentials {action} successfully.'}, status=200)


class InternalWorkflowsView(APIView):
    """
    GET  /api/settings/internal-workflows/  - get status of internal workflow toggles
    POST /api/settings/internal-workflows/  - update internal workflow toggles
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = _get_shop(request.user)
        if not shop:
            return Response({'error': 'No organization found.'}, status=400)

        return Response({
            'enable_auto_confirm_orders': getattr(shop, 'enable_auto_confirm_orders', True),
            'enable_auto_assign_couriers': getattr(shop, 'enable_auto_assign_couriers', True),
            'enable_auto_send_picklists': getattr(shop, 'enable_auto_send_picklists', True),
        })

    def post(self, request):
        shop = _get_shop(request.user)
        if not shop:
            return Response({'error': 'No organization found.'}, status=400)

        # Check permissions: only admins/founders can edit
        from core.permissions import is_org_owner
        from core.models.users import WorkspaceMembership
        
        user = request.user
        membership = WorkspaceMembership.objects.filter(user=user).select_related('role', 'workspace').first()
        user_is_co_founder = bool(membership and membership.is_co_founder)
        is_founder = hasattr(user, 'shop_credentials') or user_is_co_founder
        is_admin = is_org_owner(user)

        if not (is_founder or is_admin):
            return Response({"error": "Only administrators or founders can edit internal workflows settings."}, status=status.HTTP_403_FORBIDDEN)

        data = request.data
        if 'enable_auto_confirm_orders' in data:
            shop.enable_auto_confirm_orders = bool(data.get('enable_auto_confirm_orders'))
        if 'enable_auto_assign_couriers' in data:
            shop.enable_auto_assign_couriers = bool(data.get('enable_auto_assign_couriers'))
        if 'enable_auto_send_picklists' in data:
            shop.enable_auto_send_picklists = bool(data.get('enable_auto_send_picklists'))

        shop.save()
        logger.info(f"Internal workflows settings updated for shop {shop.organization_id}")
        return Response({
            'detail': 'Internal Workflows settings updated successfully.',
            'enable_auto_confirm_orders': shop.enable_auto_confirm_orders,
            'enable_auto_assign_couriers': shop.enable_auto_assign_couriers,
            'enable_auto_send_picklists': shop.enable_auto_send_picklists,
        }, status=200)

