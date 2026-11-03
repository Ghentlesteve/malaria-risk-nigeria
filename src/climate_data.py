"""Acquire CHIRPS v3 monthly rainfall and check DHIS2 LGA polygons.

Use the separate requirements-climate environment for spatial commands.
CHIRPS monthly rasters already contain monthly totals in millimetres.
"""

import argparse
import csv
import hashlib
import json
import math
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CHIRPS_ROOT = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs"


def periods(start, end):
    def index(text):
        if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", text) or text[:4] == "0000":
            raise ValueError("Periods must be YYYY-MM.")
        year, month = map(int, text.split("-"))
        return year * 12 + month - 1
    first, last = index(start), index(end)
    if first > last:
        raise ValueError("Start month must precede end month.")
    return [f"{i // 12:04d}-{i % 12 + 1:02d}" for i in range(first, last + 1)]


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def download_chirps(period, folder):
    periods(period, period)
    year, month = period.split("-")
    name = f"chirps-v3.0.{year}.{month}.tif"
    url = f"{CHIRPS_ROOT}/{name}"
    folder.mkdir(parents=True, exist_ok=True)
    target, metadata = folder / name, folder / (name + ".json")
    if target.exists():
        if not metadata.exists():
            raise ValueError(f"Existing raster has no provenance sidecar: {name}")
        saved = json.loads(metadata.read_text(encoding="utf-8"))
        if saved.get("url") != url or saved.get("sha256") != digest(target):
            raise ValueError(f"Cached raster/provenance mismatch: {name}")
        return saved
    partial = target.with_suffix(".tif.part")
    request = urllib.request.Request(url, headers={"User-Agent": "malaria-risk-nigeria-climate/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        expected_size = response.headers.get("Content-Length")
        with partial.open("wb") as handle:
            while block := response.read(1024 * 1024):
                handle.write(block)
        modified = response.headers.get("Last-Modified")
    if expected_size and partial.stat().st_size != int(expected_size):
        raise ValueError(f"Incomplete download: {name}; rerun to retry.")
    with partial.open("rb") as handle:
        if handle.read(4) not in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
            raise ValueError(f"Response is not a TIFF: {name}")
    # A sidecar and hash identify the exact final-product file used, including later revisions.
    result = {"dataset": "CHIRPS", "version": "3.0", "product": "monthly final, Africa",
              "period": period, "units": "mm/month", "url": url,
              "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
              "last_modified": modified, "sha256": digest(partial), "bytes": partial.stat().st_size}
    partial.replace(target)
    write_json(metadata, result)
    return result


def load_polygons(path):
    from shapely.geometry import shape
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise ValueError("Expected a GeoJSON FeatureCollection.")
    if data.get("crs"):
        crs = data["crs"].get("properties", {}).get("name", "")
        if crs not in ("EPSG:4326", "urn:ogc:def:crs:OGC:1.3:CRS84", "urn:ogc:def:crs:EPSG::4326"):
            raise ValueError("Reproject the GeoJSON to WGS84 longitude/latitude first.")
    features, ids = [], set()
    for feature in data["features"]:
        props = feature.get("properties") or {}
        unit = feature.get("id") or props.get("id") or props.get("org_unit_id")
        if not isinstance(unit, str) or not unit.strip() or unit != unit.strip() or unit in ids:
            raise ValueError("Boundary IDs must be unique nonempty text DHIS2 IDs.")
        if feature.get("id") and props.get("id") and feature["id"] != props["id"]:
            raise ValueError("Conflicting top-level and property IDs.")
        geometry = feature.get("geometry")
        if not geometry or geometry.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"Polygon/MultiPolygon required for ID {unit}; do not substitute a point.")
        geom = shape(geometry)
        if geom.is_empty or not geom.is_valid or geom.area <= 0:
            raise ValueError(f"Empty or invalid polygon for ID {unit}; review without automatic repair.")
        if not all(math.isfinite(v) for v in geom.bounds):
            raise ValueError("Nonfinite geometry bounds.")
        west, south, east, north = geom.bounds
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("Geometry is not in WGS84 longitude/latitude.")
        ids.add(unit)
        features.append({"id": unit, "name": props.get("name", ""), "geometry": geom})
    if not features:
        raise ValueError("Boundary file contains no features.")
    return features


def audit_boundaries(boundaries, cases):
    from shapely import STRtree

    features = load_polygons(boundaries)
    with Path(cases).open(encoding="utf-8-sig", newline="") as handle:
        expected = {row["org_unit_id"] for row in csv.DictReader(handle)}
    if not expected or "" in expected:
        raise ValueError("Cases must contain a nonempty DHIS2 ID roster.")
    actual = {f["id"] for f in features}
    polygons = [f["geometry"] for f in features]
    tree = STRtree(polygons)
    overlaps = []
    for i, polygon in enumerate(polygons):
        for j in tree.query(polygon, predicate="intersects"):
            if j <= i:
                continue
            fraction = polygon.intersection(polygons[j]).area / min(polygon.area, polygons[j].area)
            if fraction > 0.01:
                overlaps.append({"ids": [features[i]["id"], features[j]["id"]], "fraction": fraction})
    return {"boundary_sha256": digest(boundaries), "case_table_sha256": digest(cases),
            "expected_case_ids": len(expected), "boundary_ids": len(actual),
            "missing_boundary_ids": sorted(expected - actual), "extra_boundary_ids": sorted(actual - expected),
            "exact_roster_match": expected == actual,
            "overlaps_above_one_percent": overlaps,
            "geometry_check": "Valid polygons in WGS84; overlap screen uses planar longitude/latitude area."}


def polygon_weights(src, features):
    """Intersect native pixels with polygons, measure overlap in equal-area metres."""
    from pyproj import Transformer
    from shapely.geometry import box
    from shapely import transform
    if src.crs is None or src.crs.to_epsg() != 4326 or src.count != 1:
        raise ValueError("Expected one WGS84 raster band.")
    affine = src.transform
    if affine.b != 0 or affine.d != 0 or affine.a <= 0 or affine.e >= 0:
        raise ValueError("Expected an unrotated north-up grid.")
    project = Transformer.from_crs(4326, 6933, always_xy=True).transform
    weights = {}
    for feature in features:
        geom = feature["geometry"]
        west, south, east, north = geom.bounds
        r0, c0 = src.index(west, north)
        r1, c1 = src.index(east, south)
        cells = []
        for row in range(max(0, r0), min(src.height - 1, r1) + 1):
            for col in range(max(0, c0), min(src.width - 1, c1) + 1):
                x0, y0 = affine.c + affine.a * col, affine.f + affine.e * row
                x1, y1 = affine.c + affine.a * (col + 1), affine.f + affine.e * (row + 1)
                clipped = geom.intersection(box(x0, y1, x1, y0))
                if not clipped.is_empty and clipped.area > 0:
                    cells.append((row, col, transform(clipped, project, interleaved=False).area))
        weights[feature["id"]] = (transform(geom, project, interleaved=False).area, cells)
    return weights


def rainfall_value(array, total_area, cells, minimum_coverage=0.999):
    import numpy as np
    area, numerator = 0.0, 0.0
    for row, col, weight in cells:
        value = array[row, col]
        if np.ma.is_masked(value) or not np.isfinite(value) or value < 0:
            continue
        area += weight
        numerator += float(value) * weight
    coverage = min(1.0, area / total_area) if total_area else 0.0
    if area == 0 or coverage < minimum_coverage:
        return "", coverage, "insufficient_valid_area"
    return numerator / area, coverage, "ok"


def aggregate_rainfall(boundaries, cases, start, end, folder, output, minimum_coverage=0.999):
    import rasterio
    if not 0 < minimum_coverage <= 1:
        raise ValueError("Coverage threshold must be in (0, 1].")
    audit = audit_boundaries(boundaries, cases)
    if not audit["exact_roster_match"]:
        raise ValueError("Boundary IDs do not exactly match the case roster; run boundary-audit for details.")
    if audit["overlaps_above_one_percent"]:
        raise ValueError("Boundary overlaps exceed 1% of the smaller polygon; run boundary-audit for details.")
    features = load_polygons(boundaries)
    records, sources, weights, grid = [], [], None, None
    for period in periods(start, end):
        path = folder / f"chirps-v3.0.{period.replace('-', '.')}.tif"
        sidecar = path.with_suffix(".tif.json")
        if not path.exists() or not sidecar.exists():
            raise ValueError(f"Missing raster/provenance for {period}; download first.")
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        if metadata.get("sha256") != digest(path) or metadata.get("period") != period:
            raise ValueError(f"Raster provenance mismatch for {period}.")
        with rasterio.open(path) as src:
            key = (src.width, src.height, tuple(src.transform), str(src.crs))
            if grid is None:
                grid, weights = key, polygon_weights(src, features)
            elif grid != key:
                raise ValueError("Raster grid changed; do not reuse spatial weights.")
            array = src.read(1, masked=True)
            for feature in features:
                total, cells = weights[feature["id"]]
                value, fraction, status = rainfall_value(array, total, cells, minimum_coverage)
                records.append({"org_unit_id": feature["id"], "period": period, "rainfall_mm": value,
                                "valid_area_fraction": fraction, "status": status})
        sources.append(metadata)
    if output.resolve() in (Path(boundaries).resolve(), Path(cases).resolve()):
        raise ValueError("Output must not overwrite inputs.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(records[0]))
        writer.writeheader()
        writer.writerows(records)
    write_json(output.with_suffix(".json"), {"boundary_audit": audit, "source_files": sources,
               "method": "Pixel-polygon intersection areas measured in EPSG:6933, weighted mean rainfall depth.",
               "units": "mm/month", "minimum_valid_area_fraction": minimum_coverage,
               "rows": len(records), "unavailable_rows": sum(r["status"] != "ok" for r in records),
               "output_sha256": digest(output)})
    return {"rows": len(records), "output": str(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    download = commands.add_parser("download-rainfall")
    download.add_argument("--start", required=True)
    download.add_argument("--end", required=True)
    download.add_argument("--folder", type=Path, default=Path("data/raw/climate/chirps_v3"))
    for name in ("boundary-audit", "aggregate-rainfall"):
        command = commands.add_parser(name)
        command.add_argument("--boundaries", type=Path, required=True)
        command.add_argument("--cases", type=Path, default=Path("data/processed/routine/monthly_cases.csv"))
        if name == "aggregate-rainfall":
            command.add_argument("--start", required=True)
            command.add_argument("--end", required=True)
            command.add_argument("--folder", type=Path, default=Path("data/raw/climate/chirps_v3"))
            command.add_argument("--output", type=Path, default=Path("data/processed/climate/rainfall_monthly.csv"))
            command.add_argument("--minimum-coverage", type=float, default=0.999)
    args = parser.parse_args(argv)
    try:
        if args.command == "download-rainfall":
            for period in periods(args.start, args.end):
                result = download_chirps(period, args.folder)
                print(json.dumps({"period": period, "bytes": result["bytes"], "sha256": result["sha256"]}), flush=True)
        elif args.command == "boundary-audit":
            result = audit_boundaries(args.boundaries, args.cases)
            print(json.dumps(result, indent=2))
            return 0 if result["exact_roster_match"] and not result["overlaps_above_one_percent"] else 1
        else:
            print(json.dumps(aggregate_rainfall(args.boundaries, args.cases, args.start, args.end,
                             args.folder, args.output, args.minimum_coverage), indent=2))
    except (ValueError, OSError, KeyError, ImportError) as exc:
        parser.exit(1, f"Climate step failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
