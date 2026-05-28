"""
Flask Backend for News Headline Monitor
Real-time scraping with sentiment analysis and comparison
"""
import os
from dotenv import load_dotenv

import logging
import mysql.connector
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from datetime import datetime, timedelta
import time
import threading
from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from textblob import TextBlob
import spacy
from difflib import SequenceMatcher
import json

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

# ---------------- FLASK ---------------- #

app = Flask(__name__)
CORS(app)

# ---------------- MYSQL ---------------- #

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

# ---------------- SPACY ---------------- #

try:
    nlp = spacy.load('en_core_web_sm')
except:
    nlp = None

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
    },

    "Al Jazeera": {
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "selectors": ["h3.gc__title", "span.gc__title__text", "article h3"],
        "type": "static"
    },

    "Associated Press": {
        "url": "https://apnews.com/rss",
        "selectors": ["h2.PagePromo-title", "h3.PagePromo-title", "a.Link"],
        "type": "static"
    },

    "The Guardian": {
        "url": "https://www.theguardian.com/international",
        "selectors": ["h3.card-headline", "span.js-headline-text"],
        "type": "static"
    },

    "BBC News": {
        "url": "http://feeds.bbci.co.uk/news/rss.xml",
        "selectors": ["h2[data-testid='card-headline']", "h3[data-testid='card-headline']"],
        "type": "dynamic"
    },

    "Reuters": {
        "url": "https://feeds.reuters.com/reuters/topNews",
        "selectors": ["h3[data-testid='Heading']", "a[data-testid='Link']"],
        "type": "static"
    },

    "CNN": {
        "url": "http://rss.cnn.com/rss/edition.rss",
        "selectors": ["span.container__headline-text", "h3.cd__headline"],
        "type": "dynamic"
    }
}

# ---------------- DATABASE SETUP ---------------- #

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS headlines (
            id INT AUTO_INCREMENT PRIMARY KEY,
            source VARCHAR(255) NOT NULL,
            headline TEXT NOT NULL,
            url TEXT,
            scraped_date DATE NOT NULL,
            scraped_time TIME NOT NULL,
            category VARCHAR(100),
            sentiment FLOAT,
            sentiment_label VARCHAR(50),
            entities JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_headline (source(255), headline(255), scraped_date)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrape_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            scrape_datetime DATETIME NOT NULL,
            total_headlines INT,
            status VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- NLP HELPERS ---------------- #

def analyze_sentiment(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity

    if polarity > 0.1:
        label = 'positive'
    elif polarity < -0.1:
        label = 'negative'
    else:
        label = 'neutral'

    return {'score': polarity, 'label': label}

def extract_entities(text):
    if not nlp:
        return []

    doc = nlp(text)

    entities = []

    for ent in doc.ents:
        if ent.label_ in ['PERSON', 'ORG', 'GPE', 'EVENT', 'PRODUCT']:
            entities.append({
                'text': ent.text,
                'label': ent.label_
            })

    return entities

def categorize_headline(text):

    text_lower = text.lower()

    categories = {
        'Sports': ['sport', 'game', 'player', 'team', 'match', 'football', 'cricket'],
        'Politics': ['election', 'government', 'minister', 'parliament'],
        'Business': ['market', 'economy', 'stock', 'trade', 'company'],
        'Technology': ['tech', 'ai', 'software', 'digital'],
        'Health': ['health', 'medical', 'hospital', 'covid'],
        'World': ['war', 'international', 'country', 'conflict'],
        'Crime': ['crime', 'arrest', 'police'],
        'Weather': ['weather', 'storm', 'flood'],
        'Environment': ['climate', 'pollution']
    }

    for category, keywords in categories.items():
        if any(keyword in text_lower for keyword in keywords):
            return category

    return "General"

# ---------------- SCRAPING ---------------- #

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

        soup = BeautifulSoup(response.content, 'xml')

        headlines = set()

        for item in soup.find_all('item'):

            title = item.title.text if item.title else ""

            if title and 15 < len(title) < 300:
                headlines.add(title)

        logger.info(f"{source_name} fetched {len(headlines)} headlines")

        return list(headlines)[:30]

    except Exception as e:
        logger.error(f"Error scraping {source_name}: {e}")
        return []

def scrape_dynamic_source(source_name, config):

    try:
        chrome_options = Options()

        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')

        driver = webdriver.Chrome(options=chrome_options)

        driver.get(config['url'])

        time.sleep(3)

        headlines = set()

        for selector in config['selectors']:

            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)

                for elem in elements:

                    text = elem.text.strip()

                    if text and 15 < len(text) < 300:
                        headlines.add(text)

            except:
                continue

        driver.quit()

        logger.info(f"{source_name} fetched {len(headlines)} headlines")

        return list(headlines)[:30]

    except Exception as e:
        logger.error(f"Dynamic scraping error {source_name}: {e}")
        return []

# ---------------- MAIN SCRAPER ---------------- #

def scrape_all_sources():

    now = datetime.now()

    current_date = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%H:%M:%S')

    all_headlines = []

    for source_name, config in NEWS_SOURCES.items():

        logger.info(f"Scraping {source_name}...")

        if config['type'] == 'static':
            headlines = scrape_static_source(source_name, config)
        else:
            headlines = scrape_dynamic_source(source_name, config)

        for headline_text in headlines:

            sentiment = analyze_sentiment(headline_text)
            entities = extract_entities(headline_text)
            category = categorize_headline(headline_text)

            all_headlines.append({
                'source': source_name,
                'text': headline_text,
                'url': config['url'],
                'category': category,
                'sentiment': sentiment['score'],
                'sentiment_label': sentiment['label'],
                'entities': json.dumps(entities)
            })

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM headlines WHERE scraped_date = %s",
        (current_date,)
    )

    for h in all_headlines:

        cursor.execute("""
            INSERT IGNORE INTO headlines
            (source, headline, url, scraped_date, scraped_time,
             category, sentiment, sentiment_label, entities)

            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            h['source'],
            h['text'],
            h['url'],
            current_date,
            current_time,
            h['category'],
            h['sentiment'],
            h['sentiment_label'],
            h['entities']
        ))

    cursor.execute("""
        INSERT INTO scrape_logs
        (scrape_datetime, total_headlines, status)

        VALUES (%s, %s, %s)
    """, (
        now,
        len(all_headlines),
        "success"
    ))

    conn.commit()
    conn.close()

    logger.info(f"Scraping completed. Total headlines: {len(all_headlines)}")

    return len(all_headlines)

# ---------------- SIMILARITY ---------------- #

def calculate_similarity(text1, text2):
    return SequenceMatcher(
        None,
        text1.lower(),
        text2.lower()
    ).ratio()

# ---------------- ROUTES ---------------- #

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def trigger_scrape():

    try:

        def scrape_async():
            scrape_all_sources()

        thread = threading.Thread(target=scrape_async)
        thread.start()

        return jsonify({
            'status': 'success',
            'message': 'Scraping started'
        })

    except Exception as e:

        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/last-scrape')
def get_last_scrape():

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT scrape_datetime, total_headlines
            FROM scrape_logs
            ORDER BY id DESC
            LIMIT 1
        """)

        row = cursor.fetchone()

        conn.close()

        if row:
            return jsonify({
                'timestamp': str(row[0]),
                'total_headlines': row[1]
            })

        return jsonify({
            'timestamp': None,
            'total_headlines': 0
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/headlines/today')
def get_todays_headlines():

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute("""
            SELECT source, headline, category,
                   sentiment_label

            FROM headlines

            WHERE scraped_date = %s

            ORDER BY id DESC
        """, (today,))

        rows = cursor.fetchall()

        conn.close()

        headlines = []

        for row in rows:

            headlines.append({
                'source': row[0],
                'headline': row[1],
                'category': row[2],
                'sentiment_label': row[3]
            })

        return jsonify(headlines)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/comparison')
def get_comparison():

    try:

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)

        today = datetime.now().date()
        yesterday = today - timedelta(days=1)

        # ---------------- TODAY HEADLINES ---------------- #

        cursor.execute("""

            SELECT
                source,
                headline,
                sentiment_label

            FROM headlines

            WHERE scraped_date = %s

        """, (today,))

        today_rows = cursor.fetchall()

        # ---------------- YESTERDAY ---------------- #

        cursor.execute("""

            SELECT
                source,
                headline

            FROM headlines

            WHERE scraped_date = %s

        """, (yesterday,))

        yesterday_rows = cursor.fetchall()

        # ---------------- SOURCE STATS ---------------- #

        cursor.execute("""

            SELECT

                source,

                COUNT(*) as total,

                SUM(
                    CASE
                        WHEN sentiment_label = 'positive'
                        THEN 1
                        ELSE 0
                    END
                ) as positive,

                SUM(
                    CASE
                        WHEN sentiment_label = 'neutral'
                        THEN 1
                        ELSE 0
                    END
                ) as neutral,

                SUM(
                    CASE
                        WHEN sentiment_label = 'negative'
                        THEN 1
                        ELSE 0
                    END
                ) as negative

            FROM headlines

            WHERE scraped_date = %s

            GROUP BY source

        """, (today,))

        source_stats = cursor.fetchall()

        conn.close()

        # ---------------- COMPARISON LOGIC ---------------- #

        yesterday_headlines = [
            row['headline']
            for row in yesterday_rows
        ]

        new_headlines = []

        for row in today_rows:

            if row['headline'] not in yesterday_headlines:

                new_headlines.append({
                    'source': row['source'],
                    'headline': row['headline']
                })

        updated_headlines = []

        used_yesterday = set()

        for today_item in today_rows:

            for idx, yesterday_item in enumerate(yesterday_rows):

                if idx in used_yesterday:
                    continue

                similarity = calculate_similarity(
                    today_item['headline'],
                    yesterday_item['headline']
                )

                if 0.6 < similarity < 0.95:

                    updated_headlines.append({

                        'today': {
                            'source': today_item['source'],
                            'headline': today_item['headline']
                        },

                        'yesterday': {
                            'source': yesterday_item['source'],
                            'headline': yesterday_item['headline']
                        }

                    })

                    used_yesterday.add(idx)

                    break

        unchanged_count = 0

        for row in today_rows:

            if row['headline'] in yesterday_headlines:
                unchanged_count += 1

        return jsonify({

            'sources': source_stats,

            'new': new_headlines,

            'updated': updated_headlines,

            'unchanged': unchanged_count,

            'total_today': len(today_rows)

        })

    except Exception as e:

        return jsonify({
            'error': str(e)
        }), 500


@app.route('/api/entities')
def get_entities():

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute("""

            SELECT entities

            FROM headlines

            WHERE scraped_date = %s

        """, (today,))

        rows = cursor.fetchall()

        conn.close()

        entity_count = {}

        for row in rows:

            try:

                entities = json.loads(row[0])

                for ent in entities:

                    text = ent['text']

                    entity_count[text] = entity_count.get(text, 0) + 1

            except:
                continue

        sorted_entities = sorted(
            entity_count.items(),
            key=lambda x: x[1],
            reverse=True
        )

        result = []

        for entity, count in sorted_entities[:20]:

            result.append({
                'entity': entity,
                'count': count
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/similar-groups')
def get_similar_groups():

    try:

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        today = datetime.now().strftime('%Y-%m-%d')

        cursor.execute("""

            SELECT source, headline

            FROM headlines

            WHERE scraped_date = %s

        """, (today,))

        rows = cursor.fetchall()

        conn.close()

        groups = []

        used = set()

        for i in range(len(rows)):

            if i in used:
                continue

            base = rows[i]

            group = [base]

            for j in range(i + 1, len(rows)):

                if j in used:
                    continue

                compare = rows[j]

                similarity = calculate_similarity(
                    base['headline'],
                    compare['headline']
                )

                if similarity > 0.6:

                    group.append(compare)

                    used.add(j)

            if len(group) > 1:
                groups.append(group)

        return jsonify(groups)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------- MAIN ---------------- #

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)