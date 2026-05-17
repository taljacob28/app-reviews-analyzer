"""
Segment users via K-Means clustering on 10 behavioral features.

Workflow:
    1. Load user_features (filter to users with sentiment data).
    2. Standardize feature matrix.
    3. Run K from 2 to 10, compute inertia (elbow) and silhouette.
    4. Auto-select k with highest silhouette unless --k is given.
    5. Fit final K-Means, save cluster_id back to user_features.
    6. Print cluster profiles and suggest persona labels.

Run after build_user_features.py:
    python scripts/segment_users.py             # auto-select k
    python scripts/segment_users.py --k 5       # manual k
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score
except ImportError:
    print("scikit-learn is not installed. Run: pip install scikit-learn")
    sys.exit(1)

from src.database.db import get_connection


FEATURE_COLUMNS = [
    "total_reviews",
    "apps_reviewed",
    "avg_score",
    "std_score",
    "avg_review_length",
    "lifespan_days",
    "reviews_per_month",
    "positive_ratio",
    "negative_ratio",
    "developer_response_rate",
]

K_RANGE = range(2, 11)
RANDOM_STATE = 42


def load_user_features() -> pd.DataFrame:
    sql = """
        SELECT * FROM user_features
        WHERE positive_ratio IS NOT NULL
          AND negative_ratio IS NOT NULL
    """
    with get_connection() as conn:
        return pd.read_sql(sql, conn)


def prepare_features(users: pd.DataFrame):
    """Standardize feature matrix; fill NaN with column means."""
    X_raw = users[FEATURE_COLUMNS].copy()
    X_raw = X_raw.fillna(X_raw.mean())
    scaler = StandardScaler()
    X = scaler.fit_transform(X_raw)
    return X, scaler


def evaluate_k_range(X) -> pd.DataFrame:
    """Compute inertia and silhouette for each k."""
    results = []
    for k in K_RANGE:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = km.fit_predict(X)
        sil = silhouette_score(X, labels)
        results.append({
            "k": k,
            "inertia": km.inertia_,
            "silhouette": sil,
        })
    return pd.DataFrame(results)


def fit_kmeans(X, k):
    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    labels = km.fit_predict(X)
    return labels, km


def save_cluster_ids(users: pd.DataFrame, labels) -> None:
    """Add cluster_id column to user_features if missing, then update rows."""
    with get_connection() as conn:
        cols = pd.read_sql("PRAGMA table_info(user_features)", conn)
        if "cluster_id" not in cols["name"].values:
            conn.execute("ALTER TABLE user_features ADD COLUMN cluster_id INTEGER")
            conn.commit()

        updates = list(zip([int(c) for c in labels], users["user_key"].tolist()))
        conn.executemany(
            "UPDATE user_features SET cluster_id = ? WHERE user_key = ?",
            updates,
        )
        conn.commit()


def print_cluster_profiles(users: pd.DataFrame, labels) -> pd.DataFrame:
    """Print mean of each feature per cluster."""
    users = users.copy()
    users["cluster_id"] = labels

    print()
    print("=" * 110)
    print("Cluster profiles (mean of each feature per cluster)")
    print("=" * 110)

    profiles = users.groupby("cluster_id").agg(
        n=("user_key", "count"),
        **{c: (c, "mean") for c in FEATURE_COLUMNS},
    )

    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    print(profiles.round(2).T)

    print()
    print("Dominant sentiment distribution per cluster:")
    sent = users.groupby("cluster_id")["dominant_sentiment"].value_counts(normalize=True).unstack(fill_value=0)
    print(sent.round(3))

    return profiles


def suggest_persona(profile: pd.Series) -> str:
    """Heuristic persona name from feature averages."""
    parts = []

    if profile["avg_score"] >= 4.0:
        parts.append("Happy")
    elif profile["avg_score"] <= 2.5:
        parts.append("Angry")
    else:
        parts.append("Mixed")

    if profile["avg_review_length"] >= 200:
        parts.append("Detailed")
    elif profile["avg_review_length"] < 30:
        parts.append("Brief")

    if profile["apps_reviewed"] >= 3:
        parts.append("Multi-bank")
    elif profile["apps_reviewed"] >= 2:
        parts.append("Switcher")

    if profile["total_reviews"] >= 5:
        parts.append("Frequent")

    return " ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="K-Means user segmentation")
    parser.add_argument("--k", type=int, help="Override k (else auto-select via silhouette)")
    args = parser.parse_args()

    print("Loading user_features...")
    users = load_user_features()
    print(f"  {len(users):,} users with sentiment data.")

    if len(users) < 50:
        print("Too few users for clustering. Aborting.")
        return

    print("Preparing standardized feature matrix...")
    X, scaler = prepare_features(users)
    print(f"  Matrix shape: {X.shape}  ({X.shape[0]:,} users x {X.shape[1]} features)")

    print(f"\nEvaluating k from {min(K_RANGE)} to {max(K_RANGE)}...")
    eval_df = evaluate_k_range(X)
    print()
    print(f"  {'k':<4} {'inertia':>12} {'silhouette':>12}")
    print("  " + "-" * 30)
    for _, row in eval_df.iterrows():
        print(f"  {int(row['k']):<4} {row['inertia']:>12.1f} {row['silhouette']:>12.4f}")

    auto_k = int(eval_df.loc[eval_df["silhouette"].idxmax(), "k"])
    print(f"\n  Auto-selected k (max silhouette): {auto_k}")

    k = args.k if args.k else auto_k
    if args.k:
        print(f"  Using manual k = {k}")
    else:
        print(f"  Using auto k = {k}")

    print(f"\nFitting final K-Means with k={k}...")
    labels, km = fit_kmeans(X, k)

    print("Saving cluster_id back to user_features...")
    save_cluster_ids(users, labels)
    print(f"  Updated {len(users):,} rows.")

    profiles = print_cluster_profiles(users, labels)

    print()
    print("=" * 70)
    print("Suggested persona labels")
    print("=" * 70)
    for cluster_id in sorted(set(labels)):
        n_users = int((labels == cluster_id).sum())
        pct = 100.0 * n_users / len(labels)
        persona = suggest_persona(profiles.loc[cluster_id])
        print(f"  Cluster {cluster_id} (n={n_users:,}, {pct:.1f}%):  {persona}")
    print()


if __name__ == "__main__":
    main()
