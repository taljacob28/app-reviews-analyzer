"""
Configuration for the Israeli Financial Apps Reviews Analyzer.

Contains the list of apps to scrape, their segments, and global settings.

App IDs verified against Google Play (May 2026). If an ID stops resolving in
the future, search the app on Google Play and check the URL:
    https://play.google.com/store/apps/details?id=<PACKAGE_ID>
Update the relevant entry below, then re-run:
    python scripts/run_scraper.py --verify-only
"""

from pathlib import Path
import os

# -------------------- Paths --------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXPORTS_DIR = PROJECT_ROOT / "data" / "exports"
DB_PATH = PROCESSED_DATA_DIR / "reviews.db"

# -------------------- Scraping settings --------------------

COUNTRY_CODE = "il"           # Israel
LANGUAGE_CODE = "iw"          # Hebrew (Google's legacy code; some tools use 'he')
MAX_REVIEWS_PER_APP = int(os.getenv("MAX_REVIEWS_PER_APP", 50000))
SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY_SECONDS", 0.5))
BATCH_SIZE = 200              # Reviews per pagination request

# -------------------- App registry --------------------
# segment values: "traditional_bank", "digital_bank", "credit_card"

APPS = [
    # ---- Traditional banks ----
    {
        "name": "Bank Hapoalim",
        "name_he": "בנק הפועלים",
        "app_id": "com.ideomobile.hapoalim",
        "segment": "traditional_bank",
    },
    {
        "name": "Bank Leumi",
        "name_he": "בנק לאומי",
        "app_id": "com.leumi.leumiwallet",
        "segment": "traditional_bank",
    },
    {
        "name": "Discount Bank",
        "name_he": "בנק דיסקונט",
        "app_id": "com.ideomobile.discount",
        "segment": "traditional_bank",
    },
    {
        "name": "Mizrahi-Tefahot",
        "name_he": "מזרחי טפחות",
        "app_id": "com.MizrahiTefahot.nh",
        "segment": "traditional_bank",
    },
    {
        "name": "First International Bank",
        "name_he": "הבינלאומי",
        "app_id": "com.fibi.nativeapp",
        "segment": "traditional_bank",
    },
    {
        "name": "Mercantile Discount",
        "name_he": "מרכנתיל דיסקונט",
        "app_id": "com.ideomobile.mercantile",
        "segment": "traditional_bank",
    },
    # ---- Digital banks ----
    {
        "name": "One Zero",
        "name_he": "ONE ZERO",
        "app_id": "il.co.firstdigitalbank",
        "segment": "digital_bank",
    },
    {
        "name": "Pepper",
        "name_he": "פפר",
        "app_id": "com.pepper.ldb",
        "segment": "digital_bank",
    },
    # ---- Credit cards ----
    {
        "name": "Isracard",
        "name_he": "ישראכרט",
        "app_id": "com.isracard.hatavot",
        "segment": "credit_card",
    },
    {
        "name": "Cal",
        "name_he": "כאל",
        "app_id": "com.onoapps.cal4u",
        "segment": "credit_card",
    },
    {
        "name": "Max",
        "name_he": "מקס",
        "app_id": "com.ideomobile.leumicard",
        "segment": "credit_card",
    },
]

SEGMENT_LABELS = {
    "traditional_bank": "Traditional Bank",
    "digital_bank": "Digital Bank",
    "credit_card": "Credit Card",
}

SEGMENT_LABELS_HE = {
    "traditional_bank": "בנק מסורתי",
    "digital_bank": "בנק דיגיטלי",
    "credit_card": "חברת אשראי",
}

# -------------------- Topic taxonomy --------------------
# Used for review classification in the ML phase.

TOPIC_CATEGORIES = [
    "performance",        # speed, load time, crashes
    "security",           # login, authentication, fraud
    "ui_ux",              # design, navigation, ease of use
    "customer_service",   # support, response time, agents
    "features",           # missing features, requests
    "fees",               # pricing, hidden charges
    "login_auth",         # password issues, biometrics
    "stability",          # bugs, errors, freezes
    "praise",             # positive feedback (no specific complaint)
    "other",
]

# -------------------- Health Score weights --------------------
# Used to compute the composite Health Score per app per time window.
# Adjust these during analysis based on what tells the best story.

HEALTH_SCORE_WEIGHTS = {
    "avg_rating": 0.40,
    "sentiment_balance": 0.25,
    "momentum": 0.20,
    "volume_normalized": 0.10,
    "developer_response_rate": 0.05,
}