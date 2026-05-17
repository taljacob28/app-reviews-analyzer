"""
Database connection and initialization utilities.

Run this module directly to initialize the database from the schema:
    python -m src.database.db
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

from src.config import DB_PATH


SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_database(schema_path: Path = SCHEMA_PATH) -> None:
    """Create the database file and apply the schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(schema_sql)
        conn.commit()

    print(f"Database initialized at: {DB_PATH}")


@contextmanager
def get_connection():
    """Yield a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
    finally:
        conn.close()


def execute_query(sql: str, params: tuple = ()) -> list:
    """Run a SELECT and return all rows as dictionaries."""
    with get_connection() as conn:
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def table_counts() -> dict:
    """Return row counts for every table in the database."""
    counts = {}
    with get_connection() as conn:
        tables = [
            r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        for table in tables:
            cur = conn.execute(f"SELECT COUNT(*) AS n FROM {table}")
            counts[table] = cur.fetchone()["n"]
    return counts


if __name__ == "__main__":
    init_database()
    print("\nTable row counts:")
    for table, count in table_counts().items():
        print(f"  {table}: {count}")
