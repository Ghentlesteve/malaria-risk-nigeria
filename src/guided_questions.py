"""Question menus and factual explanations for the guided dashboard assistant."""

import pandas as pd

TOPICS = {
    "cases": ("Explore malaria cases", (
        ("case_count", "How many cases were reported that month?"),
        ("cases_previous", "Were there more cases than the previous month?"),
        ("cases_last_year", "How does that compare with the same month last year?"),
        ("cases_high", "Which month had the most reported cases that year?"),
        ("cases_low", "Which month had the fewest reported cases that year?"),
        ("cases_total", "How many cases were reported that year?"),
        ("cases_recent", "How did cases change over the last six months?"),
        ("cases_missing", "Which months are missing a case count?"),
        ("case_zero", "Does a blank mean there were zero cases?"),
        ("case_definition", "What counts as a confirmed case here?"),
    )),
    "rain": ("Explore rainfall", (
        ("rain_count", "How much rain fell that month?"),
        ("rain_previous", "Was it wetter than the previous month?"),
        ("rain_last_year", "Was it wetter than the same month last year?"),
        ("rain_usual", "Was that a lot of rain for this time of year?"),
        ("rain_high", "Which month had the most rain that year?"),
        ("rain_recent", "Can I see rainfall and cases for the same months?"),
        ("rain_cause", "Can we tell if rainfall caused the rise in cases?"),
        ("rain_source", "Where do the rainfall figures come from?"),
    )),
    "reports": ("Check reporting quality", (
        ("report_rates", "How complete and timely was reporting?"),
        ("report_expected", "How many reports were expected?"),
        ("report_received", "How many reports came in?"),
        ("report_on_time", "How many reports arrived on time?"),
        ("report_previous", "Did reporting improve since the previous month?"),
        ("report_last_year", "Has reporting improved since the same month last year?"),
        ("report_complete_meaning", "What does reporting completeness mean?"),
        ("report_timely_meaning", "What does reporting timeliness mean?"),
        ("report_late", "How can reporting be complete if some reports were late?"),
        ("report_unavailable", "Why might a reporting rate be unavailable?"),
        ("report_every_case", "Does 100% completeness mean every malaria case was counted?"),
    )),
    "compare": ("Compare with another LGA", (
        ("compare_summary", "How do these LGAs compare for this month?"),
        ("compare_cases", "Which LGA reported more cases?"),
        ("compare_rain", "Which LGA had more rain?"),
        ("compare_complete", "Which LGA had better reporting completeness?"),
        ("compare_timely", "Which LGA submitted a higher share on time?"),
        ("compare_shared", "What is the latest month both LGAs have reporting records for?"),
        ("compare_recent", "Can I compare their recent case trends side by side?"),
        ("case_prevalence", "Does a higher case count mean malaria is more common there?"),
    )),
    "forecast": ("Explore forecast performance", (
        ("forecast_best", "Which model was closest to the reported counts?"),
        ("forecast_mae", "How far off were the models in a typical month?"),
        ("forecast_bias", "Did the models usually predict too high or too low?"),
        ("forecast_worst", "Which month did the best model get most wrong?"),
        ("forecast_actual", "What did the models predict for this month?"),
        ("forecast_rain", "Did adding rainfall improve model accuracy here?"),
        ("forecast_baseline", "How did the models do against using the same month last year?"),
        ("forecast_national", "Did the local winner also do best across Nigeria?"),
        ("forecast_definition", "What is a backtest?"),
        ("forecast_delay", "What does the assumed input delay mean?"),
        ("forecast_live", "How many cases should we expect next month?"),
    )),
    "data": ("Understand the dashboard", (
        ("data_coverage", "How far back does the data go for this LGA?"),
        ("data_latest", "When was the last month with a reported case count?"),
        ("data_sources", "Where does the dashboard get its data?"),
        ("data_start", "Where should I start if I’m new to the dashboard?"),
        ("data_facility", "Can I see figures for my ward or health facility?"),
        ("data_download", "Can I download what I’m looking at?"),
        ("data_outbreak", "Can this tell me if an outbreak is coming?"),
        ("data_supplies", "How many test kits should we order?"),
    )),
}

OVERVIEW = "Tell me about this LGA"
QUESTIONS = {key: label for _, questions in TOPICS.values() for key, label in questions}
QUESTIONS["overview"] = OVERVIEW

FOLLOW_UPS = {
    "overview": ("cases_previous", "rain_usual", "report_rates", "compare_summary"),
    "cases_previous": ("cases_last_year", "report_previous", "rain_previous", "cases_recent"),
    "cases_last_year": ("cases_total", "report_last_year", "rain_last_year"),
    "rain_previous": ("rain_usual", "cases_previous", "rain_cause"),
    "report_rates": ("report_complete_meaning", "report_timely_meaning", "report_on_time", "report_previous"),
    "compare_summary": ("compare_cases", "compare_complete", "compare_timely", "compare_recent"),
    "forecast_best": ("forecast_mae", "forecast_worst", "forecast_rain", "forecast_national"),
    "forecast_live": ("forecast_best", "forecast_definition", "data_outbreak"),
}

CASE_SOURCE = "Monthly NHMIS case export"
RAIN_SOURCE = "CHIRPS rainfall"
REPORT_SOURCE = "NHMIS Monthly Summary Form"
BACKTEST_SOURCE = "Historical forecast backtest"
METHOD_SOURCE = "Project methodology"

EXPLANATIONS = {
    "case_zero": ("A blank means the case count is unavailable. A reported zero appears as 0.", CASE_SOURCE),
    "case_definition": ("The selected NHMIS indicator adds people who tested positive by rapid diagnostic test and people who tested positive by microscopy.", CASE_SOURCE),
    "rain_cause": ("The dashboard can show whether rainfall and reported cases moved together. Establishing cause would require evidence that accounts for seasonality, reporting changes, and other factors.", METHOD_SOURCE),
    "rain_source": ("Monthly rainfall estimates come from CHIRPS and are averaged across the area of each LGA.", RAIN_SOURCE),
    "report_complete_meaning": ("Completeness is the percentage of expected forms that were submitted. The denominator is all expected reports.", REPORT_SOURCE),
    "report_timely_meaning": ("Timeliness is the percentage of expected forms submitted by the deadline. The denominator is all expected reports.", REPORT_SOURCE),
    "report_late": ("A late report counts toward completeness. Timeliness only counts forms that arrived by the deadline.", REPORT_SOURCE),
    "report_unavailable": ("Rates are unavailable when the expected or submitted counts are missing or inconsistent, or when there were no expected reports.", REPORT_SOURCE),
    "report_every_case": ("100% completeness means all expected forms were submitted. Case detection and recording determine how many infections enter those forms.", REPORT_SOURCE),
    "case_prevalence": ("Comparing how common malaria is requires population denominators and comparable detection and reporting. This comparison shows counts of reported confirmed cases.", METHOD_SOURCE),
    "forecast_definition": ("A backtest simulates forecasts for past months and checks them against the reported counts for those months.", BACKTEST_SOURCE),
    "forecast_delay": ("The input delay is how long the backtest assumes it takes for rainfall and case data to become available. Use the Forecast backtest tab to compare the one-month and two-month assumptions.", BACKTEST_SOURCE),
    "forecast_live": ("Live forecasts are planned. Forecast backtest shows how the models performed on past months.", BACKTEST_SOURCE),
    "data_sources": ("Case counts come from a monthly NHMIS case export, reporting rates from the NHMIS Monthly Summary Form, and rainfall estimates from CHIRPS.", METHOD_SOURCE),
    "data_start": ("Pick an LGA in the sidebar, then choose a month on Overview. Use Case and rainfall trends for the monthly series and Forecast backtest for model performance.", METHOD_SOURCE),
    "data_facility": ("The dashboard shows monthly data at LGA level. Ward and facility figures are unavailable here.", METHOD_SOURCE),
    "data_download": ("Use the download control in the toolbar of a dashboard table to save the displayed rows.", METHOD_SOURCE),
    "data_outbreak": ("Outbreak alerts require validated thresholds and current surveillance inputs. This dashboard shows reported case trends and historical forecast performance.", METHOD_SOURCE),
    "data_supplies": ("An order quantity requires current stock levels, test use, delivery times, and programme guidance. This dashboard can provide historical reported case counts for context.", METHOD_SOURCE),
}


def month_label(month):
    return pd.Period(month, freq="M").strftime("%B %Y")


def previous_month(month, months):
    return str(pd.Period(month, freq="M") - months)


def latest_snapshot_month(history):
    observed = history["confirmed_cases"].dropna()
    return observed.index.max() if not observed.empty else history.index.max()


METRICS = (
    ("Reported confirmed cases", ",.0f", ""),
    ("Rainfall (mm)", ",.1f", ""),
    ("Reporting completeness", ".1f", "%"),
    ("Reporting timeliness", ".1f", "%"),
)


def format_value(value, spec, suffix=""):
    return f"{value:{spec}}{suffix}" if pd.notna(value) else "Unavailable"


def snapshot_values(history, reporting, month):
    records = reporting.loc[reporting["period"].eq(month)]
    rates = records.loc[records["status"].eq("OK")] if not records.empty else records
    completeness, timeliness = (rates.iloc[0][["completeness_pct", "timeliness_pct"]]
                                if not rates.empty else (None, None))
    return history["confirmed_cases"].get(month), history["rainfall_mm"].get(month), completeness, timeliness


def snapshot_metrics(history, reporting, month):
    return [(label, format_value(value, spec, suffix)) for (label, spec, suffix), value in
            zip(METRICS, snapshot_values(history, reporting, month))]


def recent_months(month):
    return pd.period_range(end=month, periods=6, freq="M").astype(str)


def series_answer(question, history, month):
    rain = question.startswith("rain_")
    series = history["rainfall_mm" if rain else "confirmed_cases"]
    spec, suffix = (",.1f", " mm") if rain else (",.0f", " cases")
    current = series.get(month)
    action = question.split("_", 1)[1]
    if action == "count":
        return f"**{format_value(current, spec, suffix)}** for {month_label(month)}."
    if action in ("previous", "last_year"):
        prior = previous_month(month, 1 if action == "previous" else 12)
        earlier = series.get(prior)
        comparison = f"{month_label(prior)} had **{format_value(earlier, spec, suffix)}**."
        if pd.isna(current) or pd.isna(earlier):
            return f"{month_label(month)} had **{format_value(current, spec, suffix)}**. {comparison} Both values are needed to measure a change."
        difference = format_value(current - earlier, "+" + spec, suffix)
        return f"{month_label(month)} had **{format_value(current, spec, suffix)}**, a change of **{difference}**. {comparison}"
    if action == "usual":
        peers = series.loc[series.index.str.endswith(month[-3:]) & (series.index != month)].dropna()
        if pd.isna(current) or peers.empty:
            return "Rainfall for this month and at least one other year are needed for this comparison."
        return (f"Rainfall was **{current:,.1f} mm**, compared with an average of **{peers.mean():,.1f} mm** "
                f"across {len(peers)} other years for the same calendar month in the available data.")
    if action == "recent":
        lines = []
        for period in recent_months(month):
            case_count = format_value(history["confirmed_cases"].get(period), ",.0f", " cases")
            rainfall = format_value(history["rainfall_mm"].get(period), ",.1f", " mm")
            detail = f"{case_count} · {rainfall}" if rain else case_count
            lines.append(f"- **{month_label(period)}** · {detail}")
        return "\n".join(lines)

    year = month[:4]
    year_values = series.reindex(pd.period_range(f"{year}-01", periods=12, freq="M").astype(str))
    observed = year_values.dropna()
    coverage = f"**{len(observed)} of 12 months** have values for {year}."
    if action == "missing":
        missing = ", ".join(month_label(period) for period in year_values.index[year_values.isna()])
        return f"{coverage}\n\nMonths with unavailable counts: {missing}." if missing else coverage
    if observed.empty:
        return f"There are no values available for {year}."
    if action == "total":
        return f"**{observed.sum():,.0f} cases** across the months with reported counts. {coverage}"
    extreme = observed.max() if action == "high" else observed.min()
    periods = ", ".join(month_label(period) for period in observed.index[observed.eq(extreme)])
    return f"**{periods}** had **{format_value(extreme, spec, suffix)}**. {coverage}"


def report_detail(question, reporting, month):
    if reporting.empty:
        return "No reporting records are available for this LGA."
    records = reporting.set_index("period")
    if question in ("report_previous", "report_last_year"):
        prior = previous_month(month, 1 if question == "report_previous" else 12)
        paired = records.reindex([prior, month])
        columns = ["completeness_pct", "timeliness_pct"]
        values = paired[columns]
        if not paired["status"].eq("OK").all() or values.isna().any().any():
            return f"Valid reporting rates for both {month_label(prior)} and {month_label(month)} are needed."
        changes = values.iloc[1] - values.iloc[0]
        return (f"Compared with {month_label(prior)}, completeness changed by **{changes.iloc[0]:+.1f} percentage points** "
                f"and timeliness changed by **{changes.iloc[1]:+.1f} percentage points**.")
    if month not in records.index:
        return "No reporting record is available for this month."
    record = records.loc[month]
    field, description = {
        "report_expected": ("reports_expected", "were expected"),
        "report_received": ("reports_received", "were received"),
        "report_on_time": ("reports_on_time", "arrived on time"),
    }[question]
    value = record[field]
    if pd.isna(value):
        return "This reporting count is unavailable for the selected month."
    note = " The reporting record is flagged for review." if record["status"] != "OK" else ""
    return f"**{value:,.0f} reports** {description}.{note}"


def compare_answer(question, month, names, histories, reports):
    if question == "compare_shared":
        common = set(reports[0]["period"]) & set(reports[1]["period"])
        return (f"**{month_label(max(common))}** is the latest month with a reporting record for both LGAs."
                if common else "These LGAs have no shared reporting month.")
    if question == "compare_recent":
        lines = []
        for period in recent_months(month):
            values = [format_value(history["confirmed_cases"].get(period), ",.0f") for history in histories]
            lines.append(f"- **{month_label(period)}** · {values[0]} / {values[1]}")
        return f"Reported cases for **{names[0]}** / **{names[1]}**\n\n" + "\n".join(lines)

    snapshots = [snapshot_values(history, reporting, month) for history, reporting in zip(histories, reports)]
    if question == "compare_summary":
        parts = []
        for name, values in zip(names, snapshots):
            lines = [f"- {label} · **{format_value(value, spec, suffix)}**"
                     for (label, spec, suffix), value in zip(METRICS, values)]
            parts.append(f"**{name}**\n\n" + "\n".join(lines))
        return "\n\n".join(parts)

    index = {"compare_cases": 0, "compare_rain": 1, "compare_complete": 2, "compare_timely": 3}[question]
    label, spec, suffix = METRICS[index]
    first, second = (snapshot[index] for snapshot in snapshots)
    values = [format_value(value, spec, suffix) for value in (first, second)]
    result = f"**{label}**\n\n- {names[0]} · **{values[0]}**\n- {names[1]} · **{values[1]}**"
    if pd.isna(first) or pd.isna(second):
        return result + "\n\nBoth values are needed to compare the LGAs."
    if values[0] == values[1]:
        return result + "\n\nThe displayed values are equal."
    return result + f"\n\n**{names[0 if first > second else 1]}** had the higher value."


def forecast_answer(question, month, predictions, national, models):
    if predictions.empty:
        return "There are no scored months for this LGA under the selected backtest settings."
    errors = predictions[list(models)].sub(predictions["confirmed_cases"], axis=0)
    mae = errors.abs().mean()
    best = mae.index[mae.eq(mae.min())].tolist()
    local_winners = ", ".join(models[key] for key in best)
    if question == "forecast_best":
        return f"**{local_winners}** had the lowest mean absolute error, **{mae.min():,.1f} cases per month**."
    if question == "forecast_worst":
        peak = errors[best[0]].abs().max()
        months = predictions.loc[errors[best[0]].abs().eq(peak), "period"]
        when = ", ".join(month_label(period) for period in months)
        return f"**{models[best[0]]}** missed by **{peak:,.0f} cases** in {when}, its largest absolute error."
    if question == "forecast_actual":
        rows = predictions.loc[predictions["period"].eq(month)]
        if rows.empty:
            return "The selected month has no scored predictions under these backtest settings."
        row = rows.iloc[0]
        lines = [f"Reported cases · **{row.confirmed_cases:,.0f}**"]
        lines.extend(f"{label} · **{row[key]:,.0f}**" for key, label in models.items())
        return "\n".join(f"- {line}" for line in lines)
    if question == "forecast_rain":
        difference = mae["case_rainfall"] - mae["case_history"]
        return (f"Mean absolute error was **{mae['case_rainfall']:,.1f}** with rainfall and "
                f"**{mae['case_history']:,.1f}** using case history alone. Adding rainfall changed the error "
                f"by **{difference:+,.1f} cases per month** in this backtest.")
    if question == "forecast_national":
        leaders = national.loc[national["mae"].eq(national["mae"].min()), "model"].tolist()
        if not leaders:
            return "Nationwide scores are unavailable for these settings."
        nationwide = ", ".join(models[key] for key in leaders)
        return f"Lowest average error for this LGA · **{local_winners}**\n\nLowest average error nationwide · **{nationwide}**"
    if question == "forecast_bias":
        return ("Average prediction minus reported cases. Positive values mean the model predicted too high on average.\n\n"
                + "\n".join(f"- {models[key]} · **{value:+,.1f} cases per month**" for key, value in errors.mean().items()))
    if question == "forecast_baseline":
        baseline = mae["seasonal_naive"]
        return (f"Using the same month last year had a mean absolute error of **{baseline:,.1f} cases per month**.\n\n"
                + "\n".join(f"- {models[key]} · **{value - baseline:+,.1f} cases per month** versus that baseline"
                            for key, value in mae.items() if key != "seasonal_naive"))
    return "\n".join(f"- {models[key]} · **{value:,.1f} cases per month**" for key, value in mae.items())
