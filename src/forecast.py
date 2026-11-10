"""Generate one- and two-month malaria forecasts for a specified issue month."""

import argparse
import calendar
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from src.climate_data import digest, periods, write_json
from src.features import month_index, read_rainfall
from src.model import CLIMATE, HISTORY, predict, prepare_features, read_case_history


def month_label(index):
    year, month_zero = divmod(index, 12)
    return f"{year:04d}-{month_zero + 1:02d}"


def run_forecast(case_path, rainfall_paths, output, issue_month, case_delay=1, rainfall_delay=1):
    periods(issue_month, issue_month)
    if not 1 <= case_delay <= 10 or rainfall_delay < 1:
        raise ValueError("Use a case delay of 1–10 months and a rainfall delay of at least one month.")
    target_path = output / "forecast_predictions.csv"
    partial = target_path.with_suffix(".csv.part")
    audit_path = output / "forecast_audit.json"
    inputs = (case_path, *rainfall_paths)
    destinations = (target_path, partial, audit_path, audit_path.with_suffix(".json.part"))
    if {path.resolve() for path in inputs} & {path.resolve() for path in destinations}:
        raise ValueError("Use a separate output directory for forecast results.")
    input_hashes = [digest(path) for path in inputs]

    issue = month_index(issue_month)
    case_cutoff = issue - case_delay
    rainfall_cutoff = issue - rainfall_delay
    cases = read_case_history(case_path)
    history = cases.loc[cases["target_month"].le(case_cutoff)]
    observed = history.loc[history["confirmed_cases"].notna()]
    if observed["target_month"].max() != case_cutoff:
        raise ValueError(f"Case counts through {month_label(case_cutoff)} are required for this issue month.")

    rainfall = {}
    for path in rainfall_paths:
        source = read_rainfall(path)
        if rainfall.keys() & source.keys():
            raise ValueError("Rainfall files contain overlapping LGA-month keys.")
        rainfall.update(source)
    rainfall = {key: value for key, value in rainfall.items() if key[1] <= rainfall_cutoff}
    if not any(month == rainfall_cutoff and value != "" for (_, month), value in rainfall.items()):
        raise ValueError(f"Rainfall through {month_label(rainfall_cutoff)} is required for this issue month.")
    rainfall = {key: value if value != "" else np.nan for key, value in rainfall.items()}

    locations = history["org_unit_id"].drop_duplicates()
    output_frames = []
    with threadpool_limits(limits=4):
        for horizon in (1, 2):
            target = issue + horizon
            future = pd.DataFrame({"org_unit_id": locations, "period": month_label(target),
                                   "target_month": target, "confirmed_cases": np.nan})
            frame = prepare_features(pd.concat([history, future], ignore_index=True), rainfall,
                                     horizon, case_delay, rainfall_delay)
            train = frame.loc[frame["target_month"].le(case_cutoff) & frame["confirmed_cases"].notna()]
            forecast = frame.loc[frame["target_month"].eq(target), ["org_unit_id", "period", *CLIMATE]].copy()
            has_baseline = forecast["seasonal_naive"].notna()
            has_rainfall = forecast[CLIMATE[-3:]].notna().all(axis=1)
            forecast["case_history"] = np.nan
            forecast["case_rainfall"] = np.nan
            if has_baseline.any():
                forecast.loc[has_baseline, "case_history"] = predict(train, forecast.loc[has_baseline], HISTORY)
            ready = has_baseline & has_rainfall
            if ready.any():
                forecast.loc[ready, "case_rainfall"] = predict(train, forecast.loc[ready], CLIMATE)
            forecast["issue_month"] = issue_month
            forecast["horizon_months"] = horizon
            forecast["rainfall_model_status"] = np.select(
                [~has_baseline, ~has_rainfall], ["missing_same_month_last_year", "missing_rainfall"], default="ok"
            )
            output_frames.append(forecast[["org_unit_id", "issue_month", "period", "horizon_months",
                                           "seasonal_naive", "case_history", "case_rainfall", "rainfall_model_status"]])

    forecasts = pd.concat(output_frames, ignore_index=True)
    if input_hashes != [digest(path) for path in inputs]:
        raise ValueError("An input file changed during the forecast. Rerun with a stable snapshot.")
    output.mkdir(parents=True, exist_ok=True)
    forecasts.to_csv(partial, index=False)
    partial.replace(target_path)
    year, month = map(int, issue_month.split("-"))
    audit = {
        "issue_date": f"{issue_month}-{calendar.monthrange(year, month)[1]:02d}",
        "target_months": [month_label(issue + horizon) for horizon in (1, 2)],
        "case_cutoff": month_label(case_cutoff), "rainfall_cutoff": month_label(rainfall_cutoff),
        "case_delay_months": case_delay, "rainfall_delay_months": rainfall_delay,
        "cases_sha256": input_hashes[0], "rainfall_sha256": input_hashes[1:],
        "forecast_sha256": digest(target_path), "rows": len(forecasts),
        "rainfall_model_status_counts": forecasts["rainfall_model_status"].value_counts().to_dict(),
        "availability": "Calendar cutoffs applied to supplied exports. Historical publication dates are unverified.",
    }
    write_json(audit_path, audit)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("data/processed/routine/monthly_cases.csv"))
    parser.add_argument("--rainfall", type=Path, action="append", required=True, help="Repeat for nonoverlapping files.")
    parser.add_argument("--issue-month", required=True, help="Month-end forecast issue in YYYY-MM format.")
    parser.add_argument("--case-delay", type=int, default=1)
    parser.add_argument("--rainfall-delay", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_forecast(args.cases, args.rainfall, args.output, args.issue_month,
                              args.case_delay, args.rainfall_delay)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Forecast failed: {exc}\n")
    print(f"Issued {result['issue_date']} for {', '.join(result['target_months'])}.")
    print(f"Wrote {result['rows']:,} LGA-month rows to {args.output}.")


if __name__ == "__main__":
    main()
