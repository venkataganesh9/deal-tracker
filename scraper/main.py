# scraper/main.py
import os
import re
import random
import time
import json
import hashlib
from datetime import datetime
from playwright.sync_api import sync_playwright
import firebase_admin
from firebase_admin import credentials, firestore
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def init_firebase():
    """Initialize Firebase with multiple credential loading methods"""
    try:
        # Method 1: Direct environment variable (GitHub Actions)
        service_account = os.getenv("FIREBASE_SERVICE_ACCOUNT")
        if service_account:
            logger.info("ℹ️ Using FIREBASE_SERVICE_ACCOUNT environment variable")
            with open("serviceAccountKey.json", "w") as f:
                f.write(service_account)
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            return firestore.client()
        
        # Method 2: Individual environment variables (fallback)
        logger.info("ℹ️ Trying individual environment variables")
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
        })
        firebase_admin.initialize_app(cred)
        return firestore.client()
    
    except Exception as e:
        logger.error(f"❌ Firebase initialization failed: {e}")
        raise

def scrape_amazon_deals():
    """Scrape deals from Amazon"""
    logger.info("🚀 Starting Amazon deals scraping...")
    deals = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        
        try:
            # Navigate to deals page
            page.goto("https://www.amazon.com/deals", timeout=60000)
            logger.info("✅ Loaded Amazon deals page")
            
            # Wait for deals container
            page.wait_for_selector('div[data-testid="deal-card"]', timeout=60000)
            logger.info("✅ Deals container loaded")
            
            # Scroll to load more deals
            for i in range(3):
                page.mouse.wheel(0, 10000)
                time.sleep(random.uniform(1.5, 3))
                logger.info(f"🔄 Scrolled page ({i+1}/3)")
            
            # Extract deals
            deal_cards = page.query_selector_all('div[data-testid="deal-card"]')
            logger.info(f"🔍 Found {len(deal_cards)} deals")
            
            # Process each deal
            for card in deal_cards:
                try:
                    # Extract deal information
                    title = card.query_selector('h2').inner_text().strip()
                    
                    # Price handling
                    current_price_elem = card.query_selector('.a-price .a-offscreen')
                    current_price = current_price_elem.get_attribute('aria-label') if current_price_elem else None
                    
                    original_price_elem = card.query_selector('.a-text-price .a-offscreen')
                    original_price = original_price_elem.inner_text() if original_price_elem else None
                    
                    # Clean prices
                    def clean_price(price_str):
                        if not price_str: return None
                        try: return float(re.sub(r'[^\d.]', '', price_str))
                        except: return None
                    
                    current_price = clean_price(current_price)
                    original_price = clean_price(original_price)
                    
                    # Calculate discount
                    discount_percent = 0
                    if current_price and original_price and original_price > 0:
                        discount_percent = int((1 - current_price / original_price) * 100)
                    
                    # Get URL and image
                    link = card.query_selector('a[href]')
                    url = "https://amazon.com" + link.get_attribute('href') if link else None
                    img = card.query_selector('img')
                    image_url = img.get_attribute('src') if img else None
                    
                    # Add affiliate tag
                    affiliate_tag = os.getenv("AMAZON_ASSOCIATE_TAG", "")
                    affiliate_url = f"{url}?tag={affiliate_tag}" if url and affiliate_tag else url
                    
                    # Create deal object
                    deal = {
                        "id": hashlib.md5((title + str(current_price)).encode()).hexdigest(),
                        "title": title,
                        "current_price": current_price,
                        "original_price": original_price,
                        "discount_percent": discount_percent,
                        "affiliate_url": affiliate_url,
                        "image_url": image_url,
                        "source": "Amazon",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    deals.append(deal)
                    logger.info(f"✔ Processed: {title[:50]}...")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing deal: {str(e)[:100]}")
        
        except Exception as e:
            logger.error(f"🚨 Scraping failed: {e}")
        finally:
            browser.close()
    
    logger.info(f"🎉 Successfully scraped {len(deals)} deals")
    return deals

def save_to_firestore(deals, db):
    """Save deals to Firestore"""
    if not deals:
        logger.warning("⚠️ No deals to save")
        return
    
    batch = db.batch()
    collection_ref = db.collection('deals')
    
    for deal in deals:
        doc_ref = collection_ref.document(deal['id'])
        batch.set(doc_ref, deal)
    
    batch.commit()
    logger.info(f"💾 Saved {len(deals)} deals to Firestore")

def main():
    start_time = time.time()
    logger.info("🚀 Starting deal scraping process")
    
    try:
        # Initialize Firebase
        db = init_firebase()
        logger.info("🔥 Firebase initialized successfully")
        
        # Scrape and save deals
        deals = scrape_amazon_deals()
        save_to_firestore(deals, db)
        
        duration = time.time() - start_time
        logger.info(f"🏁 Completed in {duration:.2f} seconds")
        return 0
        
    except Exception as e:
        logger.error(f"💥 Critical error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)