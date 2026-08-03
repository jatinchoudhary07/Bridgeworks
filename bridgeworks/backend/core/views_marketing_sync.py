from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.models import MarketingCredential, CampaignDailyMetric, AdSetDailyMetric, AdDailyMetric, MetaCampaign, MetaAdSet, MetaAd
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from decimal import Decimal
from core.utils.marketing_retry import execute_meta_api_with_retry
import logging
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)

def extract_action_value(array, action_type, key='value'):
    """Try exact match, then try with fb_pixel_ prefix for short names."""
    if not array:
        return "0"
    for entry in array:
        if entry.get('action_type') == action_type:
            return entry.get(key, "0")
    # Try with pixel prefix
    prefixed = 'offsite_conversion.fb_pixel_' + action_type
    for entry in array:
        if entry.get('action_type') == prefixed:
            return entry.get(key, "0")
    return "0"

def extract_safe_int(array, *action_types):
    """Extract int trying multiple possible action_type strings, first match wins."""
    if not array:
        return 0
    for at in action_types:
        for entry in array:
            if entry.get('action_type') == at:
                try:
                    return int(float(entry.get('value', '0')))
                except (ValueError, TypeError):
                    return 0
    return 0

def perform_meta_sync_for_credential(cred, start_date=None, end_date=None, date_preset=None, skip_structural=False):
    """
    Core logic to sync Meta data for a single credential.
    Supports either a specific date range (start_date/end_date) or a Meta date_preset.
    """
    access_token = cred.get_access_token()
    app_id = cred.get_app_id()
    app_secret = cred.get_app_secret()
    ad_account_id = cred.ad_account_id

    stats = {
        'campaigns': 0, 'adsets': 0, 'ads': 0, 'metrics': 0, 'errors': []
    }

    try:
        FacebookAdsApi.init(app_id=app_id, app_secret=app_secret, access_token=access_token)
        account = AdAccount(ad_account_id)
        
        logger.info(f"Starting Meta Sync for {ad_account_id} | Range: {start_date} to {end_date} | Preset: {date_preset}")

        # 1. Structural Objects (Optional Refresh)
        # -----------------------------------------------
        if not skip_structural:
            # Fetch Campaigns
            campaign_fields = ['id', 'name', 'status', 'effective_status', 'daily_budget', 'objective']
            campaigns = execute_meta_api_with_retry(account.get_campaigns, fields=campaign_fields, params={'limit': '500'})
            with transaction.atomic():
                for camp in campaigns:
                    camp_id = camp.get('id')
                    budget_str = camp.get('daily_budget', '0')
                    budget = int(budget_str) / 100 if budget_str else 0
                    if camp_id:
                        MetaCampaign.objects.update_or_create(
                            credential=cred, campaign_id=camp_id,
                            defaults={
                                'name': (camp.get('name') or 'Unknown')[:500],
                                'status': camp.get('status', 'UNKNOWN'),
                                'effective_status': camp.get('effective_status', 'UNKNOWN'),
                                'daily_budget': budget,
                                'objective': camp.get('objective', '')
                            }
                        )
                        stats['campaigns'] += 1

            # Fetch Ad Sets
            adset_fields = ['id', 'name', 'campaign_id', 'status', 'effective_status', 'daily_budget']
            adsets = execute_meta_api_with_retry(account.get_ad_sets, fields=adset_fields, params={'limit': '500'})
            with transaction.atomic():
                for adset in adsets:
                    adset_id = adset.get('id')
                    if adset_id:
                        budget_str = adset.get('daily_budget', '0')
                        budget = int(budget_str) / 100 if budget_str else 0
                        MetaAdSet.objects.update_or_create(
                            credential=cred, adset_id=adset_id,
                            defaults={
                                'campaign_id': adset.get('campaign_id', ''),
                                'name': (adset.get('name') or 'Unknown')[:500],
                                'status': adset.get('status', 'UNKNOWN'),
                                'effective_status': adset.get('effective_status', 'UNKNOWN'),
                                'daily_budget': budget,
                            }
                        )
                        stats['adsets'] += 1

            # Fetch Ads
            ad_fields = ['id', 'name', 'adset_id', 'campaign_id', 'status', 'effective_status']
            ads = execute_meta_api_with_retry(account.get_ads, fields=ad_fields, params={'limit': '500'})
            with transaction.atomic():
                for ad in ads:
                    ad_id = ad.get('id')
                    if ad_id:
                        MetaAd.objects.update_or_create(
                            credential=cred, ad_id=ad_id,
                            defaults={
                                'adset_id': ad.get('adset_id', ''),
                                'campaign_id': ad.get('campaign_id', ''),
                                'name': (ad.get('name') or 'Unknown')[:500],
                                'status': ad.get('status', 'UNKNOWN'),
                                'effective_status': ad.get('effective_status', 'UNKNOWN'),
                            }
                        )
                        stats['ads'] += 1

        # 2. Insights (Daily Metrics)
        # -----------------------------------------------
        _base_fields = [
            'spend', 'impressions', 'clicks', 'date_start', 'date_stop',
            'cpc', 'cpm', 'ctr', 'reach', 'actions', 'action_values',
            'purchase_roas', 'cost_per_action_type', 'outbound_clicks'
        ]
        
        # Prepare params
        params = {'time_increment': 1}
        if start_date and end_date:
            params['time_range'] = {'since': str(start_date), 'until': str(end_date)}
        else:
            # Shift presets to explicit time_ranges to include TODAY (Meta defaults exclude today)
            from datetime import date as dt_date, timedelta as dt_delta
            preset_to_use = date_preset or 'last_30d'
            today = dt_date.today()
            
            days_map = {
                'today': 0, 'yesterday': 1, 'last_3d': 3, 'last_7d': 7, 
                'last_14d': 14, 'last_28d': 28, 'last_30d': 30, 'last_90d': 90,
                'maximum': 730 # 2 years
            }
            
            if preset_to_use in days_map:
                days = days_map[preset_to_use]
                since = (today - dt_delta(days=days)).isoformat()
                params['time_range'] = {'since': since, 'until': today.isoformat()}
            else:
                params['date_preset'] = preset_to_use

        # Fetch Campaign Level
        camp_fields_insights = ['campaign_id', 'campaign_name'] + _base_fields
        insights = list(execute_meta_api_with_retry(account.get_insights, fields=camp_fields_insights, params={**params, 'level': 'campaign'}))
        logger.info(f"Insights: Fetched {len(insights)} campaign-level rows for {ad_account_id}")
        
        with transaction.atomic():
            for item in insights:
                cid = item.get('campaign_id')
                metric_date = item.get('date_start')
                if not cid or not metric_date: continue
                
                actions = item.get('actions', [])
                CampaignDailyMetric.objects.update_or_create(
                    credential=cred, date=metric_date, campaign_id=cid,
                    defaults={
                        'campaign_name': (item.get('campaign_name') or item.get('name') or f"Campaign {cid}")[:500],
                        'spend': Decimal(item.get('spend', '0.00')),
                        'impressions': int(item.get('impressions', '0')),
                        'clicks': int(item.get('clicks', '0')),
                        'cpc': Decimal(item.get('cpc', '0.00')),
                        'cpm': Decimal(item.get('cpm', '0.00')),
                        'ctr': Decimal(item.get('ctr', '0.0000')),
                        'reach': int(item.get('reach', 0) or 0),
                        'purchases': extract_safe_int(actions, 'purchase', 'offsite_conversion.fb_pixel_purchase'),
                        'revenue': Decimal(extract_action_value(item.get('action_values', []), 'purchase')),
                        'roas': Decimal(extract_action_value(item.get('purchase_roas', []), 'omni_purchase')),
                        'cost_per_purchase_cpa': Decimal(extract_action_value(item.get('cost_per_action_type', []), 'purchase')),
                        'view_content': extract_safe_int(actions, 'offsite_conversion.fb_pixel_view_content', 'view_content'),
                        'add_to_cart': extract_safe_int(actions, 'offsite_conversion.fb_pixel_add_to_cart', 'add_to_cart'),
                        'initiate_checkout': extract_safe_int(actions, 'offsite_conversion.fb_pixel_initiate_checkout', 'initiate_checkout'),
                        'add_payment_info': extract_safe_int(actions, 'offsite_conversion.fb_pixel_add_payment_info', 'add_payment_info'),
                        'engagement': extract_safe_int(actions, 'post_engagement', 'page_engagement'),
                        'outbound_clicks': extract_safe_int(item.get('outbound_clicks', []), 'outbound_click'),
                    }
                )
                stats['metrics'] += 1

        # Fetch AdSet Level
        adset_fields_insights = ['adset_id', 'adset_name', 'campaign_id'] + _base_fields
        as_insights = list(execute_meta_api_with_retry(account.get_insights, fields=adset_fields_insights, params={**params, 'level': 'adset'}))
        logger.info(f"Insights: Fetched {len(as_insights)} adset-level rows for {ad_account_id}")
        
        with transaction.atomic():
            for item in as_insights:
                asid = item.get('adset_id')
                metric_date = item.get('date_start')
                if not asid or not metric_date: continue
                
                actions = item.get('actions', [])
                AdSetDailyMetric.objects.update_or_create(
                    credential=cred, date=metric_date, adset_id=asid,
                    defaults={
                        'adset_name': (item.get('adset_name') or item.get('name') or f"AdSet {asid}")[:500],
                        'campaign_id': item.get('campaign_id', ''),
                        'spend': Decimal(item.get('spend', '0.00')),
                        'impressions': int(item.get('impressions', '0')),
                        'clicks': int(item.get('clicks', '0')),
                        'cpc': Decimal(item.get('cpc', '0.00')),
                        'cpm': Decimal(item.get('cpm', '0.00')),
                        'ctr': Decimal(item.get('ctr', '0.0000')),
                        'reach': int(item.get('reach', 0) or 0),
                        'purchases': extract_safe_int(actions, 'purchase', 'offsite_conversion.fb_pixel_purchase'),
                        'revenue': Decimal(extract_action_value(item.get('action_values', []), 'purchase')),
                        'roas': Decimal(extract_action_value(item.get('purchase_roas', []), 'omni_purchase')),
                        'cost_per_purchase_cpa': Decimal(extract_action_value(item.get('cost_per_action_type', []), 'purchase')),
                        'view_content': extract_safe_int(actions, 'offsite_conversion.fb_pixel_view_content', 'view_content'),
                        'add_to_cart': extract_safe_int(actions, 'offsite_conversion.fb_pixel_add_to_cart', 'add_to_cart'),
                        'initiate_checkout': extract_safe_int(actions, 'offsite_conversion.fb_pixel_initiate_checkout', 'initiate_checkout'),
                        'add_payment_info': extract_safe_int(actions, 'offsite_conversion.fb_pixel_add_payment_info', 'add_payment_info'),
                        'engagement': extract_safe_int(actions, 'post_engagement', 'page_engagement'),
                        'outbound_clicks': extract_safe_int(item.get('outbound_clicks', []), 'outbound_click'),
                    }
                )

        # Fetch Ad Level
        ad_fields_insights = ['ad_id', 'ad_name', 'adset_id', 'campaign_id'] + _base_fields
        ad_insights = list(execute_meta_api_with_retry(account.get_insights, fields=ad_fields_insights, params={**params, 'level': 'ad'}))
        logger.info(f"Insights: Fetched {len(ad_insights)} ad-level rows for {ad_account_id}")
        
        with transaction.atomic():
            for item in ad_insights:
                aid = item.get('ad_id') or item.get('id')
                metric_date = item.get('date_start')
                if not aid or not metric_date: continue
                
                actions = item.get('actions', [])
                AdDailyMetric.objects.update_or_create(
                    credential=cred, date=metric_date, ad_id=aid,
                    defaults={
                        'ad_name': (item.get('ad_name') or item.get('name') or f"Ad {aid}")[:500],
                        'adset_id': item.get('adset_id', ''),
                        'campaign_id': item.get('campaign_id', ''),
                        'spend': Decimal(item.get('spend', '0.00')),
                        'impressions': int(item.get('impressions', '0')),
                        'clicks': int(item.get('clicks', '0')),
                        'cpc': Decimal(item.get('cpc', '0.00')),
                        'cpm': Decimal(item.get('cpm', '0.00')),
                        'ctr': Decimal(item.get('ctr', '0.0000')),
                        'reach': int(item.get('reach', 0) or 0),
                        'purchases': extract_safe_int(actions, 'purchase', 'offsite_conversion.fb_pixel_purchase'),
                        'revenue': Decimal(extract_action_value(item.get('action_values', []), 'purchase')),
                        'roas': Decimal(extract_action_value(item.get('purchase_roas', []), 'omni_purchase')),
                        'cost_per_purchase_cpa': Decimal(extract_action_value(item.get('cost_per_action_type', []), 'purchase')),
                        'view_content': extract_safe_int(actions, 'offsite_conversion.fb_pixel_view_content', 'view_content'),
                        'add_to_cart': extract_safe_int(actions, 'offsite_conversion.fb_pixel_add_to_cart', 'add_to_cart'),
                        'initiate_checkout': extract_safe_int(actions, 'offsite_conversion.fb_pixel_initiate_checkout', 'initiate_checkout'),
                        'add_payment_info': extract_safe_int(actions, 'offsite_conversion.fb_pixel_add_payment_info', 'add_payment_info'),
                        'engagement': extract_safe_int(actions, 'post_engagement', 'page_engagement'),
                        'outbound_clicks': extract_safe_int(item.get('outbound_clicks', []), 'outbound_click'),
                    }
                )

    except Exception as e:
        logger.error(f"Meta sync error for {ad_account_id}: {str(e)}")
        stats['errors'].append(f"{ad_account_id}: {str(e)}")

    return stats

def perform_meta_sync_for_shop(shop, start_date=None, end_date=None, date_preset='last_30d', skip_structural=False):
    """
    Wrapper to sync all active Meta credentials for a shop.
    """
    creds = MarketingCredential.objects.filter(shop=shop, platform='Meta', is_active=True)
    results = []
    for cred in creds:
        res = perform_meta_sync_for_credential(cred, start_date, end_date, date_preset, skip_structural)
        results.append(res)
    return results

from core.permissions import IsMarketingAnalyst

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def trigger_meta_sync(request):
    from core.views_marketing import _get_org # Reuse helper if available, else use local _get_shop
    shop = _get_org(request)
    if not shop:
        return Response({'error': 'No organization found.'}, status=400)

    # Default to last_90d for manual triggers to ensure 'all data' is captured
    date_preset = request.data.get('date_preset', 'last_90d')
    results = perform_meta_sync_for_shop(shop, date_preset=date_preset)
    
    total_c = sum(r['campaigns'] for r in results)
    total_as = sum(r['adsets'] for r in results)
    total_ad = sum(r['ads'] for r in results)
    total_m = sum(r['metrics'] for r in results)
    all_errors = []
    for r in results: all_errors.extend(r['errors'])

    return Response({
        'detail': f'Synced {total_c} campaigns, {total_as} ad sets, {total_ad} ads, and {total_m} metrics.',
        'errors': all_errors if all_errors else None
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsMarketingAnalyst])
def trigger_google_ads_sync(request):
    from core.views_marketing import _get_org
    from core.tasks.google_ads_sync import sync_google_ads_for_shop

    shop = _get_org(request)
    if not shop:
        return Response({'error': 'No organization found.'}, status=400)
        
    start_date = request.data.get('start_date')
    end_date = request.data.get('end_date')

    results = sync_google_ads_for_shop(shop, start_date=start_date, end_date=end_date)

    if not results:
        return Response({'error': 'No active Google Ads credentials found. Add them in Settings first.'}, status=400)

    total_updates = sum(r['updates'] for r in results)
    errors = [r['error'] for r in results if r['error']]

    return Response({
        'detail': f'Google Ads sync complete: {total_updates} campaign-day records updated across all categories.',
        'errors': errors if errors else None
    })
