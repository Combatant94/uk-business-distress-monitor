# UK Business Distress Monitor

End-to-end SQL + Python analysis of **220,650 official UK company insolvency records** (Jan 2016 – Aug 2026), validated against published UK Insolvency Service statistics and combined with ONS business-population data to measure where corporate distress is really concentrated — not just where the raw case count is highest.

🖥️ **[Live interactive dashboard](https://claude.ai/artifact/BYxFG26p329gmA2T3XzyCD)** — explore all 272 industries, sort by volume or population-adjusted risk rate, click through to each industry's 2016–2025 trend
📄 **[Read the full report (PDF)](reports/UK_Business_Distress_Monitor_Report.pdf)** — plain-English write-up for a non-technical audience
📝 **[Project walkthrough](WALKTHROUGH.md)** — what was done at each stage and why, including the model sanity-checks
📓 **[Full analysis notebook](notebooks/uk_business_distress_analysis.ipynb)** — every step, from raw data to model
🗄️ **[SQL scripts](sql/)** — schema, dimension build, and the analytical views/queries behind the findings
              
---

## What this project does

1. **Validates before analysing.** Every published monthly total (44/44) and every published 3-digit SIC industry group (272/272) is reconciled exactly against the raw data before any conclusion is drawn.
2. **Separates volume from risk.** Adjusts insolvency counts by the number of enterprises registered in each industry (ONS data), because the industries with the most failures aren't always the highest-risk ones.
3. **Tracks structural change over time.** Compares 2025 incidence against a 2019 pre-pandemic reference year to find industries under sustained, not one-off, pressure.
4. **Tests whether the recent past can forecast the near future.** Benchmarks a simple 12-month historical baseline against Ridge Regression, Random Forest and Gradient Boosting models, using a proper chronological train/validation/test split.

## Key findings

- The rolling 12-month insolvency total eased **3.9%** (23,883 → 22,960) to August 2026 — but remains well above pre-2020 norms.
- **Beverage serving activities** (pubs/bars) had the *highest* insolvency rate of the ten highest-volume industries in 2025, despite ranking only 7th by raw count — while **computer programming**, 4th by volume, dropped to 9th once adjusted for industry size.
- **Residential care** insolvency incidence more than tripled from 2019 to 2025 (108 → 359 per 10,000 enterprises) — the largest sustained increase of any industry in the dataset.
- A simple 12-month historical-average baseline (MAE 3.56) **outperformed every machine-learning model tested** (Ridge, Random Forest, Gradient Boosting: MAE 4.43–4.69) on 3-month-ahead forecasts.
- One sub-industry — buying & selling of own real estate (SIC 681) — accounted for a disproportionate share of forecast error; excluding it improved the baseline's error by over 20%.

## Tech stack

| Layer | Tools |
|---|---|
| Data cleaning & analysis | Python (pandas, NumPy) |
| Database | MySQL (SQLAlchemy + PyMySQL) |
| Modelling | scikit-learn (Ridge, Random Forest, Histogram Gradient Boosting) |
| Visualisation | matplotlib |
| Reporting | HTML/CSS → PDF |

## Data sources

- [UK Insolvency Service — Company Insolvency Statistics](https://www.gov.uk/government/collections/company-insolvency-statistics) (record-level data, August 2026 release)
- [ONS Inter-Departmental Business Register](https://www.ons.gov.uk/) — VAT/PAYE registered enterprise counts by industry

## Repository structure

```
├── dashboard/
│   └── index.html                            # interactive dashboard (self-contained, also deployable via GitHub Pages)
├── notebooks/
│   └── uk_business_distress_analysis.ipynb   # full analysis, start to finish (canonical, runnable record)
├── src/
│   ├── 01_load_validate_clean.py             # stage scripts mirroring the notebook, one per pipeline stage
│   ├── 02_load_to_mysql.py
│   ├── 03_industry_incidence_analysis.py
│   ├── 04_forecasting_models.py
│   └── 05_model_validation_checks.py
├── sql/
│   ├── 01_schema.sql                         # fact/dimension table definitions
│   ├── 02_dimension_build.sql                # calendar dim + zero-filled month×industry panel
│   └── 03_views_and_analysis.sql             # reusable views + key analysis queries
├── reports/
│   ├── UK_Business_Distress_Monitor_Report.pdf
│   └── figures/                              # chart images used in the report
├── requirements.txt
└── README.md
```

The notebook is the canonical, executed record of the analysis. The `src/` scripts mirror each of its stages for readability on GitHub (so the pipeline structure is visible without opening a 1.8 MB notebook) — they're extracted from the same cells, with notebook-only syntax (`%pip install`, `display()`) converted to plain Python. Some exploratory investigation lines (shape checks, preview prints) are kept deliberately, as a true reflection of how the data was actually explored.

## Running it yourself

```bash
pip install -r requirements.txt
```

Run `sql/01_schema.sql` then `sql/02_dimension_build.sql` against a local MySQL instance to build the database, then open the notebook. The notebook prompts for your MySQL password interactively (`getpass`) rather than storing it — no credentials are stored anywhere in this repo. Raw source data (UK Insolvency Service and ONS spreadsheets) isn't included in the repo for size reasons; see the Data sources section above.

## Methodology notes

- Bulk insolvency cases and "Administration to CVL" records are excluded from headline counts, following UK Insolvency Service guidance, to avoid double-counting.
- Because ONS enterprise-population figures are UK-wide while the insolvency numerator covers England & Wales, population-adjusted incidence figures are a comparative proxy, not an exact rate.
- Industries are only ranked on population-adjusted incidence where they had at least 500 registered enterprises, to avoid small-sample distortion.
- Forecast models are evaluated out-of-time on a chronological split, so test-period results reflect genuinely unseen future months.

---

**Author:** Mohd Nafees — [LinkedIn](https://www.linkedin.com/in/nafees-mohd-59863524b/) · [GitHub](https://github.com/Combatant94)
