# Project Walkthrough: UK Business Distress Monitor

This document explains what was actually done in this project, in the order it was done, and — more importantly — *why* each step was necessary. The notebook and SQL scripts show the "what"; this is the "why," written the way I'd talk someone through it rather than as a list of bullet points.

## The question behind the project

The UK Insolvency Service publishes monthly company insolvency statistics, and the ONS separately publishes how many businesses exist in each industry. Neither dataset on its own answers the question a business analyst actually cares about: **where is financial distress concentrated, is it getting better or worse, and can the recent past tell us anything reliable about the next few months?**

That's a validation problem, a data-modelling problem, and a forecasting problem stacked on top of each other. I treated them as three separate stages, in that order, because getting the order wrong is how projects like this quietly go wrong — it's easy to build an impressive chart on top of a subtly incorrect number.

## Stage 1 — Validate before doing anything else

The raw dataset is 220,650 individual insolvency records. Before calculating a single trend or rate, every published monthly total (44 months) and every published 3-digit industry total (272 SIC groups) was reconciled against the raw data, record for record, until both matched exactly.

This sounds like busywork, but it caught real issues early: the published tables exclude "bulk" insolvencies and "Administration to CVL" records (a company that goes through administration and then converts to creditors' voluntary liquidation would otherwise be counted twice for the same insolvency event — the README that ships with the official data explicitly warns about this). Getting the inclusion/exclusion logic right *before* building anything downstream meant every later number — the monthly trend, the industry rankings, the forecasting target — was built on a number that had already been proven correct, not assumed correct.

## Stage 2 — Structuring the data properly in SQL

Once validated, the data was loaded into MySQL as a proper fact table (`fact_insolvency`), with SIC industry codes attached at five levels of granularity (1-digit down to 5-digit) and boolean flags (`is_bulk_flag`, `include_table1b`, `sic_status`) computed once in Python and stored, rather than recalculated inline in every query. Indexes were added on the columns the analysis actually filters and groups by (`month_registered`, `sic07_3_digit`, `case_type`, `include_table1b`).

This is a fairly standard analytical schema, but one design decision mattered more than it looks: a separate **`fact_industry_month`** table was built by cross-joining every month against every industry, rather than just grouping the raw data by month and industry. The difference matters because of how window functions work. If an industry has zero insolvencies in a given month, a `GROUP BY` on the raw data simply produces no row for that month — and `LAG(insolvencies, 12)` over a partition with missing months doesn't mean "12 calendar months ago" anymore, it means "12 *rows* ago," which could be 13, 15, or 20 calendar months ago depending on how many months that industry happened to have zero cases. Cross-joining the calendar against every industry and `LEFT JOIN`-ing the real counts (with `COALESCE(..., 0)`) guarantees every industry has exactly one row per month, including zeros. Only after that does `LAG(12)` genuinely mean what it says.

## Stage 3 — Volume vs. rate: the central analytical idea

Raw insolvency counts answer "how many companies failed" but not "how risky is this industry to be in." An industry with 2,000 insolvencies a year could be enormous (so 2,000 is unremarkable) or it could be a relatively small industry in real trouble. The only way to tell them apart is to divide by how many businesses exist in that industry — which meant bringing in the ONS Inter-Departmental Business Register (VAT/PAYE registered enterprises) as a denominator, joined by 3-digit SIC code.

This is the finding that does the most work in the whole project: **restaurants and mobile food service had the highest raw insolvency count of any industry (2,082 in the year to August 2026) — but beverage serving activities (pubs and bars), a much smaller industry by raw count, had a higher insolvency *rate* once adjusted for size.** A monitoring system that only ranked industries by count would miss that pubs are, proportionally, in worse shape than restaurants. The same adjustment showed the reverse effect too: industries like management consultancy generate a respectable-looking raw count simply because the industry is huge, not because it's under particular stress.

One honest caveat that's worth stating plainly rather than glossing over: the insolvency numerator in this dataset covers England & Wales, but the ONS enterprise denominator is UK-wide. The incidence figures are therefore a *comparative* proxy — useful for ranking industries against each other — not a precise legal insolvency rate.

## Stage 4 — Trend, not just a snapshot

A single year's rate can be a blip. To find industries under *sustained* pressure rather than a one-off bad patch, the same rate calculation was repeated for every year from 2017 to 2025, using 2019 as a deliberate pre-pandemic reference point, and industries were ranked by how much their rate had moved since then (with a minimum enterprise-population threshold applied so a tiny industry going from 2 to 6 failures doesn't produce a dramatic-looking but meaningless percentage swing).

Residential care stood out clearly here — its insolvency rate roughly tripled between 2019 and 2025 and, unlike some other industries in the top 10, kept climbing right through to 2025 rather than spiking and easing back. That distinction — still rising vs. already past its peak — is only visible with the full year-by-year series, which is why the project didn't stop at a single before/after comparison.

## Stage 5 — Can any of this forecast the next 3 months?

This is where the project tests itself honestly rather than just describing the past. The task: predict each industry's insolvency count for the next 3 months, using a proper chronological train/validation/test split so the test period is genuinely unseen future data, not a random shuffle that leaks future information into training.

The benchmark was deliberately unglamorous: assume the next 3 months look like the trailing 12-month average. Three more sophisticated models — Ridge Regression, Random Forest, and Poisson Gradient Boosting — were built and evaluated against it, along with a variant that also incorporated the ONS population data as a feature.

**None of them beat the simple baseline.** The 12-month rolling average scored MAE 3.56 / RMSE 8.62 on the test set; the machine learning models all came in worse (MAE 4.43–4.69), and a population-aware Ridge variant scored worse still (MAE 4.64 against its own like-for-like benchmark of 3.65). This isn't a failure of the project — it's a genuinely useful result. Industry-level insolvency counts are fairly stable month to month, so a trailing average already captures most of the predictable signal, and added model complexity mostly fits noise rather than pattern. That's a better and more honest answer than forcing a more "sophisticated" model to win.

## Stage 6 — Why the model gets some industries badly wrong

Aggregate error metrics can hide a lot. Digging into *where* the baseline's error was concentrated turned up SIC 681 (buying and selling of own real estate) as a clear outlier — a short, sharp cluster of administration filings in a single quarter that no amount of historical pattern-matching could have anticipated, because it wasn't a trend, it was an event. Excluding that one sub-industry from the test set improved the baseline's own MAE by over 20%. That's a useful, specific limitation to be able to state rather than a vague "forecasts aren't perfect": **the model is a solid surveillance tool for gradual, structural change, and a poor tool for sudden, sector-specific shocks** — and now there's a concrete example of exactly that kind of shock to point to.

## Stage 7 — Checking the headline number for being *too* good

The pooled R² across all industries and months came out at 0.973, which is the kind of number that should make you suspicious of yourself before it makes you proud. A high pooled R² across many industries of very different sizes can be mostly explained by the model correctly telling large industries apart from small ones, rather than by genuinely predicting month-to-month movement within each industry.

So that was tested directly: a training-period industry-mean benchmark (predict each industry's own historical average, nothing more) *on its own* already achieves R² of 0.845 — confirming that a large share of the pooled R² is coming from between-industry scale differences, not from forecasting skill. What the rolling 12-month model adds on top of that is real, but more modest and better measured in MAE and RMSE than in R²: MAE improved from 7.43 (mean-only benchmark) to 3.56, and RMSE from 20.49 to 8.62. Breaking the error down industry-by-industry rather than pooling it also showed the median industry has an MAE of just 1.73 — the pooled average is being pulled up by a small number of high-volume or shock-affected industries, SIC 681 chief among them. The honest conclusion is not "97% accurate forecasting" — it's that the model does a solid, well-quantified job on typical industries and a poor job on rare, shock-driven ones, and now there's a clear number for each.

## What this adds up to

Put together, the project answers the three-part question it started with:

1. **Where is distress concentrated?** Not always where the raw counts suggest — beverage serving and a handful of smaller industries carry more relative risk than their headline numbers imply.
2. **Is it getting better or worse?** Nationally, easing (23,883 → 22,960 on a rolling 12-month basis). Industry by industry, very unevenly — residential care is still climbing, while construction-related industries are moving in the *opposite* direction to the national trend, worth watching precisely because they're the exception.
3. **Can the recent past forecast the near future?** Yes, reasonably well, for stable industries, using nothing more complex than a trailing average — and reliably badly for industries hit by a sudden, sector-specific event, which is a real and now-quantified limitation rather than an unstated one.

The recurring theme across every stage is the same: validate before trusting a number, and check a good-looking result for *why* it looks good before repeating it as a headline. That's the habit this project was really built to demonstrate.
