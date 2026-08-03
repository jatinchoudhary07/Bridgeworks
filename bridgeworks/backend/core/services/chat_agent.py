"""
chat_agent.py — Conversational SQL Agent ("Thorfinn")
=====================================================
Uses the native Google GenAI SDK with automatic function calling
to query database records securely via safe ORM-backed query tools.

The agent uses specific whitelisted Python query functions with typed parameters.
Direct SQL execution is disabled for security.
"""
import os
import logging
import threading
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

# Thread-local storage for request-scoped context during LLM run
_thread_local = threading.local()


# =============================================================================
# 1. Safe Query Tools (ORM-backed and scoped to thread-local org_id)
# =============================================================================

def list_orders(search: str = "", limit: int = 50) -> list[dict]:
    """
    List orders in the database for the active organization. Use search to find 
    specific orders by order number, contact name, or email. Results are limited to a max of 100.
    """
    org_id = getattr(_thread_local, 'org_id', None)
    if not org_id:
        return [{"error": "Organization context missing."}]
        
    from core.models import Order
    
    limit = min(max(int(limit), 1), 100)
    qs = Order.objects.filter(org_id=org_id)
    
    if search:
        clean_search = search.strip().lstrip('#')
        qs = qs.filter(
            Q(order_number__icontains=clean_search) |
            Q(customer_first_name__icontains=clean_search) |
            Q(customer_last_name__icontains=clean_search) |
            Q(email__icontains=clean_search)
        )
        
    qs = qs.order_by('-created_at')[:limit]
    
    return [
        {
            "id": order.id,
            "order_number": order.order_number,
            "customer_name": f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
            "email": order.email,
            "total_price": str(order.total_price),
            "status": order.status,
            "current_status": order.current_status,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }
        for order in qs
    ]


def order_summary(days: int = 30) -> dict:
    """
    Get aggregated stats of orders (count, revenue, average order value) over the last N days.
    """
    org_id = getattr(_thread_local, 'org_id', None)
    if not org_id:
        return {"error": "Organization context missing."}
        
    from core.models import Order
    
    days = min(max(int(days), 1), 365)
    since = timezone.now() - timedelta(days=days)
    
    stats = Order.objects.filter(
        org_id=org_id,
        created_at__gte=since
    ).aggregate(
        total_orders=Count("id"),
        total_revenue=Sum("total_price"),
        avg_order_value=Avg("total_price")
    )
    
    return {
        "days": days,
        "total_orders": stats["total_orders"] or 0,
        "total_revenue": str(stats["total_revenue"] or 0.0),
        "average_order_value": str(stats["avg_order_value"] or 0.0),
    }


def list_returns(limit: int = 50) -> list[dict]:
    """
    List open return requests for the organization.
    """
    org_id = getattr(_thread_local, 'org_id', None)
    if not org_id:
        return [{"error": "Organization context missing."}]
        
    from core.models import ReturnRequest
    
    limit = min(max(int(limit), 1), 100)
    qs = ReturnRequest.objects.filter(order__org_id=org_id).select_related('order')[:limit]
    
    return [
        {
            "id": r.id,
            "order_number": r.order.order_number if r.order else None,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in qs
    ]


def search_customer(query: str, limit: int = 20) -> list[dict]:
    """
    Search customers by name, email, or phone number in this organization.
    """
    org_id = getattr(_thread_local, 'org_id', None)
    if not org_id:
        return [{"error": "Organization context missing."}]
        
    from core.models import Order
    
    limit = min(max(int(limit), 1), 100)
    
    qs = Order.objects.filter(org_id=org_id)
    if query:
        qs = qs.filter(
            Q(customer_first_name__icontains=query) |
            Q(customer_last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(contact_phone__icontains=query)
        )
        
    # Get distinct customers by name and email
    customers = qs.values(
        'customer_first_name', 'customer_last_name', 'email', 'contact_phone'
    ).distinct()[:limit]
    
    return list(customers)


def get_order_details(order_number: str) -> dict:
    """
    Get detailed information about a single order by its order number.
    """
    org_id = getattr(_thread_local, 'org_id', None)
    if not org_id:
        return {"error": "Organization context missing."}
        
    from core.models import Order
    clean_num = order_number.strip().lstrip('#')
    
    order = Order.objects.filter(order_number=clean_num, org_id=org_id).prefetch_related('fulfillments', 'line_items').first()
    if not order:
        return {"error": f"Order #{order_number} not found."}
        
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_name": f"{order.customer_first_name or ''} {order.customer_last_name or ''}".strip(),
        "email": order.email,
        "phone": order.contact_phone,
        "total_price": str(order.total_price),
        "status": order.status,
        "current_status": order.current_status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "ndr_remarks": order.ndr_remarks,
        "line_items": [
            {"sku": item.sku, "title": item.title, "quantity": item.quantity, "price": str(item.price)}
            for item in order.line_items.all()
        ],
        "fulfillments": [
            {"shopify_id": f.shopify_id, "status": f.shipment_status}
            for f in order.fulfillments.all()
        ]
    }


def get_ticket_details(case_number: str) -> dict:
    """
    Get detailed information about a single support ticket (CaseFile) by its case number.
    """
    org_id = getattr(_thread_local, 'org_id', None)
    if not org_id:
        return {"error": "Organization context missing."}
        
    from core.models import CaseFile
    clean_num = case_number.strip().upper().replace('CF-', '')
    
    ticket = CaseFile.objects.filter(case_number=clean_num, order__org_id=org_id).select_related('order').first()
    if not ticket:
        return {"error": f"Ticket CF-{case_number} not found."}
        
    return {
        "id": ticket.id,
        "case_number": ticket.case_number,
        "order_number": ticket.order.order_number if ticket.order else None,
        "subject": ticket.subject,
        "description": ticket.description,
        "issue_type": ticket.issue_type,
        "priority": ticket.priority,
        "status": ticket.status,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "solution_provided_text": ticket.solution_provided_text,
    }


def run_sql_query(query: str) -> str:
    """
    REMOVED: Direct SQL execution is disabled for security.
    """
    raise RuntimeError(
        "run_sql_query() has been disabled for security. "
        "Use safe ORM retrieval tools instead."
    )


# =============================================================================
# 2. Interactive Action Tools
# =============================================================================

def trigger_navigation(page_route: str) -> str:
    """
    Trigger a frontend navigation to a specific page or dashboard module.
    Use this tool whenever the user asks to "go to", "navigate to", "open", "show", or "switch to" a specific section or module.
    Routes available:
    - '/' (Home)
    - '/operations' (Operations & Fulfillment)
    - '/tracking' (Logistics/Tracking)
    - '/rto' (Reverse Shipment)
    - '/customer-care' (Customer Care / Tickets)
    - '/intelligence' (Intelligence / AI config)
    - '/marketing' (Marketing & Growth)
    - '/finance' (Finance & Accounting)
    - '/sales' (Sales & Business Dev)
    - '/mydesk' (My Desk / Tasks)
    - '/profile' (Profile)
    - '/shop-profile' (Shop Profile)
    - '/team' (Team Management)
    """
    if not hasattr(_thread_local, 'actions'):
        _thread_local.actions = []
    _thread_local.actions.append({
        "type": "navigate",
        "route": page_route
    })
    return f"Success: Navigation action to '{page_route}' recorded."


def raise_ticket(order_number: str, subject: str, description: str, issue_type: str = 'DELIVERY', priority: int = 1) -> str:
    """
    Create a new support ticket (CaseFile) in the database and link it to the specified order.
    Use this tool only when the user explicitly requests to "raise", "file", "create", or "open" a ticket, case, or issue.
    - Valid issue_types: 'DELIVERY', 'RTO', 'DAMAGE', 'MISSING', 'REFUND', 'CANCELLATION', 'OTHER'.
    - Valid priorities: 1 (Low), 2 (Medium), 3 (High).
    """
    user = getattr(_thread_local, 'user', None)
    org_id = getattr(_thread_local, 'org_id', None)
    
    # We find the order within the organization
    from core.models import Order, CaseFile
    
    # Clean order number (strip '#' if present)
    clean_num = order_number.strip().lstrip('#')
    order = Order.objects.filter(order_number=clean_num, org_id=org_id).first()
    if not order:
        return f"Error: Order #{order_number} not found in this organization."
    
    # Create ticket
    try:
        with transaction.atomic():
            # Validate issue_type
            valid_types = [choice[0] for choice in CaseFile.ISSUE_TYPE_CHOICES]
            if issue_type not in valid_types:
                issue_type = 'DELIVERY'
                
            ticket = CaseFile.objects.create(
                order=order,
                subject=subject,
                description=description,
                issue_type=issue_type,
                priority=priority,
                registered_by=user,
                status='NEW_FIR'
            )
            
            # Append an action to notify frontend of the new ticket (e.g. to display toast or redirect)
            if not hasattr(_thread_local, 'actions'):
                _thread_local.actions = []
            _thread_local.actions.append({
                "type": "ticket_created",
                "ticket_number": ticket.case_number,
                "ticket_id": ticket.id
            })
            
            return f"Success: Successfully created support ticket CF-{ticket.case_number} linked to Order #{order_number}."
    except Exception as e:
        return f"Error creating ticket: {str(e)}"


def resolve_ticket(case_number: str, solution: str) -> str:
    """
    Resolve an existing support ticket (CaseFile) by updating its status to 'RESOLVED' and saving the solution.
    Use this tool when the user asks to "resolve", "close", or "solve" a ticket or case file.
    """
    org_id = getattr(_thread_local, 'org_id', None)
    user = getattr(_thread_local, 'user', None)
    from core.models import CaseFile, IssueComment
    
    # Strip non-numeric/clean case number
    clean_case_num = case_number.strip().upper().replace('CF-', '')
    ticket = CaseFile.objects.filter(case_number=clean_case_num, order__org_id=org_id).first()
    if not ticket:
        return f"Error: Support ticket with case number '{case_number}' not found in this organization."
    
    try:
        with transaction.atomic():
            ticket.status = 'RESOLVED'
            ticket.solution_provided_text = solution
            ticket.latest_remark = f"Resolved via Thorfinn AI Assistant."
            ticket.save()
            
            # Create an issue comment as well
            IssueComment.objects.create(
                case=ticket,
                user=user,
                message=f"Resolved via AI Assistant: {solution}",
                is_internal_note=False
            )
            
            return f"Success: Support ticket CF-{ticket.case_number} has been resolved."
    except Exception as e:
        return f"Error resolving ticket: {str(e)}"


def update_order_remarks(order_number: str, remark: str) -> str:
    """
    Update or append internal remarks/notes for a specific order.
    Use this tool when the user asks to "add a remark", "add a note", "update notes", or "set remarks" on an order.
    """
    org_id = getattr(_thread_local, 'org_id', None)
    from core.models import Order
    clean_num = order_number.strip().lstrip('#')
    order = Order.objects.filter(order_number=clean_num, org_id=org_id).first()
    if not order:
        return f"Error: Order #{order_number} not found in this organization."
    
    try:
        with transaction.atomic():
            order.ndr_remarks = remark
            order.save()
            return f"Success: Order #{order_number} remarks updated to: '{remark}'."
    except Exception as e:
        return f"Error updating remarks: {str(e)}"


# =============================================================================
# 3. Main Agent Entry Point
# =============================================================================

def ask_database(user_query: str, history: list = None, user = None, org_id: str = None) -> tuple[str, list]:
    """
    Takes a natural language query, passes it to the Gemini agent with ORM and action tools,
    and returns a tuple containing: (conversational answer string, list of interactive actions).
    """
    # 1. Initialize thread-local storage for context and actions
    _thread_local.user = user
    _thread_local.org_id = org_id
    _thread_local.actions = []

    try:
        from google import genai
        from google.genai import types
        from django.utils import timezone
        import zoneinfo
        
        from core.models import AnalyticsAgentConfiguration
        config = AnalyticsAgentConfiguration.objects.filter(is_active=True).first()
        
        base_system_prompt = config.system_prompt if config else (
            "You are Thorfinn, the BridgeWorks Data Analyst. You answer questions about the database. "
            "You have access to safe query tools to search for orders, customer details, return requests, and ticket details."
        )
        
        try:
            current_time_ist = timezone.now().astimezone(zoneinfo.ZoneInfo("Asia/Kolkata"))
        except Exception:
            from datetime import datetime, timedelta
            current_time_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
            
        current_time_str = current_time_ist.strftime("%Y-%m-%d %H:%M:%S")
        
        system_prefix = f"""{base_system_prompt}

CURRENT DATE AND TIME IN ASIA/KOLKATA TIMEZONE:
- Today's date and time is: {current_time_str}
- Day of the week: {current_time_ist.strftime('%A')}

ADDITIONAL PERSONAL ASSISTANT INSTRUCTIONS:
- You are not just a database analyst; you are a proactive personal assistant.
- You do NOT have a raw SQL query tool. You MUST use the specific query tools: `list_orders`, `order_summary`, `list_returns`, `search_customer`, `get_order_details`, and `get_ticket_details` to retrieve data.
- You can help the user navigate to different modules of the app using `trigger_navigation`.
- You can raise a support ticket (CaseFile) using `raise_ticket`, resolve tickets using `resolve_ticket`, or update order remarks using `update_order_remarks`.
- Use the appropriate tools immediately when the user requests an action or data, then summarize what you did for the user.
- Never output SQL queries to the user.
"""
        model_name = config.model_name if config else "gemini-2.5-flash-lite"
        
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

        # Build native conversation messages with history
        native_messages = []
        if history:
            # Keep only the last 15 messages to prevent token bloat
            for msg in history[-15:]:
                role = "user" if msg.get('role') == 'user' else "model"
                native_messages.append(types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg.get('content', ''))]
                ))
        
        # Append current user query
        native_messages.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_query)]
        ))

        # Invoke Gemini with all tools registered using fallback wrapper
        from core.utils.gemini_fallback import generate_content_with_fallback
        response = generate_content_with_fallback(
            client=client,
            model=model_name,
            contents=native_messages,
            config=types.GenerateContentConfig(
                system_instruction=system_prefix,
                tools=[
                    list_orders,
                    order_summary,
                    list_returns,
                    search_customer,
                    get_order_details,
                    get_ticket_details,
                    trigger_navigation,
                    raise_ticket,
                    resolve_ticket,
                    update_order_remarks
                ],
                temperature=0,
            ),
        )
        
        # Try to pull text from candidate.
        answer = None
        try:
            answer = response.text
        except (ValueError, AttributeError):
            pass
        
        if not answer:
            # Fallback: manually extract text from candidate parts
            try:
                if response.candidates and response.candidates[0].content:
                    parts = response.candidates[0].content.parts
                    if parts:
                        text_parts = [p.text for p in parts if p and hasattr(p, 'text') and p.text]
                        if text_parts:
                            answer = " ".join(text_parts)
            except (AttributeError, IndexError, TypeError):
                pass
                
        if not answer:
            answer = "I have processed your request."
            
        actions = list(getattr(_thread_local, 'actions', []))
        return answer, actions
        
    except Exception as e:
        logger.error(f"Chat Agent Error: {e}", exc_info=True)
        return "I encountered an issue while processing your request.", []
    finally:
        # Clear thread local storage to prevent memory leaks
        _thread_local.user = None
        _thread_local.org_id = None
        _thread_local.actions = []
