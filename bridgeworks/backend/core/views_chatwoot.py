import os
import logging
import json
import os
import requests
import threading
from django.conf import settings
from django.db import close_old_connections
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.models import Order, Customer, ShopCredentials
from core.services.chatwoot_service import ChatwootService

logger = logging.getLogger(__name__)

def _get_chatwoot_user_token():
    from django.core.cache import cache
    cache_key = "chatwoot_platform_user_1_token"
    token = cache.get(cache_key)
    if token:
        return token
    try:
        cw_service = ChatwootService()
        if not cw_service.platform_key:
            return None
        token_url = f"{cw_service.api_url}/platform/api/v1/users/1/token"
        token_resp = requests.post(token_url, headers=cw_service._get_headers(), timeout=10)
        if token_resp.status_code in (200, 201):
            token = token_resp.json().get("access_token")
            cache.set(cache_key, token, timeout=86400) # Cache for 1 day
            return token
    except Exception as e:
        logger.error(f"Error fetching Chatwoot user token: {e}")
    return None

# --- HELPERS ---
def _get_org_id(request):
    """Return the organization_id for the logged-in user, or None."""
    user = request.user
    if not user.is_authenticated:
        return None
    if hasattr(user, 'shop_credentials'):
        return user.shop_credentials.organization_id
    try:
        return user.team_settings.organization.organization_id
    except Exception:
        return None


class ChatwootSSORedirectView(APIView):
    """
    POST /api/chatwoot/sso-login/
    Generates a secure Single Sign-On (SSO) redirect URL for the logged-in BridgeWorks merchant.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "No organization found for your user profile."}, status=400)

        # Get organization name from credentials if available
        org_name = org_id
        try:
            shop = ShopCredentials.objects.filter(organization_id=org_id).first()
            if shop:
                if shop.store_name:
                    org_name = shop.store_name
                elif shop.myshopify_domain:
                    org_name = shop.myshopify_domain.split('.')[0].replace('-', ' ').title()
        except Exception:
            pass

        full_name = f"{user.first_name} {user.last_name}".strip() or user.username

        # Call service to provision and get SSO URL
        service = ChatwootService()
        sso_url = service.generate_sso_url(
            user_email=user.email,
            user_name=full_name,
            org_name=org_name,
            org_id=org_id
        )

        return Response({"url": sso_url})


@method_decorator(xframe_options_exempt, name='dispatch')
class ChatwootSidebarWidgetView(APIView):
    """
    GET /api/chatwoot/sidebar-context/
    Provides customer storefront context (Orders, Fulfillment, Returns, RTO risk)
    dynamically inside the Chatwoot agent dashboard.
    
    Supports:
    - HTML shell (renders client-side postMessage listener to handle Chatwoot context dynamically)
    - JSON payload (queried by the client-side shell or API-driven clients)
    
    Note: @xframe_options_exempt allows this view to be embedded in Chatwoot's iframe.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        output_format = request.query_params.get('format', 'html').strip().lower()
        org_id = request.query_params.get('org_id', '').strip()
        agent_email = request.query_params.get('agent_email', '').strip()

        # --- JSON Response Mode (Searches matching orders dynamically) ---
        if output_format == 'json':
            email = request.query_params.get('email', '').strip()
            phone = request.query_params.get('phone', '').strip()

            if not email and not phone:
                return JsonResponse({"error": "Missing customer email or phone parameter."}, status=400)

            # Dynamically resolve org_id from the logged-in agent email if not provided in URL
            if not org_id and agent_email:
                try:
                    from core.models import ShopCredentials
                    shop = ShopCredentials.objects.filter(owner__email__iexact=agent_email).first()
                    if shop:
                        org_id = shop.organization_id
                except Exception:
                    pass

            # Find matching orders in BridgeWorks
            orders_qs = Order.objects.all()
            if org_id:
                orders_qs = orders_qs.filter(org_id=org_id)
            else:
                # Secure by default: do not leak cross-tenant data if org cannot be mapped
                orders_qs = orders_qs.none()

            orders = []
            if email or phone:
                from django.db.models import Q
                combined_query = Q()
                if email:
                    combined_query |= Q(contact_email__iexact=email)
                if phone:
                    # Strip standard formatting like spacing or country codes for matching
                    cleaned_phone = ''.join(filter(str.isdigit, phone))
                    if len(cleaned_phone) >= 10:
                        combined_query |= Q(contact_phone__contains=cleaned_phone[-10:])
                    else:
                        combined_query |= Q(contact_phone__icontains=phone)
                
                orders = orders_qs.filter(combined_query).select_related('customer').prefetch_related('line_items', 'fulfillments').order_by('-created_at')[:5]

            # Extract details for payload
            orders_list = []
            for o in orders:
                items = [{"title": li.title, "sku": li.sku or 'N/A', "qty": li.quantity, "price": str(li.price)} for li in o.line_items.all()]
                
                # Fetch tracking details uniquely
                tracking_list = []
                seen_numbers = set()
                for f in o.fulfillments.all():
                    for t in f.tracking_info.all():
                        if t.number and t.number not in seen_numbers:
                            seen_numbers.add(t.number)
                            tracking_list.append({
                                "company": t.company or 'Courier',
                                "number": t.number or '',
                                "url": t.url or '#'
                            })
                
                orders_list.append({
                    "id": o.id,
                    "order_number": o.order_number or o.shopify_id,
                    "shopify_id": o.shopify_id,
                    "created_at": o.created_at.strftime('%d %b %Y, %H:%M') if o.created_at else 'N/A',
                    "status": o.status or 'Pending',
                    "fulfillment_status": o.fulfillment_status or 'Unfulfilled',
                    "financial_status": o.financial_status or 'Unpaid',
                    "total_price": str(o.total_price or '0.00'),
                    "currency": o.currency or 'INR',
                    "risk_score": o.risk_score,
                    "intelligence_flag": o.intelligence_flag or 'NONE',
                    "system_suggestion": o.system_suggestion or '',
                    "current_status": o.current_status or '',
                    "current_status_details": o.current_status_details or '',
                    "is_ndr": o.is_ndr,
                    "items": items,
                    "tracking": tracking_list,
                    "shipping_pincode": o.shipping_pincode or 'N/A'
                })

            return JsonResponse({
                "customer": {
                    "email": email,
                    "phone": phone,
                    "org_id": org_id
                },
                "orders": orders_list
            })

        # --- HTML Dynamic Widget Response Mode (Premium visual layout) ---
        return self._render_iframe_shell(org_id)

    def _render_iframe_shell(self, org_id):
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Shori Storefront Context</title>
    <!-- Modern Premium Font -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            darkMode: 'class',
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['Outfit', 'sans-serif'],
                    }},
                    colors: {{
                        brandBlue: '#1f93ff',
                        brandPurple: '#3b82f6',
                    }}
                }}
            }}
        }}
    </script>
    <style>
        * {{
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}
        body {{
            background-color: #ffffff;
            color: #0f172a;
            background-attachment: fixed;
            transition: background-color 0.2s, color 0.2s;
        }}
        body.dark {{
            background-color: #0b0f17;
            color: #f1f5f9;
        }}
        .glass-card {{
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: all 0.2s;
        }}
        body.dark .glass-card {{
            background-color: #111827;
            border: 1px solid #334155;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.2);
        }}
    </style>
</head>
<body class="p-4 select-none">

    <!-- Header -->
    <div class="flex items-center justify-between border-b-2 border-slate-200 dark:border-slate-800 pb-3.5 mb-5">
        <div class="flex items-center gap-3">
            <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-sky-400 flex items-center justify-center shadow-[0_0_15px_rgba(31,147,255,0.4)]">
                <span class="text-white font-extrabold text-base">S</span>
            </div>
            <div>
                <h1 class="text-slate-900 dark:text-white text-base font-black tracking-tight leading-tight">
                    SHORI CONTEXT
                </h1>
                <p class="text-[10px] text-slate-500 dark:text-slate-400 font-extrabold tracking-widest uppercase">Live CRM Insights</p>
            </div>
        </div>
        <span class="text-[10px] font-black bg-blue-50 text-blue-700 border border-blue-200 dark:bg-blue-950/50 dark:text-blue-400 dark:border-blue-900/60 px-3 py-1 rounded-full uppercase tracking-wider">
            Connected
        </span>
    </div>

    <!-- Main Container -->
    <div id="loader" class="flex flex-col items-center justify-center py-24 gap-4">
        <div class="relative w-12 h-12">
            <div class="absolute inset-0 rounded-full border-4 border-blue-500/20"></div>
            <div class="absolute inset-0 rounded-full border-4 border-blue-500 border-t-transparent animate-spin"></div>
        </div>
        <p class="text-sm text-slate-600 dark:text-slate-300 font-bold">Retrieving storefront context...</p>
    </div>

    <div id="content" class="hidden space-y-4">
        <!-- Rendered order cards go here -->
    </div>

    <script>
        console.log("[Shori Iframe] Loaded. Origin:", window.location.origin);
        
        // Default to system preference on load
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {{
            document.documentElement.classList.add('dark');
            document.body.classList.add('dark');
        }} else {{
            document.documentElement.classList.remove('dark');
            document.body.classList.remove('dark');
        }}

        let receivedContext = false;
        const orgId = "{org_id}";

        // Helper to dynamic class color statuses
        function getStatusBadgeClass(status) {{
            const s = (status || '').toLowerCase().trim();
            if (['fulfilled', 'delivered', 'completed', 'paid', 'green'].some(v => s.includes(v))) {{
                return 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-400 dark:border-emerald-900/30';
            }}
            if (['cancelled', 'refunded', 'failed', 'rto', 'red', 'failed_to_deliver', 'undelivered'].some(v => s.includes(v))) {{
                return 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/30 dark:text-rose-400 dark:border-rose-900/30';
            }}
            if (['pending', 'processing', 'unfulfilled', 'unpaid', 'yellow', 'hold', 'partially'].some(v => s.includes(v))) {{
                return 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/30 dark:text-amber-400 dark:border-amber-900/30';
            }}
            return 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/30 dark:text-blue-400 dark:border-blue-900/30';
        }}

        // Setup message listener to capture Chatwoot contact details
        window.addEventListener('message', function(event) {{
            let data;
            try {{ data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data; }} catch(e) {{ data = event.data; }}
            
            if (data && data.theme) {{
                if (data.theme === 'dark') {{
                    document.documentElement.classList.add('dark');
                    document.body.classList.add('dark');
                }} else {{
                    document.documentElement.classList.remove('dark');
                    document.body.classList.remove('dark');
                }}
            }}
            
            if (data && data.event === 'appContext') {{
                receivedContext = true;
                if (data.data && data.data.theme) {{
                    if (data.data.theme === 'dark') {{
                        document.documentElement.classList.add('dark');
                        document.body.classList.add('dark');
                    }} else {{
                        document.documentElement.classList.remove('dark');
                        document.body.classList.remove('dark');
                    }}
                }}
                const contact = data.data.contact || {{}};
                const agent = data.data.currentAgent || {{}};
                const agentEmail = agent.email || "";
                fetchData(contact.email || "", contact.phone_number || "", agentEmail);
            }}
        }});

        window.parent.postMessage('chatwoot-dashboard-app:fetch-info', '*');

        setTimeout(function() {{
            if (!receivedContext) {{
                const urlParams = new URLSearchParams(window.location.search);
                fetchData(urlParams.get('email') || '', urlParams.get('phone') || '', '');
            }}
        }}, 1500);

        function fetchData(email, phone, agentEmail) {{
            if (!email && !phone) {{ renderEmptyState("No contact details found."); return; }}
            const url = "/api/chatwoot/sidebar-context/?format=json&email=" + encodeURIComponent(email) + "&phone=" + encodeURIComponent(phone) + "&org_id=" + encodeURIComponent(orgId) + "&agent_email=" + encodeURIComponent(agentEmail || "");
            fetch(url).then(res => res.json()).then(data => renderData(data)).catch(err => renderError(err.message));
        }}

        function renderData(data) {{
            document.getElementById('loader').style.display = 'none';
            const contentEl = document.getElementById('content');
            contentEl.classList.remove('hidden');
            contentEl.innerHTML = (data.orders || []).length === 0 ? renderEmptyState("No order records found.") : (data.orders || []).map(o => renderOrderCard(o)).join('');
        }}

        function renderEmptyState(msg) {{
            document.getElementById('loader').style.display = 'none';
            const contentEl = document.getElementById('content');
            contentEl.classList.remove('hidden');
            contentEl.innerHTML = `
                <div class="flex flex-col items-center justify-center p-8 text-center glass-card rounded-3xl mx-auto my-6 border-2 border-dashed border-slate-300 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-900/20">
                    <div class="text-4xl mb-4">🔍</div>
                    <h3 class="text-slate-900 dark:text-white text-base font-extrabold mb-2">No Customer Profile</h3>
                    <p class="text-slate-600 dark:text-slate-300 text-sm font-semibold">${{msg}}</p>
                </div>
            `;
        }}

        function renderError(msg) {{ renderEmptyState("Failed to retrieve profile. " + msg); }}

        function renderOrderCard(o) {{
            let riskBadgeColor = 'text-slate-600 bg-slate-50 border-slate-300 dark:text-slate-400 dark:bg-gray-900/50 dark:border-slate-800';
            let riskLabel = 'Not Analyzed';
            
            if (o.intelligence_flag === 'RED') {{
                riskBadgeColor = 'text-red-700 bg-red-50 border-red-300 dark:text-red-400 dark:bg-red-950/20 dark:border-red-500/20';
                riskLabel = 'High Risk';
            }} else if (o.intelligence_flag === 'YELLOW') {{
                riskBadgeColor = 'text-amber-700 bg-amber-50 border-amber-300 dark:text-amber-400 dark:bg-amber-950/20 dark:border-amber-500/20';
                riskLabel = 'Medium Risk';
            }} else if (o.intelligence_flag === 'GREEN') {{
                riskBadgeColor = 'text-emerald-700 bg-emerald-50 border-emerald-300 dark:text-emerald-400 dark:bg-emerald-950/20 dark:border-emerald-500/20';
                riskLabel = 'Low Risk';
            }}

            const itemsHtml = o.items.map(item => `
                <div class="flex justify-between items-center py-2 border-b border-slate-100 dark:border-slate-800/60 last:border-b-0 text-sm">
                    <div class="text-slate-900 dark:text-slate-100 font-extrabold truncate">${{item.title}}</div>
                    <div class="text-xs font-black bg-slate-100 dark:bg-slate-800/80 px-2 py-0.5 rounded-full">qty: ${{item.qty}}</div>
                </div>
            `).join('');

            const trackingHtml = o.tracking && o.tracking.length > 0 ? o.tracking.map(t => `
                <a href="${{t.url}}" target="_blank" class="flex items-center justify-center gap-2 w-full bg-white hover:bg-slate-50 dark:bg-[#111827] border-2 border-slate-350 dark:border-slate-700 rounded-xl py-2.5 px-4 text-xs font-black mt-2.5 shadow-sm">
                    <span>📦 Track: ${{t.company}}</span>
                    <span class="text-slate-600 dark:text-slate-300 font-mono">(${{t.number}})</span>
                </a>
            `).join('') : '<div class="text-slate-600 dark:text-slate-400 text-xs italic p-3.5 rounded-xl border-2 border-dashed border-slate-200 text-center">No tracking info.</div>';

            return `
                <div class="glass-card hover:border-blue-500/50 rounded-3xl p-5 mb-5 shadow-lg">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <span class="text-slate-900 dark:text-white text-base font-extrabold">Order #${{o.order_number}}</span>
                            <div class="text-slate-500 dark:text-slate-400 text-xs font-bold mt-1">${{o.created_at}}</div>
                        </div>
                        <div class="text-blue-700 dark:text-sky-400 text-base font-black">${{o.currency}} ${{o.total_price}}</div>
                    </div>
                    <div class="grid grid-cols-2 gap-4 mb-4">
                        <div>
                            <span class="block text-[11px] text-slate-500 uppercase font-black mb-1">Status</span>
                            <span class="inline-block text-xs font-extrabold px-2.5 py-1 rounded-md border ${{getStatusBadgeClass(o.status)}}">${{o.status}}</span>
                        </div>
                        <div>
                            <span class="block text-[11px] text-slate-500 uppercase font-black mb-1">Fulfillment</span>
                            <span class="inline-block text-xs font-extrabold px-2.5 py-1 rounded-md border ${{getStatusBadgeClass(o.fulfillment_status)}}">${{o.fulfillment_status}}</span>
                        </div>
                    </div>
                    <div class="mb-4">
                        <span class="block text-[11px] text-slate-500 uppercase font-black mb-2.5">Items Ordered</span>
                        <div class="border border-slate-200 dark:border-slate-800 rounded-2xl p-3.5 bg-slate-50/50 dark:bg-slate-900/20">${{itemsHtml}}</div>
                    </div>
                    <div class="mb-4">
                        <div class="flex justify-between items-center mb-2.5">
                            <span class="text-[11px] text-slate-500 uppercase font-black">AI Risk Analyzer</span>
                            <span class="text-[10px] font-black px-2.5 py-0.5 rounded border ${{riskBadgeColor}}">${{riskLabel}} (${{o.risk_score}}%)</span>
                        </div>
                        <div class="text-xs font-bold p-3.5 rounded-2xl bg-slate-50 dark:bg-slate-800/40 border dark:border-slate-800">${{o.system_suggestion || 'No risks detected.'}}</div>
                    </div>
                    <div>
                        <span class="block text-[11px] text-slate-500 uppercase font-black mb-2.5">Fulfillment Tracking</span>
                        ${{trackingHtml}}
                    </div>
                </div>
            `;
        }}
    </script>
</body>
</html>"""
        return HttpResponse(html_content)


def update_conversation_workflow_labels(conversation_id, account_id, user_token, message_type, sender_id, sender_type, current_labels, assignee, messages=None, push_to_chatwoot=True):
    """
    Programmatically calculates and synchronizes workflow labels for a conversation:
    - 'needs first reply': if no human agent has ever replied.
    - 'needs reply': if the last message was from customer (incoming).
    - 'awaiting': if the conversation is waiting for human response.
    - 'investigating': if a human has replied in the past and a new customer message came in.
    - 'human-agent': if assigned to a human agent.
    """
    cw_service = ChatwootService()
    message_headers = {
        "api_access_token": user_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Fetch conversation messages to analyze history if not provided
    human_reply_count = 0
    if messages is None:
        try:
            history_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
            hist_resp = requests.get(history_url, headers=message_headers, timeout=10)
            if hist_resp.status_code == 200:
                messages = hist_resp.json().get("payload", [])
        except Exception as e:
            logger.error(f"Failed to fetch conversation history for label analysis: {e}")

    if messages:
        for msg in messages:
            # Count outgoing public messages sent by human users (sender_type == 'user' and sender_id != 1)
            m_sender = msg.get("sender") or {}
            if (msg.get("message_type") == 1 and 
                not msg.get("private") and 
                m_sender.get("type") == "user" and 
                m_sender.get("id") != 1):
                human_reply_count += 1

    # Start with existing labels
    labels = list(current_labels or [])

    # Define our workflow labels set to manage them cleanly
    workflow_labels = {"needs-first-reply", "needs-reply", "awaiting", "investigating", "human-agent"}
    
    # Filter out current workflow labels so we can recalculate them cleanly
    labels = [l for l in labels if l not in workflow_labels]

    is_assigned_to_human = (assignee is not None and assignee.get("id") != 1)

    if message_type == "incoming":
        # Customer sent a message -> needs reply!
        labels.append("needs-reply")
        
        if human_reply_count == 0:
            labels.append("needs-first-reply")
            labels.append("awaiting")
        else:
            if is_assigned_to_human:
                labels.append("investigating")
                labels.append("human-agent")
            else:
                labels.append("awaiting")

    elif message_type == "outgoing":
        # Outgoing message
        if sender_type == "user" and sender_id != 1:
            # Human agent replied!
            # Clear needs-reply, needs-first-reply, and awaiting
            if is_assigned_to_human:
                labels.append("human-agent")
                labels.append("investigating")
        else:
            # Bot replied
            if human_reply_count == 0:
                labels.append("needs-first-reply")
                labels.append("awaiting")
            else:
                if is_assigned_to_human:
                    labels.append("human-agent")

    # Always ensure 'human-agent' is present if assigned to human
    if is_assigned_to_human and "human-agent" not in labels:
        labels.append("human-agent")

    # Remove duplicates
    final_labels = list(set(labels))

    # Send to Chatwoot if changed and push_to_chatwoot is True
    if push_to_chatwoot and set(final_labels) != set(current_labels or []):
        try:
            labels_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/labels"
            requests.post(labels_url, json={"labels": final_labels}, headers=message_headers, timeout=10)
            logger.info(f"Successfully synchronized workflow labels for convo #{conversation_id} to: {final_labels}")
        except Exception as le:
            logger.error(f"Failed to update workflow labels: {le}")
            
    return final_labels


class ChatwootWebhookView(APIView):
    """
    POST /api/chatwoot/webhook/
    Listens to Chatwoot events (specifically message_created).
    Fetches the storefront's active AIAgent and applies Sandbox checks:
    - Draft: completely ignored.
    - Sandbox-Testing: only responds to whitelisted phone numbers.
    - Live: responds to all customer messages.
    
    Supports Auto vs. Manual routing (public chat response vs. private comment).
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            payload = request.data
            event = payload.get("event")
            
            if event != "message_created":
                return Response({"status": "ignored", "reason": f"Unhandled event: {event}"})
                
            message_type = payload.get("message_type")
            if message_type not in ("incoming", "outgoing"):
                return Response({"status": "ignored", "reason": f"Unhandled message_type: {message_type}"})

            conversation = payload.get("conversation", {})
            conversation_id = conversation.get("id")
            account = payload.get("account", {})
            account_id = account.get("id")
            
            if not conversation_id or not account_id:
                return Response({"error": "Missing conversation_id or account_id in webhook payload"}, status=400)

            import threading
            thread = threading.Thread(target=self._process_payload_async, args=(payload,))
            thread.start()
            
            return Response({"status": "processing"})
            
        except Exception as e:
            logger.exception("Error in ChatwootWebhookView")
            return Response({"error": str(e)}, status=500)

    def _process_payload_async(self, payload):
        try:
            event = payload.get("event")
            message_type = payload.get("message_type")
            conversation = payload.get("conversation", {})
            conversation_id = conversation.get("id")
            account = payload.get("account", {})
            account_id = account.get("id")
            
            # --- Staleness Guard ---
            import time
            created_at = payload.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str) and not created_at.isdigit():
                        from dateutil.parser import parse
                        msg_time = parse(created_at).timestamp()
                    else:
                        msg_time = float(created_at)
                    
                    if time.time() - msg_time > 180: # 3 minutes
                        logger.warning(f"Ignored stale webhook message (ID {payload.get('id')}) from {msg_time}. (Likely retried after tunnel downtime)")
                        return
                except Exception as e:
                    logger.error(f"Error parsing created_at for staleness check: {e}")

            # Get sender info
            sender = payload.get("sender", {})
            sender_type = sender.get("type")
            sender_id = sender.get("id")
            assignee = conversation.get("meta", {}).get("assignee") or conversation.get("assignee")

            # --- Outgoing (Agent Reply) Flow ---
            if message_type == "outgoing":
                if sender_type == "user" and sender_id != 1:
                    logger.info(f"Human agent #{sender_id} replied in conversation #{conversation_id}. Assigning to agent and syncing workflow labels...")
                    user_token = _get_chatwoot_user_token()
                    if user_token:
                        cw_service = ChatwootService()
                        # 1. Explicitly assign the conversation to the responding human agent
                        assign_headers = {
                            "api_access_token": user_token,
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                        }
                        try:
                            assign_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/assignments"
                            requests.post(assign_url, json={"assignee_id": sender_id}, headers=assign_headers, timeout=10)
                            logger.info(f"Successfully assigned conversation #{conversation_id} to human agent #{sender_id}")
                        except Exception as ae:
                            logger.error(f"Failed to assign conversation to human agent #{sender_id}: {ae}")

                        # 2. Sync workflow labels with assignee overridden to human agent
                        update_conversation_workflow_labels(
                            conversation_id=conversation_id,
                            account_id=account_id,
                            user_token=user_token,
                            message_type="outgoing",
                            sender_id=sender_id,
                            sender_type=sender_type,
                            current_labels=conversation.get("labels") or [],
                            assignee={"id": sender_id}
                        )
                    return
                return

            # --- Incoming Customer Flow ---
            if sender_type == "user":
                return

            # --- Human Takeover Guard ---
            is_assigned_to_human = (assignee is not None and assignee.get("id") != 1)
            current_labels_lower = [l.lower() for l in (conversation.get("labels") or [])]
            is_human_handling = any(l in current_labels_lower for l in ["human-agent", "escalated", "human-needed", "needs-reply"])
            
            if is_assigned_to_human and is_human_handling:
                logger.info(f"Takeover Guard: Conversation #{conversation_id} is assigned to human agent {assignee.get('name')} (ID: {assignee.get('id')}). Skipping AI response...")
                user_token = _get_chatwoot_user_token()
                if user_token:
                    cw_service = ChatwootService()
                    update_conversation_workflow_labels(
                        conversation_id=conversation_id,
                        account_id=account_id,
                        user_token=user_token,
                        message_type="incoming",
                        sender_id=sender_id,
                        sender_type=sender_type,
                        current_labels=conversation.get("labels") or [],
                        assignee=assignee
                    )
                return

            content = (payload.get("content") or "").strip()
            inbox_id = conversation.get("inbox_id")

            attachments = payload.get("attachments") or []
            has_attachments = len(attachments) > 0

            email = (sender.get("email") or "").strip()
            phone = (sender.get("phone_number") or "").strip()
            customer_name = (sender.get("name") or "Customer").strip()

            if not email and not phone:
                # Fallback to check contact inbox
                contact = conversation.get("contact_inbox", {}).get("contact", {})
                email = (contact.get("email") or "").strip()
                phone = (contact.get("phone_number") or "").strip()
                customer_name = (contact.get("name") or "Customer").strip()

            # --- 1. AIAgent Scoping & Loading ---
            from core.models import AIAgent
            agent = AIAgent.objects.filter(chatwoot_inbox_id=inbox_id).first()
            if not agent:
                agent = AIAgent.objects.first()
                
            if not agent:
                logger.warning(f"No AIAgent configured for Chatwoot Inbox ID: {inbox_id}. Auto-reply ignored.")
                return

            # --- 2. Sandbox Whitelist Checks ---
            if agent.status == 'draft':
                logger.info(f"Agent {agent.name} is in Draft mode. Short-circuiting response.")
                return

            if agent.status == 'sandbox':
                whitelisted_numbers = agent.get_sandbox_numbers_list()
                
                def clean_phone(num):
                    return ''.join(filter(str.isdigit, str(num))) if num else ""
                
                cleaned_cust = clean_phone(phone)
                is_whitelisted = False
                
                if cleaned_cust:
                    for item in whitelisted_numbers:
                        cleaned_item = clean_phone(item)
                        if cleaned_item and (cleaned_cust.endswith(cleaned_item) or cleaned_item.endswith(cleaned_cust)):
                            is_whitelisted = True
                            break
                            
                if not is_whitelisted:
                    logger.warning(
                        f"Unwhitelisted number ({phone}) messaged in Sandbox mode for storefront: {agent.organization_id}. "
                        f"Auto-response suppressed."
                    )
                    return

            logger.info(f"Received customer message in conversation #{conversation_id} from {customer_name} ({phone} / {email}): {content}")

            user_token = _get_chatwoot_user_token()
            if not user_token:
                logger.error("Failed to fetch platform token.")
                return

            cw_service = ChatwootService()

            # --- 3. Parallel Pre-LLM Data Gathering ---
            # Fetch history and catalog search in parallel threads to save round-trip time.
            def fetch_history_task():
                try:
                    history_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
                    history_headers = {
                        "api_access_token": user_token,
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                    hist_resp = requests.get(history_url, headers=history_headers, timeout=10)
                    if hist_resp.status_code == 200:
                        return hist_resp.json().get("payload", [])
                except Exception as he:
                    logger.error(f"Failed to fetch Chatwoot conversation history: {he}")
                return []

            def search_catalog_task():
                min_price = 0.0
                max_price = 99999.0
                
                price_numbers = [float(n) for n in re.findall(r"\b\d{3,5}\b", content or "")]
                if len(price_numbers) >= 2:
                    min_price = min(price_numbers[0], price_numbers[1])
                    max_price = max(price_numbers[0], price_numbers[1])
                elif len(price_numbers) == 1:
                    max_price = price_numbers[0]
                    
                keywords = []
                normalized_content = (content or "").lower()
                
                SEARCH_KEYWORDS = ["arushaa", "silver", "earring", "necklace", "ring", "hoop", "choker", "set", "jewel"]
                for kw in SEARCH_KEYWORDS:
                    if kw in normalized_content:
                        keywords.append(kw)
                        
                from inventory.models import ShopifyProductCache
                from django.db.models import Q
                
                product_query = Q(organization_id=agent.organization_id)
                if keywords:
                    keyword_queries = Q()
                    for kw in keywords:
                        keyword_queries |= Q(data__name__icontains=kw) | Q(data__tags__icontains=kw) | Q(data__handle__icontains=kw)
                    product_query &= keyword_queries
                    
                catalog_matches = []
                try:
                    # Limit the query to 30 records to save DB serialization time
                    products_qs = list(ShopifyProductCache.objects.filter(product_query)[:30])
                    if not products_qs and max_price < 99999.0:
                        products_qs = list(ShopifyProductCache.objects.filter(organization_id=agent.organization_id)[:30])
                        
                    for p in products_qs:
                        p_data = p.data
                        p_price = 0.0
                        try:
                            p_price = float(p_data.get("price") or 0.0)
                        except:
                            pass
                            
                        if min_price <= p_price <= max_price:
                            name = p_data.get("name")
                            handle = p_data.get("handle")
                            image = p_data.get("image") or ""
                            if image.startswith("//"):
                                image = "https:" + image
                                
                            if name and handle:
                                catalog_matches.append({
                                    "name": name,
                                    "price": p_price,
                                    "image_url": image,
                                    "product_url": f"https://thejanki.com/products/{handle}"
                                })
                    
                    import random
                    if len(catalog_matches) > 5:
                        catalog_matches = random.sample(catalog_matches, 5)
                except Exception as ce:
                    logger.error(f"Failed to query ShopifyProductCache for store catalog context: {ce}")
                return catalog_matches

            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as executor:
                history_future = executor.submit(fetch_history_task)
                catalog_future = executor.submit(search_catalog_task)
                
                messages = history_future.result()
                catalog_matches = catalog_future.result()

            # Compile conversation history & Layer 2 state
            conversation_history = ""
            if messages:
                recent_exchanges = []
                import datetime
                for msg in messages[-8:]:
                    if msg.get("private"):
                        continue
                    sender_lbl = "Customer" if msg.get("message_type") == 0 else "Agent"
                    msg_content = msg.get("content")
                    created_at = msg.get("created_at")
                    time_str = ""
                    if created_at:
                        try:
                            dt = datetime.datetime.fromtimestamp(created_at)
                            time_str = dt.strftime("[%b %d, %I:%M %p] ")
                        except Exception:
                            pass
                    if msg_content:
                        recent_exchanges.append(f"{time_str}{sender_lbl}: {msg_content}")
                conversation_history = "\n".join(recent_exchanges)

            # Build session state
            import time as _time
            now_ts = _time.time()
            session_state = {
                "session_age_minutes": 0,
                "is_new_session": True,
                "last_assistant_intent": None,
                "last_customer_entity": None,
                "lookup_completed": False,
                "orders_found": 0,
                "message_count": len([m for m in messages if not m.get("private")]),
            }

            last_agent_msg = None
            last_customer_ts = None
            prev_agent_ts = None
            for msg in messages:
                if msg.get("private"):
                    continue
                msg_ts = msg.get("created_at")
                msg_type = msg.get("message_type")
                msg_text = (msg.get("content") or "").lower()

                if msg_type == 0 and msg_ts:
                    last_customer_ts = msg_ts
                if msg_type == 1:
                    last_agent_msg = msg_text
                    if msg_ts:
                        prev_agent_ts = msg_ts

            if last_customer_ts:
                session_state["session_age_minutes"] = round((now_ts - last_customer_ts) / 60, 1)

            if prev_agent_ts:
                gap_hours = (now_ts - prev_agent_ts) / 3600
                session_state["is_new_session"] = gap_hours > 6
            else:
                session_state["is_new_session"] = True

            if last_agent_msg:
                if any(p in last_agent_msg for p in ["order number", "order id", "which order"]):
                    session_state["last_assistant_intent"] = "asked_for_order_number"
                elif any(p in last_agent_msg for p in ["registered", "phone", "mobile", "number", "email", "verify"]):
                    session_state["last_assistant_intent"] = "asked_for_identity_verification"
                elif any(p in last_agent_msg for p in ["photo", "image", "picture", "screenshot"]):
                    session_state["last_assistant_intent"] = "asked_for_photos"
                elif any(p in last_agent_msg for p in ["anything else", "help you with", "assist you"]):
                    session_state["last_assistant_intent"] = "offered_further_help"
                elif any(p in last_agent_msg for p in ["human", "specialist", "connecting you", "transfer"]):
                    session_state["last_assistant_intent"] = "initiated_handover"

            current_lower = (content or "").lower()
            import re
            if re.search(r"\b\d{10}\b", current_lower):
                session_state["last_customer_entity"] = "phone_number"
            elif re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", current_lower):
                session_state["last_customer_entity"] = "email"
            elif re.search(r"(?:order|#)\s*\d{4,7}", current_lower):
                session_state["last_customer_entity"] = "order_number"

            # In-memory workflow label calculation (push_to_chatwoot=False to save API calls)
            updated_labels = update_conversation_workflow_labels(
                conversation_id=conversation_id,
                account_id=account_id,
                user_token=user_token,
                message_type="incoming",
                sender_id=sender_id,
                sender_type=sender_type,
                current_labels=conversation.get("labels") or [],
                assignee=assignee,
                messages=messages,
                push_to_chatwoot=False
            )

            # --- Gather Mentioned Emails, Phones, and Order Numbers ---
            mentioned_order_nums = set()
            mentioned_phones = set()
            mentioned_emails = set()

            if phone:
                mentioned_phones.add(phone)
            if email:
                mentioned_emails.add(email.lower())

            if content:
                for num in re.findall(r"(?:janki|#)?(\b\d{4,7}\b)", content, re.IGNORECASE):
                    mentioned_order_nums.add(num)
                for ph in re.findall(r"\b\d{10}\b", content):
                    mentioned_phones.add(ph)
                for em in re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", content):
                    mentioned_emails.add(em.lower())

            for msg in messages[-8:]:
                msg_content = msg.get("content") or ""
                if msg_content:
                    for num in re.findall(r"(?:janki|#)?(\b\d{4,7}\b)", msg_content, re.IGNORECASE):
                        mentioned_order_nums.add(num)
                    for ph in re.findall(r"\b\d{10}\b", msg_content):
                        mentioned_phones.add(ph)
                    for em in re.findall(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", msg_content):
                        mentioned_emails.add(em.lower())

            # Single DB query for matching orders (eliminates redundant queries and duplicate context logic)
            orders = []
            if mentioned_order_nums or mentioned_phones or mentioned_emails:
                from django.db.models import Q
                order_query = Q(org_id=agent.organization_id)
                num_queries = Q()
                
                if mentioned_order_nums:
                    for num in mentioned_order_nums:
                        num_queries |= Q(order_number__icontains=num) | Q(shopify_id__icontains=num)
                
                if mentioned_phones:
                    for ph in mentioned_phones:
                        cleaned_ph = ''.join(filter(str.isdigit, ph))
                        if len(cleaned_ph) >= 10:
                            num_queries |= Q(contact_phone__contains=cleaned_ph[-10:])
                        else:
                            num_queries |= Q(contact_phone__icontains=ph)
                
                if mentioned_emails:
                    for em in mentioned_emails:
                        num_queries |= Q(contact_email__iexact=em)
                        
                order_query &= num_queries
                orders = list(Order.objects.filter(order_query).select_related('customer').prefetch_related('line_items', 'fulfillments').order_by('-created_at')[:5])

            orders_context = []
            for o in orders:
                items = [{"title": li.title, "sku": li.sku or 'N/A', "qty": li.quantity, "price": float(li.price)} for li in o.line_items.all()]
                tracking_list = []
                for f in o.fulfillments.all():
                    for t in f.tracking_info.all():
                        tracking_list.append({
                            "company": t.company or 'Courier',
                            "number": t.number or '',
                            "url": t.url or ''
                        })
                
                orders_context.append({
                    "order_number": o.order_number or o.shopify_id,
                    "created_at": o.created_at.strftime('%d %b %Y, %H:%M') if o.created_at else 'N/A',
                    "status": o.status or 'Pending',
                    "fulfillment_status": o.fulfillment_status or 'Unfulfilled',
                    "financial_status": o.financial_status or 'Unpaid',
                    "total_price": float(o.total_price or 0.0),
                    "currency": o.currency or 'INR',
                    "items": items,
                    "tracking": tracking_list
                })

            # --- Graceful Auto-Handover: No order data + order-related intent ---
            ORDER_INTENT_KEYWORDS = [
                'order', 'tracking', 'track', 'delivery', 'deliver', 'shipped', 'shipping',
                'dispatch', 'dispatched', 'courier', 'status', 'refund', 'return', 'cancel',
                'cancelled', 'exchange', 'replacement', 'where is my', 'when will',
                'not received', 'haven\'t received', 'didn\'t receive', 'wrong item',
                'missing', 'damaged', 'broken', 'lost', 'parcel', 'package',
                'AWB', 'waybill', 'consignment', 'ETA', 'estimated',
            ]
            content_lower = (content or "").lower()
            combined_text = f"{content_lower} {conversation_history.lower()}"

            has_order_intent = any(kw.lower() in combined_text for kw in ORDER_INTENT_KEYWORDS)
            no_orders_found = len(orders_context) == 0

            if has_order_intent and no_orders_found and agent.handover_enabled:
                logger.info(
                    f"Graceful auto-handover: Customer has order-related intent but 0 orders found in DB. "
                    f"Skipping LLM and triggering deterministic handover for conversation #{conversation_id}."
                )
                ai_reply = (
                    f"Hi {customer_name} 🙏 I wasn't able to locate any order details linked to your current "
                    f"contact information. Let me connect you with my manager who can look this up "
                    f"and assist you right away!"
                )
                is_handover = True

                # Post the polite message to Chatwoot immediately
                is_private = (agent.response_mode == 'manual')
                message_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
                message_payload = {
                    "content": ai_reply,
                    "message_type": "outgoing",
                    "private": is_private
                }
                message_headers = {
                    "api_access_token": user_token,
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
                post_resp = requests.post(message_url, json=message_payload, headers=message_headers, timeout=10)
                if post_resp.status_code not in (200, 201):
                    logger.error(f"Failed to post graceful handover message: {post_resp.status_code}, {post_resp.text}")

                # Post-reply bookkeeping tasks run now:
                # Set priority to high for unlinked order queries
                priority_val = "high"
                current_priority = conversation.get("priority")
                if priority_val != current_priority:
                    try:
                        priority_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_priority"
                        requests.post(priority_url, json={"priority": priority_val}, headers=message_headers, timeout=10)
                    except Exception as pe:
                        logger.error(f"Failed to toggle priority for graceful handover: {pe}")

                # Apply handover labels
                existing_labels = updated_labels if 'updated_labels' in locals() else conversation.get("labels") or []
                try:
                    h_labels = json.loads(agent.handover_labels)
                except Exception:
                    h_labels = ["human-needed", "ai-escalated"]
                combined_labels = list(set(existing_labels + h_labels + ["awaiting", "needs-reply"]))
                try:
                    labels_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/labels"
                    requests.post(labels_url, json={"labels": combined_labels}, headers=message_headers, timeout=10)
                except Exception as le:
                    logger.error(f"Failed to update labels for graceful handover: {le}")

                # Add internal audit note
                note_payload = {
                    "content": (
                        f"🔄 **Graceful Auto-Handover triggered.**\n"
                        f"Customer has order-related intent but 0 matching orders were found in the database "
                        f"for phone: {phone or 'N/A'}, email: {email or 'N/A'}.\n"
                        f"Conversation auto-escalated to a human agent."
                    ),
                    "message_type": "outgoing",
                    "private": True
                }
                requests.post(message_url, json=note_payload, headers=message_headers, timeout=10)

                # Round-robin assign agent & open status
                assignee_id = None
                if agent.handover_mode == 'specific_agent' and agent.handover_agent_id:
                    assignee_id = agent.handover_agent_id
                else:
                    agents_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/inboxes/{inbox_id}/assignable_agents"
                    try:
                        a_resp = requests.get(agents_url, headers=message_headers, timeout=10)
                        if a_resp.status_code == 200:
                            a_data = a_resp.json()
                            agents_list = a_data if isinstance(a_data, list) else a_data.get("payload", [])
                            human_agent_ids = [a.get("id") for a in agents_list if a.get("id") and a.get("id") != 1]
                            agent_ids = human_agent_ids if human_agent_ids else [a.get("id") for a in agents_list if a.get("id")]
                            if agent_ids:
                                next_id = agent_ids[0]
                                if agent.last_assigned_agent_id in agent_ids:
                                    last_idx = agent_ids.index(agent.last_assigned_agent_id)
                                    next_id = agent_ids[(last_idx + 1) % len(agent_ids)]
                                assignee_id = next_id
                                agent.last_assigned_agent_id = assignee_id
                                agent.save(update_fields=['last_assigned_agent_id'])
                    except Exception as ex:
                        logger.error(f"Error resolving round-robin assignee for graceful handover: {ex}")

                if assignee_id:
                    assign_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/assignments"
                    requests.post(assign_url, json={"assignee_id": assignee_id}, headers=message_headers, timeout=10)

                status_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_status"
                requests.post(status_url, json={"status": "open"}, headers=message_headers, timeout=10)

                return

            # --- 4. Invoke LLM Support Generation ---
            session_state["lookup_completed"] = True
            session_state["orders_found"] = len(orders_context)

            from core.services.ai_support_agent import generate_support_response
            ai_reply = generate_support_response(
                agent=agent,
                customer_name=customer_name,
                email=email,
                phone=phone,
                message_content=content,
                orders_context=orders_context,
                conversation_history=conversation_history,
                has_attachments=has_attachments,
                products_context=catalog_matches,
                session_state=session_state
            )

            if not ai_reply:
                return

            # --- 5. Parse and Strip Priority & Labels from AI response ---
            priority_val = None
            priority_match = re.search(r"\[PRIORITY:\s*(urgent|high|medium|low|none)\]", ai_reply, re.IGNORECASE)
            if priority_match:
                priority_val = priority_match.group(1).lower()
                if priority_val == "none":
                    priority_val = None
                ai_reply = re.sub(r"\[PRIORITY:\s*[^\]]+\]", "", ai_reply, flags=re.IGNORECASE).strip()
                
            ai_labels = []
            labels_match = re.search(r"\[LABELS:\s*([^\]]+)\]", ai_reply, re.IGNORECASE)
            if labels_match:
                ai_labels = [lbl.strip().lower() for lbl in labels_match.group(1).split(",") if lbl.strip()]
                ai_reply = re.sub(r"\[LABELS:\s*[^\]]+\]", "", ai_reply, flags=re.IGNORECASE).strip()

            ai_sources = []
            sources_match = re.search(r"\[SOURCES:\s*([^\]]+)\]", ai_reply, re.IGNORECASE)
            if sources_match:
                sources_str = sources_match.group(1).strip()
                if sources_str.lower() != "none":
                    ai_sources = [src.strip() for src in sources_str.split(",") if src.strip()]
                ai_reply = re.sub(r"\[SOURCES:\s*[^\]]+\]", "", ai_reply, flags=re.IGNORECASE).strip()

            # --- 6. Check for AI Handover Escalation ---
            handover_summary = ""
            summary_match = re.search(r"\[HANDOVER_SUMMARY:\s*(.*?)\]", ai_reply, re.DOTALL | re.IGNORECASE)
            if summary_match:
                handover_summary = summary_match.group(1).strip()
                ai_reply = re.sub(r"\[HANDOVER_SUMMARY:\s*.*?\]", "", ai_reply, flags=re.DOTALL | re.IGNORECASE).strip()

            is_handover = "[HANDOVER]" in ai_reply
            
            content_lower = (content or "").lower().strip()
            explicit_customer_handover = any(phrase in content_lower for phrase in ["transfer to", "speak to a human", "talk to a human", "human agent", "talk to human", "speak to human", "connect me to a human"])
            llm_handover_phrases = any(phrase in ai_reply.lower() for phrase in ["transfer you", "human agent", "human specialist", "connecting you", "support specialist"])
            
            if explicit_customer_handover or llm_handover_phrases:
                is_handover = True
                
            clean_reply = ai_reply.replace("[HANDOVER]", "").strip()
            
            if is_handover:
                if not clean_reply:
                    clean_reply = "Sure! Let me connect you with my manager right away to help you further with this. 🙏"
                ai_reply = clean_reply
                if not handover_summary:
                    handover_summary = f"Customer requested to speak with a manager. Latest inquiry: '{content}'."

            # --- 7. Post Back to Chatwoot (Auto vs. Manual Private Note) ---
            is_private = (agent.response_mode == 'manual')
            message_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
            message_headers = {
                "api_access_token": user_token,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            image_urls = re.findall(r"!\[.*?\]\((https?://[^\s)]+)\)", ai_reply)
            ai_reply = re.sub(r"!\[.*?\]\(https?://[^\s)]+\)", "", ai_reply).strip()
            
            posted_successfully = False
            if image_urls:
                import tempfile
                primary_img_url = image_urls[0]
                try:
                    img_resp = requests.get(primary_img_url, timeout=10)
                    if img_resp.status_code == 200:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                            tmp_file.write(img_resp.content)
                            tmp_file_path = tmp_file.name
                            
                        attachment_headers = {
                            "api_access_token": user_token
                        }
                        with open(tmp_file_path, "rb") as f:
                            files = {
                                "attachments[]": ("product.jpg", f, "image/jpeg")
                            }
                            data = {
                                "content": ai_reply,
                                "message_type": "outgoing",
                                "private": "true" if is_private else "false"
                            }
                            post_resp = requests.post(message_url, data=data, files=files, headers=attachment_headers, timeout=15)
                            if post_resp.status_code in (200, 201):
                                posted_successfully = True
                                logger.info(f"Successfully posted unified text and image attachment: {primary_img_url}")
                                
                        os.unlink(tmp_file_path)
                except Exception as ie:
                    logger.error(f"Failed to send unified text and image: {ie}")
                    
            if not posted_successfully:
                message_payload = {
                    "content": ai_reply,
                    "message_type": "outgoing",
                    "private": is_private
                }
                post_resp = requests.post(message_url, json=message_payload, headers=message_headers, timeout=10)
                if post_resp.status_code not in (200, 201):
                    logger.error(f"Failed to post to Chatwoot: {post_resp.status_code}, {post_resp.text}")
                    return
                logger.info("AI response successfully posted to Chatwoot!")

            # --- 8. POST-REPLY BOOKKEEPING WORK ---
            # All operations below this line are non-blocking to the customer's response delivery.
            
            # A. Force Assign to AI if not handing over
            if not is_handover:
                try:
                    assign_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/assignments"
                    requests.post(assign_url, json={"assignee_id": 1}, headers=message_headers, timeout=10)
                    logger.info("AI Agent successfully assigned itself to the conversation.")
                except Exception as ae:
                    logger.error(f"Failed to assign AI Agent: {ae}")

            # B. Apply Dynamic Priority via Chatwoot API
            current_priority = conversation.get("priority")
            should_update_priority = False
            if priority_val:
                if not current_priority:
                    should_update_priority = True
                elif priority_val in ("high", "urgent") and current_priority not in ("high", "urgent"):
                    should_update_priority = True

            if should_update_priority:
                try:
                    priority_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_priority"
                    requests.post(priority_url, json={"priority": priority_val}, headers=message_headers, timeout=10)
                    logger.info(f"AI successfully updated conversation priority from '{current_priority}' to '{priority_val}'")
                except Exception as pe:
                    logger.error(f"Failed to toggle conversation priority: {pe}")

            # C. Merge with existing labels & Shori Premium Rules
            existing_labels = updated_labels if 'updated_labels' in locals() else conversation.get("labels") or []
            combined_labels = list(set(existing_labels + ai_labels))
            
            if is_handover and agent.handover_enabled:
                try:
                    h_labels = json.loads(agent.handover_labels)
                except Exception:
                    h_labels = ["human-needed", "ai-escalated"]
                
                combined_labels = list(set(combined_labels + h_labels + ["escalated-to-agent", "needs-reply"]))
                for al in ["ai-handling", "awaiting"]:
                    if al in combined_labels:
                        combined_labels.remove(al)
            else:
                if "ai-handling" not in combined_labels:
                    combined_labels.append("ai-handling")
                for hl in ["human-agent", "escalated-to-agent", "human-needed", "ai-escalated", "needs-reply", "investigating"]:
                    if hl in combined_labels:
                        combined_labels.remove(hl)

            if combined_labels:
                try:
                    labels_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/labels"
                    requests.post(labels_url, json={"labels": combined_labels}, headers=message_headers, timeout=10)
                    logger.info(f"AI successfully updated conversation labels to: {combined_labels}")
                except Exception as le:
                    logger.error(f"Failed to update conversation labels: {le}")

            # D. Execute Human Handover Escalation Workflow
            if is_handover and agent.handover_enabled:
                logger.info(f"Triggering human handover escalation for conversation #{conversation_id}...")
                
                # Determine assignee ID
                assignee_id = None
                if agent.handover_mode == 'specific_agent' and agent.handover_agent_id:
                    assignee_id = agent.handover_agent_id
                    logger.info(f"Handing over to specific agent ID: {assignee_id}")
                else:
                    # Round Robin mode
                    agents_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/inboxes/{inbox_id}/assignable_agents"
                    try:
                        a_resp = requests.get(agents_url, headers=message_headers, timeout=10)
                        if a_resp.status_code == 200:
                            a_data = a_resp.json()
                            agents_list = a_data if isinstance(a_data, list) else a_data.get("payload", [])
                            human_agent_ids = [a.get("id") for a in agents_list if a.get("id") and a.get("id") != 1]
                            agent_ids = human_agent_ids if human_agent_ids else [a.get("id") for a in agents_list if a.get("id")]
                            
                            if agent_ids:
                                next_id = agent_ids[0]
                                if agent.last_assigned_agent_id in agent_ids:
                                    last_idx = agent_ids.index(agent.last_assigned_agent_id)
                                    next_id = agent_ids[(last_idx + 1) % len(agent_ids)]
                                
                                assignee_id = next_id
                                agent.last_assigned_agent_id = assignee_id
                                agent.save(update_fields=['last_assigned_agent_id'])
                                logger.info(f"Round-robin assignee calculated: {assignee_id}")
                    except Exception as ex:
                        logger.error(f"Error resolving round-robin assignee: {ex}")

                # Assign Agent
                if assignee_id:
                    assign_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/assignments"
                    requests.post(assign_url, json={"assignee_id": assignee_id}, headers=message_headers, timeout=10)

                # Toggle status to 'open'
                status_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_status"
                requests.post(status_url, json={"status": "open"}, headers=message_headers, timeout=10)

                # Add internal log note
                note_content = "🤖 **AI Handover Escalation Triggered**\n\n"
                if handover_summary:
                    note_content += f"**AI Summary:** {handover_summary}"
                else:
                    note_content += "Conversation reassigned to human support agent, marked as open, and escalation labels attached."

                note_payload = {
                    "content": note_content,
                    "message_type": "outgoing",
                    "private": True
                }
                requests.post(message_url, json=note_payload, headers=message_headers, timeout=10)

            return
            
        except Exception as e:
            logger.exception("Error in async Chatwoot Webhook processor")
        finally:
            from django.db import close_old_connections
            close_old_connections()

# =============================================================================
# CHATWOOT AGENT AUDIT & MANAGEMENT VIEWS
# =============================================================================

class ChatwootAgentSimulationView(APIView):
    """
    POST /api/chatwoot/audit/simulate/
    Dual-mode testing engine:
    - Customer Mode: simulates customer queries and feeds generated LLM bot replies back.
    - Manager Mode: runs meta-LLM system directives parsing and saves updated SOP guidelines.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        agent_id = request.data.get("agent_id")
        message = request.data.get("message", "").strip()
        role = request.data.get("role", "customer").strip().lower()

        if not message:
            return Response({"error": "Message content cannot be blank"}, status=400)

        # Scoping agent to merchant organization
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "No organization associated with this session"}, status=400)

        from core.models import AIAgent, AgentAuditLog
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if agent_id:
            agent = AIAgent.objects.filter(pk=agent_id, organization_id=org_id).first()
            
        if not agent:
            return Response({"error": "AI Agent not found for your storefront"}, status=404)

        from core.services.ai_support_agent import generate_support_response, update_agent_instruction_via_directive

        if role == "customer":
            # 1. Save Customer simulated text
            AgentAuditLog.objects.create(
                agent=agent,
                role='customer',
                message=message
            )
            
            # 2. Get standard active orders context
            orders_qs = Order.objects.filter(org_id=org_id).prefetch_related('line_items')[:1]
            orders_context = []
            for o in orders_qs:
                orders_context.append({
                    "order_number": o.order_number,
                    "created_at": o.created_at.strftime('%d %b %Y, %H:%M') if o.created_at else 'N/A',
                    "status": o.status or 'Pending',
                    "items": [{"title": li.title, "qty": li.quantity} for li in o.line_items.all()]
                })
                
            # 3. Generate bot response in simulation mode
            bot_reply = generate_support_response(
                agent=agent,
                customer_name="Simulated Customer",
                email="sandbox@bridgeworks.com",
                phone="6378081097",
                message_content=message,
                orders_context=orders_context,
                simulated=True
            )
            
            return Response({"status": "success", "reply": bot_reply})

        elif role == "manager":
            # Directively feed Manager instruction to Meta-LLM prompt-coordinator
            confirmation = update_agent_instruction_via_directive(agent, request.user, message)
            return Response({"status": "success", "reply": confirmation})

        else:
            return Response({"error": f"Invalid role: {role}"}, status=400)


class ChatwootAgentAuditLogsView(APIView):
    """
    GET /api/chatwoot/audit/logs/ - retrieves all audit simulation chat logs.
    DELETE /api/chatwoot/audit/logs/ - clears audit history for a fresh testing session.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        from core.models import AIAgent, AgentAuditLog
        
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if not agent:
            return Response({"logs": []})

        logs = AgentAuditLog.objects.filter(agent=agent).order_by('created_at')
        logs_list = [{
            "id": l.id,
            "role": l.role,
            "message": l.message,
            "created_at": l.created_at.strftime('%I:%M %p')
        } for l in logs]
        
        return Response({
            "logs": logs_list,
            "agent_instructions": agent.system_prompt
        })

    def delete(self, request):
        org_id = _get_org_id(request)
        from core.models import AIAgent, AgentAuditLog
        
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if agent:
            AgentAuditLog.objects.filter(agent=agent).delete()
            
        return Response({"status": "success", "message": "Simulation log cleared."})


class ChatwootAgentConfigView(APIView):
    """
    GET /api/chatwoot/agent/config/ - Retrieves store agent configurations and white-listed numbers.
    POST /api/chatwoot/agent/config/ - Updates store AI properties and clears pointer for context invalidation.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "No organization linked to user profile"}, status=400)

        from core.models import AIAgent
        agent, created = AIAgent.objects.get_or_create(
            organization_id=org_id,
            defaults={
                'name': 'Shori',
                'status': 'draft',
                'response_mode': 'auto',
                'system_prompt': "You are Shori, the warm, polite and exceptionally helpful AI Support Executive for Janki Jewels."
            }
        )

        nuggets_count = agent.knowledge_nuggets.filter(is_active=True).count()

        handover_labels_list = []
        try:
            handover_labels_list = json.loads(agent.handover_labels)
        except Exception:
            handover_labels_list = ["human-needed", "ai-escalated"]

        return Response({
            "id": agent.id,
            "name": agent.name,
            "avatar_url": agent.avatar_url,
            "status": agent.status,
            "response_mode": agent.response_mode,
            "chatwoot_inbox_id": agent.chatwoot_inbox_id,
            "sandbox_numbers": agent.get_sandbox_numbers_list(),
            "system_prompt": agent.system_prompt,
            "recurring_scraping": agent.recurring_scraping,
            "scraping_interval": agent.scraping_interval,
            "nuggets_count": nuggets_count,
            "last_scraped_at": agent.last_scraped_at.strftime('%d %b %Y, %H:%M') if agent.last_scraped_at else 'Never',
            "handover_enabled": agent.handover_enabled,
            "handover_mode": agent.handover_mode,
            "handover_agent_id": agent.handover_agent_id,
            "handover_labels": handover_labels_list
        })

    def post(self, request):
        org_id = _get_org_id(request)
        from core.models import AIAgent
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if not agent:
            return Response({"error": "No agent found for this merchant storefront"}, status=404)

        # Update fields dynamically with defensive sanitization
        status = request.data.get("status")
        if status in ['draft', 'sandbox', 'live']:
            agent.status = status

        response_mode = request.data.get("response_mode")
        if response_mode in ['auto', 'manual']:
            agent.response_mode = response_mode

        chatwoot_inbox_id = request.data.get("chatwoot_inbox_id")
        if chatwoot_inbox_id == "" or chatwoot_inbox_id is None:
            agent.chatwoot_inbox_id = None
        else:
            try:
                agent.chatwoot_inbox_id = int(chatwoot_inbox_id)
            except (ValueError, TypeError):
                pass

        recurring_scraping = request.data.get("recurring_scraping")
        if recurring_scraping is not None:
            agent.recurring_scraping = bool(recurring_scraping)

        scraping_interval = request.data.get("scraping_interval")
        if scraping_interval in ['weekly', 'monthly']:
            agent.scraping_interval = scraping_interval

        sandbox_list = request.data.get("sandbox_numbers")
        if isinstance(sandbox_list, list):
            agent.set_sandbox_numbers_list(sandbox_list)

        # Handover Config Fields
        handover_enabled = request.data.get("handover_enabled")
        if handover_enabled is not None:
            agent.handover_enabled = bool(handover_enabled)

        handover_mode = request.data.get("handover_mode")
        if handover_mode in ['round_robin', 'specific_agent']:
            agent.handover_mode = handover_mode

        handover_agent_id = request.data.get("handover_agent_id")
        if handover_agent_id == "" or handover_agent_id is None:
            agent.handover_agent_id = None
        else:
            try:
                agent.handover_agent_id = int(handover_agent_id)
            except (ValueError, TypeError):
                pass

        handover_labels_data = request.data.get("handover_labels")
        if isinstance(handover_labels_data, list):
            agent.handover_labels = json.dumps(handover_labels_data)

        prompt_input = request.data.get("system_prompt")
        if prompt_input is not None:
            # Guidelines modified - force context cache rebuild
            if prompt_input.strip() != agent.system_prompt.strip():
                agent.gemini_cache_id = None
            agent.system_prompt = prompt_input

        agent.save()
        return Response({"status": "success", "message": "Agent configurations updated successfully."})


class ChatwootInboxAgentsView(APIView):
    """
    GET /api/chatwoot/agent/assignable-agents/ - Retrieves assignable agents from Chatwoot for the agent's linked inbox.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "No organization linked to user profile"}, status=400)

        from core.models import AIAgent
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if not agent:
            return Response({"error": "No AIAgent configured for this storefront"}, status=404)

        if not agent.chatwoot_inbox_id:
            return Response({"agents": []})  # No inbox linked yet

        try:
            cw_service = ChatwootService()
            # Fetch Platform access token
            token_url = f"{cw_service.api_url}/platform/api/v1/users/1/token"
            token_resp = requests.post(token_url, headers=cw_service._get_headers(), timeout=10)
            if token_resp.status_code not in (200, 201):
                logger.error(f"Failed to fetch platform token in assignable agents: {token_resp.status_code}")
                return Response({"error": "Failed to authenticate with Chatwoot"}, status=500)
            
            user_token = token_resp.json().get("access_token")

            # Dynamically resolve account_id from the organization profile
            from core.models import ShopCredentials
            shop = ShopCredentials.objects.filter(organization_id=org_id).first()
            org_name = org_id
            if shop:
                if shop.store_name:
                    org_name = shop.store_name
                elif shop.myshopify_domain:
                    org_name = shop.myshopify_domain.split('.')[0].replace('-', ' ').title()
            
            account = cw_service.get_or_create_account(org_name, org_id=org_id)
            account_id = account.get("id") if account else 1

            # Chatwoot inbox assignable agents API is GET /api/v1/accounts/{account_id}/inboxes/{inbox_id}/assignable_agents
            agents_url = f"{cw_service.api_url}/api/v1/accounts/{account_id}/inboxes/{agent.chatwoot_inbox_id}/assignable_agents"
            headers = {
                "api_access_token": user_token,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            resp = requests.get(agents_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                payload = resp.json()
                agents_list = payload if isinstance(payload, list) else payload.get("payload", [])
                
                formatted = []
                for a in agents_list:
                    formatted.append({
                        "id": a.get("id"),
                        "name": a.get("name"),
                        "email": a.get("email"),
                        "role": a.get("role")
                    })
                return Response({"agents": formatted})
            else:
                logger.error(f"Chatwoot assignable agents returned {resp.status_code}: {resp.text}")
                return Response({"error": "Failed to fetch agents from Chatwoot"}, status=resp.status_code)
        except Exception as e:
            logger.exception(f"Error fetching Chatwoot assignable agents: {e}")
            return Response({"error": str(e)}, status=500)


class ChatwootAgentTriggerScrapeView(APIView):
    """
    POST /api/chatwoot/agent/trigger-scrape/
    Launches background crawler for storefront pages and processes nuggets asynchronously.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org_id = _get_org_id(request)
        custom_url = request.data.get("url", "").strip()

        from core.models import AIAgent
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if not agent:
            return Response({"error": "No AIAgent configured for this organization"}, status=404)

        from django_q.tasks import async_task
        
        # Enqueue background django-q scraper execution
        task_id = async_task(
            'core.tasks.ai_evaluation.scrape_agent_website_task',
            agent.id,
            custom_url=custom_url or None
        )

        return Response({
            "status": "success",
            "task_id": task_id,
            "message": "Storefront background scraper successfully scheduled."
        })


class ChatwootAgentNuggetsView(APIView):
    """
    GET /api/chatwoot/agent/nuggets/ - Retrieves all knowledge nuggets for this storefront agent.
    POST /api/chatwoot/agent/nuggets/ - Creates a new knowledge nugget (supports url, text, document).
    DELETE /api/chatwoot/agent/nuggets/ - Deletes a specific knowledge nugget by id.
    PATCH /api/chatwoot/agent/nuggets/ - Toggles active status of a knowledge nugget by id.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org_id = _get_org_id(request)
        if not org_id:
            return Response({"error": "No organization linked to user profile"}, status=400)

        from core.models import AIAgent, KnowledgeNugget
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if not agent:
            return Response({"nuggets": []})

        nuggets = KnowledgeNugget.objects.filter(agent=agent).order_by('-created_at')
        
        nuggets_list = []
        for n in nuggets:
            nuggets_list.append({
                "id": n.id,
                "source_type": n.source_type,
                "title": n.title,
                "content": n.content,
                "is_active": n.is_active,
                "metadata": n.get_metadata_dict(),
                "created_at": n.created_at.strftime('%d %b %Y, %H:%M') if n.created_at else 'N/A'
            })
            
        return Response({"nuggets": nuggets_list})

    def post(self, request):
        org_id = _get_org_id(request)
        from core.models import AIAgent, KnowledgeNugget
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if not agent:
            return Response({"error": "No agent found for this merchant storefront"}, status=404)

        source_type = request.data.get("source_type", "text")
        title = request.data.get("title", "").strip()
        content = request.data.get("content", "").strip()
        metadata_dict = request.data.get("metadata", {})

        if not title:
            return Response({"error": "Title cannot be blank"}, status=400)
        if not content:
            return Response({"error": "Content cannot be blank"}, status=400)

        nugget = KnowledgeNugget.objects.create(
            agent=agent,
            source_type=source_type,
            title=title,
            content=content,
            is_active=True
        )
        nugget.set_metadata_dict(metadata_dict)
        nugget.save()

        # Invalidate Gemini prompt cache
        agent.gemini_cache_id = None
        agent.save(update_fields=['gemini_cache_id'])

        return Response({
            "status": "success",
            "message": "Knowledge nugget successfully added.",
            "nugget": {
                "id": nugget.id,
                "source_type": nugget.source_type,
                "title": nugget.title,
                "content": nugget.content,
                "is_active": nugget.is_active,
                "metadata": nugget.get_metadata_dict(),
                "created_at": nugget.created_at.strftime('%d %b %Y, %H:%M') if nugget.created_at else 'N/A'
            }
        })

    def delete(self, request):
        nugget_id = request.data.get("nugget_id") or request.query_params.get("nugget_id")
        if not nugget_id:
            return Response({"error": "Missing nugget_id parameter"}, status=400)

        org_id = _get_org_id(request)
        from core.models import AIAgent, KnowledgeNugget
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if not agent:
            return Response({"error": "No agent found for storefront"}, status=404)

        try:
            nugget = KnowledgeNugget.objects.get(pk=nugget_id, agent=agent)
            nugget.delete()
            
            # Invalidate Gemini prompt cache
            agent.gemini_cache_id = None
            agent.save(update_fields=['gemini_cache_id'])
            
            return Response({"status": "success", "message": "Knowledge nugget deleted successfully."})
        except KnowledgeNugget.DoesNotExist:
            return Response({"error": "Knowledge nugget not found"}, status=404)

    def patch(self, request):
        nugget_id = request.data.get("nugget_id")
        if not nugget_id:
            return Response({"error": "Missing nugget_id parameter"}, status=400)

        org_id = _get_org_id(request)
        from core.models import AIAgent, KnowledgeNugget
        agent = AIAgent.objects.filter(organization_id=org_id).first()
        if not agent:
            return Response({"error": "No agent found for storefront"}, status=404)

        try:
            nugget = KnowledgeNugget.objects.get(pk=nugget_id, agent=agent)
            is_active = request.data.get("is_active")
            if is_active is not None:
                nugget.is_active = bool(is_active)
                nugget.save()

                # Invalidate Gemini prompt cache
                agent.gemini_cache_id = None
                agent.save(update_fields=['gemini_cache_id'])

            return Response({
                "status": "success",
                "message": "Knowledge nugget status updated successfully.",
                "nugget": {
                    "id": nugget.id,
                    "is_active": nugget.is_active
                }
            })
        except KnowledgeNugget.DoesNotExist:
            return Response({"error": "Knowledge nugget not found"}, status=404)


class ChatwootAgentNuggetParseView(APIView):
    """
    POST /api/chatwoot/agent/nuggets/parse/
    Accepts a multipart file upload (PDF or DOCX), parses and extracts its text contents,
    and returns {"title": filename, "content": text}.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    @property
    def parser_classes(self):
        from rest_framework.parsers import MultiPartParser, FormParser
        return [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({"error": "No file uploaded"}, status=400)

        filename = uploaded_file.name
        
        # Support PDF and DOCX based on extension
        ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        if ext == 'pdf':
            # Parse PDF using pdfplumber
            try:
                import pdfplumber
                pages_text = []
                with pdfplumber.open(uploaded_file) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text()
                        if text:
                            pages_text.append(text)
                parsed_text = "\n\n".join(pages_text)
                if not parsed_text.strip():
                    return Response({"error": "PDF file is empty or contains no extractable text"}, status=400)
            except Exception as e:
                return Response({"error": f"Failed to parse PDF: {str(e)}"}, status=500)
                
        elif ext in ('docx', 'doc'):
            # Parse DOCX using built-in zipfile & xml parser
            try:
                import zipfile
                import xml.etree.ElementTree as ET
                
                with zipfile.ZipFile(uploaded_file) as docx:
                    xml_content = docx.read('word/document.xml')
                    root = ET.fromstring(xml_content)
                    texts = []
                    for child in root.iter():
                        if child.tag.endswith('}t'):
                            if child.text:
                                texts.append(child.text)
                    parsed_text = "".join(texts)
                if not parsed_text.strip():
                    return Response({"error": "DOCX file is empty or contains no extractable text"}, status=400)
            except Exception as e:
                return Response({"error": f"Failed to parse DOCX: {str(e)}"}, status=500)
        else:
            return Response({"error": "Unsupported file format. Please upload a PDF or DOCX file."}, status=400)

        # Truncate extension from title
        title = filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').title()

        return Response({
            "status": "success",
            "title": title,
            "content": parsed_text
        })


