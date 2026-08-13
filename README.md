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

## Product Performance exports

All three Flexible Report exports share the same filename prefix, so `enrich.py` tells them
apart by header shape rather than name — drop them in `raw/` and they sort themselves out:

| shape | header marker | feeds |
|---|---|---|
| rep × SKU × month pivot of UPC | `L2Position User` | Assortment tab, manager scorecard |
| one row per visit line | `Visit Id` | Distributors tab |
| shop channel × category totals | `Shop Channel` | reconciliation only |

Each block is optional. If an export is missing, its tab does not render and the rest of
the dashboard is unaffected.

**Pull these with the position filter cleared.** The first set covered 51 of 124 reps and
about 47% of booked value, which is why the Assortment and Distributors tabs carry a
partial-scope caveat. The dashboard states its own coverage on those tabs, so a filtered
export is safe to ship — it is just narrower than it looks.

## Widening the date range

Add the months to `PERIODS` in `etl.py`:

```python
PERIODS = ["April", "May", "June", "July", "August"]
```

## Colour and theme

Every colour on the page is a CSS custom property, so light/dark is a token swap
with no re-render. The toggle sits in the masthead; it writes `frido-theme` to
localStorage and stamps `data-theme` on `<html>`. No stored value means "follow the
OS", and an inline script in `<head>` applies the choice before first paint so the
page never flashes the wrong mode.

**To match brand colour, edit only the `FRIDO BRAND` block** at the top of
`template.html` — three hexes (`--brand-ink`, `--brand`, `--brand-warm`). The
placeholders there are a reasonable stand-in, not the official values; swap in the
real ones and nothing else needs to change.

The data-viz roles are a separate, validated set — light and dark steps chosen for
their own surface rather than flipped:

| role | meaning | light | dark |
|---|---|---|---|
| `--gain` | converted / positive | `#0F7D52` | `#2CA277` |
| `--loss` | shop-related issue | `#B03A22` | `#DE6244` |
| `--cool` | company / distributor / product | `#2F72BC` | `#5497DE` |
| `--warn` | competitor | `#CE8C00` | `#C98500` |
| `--neut` | unexplained / misc | `#B7BEC5` | `#5A646E` |
| `--seq` | sequential magnitude (matrix) | `#2F72BC` | `#5497DE` |

Two constraints are load-bearing, not cosmetic:

- **`ROLE_ORDER` in `template.html` keeps `loss` and `warn` apart.** Ribbon segments
  are sorted into that order so the two warm hues are never adjacent — that pair is
  the one that fails the dark-mode colourblind separation gate. Reordering it
  without re-validating will quietly break the ribbon for deuteranopic readers.
- **`--t1` is a single tint step, not a ramp.** Same-category segments alternate
  between `--t0` and `--t1`; the 2px surface gap does the rest. A deeper ramp drops
  at least one role's in-segment label under 4.5:1 in one of the two themes.

To re-validate after any change, run the palette through the checker
(`worst adjacent CVD ΔE ≥ 8`, `normal-vision ΔE ≥ 15`, contrast ≥ 3:1 vs surface):

```
node validate_palette.js "#0F7D52,#B03A22,#2F72BC,#CE8C00" --mode light --surface "#FFFFFF"
node validate_palette.js "#2CA277,#DE6244,#5497DE,#C98500" --mode dark  --surface "#151A21"
```

Dark passes every check. Light carries two documented WARNs — `loss`↔`gain` CVD 6.6
and amber's 2.85:1 contrast — both relieved by what the ribbon already ships: a
direct percentage label in each segment, a key naming every segment, and the same
numbers available as a table.

## Files

| file | role |
|---|---|
| `raw/` | untouched FieldAssist exports (gitignored) |
| `etl.py` | reads every export, emits `aggregates.json` |
| `enrich.py` | the three Product Performance reports → assortment, hierarchy, distributors |
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
- **UPC** — a unique productive call: one outlet buying one SKU inside one month. Counts
  distribution width, not value.
- **Reordered** — an outlet with more than one separate billed visit inside the window.

## Validation

Net sales of ₹6,99,29,783 derived from the order dump reconciles to the rupee against the
sum of NetValue across both dump files. Company conversion of 13.8% matches Employee
Productivity's own PC/TC to within 1%.

## Working agreement

Claude Code commits and pushes to its designated feature branch. It does not push to
`main` or open a pull request unless asked — merges are the repo owner's call.

Regenerate `aggregates.json` and `dist/index.html` in the same commit as any change to
`etl.py`, `enrich.py` or `template.html`, so the deployed artefact never trails the source
that built it. Run `node test.js` before pushing.
