"""
run_daily.py
Safe daily scraper for News Headline Monitor
Compatible with Jenkins automation
"""

import threading
from datetime import datetime
import json
import sqlite3
import time
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# Try importing spaCy, fall back if not available
try:
    import spacy
    nlp = spacy.load('en_core_web_sm')
except Exception as e:
    print(f"[WARN] spaCy not loaded: {e}")
    nlp = None

# TextBlob for sentiment
try:
    from textblob import TextBlob
except ImportError:
    print("[ERROR] Install textblob: pip install textblob")
    exit(1)

# Selenium for dynamic sites
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
except ImportError:
    print("[WARN] Selenium not installed, dynamic scraping disabled")
    webdriver = None

# --- Configuration ---
NEWS_SOURCES = {
    "THE HINDU": {
        "url": "https://www.thehindu.com/news/feeder/default.rss",
        "type": "static",
        "selectors": ["h2.title a", ".story-card-text a", ".title a", ".story-element a"]
    },
    "TIMES OF INDIA": {
        "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "type": "dynamic",
        "selectors": ["a", "h3"]
    }
    # Add other sources as needed
}

DB_FILE = "news_monitor.db"

# --- Helper functions ---
def analyze_sentiment(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    if polarity > 0.1:
        label = "positive"
    elif polarity < -0.1:
        label = "negative"
    else:
        label = "neutral"
    return {"score": polarity, "label": label}

def extract_entities(text):
    if not nlp:
        return []
    doc = nlp(text)
    entities = []
    for ent in doc.ents:
        if ent.label_ in ['PERSON', 'ORG', 'GPE', 'EVENT', 'PRODUCT']:
            entities.append({'text': ent.text, 'label': ent.label_})
    return entities

def scrape_static_source(source_name, config):
    """
    Scrape static sources: either XML RSS feeds or normal HTML pages.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        r = requests.get(config['url'], headers=headers, timeout=10)

        headlines = set()

        # Determine if it's an XML RSS feed (common for news sites)
        if r.headers.get('Content-Type', '').startswith('application/rss') or '.rss' in config['url']:
            # Parse as XML
            soup = BeautifulSoup(r.content, 'xml')
            for item in soup.find_all('item'):
                title = item.title.text if item.title else ''
                if title and 15 < len(title) < 300:
                    headlines.add(title)
        else:
            # Parse as HTML for normal web pages
            soup = BeautifulSoup(r.content, 'html.parser')
            for selector in config['selectors']:
                elements = soup.select(selector)
                for elem in elements:
                    text = elem.get_text(strip=True)
                    if text and 15 < len(text) < 300:
                        headlines.add(text)

        print(f"[INFO] {source_name} fetched {len(headlines)} headlines.")
        return list(headlines)[:30]

    except Exception as e:
        print(f"[ERROR] Scraping {source_name}: {e}")
        return []

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(config['url'], headers=headers, timeout=10)
        soup = BeautifulSoup(r.content, 'html.parser')
        headlines = set()
        for sel in config['selectors']:
            for elem in soup.select(sel):
                text = elem.get_text(strip=True)
                if text and 15 < len(text) < 300:
                    headlines.add(text)
        return list(headlines)[:30]
    except Exception as e:
        print(f"[ERROR] Static scrape failed: {e}")
        return []

def scrape_dynamic_source(config):
    if not webdriver:
        return []
    try:
        options = Options()
        options.add_argument("--headless")
        driver = webdriver.Chrome(options=options)
        driver.get(config['url'])
        time.sleep(3)
        headlines = set()
        for sel in config['selectors']:
            for elem in driver.find_elements(By.CSS_SELECTOR, sel):
                text = elem.text.strip()
                if text and 15 < len(text) < 300:
                    headlines.add(text)
        driver.quit()
        return list(headlines)[:30]
    except Exception as e:
        print(f"[ERROR] Dynamic scrape failed: {e}")
        return []

def scrape_all_sources():
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    all_headlines = []

    for source, cfg in NEWS_SOURCES.items():
        print(f"[INFO] Scraping {source}...")
        if cfg['type'] == 'static':
            headlines = scrape_static_source(cfg)
        else:
            headlines = scrape_dynamic_source(cfg)

        for h in headlines:
            sentiment = analyze_sentiment(h)
            entities = extract_entities(h)
            headline_obj = {
                "source": source,
                "text": h,
                "url": cfg['url'],
                "category": "General",  # Optional: add categorization
                "sentiment": sentiment['score'],
                "sentiment_label": sentiment['label'],
                "entities": json.dumps(entities)
            }
            all_headlines.append(headline_obj)

    # Save to DB
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for h in all_headlines:
        cursor.execute("""
            INSERT INTO headlines
            (source, headline, url, scraped_date, scraped_time, category, sentiment, sentiment_label, entities)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (h['source'], h['text'], h['url'], date_str, time_str,
              h['category'], h['sentiment'], h['sentiment_label'], h['entities']))
    cursor.execute("""
        INSERT INTO scrape_logs (scrape_datetime, total_headlines, status)
        VALUES (?, ?, ?)
    """, (now, len(all_headlines), "success"))
    conn.commit()
    conn.close()

    print(f"[INFO] Scraping finished: {len(all_headlines)} headlines")
    return len(all_headlines)

# --- Main entry point ---
if __name__ == "__main__":
    scrape_all_sources()
