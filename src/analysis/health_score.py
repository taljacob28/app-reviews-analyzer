"""
Composite Health Score computation per app per time window.

Weights come from src.config.HEALTH_SCORE_WEIGHTS.
Health Score = weighted sum of normalized components, scaled to 0-100.
"""

from typing import Dict
import pandas as pd

from src.config import HEALTH_SCORE_WEIGHTS


def _minmax(s: pd.Series) -> pd.Series:
    """Min-max normalize a series to [0, 1]. Constant series return 0.5."""
    if s.max() == s.min():
        return pd.Series([0.5] * len(s), index=s.index)
    return (s - s.min()) / (s.max() - s.min())


def compute_health_score(metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Compute Health Score for each row in `metrics`.

    Expected columns:
        avg_rating, sentiment_balance, momentum,
        volume_normalized, developer_response_rate

    Returns the input dataframe with an extra column 'health_score' (0-100).
    """
    df = metrics.copy()
    components = list(HEALTH_SCORE_WEIGHTS.keys())
    missing = [c for c in components if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    normalized = pd.DataFrame(index=df.index)
    for col in components:
        normalized[col] = _minmax(df[col])

    score = sum(
        normalized[col] * weight
        for col, weight in HEALTH_SCORE_WEIGHTS.items()
    )
    df["health_score"] = (score * 100).round(2)
    return df


def explain_score(row: pd.Series) -> Dict:
    """Return a per-component breakdown of a Health Score row."""
    return {
        col: {
            "raw": row[col],
            "weight": weight,
        }
        for col, weight in HEALTH_SCORE_WEIGHTS.items()
        if col in row.index
    }
