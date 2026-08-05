# ER Throughput & Patient Flow Analytics

An end-to-end analytics platform for emergency-department operations: how demand arrives, how long patients wait, where the bottlenecks sit, and whether the department is statistically *stable* or drifting.

Built on the Maven Analytics **Hospital Emergency Room** dataset (~9K visits) with a DuckDB + dbt warehouse feeding two dashboards — an interactive Streamlit app for analysts and a Power BI report for executives.

> **Status: analytics complete.** Warehouse, 7 analysis notebooks, and the Streamlit dashboard are built, executed, and validated (34/34 dbt tests, 3/3 pytest, `ruff` clean — see [`docs/validation.md`](docs/validation.md)). The Power BI **assets** (CSV exports, DAX measures, theme) are regenerated and current; assembling the `.pbix` itself in Power BI Desktop is the one remaining manual step — see [`dashboard/README.md`](dashboard/README.md). See the [roadmap](#roadmap).
>
> One-page version for recruiters/hiring managers: [`executive_summary.md`](executive_summary.md). Full findings: [`docs/findings.md`](docs/findings.md).

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

## Key insights

Five findings from the full analysis (`docs/findings.md` has the complete report with methodology and caveats for each):

1. **Stable process, missed target.** Only 3 of 579 days trigger an SPC signal, yet only 40.7% of visits meet the 30-minute target — every month misses it. Stability and target attainment are independent; this department is stable at the wrong level.
2. **No capacity signal in the data.** Hourly arrival volume correlates with wait time at r = -0.01 — essentially zero. A volume-triggered staffing rule is not supported here.
3. **Demand is nearly flat.** Daily arrivals have a coefficient of variation of 0.23 with no strong diurnal or weekly cycle — unusual for a real ED and flagged as a provenance caveat, not taken at face value.
4. **Survey non-response isn't explained by wait time or admission.** Both correlations are negligible (|r| < 0.02) for the 27.3%-response satisfaction score.
5. **No systematic demographic wait-time gap.** Group medians cluster within minutes across gender, age, and race; the one statistically distinguishable extreme-segment gap is one comparison out of 86, not a pattern — and without acuity data, not evidence of differential treatment either way.

## Repository structure

```
er-throughput-analytics/
├── src/erops/            # config, ingest, profile, and the shared metrics.py query module
├── dbt/                  # staging model, star-schema marts, dbt tests
├── notebooks/            # 00_profile ... 06_segment_equity -- 7 executed consulting-style notebooks
├── app/streamlit_app.py  # 7-tab live dashboard (Overview, Demand, Wait Times, Stability, ...)
├── dashboard/            # Power BI theme, DAX measures, build instructions (dashboard/README.md)
├── data/                 # raw/ (git-ignored source CSV), exports/ (Power BI CSVs), er.duckdb
├── docs/                 # measure_spec, limitations, data_dictionary, findings, metric_catalog,
│                         # business_questions, architecture, validation, performance
├── tests/                # pytest -- Python/dbt config parity
└── executive_summary.md  # one-page version of this project for recruiters/hiring managers
```

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
jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb   # re-run all 7 notebooks
```

The Kaggle CSV is not committed. `make ingest` fetches it via `kagglehub`, or you can download it manually and unzip into `data/raw/` — the loader accepts either.

After `make build`, open any notebook in `notebooks/` or run `make app` to explore interactively — both read the same warehouse through `src/erops/metrics.py`, so their numbers cannot disagree.

---

## Roadmap

- [x] Repo scaffold, warehouse config, ingest + profiling modules
- [x] Phase 0 — profile raw data, write `docs/data_dictionary.md`
- [x] Phase 1 — staging model, star schema, dbt tests green
- [x] Phase 2 — aggregate models (SPC limits, segment CIs)
- [x] Phase 3 — 7 analysis notebooks (demand, wait distribution, load-vs-wait, SPC, non-response, segments), each executed and ending in an Executive Summary / Recommendations / Limitations / Next Steps
- [x] Phase 4 — Streamlit app, all 7 tabs live (Overview, Demand, Wait Times, Operational Stability, Patient Satisfaction, Equity, Data Quality)
- [x] Phase 5 — Power BI assets regenerated (CSV exports, DAX measures, theme) and written findings (`docs/findings.md`) complete. `.pbix` assembly itself is a manual Power BI Desktop step (no Power BI automation tool exists in this environment) — see [`dashboard/README.md`](dashboard/README.md).

---

## Documentation

| Doc | What it's for |
|---|---|
| [`docs/measure_spec.md`](docs/measure_spec.md) | Exact numerator/denominator/exclusion for every metric, plus SPC methodology. |
| [`docs/metric_catalog.md`](docs/metric_catalog.md) | Business meaning, formula, source table, and owner for every KPI. |
| [`docs/business_questions.md`](docs/business_questions.md) | The 7 questions this project answers, the metric used, and the business implication. |
| [`docs/findings.md`](docs/findings.md) | Full executive findings report — read this first if you want the "so what," not the code. |
| [`docs/architecture.md`](docs/architecture.md) | Pipeline diagram and layer responsibilities. |
| [`docs/validation.md`](docs/validation.md) | What was checked, the command run, and the real result. |
| [`docs/performance.md`](docs/performance.md) | Warehouse size, query latency, notebook and dashboard timings. |
| [`docs/data_dictionary.md`](docs/data_dictionary.md) | Raw column mapping and every mart's grain and columns. |
| [`docs/limitations.md`](docs/limitations.md) | What this dataset cannot support — read alongside every finding. |
| [`docs/PROJECT_PLAN.md`](docs/PROJECT_PLAN.md) | Build order, decisions, and tradeoffs — the reasoning behind the roadmap above. |

## Data & limitations

Single unnamed facility, no acuity/ESI triage level, no departure timestamps, no staffing or bed-census data, and materially incomplete satisfaction scores. These bound what can honestly be claimed and are documented in [`docs/limitations.md`](docs/limitations.md) rather than left for the reader to discover.

Source data: Maven Analytics Hospital Emergency Room dataset, via Kaggle. Used here for academic analysis only.

## License

MIT — see [LICENSE](LICENSE).
