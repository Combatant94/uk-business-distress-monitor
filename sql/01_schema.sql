-- ============================================================
-- UK Business Distress Monitor — Schema
-- Core fact table for company insolvency records, plus indexes
-- used by the analysis queries in 03_analysis_queries.sql.
-- ============================================================

CREATE DATABASE IF NOT EXISTS uk_business_distress;
USE uk_business_distress;

CREATE TABLE fact_insolvency (
    insolvency_id BIGINT AUTO_INCREMENT PRIMARY KEY,

    company_number VARCHAR(20),
    company_name VARCHAR(255),

    register_location VARCHAR(30) NOT NULL,
    case_type VARCHAR(60) NOT NULL,
    month_registered DATE NOT NULL,

    sic07_1_digit VARCHAR(3),
    sic07_2_digit VARCHAR(3),
    sic07_3_digit VARCHAR(4),
    sic07_4_digit VARCHAR(5),
    sic07_5_digit VARCHAR(6),

    is_bulk VARCHAR(1),
    is_bulk_flag BOOLEAN NOT NULL,
    is_table1b_excluded_type BOOLEAN NOT NULL,
    include_table1b BOOLEAN NOT NULL,

    sic_status VARCHAR(10) NOT NULL
);

CREATE INDEX idx_month      ON fact_insolvency(month_registered);
CREATE INDEX idx_sic3       ON fact_insolvency(sic07_3_digit);
CREATE INDEX idx_case_type  ON fact_insolvency(case_type);
CREATE INDEX idx_table1b    ON fact_insolvency(include_table1b);

-- Industry lookup (3-digit SIC code -> description), loaded from
-- the UK Insolvency Service's published industry tables.
CREATE TABLE dim_industry (
    sic07_3_digit VARCHAR(4) PRIMARY KEY,
    industry_description VARCHAR(255) NOT NULL
);

-- Calendar dimension, generated directly from the months present
-- in fact_insolvency (see 02_dimension_build.sql).
CREATE TABLE dim_date (
    month_date DATE PRIMARY KEY,
    year INT NOT NULL,
    month_number INT NOT NULL,
    month_name VARCHAR(9) NOT NULL,
    quarter_number INT NOT NULL,
    year_month_label VARCHAR(7) NOT NULL
);
