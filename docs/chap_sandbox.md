# Chap sandbox

The first step is to validate the historical monthly cases and rainfall in Chap. The project uses DHIS2 organisation-unit IDs as Chap's `location` values so the same keys identify the case records, rainfall records and map boundaries. [Chap data format](https://chap.dhis2.org/chap-modeling-platform/external_models/data_formats/)

Generate the input from the repository root after preparing the routine case and rainfall files.

```powershell
python -m src.chap_export
```

The export writes `data/processed/chap/nigeria_malaria_monthly.csv`. It includes every LGA and month within the case file's date range. Missing case counts remain blank, including months absent from the case file. The export stops if any LGA-month has unavailable rainfall.

With Chap Core installed, validate the CSV and its matching boundaries.

```powershell
chap validate --dataset-csv data/processed/chap/nigeria_malaria_monthly.csv --dataset-geo data/processed/climate/nigeria_lga_boundaries_ocha_matched.geojson
```

The official CLI guide describes the supported setup for Windows and the standalone evaluation workflow. [Install Chap Core](https://chap.dhis2.org/chap-modeling-platform/chap-cli/chap-core-cli-setup/) · [Validate the data](https://chap.dhis2.org/chap-modeling-platform/external_models/prepare_data/validate-data/)

The [seasonal baseline](../integration/chap/seasonal_baseline/) implements the Chap train and predict commands. It forecasts the reported case count for the same LGA and month one year earlier. If that count is missing from the training history, the command reports the affected LGA and month. Use a complete subset for the first Chap evaluation. The model writes one prediction per requested LGA-month in `sample_0`. [Chap model interface](https://chap.dhis2.org/chap-modeling-platform/external_models/describe_model/)

The local parity check trains only on case counts available under each assumed delay and compares predictions on the targets scored by the existing backtest. A Chap evaluation must use equivalent forecast origins and targets to make its scores comparable. For the rainfall model, preserve the case and rainfall availability cutoffs at each origin. Predictive intervals require a separate uncertainty method and evaluation.

Connecting the DHIS2 Modeling app to a sandbox Chap backend is a later step and requires a sandbox instance and administrator access. [DHIS2 Modeling setup](https://chap.dhis2.org/chap-modeling-platform/modeling-app/fresh-installation/)
