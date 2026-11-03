"""Build a single-source OCHA polygon layer keyed to the DHIS2 case roster."""

import csv
import json
import re
from pathlib import Path

from shapely.geometry import shape

from src.climate_data import load_polygons, write_json

CONFIRMED = {
    "abia": {"obinwga": "obingwa"},
    "bayelsa": {"yenagoa": "yenegoa"},
    "kogi": {"olamaboro": "olamabolo"},
    "ogun": {"sagamu": "shagamu", "yewanorth": "egbadonorth", "yewasouth": "egbadosouth"},
    "osun": {"ayedaade": "aiyedade", "ayedire": "aiyedire", "ilesaeast": "ileshaeast",
             "ilesawest": "ileshawest"},
    "yobe": {"busari": "bursari"},
}


def key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def main():
    raw = Path("data/raw")
    output = Path("data/processed/climate/nigeria_lga_boundaries_ocha_matched.geojson")
    ocha = json.loads((raw / "nigeria_lga_ocha.geojson").read_text(encoding="utf-8"))["features"]
    dhis = {f["id"]: shape(f["geometry"]) for f in
            json.loads((raw / "nigeria_lga_boundaries.geojson").read_text(encoding="utf-8-sig"))["features"]}
    index = {}
    for feature in ocha:
        p = feature["properties"]
        label = key(p["adm1_en"]), key(p["adm2_en"])
        if label in index:
            raise ValueError(f"Duplicate OCHA label {label}")
        index[label] = feature
    with Path("data/processed/routine/monthly_cases.csv").open(encoding="utf-8", newline="") as handle:
        roster = {r["org_unit_id"]: r for r in csv.DictReader(handle)}
    matched, pending = {}, {}
    for uid, row in roster.items():
        state = key(re.sub(r" state$", "", row["state"][3:], flags=re.I))
        name = key(re.sub(r" (local government area|area council)$", "", row["org_unit_name"][3:], flags=re.I))
        alias = CONFIRMED.get(state, {}).get(name)
        label = state, alias or name
        if label in index:
            matched[uid] = label, "user-confirmed alias" if alias else "normalized name"
        else:
            pending[uid] = state
    used = {label for label, _ in matched.values()}
    if len(used) != len(matched):
        raise ValueError("Multiple DHIS2 IDs map to one OCHA polygon.")
    for uid, state in pending.items():
        reference = dhis.get(uid)
        if reference is None or not reference.is_valid:
            raise ValueError(f"No valid reference polygon for {uid}.")
        candidates = []
        for label in index.keys() - used:
            if label[0] == state:
                polygon = shape(index[label]["geometry"])
                iou = reference.intersection(polygon).area / reference.union(polygon).area
                # After name matching, require substantial overlap with a single unused
                # polygon in the same state. Boundary sources can disagree on the extent.
                if iou >= .40:
                    candidates.append((label, iou))
        if len(candidates) != 1:
            raise ValueError(f"No unique spatial match for {uid}: {candidates}")
        label, iou = candidates[0]
        matched[uid] = label, f"same-state spatial match (IoU {iou:.3f})"
        used.add(label)
    if used != set(index):
        raise ValueError("The case roster and OCHA boundaries do not map one-to-one.")
    features = []
    for uid, (label, method) in sorted(matched.items()):
        original = index[label]
        features.append({"type": "Feature", "id": uid, "geometry": original["geometry"],
                         "properties": {**original["properties"], "name": roster[uid]["org_unit_name"],
                                        "source": "UN OCHA Nigeria ADM2", "match_method": method}})
    write_json(output, {"type": "FeatureCollection", "features": features})
    print(f"Validated {len(load_polygons(output))} polygons. Spatial matches: {len(pending)}.")


if __name__ == "__main__":
    main()
