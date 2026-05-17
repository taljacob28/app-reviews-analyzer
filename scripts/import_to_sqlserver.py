"""
Migrate exported CSV data from SQLite to SQL Server.
Reads each CSV, loads into the corresponding SQL Server table.

Configuration is read from environment variables. Copy .env.example to .env
and set SQL_SERVER_HOST and SQL_SERVER_DATABASE before running.
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = PROJECT_ROOT / "data" / "exports"

# Load .env manually so the script works without python-dotenv installed
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

try:
    import pandas as pd
    from sqlalchemy import create_engine, text
except ImportError:
    print("Missing deps. Run: pip install pyodbc sqlalchemy pandas")
    sys.exit(1)

# Connection (configured via .env)
SERVER = os.getenv("SQL_SERVER_HOST", "")
DATABASE = os.getenv("SQL_SERVER_DATABASE", "AppReviewsAnalysis")
DRIVER = "ODBC Driver 17 for SQL Server"

if not SERVER:
    print(
        "SQL_SERVER_HOST is not set.\n"
        "Copy .env.example to .env and set SQL_SERVER_HOST to your server name.\n"
        "Example: SQL_SERVER_HOST=LAPTOP-ABC\\SQLEXPRESS"
    )
    sys.exit(1)

CONN_STR = (
    f"mssql+pyodbc://@{SERVER}/{DATABASE}"
    f"?driver={DRIVER.replace(' ', '+')}"
    f"&trusted_connection=yes"
)

# Parent tables first
IMPORT_ORDER = [
    "apps",
    "stock_tickers",
    "reviews",
    "review_features",
    "review_topics",
    "stock_prices",
]

# Datetime columns per table (will be parsed in pandas before insert)
DATE_COLS = {
    "apps":          ["first_scraped", "last_scraped"],
    "reviews":       ["review_date", "developer_reply_date", "scraped_at"],
    "review_topics": ["labeled_at"],
    "stock_prices":  ["date"],
}


def main():
    print(f"Connecting to {SERVER}/{DATABASE}...")
    try:
        engine = create_engine(CONN_STR, fast_executemany=True)
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT @@VERSION")).scalar()
            print(f"  Connected. Server version: {str(ver)[:60]}...")
    except Exception as e:
        print(f"  Connection failed: {e}")
        print("\nVerify:")
        print(f"  1. ODBC Driver 17 for SQL Server is installed")
        print(f"  2. SQL Server is running at {SERVER}")
        print(f"  3. Database {DATABASE} exists")
        sys.exit(1)

    for table in IMPORT_ORDER:
        csv_path = EXPORTS_DIR / f"{table}.csv"
        if not csv_path.exists():
            print(f"\n  WARNING: {csv_path.name} not found, skipping.")
            continue

        print(f"\nLoading {table}...")
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        print(f"  Read {len(df):,} rows from CSV.")

        # Parse datetime columns to proper types
        if table in DATE_COLS:
            for col in DATE_COLS[table]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")

        try:
            df.to_sql(
                table, engine,
                if_exists="append",
                index=False,
                chunksize=500,
            )
            print(f"  Inserted {len(df):,} rows into {table}.")
        except Exception as e:
            print(f"  ERROR loading {table}: {e}")
            sys.exit(1)

    # Verify
    print("\n" + "=" * 60)
    print("Verification: row counts in SQL Server")
    print("=" * 60)
    with engine.connect() as conn:
        for table in IMPORT_ORDER:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table:<22s}  {count:>10,} rows")

    print("\nMigration complete.")


if __name__ == "__main__":
    main()