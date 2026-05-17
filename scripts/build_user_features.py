"""
Build per-user aggregated features in the user_features table.

CRITICAL: Google Play user names are not unique. Default names like
"משתמש Google" or "Google User" are shared by thousands of different
anonymous reviewers. This script detects shared names by frequency and
excludes them before aggregating.

A name is considered a shared default if it appears more than
MAX_REVIEWS_PER_NAME times in the dataset.

Run after compute_sentiment.py:
    python scripts/build_user_features.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from tqdm import tqdm

from src.database.db import get_connection, init_database


MIN_REVIEWS_FOR_USER = 2        # Drop one-time reviewers
MAX_REVIEWS_PER_NAME = 50       # Above this, treat as shared/default name


def load_reviews_with_features() -> pd.DataFrame:
    """Load reviews joined with derived features."""
    sql = """
        SELECT
            r.review_id,
            r.app_id,
            r.user_name,
            r.score,
            r.review_date,
            r.developer_reply,
            rf.text_length,
            rf.sentiment_label
        FROM reviews r
        LEFT JOIN review_features rf ON r.review_id = rf.review_id
        WHERE r.user_name IS NOT NULL
          AND r.user_name != ''
          AND r.review_date IS NOT NULL
        ORDER BY r.user_name, r.review_date
    """
    with get_connection() as conn:
        df = pd.read_sql(sql, conn)
    df["developer_reply"] = df["developer_reply"].fillna("")
    df["text_length"] = df["text_length"].fillna(0)
    return df


def detect_shared_names(reviews: pd.DataFrame, threshold: int) -> dict:
    """Return dict of {name: count} for names exceeding threshold."""
    counts = reviews["user_name"].value_counts()
    shared = counts[counts > threshold].to_dict()
    return shared


def aggregate_user_features(reviews: pd.DataFrame) -> pd.DataFrame:
    """Compute per-user aggregates. Reviews dataframe must already be filtered."""
    groups = reviews.groupby("user_name")
    rows = []

    for user_name, g in tqdm(groups, total=len(groups), desc="Users"):
        n = len(g)
        if n < MIN_REVIEWS_FOR_USER:
            continue

        first_dt = pd.to_datetime(g["review_date"]).min()
        last_dt = pd.to_datetime(g["review_date"]).max()
        lifespan = max((last_dt - first_dt).days, 0)

        reviews_per_month = float(n) if lifespan == 0 else float(n) * 30.0 / lifespan

        sent_counts = g["sentiment_label"].dropna().value_counts()
        dominant_sentiment = sent_counts.index[0] if len(sent_counts) > 0 else None

        with_sentiment = g["sentiment_label"].notna().sum()
        if with_sentiment > 0:
            positive_ratio = float((g["sentiment_label"] == "Positive").sum()) / with_sentiment
            negative_ratio = float((g["sentiment_label"] == "Negative").sum()) / with_sentiment
        else:
            positive_ratio = None
            negative_ratio = None

        has_reply = (g["developer_reply"] != "").sum()
        response_rate = float(has_reply) / n

        user_key = f"{user_name}|{first_dt.strftime('%Y-%m-%d')}"

        rows.append({
            "user_key": user_key,
            "user_name": user_name,
            "total_reviews": n,
            "apps_reviewed": int(g["app_id"].nunique()),
            "avg_score": float(g["score"].mean()),
            "std_score": float(g["score"].std()) if n > 1 else 0.0,
            "avg_review_length": float(g["text_length"].mean()),
            "dominant_sentiment": dominant_sentiment,
            "first_review_date": first_dt.strftime("%Y-%m-%d"),
            "last_review_date": last_dt.strftime("%Y-%m-%d"),
            "lifespan_days": lifespan,
            "reviews_per_month": reviews_per_month,
            "positive_ratio": positive_ratio,
            "negative_ratio": negative_ratio,
            "dominant_topic": None,
            "developer_response_rate": response_rate,
        })

    return pd.DataFrame(rows)


def save_user_features(df: pd.DataFrame) -> None:
    """Drop and recreate user_features, then bulk-insert."""
    with get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS user_features")
        conn.commit()

    init_database()

    cols = list(df.columns)
    placeholders = ", ".join("?" * len(cols))
    col_names = ", ".join(cols)
    sql = f"INSERT INTO user_features ({col_names}) VALUES ({placeholders})"

    rows = [tuple(r) for r in df.itertuples(index=False)]
    with get_connection() as conn:
        conn.executemany(sql, rows)
        conn.commit()


def print_summary(user_features: pd.DataFrame, excluded_names: dict,
                  excluded_review_count: int, total_reviews: int) -> None:
    print()
    print("=" * 70)
    print("Shared/default name filtering")
    print("=" * 70)
    print(f"  Threshold: name with > {MAX_REVIEWS_PER_NAME} reviews = shared/default")
    print(f"  Shared names detected:        {len(excluded_names)}")
    print(f"  Reviews under shared names:   {excluded_review_count:,} "
          f"({100.0 * excluded_review_count / total_reviews:.1f}%)")

    if excluded_names:
        print("\n  Top 10 excluded names:")
        sorted_names = sorted(excluded_names.items(), key=lambda x: -x[1])
        for name, count in sorted_names[:10]:
            display_name = (name[:30] + "...") if len(name) > 33 else name
            print(f"    {display_name:<35s}  {count:>6,} reviews")

    print()
    print("=" * 70)
    print("User feature summary (real users only)")
    print("=" * 70)
    print(f"  Total users:                  {len(user_features):,}")
    print(f"  Avg reviews per user:         {user_features['total_reviews'].mean():.2f}")
    print(f"  Max reviews from one user:    {user_features['total_reviews'].max()}")
    print(f"  Multi-app users:              {(user_features['apps_reviewed'] > 1).sum():,}")
    print(f"  Users on 3+ apps:             {(user_features['apps_reviewed'] >= 3).sum():,}")
    print(f"  Avg score (across users):     {user_features['avg_score'].mean():.2f}")
    print(f"  Avg user lifespan (days):     {user_features['lifespan_days'].mean():.0f}")

    print("\n  Reviews-per-user distribution:")
    for cutoff in [2, 3, 5, 10, 20, 50]:
        n = (user_features['total_reviews'] >= cutoff).sum()
        pct = 100.0 * n / len(user_features) if len(user_features) > 0 else 0
        print(f"    >= {cutoff:>3d} reviews:  {n:>6,}  ({pct:5.1f}%)")

    print("\n  Dominant sentiment per user:")
    for label, count in user_features["dominant_sentiment"].value_counts(dropna=False).items():
        pct = 100.0 * count / len(user_features)
        label_str = str(label) if pd.notna(label) else "None"
        print(f"    {label_str:<10s}  {count:>6,}  ({pct:5.1f}%)")


def main() -> None:
    print("Loading reviews with features...")
    reviews = load_reviews_with_features()
    total_reviews = len(reviews)
    print(f"  {total_reviews:,} reviews loaded.")
    print(f"  {reviews['user_name'].nunique():,} unique user names.")

    print(f"\nDetecting shared/default names (threshold > {MAX_REVIEWS_PER_NAME} reviews)...")
    shared_names = detect_shared_names(reviews, MAX_REVIEWS_PER_NAME)
    excluded_review_count = sum(shared_names.values())
    print(f"  Found {len(shared_names)} shared names covering {excluded_review_count:,} reviews.")

    if shared_names:
        reviews_filtered = reviews[~reviews["user_name"].isin(shared_names.keys())]
    else:
        reviews_filtered = reviews
    print(f"  Reviews after filtering: {len(reviews_filtered):,}")
    print(f"  Unique names after filtering: {reviews_filtered['user_name'].nunique():,}")

    print(f"\nAggregating users (keeping only those with >= {MIN_REVIEWS_FOR_USER} reviews)...")
    user_features = aggregate_user_features(reviews_filtered)
    print(f"  {len(user_features):,} qualifying real users.")

    if len(user_features) == 0:
        print("No qualifying users. Aborting.")
        return

    print("\nSaving to user_features table...")
    save_user_features(user_features)
    print(f"  Saved {len(user_features):,} rows.")

    print_summary(user_features, shared_names, excluded_review_count, total_reviews)


if __name__ == "__main__":
    main()