"""
Stage 1: Load, validate and clean the raw insolvency data.

Loads the raw UK Insolvency Service record-level extract, cross-checks it
cell-for-cell against the official published monthly and industry tables
(44/44 months, 272/272 SIC groups), then derives the boolean flags
(is_bulk_flag, include_table1b, sic_status) used by every later stage.

Nothing downstream in this project is calculated until this script's checks
pass exactly -- see WALKTHROUGH.md, "Stage 1" for why that order matters.

Note: this is extracted from the exploratory notebook (notebooks/) to show
the pipeline stages clearly. The notebook is the canonical, runnable record;
this script mirrors it for readability and is not independently re-tested
outside that notebook environment.
"""

import pandas as pd
import numpy as np

pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", 100)

print("Pandas version:", pd.__version__)
print("NumPy version:", np.__version__)

df = pd.read_csv(
    "record-level-data.csv",
    encoding="latin1",
    low_memory=False
)

print("Dataset loaded successfully.")
print("Shape:", df.shape)

df.head()

df.columns.tolist()

df.info()

with open("README.txt", "r", encoding="latin1") as f:
    readme = f.read()

print(readme)

metadata = pd.read_csv(
    "Metadata.csv",
    encoding="latin1"
)

metadata

print("REGISTER LOCATION")
print(df["register_location"].value_counts(dropna=False))

print("\nCASE TYPE")
print(df["case_type"].value_counts(dropna=False))

print("\nBULK FLAG")
print(df["is_bulk"].value_counts(dropna=False))

print("Earliest month:", df["month_registered"].min())
print("Latest month:", df["month_registered"].max())
print("Number of months:", df["month_registered"].nunique())

excel_file = "Data_Tables_in_Excel__xlsx__Format_-_Company_Insolvency_Statistics_August_2026.xlsx"

xls = pd.ExcelFile(excel_file)

xls.sheet_names

excel_file = "Data_Tables_in_Excel__xlsx__Format_-_Company_Insolvency_Statistics_August_2026.xlsx"

xls = pd.ExcelFile(excel_file)

xls.sheet_names

contents = pd.read_excel(
    excel_file,
    sheet_name="Contents",
    header=None
)

pd.set_option("display.max_colwidth", None)

contents

table_1b_raw = pd.read_excel(
    excel_file,
    sheet_name="Table_1b",
    header=None
)

table_1b_raw.head(25)

df["is_bulk"].value_counts(dropna=False)

table1b_population = df[
    (df["register_location"] == "England/Wales") &
    (df["is_bulk"].isna()) &
    (~df["case_type"].isin([
        "Administration to CVL",
        "Moratorium"
    ]))
].copy()

print("All records:", f"{len(df):,}")
print("Table 1b population:", f"{len(table1b_population):,}")

aug_2026 = table1b_population[
    table1b_population["month_registered"] == "2026-08"
]

print("August 2026 total:", f"{len(aug_2026):,}")

print("\nBreakdown by insolvency type:")
print(aug_2026["case_type"].value_counts())

aug_all = df[
    (df["register_location"] == "England/Wales") &
    (df["month_registered"] == "2026-08")
].copy()

print("All England/Wales records in August 2026:", len(aug_all))

pd.crosstab(
    aug_all["case_type"],
    aug_all["is_bulk"],
    dropna=False,
    margins=True
)

aug_all[
    ["case_type", "is_bulk"]
].value_counts(dropna=False)

df[
    df["month_registered"] == "2026-08"
].groupby(
    ["register_location", "case_type"],
    dropna=False
).size()

df[
    df["month_registered"] == "2026-08"
].shape

df.tail(20)

df[
    df["month_registered"] == "2026-08"
].groupby(
    ["register_location", "case_type"],
    dropna=False
).size()

df[
    df["month_registered"] == "2026-08"
].shape

table_1b_raw[
    table_1b_raw[0].astype(str).str.contains(
        "Aug 2026",
        case=False,
        na=False
    )
]

table_1b_raw.tail(15)

python_monthly = (
    table1b_population
    .groupby("month_registered")
    .size()
    .reset_index(name="python_total")
)

python_monthly.head()

python_monthly.tail(10)

official_1b = pd.read_excel(
    excel_file,
    sheet_name="Table_1b",
    header=8
)

official_1b.head()

official_1b.columns.tolist()

official_1b["Period"].tolist()

official_monthly = official_1b.copy()

official_monthly["period_date"] = pd.to_datetime(
    official_monthly["Period"],
    format="%b %Y",
    errors="coerce"
)

official_monthly = official_monthly[
    official_monthly["period_date"].notna()
].copy()

official_monthly.head()

official_monthly.tail()

official_monthly.shape

python_monthly["period_date"] = pd.to_datetime(
    python_monthly["month_registered"],
    format="%Y-%m"
)

python_monthly.head()

reconciliation = official_monthly[
    [
        "period_date",
        "Total Company Insolvencies"
    ]
].merge(
    python_monthly[
        [
            "period_date",
            "python_total"
        ]
    ],
    on="period_date",
    how="left"
)

reconciliation = reconciliation.rename(
    columns={
        "Total Company Insolvencies": "official_total"
    }
)

reconciliation.head(10)

reconciliation["difference"] = (
    reconciliation["python_total"]
    - reconciliation["official_total"]
)

reconciliation["match"] = (
    reconciliation["difference"] == 0
)

reconciliation

print(
    "Months checked:",
    len(reconciliation)
)

print(
    "Exact matches:",
    reconciliation["match"].sum()
)

print(
    "Mismatches:",
    (~reconciliation["match"]).sum()
)

print(
    "Maximum absolute difference:",
    reconciliation["difference"].abs().max()
)

print(
    "Months checked:",
    len(reconciliation)
)

print(
    "Exact matches:",
    reconciliation["match"].sum()
)

print(
    "Mismatches:",
    (~reconciliation["match"]).sum()
)

print(
    "Maximum absolute difference:",
    reconciliation["difference"].abs().max()
)

reconciliation[
    reconciliation["match"] == False
]

python_by_type = (
    table1b_population
    .groupby(
        ["month_registered", "case_type"]
    )
    .size()
    .unstack(fill_value=0)
    .reset_index()
)

python_by_type.tail()

print("Months checked:", len(reconciliation))
print("Exact matches:", reconciliation["match"].sum())
print("Mismatches:", (~reconciliation["match"]).sum())
print(
    "Maximum absolute difference:",
    reconciliation["difference"].abs().max()
)

reconciliation[
    reconciliation["match"] == False
]

table_1c_raw = pd.read_excel(
    excel_file,
    sheet_name="Table_1c",
    header=None
)

table_1c_raw.head(30)

print("Shape:", table_1c_raw.shape)

official_1c = pd.read_excel(
    excel_file,
    sheet_name="Table_1c",
    header=7
)

official_1c.head()

official_3digit = official_1c[
    official_1c["Group"].notna()
].copy()

print("3-digit industry rows:", len(official_3digit))

official_3digit[
    ["Section", "Division", "Group", "Description", "Aug 2026"]
].head(15)

official_3digit[
    ["Section", "Division", "Group", "Description", "Aug 2026"]
].tail(15)

official_3digit[
    official_3digit["Group"].astype(str).str.contains(
        "UNK",
        case=False,
        na=False
    )
][["Section", "Division", "Group", "Description", "Aug 2026"]]

official_1c[
    official_1c["Description"].astype(str).str.contains(
        "unknown|unclassified",
        case=False,
        na=False
    )
][["Section", "Division", "Group", "Description", "Aug 2026"]]

official_3digit[
    ["Section", "Division", "Group", "Description", "Aug 2026"]
].head(15)

aug_2026_3digit = (
    table1b_population[
        table1b_population["month_registered"] == "2026-08"
    ]
    .groupby("sic07_3_digit", dropna=False)
    .size()
    .reset_index(name="python_count")
)

aug_2026_3digit.head(15)

aug_2026_3digit[
    aug_2026_3digit["sic07_3_digit"].isin(["UNK"]) |
    aug_2026_3digit["sic07_3_digit"].isna()
]

print("Total August records:", aug_2026_3digit["python_count"].sum())
print("Number of SIC groups:", len(aug_2026_3digit))

official_1c[
    official_1c["Description"]
    .astype(str)
    .str.contains(
        "unknown|unclassified|classification",
        case=False,
        na=False
    )
][
    ["Section", "Division", "Group", "Description", "Aug 2026"]
]

official_1c[
    ["Section", "Division", "Group", "Description", "Aug 2026"]
].tail(20)

official_3digit_clean = official_1c[
    official_1c["Group"].notna() &
    (official_1c["Section"] != "Total") &
    (official_1c["Section"] != "V")
].copy()

official_3digit_clean[
    ["Section", "Division", "Group", "Description", "Aug 2026"]
].head()

python_3digit_clean = aug_2026_3digit[
    aug_2026_3digit["sic07_3_digit"].notna() &
    (aug_2026_3digit["sic07_3_digit"] != "UNK")
].copy()

print(
    "Official 3-digit groups:",
    len(official_3digit_clean)
)

print(
    "Python 3-digit groups:",
    len(python_3digit_clean)
)

print(
    "Official Aug 2026 total across 3-digit groups:",
    official_3digit_clean["Aug 2026"].sum()
)

print(
    "Python Aug 2026 total across known 3-digit groups:",
    python_3digit_clean["python_count"].sum()
)

official_3digit_clean["Group"] = (
    official_3digit_clean["Group"]
    .astype(str)
    .str.strip()
)

python_3digit_clean["sic07_3_digit"] = (
    python_3digit_clean["sic07_3_digit"]
    .astype(str)
    .str.strip()
)

sic_reconciliation = official_3digit_clean[
    ["Group", "Description", "Aug 2026"]
].merge(
    python_3digit_clean[
        ["sic07_3_digit", "python_count"]
    ],
    left_on="Group",
    right_on="sic07_3_digit",
    how="outer"
)

sic_reconciliation["official_count"] = (
    sic_reconciliation["Aug 2026"]
    .fillna(0)
)

sic_reconciliation["python_count"] = (
    sic_reconciliation["python_count"]
    .fillna(0)
)

sic_reconciliation["difference"] = (
    sic_reconciliation["python_count"]
    - sic_reconciliation["official_count"]
)

sic_reconciliation["match"] = (
    sic_reconciliation["difference"] == 0
)

print("SIC groups checked:", len(sic_reconciliation))
print("Exact matches:", sic_reconciliation["match"].sum())
print("Mismatches:", (~sic_reconciliation["match"]).sum())
print(
    "Maximum absolute difference:",
    sic_reconciliation["difference"].abs().max()
)

sic_reconciliation[
    sic_reconciliation["match"] == False
][
    [
        "Group",
        "Description",
        "official_count",
        "python_count",
        "difference"
    ]
]

sic_reconciliation[
    sic_reconciliation["Group"].isna()
][
    [
        "sic07_3_digit",
        "python_count"
    ]
]

print(
    python_3digit_clean[
        python_3digit_clean["sic07_3_digit"].isin(
            ["13", "14", "16", "22", "62",
             "013", "014", "016", "022", "062"]
        )
    ]
)

python_3digit_clean["sic07_3_digit"] = (
    python_3digit_clean["sic07_3_digit"]
    .astype(str)
    .str.strip()
    .str.zfill(3)
)

python_3digit_clean[
    python_3digit_clean["sic07_3_digit"].isin(
        ["013", "014", "016", "022", "062"]
    )
]

sic_reconciliation = official_3digit_clean[
    ["Group", "Description", "Aug 2026"]
].merge(
    python_3digit_clean[
        ["sic07_3_digit", "python_count"]
    ],
    left_on="Group",
    right_on="sic07_3_digit",
    how="outer"
)

sic_reconciliation["official_count"] = (
    sic_reconciliation["Aug 2026"].fillna(0)
)

sic_reconciliation["python_count"] = (
    sic_reconciliation["python_count"].fillna(0)
)

sic_reconciliation["difference"] = (
    sic_reconciliation["python_count"]
    - sic_reconciliation["official_count"]
)

sic_reconciliation["match"] = (
    sic_reconciliation["difference"] == 0
)

print("SIC groups checked:", len(sic_reconciliation))
print("Exact matches:", sic_reconciliation["match"].sum())
print("Mismatches:", (~sic_reconciliation["match"]).sum())
print(
    "Maximum absolute difference:",
    sic_reconciliation["difference"].abs().max()
)

sic_reconciliation[
    sic_reconciliation["match"] == False
]

clean_df = df.copy()

clean_df["month_registered"] = pd.to_datetime(
    clean_df["month_registered"],
    format="%Y-%m"
)

for col, width in {
    "sic07_2_digit": 2,
    "sic07_3_digit": 3,
    "sic07_4_digit": 4
}.items():
    
    mask = (
        clean_df[col].notna()
        & (clean_df[col] != "UNK")
    )
    
    clean_df.loc[mask, col] = (
        clean_df.loc[mask, col]
        .astype(str)
        .str.strip()
        .str.zfill(width)
    )

clean_df[
    [
        "month_registered",
        "sic07_2_digit",
        "sic07_3_digit",
        "sic07_4_digit",
        "sic07_5_digit"
    ]
].head(10)

clean_df.info()

clean_df["sic07_5_digit"] = (
    clean_df["sic07_5_digit"]
    .astype("Int64")
    .astype("string")
    .str.zfill(5)
)

clean_df[
    [
        "sic07_1_digit",
        "sic07_2_digit",
        "sic07_3_digit",
        "sic07_4_digit",
        "sic07_5_digit"
    ]
].head(10)

clean_df["sic07_5_digit"].dtype

clean_df[
    clean_df["sic07_2_digit"].str.startswith("0", na=False)
][
    [
        "sic07_1_digit",
        "sic07_2_digit",
        "sic07_3_digit",
        "sic07_4_digit",
        "sic07_5_digit"
    ]
].head(10)

clean_df["is_bulk_flag"] = (
    clean_df["is_bulk"].eq("Y")
)

clean_df["is_table1b_excluded_type"] = (
    clean_df["case_type"].isin([
        "Administration to CVL",
        "Moratorium"
    ])
)

clean_df["include_table1b"] = (
    (clean_df["register_location"] == "England/Wales")
    & (~clean_df["is_bulk_flag"])
    & (~clean_df["is_table1b_excluded_type"])
)

clean_df["include_table1b"].value_counts()

clean_df[
    (clean_df["month_registered"] == "2026-08-01")
    & (clean_df["include_table1b"])
].shape[0]

clean_df["sic_status"] = "VALID"

clean_df.loc[
    clean_df["sic07_3_digit"].isna(),
    "sic_status"
] = "MISSING"

clean_df.loc[
    clean_df["sic07_3_digit"].eq("UNK"),
    "sic_status"
] = "UNKNOWN"

clean_df["sic_status"].value_counts(dropna=False)

clean_df.loc[
    clean_df["include_table1b"],
    "sic_status"
].value_counts(dropna=False)
