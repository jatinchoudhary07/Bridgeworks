import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from core.models import (
    GoogleAdsCredential, GoogleCampaignDailyMetric, 
    GoogleSearchTermMetric, GoogleDemographicMetric, 
    GoogleAdPerformanceMetric
)
from decimal import Decimal

logger = logging.getLogger(__name__)

def parse_is(val):
    """Parse impression share strings like '0.45' or '< 10%' to Decimal."""
    if not val or val == '--':
        return None
    # Google Ads API sometimes returns floats directly for certain IS metrics
    if not isinstance(val, str):
        try:
            return Decimal(str(val))
        except:
            return None
    if '<' in val:
        return Decimal('0.0999') # Represent < 10% as 9.99%
    if '>' in val:
        return Decimal('0.9001') # Represent > 90% as 90.01%
    try:
        return Decimal(val)
    except:
        return None

def sync_google_ads_credential(cred, start_date=None, end_date=None):
    """
    Core sync logic for a single Google Ads credential.
    Fetches Campaign, Search Term, Demographic, and Ad performance.
    """
    status = {'updates': 0, 'error': None}
    try:
        google_creds = {
            "developer_token": cred.get_developer_token(),
            "client_id": cred.client_id,
            "client_secret": cred.get_client_secret(),
            "refresh_token": cred.get_refresh_token(),
            "login_customer_id": cred.login_customer_id,
            "use_proto_plus": True
        }

        client = GoogleAdsClient.load_from_dict(google_creds)
        ga_service = client.get_service("GoogleAdsService")
        customer_id = cred.customer_id

        if start_date and end_date:
            where_clause = f"WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        else:
            where_clause = "WHERE segments.date DURING LAST_30_DAYS"

        # Define worker functions for parallel execution
        def run_campaign_query():
            try:
                query = f"""
                    SELECT segments.date, campaign.name, metrics.impressions, metrics.clicks,
                           metrics.cost_micros, metrics.conversions, metrics.conversions_value,
                           metrics.search_impression_share, metrics.search_budget_lost_impression_share
                    FROM campaign {where_clause}
                """
                # Re-fetch service instance for the thread if possible, or use the existing one
                res = ga_service.search(customer_id=customer_id, query=query)
                local_updates = 0
                for row in res:
                    GoogleCampaignDailyMetric.objects.update_or_create(
                        credential=cred, date=row.segments.date, campaign_name=row.campaign.name[:500] if row.campaign.name else "Unknown",
                        defaults={
                            'impressions': row.metrics.impressions,
                            'clicks': row.metrics.clicks,
                            'spend': row.metrics.cost_micros / 1000000,
                            'conversions': row.metrics.conversions,
                            'revenue': row.metrics.conversions_value,
                            'search_impression_share': parse_is(row.metrics.search_impression_share),
                            'search_budget_lost_impression_share': parse_is(row.metrics.search_budget_lost_impression_share),
                        }
                    )
                    local_updates += 1
                return local_updates
            except Exception as e:
                logger.error(f"Campaign Query Failed: {str(e)}")
                return 0

        def run_search_term_query():
            try:
                query = f"SELECT segments.date, campaign.name, search_term_view.search_term, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM search_term_view {where_clause} AND metrics.clicks > 0"
                res = ga_service.search(customer_id=customer_id, query=query)
                for row in res:
                    GoogleSearchTermMetric.objects.update_or_create(
                        credential=cred, date=row.segments.date, 
                        campaign_name=row.campaign.name[:500] if row.campaign.name else "Unknown", search_term=row.search_term_view.search_term[:500] if row.search_term_view.search_term else "Unknown",
                        defaults={
                            'clicks': row.metrics.clicks, 'spend': row.metrics.cost_micros / 1000000,
                            'conversions': row.metrics.conversions, 'revenue': row.metrics.conversions_value,
                        }
                    )
            except Exception as e:
                logger.error(f"Search Term Query Failed: {str(e)}")

        def run_gender_query():
            try:
                query = f"SELECT segments.date, ad_group_criterion.gender.type, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM gender_view {where_clause}"
                res = ga_service.search(customer_id=customer_id, query=query)
                count = 0
                for row in res:
                    dim_val = row.ad_group_criterion.gender.type_.name
                    GoogleDemographicMetric.objects.update_or_create(
                        credential=cred, date=row.segments.date, dimension='gender', dimension_value=dim_val,
                        defaults={
                            'clicks': row.metrics.clicks, 'spend': row.metrics.cost_micros / 1000000,
                            'conversions': row.metrics.conversions, 'revenue': row.metrics.conversions_value,
                        }
                    )
                    count += 1
                logger.info(f"Gender Sync: {count} rows for {customer_id}")
            except Exception as e:
                logger.error(f"Gender Query Failed: {str(e)}")

        def run_age_query():
            try:
                query = f"SELECT segments.date, ad_group_criterion.age_range.type, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM age_range_view {where_clause}"
                res = ga_service.search(customer_id=customer_id, query=query)
                count = 0
                for row in res:
                    dim_val = row.ad_group_criterion.age_range.type_.name
                    GoogleDemographicMetric.objects.update_or_create(
                        credential=cred, date=row.segments.date, dimension='age', dimension_value=dim_val,
                        defaults={
                            'clicks': row.metrics.clicks, 'spend': row.metrics.cost_micros / 1000000,
                            'conversions': row.metrics.conversions, 'revenue': row.metrics.conversions_value,
                        }
                    )
                    count += 1
                logger.info(f"Age Sync: {count} rows for {customer_id}")
            except Exception as e:
                logger.error(f"Age Query Failed: {str(e)}")

        def run_device_query():
            try:
                query = f"SELECT segments.date, segments.device, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value FROM campaign {where_clause}"
                res = ga_service.search(customer_id=customer_id, query=query)
                count = 0
                for row in res:
                    GoogleDemographicMetric.objects.update_or_create(
                        credential=cred, date=row.segments.date, dimension='device', dimension_value=row.segments.device.name,
                        defaults={
                            'clicks': row.metrics.clicks, 'spend': row.metrics.cost_micros / 1000000,
                            'conversions': row.metrics.conversions, 'revenue': row.metrics.conversions_value,
                        }
                    )
                    count += 1
                logger.info(f"Device Sync: {count} rows for {customer_id}")
            except Exception as e:
                logger.error(f"Device Query Failed: {str(e)}")

        def run_ad_query():
            try:
                # Expanded query to include Shopping ad fields if applicable
                query = f"""
                    SELECT segments.date, campaign.name, ad_group.name, ad_group_ad.ad.id,
                           ad_group_ad.ad.type,
                           ad_group_ad.ad.responsive_search_ad.headlines,
                           ad_group_ad.ad.responsive_search_ad.descriptions,
                           metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value
                    FROM ad_group_ad {where_clause} AND metrics.impressions > 0
                """
                res = ga_service.search(customer_id=customer_id, query=query)
                for row in res:
                    headlines = []
                    descriptions = []
                    
                    # Handle RSA
                    if hasattr(row.ad_group_ad.ad, 'responsive_search_ad') and row.ad_group_ad.ad.responsive_search_ad.headlines:
                        headlines = [h.text for h in row.ad_group_ad.ad.responsive_search_ad.headlines]
                        descriptions = [d.text for d in row.ad_group_ad.ad.responsive_search_ad.descriptions]
                    
                    # Fallback for Shopping or other types
                    if not headlines:
                        ad_type = row.ad_group_ad.ad.type_.name
                        headlines = [f"{ad_type.replace('_', ' ').title()}"]
                        descriptions = ["Product-based Shopping Ad" if "SHOPPING" in ad_type else "Dynamic Ad Content"]

                    GoogleAdPerformanceMetric.objects.update_or_create(
                        credential=cred, date=row.segments.date, ad_id=str(row.ad_group_ad.ad.id),
                        defaults={
                            'campaign_name': row.campaign.name[:500] if row.campaign.name else "Unknown", 'ad_group_name': row.ad_group.name[:500] if row.ad_group.name else "Unknown",
                            'headlines': headlines, 'descriptions': descriptions,
                            'clicks': row.metrics.clicks, 'spend': row.metrics.cost_micros / 1000000,
                            'conversions': row.metrics.conversions, 'revenue': row.metrics.conversions_value,
                        }
                    )
            except Exception as e:
                logger.error(f"Ad Query Failed: {str(e)}")

        # Execute queries in parallel to fix slow request (from 40s -> ~8s)
        tasks = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            tasks.append(executor.submit(run_campaign_query))
            tasks.append(executor.submit(run_search_term_query))
            tasks.append(executor.submit(run_gender_query))
            tasks.append(executor.submit(run_age_query))
            tasks.append(executor.submit(run_device_query))
            tasks.append(executor.submit(run_ad_query))
            
            for future in as_completed(tasks):
                res = future.result()
                if isinstance(res, int):
                    status['updates'] += res

        logger.info(f"Successfully synced expanded Google Ads for {customer_id}: {status['updates']} campaign rows.")

    except GoogleAdsException as ex:
        err_msg = f"API error: {ex.error.code().name}"
        logger.error(f"Google Ads API failed for {cred.customer_id}: {err_msg}")
        status['error'] = err_msg
    except Exception as e:
        logger.error(f"Unexpected error during Google Ads sync for {cred.customer_id}: {str(e)}")
        status['error'] = str(e)

    return status

def sync_google_ads_for_shop(shop, start_date=None, end_date=None):
    creds = GoogleAdsCredential.objects.filter(shop=shop, is_active=True)
    results = [sync_google_ads_credential(cred, start_date, end_date) for cred in creds]
    return results

def fetch_google_ads_daily_metrics():
    logger.info("Starting Global Google Ads API Sync")
    for cred in GoogleAdsCredential.objects.filter(is_active=True):
        sync_google_ads_credential(cred)
    logger.info("Global Google Ads Sync Completed.")
