# Lane A implementation

Run `cd backend && uv sync --locked`, then `make check-a` from the repository root.
The pinned environment is Python 3.12; network access is unnecessary after setup.
All A-01 through A-18 acceptance checks pass. `evidence.json` records measured results.

## Interfaces for Lane B

```python
from app.data import load_scenario, scenario_ids, summarize, ScenarioLoadError
from app.validate import validate_plan
from app.valuation.value_table import value_table

scenario = load_scenario("standard")
values = value_table(scenario)
# Apply request edits to a copy of scenario before validation.
report = validate_plan(edited_scenario, result)
```

- `ScenarioLoadError.issues` contains structured `InputIssue` models. Ready-after-deadline
  remains a valid planning case. Contradictory hard locks are reported, never removed.
- Compute result hashes with `scenario_hash(base_scenario, edits)`, before applying edits.
  The loader produces exactly the hashes in the frozen tiny fixtures.
- The validator accepts the edited scenario. It recomputes constraints, job states,
  crew-day usage, objective totals, and assignment values. Report every crew-day,
  including unused days, in `result.crew_days`.
- Crew utilization includes onsite plus travel minutes divided by **all** available
  crew minutes. Frozen fixture values have four decimal places, so the validator allows
  absolute rounding error of 0.000051 for this one field. Other floating totals use 1e-6.
- `changed_installs` counts an unlocked current install whose crew/date changed or which
  was removed. Locked jobs cannot be moved or omitted. `total_delay_days` excludes the
  unscheduled penalty; that penalty belongs to the recovery stage objective.
- Jobs with no skill/geography/readiness/calendar option before deadline filtering are
  blocked. Strict mode still requires all other jobs by deadline. Resource contention
  does not by itself prove a hard blocker. Force-included jobs require an on-time slot
  even in recovery mode.
- An infeasible/timeout/invalid-input response has no assignments, usage or objective.
  For these, the validator checks empty-result shape; it does **not** prove a solver's
  infeasibility claim. Its report is labeled `independent-v1:no-incumbent-shape`.
- `app.validate.enumerate_tiny.enumerate_tiny` independently enumerates small scenarios,
  using no planner imports. It returns a proven optimum or `None` for infeasible cases.
  Pass an already-edited scenario and forced site IDs. A combination budget prevents
  accidental use as a production planner. It reproduces all five frozen plan cases.
- Tiny energy coefficients are explicitly `assumed_zero`, matching its fixture. Other
  scenarios require complete prepared prices; missing data never becomes zero value.
- The value table covers every calendar date in the planning horizon, including dates
  without crew availability. Filter candidates in the planner. Identical batteries in
  one zone/date share a solve and receive identical unrestricted-export values.
- Value rows include commissioning UTC, input hash, kind and solver status. Operation
  starts at midnight after installation plus the qualification lag. A non-optimal
  dispatch solve raises `ValueError` rather than supplying an exact coefficient.
- Precompute standard valuations before a demo. The first run measured about 21 seconds
  for 360 rows; an unchanged reload took about 0.001 seconds. These are **valuation
  preparation** measurements, not scheduling performance. Content hashes include
  scenario inputs, prices, loads when applicable, and model version. Cache writes are
  atomic; corrupt/incomplete caches are recomputed.

## Prepared datasets and provenance

`standard` has 30 synthetic jobs, three synthetic clusters, three crews, and ten working
weekdays. Its existing plan validates with all 30 jobs on time. Geometry, readiness,
commitments, crew resources and travel allowances are synthetic assumptions.

The committed `prices.parquet` contains 5,376 observed LZ_HOUSTON quarter-hours from
2018-06-04 through 2018-07-29. The official workbook contains both `LZ` and `LZEW` rows:
preparation explicitly selects `LZ`. Repeated-hour flags select UTC offsets; nonexistent
local times, duplicate intervals and missing intervals are rejected. No price filling
or interpolation occurs. The ERCOT manifest records the exact download URL and hash.

The committed `loads.parquet` contains one **modeled ResStock Texas archetype**, from
2025 release 1, AMY 2018, baseline model 100, over the same window. It is assigned to all
synthetic sites only for sensitivity analysis. It is not measured household demand and
was not selected to represent specific Houston parcels. Published interval ends use
fixed EST (UTC-5); preparation converts them to UTC starts and converts kWh to kW.
The ResStock license notice is retained in `data/LICENSE_RESSTOCK.md`.

Use `value_table(scenario, load_limited=True)` for the standalone load-limited sensitivity.
`export_allowance_kw` defaults to zero. Default `value_table(scenario)` and plan validation
use unrestricted export; the frozen API contract has no valuation-mode selector, so this
optional sensitivity is not silently substituted into API plan results. Its output is
modeled gross operating margin, not a retail bill, lifetime profit, or operational savings.

`standard_real` combines 30 current HCAD A1 parcel candidates with synthetic operations.
Three bounded requests fetch ten polygons each and request only OBJECTID and STATE_CLASS.
Prepared features keep geometry, a seeded opaque ID, and the assumed cluster. No owner
names or addresses survive. Generated observed files are ignored because redistribution
terms have not been established. The code and manifests are committed; a fresh clone
can regenerate the local sample explicitly. Source geometry is current, so combining it
with 2018 prices is a constructed benchmark, not a historical reconstruction.

## Reproduce preparation

Run these from `backend/`. Download commands are explicit; no loader or server startup
contacts an external service. Raw downloads and derived caches are ignored by Git.

```bash
uv run python -m app.data.generate_standard
mkdir -p ../data/raw
curl -fL 'https://www.ercot.com/misdownload/servlets/mirDownload?doclookupId=642564849' \
  -o ../data/raw/RTMLZHBSPP_2018.zip
uv run python -m app.data.prepare_ercot \
  --input ../data/raw/RTMLZHBSPP_2018.zip \
  --output ../data/demo/standard/prices.parquet
curl -fL 'https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2025/resstock_amy2018_release_1/timeseries_individual_buildings/by_state/upgrade=0/state=TX/100-0.parquet' \
  -o ../data/raw/resstock-tx-100-0.parquet
uv run python -m app.data.prepare_resstock \
  --input ../data/raw/resstock-tx-100-0.parquet --scenario-dir ../data/demo/standard
uv run python -m app.data.prepare_hcad --download
```

The synthetic generator uses seed 42 by default and has a byte-for-byte reproducibility
test. The preparation pipeline then attaches observed-price and modeled-load provenance.
Manifests distinguish synthetic, observed, derived and modeled fields and hash the final
prepared files. Retrieval dates reflect each download's local modification timestamp.

Source references: [ERCOT archive](https://www.ercot.com/mp/data-products/data-product-details?id=np6-785-er),
[ERCOT redistribution terms](https://www.ercot.com/help/terms),
[ResStock timestamp and unit conventions](https://natlabrockies.github.io/ResStock.github.io/docs/FAQ.html),
[ResStock dataset release](https://resstock.nlr.gov/datasets),
[HCAD layer](https://mycity2.houstontx.gov/pubgis02/rest/services/PDD/HCAD_Parcels/MapServer/0).
