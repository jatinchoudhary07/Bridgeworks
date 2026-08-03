import logging
from core.models import Order

# Shared retry delays
RETRY_DELAYS = {
    1: 10,
    2: 30,
}


def evaluate_order_task(order_id, attempt=1):
    """
    Django-Q Background Task: Evaluates an order using the Gemini AI Agent.
    
    SMART RETRY: If contact_phone is missing (PII not yet fetched from Shipway),
    the task re-schedules itself in 10 minutes instead of wasting a Gemini API call.
    Max 3 attempts before running with whatever data is available.
    """
    MAX_ATTEMPTS = 3
    logger = logging.getLogger(__name__)

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning(f"[AI-AGENT] Order {order_id} not found. Aborting evaluation.")
        return f"SKIP: Order {order_id} not found"

    has_phone = bool(order.contact_phone and order.contact_phone.strip())
    has_email = bool(order.contact_email and order.contact_email.strip())

    # If Shipway PII sync is skipped/disabled, we don't expect updates from Shipway.
    # Run evaluation with available data rather than scheduling retries.
    skip_shipway_pii = False
    try:
        from core.models import ShopCredentials
        shop_cred = ShopCredentials.objects.get(organization_id=order.org_id)
        if shop_cred.skip_shipway_pii_sync:
            skip_shipway_pii = True
    except Exception:
        pass

    if not has_phone and not has_email and attempt < MAX_ATTEMPTS and not skip_shipway_pii:
        delay_minutes = RETRY_DELAYS.get(attempt, 30)
        logger.info(
            f"[AI-AGENT] ⏳ Order #{order.order_number}: No phone/email found "
            f"(attempt {attempt}/{MAX_ATTEMPTS}). Retrying in {delay_minutes} min..."
        )
        from django_q.tasks import schedule
        from django.utils import timezone
        from datetime import timedelta
        schedule(
            'core.tasks.evaluate_order_task',
            order_id,
            attempt=attempt + 1,
            next_run=timezone.now() + timedelta(minutes=delay_minutes)
        )
        return f"RETRY: Missing phone/email. Scheduled attempt {attempt + 1} for {delay_minutes}m."

    if not has_phone and not has_email:
        logger.warning(
            f"[AI-AGENT] ⚠️ Order #{order.order_number}: Still no phone/email after "
            f"{MAX_ATTEMPTS} attempts. Running agent with available data."
        )

    logger.info(
        f"[AI-AGENT] Starting evaluation for Order #{order.order_number} "
        f"(attempt {attempt}/{MAX_ATTEMPTS}, phone={'✅' if has_phone else '❌'}, "
        f"email={'✅' if has_email else '❌'})"
    )

    try:
        from core.services.ai_agent import run_gemini_agent

        verdict = run_gemini_agent(order)

        order.risk_score = verdict.risk_score
        order.intelligence_flag = verdict.intelligence_flag
        order.system_suggestion = f"Recommended Courier: {verdict.recommended_courier}"
        order.agent_reasoning = verdict.agent_reasoning
        order.confirmation_reason = verdict.confirmation_reason if verdict.is_confirmed else None
        order.hold_reason = verdict.hold_reason if not verdict.is_confirmed else None
        
        # If the agent decided not to confirm, put the order on hold
        if not verdict.is_confirmed:
            order.status = "On Hold"

        order.save(update_fields=[
            'risk_score',
            'intelligence_flag',
            'system_suggestion',
            'agent_reasoning',
            'confirmation_reason',
            'hold_reason',
            'status',
        ])

        try:
            from core.tasks.order_automation import auto_confirm_if_eligible
            auto_confirm_if_eligible(order)
        except Exception as auto_err:
            logger.error(f"[AI-AGENT] Failed auto-confirm call for Order #{order.order_number}: {auto_err}", exc_info=True)

        logger.info(
            f"[AI-AGENT] ✅ Order #{order.order_number} evaluated: "
            f"Score={verdict.risk_score}, Flag={verdict.intelligence_flag}, "
            f"Courier={verdict.recommended_courier}"
        )
        return (
            f"✅ Order #{order.order_number}: Score={verdict.risk_score}, "
            f"Flag={verdict.intelligence_flag}, Courier={verdict.recommended_courier}, "
            f"Reasoning={verdict.agent_reasoning[:100]}"
        )

    except Exception as e:
        logger.error(f"[AI-AGENT] ❌ Failed to evaluate Order #{order.order_number}: {e}", exc_info=True)
        order.risk_score = 50
        order.intelligence_flag = 'YELLOW'
        order.system_suggestion = 'Recommended Courier: Standard'
        order.agent_reasoning = f'AI Agent Error - Requires Manual Review. Error: {str(e)[:200]}'
        order.confirmation_reason = None
        order.hold_reason = f'AI Agent Error: {str(e)[:200]}'
        order.save(update_fields=[
            'risk_score',
            'intelligence_flag',
            'system_suggestion',
            'agent_reasoning',
            'confirmation_reason',
            'hold_reason',
        ])
        return f"❌ Order #{order.order_number}: FAILED — {str(e)[:150]}"


def scrape_agent_website_task(agent_id, custom_url=None):
    """
    Django-Q Background Task to crawl and scrape the merchant's storefront pages.
    Populates KnowledgeNugget models with text extracted from policies/FAQ/about sections.
    Automatically handles next run scheduling if recurring scraping is active.
    """
    import json
    import logging
    from django.utils import timezone
    from datetime import timedelta
    from django_q.tasks import schedule
    
    from core.models import AIAgent, KnowledgeNugget, ShopCredentials
    from core.scrapers import crawl_and_parse_website

    logger = logging.getLogger(__name__)
    
    try:
        agent = AIAgent.objects.get(pk=agent_id)
    except AIAgent.DoesNotExist:
        logger.error(f"[AI-SCRAPE] Agent {agent_id} not found. Aborting.")
        return f"SKIP: Agent {agent_id} not found"

    # Determine URL to scrape
    url_to_scrape = custom_url
    if not url_to_scrape:
        # Fallback to ShopCredentials
        try:
            shop = ShopCredentials.objects.get(organization_id=agent.organization_id)
            url_to_scrape = shop.get_shopify_shop_url()
        except Exception:
            pass

    if not url_to_scrape:
        logger.error(f"[AI-SCRAPE] No URL configured or found for organization: {agent.organization_id}")
        return "FAILED: No scraping URL available"

    logger.info(f"[AI-SCRAPE] Starting scraping execution for agent: {agent.name} on URL: {url_to_scrape}")
    
    try:
        pages = crawl_and_parse_website(url_to_scrape, max_pages=150)
        
        # Keep track of imported URLs to clean duplicates
        imported_count = 0
        
        for page in pages:
            page_url = page['url']
            page_title = page['title']
            page_content = page['content']
            
            # Clean duplicate nuggets with exact same URL
            existing = KnowledgeNugget.objects.filter(agent=agent, source_type='url')
            for nugget in existing:
                metadata = nugget.get_metadata_dict()
                if metadata.get('url') == page_url:
                    nugget.delete()
            
            # Create fresh nugget
            n = KnowledgeNugget.objects.create(
                agent=agent,
                source_type='url',
                title=page_title[:255] if page_title else "",
                content=page_content,
                is_active=True
            )
            n.set_metadata_dict({'url': page_url})
            n.save()
            imported_count += 1
            
        # Update scrape timestamp and reset Gemini cache pointer
        agent.last_scraped_at = timezone.now()
        agent.gemini_cache_id = None
        agent.save(update_fields=['last_scraped_at', 'gemini_cache_id'])
        
        # Schedule next recurring task if active
        if agent.recurring_scraping:
            delay_days = 7 if agent.scraping_interval == 'weekly' else 30
            next_run = timezone.now() + timedelta(days=delay_days)
            logger.info(f"[AI-SCRAPE] Scheduling next recurring scrape for agent {agent.name} at {next_run}")
            
            schedule(
                'core.tasks.ai_evaluation.scrape_agent_website_task',
                agent_id,
                next_run=next_run
            )
            
        logger.info(f"[AI-SCRAPE] Successfully finished scraping agent website. Imported {imported_count} pages.")
        return f"SUCCESS: Crawled {url_to_scrape}. Imported {imported_count} pages."

    except Exception as e:
        logger.error(f"[AI-SCRAPE] Scraping execution failed: {e}", exc_info=True)
        return f"FAILED: Scraping failed due to error: {str(e)}"

