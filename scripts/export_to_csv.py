"""
Export all relevant tables from SQLite to CSV files.
The CSVs will be imported to SQL Server in the next step.
"""

import sqlite3
import pandas as pd
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQLITE_PATH = PROJECT_ROOT / "data" / "processed" / "reviews.db"
OUTPUT_DIR = PROJECT_ROOT / "data" / "exports"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Tables to export
TABLES = [
    "apps",
    "stock_tickers",
    "reviews",
    "review_features",
    "review_topics",
    "stock_prices",
]

print(f"Connecting to {SQLITE_PATH}")
conn = sqlite3.connect(SQLITE_PATH)

for table in TABLES:
    print(f"Exporting {table}...")
    df = pd.read_sql(f"SELECT * FROM {table}", conn)
    out_path = OUTPUT_DIR / f"{table}.csv"
    # utf-8-sig adds BOM, helps SSMS recognize Unicode (essential for Hebrew)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  Saved {len(df):,} rows to {out_path.name}")

conn.close()
print("\nDone. CSVs are in data/exports/.")