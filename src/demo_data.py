"""Generate a small, entirely synthetic dataset for the dashboard demo."""

import csv
import hashlib
import json
from pathlib import Path
from statistics import mean


DEMO_ROOT = Path(__file__).resolve().parents[1] / "data" / "processed" / "demo"
DEMO_YEAR = 2025


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_backtest(folder, cases, delay):
    models = ("seasonal_naive", "case_history", "case_rainfall")
    predictions, metrics = [], []
    for horizon in (1, 2):
        errors = {model: [] for model in models}
        for (unit, year, month), actual in cases.items():
            if year != DEMO_YEAR:
                continue
            # Invent forecast values with varying errors for both settings.
            offset = (month % 5 - 2) * (delay + horizon)
            estimates = (cases[unit, year - 1, month], actual + 9 + offset, actual - 5 + offset)
            predictions.append(dict(org_unit_id=unit, period=f"{year}-{month:02d}", horizon_months=horizon,
                                    confirmed_cases=actual, **dict(zip(models, estimates))))
            for model, estimate in zip(models, estimates):
                errors[model].append(estimate - actual)
        for model, values in errors.items():
            metrics.append(dict(horizon_months=horizon, model=model, rows=len(values),
                                mae=mean(map(abs, values)), mean_bias=mean(values)))

    output_hashes = {
        "backtest_predictions.csv": write_csv(folder / "backtest_predictions.csv", predictions),
        "backtest_metrics.csv": write_csv(folder / "backtest_metrics.csv", metrics),
    }
    write_json(folder / "backtest_audit.json", dict(holdout_year=DEMO_YEAR, case_delay_months=delay,
                                                   rainfall_delay_months=delay, output_sha256=output_hashes))


def generate_demo(root):
    features, monthly_cases, reporting = [], [], []
    case_counts = {}
    for index in range(4):
        unit = f"demo-lga-{index + 1}"
        name = f"Demo LGA {index + 1}"
        state = "Demo North State" if index < 2 else "Demo South State"
        west, south = 7 + index % 2, 9 - index // 2
        ring = [[west, south], [west, south + 1], [west + 1, south + 1],
                [west + 1, south], [west, south]]
        features.append(dict(type="Feature", id=unit, properties={},
                             geometry=dict(type="Polygon", coordinates=[ring])))
        for year in (DEMO_YEAR - 1, DEMO_YEAR):
            for month in range(1, 13):
                period = f"{year}-{month:02d}"
                season = min(month, 13 - month)
                actual = 60 + index * 24 + season * 17 + (year - DEMO_YEAR + 1) * (10 + month)
                rainfall = 12 + season ** 2 * 4 + (month * (index + 1) + year) % 13
                case_counts[unit, year, month] = actual
                monthly_cases.append(dict(org_unit_id=unit, org_unit_name=name, state=state, period=period,
                                          confirmed_cases=actual, rainfall_mm=rainfall))
                expected = 20 + index * 5
                received = expected - (month + index) % 4
                on_time = received - month % 3
                reporting.append(dict(org_unit_id=unit, period=period, reports_expected=expected,
                                      reports_received=received, reports_on_time=on_time,
                                      completeness_pct=100 * received / expected,
                                      timeliness_pct=100 * on_time / expected, status="OK"))

    write_csv(root / "features" / "case_rainfall_monthly.csv", monthly_cases)
    write_csv(root / "routine" / "nhmis_reporting_monthly.csv", reporting)
    write_json(root / "climate" / "demo_lga_boundaries.geojson", dict(type="FeatureCollection", features=features))
    write_backtest(root / "forecast", case_counts, delay=1)
    write_backtest(root / "forecast" / "delay2", case_counts, delay=2)


if __name__ == "__main__":
    generate_demo(DEMO_ROOT)
    print(f"Synthetic dashboard files generated in {DEMO_ROOT}")
