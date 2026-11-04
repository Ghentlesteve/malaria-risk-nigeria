# Nigeria Climate-Informed Malaria Analysis and Forecasting

A research and decision-support prototype inspired by the DHIS2 Climate Tools training held in Kaduna State. The project will investigate local rainfall–malaria relationships and test whether climate information improves forecasts of monthly reported confirmed malaria cases one and two months ahead.

The intended users are national and state malaria programme teams reviewing preparedness and potential demand for diagnostic tests and treatments. The extraction scope is **all 36 states and the FCT, by LGA and month**. Nasarawa was an initial extraction test, not a selected pilot. Any smaller modeling pilot remains undecided.

## Questions

1. Are wetter periods followed by increases in reported malaria cases, after what delay, and in which locations?
2. Does climate information improve predictions beyond seasonality and previous case counts?
3. How do incomplete or delayed reports affect interpretation?

The exploratory analysis and retrospective backtest address the first two questions. Observational associations alone do not establish causation. Operational forecast accuracy and alert thresholds require prospective validation.

## Current status

- Existing work: DHS/MIS ingestion, exploratory analysis, figures and a processed state-by-survey-year dataset.
- New foundation: monthly case-data specification, a CSV template, validator and reproducible DHIS2 export ingestion with provenance and coverage reports.
- Available locally: yearly routine case exports for 2020–2025, combined into a monthly table with blanks preserved. Run the preparation command below to regenerate the audit.
- Available locally: matched LGA polygons, CHIRPS rainfall for 2019–2025, the case–rainfall join, exploratory analysis and a rolling 2025 backtest.
- Available locally: a Streamlit dashboard for LGA trends and retrospective forecast comparisons.
- Available locally: NHMIS 2019 reporting counts and dashboard rates for 2020–2025.
- Pending: historical availability evidence, temperature, uncertainty estimates and deployment.

The DHS/MIS work remains historical context on prevalence and interventions. Its survey risk categories are not outbreak alerts. Survey estimates will not be interpolated into monthly cases or assigned to LGAs as observed outcomes.

## Stages and deliverables

| Stage | Deliverable | Status |
| --- | --- | --- |
| 1. Scope | Nationwide LGA analysis, user decision and data requirements | Nationwide extraction agreed; smaller modeling pilot undecided |
| 2. Data readiness | Validated monthly cases, reporting metadata, geography and climate data | Case ingestion and initial audit completed; remaining inputs pending |
| 3. Relationship analysis | Rainfall and case seasonality, lag associations and variation across LGAs | Initial nationwide analysis complete |
| 4. Forecasting | Seasonal baseline, case-history model and rainfall-informed model | Initial rolling 2025 backtest complete |
| 5. Dashboard | Observed trends, retrospective forecasts and reporting-quality status | Local prototype available |
| 6. AI assistant | Answers from verified dashboard data and cited document search | Floating chat available locally |
| 7. Deployment and integration | Hosted pilot, monitoring, CI/CD and evaluation of Chap/DHIS2 integration | Later phase |

See [APPROACH.md](APPROACH.md) for the design and evaluation rules, and [docs/monthly_case_data.md](docs/monthly_case_data.md) for the first input specification.

The climate pipeline aggregates CHIRPS v3 rainfall for 2019–2025 using the OCHA Nigeria ADM2 layer matched to DHIS2 LGA IDs. ERA5-Land temperature acquisition awaits Copernicus setup and implementation. See [docs/climate_data.md](docs/climate_data.md) for commands and source versions. See [CONTRIBUTING.md](CONTRIBUTING.md) for commits, tests and local data handling.

## Data plan

| Source | Role | Resolution |
| --- | --- | --- |
| Authorised aggregate NHMIS/DHIS2 export | Confirmed cases and observed reporting quality | Monthly, LGA where available |
| Rainfall and temperature data | Climate exposures, seasonality and lagged features | Monthly, matching health geography |
| Organisation-unit metadata and boundaries | Stable geographical joins and spatial aggregation | Matching export geography |
| DHS/MIS indicators | Historical prevalence and intervention context | State by survey year |

Case counts are the initial forecasting target. Incidence needs a suitable population denominator. Missing reports remain missing; an absent reporting-quality measure means unknown quality. Aggregate exports are sufficient; patient records are not required.

## Run the available data checks

From the repository root, with Python 3.10 or later:

```bash
# Prepare the supplied yearly DHIS2 exports (2020–2025).
python -m src.ingest_dhis2

# Checks use the Python standard library; no package installation required.
python -m src.data_utils path/to/monthly_cases.csv

# Optionally save a summary (this location is ignored by Git).
python -m src.data_utils path/to/monthly_cases.csv --report data/processed/monthly_cases_validation.json

# Run validator tests.
python -m unittest discover -s tests -v
```

The preparation command reads `data/raw/malaria_confirmed_lga_monthly_YYYY.csv` and writes derived files to `data/processed/routine/`: a monthly case table, source-cell lineage, source fingerprints and schema results, yearly/state coverage, absent unit-years and a readable readiness report. Raw files are unchanged. Original names and hierarchy prefixes are retained. Reporting measures stay blank until supplied. The importer accepts the observed wide monthly export layouts, checks all twelve month headings against the filename year, and accepts decimal-formatted whole counts without rounding. Unsupported layouts or ambiguous identities fail for review.

For manually prepared inputs, `templates/monthly_cases.csv` documents the validator's expected format. It is deliberately header-only and fails the empty-data check.

The validator reports schema errors, invalid values, duplicate unit-month records, internal missing months and missing reporting measures. It does not modify input, fill gaps, establish epidemiological validity or certify readiness to forecast. Coverage checks cannot detect LGAs absent from the whole file or missing periods outside each unit's observed range without an expected roster and date window.

Run `python -m src.analyze_rainfall` from a Python environment with pandas, NumPy and Matplotlib after generating the case–rainfall table with `python -m src.features`. The analysis writes a seasonal profile, lag associations and a figure under `data/processed/analysis/`. It compares rainfall and log-transformed reported cases at lags of zero to three months. The adjusted comparison subtracts each LGA’s calendar-month mean over the observed years. These retrospective summaries use the full available series and are separate from forecast evaluation.

Run `python -m src.model` from a Python environment with pandas, NumPy and scikit-learn to regenerate the rolling backtest. Forecasts are issued at month end for one and two months ahead. The default assumes cases and rainfall through the preceding calendar month are available. At each issue date, training includes only outcomes available under that assumption. The seasonal baseline uses the same target month a year earlier. The two models use identical histogram gradient boosting settings, with rainfall added to the second model. Metrics use the same evaluable targets for all three methods. Outputs stay under `data/processed/forecast/`.

To check sensitivity to slower publication, run `python -m src.model --case-delay 2 --rainfall-delay 2 --output data/processed/forecast/delay2`. The delays are assumptions because the retrospective files do not establish what was actually available at each historical forecast date. Case counts represent reported cases and historical revisions may affect results.

After generating the joined case table and both backtest runs, start the local dashboard from a Python environment with Streamlit 1.52.2 and pandas.

```powershell
python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Select a state and LGA to view reported case and rainfall trends. The Forecast backtest tab compares three methods and lets you switch the horizon and input delay. The tab reads the year and verifies the prediction and score files against the run audit. Forecast uncertainty estimates are pending.

Run `python -m src.reliability` to combine the local `nhmis_2019_reporting_monthly_YYYY.csv` exports in `data/raw/`. The dashboard displays the resulting counts and rates in **Data quality**. The rates use expected reports as the denominator and stay blank when the counts are incomplete, inconsistent, or have no expected reports.

For the existing survey analysis, install `requirements.txt` in an isolated environment and use notebooks 01 and 02. Those requirements are the original analysis environment, not a completed deployment specification. No automated NHMIS connection or cloud deployment is configured.

## Ask the dashboard

Click **Ask assistant** in the lower-right corner of either dashboard tab. Try “What is the latest reported malaria case count?”, “Reporting completeness for 2025-01”, or “Which model had the lowest error for this LGA?”. Use `YYYY-MM` to ask for case counts or reporting rates in a specific month. Answers use the LGA and forecast settings selected when you send the question. The chat keeps the last eight exchanges in the current dashboard session.

Dashboard answers use local tables and show their source. Other queries return keyword-matched excerpts from selected sections of the README, methodology, and monthly case-data guide. Open-ended LLM answers are pending.

## Structure

```text
data/raw/                  Local source files, ignored by Git
data/processed/            Local processed data and validation summaries, ignored by Git
templates/monthly_cases.csv
docs/monthly_case_data.md
src/data_utils.py          Monthly CSV validation and CLI
src/ingest_dhis2.py        Yearly export reshaping, source lineage and coverage audit
src/climate_data.py        CHIRPS download, polygon audit and area-weighted rainfall extraction
src/features.py            Placeholder
src/model.py               Placeholder
src/reliability.py         Placeholder
tests/                     Data-validation tests
notebooks/01_*.ipynb        Existing survey ingestion
notebooks/02_*.ipynb        Existing survey EDA
notebooks/03_*.ipynb        Placeholder for later work (also notebooks 04 and 05)
app/streamlit_app.py        Placeholder
reports/figures/            Existing survey figures
APPROACH.md                Proposed research and product design
```

## Author

**Kwenev Stephen** — Data Analyst & Health Information Systems Specialist

[LinkedIn](https://linkedin.com/in/stephen-kwenev-85315b278) · [GitHub](https://github.com/Ghentlesteve)

## Reference materials

- Local DHIS2 Climate Tools training slides (original venue text retained in the slides; training held in Kaduna).
- [DHIS2 Climate Tools](https://climate-tools.dhis2.org/)
- [Chap modeling documentation](https://chap.dhis2.org/)
- [DHS/HDX Nigeria subnational data](https://data.humdata.org/dataset/dhs-subnational-data-for-nigeria)
