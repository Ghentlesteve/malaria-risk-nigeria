"""Package only the data used by the public dashboard."""

import csv
import io
import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
ASSET_NAME = "malaria-dashboard-data-2020-2025.zip"
RELEASE_TAG = "dashboard-data-2020-2025-v1"
RELEASE_URL = f"https://github.com/Ghentlesteve/malaria-risk-nigeria/releases/download/{RELEASE_TAG}/{ASSET_NAME}"
CASES = "features/case_rainfall_monthly.csv"
REPORTING = "routine/nhmis_reporting_monthly.csv"
BOUNDARIES = "climate/nigeria_lga_boundaries_ocha_matched.geojson"
RUNS = ("forecast", "forecast/delay2")
PREDICTIONS = "backtest_predictions.csv"
METRICS = "backtest_metrics.csv"
AUDIT = "backtest_audit.json"
MEMBERS = {CASES, REPORTING, BOUNDARIES} | {
    f"{run}/{name}" for run in RUNS for name in (PREDICTIONS, METRICS, AUDIT)
}


def select_columns(content, columns):
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    if not set(columns).issubset(reader.fieldnames or ()):
        raise ValueError("A dashboard CSV is missing required columns.")
    result = io.StringIO()
    writer = csv.DictWriter(result, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(reader)
    return result.getvalue().encode("utf-8")


def bundle_files(data):
    yield CASES, select_columns((data / CASES).read_bytes(),
                                ("org_unit_id", "org_unit_name", "state", "period", "confirmed_cases", "rainfall_mm"))
    yield REPORTING, select_columns((data / REPORTING).read_bytes(),
                                    ("org_unit_id", "period", "reports_received", "reports_on_time",
                                     "reports_expected", "status", "completeness_pct", "timeliness_pct"))
    collection = json.loads((data / BOUNDARIES).read_text(encoding="utf-8-sig"))
    features = [{key: feature[key] for key in ("type", "id", "geometry")} for feature in collection["features"]]
    yield BOUNDARIES, json.dumps({"type": collection["type"], "features": features}).encode("utf-8")

    for run in RUNS:
        audit = json.loads((data / run / AUDIT).read_text(encoding="utf-8"))
        public_audit = {key: audit[key] for key in ("holdout_year", "case_delay_months", "rainfall_delay_months")}
        hashes = {}
        for name, columns in (
            (PREDICTIONS, ("org_unit_id", "period", "horizon_months", "confirmed_cases",
                           "seasonal_naive", "case_history", "case_rainfall")),
            (METRICS, ("horizon_months", "model", "rows", "mae", "mean_bias")),
        ):
            original = (data / run / name).read_bytes()
            if sha256(original).hexdigest() != audit["output_sha256"][name]:
                raise ValueError(f"Backtest file differs from its audit: {run}/{name}")
            content = select_columns(original, columns)
            hashes[name] = sha256(content).hexdigest()
            yield f"{run}/{name}", content
        public_audit["output_sha256"] = hashes
        yield f"{run}/{AUDIT}", json.dumps(public_audit).encode("utf-8")


def write_bundle(data, output):
    files = dict(bundle_files(data))
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(ZipInfo(name), content, compress_type=ZIP_DEFLATED)


def unpack_bundle(payload, destination):
    with ZipFile(io.BytesIO(payload)) as archive:
        names = archive.namelist()
        if len(names) != len(MEMBERS) or set(names) != MEMBERS:
            raise ValueError("The dashboard archive must contain exactly the expected files.")
        archive.extractall(destination, sorted(MEMBERS))


if __name__ == "__main__":
    bundle = ROOT / "outputs" / ASSET_NAME
    write_bundle(ROOT / "data" / "processed", bundle)
    print(bundle)
    print(f"SHA-256 {sha256(bundle.read_bytes()).hexdigest()}")
