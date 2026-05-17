"""
Compute weekly Health Score for each app and write to app_weekly_metrics.

Run after compute_sentiment.py:
    python scripts/compute_health_score.py

Outputs:
    - Populated app_weekly_metrics table with per-app per-week metrics + health_score
    - Printed summary: top/bottom apps by current Health Score (last 8 weeks)
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.database.db import get_connection
from src.analysis.health_score import compute_health_score


def aggregate_weekly_metrics() -> pd.DataFrame:
    """SQL aggregation: weekly metrics per app.

    DictaBERT emits Title-cased labels ('Positive', 'Negative', 'Neutral'),
    so the CASE expressions match that capitalization.
    """
    sql = """
        SELECT
            r.app_id,
            strftime('%Y-%W', r.review_date) AS year_week,
            COUNT(*) AS review_count,
            AVG(r.score) AS avg_rating,
            AVG(CASE WHEN rf.sentiment_label = 'Positive' THEN 1.0 ELSE 0.0 END)
                AS sentiment_positive_ratio,
            AVG(CASE WHEN rf.sentiment_label = 'Negative' THEN 1.0 ELSE 0.0 END)
                AS sentiment_negative_ratio,
            AVG(CASE WHEN r.developer_reply IS NOT NULL AND r.developer_reply != ''
                     THEN 1.0 ELSE 0.0 END)
                AS developer_response_rate
        FROM reviews r
        LEFT JOIN review_features rf ON r.review_id = rf.review_id
        WHERE r.review_date IS NOT NULL
          AND r.score IS NOT NULL
        GROUP BY r.app_id, year_week
        ORDER BY r.app_id, year_week
    """
    with get_connection() as conn:
        return pd.read_sql(sql, conn)


def compute_momentum(metrics: pd.DataFrame, window: int = 4) -> pd.DataFrame:
    """Compute rolling momentum: change in avg_rating over `window` weeks."""
    metrics = metrics.sort_values(["app_id", "year_week"]).copy()
    metrics["momentum"] = (
        metrics.groupby("app_id")["avg_rating"]
        .transform(lambda s: s.diff(window))
        .fillna(0)
    )
    return metrics


def normalize_volume(metrics: pd.DataFrame) -> pd.DataFrame:
    """Add a volume_normalized column scaled within each app."""
    metrics = metrics.copy()
    metrics["volume_normalized"] = (
        metrics.groupby("app_id")["review_count"]
        .transform(lambda s: (s - s.min()) / (s.max() - s.min() + 1e-9))
    )
    return metrics


def sentiment_balance(metrics: pd.DataFrame) -> pd.DataFrame:
    """Add a sentiment_balance column: positive_ratio - negative_ratio."""
    metrics = metrics.copy()
    metrics["sentiment_balance"] = (
        metrics["sentiment_positive_ratio"] - metrics["sentiment_negative_ratio"]
    )
    return metrics


def print_summary(scored: pd.DataFrame) -> None:
    """Print top/bottom apps by current Health Score (last 8 weeks)."""
    print()
    print("=" * 70)
    print("Current Health Score (avg of last 8 weeks per app)")
    print("=" * 70)

    # Get last 8 weeks of data per app
    latest = (
        scored.sort_values(["app_id", "year_week"])
              .groupby("app_id")
              .tail(8)
    )

    # Join with apps table for names and segments
    with get_connection() as conn:
        apps_df = pd.read_sql("SELECT app_id, name, segment FROM apps", conn)

    summary = (
        latest.groupby("app_id")
              .agg(
                  health_score=("health_score", "mean"),
                  avg_rating=("avg_rating", "mean"),
                  sentiment_balance=("sentiment_balance", "mean"),
                  momentum=("momentum", "mean"),
                  review_count=("review_count", "sum"),
                  weeks_covered=("year_week", "nunique"),
              )
              .reset_index()
    )
    summary = summary.merge(apps_df, on="app_id", how="left")
    summary = summary.sort_values("health_score", ascending=False)

    print(
        f"  {'Rank':<5} {'Name':<28} {'Segment':<18} "
        f"{'Health':>7} {'Rating':>7} {'SentBal':>8} {'Momntm':>7}"
    )
    print("  " + "-" * 88)
    for i, r in enumerate(summary.itertuples(index=False), start=1):
        print(
            f"  {i:<5} {r.name:<28} {r.segment:<18} "
            f"{r.health_score:>7.2f} {r.avg_rating:>7.2f} "
            f"{r.sentiment_balance:>8.2f} {r.momentum:>+7.2f}"
        )


def main() -> None:
    print("Aggregating weekly metrics...")
    metrics = aggregate_weekly_metrics()
    print(f"  Aggregated {len(metrics):,} app-week rows.")

    if len(metrics) == 0:
        print("No data to process. Have you run compute_sentiment.py first?")
        return

    print("Computing derived components (momentum, volume, sentiment balance)...")
    metrics = compute_momentum(metrics)
    metrics = normalize_volume(metrics)
    metrics = sentiment_balance(metrics)

    print("Computing Health Score...")
    scored = compute_health_score(metrics)

    print("Saving to app_weekly_metrics...")
    with get_connection() as conn:
        scored.to_sql("app_weekly_metrics", conn, if_exists="replace", index=False)
    print(f"  Saved {len(scored):,} rows.")

    print_summary(scored)
    print()


if __name__ == "__main__":
    main()