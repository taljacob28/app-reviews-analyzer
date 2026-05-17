"""
Label sample reviews with topics using Claude API.

Samples N reviews stratified by sentiment, sends them in batches to Claude
Haiku for topic classification, and saves results to the review_topics table.

Topic categories (10 total):
    performance, stability, login_auth, security, ui_ux,
    customer_service, features, fees, praise, other

Run after compute_sentiment.py:
    python scripts/label_topics_with_llm.py                     # default 500 reviews
    python scripts/label_topics_with_llm.py --n 100             # smaller sample
    python scripts/label_topics_with_llm.py --n 20 --dry-run    # sample only, no API
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

# Load .env file manually (avoids needing python-dotenv as a dep)
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

try:
    from anthropic import Anthropic
except ImportError:
    print("anthropic SDK not installed. Run: pip install anthropic")
    sys.exit(1)

from src.database.db import get_connection


MODEL = "claude-haiku-4-5"
BATCH_SIZE = 10
DEFAULT_N = 500
RANDOM_STATE = 42

VALID_TOPICS = {
    "performance", "stability", "login_auth", "security", "ui_ux",
    "customer_service", "features", "fees", "praise", "other",
}

SYSTEM_PROMPT = """You classify Hebrew banking app reviews into ONE topic from this list:

- performance: speed, slowness, lag, response time
- stability: crashes, app not opening, freezes, bugs
- login_auth: authentication, login problems, password, biometrics, OTP
- security: trust concerns, fraud, account safety, suspicious activity
- ui_ux: interface design, usability, navigation, look & feel
- customer_service: support quality, human help, chat agents, call center
- features: missing or existing functionality (transfers, payments, etc.)
- fees: pricing, charges, transaction costs, account fees
- praise: positive review without specific complaint or feature mention
- other: doesn't fit other categories

The reviews are in Hebrew (some Arabic or English). Choose the SINGLE best-fit topic.
If a review mentions multiple topics, pick the dominant one.

Output ONLY valid JSON, no preamble, no explanation, no markdown:
{"reviews": [{"id": "<review_id>", "topic": "<topic>"}, ...]}
"""


def create_topics_table() -> None:
    """Create review_topics table with the schema this script needs.
    
    If an older incompatible schema exists, migrate by dropping (only safe
    when the existing table is empty, which is verified first).
    """
    needed_cols = {"review_id", "topic", "method", "labeled_at"}

    with get_connection() as conn:
        cur = conn.execute("PRAGMA table_info(review_topics)")
        existing_cols = {row[1] for row in cur.fetchall()}

        if existing_cols and not needed_cols.issubset(existing_cols):
            row_count = conn.execute("SELECT COUNT(*) FROM review_topics").fetchone()[0]
            if row_count == 0:
                print("  Old review_topics schema detected (0 rows). Recreating...")
                conn.execute("DROP TABLE review_topics")
                conn.commit()
            else:
                missing = needed_cols - existing_cols
                print(f"  Adding missing columns to review_topics: {missing}")
                for col in missing:
                    try:
                        conn.execute(f"ALTER TABLE review_topics ADD COLUMN {col} TEXT")
                    except Exception as e:
                        print(f"    Could not add {col}: {e}")
                conn.commit()

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS review_topics (
                review_id    TEXT PRIMARY KEY,
                topic        TEXT,
                method       TEXT,
                labeled_at   TEXT,
                FOREIGN KEY (review_id) REFERENCES reviews(review_id)
            );
            CREATE INDEX IF NOT EXISTS idx_review_topics_topic ON review_topics(topic);
            CREATE INDEX IF NOT EXISTS idx_review_topics_method ON review_topics(method);
        """)
        conn.commit()


def sample_reviews(n: int) -> pd.DataFrame:
    """Sample N reviews from DB, stratified by sentiment."""
    sql = """
        SELECT
            r.review_id,
            r.app_id,
            r.score,
            r.content,
            rf.sentiment_label
        FROM reviews r
        LEFT JOIN review_features rf ON r.review_id = rf.review_id
        WHERE r.content IS NOT NULL
          AND length(r.content) >= 15
          AND rf.sentiment_label IS NOT NULL
    """
    with get_connection() as conn:
        df = pd.read_sql(sql, conn)

    per_label = n // 3
    samples = []
    for label in ["Positive", "Negative", "Neutral"]:
        group = df[df["sentiment_label"] == label]
        n_take = min(per_label, len(group))
        if n_take > 0:
            samples.append(group.sample(n=n_take, random_state=RANDOM_STATE))

    result = pd.concat(samples).reset_index(drop=True)
    return result.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)


def get_already_labeled() -> set:
    with get_connection() as conn:
        df = pd.read_sql("SELECT review_id FROM review_topics WHERE method = 'llm'", conn)
    return set(df["review_id"].tolist())


def classify_batch(client: Anthropic, batch: pd.DataFrame) -> list:
    """Send one batch of reviews to Claude API, return list of (review_id, topic)."""
    reviews_text = "\n".join([
        f'ID {r["review_id"]}: "{str(r["content"])[:300]}"'
        for _, r in batch.iterrows()
    ])

    user_message = f"Classify these {len(batch)} reviews:\n\n{reviews_text}"

    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    text = response.content[0].text.strip()

    # Strip markdown code fences if Claude added them
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.startswith("json"):
                text = text[4:].strip()
            text = text.strip()

    try:
        parsed = json.loads(text)
        results = []
        for r in parsed.get("reviews", []):
            rid = r.get("id")
            topic = r.get("topic", "other").lower().strip()
            if topic not in VALID_TOPICS:
                topic = "other"
            results.append((rid, topic))
        return results
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"\n  Failed to parse response: {e}")
        print(f"  Raw response: {text[:300]}")
        return []


def save_labels(labels: list) -> None:
    if not labels:
        return
    now = datetime.now().isoformat()
    rows = [(rid, topic, "llm", now) for rid, topic in labels if rid]
    with get_connection() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO review_topics
               (review_id, topic, method, labeled_at) VALUES (?, ?, ?, ?)""",
            rows,
        )
        conn.commit()


def print_topic_summary() -> None:
    with get_connection() as conn:
        topic_dist = pd.read_sql(
            """SELECT topic, COUNT(*) AS n
               FROM review_topics
               WHERE method = 'llm'
               GROUP BY topic
               ORDER BY n DESC""",
            conn,
        )
    if len(topic_dist) == 0:
        return
    total = topic_dist["n"].sum()
    print()
    print("=" * 50)
    print("Topic distribution (LLM-labeled)")
    print("=" * 50)
    for _, r in topic_dist.iterrows():
        pct = 100.0 * r["n"] / total
        bar = "#" * int(pct / 2)
        print(f"  {r['topic']:<18s}  {int(r['n']):>5d}  ({pct:5.1f}%)  {bar}")
    print(f"  {'TOTAL':<18s}  {int(total):>5d}")


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM-based topic labeling")
    parser.add_argument("--n", type=int, default=DEFAULT_N,
                        help=f"Number of reviews to label (default {DEFAULT_N})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Sample reviews but don't call API")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE,
                        help=f"API batch size (default {BATCH_SIZE})")
    args = parser.parse_args()

    if "ANTHROPIC_API_KEY" not in os.environ:
        print("ANTHROPIC_API_KEY not found in environment.")
        print(f"Expected to find it in: {ENV_PATH}")
        print("Format: ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    print("Creating review_topics table...")
    create_topics_table()

    print(f"Sampling {args.n} reviews stratified by sentiment...")
    sample = sample_reviews(args.n)
    print(f"  Sampled {len(sample):,} reviews.")
    print(f"  Sentiment distribution: {sample['sentiment_label'].value_counts().to_dict()}")

    if args.dry_run:
        print("\nDry run. Showing 10 example reviews:")
        for _, r in sample.head(10).iterrows():
            content_preview = str(r['content'])[:80].replace("\n", " ")
            print(f"  [{r['sentiment_label']:<8s}] {content_preview}...")
        return

    # Skip already labeled
    already = get_already_labeled()
    if already:
        overlap = len(already & set(sample['review_id']))
        if overlap > 0:
            print(f"  Skipping {overlap} already-labeled reviews.")
            sample = sample[~sample["review_id"].isin(already)].reset_index(drop=True)

    if len(sample) == 0:
        print("Nothing to label.")
        print_topic_summary()
        return

    print(f"\nCalling Claude API ({MODEL}) in batches of {args.batch_size}...")
    client = Anthropic()

    n_batches = (len(sample) + args.batch_size - 1) // args.batch_size
    total_labeled = 0
    start_time = time.time()

    for i in range(0, len(sample), args.batch_size):
        batch = sample.iloc[i:i + args.batch_size]
        batch_num = (i // args.batch_size) + 1
        print(f"  Batch {batch_num:>3d}/{n_batches} ({len(batch):>2d} reviews)...",
              end=" ", flush=True)
        try:
            labels = classify_batch(client, batch)
            save_labels(labels)
            total_labeled += len(labels)
            print(f"labeled {len(labels)}.")
        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(0.3)

    elapsed = time.time() - start_time
    print(f"\nDone in {elapsed:.0f}s. Labeled {total_labeled:,} reviews total.")
    print_topic_summary()


if __name__ == "__main__":
    main()