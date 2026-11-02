# Nigeria Climate-Informed Malaria Analysis and Forecasting

A research and decision-support prototype inspired by the DHIS2 Climate Tools training held in Kaduna State. The project will investigate local rainfall–malaria relationships and test whether climate information improves forecasts of monthly reported confirmed malaria cases one and two months ahead.

The intended users are national and state malaria programme teams reviewing preparedness and potential demand for diagnostic tests and treatments. The extraction scope is **all 36 states and the FCT, by LGA and month**. Nasarawa was an initial extraction test, not a selected pilot. Any smaller modeling pilot remains undecided.

## Questions

1. Are wetter periods followed by increases in reported malaria cases, after what delay, and in which locations?
2. Does climate information improve predictions beyond seasonality and previous case counts?
3. How do incomplete or delayed reports affect interpretation?

These are research questions. No local rainfall effect, forecasting accuracy or operational alert threshold has been established yet. Observational associations alone do not establish causation.

## Current status

- Existing work: DHS/MIS ingestion, exploratory analysis, figures and a processed state-by-survey-year dataset.
- New foundation: monthly case-data specification, a CSV template, validator and reproducible DHIS2 export ingestion with provenance and coverage reports.
- Available locally: yearly routine case exports for 2020–2025, combined into a monthly table with blanks preserved. Run the preparation command below to regenerate the audit.
- Pending: NHMIS 2019 dataset reporting measures, geography/boundary verification, climate ingestion, relationship analysis, model evaluation, dashboard and deployment.
- The feature, model and reliability modules and Streamlit entry point are placeholders. There is no working dashboard or trained forecasting model yet.

The DHS/MIS work remains historical context on prevalence and interventions. Its survey risk categories are not outbreak alerts. Survey estimates will not be interpolated into monthly cases or assigned to LGAs as observed outcomes.

## Stages and deliverables

| Stage | Deliverable | Status |
| --- | --- | --- |
| 1. Scope | Nationwide LGA analysis, user decision and data requirements | Nationwide extraction agreed; smaller modeling pilot undecided |
| 2. Data readiness | Validated monthly cases, reporting metadata, geography and climate data | Case ingestion and initial audit completed; remaining inputs pending |
| 3. Relationship analysis | Rainfall/case charts, lag analysis and geographical comparisons | Planned |
| 4. Forecasting | Seasonal baseline, case-history model and climate-informed model, evaluated over time | Planned |
| 5. Dashboard | Trends, forecasts, uncertainty and reporting-quality flags | Planned |
| 6. AI assistant | Cited document search and explanations using computed analytical results | Later phase |
| 7. Deployment and integration | Hosted pilot, monitoring, CI/CD and evaluation of Chap/DHIS2 integration | Later phase |

See [APPROACH.md](APPROACH.md) for the design and evaluation rules, and [docs/monthly_case_data.md](docs/monthly_case_data.md) for the first input specification.

The selected climate-data route is Python download and LGA polygon aggregation. CHIRPS v3 rainfall acquisition and an ID/geometry audit are implemented; a January 2025 raster sample is available locally. Aggregation of real LGAs awaits boundaries; ERA5-Land temperature acquisition awaits Copernicus setup and implementation. See [docs/climate_data.md](docs/climate_data.md) for commands, source versions and how to obtain polygons from DHIS2. See [CONTRIBUTING.md](CONTRIBUTING.md) for commits, tests and what stays local when the repository is public.

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

For the existing survey analysis, install `requirements.txt` in an isolated environment and use notebooks 01 and 02. Those requirements are the original analysis environment, not a completed deployment specification. No automated NHMIS connection or cloud deployment is configured.

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
