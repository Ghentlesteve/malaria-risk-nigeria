"""Join case records to observed rainfall by organisation unit and calendar month."""

import argparse
import csv
import math
from datetime import date
from pathlib import Path

from src.climate_data import digest, write_json
from src.data_utils import validate_monthly_cases

LAGS = (0, 1, 2, 3)
RAIN_FIELDS = ("rainfall_mm", *(f"rainfall_lag{lag}_mm" for lag in LAGS[1:]))


def month_index(period):
    month = date.fromisoformat(f"{period}-01")
    return month.year * 12 + month.month - 1


def read_rainfall(path):
    rainfall = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        required = {"org_unit_id", "period", "rainfall_mm", "status"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Rainfall CSV is missing required fields.")
        for row in reader:
            key = (row["org_unit_id"], month_index(row["period"]))
            if key in rainfall or not key[0]:
                raise ValueError(f"Duplicate or empty rainfall key at line {reader.line_num}.")
            if row["status"] == "ok":
                value = float(row["rainfall_mm"])
                if not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid rainfall at line {reader.line_num}.")
                rainfall[key] = row["rainfall_mm"]
            elif row["status"] == "insufficient_valid_area" and row["rainfall_mm"] == "":
                rainfall[key] = ""
            else:
                raise ValueError(f"Inconsistent rainfall status at line {reader.line_num}.")
    return rainfall


def build_case_rainfall(cases, rainfall_path, output):
    audit_path = output.with_suffix(".json")
    inputs = {cases.resolve(), rainfall_path.resolve()}
    if output.suffix != ".csv" or inputs.intersection({output.resolve(), audit_path.resolve()}):
        raise ValueError("Use a separate .csv output path.")
    validation = validate_monthly_cases(cases)
    if not validation.valid:
        raise ValueError("Case input failed the monthly schema check.")
    rainfall = read_rainfall(rainfall_path)
    rows = []
    missing_keys = dict.fromkeys(RAIN_FIELDS, 0)
    unavailable = dict.fromkeys(RAIN_FIELDS, 0)
    with cases.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = [*reader.fieldnames, *RAIN_FIELDS]
        for row in reader:
            unit, month = row["org_unit_id"].strip(), month_index(row["period"].strip())
            for field, lag in zip(RAIN_FIELDS, LAGS):
                key = (unit, month - lag)
                if key not in rainfall:
                    missing_keys[field] += 1
                elif rainfall[key] == "":
                    unavailable[field] += 1
                row[field] = rainfall.get(key, "")
            rows.append(row)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".csv.part")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)
    audit = {
        "rows": len(rows),
        "case_ids": validation.units,
        "blank_case_counts": validation.missing_cases,
        "missing_rainfall_keys": missing_keys,
        "unavailable_rainfall_values": unavailable,
        "cases_sha256": digest(cases),
        "rainfall_sha256": digest(rainfall_path),
        "output_sha256": digest(output),
        "timing": "Observed rainfall keyed by calendar month. Check publication availability separately before forecasting.",
    }
    write_json(audit_path, audit)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("data/processed/routine/monthly_cases.csv"))
    parser.add_argument("--rainfall", type=Path,
                        default=Path("data/processed/climate/rainfall_monthly_2019_2025.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/features/case_rainfall_monthly.csv"))
    args = parser.parse_args()
    try:
        audit = build_case_rainfall(args.cases, args.rainfall, args.output)
    except (ValueError, OSError, TypeError, csv.Error) as exc:
        parser.exit(1, f"Case–rainfall join failed: {exc}\n")
    print(f"Wrote {audit['rows']} rows to {args.output}. See the JSON audit for coverage.")


if __name__ == "__main__":
    main()
