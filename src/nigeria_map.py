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


def locator_point(geometry):
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    polygon = max(polygons, key=lambda rings: abs(sum(
        a[0] * b[1] - b[0] * a[1] for a, b in zip(rings[0], rings[0][1:])
    )))
    latitudes = [point[1] for point in polygon[0]]
    latitude = (min(latitudes) + max(latitudes)) / 2
    # Pair crossings through the polygon and its holes, then use the widest interior interval.
    crossings = sorted(
        a[0] + (b[0] - a[0]) * (latitude - a[1]) / (b[1] - a[1])
        for ring in polygon for a, b in zip(ring, ring[1:])
        if (a[1] > latitude) != (b[1] > latitude)
    )
    west, east = max(zip(crossings[::2], crossings[1::2]), key=lambda pair: pair[1] - pair[0])
    return [(west + east) / 2, latitude]


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
    picked = alt.selection_point(name="picked_lga", fields=["id"], toggle=False, clear=False)
    is_selected = f"datum.id === {json.dumps(selected)}"
    # Draw the selected outline last so adjacent polygons cannot cover it.
    features.sort(key=lambda feature: feature["id"] == selected)
    if selected in boundaries:
        features.append({
            **features[-1],
            "geometry": {"type": "Point", "coordinates": locator_point(boundaries[selected])},
        })
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
                fillOpacity=alt.condition("datum.geometry.type === 'Point'", alt.value(0), alt.value(1)),
                stroke=alt.condition(is_selected, alt.value("#d81b60"), alt.value("#f1f4f8")),
                strokeWidth=alt.condition(is_selected, alt.value(3), alt.value(0.45)),
                tooltip=[alt.Tooltip("properties.lga:N", title="LGA"),
                         alt.Tooltip("properties.state:N", title="State or FCT"),
                         alt.Tooltip("properties.display:N", title=metric)],
            )
            .add_params(picked)
            .project(type="mercator")
            .properties(width="container", description="Nigeria map of monthly values by LGA")
            .configure_view(stroke=None))
