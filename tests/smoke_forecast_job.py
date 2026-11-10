"""Check the hosted forecast runner with invented LGA data."""

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.climate_data import digest
from src.demo_data import generate_demo, write_csv
from src.forecast import run_forecast


class ForecastJobSmokeTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        generate_demo(self.root)
        self.cases = self.root / "features" / "case_rainfall_monthly.csv"
        self.rainfall = self.root / "rainfall.csv"
        self.output = self.root / "output"
        with self.cases.open(encoding="utf-8", newline="") as handle:
            self.rain_rows = [
                {key: row[key] for key in ("org_unit_id", "period", "rainfall_mm")} | {"status": "ok"}
                for row in csv.DictReader(handle)
            ]

    def test_runs_six_months_and_records_cutoffs(self):
        write_csv(self.rainfall, self.rain_rows)
        audit = run_forecast(self.cases, [self.rainfall], self.output, "2025-12", max_horizon=6)
        self.assertEqual(audit["target_months"], [f"2026-{month:02d}" for month in range(1, 7)])
        self.assertEqual((audit["case_cutoff"], audit["rainfall_cutoff"]), ("2025-11", "2025-11"))
        self.assertEqual(audit["rainfall_model_status_counts"], {"ok": 24})
        self.assertEqual(audit["forecast_sha256"], digest(self.output / "forecast_predictions.csv"))

    def test_rejects_stale_rainfall_before_writing_output(self):
        write_csv(self.rainfall, [row for row in self.rain_rows if row["period"] <= "2025-10"])
        with self.assertRaisesRegex(ValueError, "Rainfall through 2025-11"):
            run_forecast(self.cases, [self.rainfall], self.output, "2025-12", max_horizon=6)
        self.assertFalse(self.output.exists())
