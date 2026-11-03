"""Prepare NHMIS 2019 reporting counts for the local dashboard."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

METRICS = {
    "O82o1WlMisO.EXPECTED_REPORTS": "reports_expected",
    "O82o1WlMisO.ACTUAL_REPORTS": "reports_received",
    "O82o1WlMisO.ACTUAL_REPORTS_ON_TIME": "reports_on_time",
}


def prepare(source, cases_path, output):
    data = pd.read_csv(source, dtype={"Organisation unit": str, "Period": str})
    if set(data["Data"].unique()) != set(METRICS):
        raise ValueError("Expected all three NHMIS 2019 reporting measures.")
    data["period"] = pd.to_datetime(data["Period"], format="%Y%m", errors="raise").dt.strftime("%Y-%m")
    data["Value"] = pd.to_numeric(data["Value"], errors="raise")
    counts = data["Value"]
    if not (np.isfinite(counts) & counts.ge(0) & counts.mod(1).eq(0)).all():
        raise ValueError("Reporting counts must be finite nonnegative integers.")
    cases = pd.read_csv(cases_path, usecols=["org_unit_id"], dtype=str)
    if not set(data["Organisation unit"]).issubset(set(cases["org_unit_id"])):
        raise ValueError("Reporting export contains organisation-unit IDs outside the case roster.")
    wide = (data.pivot(index=["Organisation unit", "period"], columns="Data", values="Value")
            .rename(columns=METRICS).rename_axis(index=["org_unit_id", "period"]).reset_index())
    expected, received, timely = (wide[name] for name in METRICS.values())
    missing = wide[list(METRICS.values())].isna().any(axis=1)
    inconsistent = received.gt(expected) | timely.gt(received)
    wide["status"] = np.select([missing, inconsistent, expected.eq(0)],
                               ["Missing counts", "Inconsistent counts", "No reports expected"], default="OK")
    denominator = expected.where(wide["status"].eq("OK"))
    wide["completeness_pct"] = 100 * received / denominator
    wide["timeliness_pct"] = 100 * timely / denominator
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(".csv.part")
    wide.to_csv(partial, index=False)
    partial.replace(output)
    print(f"{len(wide)} LGA-months, {wide.org_unit_id.nunique()} LGAs, {wide.period.nunique()} months")
    print(wide["status"].value_counts().to_string())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/nhmis_2019_reporting_monthly_2025.csv"))
    parser.add_argument("--cases", type=Path, default=Path("data/processed/routine/monthly_cases.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/routine/nhmis_reporting_monthly.csv"))
    args = parser.parse_args()
    prepare(args.input, args.cases, args.output)
