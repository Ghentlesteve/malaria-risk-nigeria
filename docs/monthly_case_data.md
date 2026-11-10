# Monthly case-data specification (version 1)

## Unit of observation

One row per organisation unit per calendar month, with a single agreed definition of confirmed malaria cases. The agreed scope is nationwide LGA data across all 36 states and the FCT. Never mix state totals and their LGAs in one modeling series or silently combine different case definitions.

Nasarawa was the initial extraction test. The local routine exports span January 2020 through October 2026. The template in `templates/monthly_cases.csv` contains only column headers.

## CSV fields

Use UTF-8 CSV with the exact column names below. Unknown extra columns cause an error to catch typos and accidental schema changes. Map additional breakdowns explicitly before validation; do not sum age groups, sex groups or test categories without checking for overlapping totals.

| Field | Required column? | Values |
| --- | --- | --- |
| org_unit_id | Yes | Nonempty stable ID, stored as text |
| org_unit_name | Yes | Nonempty organisation-unit name |
| state | Yes | Nonempty parent state; use consistent naming |
| period | Yes | Calendar month, `YYYY-MM`; map DHIS2 `YYYYMM` explicitly |
| confirmed_cases | Yes | Nonnegative whole count; blank if missing, zero only if an actual reported zero |
| reports_expected | No | Nonnegative whole count of expected reports |
| reports_received | No | Nonnegative whole count of reports received |
| reports_on_time | No | Nonnegative whole count received by the agreed deadline |
| tests_performed | No | Nonnegative whole count, with definition documented |
| population | No | Positive whole population estimate appropriate to geography and period |

Optional columns may be omitted or blank. Blank means unknown; strings such as `NA`, `-` and `null` require deliberate mapping to blank. Fractions, scientific notation, negative numbers and infinity are invalid. Counts are limited to 18 digits. Remove thousands separators before validation. Whitespace around values is ignored for checking.

Reporting counts must refer to the same reporting dataset, frequency and population of reporting units. Do not enter percentages into count fields. The initial validator checks `reports_on_time <= reports_received <= reports_expected` wherever the relevant pair is present. It does not assume confirmed cases must be below tests performed because their definitions may differ; assess that separately with the data owner.

## Accompanying export notes

Save these locally alongside the export in `data/raw/` before analytical use:

- Source instance, extraction date and who can clarify the definitions.
- Exact indicator IDs, case definition, age coverage and confirmation methods; flag definition changes.
- Reporting dataset, expected reporting units, deadline and treatment of late/revised reports.
- Requested unit roster and date range, missing LGAs, boundary changes and known service disruptions.
- Population source and reference year where supplied.

These notes are manual readiness requirements. The CSV validator does not check their presence or correctness.

## What the checker does

Run `python -m src.data_utils data/raw/monthly_cases.csv` from the root. It reports errors and warnings with CSV record numbers, plus aggregate counts. Exit code is 1 for errors and 0 otherwise; warnings still require review. Record 1 is the header. A JSON summary can be saved with `--report`, keeping it under a Git-ignored data directory. Input CSVs are never rewritten.

Errors include missing/unknown/duplicate headers, malformed rows or periods, missing IDs/names/state, duplicate unit-months, inconsistent names/state for one ID, invalid numbers, impossible reporting totals and an empty file. Warnings identify blank case counts, unknown reporting measures, zero expected reports and missing months between each unit's first and last observed month.

The checks preserve leading zeros in IDs. They do not fill missing months or case counts. Coverage is limited to observed units and their internal date ranges; checking the full requested window and expected LGA roster requires the export notes and a later readiness audit. A clean CSV is not proof of sufficient history, reliable reporting, stable geography, appropriate access or forecasting validity.

## Supplied DHIS2 exports

Run `python -m src.ingest_dhis2` to reshape the supplied yearly files. The importer supports full headings such as `January 2020` and short headings such as `Jan-25`, using the four-digit filename year to verify the month labels. It converts whole decimal counts such as `68.0` to `68`; fractional values fail instead of being rounded. Blanks remain blank. Preserve the raw exports for reference.

The selected indicator is `MAL - Malaria cases confirmed (number)`. The user supplied its formula as RDT-positive persons plus microscopy-positive persons with no denominator. Record that as user-supplied metadata; the export files do not contain the indicator definition or its UID. Obtain age scope and historical definition changes before treating all years as fully comparable.

For reporting measures, request NHMIS 2019 dataset-level expected reports, actual reports (registered complete) and actual reports on time. Do not search for malaria-only reporting rates unless separately defined. Dataset completion is context and does not guarantee completion of the malaria fields.

Source cells map to the combined table through `monthly_cases_lineage.csv`. The audit records fingerprints, blank case cells and unit-years absent relative to the union of observed IDs. It does not create absent observations or assume a national master roster was supplied. Check zero-suppression settings if exports contain blanks but no explicit zeros.

## Next inputs

Climate will be a separate table keyed by the same ID and month, with declared units, sources, spatial aggregation and availability dates. Establish the pilot and boundary metadata before climate extraction. Future validation will check join coverage and what data would have been available at each forecast issue date.
