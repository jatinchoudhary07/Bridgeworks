import logging
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from core.models import MarketingCredential, CampaignDailyMetric, MetaCampaign, MetaDemographicMetric
from core.utils.marketing_retry import execute_meta_api_with_retry

logger = logging.getLogger(__name__)

def fetch_meta_daily_metrics():
    """
    Background Django Q Task to fetch Meta (Facebook) Marketing API performance
    for all active credentials, spanning the last 14 days to handle late-attributions.
    Reuses the robust perform_meta_sync_for_credential logic to sync campaigns,
    ad sets, ads, and their daily metrics, then syncs demographic data.
    """
    logger.info("Starting Periodic Meta Marketing API Sync")
    
    # Get all active Meta credentials
    credentials = MarketingCredential.objects.filter(is_active=True, platform='Meta')
    
    if not credentials.exists():
        logger.info("No active Meta credentials found. Skipping sync.")
        return
        
    from core.views_marketing_sync import perform_meta_sync_for_credential
    from datetime import date as dt_date, timedelta as dt_delta
    
    today = dt_date.today()
    since_date = today - dt_delta(days=14)
    # List of date strings for last 14 days + today
    target_date_str_list = [(since_date + dt_delta(days=i)).isoformat() for i in range(15)]
    
    for cred in credentials:
        access_token = cred.get_access_token()
        app_id = cred.get_app_id()
        app_secret = cred.get_app_secret()
        ad_account_id = cred.ad_account_id
        
        if not access_token or not ad_account_id:
            logger.warning(f"Skipping Meta credential {cred.id} due to missing token or ad_account_id.")
            continue
            
        logger.info(f"Syncing Meta data in background for credential {cred.id} ({ad_account_id})...")
        
        try:
            # 1. Sync Campaigns, AdSets, Ads structural objects and daily metrics for last 14 days
            stats = perform_meta_sync_for_credential(cred, date_preset='last_14d')
            logger.info(f"Background sync stats for {ad_account_id}: {stats}")
            
            # 2. Sync Demographic metrics (age, gender) for last 14 days (one day at a time)
            FacebookAdsApi.init(app_id=app_id, app_secret=app_secret, access_token=access_token)
            account = AdAccount(ad_account_id)
            
            for date_str in target_date_str_list:
                try:
                    sync_meta_demographics(account, cred, date_str)
                except Exception as de:
                    logger.error(f"Failed to fetch Meta Demographics for {ad_account_id} on {date_str}: {str(de)}")
                    
        except Exception as e:
            logger.error(f"Failed to fetch background Meta data for credential {cred.id} ({ad_account_id}): {str(e)}")

    logger.info("Meta Marketing API Sync Completed.")

def sync_meta_demographics(account, cred, date_str):
    """
    Helper to fetch age and gender breakdowns for a specific date.
    """
    fields = ['spend', 'impressions', 'clicks', 'actions', 'action_values']
    
    # Process both Age and Gender
    for dimension in ['age', 'gender']:
        params = {
            'level': 'account',
            'breakdowns': [dimension],
            'time_range': {'since': date_str, 'until': date_str}
        }
        
        insights = execute_meta_api_with_retry(account.get_insights, fields=fields, params=params)
        
        for item in insights:
            dim_value = item.get(dimension, 'unknown')
            spend = Decimal(item.get('spend', '0.00'))
            impressions = int(item.get('impressions', '0'))
            clicks = int(item.get('clicks', '0'))
            
            # Extract purchases and revenue
            actions = item.get('actions', [])
            purchases = 0
            for a in actions:
                if a.get('action_type') == 'purchase' or a.get('action_type') == 'offsite_conversion.fb_pixel_purchase':
                    purchases += int(a.get('value', '0'))
            
            action_values = item.get('action_values', [])
            revenue = Decimal('0.00')
            for av in action_values:
                if av.get('action_type') == 'purchase' or av.get('action_type') == 'offsite_conversion.fb_pixel_purchase':
                    revenue += Decimal(av.get('value', '0.00'))
            
            MetaDemographicMetric.objects.update_or_create(
                credential=cred,
                date=date_str,
                dimension=dimension,
                dimension_value=dim_value,
                defaults={
                    'spend': spend,
                    'impressions': impressions,
                    'clicks': clicks,
                    'purchases': purchases,
                    'revenue': revenue
                }
            )
