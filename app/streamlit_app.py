"""Local dashboard for observed malaria cases and retrospective forecasts."""

import hashlib
import io
import json
import os
from pathlib import Path
from string import punctuation

import pandas as pd
import streamlit as st

from src.dashboard_questions import (
    CASE_COUNT, COMPARE_REPORTING, REPORTING, match_dashboard_question, match_named_question, resolve_lga,
)
from src.document_answer import answer_from_documents
from src.document_search import search_documents

DATA = Path(__file__).resolve().parents[1] / "data" / "processed"
MODELS = {
    "seasonal_naive": "Same month last year",
    "case_history": "Case history",
    "case_rainfall": "Case history + rainfall",
}
MARKDOWN_ESCAPES = str.maketrans({character: "\\" + character for character in punctuation})
REPORTING_SOURCE = "NHMIS Monthly Summary Form · Data quality"


@st.cache_data
def read_table(path, modified_ns):
    return pd.read_csv(path, dtype={"org_unit_id": str})


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


def dashboard_answer(question, period, history, reporting, local_mae, scored_months, year, horizon, delay):
    if question == CASE_COUNT:
        observed = history.set_index("period")["confirmed_cases"].dropna()
        if period and period not in observed.index:
            reply = f"No case count is available for this LGA in {period}."
        elif observed.empty:
            reply = "No case counts are available for this LGA."
        else:
            month = period or observed.index.max()
            reply = f"**{observed.at[month]:,.0f} reported confirmed cases** in {month}."
        source = "Monthly NHMIS case export · Case and rainfall trends"
    elif question == REPORTING:
        reply = reporting_answer(period, reporting)
        source = REPORTING_SOURCE
    else:
        if not scored_months:
            reply = "No scored months are available for this LGA under the selected settings."
        else:
            minimum = local_mae.min()
            best = ", ".join(MODELS[name] for name in local_mae.index[local_mae.eq(minimum)])
            reply = (f"**{best}** had the lowest mean absolute error, **{minimum:,.1f} cases per month**, "
                     f"across {scored_months} scored months in {year}.")
        reply += f"\n\nBacktest settings: {horizon}-month horizon, {delay}-month assumed input delay."
        source = "Verified retrospective predictions · Forecast backtest"
    return reply, source


def assistant_reply(query, selected_unit, locations, cases, reporting, backtest_data):
    answer = match_dashboard_question(query)
    units = [selected_unit]
    named = match_named_question(query) if not answer else None
    if named:
        question, period, names = named
        answer = question, period
        roster = [(uid, unit_name, state) for uid, (unit_name, state) in locations.items()]
        try:
            units = [resolve_lga(name, roster) for name in names]
        except ValueError as error:
            return str(error).translate(MARKDOWN_ESCAPES), []
    if answer:
        question, period = answer
        if question == COMPARE_REPORTING:
            if units[0] == units[1]:
                return "Choose two different LGAs to compare their reporting rates.", []
            first, second = [reporting.loc[reporting["org_unit_id"].eq(unit)] for unit in units]
            if not period:
                period = max(set(first["period"]) & set(second["period"]), default=None)
                if not period:
                    return "These LGAs have no shared NHMIS reporting month.", [("", REPORTING_SOURCE)]
            parts = [f"**NHMIS reporting comparison · {period}**"]
            for unit, records in zip(units, (first, second)):
                parts.append(f"**{', '.join(locations[unit])}**\n\n{reporting_answer(period, records)}")
            return "\n\n".join(parts), [("", REPORTING_SOURCE)]
        unit = units[0]
        reply, source = dashboard_answer(question, period, cases.loc[cases["org_unit_id"].eq(unit)],
                                         reporting.loc[reporting["org_unit_id"].eq(unit)], *backtest_data)
        return f"**{', '.join(locations[unit])}**\n\n{reply}", [("", source)]

    try:
        matches = search_documents(DATA.parents[1], query)
    except OSError:
        return "The project documentation is unavailable.", []
    if not matches:
        return "I couldn’t find a dashboard answer or a matching excerpt. Try one of the example questions.", []
    reply = "I found these related excerpts in the project documentation."
    model = os.getenv("MALARIA_ASSISTANT_OLLAMA_MODEL", "").strip()
    if model:
        generated = answer_from_documents(model, query, matches)
        if generated:
            answer, matches = generated
            reply = f"**Explanation from the local model**\n\n{answer.translate(MARKDOWN_ESCAPES)}"
    return reply, [
        (match["excerpt"], f"{match['file']} · {match['section']}") for match in matches
    ]


def floating_assistant(location, selected_unit, locations, cases, reporting, backtest_data):
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
        .st-key-assistant-transcript {
            max-height: 42dvh;
        }
        </style>
    """)
    with st.container(key="assistant-launcher"):
        with st.popover("Ask assistant", type="primary", icon=":material/chat:"):
            with st.container(key="assistant-panel"):
                st.markdown("**Malaria dashboard assistant**")
                st.caption(f"Sidebar selection: {location}. You can name another LGA in your question.")
                transcript = st.container(key="assistant-transcript", height=280, border=True)
                query = st.chat_input("Ask about this LGA or the project", key="assistant-question", max_chars=200)
                exchanges = st.session_state.get("assistant-exchanges", [])
                if query and query.strip():
                    query = query.strip()
                    reply, sources = assistant_reply(query, selected_unit, locations, cases, reporting, backtest_data)
                    exchanges = [*exchanges[-7:], (query, reply, sources)]
                    st.session_state["assistant-exchanges"] = exchanges

                with transcript:
                    if not exchanges:
                        st.markdown("Try asking:\n\n"
                                    "- What is the latest reported malaria case count?\n"
                                    "- Reporting completeness for 2025-01\n"
                                    "- Which model had the lowest error for this LGA?\n"
                                    "- Compare reporting rates between Oji River in Enugu and Offa in Kwara")
                        st.caption("Use YYYY-MM for a specific month. You can also ask about the project methods.")
                    for question, reply, sources in exchanges:
                        with st.chat_message("user"):
                            st.text(question, width="stretch")
                        with st.chat_message("assistant"):
                            st.markdown(reply)
                            for excerpt, source in sources:
                                if excerpt:
                                    st.markdown(excerpt)
                                st.caption(f"Source: {source}")


def main():
    st.set_page_config(page_title="Nigeria Malaria Forecasting", layout="wide")
    st.title("Nigeria Malaria Forecasting")
    st.caption("Stage 6 prototype · Monthly reported confirmed cases and retrospective forecasts")

    cases = table(DATA / "features" / "case_rainfall_monthly.csv")
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

    reporting_path = DATA / "routine" / "nhmis_reporting_monthly.csv"
    all_reporting = pd.DataFrame(columns=["org_unit_id", "period"])
    if reporting_path.is_file():
        all_reporting = table(reporting_path)
    reporting = all_reporting.loc[all_reporting["org_unit_id"].eq(unit)].sort_values("period")

    trends, backtest = st.tabs(["Case and rainfall trends", "Forecast backtest"])
    with trends:
        first, second = st.columns(2)
        first.metric("Months with case counts", int(history["confirmed_cases"].count()))
        second.metric("Months without a case count in this series", int(history["confirmed_cases"].isna().sum()))
        st.markdown("**Reported confirmed cases**")
        st.line_chart(history[["confirmed_cases"]].rename(columns={"confirmed_cases": "Reported cases"}))
        st.markdown("**Monthly rainfall (mm)**")
        st.line_chart(history[["rainfall_mm"]].rename(columns={"rainfall_mm": "Rainfall (mm)"}))
        st.caption(f"Displayed period {history.index.min()} through {history.index.max()}.")
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

    with backtest:
        first, second = st.columns(2)
        horizon = first.radio("Forecast horizon (months)", [1, 2], horizontal=True)
        delay = second.radio("Assumed input delay (months)", [1, 2], horizontal=True)
        folder = DATA / "forecast"
        if delay == 2:
            folder = folder / "delay2"
        year, predictions, scores = backtest_tables(folder, delay)
        filtered = predictions.loc[predictions["org_unit_id"].eq(unit)
                                   & predictions["horizon_months"].eq(horizon)]
        local_mae = filtered[list(MODELS)].sub(filtered["confirmed_cases"], axis=0).abs().mean()
        st.caption(f"Forecasts were evaluated retrospectively on {year} case counts. The input delays are assumptions. "
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
        national["model"] = national["model"].map(MODELS)
        st.markdown("**Nationwide backtest errors**")
        st.dataframe(national.round(1).rename(columns={"model": "Model", "rows": "Scored LGA-months",
                                                        "mae": "MAE", "mean_bias": "Mean bias"}),
                     hide_index=True)
        st.caption("MAE is the average absolute error in cases per LGA-month. Negative bias means the model "
                   "predicted fewer cases than were reported, on average.")

    floating_assistant(location, unit, locations, cases, all_reporting, (local_mae, len(filtered), year, horizon, delay))


if __name__ == "__main__":
    main()
