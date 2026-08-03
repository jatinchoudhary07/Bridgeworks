"""
Logistics Aura — AI chat views
================================
Provides SSE-streaming chat sessions for the Logistics Intelligence feature.
Pattern mirrors views_marketing.py (marketing_ai_sessions / marketing_ai_chat).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import date as dt_date, timedelta
import json
import logging

logger = logging.getLogger(__name__)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _get_org(request):
    user = request.user
    try:
        sc = user.shop_credentials
        if sc:
            return sc
    except Exception:
        pass
    try:
        if user.team_settings and user.team_settings.organization:
            return user.team_settings.organization
    except Exception:
        pass
    # Superuser / staff fallback — use the org specified in query params or the first available
    if user.is_superuser or user.is_staff:
        from core.models import ShopCredentials
        org_id_param = (request.GET if request.method == 'GET' else request.data).get('org_id')
        if org_id_param:
            org = ShopCredentials.objects.filter(organization_id=org_id_param).first()
            if org:
                return org
        return ShopCredentials.objects.filter(myshopify_domain__isnull=False).order_by('id').first() \
            or ShopCredentials.objects.order_by('id').first()
    return None


def _get_date_params(request):
    source = request.GET if request.method == 'GET' else request.data
    preset = source.get('date_preset')
    start_str = source.get('start_date')
    end_str = source.get('end_date')

    if preset:
        return _preset_to_dates(preset)
    if start_str and end_str:
        return dt_date.fromisoformat(start_str), dt_date.fromisoformat(end_str)
    return _preset_to_dates('last_30d')


def _preset_to_dates(preset):
    today = timezone.now().date()
    presets = {
        'today':        (today, today),
        'yesterday':    (today - timedelta(days=1), today - timedelta(days=1)),
        'this_month':   (today.replace(day=1), today),
        'last_7d':      (today - timedelta(days=7), today),
        'last_14d':     (today - timedelta(days=14), today),
        'last_28d':     (today - timedelta(days=28), today),
        'last_30d':     (today - timedelta(days=30), today),
        'last_90d':     (today - timedelta(days=90), today),
        'this_year':    (today.replace(month=1, day=1), today),
    }
    if preset in presets:
        return presets[preset]
    # last_month
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    if preset == 'last_month':
        return last_prev.replace(day=1), last_prev
    return today - timedelta(days=30), today


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Logistics AI Sessions  —  GET (list) / POST (create)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def logistics_ai_sessions(request):
    """
    GET  — list all logistics AI chat sessions for the authenticated user.
    POST — create a new session (optionally generate initial analysis).
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization associated with this user"}, status=400)

    from core.models import LogisticsAIChatSession, LogisticsAIChatMessage

    # ── GET: list sessions ────────────────────────────────────────────────────
    if request.method == 'GET':
        sessions = LogisticsAIChatSession.objects.filter(
            shop=org, user=request.user
        ).order_by('-created_at')
        data = [
            {
                "id": s.id,
                "title": s.title,
                "model_name": s.model_name,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in sessions
        ]
        return Response(data)

    # ── POST: create session ──────────────────────────────────────────────────
    sd, ed = _get_date_params(request)
    model_name = request.data.get('model', 'gemini-2.5-flash')
    date_preset = request.data.get('date_preset', '')
    skip_initial = request.data.get('skip_initial_analysis', False)

    try:
        if not date_preset:
            # General chat — no preset, no initial analysis
            session = LogisticsAIChatSession.objects.create(
                shop=org, user=request.user,
                title="New Chat",
                model_name=model_name,
            )
            return Response({
                "message": "General chat session created",
                "session_id": str(session.id),
                "title": session.title,
            })

        title = f"Logistics Analysis: {date_preset} ({timezone.now().strftime('%b %d, %H:%M')})"
        session = LogisticsAIChatSession.objects.create(
            shop=org, user=request.user,
            title=title, model_name=model_name,
        )

        if skip_initial:
            return Response({
                "message": "Empty session created",
                "session_id": str(session.id),
                "title": session.title,
            })

        # Generate initial structured insights
        from core.services.ai_logistics_agent import _fetch_logistics_payload
        import json as _json
        from decimal import Decimal

        payload = _fetch_logistics_payload(org, sd, ed)

        class _Dec(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, Decimal):
                    return float(o)
                if hasattr(o, 'isoformat'):
                    return o.isoformat()
                return super().default(o)

        structured_data = json.loads(json.dumps(payload, cls=_Dec))

        msg = LogisticsAIChatMessage.objects.create(
            session=session,
            role='ai',
            content='Logistics Intelligence Report Generated:',
            structured_data=structured_data,
        )

        return Response({
            "session_id": str(session.id),
            "title": session.title,
            "first_message": {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "structured_data": msg.structured_data,
                "created_at": msg.created_at,
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Session Detail  —  GET (messages) / DELETE
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def logistics_ai_session_detail(request, session_id):
    """
    GET    — return all messages in the session.
    DELETE — remove the session.
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization associated with this user"}, status=400)

    from core.models import LogisticsAIChatSession
    try:
        session = LogisticsAIChatSession.objects.get(id=session_id, shop=org, user=request.user)
    except LogisticsAIChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)

    if request.method == 'DELETE':
        session.delete()
        return Response({"detail": "Session deleted"})

    messages = session.messages.all()
    return Response({
        "session": {
            "id": str(session.id),
            "title": session.title,
            "model_name": session.model_name,
        },
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "structured_data": m.structured_data,
                "created_at": m.created_at,
            }
            for m in messages
        ],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Streaming Chat  —  POST
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logistics_ai_chat(request):
    """
    POST a new question to an existing logistics session.
    Streams the AI response using Server-Sent Events (SSE).
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization associated with this user"}, status=400)

    session_id = request.data.get('session_id')
    question = request.data.get('question')

    if not session_id or not question:
        return Response({"error": "session_id and question are required"}, status=400)

    from core.models import LogisticsAIChatSession, LogisticsAIChatMessage
    try:
        session = LogisticsAIChatSession.objects.get(id=session_id, shop=org, user=request.user)
    except LogisticsAIChatSession.DoesNotExist:
        return Response({"error": "Session not found"}, status=404)

    # ── Detect date range from the question text ──────────────────────────────
    sd, ed = _get_date_params(request)
    today = timezone.now().date()

    # ── Save user message ─────────────────────────────────────────────────────
    LogisticsAIChatMessage.objects.create(session=session, role='user', content=question)

    # Auto-title from first question
    user_msg_count = session.messages.filter(role='user').count()
    if user_msg_count <= 1:
        session.title = question[:60] + ('…' if len(question) > 60 else '')
        session.save(update_fields=['title'])

    model_name = request.data.get('model', session.model_name)

    def stream_generator():
        try:
            yield ": keep-alive\n\n"

            from core.services.ai_logistics_agent import run_logistics_chat

            # Build conversation history for multi-turn context
            history_msgs = list(session.messages.all().order_by('-created_at')[:12])
            history_msgs.reverse()
            history_context = []
            for m in history_msgs:
                if m.structured_data:
                    summary = json.dumps({
                        k: v for k, v in m.structured_data.items()
                        if k in ('order_summary', 'ndr_analysis', 'rto_analysis', 'cod_analysis', 'date_range')
                    })
                    history_context.append({"role": m.role, "content": f"Logistics data summary: {summary}"})
                else:
                    history_context.append({"role": m.role, "content": m.content})

            # ── Handle file attachments ──────────────────────────────────────
            attached_files = []
            if hasattr(request, 'FILES'):
                for file_key in request.FILES:
                    f = request.FILES[file_key]
                    mime_map = {
                        '.pdf': 'application/pdf',
                        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                        '.gif': 'image/gif', '.webp': 'image/webp',
                        '.csv': 'text/csv', '.txt': 'text/plain',
                        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        '.xls': 'application/vnd.ms-excel',
                        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    }
                    import os
                    ext = os.path.splitext(f.name.lower())[1]
                    mime = mime_map.get(ext, f.content_type or 'application/octet-stream')
                    attached_files.append({"data": f.read(), "mime_type": mime})

            result = run_logistics_chat(
                org=org,
                question=question,
                start_date=sd,
                end_date=ed,
                model_name=model_name,
                conversation_context=history_context,
                attached_files=attached_files if attached_files else None,
                session_id=str(session_id),
                user_identifier=str(request.user.id),
            )

            if result and "stream" in result:
                full_text = []
                try:
                    for chunk in result["stream"]:
                        if chunk:
                            full_text.append(chunk)
                            yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                except Exception as stream_exc:
                    logger.error(f"Gemini stream interrupted: {stream_exc}", exc_info=True)
                finally:
                    final_text = "".join(full_text)
                    if final_text:
                        msg = LogisticsAIChatMessage.objects.create(
                            session=session, role='ai', content=final_text
                        )
                        yield f"data: {json.dumps({'done': True, 'message_id': msg.id})}\n\n"

            elif result and "error" in result:
                yield f"data: {json.dumps({'error': result['error']})}\n\n"
            else:
                yield f"data: {json.dumps({'error': 'Unknown AI response'})}\n\n"

        except Exception as exc:
            logger.error(f"Logistics AI stream failed: {exc}", exc_info=True)
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    from django.http import StreamingHttpResponse
    response = StreamingHttpResponse(stream_generator(), content_type='text/event-stream')
    response['X-Accel-Buffering'] = 'no'
    response['Cache-Control'] = 'no-cache'
    response['Connection'] = 'keep-alive'
    response['Content-Encoding'] = 'identity'
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Agent Manager — Global Rules (CRUD)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def logistics_agent_global_rules(request):
    """
    GET  — list all logistics global rules.
    POST — create a new rule.
    """
    from core.models import LogisticsAgentGlobalRule

    if request.method == 'GET':
        rules = LogisticsAgentGlobalRule.objects.all().order_by('-priority', '-created_at')
        return Response([
            {
                "id": r.id,
                "rule_text": r.rule_text,
                "is_active": r.is_active,
                "priority": r.priority,
                "expires_at": r.expires_at,
                "created_by": r.created_by,
                "is_expired": r.is_expired,
                "created_at": r.created_at,
            }
            for r in rules
        ])

    # POST
    rule_text = request.data.get('rule_text', '').strip()
    if not rule_text:
        return Response({"error": "rule_text is required"}, status=400)

    rule = LogisticsAgentGlobalRule.objects.create(
        rule_text=rule_text,
        is_active=request.data.get('is_active', True),
        priority=request.data.get('priority', 0),
        expires_at=request.data.get('expires_at'),
        created_by=str(request.user),
    )
    return Response({
        "id": rule.id,
        "rule_text": rule.rule_text,
        "is_active": rule.is_active,
        "priority": rule.priority,
        "expires_at": rule.expires_at,
        "is_expired": rule.is_expired,
        "created_at": rule.created_at,
    }, status=201)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def logistics_agent_global_rule_detail(request, rule_id):
    """
    PATCH  — update a rule.
    DELETE — remove a rule.
    """
    from core.models import LogisticsAgentGlobalRule
    try:
        rule = LogisticsAgentGlobalRule.objects.get(id=rule_id)
    except LogisticsAgentGlobalRule.DoesNotExist:
        return Response({"error": "Rule not found"}, status=404)

    if request.method == 'DELETE':
        rule.delete()
        return Response({"detail": "Deleted"})

    for field in ('rule_text', 'is_active', 'priority', 'expires_at'):
        if field in request.data:
            setattr(rule, field, request.data[field])
    rule.save()
    return Response({
        "id": rule.id,
        "rule_text": rule.rule_text,
        "is_active": rule.is_active,
        "priority": rule.priority,
        "expires_at": rule.expires_at,
        "is_expired": rule.is_expired,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Agent Manager — Conversation Audit Logs (read-only)
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def logistics_agent_conversation_logs(request):
    """
    GET — paginated list of conversation logs for admin audit.
    Optional query params: ?flagged=true  ?shop=name  ?search=text  ?page=N
    """
    from core.models import LogisticsConversationLog

    qs = LogisticsConversationLog.objects.all().order_by('-created_at')

    if request.GET.get('flagged') == 'true':
        qs = qs.filter(flagged_for_review=True)
    if request.GET.get('shop'):
        qs = qs.filter(shop_name__icontains=request.GET['shop'])
    if request.GET.get('search'):
        q = request.GET['search']
        qs = qs.filter(user_message__icontains=q) | qs.filter(ai_response__icontains=q)

    page = int(request.GET.get('page', 1))
    per_page = 20
    total = qs.count()
    logs = qs[(page - 1) * per_page: page * per_page]

    return Response({
        "count": total,
        "page": page,
        "total_pages": (total + per_page - 1) // per_page,
        "results": [
            {
                "id": l.id,
                "session_id": l.session_id,
                "user_identifier": l.user_identifier,
                "shop_name": l.shop_name,
                "user_message": l.user_message[:300],
                "ai_response": l.ai_response[:500],
                "model_used": l.model_used,
                "tokens_input": l.tokens_input,
                "tokens_output": l.tokens_output,
                "response_time_ms": l.response_time_ms,
                "flagged_for_review": l.flagged_for_review,
                "admin_note": l.admin_note,
                "created_at": l.created_at,
            }
            for l in logs
        ],
    })


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Audit Response — Retrieve full log detail
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logistics_agent_audit_response(request):
    """
    POST { log_id }: Explain why Logistics AURA gave that specific response.
    Makes a second Gemini call using the stored system_prompt_snapshot — same
    pattern as the Marketing AURA audit endpoint.
    Optional body field: { question: "..." } for targeted follow-up questions.
    """
    from core.models import LogisticsConversationLog

    log_id = request.data.get('log_id')
    if not log_id:
        return Response({"error": "log_id required"}, status=400)

    try:
        log = LogisticsConversationLog.objects.get(id=log_id)
    except LogisticsConversationLog.DoesNotExist:
        return Response({"error": "Log not found"}, status=404)

    # ── Optional admin note (non-AI, just store it) ──────────────────────────
    admin_note = request.data.get('admin_note')
    if admin_note is not None:
        log.admin_note = admin_note
        log.save(update_fields=['admin_note'])

    # ── Gemini self-audit ────────────────────────────────────────────────────
    try:
        from google import genai as genai_client
        from google.genai import types
        from django.conf import settings

        client = genai_client.Client(api_key=settings.GEMINI_API_KEY)
        question = request.data.get('question')

        if question:
            audit_prompt = f"""
You are an AI response auditor. The user has a specific question about why the Logistics AURA agent produced a specific response.

--- SYSTEM PROMPT THAT WAS ACTIVE ---
{log.system_prompt_snapshot[:3000]}

--- USER ASKED ---
{log.user_message}

--- AI RESPONDED ---
{log.ai_response[:2000]}

--- USER'S QUESTION ABOUT THIS RESPONSE ---
{question}

--- YOUR INSTRUCTIONS ---
Answer the user's question directly and concisely. Explain exactly what caused the AI to say that, citing the system prompt or data above if necessary.
"""
        else:
            audit_prompt = f"""
You are an AI response auditor. Explain exactly why the Logistics AURA agent produced the response below.

--- SYSTEM PROMPT THAT WAS ACTIVE ---
{log.system_prompt_snapshot[:3000]}

--- USER ASKED ---
{log.user_message}

--- AI RESPONDED ---
{log.ai_response[:2000]}

--- YOUR AUDIT ---
Explain:
1. Which part of the system prompt triggered this response?
2. Was this response aligned with the active override rules (if any)?
3. What data from the logistics payload influenced the answer?
4. What correction could be added to the system prompt to improve this?
Be specific. Cite exact sections of the system prompt where relevant.
"""

        from core.utils.gemini_fallback import generate_content_with_fallback
        response = generate_content_with_fallback(
            client=client,
            model='gemini-2.5-flash-lite',
            contents=audit_prompt,
        )
        return Response({'explanation': response.text, 'log_id': log_id})

    except Exception as e:
        logger.error(f"Logistics agent audit failed: {e}", exc_info=True)
        return Response({'error': str(e)}, status=500)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Flag and Correct — Flag a log + optionally create a correction rule
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logistics_agent_flag_and_correct(request):
    """
    POST {
        log_id, bad_behavior_description, corrected_instruction,
        example_bad_response (optional), example_good_response (optional)
    }
    Flags the log and creates a LogisticsCorrectionRule.
    """
    from core.models import LogisticsConversationLog, LogisticsCorrectionRule

    log_id = request.data.get('log_id')
    bad = request.data.get('bad_behavior_description', '').strip()
    fix = request.data.get('corrected_instruction', '').strip()

    if not log_id or not bad or not fix:
        return Response({"error": "log_id, bad_behavior_description, and corrected_instruction are required"}, status=400)

    try:
        log = LogisticsConversationLog.objects.get(id=log_id)
    except LogisticsConversationLog.DoesNotExist:
        return Response({"error": "Log not found"}, status=404)

    log.flagged_for_review = True
    log.save(update_fields=['flagged_for_review'])

    correction = LogisticsCorrectionRule.objects.create(
        bad_behavior_description=bad,
        corrected_instruction=fix,
        example_bad_response=request.data.get('example_bad_response', log.ai_response[:500]),
        example_good_response=request.data.get('example_good_response', ''),
        source_log_id=log.id,
        created_by=str(request.user),
    )

    return Response({
        "detail": "Log flagged and correction rule created.",
        "correction_id": correction.id,
        "log_id": log.id,
    }, status=201)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Sync Cache — Clear cached logistics payload so next query fetches fresh data
# ═══════════════════════════════════════════════════════════════════════════════

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logistics_sync_cache(request):
    """
    POST — Clears the Django cache for the org's logistics payload.
    Body (optional):
      { start_date: "YYYY-MM-DD", end_date: "YYYY-MM-DD" }  → clears that specific range key
      { clear_all: true }                                    → clears all keys matching this org
    """
    org = _get_org(request)
    if not org:
        return Response({"error": "No organization associated with this user"}, status=400)

    from django.core.cache import cache

    clear_all = request.data.get('clear_all', False)

    if clear_all:
        # Django's default cache doesn't support pattern deletion; we delete known range keys
        # by iterating common presets to bust the most likely cached entries.
        from datetime import date as dt_date, timedelta
        today = dt_date.today()
        cleared = 0
        for days_back in [0, 7, 14, 28, 30, 60, 90, 120, 180, 365]:
            for window in [7, 14, 28, 30, 60, 90]:
                start = today - timedelta(days=days_back + window)
                end = today - timedelta(days=days_back)
                key = f"logistics_aura_payload:{org.id}:{start}:{end}"
                if cache.get(key) is not None:
                    cache.delete(key)
                    cleared += 1
        # Also bust the most common "rolling" ranges
        for days in [7, 14, 28, 30, 60, 90]:
            start = today - timedelta(days=days)
            key = f"logistics_aura_payload:{org.id}:{start}:{today}"
            cache.delete(key)
            cleared += 1
        return Response({"detail": f"All logistics caches cleared ({cleared} keys). Fresh data will be fetched on next query."})

    # Clear a specific date range
    sd, ed = _get_date_params(request)
    cache_key = f"logistics_aura_payload:{org.id}:{sd}:{ed}"
    cache.delete(cache_key)
    return Response({"detail": f"Cache cleared for {sd} → {ed}. Next query will fetch fresh logistics data."})
