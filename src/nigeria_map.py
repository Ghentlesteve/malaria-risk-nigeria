"""Render the matched Nigeria LGA boundaries with monthly dashboard measures."""

import json
from base64 import b64encode

import altair as alt
import pandas as pd

MAP_METRICS = {
    "Reported cases": ("confirmed_cases", ",.0f", "", "oranges"),
    "Rainfall (mm)": ("rainfall_mm", ",.1f", " mm", "blues"),
    "Reporting completeness (%)": ("completeness_pct", ".1f", "%", "viridis"),
}


def load_map_boundaries(path):
    """Read display geometry keyed to the same DHIS2 IDs as the dashboard."""
    collection = json.loads(path.read_text(encoding="utf-8-sig"))
    if collection.get("type") != "FeatureCollection":
        raise ValueError("Expected a GeoJSON FeatureCollection.")
    boundaries = {}
    for feature in collection["features"]:
        uid = feature["id"]
        geometry = feature["geometry"]
        kind = geometry["type"]
        if not uid or uid in boundaries or kind not in ("Polygon", "MultiPolygon"):
            raise ValueError("Expected unique LGA IDs and polygon geometries.")
        polygons = [geometry["coordinates"]] if kind == "Polygon" else geometry["coordinates"]
        display_polygons = []
        for polygon in polygons:
            rings = []
            for index, ring in enumerate(polygon):
                # Vega's spherical projection expects clockwise exteriors and counterclockwise holes.
                signed_area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:]))
                oriented = reversed(ring) if (signed_area > 0) == (index == 0) else ring
                rings.append([[round(lon, 5), round(lat, 5)] for lon, lat in oriented])
            display_polygons.append(rings)
        boundaries[uid] = {"type": kind, "coordinates": display_polygons[0] if kind == "Polygon" else display_polygons}
    return boundaries


def map_values(cases, reporting, month, metric):
    field = MAP_METRICS[metric][0]
    if field == "completeness_pct":
        if reporting.empty:
            return {}
        rows = reporting.loc[reporting["period"].eq(month) & reporting["status"].eq("OK")]
    else:
        rows = cases.loc[cases["period"].eq(month)]
    return rows.set_index("org_unit_id")[field].dropna().to_dict()


def nigeria_map_chart(boundaries, locations, values, metric, selected=None):
    field, spec, suffix, scheme = MAP_METRICS[metric]
    features = []
    for uid, geometry in boundaries.items():
        name, state = locations[uid]
        value = values.get(uid)
        features.append({"type": "Feature", "id": uid, "geometry": geometry, "properties": {
            "lga": name, "state": state, "value": value,
            "display": f"{value:{spec}}{suffix}" if pd.notna(value) else "Unavailable",
        }})
    picked = alt.selection_point(name="picked_lga", fields=["id"], toggle=False, empty=False, clear=False,
                                 value=[{"id": selected}] if selected else alt.Undefined)
    scale = alt.Scale(scheme=scheme, domain=[0, 100]) if field == "completeness_pct" else alt.Scale(scheme=scheme, zero=True)
    color = alt.Color("properties.value:Q", title=metric, scale=scale,
                      legend=alt.Legend(orient="bottom"))
    # A local data URL keeps GeoJSON out of Streamlit's tabular Arrow conversion.
    encoded = b64encode(json.dumps(features, separators=(",", ":"), allow_nan=False).encode()).decode("ascii")
    data = alt.UrlData(url="data:application/json;base64," + encoded, format=alt.DataFormat(type="json"))
    return (alt.Chart(data)
            .mark_geoshape(invalid=None, cursor="pointer")
            .encode(
                color=alt.condition("isValid(datum.properties.value)", color, alt.value("#9099a5")),
                stroke=alt.condition(picked, alt.value("#172534"), alt.value("#f1f4f8")),
                strokeWidth=alt.condition(picked, alt.value(2.1), alt.value(0.45)),
                tooltip=[alt.Tooltip("properties.lga:N", title="LGA"),
                         alt.Tooltip("properties.state:N", title="State or FCT"),
                         alt.Tooltip("properties.display:N", title=metric)],
            )
            .add_params(picked)
            .project(type="mercator")
            .properties(width="container", description="Nigeria map of monthly values by LGA")
            .configure_view(stroke=None))
