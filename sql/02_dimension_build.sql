-- ============================================================
-- UK Business Distress Monitor — Dimension & Panel Build
-- Builds dim_date from the real data, then a zero-filled
-- month x industry panel so that every industry has one row
-- per month (including zeros) — required for LAG(12) to mean
-- "the same industry, exactly 12 calendar months earlier".
-- ============================================================

USE uk_business_distress;

-- ---- dim_date: populate the calendar from the real data ----
INSERT INTO dim_date (
    month_date, year, month_number, month_name, quarter_number, year_month_label
)
SELECT DISTINCT
    month_registered,
    YEAR(month_registered),
    MONTH(month_registered),
    MONTHNAME(month_registered),
    QUARTER(month_registered),
    DATE_FORMAT(month_registered, '%Y-%m')
FROM fact_insolvency
ORDER BY month_registered;

SELECT COUNT(*) AS months, MIN(month_date) AS first_month, MAX(month_date) AS last_month
FROM dim_date;

-- ---- fact_industry_month: zero-filled month x industry panel ----
-- CROSS JOIN every month against every industry, then LEFT JOIN the
-- real counts so industries with zero cases in a given month still
-- get an explicit row (COALESCE to 0), rather than being missing.
CREATE TABLE fact_industry_month AS
SELECT
    d.month_date,
    i.sic07_3_digit,
    i.industry_description,
    COALESCE(COUNT(f.insolvency_id), 0) AS insolvencies
FROM dim_date AS d
CROSS JOIN dim_industry AS i
LEFT JOIN fact_insolvency AS f
    ON f.month_registered = d.month_date
    AND f.sic07_3_digit = i.sic07_3_digit
    AND f.include_table1b = 1
    AND f.sic_status = 'VALID'
GROUP BY d.month_date, i.sic07_3_digit, i.industry_description;

-- Sanity check: totals should match the raw fact table for any given month
SELECT SUM(insolvencies) AS aug_2026_valid_sic_insolvencies
FROM fact_industry_month
WHERE month_date = '2026-08-01';

SELECT COUNT(*) AS zero_insolvency_months
FROM fact_industry_month
WHERE insolvencies = 0;
