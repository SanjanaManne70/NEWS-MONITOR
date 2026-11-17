"""
Conversational, database-grounded assistant for News Headline Monitor.
Gemini interprets requests and explains results; Python alone builds SQL.
Conversation context is passed by the browser and is never persisted.
"""
import json
import os
import re
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types, errors

load_dotenv()
MODEL_NAME = "gemini-3.5-flash-lite"

ALLOWED_OPERATIONS = {
    "list_headlines", "count", "daily_count",
    "sentiment_breakdown", "source_breakdown", "top_entities"
}
ALLOWED_SENTIMENTS = {"positive", "negative", "neutral"}


def get_gemini_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    return genai.Client(api_key=key)


def call_gemini(prompt, json_mode=False):
    config = types.GenerateContentConfig(
        temperature=0.1,
        **({"response_mime_type": "application/json"} if json_mode else {})
    )
    client = get_gemini_client()
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME, contents=prompt, config=config
            )
            if not response.text:
                raise ValueError("Gemini returned an empty response.")
            return response.text.strip()
        except errors.ServerError as exc:
            if getattr(exc, "code", None) == 503 and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise


def extract_intent(question, history=None):
    history = history or []

    context = "\n".join(
        f"{m['role']}: {m['content'][:700]}"
        for m in history[-8:]
        if isinstance(m, dict)
        and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str)
    )

    prompt = f"""
You are an intelligent conversational assistant for a news-monitoring
database.

Your job is to understand natural-language questions, identify database
operations, and resolve follow-up questions using conversation history.

DATABASE TABLE: headlines

Columns:
id, source, headline, url, scraped_date, scraped_time, category,
sentiment (numeric), sentiment_label (positive/negative/neutral),
entities (JSON array with text and label).

SUPPORTED DATABASE OPERATIONS:
list_headlines
count
daily_count
sentiment_breakdown
source_breakdown
top_entities

Return valid JSON only, with exactly these keys:
{{
    "intent_type": "database|conversation|clarification",
    "operation": "list_headlines",
    "entity": null,
    "source": null,
    "sentiment": null,
    "category": null,
    "days": null,
    "sort": "newest",
    "limit": 20,
    "reply": null,
    "clarification_question": null
}}

IMPORTANT RULES:

1. CONVERSATIONAL BEHAVIOUR
- Greetings, thanks, and general questions about the assistant should
  use intent_type="conversation".
- Give a short, natural response in the reply field.
- Database questions must use intent_type="database".

2. NEVER ASK UNNECESSARY CLARIFICATION
- If the user's question has a reasonably clear database interpretation,
  execute it directly.
- Do not ask whether the user wants a count or a list when the question
  already indicates an analytical operation.
- Do not treat analytical questions as ambiguous.

3. ANALYTICAL QUERY RECOGNITION

A. Highest negative coverage:
Questions such as:
- Which source has the highest negative coverage?
- Which news outlet reports the most negative stories?
- Which publisher has the most negative headlines?
- Which source has the highest number of negative articles?

Set:
intent_type = "database"
operation = "source_breakdown"
sentiment = "negative"
sort = "highest_count"

B. Highest positive coverage:
Questions such as:
- Which source has the highest positive coverage?
- Which outlet reports the most positive stories?

Set:
intent_type = "database"
operation = "source_breakdown"
sentiment = "positive"
sort = "highest_count"

C. Highest headline count:
Questions such as:
- Which source has the most headlines?
- Which publisher publishes the most articles?

Set:
intent_type = "database"
operation = "source_breakdown"
sentiment = null
sort = "highest_count"

D. Sentiment comparison:
- Compare positive, negative and neutral coverage.
  => operation="sentiment_breakdown"

E. Source comparison:
- Compare headlines across sources.
- Show headline distribution by publisher.
  => operation="source_breakdown"

F. Entity analysis:
- Which companies are mentioned most?
- Which entities appear most frequently?
  => operation="top_entities"

4. OTHER OPERATION MAPPING
- "how many headlines" => count
- "daily counts", "by day", "trend over time" => daily_count
- "sentiment distribution" => sentiment_breakdown
- "compare sources", "group by source" => source_breakdown
- "top mentioned entities" => top_entities
- Ordinary headline searches => list_headlines

5. SENTIMENT RECOGNITION
- bad, negative, unfavourable => negative
- good, positive, favourable => positive
- neutral => neutral
- "top positive headlines" => list_headlines,
  sentiment="positive", sort="best_sentiment"
- "top negative headlines" => list_headlines,
  sentiment="negative", sort="worst_sentiment"

6. FILTER RECOGNITION
- Identify publishers as source.
- Identify companies, people and places as entity.
- Extract category when explicitly mentioned.
- "last N days" => days=N
- "this week" => days=7
- "this month" => days=30
- "today" => days=1
- "yesterday" => days=2
- "all time", "ever", or no date => days=null
- Never assume today when no date is specified.

7. FOLLOW-UP CONVERSATIONS
Use the recent conversation to understand follow-up questions.

Examples:
- "What about negative ones?"
- "Only BBC."
- "Now last 30 days."
- "And positive?"
- "Show me the top 5."

Preserve previous filters unless the user explicitly changes or removes
them.

Use only the latest user message as the new request.
Do not interpret the assistant's previous answer as a new filter.

If the user asks "what about positive ones?" after a negative query,
change sentiment to positive while preserving other applicable filters.

8. SORTING
- newest => newest first
- oldest => oldest first
- highest_count => highest count first
- best_sentiment => highest sentiment first
- worst_sentiment => lowest sentiment first

9. LIMIT
- Default limit = 20.
- User-requested limits must be between 1 and 100.

10. CLARIFICATION
Ask one concise question only if an essential detail is genuinely missing.
Never invent database facts.
Never generate SQL.
Never claim that a database query has already been executed.

RECENT CONVERSATION:
{context if context else "(none)"}

LATEST USER MESSAGE:
{question}
"""

    raw = call_gemini(prompt, json_mode=True)

    raw = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        raw,
        flags=re.I
    ).strip()

    result = json.loads(raw)

    if not isinstance(result, dict):
        raise ValueError("Gemini returned an invalid intent.")

    required_keys = {
        "intent_type",
        "operation",
        "entity",
        "source",
        "sentiment",
        "category",
        "days",
        "sort",
        "limit",
        "reply",
        "clarification_question"
    }

    if set(result.keys()) != required_keys:
        raise ValueError("Gemini returned an unexpected intent structure.")

    allowed_intent_types = {
        "database",
        "conversation",
        "clarification"
    }

    allowed_operations = {
        "list_headlines",
        "count",
        "daily_count",
        "sentiment_breakdown",
        "source_breakdown",
        "top_entities"
    }

    allowed_sentiments = {
        None,
        "positive",
        "negative",
        "neutral"
    }

    allowed_sorts = {
        "newest",
        "oldest",
        "highest_count",
        "best_sentiment",
        "worst_sentiment"
    }

    if result["intent_type"] not in allowed_intent_types:
        raise ValueError("Invalid intent type returned by Gemini.")

    if result["operation"] not in allowed_operations:
        raise ValueError("Unsupported database operation.")

    if result["sentiment"] not in allowed_sentiments:
        raise ValueError("Invalid sentiment returned by Gemini.")

    if result["sort"] not in allowed_sorts:
        raise ValueError("Invalid sorting option returned by Gemini.")

    if result["days"] is not None:
        if (
            not isinstance(result["days"], int)
            or isinstance(result["days"], bool)
            or not 1 <= result["days"] <= 3650
        ):
            raise ValueError("Invalid date range returned by Gemini.")

    if (
        not isinstance(result["limit"], int)
        or isinstance(result["limit"], bool)
        or not 1 <= result["limit"] <= 100
    ):
        result["limit"] = 20

    return result


def validate_intent(data):
    kind = data.get("intent_type", "database")
    if kind == "conversation":
        return {"intent_type": kind,
                "reply": str(data.get("reply") or "Hi! I can help you explore your stored news.").strip()[:1000]}
    if kind == "clarification":
        return {"intent_type": kind,
                "reply": str(data.get("clarification_question") or "Could you clarify what news you want to explore?").strip()[:500]}

    op = data.get("operation")
    if op not in ALLOWED_OPERATIONS:
        raise ValueError("I couldn't map that request to a supported news query.")

    clean = {"intent_type": "database", "operation": op}
    for field in ("entity", "source", "category"):
        value = data.get(field)
        if value is not None:
            if not isinstance(value, str) or not value.strip() or len(value) > 150:
                raise ValueError(f"Invalid {field} filter.")
            value = value.strip()
        clean[field] = value

    sentiment = data.get("sentiment")
    if sentiment is not None:
        sentiment = str(sentiment).strip().lower()
        if sentiment not in ALLOWED_SENTIMENTS:
            raise ValueError("Unsupported sentiment filter.")
    clean["sentiment"] = sentiment

    days = data.get("days")
    if days is not None and (
        isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 3650
    ):
        raise ValueError("Date range must be between 1 and 3650 days.")
    clean["days"] = days

    sort = data.get("sort", "newest")
    clean["sort"] = sort if sort in {"newest", "best_sentiment", "worst_sentiment"} else "newest"
    limit = data.get("limit", 20)
    if isinstance(limit, bool) or not isinstance(limit, int):
        limit = 20
    clean["limit"] = max(1, min(limit, 100))
    return clean


def build_filters(intent):
    conditions, params = [], []
    if intent.get("entity"):
        pattern = f"%{intent['entity']}%"
        conditions.append(
            "(LOWER(headline) LIKE LOWER(%s) OR "
            "LOWER(CAST(entities AS CHAR)) LIKE LOWER(%s))"
        )
        params.extend([pattern, pattern])
    if intent.get("source"):
        conditions.append("LOWER(source) LIKE LOWER(%s)")
        params.append(f"%{intent['source']}%")
    if intent.get("sentiment"):
        conditions.append("LOWER(sentiment_label) = %s")
        params.append(intent["sentiment"])
    if intent.get("category"):
        conditions.append("LOWER(category) LIKE LOWER(%s)")
        params.append(f"%{intent['category']}%")
    if intent.get("days") is not None:
        conditions.append("scraped_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)")
        params.append(intent["days"])
    return (" WHERE " + " AND ".join(conditions) if conditions else ""), params



def execute_news_query(connection, intent):
    where, params = build_filters(intent)

    op = intent["operation"]
    sort = intent.get("sort", "newest")
    limit = intent.get("limit", 20)

    cursor = connection.cursor(dictionary=True)

    try:
        # --------------------------------------------------
        # 1. DATABASE COVERAGE INFORMATION
        # --------------------------------------------------
        cursor.execute(
            """
            SELECT
                MIN(scraped_date) AS oldest_date,
                MAX(scraped_date) AS newest_date,
                COUNT(*) AS total
            FROM headlines
            """
        )

        coverage_row = cursor.fetchone() or {}

        coverage = {
            "oldest_date": (
                str(coverage_row["oldest_date"])
                if coverage_row.get("oldest_date") else None
            ),
            "newest_date": (
                str(coverage_row["newest_date"])
                if coverage_row.get("newest_date") else None
            ),
            "total_records": int(coverage_row.get("total") or 0)
        }

        # --------------------------------------------------
        # 2. TOP MENTIONED ENTITIES
        # --------------------------------------------------
        if op == "top_entities":

            entity_intent = dict(intent)
            entity_intent["entity"] = None

            entity_where, entity_params = build_filters(entity_intent)

            cursor.execute(
                "SELECT entities FROM headlines" + entity_where,
                tuple(entity_params)
            )

            counts = {}

            for row in cursor.fetchall():
                try:
                    values = row.get("entities")

                    if isinstance(values, str):
                        values = json.loads(values)

                    for item in values or []:
                        name = (
                            item.get("text")
                            if isinstance(item, dict)
                            else None
                        )

                        if name:
                            counts[name] = counts.get(name, 0) + 1

                except (ValueError, TypeError, AttributeError):
                    continue

            results = [
                {"entity": name, "total": total}
                for name, total in sorted(
                    counts.items(),
                    key=lambda pair: pair[1],
                    reverse=True
                )[:20]
            ]

            return {
                "operation": op,
                "count": len(results),
                "results": results,
                "coverage": coverage
            }

        # --------------------------------------------------
        # 3. COUNT HEADLINES
        # --------------------------------------------------
        if op == "count":

            sql = (
                "SELECT COUNT(*) AS total "
                "FROM headlines"
                + where
            )

        # --------------------------------------------------
        # 4. DAILY HEADLINE COUNTS
        # --------------------------------------------------
        elif op == "daily_count":

            sql = (
                "SELECT scraped_date, COUNT(*) AS total "
                "FROM headlines"
                + where +
                " GROUP BY scraped_date "
                "ORDER BY scraped_date DESC"
            )

        # --------------------------------------------------
        # 5. SENTIMENT BREAKDOWN
        # --------------------------------------------------
        elif op == "sentiment_breakdown":

            sql = (
                "SELECT LOWER(sentiment_label) AS sentiment, "
                "COUNT(*) AS total "
                "FROM headlines"
                + where +
                " GROUP BY LOWER(sentiment_label) "
                "ORDER BY total DESC"
            )

        # --------------------------------------------------
        # 6. SOURCE-WISE ANALYSIS
        # --------------------------------------------------
        elif op == "source_breakdown":

            # When sentiment is negative, this query counts
            # only negative headlines for each source.
            #
            # When sentiment is positive, it counts only
            # positive headlines for each source.
            #
            # When sentiment is None, it counts all headlines.

            order = "total DESC"

            if sort == "highest_count":
                order = "total DESC"

            elif sort == "oldest":
                order = "total ASC"

            sql = (
                "SELECT source, COUNT(*) AS total "
                "FROM headlines"
                + where +
                " GROUP BY source "
                f"ORDER BY {order}"
            )

        # --------------------------------------------------
        # 7. NORMAL HEADLINE SEARCH
        # --------------------------------------------------
        else:

            order_options = {
                "newest": "scraped_date DESC, scraped_time DESC",
                "oldest": "scraped_date ASC, scraped_time ASC",
                "best_sentiment": (
                    "sentiment DESC, scraped_date DESC, scraped_time DESC"
                ),
                "worst_sentiment": (
                    "sentiment ASC, scraped_date DESC, scraped_time DESC"
                )
            }

            order = order_options.get(
                sort,
                "scraped_date DESC, scraped_time DESC"
            )

            sql = (
                "SELECT id, source, headline, url, "
                "scraped_date, scraped_time, category, "
                "sentiment_label, sentiment "
                "FROM headlines"
                + where +
                f" ORDER BY {order} LIMIT %s"
            )

            params = list(params) + [limit]

        # --------------------------------------------------
        # 8. EXECUTE QUERY
        # --------------------------------------------------
        cursor.execute(sql, tuple(params))

        rows = cursor.fetchall()

        # --------------------------------------------------
        # 9. PROCESS RESULTS
        # --------------------------------------------------
        if op == "count":

            results = []

            count = int(rows[0]["total"]) if rows else 0

        elif op in {
            "daily_count",
            "sentiment_breakdown",
            "source_breakdown"
        }:

            results = rows

            for row in results:

                if row.get("scraped_date"):
                    row["scraped_date"] = str(
                        row["scraped_date"]
                    )

                if row.get("total") is not None:
                    row["total"] = int(row["total"])

            count = sum(
                int(row["total"])
                for row in results
            )

        else:

            results = rows

            for row in results:

                if row.get("scraped_date"):
                    row["scraped_date"] = str(
                        row["scraped_date"]
                    )

                if row.get("scraped_time"):
                    row["scraped_time"] = str(
                        row["scraped_time"]
                    )

            count = len(results)

        # --------------------------------------------------
        # 10. RETURN STRUCTURED RESPONSE
        # --------------------------------------------------
        return {
            "operation": op,
            "count": count,
            "results": results,
            "coverage": coverage
        }

    finally:
        cursor.close()


def fallback_answer(intent, data):
    coverage = data.get("coverage", {})
    if data["count"] == 0:
        if coverage.get("total_records"):
            return (f"No matching headlines were found. Your database contains "
                    f"{coverage['total_records']} records dated from "
                    f"{coverage.get('oldest_date')} to {coverage.get('newest_date')}. "
                    "The requested period may be outside the dates currently stored.")
        return "Your headlines database is currently empty."
    op = intent["operation"]
    if op == "count":
        return f"I found {data['count']} matching headlines."
    if op == "daily_count":
        return f"I found {data['count']} headlines across {len(data['results'])} recorded dates."
    return f"I found {data['count']} matching results. Here is the breakdown."


def compose_answer(question, intent, data):
    prompt = f"""
You are a helpful conversational assistant in a news monitoring dashboard.
Explain the database result in natural language.
Use ONLY the supplied database result for factual claims. Never invent counts,
headlines, sources, dates or sentiment. For zero matches, explain the database's
overall date coverage and distinguish stale coverage from an empty database.
Keep it concise. Do not mention SQL or JSON.

User question: {question}
Validated filters: {json.dumps(intent)}
Actual database result: {json.dumps(data, default=str, ensure_ascii=False)}
"""
    try:
        return call_gemini(prompt)
    except Exception:
        # Keep a successful database answer useful even during Gemini 503 outages.
        return fallback_answer(intent, data)


def process_natural_language_query(question, connection, history=None):
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Please enter a question.")
    if len(question) > 1000:
        raise ValueError("Question is too long.")

    intent = validate_intent(extract_intent(question.strip(), history))
    if intent["intent_type"] == "conversation":
        return {"status": "conversation", "message": intent["reply"], "results": []}
    if intent["intent_type"] == "clarification":
        return {"status": "clarification_required", "message": intent["reply"], "results": []}

    data = execute_news_query(connection, intent)
    return {
        "status": "success",
        "message": compose_answer(question.strip(), intent, data),
        "intent": intent,
        **data
    }
