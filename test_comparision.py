from app import get_db_connection
import re
from datetime import date, timedelta

conn = get_db_connection()
cursor = conn.cursor(dictionary=True)

today = date.today()
yesterday = today - timedelta(days=1)

cursor.execute("""
    SELECT headline
    FROM headlines
    WHERE scraped_date = %s
""", (today,))
today_rows = cursor.fetchall()

cursor.execute("""
    SELECT headline
    FROM headlines
    WHERE scraped_date = %s
""", (yesterday,))
yesterday_rows = cursor.fetchall()


def words(text):
    return set(re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()))


results = []

for t in today_rows:
    t_words = words(t["headline"])

    for y in yesterday_rows:
        y_words = words(y["headline"])

        common = t_words & y_words
        union = t_words | y_words

        score = len(common) / len(union) if union else 0

        results.append((
            score,
            t["headline"],
            y["headline"],
            common
        ))

results.sort(reverse=True)

print("\nTOP 20 WORD-OVERLAP PAIRS")
print("=" * 80)

for score, today_h, yesterday_h, common in results[:20]:
    print(f"\nOverlap: {score:.2f}")
    print("TODAY     :", today_h)
    print("YESTERDAY :", yesterday_h)
    print("COMMON    :", ", ".join(common))

cursor.close()
conn.close()