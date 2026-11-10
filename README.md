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
- Available locally: routine monthly case exports from January 2020 through October 2026, combined with blanks preserved. Run the preparation command below to regenerate the audit.
- Available locally: matched LGA polygons, CHIRPS rainfall for 2019–2025, the case–rainfall join, exploratory analysis and a rolling 2025 backtest.
- The public Streamlit dashboard shows LGA trends, reporting quality and retrospective forecast comparisons. [Open the public dashboard](https://malaria-rain-risk-nigeria.streamlit.app/).
- Available locally: NHMIS 2019 reporting counts and dashboard rates for 2020–2025.
- Pending: historical availability evidence, temperature, uncertainty estimates and Chap/DHIS2 integration.

The DHS/MIS work remains historical context on prevalence and interventions. Its survey risk categories are not outbreak alerts. Survey estimates will not be interpolated into monthly cases or assigned to LGAs as observed outcomes.

## Stages and deliverables

| Stage | Deliverable | Status |
| --- | --- | --- |
| 1. Scope | Nationwide LGA analysis, user decision and data requirements | Nationwide extraction agreed; smaller modeling pilot undecided |
| 2. Data readiness | Validated monthly cases, reporting metadata, geography and climate data | Case ingestion and initial audit completed; remaining inputs pending |
| 3. Relationship analysis | Rainfall and case seasonality, lag associations and variation across LGAs | Initial nationwide analysis complete |
| 4. Forecasting | Seasonal baseline, case-history model and rainfall-informed model | Initial rolling 2025 backtest complete |
| 5. Dashboard | Observed trends, retrospective forecasts and reporting-quality status | Public dashboard live |
| 6. Dashboard assistant | Guided questions with answers from dashboard data | Available in the floating panel |
| 7. Deployment and integration | Hosted pilot, monitoring, CI/CD and evaluation of Chap/DHIS2 integration | Public dashboard, automated startup checks and a Chap input export available. See the [Chap sandbox guide](docs/chap_sandbox.md). |

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

The preparation command reads `data/raw/malaria_confirmed_lga_monthly_YYYY.csv` and writes derived files to `data/processed/routine/`: a monthly case table, source-cell lineage, source fingerprints and schema results, yearly/state coverage, absent unit-years and a readable readiness report. Raw files are unchanged. Original names and hierarchy prefixes are retained. Reporting measures stay blank until supplied. The importer checks month headings against the filename year and accepts decimal-formatted whole counts without rounding. The latest export may end before December if it contains every month from January through its final month. Earlier exports must cover all twelve months.

For manually prepared inputs, `templates/monthly_cases.csv` documents the validator's expected format. It is deliberately header-only and fails the empty-data check.

The validator reports schema errors, invalid values, duplicate unit-month records, internal missing months and missing reporting measures. It does not modify input, fill gaps, establish epidemiological validity or certify readiness to forecast. Coverage checks cannot detect LGAs absent from the whole file or missing periods outside each unit's observed range without an expected roster and date window.

Run `python -m src.analyze_rainfall` from a Python environment with pandas, NumPy and Matplotlib after generating the case–rainfall table with `python -m src.features`. The analysis writes a seasonal profile, lag associations and a figure under `data/processed/analysis/`. It compares rainfall and log-transformed reported cases at lags of zero to three months. The adjusted comparison subtracts each LGA’s calendar-month mean over the observed years. These retrospective summaries use the full available series and are separate from forecast evaluation.

Run `python -m src.model` from a Python environment with pandas, NumPy and scikit-learn to regenerate the rolling backtest. Forecasts are issued at month end for one and two months ahead. The default assumes cases and rainfall through the preceding calendar month are available. At each issue date, training includes only outcomes available under that assumption. The seasonal baseline uses the same target month a year earlier. The two models use identical histogram gradient boosting settings, with rainfall added to the second model. Metrics use the same evaluable targets for all three methods. Outputs stay under `data/processed/forecast/`.

To check sensitivity to slower publication, run `python -m src.model --case-delay 2 --rainfall-delay 2 --output data/processed/forecast/delay2`. The delays are assumptions because the retrospective files do not establish what was actually available at each historical forecast date. Case counts represent reported cases and historical revisions may affect results.

Replay an issue date with the same models using the following command. The October 2025 replay uses inputs through September and forecasts November and December. It writes the predictions and an audit with the issue date, input cutoffs, and file checksums.

```powershell
python -m src.forecast --issue-month 2025-10 --rainfall data/processed/climate/rainfall_monthly_2019_2025.csv --output data/processed/forecast_runs/2025-10-replay
```

For a new issue month, supply updated case and rainfall inputs through their required cutoffs. Repeat `--rainfall` to include separate rainfall files with distinct LGA-month keys. Forecasts use the existing one-month input delay by default. Historical replays use calendar cutoffs applied to retrospective exports.

Use `--max-horizon 6` with either `src.model` or `src.forecast` to evaluate or generate forecasts for months one through six. Both commands default to two months. Give the extended backtest a separate output directory to keep it distinct from the dashboard's existing backtest.

After generating a forecast trial, point the local dashboard to the folder that contains its CSV and audit. The **Forecasts** tab defaults to **Next 2 months**. It offers **Next 4 months** and **Next 6 months** when the run covers those windows.

```powershell
$env:MALARIA_DASHBOARD_FORECAST_DIR = "data/processed/forecast_runs/2026-10-trial-6mo"
python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1 --server.port 8529
```

After generating the joined case table and both backtest runs, start the local dashboard from a Python environment with Streamlit 1.52.2 and pandas.

```powershell
python -m streamlit run app/streamlit_app.py --server.address 127.0.0.1
```

Select a state and LGA to view reported case and rainfall trends. The Forecast backtest tab compares three methods and lets you switch the horizon and input delay. The tab reads the year and verifies the prediction and score files against the run audit. Forecast uncertainty estimates are pending.

Run `python -m src.reliability` to combine the local `nhmis_2019_reporting_monthly_YYYY.csv` exports in `data/raw/`. The dashboard displays the resulting counts and rates in **Data quality**. The rates use expected reports as the denominator and stay blank when the counts are incomplete, inconsistent, or have no expected reports.

For the existing survey analysis, install `requirements.txt` in an isolated environment and use notebooks 01 and 02. Those requirements are the original analysis environment, not a completed deployment specification. No automated NHMIS connection or cloud deployment is configured.

## Run the synthetic dashboard demo

From the repository root, use an isolated Python 3.12 environment.

```powershell
python -m pip install -r app/requirements.txt
python -m streamlit run app/demo_app.py --server.address 127.0.0.1
```

The demo entry point generates four fictional LGAs with monthly data for 2024–2025, simple map boundaries, and simulated backtest outputs in a temporary directory when it starts. It displays a synthetic data banner and requires no NHMIS exports, climate downloads, or credentials.

For [Streamlit Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), select this GitHub repository, the `main` branch, and `app/demo_app.py` as the main file. Choose Python 3.12 in Advanced settings. The host installs the dependencies from `app/requirements.txt`.

The [Dashboard checks workflow](.github/workflows/dashboard-demo.yml) tests both entry points. The synthetic check covers the dashboard, assistant month changes and both backtest delay settings. To run it locally, use `python -m unittest discover -s tests -p smoke_demo_dashboard.py -v`.

## Deploy the dashboard with approved figures

Generate the release archive from the approved processed tables with `python -m src.public_dashboard_data`. It writes `outputs/malaria-dashboard-data-2020-2025.zip`. The archive contains the dashboard's monthly case, rainfall, and reporting figures, LGA geometry, and backtest results for both delay settings.

Attach the verified archive to a [GitHub release](https://github.com/Ghentlesteve/malaria-risk-nigeria/releases/new) tagged `dashboard-data-2020-2025-v1`. Then deploy `app/public_app.py` from `main` on [Streamlit Community Cloud](https://share.streamlit.io/) with Python 3.12. The app downloads and verifies the release archive at startup. If the dashboard data changes, update the release tag in `src/public_dashboard_data.py` and the expected SHA-256 in `app/public_app.py`.

The public startup check uses the published ZIP and verifies that the app loads the map, case counts and both backtest delay settings. Run it locally with `python -m unittest discover -s tests -p smoke_public_dashboard.py -v`.

To publish the October 2026 forecast trial, generate its separate archive.

```powershell
python -m src.public_dashboard_data --forecast-dir data/processed/forecast_runs/2026-10-trial-6mo
```

Attach `outputs/malaria-forecast-trial-2026-10.zip` to a GitHub release tagged `forecast-trial-2026-10-v1`. The public app shows the **Forecasts** tab once it downloads the verified archive. The tab displays the simulated issue date and the case and rainfall cutoffs. Allow up to five minutes for the app to check again after a release appears.

## Run a forecast on GitHub

Open **Actions → Run malaria forecast → Run workflow**. Leave the issue month blank to run the synthetic checks. For a run with real inputs, select `main` and enter the month of issue in `YYYY-MM` format. The job generates six monthly estimates for each LGA and requires cases and rainfall through the preceding month.

Before running with real inputs, create a GitHub environment named `forecast-inputs` and restrict it to the `main` branch. Set its `FORECAST_CASES_URL` and `FORECAST_RAINFALL_URL` secrets to direct HTTPS download links from approved storage for the prepared case and rainfall CSVs. If recent rainfall is in a separate file, set `FORECAST_RAINFALL_UPDATE_URL` as well. Rainfall files must cover distinct LGA-month keys.

By default the job reports completion without retaining the result. Enable **Make forecast outputs downloadable by repository readers** only for results approved for that audience. That option retains the forecast CSV and audit for seven days. Publication to the dashboard still uses the reviewed release archive. A monthly schedule depends on having a source that the runner can access as new inputs arrive.

## Ask the dashboard

The dashboard opens on **Overview**. Choose an LGA and a snapshot month to see reported cases, rainfall, and NHMIS reporting rates for the same period. The snapshot starts on the latest month with a reported case count when one is available.

Open **Case and rainfall trends** to explore reported cases, rainfall, and reporting completeness on a shared timeline. The date range applies to the timeline and the seasonal heatmap. Switch the heatmap between cases and rainfall to compare the same calendar month across years.

In **LGA comparison**, the sidebar sets the first LGA. Choose a second LGA and a date range to compare reported cases, rainfall, and reporting completeness on shared scales. Hover over a month to see both values for that measure.

In **Nigeria map**, choose a month and measure to see values across LGAs. Click a boundary to see that LGA’s Overview below the map for the selected month. The map uses the matched OCHA boundaries produced by the boundary preparation step in [the climate guide](docs/climate_data.md).

Click **Ask assistant** in the lower-right corner of any dashboard tab. Start with **Tell me about this LGA** or choose a topic. Each answer shows its sources and offers related questions. Use **More questions** to browse the topic and **Start over** to clear the conversation.

The sidebar sets the LGA and the Forecast backtest tab sets the backtest settings. Changing **Question month** updates the current answer if it depends on the selected period. **Earlier replies** retain the periods shown when those replies were displayed. **Compare with another LGA** lets you pick an LGA anywhere in Nigeria and compare both places for the same month. The assistant uses local tables and project definitions. It requires no model setup or training.

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
