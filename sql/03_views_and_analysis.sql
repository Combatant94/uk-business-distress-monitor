-- ============================================================
-- UK Business Distress Monitor — Reusable Views & Key Analysis
-- Two production views (national trend, industry trend) plus
-- the analysis queries used to reach the report's headline
-- findings. Each query is commented with what it was for.
-- ============================================================

USE uk_business_distress;

-- ------------------------------------------------------------
-- VIEW 1: national monthly trend — raw count, YoY %, rolling 12m
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_monthly_insolvency_trends AS
WITH monthly AS (
    SELECT month_registered AS month_date, COUNT(*) AS insolvencies
    FROM fact_insolvency
    WHERE include_table1b = 1
    GROUP BY month_registered
),
metrics AS (
    SELECT
        month_date,
        insolvencies,
        LAG(insolvencies, 12) OVER (ORDER BY month_date) AS insolvencies_12m_ago,
        SUM(insolvencies) OVER (
            ORDER BY month_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS rolling_12m_insolvencies,
        COUNT(*) OVER (
            ORDER BY month_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS months_in_window
    FROM monthly
)
SELECT
    month_date,
    insolvencies,
    insolvencies_12m_ago,
    CASE WHEN insolvencies_12m_ago > 0
         THEN ROUND(100.0 * (insolvencies - insolvencies_12m_ago) / insolvencies_12m_ago, 1)
    END AS yoy_change_pct,
    CASE WHEN months_in_window = 12 THEN rolling_12m_insolvencies END AS rolling_12m_insolvencies
FROM metrics;

-- ------------------------------------------------------------
-- VIEW 2: industry-level trend — same metrics, per 3-digit SIC,
-- plus a rolling-vs-previous-12m change used for the "who's
-- getting worse" analysis.
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW vw_industry_trends AS
WITH metrics AS (
    SELECT
        month_date,
        sic07_3_digit,
        industry_description,
        insolvencies,
        LAG(insolvencies, 12) OVER (
            PARTITION BY sic07_3_digit ORDER BY month_date
        ) AS insolvencies_12m_ago,
        SUM(insolvencies) OVER (
            PARTITION BY sic07_3_digit ORDER BY month_date
            ROWS BETWEEN 11 PRECEDING AND CURRENT ROW
        ) AS rolling_12m_insolvencies,
        SUM(insolvencies) OVER (
            PARTITION BY sic07_3_digit ORDER BY month_date
            ROWS BETWEEN 23 PRECEDING AND 12 PRECEDING
        ) AS previous_12m_insolvencies,
        COUNT(*) OVER (
            PARTITION BY sic07_3_digit ORDER BY month_date
            ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
        ) AS months_available
    FROM fact_industry_month
)
SELECT
    month_date,
    sic07_3_digit,
    industry_description,
    insolvencies,
    insolvencies_12m_ago,
    CASE WHEN insolvencies_12m_ago > 0
         THEN ROUND(100.0 * (insolvencies - insolvencies_12m_ago) / insolvencies_12m_ago, 1)
    END AS yoy_change_pct,
    CASE WHEN months_available >= 12 THEN rolling_12m_insolvencies END AS rolling_12m_insolvencies,
    CASE WHEN months_available = 24 THEN previous_12m_insolvencies END AS previous_12m_insolvencies,
    CASE WHEN months_available = 24 AND previous_12m_insolvencies > 0
         THEN ROUND(100.0 * (rolling_12m_insolvencies - previous_12m_insolvencies) / previous_12m_insolvencies, 1)
    END AS rolling_12m_change_pct
FROM metrics;

-- ------------------------------------------------------------
-- ANALYSIS: top 10 industries by rolling-12m volume (Aug 2026)
-- ------------------------------------------------------------
SELECT month_date, sic07_3_digit, industry_description, insolvencies, rolling_12m_insolvencies
FROM vw_industry_trends
WHERE month_date = '2026-08-01'
ORDER BY rolling_12m_insolvencies DESC
LIMIT 10;

-- ------------------------------------------------------------
-- ANALYSIS: strongest genuine increases (min. 50 cases in the
-- latest 12m, to filter out small-sample industries where e.g.
-- 1 -> 4 cases looks like a dramatic +300% but isn't material)
-- ------------------------------------------------------------
WITH rolling AS (
    SELECT
        sic07_3_digit,
        industry_description,
        rolling_12m_insolvencies AS rolling_12m,
        previous_12m_insolvencies AS previous_12m
    FROM vw_industry_trends
    WHERE month_date = '2026-08-01'
)
SELECT
    sic07_3_digit,
    industry_description,
    rolling_12m,
    previous_12m,
    rolling_12m - previous_12m AS absolute_change,
    ROUND(100.0 * (rolling_12m - previous_12m) / NULLIF(previous_12m, 0), 1) AS change_pct
FROM rolling
WHERE rolling_12m >= 50 AND previous_12m > 0
ORDER BY change_pct DESC
LIMIT 15;

-- ------------------------------------------------------------
-- INVESTIGATION: SIC 681 (buying & selling of own real estate)
-- was flagged as a forecasting outlier. These queries drill into
-- which months and case types drove that spike, down to company
-- level, to understand whether it was a genuine, explainable event.
-- ------------------------------------------------------------
SELECT month_date, insolvencies
FROM fact_industry_month
WHERE sic07_3_digit = '681'
ORDER BY month_date DESC
LIMIT 24;

SELECT month_registered, case_type, COUNT(*) AS insolvencies
FROM fact_insolvency
WHERE include_table1b = 1 AND sic_status = 'VALID' AND sic07_3_digit = '681'
  AND month_registered BETWEEN '2026-03-01' AND '2026-06-01'
GROUP BY month_registered, case_type
ORDER BY month_registered, insolvencies DESC;

SELECT month_registered, COUNT(*) AS administration_records, COUNT(DISTINCT company_number) AS distinct_companies
FROM fact_insolvency
WHERE include_table1b = 1 AND sic07_3_digit = '681' AND case_type = 'In Administration'
  AND month_registered BETWEEN '2026-03-01' AND '2026-06-01'
GROUP BY month_registered
ORDER BY month_registered;

-- ------------------------------------------------------------
-- ANALYSIS: within-year concentration — for each industry with
-- >= 50 insolvencies in 2026 YTD, what share of the year's total
-- fell in its single largest month (flags lumpy vs. steady industries)
-- ------------------------------------------------------------
WITH sector_2026 AS (
    SELECT sic07_3_digit, MONTH(month_registered) AS month_number, COUNT(*) AS insolvencies
    FROM fact_insolvency
    WHERE include_table1b = 1 AND sic_status = 'VALID' AND YEAR(month_registered) = 2026
    GROUP BY sic07_3_digit, MONTH(month_registered)
),
sector_stats AS (
    SELECT
        sic07_3_digit,
        SUM(insolvencies) AS ytd_2026,
        MAX(insolvencies) AS largest_month,
        ROUND(100.0 * MAX(insolvencies) / SUM(insolvencies), 1) AS largest_month_share_pct
    FROM sector_2026
    GROUP BY sic07_3_digit
)
SELECT s.sic07_3_digit, d.industry_description, s.ytd_2026, s.largest_month, s.largest_month_share_pct
FROM sector_stats AS s
JOIN dim_industry AS d ON s.sic07_3_digit = d.sic07_3_digit
WHERE s.ytd_2026 >= 50
ORDER BY s.ytd_2026 DESC
LIMIT 20;
