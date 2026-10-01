"""
Stage 5: Sanity-check the headline R² before trusting it.

A pooled R² of 0.973 across industries of very different sizes can be
mostly explained by the model telling large and small industries apart,
not by genuine month-to-month forecasting skill. This script checks that
directly against an industry-mean-only benchmark, and breaks error down
industry-by-industry rather than pooled. See WALKTHROUGH.md, "Stage 7".
"""

# FINAL SANITY CHECK — HIGH R²

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np
import pandas as pd

# Recreate the exact original modelling splits
check_train = model_data[
    model_data["month_date"] < "2023-01-01"
].copy()

check_test = model_data[
    model_data["month_date"] >= "2025-01-01"
].copy()

# 1. Winning 12-month baseline
check_test["pred_12m_baseline"] = (
    check_test["previous_12m_total"] / 4
)

# 2. Simple 3-month persistence
check_test["pred_3m_persistence"] = (
    check_test["previous_3m_total"]
)

# 3. Historical industry average
# Calculated ONLY from training period
industry_train_mean = (
    check_train
    .groupby("sic07_3_digit")[target_col]
    .mean()
)

check_test["pred_industry_mean"] = (
    check_test["sic07_3_digit"]
    .map(industry_train_mean)
)


def sanity_metrics(data, prediction_col):
    mask = (
        data[target_col].notna()
        & data[prediction_col].notna()
    )

    actual = data.loc[mask, target_col]
    pred = data.loc[mask, prediction_col]

    return {
        "N": len(actual),
        "MAE": mean_absolute_error(actual, pred),
        "RMSE": np.sqrt(mean_squared_error(actual, pred)),
        "R²": r2_score(actual, pred)
    }


results = pd.DataFrame({
    "12M historical baseline":
        sanity_metrics(check_test, "pred_12m_baseline"),

    "3M persistence":
        sanity_metrics(check_test, "pred_3m_persistence"),

    "Training-period industry mean":
        sanity_metrics(check_test, "pred_industry_mean")
}).T

print(results.round(3))

# Per-industry forecasting performance

industry_performance = (
    check_test
    .assign(
        absolute_error=lambda x:
            abs(x[target_col] - x["pred_12m_baseline"])
    )
    .groupby(["sic07_3_digit", "industry_description"])
    .agg(
        observations=(target_col, "size"),
        mean_actual=(target_col, "mean"),
        MAE=("absolute_error", "mean")
    )
    .reset_index()
)

print("Industries:", len(industry_performance))
print()
print("Median industry MAE:",
      round(industry_performance["MAE"].median(), 3))
print("25th percentile:",
      round(industry_performance["MAE"].quantile(0.25), 3))
print("75th percentile:",
      round(industry_performance["MAE"].quantile(0.75), 3))
print("90th percentile:",
      round(industry_performance["MAE"].quantile(0.90), 3))

print(
    industry_performance
    .sort_values("MAE", ascending=False)
    .head(10)
)
