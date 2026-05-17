"""
Analyze topic distribution across apps and segments.

For each app, computes:
- Volume and distribution of topics
- Concentration index vs overall average (lift)
- Top complaint topics

Compares:
- Digital banks vs traditional banks vs credit cards
- Top 3 Health Score apps vs Bottom 3
- Each app vs overall average

Run after label_topics_with_llm.py:
    python scripts/analyze_topics_by_app.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

from src.database.db import get_connection


# Topic order for consistent display
TOPIC_ORDER = [
    "praise", "stability", "features", "ui_ux", "customer_service",
    "login_auth", "performance", "other", "security", "fees",
]


def load_topics() -> pd.DataFrame:
    sql = """
        SELECT
            a.app_id,
            a.name,
            a.segment,
            rt.topic
        FROM review_topics rt
        JOIN reviews r ON rt.review_id = r.review_id
        JOIN apps a ON r.app_id = a.app_id
        WHERE rt.method = 'llm'
    """
    with get_connection() as conn:
        return pd.read_sql(sql, conn)


def per_app_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Topic % for each app."""
    pivot = pd.crosstab(df["name"], df["topic"])
    pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    cols = [c for c in TOPIC_ORDER if c in pct.columns]
    return pct[cols]


def concentration_index(df: pd.DataFrame) -> pd.DataFrame:
    """For each app, ratio of app% to overall% per topic. Values >1 = above avg."""
    pivot = pd.crosstab(df["name"], df["topic"])
    app_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    overall_pct = pivot.sum() / pivot.sum().sum() * 100
    lift = app_pct.div(overall_pct, axis=1)
    cols = [c for c in TOPIC_ORDER if c in lift.columns]
    return lift[cols]


def compare_segments(df: pd.DataFrame) -> pd.DataFrame:
    pivot = pd.crosstab(df["segment"], df["topic"])
    pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    cols = [c for c in TOPIC_ORDER if c in pct.columns]
    return pct[cols]


def compare_health_tiers(df: pd.DataFrame, top: list, bottom: list) -> pd.DataFrame:
    top_topics = df[df["name"].isin(top)]["topic"].value_counts(normalize=True) * 100
    bot_topics = df[df["name"].isin(bottom)]["topic"].value_counts(normalize=True) * 100

    comp = pd.DataFrame({
        "Top_3_pct": top_topics,
        "Bottom_3_pct": bot_topics,
    }).fillna(0)
    comp["Diff_Bottom_minus_Top"] = comp["Bottom_3_pct"] - comp["Top_3_pct"]
    comp = comp.reindex([t for t in TOPIC_ORDER if t in comp.index])
    return comp.round(1)


def identify_outliers(lift_df: pd.DataFrame, threshold_high: float = 1.5,
                      threshold_low: float = 0.5) -> list:
    """Return list of (app, topic, lift, direction) for unusually high or low cells."""
    outliers = []
    for app in lift_df.index:
        for topic in lift_df.columns:
            v = lift_df.loc[app, topic]
            if pd.isna(v):
                continue
            if v >= threshold_high:
                outliers.append((app, topic, v, "HIGH"))
            elif v <= threshold_low:
                outliers.append((app, topic, v, "LOW"))
    return outliers


def main() -> None:
    print("Loading topic data with app metadata...")
    df = load_topics()
    print(f"  {len(df):,} labeled reviews across {df['name'].nunique()} apps "
          f"and {df['topic'].nunique()} topics.")

    # 1. Per-app distribution
    print()
    print("=" * 130)
    print("1. Topic distribution per app (% of each app's labeled reviews)")
    print("=" * 130)
    per_app = per_app_distribution(df)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(per_app.round(1).to_string())

    # 2. Concentration index (lift vs overall)
    print()
    print("=" * 130)
    print("2. Concentration index (app % / overall %)")
    print("   Values > 1.0 = above average for this app, < 1.0 = below average")
    print("=" * 130)
    lift = concentration_index(df)
    print(lift.round(2).to_string())

    # 3. Highlighted outliers
    print()
    print("=" * 80)
    print("3. Notable outliers (lift >= 1.5 or <= 0.5)")
    print("=" * 80)
    outliers = identify_outliers(lift)
    if outliers:
        high = sorted([o for o in outliers if o[3] == "HIGH"], key=lambda x: -x[2])
        low = sorted([o for o in outliers if o[3] == "LOW"], key=lambda x: x[2])
        print("\n  HIGH concentration (this app talks about this topic more than average):")
        for app, topic, v, _ in high[:20]:
            print(f"    {app:<28s}  {topic:<18s}  lift = {v:.2f}x")
        print("\n  LOW concentration (this app rarely discusses this topic):")
        for app, topic, v, _ in low[:15]:
            print(f"    {app:<28s}  {topic:<18s}  lift = {v:.2f}x")
    else:
        print("  No outliers found at this threshold.")

    # 4. Segment comparison
    print()
    print("=" * 130)
    print("4. Topic distribution per segment")
    print("=" * 130)
    seg_dist = compare_segments(df)
    print(seg_dist.round(1).to_string())

    # 5. Health tier comparison
    print()
    print("=" * 80)
    print("5. Top 3 Health vs Bottom 3 Health (topic distribution gap)")
    print("=" * 80)
    top = ["First International Bank", "Cal", "Bank Leumi"]
    bottom = ["One Zero", "Discount Bank", "Mizrahi-Tefahot"]
    print(f"  Top 3: {', '.join(top)}")
    print(f"  Bottom 3: {', '.join(bottom)}")
    print()
    tier_comp = compare_health_tiers(df, top, bottom)
    print(tier_comp.to_string())

    # 6. Quick One Zero focus
    print()
    print("=" * 80)
    print("6. One Zero focus")
    print("=" * 80)
    if "One Zero" in df["name"].values:
        oz = df[df["name"] == "One Zero"]
        oz_dist = oz["topic"].value_counts(normalize=True) * 100
        overall = df["topic"].value_counts(normalize=True) * 100
        oz_table = pd.DataFrame({
            "One_Zero_pct": oz_dist,
            "Overall_pct": overall,
            "Lift": oz_dist / overall,
        }).fillna(0).reindex([t for t in TOPIC_ORDER if t in overall.index])
        print(oz_table.round(2).to_string())


if __name__ == "__main__":
    main()
