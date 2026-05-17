"""
Fetch daily stock prices from TASE via yfinance and store them in the DB.

Tickers correspond to companies behind apps in our analysis:
    POLI.TA   Bank Hapoalim
    LUMI.TA   Bank Leumi le-Israel (parent of Pepper)
    DSCT.TA   Israel Discount Bank (parent of Mercantile, Cal)
    MZTF.TA   Mizrahi-Tefahot Bank
    FIBIH.TA  F.I.B.I. Holdings (parent of First International Bank)
    ISCD.TA   Isracard

Usage:
    python scripts/fetch_stock_prices.py                # full fetch
    python scripts/fetch_stock_prices.py --verify-only  # check tickers only
    python scripts/fetch_stock_prices.py --start 2015-01-01  # custom start date

Prerequisites:
    pip install yfinance
"""

import argparse
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("yfinance is not installed. Run: pip install yfinance")
    sys.exit(1)

from src.config import DB_PATH


# (ticker, company_name, [related_app_ids])
TICKERS = [
    ("POLI.TA",  "Bank Hapoalim",
        ["com.ideomobile.hapoalim"]),
    ("LUMI.TA",  "Bank Leumi le-Israel",
        ["com.leumi.leumiwallet", "com.pepper.ldb"]),
    ("DSCT.TA",  "Israel Discount Bank",
        ["com.ideomobile.discount", "com.ideomobile.mercantile", "com.onoapps.cal4u"]),
    ("MZTF.TA",  "Mizrahi-Tefahot Bank",
        ["com.MizrahiTefahot.nh"]),
    ("FIBIH.TA", "F.I.B.I. Holdings",
        ["com.fibi.nativeapp"]),
    ("ISCD.TA",  "Isracard",
        ["com.isracard.hatavot"]),
]

DEFAULT_START_DATE = "2010-01-01"


def create_tables() -> None:
    """Create stock tables if they don't exist."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS stock_tickers (
                ticker             TEXT PRIMARY KEY,
                company_name       TEXT,
                related_app_ids    TEXT
            );

            CREATE TABLE IF NOT EXISTS stock_prices (
                ticker         TEXT,
                date           TEXT,
                open           REAL,
                high           REAL,
                low            REAL,
                close          REAL,
                volume         INTEGER,
                daily_return   REAL,
                PRIMARY KEY (ticker, date),
                FOREIGN KEY (ticker) REFERENCES stock_tickers(ticker)
            );

            CREATE INDEX IF NOT EXISTS idx_stock_prices_ticker ON stock_prices(ticker);
            CREATE INDEX IF NOT EXISTS idx_stock_prices_date   ON stock_prices(date);
        """)
        conn.commit()


def save_ticker_metadata() -> None:
    """Insert ticker metadata into stock_tickers."""
    with sqlite3.connect(DB_PATH) as conn:
        for ticker, name, apps in TICKERS:
            conn.execute(
                "INSERT OR REPLACE INTO stock_tickers "
                "(ticker, company_name, related_app_ids) VALUES (?, ?, ?)",
                (ticker, name, ",".join(apps)),
            )
        conn.commit()


def verify_tickers() -> list:
    """Verify each ticker returns data on yfinance."""
    print(f"Verifying {len(TICKERS)} tickers...\n")
    results = []
    for ticker, name, _ in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d")
            if len(hist) > 0:
                latest = hist.iloc[-1]
                print(f"  [OK  ] {ticker:10s}  {name:30s}  latest: {latest['Close']:>10.2f}")
                results.append((ticker, True))
            else:
                print(f"  [FAIL] {ticker:10s}  {name:30s}  no data")
                results.append((ticker, False))
        except Exception as e:
            print(f"  [FAIL] {ticker:10s}  {name:30s}  error: {e}")
            results.append((ticker, False))

    ok = sum(1 for _, v in results if v)
    fail = len(results) - ok
    print(f"\nSummary: {ok} OK, {fail} failed.")
    return results


def fetch_and_save(ticker: str, name: str, start_date: str) -> int:
    """Download history for one ticker and save to stock_prices."""
    print(f"Fetching {ticker} ({name})...")
    stock = yf.Ticker(ticker)
    hist = stock.history(start=start_date)

    if len(hist) == 0:
        print(f"  No data returned.")
        return 0

    hist = hist.reset_index()
    hist["daily_return"] = hist["Close"].pct_change()

    rows = []
    for _, r in hist.iterrows():
        rows.append((
            ticker,
            r["Date"].strftime("%Y-%m-%d"),
            float(r["Open"])  if pd.notna(r["Open"])  else None,
            float(r["High"])  if pd.notna(r["High"])  else None,
            float(r["Low"])   if pd.notna(r["Low"])   else None,
            float(r["Close"]) if pd.notna(r["Close"]) else None,
            int(r["Volume"]) if pd.notna(r["Volume"]) else 0,
            float(r["daily_return"]) if pd.notna(r["daily_return"]) else None,
        ))

    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO stock_prices
                (ticker, date, open, high, low, close, volume, daily_return)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    earliest = hist["Date"].min().strftime("%Y-%m-%d")
    latest = hist["Date"].max().strftime("%Y-%m-%d")
    print(f"  Saved {len(rows):,} trading days ({earliest} to {latest}).")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch TASE stock prices")
    parser.add_argument("--verify-only", action="store_true",
                        help="Verify tickers without saving")
    parser.add_argument("--start", type=str, default=DEFAULT_START_DATE,
                        help=f"Start date YYYY-MM-DD (default {DEFAULT_START_DATE})")
    args = parser.parse_args()

    if args.verify_only:
        verify_tickers()
        return

    print("Creating tables...")
    create_tables()
    save_ticker_metadata()

    print(f"Fetching prices for {len(TICKERS)} tickers from {args.start}...\n")
    total = 0
    for ticker, name, _ in TICKERS:
        try:
            n = fetch_and_save(ticker, name, args.start)
            total += n
        except Exception as e:
            print(f"  [error] {ticker}: {e}")

    print(f"\nDone. Saved {total:,} total price rows.")


if __name__ == "__main__":
    main()
