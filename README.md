
# 📰 News Headline Monitor

### Automated News Collection, NLP-Based Analysis & Historical Headline Comparison

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Flask-3.0-black?logo=flask" alt="Flask">
  <img src="https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white" alt="MySQL">
  <img src="https://img.shields.io/badge/NLP-spaCy%20%7C%20TextBlob-green" alt="NLP">
  <img src="https://img.shields.io/badge/Automation-Jenkins-D24939?logo=jenkins&logoColor=white" alt="Jenkins">
  <img src="https://img.shields.io/badge/Containerization-Docker-2496ED?logo=docker&logoColor=white" alt="Docker">
</p>

---

## 📌 Overview

**News Headline Monitor** is a news collection and analysis platform that gathers headlines from multiple news outlets, processes them using Natural Language Processing (NLP), and presents the results through an interactive web dashboard.

Instead of manually visiting different news websites, users can monitor headlines, explore sentiment distribution, identify frequently appearing entities, discover similar stories across sources, and compare current headlines with historical coverage.

The system combines web scraping, NLP-based processing, database management, text similarity algorithms, REST APIs, and scheduled automation to provide a centralized news-monitoring experience.

## 🎯 Problem Statement

News is published continuously across different media outlets. Monitoring these sources manually creates several challenges:

- **Multiple Sources:** Users need to visit different websites to follow current events.
- **Changing Headlines:** The same news story may be reported using different wording.
- **Unstructured Information:** Raw headlines do not directly reveal sentiment, entities, or topics.
- **Historical Tracking:** Identifying what is new, updated, or unchanged requires comparing previous coverage.
- **Manual Execution:** Repeatedly running a scraper is inconvenient.

News Headline Monitor addresses these challenges through automated collection, NLP-based processing, historical storage, and headline comparison.

## 📸 Screenshots

## ✨ Key Features

### 1. Multi-Source News Collection

- Collects headlines from configured news outlets.
- Uses `requests` and `BeautifulSoup` for static HTML and RSS content.
- Supports Selenium-based extraction for dynamically rendered web pages.
- Removes duplicate headlines during extraction.
- Limits the number of headlines processed per source.

The standalone daily automation script currently processes The Hindu and Times of India.

### 2. Sentiment Analysis

Uses **TextBlob** to calculate the polarity of each headline.

The polarity score is classified into three sentiment categories:

| Polarity | Sentiment |
|---|---|
| Greater than 0.1 | Positive |
| Less than -0.1 | Negative |
| Otherwise | Neutral |

The dashboard presents sentiment distributions for the collected headlines.

### 3. Named Entity Recognition (NER)

Uses **spaCy (`en_core_web_sm`)** to identify relevant named entities in news headlines.

The implementation extracts entities with labels such as:

- PERSON
- ORG
- GPE
- EVENT
- PRODUCT

These entities help identify frequently mentioned people, organizations, places, and other subjects in the news.

### 4. News Category Classification

The Flask application's categorization function uses a rule-based keyword-matching approach.

Configured categories include:

- Sports
- Politics
- Business
- Technology
- Health
- World
- Crime
- Weather
- Environment
- General

### 5. Hybrid Headline Similarity Analysis

A major feature of the project is identifying potentially related headlines even when their wording differs.

The comparison engine combines three similarity signals:

| Similarity Technique | Weight |
|---|---:|
| Sequence Similarity | 25% |
| Important-Word Overlap | 50% |
| Named-Entity Overlap | 25% |

The combined similarity score is calculated as:

```text
Combined Score =
    0.25 × Sequence Similarity
  + 0.50 × Word Overlap
  + 0.25 × Entity Overlap
```

**Comparison Workflow:**

1. Check whether the headline exactly matches a previous headline.
2. If no exact match exists, compare it with historical headlines.
3. Calculate the three similarity scores.
4. Combine the scores using the configured weights.
5. Identify the best matching historical headline.
6. Apply the configured similarity threshold to classify the result.

The system classifies headlines as:

- **UNCHANGED:** An exact headline match is found.
- **UPDATED:** A sufficiently similar historical headline is found.
- **NEW:** No historical headline meets the similarity threshold.

The current comparison threshold is `0.25`.

### 6. Similar Stories Across Sources

The project also identifies potentially related headlines published by different news outlets on the same day.

Unlike historical comparison, this feature compares headlines from the current day's collection.

The Flask implementation groups headlines when their sequence similarity exceeds `0.6`.

This helps users identify stories receiving coverage across multiple outlets.

### 7. Historical News Storage

Uses **MySQL** to maintain collected headlines and scraping information.

The database stores headline details such as:

- News source
- Headline text
- Article/source URL
- Scraped date and time
- Category
- Sentiment score and label
- Extracted entities

A separate `scrape_logs` table records scraping timestamps, headline counts, and execution status.

A unique database key helps prevent duplicate headline records for the same source and date.

### 8. Interactive Web Dashboard

The frontend is developed using HTML, CSS, and JavaScript.

The dashboard provides:

- Total headline statistics
- News source-wise coverage
- Sentiment distribution
- Trending terms and entities
- Similar stories across sources
- Yesterday-versus-today headline comparison
- Manual scraping functionality
- Last scraping information

The frontend communicates with the Flask backend through REST APIs and displays the returned JSON data.

### 9. Scheduled Automation with Jenkins

Jenkins is used to schedule the execution of the standalone daily scraping script.

The configured freestyle Jenkins job executes:

```bat
cd C:\path\to\news-headline-monitor
call venv\Scripts\activate
python run_daily.py
```

The local Jenkins job can be configured to execute daily using a cron schedule.

### 10. Docker Containerization

The project includes a Dockerfile and Docker Compose configuration.

The Compose configuration defines:

- A MySQL 8.0 database service.
- A Flask application service.
- Persistent MySQL storage through a named Docker volume.

The Dockerfile packages the Flask application and its Python dependencies.

---

## 🏗️ System Architecture

### Overall Architecture

```text
                   NEWS SOURCES
                        |
             +----------+----------+
             |          |          |
          THE HINDU    TOI      OTHER OUTLETS
             |          |          |
             +----------+----------+
                        |
                        v
                NEWS COLLECTION
                        |
             +----------+----------+
             |                     |
        STATIC SCRAPING       DYNAMIC SCRAPING
      Requests + BS4              Selenium
             |                     |
             +----------+----------+
                        |
                        v
                 NLP PROCESSING
                        |
          +-------------+-------------+
          |             |             |
       Sentiment      Entities     Category
       TextBlob        spaCy      Keyword Rules
          |             |             |
          +-------------+-------------+
                        |
                        v
                  MYSQL DATABASE
                        |
             +----------+----------+
             |                     |
       Historical Storage     Scrape Logs
             |
             v
         FLASK BACKEND
             |
          REST APIs
             |
             v
       HTML / CSS / JS
             |
             v
       WEB DASHBOARD
             |
             v
       USER INTERFACE


          JENKINS AUTOMATION
                 |
                 v
             run_daily.py
                 |
                 v
          Scheduled Scraping
```

### Application Request Flow

```text
User opens dashboard
        |
        v
Browser requests Flask application
        |
        v
Flask renders index.html
        |
        v
JavaScript calls REST endpoints
        |
        v
Flask retrieves information from MySQL
        |
        v
JSON responses are returned
        |
        v
Dashboard dynamically displays results
```

---

## 🛠️ Technology Stack

| Component | Technologies |
|---|---|
| Programming Language | Python |
| Frontend | HTML, CSS, JavaScript |
| Backend | Flask |
| API Communication | REST APIs, JSON |
| Web Scraping | Requests, BeautifulSoup, Selenium |
| NLP – Sentiment | TextBlob |
| NLP – Entity Recognition | spaCy |
| Database | MySQL |
| Text Similarity | SequenceMatcher, Set-Based Word Overlap, Entity Overlap |
| Automation | Jenkins |
| Containerization | Docker, Docker Compose |
| WSGI Server | Gunicorn |
| Configuration | python-dotenv |

---

## 📁 Project Structure

```text
news-headline-monitor/
│
├── templates/
│   └── index.html
│
├── docs/
│   └── screenshots/
│       ├── project-banner.png
│       └── demo-thumbnail.png
│
├── app.py
├── run_daily.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── Jenkinsfile
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Installation and Setup

### Prerequisites

Make sure the following are installed:

- Python 3.10
- MySQL 8.0
- Git
- Google Chrome (required if using Selenium-based dynamic scraping)
- Jenkins (required for scheduled automation)
- Docker and Docker Compose (optional)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/news-headline-monitor.git

cd news-headline-monitor
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```bat
venv\Scripts\activate
```

Activate it on Linux/macOS:

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip

pip install -r requirements.txt
```

### 4. Download the spaCy Language Model

```bash
python -m spacy download en_core_web_sm
```

### 5. Configure Environment Variables

Create a `.env` file in the project root.

Use `.env.example` as a reference:

```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=news_monitor

MYSQL_ROOT_PASSWORD=your_mysql_root_password
MYSQL_DATABASE=news_monitor
```

Replace the placeholder passwords with your actual MySQL credentials.

Never commit `.env` or real database credentials to GitHub.

### 6. Create the MySQL Database

Open MySQL and execute:

```sql
CREATE DATABASE news_monitor;
```

Ensure that the database connection configuration matches your local MySQL setup.

### 7. Run the Flask Application

```bash
python app.py
```

Open your browser:

```text
http://127.0.0.1:5000
```

### 8. Run the Daily Scraper Independently

To execute the standalone scraper:

```bash
python run_daily.py
```

This script collects headlines from the two sources currently configured in its `NEWS_SOURCES` dictionary, processes the data, and stores the results in MySQL.

---

## 🌐 REST API Endpoints

The Flask backend exposes the following endpoints:

| Endpoint | HTTP Method | Purpose |
|---|---|---|
| `/` | GET | Loads the dashboard |
| `/api/scrape` | POST | Starts manual scraping asynchronously |
| `/api/last-scrape` | GET | Retrieves the latest scraping information |
| `/api/headlines/today` | GET | Retrieves today's headlines |
| `/api/comparison` | GET | Compares today's headlines with yesterday's |
| `/api/entities` | GET | Retrieves frequently appearing entities |
| `/api/similar-groups` | GET | Retrieves groups of similar headlines across sources |

The frontend uses JavaScript `fetch()` to communicate with these endpoints.

Example:

```javascript
fetch('/api/headlines/today')
    .then(response => response.json())
    .then(data => {
        console.log(data);
    })
    .catch(error => {
        console.error('Error fetching headlines:', error);
    });
```

---

## 🧠 Headline Comparison Algorithm

The historical comparison engine uses a hybrid approach to identify headlines that may describe the same developing story.

### Similarity Components

**1. Sequence Similarity**

Uses Python's `SequenceMatcher` to compare the character sequences of two headlines.

**2. Important-Word Overlap**

Extracts meaningful words, removes common stop words, and compares the overlap between the two sets.

The overlap is calculated using a Jaccard-style ratio:

```text
Word Overlap =
    Number of Common Important Words
    ---------------------------------
    Number of Unique Words in Both Headlines
```

**3. Entity Overlap**

Uses extracted named entities to identify shared people, organizations, places, and other relevant entities.

### Combined Similarity

```text
Combined Score =
    (0.25 × Sequence Score)
  + (0.50 × Word Overlap Score)
  + (0.25 × Entity Overlap Score)
```

The highest-scoring historical match is used for classification.

The threshold is set to `0.25` in the current implementation.

---

## 🤖 Jenkins Automation

Jenkins automates the execution of the standalone scraper.

### Configuration

1. Create a Jenkins freestyle project named `NewsHeadlineMonitor`.
2. Configure the project to execute the daily scraper.
3. Add a periodic build trigger.
4. Configure the desired schedule.
5. Save and run a test build.

For an 11:00 AM daily schedule:

```text
0 11 * * *
```

The Jenkins timezone should be configured as `Asia/Kolkata` if the intended execution time is Indian Standard Time.

### Windows Build Command

```bat
cd C:\path\to\news-headline-monitor

call venv\Scripts\activate

python run_daily.py
```

### Expected Execution Flow

```text
Jenkins Scheduler
       |
       v
Build Triggered
       |
       v
Activate Python Environment
       |
       v
Execute run_daily.py
       |
       v
Scrape News Sources
       |
       v
Perform NLP Processing
       |
       v
Store Results in MySQL
       |
       v
Record Scraping Status
       |
       v
Build Completed
```

---

## 🐳 Docker Setup

The repository includes Docker configuration for running the Flask application and MySQL as separate services.

Build and start the services:

```bash
docker compose up --build -d
```

Check running containers:

```bash
docker ps
```

View logs:

```bash
docker compose logs -f
```

Stop the services:

```bash
docker compose down
```

The Compose configuration uses a named MySQL volume to persist database files.

---
## 👩‍💻 Author

**Sanjana Manne**

B.Tech – Computer Science and Engineering

JNTUH, Hyderabad

---
