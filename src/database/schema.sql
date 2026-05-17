-- ============================================================
-- App Reviews Database Schema
-- Israeli Financial Apps Reviews Analyzer
-- ============================================================

-- ----------- apps ---------------------------------------------
-- Master list of applications being analyzed.
CREATE TABLE IF NOT EXISTS apps (
    app_id              TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    name_he             TEXT,
    segment             TEXT NOT NULL,
    developer           TEXT,
    category            TEXT,
    installs_range      TEXT,
    current_version     TEXT,
    last_updated        TEXT,
    first_scraped       TEXT DEFAULT CURRENT_TIMESTAMP,
    last_scraped        TEXT
);

CREATE INDEX IF NOT EXISTS idx_apps_segment ON apps(segment);


-- ----------- reviews -------------------------------------------
-- Individual user reviews.
CREATE TABLE IF NOT EXISTS reviews (
    review_id                  TEXT PRIMARY KEY,
    app_id                     TEXT NOT NULL,
    user_name                  TEXT,
    content                    TEXT,
    score                      INTEGER CHECK (score BETWEEN 1 AND 5),
    thumbs_up_count            INTEGER DEFAULT 0,
    review_created_version     TEXT,
    review_date                TEXT,
    developer_reply            TEXT,
    developer_reply_date       TEXT,
    scraped_at                 TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (app_id) REFERENCES apps(app_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_app      ON reviews(app_id);
CREATE INDEX IF NOT EXISTS idx_reviews_date     ON reviews(review_date);
CREATE INDEX IF NOT EXISTS idx_reviews_score    ON reviews(score);
CREATE INDEX IF NOT EXISTS idx_reviews_version  ON reviews(review_created_version);


-- ----------- review_features -----------------------------------
-- Derived features per review (computed during the cleaning phase).
CREATE TABLE IF NOT EXISTS review_features (
    review_id                  TEXT PRIMARY KEY,
    text_length                INTEGER,
    word_count                 INTEGER,
    language                   TEXT,
    has_emoji                  INTEGER DEFAULT 0,
    emoji_count                INTEGER DEFAULT 0,
    exclamation_count          INTEGER DEFAULT 0,
    question_count             INTEGER DEFAULT 0,
    all_caps_ratio             REAL,
    sentiment_score            REAL,
    sentiment_label            TEXT,
    day_of_week                INTEGER,
    hour_of_day                INTEGER,
    days_since_last_update     INTEGER,
    is_near_update             INTEGER DEFAULT 0,
    has_developer_reply        INTEGER DEFAULT 0,
    time_to_reply_hours        REAL,
    FOREIGN KEY (review_id) REFERENCES reviews(review_id)
);


-- ----------- review_topics -------------------------------------
-- Multi-label topic classification results.
CREATE TABLE IF NOT EXISTS review_topics (
    review_id    TEXT,
    topic        TEXT,
    confidence   REAL,
    PRIMARY KEY (review_id, topic),
    FOREIGN KEY (review_id) REFERENCES reviews(review_id)
);

CREATE INDEX IF NOT EXISTS idx_topics_topic ON review_topics(topic);


-- ----------- app_weekly_metrics --------------------------------
-- Weekly aggregations per app for time-series analysis.
CREATE TABLE IF NOT EXISTS app_weekly_metrics (
    app_id                       TEXT,
    year_week                    TEXT,
    review_count                 INTEGER,
    avg_score                    REAL,
    sentiment_positive_ratio     REAL,
    sentiment_negative_ratio     REAL,
    has_release                  INTEGER DEFAULT 0,
    days_since_last_release      INTEGER,
    PRIMARY KEY (app_id, year_week),
    FOREIGN KEY (app_id) REFERENCES apps(app_id)
);


-- ----------- user_features -------------------------------------
-- Per-user behavioral aggregations for K-Means clustering and the
-- score-change predictor.
-- user_key = composite of (user_name, first_review_date) to handle name reuse.
CREATE TABLE IF NOT EXISTS user_features (
    user_key                  TEXT PRIMARY KEY,
    user_name                 TEXT,
    total_reviews             INTEGER,
    apps_reviewed             INTEGER,
    avg_score                 REAL,
    std_score                 REAL,
    avg_review_length         REAL,
    dominant_sentiment        TEXT,
    first_review_date         TEXT,
    last_review_date          TEXT,
    lifespan_days             INTEGER,
    reviews_per_month         REAL,
    positive_ratio            REAL,
    negative_ratio            REAL,
    dominant_topic            TEXT,
    developer_response_rate   REAL
);


-- ----------- stock_tickers -------------------------------------
-- TASE tickers for parent companies of the apps under analysis.
-- Populated by scripts/fetch_stock_prices.py.
CREATE TABLE IF NOT EXISTS stock_tickers (
    ticker             TEXT PRIMARY KEY,
    company_name       TEXT,
    related_app_ids    TEXT
);


-- ----------- stock_prices --------------------------------------
-- Daily TASE price data fetched via yfinance.
-- Populated by scripts/fetch_stock_prices.py.
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


-- ----------- health_stock_correlations -------------------------
-- Cross-source analysis results: weekly Health Score vs weekly
-- stock returns, with lead/lag correlation sweep.
-- Populated by scripts/analyze_stocks_vs_reviews.py.
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
);
