"""
Stage 2: Load the cleaned data into MySQL.

Creates the fact_insolvency table (schema: sql/01_schema.sql) and loads the
validated, flagged records from Stage 1. Prompts for the MySQL password
interactively via getpass -- no credentials are stored in this repo.
"""

import sqlalchemy
import pymysql

print("SQLAlchemy:", sqlalchemy.__version__)
print("PyMySQL:", pymysql.__version__)


import pymysql
import sqlalchemy

print("SQLAlchemy:", sqlalchemy.__version__)
print("PyMySQL:", pymysql.__version__)

import getpass

mysql_password = getpass.getpass("Enter MySQL root password: ")

from sqlalchemy import create_engine, text
from urllib.parse import quote_plus

engine = create_engine(
    f"mysql+pymysql://root:{quote_plus(mysql_password)}"
    "@localhost/uk_business_distress"
)

with engine.connect() as connection:
    result = connection.execute(
        text("SELECT DATABASE();")
    )
    print(result.scalar())

sql_df = clean_df[
    [
        "company_number",
        "company_name",
        "register_location",
        "case_type",
        "month_registered",
        "sic07_1_digit",
        "sic07_2_digit",
        "sic07_3_digit",
        "sic07_4_digit",
        "sic07_5_digit",
        "is_bulk",
        "is_bulk_flag",
        "is_table1b_excluded_type",
        "include_table1b",
        "sic_status"
    ]
].copy()

print("Rows:", len(sql_df))
print("Columns:", len(sql_df.columns))

sql_df.info()

with engine.connect() as connection:
    result = connection.execute(
        text("SELECT COUNT(*) FROM fact_insolvency;")
    )
    print("Rows currently in MySQL:", result.scalar())

import pandas as pd

load_df = sql_df.astype(object).where(
    pd.notna(sql_df),
    None
)

print("Rows ready to load:", len(load_df))
print("Columns ready to load:", len(load_df.columns))

with engine.connect() as connection:
    result = connection.execute(
        text("SELECT COUNT(*) FROM fact_insolvency;")
    )
    print("Rows currently in MySQL:", result.scalar())

print("Rows ready to load:", len(load_df))
print("Columns ready to load:", len(load_df.columns))

load_df.to_sql(
    name="fact_insolvency",
    con=engine,
    if_exists="append",
    index=False,
    chunksize=1000
)

print("Upload complete.")

with engine.connect() as connection:
    mysql_count = connection.execute(
        text("SELECT COUNT(*) FROM fact_insolvency;")
    ).scalar()

print("Python rows:", len(clean_df))
print("MySQL rows:", mysql_count)
print("Difference:", mysql_count - len(clean_df))

validation_query = """
SELECT
    COUNT(*) AS total_rows,

    SUM(include_table1b = 1) AS table1b_population,

    SUM(
        include_table1b = 1
        AND month_registered = '2026-08-01'
    ) AS aug_2026_table1b,

    SUM(sic_status = 'VALID') AS valid_sic,

    SUM(sic_status = 'MISSING') AS missing_sic,

    SUM(sic_status = 'UNKNOWN') AS unknown_sic

FROM fact_insolvency;
"""

with engine.connect() as connection:
    result = connection.execute(text(validation_query)).mappings().one()

result

table1c_raw = pd.read_excel(
    excel_file,
    sheet_name="Table_1c",
    header=None
)

table1c_raw.iloc[7:20, :4]

dim_industry = table1c_raw.iloc[8:, :4].copy()

dim_industry.columns = [
    "section",
    "division",
    "sic07_3_digit",
    "industry_description"
]

# Keep only genuine 3-digit SIC group rows
dim_industry = dim_industry[
    dim_industry["sic07_3_digit"].notna()
].copy()

# Preserve leading zeros
dim_industry["sic07_3_digit"] = (
    dim_industry["sic07_3_digit"]
    .astype(str)
    .str.strip()
    .str.zfill(3)
)

dim_industry = dim_industry.reset_index(drop=True)

dim_industry.head(10)

print("Rows:", len(dim_industry))
print("Unique SIC groups:", dim_industry["sic07_3_digit"].nunique())

dim_industry.tail(10)

dim_industry.tail(3).to_dict("records")

print("Dimension rows:", len(dim_industry))
print("Unique SIC codes:", dim_industry["sic07_3_digit"].nunique())
print("Duplicate SIC codes:", dim_industry["sic07_3_digit"].duplicated().sum())
print("Missing descriptions:", dim_industry["industry_description"].isna().sum())

fact_sic = set(
    clean_df.loc[
        clean_df["sic_status"] == "VALID",
        "sic07_3_digit"
    ].dropna()
)

dim_sic = set(dim_industry["sic07_3_digit"])

unmatched = fact_sic - dim_sic

print("Valid SIC codes in insolvency data:", len(fact_sic))
print("Unmatched against dimension:", len(unmatched))
print("Unmatched codes:", sorted(unmatched))

print("Dimension rows:", len(dim_industry))
print("Unique SIC codes:", dim_industry["sic07_3_digit"].nunique())
print("Duplicate SIC codes:", dim_industry["sic07_3_digit"].duplicated().sum())
print("Missing descriptions:", dim_industry["industry_description"].isna().sum())

dim_industry = dim_industry[
    dim_industry["sic07_3_digit"].str.fullmatch(r"\d{3}")
].copy()

dim_industry = dim_industry.reset_index(drop=True)

print("Dimension rows:", len(dim_industry))
print("Unique SIC codes:", dim_industry["sic07_3_digit"].nunique())
print("Duplicate SIC codes:", dim_industry["sic07_3_digit"].duplicated().sum())
print("Missing descriptions:", dim_industry["industry_description"].isna().sum())

dim_industry.head()

dim_industry[
    ~dim_industry["section"].astype(str).str.fullmatch(r"[A-U]")
]

with engine.connect() as connection:
    count = connection.execute(
        text("SELECT COUNT(*) FROM dim_industry;")
    ).scalar()

print("Rows currently in MySQL dim_industry:", count)

dim_industry.to_sql(
    name="dim_industry",
    con=engine,
    if_exists="append",
    index=False
)

print("Industry dimension uploaded.")

with engine.connect() as connection:
    result = connection.execute(
        text("""
            SELECT
                COUNT(*) AS rows_loaded,
                COUNT(DISTINCT sic07_3_digit) AS unique_sic_codes
            FROM dim_industry;
        """)
    ).mappings().one()

result
