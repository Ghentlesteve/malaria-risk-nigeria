"""Chap entry points for the same-month-last-year case count baseline."""

import argparse
import csv
import json
import math
from datetime import date
from pathlib import Path


def train(train_data, model):
    counts = {}
    with train_data.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = row["disease_cases"].strip()
            if value:
                count = float(value)
                if math.isnan(count):
                    continue
                if not math.isfinite(count) or count < 0:
                    raise ValueError("Training case counts must be finite and nonnegative.")
                counts.setdefault(row["location"], {})[row["time_period"]] = count
    model.write_text(json.dumps(counts), encoding="utf-8")


def predict(model, future_data, output):
    counts = json.loads(model.read_text(encoding="utf-8"))
    predictions = []
    with future_data.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            period, location = row["time_period"], row["location"]
            month = date.fromisoformat(f"{period}-01")
            previous_year = f"{month.year - 1:04d}-{month.month:02d}"
            count = counts.get(location, {}).get(previous_year)
            if count is None:
                raise ValueError(f"No reported cases for {location} in {previous_year}; cannot forecast {period}.")
            predictions.append((period, location, count))

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("time_period", "location", "sample_0"))
        writer.writerows(predictions)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    training = commands.add_parser("train")
    training.add_argument("train_data", type=Path)
    training.add_argument("model", type=Path)
    prediction = commands.add_parser("predict")
    prediction.add_argument("model", type=Path)
    prediction.add_argument("historic_data", type=Path, help="Chap history path. Training saves the required counts.")
    prediction.add_argument("future_data", type=Path)
    prediction.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "train":
            train(args.train_data, args.model)
        else:
            predict(args.model, args.future_data, args.output)
    except (KeyError, OSError, ValueError) as exc:
        parser.exit(1, f"Seasonal baseline failed: {exc}\n")


if __name__ == "__main__":
    main()
