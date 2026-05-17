-- ============================================================
-- File:    02_analysis.sql
-- Purpose: Analysis of Israeli financial app reviews
-- Author:  Tal Jacob
--
-- Data sources: 47K Google Play reviews + DictaBERT sentiment 
--               labels + Claude API topic labels + TASE stock prices
--
-- Story arc:
--   1-3:   Industry overview and decline
--   4-5:   Segment-level patterns
--   6-7:   Isracard April 2023 incident case study
--   8-9:   Topic-level analysis
--   10-11: FIBI recovery and Pepper decline case studies
-- ============================================================

USE AppReviewsAnalysis;
GO

-- ============================================================
-- 1. App overview: absolute performance per app
-- ============================================================
-- Avg score, 5-star %, 1-star %, dev reply rate per app.
-- Establishes a baseline of who is loved, hated, polarizing.

SELECT 
    a.name,
    a.segment,
    COUNT(r.review_id) AS total_reviews,
    CAST(AVG(CAST(r.score AS FLOAT)) AS DECIMAL(3,2)) AS avg_score,
    CAST(SUM(CASE WHEN r.score = 5 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) 
         AS DECIMAL(4,1)) AS pct_5_star,
    CAST(SUM(CASE WHEN r.score = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) 
         AS DECIMAL(4,1)) AS pct_1_star,
    CAST(SUM(CASE WHEN r.developer_reply IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*) 
         AS DECIMAL(4,1)) AS reply_rate_pct
FROM apps a
LEFT JOIN reviews r ON a.app_id = r.app_id
GROUP BY a.name, a.segment
ORDER BY avg_score DESC;


-- ============================================================
-- 2. Annual trajectory per app
-- ============================================================
-- Score per year per app. Reveals decline or recovery paths 
-- that lifetime averages hide.

SELECT 
    a.name,
    YEAR(r.review_date) AS yr,
    COUNT(*) AS n_reviews,
    CAST(AVG(CAST(r.score AS FLOAT)) AS DECIMAL(3,2)) AS avg_score
FROM apps a
INNER JOIN reviews r ON a.app_id = r.app_id
WHERE r.review_date IS NOT NULL
GROUP BY a.name, YEAR(r.review_date)
ORDER BY a.name, yr;


-- ============================================================
-- 3. Decline magnitude: peak score vs recent score
-- ============================================================
-- How far each app fell from its best year. Filter to years 
-- with at least 30 reviews to reduce small-sample noise.

WITH yearly AS (
    SELECT 
        a.name,
        a.segment,
        YEAR(r.review_date) AS yr,
        AVG(CAST(r.score AS FLOAT)) AS yr_score,
        COUNT(*) AS n_reviews
    FROM apps a
    INNER JOIN reviews r ON a.app_id = r.app_id
    WHERE r.review_date IS NOT NULL
    GROUP BY a.name, a.segment, YEAR(r.review_date)
    HAVING COUNT(*) >= 30
)
SELECT 
    name,
    segment,
    CAST(MAX(yr_score) AS DECIMAL(3,2)) AS peak_score,
    CAST(AVG(CASE WHEN yr >= 2025 THEN yr_score END) AS DECIMAL(3,2)) AS recent_avg,
    CAST(AVG(CASE WHEN yr >= 2025 THEN yr_score END) - MAX(yr_score) AS DECIMAL(4,2)) AS change_from_peak
FROM yearly
GROUP BY name, segment
HAVING AVG(CASE WHEN yr >= 2025 THEN yr_score END) IS NOT NULL
ORDER BY change_from_peak;


-- ============================================================
-- 4. Segment trends with YoY change (LAG window function)
-- ============================================================
-- Are credit cards, digital banks, and traditional banks moving 
-- together or on separate paths? LAG reveals turning points.

WITH segment_yearly AS (
    SELECT 
        a.segment,
        YEAR(r.review_date) AS yr,
        COUNT(*) AS n_reviews,
        AVG(CAST(r.score AS FLOAT)) AS avg_score_raw
    FROM apps a
    INNER JOIN reviews r ON a.app_id = r.app_id
    WHERE r.review_date IS NOT NULL
      AND YEAR(r.review_date) >= 2018
    GROUP BY a.segment, YEAR(r.review_date)
)
SELECT 
    segment,
    yr,
    n_reviews,
    CAST(avg_score_raw AS DECIMAL(3,2)) AS avg_score,
    CAST(LAG(avg_score_raw) OVER (PARTITION BY segment ORDER BY yr) 
         AS DECIMAL(3,2)) AS prev_yr_score,
    CAST(avg_score_raw - LAG(avg_score_raw) OVER (PARTITION BY segment ORDER BY yr) 
         AS DECIMAL(4,2)) AS yoy_change
FROM segment_yearly
ORDER BY segment, yr;


-- ============================================================
-- 5. Monthly drill-down: identify exact event timing in 2023
-- ============================================================
-- Where in the year did each segment hit trouble? 
-- Tests the hypothesis that the Oct 2023 war was the trigger.

SELECT 
    a.segment,
    YEAR(r.review_date) AS yr,
    MONTH(r.review_date) AS mo,
    COUNT(*) AS n_reviews,
    CAST(AVG(CAST(r.score AS FLOAT)) AS DECIMAL(3,2)) AS avg_score
FROM apps a
INNER JOIN reviews r ON a.app_id = r.app_id
WHERE r.review_date >= '2023-01-01'
  AND r.review_date <  '2024-01-01'
GROUP BY a.segment, YEAR(r.review_date), MONTH(r.review_date)
ORDER BY a.segment, yr, mo;


-- ============================================================
-- 6. Isracard incident: monthly per credit-card app in 2023
-- ============================================================
-- Disaggregates the segment-level dip. Did the credit card 2023 
-- decline come from all three apps or one?

SELECT 
    a.name,
    YEAR(r.review_date) AS yr,
    MONTH(r.review_date) AS mo,
    COUNT(*) AS n_reviews,
    CAST(AVG(CAST(r.score AS FLOAT)) AS DECIMAL(3,2)) AS avg_score
FROM apps a
INNER JOIN reviews r ON a.app_id = r.app_id
WHERE a.segment = 'credit_card'
  AND r.review_date >= '2023-01-01'
  AND r.review_date <  '2024-01-01'
GROUP BY a.name, YEAR(r.review_date), MONTH(r.review_date)
ORDER BY a.name, yr, mo;


-- ============================================================
-- 7. Qualitative validation: read 30 negative April 2023 reviews
-- ============================================================
-- Random sample of negative credit_card reviews from April 2023. 
-- Numbers tell where, text tells why.

SELECT TOP 30
    a.name AS app,
    r.review_date,
    r.score,
    r.content
FROM apps a
INNER JOIN reviews r ON a.app_id = r.app_id
WHERE a.segment = 'credit_card'
  AND r.review_date >= '2023-04-01'
  AND r.review_date <  '2023-05-01'
  AND r.score <= 2
ORDER BY NEWID();


-- ============================================================
-- 8. Topic-level: which topics drive low and high scores
-- ============================================================
-- For each LLM-classified topic, compute avg score plus share 
-- of negative (1-2) and positive (4-5) reviews.
--  Identifies foundational vs polarized topics.

SELECT 
    rt.topic,
    COUNT(*) AS n,
    CAST(AVG(CAST(r.score AS FLOAT)) AS DECIMAL(3,2)) AS avg_score,
    SUM(CASE WHEN r.score <= 2 THEN 1 ELSE 0 END) * 100 / COUNT(*) AS pct_negative,
    SUM(CASE WHEN r.score >= 4 THEN 1 ELSE 0 END) * 100 / COUNT(*) AS pct_positive
FROM review_topics rt
INNER JOIN reviews r ON rt.review_id = r.review_id
GROUP BY rt.topic
ORDER BY avg_score;


-- ============================================================
-- 9. Topic share per app: each bank's complaint personality
-- ============================================================
-- Which topic dominates each app's reviews? Reveals the unique 
-- weakness profile of each company.

SELECT 
    a.name,
    rt.topic,
    COUNT(*) AS n,
    CAST(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY a.name) 
         AS DECIMAL(4,1)) AS pct_of_app
FROM review_topics rt
INNER JOIN reviews r ON rt.review_id = r.review_id
INNER JOIN apps a    ON r.app_id = a.app_id
GROUP BY a.name, rt.topic
ORDER BY a.name, n DESC;


-- ============================================================
-- 10. FIBI recovery case: topic mix shift over time
-- ============================================================
-- Compares FIBI's topic distribution between trouble (2022-2023) 
-- and recovery (2025-2026). What did they fix to climb back?
-- pp_change = shift in percentage points of share.

WITH counts AS (
    SELECT 
        rt.topic,
        SUM(CASE WHEN YEAR(r.review_date) IN (2022, 2023) THEN 1 ELSE 0 END) AS n_old,
        SUM(CASE WHEN YEAR(r.review_date) IN (2025, 2026) THEN 1 ELSE 0 END) AS n_new
    FROM review_topics rt
    INNER JOIN reviews r ON rt.review_id = r.review_id
    INNER JOIN apps a    ON r.app_id = a.app_id
    WHERE a.name = 'First International Bank'
      AND YEAR(r.review_date) IN (2022, 2023, 2025, 2026)
    GROUP BY rt.topic
)
SELECT 
    topic,
    n_old,
    n_new,
    CAST(n_old * 100.0 / SUM(n_old) OVER () AS DECIMAL(4,1)) AS pct_old,
    CAST(n_new * 100.0 / SUM(n_new) OVER () AS DECIMAL(4,1)) AS pct_new,
    CAST(n_new * 100.0 / SUM(n_new) OVER () 
       - n_old * 100.0 / SUM(n_old) OVER () AS DECIMAL(5,1)) AS pp_change
FROM counts
ORDER BY pp_change DESC;


-- ============================================================
-- 11. Pepper decline case: topic mix shift over time
-- ============================================================
-- Same structure for Pepper, comparing peak (2020-2021) to 
-- decline (2024-2025). Mirror analysis of the FIBI recovery.

WITH counts AS (
    SELECT 
        rt.topic,
        SUM(CASE WHEN YEAR(r.review_date) IN (2020, 2021) THEN 1 ELSE 0 END) AS n_old,
        SUM(CASE WHEN YEAR(r.review_date) IN (2024, 2025) THEN 1 ELSE 0 END) AS n_new
    FROM review_topics rt
    INNER JOIN reviews r ON rt.review_id = r.review_id
    INNER JOIN apps a    ON r.app_id = a.app_id
    WHERE a.name = 'Pepper'
      AND YEAR(r.review_date) IN (2020, 2021, 2024, 2025)
    GROUP BY rt.topic
)
SELECT 
    topic,
    n_old,
    n_new,
    CAST(n_old * 100.0 / SUM(n_old) OVER () AS DECIMAL(4,1)) AS pct_old,
    CAST(n_new * 100.0 / SUM(n_new) OVER () AS DECIMAL(4,1)) AS pct_new,
    CAST(n_new * 100.0 / SUM(n_new) OVER () 
       - n_old * 100.0 / SUM(n_old) OVER () AS DECIMAL(5,1)) AS pp_change
FROM counts
ORDER BY pp_change DESC;

-- ============================================================
-- SUMMARY
-- ============================================================
-- All 11 apps in the dataset declined from their historical 
-- peak years. In topic analysis of 31K labeled reviews, four
-- topics (stability, security, login_auth, performance) show
-- the lowest average scores (1.73 to 2.25) and the highest 
-- negative-review shares (63 to 78%). Features and fees split
-- roughly evenly between positive and negative.
--
-- FIBI rose from 2.25 (2023) to 4.42 (2026). In the same 
-- period the stability share of its topic mix fell 14 points
-- and praise rose 29. Pepper fell from 4.50 (2021) to 1.95 
-- (2025). UI/UX share rose 24 points and praise dropped 50.
-- An Isracard score drop in April 2023 (162 reviews at 1.47
-- avg, roughly triple normal volume) coincides with content 
-- describing a failed app update, sampled from 30 negative 
-- reviews.
--
-- The data is consistent with foundational reliability 
-- mattering more than features for score. Topic mix differs 
-- notably across apps, consistent with bank-specific 
-- priorities mattering more than industry-wide ones.
-- ============================================================