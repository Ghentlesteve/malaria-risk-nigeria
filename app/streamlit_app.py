"""Local dashboard for observed malaria cases and retrospective forecasts."""

import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import streamlit as st

DATA = Path(__file__).resolve().parents[1] / "data" / "processed"
MODELS = {
    "seasonal_naive": "Same month last year",
    "case_history": "Case history",
    "case_rainfall": "Case history + rainfall",
}


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


def guided_answers(history, reporting, local_mae, scored_months, year, horizon, delay):
    st.caption("Answers use the selected LGA and the settings in Forecast backtest.")
    question = st.selectbox("Choose a question", [
        "What is the latest reported case count?",
        "What is the reporting completeness and timeliness?",
        "Which model had the lowest error for this LGA?",
    ])
    if question == "What is the latest reported case count?":
        observed = history["confirmed_cases"].dropna()
        if observed.empty:
            st.write("No case counts are available for this LGA.")
        else:
            st.write(f"**{observed.iloc[-1]:,.0f} reported confirmed cases** in {observed.index[-1]}.")
        st.caption("Source: monthly NHMIS case export, shown in Case and rainfall trends.")
    elif question == "What is the reporting completeness and timeliness?":
        if reporting.empty:
            st.write("No NHMIS reporting records are available for this LGA.")
        else:
            periods = reporting["period"].tolist()
            period = st.selectbox("Reporting month", periods, index=len(periods) - 1)
            row = reporting.loc[reporting["period"].eq(period)].iloc[0]
            if row["status"] == "OK":
                st.write(f"For {period}, completeness was **{row.completeness_pct:.1f}%** and "
                         f"timeliness was **{row.timeliness_pct:.1f}%**.")
                st.write(f"{row.reports_received:,.0f} of {row.reports_expected:,.0f} expected reports "
                         f"were completed, with {row.reports_on_time:,.0f} completed on time.")
            else:
                st.write(f"Rates for {period} are unavailable. Status: **{row['status']}**. "
                         "See the counts in Data quality.")
        st.caption("Source: NHMIS Monthly Summary Form (Version 2019), shown in Data quality.")
    else:
        if not scored_months:
            st.write("No scored months are available for this LGA under the selected settings.")
        else:
            minimum = local_mae.min()
            best = ", ".join(MODELS[name] for name in local_mae.index[local_mae.eq(minimum)])
            st.write(f"**{best}** had the lowest mean absolute error, **{minimum:,.1f} cases per month**, "
                     f"across {scored_months} scored months in {year}.")
            st.write(f"This backtest uses a {horizon}-month horizon and an assumed {delay}-month input delay.")
        st.caption("Source: verified retrospective predictions, shown in Forecast backtest.")


def main():
    st.set_page_config(page_title="Nigeria Malaria Forecasting", layout="wide")
    st.title("Nigeria Malaria Forecasting")
    st.caption("Stage 6 prototype · Monthly reported confirmed cases and retrospective forecasts")

    cases = table(DATA / "features" / "case_rainfall_monthly.csv")
    state = st.sidebar.selectbox("State or FCT", sorted(cases["state"].unique()), format_func=display_name)
    units = (cases.loc[cases["state"].eq(state), ["org_unit_id", "org_unit_name"]]
             .drop_duplicates("org_unit_id").sort_values("org_unit_name").set_index("org_unit_id"))
    unit = st.sidebar.selectbox("LGA", units.index.tolist(),
                                format_func=lambda uid: display_name(units.at[uid, "org_unit_name"]))
    history = cases.loc[cases["org_unit_id"].eq(unit)].sort_values("period").set_index("period")
    history = history.reindex(pd.period_range(history.index.min(), history.index.max(), freq="M").astype(str))
    st.subheader(f"{display_name(units.at[unit, 'org_unit_name'])}, {display_name(state)}")

    reporting_path = DATA / "routine" / "nhmis_reporting_monthly.csv"
    reporting = pd.DataFrame()
    if reporting_path.is_file():
        reporting = table(reporting_path)
        reporting = reporting.loc[reporting["org_unit_id"].eq(unit)].sort_values("period")

    trends, backtest, assistant = st.tabs(["Case and rainfall trends", "Forecast backtest", "Guided answers"])
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
            st.caption("NHMIS Monthly Summary Form (Version 2019). Rates describe completion of the whole form. "
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

    with assistant:
        guided_answers(history, reporting, local_mae, len(filtered), year, horizon, delay)


if __name__ == "__main__":
    main()
