# Frido GT Field Intelligence — V1

Dashboard over Frido's FieldAssist (SFA) exports. General trade, Apr–Jun 2026.

`dist/index.html` is self-contained — data is baked in at build time. Open it directly,
or drop the `dist/` folder on Netlify. No server, no CDN dependency except Google Fonts
(it degrades to system fonts offline).

## Build

```bash
pip install pandas openpyxl --break-system-packages
python3 etl.py raw aggregates.json     # raw exports -> aggregates
python3 build.py                        # aggregates + template -> dist/index.html
```

## Layout

| file | role |
|---|---|
| `raw/` | untouched FieldAssist exports |
| `etl.py` | reads every export, emits `aggregates.json` (~40 KB) |
| `template.html` | all markup, CSS and JS; `/*__DATA__*/` is the injection point |
| `build.py` | substitutes the JSON into the template |
| `dist/index.html` | the deployable artefact |
| `test.js` | jsdom pass — renders every tab, checks for empty panels and unresolved values |

## Refreshing with new months

Drop the new exports into `raw/` and re-run both scripts. The ETL globs by filename prefix
and takes the first match for single-file reports, all matches for the monthly ones
(`Employee_Productivity_Report*`, `Attendance_Report*`), so keep FieldAssist's default
filenames. The quarter is pinned by the `Period` column — widen the `Q = dump[...]` filter
in `etl.py` to take more months.

## Definitions

- **Visit** — one unique `Order No` in the Secondary Order Dump. Unproductive visits appear
  as rows carrying a no-sale reason instead of product lines.
- **Order / productive call** — a visit whose lines sum to net value > 0.
- **Field day** — `Total Present` from Employee Productivity. Per-day metrics divide by this,
  never by calendar days.
- **Outlet base** — Outlet Dump GeoHierarchy deduplicated on `Outlet Erp Id`; the raw export
  repeats outlets mapped to more than one beat (27,883 rows → 24,858 outlets).
- **Indicative gap value** — zone sales × (national category share − zone category share).
  A prompt for the sales team, not a forecast. Only zones holding ≥3% of national sales qualify.

## Validation

Net sales of ₹4,53,08,682 derived from the order dump reconciles to the rupee against the
Product Category Analysis export, which is the check that the dump is complete. Company
conversion of 13.9% reconciles with Employee Productivity's own PC/TC.

## Known gaps in the source data

These are FieldAssist configuration gaps, not build gaps. The Data notes tab spells each out.

1. No target data — Employee T/A Report has never exported successfully.
2. Journey planning is off; CAP, PJP Adherence % and SC are zero for every user, every month.
3. No modern trade — all 24,858 outlets carry channel `GT`.
4. 3,391 outlets (13.6%) have no shop type. No Physio or Clinic type is defined in the instance.
5. 42 users have no designation; designation only ever holds L1–L4, mirroring position level.
6. `ProductDivision` is unpopulated, so category analysis runs on `PrimaryCategory`.

## Working agreement

Arfa runs all git commands herself. Claude Code must not run any git command —
no checkout, add, commit, push, status, restore, stash or diff.
