# Measure specification

Every KPI in this project is defined here before it is computed anywhere. A dashboard number without a written numerator, denominator and exclusion list is not a measure — it is a guess with formatting.

Parameters (`wait_target_minutes`, `max_plausible_wait_minutes`, `spc_sigma`) live in `dbt/dbt_project.yml` and are mirrored in `src/erops/config.py`; `tests/test_config_matches_dbt.py` fails if the two drift.

---

## Core operational measures

### Visits
- **Numerator:** count of rows in `fct_er_visit`
- **Denominator:** n/a
- **Exclusions:** none — every ingested visit is counted, including those with a quality flag, so volume always reconciles to source.

### Median wait
- **Definition:** 50th percentile of `wait_minutes`
- **Population:** visits with a non-null `wait_minutes`
- **Exclusions:** visits flagged `wait_implausible` (> `max_plausible_wait_minutes`) are excluded from wait statistics but retained in the fact table and counted in Visits.
- **Why median:** the distribution is right-skewed; the mean is pulled by the tail and describes no actual patient.

### P90 wait
- **Definition:** 90th percentile of `wait_minutes`, same population and exclusions as median wait.
- **Why:** the tail is what generates complaints and escalations. A stable median with a rising P90 is a real deterioration that a mean would hide.

### % within target
- **Numerator:** visits with `wait_minutes <= wait_target_minutes` (default 30)
- **Denominator:** visits with a non-null, plausible `wait_minutes`
- **Note:** the 30-minute target is a project convention for analysis, not a regulatory threshold. It is parameterised so the warehouse can be rebuilt against a different target.

### Admission rate
- **Numerator:** visits where the admitted flag is true
- **Denominator:** all visits
- **Note:** an ED-level case-mix proxy in the absence of acuity data — a rising admission rate suggests a sicker arriving population. It is a *proxy*, and is described as one wherever it appears.

### Satisfaction response rate
- **Numerator:** visits with a non-null satisfaction score
- **Denominator:** all visits
- **Why it is a headline measure and not a footnote:** the score is substantially incomplete. Reporting mean satisfaction without the response rate beside it implies a representativeness the data does not have.

### Mean satisfaction
- **Numerator:** sum of satisfaction scores
- **Denominator:** count of visits with a non-null score (responders only)
- **Mandatory pairing:** never displayed without the response rate, and never without the non-response bias finding from `notebooks/05_satisfaction_and_nonresponse.ipynb`.

---

## Statistical process control

### XmR chart — daily median wait
- **Centre line:** mean of daily median wait across the baseline period
- **Control limits:** centre ± `spc_sigma` × (mean moving range / 1.128)
- **1.128** is the d2 constant for a moving range of n=2; it converts average moving range into a standard-deviation estimate.
- **Signals:** point outside limits; 8 consecutive points one side of centre; 2 of 3 beyond 2 sigma.

### p-chart — daily admission rate
- **Centre line:** total admissions / total visits over the baseline
- **Control limits:** centre ± `spc_sigma` × sqrt(p(1−p)/n_day) — limits vary by day because daily volume varies.
- **Note:** on low-volume days the limits widen and may clip at 0 or 1; clipped limits are drawn but flagged as uninformative.

---

## Measures deliberately NOT computed

Stating these matters as much as the ones above.

| Measure | Why not |
|---|---|
| **CMS OP-18** — median time from ED arrival to departure | No departure timestamp in the dataset. Wait time is arrival-to-provider, a different and shorter interval. Presenting it as OP-18 would be wrong. |
| **CMS OP-22** — left without being seen | No disposition category for LWBS. |
| **Boarding time** | No inpatient bed-assignment timestamp. |
| **Acuity-adjusted wait** | No ESI or triage level, so waits cannot be case-mix adjusted. All comparisons here are unadjusted, and that is a real limitation, not a rounding detail. |
| **Length of stay** | Requires departure time. Not available. |

See [`limitations.md`](limitations.md).
