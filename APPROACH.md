# Nigeria Climate-Informed Malaria Early Warning

## Proposed direction

Develop a decision-support prototype aligned with the DHIS2 Climate Tools training: help national and state malaria programme teams identify LGAs that may need additional diagnostic tests and treatment supplies in the coming one to two months. This is a proposed research and prototype scope, not a validated operational alert system.

The agreed extraction and analysis scope is nationwide, covering all 36 states and the FCT by LGA and month. Nasarawa was an initial extraction test only. A smaller modeling pilot, if useful, remains undecided and will be chosen after assessing coverage and quality.

## Connection to the existing project

The current DHS/MIS ingestion and exploratory analysis remain useful as historical context on prevalence and intervention coverage. Retain their original survey-year resolution. Do not interpolate survey prevalence into monthly case counts, assign state survey estimates to LGAs as observed outcomes, or treat survey prevalence and routine reported incidence as interchangeable.

The new forecasting target is future monthly reported confirmed malaria cases. Population denominators can support a separate incidence view when reliable and aligned to the geography. Existing Low/Medium/High prevalence labels remain descriptive survey categories; they do not become outbreak alert thresholds.

## First analytical question

Examine whether rainfall changes are followed by changes in reported confirmed malaria cases, at what delay, and whether this varies by LGA and season. Compare the evidence with ordinary seasonal patterns, temperature and reporting changes. These are local empirical questions; matching rainfall and case peaks does not establish causation. Use this analysis to motivate candidate forecasting features, then test their predictive value on held-out periods.

## Phased delivery

1. **Climate and historical context:** retain survey analysis; add monthly rainfall and temperature, seasonal normals and anomalies for the selected geography. Without routine cases, deliver a climate monitoring demonstration and clearly label any synthetic examples. Do not claim malaria forecast accuracy.
2. **Routine-data pilot:** obtain authorised aggregate monthly case exports, organisation-unit identifiers and boundaries, and reporting metadata. Audit continuity, definitions, missing periods and reporting changes before selecting a forecast period.
3. **Forecast evaluation:** forecast one and two months ahead, compare against seasonal baselines, and assess whether climate variables improve performance over a model using case history alone.
4. **Integration prototype:** produce exportable results keyed to DHIS2 organisation units and periods. Explore Chap compatibility and sandbox visualisation after the local pipeline is reproducible. Production integration depends on instance metadata, permissions, validation and an agreed owner.

## Minimum data contract

| Dataset | Required information |
| --- | --- |
| Monthly health outcomes | Organisation-unit ID, month, confirmed malaria cases, indicator definition and extraction date |
| Reporting quality | Expected and submitted reports, timely reports and reporting deadline where available |
| Geography | Stable organisation-unit IDs, names, parent state, boundaries and boundary-change history |
| Climate | Monthly rainfall total and mean temperature, units, source, spatial aggregation method and data availability date |
| Optional context | Population estimates, tests performed, intervention coverage and known service or reporting changes |

Aim for several complete seasonal cycles, preferably at least five years where available; this is a planning preference, not a guarantee of sufficient data. Never replace missing case reports with zero. Flag absent reporting metadata as unknown quality.

## Features and validation

- Use only values available at each forecast issue date, accounting for reporting delays and climate publication delays. Future observed weather must not enter a historical forecast unless explicitly evaluating an unrealistic oracle scenario.
- Candidate predictors include lagged cases, lagged rainfall and temperature, calendar seasonality and rainfall anomalies. Choose lags through training-period evaluation rather than assuming a fixed local climate relationship.
- Calculate monthly climate normals from a declared historical reference period. For backtesting, avoid using future observations to estimate normals or preprocessing parameters. Percentage anomalies are undefined when normal rainfall is zero; flag those cases or use absolute anomalies.
- Aggregate rainfall over time by summing and temperature by averaging. Across geographical areas, use an appropriate spatial average of rainfall depth rather than summing millimetres across LGAs.
- Use rolling forecast origins with a final held-out time window. Fit preprocessing on training data only. Assess errors separately for each horizon and geography.
- Compare a seasonal naive forecast and a case-history-only model with a climate-informed model. Report MAE, forecast bias and interval coverage when intervals are available. If alert labels are justified, also assess missed events, false alarms and useful lead time.
- Define any alert threshold with programme users and test it historically before claiming operational value. A rainfall anomaly alone is a climate signal, not a validated outbreak prediction.

## Reporting confidence

Replace the planned synthetic reporting-reliability model with transparent checks on observed reporting completeness, timeliness, missing periods, duplicates and abrupt changes. Distinguish reporting quality from predictive uncertainty. Missing DHS RDT measurements indicate survey-data availability, not routine NHMIS reporting reliability.

Show data-quality flags beside forecasts. Do not automatically interpret a fall in reported cases as lower disease risk when reporting deteriorates.

## Intended product

A prototype dashboard showing observed cases, rainfall anomalies, one- and two-month forecasts with uncertainty where supported, reporting-quality flags, and a ranked review table. Each output should state its geography, forecast issue date, target month and data freshness. Programme users determine the response to an alert; model output alone does not establish procurement quantities.

Streamlit can support initial exploration. DHIS2 dashboards and Chap are subsequent integration targets, not existing capabilities of this repository.

## Current repository status

The repository contains DHS/MIS ingestion and exploratory analysis, nationwide monthly case exports for 2020–2025, matched LGA boundaries and CHIRPS rainfall. Reproducible scripts validate the inputs, join case and rainfall records, examine seasonality and evaluate one- and two-month forecasts on rolling 2025 targets. Derived files stay under the Git-ignored data/processed directory. Reporting measures, temperature and historical availability metadata are pending. The initial backtest uses assumed availability delays, with a sensitivity run for slower reporting. Operational integration remains planned.

## Sources

- Local workshop reference: DHIS2_Climate_Tools_Presentation.pptx, especially slides 22, 25 and 31–35.
- DHIS2 Climate Tools: https://climate-tools.dhis2.org/
- Chap modeling documentation: https://chap.dhis2.org/

The workflow above is a project proposal informed by these materials. Data access, local model validity and operational readiness remain to be established.
