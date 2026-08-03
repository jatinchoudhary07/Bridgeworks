import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from core.models import PixelEvent

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class PixelTrackView(APIView):
    """
    POST /api/v1/pixel/track/
    
    Receives tracking data from the Shori storefront pixel.
    Expects JSON payload with session_id, cart_token, and UTMs.

    PATCH /api/v1/pixel/track/

    Links a cart_token to all PixelEvents for a session once a
    Shopify cart is created (after add-to-cart).
    """
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = request.data
            org_id = self._resolve_org_id(request, data)
            if not org_id:
                return Response({'error': 'Missing or unresolvable org_id'}, status=status.HTTP_400_BAD_REQUEST)

            # Create the event
            PixelEvent.objects.create(
                org_id=org_id,
                session_id=data.get('session_id', ''),
                cart_token=data.get('cart_token'),
                
                utm_source=data.get('utm_source', ''),
                utm_medium=data.get('utm_medium', ''),
                utm_campaign=data.get('utm_campaign', ''),
                utm_content=data.get('utm_content', ''),
                utm_term=data.get('utm_term', ''),
                
                fbclid=data.get('fbclid', ''),
                gclid=data.get('gclid', ''),
                ttclid=data.get('ttclid', ''),
                epik=data.get('epik', ''),
                sclid=data.get('sclid', ''),
                
                url=data.get('url', ''),
                referrer=data.get('referrer', ''),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_address=self._get_client_ip(request)
            )

            return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Pixel tracking error: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request):
        """
        PATCH /api/v1/pixel/track/

        Links a cart_token to all PixelEvents for a given session_id.
        Called by the Shori pixel JS the moment a Shopify cart token appears
        (i.e. after the user first adds a product to cart).

        This is the key that makes the cart_token fallback lookup in the
        order webhook reliable — without it, all PixelEvents have cart_token=NULL
        because they were created at page-load time before any cart existed.

        Request Body:
            {
                "org_id": "janki-jewels",
                "session_id": "sess_abc123",
                "cart_token": "shopify-cart-token-xyz"
            }
        """
        try:
            session_id = request.data.get('session_id')
            cart_token = request.data.get('cart_token')
            org_id = self._resolve_org_id(request, request.data)

            if not session_id or not cart_token:
                return Response(
                    {'error': 'Missing session_id or cart_token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not org_id:
                return Response(
                    {'error': 'Missing or unresolvable org_id'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            updated = PixelEvent.objects.filter(
                session_id=session_id,
                org_id=org_id,
                cart_token__isnull=True  # Only update rows that don't already have one
            ).update(cart_token=cart_token)

            logger.info(
                f"Pixel PATCH: linked cart_token to {updated} events "
                f"for session={session_id[:20]}... org={org_id}"
            )
            return Response({'status': 'ok', 'updated': updated})

        except Exception as e:
            logger.error(f"Pixel PATCH error: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _resolve_org_id(self, request, data):
        org_id = data.get('org_id')
        if org_id:
            return org_id

        # Try to resolve org_id from domains present in request
        domains_to_try = []
        
        # 1. URL being tracked
        tracking_url = data.get('url')
        if tracking_url:
            domains_to_try.append(tracking_url)
            
        # 2. Referrer being tracked
        referrer = data.get('referrer')
        if referrer:
            domains_to_try.append(referrer)
            
        # 3. HTTP headers (Origin / Referer)
        origin = request.META.get('HTTP_ORIGIN')
        if origin:
            domains_to_try.append(origin)
            
        referer_header = request.META.get('HTTP_REFERER')
        if referer_header:
            domains_to_try.append(referer_header)

        # Parse hostnames from URLs
        from urllib.parse import urlparse
        hostnames = []
        for url_str in domains_to_try:
            if not url_str:
                continue
            try:
                # Add scheme if missing to make urlparse work correctly
                if not url_str.startswith(('http://', 'https://')):
                    parsed = urlparse('https://' + url_str)
                else:
                    parsed = urlparse(url_str)
                if parsed.netloc:
                    hostnames.append(parsed.netloc.lower())
            except Exception:
                pass

        # Clean hostnames (remove port, handle www)
        cleaned_domains = []
        for hostname in hostnames:
            hostname = hostname.split(':')[0]  # Remove port
            cleaned_domains.append(hostname)
            if hostname.startswith('www.'):
                cleaned_domains.append(hostname[4:])
            else:
                cleaned_domains.append('www.' + hostname)

        # Unique cleaned domains
        cleaned_domains = list(set(filter(None, cleaned_domains)))
        if not cleaned_domains:
            return None

        # Look up in ShopCredentials
        from core.models.store import ShopCredentials
        from django.db.models import Q
        
        for domain in cleaned_domains:
            # Look for domain match in myshopify_domain or store_url
            shop = ShopCredentials.objects.filter(
                Q(myshopify_domain__icontains=domain) | 
                Q(store_url__icontains=domain)
            ).first()
            if shop:
                return shop.organization_id

        return None

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
