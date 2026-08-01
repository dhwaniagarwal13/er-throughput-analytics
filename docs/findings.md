# ER Throughput Analytics — Findings Report

**Prepared for:** ED operations and hospital leadership
**Observation window:** 2023-04-01 to 2024-10-30 (579 calendar days, 9,216 visits)
**Data source:** Single-facility ER visit extract (Maven Analytics "Hospital Emergency Room Data",
mirrored on Kaggle) — see Limitations for a note on provenance.

---

## Executive Summary

This department is **operationally stable but consistently under its own wait-time target.** Only
40.7% of visits are seen within the 30-minute internal target, and this shortfall is present in every
single month of the 19-month observation window — it is not a recent trend or a handful of bad days.
At the same time, statistical process control finds the underlying process highly stable: only 3 of 579
days (0.5%) signal an unusual wait-time day, and 1 of 579 (0.2%) an unusual admission-rate day. **Being
stable and being on-target are different questions, and this department is stable at the wrong level.**

Two candidate explanations were tested and ruled out by this analysis: demand volume (arrivals show no
meaningful daily or hourly pattern, CV = 0.23, and hourly load has essentially zero correlation with
wait time, r = -0.01) and demographic disparity (group-level wait times cluster within a few minutes
across gender, age, and race, with one statistically distinguishable but isolated extreme-segment gap).
Neither points to an obvious operational lever. The most defensible next step is a process-level
investigation of intake and triage throughput, not a staffing-volume or demographic-targeting
intervention.

Patient-reported satisfaction is incomplete (27.3% response rate) but the missingness does not appear
driven by wait time or admission outcome — the two most obvious sources of bias are ruled out, though
not every possible source can be tested with this data.

---

## Business Context

Emergency department throughput — how long a patient waits to be seen — is a widely used proxy for
service quality and operational health. This project builds a governed, single-source-of-truth
analytics stack (dbt warehouse → notebooks → Streamlit → Power BI) over one ED's visit-level data to
answer seven concrete operational and equity questions (`docs/business_questions.md`) rather than
producing an undifferentiated dashboard of charts. Every number in this report, the notebooks, and both
dashboards is computed from the same nine dbt models — there is exactly one formula per metric in this
project (`docs/measure_spec.md`), so a finding here cannot silently disagree with what an analyst sees
in Streamlit or an executive sees in Power BI.

## Methodology

- **Warehouse:** raw CSV → DuckDB → dbt staging (`stg_er_visits`) → dbt marts (one fact table, four
  dimensions, three pre-aggregated marts). See `docs/architecture.md`.
- **Metric definitions:** every KPI (median wait, P90, % within target, admission rate, satisfaction
  response rate) has a written numerator, denominator, and exclusion list in `docs/measure_spec.md`
  before it is computed anywhere.
- **Statistical methods:** median/percentiles (not mean) for wait time, given the project's use of the
  median as the resistant-to-outliers standard; skewness and kurtosis to check that assumption against
  this specific dataset; Pearson correlation and quintile analysis for the load-vs-wait relationship;
  XmR and p-chart statistical process control (Western Electric rules: point beyond limits, run of 8, 2
  of 3 beyond 2-sigma) for stability; normal-approximation confidence intervals on segment medians, with
  a multiple-comparisons caveat, for the equity analysis.
- **Reproducibility:** every finding below is backed by an executable notebook
  (`notebooks/00_profile.ipynb` through `06_segment_equity.ipynb`) that queries the live warehouse
  through `src/erops/metrics.py` and is re-executable from a clean environment (`docs/validation.md`).

## Data Quality

The warehouse is clean: 9,216 visits, **zero** duplicate visit IDs, **zero** implausible or negative
wait values, and a gap-free 579-day calendar. Every operational column is 100% complete. The one
material gap is `satisfaction_score` (72.7% null) — expected, structural non-response, analyzed
directly rather than silently averaged over (see Patient Satisfaction below). Full detail in
`notebooks/00_profile.ipynb` and `docs/validation.md`.

---

## Key Findings

### Demand

Arrival volume is close to flat: a coefficient of variation of 0.23 on daily arrivals, a 2.8% weekend
uptick (16.2 vs. 15.8 visits/day), and no pronounced hour-of-day peak or trough (hourly totals stay in a
narrow band with no diurnal cycle). The day x hour heatmap shows no hot spot.

*Real EDs almost always show a stronger diurnal/weekly cycle than this. Treat this as a data
characteristic to corroborate, not a confirmed operational fact — see Limitations.*

### Operational Performance

Only **40.7%** of visits are seen within the 30-minute target; the median wait is 35 minutes and the
P90 is 56 minutes. The wait-time distribution itself is close to symmetric (skew ≈ -0.02) with no long
right tail (max observed wait 60 minutes) — this is a whole-distribution shift below target, not a
small number of outlier waits dragging an average up. Hourly arrival volume shows essentially no
relationship with wait time (r = -0.01; flat across all five volume quintiles), so the shortfall is not
explained by concurrent patient load in this dataset.

### Statistical Process Control (SPC)

The wait-time process is stable: only 3 of 579 days (0.5%) signal on the XmR chart, all `run_of_8`
within a narrow mid-2023 window, with no recurrence since. The admission-rate p-chart shows a single
isolated signal day (2024-08-01). **Stability and target attainment are independent questions** — this
process is stable *at* a level below target, which argues for a structural process change rather than a
reaction to day-to-day variation.

### Patient Satisfaction

27.3% of visits carry a satisfaction score (mean 4.99/10 among responders). Response propensity shows
no meaningful association with wait time (r = 0.004) or admission status (r = -0.012); mean wait is
nearly identical between responders (35.4 min) and non-responders (35.2 min). This rules out the two
most obvious bias mechanisms but cannot test bias against the patient's actual (unmeasured)
satisfaction — the response rate must continue to be reported alongside the score.

### Equity

Median wait clusters within a few minutes of the overall median across gender, age band, and race. The
single largest gap — between the highest- and lowest-median demographic segment out of 86 — has
non-overlapping 95% confidence intervals, but represents one extreme comparison, not a systematic
pattern; 18.6% of all segments are too small (under 30 visits) to rank reliably at all. **This dataset
has no acuity or triage data — the single most important caveat in this project** — so even a real gap
found here would describe what happened, not prove differential treatment.

---

## Business Recommendations

1. **Treat the wait-time gap as a throughput problem, not a capacity or demographic problem.** Neither
   arrival volume nor patient demographics explain the 59.3% target-miss rate in this data; investigate
   intake/triage process time directly.
2. **Do not build a volume-triggered staffing rule from this analysis.** The correlation between hourly
   arrivals and wait time is statistically indistinguishable from zero in the observed range.
3. **Do not treat the mid-2023 SPC signal window as an ongoing issue.** It is a bounded historical event
   worth a qualitative retrospective, not a live escalation — there has been no recurrence since.
4. **Invest in raising the satisfaction survey response rate** before trusting the headline score as
   representative — 27.3% is workable for ruling out two candidate biases but not for certifying the
   figure overall.
5. **Do not act on the single extreme demographic wait-time gap as an equity finding** without acuity
   data and without correcting for the fact that it is the most extreme of 86 possible comparisons.
6. **Prioritize acquiring acuity/triage data** in any future data collection — it is the single
   improvement that would most increase the trustworthiness of every finding in this report, especially
   the equity analysis.

## Limitations

- **Single facility, unnamed, no external benchmark** — every finding is internal-relative.
- **No acuity or triage level** — the project's most important caveat; wait times cannot be case-mix
  adjusted anywhere in this report.
- **No departure timestamps, staffing data, or patient history** — length of stay, boarding time, and
  true capacity-driven mechanisms cannot be examined.
- **Incomplete satisfaction scores (72.7% null)** — analyzed directly for the two testable bias
  mechanisms, but not provably free of bias from unobserved factors.
- **Small-n demographic cells** — 18.6% of segments are suppressed from ranking; confidence intervals
  are reported wherever a segment comparison is made.
- **Unverified, possibly-synthetic provenance** — this dataset's near-total absence of a demand cycle
  and its narrow, hard-capped wait-time distribution (max 60 minutes) are atypical for a real ED and
  should be corroborated before any finding here drives a real operational decision.
- **Descriptive, not causal** — every relationship in this report is an association; the SPC baseline
  itself is the full observation window (no separate baseline period configured), which would absorb a
  real trend if the window itself contained one.

Full detail in `docs/limitations.md`.

## Future Improvements

- Acquire acuity/triage data to enable case-mix-adjusted wait and equity analysis.
- Acquire staffing/capacity data to test true capacity-driven mechanisms behind the load-vs-wait
  relationship (`notebooks/03_load_vs_wait.ipynb`).
- Acquire departure timestamps to compute length-of-stay and boarding-time measures (currently
  explicitly out of scope — see `docs/measure_spec.md`, "Measures deliberately NOT computed").
- Extend the observation window to enable seasonal decomposition once more than 19 months of data
  exist.
- Run a targeted non-response follow-up survey to directly test whether satisfaction non-response
  correlates with true (unmeasured) satisfaction, closing the one bias channel this analysis cannot
  currently test.
- Automate `.pbix` refresh once a Power BI automation surface is available in this environment (today
  it is a manual Power BI Desktop step — see `dashboard/README.md`).
