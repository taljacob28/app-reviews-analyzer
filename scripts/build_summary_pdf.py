"""
Build an executive PDF summary of the Israeli Financial Apps Reviews Analyzer project.

Design choices match the hebrew-news-sentiment summary for portfolio consistency:
- Justified body text (alignment=TA_JUSTIFY) on every paragraph.
- Generous line spacing (~1.5x leading) for readability.
- Two-page A4 layout: page 1 = context + findings, page 2 = methodology + skills.
- Navy/gold color identity consistent with the Power BI theme and CV.

Output: docs/Project_Summary.pdf
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "Project_Summary.pdf"
PIPELINE_IMG = ROOT / "docs" / "images" / "pipeline_overview.png"

# Color identity (matches the Power BI Navy/Gold theme)
NAVY = colors.HexColor("#1A3A5C")
GOLD = colors.HexColor("#C9A14A")
TEXT = colors.HexColor("#1F1F1F")
SUB = colors.HexColor("#555555")
RULE = colors.HexColor("#D5D5D5")


def make_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"],
            fontName="Helvetica-Bold", fontSize=19, textColor=NAVY,
            leading=23, spaceAfter=4, alignment=TA_LEFT,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=9.5, textColor=SUB,
            leading=14, spaceAfter=8, alignment=TA_JUSTIFY,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"],
            fontName="Helvetica-Bold", fontSize=12, textColor=NAVY,
            leading=15, spaceBefore=8, spaceAfter=4, alignment=TA_LEFT,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"],
            fontName="Helvetica", fontSize=9.5, textColor=TEXT,
            leading=15, spaceAfter=6, alignment=TA_JUSTIFY,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base["Normal"],
            fontName="Helvetica", fontSize=9.5, textColor=TEXT,
            leading=15, leftIndent=14, bulletIndent=2,
            spaceAfter=4, alignment=TA_JUSTIFY,
        ),
        "caption": ParagraphStyle(
            "caption", parent=base["Normal"],
            fontName="Helvetica-Oblique", fontSize=8.5, textColor=SUB,
            leading=12, spaceAfter=8, alignment=TA_CENTER,
        ),
        "footer": ParagraphStyle(
            "footer", parent=base["Normal"],
            fontName="Helvetica", fontSize=8, textColor=SUB,
            leading=11, alignment=TA_CENTER,
        ),
    }


def horizontal_rule(width_cm=17.6, color=RULE, thickness=0.5, space=6):
    t = Table([[""]], colWidths=[width_cm * cm], rowHeights=[0.01])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), thickness, color),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), space),
    ]))
    return t


def header_band(S):
    return [
        Paragraph("Israeli Financial Apps Reviews Analyzer", S["title"]),
        Paragraph(
            "End-to-end data analytics pipeline that scrapes, enriches, and visualizes "
            "<b>47,188 Hebrew Google Play reviews</b> across <b>11 Israeli banking and credit card apps</b> "
            "over <b>15 years</b>. The work pairs T-SQL analysis on Microsoft SQL Server with Hebrew NLP, "
            "scikit-learn ML, and a three-page Power BI dashboard with a custom Navy and Gold theme. "
            "<i>Portfolio analytics project. The full pipeline is reproducible from the bundled SQLite "
            "database and CSV exports without re-scraping or re-labeling.</i>",
            S["subtitle"],
        ),
    ]


def pipeline_image(S):
    elements = []
    if PIPELINE_IMG.exists():
        img = Image(str(PIPELINE_IMG), width=17.5 * cm, height=5.5 * cm)
        img.hAlign = "CENTER"
        elements.append(img)
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            "Figure 1. End-to-end pipeline from Google Play ingestion through SQL warehousing, "
            "Hebrew NLP enrichment, and the three-page Power BI dashboard.",
            S["caption"],
        ))
    return elements


def business_question_block(S):
    return [
        Paragraph("The Business Question", S["h2"]),
        Paragraph(
            "Israeli banks compete on digital experience, yet leadership teams rarely see a unified, "
            "evidence-based view of how their app stacks up against the rest of the market. This project "
            "answers the operational question: <b>Which Israeli banking apps are winning on user "
            "experience, what drives complaints, and does that signal predict business outcomes?</b>",
            S["body"],
        ),
        Paragraph(
            "Four sub-questions an Israeli banking product, CX, or strategy team needs answered: "
            "<b>(1)</b> Who is winning? "
            "<b>(2)</b> Does the digital-native promise hold? "
            "<b>(3)</b> What drives complaints across 10 topic categories? "
            "<b>(4)</b> Does the app signal predict TASE stock returns?",
            S["body"],
        ),
    ]


def findings_block(S):
    bullets = [
        "<b>Digital banks beat traditional banks by 0.42 stars on average</b> (4.00 vs 3.58 stars). "
        "The gap is consistent year over year and shows up clearly in the per-app ranking.",

        "<b>Reliability beats features as the lever that matters.</b> The four harshest topic categories "
        "are all foundational: Stability (83% negative), Login &amp; Authentication (74%), Security "
        "(72%), Customer Service (72%). Feature complaints sit at 52%.",

        "<b>Industry-wide decline since 2018.</b> Digital banks fell from 4.5 in 2021 to 2.0 in 2025. "
        "Pepper had the steepest individual fall: peak 4.50, trough 1.95.",

        "<b>App quality is an operating KPI, not a stock signal.</b> Weekly Health Score versus weekly "
        "stock return: strongest correlation in the matrix is +0.12 (Isracard, contemporaneous), "
        "documented null finding across nine app-ticker pairs and the full -8 to +8 week lag sweep. "
        "Macro factors dominate at this horizon.",
    ]
    elements = [Paragraph("Key Findings", S["h2"])]
    for b in bullets:
        elements.append(Paragraph("&bull;&nbsp; " + b, S["bullet"]))
    return elements


def bottom_line_block(S):
    return [
        Paragraph("Bottom Line for a Stakeholder", S["h2"]),
        Paragraph(
            "<b>The digital advantage is real, but fragile and shrinking.</b> Digital-native banks lead "
            "by 0.42 stars on the segment average, yet Pepper itself fell from a 4.50 peak in 2021 to "
            "1.95 in 2025. Incumbents that close the experience gap will compete on equal footing within "
            "three to five years.",
            S["body"],
        ),
        Paragraph(
            "<b>Reliability beats features as the lever that matters.</b> Engineering resources allocated "
            "to crash rates, auth flow reliability, and incident response will move the satisfaction "
            "needle more than any new feature. The complaint mix is the dashboard.",
            S["body"],
        ),
        Paragraph(
            "<b>Treat app quality as an operating KPI, not a stock signal.</b> Weekly correlations sit "
            "inside |r| &lt; 0.3 across all nine app-ticker pairs and across the full -8 to +8 week lag "
            "sweep. App quality matters for retention, support cost, and brand. Treating it as a leading "
            "indicator for equity is overreach.",
            S["body"],
        ),
    ]


def methodology_block(S):
    return [
        Paragraph("Methodology Highlights", S["h2"]),
        Paragraph(
            "<b>Data layer.</b> 47,188 reviews scraped from Google Play (IL, he) with resumable runs and "
            "JSON backups. Loaded into a nine-table SQLite warehouse with primary keys, foreign keys, "
            "and four indexes on the reviews table. Production warehouse on Microsoft SQL Server, "
            "migrated via `import_to_sqlserver.py`.",
            S["body"],
        ),
        Paragraph(
            "<b>NLP and feature engineering.</b> DictaBERT classifies sentiment on 45,883 reviews. "
            "Anthropic Claude Haiku labels 31,109 reviews against 10 business categories using "
            "stratified sampling by sentiment. A composite Health Score per week per app combines "
            "average rating, sentiment balance, momentum, normalized volume, and developer response.",
            S["body"],
        ),
        Paragraph(
            "<b>Analysis in three parallel streams.</b> Eleven analytical T-SQL queries (CTEs, window "
            "functions, conditional aggregation) feed the Power BI semantic model. Six Jupyter notebooks "
            "tell the analytical story phase by phase. Three scikit-learn modeling layers: K-Means user "
            "segmentation with k auto-selected by silhouette score, score-change classifier (Logistic "
            "Regression vs Random Forest vs majority-class and regression-to-mean baselines), and a "
            "full lag sweep for stock correlation.",
            S["body"],
        ),
    ]


def skills_block(S):
    bullets = [
        "<b>Advanced T-SQL.</b> Eleven analytical queries using CTEs, window functions, and conditional "
        "aggregation. Same queries drive both the EDA notebooks and the BI semantic model.",

        "<b>Power BI dashboard.</b> Three pages with custom Navy and Gold theme: State of the Market "
        "(KPIs, Health Score heatmap, peak-vs-current scatter), Topic Drivers, Case Studies (Leumi, "
        "Pepper, Isracard) with DAX measures and drill-through navigation.",

        "<b>Hebrew NLP at scale.</b> DictaBERT sentiment on 45,883 reviews. Claude API topic labeling "
        "across 10 business categories with stratified sampling.",

        "<b>ML modeling in scikit-learn.</b> K-Means user segmentation, score-change classifier, full "
        "-8 to +8 week lag sweep for stock correlation. Compared against principled baselines, not "
        "just defaults.",

        "<b>Production ETL.</b> SQLite working store, Microsoft SQL Server production warehouse, "
        "9-table schema with PKs, FKs, indexed lookups, resumable scrapers, structured logging.",

        "<b>Analyst judgment.</b> Documented null finding on stock correlation. Explicit limitations on "
        "self-selection bias and the lack of stable user IDs. Findings framed as evidence rather than "
        "as marketing.",
    ]
    elements = [Paragraph("Skills Demonstrated", S["h2"])]
    for b in bullets:
        elements.append(Paragraph("&bull;&nbsp; " + b, S["bullet"]))
    return elements


def tech_stack_block(S):
    return [
        Paragraph("Tech Stack", S["h2"]),
        Paragraph(
            "Python 3.13. T-SQL on Microsoft SQL Server with CTEs, window functions, and conditional "
            "aggregation. SQLite via SQLAlchemy. pyodbc for SQL Server. Power BI Desktop with custom "
            "theme and DAX. transformers and torch for DictaBERT. Anthropic Claude API for topic "
            "labeling. scikit-learn for K-Means, Logistic Regression, and Random Forest. pandas, numpy, "
            "scipy for analytics. matplotlib, seaborn, and plotly for visualization. google-play-scraper "
            "and yfinance for ingestion.",
            S["body"],
        ),
    ]


def footer_block(S):
    footer = Table(
        [[Paragraph(
            "Tal Jacob &middot; Data Analyst &middot; "
            "<font color='#1A3A5C'><b>github.com/taljacob28/app-reviews-analyzer</b></font> &middot; "
            "taljacob28@gmail.com",
            S["footer"]
        )]],
        colWidths=[17.6 * cm],
    )
    footer.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [Spacer(1, 6), footer]


def make_pdf():
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=1.7 * cm, rightMargin=1.7 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="full",
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="single", frames=[frame])])

    S = make_styles()
    story = []

    # ----- PAGE 1: context + business question + findings -----
    story.extend(header_band(S))
    story.extend(pipeline_image(S))
    story.append(horizontal_rule())
    story.extend(business_question_block(S))
    story.extend(findings_block(S))

    # ----- PAGE 2: bottom line + methodology + skills + tech -----
    story.append(PageBreak())
    story.extend(bottom_line_block(S))
    story.extend(methodology_block(S))
    story.extend(skills_block(S))
    story.extend(tech_stack_block(S))
    story.extend(footer_block(S))

    doc.build(story)
    print(f"Wrote: {OUTPUT}")


if __name__ == "__main__":
    make_pdf()
