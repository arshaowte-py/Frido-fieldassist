# Frido GT Field Intelligence

Dashboard over Frido's FieldAssist exports. General trade, Apr–Aug 2026.

`dist/index.html` is self-contained — data is baked in at build time. Open it directly,
or drop the `dist/` folder on Vercel. `vercel.json` points to `dist/` as the output.

## Refresh flow

Drop new FieldAssist exports into `raw/` (keep FieldAssist's default filenames — the ETL
globs by prefix), then:

```bash
pip install pandas openpyxl --break-system-packages
python3 etl.py raw aggregates.json
python3 build.py
```

Commit `dist/`, `aggregates.json` and the updated raw files. Vercel rebuilds on push.

Multiple order dumps in `raw/` are concatenated — Order No is per product line, not per
order, so the ETL does not dedupe on it. FieldAssist exports pulled on non-overlapping
date ranges will not overlap on Order No; the ETL warns if any do.

## Widening the date range

Add the months to `PERIODS` in `etl.py`:

```python
PERIODS = ["April", "May", "June", "July", "August"]
```

## Files

| file | role |
|---|---|
| `raw/` | untouched FieldAssist exports (gitignored) |
| `etl.py` | reads every export, emits `aggregates.json` (~45 KB) |
| `template.html` | markup + CSS + JS, `/*__DATA__*/` is the injection point |
| `build.py` | substitutes JSON into template |
| `dist/index.html` | the deployable artefact |
| `test.js` | jsdom pass — renders every tab, flags empty panels |
| `vercel.json` | tells Vercel `dist/` is the output directory |

## Definitions

- **Visit** — one unique `Order No` in the Secondary Order Dump. Unproductive visits carry
  a no-sale reason instead of product lines.
- **Order / productive call** — a visit whose lines sum to net value > 0.
- **Field day** — `Total Present` from Employee Productivity. Per-day metrics divide by
  this, never by calendar days.
- **Outlet base** — Outlet Dump GeoHierarchy deduplicated on `Outlet Erp Id`.
- **Indicative gap value** — zone sales × (national category share − zone category share).
  A prompt for the sales team, not a forecast. Only zones holding ≥3% of national sales.

## Validation

Net sales of ₹6,99,29,783 derived from the order dump reconciles to the rupee against the
sum of NetValue across both dump files. Company conversion of 13.8% matches Employee
Productivity's own PC/TC to within 1%.

## Working agreement

All git commands run by the repo owner. Claude Code does not run `git checkout`, `add`,
`commit`, `push`, `status`, `restore`, `stash` or `diff`.
