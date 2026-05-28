"""
run_daily.py
Safe daily scraper for News Headline Monitor
Compatible with Jenkins automation
"""
import os
from dotenv import load_dotenv
import logging
import mysql.connector
from datetime import datetime
import json
import time
import requests
from bs4 import BeautifulSoup

load_dotenv()
# ---------------- LOGGING ---------------- #

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("news_monitor.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ---------------- MYSQL ---------------- #

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="sanju@2005",
        database="news_monitor"
    )

# ---------------- SPACY ---------------- #

try:
    import spacy
    nlp = spacy.load('en_core_web_sm')
except Exception as e:
    logger.warning(f"spaCy not loaded: {e}")
    nlp = None

# ---------------- TEXTBLOB ---------------- #

try:
    from textblob import TextBlob
except ImportError:
    logger.error("Install textblob: pip install textblob")
    exit(1)

# ---------------- SELENIUM ---------------- #

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
except ImportError:
    logger.warning("Selenium not installed")
    webdriver = None

# ---------------- NEWS SOURCES ---------------- #

NEWS_SOURCES = {

    "THE HINDU": {
        "url": "https://www.thehindu.com/news/feeder/default.rss",
        "type": "static",
        "selectors": [
            "h2.title a",
            ".story-card-text a",
            ".title a",
            ".story-element a"
        ]
    },

    "TIMES OF INDIA": {
        "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "type": "dynamic",
        "selectors": ["a", "h3"]
    }
}

# ---------------- NLP ---------------- #

def analyze_sentiment(text):

    blob = TextBlob(text)

    polarity = blob.sentiment.polarity

    if polarity > 0.1:
        label = "positive"

    elif polarity < -0.1:
        label = "negative"

    else:
        label = "neutral"

    return {
        "score": polarity,
        "label": label
    }

def extract_entities(text):

    if not nlp:
        return []

    doc = nlp(text)

    entities = []

    for ent in doc.ents:

        if ent.label_ in [
            'PERSON',
            'ORG',
            'GPE',
            'EVENT',
            'PRODUCT'
        ]:

            entities.append({
                'text': ent.text,
                'label': ent.label_
            })

    return entities

# ---------------- STATIC SCRAPER ---------------- #

def scrape_static_source(source_name, config):

    try:

        headers = {
            'User-Agent': 'Mozilla/5.0'
        }

        response = requests.get(
            config['url'],
            headers=headers,
            timeout=10
        )

        headlines = set()

        if (
            response.headers.get(
                'Content-Type',
                ''
            ).startswith('application/rss')

            or '.rss' in config['url']
        ):

            soup = BeautifulSoup(
                response.content,
                'xml'
            )

            for item in soup.find_all('item'):

                title = item.title.text if item.title else ''

                if title and 15 < len(title) < 300:
                    headlines.add(title)

        else:

            soup = BeautifulSoup(
                response.content,
                'html.parser'
            )

            for selector in config['selectors']:

                elements = soup.select(selector)

                for elem in elements:

                    text = elem.get_text(strip=True)

                    if text and 15 < len(text) < 300:
                        headlines.add(text)

        logger.info(
            f"{source_name} fetched {len(headlines)} headlines"
        )

        return list(headlines)[:30]

    except Exception as e:

        logger.error(
            f"Scraping error for {source_name}: {e}"
        )

        return []

# ---------------- DYNAMIC SCRAPER ---------------- #

def scrape_dynamic_source(source_name, config):

    if not webdriver:
        return []

    try:

        options = Options()

        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)

        driver.get(config['url'])

        time.sleep(3)

        headlines = set()

        for selector in config['selectors']:

            elements = driver.find_elements(
                By.CSS_SELECTOR,
                selector
            )

            for elem in elements:

                text = elem.text.strip()

                if text and 15 < len(text) < 300:
                    headlines.add(text)

        driver.quit()

        logger.info(
            f"{source_name} fetched {len(headlines)} headlines"
        )

        return list(headlines)[:30]

    except Exception as e:

        logger.error(
            f"Dynamic scraping error for {source_name}: {e}"
        )

        return []

# ---------------- MAIN SCRAPER ---------------- #

def scrape_all_sources():

    now = datetime.now()

    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    all_headlines = []

    for source, cfg in NEWS_SOURCES.items():

        logger.info(f"Scraping {source}...")

        if cfg['type'] == 'static':
            headlines = scrape_static_source(source, cfg)

        else:
            headlines = scrape_dynamic_source(source, cfg)

        for headline in headlines:

            sentiment = analyze_sentiment(headline)
            entities = extract_entities(headline)

            all_headlines.append({

                "source": source,
                "text": headline,
                "url": cfg['url'],
                "category": "General",
                "sentiment": sentiment['score'],
                "sentiment_label": sentiment['label'],
                "entities": json.dumps(entities)
            })

    # ---------------- SAVE TO MYSQL ---------------- #

    conn = get_db_connection()
    cursor = conn.cursor()

    # Remove today's old headlines
    cursor.execute(
        "DELETE FROM headlines WHERE scraped_date = %s",
        (date_str,)
    )

    for h in all_headlines:

        cursor.execute("""

            INSERT IGNORE INTO headlines
            (
                source,
                headline,
                url,
                scraped_date,
                scraped_time,
                category,
                sentiment,
                sentiment_label,
                entities
            )

            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)

        """, (

            h['source'],
            h['text'],
            h['url'],
            date_str,
            time_str,
            h['category'],
            h['sentiment'],
            h['sentiment_label'],
            h['entities']

        ))

    cursor.execute("""

        INSERT INTO scrape_logs
        (
            scrape_datetime,
            total_headlines,
            status
        )

        VALUES (%s, %s, %s)

    """, (

        now,
        len(all_headlines),
        "success"

    ))

    conn.commit()
    conn.close()

    logger.info(
        f"Scraping finished: {len(all_headlines)} headlines"
    )

    return len(all_headlines)

# ---------------- MAIN ---------------- #

if __name__ == "__main__":
    scrape_all_sources()