"""Describe seasonality and lagged rainfall associations in reported malaria cases."""

import argparse
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

from src.features import RAIN_FIELDS

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def analyze(source, output):
    data = pd.read_csv(source, usecols=["org_unit_id", "period", "confirmed_cases", *RAIN_FIELDS])
    if data.duplicated(["org_unit_id", "period"]).any():
        raise ValueError("Expected one record per LGA and month.")
    data["month"] = pd.PeriodIndex(data["period"], freq="M").month
    observed = data.dropna(subset=["confirmed_cases", *RAIN_FIELDS]).copy()
    observed["log_cases"] = np.log1p(observed["confirmed_cases"])
    variables = ["log_cases", *RAIN_FIELDS]
    groups = observed.groupby(["org_unit_id", "month"])
    # Single observations contain no within-LGA, within-calendar-month comparison.
    repeated = groups["log_cases"].transform("size").ge(2)
    deviations = (observed[variables] - groups[variables].transform("mean")).loc[repeated]
    deviations["org_unit_id"] = observed.loc[repeated, "org_unit_id"]

    rows = []
    for lag, column in enumerate(RAIN_FIELDS):
        per_lga = []
        for _, unit in deviations.groupby("org_unit_id"):
            if len(unit) >= 24 and unit[column].nunique() > 1 and unit["log_cases"].nunique() > 1:
                per_lga.append(unit[column].corr(unit["log_cases"]))
        values = pd.Series(per_lga, dtype=float)
        rows.append({
            "lag_months": lag,
            "pooled_raw_r": observed[column].corr(observed["log_cases"]),
            "pooled_adjusted_r": deviations[column].corr(deviations["log_cases"]),
            "lga_median_adjusted_r": values.median(),
            "lga_q25_adjusted_r": values.quantile(.25),
            "lga_q75_adjusted_r": values.quantile(.75),
            "lgas_evaluated": len(values),
        })
    results = pd.DataFrame(rows)

    expected_periods = pd.period_range(data["period"].min(), data["period"].max(), freq="M")
    counts = observed.groupby("org_unit_id")["period"].transform("size")
    balanced = observed.loc[counts.eq(len(expected_periods))].copy()
    measures = ["confirmed_cases", "rainfall_mm"]
    averages = balanced.groupby("org_unit_id")[measures].transform("mean")
    # Normalize each LGA to its own overall mean before averaging across LGAs.
    scaled = balanced[measures].div(averages.where(averages.gt(0)))
    seasonal = scaled.groupby(balanced["month"]).mean()

    output.mkdir(parents=True, exist_ok=True)
    results.to_csv(output / "lag_associations.csv", index=False)
    seasonal.to_csv(output / "seasonal_profiles.csv")
    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained")
    left.plot(seasonal.index, seasonal["rainfall_mm"], marker="o", label="Rainfall")
    left.plot(seasonal.index, seasonal["confirmed_cases"], marker="o", label="Reported cases")
    left.axhline(1, color="0.65", linewidth=1)
    left.set(title=f"Seasonal profiles · {balanced.org_unit_id.nunique()} complete LGAs",
             xlabel="Calendar month", ylabel="Ratio to each LGA's overall mean", xticks=range(1, 13))
    left.legend()
    right.plot(results.lag_months, results.pooled_raw_r, marker="o", label="Raw pooled")
    right.plot(results.lag_months, results.pooled_adjusted_r, marker="o", label="After seasonal adjustment")
    right.axhline(0, color="0.65", linewidth=1)
    right.set(title="Rainfall and log(1 + reported cases)", xlabel="Months rainfall precedes cases",
              ylabel="Pearson correlation", xticks=range(len(RAIN_FIELDS)))
    right.legend()
    fig.savefig(output / "rainfall_case_patterns.png", dpi=160)
    plt.close(fig)
    print(f"{len(data):,} case rows; {len(observed):,} complete for all lags; "
          f"{len(deviations):,} seasonally adjusted rows; {balanced.org_unit_id.nunique()} complete LGAs.")
    print(results.to_string(index=False))
    print(seasonal.to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/processed/features/case_rainfall_monthly.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/analysis"))
    args = parser.parse_args()
    analyze(args.input, args.output)
