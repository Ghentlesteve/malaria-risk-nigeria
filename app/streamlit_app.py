"""Local dashboard for observed malaria cases and retrospective forecasts."""

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


def main():
    st.set_page_config(page_title="Nigeria Malaria Forecasting", layout="wide")
    st.title("Nigeria Malaria Forecasting")
    st.caption("Stage 5 prototype · Monthly reported confirmed cases and retrospective forecasts")

    cases = table(DATA / "features" / "case_rainfall_monthly.csv")
    state = st.sidebar.selectbox("State or FCT", sorted(cases["state"].unique()), format_func=display_name)
    units = (cases.loc[cases["state"].eq(state), ["org_unit_id", "org_unit_name"]]
             .drop_duplicates("org_unit_id").sort_values("org_unit_name").set_index("org_unit_id"))
    unit = st.sidebar.selectbox("LGA", units.index.tolist(),
                                format_func=lambda uid: display_name(units.at[uid, "org_unit_name"]))
    history = cases.loc[cases["org_unit_id"].eq(unit)].sort_values("period").set_index("period")
    history = history.reindex(pd.period_range(history.index.min(), history.index.max(), freq="M").astype(str))
    st.subheader(f"{display_name(units.at[unit, 'org_unit_name'])}, {display_name(state)}")
    st.info("NHMIS reporting completeness and timeliness are unknown. Gaps in reported cases remain blank.")

    trends, backtest = st.tabs(["Case and rainfall trends", "2025 backtest"])
    with trends:
        first, second = st.columns(2)
        first.metric("Months with case counts", int(history["confirmed_cases"].count()))
        second.metric("Months without a case count in this series", int(history["confirmed_cases"].isna().sum()))
        st.markdown("**Reported confirmed cases**")
        st.line_chart(history[["confirmed_cases"]].rename(columns={"confirmed_cases": "Reported cases"}))
        st.markdown("**Monthly rainfall (mm)**")
        st.line_chart(history[["rainfall_mm"]].rename(columns={"rainfall_mm": "Rainfall (mm)"}))
        st.caption(f"Displayed period {history.index.min()} through {history.index.max()}.")

    with backtest:
        first, second = st.columns(2)
        horizon = first.radio("Forecast horizon (months)", [1, 2], horizontal=True)
        delay = second.radio("Assumed input delay (months)", [1, 2], horizontal=True)
        folder = DATA / "forecast"
        if delay == 2:
            folder = folder / "delay2"
        predictions = table(folder / "backtest_predictions.csv")
        scores = table(folder / "backtest_metrics.csv")
        filtered = predictions.loc[predictions["org_unit_id"].eq(unit)
                                   & predictions["horizon_months"].eq(horizon)]
        st.caption("Forecasts were evaluated retrospectively on 2025 case counts. The input delays are assumptions. "
                   "Prediction intervals have yet to be estimated.")
        if filtered.empty:
            st.info("This LGA has no scored targets for the selected scenario.")
        else:
            plot = (filtered.set_index("period")[["confirmed_cases", *MODELS]]
                    .rename(columns={"confirmed_cases": "Reported cases", **MODELS})
                    .reindex(pd.period_range("2025-01", "2025-12", freq="M").astype(str)))
            st.line_chart(plot)
            local_mae = filtered[list(MODELS)].sub(filtered["confirmed_cases"], axis=0).abs().mean()
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


if __name__ == "__main__":
    main()
