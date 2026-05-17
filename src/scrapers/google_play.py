"""
Google Play Store reviews scraper.

Uses the google-play-scraper library to fetch reviews and app metadata
for the apps defined in src/config.py.

Functions:
    fetch_app_metadata(app_id)   -> dict or None
    fetch_app_reviews(app_id)    -> list of review dicts
    verify_app_id(app_id)        -> bool
    verify_all_apps()            -> dict of {app_id: bool}
"""

from typing import List, Dict, Optional
import time

from google_play_scraper import app, reviews, Sort
from tqdm import tqdm

from src.config import (
    APPS,
    COUNTRY_CODE,
    LANGUAGE_CODE,
    MAX_REVIEWS_PER_APP,
    SCRAPE_DELAY,
    BATCH_SIZE,
)


def fetch_app_metadata(app_id: str) -> Optional[Dict]:
    """Fetch metadata for a single app, or return None on failure."""
    try:
        return app(
            app_id,
            lang=LANGUAGE_CODE,
            country=COUNTRY_CODE,
        )
    except Exception as e:
        print(f"  [metadata error] {app_id}: {e}")
        return None


def fetch_app_reviews(
    app_id: str,
    max_reviews: int = MAX_REVIEWS_PER_APP,
) -> List[Dict]:
    """
    Fetch reviews for one app, up to max_reviews, sorted newest first.

    Returns a list of review dicts as produced by google-play-scraper.
    """
    all_reviews: List[Dict] = []
    continuation_token = None
    pbar = tqdm(total=max_reviews, desc=f"  {app_id}", unit="rev", leave=False)

    while len(all_reviews) < max_reviews:
        try:
            batch, continuation_token = reviews(
                app_id,
                lang=LANGUAGE_CODE,
                country=COUNTRY_CODE,
                sort=Sort.NEWEST,
                count=BATCH_SIZE,
                continuation_token=continuation_token,
            )
        except Exception as e:
            print(f"  [reviews error] {app_id}: {e}")
            break

        if not batch:
            break

        all_reviews.extend(batch)
        pbar.update(len(batch))

        if continuation_token is None:
            break

        time.sleep(SCRAPE_DELAY)

    pbar.close()
    return all_reviews[:max_reviews]


def verify_app_id(app_id: str) -> bool:
    """Check whether a package ID resolves on Google Play."""
    return fetch_app_metadata(app_id) is not None


def verify_all_apps() -> Dict[str, bool]:
    """Verify every configured app ID. Print and return results."""
    results: Dict[str, bool] = {}
    print(f"Verifying {len(APPS)} configured apps...\n")
    for app_info in APPS:
        app_id = app_info["app_id"]
        name = app_info["name"]
        is_valid = verify_app_id(app_id)
        results[app_id] = is_valid
        status = "OK  " if is_valid else "FAIL"
        print(f"  [{status}] {name:30s} ({app_id})")

    ok = sum(1 for v in results.values() if v)
    fail = len(results) - ok
    print(f"\nSummary: {ok} OK, {fail} failed.")
    if fail:
        print("\nFor failed apps, find the correct package ID by searching")
        print("Google Play and reading the URL after id=, then update src/config.py.")
    return results


if __name__ == "__main__":
    verify_all_apps()
