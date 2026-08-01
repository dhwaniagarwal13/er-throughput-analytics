# ER Throughput Analytics — Executive Summary

A production-quality analytics engagement, end to end: raw CSV → governed dbt warehouse → statistical
analysis → interactive dashboard → executive BI report. Built to demonstrate the full analytics
lifecycle a Senior Analytics Engineer / Data Analyst would own, not just a single chart or model.

## Problem

Emergency departments track wait time as a core service metric but rarely have a governed, single-
source-of-truth pipeline behind it — the same number often gets recomputed three different ways across
an analyst's notebook, a live dashboard, and an executive report, and quietly disagrees. This project
asks seven concrete operational questions (is demand predictable? is the wait-time process stable? does
survey non-response bias satisfaction scores? does wait time differ by patient group, and is that
difference real?) and answers every one of them from **one** set of metric definitions, computed once.

## Dataset

9,216 single-facility ER visits, 2023-04-01 to 2024-10-30 (579 days). Patient demographics, arrival
timestamp, department referral, wait time, admission flag, and an optional (27% response rate)
satisfaction score. No acuity/triage data — the project's central limitation, handled explicitly rather
than glossed over.

## Architecture

`Raw CSV → DuckDB → dbt staging → dbt marts (1 fact, 4 dims, 3 pre-aggregated stats tables) → Python
analysis (shared query module + 7 notebooks) → Streamlit (live, analyst-facing) → Power BI (static
export, executive-facing)`. Full diagram in `docs/architecture.md`. Every KPI, percentile, and SPC
control limit is computed exactly once in dbt SQL and read from there by every downstream consumer.

## Methods

- **Statistical process control:** XmR chart (moving-range sigma estimate, Western Electric run rules)
  on daily median wait; p-chart (volume-varying control limits) on daily admission rate.
- **Distribution diagnostics:** skewness/kurtosis used to test — not assume — whether the median is the
  right central-tendency measure for this specific dataset.
- **Inferential caution:** 95% confidence intervals on every segment-level wait comparison (normal
  approximation to the median's sampling distribution), an explicit multiple-comparisons caveat on the
  86-segment equity ranking, and small-n suppression below a minimum cell size.
- **Non-response bias testing:** point-biserial correlation to test whether satisfaction survey
  non-response is associated with wait time or admission outcome, rather than assuming the missing data
  is random.

## Five Major Findings

1. **Stable process, missed target.** Only 3 of 579 days show a statistical process control signal, yet
   only 40.7% of visits meet the 30-minute wait target — every month of the window misses it. Stability
   and target attainment are independent, and this department is stable at the wrong level.
2. **No capacity signal in the data.** Hourly arrival volume has essentially zero correlation with wait
   time (r = -0.01); a volume-triggered staffing rule is not supported by this dataset.
3. **Demand is nearly flat.** Daily arrivals have a coefficient of variation of just 0.23 with no strong
   diurnal or weekly cycle — atypical for a real ED and flagged as a data-provenance caveat, not taken
   at face value.
4. **Survey non-response isn't explained by wait time or admission.** Both correlations are
   statistically negligible (|r| < 0.02), ruling out the two most obvious bias mechanisms for the 27.3%
   response rate — though not proving the remaining 72.7% would report the same average.
5. **No systematic demographic wait-time gap.** Group medians cluster within minutes across gender, age,
   and race; the one statistically distinguishable extreme-segment gap is one comparison out of 86 and
   is explicitly not treated as an equity conclusion, especially absent acuity data.

## Business Recommendations

Investigate intake/triage throughput directly (the gap is structural, not volume- or demographic-
driven); do not build a volume-based staffing trigger from this data; treat the historical SPC signal
window as closed, not ongoing; invest in satisfaction survey response rate before treating the score as
representative; prioritize acquiring acuity/triage data, the single addition that would most improve
every finding in this report. Full detail in `docs/findings.md`.

## Technology Stack

**Warehouse/transform:** DuckDB, dbt-duckdb · **Analysis:** Python, pandas, Plotly, Jupyter ·
**Dashboard:** Streamlit · **BI:** Power BI (DAX measures, custom theme, static CSV export) ·
**Quality:** dbt tests (34), pytest, ruff · **Docs-as-code:** every metric, limitation, and architecture
decision written down before or alongside the code that implements it.

---

*Full documentation: `README.md` (setup and reproduction), `docs/findings.md` (full report),
`docs/measure_spec.md` (every metric's exact formula), `docs/limitations.md` (what this data cannot
support), `docs/metric_catalog.md`, `docs/architecture.md`, `docs/validation.md`, `docs/performance.md`.*
