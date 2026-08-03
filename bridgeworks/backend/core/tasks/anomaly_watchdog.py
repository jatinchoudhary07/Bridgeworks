"""
Marketing Anomaly Watchdog — Django-Q Scheduled Task
=====================================================
Runs daily to check for CPA/ROAS anomalies across all shops
with active Meta credentials. Generates AI-powered alerts.

Schedule this in Django-Q admin:
  func: core.tasks.anomaly_watchdog.run_daily_watchdog
  schedule_type: DAILY
  next_run: <tomorrow at midnight IST>
"""
import logging

logger = logging.getLogger(__name__)


def run_daily_watchdog():
    """
    Django-Q task entry point.
    Wraps the service-layer function for the task runner.
    """
    from core.services.anomaly_watchdog import run_watchdog_for_all_shops

    logger.info("[Task] Starting daily marketing anomaly watchdog...")
    result = run_watchdog_for_all_shops()
    logger.info(f"[Task] Watchdog completed: {result}")
    return result
