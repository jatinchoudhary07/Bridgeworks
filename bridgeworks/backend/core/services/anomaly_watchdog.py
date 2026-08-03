"""
Anomaly Watchdog — AI-Driven Metric Anomaly Detection
======================================================
Compares yesterday's CPA/ROAS against a 7-day moving average.
If CPA increases by >20% or ROAS drops by >20%, calls Gemini to
generate a 2-sentence alert and saves it to MarketingAlert.
"""
import logging
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum, Avg
from datetime import timedelta
from django.conf import settings

logger = logging.getLogger(__name__)


def check_metric_anomalies(shop):
    """
    Core anomaly detection for a single shop.
    Compares yesterday's metrics against the 7-day moving average.
    """
    from core.models import CampaignDailyMetric, MarketingAlert

    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=8)  # 7 days before yesterday

    # --- Yesterday's Metrics ---
    yesterday_qs = CampaignDailyMetric.objects.filter(
        credential__shop=shop,
        credential__platform='Meta',
        date=yesterday
    )
    yesterday_stats = yesterday_qs.aggregate(
        total_spend=Sum('spend'),
        total_revenue=Sum('revenue'),
        total_purchases=Sum('purchases'),
    )

    y_spend = yesterday_stats['total_spend'] or Decimal('0.00')
    y_revenue = yesterday_stats['total_revenue'] or Decimal('0.00')
    y_purchases = yesterday_stats['total_purchases'] or 0

    if y_spend == 0:
        logger.info(f"[Watchdog] No spend data for {shop.organization_id} on {yesterday}. Skipping.")
        return None

    y_cpa = float(y_spend / y_purchases) if y_purchases > 0 else 0
    y_roas = float(y_revenue / y_spend) if y_spend > 0 else 0

    # --- 7-Day Moving Average (excluding yesterday) ---
    week_qs = CampaignDailyMetric.objects.filter(
        credential__shop=shop,
        credential__platform='Meta',
        date__gte=week_start,
        date__lt=yesterday
    )

    # Get daily aggregates first, then average
    from django.db.models.functions import TruncDate
    daily_aggs = week_qs.values('date').annotate(
        daily_spend=Sum('spend'),
        daily_revenue=Sum('revenue'),
        daily_purchases=Sum('purchases'),
    )

    if not daily_aggs.exists():
        logger.info(f"[Watchdog] Not enough historical data for {shop.organization_id}. Skipping.")
        return None

    # Calculate averages
    total_days = daily_aggs.count()
    avg_spend = sum(float(d['daily_spend'] or 0) for d in daily_aggs) / total_days
    avg_purchases = sum(int(d['daily_purchases'] or 0) for d in daily_aggs) / total_days
    avg_revenue = sum(float(d['daily_revenue'] or 0) for d in daily_aggs) / total_days

    avg_cpa = avg_spend / avg_purchases if avg_purchases > 0 else 0
    avg_roas = avg_revenue / avg_spend if avg_spend > 0 else 0

    # --- Anomaly Detection ---
    alerts_generated = []

    cpa_delta_pct = ((y_cpa - avg_cpa) / avg_cpa * 100) if avg_cpa > 0 else 0
    roas_delta_pct = ((y_roas - avg_roas) / avg_roas * 100) if avg_roas > 0 else 0

    anomaly_detected = False
    anomaly_details = []

    if cpa_delta_pct > 20:
        anomaly_detected = True
        anomaly_details.append(f"CPA increased by {cpa_delta_pct:.1f}% (₹{y_cpa:.2f} vs 7-day avg ₹{avg_cpa:.2f})")

    if roas_delta_pct < -20:
        anomaly_detected = True
        anomaly_details.append(f"ROAS dropped by {abs(roas_delta_pct):.1f}% ({y_roas:.2f}x vs 7-day avg {avg_roas:.2f}x)")

    if not anomaly_detected:
        logger.info(f"[Watchdog] No anomalies for {shop.organization_id}. CPA delta: {cpa_delta_pct:.1f}%, ROAS delta: {roas_delta_pct:.1f}%")
        return None

    # --- Generate AI Alert via Gemini ---
    gemini_prompt = (
        f"You are a marketing analyst for an e-commerce brand. "
        f"Yesterday's Meta Ads performance showed concerning changes: "
        f"{'; '.join(anomaly_details)}. "
        f"Yesterday: Spend ₹{y_spend}, Revenue ₹{y_revenue}, {y_purchases} purchases. "
        f"Generate a concise 2-sentence alert message for the brand owner. "
        f"First sentence: state what happened. Second sentence: suggest one quick action they can take."
    )

    ai_message = _call_gemini(gemini_prompt)

    # Determine alert type and severity
    alert_type = 'cpa_spike' if cpa_delta_pct > 20 else 'roas_drop'
    severity = 'critical' if (cpa_delta_pct > 40 or roas_delta_pct < -40) else 'warning'

    # Save alert
    alert = MarketingAlert.objects.create(
        shop=shop,
        alert_type=alert_type,
        severity=severity,
        title=f"AI Alert: {anomaly_details[0].split('(')[0].strip()}",
        message=ai_message,
        metric_data={
            'date': str(yesterday),
            'yesterday': {
                'spend': float(y_spend),
                'revenue': float(y_revenue),
                'purchases': y_purchases,
                'cpa': round(y_cpa, 2),
                'roas': round(y_roas, 2),
            },
            'seven_day_avg': {
                'cpa': round(avg_cpa, 2),
                'roas': round(avg_roas, 2),
            },
            'deltas': {
                'cpa_delta_pct': round(cpa_delta_pct, 1),
                'roas_delta_pct': round(roas_delta_pct, 1),
            }
        }
    )

    logger.info(f"[Watchdog] Alert generated for {shop.organization_id}: {alert.title}")
    return alert


def _call_gemini(prompt):
    """
    Call the Gemini API to generate an alert message.
    Falls back to a template message if the API is unavailable.
    """
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        logger.warning("[Watchdog] No GEMINI_API_KEY configured. Using template alert.")
        return "Your Meta Ads metrics are trending down compared to the 7-day average. Review your top-spending campaigns and consider pausing underperformers."

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"[Watchdog] Gemini API call failed: {e}")
        return "Your Meta Ads metrics are trending down compared to the 7-day average. Review your top-spending campaigns and consider pausing underperformers."


def run_watchdog_for_all_shops():
    """
    Django-Q compatible task: runs the anomaly watchdog for all shops
    with active Meta credentials. Designed to be scheduled daily.
    """
    from core.models import MarketingCredential

    logger.info("[Watchdog] Starting daily anomaly detection run...")

    # Get unique shops with active Meta credentials
    shops = set()
    for cred in MarketingCredential.objects.filter(is_active=True, platform='Meta'):
        shops.add(cred.shop)

    alerts_count = 0
    for shop in shops:
        try:
            result = check_metric_anomalies(shop)
            if result:
                alerts_count += 1
        except Exception as e:
            logger.error(f"[Watchdog] Error processing {shop.organization_id}: {e}", exc_info=True)

    logger.info(f"[Watchdog] Daily run completed. {alerts_count} alerts generated for {len(shops)} shops.")
    return f"Processed {len(shops)} shops, generated {alerts_count} alerts"
