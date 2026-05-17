-- ============================================================
-- 03_views.sql
-- Power BI-facing views for the Israeli Banking Apps project.
-- Run after 01_schema.sql + data loading is complete.
-- ============================================================

-- ------------------------------------------------------------
-- vw_reviews_enriched
-- One row per review. Joins reviews + apps + review_features + review_topics.
-- Used as the primary fact source for the Power BI semantic model.
-- ------------------------------------------------------------
IF OBJECT_ID('dbo.vw_reviews_enriched', 'V') IS NOT NULL
    DROP VIEW dbo.vw_reviews_enriched;
GO

CREATE VIEW dbo.vw_reviews_enriched AS
SELECT
    r.review_id,
    r.app_id,
    a.[name]                          AS app_name,
    a.name_he                         AS app_name_he,
    a.segment                         AS app_segment,
    r.user_name,
    r.content,
    r.score,
    r.review_date,
    CAST(r.review_date AS date)       AS review_date_d,
    YEAR(r.review_date)               AS review_year,
    DATEPART(quarter, r.review_date)  AS review_quarter,
    MONTH(r.review_date)              AS review_month,
    DATEFROMPARTS(YEAR(r.review_date), MONTH(r.review_date), 1) AS review_month_start,
    r.thumbs_up_count,
    r.developer_reply,
    r.developer_reply_date,
    f.text_length,
    f.word_count,
    f.[language],
    f.has_emoji,
    f.has_developer_reply,
    f.sentiment_score,
    f.sentiment_label,
    t.topic,
    t.method                          AS topic_method
FROM reviews r
INNER JOIN apps a            ON r.app_id     = a.app_id
LEFT JOIN review_features f  ON r.review_id  = f.review_id
LEFT JOIN review_topics t    ON r.review_id  = t.review_id;
GO

-- ------------------------------------------------------------
-- Quick verification
-- Expected: row count equals 47,188 (matches reviews table).
-- ------------------------------------------------------------
SELECT
    COUNT(*)                              AS total_rows,
    COUNT(DISTINCT review_id)             AS distinct_reviews,
    COUNT(DISTINCT app_id)                AS distinct_apps,
    COUNT(topic)                          AS rows_with_topic,
    SUM(CASE WHEN sentiment_label IS NOT NULL THEN 1 ELSE 0 END) AS rows_with_sentiment,
    MIN(review_date)                      AS earliest,
    MAX(review_date)                      AS latest
FROM dbo.vw_reviews_enriched;
GO
