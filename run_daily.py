
"""
run_daily.py
Safe daily scraper for News Headline Monitor
Compatible with Jenkins automation
"""

import os
import sys
import json
import time
import logging

import requests
import mysql.connector

from dotenv import load_dotenv
from bs4 import BeautifulSoup
from datetime import datetime

# ---------------- ENVIRONMENT ---------------- #

load_dotenv()

# ---------------- LOGGING ---------------- #

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("news_monitor.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ---------------- MYSQL ---------------- #

def get_db_connection():

    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "sanju@2005"),
        database=os.getenv("DB_NAME", "news_monitor"),
        connection_timeout=15
    )


# ---------------- SPACY ---------------- #

try:

    import spacy

    nlp = spacy.load("en_core_web_sm")

    logger.info("spaCy model loaded successfully")

except Exception as e:

    logger.warning(f"spaCy not loaded: {e}")

    nlp = None


# ---------------- TEXTBLOB ---------------- #

try:

    from textblob import TextBlob

except ImportError:

    logger.error("Install TextBlob: pip install textblob")

    sys.exit(1)


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
        "type": "static",
        "selectors": []
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

    if nlp is None:

        return []

    doc = nlp(text)

    entities = []

    for ent in doc.ents:

        if ent.label_ in [
            "PERSON",
            "ORG",
            "GPE",
            "EVENT",
            "PRODUCT"
        ]:

            entities.append({

                "text": ent.text,
                "label": ent.label_

            })

    return entities


# ---------------- STATIC SCRAPER ---------------- #

def scrape_static_source(source_name, config):

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(
            config["url"],
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        headlines = set()

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        is_xml = (
            "xml" in content_type
            or "rss" in content_type
            or ".rss" in config["url"].lower()
        )

        # -------- RSS / XML PARSING -------- #

        if is_xml:

            soup = BeautifulSoup(
                response.content,
                "xml"
            )

            for item in soup.find_all("item"):

                title_tag = item.find("title")

                title = (
                    title_tag.get_text(strip=True)
                    if title_tag else ""
                )

                if title and 15 < len(title) < 300:

                    headlines.add(title)

        # -------- HTML PARSING -------- #

        else:

            soup = BeautifulSoup(
                response.content,
                "html.parser"
            )

            for selector in config["selectors"]:

                elements = soup.select(selector)

                for elem in elements:

                    text = elem.get_text(
                        separator=" ",
                        strip=True
                    )

                    if text and 15 < len(text) < 300:

                        headlines.add(text)

        logger.info(
            f"{source_name} fetched {len(headlines)} headlines"
        )

        return list(headlines)[:30]

    except Exception as e:

        logger.exception(
            f"Scraping error for {source_name}: {e}"
        )

        # None means scraping failed.
        # An empty list means scraping succeeded but found no headlines.

        return None


# ---------------- DYNAMIC SCRAPER ---------------- #

def scrape_dynamic_source(source_name, config):

    if not webdriver:

        logger.error("Selenium is not available")

        return None

    driver = None

    try:

        options = Options()

        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # Selenium Manager automatically resolves ChromeDriver.

        driver = webdriver.Chrome(options=options)

        driver.set_page_load_timeout(30)

        driver.get(config["url"])

        time.sleep(3)

        headlines = set()

        for selector in config["selectors"]:

            elements = driver.find_elements(
                By.CSS_SELECTOR,
                selector
            )

            for elem in elements:

                text = elem.text.strip()

                if text and 15 < len(text) < 300:

                    headlines.add(text)

        logger.info(
            f"{source_name} fetched {len(headlines)} headlines"
        )

        return list(headlines)[:30]

    except Exception as e:

        logger.exception(
            f"Dynamic scraping error for {source_name}: {e}"
        )

        return None

    finally:

        if driver:

            try:

                driver.quit()

            except Exception:

                logger.warning(
                    f"Could not close browser for {source_name}"
                )


# ---------------- MAIN SCRAPER ---------------- #

def scrape_all_sources():

    now = datetime.now()

    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M:%S")

    all_headlines = []

    successful_sources = []
    failed_sources = []

    # -------- SCRAPE ALL SOURCES -------- #

    for source, cfg in NEWS_SOURCES.items():

        logger.info(f"Scraping {source}...")

        if cfg["type"] == "static":

            headlines = scrape_static_source(source, cfg)

        else:

            headlines = scrape_dynamic_source(source, cfg)

        if headlines is None:

            failed_sources.append(source)

            continue

        successful_sources.append(source)

        for headline in headlines:

            sentiment = analyze_sentiment(headline)

            entities = extract_entities(headline)

            all_headlines.append({

                "source": source,

                "text": headline,

                "url": cfg["url"],

                "category": "General",

                "sentiment": sentiment["score"],

                "sentiment_label": sentiment["label"],

                "entities": json.dumps(entities)

            })

    # -------- DETERMINE SCRAPE STATUS -------- #

    if failed_sources and successful_sources:

        status = "partial"

    elif failed_sources:

        status = "failed"

    else:

        status = "success"

    logger.info(
        f"Successful sources: {successful_sources}"
    )

    logger.info(
        f"Failed sources: {failed_sources}"
    )

    # -------- DATABASE STORAGE -------- #

    conn = None
    cursor = None

    try:

        conn = get_db_connection()

        cursor = conn.cursor()

        # Only update sources whose scraping completed.
        # Failed sources retain their previously stored headlines.

        for source in successful_sources:

            cursor.execute(
                """
                DELETE FROM headlines
                WHERE scraped_date = %s
                AND source = %s
                """,
                (date_str, source)
            )

        # -------- INSERT HEADLINES -------- #

        for h in all_headlines:

            cursor.execute(
                """
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
                """,
                (
                    h["source"],
                    h["text"],
                    h["url"],
                    date_str,
                    time_str,
                    h["category"],
                    h["sentiment"],
                    h["sentiment_label"],
                    h["entities"]
                )
            )

        # -------- SCRAPE LOG -------- #

        cursor.execute(
            """
            INSERT INTO scrape_logs
            (
                scrape_datetime,
                total_headlines,
                status
            )
            VALUES (%s, %s, %s)
            """,
            (
                now,
                len(all_headlines),
                status
            )
        )

        conn.commit()

        logger.info(
            f"Scraping finished: {len(all_headlines)} headlines"
        )

        logger.info(
            f"Scraping status: {status}"
        )

        return len(all_headlines)

    except Exception as e:

        if conn:

            conn.rollback()

        logger.exception(
            f"Database operation failed: {e}"
        )

        raise

    finally:

        if cursor:

            cursor.close()

        if conn and conn.is_connected():

            conn.close()


# ---------------- MAIN ---------------- #

if __name__ == "__main__":

    try:

        total = scrape_all_sources()

        logger.info(
            f"Daily scraping completed with {total} headlines"
        )

        # Exit non-zero if every source failed.

        # A partial scrape is still useful and is recorded as partial.

        if total == 0:

            logger.warning(
                "No headlines collected. Check source availability."
            )

    except Exception as e:

        logger.exception(
            f"Daily scraper execution failed: {e}"
        )

        sys.exit(1)
