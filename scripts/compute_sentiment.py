"""
Sentiment analysis for Hebrew reviews using DictaBERT.

Run after clean_data.py. Updates review_features.sentiment_score and
review_features.sentiment_label for Hebrew reviews with non-trivial text.

Skips:
    - Reviews already classified (resume support).
    - Non-Hebrew reviews (language != 'he').
    - Empty or trivial reviews (text_length <= 2).

Checkpoints every 1,000 reviews so a crash mid-run loses at most a minute.

Usage:
    python scripts/compute_sentiment.py
    python scripts/compute_sentiment.py --limit 100         # quick test run
    python scripts/compute_sentiment.py --batch-size 16     # lower memory
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from tqdm import tqdm

from src.database.db import get_connection
from src.analysis.sentiment import load_sentiment_pipeline


CHECKPOINT_EVERY = 1000
DEFAULT_BATCH_SIZE = 32


def load_pending_reviews(limit: int = None) -> pd.DataFrame:
    """
    Return Hebrew reviews that don't yet have sentiment.
    Filters out empty content and very short text.
    """
    sql = """
        SELECT r.review_id, r.content
        FROM reviews r
        JOIN review_features rf ON r.review_id = rf.review_id
        WHERE rf.language = 'he'
          AND rf.text_length > 2
          AND rf.sentiment_label IS NULL
        ORDER BY r.review_id
    """
    if limit:
        sql += f" LIMIT {int(limit)}"

    with get_connection() as conn:
        df = pd.read_sql(sql, conn)
    df["content"] = df["content"].fillna("")
    return df


def save_sentiment_batch(results: list) -> None:
    """Update review_features with (label, score, review_id) tuples."""
    if not results:
        return
    with get_connection() as conn:
        conn.executemany(
            """
            UPDATE review_features
            SET sentiment_label = ?, sentiment_score = ?
            WHERE review_id = ?
            """,
            results,
        )
        conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute sentiment for Hebrew reviews")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Batch size for the pipeline (default {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N reviews (for testing)")
    args = parser.parse_args()

    print("Loading pending reviews...")
    reviews = load_pending_reviews(limit=args.limit)
    print(f"  {len(reviews):,} reviews need sentiment classification.")

    if len(reviews) == 0:
        print("Nothing to do.")
        return

    print("Loading DictaBERT sentiment pipeline...")
    print("  (first run will download ~500MB; subsequent runs use the cached model)")
    t0 = time.time()
    pipe = load_sentiment_pipeline()
    print(f"  Model loaded in {time.time() - t0:.1f}s.")

    print(f"Classifying in batches of {args.batch_size}...")
    pending_save = []
    pbar = tqdm(total=len(reviews), desc="Sentiment", unit="rev")

    for i in range(0, len(reviews), args.batch_size):
        chunk = reviews.iloc[i:i + args.batch_size]
        texts = [str(t)[:512] for t in chunk["content"].tolist()]

        try:
            outputs = pipe(texts, batch_size=args.batch_size)
        except Exception as e:
            print(f"\n  [batch error at index {i}]: {e}")
            print(f"  Skipping this batch and continuing.")
            pbar.update(len(chunk))
            continue

        for j, output in enumerate(outputs):
            review_id = chunk.iloc[j]["review_id"]
            label = output["label"]
            score = float(output["score"])
            pending_save.append((label, score, review_id))

        pbar.update(len(chunk))

        if len(pending_save) >= CHECKPOINT_EVERY:
            save_sentiment_batch(pending_save)
            pending_save = []

    # Final save
    if pending_save:
        save_sentiment_batch(pending_save)

    pbar.close()

    # Summary of what was added
    with get_connection() as conn:
        labels = conn.execute("""
            SELECT sentiment_label, COUNT(*) AS n
            FROM review_features
            WHERE sentiment_label IS NOT NULL
            GROUP BY sentiment_label
            ORDER BY n DESC
        """).fetchall()
    print("\nSentiment label distribution so far:")
    total = sum(r["n"] for r in labels)
    for r in labels:
        pct = 100.0 * r["n"] / total
        print(f"  {r['sentiment_label']:<10s} {r['n']:>7,}  {pct:5.1f}%")

    print("\nDone.")


if __name__ == "__main__":
    main()
