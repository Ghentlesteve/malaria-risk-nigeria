"""Local dashboard for observed malaria cases and retrospective forecasts."""

import hashlib
import io
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.demo_data import DEMO_ROOT
from src.guided_questions import (
    BACKTEST_SOURCE, CASE_SOURCE, EXPLANATIONS, FOLLOW_UPS, QUESTIONS, RAIN_SOURCE, REPORT_SOURCE, TOPICS,
    compare_answer, forecast_answer, latest_snapshot_month, month_label, report_detail, series_answer, snapshot_metrics,
)
from src.nigeria_map import MAP_METRICS, load_map_boundaries, map_values, nigeria_map_chart
from src.trend_charts import comparison_chart, monthly_chart_data, seasonal_chart, timeline_chart

DATA = Path(__file__).resolve().parents[1] / "data" / "processed"
MODELS = {
    "seasonal_naive": "Same month last year",
    "case_history": "Case history",
    "case_rainfall": "Case history + rainfall",
}


@st.cache_data
def read_table(path, modified_ns):
    return pd.read_csv(path, dtype={"org_unit_id": str})


@st.cache_data
def read_map_boundaries(path, modified_ns):
    return load_map_boundaries(path)


def table(path):
    if not path.is_file():
        st.error(f"Missing local data file: {path.name}. See the dashboard setup in README.md.")
        st.stop()
    return read_table(path, path.stat().st_mtime_ns)


def display_name(value):
    code, separator, name = value.partition(" ")
    return name if separator and len(code) == 2 and code.islower() else value


def backtest_tables(folder, delay):
    try:
        audit = json.loads((folder / "backtest_audit.json").read_text(encoding="utf-8"))
        if audit["case_delay_months"] != delay or audit["rainfall_delay_months"] != delay:
            raise ValueError("Unexpected input delay")
        tables = []
        for name in ("backtest_predictions.csv", "backtest_metrics.csv"):
            content = (folder / name).read_bytes()
            if hashlib.sha256(content).hexdigest() != audit["output_sha256"][name]:
                raise ValueError(f"Backtest output does not match the audit: {name}")
            tables.append(pd.read_csv(io.BytesIO(content), dtype={"org_unit_id": str}))
        return audit["holdout_year"], *tables
    except (OSError, ValueError, KeyError) as error:
        st.error(f"Backtest files are unavailable or inconsistent. Regenerate the selected run. ({error})")
        st.stop()


def reporting_answer(period, reporting):
    if reporting.empty:
        return "No NHMIS reporting records are available for this LGA."
    month = period or reporting["period"].max()
    records = reporting.loc[reporting["period"].eq(month)]
    if records.empty:
        return f"No NHMIS reporting record is available for this LGA in {month}."
    row = records.iloc[0]
    if row["status"] != "OK":
        return f"Rates for {month} are unavailable. Status: **{row['status']}**."
    return (f"For {month}, completeness was **{row.completeness_pct:.1f}%** and "
            f"timeliness was **{row.timeliness_pct:.1f}%**.\n\n"
            f"{row.reports_received:,.0f} of {row.reports_expected:,.0f} expected reports "
            f"were completed, with {row.reports_on_time:,.0f} completed on time.")


def guided_reply(question, month, unit, other, locations, cases, reporting, backtest_data):
    if question in EXPLANATIONS:
        reply, source = EXPLANATIONS[question]
        return reply, (source,)

    name = ", ".join(locations[unit])
    history = cases.loc[cases["org_unit_id"].eq(unit)].set_index("period")
    records = reporting.loc[reporting["org_unit_id"].eq(unit)]
    title = f"**{name} · {month_label(month)}**"
    if question == "overview":
        reply = "\n".join(f"- {label} · **{value}**" for label, value in snapshot_metrics(history, records, month))
        sources = (CASE_SOURCE, RAIN_SOURCE, REPORT_SOURCE)
    elif question == "data_latest":
        observed = history["confirmed_cases"].dropna()
        reply = (f"**{month_label(observed.index.max())}** is the latest month with a reported count."
                 if not observed.empty else "There are no reported case counts for this LGA.")
        title, sources = f"**{name}**", (CASE_SOURCE,)
    elif question == "data_coverage":
        title = f"**{name}**"
        reply = (f"The dashboard series spans **{month_label(history.index.min())} through "
                 f"{month_label(history.index.max())}**. It contains case counts in "
                 f"**{history['confirmed_cases'].count()} months**.")
        sources = (CASE_SOURCE,)
    elif question.startswith(("case_", "cases_", "rain_")):
        reply = series_answer(question, history, month)
        sources = (RAIN_SOURCE,) if question.startswith("rain_") else (CASE_SOURCE,)
        if question == "rain_recent":
            sources = (CASE_SOURCE, RAIN_SOURCE)
    elif question.startswith("report_"):
        reply = reporting_answer(month, records) if question == "report_rates" else report_detail(question, records, month)
        sources = (REPORT_SOURCE,)
    elif question.startswith("compare_"):
        other_name = ", ".join(locations[other])
        other_history = cases.loc[cases["org_unit_id"].eq(other)].set_index("period")
        other_records = reporting.loc[reporting["org_unit_id"].eq(other)]
        title = (f"**LGA comparison · {month_label(month)}**" if question == "compare_summary"
                 else f"**{name} and {other_name} · {month_label(month)}**")
        if question == "compare_shared":
            title = f"**{name} and {other_name}**"
        reply = compare_answer(question, month, (name, other_name), (history, other_history), (records, other_records))
        sources = {
            "compare_summary": (CASE_SOURCE, RAIN_SOURCE, REPORT_SOURCE),
            "compare_cases": (CASE_SOURCE,), "compare_recent": (CASE_SOURCE,), "compare_rain": (RAIN_SOURCE,),
        }.get(question, (REPORT_SOURCE,))
    else:
        predictions, national, year, horizon, delay = backtest_data
        title = f"**{name} · {year} backtest**"
        reply = forecast_answer(question, month, predictions, national, MODELS)
        reply += f"\n\nSettings · {horizon}-month horizon and {delay}-month assumed input delay."
        sources = (BACKTEST_SOURCE,)
    return f"{title}\n\n{reply}", sources


def floating_assistant(location, unit, locations, cases, reporting, months, snapshot_month, backtest_data, demo):
    st.html("""
        <style>
        .st-key-assistant-launcher {
            position: fixed;
            right: max(1rem, env(safe-area-inset-right));
            bottom: max(1rem, env(safe-area-inset-bottom));
            width: max-content;
            z-index: 100;
        }
        .st-key-assistant-launcher button {
            min-height: 2.75rem;
            border-radius: 999px;
        }
        .st-key-assistant-panel {
            width: min(25rem, calc(100vw - 4rem));
        }
        </style>
    """)
    with st.container(key="assistant-launcher"):
        with st.popover("Ask assistant", type="primary", icon=":material/chat:"):
            with st.container(key="assistant-panel"):
                st.markdown("**Malaria dashboard assistant**")
                st.caption(location)
                if demo:
                    st.caption("Demo figures are synthetic. Source explanations describe the research dashboard.")
                month = st.selectbox("Question month", months, index=months.index(snapshot_month),
                                     format_func=month_label, key=f"guided-month-{unit}")
                state = st.session_state
                topic = state.get("guided-topic")
                page = state.get("guided-page", 0)
                followups = state.get("guided-followups", ())
                active_question = state.get("guided-active-question")
                earlier_replies = state.get("guided-earlier-replies", [])
                is_comparison = active_question is not None and active_question.startswith("compare_")
                other = None
                if topic == "compare" or is_comparison:
                    candidates = sorted((key for key in locations if key != unit), key=locations.get)
                    other = st.selectbox("Compare with", candidates, index=None,
                                         placeholder="Choose an LGA and state",
                                         format_func=lambda key: ", ".join(locations[key]),
                                         key=f"guided-other-{unit}")

                current_reply = None
                if active_question and (not is_comparison or other is not None):
                    reply, sources = guided_reply(active_question, month, unit, other,
                                                  locations, cases, reporting, backtest_data)
                    current_reply = (QUESTIONS[active_question], reply, sources)

                def browse(next_topic=None, next_page=0):
                    state["guided-topic"] = next_topic
                    state["guided-page"] = next_page
                    state["guided-followups"] = ()

                def answer(question):
                    if question.startswith("compare_") and other is None:
                        browse("compare")
                        return
                    if current_reply is not None:
                        state["guided-earlier-replies"] = [*earlier_replies[-6:], current_reply]
                    state["guided-active-question"] = question
                    group = next((name for name, (_, items) in TOPICS.items()
                                  if any(key == question for key, _ in items)), None)
                    browse(group)
                    suggestions = FOLLOW_UPS.get(question)
                    if suggestions is None:
                        items = TOPICS[group][1]
                        start = next(index for index, (key, _) in enumerate(items) if key == question)
                        suggestions = tuple(key for key, _ in (items[start + 1:] + items[:start])[:4])
                    state["guided-followups"] = suggestions

                def start_over():
                    browse()
                    state.pop("guided-active-question", None)
                    state.pop("guided-earlier-replies", None)

                def show_reply(exchange):
                    question, reply, sources = exchange
                    with st.chat_message("assistant"):
                        st.caption(question)
                        st.markdown(reply)
                        st.caption("Demo mode · Synthetic data and project documentation" if demo
                                   else "Sources · " + " · ".join(sources))

                if current_reply is not None:
                    show_reply(current_reply)

                def question_button(key):
                    st.button(QUESTIONS[key], key=f"guided-question-{key}", width="stretch",
                              disabled=topic == "compare" and key.startswith("compare_") and other is None,
                              on_click=answer, args=(key,))

                if followups:
                    st.caption("What would you like to ask next?")
                    for key in followups:
                        question_button(key)
                    if topic:
                        st.button("More questions on this topic", on_click=browse, args=(topic,))
                elif topic:
                    label, items = TOPICS[topic]
                    st.caption(label)
                    for key, _ in items[page:page + 4]:
                        question_button(key)
                    if page + 4 < len(items):
                        st.button("More questions", on_click=browse, args=(topic, page + 4))
                    if page:
                        st.button("Previous questions", on_click=browse, args=(topic, page - 4))
                else:
                    st.caption("Choose a question or topic")
                    question_button("overview")
                    for key, (label, _) in TOPICS.items():
                        st.button(label, key=f"guided-topic-{key}", width="stretch", on_click=browse, args=(key,))
                if topic or followups:
                    st.button("All topics", on_click=browse)
                if active_question:
                    st.button("Start over", on_click=start_over)
                if earlier_replies:
                    with st.expander("Earlier replies"):
                        for exchange in reversed(earlier_replies):
                            show_reply(exchange)


def show_snapshot(history, reporting, month):
    for column, (label, value) in zip(st.columns(4), snapshot_metrics(history, reporting, month)):
        column.metric(label, value, border=True)
    st.caption("Reporting rates describe submission of the NHMIS Monthly Summary Form.")


def show_overview(history, reporting):
    latest_month = latest_snapshot_month(history)
    months = sorted(history.index, reverse=True)
    month = st.selectbox("Snapshot month", months, index=months.index(latest_month),
                         format_func=month_label)
    show_snapshot(history, reporting, month)
    st.info("Forecast backtest shows how models performed on historical data. Live forecasts are planned.")
    return month


def show_comparison(unit, locations, history, reporting, cases, all_reporting):
    st.subheader("Compare LGA trends")
    candidates = sorted((key for key in locations if key != unit), key=locations.get)
    other_unit = st.selectbox("Second LGA", candidates, index=None, placeholder="Choose an LGA and state",
                              format_func=lambda key: ", ".join(locations[key]))
    if other_unit is None:
        st.info("Choose a second LGA to compare with the LGA selected in the sidebar.")
        return

    other_history = cases.loc[cases["org_unit_id"].eq(other_unit)].set_index("period")
    other_reporting = all_reporting.loc[all_reporting["org_unit_id"].eq(other_unit)]
    start = min(history.index.min(), other_history.index.min())
    end = max(history.index.max(), other_history.index.max())
    periods = pd.period_range(start, end, freq="M").astype(str).tolist()
    if len(periods) > 1:
        start, end = st.select_slider("Comparison date range", options=periods, value=(start, end),
                                      format_func=month_label)
    months = pd.period_range(start, end, freq="M").astype(str)
    first = monthly_chart_data(history.reindex(months), reporting)
    second = monthly_chart_data(other_history.reindex(months), other_reporting)
    names = [f"{name.removesuffix(' Local Government Area')}, {state}"
             for name, state in (locations[unit], locations[other_unit])]
    st.caption("Hover over a month to see both LGAs’ values. Gaps indicate unavailable data.")
    st.altair_chart(comparison_chart(first, second, *names), width="stretch")
    st.caption("Case counts reflect reported confirmed cases. Reporting completeness measures submission of the "
               "NHMIS Monthly Summary Form.")


@st.fragment
def show_nigeria_map(cases, reporting, locations, sidebar_unit, path, demo):
    st.subheader("Demo map" if demo else "Nigeria map")
    if not path.is_file():
        st.info("Run `python -m src.demo_data` to generate the fictional boundaries." if demo else
                "The map needs the matched LGA boundaries. Run the boundary preparation step in the project guide.")
        return
    try:
        boundaries = read_map_boundaries(path, path.stat().st_mtime_ns)
        if boundaries.keys() != locations.keys():
            raise ValueError("Boundary IDs differ from the dashboard LGA list.")
    except (OSError, ValueError, KeyError, TypeError):
        st.warning("The map boundaries could not be loaded. Rebuild the matched LGA boundaries and try again.")
        return

    first, second = st.columns(2)
    month = first.selectbox("Map month", sorted(cases["period"].unique(), reverse=True), format_func=month_label)
    metric = second.selectbox("Map measure", list(MAP_METRICS))
    values = map_values(cases, reporting, month, metric)
    if st.session_state.get("map-sidebar-lga") != sidebar_unit:
        st.session_state["map-sidebar-lga"] = sidebar_unit
        st.session_state["map-selected-lga"] = sidebar_unit
    selected = st.session_state["map-selected-lga"]
    chart_key = f"nigeria-map-{sidebar_unit}"

    def update_map_selection():
        selection = st.session_state[chart_key].selection.get("picked_lga", [])
        if selection and selection[0].get("id") in locations:
            st.session_state["map-selected-lga"] = selection[0]["id"]

    name, state = locations[selected]
    st.caption(f"The pink outline shows {name}, {state}. Click an LGA to see its overview below. "
               "Grey areas have unavailable values.")
    if not values:
        st.info("This measure has no available values for the selected month.")
    st.altair_chart(nigeria_map_chart(boundaries, locations, values, metric, selected), width="stretch",
                    height=530, key=chart_key, on_select=update_map_selection, selection_mode="picked_lga")
    st.caption("Boundaries · Fictional shapes for the demo." if demo else
               "Boundaries · UN OCHA Nigeria ADM2 matched to DHIS2 organisation units.")

    st.markdown(f"**{name}, {state} · {month_label(month)}**")
    history = cases.loc[cases["org_unit_id"].eq(selected)].set_index("period")
    records = reporting.loc[reporting["org_unit_id"].eq(selected)]
    show_snapshot(history, records, month)


def main():
    demo = os.environ.get("MALARIA_DASHBOARD_DEMO") == "1"
    data_dir = DEMO_ROOT if demo else DATA
    st.set_page_config(page_title="Nigeria Malaria Forecasting", layout="wide")
    st.title("Nigeria Malaria Forecasting")
    if demo:
        st.warning("Synthetic demo. Locations, boundaries, figures, and forecasts are fictional.")
        if not (data_dir / "features" / "case_rainfall_monthly.csv").is_file():
            st.info("Run `python -m src.demo_data` to generate the demo files, then reload the dashboard.")
            st.stop()
    else:
        st.caption("Monthly malaria cases, rainfall, reporting quality, and forecast evaluation across Nigeria")

    cases = table(data_dir / "features" / "case_rainfall_monthly.csv")
    roster = cases[["org_unit_id", "org_unit_name", "state"]].drop_duplicates("org_unit_id")
    locations = {uid: (display_name(unit_name), display_name(state))
                 for uid, unit_name, state in roster.itertuples(index=False, name=None)}
    state = st.sidebar.selectbox("State or FCT", sorted(cases["state"].unique()), format_func=display_name)
    units = roster.loc[roster["state"].eq(state)].sort_values("org_unit_name").set_index("org_unit_id")
    unit = st.sidebar.selectbox("LGA", units.index.tolist(),
                                format_func=lambda uid: display_name(units.at[uid, "org_unit_name"]))
    history = cases.loc[cases["org_unit_id"].eq(unit)].sort_values("period").set_index("period")
    history = history.reindex(pd.period_range(history.index.min(), history.index.max(), freq="M").astype(str))
    location = f"{display_name(units.at[unit, 'org_unit_name'])}, {display_name(state)}"
    st.subheader(location)

    reporting_path = data_dir / "routine" / "nhmis_reporting_monthly.csv"
    all_reporting = pd.DataFrame(columns=["org_unit_id", "period"])
    if reporting_path.is_file():
        all_reporting = table(reporting_path)
    reporting = all_reporting.loc[all_reporting["org_unit_id"].eq(unit)].sort_values("period")

    overview, trends, comparison, nigeria_map, backtest = st.tabs(
        ["Overview", "Case and rainfall trends", "LGA comparison", "Demo map" if demo else "Nigeria map",
         "Forecast backtest"]
    )
    with overview:
        snapshot_month = show_overview(history, reporting)
    with trends:
        st.subheader("Trends explorer")
        periods = history.index.tolist()
        start, end = periods[0], periods[-1]
        if len(periods) > 1:
            start, end = st.select_slider("Date range", options=periods, value=(start, end), format_func=month_label)
        selected_history = history.loc[start:end]
        data = monthly_chart_data(selected_history, reporting)
        first, second = st.columns(2)
        first.metric("Months with case counts", int(selected_history["confirmed_cases"].count()))
        second.metric("Months without a case count", int(selected_history["confirmed_cases"].isna().sum()))
        st.caption("Hover over any month to see cases, rainfall, and completeness together. Gaps indicate unavailable values.")
        st.altair_chart(timeline_chart(data), width="stretch")
        st.subheader("Seasonal heatmap")
        measure = st.radio("Heatmap measure", ["Reported cases", "Rainfall"], horizontal=True)
        field = "confirmed_cases" if measure == "Reported cases" else "rainfall_mm"
        heatmap_height = max(180, 100 + 34 * data["year"].nunique())
        st.altair_chart(seasonal_chart(data, field), width="stretch", height=heatmap_height)
        st.caption("Darker cells show higher values. Grey cells indicate missing data. Blank cells fall outside the selected range.")
        with st.expander("Data quality"):
            st.caption("NHMIS Monthly Summary Form. Rates describe completion of the whole form. "
                       "Blank case counts indicate missing values.")
            if reporting_path.is_file():
                if reporting.empty:
                    st.write("Reporting measures are unavailable for this LGA.")
                else:
                    st.caption(f"Reporting data available from {reporting.period.min()} through "
                               f"{reporting.period.max()}. Both rates use expected reports as the denominator.")
                    st.dataframe(reporting.drop(columns="org_unit_id").round(1).rename(columns={
                        "period": "Month", "reports_expected": "Expected", "reports_received": "Completed",
                        "reports_on_time": "On time", "completeness_pct": "Completeness (%)",
                        "timeliness_pct": "Timeliness (%)", "status": "Status",
                    }), hide_index=True)
                    if reporting["status"].ne("OK").any():
                        st.caption("Rates are blank for months with missing or inconsistent counts or no expected reports.")
            else:
                st.write("Reporting completeness and timeliness are unavailable for these records.")

    with comparison:
        show_comparison(unit, locations, history, reporting, cases, all_reporting)

    with nigeria_map:
        boundary_file = "demo_lga_boundaries.geojson" if demo else "nigeria_lga_boundaries_ocha_matched.geojson"
        show_nigeria_map(cases, all_reporting, locations, unit, data_dir / "climate" / boundary_file, demo)

    with backtest:
        first, second = st.columns(2)
        horizon = first.radio("Forecast horizon (months)", [1, 2], horizontal=True)
        delay = second.radio("Assumed input delay (months)", [1, 2], horizontal=True)
        folder = data_dir / "forecast"
        if delay == 2:
            folder = folder / "delay2"
        year, predictions, scores = backtest_tables(folder, delay)
        filtered = predictions.loc[predictions["org_unit_id"].eq(unit)
                                   & predictions["horizon_months"].eq(horizon)]
        local_mae = filtered[list(MODELS)].sub(filtered["confirmed_cases"], axis=0).abs().mean()
        st.caption("The demo uses simulated estimates to illustrate backtest charts and settings." if demo else
                   f"Forecasts were evaluated retrospectively on {year} case counts. The input delays are assumptions. "
                   "Prediction intervals have yet to be estimated.")
        if filtered.empty:
            st.info("This LGA has no scored targets for the selected scenario.")
        else:
            plot = (filtered.set_index("period")[["confirmed_cases", *MODELS]]
                    .rename(columns={"confirmed_cases": "Reported cases", **MODELS})
                    .reindex(pd.period_range(f"{year}-01", f"{year}-12", freq="M").astype(str)))
            st.line_chart(plot)
            local = pd.DataFrame({"Model": local_mae.index.map(MODELS),
                                  "LGA MAE": local_mae.round(1).to_numpy()})
            st.markdown(f"**LGA errors across {len(filtered)} scored months**")
            st.dataframe(local, hide_index=True)
        national = scores.loc[scores["horizon_months"].eq(horizon), ["model", "rows", "mae", "mean_bias"]].copy()
        displayed_scores = national.assign(model=national["model"].map(MODELS))
        st.markdown("**Backtest errors across demo LGAs**" if demo else "**Nationwide backtest errors**")
        st.dataframe(displayed_scores.round(1).rename(columns={"model": "Model", "rows": "Scored LGA-months",
                                                        "mae": "MAE", "mean_bias": "Mean bias"}),
                     hide_index=True)
        st.caption("MAE is the average absolute error in cases per LGA-month. Negative bias means the model "
                   "predicted fewer cases than were reported, on average.")

    floating_assistant(location, unit, locations, cases, all_reporting, history.index.tolist(), snapshot_month,
                       (filtered, national, year, horizon, delay), demo)


if __name__ == "__main__":
    main()
