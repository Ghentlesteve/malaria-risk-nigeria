"""Synthetic geometry/raster tests; no routine health data or network required."""

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from src.climate_data import audit_boundaries, digest, download_chirps, load_polygons, periods

SPATIAL = all(importlib.util.find_spec(name) is not None for name in ("numpy", "shapely", "rasterio", "pyproj"))


class ClimateAcquisitionTests(unittest.TestCase):
    def test_month_span_is_inclusive_and_validated(self):
        self.assertEqual(periods("2019-12", "2020-02"), ["2019-12", "2020-01", "2020-02"])
        self.assertEqual(len(periods("2019-01", "2025-12")), 84)
        for start, end in (("2025-13", "2025-13"), ("2025-02", "2025-01"), ("0000-01", "2025-01")):
            with self.subTest(start=start), self.assertRaises(ValueError):
                periods(start, end)

    def test_download_cache_requires_matching_source_and_hash(self):
        from src.climate_data import CHIRPS_ROOT
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            path = folder / "chirps-v3.0.2025.01.tif"
            path.write_bytes(b"II*\x00test")
            sidecar = folder / (path.name + ".json")
            sidecar.write_text(json.dumps({"url": f"{CHIRPS_ROOT}/{path.name}", "sha256": digest(path)}))
            self.assertEqual(download_chirps("2025-01", folder)["sha256"], digest(path))
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "mismatch"):
                download_chirps("2025-01", folder)


@unittest.skipUnless(SPATIAL, "Use the requirements-climate environment for spatial tests.")
class ClimateSpatialTests(unittest.TestCase):
    def setUp(self):
        from shapely.geometry import box, mapping
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.boundaries = self.root / "boundaries.geojson"
        self.feature = {"type": "Feature", "id": "001", "properties": {"name": "Test LGA"},
                        "geometry": mapping(box(0.5, 0, 2, 1))}
        self.save([self.feature])
        self.cases = self.root / "cases.csv"
        self.cases.write_text("org_unit_id\n001\n001\n", encoding="utf-8")

    def save(self, features):
        self.boundaries.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")

    def test_matching_ids_and_missing_or_extra_geometry(self):
        self.assertTrue(audit_boundaries(self.boundaries, self.cases)["exact_roster_match"])
        self.cases.write_text("org_unit_id\n002\n", encoding="utf-8")
        audit = audit_boundaries(self.boundaries, self.cases)
        self.assertEqual(audit["missing_boundary_ids"], ["002"])
        self.assertEqual(audit["extra_boundary_ids"], ["001"])

    def test_overlap_blocks_aggregation_even_when_ids_match(self):
        from shapely.geometry import box, mapping
        from src.climate_data import aggregate_rainfall

        other = {**self.feature, "id": "002", "geometry": mapping(box(1, 0, 3, 1))}
        self.save([self.feature, other])
        self.cases.write_text("org_unit_id\n001\n002\n", encoding="utf-8")
        audit = audit_boundaries(self.boundaries, self.cases)
        self.assertTrue(audit["exact_roster_match"])
        self.assertEqual(audit["overlaps_above_one_percent"][0]["ids"], ["001", "002"])
        with self.assertRaisesRegex(ValueError, "overlaps exceed"):
            aggregate_rainfall(self.boundaries, self.cases, "2025-01", "2025-01",
                               self.root, self.root / "rain.csv")

    def test_points_empty_invalid_geometry_and_duplicate_ids_fail(self):
        cases = [
            [{**self.feature, "geometry": {"type": "Point", "coordinates": [1, 1]}}],
            [{**self.feature, "geometry": None}],
            [{**self.feature, "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]}}],
            [self.feature, self.feature],
            [],
        ]
        for features in cases:
            with self.subTest(features=features), self.assertRaises(ValueError):
                self.save(features)
                load_polygons(self.boundaries)

    def test_partial_pixel_area_weighted_mean_and_zero_preserved(self):
        import numpy as np
        from rasterio.io import MemoryFile
        from rasterio.transform import from_origin
        from src.climate_data import polygon_weights, rainfall_value
        features = load_polygons(self.boundaries)
        with MemoryFile() as memory:
            with memory.open(driver="GTiff", width=2, height=1, count=1, dtype="float32",
                             crs="EPSG:4326", transform=from_origin(0, 1, 1, 1)) as src:
                src.write(np.array([[10, 30]], dtype="float32"), 1)
                total, cells = polygon_weights(src, features)["001"]
                value, coverage, status = rainfall_value(src.read(1, masked=True), total, cells)
                self.assertAlmostEqual(value, 70 / 3, places=5)
                self.assertAlmostEqual(coverage, 1.0, places=5)
                self.assertEqual(status, "ok")
                value, _, status = rainfall_value(np.zeros((1, 2)), total, cells)
                self.assertEqual((value, status), (0, "ok"))
                masked = np.ma.array([[10.0, 30.0]], mask=[[False, True]])
                value, fraction, status = rainfall_value(masked, total, cells)
                self.assertEqual(value, "")
                self.assertLess(fraction, 0.34)
                self.assertEqual(status, "insufficient_valid_area")

    def test_aggregation_provenance_and_missing_roster_guard(self):
        import numpy as np
        import rasterio
        from rasterio.transform import from_origin
        from src.climate_data import aggregate_rainfall
        path = self.root / "chirps-v3.0.2025.01.tif"
        with rasterio.open(path, "w", driver="GTiff", width=2, height=1, count=1, dtype="float32",
                           crs="EPSG:4326", transform=from_origin(0, 1, 1, 1)) as src:
            src.write(np.array([[10, 30]], dtype="float32"), 1)
        path.with_suffix(".tif.json").write_text(json.dumps({"period": "2025-01", "sha256": digest(path)}))
        output = self.root / "rain.csv"
        result = aggregate_rainfall(self.boundaries, self.cases, "2025-01", "2025-01", self.root, output)
        self.assertEqual(result["rows"], 1)
        with output.open(newline="") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual((row["org_unit_id"], row["period"]), ("001", "2025-01"))
        self.assertAlmostEqual(float(row["rainfall_mm"]), 70 / 3, places=5)
        self.assertTrue(output.with_suffix(".json").exists())
        self.cases.write_text("org_unit_id\n002\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "roster"):
            aggregate_rainfall(self.boundaries, self.cases, "2025-01", "2025-01", self.root, output)


if __name__ == "__main__":
    unittest.main()
