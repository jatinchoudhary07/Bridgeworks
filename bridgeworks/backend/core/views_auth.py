from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from django.conf import settings
from django.core.cache import cache
import secrets
from django.core.exceptions import ObjectDoesNotExist
from allauth.socialaccount.providers.google.views import oauth2_callback
from allauth.socialaccount.models import SocialToken, SocialAccount, SocialApp
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode
from .models import GoogleCalendarAuth, GmailAuth

class AuthAnonRateThrottle(AnonRateThrottle):
    rate = '5/minute'

class AuthUserRateThrottle(UserRateThrottle):
    rate = '10/minute'

class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [AuthAnonRateThrottle, AuthUserRateThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')

            # Return both access and refresh tokens in JSON body as a fallback for cross-site cookie restrictions
            res = Response({'access': access_token, 'refresh': refresh_token}, status=status.HTTP_200_OK)

            # Set refresh token in HttpOnly cookie
            cookie_max_age = 3600 * 24 * 7 # 7 days
            secure_param = getattr(settings, 'SESSION_COOKIE_SECURE', True)
            samesite_param = getattr(settings, 'SESSION_COOKIE_SAMESITE', 'None')
            
            res.set_cookie(
                key='refresh_token',
                value=refresh_token,
                max_age=cookie_max_age,
                httponly=True,
                secure=secure_param,
                samesite=samesite_param
            )
            return res
        return response

class CustomTokenRefreshView(TokenRefreshView):
    throttle_classes = [AuthAnonRateThrottle, AuthUserRateThrottle]

    def post(self, request, *args, **kwargs):
        # Fallback to JSON body if the browser blocked the cross-origin cookie
        refresh_token = request.COOKIES.get('refresh_token') or request.data.get('refresh')
        
        if not refresh_token:
            return Response({"detail": "Refresh token missing."}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Inject the refresh token into the request data for TokenRefreshView to process
        request._full_data = request.data.copy()
        request._full_data['refresh'] = refresh_token
        
        try:
            response = super().post(request, *args, **kwargs)
        except TokenError as e:
            raise InvalidToken(e.args[0])
        except ObjectDoesNotExist:
            return Response({"detail": "Invalid refresh token."}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception:
            # Never fail refresh with 500 for token/user lookup problems.
            return Response({"detail": "Invalid refresh token."}, status=status.HTTP_401_UNAUTHORIZED)

        if response.status_code == 200:
            access_token = response.data.get('access')
            new_refresh_token = response.data.get('refresh')
            
            # Return both access and refresh tokens in JSON body
            res = Response({'access': access_token, 'refresh': new_refresh_token or refresh_token}, status=status.HTTP_200_OK)
            
            # Also set the new refresh token in the HttpOnly cookie for standard environments
            if new_refresh_token:
                cookie_max_age = 3600 * 24 * 7
                secure_param = getattr(settings, 'SESSION_COOKIE_SECURE', True)
                samesite_param = getattr(settings, 'SESSION_COOKIE_SAMESITE', 'None')
                res.set_cookie(
                    key='refresh_token',
                    value=new_refresh_token,
                    max_age=cookie_max_age,
                    httponly=True,
                    secure=secure_param,
                    samesite=samesite_param
                )
            return res
        return response

class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            # Safely check request.COOKIES and request.data for refresh token
            refresh_token = request.COOKIES.get('refresh_token')
            if not refresh_token:
                try:
                    refresh_token = request.data.get('refresh') if request.data else None
                except Exception as parse_err:
                    print(f"[Logout] request.data parse warning: {parse_err}")
                    refresh_token = None

            if refresh_token:
                try:
                    token = RefreshToken(refresh_token)
                    token.blacklist()
                except Exception as e:
                    # Ignore invalid or already blacklisted tokens
                    print(f"[Logout] Token blacklist warning: {e}")
                
            try:
                from django.contrib.auth import logout as django_logout
                django_logout(request)  # Clear session cookies & server-side Django session
            except Exception as session_err:
                print(f"[Logout] Django session logout warning: {session_err}")
            
            res = Response({"detail": "Successfully logged out."}, status=status.HTTP_200_OK)
            
            samesite_param = getattr(settings, 'SESSION_COOKIE_SAMESITE', 'None')
            res.delete_cookie('refresh_token', samesite=samesite_param)
            return res
        except Exception as e:
            # Fallback error handling: always try to clear the cookie and return OK
            print(f"[Logout] Unexpected logout error: {e}")
            res = Response({"detail": "Successfully logged out with fallback."}, status=status.HTTP_200_OK)
            try:
                samesite_param = getattr(settings, 'SESSION_COOKIE_SAMESITE', 'None')
                res.delete_cookie('refresh_token', samesite=samesite_param)
            except Exception:
                pass
            return res

def _sync_gcal_token(user):
    """
    Called after every successful Google login.
    Copies the SocialToken allauth stored into GoogleCalendarAuth so that
    the Calendar / Meet integration works automatically — no separate
    "Connect Calendar" step needed.
    """
    try:
        social_account = SocialAccount.objects.get(user=user, provider='google')
        token_obj = SocialToken.objects.filter(account=social_account).order_by('-expires_at').first()
        if not token_obj or not token_obj.token:
            return
        # allauth stores: token = access_token, token_secret = refresh_token
        refresh_token = token_obj.token_secret or ''
        GoogleCalendarAuth.objects.update_or_create(
            user=user,
            defaults={
                'access_token':  token_obj.token,
                'refresh_token': refresh_token,
                'token_expiry':  token_obj.expires_at,
                'scopes':        ' '.join(settings.GOOGLE_CALENDAR_SCOPES),
            },
        )
        print(f'[_sync_gcal_token] synced calendar token for user={user.id}, has_refresh={bool(refresh_token)}')
    except Exception as exc:
        # Non-fatal – login still succeeds even if this fails
        print(f'[_sync_gcal_token] warning: {exc}')


def _sync_gmail_token(user):
    """
    Copies the SocialToken allauth stored into GmailAuth so that the
    Gmail integration works automatically without a second login popup.
    """
    try:
        social_account = SocialAccount.objects.get(user=user, provider='google')
        token_obj = SocialToken.objects.filter(account=social_account).order_by('-expires_at').first()
        if not token_obj or not token_obj.token:
            return
        # allauth stores: token = access_token, token_secret = refresh_token
        refresh_token = token_obj.token_secret or ''
        gmail_email = social_account.extra_data.get('email', user.email or '')

        # Define Gmail-specific scopes we sync
        gmail_scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.modify',
        ]

        GmailAuth.objects.update_or_create(
            user=user,
            defaults={
                'access_token':  token_obj.token,
                'refresh_token': refresh_token,
                'token_expiry':  token_obj.expires_at,
                'scopes':        ' '.join(gmail_scopes),
                'gmail_email':   gmail_email,
            },
        )
        print(f'[_sync_gmail_token] synced gmail token for user={user.id}, email={gmail_email}, has_refresh={bool(refresh_token)}')
    except Exception as exc:
        print(f'[_sync_gmail_token] warning: {exc}')


def google_callback_with_jwt(request):
    # Call the original allauth callback
    response = oauth2_callback(request)
    
    # If the login was successful, allauth redirects to LOGIN_REDIRECT_URL
    if response.status_code == 302 and request.user.is_authenticated:
        user = request.user

        # Auto-sync the Google Calendar and Gmail tokens so no separate OAuth popups are needed
        _sync_gcal_token(user)
        _sync_gmail_token(user)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Generate a short-lived 30-second one-time exchange code to prevent URL parameter exposure
        exchange_code = f"google_exchange_{secrets.token_hex(20)}"
        cache_data = {
            'access_token': access_token,
            'refresh_token': refresh_token
        }
        cache.set(exchange_code, cache_data, timeout=30)
        
        # Parse existing redirect URL
        parsed_url = urlparse(response.url)
        query = parse_qs(parsed_url.query)
        
        # Pass only the secure one-time code to the frontend URL
        query['code'] = exchange_code
        new_query = urlencode(query, doseq=True)
        response['Location'] = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query, parsed_url.fragment))
        
        # Avoid setting the cookie in the GET callback to prevent cross-site exposure;
        # the cookie will be set securely via HttpOnly on the POST exchange request.
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AuthAnonRateThrottle, AuthUserRateThrottle])
def google_token_exchange(request):
    """
    Exchanges a short-lived one-time code for JWT access and refresh tokens.
    """
    code = request.data.get('code')
    if not code:
        return Response({"detail": "Code is required."}, status=status.HTTP_400_BAD_REQUEST)
        
    if not code.startswith("google_exchange_"):
        return Response({"detail": "Invalid code format."}, status=status.HTTP_400_BAD_REQUEST)
        
    # Retrieve from cache
    cache_data = cache.get(code)
    if not cache_data:
        return Response({"detail": "Code has expired or is invalid."}, status=status.HTTP_400_BAD_REQUEST)
        
    # Invalidate immediately (one-time use)
    cache.delete(code)
    
    access_token = cache_data.get('access_token')
    refresh_token = cache_data.get('refresh_token')
    
    # Return both access and refresh tokens in JSON body
    res = Response({
        'access': access_token,
        'refresh': refresh_token
    }, status=status.HTTP_200_OK)
    
    # Set the refresh token in HttpOnly cookie securely
    cookie_max_age = 3600 * 24 * 7
    secure_param = getattr(settings, 'SESSION_COOKIE_SECURE', True)
    samesite_param = getattr(settings, 'SESSION_COOKIE_SAMESITE', 'None')
    res.set_cookie(
        key='refresh_token',
        value=refresh_token,
        max_age=cookie_max_age,
        httponly=True,
        secure=secure_param,
        samesite=samesite_param
    )
    return res


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def google_id_token(request):
    """
    Exposes the Google ID token (stored in token_secret by allauth for this setup)
    to the frontend so it can authenticate with the external Production/Manufacturing module.
    """
    try:
        # Note: DRF request object already has the authenticated user in request.user
        app = SocialApp.objects.get(provider='google')
        token = SocialToken.objects.get(account__user=request.user, account__provider='google', app=app)
        # In this specific allauth configuration, token_secret holds the id_token
        return Response({'id_token': token.token_secret})
    except SocialToken.DoesNotExist:
        return Response({'error': 'No Google token found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
