"""
Main scraping pipeline.

Fetches metadata and reviews for all configured apps and stores them
in the SQLite database. Raw JSON backups are also written under data/raw/.

Usage:
    python scripts/run_scraper.py                    # scrape everything
    python scripts/run_scraper.py --verify-only      # check app IDs only
    python scripts/run_scraper.py --apps com.x,com.y # scrape specific apps
    python scripts/run_scraper.py --max 5000         # cap reviews per app
    python scripts/run_scraper.py --resume           # skip apps already in DB
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

# Make the project root importable when running the script directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import APPS, RAW_DATA_DIR, MAX_REVIEWS_PER_APP
from src.database.db import init_database, get_connection
from src.scrapers.google_play import (
    fetch_app_metadata,
    fetch_app_reviews,
    verify_all_apps,
)


def save_app_metadata(metadata: dict, app_info: dict) -> None:
    """Insert or update one app row."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO apps
                (app_id, name, name_he, segment, developer, category,
                 installs_range, current_version, last_updated, last_scraped)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                app_info["app_id"],
                app_info["name"],
                app_info["name_he"],
                app_info["segment"],
                metadata.get("developer"),
                metadata.get("genre"),
                metadata.get("installs"),
                metadata.get("version"),
                metadata.get("updated"),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()


def _iso(value) -> str:
    """Best-effort ISO datetime string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _sanitize_score(score):
    """
    Google Play occasionally returns scores outside the 1-5 range
    (e.g. 0 for reviews with no rating). The DB schema has
    CHECK (score BETWEEN 1 AND 5), so we coerce anything invalid
    to NULL instead of failing the entire batch insert.
    """
    if score is None:
        return None
    try:
        score_int = int(score)
    except (TypeError, ValueError):
        return None
    if 1 <= score_int <= 5:
        return score_int
    return None


def save_reviews(reviews_list: list, app_id: str) -> int:
    """Insert reviews, replacing duplicates by review_id."""
    if not reviews_list:
        return 0

    rows = []
    bad_score_count = 0
    for r in reviews_list:
        raw_score = r.get("score")
        clean_score = _sanitize_score(raw_score)
        if raw_score is not None and clean_score is None:
            bad_score_count += 1

        rows.append((
            r.get("reviewId"),
            app_id,
            r.get("userName"),
            r.get("content"),
            clean_score,
            r.get("thumbsUpCount", 0),
            r.get("reviewCreatedVersion"),
            _iso(r.get("at")),
            r.get("replyContent"),
            _iso(r.get("repliedAt")),
        ))

    if bad_score_count:
        print(f"  Note: {bad_score_count} reviews had invalid scores, saved with NULL")

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO reviews
                (review_id, app_id, user_name, content, score, thumbs_up_count,
                 review_created_version, review_date, developer_reply,
                 developer_reply_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    return len(rows)


def save_reviews_raw_json(reviews_list: list, app_id: str) -> None:
    """Write a raw JSON backup of the scraped reviews."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DATA_DIR / f"{app_id}_reviews.json"

    serializable = []
    for r in reviews_list:
        item = dict(r)
        for key in ("at", "repliedAt"):
            if item.get(key) is not None:
                item[key] = _iso(item[key])
        serializable.append(item)

    with open(out, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def get_apps_already_scraped(min_reviews: int = 100) -> set:
    """Return the set of app_ids that already have >= min_reviews in the DB."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT app_id, COUNT(*) AS n
            FROM reviews
            GROUP BY app_id
            HAVING COUNT(*) >= ?
            """,
            (min_reviews,),
        ).fetchall()
    return {r["app_id"] for r in rows}


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Google Play reviews")
    parser.add_argument("--apps", type=str,
                        help="Comma-separated list of app IDs to scrape")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only verify app IDs, do not scrape")
    parser.add_argument("--max", type=int, default=MAX_REVIEWS_PER_APP,
                        help="Max reviews per app")
    parser.add_argument("--resume", action="store_true",
                        help="Skip apps that already have >= 100 reviews in the DB")
    args = parser.parse_args()

    init_database()

    if args.verify_only:
        verify_all_apps()
        return

    if args.apps:
        targets = set(args.apps.split(","))
        apps_to_scrape = [a for a in APPS if a["app_id"] in targets]
    else:
        apps_to_scrape = list(APPS)

    if args.resume:
        already = get_apps_already_scraped(min_reviews=100)
        skipped = [a for a in apps_to_scrape if a["app_id"] in already]
        apps_to_scrape = [a for a in apps_to_scrape if a["app_id"] not in already]
        if skipped:
            print(f"--resume: skipping {len(skipped)} apps already in DB:")
            for a in skipped:
                print(f"  - {a['name']} ({a['app_id']})")
            print()

    print(f"Scraping {len(apps_to_scrape)} apps (max {args.max} reviews each)\n")

    for app_info in apps_to_scrape:
        app_id = app_info["app_id"]
        name = app_info["name"]

        print("=" * 60)
        print(f"  {name}  ({app_id})")
        print("=" * 60)

        metadata = fetch_app_metadata(app_id)
        if metadata is None:
            print(f"  [skip] Could not fetch metadata (network or 404). Will retry on next run.\n")
            continue

        save_app_metadata(metadata, app_info)
        print(f"  Metadata saved.")

        try:
            reviews_list = fetch_app_reviews(app_id, max_reviews=args.max)
        except Exception as e:
            print(f"  [error] Reviews fetch failed: {e}")
            print(f"  Continuing with next app. Re-run with --resume to retry.\n")
            continue

        if reviews_list:
            save_reviews_raw_json(reviews_list, app_id)
            try:
                count = save_reviews(reviews_list, app_id)
                print(f"  Saved {count} reviews to database.\n")
            except Exception as e:
                print(f"  [error] DB save failed: {e}")
                print(f"  Raw JSON backup is in data/raw/{app_id}_reviews.json")
                print(f"  Continuing with next app.\n")
                continue
        else:
            print(f"  No reviews retrieved.\n")

    print("Done.")


if __name__ == "__main__":
    main()