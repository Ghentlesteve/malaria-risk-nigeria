# Climate-data acquisition plan

## Current position

The selected route is **Python download and polygon aggregation**, as requested by the user. The Climate App is available as a reference, but extraction will run locally. A CHIRPS v3 January 2025 rainfall sample has been downloaded; no real LGA series has been aggregated yet. LGA boundary geometry and Copernicus access for temperature are pending.

## First inputs

| Variable | Required measure | Proposed source |
| --- | --- | --- |
| Rainfall | Monthly precipitation total in millimetres, spatially averaged over each LGA | CHIRPS v3.0 monthly final Africa GeoTIFFs |
| Temperature | Monthly mean near-surface air temperature in degrees Celsius, spatially averaged over each LGA | ERA5-Land |
| Geography | LGA polygon geometry and organisation-unit IDs matching the case exports | DHIS2 organisation-unit boundaries where available |

Request January 2019 through December 2025 for initial case/climate analysis. The extra year supplies climate lags for early 2020. A later anomaly analysis needs a separately declared historical reference period; do not calculate a long-term normal from the six case years alone or use future years in a retrospective baseline.

## Get LGA polygons from the instance

The case exports put LGAs at hierarchy level 3. While logged in through the browser, open this read-only path on the same instance base URL:

```text
/api/organisationUnits.geojson?level=3
```

Keep any instance base path (for example `/dhis`) before `/api`. Replace the application route, not the whole instance address. Save the response as `data/raw/nigeria_lga_boundaries.geojson`. We expect a GeoJSON FeatureCollection with Polygon/MultiPolygon geometries and DHIS2 IDs at each feature's top-level `id`. A point-only export cannot represent LGA area. An empty or access-denied response requires assistance from the instance administrator. This request reads existing geometry and does not change the national instance.

The boundary audit rejects invalid polygons, duplicate or conflicting IDs and non-WGS84 coordinates. It compares IDs against the observed case roster, including missing and extra boundary IDs. It does not certify historical boundary stability or topology across neighbouring LGAs. No name-based automatic matching is performed.

## Local Python workflow

Use a separate environment because the original requirements describe the older survey-analysis stack:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-climate.lock.txt

# Test a single downloaded rainfall month before scaling up.
.venv/Scripts/python.exe -m src.climate_data download-rainfall --start 2025-01 --end 2025-01

# Run after the boundary file is saved.
.venv/Scripts/python.exe -m src.climate_data boundary-audit --boundaries data/raw/nigeria_lga_boundaries.geojson

# Aggregate the test month only after IDs match.
.venv/Scripts/python.exe -m src.climate_data aggregate-rainfall --boundaries data/raw/nigeria_lga_boundaries.geojson --start 2025-01 --end 2025-01

# Then acquire the full 84-month historical rainfall period (about 400–500 MB).
.venv/Scripts/python.exe -m src.climate_data download-rainfall --start 2019-01 --end 2025-12
.venv/Scripts/python.exe -m src.climate_data aggregate-rainfall --boundaries data/raw/nigeria_lga_boundaries.geojson --start 2019-01 --end 2025-12

.venv/Scripts/python.exe -m unittest discover -s tests -v
```

The lock file records the tested Windows/Python 3.12 environment. `requirements-climate.txt` gives the direct dependency constraints for intentional environment updates; regenerate and test the lock when updating. These packages are separate from the original survey requirements.

Downloads stay under `data/raw/climate/chirps_v3/`. Each raster has a sidecar recording its source URL, version, period, units, retrieval time, server modification date and SHA-256 fingerprint. Re-running verifies the cached file; failed or partial downloads are not accepted as complete rasters. A cached raster without a matching provenance sidecar fails for review.

`aggregate-rainfall` produces `data/processed/climate/rainfall_monthly.csv` and a JSON provenance summary. It requires exact ID agreement between boundaries and the case roster, uses actual pixel-polygon intersections with areas measured in equal-area EPSG:6933, and reuses weights only when raster grids match. It does not resample, use centroid values or multiply the already-monthly CHIRPS totals by the number of days.

The output contains ID, month, rainfall in mm, valid-area fraction and status. Missing/negative/no-data raster values are excluded from valid area. A month with less than the configured valid-area coverage stays blank and flagged. The default `--minimum-coverage 0.999` is an explicit processing threshold, not an epidemiological rule; review it for the actual polygons, coastline and source land mask. Genuine zero rainfall remains zero.

## Temperature step

Use the Copernicus monthly ERA5-Land dataset and select monthly averaged reanalysis, 2m temperature, 2019–2025 and a bounding box derived from the verified polygons. Direct access requires an ECMWF account, dataset terms accepted in the portal, and a local `.cdsapirc` token file. Do not paste tokens into chat or commit them. The credential filename and `.env` files are ignored.

The local credential file is not configured yet. Temperature download and NetCDF aggregation have **not** been implemented or executed; the rainfall commands do not acquire temperature. After access and polygons are available, implement the CDS request from the dataset's current generated API request, verify the time axis/units and convert temperature from kelvin to Celsius before producing matched monthly LGA means.

## Optional reference: Climate App

1. Check whether climate data elements have already been populated for the relevant LGAs and months. An installed app or a chart in Explore does not establish that data has been imported.
2. In the Climate App, inspect precipitation and temperature for one LGA, verifying that the organisation unit has suitable polygon geometry, the source is identified and the desired months are available.
3. Record the exact source/version, units, period aggregation, spatial method and whether the product is preliminary or final. The app may expose a different CHIRPS version depending on its configuration; do not assume v3 is present or mix versions silently.
4. Reuse existing imported climate data through an authorised monthly export if it matches these requirements. Retain organisation-unit IDs.
5. If data has not been imported, coordinate a sandbox or an import/export with the instance administrator. Do not create data elements or initiate a national production import just because the app is installed.
6. Confirm the first LGA sample and its definitions before scaling extraction to the nationwide roster. Retain failures and missing values rather than dropping LGAs.

Climate App exploration is calculated on the fly through Google Earth Engine, while imports store values in DHIS2. The instance needs Earth Engine configuration and geographical coordinates at the relevant levels. For area-based exposure, confirm polygon geometry rather than substituting facility or LGA centroid points without documenting the change.

## Source version

DHIS2 Climate Tools documents downloading ERA5-Land data and aggregating it to organisation units. An available Climate App does not imply local Python Copernicus access is configured.

The downloader is fixed to the producer's CHIRPS v3.0 monthly final Africa archive. The producer plans to end v2 production after December 2026. Use one documented version across history, normals and evaluation. The January 2025 sample verifies acquisition only; full extraction and linkage remain pending boundary data.

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
- Read-only DHIS2 GeoJSON endpoint: https://docs.dhis2.org/en/develop/using-the-api/dhis-core-version-242/analytics.html#geojson
- Verified monthly rainfall archive: https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/africa/tifs/
- Copernicus API setup: https://cds.climate.copernicus.eu/how-to-api
- Monthly ERA5-Land dataset: https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-monthly-means
