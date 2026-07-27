# Power BI layer

The `.pbix` is **presentation only**. Every number it shows is computed in dbt and arrives as a flat CSV — see the architecture note in the root README. If you find yourself writing a calculated column here that changes a value, it belongs in a dbt model instead.

## Building the report

1. `make build && make export` — writes `data/exports/*.csv`
2. Power BI Desktop → **Get Data → Text/CSV**, load every file in `data/exports/`
3. **View → Themes → Browse for themes** → `powerbi_theme.json`
4. Model view: relate the fact and aggregate tables to the dims on their key columns; set `dim_date` as the date table
5. Paste the measures from `dax_measures.txt` (Modeling → New measure)

## Pages

| Page | Purpose | Key visuals |
|---|---|---|
| Executive Summary | Is the department meeting its commitment? | KPI cards with MoM deltas, monthly volume trend, % within target gauge |
| Patient Flow | When does demand arrive and when does it hurt? | hour × weekday arrivals matrix (heatmap), arrivals-vs-median-wait scatter, wait distribution |
| Service Quality | Is the process stable, and for whom? | XmR control chart, admission-rate p-chart, wait by segment with error bars |

## Palette notes

The theme uses the validated eight-slot categorical palette in fixed slot order — **do not let Power BI reassign colors by rank**. Assign each series its slot explicitly so a filter that drops a series does not repaint the survivors.

Three slots (aqua, yellow, magenta) fall below 3:1 contrast against the light surface. That is acceptable *only with relief*: those series carry visible direct labels, or the visual has a table view available. Do not use them for a thin unlabeled line.

`minimum`/`center`/`maximum` are a single-hue blue ramp, intended for the arrivals heatmap conditional formatting. Sequential means one hue, light to dark — do not swap in a rainbow scale.

Status colors (`good` / `bad` / `neutral`) are reserved for SPC signals and target attainment. They are never used as a series color, and an out-of-control point carries a marker shape and label as well as color.
