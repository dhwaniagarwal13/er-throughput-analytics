# Metric catalog

One entry per KPI surfaced in the notebooks, the Streamlit app, or the Power BI report. This is the
canonical reference — `docs/measure_spec.md` has the full numerator/denominator/exclusion detail and
the SPC methodology; this catalog adds business meaning, source, refresh, and ownership so the two
documents serve different readers (measure_spec.md for whoever builds it, this catalog for whoever
consumes it).

Every metric here is computed in exactly one place (`src/erops/metrics.py` for Python, `agg_daily_ops`
/ `agg_segment_waits` in dbt for the pre-aggregated statistics) and read from there by every consumer —
notebooks, Streamlit, and the Power BI export. No metric is redefined per-report.

---

### Visits
- **Definition:** Count of ER visits in the observation window.
- **Business meaning:** Volume — the denominator for every rate metric below, and the baseline for
  staffing and capacity planning.
- **Formula:** `count(*)` over `fct_er_visit`.
- **Source table:** `main_marts.fct_er_visit`.
- **Refresh assumption:** Recomputed on every `dbt run` (`make build`); this project has no
  incremental/streaming refresh, only full-batch rebuilds from the source CSV.
- **Owner:** Analytics engineering (this repo) for the pipeline; ED Operations for the business
  interpretation.

### Median wait
- **Definition:** 50th percentile of `wait_minutes` among plausible visits.
- **Business meaning:** The typical patient's arrival-to-provider wait — the headline throughput number,
  chosen over the mean because it isn't pulled by outliers.
- **Formula:** `median(wait_minutes) filter (where not wait_implausible_flag)`.
- **Source table:** `main_marts.fct_er_visit` (point-in-time); `main_marts.agg_daily_ops.median_wait_minutes` (daily).
- **Refresh assumption:** Same as Visits.
- **Owner:** ED Operations (accountable for the number); Analytics engineering (computes it).

### P90 wait
- **Definition:** 90th percentile of `wait_minutes` among plausible visits.
- **Business meaning:** The "worst typical" experience — a stable median with a rising P90 signals a
  real deterioration in the tail that the median alone would hide.
- **Formula:** `quantile_cont(wait_minutes, 0.9) filter (where not wait_implausible_flag)`.
- **Source table:** `main_marts.fct_er_visit`; `main_marts.agg_daily_ops.p90_wait_minutes` (daily).
- **Refresh assumption:** Same as Visits.
- **Owner:** ED Operations / Analytics engineering.

### % within target
- **Definition:** Share of plausible visits with `wait_minutes <= wait_target_minutes` (30, configurable).
- **Business meaning:** Direct service-level attainment against the department's internal wait target.
- **Formula:** `count(*) filter (where within_target_flag) / count(*) filter (where wait_minutes is not null and not wait_implausible_flag)`.
- **Source table:** `main_marts.fct_er_visit.within_target_flag` (precomputed in the mart from
  `dbt/dbt_project.yml`'s `wait_target_minutes` var).
- **Refresh assumption:** Changes if `ER_WAIT_TARGET_MINUTES` / `wait_target_minutes` is changed and the
  warehouse rebuilt — see `tests/test_config_matches_dbt.py`, which fails the build if the Python and
  dbt values drift.
- **Owner:** ED Operations (target owner); Analytics engineering (pipeline).

### Admission rate
- **Definition:** Share of all visits where `admitted_flag` is true.
- **Business meaning:** A case-mix proxy in the absence of acuity data — a rising rate suggests a sicker
  arriving population, not necessarily worse throughput.
- **Formula:** `count(*) filter (where admitted_flag) / count(*)`.
- **Source table:** `main_marts.fct_er_visit`; `main_marts.agg_daily_ops.admission_rate` (daily, with
  p-chart control limits).
- **Refresh assumption:** Same as Visits.
- **Owner:** ED Operations / Analytics engineering.

### Satisfaction response rate
- **Definition:** Share of visits with a non-null `satisfaction_score`.
- **Business meaning:** Reported alongside every satisfaction figure by project rule — at 27.3%, mean
  satisfaction describes the responding minority, not the department overall.
- **Formula:** `count(*) filter (where satisfaction_score is not null) / count(*)`.
- **Source table:** `main_marts.fct_er_visit`.
- **Refresh assumption:** Same as Visits.
- **Owner:** Patient Experience (business owner); Analytics engineering (pipeline).

### Mean satisfaction
- **Definition:** Average `satisfaction_score` among responders only, 0-10 scale.
- **Business meaning:** Patient-reported experience. Never shown without the response rate — see
  `notebooks/05_satisfaction.ipynb` for the non-response bias check that justifies this rule.
- **Formula:** `avg(satisfaction_score)` (responders only, i.e. `satisfaction_score is not null`).
- **Source table:** `main_marts.fct_er_visit`.
- **Refresh assumption:** Same as Visits.
- **Owner:** Patient Experience / Analytics engineering.

### Wait-time control limits (XmR: centre line, UCL, LCL)
- **Definition:** Statistical process control bounds on daily median wait, computed once over the full
  observation window (the baseline).
- **Business meaning:** Distinguishes routine day-to-day noise from a genuine shift in the wait-time
  process worth investigating.
- **Formula:** Centre = `avg(daily median wait)`; limits = centre ± `spc_sigma` x (mean moving range /
  1.128). Full detail in `docs/measure_spec.md`.
- **Source table:** `main_marts.agg_daily_ops` (`wait_centre_line`, `wait_ucl`, `wait_lcl`, `spc_signal`).
- **Refresh assumption:** Recomputed on every `dbt run` over the *entire* history to date — there is no
  fixed/frozen baseline period configured (see `docs/limitations.md`, "SPC baseline sensitivity").
- **Owner:** Analytics engineering (methodology); ED Operations (interpretation/action).

### Admission-rate control limits (p-chart: centre line, UCL, LCL)
- **Definition:** Statistical process control bounds on daily admission rate; limits vary by day because
  they depend on that day's visit volume.
- **Business meaning:** Same purpose as the wait-time chart, applied to the case-mix proxy.
- **Formula:** Centre = pooled admission rate over the baseline; limits = centre ± `spc_sigma` x
  sqrt(p(1-p)/n_day), clipped at [0, 1] and flagged when clipped.
- **Source table:** `main_marts.agg_daily_ops` (`admit_centre_line`, `admit_ucl`, `admit_lcl`,
  `admit_signal`, `admit_limits_clipped`).
- **Refresh assumption:** Same as the wait-time control limits.
- **Owner:** Analytics engineering / ED Operations.

### Daily-arrivals coefficient of variation (CV)
- **Definition:** `stddev(daily visit count) / avg(daily visit count)`.
- **Business meaning:** Scale-free measure of how "lumpy" demand is; low CV supports flat staffing, high
  CV would support demand-responsive staffing.
- **Formula:** See `erops.metrics.demand_volume_stats`.
- **Source table:** `main_marts.fct_er_visit` (aggregated on the fly, not pre-materialized in dbt).
- **Refresh assumption:** Recomputed on every call — cheap (single group-by over 579 days).
- **Owner:** Analytics engineering.

### Load-vs-wait correlation
- **Definition:** Pearson correlation between hourly arrival count and that hour's median wait.
- **Business meaning:** Tests whether a capacity ceiling is visible in the observed range of hourly
  volume; near zero here (r = -0.01).
- **Formula:** `corr(arrivals, median_wait_minutes)` over `agg_hourly_arrivals`.
- **Source table:** `main_marts.agg_hourly_arrivals`.
- **Refresh assumption:** Same as Visits.
- **Owner:** Analytics engineering / ED Operations (capacity planning).

### Segment median wait (with 95% CI)
- **Definition:** Median wait per (age band x gender x race) segment, with a 95% confidence interval on
  the median and a `low_n_flag` for segments under 30 plausible visits.
- **Business meaning:** Supports the equity analysis without over-reading noise from small cells.
- **Formula:** CI via normal approximation to the median's sampling distribution:
  `median ± 1.96 x 1.2533 x (stddev / sqrt(n))`. Full detail in `docs/measure_spec.md`.
- **Source table:** `main_marts.agg_segment_waits`.
- **Refresh assumption:** Same as Visits.
- **Owner:** Analytics engineering (methodology); Equity/Patient Experience (interpretation).

---

**Ownership note:** this is a solo portfolio project — "Owner" columns above describe the *role* that
would own each metric in a real deployment (ED Operations, Patient Experience, Analytics Engineering),
not a named individual, so the catalog reads correctly if this pipeline were handed to an actual team.
