"""
Flask Backend for News Headline Monitor
Real-time scraping with sentiment analysis and comparison
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import sqlite3
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

app = Flask(__name__)
CORS(app)

# Load spaCy model
try:
    nlp = spacy.load('en_core_web_sm')
except:
    nlp = None

# News sources configuration
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
}
,
    "TIMES OF INDIA": {
    "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
    "type": "dynamic",
    "selectors": 
        "a, h3"
    
},
    'Al Jazeera': {
        'url': "https://www.aljazeera.com/xml/rss/all.xml",

        'selectors': ['h3.gc__title', 'span.gc__title__text', 'article h3'],
        'type': 'static'
    },
    'Associated Press': {
        'url': 'https://apnews.com/rss',
        'selectors': ['h2.PagePromo-title', 'h3.PagePromo-title', 'a.Link'],
        'type': 'static'
    },
    'The Guardian': {
        'url': 'https://www.theguardian.com/international',
        'selectors': ['h3.card-headline', 'span.js-headline-text'],
        'type': 'static'
    },
    'BBC News': {
        'url': "http://feeds.bbci.co.uk/news/rss.xml",
        'selectors': ['h2[data-testid="card-headline"]', 'h3[data-testid="card-headline"]'],
        'type': 'dynamic'
    },
    'Reuters': {
        'url': 'https://feeds.reuters.com/reuters/topNews',
        'selectors': ['h3[data-testid="Heading"]', 'a[data-testid="Link"]'],
        'type': 'static'
    },
    'CNN': {
        'url': "http://rss.cnn.com/rss/edition.rss",
        'selectors': ['span.container__headline-text', 'h3.cd__headline'],
        'type': 'dynamic'
    }
}

# Database setup
def init_db():
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS headlines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            headline TEXT NOT NULL,
            url TEXT,
            scraped_date DATE NOT NULL,
            scraped_time TIME NOT NULL,
            category TEXT,
            sentiment REAL,
            sentiment_label TEXT,
            entities TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scrape_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scrape_datetime TIMESTAMP NOT NULL,
            total_headlines INTEGER,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Helper functions
def analyze_sentiment(text):
    """Analyze sentiment using TextBlob"""
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
    """Extract named entities using spaCy"""
    if not nlp:
        return []
    
    doc = nlp(text)
    entities = []
    
    for ent in doc.ents:
        if ent.label_ in ['PERSON', 'ORG', 'GPE', 'EVENT', 'PRODUCT']:
            entities.append({'text': ent.text, 'label': ent.label_})
    
    return entities

def categorize_headline(text):
    """Simple keyword-based categorization"""
    text_lower = text.lower()
    
    categories = {
        'Sports': ['sport', 'game', 'player', 'team', 'championship', 'match', 'football', 'basketball', 'soccer', 'cricket'],
        'Politics': ['election', 'government', 'president', 'congress', 'political', 'vote', 'minister', 'parliament', 'policy'],
        'Business': ['market', 'economy', 'stock', 'financial', 'business', 'trade', 'company', 'CEO'],
        'Technology': ['tech', 'ai', 'software', 'digital', 'cyber', 'innovation', 'app', 'computer'],
        'Health': ['health', 'medical', 'disease', 'hospital', 'covid', 'vaccine', 'doctor'],
        'World': ['war', 'international', 'country', 'peace', 'conflict', 'hostage', 'crisis'],
        'Crime': ['crime', 'arrest', 'police', 'jail', 'assault', 'murder'],
        'Weather': ['weather', 'storm', 'hurricane', 'flood', 'temperature'],
        'Environment': ['climate', 'environment', 'carbon', 'pollution']
    }
    
    for category, keywords in categories.items():
        if any(keyword in text_lower for keyword in keywords):
            return category
    
    return 'General'

def scrape_static_source(source_name, config):
    """Scrape using requests and BeautifulSoup"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(config['url'], headers=headers, timeout=8)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        headlines = set()
        for selector in config['selectors']:
            elements = soup.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                if text and len(text) > 15 and len(text) < 300:
                    headlines.add(text)
        
        return list(headlines)[:30]
    
    except Exception as e:
        print(f"Error scraping {source_name}: {e}")
        return []

def scrape_dynamic_source(source_name, config):
    """Scrape using Selenium"""
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-java")
        chrome_options.add_argument("--disable-javascript")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get(config['url'])
        time.sleep(3)
        
        headlines = set()
        for selector in config['selectors']:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.strip()
                    if text and len(text) > 15 and len(text) < 300:
                        headlines.add(text)
            except:
                continue
        
        driver.quit()
        return list(headlines)[:30]
    
    except Exception as e:
        print(f"Error scraping {source_name}: {e}")
        return []

def scrape_all_sources():
    """Scrape all configured news sources"""
    now = datetime.now()
    current_date = now.strftime('%Y-%m-%d')
    current_time = now.strftime('%H:%M:%S')
    
    all_headlines = []
    
    for source_name, config in NEWS_SOURCES.items():
        print(f"Scraping {source_name}...")
        
        if config['type'] == 'static':
            headlines = scrape_static_source(source_name, config)
        else:
            headlines = scrape_dynamic_source(source_name, config)
        
        for headline_text in headlines:
            sentiment = analyze_sentiment(headline_text)
            entities = extract_entities(headline_text)
            category = categorize_headline(headline_text)
            
            headline_obj = {
                'source': source_name,
                'text': headline_text,
                'url': config['url'],
                'category': category,
                'sentiment': sentiment['score'],
                'sentiment_label': sentiment['label'],
                'entities': json.dumps(entities)
            }
            all_headlines.append(headline_obj)
    
    # Save to database
    conn = sqlite3.connect('news_monitor.db')
    cursor = conn.cursor()
    
    for h in all_headlines:
        cursor.execute('''
            INSERT INTO headlines 
            (source, headline, url, scraped_date, scraped_time, category, sentiment, sentiment_label, entities)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (h['source'], h['text'], h['url'], current_date, current_time, 
              h['category'], h['sentiment'], h['sentiment_label'], h['entities']))
    
    cursor.execute('''
        INSERT INTO scrape_logs (scrape_datetime, total_headlines, status)
        VALUES (?, ?, ?)
    ''', (now, len(all_headlines), 'success'))
    
    conn.commit()
    conn.close()
    
    return len(all_headlines)

def calculate_similarity(text1, text2):
    """Calculate similarity between two texts"""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

def find_similar_headlines(headlines, threshold=0.7):
    """Group similar headlines together"""
    groups = []
    used = set()
    
    for i, h1 in enumerate(headlines):
        if i in used:
            continue
        
        group = [h1]
        used.add(i)
        
        for j, h2 in enumerate(headlines[i+1:], i+1):
            if j in used:
                continue
            
            similarity = calculate_similarity(h1['text'], h2['text'])
            if similarity >= threshold:
                group.append(h2)
                used.add(j)
        
        if len(group) > 1:
            groups.append(group)
    
    return groups

# API Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scrape', methods=['POST'])
def trigger_scrape():
    """Manually trigger scraping"""
    try:
        def scrape_async():
            scrape_all_sources()
        
        thread = threading.Thread(target=scrape_async)
        thread.start()
        
        return jsonify({
            'status': 'success',
            'message': 'Scraping started',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/headlines/today')
def get_todays_headlines():
    """Get today's headlines"""
    try:
        conn = sqlite3.connect('news_monitor.db')
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT source, headline, url, category, sentiment, sentiment_label, entities
            FROM headlines
            WHERE scraped_date = ?
            ORDER BY source, id DESC
        ''', (today,))
        
        rows = cursor.fetchall()
        headlines = []
        
        for row in rows:
            headlines.append({
                'source': row[0],
                'text': row[1],
                'url': row[2],
                'category': row[3],
                'sentiment': row[4],
                'sentiment_label': row[5],
                'entities': json.loads(row[6]) if row[6] else []
            })
        
        conn.close()
        return jsonify(headlines)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/headlines/yesterday')
def get_yesterdays_headlines():
    """Get yesterday's headlines"""
    try:
        conn = sqlite3.connect('news_monitor.db')
        cursor = conn.cursor()
        
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT source, headline, url, category, sentiment, sentiment_label
            FROM headlines
            WHERE scraped_date = ?
        ''', (yesterday,))
        
        rows = cursor.fetchall()
        headlines = []
        
        for row in rows:
            headlines.append({
                'source': row[0],
                'text': row[1],
                'url': row[2],
                'category': row[3],
                'sentiment': row[4],
                'sentiment_label': row[5]
            })
        
        conn.close()
        return jsonify(headlines)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/similar-groups')
def get_similar_groups():
    """Get groups of similar headlines"""
    try:
        conn = sqlite3.connect('news_monitor.db')
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT source, headline, url, category
            FROM headlines
            WHERE scraped_date = ?
        ''', (today,))
        
        rows = cursor.fetchall()
        headlines = [{'source': r[0], 'text': r[1], 'url': r[2], 'category': r[3]} for r in rows]
        
        groups = find_similar_headlines(headlines)
        
        conn.close()
        return jsonify(groups)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/entities')
def get_top_entities():
    """Get top named entities from today's headlines"""
    try:
        conn = sqlite3.connect('news_monitor.db')
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT entities
            FROM headlines
            WHERE scraped_date = ? AND entities IS NOT NULL
        ''', (today,))
        
        rows = cursor.fetchall()
        entity_counts = {}
        
        for row in rows:
            entities = json.loads(row[0]) if row[0] else []
            for ent in entities:
                key = f"{ent['text']}_{ent['label']}"
                if key not in entity_counts:
                    entity_counts[key] = {'text': ent['text'], 'label': ent['label'], 'count': 0}
                entity_counts[key]['count'] += 1
        
        top_entities = sorted(entity_counts.values(), key=lambda x: x['count'], reverse=True)[:30]
        
        conn.close()
        return jsonify(top_entities)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/comparison')
def get_comparison():
    """Compare today's headlines with yesterday's"""
    try:
        conn = sqlite3.connect('news_monitor.db')
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Get today's headlines
        cursor.execute('SELECT source, headline FROM headlines WHERE scraped_date = ?', (today,))
        today_headlines = [{'source': r[0], 'text': r[1]} for r in cursor.fetchall()]
        
        # Get yesterday's headlines
        cursor.execute('SELECT source, headline FROM headlines WHERE scraped_date = ?', (yesterday,))
        yesterday_headlines = [{'source': r[0], 'text': r[1]} for r in cursor.fetchall()]
        
        # Find new headlines
        new_headlines = []
        updated_headlines = []
        
        for today_h in today_headlines:
            is_new = True
            for yesterday_h in yesterday_headlines:
                similarity = calculate_similarity(today_h['text'], yesterday_h['text'])
                if similarity >= 0.9:
                    is_new = False
                    break
                elif similarity >= 0.6:
                    updated_headlines.append({
                        'yesterday': yesterday_h,
                        'today': today_h,
                        'similarity': similarity
                    })
                    is_new = False
                    break
            
            if is_new:
                new_headlines.append(today_h)
        
        conn.close()
        
        return jsonify({
            'new': new_headlines[:20],
            'updated': updated_headlines[:20],
            'total_today': len(today_headlines),
            'total_yesterday': len(yesterday_headlines)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/last-scrape')
def get_last_scrape():
    """Get last scrape timestamp"""
    try:
        conn = sqlite3.connect('news_monitor.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT scrape_datetime, total_headlines
            FROM scrape_logs
            ORDER BY id DESC
            LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify({
                'timestamp': row[0],
                'total_headlines': row[1]
            })
        else:
            return jsonify({'timestamp': None, 'total_headlines': 0})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)