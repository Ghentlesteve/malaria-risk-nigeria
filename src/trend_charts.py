"""Charts for comparing monthly dashboard measures and seasonal patterns."""

from calendar import month_abbr

import altair as alt
import pandas as pd

METRICS = {
    "confirmed_cases": ("Reported cases", ",.0f", "", "#de6577"),
    "rainfall_mm": ("Rainfall (mm)", ",.1f", " mm", "#418fda"),
    "completeness_pct": ("Completeness (%)", ".1f", "%", "#2ba486"),
}


def monthly_chart_data(history, reporting):
    """Align the three measures to the same LGA-months and preserve gaps."""
    data = history[["confirmed_cases", "rainfall_mm"]].copy()
    data["completeness_pct"] = float("nan")
    if not reporting.empty:
        rates = reporting.loc[reporting["status"].eq("OK")].set_index("period")["completeness_pct"]
        data["completeness_pct"] = rates
    data.index.name = "period"
    data = data.reset_index()
    calendar = pd.PeriodIndex(data["period"], freq="M")
    data["month_name"] = calendar.strftime("%B %Y")
    data["month"] = calendar.strftime("%b")
    data["year"] = calendar.strftime("%Y")
    for field, (_, spec, suffix, _) in METRICS.items():
        data[f"{field}_label"] = data[field].map(
            lambda value: f"{value:{spec}}{suffix}" if pd.notna(value) else "Unavailable"
        )
    return data


def timeline_chart(data):
    tooltip = [alt.Tooltip("month_name:N", title="Month")]
    tooltip.extend(alt.Tooltip(f"{field}_label:N", title=label) for field, (label, *_) in METRICS.items())
    return _monthly_timeline(data, data, dict.fromkeys(METRICS, tooltip))


def comparison_chart(first, second, first_name, second_name):
    """Overlay two LGAs using one time and value scale per measure."""
    labels = [first_name, second_name]
    series = pd.concat([first.assign(lga=first_name), second.assign(lga=second_name)], ignore_index=True)
    hover_data = first[["period", "month_name"]].copy()
    second_by_month = second.set_index("period")
    tooltips = {}
    for field in METRICS:
        hover_data["first_" + field] = first[f"{field}_label"]
        hover_data["second_" + field] = hover_data["period"].map(second_by_month[f"{field}_label"])
        tooltips[field] = [
            alt.Tooltip("month_name:N", title="Month"),
            alt.Tooltip(f"first_{field}:N", title=first_name),
            alt.Tooltip(f"second_{field}:N", title=second_name),
        ]
    return _monthly_timeline(series, hover_data, tooltips, labels)


def _monthly_timeline(data, hover_data, tooltips, series_labels=None):
    periods = hover_data["period"].tolist()
    tick_step = max(1, (len(periods) + 8) // 9)
    panels = []
    for field, (label, _, _, color) in METRICS.items():
        is_reporting = field == "completeness_pct"
        axis = alt.Axis(title=None, values=periods[::tick_step], labelAngle=0) if is_reporting else None
        month = alt.X("period:O", sort=periods, scale=alt.Scale(type="band"), axis=axis)
        scale = alt.Scale(domain=[0, 100]) if is_reporting else alt.Scale(zero=True)
        line = alt.Chart(data).mark_line(point=alt.OverlayMarkDef(filled=True, size=24),
                                         invalid="break-paths-show-path-domains").encode(
            x=month,
            y=alt.Y(f"{field}:Q", title=label, scale=scale),
        )
        if series_labels:
            legend = alt.Legend(orient="top", labelLimit=320)
            line = line.encode(
                color=alt.Color("lga:N", title=None, legend=legend,
                                scale=alt.Scale(domain=series_labels, range=["#418fda", "#d88427"])),
                strokeDash=alt.StrokeDash("lga:N", title=None, legend=legend,
                                          scale=alt.Scale(domain=series_labels, range=[[1, 0], [5, 3]])),
            )
        else:
            line = line.encode(color=alt.value(color))
        hover = alt.Chart(hover_data).mark_rect(opacity=0.001).encode(x=month, tooltip=tooltips[field])
        panels.append((line + hover).properties(width="container", height=105))
    return (alt.vconcat(*panels, spacing=13).resolve_scale(x="shared", color="shared", strokeDash="shared")
            .configure_view(stroke=None))


def seasonal_chart(data, field):
    label = METRICS[field][0]
    tooltip = [alt.Tooltip("month_name:N", title="Month"), alt.Tooltip(f"{field}_label:N", title=label)]
    base = alt.Chart(data).mark_rect(cornerRadius=2).encode(
        x=alt.X("month:O", sort=list(month_abbr)[1:], title=None,
                scale=alt.Scale(domain=list(month_abbr)[1:], paddingInner=0.08), axis=alt.Axis(labelAngle=0)),
        y=alt.Y("year:O", sort="descending", title=None, scale=alt.Scale(paddingInner=0.12),
                axis=alt.Axis(labelOverlap=False)),
        tooltip=tooltip,
    )
    missing = base.transform_filter(f"!isValid(datum.{field})").encode(color=alt.value("#8b949e"))
    present = base.transform_filter(f"isValid(datum.{field})").encode(
        color=alt.Color(f"{field}:Q", title=label,
                        scale=alt.Scale(scheme="blues" if field == "rainfall_mm" else "oranges", zero=True),
                        legend=alt.Legend(orient="bottom")),
    )
    return (missing + present).properties(width="container").configure_view(stroke=None)
