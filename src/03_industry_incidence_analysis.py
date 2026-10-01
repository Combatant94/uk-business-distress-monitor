"""
Stage 3: Bring in ONS business-population data and compute industry incidence.

Joins ONS enterprise-population counts by 3-digit SIC code to turn raw
insolvency counts into a rate per 10,000 enterprises, then compares that
rate across industries for 2025 and tracks it from 2017-2025 against a 2019
pre-pandemic reference year. See WALKTHROUGH.md, "Stage 3" and "Stage 4".
"""


import pandas as pd

ons_file = "ah1756p.xls"

ons_excel = pd.ExcelFile(ons_file)

print(ons_excel.sheet_names)

for sheet in ons_excel.sheet_names:
    print(f"\n--- {sheet} ---")
    
    preview = pd.read_excel(
        ons_file,
        sheet_name=sheet,
        header=None
    )
    
    print("Shape:", preview.shape)
    print(preview.head(15))

analysis1_raw = pd.read_excel(
    ons_file,
    sheet_name="Analysis 1",
    header=None
)

print(analysis1_raw.tail(25))

print("Shape:", analysis1_raw.shape)
print("Non-null values in first column:",
      analysis1_raw[0].notna().sum())

print(analysis1_raw.tail(25))

print(analysis1_raw.tail(25).to_string())

import re

# Keep only genuine 3-digit SIC group rows
ons_business = analysis1_raw[
    analysis1_raw[0]
    .astype(str)
    .str.match(r"^\d{3}\s*:")
].copy()

print("SIC rows found:", len(ons_business))

print(ons_business.head())
print(ons_business.tail())

# ---------------------------------------------------------
# Build annual SIC-3 enterprise denominator: 2017–2025
# ---------------------------------------------------------

years = list(range(2017, 2026))

# In Analysis 1:
# col 1 = 2017 count, col 3 = 2018 count ... col 17 = 2025 count
count_columns = {
    1: 2017,
    3: 2018,
    5: 2019,
    7: 2020,
    9: 2021,
    11: 2022,
    13: 2023,
    15: 2024,
    17: 2025
}

# Extract SIC and description
ons_business["sic07_3_digit"] = (
    ons_business[0]
    .str.extract(r"^(\d{3})")[0]
)

ons_business["industry_description"] = (
    ons_business[0]
    .str.replace(r"^\d{3}\s*:\s*", "", regex=True)
)

# Wide → long
denominator_parts = []

for col, year in count_columns.items():
    temp = ons_business[
        ["sic07_3_digit", "industry_description", col]
    ].copy()

    temp["year"] = year
    temp = temp.rename(columns={col: "enterprise_count"})

    denominator_parts.append(temp)

enterprise_population = pd.concat(
    denominator_parts,
    ignore_index=True
)

enterprise_population["enterprise_count"] = pd.to_numeric(
    enterprise_population["enterprise_count"],
    errors="coerce"
)

enterprise_population = enterprise_population[
    [
        "year",
        "sic07_3_digit",
        "industry_description",
        "enterprise_count"
    ]
].sort_values(
    ["year", "sic07_3_digit"]
).reset_index(drop=True)

print("Rows:", len(enterprise_population))
print("Years:", enterprise_population["year"].min(),
      "to", enterprise_population["year"].max())
print("SIC groups:", enterprise_population["sic07_3_digit"].nunique())
print("Missing counts:", enterprise_population["enterprise_count"].isna().sum())

print(enterprise_population.head(10))

from sqlalchemy import text
import pandas as pd

query = """
SELECT
    sic07_3_digit,
    COUNT(*) AS insolvencies_2025
FROM fact_insolvency
WHERE include_table1b = 1
  AND sic_status = 'VALID'
  AND YEAR(month_registered) = 2025
GROUP BY sic07_3_digit;
"""

with engine.connect() as conn:
    insolvency_2025 = pd.read_sql(text(query), conn)

# 2025 ONS enterprise population
population_2025 = enterprise_population[
    enterprise_population["year"] == 2025
][
    ["sic07_3_digit", "industry_description", "enterprise_count"]
].copy()

# Join numerator and denominator
sector_rates_2025 = population_2025.merge(
    insolvency_2025,
    on="sic07_3_digit",
    how="left"
)

sector_rates_2025["insolvencies_2025"] = (
    sector_rates_2025["insolvencies_2025"]
    .fillna(0)
    .astype(int)
)

# Derived analytical rate
sector_rates_2025["insolvencies_per_10k_enterprises"] = (
    sector_rates_2025["insolvencies_2025"]
    / sector_rates_2025["enterprise_count"]
    * 10000
)

print("Industries:", len(sector_rates_2025))
print("Total insolvencies represented:",
      sector_rates_2025["insolvencies_2025"].sum())

print(
    sector_rates_2025
    .sort_values("insolvencies_per_10k_enterprises", ascending=False)
    .head(15)
)

stable_rates_2025 = (
    sector_rates_2025[
        sector_rates_2025["enterprise_count"] >= 500
    ]
    .copy()
)

stable_rates_2025 = stable_rates_2025.sort_values(
    "insolvencies_per_10k_enterprises",
    ascending=False
)

print("Industries retained:", len(stable_rates_2025))

print(
    stable_rates_2025[
        [
            "sic07_3_digit",
            "industry_description",
            "enterprise_count",
            "insolvencies_2025",
            "insolvencies_per_10k_enterprises"
        ]
    ].head(15)
)

import matplotlib.pyplot as plt

plot_df = stable_rates_2025.copy()

fig, ax = plt.subplots(figsize=(12, 7))

ax.scatter(
    plot_df["enterprise_count"],
    plot_df["insolvencies_per_10k_enterprises"],
    alpha=0.6
)

# Label the 10 highest-rate industries
top10 = plot_df.nlargest(
    10,
    "insolvencies_per_10k_enterprises"
)

for _, row in top10.iterrows():
    ax.annotate(
        f'{row["sic07_3_digit"]}',
        (
            row["enterprise_count"],
            row["insolvencies_per_10k_enterprises"]
        ),
        xytext=(5, 5),
        textcoords="offset points",
        fontsize=9
    )

ax.set_title(
    "UK Industry Insolvency Incidence vs Enterprise Population, 2025"
)

ax.set_xlabel(
    "VAT/PAYE Registered Enterprises (ONS, March 2025)"
)

ax.set_ylabel(
    "Insolvencies per 10,000 Enterprises"
)

ax.grid(alpha=0.25)

plt.tight_layout()
plt.show()

from sqlalchemy import text
import pandas as pd

query = """
SELECT
    YEAR(month_registered) AS year,
    sic07_3_digit,
    COUNT(*) AS insolvencies
FROM fact_insolvency
WHERE include_table1b = 1
  AND sic_status = 'VALID'
  AND YEAR(month_registered) BETWEEN 2017 AND 2025
GROUP BY
    YEAR(month_registered),
    sic07_3_digit
ORDER BY
    year,
    sic07_3_digit;
"""

with engine.connect() as conn:
    annual_insolvencies = pd.read_sql(
        text(query),
        conn
    )

# Join ALL 2017–2025 ONS enterprise populations
industry_panel = enterprise_population.merge(
    annual_insolvencies,
    on=["year", "sic07_3_digit"],
    how="left"
)

industry_panel["insolvencies"] = (
    industry_panel["insolvencies"]
    .fillna(0)
    .astype(int)
)

industry_panel["insolvencies_per_10k"] = (
    industry_panel["insolvencies"]
    / industry_panel["enterprise_count"]
    * 10000
)

# Stability flag — keep the raw observations,
# but identify populations large enough for ranking
industry_panel["stable_population"] = (
    industry_panel["enterprise_count"] >= 500
)

print("Panel rows:", len(industry_panel))
print(
    "Years:",
    industry_panel["year"].min(),
    "to",
    industry_panel["year"].max()
)
print(
    "Industries:",
    industry_panel["sic07_3_digit"].nunique()
)
print(
    "Missing enterprise counts:",
    industry_panel["enterprise_count"].isna().sum()
)
print(
    "Missing insolvency counts:",
    industry_panel["insolvencies"].isna().sum()
)

print(industry_panel.head())

national_trend = pd.read_sql(
    """
    SELECT
        month_date,
        insolvencies,
        rolling_12m_insolvencies
    FROM vw_monthly_insolvency_trends
    ORDER BY month_date
    """,
    engine
)

national_trend["month_date"] = pd.to_datetime(
    national_trend["month_date"]
)

national_trend.tail()

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

fig, ax = plt.subplots(figsize=(14, 7.5))

# Monthly observations
ax.plot(
    national_trend["month_date"],
    national_trend["insolvencies"],
    linewidth=1.2,
    alpha=0.30,
    label="Monthly insolvencies"
)

# 12-month rolling monthly average
ax.plot(
    national_trend["month_date"],
    national_trend["rolling_12m_insolvencies"] / 12,
    linewidth=3,
    label="12-month rolling average"
)

# ----- HEADER -----
fig.suptitle(
    "Company Insolvency Pressure in England & Wales",
    x=0.10,
    y=0.97,
    ha="left",
    fontsize=20,
    fontweight="bold"
)

fig.text(
    0.10,
    0.915,
    "Monthly company insolvencies | January 2016 – August 2026",
    ha="left",
    fontsize=11
)

# ----- AXES -----
ax.set_ylabel("Company insolvencies", fontsize=11)
ax.set_xlabel("")

ax.xaxis.set_major_locator(mdates.YearLocator())
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax.grid(
    axis="y",
    alpha=0.15
)

ax.legend(
    frameon=False,
    loc="upper left"
)

# ----- LATEST OBSERVATION -----
latest = national_trend.iloc[-1]

ax.scatter(
    latest["month_date"],
    latest["insolvencies"],
    s=35,
    zorder=5
)

ax.annotate(
    f'Aug 2026\n{int(latest["insolvencies"]):,}',
    xy=(
        latest["month_date"],
        latest["insolvencies"]
    ),
    xytext=(-75, 25),
    textcoords="offset points",
    fontsize=10,
    fontweight="bold",
    arrowprops=dict(
        arrowstyle="-",
        alpha=0.5
    )
)

# ----- SOURCE -----
fig.text(
    0.10,
    0.025,
    "Source: UK Insolvency Service | Non-bulk England & Wales company insolvencies; "
    "Administration-to-CVL transitions and moratoriums excluded.",
    fontsize=8.5
)

# Reserve space for header + footer
plt.subplots_adjust(
    top=0.86,
    bottom=0.12,
    left=0.10,
    right=0.97
)

plt.savefig(
    "01_uk_insolvency_trend.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

# 2025 industries with a sufficiently large enterprise population
v2 = industry_panel[
    (industry_panel["year"] == 2025) &
    (industry_panel["stable_population"])
].copy()

# Select highest insolvency-volume industries
v2 = (
    v2.nlargest(10, "insolvencies")
      .sort_values("insolvencies")
)

v2[
    [
        "sic07_3_digit",
        "industry_description",
        "enterprise_count",
        "insolvencies",
        "insolvencies_per_10k"
    ]
]

# Top 10 sectors by 2025 insolvency volume
rank_df = (
    industry_panel[
        (industry_panel["year"] == 2025) &
        (industry_panel["stable_population"])
    ]
    .nlargest(10, "insolvencies")
    .copy()
)

# Rank within these 10 sectors
rank_df["volume_rank"] = (
    rank_df["insolvencies"]
    .rank(method="min", ascending=False)
    .astype(int)
)

rank_df["incidence_rank"] = (
    rank_df["insolvencies_per_10k"]
    .rank(method="min", ascending=False)
    .astype(int)
)

rank_df["label"] = (
    rank_df["sic07_3_digit"] + "  " +
    rank_df["industry_description"]
)

rank_df = rank_df.sort_values("volume_rank")

print(
    rank_df[
        [
            "sic07_3_digit",
            "industry_description",
            "insolvencies",
            "insolvencies_per_10k",
            "volume_rank",
            "incidence_rank"
        ]
    ]
)

import matplotlib.pyplot as plt

# Keep sectors ordered by volume rank
plot_rank = rank_df.sort_values("volume_rank").reset_index(drop=True)

fig, ax = plt.subplots(figsize=(14, 8.5))

y = range(len(plot_rank))

# Neutral connectors
for i, (_, row) in enumerate(plot_rank.iterrows()):
    ax.plot(
        [row["volume_rank"], row["incidence_rank"]],
        [i, i],
        linewidth=2,
        alpha=0.30,
        color="grey",
        zorder=1
    )

# Volume rank
ax.scatter(
    plot_rank["volume_rank"],
    y,
    s=100,
    label="Rank by insolvency volume",
    zorder=3
)

# Incidence rank
ax.scatter(
    plot_rank["incidence_rank"],
    y,
    s=100,
    label="Rank by population-adjusted incidence",
    zorder=3
)

# Actual values next to the dots
for i, (_, row) in enumerate(plot_rank.iterrows()):

    ax.annotate(
        f'{int(row["insolvencies"]):,}',
        (row["volume_rank"], i),
        xytext=(0, -15),
        textcoords="offset points",
        ha="center",
        fontsize=8
    )

    ax.annotate(
        f'{row["insolvencies_per_10k"]:.0f}/10k',
        (row["incidence_rank"], i),
        xytext=(0, 10),
        textcoords="offset points",
        ha="center",
        fontsize=8
    )

# Industry labels
ax.set_yticks(list(y))

ax.set_yticklabels(
    [
        f'{code}  {name}'
        for code, name in zip(
            plot_rank["sic07_3_digit"],
            plot_rank["industry_description"]
        )
    ],
    fontsize=9
)

ax.invert_yaxis()

# Rank 1 on LEFT
ax.set_xticks(range(1, 11))
ax.set_xlim(0.5, 10.5)

ax.set_xlabel(
    "Rank within the 10 highest-volume industries",
    fontsize=10
)

# Header
fig.suptitle(
    "High Insolvency Volume Does Not Always Mean High Incidence",
    x=0.08,
    y=0.97,
    ha="left",
    fontsize=19,
    fontweight="bold"
)

fig.text(
    0.08,
    0.925,
    "How rankings change after adjusting 2025 insolvencies for the size of each industry",
    fontsize=11
)

# Legend
ax.legend(
    frameon=False,
    loc="lower right"
)

# Styling
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_visible(False)

ax.grid(
    axis="x",
    alpha=0.12
)

# Helpful rank labels
ax.text(
    1,
    -0.75,
    "HIGHER RANK",
    fontsize=8,
    fontweight="bold",
    ha="center"
)

ax.text(
    10,
    -0.75,
    "LOWER RANK",
    fontsize=8,
    fontweight="bold",
    ha="center"
)

# Source
fig.text(
    0.08,
    0.025,
    "Sources: UK Insolvency Service; ONS IDBR. "
    "Incidence = insolvencies per 10,000 VAT/PAYE registered enterprises. "
    "Minimum enterprise population = 500.",
    fontsize=8.5
)

plt.subplots_adjust(
    left=0.39,
    right=0.96,
    top=0.84,
    bottom=0.13
)

plt.savefig(
    "02_volume_vs_incidence_rank_final.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

# Stable-population observations only
trend_base = industry_panel[
    industry_panel["stable_population"]
].copy()

# 2019 baseline
rate_2019 = (
    trend_base[trend_base["year"] == 2019]
    [
        [
            "sic07_3_digit",
            "industry_description",
            "enterprise_count",
            "insolvencies_per_10k"
        ]
    ]
    .rename(columns={
        "enterprise_count": "enterprises_2019",
        "insolvencies_per_10k": "rate_2019"
    })
)

# 2025 endpoint
rate_2025 = (
    trend_base[trend_base["year"] == 2025]
    [
        [
            "sic07_3_digit",
            "enterprise_count",
            "insolvencies_per_10k"
        ]
    ]
    .rename(columns={
        "enterprise_count": "enterprises_2025",
        "insolvencies_per_10k": "rate_2025"
    })
)

change_2019_2025 = rate_2019.merge(
    rate_2025,
    on="sic07_3_digit",
    how="inner"
)

change_2019_2025["absolute_rate_change"] = (
    change_2019_2025["rate_2025"]
    - change_2019_2025["rate_2019"]
)

change_2019_2025["pct_rate_change"] = (
    100 *
    change_2019_2025["absolute_rate_change"]
    / change_2019_2025["rate_2019"].replace(0, pd.NA)
)

print(
    change_2019_2025
    .sort_values(
        "absolute_rate_change",
        ascending=False
    )
    .head(15)
)

# Top 10 industries by absolute increase from 2019 to 2025
top_change_codes = (
    change_2019_2025
    .nlargest(10, "absolute_rate_change")["sic07_3_digit"]
    .tolist()
)

trajectory = (
    industry_panel[
        industry_panel["sic07_3_digit"].isin(top_change_codes)
    ]
    [
        [
            "year",
            "sic07_3_digit",
            "industry_description",
            "enterprise_count",
            "insolvencies",
            "insolvencies_per_10k"
        ]
    ]
    .sort_values(["sic07_3_digit", "year"])
)

# Pivot so we can inspect every annual rate clearly
trajectory_table = trajectory.pivot(
    index=["sic07_3_digit", "industry_description"],
    columns="year",
    values="insolvencies_per_10k"
).round(1)

print(trajectory_table)

import matplotlib.pyplot as plt
import pandas as pd

# Shorter display names for a clean portfolio chart
short_names = {
    "101": "Meat processing",
    "110": "Beverage manufacturing",
    "172": "Paper & paperboard",
    "221": "Rubber products",
    "279": "Electrical equipment",
    "559": "Other accommodation",
    "639": "Other information services",
    "643": "Trusts & funds",
    "781": "Employment agencies",
    "872": "Residential care"
}

plot3 = trajectory.copy()

plot3["short_name"] = (
    plot3["sic07_3_digit"]
    .map(short_names)
)

fig, ax = plt.subplots(figsize=(14, 8))

# Plot each industry's full history
for code in top_change_codes:

    temp = plot3[
        plot3["sic07_3_digit"] == code
    ].sort_values("year")

    ax.plot(
        temp["year"],
        temp["insolvencies_per_10k"],
        marker="o",
        linewidth=2,
        alpha=0.75,
        label=f'{code}  {short_names[code]}'
    )

# Reference line for pre-2020 point
ax.axvline(
    2019,
    linestyle="--",
    linewidth=1,
    alpha=0.35
)

ax.text(
    2019.08,
    375,
    "Pre-2020\nreference year",
    fontsize=9
)

# Header
fig.suptitle(
    "Industry Insolvency Pressure Has Diverged Since 2019",
    x=0.08,
    y=0.97,
    ha="left",
    fontsize=19,
    fontweight="bold"
)

fig.text(
    0.08,
    0.925,
    "Annual insolvencies per 10,000 enterprises | "
    "10 industries with the largest increase between 2019 and 2025",
    fontsize=11
)

ax.set_xlabel("")
ax.set_ylabel(
    "Insolvencies per 10,000 enterprises",
    fontsize=10
)

ax.set_xticks(range(2017, 2026))

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax.grid(
    axis="y",
    alpha=0.15
)

ax.legend(
    frameon=False,
    bbox_to_anchor=(1.02, 1),
    loc="upper left",
    fontsize=9
)

fig.text(
    0.08,
    0.025,
    "Sources: UK Insolvency Service; ONS IDBR. "
    "Population-adjusted incidence based on annual VAT/PAYE enterprise counts. "
    "Industries required ≥500 enterprises in both 2019 and 2025.",
    fontsize=8.5
)

plt.subplots_adjust(
    left=0.08,
    right=0.73,
    top=0.86,
    bottom=0.12
)

plt.savefig(
    "03_industry_pressure_2017_2025.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()

import matplotlib.pyplot as plt
import pandas as pd

# Prepare matrix
heatmap_df = (
    trajectory
    .assign(
        short_name=lambda x:
            x["sic07_3_digit"] + "  " +
            x["sic07_3_digit"].map(short_names)
    )
    .pivot(
        index="short_name",
        columns="year",
        values="insolvencies_per_10k"
    )
)

# Order by 2025 incidence
heatmap_df = heatmap_df.sort_values(
    2025,
    ascending=False
)

fig, ax = plt.subplots(figsize=(13, 7.5))

im = ax.imshow(
    heatmap_df.values,
    aspect="auto",
    cmap="YlOrRd"
)

# Axes
ax.set_xticks(range(len(heatmap_df.columns)))
ax.set_xticklabels(heatmap_df.columns)

ax.set_yticks(range(len(heatmap_df.index)))
ax.set_yticklabels(heatmap_df.index, fontsize=9)

ax.set_xlabel("")
ax.set_ylabel("")

# Put actual rate inside every cell
for i in range(heatmap_df.shape[0]):
    for j in range(heatmap_df.shape[1]):

        value = heatmap_df.iloc[i, j]

        ax.text(
            j,
            i,
            f"{value:.0f}",
            ha="center",
            va="center",
            fontsize=8,
            color="black"
        )

# Colour scale
cbar = fig.colorbar(
    im,
    ax=ax,
    pad=0.02
)

cbar.set_label(
    "Insolvencies per 10,000 enterprises",
    rotation=270,
    labelpad=18
)

# Header
fig.suptitle(
    "Industry Insolvency Pressure Has Diverged Since 2019",
    x=0.08,
    y=0.97,
    ha="left",
    fontsize=19,
    fontweight="bold"
)

fig.text(
    0.08,
    0.92,
    "Population-adjusted insolvency incidence, 2017–2025 | "
    "Industries with the largest increase from 2019 to 2025",
    fontsize=10.5
)

fig.text(
    0.08,
    0.025,
    "Sources: UK Insolvency Service; ONS IDBR. "
    "Values are annual insolvencies per 10,000 VAT/PAYE registered enterprises. "
    "Selection requires ≥500 enterprises in both 2019 and 2025.",
    fontsize=8.3
)

plt.subplots_adjust(
    left=0.28,
    right=0.90,
    top=0.84,
    bottom=0.12
)

plt.savefig(
    "03_industry_pressure_heatmap.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()
