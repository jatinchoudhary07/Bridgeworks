import logging
import re
import threading
from datetime import datetime
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from .models import Order, Fulfillment, TrackingEvent

logger = logging.getLogger(__name__)

# Regex patterns based on your logs
# Matches: "Jan 24, 2026 02:10 pm"
DATE_PATTERN = r"([A-Z][a-z]{2} \d{1,2}, \d{4} \d{2}:\d{2} [ap]m)" 
# Matches: "Arriving by Jan 31, Saturday"
ARRIVAL_PATTERN = r"(Arriving by .*)"

def parse_shipway_date(date_str):
    """Converts 'Jan 24, 2026 02:10 pm' to a Python datetime object."""
    try:
        # Parse format: Mon DD, YYYY HH:MM am/pm
        dt = datetime.strptime(date_str, "%b %d, %Y %I:%M %p")
        return timezone.make_aware(dt)
    except Exception as e:
        logger.error(f"Date parse error: {e}")
        return timezone.now()

def run_shipway_scraper(fulfillment_id, tracking_url):
    """
    Background task to scrape Shipway and update TrackingEvents.
    """
    driver = None
    try:
        logger.info(f"Starting Scraper for Fulfillment ID: {fulfillment_id}")
        
        # 1. Setup Headless Chrome
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        # Optimization: Block images/css to load faster
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        
        # 2. Navigate and Wait
        driver.get(tracking_url)
        # Wait strictly for content (adjust based on real-world speed)
        driver.implicitly_wait(10) 
        
        # 3. Extract Text
        body_text = driver.find_element("tag name", "body").text
        lines = body_text.split('\n')
        
        # 4. Process Data
        fulfillment = Fulfillment.objects.get(id=fulfillment_id)
        events_found = 0
        arrival_estimate = None

        for line in lines:
            line = line.strip()
            
            # A. Check for "Arriving by"
            arrival_match = re.search(ARRIVAL_PATTERN, line)
            if arrival_match:
                arrival_estimate = arrival_match.group(1)
                continue

            # B. Check for Timeline Events (Date at start)
            date_match = re.match(DATE_PATTERN, line)
            if date_match:
                raw_date = date_match.group(1)
                # The rest of the line is the Status + Location
                # Log: "Jan 24... pm Pickup scheduled Jaipur..."
                # content = "Pickup scheduled Jaipur..."
                content = line.replace(raw_date, "").strip()
                
                # Simple heuristic: Split by first space to guess Status vs Details
                # This isn't perfect but works for "Manifest uploaded ..."
                parts = content.split(' ', 2)
                status_guess = content # Default to full string
                details_guess = ""
                
                if len(parts) > 1:
                    # heuristic: first 3 words are status, rest details? 
                    # Let's just save the whole text as status for safety, 
                    # or split strictly if we know the patterns.
                    status_guess = content 

                dt_obj = parse_shipway_date(raw_date)

                # Save to DB (Use get_or_create to avoid duplicates)
                TrackingEvent.objects.get_or_create(
                    fulfillment=fulfillment,
                    status=status_guess, 
                    datetime=dt_obj,
                    defaults={'details': details_guess}
                )
                events_found += 1

        # 5. Save "Arriving By" (Insert as a special event or update order)
        if arrival_estimate:
            # We insert it as the latest "System" event so it shows at the top of the UI
            TrackingEvent.objects.update_or_create(
                fulfillment=fulfillment,
                status="Estimated Arrival",
                defaults={
                    'datetime': timezone.now(),
                    'details': arrival_estimate
                }
            )

        # 6. Update Order Status based on latest scrape
        fulfillment.order.update_tracking_status()
        
        logger.info(f"Scraper Success: Found {events_found} events. Estimate: {arrival_estimate}")

    except Exception as e:
        logger.error(f"Scraper Failed for {tracking_url}: {e}")
    finally:
        if driver:
            driver.quit()

def start_scraping_thread(fulfillment_id, tracking_url):
    """Helper to launch scraper in background thread"""
    t = threading.Thread(target=run_shipway_scraper, args=(fulfillment_id, tracking_url))
    t.daemon = True # Ensures thread dies if main app dies
    t.start()


def crawl_and_parse_website(base_url, max_pages=150):
    """
    Recursively scrapes up to max_pages on same-domain links starting from base_url.
    Cleans tags and extracts title and textual content.
    Returns: list of dicts [{'url': url, 'title': title, 'content': content}]
    """
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse, urljoin

    parsed_base = urlparse(base_url)
    base_domain = parsed_base.netloc
    
    visited = set()
    to_visit = [base_url]
    results = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    logger.info(f"Starting crawl for website: {base_url}")
    
    while to_visit and len(visited) < max_pages:
        current_url = to_visit.pop(0)
        
        # Standardize URL
        if current_url.endswith('/'):
            current_url = current_url[:-1]
            
        if current_url in visited:
            continue
            
        visited.add(current_url)
        logger.info(f"Crawling link ({len(visited)}/{max_pages}): {current_url}")
        
        try:
            resp = requests.get(current_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
                
            content_type = resp.headers.get('Content-Type', '')
            if 'text/html' not in content_type:
                continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Remove scripts, css, menus, footers
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
                
            title = soup.title.string.strip() if soup.title else current_url
            
            # Extract clean paragraphs and headers
            text_blocks = []
            for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'li']):
                txt = element.get_text().strip()
                if txt and len(txt) > 20:  # avoid short noise
                    text_blocks.append(txt)
                    
            content = "\n\n".join(text_blocks)
            
            if len(content) > 100:  # Valid page content found
                results.append({
                    'url': current_url,
                    'title': title,
                    'content': content
                })
                
            # Extract and filter sub-links
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                absolute_url = urljoin(current_url, href)
                parsed_abs = urlparse(absolute_url)
                
                # Check same domain, standard protocols and avoid query/anchors
                if parsed_abs.netloc == base_domain and parsed_abs.scheme in ('http', 'https'):
                    cleaned_link = absolute_url.split('#')[0].split('?')[0]
                    if cleaned_link.endswith('/'):
                        cleaned_link = cleaned_link[:-1]
                    if cleaned_link not in visited and cleaned_link not in to_visit:
                        # Prioritize pages likely to have info (about, policies, faq, help, products)
                        to_visit.append(cleaned_link)
                        
        except Exception as e:
            logger.warning(f"Error crawling link {current_url}: {e}")
            
    logger.info(f"Crawl completed. Successfully crawled and parsed {len(results)} pages.")
    return results