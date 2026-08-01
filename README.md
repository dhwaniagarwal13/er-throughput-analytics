# ER Throughput & Patient Flow Analytics

An end-to-end analytics platform for emergency-department operations: how demand arrives, how long patients wait, where the bottlenecks sit, and whether the department is statistically *stable* or drifting.

Built on the Maven Analytics **Hospital Emergency Room** dataset (~9K visits) with a DuckDB + dbt warehouse feeding two dashboards — an interactive Streamlit app for analysts and a Power BI report for executives.

> **Status: in progress.** The warehouse skeleton and pipeline scaffolding are in place; models, notebooks and dashboards are landing incrementally. See the [roadmap](#roadmap).

---

## The question this answers

An emergency department cannot choose how many patients arrive. It can only choose how it is staffed and organised to meet them. So the operationally useful questions are:

1. **Is demand predictable?** If arrivals follow a stable hour-of-day and day-of-week pattern, staffing can be matched to it. If they don't, the department is reacting rather than planning.
2. **How long do patients actually wait?** Not the average — the median and the 90th percentile, and the share seen within a 30-minute target.
3. **Where does the wait break down?** At what arrival volume does wait time degrade non-linearly? That threshold is the effective capacity ceiling.
4. **Is the process in control?** Statistical process control separates normal day-to-day variation from genuine special-cause signals worth investigating.
5. **Does experience differ by who you are?** Wait time stratified by age, gender, race and referral department, with confidence intervals — so stated gaps are defensible rather than eyeballed.

---

## Why the mean wait time is the wrong headline metric

ED wait times are strongly right-skewed: most patients are seen quickly, a long tail waits far longer. The mean sits between the two and describes nobody's experience. This project reports **median** (the typical patient), **P90** (the tail that generates complaints), and **% within target** (the operational commitment) — the same convention real ED dashboards use.

Where a formal CMS measure exists but the data cannot support it, that is stated rather than approximated. The dataset has no departure timestamp, so **CMS OP-18 (median time from ED arrival to departure) is not computable here** and is not faked. See [`docs/measure_spec.md`](docs/measure_spec.md).

---

## Architecture

```
Kaggle CSV                data/raw/hospital_er.csv        (git-ignored: not ours to redistribute)
    |
    |  src/erops/ingest.py     Kaggle API or manual drop -- both land in the same place
    |  src/erops/profile.py    Phase 0: profile before modelling, never assume the schema
    v
dbt staging (views)       stg_er_visits                   typing, snake_case, quality flags
    |
    v
dbt marts (tables)        dim_date  dim_time_of_day  dim_patient_segment  dim_department
                          fct_er_visit                    grain: one row per ER visit
                          agg_hourly_arrivals             demand heatmap + load-vs-wait
                          agg_daily_ops                   daily KPIs + SPC control limits
                          agg_segment_waits               median/P90 + 95% CI per segment
    |
    +-- app/streamlit_app.py         reads DuckDB directly     (analyst-facing, interactive)
    |
    +-- src/erops/export_dashboard.py -> data/exports/*.csv -> dashboard/er_dashboard.pbix
                                                               (exec-facing, presentation only)
```

**All business logic lives in dbt.** Power BI holds formatting and layout, nothing else. That is what makes it structurally impossible for the two dashboards to report different numbers — a failure mode that is otherwise very easy to ship without noticing.

### Star schema

| Model | Grain | Notes |
|---|---|---|
| `fct_er_visit` | one ER visit | wait minutes, admitted flag, satisfaction score + response flag, within-target flag |
| `dim_date` | one calendar day | weekday, month, weekend flag |
| `dim_time_of_day` | one hour 0–23 | shift (day/evening/night), peak vs off-peak |
| `dim_patient_segment` | one demographic combination | age band, gender, race |
| `dim_department` | one referral destination | includes an explicit "None" member, not a null |

Aggregates (`agg_*`) are pre-computed rather than left to the BI layer so that the control limits and percentiles are identical everywhere they appear.

---

## Metrics

| Metric | Definition |
|---|---|
| Visits | Count of ER visits in the period |
| Median wait | 50th percentile of `wait_minutes` |
| P90 wait | 90th percentile of `wait_minutes` |
| % within target | Share of visits with `wait_minutes <= 30` (target set in `dbt_project.yml`) |
| Admission rate | Admitted visits / total visits |
| Satisfaction response rate | Visits with a non-null satisfaction score / total visits |
| Mean satisfaction | Mean score **among responders only**, always reported with the response rate |

Full numerator/denominator/exclusion definitions: [`docs/measure_spec.md`](docs/measure_spec.md).

---

## Analytical methods

- **Statistical process control** — XmR chart for daily median wait, p-chart for admission rate, with 3-sigma limits and Western Electric rule signals. Control limits are computed in `agg_daily_ops`, not in the chart.
- **Percentile service levels** — median and P90 rather than means, with target attainment.
- **Load-versus-wait analysis** — arrivals per hour against observed median wait, to locate the volume threshold where service degrades.
- **Non-response bias analysis** — satisfaction scores are substantially incomplete. Whether missingness correlates with wait time is tested explicitly, because a satisfaction average over a biased responder pool is worse than no average at all.
- **Segment comparison with confidence intervals** — every demographic gap is reported with a CI, so small-n segments are not over-read.

No predictive modelling: this is a descriptive analytics project by design, and the rigour is in the measurement rather than in a model.

---

## Tech stack

Python 3.11 · DuckDB · dbt (dbt-duckdb) · pandas · Streamlit · Plotly · Power BI · pytest · ruff

---

## Running it

```bash
make install     # venv + dependencies
make ingest      # fetch the Kaggle CSV into data/raw/  (or drop it there yourself)
make profile     # Phase 0 data-quality profile -- run this before trusting anything
make build       # dbt run -> data/er.duckdb
make test        # dbt tests + pytest
make export      # data/exports/*.csv for Power BI
make app         # launch the Streamlit dashboard
```

The Kaggle CSV is not committed. `make ingest` fetches it via `kagglehub`, or you can download it manually and unzip into `data/raw/` — the loader accepts either.

---

## Roadmap

- [x] Repo scaffold, warehouse config, ingest + profiling modules
- [x] Phase 0 — profile raw data, write `docs/data_dictionary.md`
- [x] Phase 1 — staging model, star schema, dbt tests green
- [x] Phase 2 — aggregate models (SPC limits, segment CIs)
- [ ] Phase 3 — analysis notebooks (demand, wait distribution, load-vs-wait, SPC, non-response, segments)
- [ ] Phase 4 — Streamlit app
- [ ] Phase 5 — Power BI report + written findings

---

## Data & limitations

Single unnamed facility, no acuity/ESI triage level, no departure timestamps, no staffing or bed-census data, and materially incomplete satisfaction scores. These bound what can honestly be claimed and are documented in [`docs/limitations.md`](docs/limitations.md) rather than left for the reader to discover.

Source data: Maven Analytics Hospital Emergency Room dataset, via Kaggle. Used here for academic analysis only.

## License

MIT — see [LICENSE](LICENSE).
