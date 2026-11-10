"""Rolling backtest of monthly reported malaria cases using a fixed model design."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

from src.climate_data import digest, write_json
from src.features import month_index, read_rainfall

HISTORY = ["seasonal_naive", "case_lag0", "case_lag1", "case_lag2", "month_sin", "month_cos"]
CLIMATE = HISTORY + ["rain_lag0", "rain_lag1", "rain_lag2"]


def prepare_features(cases, rainfall, horizon, case_delay, rainfall_delay):
    frame = cases.copy()
    frame["issue_month"] = frame["target_month"] - horizon
    lookup = frame.set_index(["org_unit_id", "target_month"])["confirmed_cases"]
    rain_lookup = pd.Series(rainfall, dtype=float)

    def values(series, months):
        keys = pd.MultiIndex.from_arrays([frame["org_unit_id"], months])
        return series.reindex(keys).to_numpy()

    frame["seasonal_naive"] = values(lookup, frame["target_month"] - 12)
    for lag in range(3):
        frame[f"case_lag{lag}"] = values(lookup, frame["issue_month"] - case_delay - lag)
        frame[f"rain_lag{lag}"] = values(rain_lookup, frame["issue_month"] - rainfall_delay - lag)
    angle = 2 * np.pi * (frame["target_month"] % 12) / 12
    frame["month_sin"], frame["month_cos"] = np.sin(angle), np.cos(angle)
    return frame


def predict(train, test, columns):
    model = HistGradientBoostingRegressor(max_iter=100, max_leaf_nodes=15,
                                         min_samples_leaf=50, early_stopping=False, random_state=0)
    model.fit(train[columns], np.log1p(train["confirmed_cases"]))
    return np.maximum(0, np.expm1(model.predict(test[columns])))


def read_case_history(case_path):
    cases = pd.read_csv(case_path, usecols=["org_unit_id", "period", "confirmed_cases"],
                        dtype={"org_unit_id": str})
    cases["target_month"] = cases["period"].map(month_index)
    observed = cases["confirmed_cases"].dropna()
    if cases.duplicated(["org_unit_id", "target_month"]).any() or not (
        np.isfinite(observed).all() and observed.ge(0).all()
    ):
        raise ValueError("Case records must have unique LGA-month keys and nonnegative finite counts.")
    return cases


def evaluate(case_path, rain_path, output, holdout_year, case_delay, rainfall_delay):
    if not 1 <= case_delay <= 10 or rainfall_delay < 1:
        raise ValueError("Use a case delay of 1–10 months and a rainfall delay of at least one month.")
    cases = read_case_history(case_path)
    rainfall = {key: value if value != "" else np.nan for key, value in read_rainfall(rain_path).items()}
    predictions, coverage = [], []
    with threadpool_limits(limits=4):
        for horizon in (1, 2):
            frame = prepare_features(cases, rainfall, horizon, case_delay, rainfall_delay)
            for month in range(holdout_year * 12, (holdout_year + 1) * 12):
                issue = month - horizon
                train = frame.loc[
                    frame["target_month"].le(issue - case_delay) & frame["confirmed_cases"].notna()
                ]
                observed_test = frame.loc[
                    frame["target_month"].eq(month) & frame["confirmed_cases"].notna()
                ]
                test = observed_test.dropna(subset=["seasonal_naive", *CLIMATE[-3:]]).copy()
                if test.empty or train.empty:
                    raise ValueError(f"Insufficient training or evaluation data for month index {month}.")
                test["case_history"] = predict(train, test, HISTORY)
                test["case_rainfall"] = predict(train, test, CLIMATE)
                test["horizon_months"] = horizon
                year, month_zero = divmod(issue, 12)
                test["issue_period"] = f"{year:04d}-{month_zero + 1:02d}"
                predictions.append(test[["org_unit_id", "issue_period", "period", "horizon_months",
                                         "confirmed_cases", "seasonal_naive", "case_history", "case_rainfall"]])
                coverage.append({"horizon_months": horizon, "period": test["period"].iloc[0],
                                 "training_rows": len(train), "observed_targets": len(observed_test),
                                 "scored_targets": len(test)})

    predictions = pd.concat(predictions, ignore_index=True)
    metrics = []
    for horizon, subset in predictions.groupby("horizon_months"):
        for model in ("seasonal_naive", "case_history", "case_rainfall"):
            error = subset[model] - subset["confirmed_cases"]
            metrics.append({"horizon_months": int(horizon), "model": model, "rows": len(subset),
                            "mae": error.abs().mean(), "mean_bias": error.mean(),
                            "lga_macro_mae": error.abs().groupby(subset["org_unit_id"]).mean().mean()})
    output.mkdir(parents=True, exist_ok=True)
    output_hashes = {}
    for name, table in (("backtest_predictions.csv", predictions),
                        ("backtest_metrics.csv", pd.DataFrame(metrics))):
        path = output / name
        partial = path.with_suffix(".csv.part")
        table.to_csv(partial, index=False)
        partial.replace(path)
        output_hashes[name] = digest(path)
    write_json(output / "backtest_audit.json", {
        "holdout_year": holdout_year, "case_delay_months": case_delay,
        "rainfall_delay_months": rainfall_delay, "coverage": coverage,
        "cases_sha256": digest(case_path), "rainfall_sha256": digest(rain_path),
        "output_sha256": output_hashes,
        "availability": "Retrospective data with assumed delays, not historical snapshots.",
    })
    print(pd.DataFrame(metrics).to_string(index=False))
    print(f"Observed targets: {sum(row['observed_targets'] for row in coverage)} across both horizons.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("data/processed/routine/monthly_cases.csv"))
    parser.add_argument("--rainfall", type=Path,
                        default=Path("data/processed/climate/rainfall_monthly_2019_2025.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/forecast"))
    parser.add_argument("--holdout-year", type=int, default=2025)
    parser.add_argument("--case-delay", type=int, default=1)
    parser.add_argument("--rainfall-delay", type=int, default=1)
    args = parser.parse_args()
    evaluate(args.cases, args.rainfall, args.output, args.holdout_year, args.case_delay, args.rainfall_delay)
