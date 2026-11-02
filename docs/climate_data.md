# Climate-data acquisition plan

## Current position

The repository has routine case exports and historical survey data, but no downloaded rainfall, temperature or LGA boundary dataset. The user confirmed the DHIS2 Climate App is available. Start with that route and reuse existing, documented climate imports where suitable.

## First inputs

| Variable | Required measure | Proposed source |
| --- | --- | --- |
| Rainfall | Monthly precipitation total in millimetres, spatially averaged over each LGA | CHIRPS, recording the exact version available |
| Temperature | Monthly mean near-surface air temperature in degrees Celsius, spatially averaged over each LGA | ERA5-Land |
| Geography | LGA polygon geometry and organisation-unit IDs matching the case exports | DHIS2 organisation-unit boundaries where available |

Request January 2019 through December 2025 for initial case/climate analysis. The extra year supplies climate lags for early 2020. A later anomaly analysis needs a separately declared historical reference period; do not calculate a long-term normal from the six case years alone or use future years in a retrospective baseline.

## Preferred route: the available Climate App

1. Check whether climate data elements have already been populated for the relevant LGAs and months. An installed app or a chart in Explore does not establish that data has been imported.
2. In the Climate App, inspect precipitation and temperature for one LGA, verifying that the organisation unit has suitable polygon geometry, the source is identified and the desired months are available.
3. Record the exact source/version, units, period aggregation, spatial method and whether the product is preliminary or final. The app may expose a different CHIRPS version depending on its configuration; do not assume v3 is present or mix versions silently.
4. Reuse existing imported climate data through an authorised monthly export if it matches these requirements. Retain organisation-unit IDs.
5. If data has not been imported, coordinate a sandbox or an import/export with the instance administrator. Do not create data elements or initiate a national production import just because the app is installed.
6. Confirm the first LGA sample and its definitions before scaling extraction to the nationwide roster. Retain failures and missing values rather than dropping LGAs.

Climate App exploration is calculated on the fly through Google Earth Engine, while imports store values in DHIS2. The instance needs Earth Engine configuration and geographical coordinates at the relevant levels. For area-based exposure, confirm polygon geometry rather than substituting facility or LGA centroid points without documenting the change.

## Alternative: reproducible Python extraction

If the app cannot supply suitable series, export the LGA polygons with stable IDs, obtain gridded climate data and aggregate it locally or through Earth Engine. DHIS2 Climate Tools documents downloading ERA5-Land data and aggregating it to organisation units. Direct Copernicus access requires its own registration/authentication; an available Climate App does not imply local Python access is configured.

For a new direct rainfall download, CHIRPS v3 is the preferred candidate to evaluate: the producer now provides v3 and plans to end v2 production after December 2026. Use one documented version across history, normals and evaluation. Record the exact archive, files and access dates. No download or climate integration has been implemented yet.

## Processing and validation

- Join on organisation-unit ID plus YYYY-MM. Reconcile the climate geometry roster with the union of IDs in the case exports; never assume equal names guarantee matching boundaries.
- Rainfall is summed over days within a month, then spatially averaged as rainfall depth over an LGA using an appropriate area-weighted method. Do not sum millimetres across LGAs or grid cells.
- Temperature is a temporal and spatial mean. Convert units explicitly where the source supplies kelvin. Missing raster cells and extraction failures must remain visible.
- Keep raw downloads local, retain source metadata and report unmatched IDs, missing periods, duplicate keys and spatial coverage. Commit acquisition code and documentation rather than routine health exports or credentials.
- Respect publication delays. Final historical climate products and retrospective health exports are not proof of what would have been available at a past forecast issue date. Define that assumption before forecasting evaluation.

## References

- DHIS2 climate-data integration: https://dhis2.org/climate/climate-data/
- Climate App user guide: https://docs.dhis2.org/en/implement/climate-health/climate-app-user-guide.html
- CHIRPS v3 producer documentation: https://www.chc.ucsb.edu/data/chirps3
- CHIRPS transition notice: https://www.chc.ucsb.edu/data/chirps
- ERA5-Land download workflow: https://climate-tools.dhis2.org/guides/getting-data/climate-data-store/era5-download/
- Organisation-unit aggregation: https://climate-tools.dhis2.org/guides/aggregation/org-unit-aggregation/
