"""
Cleaning pipeline: load raw reviews from the DB, compute derived features,
and write them to the review_features table.

Run after scraping:
    python scripts/clean_data.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from tqdm import tqdm

from src.database.db import get_connection
from src.cleaning.text_cleaner import clean_text, count_emojis, extract_metadata
from src.cleaning.language import detect_language


def load_reviews() -> pd.DataFrame:
    """Pull every review from the database and normalize NaN in text columns."""
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT review_id, app_id, content, review_date, "
            "developer_reply, developer_reply_date "
            "FROM reviews",
            conn,
        )
    # Replace NaN (SQL NULL) with empty string for text columns.
    # Without this, pandas yields float NaN which breaks string operations.
    for col in ("content", "developer_reply"):
        df[col] = df[col].fillna("")
    return df


def compute_features(reviews: pd.DataFrame) -> pd.DataFrame:
    """Compute per-review derived features. Skips rows that error out."""
    rows = []
    skipped = 0

    for _, r in tqdm(reviews.iterrows(), total=len(reviews), desc="Features"):
        try:
            raw_content = r["content"] or ""
            content = clean_text(raw_content)
            meta = extract_metadata(content)
            language = detect_language(content)
            emoji_n = count_emojis(raw_content)
            has_reply = int(bool(r["developer_reply"]))

            time_to_reply = None
            if pd.notna(r["developer_reply_date"]) and pd.notna(r["review_date"]):
                try:
                    rdate = pd.to_datetime(r["review_date"])
                    rrdate = pd.to_datetime(r["developer_reply_date"])
                    time_to_reply = (rrdate - rdate).total_seconds() / 3600.0
                except Exception:
                    pass

            review_dt = (
                pd.to_datetime(r["review_date"])
                if pd.notna(r["review_date"])
                else None
            )

            rows.append({
                "review_id": r["review_id"],
                "text_length": meta["text_length"],
                "word_count": meta["word_count"],
                "language": language,
                "emoji_count": emoji_n,
                "has_emoji": int(emoji_n > 0),
                "exclamation_count": meta["exclamation_count"],
                "question_count": meta["question_count"],
                "all_caps_ratio": meta["all_caps_ratio"],
                "day_of_week": review_dt.dayofweek if review_dt is not None else None,
                "hour_of_day": review_dt.hour if review_dt is not None else None,
                "has_developer_reply": has_reply,
                "time_to_reply_hours": time_to_reply,
            })
        except Exception as e:
            skipped += 1
            if skipped <= 5:
                print(f"  [skip] review_id={r.get('review_id')}: {e}")

    if skipped:
        print(f"  Skipped {skipped} rows due to errors.")

    return pd.DataFrame(rows)


def save_features(features: pd.DataFrame) -> None:
    """Upsert features into the review_features table."""
    with get_connection() as conn:
        features.to_sql("review_features", conn, if_exists="replace", index=False)


def main() -> None:
    print("Loading reviews from database...")
    reviews = load_reviews()
    print(f"  Loaded {len(reviews)} reviews.")

    print("Computing derived features...")
    features = compute_features(reviews)
    print(f"  Computed features for {len(features)} reviews.")

    print("Saving features to database...")
    save_features(features)
    print("Done.")


if __name__ == "__main__":
    main()