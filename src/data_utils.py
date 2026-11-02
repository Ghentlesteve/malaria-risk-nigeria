"""Validate the project's monthly aggregate case CSV without altering observations."""

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

REQUIRED = ("org_unit_id", "org_unit_name", "state", "period", "confirmed_cases")
REPORTING = ("reports_expected", "reports_received", "reports_on_time")
COUNTS = ("confirmed_cases", *REPORTING, "tests_performed", "population")
OPTIONAL = (*REPORTING, "tests_performed", "population")


@dataclass
class Issue:
    severity: str
    code: str
    message: str
    row: int | None = None


@dataclass
class ValidationResult:
    rows: int = 0
    units: int = 0
    missing_cases: int = 0
    zero_cases: int = 0
    internal_missing_months: int = 0
    issues: list[Issue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict:
        return {"valid": self.valid, **asdict(self)}

    def add(self, severity: str, code: str, message: str, row=None):
        self.issues.append(Issue(severity, code, message, row))


def validate_monthly_cases(path: str | Path) -> ValidationResult:
    """Check schema, values and internal coverage; blank case counts stay missing.

    Row numbers are CSV record numbers, with the header counted as record 1.
    No missing units or periods beyond observed coverage can be inferred here.
    """
    result = ValidationResult()
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            _validate_records(csv.reader(handle, strict=True), result)
    except (OSError, UnicodeError, csv.Error) as exc:
        # Do not echo observations or file contents into validation summaries.
        result.add("error", "unreadable_csv", f"Cannot read CSV ({type(exc).__name__}).")
    return result


def _validate_records(reader, result):
    header = next(reader, None)
    if header is None:
        result.add("error", "empty_file", "CSV is empty; supply a header and observations.")
        return
    duplicates = [name for name, count in Counter(header).items() if count > 1]
    missing = sorted(set(REQUIRED) - set(header))
    extra = sorted(set(header) - set(REQUIRED) - set(OPTIONAL))
    if duplicates:
        result.add("error", "duplicate_columns", "CSV contains duplicate column names.")
    if missing:
        result.add("error", "missing_columns", "Missing columns: " + ", ".join(missing))
    if extra:
        result.add("error", "unknown_columns", "CSV has unsupported columns; map to the documented schema.")
    if not result.valid:
        return

    identities = {}
    seen = set()
    months = defaultdict(set)
    unknown_reporting = Counter()
    for row_number, values in enumerate(reader, start=2):
        result.rows += 1
        if len(values) != len(header):
            result.add("error", "row_width", "Record length does not match header.", row_number)
            continue
        row = {name: value.strip() for name, value in zip(header, values)}
        for name in ("org_unit_id", "org_unit_name", "state"):
            if not row[name]:
                result.add("error", "missing_identity", f"{name} must be nonempty.", row_number)
        unit = row["org_unit_id"]
        if unit:
            identity = (row["org_unit_name"], row["state"])
            if unit in identities and identities[unit] != identity:
                result.add("error", "inconsistent_identity", "An ID has conflicting names or states.", row_number)
            identities.setdefault(unit, identity)

        period = row["period"]
        if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", period) or period[:4] == "0000":
            result.add("error", "invalid_period", "period must be a real YYYY-MM month.", row_number)
        elif unit:
            key = (unit, period)
            if key in seen:
                result.add("error", "duplicate_period", "Duplicate organisation-unit/month record.", row_number)
            seen.add(key)
            year, month = map(int, period.split("-"))
            months[unit].add(year * 12 + month - 1)

        numbers = {}
        for name in COUNTS:
            value = row.get(name, "")
            if not value:
                numbers[name] = None
                if name == "confirmed_cases":
                    result.missing_cases += 1
                    result.add("warning", "missing_cases", "confirmed_cases is unknown; retain as missing.", row_number)
                if name in REPORTING:
                    unknown_reporting[name] += 1
                continue
            if len(value) > 18 or not re.fullmatch(r"[0-9]+", value):
                result.add("error", "invalid_count", f"{name} must be a whole nonnegative count (up to 18 digits).", row_number)
                numbers[name] = None
                continue
            number = int(value)
            numbers[name] = number
            if name == "population" and number == 0:
                result.add("error", "invalid_population", "population must be positive when supplied.", row_number)
            if name == "confirmed_cases" and number == 0:
                result.zero_cases += 1
        for lower, upper in (("reports_received", "reports_expected"),
                             ("reports_on_time", "reports_received"),
                             ("reports_on_time", "reports_expected")):
            if numbers[lower] is not None and numbers[upper] is not None and numbers[lower] > numbers[upper]:
                result.add("error", "reporting_order", f"{lower} cannot exceed {upper}.", row_number)
        if numbers["reports_expected"] == 0:
            result.add("warning", "zero_expected_reports", "No reports expected; review reporting scope.", row_number)

    result.units = len(identities)
    if result.rows == 0:
        result.add("error", "no_observations", "CSV contains a header but no observations.")
    for name, count in unknown_reporting.items():
        result.add("warning", "unknown_reporting", f"{name} is unknown in {count} record(s).")
    for observed in months.values():
        result.internal_missing_months += max(observed) - min(observed) + 1 - len(observed)
    if result.internal_missing_months:
        result.add("warning", "missing_months", f"{result.internal_missing_months} unit-month(s) absent within observed date ranges; do not fill with zero.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--report", type=Path, help="Optional JSON summary path.")
    args = parser.parse_args(argv)
    if args.report and args.csv.resolve() == args.report.resolve():
        parser.error("Report must not overwrite the input CSV.")
    result = validate_monthly_cases(args.csv)
    payload = json.dumps(result.to_dict(), indent=2)
    print(payload)
    if args.report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(payload + "\n", encoding="utf-8")
        except OSError:
            parser.exit(2, "Could not write the JSON report.\n")
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
