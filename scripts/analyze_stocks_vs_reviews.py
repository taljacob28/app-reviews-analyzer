"""
Cross-source analysis: app Health Score vs stock returns.

For each app linked to a TASE-listed company (directly or via parent),
this script computes:
    1. Contemporaneous correlation between weekly Health Score and weekly
       stock return.
    2. Lead/lag correlation across -8 to +8 weeks to detect whether the app
       signal leads or lags the stock.

Run after compute_health_score.py and fetch_stock_prices.py:
    python scripts/analyze_stocks_vs_reviews.py

Output:
    - Printed correlation table per app
    - Saved to new table health_stock_correlations for reuse
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

from src.database.db import get_connection


# Map each app to its primary stock ticker (direct listing or parent company)
APP_TICKER_MAP = {
    # Direct listings
    "com.ideomobile.hapoalim":    "POLI.TA",
    "com.leumi.leumiwallet":      "LUMI.TA",
    "com.ideomobile.discount":    "DSCT.TA",
    "com.MizrahiTefahot.nh":      "MZTF.TA",
    "com.fibi.nativeapp":         "FIBIH.TA",
    "com.isracard.hatavot":       "ISCD.TA",
    # Subsidiaries -> parent
    "com.ideomobile.mercantile":  "DSCT.TA",   # Mercantile is owned by Discount
    "com.onoapps.cal4u":          "DSCT.TA",   # Cal is owned by Discount
    "com.pepper.ldb":             "LUMI.TA",   # Pepper is a Leumi sub-brand
    # Purely private
    # "il.co.firstdigitalbank":    None,        # One Zero
    # "com.ideomobile.leumicard":  None,        # Max (Warburg Pincus)
}

LAG_RANGE = range(-8, 9)   # weeks to test
MIN_OVERLAPPING_WEEKS = 12


def load_weekly_health_score() -> pd.DataFrame:
    sql = """
        SELECT app_id, year_week, health_score,
               avg_rating, sentiment_balance, momentum
        FROM app_weekly_metrics
        ORDER BY app_id, year_week
    """
    with get_connection() as conn:
        return pd.read_sql(sql, conn)


def load_weekly_stock_returns() -> pd.DataFrame:
    """Aggregate stock prices to weekly level using last close of each week."""
    sql = """
        WITH ranked AS (
            SELECT
                ticker,
                date,
                close,
                strftime('%Y-%W', date) AS year_week,
                ROW_NUMBER() OVER (
                    PARTITION BY ticker, strftime('%Y-%W', date)
                    ORDER BY date DESC
                ) AS rn
            FROM stock_prices
            WHERE close IS NOT NULL
        )
        SELECT
            ticker,
            year_week,
            date AS week_end_date,
            close AS week_close
        FROM ranked
        WHERE rn = 1
        ORDER BY ticker, year_week
    """
    with get_connection() as conn:
        df = pd.read_sql(sql, conn)

    df = df.sort_values(["ticker", "year_week"])
    df["weekly_return"] = df.groupby("ticker")["week_close"].pct_change()
    return df


def corr_with_lag(merged: pd.DataFrame, x_col: str, y_col: str, lag: int):
    """
    Compute Pearson corr between x_t and y_{t+lag}.
    Positive lag means x leads y. Returns (corr, n_obs) or (None, 0).
    """
    df = merged.copy().sort_values("year_week")
    df["_y_shifted"] = df[y_col].shift(-lag)
    valid = df.dropna(subset=[x_col, "_y_shifted"])
    if len(valid) < MIN_OVERLAPPING_WEEKS:
        return None, len(valid)
    return valid[x_col].corr(valid["_y_shifted"]), len(valid)


def analyze_app(app_id: str, ticker: str,
                health_df: pd.DataFrame, stock_df: pd.DataFrame) -> dict:
    """Compute zero-lag and best-lag correlations for one app-ticker pair."""
    h = health_df[health_df["app_id"] == app_id].copy()
    s = stock_df[stock_df["ticker"] == ticker].copy()
    if len(h) == 0 or len(s) == 0:
        return None

    merged = h.merge(s, on="year_week", how="inner")
    merged = merged.dropna(subset=["health_score", "weekly_return"])
    if len(merged) < MIN_OVERLAPPING_WEEKS:
        return None

    # Zero-lag (contemporaneous) correlation
    pearson_0, n_0 = corr_with_lag(merged, "health_score", "weekly_return", 0)
    sent_pearson_0, _ = corr_with_lag(merged, "sentiment_balance", "weekly_return", 0)

    # Lead/lag scan
    best_lag = 0
    best_corr = pearson_0 if pearson_0 is not None else 0.0
    best_n = n_0
    for lag in LAG_RANGE:
        c, n = corr_with_lag(merged, "health_score", "weekly_return", lag)
        if c is None:
            continue
        if abs(c) > abs(best_corr):
            best_corr = c
            best_lag = lag
            best_n = n

    return {
        "app_id": app_id,
        "ticker": ticker,
        "n_weeks": n_0,
        "pearson_health_zero": pearson_0,
        "pearson_sentiment_zero": sent_pearson_0,
        "best_lag_weeks": best_lag,
        "best_lag_corr": best_corr,
        "best_lag_n": best_n,
    }


def save_results_to_db(results: list) -> None:
    """Persist correlation results to a new table for reuse."""
    if not results:
        return
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS health_stock_correlations (
                app_id                      TEXT,
                ticker                      TEXT,
                n_weeks                     INTEGER,
                pearson_health_zero         REAL,
                pearson_sentiment_zero      REAL,
                best_lag_weeks              INTEGER,
                best_lag_corr               REAL,
                best_lag_n                  INTEGER,
                PRIMARY KEY (app_id, ticker)
            )
        """)
        conn.executemany(
            """
            INSERT OR REPLACE INTO health_stock_correlations
                (app_id, ticker, n_weeks,
                 pearson_health_zero, pearson_sentiment_zero,
                 best_lag_weeks, best_lag_corr, best_lag_n)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r["app_id"], r["ticker"], r["n_weeks"],
                    r["pearson_health_zero"], r["pearson_sentiment_zero"],
                    r["best_lag_weeks"], r["best_lag_corr"], r["best_lag_n"],
                )
                for r in results
            ],
        )
        conn.commit()


def print_summary(results: list) -> None:
    print()
    print("=" * 100)
    print("Health Score vs weekly stock return correlations")
    print("=" * 100)

    with get_connection() as conn:
        names = pd.read_sql(
            "SELECT app_id, name, segment FROM apps", conn
        ).set_index("app_id").to_dict("index")

    # Sort by absolute zero-lag correlation
    sorted_results = sorted(
        results,
        key=lambda r: abs(r["pearson_health_zero"] or 0),
        reverse=True,
    )

    print(
        f"  {'App':<24} {'Ticker':<10} {'N':>5} "
        f"{'Health@0':>10} {'Sent@0':>9} {'BestLag':>8} {'BestCorr':>10}"
    )
    print("  " + "-" * 96)
    for r in sorted_results:
        name = names.get(r["app_id"], {}).get("name", r["app_id"])
        lag_str = f"{r['best_lag_weeks']:+d}w" if r['best_lag_weeks'] != 0 else "0"
        p_health = r["pearson_health_zero"]
        p_sent = r["pearson_sentiment_zero"]
        b_corr = r["best_lag_corr"]
        print(
            f"  {name:<24} {r['ticker']:<10} {r['n_weeks']:>5} "
            f"{p_health:>+10.3f} {p_sent:>+9.3f} {lag_str:>8} {b_corr:>+10.3f}"
        )

    print()
    print("Interpretation:")
    print("  Health@0       Pearson corr of Health Score vs same-week stock return.")
    print("  Sent@0         Same for sentiment balance.")
    print("  BestLag        Lag (in weeks) where |correlation| is strongest.")
    print("                 Positive lag means Health Score leads the stock.")
    print("                 Negative lag means stock moves leads Health Score.")
    print("  BestCorr       Correlation at the best lag.")


def main() -> None:
    print("Loading weekly Health Score...")
    health_df = load_weekly_health_score()
    print(f"  {len(health_df):,} app-week rows.")

    print("Loading weekly stock returns...")
    stock_df = load_weekly_stock_returns()
    print(f"  {len(stock_df):,} ticker-week rows.")

    print("\nComputing correlations per app...")
    results = []
    for app_id, ticker in APP_TICKER_MAP.items():
        r = analyze_app(app_id, ticker, health_df, stock_df)
        if r:
            results.append(r)

    if not results:
        print("No overlapping data found. Did Health Score and stock prices run?")
        return

    save_results_to_db(results)
    print(f"  Saved {len(results)} correlation rows to health_stock_correlations.")

    print_summary(results)
    print()


if __name__ == "__main__":
    main()
