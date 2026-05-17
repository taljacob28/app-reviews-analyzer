-- ============================================================
-- File:    01_schema.sql
-- Purpose: Create AppReviewsAnalysis database and schema
-- Author:  Tal Jacob
-- ============================================================

-- Create the database (skip if already exists)
IF DB_ID('AppReviewsAnalysis') IS NULL
    CREATE DATABASE AppReviewsAnalysis;
GO

USE AppReviewsAnalysis;
GO

-- Drop existing tables in reverse dependency order (safe re-run)
IF OBJECT_ID('health_stock_correlations', 'U') IS NOT NULL DROP TABLE health_stock_correlations;
IF OBJECT_ID('stock_prices', 'U')    IS NOT NULL DROP TABLE stock_prices;
IF OBJECT_ID('stock_tickers', 'U')   IS NOT NULL DROP TABLE stock_tickers;
IF OBJECT_ID('user_features', 'U')   IS NOT NULL DROP TABLE user_features;
IF OBJECT_ID('app_weekly_metrics', 'U') IS NOT NULL DROP TABLE app_weekly_metrics;
IF OBJECT_ID('review_topics', 'U')   IS NOT NULL DROP TABLE review_topics;
IF OBJECT_ID('review_features', 'U') IS NOT NULL DROP TABLE review_features;
IF OBJECT_ID('reviews', 'U')         IS NOT NULL DROP TABLE reviews;
IF OBJECT_ID('apps', 'U')            IS NOT NULL DROP TABLE apps;
GO

-- App metadata (11 Israeli financial apps)
CREATE TABLE apps (
    app_id           NVARCHAR(100) NOT NULL,
    [name]           NVARCHAR(100) NOT NULL,
    name_he          NVARCHAR(100),
    segment          NVARCHAR(50),
    developer        NVARCHAR(200),
    category         NVARCHAR(50),
    installs_range   NVARCHAR(50),
    current_version  NVARCHAR(50),
    last_updated     BIGINT,
    first_scraped    DATETIME2,
    last_scraped     DATETIME2,
    CONSTRAINT PK_apps PRIMARY KEY (app_id)
);
GO

-- Raw user reviews scraped from Google Play (47K rows)
CREATE TABLE reviews (
    review_id                NVARCHAR(100) NOT NULL,
    app_id                   NVARCHAR(100) NOT NULL,
    user_name                NVARCHAR(255),
    content                  NVARCHAR(MAX),
    score                    INT,
    thumbs_up_count          INT,
    review_created_version   NVARCHAR(100),
    review_date              DATETIME2,
    developer_reply          NVARCHAR(MAX),
    developer_reply_date     DATETIME2,
    scraped_at               DATETIME2,
    CONSTRAINT PK_reviews PRIMARY KEY (review_id),
    CONSTRAINT FK_reviews_apps FOREIGN KEY (app_id) REFERENCES apps(app_id)
);
GO

CREATE INDEX idx_reviews_app_id    ON reviews(app_id);
CREATE INDEX idx_reviews_date      ON reviews(review_date);
CREATE INDEX idx_reviews_user_name ON reviews(user_name);
CREATE INDEX idx_reviews_score     ON reviews(score);
GO

-- Per-review derived features + DictaBERT sentiment classification
CREATE TABLE review_features (
    review_id            NVARCHAR(100) NOT NULL,
    text_length          INT,
    word_count           INT,
    [language]           NVARCHAR(10),
    emoji_count          INT,
    has_emoji            BIT,
    exclamation_count    INT,
    question_count       INT,
    all_caps_ratio       FLOAT,
    day_of_week          INT,
    hour_of_day          INT,
    has_developer_reply  BIT,
    time_to_reply_hours  FLOAT,
    sentiment_score      FLOAT,
    sentiment_label      NVARCHAR(20),
    CONSTRAINT PK_review_features PRIMARY KEY (review_id),
    CONSTRAINT FK_review_features_reviews FOREIGN KEY (review_id) REFERENCES reviews(review_id)
);
GO

CREATE INDEX idx_features_sentiment ON review_features(sentiment_label);
GO

-- Topic classification labels from Claude API (31K rows, 10 topics)
CREATE TABLE review_topics (
    review_id    NVARCHAR(100) NOT NULL,
    topic        NVARCHAR(50),
    method       NVARCHAR(20),
    labeled_at   DATETIME2,
    CONSTRAINT PK_review_topics PRIMARY KEY (review_id),
    CONSTRAINT FK_review_topics_reviews FOREIGN KEY (review_id) REFERENCES reviews(review_id)
);
GO

CREATE INDEX idx_topics_topic ON review_topics(topic);
GO

-- TASE stock tickers for parent banking companies (6 listed)
CREATE TABLE stock_tickers (
    ticker            NVARCHAR(20) NOT NULL,
    company_name      NVARCHAR(100),
    related_app_ids   NVARCHAR(500),
    CONSTRAINT PK_stock_tickers PRIMARY KEY (ticker)
);
GO

-- Daily TASE stock prices since 2010 (17.8K rows)
CREATE TABLE stock_prices (
    ticker          NVARCHAR(20) NOT NULL,
    [date]          DATE NOT NULL,
    [open]          FLOAT,
    high            FLOAT,
    low             FLOAT,
    [close]         FLOAT,
    volume          BIGINT,
    daily_return    FLOAT,
    CONSTRAINT PK_stock_prices PRIMARY KEY (ticker, [date]),
    CONSTRAINT FK_stock_prices_tickers FOREIGN KEY (ticker) REFERENCES stock_tickers(ticker)
);
GO

CREATE INDEX idx_prices_date ON stock_prices([date]);
GO

-- Weekly per-app composite metrics including the Health Score
-- (~6K rows, one row per app per ISO week)
CREATE TABLE app_weekly_metrics (
    app_id                    NVARCHAR(100) NOT NULL,
    week_start                DATE          NOT NULL,
    n_reviews                 INT,
    avg_score                 FLOAT,
    positive_share            FLOAT,
    negative_share            FLOAT,
    neutral_share             FLOAT,
    avg_review_length         FLOAT,
    momentum                  FLOAT,
    developer_response_rate   FLOAT,
    health_score              FLOAT,
    CONSTRAINT PK_weekly_metrics PRIMARY KEY (app_id, week_start),
    CONSTRAINT FK_weekly_metrics_apps FOREIGN KEY (app_id) REFERENCES apps(app_id)
);
GO

CREATE INDEX idx_weekly_week ON app_weekly_metrics(week_start);
GO

-- Per-user behavioral features for clustering and prediction
-- (~2K rows, after shared-name filtering)
CREATE TABLE user_features (
    user_key                  NVARCHAR(200) NOT NULL,
    user_name                 NVARCHAR(100),
    total_reviews             INT,
    apps_reviewed             INT,
    avg_score                 FLOAT,
    std_score                 FLOAT,
    avg_review_length         FLOAT,
    dominant_sentiment        NVARCHAR(20),
    first_review_date         DATE,
    last_review_date          DATE,
    lifespan_days             INT,
    reviews_per_month         FLOAT,
    positive_ratio            FLOAT,
    negative_ratio            FLOAT,
    dominant_topic            NVARCHAR(50),
    developer_response_rate   FLOAT,
    cluster_id                INT,
    CONSTRAINT PK_user_features PRIMARY KEY (user_key)
);
GO

-- Cross-source analysis output: weekly Health Score vs weekly stock returns,
-- with lead/lag correlation sweep (9 app-ticker pairs)
CREATE TABLE health_stock_correlations (
    app_id                      NVARCHAR(100) NOT NULL,
    ticker                      NVARCHAR(20)  NOT NULL,
    n_weeks                     INT,
    pearson_health_zero         FLOAT,
    pearson_sentiment_zero      FLOAT,
    best_lag_weeks              INT,
    best_lag_corr               FLOAT,
    best_lag_n                  INT,
    CONSTRAINT PK_corr PRIMARY KEY (app_id, ticker),
    CONSTRAINT FK_corr_apps    FOREIGN KEY (app_id) REFERENCES apps(app_id),
    CONSTRAINT FK_corr_tickers FOREIGN KEY (ticker) REFERENCES stock_tickers(ticker)
);
GO

PRINT 'Schema created successfully.';
PRINT 'Next step: Run scripts/import_to_sqlserver.py to populate the tables from exports/*.csv';
GO