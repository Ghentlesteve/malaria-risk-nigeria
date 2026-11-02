"""Small invented records exercise validation only; they are not project data."""

import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.data_utils import OPTIONAL, REQUIRED, main, validate_monthly_cases


class MonthlyCasesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "cases.csv"

    def write(self, rows, columns=(*REQUIRED, *OPTIONAL)):
        with self.path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return validate_monthly_cases(self.path)

    def record(self, **changes):
        return {"org_unit_id": "001", "org_unit_name": "Test unit", "state": "Test state",
                "period": "2020-01", "confirmed_cases": "0", "reports_expected": "10",
                "reports_received": "9", "reports_on_time": "8", **changes}

    def codes(self, result):
        return {issue.code for issue in result.issues}

    def test_valid_data_preserves_input_and_distinguishes_missing_from_zero(self):
        result = self.write([self.record(), self.record(period="2020-02", confirmed_cases="")])
        self.assertTrue(result.valid)
        self.assertEqual((result.missing_cases, result.zero_cases), (1, 1))
        original = self.path.read_bytes()
        validate_monthly_cases(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertIn(b"001", original)

    def test_duplicates_and_identity_conflicts(self):
        result = self.write([self.record(), self.record(org_unit_name="Changed")])
        self.assertFalse(result.valid)
        self.assertTrue({"duplicate_period", "inconsistent_identity"} <= self.codes(result))

    def test_internal_gaps_across_year_boundary_without_cross_unit_fill(self):
        result = self.write([self.record(period="2019-12"), self.record(period="2020-02"),
                             self.record(org_unit_id="002", period="2019-10")])
        self.assertTrue(result.valid)
        self.assertEqual(result.internal_missing_months, 1)
        self.assertEqual(result.units, 2)

    def test_invalid_periods_and_counts(self):
        for period in ("202001", "2020-13", "0000-01", "2020-00"):
            with self.subTest(period=period):
                self.assertIn("invalid_period", self.codes(self.write([self.record(period=period)])))
        for value in ("-1", "1.5", "NaN", "inf", "1e3", "1,000", "9" * 19):
            with self.subTest(value=value):
                self.assertFalse(self.write([self.record(confirmed_cases=value)]).valid)

    def test_optional_reporting_is_unknown_not_complete(self):
        row = {name: self.record()[name] for name in REQUIRED}
        result = self.write([row], REQUIRED)
        self.assertTrue(result.valid)
        warnings = [item for item in result.issues if item.code == "unknown_reporting"]
        self.assertEqual(len(warnings), 3)

    def test_reporting_constraints_even_with_intermediate_measure_missing(self):
        for changes in ({"reports_received": "11"}, {"reports_on_time": "10"},
                        {"reports_received": "", "reports_on_time": "11"}):
            with self.subTest(changes=changes):
                self.assertIn("reporting_order", self.codes(self.write([self.record(**changes)])))
        self.assertIn("invalid_population", self.codes(self.write([self.record(population="0")])))

    def test_schema_and_empty_data_errors(self):
        for content, code in (("", "empty_file"), (",".join(REQUIRED) + "\n", "no_observations"),
                              ("org_unit_id,period\n", "missing_columns"),
                              (",".join((*REQUIRED, "confirmed_cases")) + "\n", "duplicate_columns"),
                              (",".join((*REQUIRED, "unexpected")) + "\n", "unknown_columns"),
                              (",".join(REQUIRED) + "\nonly,two\n", "row_width")):
            with self.subTest(code=code):
                self.path.write_text(content, encoding="utf-8")
                self.assertIn(code, self.codes(validate_monthly_cases(self.path)))

    def test_blank_identity_and_unreadable_input(self):
        self.assertIn("missing_identity", self.codes(self.write([self.record(org_unit_id=" ")])))
        self.assertIn("unreadable_csv", self.codes(validate_monthly_cases(self.path.parent / "absent.csv")))

    def test_cli_exit_codes_json_and_overwrite_protection(self):
        self.write([self.record()])
        report = self.path.parent / "results" / "summary.json"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.path), "--report", str(report)]), 0)
        self.assertTrue(json.loads(report.read_text())["valid"])
        with self.assertRaises(SystemExit) as stopped:
            with redirect_stdout(io.StringIO()), patch("sys.stderr", new_callable=io.StringIO):
                main([str(self.path), "--report", str(self.path)])
        self.assertEqual(stopped.exception.code, 2)
        self.write([])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main([str(self.path)]), 1)


if __name__ == "__main__":
    unittest.main()
