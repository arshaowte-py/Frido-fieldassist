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
| one row per visit line | `Visit Id` | Distributors tab, Outlets at risk |
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

## Reading the dashboard

**Navigation.** Sections live in a left sidebar, one icon and label each. It
collapses to a 64px icon rail via the chevron in its header, and that preference
is remembered in `frido-side` — the wide tables (Category × Region, the churn
list) get the width back when it is collapsed. Below 860px the sidebar becomes an
off-canvas drawer behind a hamburger in a slim top bar; the drawer closes on
selection, on Escape, on the scrim, and when the window grows back to desktop
width. It is a real tablist: up/down arrows move between sections, Home and End
jump the ends, and only the selected section is in the tab order.

**Trend arrows.** The Overview KPIs carry a month-on-month delta. A FieldAssist pull
almost always ends mid-month — this one stops on 13 August — so trending the final
month against a full one reads as a collapse that never happened. Short months are
identified by field-days per active rep (a part month is short on days but not on
people) and the arrows compare the last two **complete** months, naming the basis on
each tile. Conversion moves in percentage points, not percent-of-a-percent.

**CSV export.** Every filterable table has a CSV button. It exports what the filters
and sort currently select — all matching rows, not just the capped view on screen —
as raw values rather than formatted text, so `1276003` lands in the sheet, not
`₹12.8 L`. A UTF-8 BOM is prepended so Excel opens the rupee sign and Indian names
correctly.

**Deep links.** The URL carries the tab and the shared filters:
`#tab=outlets&seg=Churned`. Paste one into WhatsApp and the recipient opens the view
you were looking at. The hash is the *entire* shared state — a filter absent from the
link is cleared rather than inherited, or the link would show the recipient's filters
instead of the sender's.

**Sticky filters.** Filters keyed on zone, month, manager or segment are shared: pick
"West" once and every table that offers it follows, across tabs. Free-text search
boxes stay local to their table — sharing a half-typed search would be noise. Add a
key to `STICKY_KEYS` in `template.html` to make another filter shared.

## Outlets at risk

Per-outlet recency, frequency and value, built from the line-level Product Performance
export. Recency is measured from the last date **in the file**, never from `today` —
dating it from now would silently reclassify every outlet as churned as the export
ages on disk.

| segment | meaning |
|---|---|
| Active | ordered within 30 days |
| New | first bought within those same 30 days, so there is no lapse to judge yet |
| At risk | last order 30–60 days ago — one missed reorder cycle |
| Churned | last order more than 60 days ago — roughly two missed cycles |

The bands are `BAND_ACTIVE` and `BAND_RISK` in `enrich.py`; the tab states them in
its own copy, so change both together.

This tab inherits the position filter on the Product Performance pull, so it covers
51 reps and about 47% of national billed value. **An outlet last served by a rep
outside that export looks quieter here than it is.** The tab says so on its face.
Re-pulling the export with the position filter cleared fixes it.

## Colour and theme

Every colour on the page is a CSS custom property, so light/dark is a token swap
with no re-render. The toggle sits in the sidebar footer, and again in the
narrow-screen top bar; both write `frido-theme` to localStorage and stamp
`data-theme` on `<html>`. No stored value means "follow the OS", and an inline
script in `<head>` applies the choice before first paint so the page never
flashes the wrong mode.

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
| `enrich.py` | the three Product Performance reports → assortment, hierarchy, distributors, outlet RFM |
| `template.html` | markup + CSS + JS, `/*__DATA__*/` is the injection point |
| `build.py` | substitutes JSON into template |
| `dist/index.html` | the deployable artefact |
| `test.js` | jsdom pass — renders every tab, exercises filters, CSV, trend and deep-link state |
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
- **Lapsed** — an outlet that is at risk or churned. The two together are the call list.
- **Dormant value** — what a rep's lapsed outlets billed while they were still buying.
  It is money that has stopped arriving, not a forecast of what chasing them recovers.
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
