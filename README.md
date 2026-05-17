# Israeli Financial Apps Reviews Analyzer

> End-to-end data analytics pipeline that scrapes, enriches, and visualizes **47,188 Hebrew Google Play reviews** across **11 Israeli banking and credit card apps** over **15 years**. T-SQL analysis, Hebrew NLP, ML segmentation, and a three-page Power BI dashboard.

![Python](https://img.shields.io/badge/Python-3.13-1A3A5C?style=flat-square)
![SQL](https://img.shields.io/badge/SQL_Server-T--SQL-1A3A5C?style=flat-square)
![NLP](https://img.shields.io/badge/Hebrew_NLP-DictaBERT-C9A14A?style=flat-square)
![LLM](https://img.shields.io/badge/LLM-Claude_API-C9A14A?style=flat-square)
![ML](https://img.shields.io/badge/ML-scikit--learn-1A3A5C?style=flat-square)
![BI](https://img.shields.io/badge/BI-Power_BI-C9A14A?style=flat-square)

![Pipeline Overview](docs/images/pipeline_overview.png)

## At a Glance

- **47,188 Hebrew reviews** scraped from Google Play across 11 Israeli banking and credit card apps, 2010 to 2026.
- **11 analytical T-SQL queries** using CTEs, window functions, and conditional aggregation. Same queries feed the BI semantic model.
- **Three-page Power BI dashboard** with custom Navy/Gold theme: State of the Market, Topic Drivers, Case Studies (Leumi, Pepper, Isracard).
- **Hebrew NLP layer.** DictaBERT sentiment on 45,883 reviews; Claude API topic labels on 31,109 reviews across 10 business categories.
- **ML modeling in scikit-learn.** K-Means user segmentation (k auto-selected via silhouette score), score-change classifier (Logistic Regression vs Random Forest vs baselines), full lag sweep on stock correlation.
- **Documented null finding.** App Health Score does **not** predict parent-company TASE stock returns. All correlations sit inside |r| < 0.3 across a -8 to +8 week lag sweep.

A one-page executive PDF lives at [docs/Project_Summary.pdf](docs/Project_Summary.pdf).

## The Business Question

> Which Israeli banking apps are winning on user experience, what drives complaints, and does that signal predict business outcomes?

Four sub-questions an Israeli banking product, CX, or strategy team would need answered:

1. **Who is winning?** Composite Health Score ranking across all 11 apps.
2. **Does the digital-native promise hold?** Do Pepper and One Zero materially beat traditional banks.
3. **What drives complaints?** Which of 10 topic categories carry the harshest sentiment.
4. **Does the app signal predict TASE stock returns?** Tested rigorously across nine app-ticker pairs and 17 weekly lags.

## Key Findings

- **Digital banks beat traditional banks by 0.42 stars on average** (4.00 vs 3.58 stars). The gap is consistent year over year and shows up clearly in the per-app ranking.
- **Reliability beats features as the lever that matters.** The four harshest topic categories are all foundational: Stability (83% negative), Login & Authentication (74%), Security (72%), Customer Service (72%). Feature complaints sit at 52%.
- **Industry-wide decline since 2018.** Digital banks fell from 4.5 in 2021 to 2.0 in 2025. Pepper had the steepest individual fall: peak 4.50, trough 1.95.
- **App quality is an operating KPI, not a stock signal.** Weekly Health Score versus weekly stock return: strongest correlation in the matrix is +0.12 (Isracard, contemporaneous). Macro factors dominate at this horizon.

## Power BI Dashboard

**State of the Market.** Interactive landing page surfacing the 47K-review corpus. KPI cards, per-app Health Score heatmap covering 15 years, current 180-day ranking, peak-vs-current scatter. Tooltips show app-year detail on hover.

![State of the Market](docs/images/dashboard_state_of_market.png)

**Case Studies, told in three acts.** A narrative page that turns metrics into stories. The Pepper case study below answers *what actually happened?* with five linked components: a one-line thesis, peak-trough-current KPIs, a year-by-year trajectory, a THEN vs NOW topic mix, and a delta panel quantifying the shift. Three apps get this treatment: Leumi, Pepper, Isracard.

![Case Studies, Pepper](docs/images/dashboard_case_studies.png)

## Selected Analytical Outputs

**Segment comparison and per-app ranking.** Digital banks lead the field but the gap is closing.

![Segment Comparison](docs/images/segment_comparison.png)
![App Ranking](docs/images/app_ranking.png)

**What drives the harshest reviews.** Stability and authentication carry the highest negative sentiment shares.

![Negative Drivers](docs/images/negative_drivers.png)

**Industry trajectory since 2018.** All three segments have lost ground from their peaks.

![Time Trend](docs/images/time_trend.png)

**Stock correlation null result.** No app's Health Score predicts its parent's TASE return at weekly granularity, across the full -8 to +8 lag sweep.

![Stock Correlation](docs/images/stock_correlation.png)

**Sentiment distribution and user behavior clusters.** DictaBERT classifies 54% positive, 32% negative, 14% neutral. K-Means surfaces three user archetypes.

![Sentiment Distribution](docs/images/sentiment_distribution.png)
![Cluster Analysis](docs/images/cluster_analysis.png)

## Tech Stack

| Layer | Tools |
|---|---|
| SQL & Databases | T-SQL on Microsoft SQL Server (CTEs, window functions, conditional aggregation), SQLite, SQLAlchemy, pyodbc |
| BI & Reporting | Power BI Desktop (3-page dashboard, custom Navy & Gold theme, DAX measures, drill-throughs) |
| Python Analysis | pandas, numpy, scipy, Jupyter notebooks |
| Visualization | matplotlib, seaborn, plotly |
| ML | scikit-learn (K-Means, Logistic Regression, Random Forest, StandardScaler, silhouette score) |
| Hebrew NLP | transformers, torch, DictaBERT, Anthropic Claude API |
| Scraping & APIs | google-play-scraper, yfinance |
| Language | Python 3.13 |

## Apps Covered

| Segment | Apps | Reviews |
|---|---|---:|
| Traditional banks | Hapoalim, Leumi, Discount, Mizrahi-Tefahot, FIBI, Mercantile | 26,151 |
| Digital banks | Pepper, One Zero | 7,948 |
| Credit cards | Isracard, Cal, Max | 13,089 |

## Quick Start (No Pipeline Run Needed)

The raw data, the enriched SQLite database, and all CSV exports ship in the repo. Three ways to explore:

1. **Read the notebooks on GitHub.** All six notebooks render with charts, tables, and analytical narrative inline. Start with [`notebooks/05_advanced_eda.ipynb`](notebooks/05_advanced_eda.ipynb) for the visual story or [`notebooks/04_sql_analysis.ipynb`](notebooks/04_sql_analysis.ipynb) for the SQL.
2. **Query the data directly.** Open `data/processed/reviews.db` in DB Browser for SQLite, DBeaver, or directly in Python with `sqlite3`. Nine tables: reviews, derived features, topic labels, weekly app metrics, user features, daily stock prices, plus apps, stock tickers, and Health-Stock correlations. CSV snapshots in `data/exports/`.
3. **Open the dashboard.** Open `power_bi/Banking_analyst_pbi.pbix` in Power BI Desktop and repoint the data source to the bundled SQLite database or the CSVs.

---

## Bottom Line for a Stakeholder

**The digital advantage is real, but fragile and shrinking.** Digital-native banks lead by 0.42 stars on the segment average, yet Pepper itself fell from a 4.50 peak in 2021 to 1.95 in 2025. The story is not that digital banks are immune to user frustration. The story is that they started from a stronger base. Incumbents that close the experience gap will compete on equal footing within three to five years.

**Reliability beats features as the lever that matters.** Engineering resources allocated to crash rates, auth flow reliability, and incident response will move the satisfaction needle more than any new feature. The complaint mix is the dashboard.

**Treat app quality as an operating KPI, not a stock signal.** Weekly correlations sit inside |r| < 0.3 across all nine app-ticker pairs. At that horizon, macro factors dominate. App quality matters for retention, support cost, and brand. Treating it as a leading indicator for equity is overreach.

## Sample T-SQL

The Pepper decline analysis from `sql/02_analysis.sql`. CTE with conditional aggregation, two window functions for percentage-of-total within partitions, and a percentage-point delta. This is the query that feeds the Power BI THEN vs NOW panel.

```sql
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
```

## Pipeline

**1. Data collection.** Google Play Store (country IL, language he) via `google-play-scraper`, wrapped in `scripts/run_scraper.py` with 200 reviews per request, resumable runs, JSON backups. 47,188 reviews loaded into SQLite.

**2. ETL and storage.** SQLite working store at `data/processed/reviews.db`. Production warehouse on Microsoft SQL Server (`AppReviewsAnalysis`) via `scripts/import_to_sqlserver.py`. Nine tables with PKs, FKs, and four indexes on the reviews table.

**3. NLP and feature engineering.** DictaBERT for Hebrew sentiment (45,883 reviews). Claude Haiku for topic labeling (31,109 reviews, 10 business categories, stratified sampling). User-level aggregation with 10 behavioral features. Weekly Health Score per app combining average rating, sentiment balance, momentum, normalized volume, and developer response rate. Daily TASE stock prices for six listed parents and their subsidiaries via yfinance.

**4. Analysis in three parallel streams.**

- **SQL analysis.** Eleven analytical T-SQL queries in `sql/02_analysis.sql`. Heavy use of CTEs, window functions, and conditional aggregation. Same queries feed the Power BI semantic model.
- **Python EDA.** Six Jupyter notebooks tell the story phase by phase. Twelve charts inline.
- **ML modeling.** K-Means user segmentation, score-change classifier, stock correlation lag sweep, topic lift analysis.

**5. Visualization.** Power BI dashboard at `power_bi/Banking_analyst_pbi.pbix` with custom Navy and Gold theme and three pages.

## Notebooks

| # | Notebook | Purpose |
|---|---|---|
| 01 | `01_data_collection.ipynb` | Scraping setup, app registry, volume audit |
| 02 | `02_initial_eda.ipynb` | Score distributions, missingness, data quality |
| 03 | `03_feature_engineering.ipynb` | Structural features, DictaBERT sentiment, topic labels |
| 04 | `04_sql_analysis.ipynb` | Eleven analytical queries answering the four business questions |
| 05 | `05_advanced_eda.ipynb` | Visual validation of SQL findings |
| 06 | `06_user_segmentation.ipynb` | K-Means clustering on user behavior, cluster profile interpretation |

## Project Structure

```
app-reviews-analyzer/
├── docs/                       # PDF summary, dashboard screenshots
├── notebooks/                  # Six analytical notebooks (01 to 06)
├── src/
│   ├── config.py               # App registry, global settings
│   ├── scrapers/               # Google Play scraping
│   ├── database/               # Schema and connection utilities
│   ├── cleaning/               # Text normalization, language detection
│   └── analysis/               # Sentiment and Health Score
├── scripts/                    # Thirteen runnable end-to-end scripts
├── sql/                        # T-SQL schema, eleven analysis queries, views
├── power_bi/                   # Power BI report and theme
├── data/
│   ├── raw/                    # Raw JSON from the Google Play scraper
│   ├── processed/              # Populated SQLite database
│   └── exports/                # Tabular CSV exports (one per DB table)
└── requirements.txt
```

## Setup (Full Pipeline Run)

```bash
git clone https://github.com/taljacob28/app-reviews-analyzer.git
cd app-reviews-analyzer

python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate        # macOS / Linux

pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY`. Optionally `SQL_SERVER_HOST` and `SQL_SERVER_DATABASE` for the production warehouse.

```bash
python -m src.database.db                       # initialize the database
python scripts/run_scraper.py --verify-only     # verify app IDs
python scripts/run_scraper.py                   # scrape all 11 apps
python scripts/clean_data.py                    # clean and engineer features
python scripts/compute_sentiment.py             # DictaBERT sentiment
python scripts/label_topics_with_llm.py --n 500 # Claude topic labels
python scripts/build_user_features.py
python scripts/segment_users.py
python scripts/compute_health_score.py
python scripts/fetch_stock_prices.py
python scripts/analyze_stocks_vs_reviews.py
python scripts/export_to_csv.py
python scripts/import_to_sqlserver.py           # optional: push to SQL Server
```

## Limitations

- **No stable user IDs.** Google Play does not expose persistent identifiers. Reviews are grouped by display name, which conflates distinct users sharing common Hebrew names. User-level analysis treats these as behavioral archetypes, not individuals.
- **Self-selection bias.** Users with strong opinions are over-represented. The dataset measures discontent and praise rather than satisfaction in the general population.
- **Model error in labels.** DictaBERT achieves about 85% accuracy on Hebrew benchmarks. Claude topic labels were validated on a 500-review held-out sample.

## Contact

**Tal Jacob.** PhD candidate, Political Science, Tel Aviv University. Transitioning to data analytics.

- Email: [taljacob28@gmail.com](mailto:taljacob28@gmail.com)
- GitHub: [@taljacob28](https://github.com/taljacob28)
- LinkedIn: [linkedin.com/in/tal-jacob-9753bb256](https://www.linkedin.com/in/tal-jacob-9753bb256)

## License

MIT
