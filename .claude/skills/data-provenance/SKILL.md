---
name: data-provenance
description: Rules for preparing, labeling, and documenting data in this repo. Use when writing loaders, fixture generators, ERCOT or HCAD or ResStock preparation, manifests, or any code or UI text that shows where a number came from. Covers manifest fields, observed vs modeled vs derived vs assumed vs synthetic, timezone rules, ERCOT interval-ending and DST handling, missing prices, raw data location, and anonymization.
---

# Data provenance

Every number we show has a known source and a label. If we cannot say where it came from, we do not show it.

## Kinds (`DataKind` in `backend/app/contracts/enums.py`)

| Kind | Meaning | Example |
|---|---|---|
| `observed` | Taken from a public source, only reformatted | ERCOT settlement price |
| `modeled` | Output of a model on observed inputs | Battery dispatch value, ResStock load |
| `derived` | Computed from other fields by a fixed rule | Site centroid from a parcel polygon |
| `assumed` | A stated benchmark input we chose | Travel allowance, qualification lag |
| `synthetic` | Generated or hand-built, not real | Tiny fixture, standard generator output |

Label at three levels:
1. Data: `ProvenanceNote` entries in `scenario.yaml`, `fields` in each `Manifest`.
2. API: `ScenarioConfig.synthetic`, `PlanResult.assumptions` (each with a `kind`).
3. UI: the header provenance badge and the assumptions list.

## Manifest (`Manifest` model)

Write one JSON file per prepared dataset to `data/manifests/<dataset_id>.json`.

| Field | Rule |
|---|---|
| `dataset_id` | Stable snake_case, e.g. `ercot_np6_785_2018` |
| `kind` | Dominant kind of the dataset |
| `source_url` | Exact URL or report ID used. `null` for synthetic |
| `release` | Source version, report date, or doc ID |
| `retrieved_at` | UTC timestamp of the download |
| `covered_start`, `covered_end` | Dates the data covers |
| `license_notes` | Redistribution terms. "Unknown, not redistributed" if unsure |
| `sha256` | Of the prepared output file |
| `transformation` | One or two sentences: filters, joins, unit changes |
| `row_count` | Rows in the prepared output |
| `fields` | Map of column to `DataKind` |

Compute `sha256` over file bytes. Rewrite the manifest whenever the output changes.

## Where files live

- `data/raw/`: downloads, gitignored. Never commit. Never read raw files at app startup.
- `data/demo/<scenario>/`: prepared, committed, small inputs the app reads.
- `data/manifests/`: committed manifests.
- `data/cache/`: gitignored derived caches (value tables).
- Preparation runs only by an explicit command. It never runs automatically at startup.
- If redistribution terms are unclear, commit the preparation script and the manifest, not the data. Keep a labeled synthetic fallback.

## Time

- Scheduling dates: `America/Chicago` calendar dates (`dt.date`). No times.
- Energy timestamps: timezone-aware UTC (`timestamp_utc`), plus `interval_hours`.
- Never store naive datetimes. Never merge ambiguous local timestamps.

### ERCOT NP6-785-ER (settlement point prices)

- Local times are interval-ending. Hour ending 01:00 covers 00:00 to 01:00. 15-minute rows: `Delivery Hour` plus `Delivery Interval` 1 to 4.
- Interval start (local) = hour_ending - 1 h + (interval - 1) * 15 min.
- The fall-back day has a repeated hour. ERCOT marks the second copy with a flag (`Repeated Hour Flag` in the historical workbooks, `DSTFlag` in some API reports). Check the real column name in the file. Use the flag to pick the right UTC offset. Do not guess from row order alone.
- The spring-forward day has 23 hours. Expect 92 intervals, not 96.
- Convert to UTC with `zoneinfo.ZoneInfo("America/Chicago")` and set `fold=1` on the flagged repeated hour.
- Filter to load zones (`LZ_HOUSTON`, etc.). Keep USD/MWh.
- Check that every expected interval exists. Report missing intervals as `MISSING_INTERVAL`. Never fill, interpolate, or forward-fill prices.
- Fallback order: ERCOT archive, then gridstatus, then labeled synthetic prices.

### Aligning loads and prices

Align on interval start in UTC with equal `interval_hours`. Resample only by explicit, documented rules. Report rejected rows with counts.

## Anonymization (HCAD and any parcel data)

- Assign `site_id` from a seeded hash. Never use the account number or address as an ID.
- Drop owner names, mailing addresses, and site addresses before anything leaves `data/raw/`.
- Keep only geometry, cluster assignment, and the attributes the model needs.
- Parcels are candidate locations, not customers. Say so in UI copy.

## Synthetic data

- Fixed seed in the generator and in `scenario.yaml` (`random_seed`).
- `synthetic: true` in `scenario.yaml`. A `ProvenanceNote` with `kind: synthetic`.
- Byte-identical output for the same seed. Test this.
- The UI shows a "Synthetic" badge whenever `config.synthetic` is true.

## Wording

- "Modeled operating margin with 2018 hindsight prices." Never "revenue", "profit", "savings", or "ROI".
- "ResStock archetype load", never "the household's load".
- Say what is assumed: "Travel is a fixed 60-minute allowance per crew-day in North."
