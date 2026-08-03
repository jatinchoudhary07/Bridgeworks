import json
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from core.models import AIAgent, KnowledgeNugget, AgentAuditLog

logger = logging.getLogger(__name__)

def compile_agent_context(agent: AIAgent) -> str:
    """
    Compiles all active knowledge nuggets and prompt behaviors into a single
    structured context document representing the store's static knowledge base.
    """
    context_lines = []
    
    # 1. Base Guidelines & System Instruction
    context_lines.append("=== BRAND PROFILE & CORE GUIDELINES ===")
    context_lines.append(agent.system_prompt)
    context_lines.append("")
    
    # 2. Knowledge Nuggets
    nuggets = agent.knowledge_nuggets.filter(is_active=True).order_by('source_type', 'created_at')
    
    if nuggets.exists():
        context_lines.append("=== STORE KNOWLEDGE BASE (FACTS, FAQ & POLICIES) ===")
        for n in nuggets:
            source_lbl = n.get_source_type_display()
            title_lbl = n.title or "Policy Snippet"
            context_lines.append(f"[Source Nugget ID: {n.id}] [{source_lbl}] {title_lbl}:")
            context_lines.append(n.content)
            context_lines.append("---")
    
    return "\n".join(context_lines)


def get_or_create_gemini_cache(client, agent: AIAgent, force_refresh=False) -> str:
    """
    Synchronizes BridgeWorks storefront guidelines and knowledge base with Google Gemini Context Caching.
    If a valid cache exists, returns its ID. If it is missing, expired, or forced, generates a new cache.
    """
    # If caching is not supported or fails, we return None and the main runner sends prompt in context.
    try:
        from google.genai import types
        
        # Compile full brand context
        full_context = compile_agent_context(agent)
        
        # Verify if current cache is registered and active
        # Gemini caches have an explicit ttl or expire time (default is 5 minutes unless specified)
        # We can create a cache with an expire time of e.g. 1 hour (3600 seconds) to balance costs and speed.
        if agent.gemini_cache_id and not force_refresh:
            try:
                # We can inspect the cache to verify it is valid
                cache = client.caches.get(name=agent.gemini_cache_id)
                logger.info(f"Using existing Gemini context cache: {cache.name}")
                return agent.gemini_cache_id
            except Exception as ce:
                logger.warning(f"Existing cache {agent.gemini_cache_id} invalid or expired: {ce}")
                agent.gemini_cache_id = None
                agent.save(update_fields=['gemini_cache_id'])

        logger.info(f"Creating new Gemini context cache for organization: {agent.organization_id}")
        
        # Create a CachedContent object using a supported model like gemini-2.0-flash
        cache = client.caches.create(
            model='gemini-2.0-flash',
            config=types.CreateCachedContentConfig(
                contents=[full_context],
                ttl='3600s',  # Keep context cached for 1 hour
                display_name=f"bridgeworks_agent_cache_{agent.id}",
            )
        )
        
        agent.gemini_cache_id = cache.name
        agent.save(update_fields=['gemini_cache_id'])
        logger.info(f"Successfully generated new Gemini context cache ID: {cache.name}")
        return cache.name

    except Exception as e:
        logger.warning(f"Gemini API context caching not available or failed: {e}. Falling back to standard prompt bundling.")
        return None


def generate_support_response(agent: AIAgent, customer_name: str, email: str, phone: str, 
                              message_content: str, orders_context: list, conversation_history: str = "", 
                              simulated=False, has_attachments=False, products_context: list = None,
                              session_state: dict = None) -> str:
    """
    Generates a highly contextual chatbot response using Gemini, 
    injecting specific storefront order context, guidelines and scraped facts.
    """
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.error("GEMINI_API_KEY is not set.")
        return "System Notification: Gemini API Key is missing. Please configure it in BridgeWorks settings."

    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        
        # 1. Compile order details
        orders_str = json.dumps(orders_context, indent=2)
        
        # 1.5. Compile attachments context
        attachment_context = "Yes, the customer has attached images/files." if has_attachments else "No attachments."
        
        # 1.7. Compile products details
        products_str = json.dumps(products_context or [], indent=2)
        
        # 2. Build session state context
        ss = session_state or {}
        session_state_str = json.dumps(ss, indent=2)

        # 3. Build the main user inquiry context (dynamic fields only)
        user_prompt = (
            f"Customer Name: {customer_name}\n"
            f"Customer Email: {email or 'N/A'}\n"
            f"Customer Phone: {phone or 'N/A'}\n"
            f"New Message Attachments: {attachment_context}\n\n"
            f"=== CONVERSATION STATE (Layer 2) ===\n{session_state_str}\n\n"
            f"Recent Conversation History:\n{conversation_history or 'No previous messages.'}\n\n"
            f"Customer's Order History:\n{orders_str}\n\n"
            f"Matching Store Products Catalog:\n{products_str}\n\n"
            f"Customer's New Message: \"{message_content}\"\n"
        )

        # 4. Build the system instructions containing the static guidelines
        system_instruction = (
            f"Instructions:\n"
            f"- FIRST, read and internalize the CONVERSATION STATE (Layer 2) above. It tells you: whether this is a new session, what you last asked the customer, what entity the customer just provided, whether the order lookup already completed, and how many orders were found. Use this structured state to drive your behavior — it is more reliable than guessing from raw text.\n"
            f"- Analyze the message content and conversation history.\n"
            f"- You MUST evaluate the conversation history and customer's message to determine: "
            f"1) The conversation priority (choose exactly one: urgent, high, medium, low based on customer frustration, sentiment, or handover requests). "
            f"2) The workflow labels to apply (choose one or more: 'in queue', 'awaiting', 'investigating', 'escalated to agent', 'needs reply', 'needs first reply').\n"
            f"At the very beginning of your response, you MUST output exactly `[PRIORITY: <priority>]`, `[LABELS: <label1, label2, ...>]`, and `[SOURCES: <source_id1, source_id2, ...>]` as separate tokens. "
            f"For the sources, identify the specific database ID(s) of any knowledge nuggets from the Store Knowledge Base context that you used or referenced to formulate your answer, and list them inside the `[SOURCES: ...]` block (e.g. `[SOURCES: 15, 161]`). If no specific knowledge nugget from the store knowledge base was referenced/used (for example, if you are just greeting the customer, asking for order details, recommending products from the catalog, or doing a human handover), you MUST output `[SOURCES: none]`. "
            f"For example: `[PRIORITY: urgent] [LABELS: awaiting, needs reply] [SOURCES: 15, 161]`. Then output your actual customer-facing response.\n"
            f"  * Strict Label Instruction: ONLY apply/output the 'investigating' label if you are explicitly triggering a handover due to a damaged/broken/wrong product complaint (or image upload). For all normal catalog, budget, collections, and general shopping inquiries, you MUST NOT output the 'investigating' label. Instead, choose 'awaiting' or 'in queue'.\n"
            f"- Regarding fulfillment and shipping status: If an order has a fulfillment status of \"tracking_added\" or \"tracking added\", you MUST NOT tell the customer that the order is \"shipped\", \"on its way\", or \"handed over to the courier\". Instead, explain that the order has been processed, the AWB (tracking number) has been assigned, and the package is currently being packed/prepared for shipping, but has NOT yet been manifested or physically handed over to our courier partner.\n"
            f"- Image Attachments & Damaged/Wrong Product Flow:\n"
            f"  a) If `New Message Attachments` is 'Yes, the customer has attached images/files.', you MUST immediately trigger a handover by responding with `[HANDOVER]`, output the label `investigating` (e.g. `[LABELS: investigating, escalated to agent]`), and politely inform the customer that you are connecting them to your manager to review the photos and assist them.\n"
            f"  b) If the customer complains about a damaged, broken, or wrong product in their text, but they have NOT sent images yet, you MUST politely ask them to send clear photos of the product so we can verify the issue. Meanwhile, tell them that you are transferring this chat to your manager and marking it as investigating so we can resolve this as quickly as possible once they send the images. You MUST trigger a handover by responding with `[HANDOVER]` and outputting the labels `investigating` and `escalated to agent` (e.g. `[LABELS: investigating, escalated to agent]`).\n"
            f"- Smart Handover Summaries: If you trigger `[HANDOVER]`, you MUST append a concise, professional summary at the very end of your response inside a `[HANDOVER_SUMMARY: <summary>]` block. The summary must describe: 1) why the customer contacted us in this recent interaction (focusing ONLY on the latest messages/turn, not summarizing old or resolved conversations from yesterday), 2) relevant order details (if any), and 3) the specific next action needed from the manager. Keep it short, adaptive, and highly focused on the immediate problem. For example: `[HANDOVER_SUMMARY: Customer Jatin reported a damaged Kundan Choker (Order #40364). Bot asked for photos and transferred. Action needed: Manager needs to review the photos once received and initiate exchange.]`.\n"
            f"- Order Queries & Identity Verification:\n"
            f"  a) ONLY perform identity verification if the customer is explicitly inquiring about a specific order's details, order status, or tracking (e.g. 'where is my order', 'status of order #123', or when they explicitly name an order number).\n"
            f"  b) For order-specific queries: If they inquire about a specific order, you MUST verify their identity before revealing any tracking links, item details, or specific order status. Check if the customer's messaging phone ({phone or 'N/A'}) or email ({email or 'N/A'}) matches the registered contact phone or email for that order in the context. If it does not match directly, check if the customer has provided their registered phone number or email address in the `Recent Conversation History` (e.g. in their latest or previous messages) and check if that typed contact info matches the registered contact info on the order in the database. If there is a match, you may immediately display the structured details and tracking link (no verification needed).\n"
            f"  c) If they are explicitly asking about an order but there is no match (or the order is missing from history), you MUST NOT reveal any details. Instead, politely explain that you cannot find or verify this order under their current contact info, and ask them to provide their registered email/phone number to look it up.\n"
            f"  d) For ALL non-order queries (e.g. greetings, product catalogs, collections, budget questions, general sizing/policies, etc.), you MUST completely ignore this order verification block and answer their query directly. Never ask for an order number or registered contact info unless they explicitly asked about an order first.\n"
            f"  e) IF the Conversation State shows `last_assistant_intent` = 'asked_for_identity_verification' AND `last_customer_entity` = 'phone_number' or 'email', the customer is answering YOUR previous verification request. Do NOT treat this as a new query. The system has ALREADY completed the database lookup. Check `orders_found` in the Conversation State: if > 0, use a soft transition like 'I checked that for you — here are your order details:' and IMMEDIATELY show the order details from Order History. If orders_found = 0, immediately say 'I checked that number but couldn't find any orders linked to it. Could you try another registered number or email?'. The SAME message MUST contain the result. NEVER imply another reply is coming later.\n"
            f"- Product Catalog & Image Recommendations:\n"
            f"  a) If `Matching Store Products Catalog` is provided and contains products, you MUST recommend these exact products to the customer! For each recommended product: display its name and price beautifully, provide its direct storefront URL in Markdown format (e.g. [View Product](https://thejanki.com/products/amara-drop-earrings)), and embed its high-quality image URL as a markdown image tag (e.g. ![Amara Drop Earrings](https://cdn.shopify.com/...)). This is critical so the customer sees the image preview in the chat!\n"
            f"  b) ONLY recommend and display products, links, and images that are explicitly provided in the `Matching Store Products Catalog`. NEVER guess, construct, or hallucinate links or image URLs. If the catalog matches is empty, politely explain that you don't have those items currently in stock or ask for more specifics.\n"
            f"- CONVERSATIONAL FLOW & GREETINGS: Check `is_new_session` in the Conversation State. If `is_new_session` is false, this is an active back-and-forth — You MUST NOT say 'Hello', 'Hi', 'Hey', or greet the customer in any way. Do not start with a greeting or transition phrase. Start your reply directly with the answer to their message. If `is_new_session` is true, you MAY greet the customer naturally but keep it lightweight (e.g., 'Hey [Name]!' or 'Hi again!'). NEVER use scripted greetings like 'Hello [Name]! Welcome to [Brand]'.\n"
            f"- Adapt your response length dynamically. If the conversation has been short or if it is on WhatsApp, keep your response short, clear, and direct (usually 1-3 sentences). Only provide detailed explanations if they explicitly ask for a full policy or complex query.\n"
            f"- If the customer's query cannot be answered using the facts and policies in your brand context, or if they explicitly ask to speak to a manager, you MUST trigger a handover by responding with exactly '[HANDOVER]' followed by a polite message connecting them (e.g., '[HANDOVER] Let me connect you with my manager right away to help you with this! 🙏'). Never guess or make up answers.\n"
            f"- If the customer asks for product recommendations, collections, links to specific products, or product photos/images, search for the exact URLs and image URLs in the Brand Context / Knowledge Nuggets. Respond by formatting the links beautifully in Markdown (e.g., [Gold Choker Collection](https://thejanki.com/collections/chokers)) and embed photos/images as markdown image tags (e.g., ![Kundan Gold Choker](cdn_image_url)). Only use exact URLs and image links that are explicitly stated in the Brand Context—NEVER invent, hallucinate, or construct fake URLs or image links.\n"
            f"\n!!! STRICT HANDOVER CRITICAL RULE !!!\n"
            f"If the customer explicitly requests to speak to a manager or person, you MUST begin your response with `[HANDOVER]` and append a `[HANDOVER_SUMMARY: <summary>]` block at the end. THIS IS AN ABSOLUTE MUST. DO NOT forget the brackets or omit the tags.\n"
            f"- Please draft the response based on the brand context and order details."
        )

        # 5. Handle Context Caching (Only for large contexts to avoid caching API overhead on smaller prompts)
        full_context = compile_agent_context(agent)
        cache_id = None
        if len(full_context) >= 100000:
            cache_id = get_or_create_gemini_cache(client, agent)
        
        if cache_id:
            # Generate response referencing the CachedContent
            logger.info("Generating content using Gemini Context Cache...")
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    # When context cache is active, it contains the system instructions and guidelines
                    cached_content=cache_id,
                    system_instruction=system_instruction,
                    thinking=types.ThinkingConfig(thinking_budget=0),
                )
            )
        else:
            # Fallback: Send full context in the system instruction
            logger.info("Generating content using fallback prompt injection...")
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=full_context + "\n\n" + system_instruction,
                    temperature=0.3,
                    thinking=types.ThinkingConfig(thinking_budget=0),
                )
            )
            
        ai_reply = response.text or ""
        
        if simulated:
            # Log simulated audit bot response
            AgentAuditLog.objects.create(
                agent=agent,
                role='bot',
                message=ai_reply
            )
            
        return ai_reply

    except Exception as e:
        logger.error(f"Support agent failed to generate response: {e}", exc_info=True)
        return "I apologize, but I am experiencing temporary difficulties retrieving the latest storefront guidelines. A human assistant has been notified to help you shortly."


def update_agent_instruction_via_directive(agent: AIAgent, manager_user, directive_text: str) -> str:
    """
    Directs a Meta-LLM prompt-coordinator to review the current brand guidelines and systems prompt,
    integrate the manager's live feedback/directive cleanly, write the updated instruction,
    and invalidate the Gemini Context cache to synchronize changes immediately.
    """
    # 1. Log manager input
    AgentAuditLog.objects.create(
        agent=agent,
        directed_by=manager_user,
        role='manager',
        message=directive_text
    )

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.error("GEMINI_API_KEY is not set.")
        # Fallback manual update
        previous_prompt = agent.system_prompt
        agent.system_prompt += f"\n- Additional Directive: {directive_text}"
        agent.gemini_cache_id = None
        agent.save(update_fields=['system_prompt', 'gemini_cache_id'])
        
        system_msg = "SOP updated (Manual fallback appended)."
        AgentAuditLog.objects.create(agent=agent, role='system', message=system_msg)
        return "Gemini API unavailable. Directively appended instruction manually."

    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        
        meta_prompt = (
            "You are a 'System Prompt Coordinator' for AI Agents. "
            "Your job is to review a bot's existing System Instruction prompt and integrate a manager's direct "
            "SOP directive cleanly, resolving any conflicting instructions, maintaining structure, and producing "
            "a highly polished final System Prompt.\n\n"
            f"=== CURRENT SYSTEM PROMPT ===\n{agent.system_prompt}\n\n"
            f"=== MANAGER'S NEW DIRECTIVE ===\n\"{directive_text}\"\n\n"
            "Task: Refactor the System Prompt to integrate the new directive logically. "
            "Keep the core brand identity, elegance, and formatting. "
            "Output ONLY the final, complete, refined system instruction text. Do not include introductory notes, chat wrappers or code blocks."
        )

        from core.utils.gemini_fallback import generate_content_with_fallback

        logger.info("Invoking Meta-LLM to refactor system instructions prompt...")
        response = generate_content_with_fallback(
            client=client,
            model='gemini-2.5-flash-lite',
            contents=meta_prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
            )
        )
        
        new_system_prompt = response.text.strip()
        if not new_system_prompt:
            raise ValueError("Meta-LLM returned empty prompt.")
            
        previous_prompt = agent.system_prompt
        agent.system_prompt = new_system_prompt
        agent.gemini_cache_id = None  # Force invalidate old context cache
        agent.save(update_fields=['system_prompt', 'gemini_cache_id'])
        
        # Extract visual summary of updated instructions
        confirm_prompt = (
            "Based on the new integrated guideline, provide a short, warm 1-2 sentence confirmation to the manager "
            "summarizing what behavior changes you have made. Address them directly and respectfully. "
            f"Integrated Directive: {directive_text}"
        )
        confirm_resp = generate_content_with_fallback(
            client=client,
            model='gemini-2.5-flash-lite',
            contents=confirm_prompt,
            config=types.GenerateContentConfig(temperature=0.5)
        )
        
        confirmation = confirm_resp.text.strip() or "Done! I've updated my guidelines as requested."
        
        # Log system confirmation
        AgentAuditLog.objects.create(
            agent=agent,
            role='system',
            message=f"Done, updated guidelines: {directive_text}"
        )
        
        return confirmation

    except Exception as e:
        logger.exception("Meta-LLM prompt refactoring failed")
        # Fallback safely
        agent.system_prompt += f"\n- Directive: {directive_text}"
        agent.gemini_cache_id = None
        agent.save(update_fields=['system_prompt', 'gemini_cache_id'])
        
        AgentAuditLog.objects.create(
            agent=agent,
            role='system',
            message=f"SOP updated (Manual fallback appended: {directive_text})"
        )
        return f"Done! I've updated my instructions: {directive_text}"
