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

# Initialize Firebase
def init_firebase():
    # Service account will be provided via GitHub secret
    service_account = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if not service_account:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT environment variable not set")
    
    # Write to temporary file
    with open("serviceAccountKey.json", "w") as f:
        f.write(service_account)
    
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    return firestore.client()

# Scrape Amazon deals
def scrape_amazon_deals():
    print("🚀 Starting Amazon deals scraping...")
    deals = []
    
    with sync_playwright() as p:
        # Configure browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        
        # Navigate to deals page
        page.goto("https://www.amazon.com/deals", timeout=60000)
        print("✅ Loaded Amazon deals page")
        
        # Wait for deals to load
        page.wait_for_selector('div[data-testid="deal-card"]', timeout=60000)
        print("✅ Deals container loaded")
        
        # Scroll to load more deals (3 times)
        for i in range(3):
            page.mouse.wheel(0, 10000)
            time.sleep(random.uniform(1.5, 3))
            print(f"🔄 Scrolled page ({i+1}/3)")
        
        # Extract all deal cards
        deal_cards = page.query_selector_all('div[data-testid="deal-card"]')
        print(f"🔍 Found {len(deal_cards)} deals")
        
        # Process each deal
        for card in deal_cards:
            try:
                title = card.query_selector('h2').inner_text().strip()
                
                # Price handling
                current_price_elem = card.query_selector('.a-price .a-offscreen')
                current_price = current_price_elem.get_attribute('aria-label') if current_price_elem else None
                
                original_price_elem = card.query_selector('.a-text-price .a-offscreen')
                original_price = original_price_elem.inner_text() if original_price_elem else None
                
                # Clean prices
                def clean_price(price_str):
                    if not price_str:
                        return None
                    try:
                        return float(re.sub(r'[^\d.]', '', price_str))
                    except:
                        return None
                
                current_price = clean_price(current_price)
                original_price = clean_price(original_price)
                
                # Calculate discount
                discount_percent = 0
                if current_price and original_price and original_price > 0:
                    discount_percent = round((1 - current_price / original_price) * 100)
                
                # Get URL
                link = card.query_selector('a[href]')
                url = "https://amazon.com" + link.get_attribute('href') if link else None
                
                # Get image
                img = card.query_selector('img')
                image_url = img.get_attribute('src') if img else None
                
                # Add affiliate tag
                affiliate_tag = os.getenv("AMAZON_ASSOCIATE_TAG")
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
                print(f"✔ Processed: {title[:50]}...")
                
            except Exception as e:
                print(f"❌ Error processing deal: {str(e)[:100]}")
        
        # Close browser
        browser.close()
    
    print(f"🎉 Successfully scraped {len(deals)} deals")
    return deals

# Save deals to Firestore
def save_to_firestore(deals, db):
    if not deals:
        print("⚠️ No deals to save")
        return
    
    batch = db.batch()
    collection_ref = db.collection('deals')
    
    for deal in deals:
        doc_ref = collection_ref.document(deal['id'])
        batch.set(doc_ref, deal)
    
    batch.commit()
    print(f"💾 Saved {len(deals)} deals to Firestore")

def main():
    start_time = time.time()
    
    try:
        # Initialize Firebase
        db = init_firebase()
        print("🔥 Firebase initialized")
        
        # Scrape deals
        deals = scrape_amazon_deals()
        
        # Save to database
        save_to_firestore(deals, db)
        
        # Calculate duration
        duration = time.time() - start_time
        print(f"🏁 Completed in {duration:.2f} seconds")
        
    except Exception as e:
        print(f"💥 Critical error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()