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

The existing forecasting script produces retrospective point predictions and scores. Running the model through Chap requires separate training and prediction entry points. Start by checking the seasonal baseline, then compare its one- and two-month predictions on shared historical targets. For the rainfall model, preserve the case and rainfall availability cutoffs at each forecast origin before comparing its scores. Predictive intervals require a separate uncertainty method and evaluation. [Chap model interface](https://chap.dhis2.org/chap-modeling-platform/external_models/describe_model/)

Connecting the DHIS2 Modeling app to a sandbox Chap backend is a later step and requires a sandbox instance and administrator access. [DHIS2 Modeling setup](https://chap.dhis2.org/chap-modeling-platform/modeling-app/fresh-installation/)
