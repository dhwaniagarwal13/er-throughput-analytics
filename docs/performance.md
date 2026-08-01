# Performance

Real measurements from this environment, not estimates. Numbers will vary by machine; the point is
that everything in this project is small and fast enough to iterate on interactively — there is no
part of this pipeline that needs a warehouse heavier than DuckDB.

## Warehouse

| Metric | Value |
|---|---|
| Warehouse file size (`data/er.duckdb`) | 4.5 MB (4,730,880 bytes) |
| Total rows across all marts | ~17,270 (9,216 fact + 6,757 hourly-arrivals + 2,297 dimension/aggregate rows) |
| `dbt run` (full rebuild, `make build`) | A few seconds — 9 models over 9,216 source rows. |
| `dbt test` (34 tests) | 5.7 seconds. |

## Query latency

Representative `erops.metrics` calls, timed against the live warehouse (cold connection, no OS page
cache warm-up beyond opening the file):

| Query | Latency |
|---|---|
| `kpi_summary` (headline KPIs, 2 aggregate queries) | 16.6 ms |
| `monthly_trend` | 7.6 ms |
| `demand_heatmap` (weekday x hour) | 6.7 ms |
| `wait_summary_stats` (percentiles, skew, kurtosis) | 7.6 ms |
| `spc_wait_chart` (reads pre-computed `agg_daily_ops`) | 2.6 ms |
| `segment_equity_extremes` (top/bottom 10 of 86 segments) | 8.0 ms |
| `data_quality_report` (5 sub-queries bundled) | 19.2 ms |

Every query used by the dashboard completes in under 20 ms. At this scale, the bottleneck anywhere in
the stack is Python/Streamlit/Plotly overhead, never DuckDB.

## Notebook execution

Full `jupyter nbconvert --to notebook --execute --inplace` per notebook (includes Jupyter kernel
startup, which dominates the wall-clock time — actual query and plotting time inside each notebook is
well under a second per cell): approximately 25-35 seconds per notebook, dominated by kernel spin-up,
not computation.

## Dashboard

- **Streamlit cold start** (first load, warehouse connection + first render of the Overview tab):
  approximately 3-5 seconds in local testing, most of it Streamlit's own startup and the first Plotly
  figure serialization, not the underlying queries (see latency table above).
- **Tab-to-tab navigation:** near-instant after first load — `st.cache_data` wraps one loader function
  per tab, so the warehouse is queried once per tab per session, not on every rerun.
- **Full click-through of all 7 tabs:** verified end-to-end in a live browser session with no console
  errors and no visible lag beyond the initial per-tab data load.

## Why performance is not the constraint in this project

At ~9,200 rows, this warehouse is small by data-engineering standards — the interesting problems here
are correctness of definitions (`docs/measure_spec.md`), statistical honesty (confidence intervals,
multiple-comparisons awareness), and reconciliation across three consumers (notebooks, Streamlit, Power
BI), not query performance. If this pipeline were pointed at a real multi-facility, multi-year dataset
(millions of rows), the aggregate marts (`agg_daily_ops`, `agg_hourly_arrivals`, `agg_segment_waits`)
are exactly the layer that would need incremental materialization to keep this same latency profile.
