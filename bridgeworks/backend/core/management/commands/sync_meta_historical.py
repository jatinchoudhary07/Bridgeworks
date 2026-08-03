import time
from datetime import date, timedelta
from decimal import Decimal
import logging
from django.core.management.base import BaseCommand
from core.models import MarketingCredential, CampaignDailyMetric, AdSetDailyMetric, AdDailyMetric, MetaCampaign, MetaAdSet, MetaAd

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fetches maximum historical meta marketing data (bypasses rate limits and timeout issues)'

    def add_arguments(self, parser):
        parser.add_argument('--shop-id', type=str, help='Shop ID to sync. Defaults to all active shops.')
        parser.add_argument('--days', type=int, default=None, help='Number of days back to sync (e.g. 7 for last 7 days). Defaults to full 18-month history.')

    def handle(self, *args, **options):
        shop_id = options.get('shop_id')
        
        credentials = MarketingCredential.objects.filter(platform='Meta', is_active=True)
        if shop_id:
            credentials = credentials.filter(shop_id=shop_id)

        if not credentials.exists():
            self.stdout.write(self.style.ERROR('No active Meta credentials found.'))
            return

        from facebook_business.api import FacebookAdsApi
        from facebook_business.adobjects.adaccount import AdAccount

        self.stdout.write(self.style.SUCCESS(f"Found {credentials.count()} active Meta credentials. Starting deep sync..."))

        total_updates = 0

        # Build date chunks — either a short window (--days N) or full 18-month history
        today = date.today()
        date_chunks = []
        days_arg = options.get('days')

        if days_arg:
            # Short mode: single chunk covering the last N days
            since = today - timedelta(days=days_arg)
            date_chunks = [(str(since), str(today))]
            self.stdout.write(self.style.WARNING(f"Syncing last {days_arg} days only ({since} → {today})"))
        else:
            # Full mode: 18 monthly chunks (approx 1.5 years)
            # Doing smaller chunks stops Meta from throwing Code 1 "Data too large" error
            end = today
            for _ in range(18):
                start = end.replace(day=1)
                if start > end:
                    start = end - timedelta(days=29)
                date_chunks.append((str(start), str(end)))
                end = start - timedelta(days=1)
            date_chunks = list(reversed(date_chunks))

        _base_fields = [
            'spend', 'impressions', 'clicks', 'cpc', 'cpm', 'ctr',
            'reach', 'actions', 'action_values',
            'purchase_roas', 'cost_per_action_type', 'outbound_clicks'
        ]
        
        level_fields = {
            'campaign': ['campaign_id', 'campaign_name'] + _base_fields,
            'adset':    ['campaign_id', 'adset_id', 'adset_name'] + _base_fields,
            'ad':       ['campaign_id', 'adset_id', 'ad_id', 'ad_name'] + _base_fields,
        }

        for cred in credentials:
            self.stdout.write(self.style.WARNING(f"\n--- Processing Ad Account: {cred.ad_account_id} ---"))
            
            try:
                FacebookAdsApi.init(app_id=cred.get_app_id(), app_secret=cred.get_app_secret(), access_token=cred.get_access_token())
                account = AdAccount(cred.ad_account_id)
                
                self.stdout.write(self.style.SUCCESS("Starting historical insights..."))

                for level in ['campaign', 'adset', 'ad']:
                    fields = level_fields[level]
                    
                    self.stdout.write(f"  Level: {level.capitalize()}...")
                    for chunk_since, chunk_until in date_chunks:
                        params = {
                            'level': level,
                            'time_range': {'since': chunk_since, 'until': chunk_until},
                            'time_increment': 1,
                        }
                        
                        try:
                            items = self._call_with_retry(account.get_insights, fields=fields, params=params)
                            
                            c = 0
                            for item in items:
                                if self._process_insight_item(item, level, cred):
                                    c += 1
                                    total_updates += 1
                                    
                            if c > 0:
                                self._print_inline(f"    {chunk_since} -> {chunk_until}: {c} metrics added")
                                
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"    Error on chunk {chunk_since} to {chunk_until}: {str(e)}"))
                            
                        # Mandatory sleep to prevent Meta throwing Code 17
                        time.sleep(1)
                    print()
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Fatal error on account {cred.ad_account_id}: {str(e)}"))

        self.stdout.write(self.style.SUCCESS(f"\nDone! Completely synced {total_updates} historical metrics."))


    def _print_inline(self, text):
        import sys
        sys.stdout.write(f"\r{text}")
        sys.stdout.flush()

    def _call_with_retry(self, fn, *args, max_retries=3, **kwargs):
        for attempt in range(max_retries):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                msg = str(exc)
                if '"code": 17' in msg or 'code 17' in msg.lower() or 'request limit' in msg.lower():
                    wait = 60 * (attempt + 1)
                    self.stdout.write(self.style.WARNING(f"\n    [!] Rate Limit Hit! Sleeping {wait}s to cool off..."))
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError(f"Meta API call failed after {max_retries} retries.")

    def _process_insight_item(self, item, level, cred):
        metric_date = item.get('date_start')
        if not metric_date:
            return False

        spend = Decimal(item.get('spend', '0.00') or '0.00')
        impressions = int(item.get('impressions', '0') or 0)
        clicks = int(item.get('clicks', '0') or 0)
        cpc = Decimal(item.get('cpc', '0.00') or '0.00')
        cpm = Decimal(item.get('cpm', '0.00') or '0.00')
        ctr = Decimal(item.get('ctr', '0.0000') or '0.0000')
        reach = int(item.get('reach', 0) or 0)

        actions = item.get('actions', []) or []
        purchases = self._extract_safe_int(actions, 'purchase', 'offsite_conversion.fb_pixel_purchase')
        revenue = Decimal(self._extract_action_value(item.get('action_values', []), 'purchase'))
        roas = Decimal(self._extract_action_value(item.get('purchase_roas', []), 'omni_purchase'))
        cpa = Decimal(self._extract_action_value(item.get('cost_per_action_type', []), 'purchase'))

        engagement = self._extract_safe_int(actions, 'post_engagement', 'page_engagement')
        vc = self._extract_safe_int(actions, 'offsite_conversion.fb_pixel_view_content', 'view_content')
        atc = self._extract_safe_int(actions, 'offsite_conversion.fb_pixel_add_to_cart', 'add_to_cart')
        ic = self._extract_safe_int(actions, 'offsite_conversion.fb_pixel_initiate_checkout', 'initiate_checkout')
        api_ = self._extract_safe_int(actions, 'offsite_conversion.fb_pixel_add_payment_info', 'add_payment_info')
        ob_clicks = self._extract_safe_int(item.get('outbound_clicks', []) or [], 'outbound_click')

        base = dict(
            spend=spend, impressions=impressions, clicks=clicks,
            cpc=cpc, cpm=cpm, ctr=ctr,
            purchases=purchases, revenue=revenue, roas=roas,
            cost_per_purchase_cpa=cpa,
            reach=reach, engagement=engagement, view_content=vc,
            add_to_cart=atc, initiate_checkout=ic,
            add_payment_info=api_, outbound_clicks=ob_clicks,
        )

        if level == 'campaign':
            campaign_name = item.get('campaign_name') or item.get('name') or 'Unknown'
            CampaignDailyMetric.objects.update_or_create(credential=cred, date=metric_date, campaign_id=item.get('campaign_id'), defaults={**base, 'campaign_name': campaign_name[:500]})
        elif level == 'adset':
            if not item.get('adset_id'): return False
            adset_name = item.get('adset_name') or item.get('name') or 'Unknown'
            AdSetDailyMetric.objects.update_or_create(credential=cred, date=metric_date, adset_id=item.get('adset_id'), defaults={**base, 'adset_name': adset_name[:500], 'campaign_id': item.get('campaign_id', '')})
        elif level == 'ad':
            if not item.get('ad_id'): return False
            ad_name = item.get('ad_name') or item.get('name') or 'Unknown'
            AdDailyMetric.objects.update_or_create(credential=cred, date=metric_date, ad_id=item.get('ad_id'), defaults={**base, 'ad_name': ad_name[:500], 'adset_id': item.get('adset_id', ''), 'campaign_id': item.get('campaign_id', '')})
        return True

    def _extract_action_value(self, array, action_type, key='value'):
        if not array: return "0"
        for entry in array:
            if entry.get('action_type') == action_type: return entry.get(key, "0")
        for entry in array:
            if entry.get('action_type') == 'offsite_conversion.fb_pixel_' + action_type: return entry.get(key, "0")
        return "0"

    def _extract_safe_int(self, array, *action_types):
        if not array: return 0
        for at in action_types:
            for entry in array:
                if entry.get('action_type') == at:
                    try: return int(float(entry.get('value', '0')))
                    except: return 0
        return 0
