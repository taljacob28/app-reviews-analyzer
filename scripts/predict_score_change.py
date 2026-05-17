"""
Predict whether a user's next review will be higher- or lower-scored than
their previous one.

All remaining features are known at the moment of prediction.

For each consecutive pair of reviews by the same user, builds a transition row
with features from the current review + user state up to that point.
Target: binary, score_{t+1} > score_t.

Trains and compares four models:
    1. Baseline: majority class
    2. Baseline: regression-to-mean rule (low → improve, high → decline)
    3. Logistic Regression
    4. Random Forest

Prints accuracy, AUC, feature importance, and confusion matrix.

Run after segment_users.py:
    python scripts/predict_score_change.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (
        accuracy_score, roc_auc_score,
        confusion_matrix, classification_report,
    )
except ImportError:
    print("scikit-learn is not installed. Run: pip install scikit-learn")
    sys.exit(1)

from src.database.db import get_connection


RANDOM_STATE = 42
TEST_SIZE = 0.25


def load_data() -> pd.DataFrame:
    """Load reviews joined with sentiment and user cluster info."""
    sql = """
        SELECT
            r.review_id,
            r.app_id,
            r.user_name,
            r.score,
            r.review_date,
            r.developer_reply,
            rf.text_length,
            rf.sentiment_label,
            uf.cluster_id,
            uf.user_key
        FROM reviews r
        LEFT JOIN review_features rf ON r.review_id = rf.review_id
        INNER JOIN user_features uf ON uf.user_name = r.user_name
        WHERE r.user_name IS NOT NULL
          AND r.user_name != ''
          AND r.review_date IS NOT NULL
        ORDER BY r.user_name, r.review_date
    """
    with get_connection() as conn:
        df = pd.read_sql(sql, conn)
    df["developer_reply"] = df["developer_reply"].fillna("")
    df["has_reply"] = (df["developer_reply"] != "").astype(int)
    df["review_date"] = pd.to_datetime(df["review_date"])
    df["text_length"] = df["text_length"].fillna(0)
    return df


def build_transitions(reviews: pd.DataFrame) -> pd.DataFrame:
    """Create one row per consecutive review pair from the same user."""
    transitions = []

    for user_name, g in reviews.groupby("user_name"):
        g = g.sort_values("review_date").reset_index(drop=True)
        if len(g) < 2:
            continue

        running_sum = 0.0
        for i in range(len(g) - 1):
            curr = g.iloc[i]
            nxt = g.iloc[i + 1]

            running_sum += curr["score"]
            running_mean = running_sum / (i + 1)

            transitions.append({
                "user_key":           curr["user_key"],
                "curr_score":         curr["score"],
                "curr_app_id":        curr["app_id"],
                "curr_sentiment":     curr["sentiment_label"],
                "curr_text_length":   curr["text_length"],
                "curr_has_reply":     curr["has_reply"],
                "transition_index":   i + 1,
                "running_mean_score": running_mean,
                "cluster_id":         curr["cluster_id"],
                "next_score":         nxt["score"],
                "improved":           int(nxt["score"] > curr["score"]),
                "declined":           int(nxt["score"] < curr["score"]),
                "same_score":         int(nxt["score"] == curr["score"]),
            })

    return pd.DataFrame(transitions)


def encode_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build feature matrix from the transition dataset.
    All features are known at prediction time (no leakage).
    """
    sent_map = {"Positive": 2, "Neutral": 1, "Negative": 0}
    apps = sorted(df["curr_app_id"].dropna().unique())
    app_map = {a: i for i, a in enumerate(apps)}

    X = pd.DataFrame()
    X["curr_score"]          = df["curr_score"]
    X["curr_text_length"]    = df["curr_text_length"]
    X["curr_has_reply"]      = df["curr_has_reply"]
    X["transition_index"]    = df["transition_index"]
    X["running_mean_score"]  = df["running_mean_score"]
    X["cluster_id"]          = df["cluster_id"].fillna(-1).astype(int)
    X["curr_app_encoded"]    = df["curr_app_id"].map(app_map).fillna(-1).astype(int)
    X["curr_sent_encoded"]   = df["curr_sentiment"].map(sent_map).fillna(-1).astype(int)
    return X


def print_target_distribution(transitions: pd.DataFrame) -> None:
    n = len(transitions)
    print()
    print("Target distribution across all transitions:")
    print(f"  Improved:  {transitions['improved'].sum():>6,}  ({100*transitions['improved'].mean():.1f}%)")
    print(f"  Same:      {transitions['same_score'].sum():>6,}  ({100*transitions['same_score'].mean():.1f}%)")
    print(f"  Declined:  {transitions['declined'].sum():>6,}  ({100*transitions['declined'].mean():.1f}%)")
    print(f"  Total:     {n:>6,}")


def main() -> None:
    print("Loading review data with cluster info...")
    reviews = load_data()
    print(f"  {len(reviews):,} reviews loaded.")
    print(f"  {reviews['user_name'].nunique():,} unique real users.")

    print("\nBuilding transitions...")
    transitions = build_transitions(reviews)
    print(f"  {len(transitions):,} transitions from {transitions['user_key'].nunique():,} users.")

    print_target_distribution(transitions)

    # Filter to transitions with actual change
    print("\nFiltering to transitions with score change (improved or declined)...")
    df_active = transitions[transitions["same_score"] == 0].copy().reset_index(drop=True)
    print(f"  {len(df_active):,} active transitions remain.")

    X = encode_features(df_active)
    y = df_active["improved"].values

    print(f"\nFeature matrix shape: {X.shape}  (8 features, all leak-free)")
    print(f"Class balance: improved = {y.sum()} ({100*y.mean():.1f}%), "
          f"declined = {len(y) - y.sum()} ({100*(1-y.mean()):.1f}%)")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    print(f"\nTrain: {len(X_train):,}, Test: {len(X_test):,}")

    results = {}

    # Baseline 1: majority class
    majority = int(np.round(y_train.mean()))
    pred_base1 = np.full(len(y_test), majority)
    results["Baseline (majority class)"] = (accuracy_score(y_test, pred_base1), None)

    # Baseline 2: regression-to-mean rule
    pred_base2 = np.where(
        X_test["curr_score"] <= 2, 1,
        np.where(X_test["curr_score"] >= 4, 0, majority)
    )
    results["Baseline (regression-to-mean)"] = (accuracy_score(y_test, pred_base2), None)

    # Logistic Regression
    print("\nTraining Logistic Regression...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    lr = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)
    lr.fit(X_train_scaled, y_train)
    pred_lr = lr.predict(X_test_scaled)
    proba_lr = lr.predict_proba(X_test_scaled)[:, 1]
    results["Logistic Regression"] = (
        accuracy_score(y_test, pred_lr),
        roc_auc_score(y_test, proba_lr),
    )

    print("  Coefficients (impact on probability of improvement):")
    for name, coef in sorted(zip(X.columns, lr.coef_[0]), key=lambda x: -abs(x[1])):
        sign = "+" if coef >= 0 else ""
        print(f"    {name:<24s}  {sign}{coef:.4f}")

    # Random Forest
    print("\nTraining Random Forest...")
    rf = RandomForestClassifier(n_estimators=200, random_state=RANDOM_STATE, n_jobs=-1)
    rf.fit(X_train, y_train)
    pred_rf = rf.predict(X_test)
    proba_rf = rf.predict_proba(X_test)[:, 1]
    results["Random Forest"] = (
        accuracy_score(y_test, pred_rf),
        roc_auc_score(y_test, proba_rf),
    )

    print("  Feature importance:")
    importances = sorted(zip(X.columns, rf.feature_importances_), key=lambda x: -x[1])
    for name, imp in importances:
        bar = "#" * int(imp * 100)
        print(f"    {name:<24s}  {imp:.4f}  {bar}")

    # Confusion matrix
    print("\n  Random Forest confusion matrix on test set:")
    cm = confusion_matrix(y_test, pred_rf)
    print(f"                  Pred Decline    Pred Improve")
    print(f"    True Decline   {cm[0,0]:>11d}     {cm[0,1]:>11d}")
    print(f"    True Improve   {cm[1,0]:>11d}     {cm[1,1]:>11d}")

    print("\n  Random Forest classification report:")
    print(classification_report(
        y_test, pred_rf,
        target_names=["Declined", "Improved"],
        digits=3,
    ))

    # Final summary table
    print("=" * 70)
    print("Summary: model comparison (production-clean)")
    print("=" * 70)
    print(f"  {'Model':<35s} {'Accuracy':>10s} {'AUC':>10s}")
    print("  " + "-" * 56)
    for name, (acc, auc) in results.items():
        auc_str = f"{auc:.3f}" if auc is not None else "-"
        print(f"  {name:<35s} {acc:>10.3f} {auc_str:>10s}")
    print()


if __name__ == "__main__":
    main()