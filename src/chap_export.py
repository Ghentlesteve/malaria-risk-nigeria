"""Export historical LGA cases and rainfall to the Chap monthly CSV format."""

import argparse
import csv
from pathlib import Path

from src.data_utils import validate_monthly_cases
from src.features import month_index, read_rainfall


def export_chap(cases_path, rainfall_path, output):
    temporary = output.with_suffix(".csv.part")
    inputs = {cases_path.resolve(), rainfall_path.resolve()}
    if output.suffix != ".csv" or inputs.intersection({output.resolve(), temporary.resolve()}):
        raise ValueError("Use a separate .csv output path.")
    validation = validate_monthly_cases(cases_path)
    if not validation.valid or not validation.rows:
        raise ValueError("Use a nonempty case file that passes the monthly schema check.")

    with cases_path.open(encoding="utf-8-sig", newline="") as handle:
        cases = {(row["org_unit_id"].strip(), month_index(row["period"].strip())): row["confirmed_cases"].strip()
                 for row in csv.DictReader(handle, strict=True)}
    rainfall = read_rainfall(rainfall_path)
    locations = sorted({location for location, _ in cases})
    months = [month for _, month in cases]
    periods = range(min(months), max(months) + 1)
    rows = []
    for location in locations:
        for month in periods:
            key = (location, month)
            year, month_zero = divmod(month, 12)
            period = f"{year:04d}-{month_zero + 1:02d}"
            if not rainfall.get(key):
                raise ValueError(f"Rainfall is unavailable for {location} in {period}. Chap requires complete rainfall.")
            rows.append((period, location, cases.get(key, ""), rainfall[key]))

    output.parent.mkdir(parents=True, exist_ok=True)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("time_period", "location", "disease_cases", "rainfall"))
        writer.writerows(rows)
    temporary.replace(output)
    return len(locations), len(periods), len(rows) - len(cases), sum(not row[2] for row in rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("data/processed/routine/monthly_cases.csv"))
    parser.add_argument("--rainfall", type=Path,
                        default=Path("data/processed/climate/rainfall_monthly_2019_2025.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/chap/nigeria_malaria_monthly.csv"))
    args = parser.parse_args()
    try:
        locations, months, added, blank = export_chap(args.cases, args.rainfall, args.output)
    except (ValueError, OSError, TypeError, csv.Error) as exc:
        parser.exit(1, f"Chap export failed: {exc}\n")
    print(f"Wrote {locations * months:,} rows across {locations:,} LGAs and {months} months to {args.output}.")
    print(f"Blank case counts: {blank:,}, including {added:,} LGA-months absent from the case file.")


if __name__ == "__main__":
    main()
