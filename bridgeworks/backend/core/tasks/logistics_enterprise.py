"""
logistics_enterprise.py — Celery Tasks for Logistics Enterprise Features
========================================================================
Two periodic tasks:

1. auto_detect_exceptions_task   — Daily (runs at 2AM)
   Scans all active org shipments for:
   - Lost: In Transit > 15 days
   - Delayed: Past SLA promised days (requires CourierSLAContract)
   - MissingScan: No TrackingEvent in > 3 days
   Creates ShipmentException records automatically.

2. recompute_customer_risk_profiles_task — Weekly (runs Sunday midnight)
   Recomputes CustomerRiskProfile for all customers with order activity
   in the last 90 days.

Django-Q scheduling (add to settings.py Q_CLUSTER schedule or run manually):
    {
        'name': 'auto_detect_exceptions',
        'func': 'core.tasks.logistics_enterprise.auto_detect_exceptions_task',
        'cron': '0 2 * * *',   # 2:00 AM daily
    },
    {
        'name': 'recompute_customer_risk_profiles',
        'func': 'core.tasks.logistics_enterprise.recompute_customer_risk_profiles_task',
        'cron': '0 0 * * 0',   # Midnight every Sunday
    }
"""
import logging

logger = logging.getLogger(__name__)


def _get_active_org_ids():
    """Return a list of all active organization IDs from ShopCredentials."""
    try:
        from core.models import ShopCredentials
        return list(
            ShopCredentials.objects.filter(owner__is_active=True)
            .values_list('organization_id', flat=True)
            .distinct()
        )
    except Exception as e:
        logger.error(f"[LOGISTICS-TASKS] Failed to get active org IDs: {e}")
        return []


def auto_detect_exceptions_task():
    """
    Celery/Django-Q Task: Auto-detect shipment exceptions for all active orgs.

    Runs daily. Creates ShipmentException records for:
    - Lost: In Transit > 15 days with no delivery
    - Delayed: Delivered past SLA promised days (requires CourierSLAContract)
    - MissingScan: No TrackingEvent in > 3 days for in-transit shipment

    Skips shipments that already have an open exception of the same type.
    """
    from core.services.exception_service import auto_detect_exceptions

    org_ids = _get_active_org_ids()
    if not org_ids:
        logger.warning("[EXCEPTION-TASK] No active orgs found. Skipping.")
        return

    total_created = 0
    total_skipped = 0

    for org_id in org_ids:
        try:
            created, skipped = auto_detect_exceptions(org_id)
            total_created += created
            total_skipped += skipped
            logger.info(
                f"[EXCEPTION-TASK] Org {org_id}: {created} exceptions created, {skipped} skipped"
            )
        except Exception as e:
            logger.error(
                f"[EXCEPTION-TASK] Failed for org {org_id}: {e}", exc_info=True
            )

    logger.info(
        f"[EXCEPTION-TASK] Complete. Total: {total_created} created, {total_skipped} skipped "
        f"across {len(org_ids)} orgs."
    )
    return {'created': total_created, 'skipped': total_skipped, 'orgs': len(org_ids)}


def recompute_customer_risk_profiles_task(days_back: int = 90):
    """
    Celery/Django-Q Task: Recompute CustomerRiskProfile for all active orgs.

    Runs weekly. Processes all customers with order activity in the
    last `days_back` days (default: 90).

    Risk Formula:
        score = (rto_rate*40 + refusal_rate*25 + cod_rate*20 + (1 - delivery_rate)*15) * 100
    """
    from core.services.customer_risk_service import bulk_recompute

    org_ids = _get_active_org_ids()
    if not org_ids:
        logger.warning("[RISK-TASK] No active orgs found. Skipping.")
        return

    total_updated = 0

    for org_id in org_ids:
        try:
            count = bulk_recompute(org_id, days_back=days_back)
            total_updated += count
            logger.info(
                f"[RISK-TASK] Org {org_id}: {count} risk profiles updated"
            )
        except Exception as e:
            logger.error(
                f"[RISK-TASK] Failed for org {org_id}: {e}", exc_info=True
            )

    logger.info(
        f"[RISK-TASK] Complete. Total: {total_updated} profiles updated "
        f"across {len(org_ids)} orgs."
    )
    return {'profiles_updated': total_updated, 'orgs': len(org_ids)}


def sync_weather_alerts_task():
    """
    Celery/Django-Q Task: Sync live weather alerts from Gemini using Google Search Grounding.
    Runs every 6 hours to capture regional weather disruption patterns.
    """
    from core.services.weather_service import sync_weather_alerts_via_gemini

    logger.info("[WEATHER-TASK] Starting weather sync via Gemini...")
    result = sync_weather_alerts_via_gemini()
    if 'error' in result:
        logger.error(f"[WEATHER-TASK] Weather sync failed: {result['error']}")
    else:
        logger.info(f"[WEATHER-TASK] Weather sync completed successfully: {result}")
    return result
