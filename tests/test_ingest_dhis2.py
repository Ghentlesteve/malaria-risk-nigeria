"""Invented observations test export mapping, not malaria model performance."""

import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from src.ingest_dhis2 import MONTHS, case_count, load_exports, month_period, prepare


class Dhis2IngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root / "raw"
        self.raw.mkdir()

    def export(self, year, units=("001",), long=False, override=None, months=MONTHS):
        headings = [f"{m} {year}" if long else f"{m[:3]}-{year % 100:02d}" for m in months]
        fields = ["orgunitlevel1", "orgunitlevel2", "orgunitlevel3", "organisationunitid", *headings]
        path = self.raw / f"malaria_confirmed_lga_monthly_{year}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for unit in units:
                row = dict(zip(fields[:4], ("Country", "State", f"Unit {unit} Local Government Area", unit)))
                row.update({column: "5.0" if long else "5" for column in headings})
                row[headings[0]] = ""
                row[headings[1]] = "0"
                row.update(override or {})
                writer.writerow(row)
        return path

    def test_months_map_without_locale_or_century_guessing(self):
        self.assertEqual(month_period("January 2020", 2020), "2020-01")
        self.assertEqual(month_period("Dec-25", 2025), "2025-12")
        for name in ("Total", "Jan-24", "202501"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                month_period(name, 2025)

    def test_counts_preserve_missing_and_zero_and_reject_rounding(self):
        for text, expected in (("", ""), (" ", ""), ("0.0", "0"), ("68.0", "68")):
            self.assertEqual(case_count(text), expected)
        for text in ("3.5", "-2", "NaN", "inf", "1e3", "1,000"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                case_count(text)

    def test_combined_years_reconcile_and_sources_remain_identical(self):
        self.export(2020, long=True)
        self.export(2021, units=("001", "002"))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.raw.glob("*.csv")}
        output = self.root / "processed"
        summary = prepare(self.raw, output)
        self.assertTrue(summary["schema_validation"]["valid"])
        self.assertEqual(summary["schema_validation"]["rows"], 36)
        self.assertEqual(summary["schema_validation"]["missing_cases"], 3)
        self.assertEqual(summary["coverage"][0]["absent_unit_months_vs_union_roster"], 12)
        self.assertEqual(summary["coverage"][0]["reported_case_sum"], 50)
        with (output / "monthly_cases.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["org_unit_id"], "001")
        self.assertTrue(all(row["reports_received"] == "" for row in rows))
        for path, digest in before.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_duplicate_units_are_rejected_instead_of_summed(self):
        path = self.export(2025, units=("001", "001"))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            load_exports([path])

    def test_latest_partial_year_audits_only_exported_months(self):
        self.export(2025, units=("001", "002"))
        self.export(2026, months=MONTHS[:10])
        output = self.root / "processed"
        summary = prepare(self.raw, output)
        coverage = summary["coverage"][-1]
        self.assertEqual(coverage["exported_unit_months"], 10)
        self.assertEqual(coverage["absent_unit_months_vs_union_roster"], 10)
        self.assertEqual(summary["source_files"][-1]["periods"][-1], "2026-10")
        self.assertIn("October 2026", (output / "readiness_report.md").read_text(encoding="utf-8"))

    def test_missing_month_and_historical_partial_year_are_rejected(self):
        path = self.export(2025, months=("January", "March"))
        with self.assertRaisesRegex(ValueError, "consecutive"):
            load_exports([path])
        self.export(2025, months=MONTHS[:10])
        newer = self.export(2026)
        with self.assertRaisesRegex(ValueError, "Only the latest"):
            load_exports([path, newer])

    def test_identity_changes_and_non_lga_rows_require_review(self):
        a = self.export(2020)
        b = self.export(2021, override={"orgunitlevel2": "Other state"})
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            load_exports([a, b])
        b = self.export(2021, override={"orgunitlevel3": "Cold store"})
        with self.assertRaisesRegex(ValueError, "Unrecognised"):
            load_exports([b])

    def test_wrong_header_year_and_fractional_cases_fail(self):
        path = self.export(2020, override={"Jan-20": "1.5"})
        with self.assertRaisesRegex(ValueError, "Invalid cases"):
            load_exports([path])
        path = self.export(2020)
        changed = path.with_name("malaria_confirmed_lga_monthly_2021.csv")
        path.rename(changed)
        with self.assertRaisesRegex(ValueError, "Column year"):
            load_exports([changed])

    def test_raw_directory_cannot_be_output(self):
        self.export(2025)
        for output in (self.raw, self.raw / "nested"):
            with self.assertRaisesRegex(ValueError, "separate output"):
                prepare(self.raw, output)


if __name__ == "__main__":
    unittest.main()
