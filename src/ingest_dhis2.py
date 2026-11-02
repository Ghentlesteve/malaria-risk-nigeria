"""Reshape the project's yearly DHIS2 case exports and audit coverage.

No source cells are overwritten, imputed or silently excluded. The roster is
the union of observed IDs, not an independently verified national master list.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from src.data_utils import OPTIONAL, REQUIRED, validate_monthly_cases

METADATA = {"orgunitlevel1", "orgunitlevel2", "orgunitlevel3", "organisationunitid",
            "organisationunitname", "organisationunitcode", "organisationunitdescription"}
CORE = {"orgunitlevel1", "orgunitlevel2", "orgunitlevel3", "organisationunitid"}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
FORMATS = {name.lower(): n for n, month in enumerate(MONTHS, 1)
           for name in (month, month[:3])}
INDICATOR = "MAL - Malaria cases confirmed (number)"
DEFINITION = "Persons tested positive for malaria by RDT + Persons tested positive for malaria by Microscopy"


def month_period(label: str, year: int) -> str:
    """Accept the observed long/short English month headings without date guessing."""
    match = re.fullmatch(r"([A-Za-z]+)[ -]([0-9]{2}|[0-9]{4})", label.strip())
    if not match or match[1].lower() not in FORMATS:
        raise ValueError(f"Unsupported month column: {label!r}")
    written_year = int(match[2])
    if written_year != (year % 100 if len(match[2]) == 2 else year):
        raise ValueError(f"Column year does not match filename: {label!r}")
    return f"{year:04d}-{FORMATS[match[1].lower()]:02d}"


def case_count(value: str) -> str:
    """Preserve blank and zero; accept whole decimal counts, never round fractions."""
    value = value.strip()
    if not value:
        return ""
    if not re.fullmatch(r"[0-9]{1,18}(?:\.0+)?", value):
        raise ValueError("Expected a whole nonnegative case count or blank.")
    return str(int(Decimal(value)))


def load_exports(paths):
    records, lineage, manifest = [], [], []
    identities, seen, years = {}, set(), set()
    for path in sorted(map(Path, paths)):
        match = re.fullmatch(r"malaria_confirmed_lga_monthly_([0-9]{4})\.csv", path.name)
        if not match:
            raise ValueError(f"Unexpected input filename: {path.name}")
        year = int(match[1])
        if not 1 <= year <= 9999 or year in years:
            raise ValueError("Invalid or duplicate export year.")
        years.add(year)
        source_rows = []
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            header = reader.fieldnames or []
            if len(header) != len(set(header)) or not CORE.issubset(header):
                raise ValueError(f"Missing or duplicate metadata columns: {path.name}")
            columns = {column: month_period(column, year) for column in header if column not in METADATA}
            if set(columns.values()) != {f"{year}-{m:02d}" for m in range(1, 13)} or len(columns) != 12:
                raise ValueError(f"Expected exactly twelve distinct month columns: {path.name}")
            ids = set()
            for number, row in enumerate(reader, 2):
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(f"Malformed record: {path.name}, record {number}")
                unit = row["organisationunitid"].strip()
                name = row["orgunitlevel3"].strip()
                state = row["orgunitlevel2"].strip()
                country = row["orgunitlevel1"].strip()
                if not all((unit, name, state, country)):
                    raise ValueError(f"Missing hierarchy/ID: {path.name}, record {number}")
                if not re.search(r"local government area|area council", name, re.IGNORECASE):
                    raise ValueError(f"Unrecognised LGA label: {path.name}, record {number}; review before exclusion.")
                if row.get("organisationunitname", name).strip() != name:
                    raise ValueError(f"Hierarchy/name disagreement: {path.name}, record {number}")
                identity = (name, state, country)
                if unit in identities and identities[unit] != identity:
                    raise ValueError(f"Conflicting hierarchy for an ID: {path.name}, record {number}")
                identities[unit] = identity
                ids.add(unit)
                for column, period in columns.items():
                    key = (unit, period)
                    if key in seen:
                        raise ValueError(f"Duplicate unit/month: {path.name}, record {number}")
                    seen.add(key)
                    try:
                        cases = case_count(row[column])
                    except ValueError as exc:
                        raise ValueError(f"Invalid cases: {path.name}, record {number}, {column}") from exc
                    record = dict(zip(REQUIRED, (unit, name, state, period, cases)))
                    record.update({field: "" for field in OPTIONAL})
                    records.append(record)
                    source_rows.append(record)
                    lineage.append({"org_unit_id": unit, "period": period, "source_file": path.name,
                                    "source_record": number, "source_column": column,
                                    "source_value": row[column]})
        if not source_rows:
            raise ValueError(f"Export has no observations: {path.name}")
        manifest.append({"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "year": year, "units": len(ids), "rows": len(source_rows),
                         "blank_cases": sum(r["confirmed_cases"] == "" for r in source_rows)})
    if not records:
        raise ValueError("No yearly exports found.")
    records.sort(key=lambda r: (r["org_unit_id"], r["period"]))
    return records, lineage, manifest


def coverage(records, manifest):
    roster = {r["org_unit_id"]: (r["org_unit_name"], r["state"]) for r in records}
    by_year, by_state_year = defaultdict(list), defaultdict(list)
    for row in records:
        year = int(row["period"][:4])
        by_year[year].append(row)
        by_state_year[(row["state"], year)].append(row)
    yearly, absent = [], []
    for source in sorted(manifest, key=lambda m: m["year"]):
        year = source["year"]
        rows = by_year[year]
        ids = {r["org_unit_id"] for r in rows}
        missing_units = sorted(set(roster) - ids)
        for unit in missing_units:
            name, state = roster[unit]
            absent.append({"org_unit_id": unit, "org_unit_name": name, "state": state,
                           "year": year, "absent_months": 12})
        yearly.append({"year": year, "states_or_fct": len({r["state"] for r in rows}),
                       "observed_units": len(ids), "exported_unit_months": len(rows),
                       "blank_case_cells": sum(r["confirmed_cases"] == "" for r in rows),
                       "zero_case_cells": sum(r["confirmed_cases"] == "0" for r in rows),
                       "absent_unit_months_vs_union_roster": len(missing_units) * 12,
                       "reported_case_sum": sum(int(r["confirmed_cases"]) for r in rows if r["confirmed_cases"] != "")})
    state_years = []
    for (state, year), rows in sorted(by_state_year.items()):
        state_years.append({"state": state, "year": year, "observed_units": len({r["org_unit_id"] for r in rows}),
                            "blank_case_cells": sum(r["confirmed_cases"] == "" for r in rows)})
    return yearly, absent, state_years


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_readiness_report(path, summary, absent):
    years = summary["coverage"]
    blanks = sum(y["blank_case_cells"] for y in years)
    missing = sum(y["absent_unit_months_vs_union_roster"] for y in years)
    roster_size = summary["schema_validation"]["units"]
    zero_count = summary["schema_validation"]["zero_cases"]
    span = f"January {years[0]['year']}–December {years[-1]['year']}"
    lines = ["# Routine malaria case-data readiness", "",
             f"Nationwide extraction, {span}. Nasarawa was the extraction test.", "",
             f"Prepared at: {summary['prepared_at_utc']}", "",
             "## Export coverage", "",
             "| Year | State/FCT labels | LGA IDs | Exported LGA-months | Blank case cells | Absent LGA-months against union roster |",
             "| --- | --- | --- | --- | --- | --- |"]
    for year in years:
        lines.append("| " + " | ".join(str(year[key]) for key in
                     ("year", "states_or_fct", "observed_units", "exported_unit_months", "blank_case_cells",
                      "absent_unit_months_vs_union_roster")) + " |")
    lines += ["", f"The combined table has {summary['schema_validation']['rows']:,} exported LGA-month records, "
              f"{blanks:,} blank case cells and {missing:,} additional LGA-months absent from the exports.", "",
              f"The union roster has {roster_size} IDs. This is an observed export roster, not an independently verified master list. "
              "State/FCT coverage is shown separately for each year. Blanks and absent rows are not reported zeros.", "",
              "## Units absent in earlier exports", "",
              "| Year | State label | LGA label |",
              "| --- | --- | --- |"]
    for row in absent:
        lines.append(f"| {row['year']} | {row['state']} | {row['org_unit_name']} |")
    lines += ["", "These are observations about export coverage. Their causes have not been established.", "",
              "## Checks completed", "",
              "- Normalised full and abbreviated English month headings into YYYY-MM.",
              "- Converted whole decimal counts such as 68.0 into integers without rounding or changing values.",
              "- Retained original organisation-unit IDs and hierarchy labels, including source prefixes.",
              "- Checked duplicate unit-months, conflicting hierarchy labels and non-LGA labels.",
              "- Ran the existing monthly-case schema validator successfully.",
              "- Preserved original files. SHA-256 fingerprints and cell-level provenance are saved beside the processed table.", "",
              "## Interpretation limits and remaining inputs", "",
              "- The confirmed-case indicator formula was supplied by the user: RDT-positive persons plus microscopy-positive persons. "
              "Indicator UID, age scope and formula history are not embedded in these CSV exports.",
              f"- There are {zero_count} explicit zero case counts in the exports. Confirm whether export settings suppressed zeros before interpreting blank cells. "
              "The pipeline keeps blanks missing and makes no correction without evidence.",
              "- NHMIS 2019 dataset-level expected, actual and timely report counts are not yet supplied. Reporting quality remains unknown. "
              "Dataset completion does not prove completion of each malaria field.",
              "- Extraction timestamps, historical revision dates and a full independent organisation-unit roster are pending. "
              "A retrospective export does not establish what data was available at a historical forecast issue date.",
              "- Boundary files and rainfall/temperature data are pending. No rainfall association or forecast performance has been estimated.",
              "- Reported case totals are not population incidence or an estimate of all malaria infections. "
              "Changes in recorded cases may reflect testing and reporting changes.", "",
              "## Reproduce", "", "```bash", "python -m src.ingest_dhis2", "```", "",
              "The input CSVs remain in data/raw/. Derived tables, this report, validation results and provenance remain under "
              "data/processed/routine/, which is ignored by Git. No observations are imputed and no unit-years are fabricated.", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def prepare(input_dir: Path, output_dir: Path):
    if input_dir.resolve() == output_dir.resolve() or input_dir.resolve() in output_dir.resolve().parents:
        raise ValueError("Use a separate output directory outside the raw input folder.")
    paths = list(input_dir.glob("malaria_confirmed_lga_monthly_*.csv"))
    records, lineage, manifest = load_exports(paths)
    yearly, absent, state_years = coverage(records, manifest)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "monthly_cases.csv"
    write_csv(target, records, (*REQUIRED, *OPTIONAL))
    validation = validate_monthly_cases(target)
    if not validation.valid:
        raise ValueError("Normalised output failed schema validation; do not use for analysis.")
    write_csv(output_dir / "monthly_cases_lineage.csv", lineage,
              ("org_unit_id", "period", "source_file", "source_record", "source_column", "source_value"))
    write_csv(output_dir / "yearly_coverage.csv", yearly, tuple(yearly[0]))
    write_csv(output_dir / "absent_unit_years.csv", absent,
              ("org_unit_id", "org_unit_name", "state", "year", "absent_months"))
    write_csv(output_dir / "state_year_coverage.csv", state_years, tuple(state_years[0]))
    summary = {"prepared_at_utc": datetime.now(timezone.utc).isoformat(),
               "scope": "Nationwide LGA extraction; Nasarawa was an extraction test, not a selected pilot.",
               "indicator_name_user_supplied": INDICATOR,
               "indicator_formula_user_supplied": DEFINITION,
               "indicator_metadata_embedded_in_exports": False,
               "extraction_timestamp_and_historical_revision_dates": "Not supplied",
               "reporting_quality": "Unknown; NHMIS 2019 dataset-level report counts not supplied.",
               "roster_basis": "Union of IDs observed in the supplied files; independent official roster not supplied.",
               "blank_handling": "Retained as blank; absent unit-years listed separately, not fabricated as observations.",
               "source_files": manifest, "coverage": yearly, "schema_validation": validation.to_dict()}
    (output_dir / "monthly_cases_audit.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_readiness_report(output_dir / "readiness_report.md", summary, absent)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/routine"))
    args = parser.parse_args(argv)
    try:
        summary = prepare(args.input_dir, args.output_dir)
    except (ValueError, OSError, UnicodeError, csv.Error) as exc:
        parser.exit(1, f"Preparation failed: {exc}\n")
    print(json.dumps({"output_dir": str(args.output_dir), "coverage": summary["coverage"],
                      "schema_valid": summary["schema_validation"]["valid"],
                      "reporting_quality": summary["reporting_quality"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
