import logging
import json
from django.core.management.base import BaseCommand
from core.models import ShopCredentials, ChannelDraftOrder, Order
from core.models.customers import Customer
from core.shopify_utils import get_shopify_session
from django.db.models import Q
import shopify as shopify_lib

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Fetch all historical Draft Orders from Shopify and sync to local database'

    def add_arguments(self, parser):
        parser.add_argument('--shop', type=str, help='Specific shop myshopify domain')

    def handle(self, *args, **options):
        shop_domain = options.get('shop')
        if shop_domain:
            shops = ShopCredentials.objects.filter(myshopify_domain=shop_domain)
        else:
            shops = ShopCredentials.objects.filter(onboarding_complete=True)

        for shop in shops:
            self.stdout.write(f"Syncing draft orders for {shop.myshopify_domain}...")
            try:
                session = get_shopify_session(shop.myshopify_domain, shop_creds=shop)
                shopify_lib.ShopifyResource.activate_session(session)
                
                # ── 1. Build Customer Mapping from existing Orders ─────────────────────
                self.stdout.write("Building customer mapping from existing orders (limit 2000)...")
                cust_map = {} # shopify_customer_id -> {name, email, phone}
                # We look at recently synced orders first to get the most accurate data
                recent_orders = Order.objects.filter(org_id=shop.organization_id).exclude(raw_data__isnull=True).only('raw_data', 'customer_first_name', 'customer_last_name', 'contact_email', 'contact_phone').order_by('-id')[:2000]
                for o in recent_orders:
                    try:
                        cid = o.raw_data.get('customer', {}).get('id')
                        if cid:
                            cid_str = str(cid)
                            if cid_str not in cust_map:
                                cust_map[cid_str] = {
                                    'name': f"{o.customer_first_name} {o.customer_last_name}".strip(),
                                    'email': o.contact_email,
                                    'phone': o.contact_phone
                                }
                    except Exception: continue
                self.stdout.write(f"Mapped {len(cust_map)} unique customers.")

                # ── 2. Fetch Draft Order -> Customer ID mapping via GraphQL ────────────
                self.stdout.write("Fetching Draft Order -> Customer ID mappings via GraphQL...")
                draft_to_cust_id = {} # shopify_draft_id -> shopify_customer_id
                gql_query = """
                {
                  draftOrders(first: 250) {
                    edges {
                      node {
                        id
                        customer { id }
                      }
                    }
                  }
                }
                """
                try:
                    gql_res = json.loads(shopify_lib.GraphQL().execute(gql_query))
                    edges = gql_res.get('data', {}).get('draftOrders', {}).get('edges', [])
                    for edge in edges:
                        node = edge.get('node', {})
                        did = node.get('id', '').split('/')[-1]
                        cid_obj = node.get('customer')
                        if did and cid_obj:
                            cid = cid_obj.get('id', '').split('/')[-1]
                            if cid:
                                draft_to_cust_id[did] = cid
                except Exception as gql_err:
                    self.stdout.write(self.style.WARNING(f"GraphQL fetch failed: {gql_err}"))

                # ── 3. Fetch Draft Orders via REST and Merge ───────────────────────────
                # Fetch draft orders with pagination
                params = {
                    'limit': 250,
                    'fields': 'id,customer,email,line_items,shipping_address,billing_address,total_price,completed_at,note,tags,invoice_url,created_at'
                }
                drafts = shopify_lib.DraftOrder.find(**params)
                
                count = 0
                while drafts:
                    for d in drafts:
                        draft_dict = d.to_dict()
                        customer = draft_dict.get('customer') or {}
                        shipping = draft_dict.get('shipping_address') or {}
                        billing = draft_dict.get('billing_address') or {}
                        
                        email = draft_dict.get('email') or customer.get('email') or ''
                        phone = customer.get('phone') or shipping.get('phone') or billing.get('phone') or ''
                        first_name = customer.get('first_name') or shipping.get('first_name') or billing.get('first_name') or ''
                        last_name = customer.get('last_name') or shipping.get('last_name') or billing.get('last_name') or ''
                        
                        full_name = f"{first_name} {last_name}".strip()
                        
                        # ── Customer Resolution Overrides ─────────────────────────────
                        # If REST returned Guest, try to resolve via our local mapping
                        did_str = str(draft_dict['id'])
                        mapped_cid = draft_to_cust_id.get(did_str)
                        if mapped_cid and mapped_cid in cust_map:
                            m_data = cust_map[mapped_cid]
                            if not full_name or full_name.lower() == 'guest':
                                full_name = m_data.get('name') or ''
                            if not email:
                                email = m_data.get('email') or ''
                            if not phone:
                                phone = m_data.get('phone') or ''

                        # Final safety check for nulls
                        full_name = full_name or 'Guest'
                        email = email or ''
                        phone = phone or ''

                        if full_name.lower() == 'guest':
                            # Try local lookup
                            lookups = Q()
                            if email: lookups |= Q(email=email)
                            if phone: lookups |= Q(phone=phone)
                            
                            if email or phone:
                                local_cust = Customer.objects.filter(org_id=shop.organization_id).filter(lookups).exclude(name__isnull=True).exclude(name='').first()
                                if local_cust:
                                    full_name = local_cust.name
                        
                        full_name = full_name or 'Guest'
                        
                        ChannelDraftOrder.objects.update_or_create(
                            shop=shop,
                            shopify_draft_id=str(draft_dict['id']),
                            defaults={
                                'channel': 'shopify',
                                'customer_name': full_name,
                                'customer_email': email or None,
                                'customer_phone': phone or None,
                                'line_items': draft_dict.get('line_items', []),
                                'shipping_address': shipping,
                                'total': draft_dict.get('total_price', 0),
                                'status': 'completed' if draft_dict.get('completed_at') else 'draft',
                                'note': draft_dict.get('note') or '',
                                'tags': draft_dict.get('tags') or '',
                                'invoice_url': draft_dict.get('invoice_url') or None,
                                'shopify_created_at': draft_dict.get('created_at'),
                            }
                        )
                        count += 1
                    
                    # Check for next page
                    if drafts.has_next_page():
                        drafts = drafts.next_page()
                    else:
                        break

                self.stdout.write(self.style.SUCCESS(f"Successfully synced {count} draft orders for {shop.myshopify_domain}"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to sync {shop.myshopify_domain}: {str(e)}"))
            finally:
                shopify_lib.ShopifyResource.clear_session()
