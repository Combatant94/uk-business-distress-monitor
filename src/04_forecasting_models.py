"""
Stage 4: Forecast each industry's insolvencies 3 months ahead.

Benchmarks a simple 12-month rolling-average baseline against Ridge
Regression, Random Forest and Poisson Gradient Boosting, using a
chronological train/validation/test split. See WALKTHROUGH.md, "Stage 5"
for why the simple baseline won and what that implies.
"""

import pandas as pd

industry_trends = pd.read_sql(
    """
    SELECT *
    FROM vw_industry_trends
    ORDER BY sic07_3_digit, month_date
    """,
    con=engine
)

print("Rows:", len(industry_trends))
print("Industries:", industry_trends["sic07_3_digit"].nunique())
print(
    "Period:",
    industry_trends["month_date"].min(),
    "to",
    industry_trends["month_date"].max()
)

industry_trends.head()

# Make sure join keys have matching types
industry_trends["month_date"] = pd.to_datetime(
    industry_trends["month_date"]
)

industry_trends["year"] = (
    industry_trends["month_date"].dt.year
)

industry_trends["sic07_3_digit"] = (
    industry_trends["sic07_3_digit"]
    .astype(str)
    .str.zfill(3)
)

enterprise_population["sic07_3_digit"] = (
    enterprise_population["sic07_3_digit"]
    .astype(str)
    .str.zfill(3)
)

# Keep only denominator fields needed for the join
ons_denominator = enterprise_population[
    [
        "year",
        "sic07_3_digit",
        "enterprise_count"
    ]
].copy()

# Join ONS annual enterprise population onto monthly SQL panel
model_panel = industry_trends.merge(
    ons_denominator,
    on=["year", "sic07_3_digit"],
    how="left",
    validate="many_to_one"
)

# Monthly incidence using annual enterprise population denominator
model_panel["monthly_insolvencies_per_10k"] = (
    model_panel["insolvencies"]
    / model_panel["enterprise_count"]
    * 10000
)

print("Rows:", len(model_panel))
print("Industries:", model_panel["sic07_3_digit"].nunique())

print("\nEnterprise denominator available by year:")
print(
    model_panel.groupby("year")["enterprise_count"]
    .apply(lambda x: x.notna().sum())
)

print(
    model_panel[
        [
            "month_date",
            "sic07_3_digit",
            "industry_description",
            "insolvencies",
            "rolling_12m_insolvencies",
            "rolling_12m_change_pct",
            "enterprise_count",
            "monthly_insolvencies_per_10k"
        ]
    ].tail()
)

# sort before creating future/lagged features
model_panel = (
    model_panel
    .sort_values(
        ["sic07_3_digit", "month_date"]
    )
    .reset_index(drop=True)
)

g = model_panel.groupby(
    "sic07_3_digit",
    group_keys=False
)

# Future 1, 2 and 3 month insolvencies
model_panel["future_m1"] = g["insolvencies"].shift(-1)
model_panel["future_m2"] = g["insolvencies"].shift(-2)
model_panel["future_m3"] = g["insolvencies"].shift(-3)

# Target: total insolvencies over NEXT three months
model_panel["future_3m_insolvencies"] = (
    model_panel["future_m1"]
    + model_panel["future_m2"]
    + model_panel["future_m3"]
)

# Flag rows where the complete future horizon exists
model_panel["target_available"] = (
    model_panel[
        ["future_m1", "future_m2", "future_m3"]
    ]
    .notna()
    .all(axis=1)
)

print(
    "Rows with complete 3-month future target:",
    model_panel["target_available"].sum()
)

print(
    "Rows without complete future target:",
    (~model_panel["target_available"]).sum()
)

print(
    model_panel[
        [
            "month_date",
            "sic07_3_digit",
            "insolvencies",
            "future_m1",
            "future_m2",
            "future_m3",
            "future_3m_insolvencies",
            "target_available"
        ]
    ].tail(8)
)

# Make sure ordering is still correct
model_panel = (
    model_panel
    .sort_values(["sic07_3_digit", "month_date"])
    .reset_index(drop=True)
)

g = model_panel.groupby("sic07_3_digit")

# ---------------------------
# Recent insolvency history
# ---------------------------

model_panel["lag_1m"] = g["insolvencies"].shift(1)
model_panel["lag_3m"] = g["insolvencies"].shift(3)
model_panel["lag_6m"] = g["insolvencies"].shift(6)
model_panel["lag_12m"] = g["insolvencies"].shift(12)


# ---------------------------
# Historical rolling features
# Exclude current month to make
# them strictly backward-looking
# ---------------------------

model_panel["previous_3m_total"] = (
    g["insolvencies"]
    .transform(
        lambda s: s.shift(1).rolling(3).sum()
    )
)

model_panel["previous_6m_total"] = (
    g["insolvencies"]
    .transform(
        lambda s: s.shift(1).rolling(6).sum()
    )
)

model_panel["previous_12m_total"] = (
    g["insolvencies"]
    .transform(
        lambda s: s.shift(1).rolling(12).sum()
    )
)


# ---------------------------
# Short-term momentum
# previous 3 months versus
# preceding 3 months
# ---------------------------

model_panel["preceding_3m_total"] = (
    g["insolvencies"]
    .transform(
        lambda s: s.shift(4).rolling(3).sum()
    )
)

model_panel["momentum_3m_pct"] = (
    100
    * (
        model_panel["previous_3m_total"]
        - model_panel["preceding_3m_total"]
    )
    / model_panel["preceding_3m_total"].replace(0, pd.NA)
)


# ---------------------------
# Population-adjusted history
# ---------------------------

model_panel["previous_12m_per_10k"] = (
    model_panel["previous_12m_total"]
    / model_panel["enterprise_count"]
    * 10000
)


# Calendar features
model_panel["month_number"] = model_panel["month_date"].dt.month
model_panel["quarter"] = model_panel["month_date"].dt.quarter


# QA
feature_cols = [
    "lag_1m",
    "lag_3m",
    "lag_6m",
    "lag_12m",
    "previous_3m_total",
    "previous_6m_total",
    "previous_12m_total",
    "preceding_3m_total",
    "momentum_3m_pct",
    "previous_12m_per_10k"
]

print("Feature missing values:")
print(model_panel[feature_cols].isna().sum())

print(
    model_panel[
        [
            "month_date",
            "sic07_3_digit",
            "insolvencies",
            "lag_1m",
            "previous_3m_total",
            "preceding_3m_total",
            "momentum_3m_pct",
            "previous_12m_total",
            "previous_12m_per_10k",
            "future_3m_insolvencies"
        ]
    ].tail(12)
)

# Features for our first baseline model
feature_cols = [
    "lag_1m",
    "lag_3m",
    "lag_6m",
    "lag_12m",
    "previous_3m_total",
    "previous_6m_total",
    "previous_12m_total",
    "preceding_3m_total",
    "month_number",
    "quarter"
]

target_col = "future_3m_insolvencies"

# Keep rows where:
# 1. future target is actually observed
# 2. historical features are available
model_data = model_panel[
    model_panel["target_available"]
].copy()

model_data = model_data.dropna(
    subset=feature_cols + [target_col]
)

# Chronological split
train = model_data[
    model_data["month_date"] < "2023-01-01"
].copy()

validation = model_data[
    (model_data["month_date"] >= "2023-01-01") &
    (model_data["month_date"] < "2025-01-01")
].copy()

test = model_data[
    model_data["month_date"] >= "2025-01-01"
].copy()

print("TRAIN")
print(
    len(train),
    train["month_date"].min(),
    "to",
    train["month_date"].max()
)

print("\nVALIDATION")
print(
    len(validation),
    validation["month_date"].min(),
    "to",
    validation["month_date"].max()
)

print("\nTEST")
print(
    len(test),
    test["month_date"].min(),
    "to",
    test["month_date"].max()
)

print("\nIndustries:")
print(
    "Train:", train["sic07_3_digit"].nunique(),
    "| Validation:", validation["sic07_3_digit"].nunique(),
    "| Test:", test["sic07_3_digit"].nunique()
)

print("\nTarget summary:")
print(
    model_data[target_col].describe()
)

import numpy as np
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

def evaluate_predictions(y_true, y_pred, name):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)

    print(name)
    print(f"MAE:  {mae:.3f}")
    print(f"RMSE: {rmse:.3f}")
    print(f"R²:   {r2:.3f}")

    return {
        "model": name,
        "MAE": mae,
        "RMSE": rmse,
        "R2": r2
    }


# -----------------------------------
# Naive persistence baseline
# Future 3 months = previous 3 months
# -----------------------------------

validation_baseline_pred = validation["previous_3m_total"]
test_baseline_pred = test["previous_3m_total"]

baseline_validation = evaluate_predictions(
    validation[target_col],
    validation_baseline_pred,
    "Naive baseline — Validation"
)

print()

baseline_test = evaluate_predictions(
    test[target_col],
    test_baseline_pred,
    "Naive baseline — Test"
)

validation_12m_pred = (
    validation["previous_12m_total"] / 4
)

test_12m_pred = (
    test["previous_12m_total"] / 4
)

baseline12_validation = evaluate_predictions(
    validation[target_col],
    validation_12m_pred,
    "12-month average baseline — Validation"
)

print()

baseline12_test = evaluate_predictions(
    test[target_col],
    test_12m_pred,
    "12-month average baseline — Test"
)

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

X_train = train[feature_cols]
y_train = train[target_col]

X_val = validation[feature_cols]
y_val = validation[target_col]

X_test = test[feature_cols]
y_test = test[target_col]


ridge_model = Pipeline([
    ("scaler", StandardScaler()),
    ("ridge", Ridge(alpha=1.0))
])

ridge_model.fit(X_train, y_train)


# Predictions
ridge_val_pred = ridge_model.predict(X_val)
ridge_test_pred = ridge_model.predict(X_test)

# Insolvency counts cannot be negative
ridge_val_pred = np.clip(ridge_val_pred, 0, None)
ridge_test_pred = np.clip(ridge_test_pred, 0, None)


ridge_validation = evaluate_predictions(
    y_val,
    ridge_val_pred,
    "Ridge regression — Validation"
)

print()

ridge_test = evaluate_predictions(
    y_test,
    ridge_test_pred,
    "Ridge regression — Test"
)

from sklearn.ensemble import HistGradientBoostingRegressor

hgb_model = HistGradientBoostingRegressor(
    loss="poisson",
    learning_rate=0.05,
    max_iter=300,
    max_leaf_nodes=15,
    min_samples_leaf=30,
    l2_regularization=1.0,
    random_state=42
)

hgb_model.fit(X_train, y_train)

# Validation predictions
hgb_val_pred = hgb_model.predict(X_val)
hgb_val_pred = np.clip(hgb_val_pred, 0, None)

hgb_validation = evaluate_predictions(
    y_val,
    hgb_val_pred,
    "Poisson Gradient Boosting — Validation"
)

print()

# Test predictions — evaluation only
hgb_test_pred = hgb_model.predict(X_test)
hgb_test_pred = np.clip(hgb_test_pred, 0, None)

hgb_test = evaluate_predictions(
    y_test,
    hgb_test_pred,
    "Poisson Gradient Boosting — Test"
)

baseline_errors = test[
    [
        "month_date",
        "sic07_3_digit",
        "industry_description",
        "previous_3m_total",
        "previous_12m_total",
        "future_3m_insolvencies"
    ]
].copy()

baseline_errors["prediction"] = (
    baseline_errors["previous_12m_total"] / 4
)

baseline_errors["error"] = (
    baseline_errors["future_3m_insolvencies"]
    - baseline_errors["prediction"]
)

baseline_errors["absolute_error"] = (
    baseline_errors["error"].abs()
)

print(
    baseline_errors
    .sort_values("absolute_error", ascending=False)
    .head(20)
)

# ---------------------------------------
# Sensitivity analysis:
# How much does SIC 681 affect test error?
# ---------------------------------------

test_diagnostic = test.copy()

test_diagnostic["baseline_prediction"] = (
    test_diagnostic["previous_12m_total"] / 4
)

test_without_681 = test_diagnostic[
    test_diagnostic["sic07_3_digit"] != "681"
].copy()

print("FULL TEST SET")
evaluate_predictions(
    test_diagnostic[target_col],
    test_diagnostic["baseline_prediction"],
    "12-month baseline — Full test"
)

print("\nTEST EXCLUDING SIC 681")
evaluate_predictions(
    test_without_681[target_col],
    test_without_681["baseline_prediction"],
    "12-month baseline — Excluding SIC 681"
)

print("\nSIC 681 ONLY")
evaluate_predictions(
    test_diagnostic.loc[
        test_diagnostic["sic07_3_digit"] == "681",
        target_col
    ],
    test_diagnostic.loc[
        test_diagnostic["sic07_3_digit"] == "681",
        "baseline_prediction"
    ],
    "12-month baseline — SIC 681 only"
)

# Historical concentration feature
# Uses ONLY months before the prediction month

def previous_6m_peak_share(series):
    shifted = series.shift(1)

    rolling_sum = shifted.rolling(6).sum()
    rolling_max = shifted.rolling(6).max()

    return rolling_max / rolling_sum.replace(0, np.nan)


model_panel["previous_6m_peak_share"] = (
    model_panel
    .groupby("sic07_3_digit")["insolvencies"]
    .transform(previous_6m_peak_share)
)

# Also measure recent level relative to longer history
model_panel["recent_vs_12m_ratio"] = (
    (model_panel["previous_3m_total"] / 3)
    /
    (model_panel["previous_12m_total"] / 12)
).replace([np.inf, -np.inf], np.nan)


# Inspect SIC 681 around the unusual period
print(
    model_panel.loc[
        (model_panel["sic07_3_digit"] == "681") &
        (model_panel["month_date"] >= "2025-09-01"),
        [
            "month_date",
            "insolvencies",
            "previous_3m_total",
            "previous_12m_total",
            "previous_6m_peak_share",
            "recent_vs_12m_ratio",
            "future_3m_insolvencies"
        ]
    ]
)

enhanced_features = [
    "lag_1m",
    "lag_3m",
    "lag_6m",
    "lag_12m",
    "previous_3m_total",
    "previous_6m_total",
    "previous_12m_total",
    "preceding_3m_total",
    "previous_6m_peak_share",
    "recent_vs_12m_ratio",
    "month_number",
    "quarter"
]

enhanced_data = model_panel[
    model_panel["target_available"]
].copy()

enhanced_data = enhanced_data.replace(
    [np.inf, -np.inf],
    np.nan
)

enhanced_data = enhanced_data.dropna(
    subset=enhanced_features + [target_col]
)

enhanced_train = enhanced_data[
    enhanced_data["month_date"] < "2023-01-01"
].copy()

enhanced_validation = enhanced_data[
    (enhanced_data["month_date"] >= "2023-01-01") &
    (enhanced_data["month_date"] < "2025-01-01")
].copy()

enhanced_test = enhanced_data[
    enhanced_data["month_date"] >= "2025-01-01"
].copy()

print("Enhanced modelling rows:", len(enhanced_data))

print(
    "Train:", len(enhanced_train),
    "| Validation:", len(enhanced_validation),
    "| Test:", len(enhanced_test)
)

print(
    "Period:",
    enhanced_data["month_date"].min(),
    "to",
    enhanced_data["month_date"].max()
)

# Robust short-term acceleration feature
# Does not divide by zero

model_panel["recent_vs_12m_diff"] = (
    model_panel["previous_3m_total"] / 3
    - model_panel["previous_12m_total"] / 12
)

enhanced_features = [
    "lag_1m",
    "lag_3m",
    "lag_6m",
    "lag_12m",
    "previous_3m_total",
    "previous_6m_total",
    "previous_12m_total",
    "preceding_3m_total",
    "previous_6m_peak_share",
    "recent_vs_12m_diff",
    "month_number",
    "quarter"
]

enhanced_data = model_panel[
    model_panel["target_available"]
].copy()

enhanced_data = enhanced_data.replace(
    [np.inf, -np.inf],
    np.nan
)

enhanced_data = enhanced_data.dropna(
    subset=enhanced_features + [target_col]
)

enhanced_train = enhanced_data[
    enhanced_data["month_date"] < "2023-01-01"
].copy()

enhanced_validation = enhanced_data[
    (enhanced_data["month_date"] >= "2023-01-01") &
    (enhanced_data["month_date"] < "2025-01-01")
].copy()

enhanced_test = enhanced_data[
    enhanced_data["month_date"] >= "2025-01-01"
].copy()

print("Enhanced modelling rows:", len(enhanced_data))
print(
    "Train:", len(enhanced_train),
    "| Validation:", len(enhanced_validation),
    "| Test:", len(enhanced_test)
)

print("\nMissing values:")
print(
    model_panel[
        ["previous_6m_peak_share", "recent_vs_12m_diff"]
    ].isna().sum()
)

# Identify whether a COMPLETE previous 6-month history exists
model_panel["previous_6m_count"] = (
    model_panel
    .groupby("sic07_3_digit")["insolvencies"]
    .transform(
        lambda s: s.shift(1).rolling(6).count()
    )
)

# If we have all 6 historical months and their total is zero,
# concentration is logically zero rather than missing.
zero_activity_mask = (
    (model_panel["previous_6m_count"] == 6) &
    (model_panel["previous_6m_total"] == 0)
)

model_panel.loc[
    zero_activity_mask,
    "previous_6m_peak_share"
] = 0.0


print("Remaining missing values:")
print(
    model_panel[
        [
            "previous_6m_peak_share",
            "recent_vs_12m_diff"
        ]
    ].isna().sum()
)

enhanced_data = model_panel[
    model_panel["target_available"]
].copy()

enhanced_data = enhanced_data.dropna(
    subset=enhanced_features + [target_col]
)

enhanced_train = enhanced_data[
    enhanced_data["month_date"] < "2023-01-01"
].copy()

enhanced_validation = enhanced_data[
    (enhanced_data["month_date"] >= "2023-01-01") &
    (enhanced_data["month_date"] < "2025-01-01")
].copy()

enhanced_test = enhanced_data[
    enhanced_data["month_date"] >= "2025-01-01"
].copy()

print("Enhanced modelling rows:", len(enhanced_data))

print(
    "Train:", len(enhanced_train),
    "| Validation:", len(enhanced_validation),
    "| Test:", len(enhanced_test)
)

print(
    "Industries:",
    enhanced_train["sic07_3_digit"].nunique(),
    enhanced_validation["sic07_3_digit"].nunique(),
    enhanced_test["sic07_3_digit"].nunique()
)

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

# Enhanced feature matrices
X_train_enh = enhanced_train[enhanced_features]
y_train_enh = enhanced_train[target_col]

X_val_enh = enhanced_validation[enhanced_features]
y_val_enh = enhanced_validation[target_col]

X_test_enh = enhanced_test[enhanced_features]
y_test_enh = enhanced_test[target_col]


enhanced_ridge = Pipeline([
    ("scaler", StandardScaler()),
    ("ridge", Ridge(alpha=1.0))
])

enhanced_ridge.fit(X_train_enh, y_train_enh)


# Predictions
enh_ridge_val_pred = enhanced_ridge.predict(X_val_enh)
enh_ridge_test_pred = enhanced_ridge.predict(X_test_enh)

# Counts cannot be negative
enh_ridge_val_pred = np.clip(enh_ridge_val_pred, 0, None)
enh_ridge_test_pred = np.clip(enh_ridge_test_pred, 0, None)


print("ENHANCED RIDGE")
print()

enh_ridge_validation = evaluate_predictions(
    y_val_enh,
    enh_ridge_val_pred,
    "Enhanced Ridge — Validation"
)

print()

enh_ridge_test = evaluate_predictions(
    y_test_enh,
    enh_ridge_test_pred,
    "Enhanced Ridge — Test"
)

from sklearn.ensemble import RandomForestRegressor

rf_model = RandomForestRegressor(
    n_estimators=300,
    max_depth=12,
    min_samples_leaf=5,
    max_features=0.8,
    n_jobs=-1,
    random_state=42
)

rf_model.fit(X_train, y_train)

rf_val_pred = rf_model.predict(X_val)
rf_test_pred = rf_model.predict(X_test)

rf_validation = evaluate_predictions(
    y_val,
    rf_val_pred,
    "Random Forest — Validation"
)

print()

rf_test = evaluate_predictions(
    y_test,
    rf_test_pred,
    "Random Forest — Test"
)

# Create previous-year ONS enterprise population
ons_lagged = enterprise_population[
    ["year", "sic07_3_digit", "enterprise_count"]
].copy()

ons_lagged["year"] = ons_lagged["year"] + 1

ons_lagged = ons_lagged.rename(
    columns={"enterprise_count": "previous_year_enterprises"}
)

# Remove the current-year enterprise count from the modelling panel
# and merge the lagged denominator
model_panel = model_panel.drop(
    columns=["previous_year_enterprises"],
    errors="ignore"
)

model_panel = model_panel.merge(
    ons_lagged,
    on=["year", "sic07_3_digit"],
    how="left",
    validate="many_to_one"
)

print(
    model_panel.groupby("year")[
        "previous_year_enterprises"
    ].count()
)

model_panel["lagged_12m_incidence_per_10k"] = (
    model_panel["previous_12m_total"]
    / model_panel["previous_year_enterprises"]
    * 10000
)

population_features = [
    "lag_1m",
    "lag_3m",
    "lag_6m",
    "lag_12m",
    "previous_3m_total",
    "previous_6m_total",
    "previous_12m_total",
    "preceding_3m_total",
    "month_number",
    "quarter",
    "previous_year_enterprises",
    "lagged_12m_incidence_per_10k"
]

population_data = model_panel[
    model_panel["target_available"]
].copy()

population_data = population_data.dropna(
    subset=population_features + [target_col]
)

population_train = population_data[
    population_data["month_date"] < "2023-01-01"
].copy()

population_validation = population_data[
    (population_data["month_date"] >= "2023-01-01") &
    (population_data["month_date"] < "2025-01-01")
].copy()

population_test = population_data[
    population_data["month_date"] >= "2025-01-01"
].copy()

print("Population-aware rows:", len(population_data))

print(
    "Train:", len(population_train),
    "| Validation:", len(population_validation),
    "| Test:", len(population_test)
)

print(
    "Industries:",
    population_train["sic07_3_digit"].nunique(),
    population_validation["sic07_3_digit"].nunique(),
    population_test["sic07_3_digit"].nunique()
)

print(
    "\nPeriod:",
    population_data["month_date"].min(),
    "to",
    population_data["month_date"].max()
)

# Matched-sample baseline for the population-aware model
# Future 3 months ≈ previous 12 months / 4

pop_val_baseline_pred = (
    population_validation["previous_12m_total"] / 4
)

pop_test_baseline_pred = (
    population_test["previous_12m_total"] / 4
)

print("POPULATION-MATCHED BASELINE")
print()

pop_baseline_validation = evaluate_predictions(
    population_validation[target_col],
    pop_val_baseline_pred,
    "12-month baseline — Population validation sample"
)

print()

pop_baseline_test = evaluate_predictions(
    population_test[target_col],
    pop_test_baseline_pred,
    "12-month baseline — Population test sample"
)

# Check every population feature for NaN / +inf / -inf

for col in population_features:
    values = population_data[col]

    print(
        col,
        "| NaN:", values.isna().sum(),
        "| +inf:", np.isposinf(values).sum(),
        "| -inf:", np.isneginf(values).sum()
    )

# Show the actual problematic observations

problem_mask = np.isinf(
    population_data[population_features]
).any(axis=1)

print(
    population_data.loc[
        problem_mask,
        [
            "month_date",
            "sic07_3_digit",
            "industry_description",
            "previous_year_enterprises",
            "previous_12m_total",
            "lagged_12m_incidence_per_10k"
        ]
    ].head(30)
)

print("Rows containing infinity:", problem_mask.sum())

# Zero enterprise population cannot be used as an incidence denominator
model_panel["lagged_12m_incidence_per_10k"] = np.where(
    model_panel["previous_year_enterprises"] > 0,
    (
        model_panel["previous_12m_total"]
        / model_panel["previous_year_enterprises"]
        * 10000
    ),
    np.nan
)

population_data = model_panel[
    model_panel["target_available"]
].copy()

# Defensive check: convert any remaining infinities to missing
population_data[population_features] = (
    population_data[population_features]
    .replace([np.inf, -np.inf], np.nan)
)

population_data = population_data.dropna(
    subset=population_features + [target_col]
)

population_train = population_data[
    population_data["month_date"] < "2023-01-01"
].copy()

population_validation = population_data[
    (population_data["month_date"] >= "2023-01-01") &
    (population_data["month_date"] < "2025-01-01")
].copy()

population_test = population_data[
    population_data["month_date"] >= "2025-01-01"
].copy()


print("Population-aware rows:", len(population_data))

print(
    "Train:", len(population_train),
    "| Validation:", len(population_validation),
    "| Test:", len(population_test)
)

print(
    "Industries:",
    population_train["sic07_3_digit"].nunique(),
    population_validation["sic07_3_digit"].nunique(),
    population_test["sic07_3_digit"].nunique()
)

print(
    "Remaining infinities:",
    np.isinf(
        population_data[population_features].to_numpy()
    ).sum()
)

# Final matched-sample baseline
# for the cleaned population-aware dataset

final_pop_val_baseline_pred = (
    population_validation["previous_12m_total"] / 4
)

final_pop_test_baseline_pred = (
    population_test["previous_12m_total"] / 4
)

print("FINAL POPULATION-MATCHED BASELINE")
print()

final_pop_baseline_validation = evaluate_predictions(
    population_validation[target_col],
    final_pop_val_baseline_pred,
    "12-month baseline — Final population validation"
)

print()

final_pop_baseline_test = evaluate_predictions(
    population_test[target_col],
    final_pop_test_baseline_pred,
    "12-month baseline — Final population test"
)

from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

# Final cleaned population-aware datasets
X_train_pop = population_train[population_features]
y_train_pop = population_train[target_col]

X_val_pop = population_validation[population_features]
y_val_pop = population_validation[target_col]

X_test_pop = population_test[population_features]
y_test_pop = population_test[target_col]


population_ridge = Pipeline([
    ("scaler", StandardScaler()),
    ("ridge", Ridge(alpha=1.0))
])

population_ridge.fit(X_train_pop, y_train_pop)


# Predictions
pop_ridge_val_pred = population_ridge.predict(X_val_pop)
pop_ridge_test_pred = population_ridge.predict(X_test_pop)

# Negative insolvency predictions are impossible
pop_ridge_val_pred = np.clip(pop_ridge_val_pred, 0, None)
pop_ridge_test_pred = np.clip(pop_ridge_test_pred, 0, None)


print("POPULATION-AWARE RIDGE — FINAL SAMPLE")
print()

pop_ridge_validation = evaluate_predictions(
    y_val_pop,
    pop_ridge_val_pred,
    "Population-aware Ridge — Validation"
)

print()

pop_ridge_test = evaluate_predictions(
    y_test_pop,
    pop_ridge_test_pred,
    "Population-aware Ridge — Test"
)

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

model_results = pd.DataFrame({
    "Model": [
        "12M Historical Baseline",
        "Ridge Regression",
        "Random Forest",
        "Poisson Gradient Boosting",
        "Population-aware Ridge"
    ],
    "Test MAE": [
        3.556,
        4.430,
        4.431,
        4.693,
        4.635
    ],
    "Test RMSE": [
        8.617,
        10.428,
        11.069,
        13.601,
        10.810
    ]
})

model_results = model_results.sort_values("Test MAE")

fig, ax = plt.subplots(figsize=(11, 6))

bars = ax.barh(
    model_results["Model"],
    model_results["Test MAE"]
)

ax.invert_yaxis()

ax.set_title(
    "Simple Historical Benchmark Outperformed More Complex Models",
    fontsize=16,
    fontweight="bold",
    pad=15
)

ax.set_xlabel("Mean Absolute Error — next 3 months")

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

for bar, value in zip(bars, model_results["Test MAE"]):
    ax.text(
        value + 0.05,
        bar.get_y() + bar.get_height()/2,
        f"{value:.2f}",
        va="center",
        fontsize=10
    )

ax.text(
    0,
    -0.15,
    "Out-of-time evaluation | Industry-level 3-month insolvency forecasts",
    transform=ax.transAxes,
    fontsize=9
)

plt.tight_layout()
plt.show()

view_columns = pd.read_sql("""
    SHOW COLUMNS FROM vw_industry_trends
""", engine)

view_columns

industry_pressure = pd.read_sql("""
    SELECT
        sic07_3_digit,
        industry_description,
        rolling_12m_insolvencies,
        previous_12m_insolvencies,
        rolling_12m_change_pct
    FROM vw_industry_trends
    WHERE month_date = '2026-08-01'
      AND rolling_12m_insolvencies IS NOT NULL
      AND previous_12m_insolvencies IS NOT NULL
    ORDER BY rolling_12m_insolvencies DESC
    LIMIT 10
""", engine)

industry_pressure

import matplotlib.pyplot as plt
import numpy as np

plot_df = industry_pressure.copy()

# Shorter labels for a clean business chart
plot_df["label"] = [
    "Restaurants & mobile food",
    "Business support services",
    "Other personal services",
    "Computer programming",
    "Construction installation",
    "Building construction",
    "Property development",
    "Beverage serving",
    "Building completion",
    "Management consultancy"
]

# Reverse so largest appears at the top
plot_df = plot_df.iloc[::-1].reset_index(drop=True)

fig, ax = plt.subplots(figsize=(12, 7))

y = np.arange(len(plot_df))

bars = ax.barh(
    y,
    plot_df["rolling_12m_insolvencies"]
)

ax.set_yticks(y)
ax.set_yticklabels(plot_df["label"])

ax.set_xlabel("Company insolvencies — latest rolling 12 months")

ax.set_title(
    "High-Volume Industries Show Diverging Insolvency Pressure",
    fontsize=16,
    fontweight="bold",
    pad=16
)

ax.text(
    0,
    1.01,
    "Top 10 industries by insolvency volume, Sep 2025–Aug 2026",
    transform=ax.transAxes,
    fontsize=10
)

# Volume + change labels
for bar, volume, change in zip(
    bars,
    plot_df["rolling_12m_insolvencies"],
    plot_df["rolling_12m_change_pct"]
):
    direction = "▲" if change > 0 else "▼" if change < 0 else "—"

    ax.text(
        volume + 20,
        bar.get_y() + bar.get_height()/2,
        f"{int(volume):,}   {direction} {abs(change):.1f}%",
        va="center",
        fontsize=10
    )

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

ax.text(
    0,
    -0.12,
    "Change compares Sep 2025–Aug 2026 with the preceding 12 months.\n"
    "Source: UK Insolvency Service record-level company insolvency data. "
    "Excludes bulk cases and Table 1b excluded case types.",
    transform=ax.transAxes,
    fontsize=8.5
)

plt.tight_layout()
plt.show()
