# Data dictionary

**Status: complete.** Filled in from `make ingest && make profile` output, then re-verified against the built marts after `make build`.

This file is deliberately empty of column definitions right now. The Hospital ER dataset has been reuploaded under several Kaggle slugs with differing column names, casing and date ranges, so writing this from memory would put an unverified schema at the root of the whole warehouse. `src/erops/profile.py` reports whatever is actually in the file; that output is the source of truth for everything downstream.

## What to record here

For the raw CSV:

- Exact column names as shipped, and the snake_case name each maps to in `stg_er_visits`
- Data type, null count and null percentage per column
- Distinct-value lists for every categorical (gender, race, department referral, admitted flag)
- Observation window: min and max admission datetime
- Row count, and duplicate-row / duplicate-ID counts
- Wait-time distribution: min, median, P90, P99, max, and the count beyond `max_plausible_wait_minutes`

For each mart model, once built:

- Grain, in one sentence
- Column list with definition and source
- Any row-count difference from the source, with the reason

## Findings

### Raw: `data/raw/hospital_er.csv`

Source: `laxdippatel/hospital-emergency-room-dataset` on Kaggle (the originally-configured
slug, `yashsahu02/hospital-emergency-room-data`, now 404s — Kaggle dataset slugs really do
get renamed, as this file warned). Same Maven Analytics dataset, matching schema and row count.

| Source column | Mapped to (`stg_er_visits`) | Type | Null % | Distinct | Notes |
|---|---|---|---|---|---|
| Patient Id | `visit_id` | str | 0% | 9,216 | Unique per row — used directly as the visit grain key, no surrogate needed. |
| Patient Admission Date | `visit_ts` / `visit_date` / `visit_hour` | str -> timestamp | 0% | 9,176 | Format is `DD-MM-YYYY HH:MM` (day-first — e.g. `20-03-2024` is 20 March). |
| Patient First Inital | `first_initial` | str | 0% | 26 | Kept in staging only; not exposed in the marts. |
| Patient Last Name | `last_name` | str | 0% | 8,400 | Kept in staging only; not exposed in the marts. |
| Patient Gender | `gender` | str | 0% | 3 | `M` (4,705), `F` (4,487), `NC` (24). |
| Patient Age | `age` / `age_band` | int | 0% | 79 | Range 1–79. Banded into `0-17` / `18-34` / `35-49` / `50-64` / `65+`. |
| Patient Race | `race` | str | 0% | 7 | White, African American, Two or More Races, Asian, Declined to Identify, Pacific Islander, Native American/Alaska Native. |
| Department Referral | `department_referral` | str | 58.6%* | 7 | *Not a real null — the source ships the literal text `None` for "no referral" (1,840 General Practice, 995 Orthopedics, 276 Physiotherapy, 248 Cardiology, 193 Neurology, 178 Gastroenterology, 86 Renal, 5,400 `None`). Read as VARCHAR in staging so DuckDB's type inference can't turn that text into a real NULL — `dim_department` carries `None` as an explicit member. |
| Patient Admission Flag | `admitted_flag` | bool | 0% | 2 | TRUE 4,612 / FALSE 4,604 — roughly balanced. |
| Patient Satisfaction Score | `satisfaction_score` | float | 72.7% | 11 | Genuinely blank in the source (not a text sentinel). 0–10 integer scale among responders. Never report without the response rate alongside it (measure_spec.md). |
| Patient Waittime | `wait_minutes` | int | 0% | 51 | Range 10–60 minutes, mean 35.3. Never exceeds `max_plausible_wait_minutes` (240), so `wait_implausible_flag` is `false` for every row in this snapshot of the data. |
| Patients CM | `case_management_flag` | bool | 0% | 2 | 0 (8,736) / 1 (480). Not used in any current metric — carried through for future use. |

**Observation window:** 2023-04-01 to 2024-10-30 (579 calendar days; `dim_date` is generated as a continuous calendar over this span so Power BI time-intelligence measures like `DATEADD(..., -1, MONTH)` don't break on zero-arrival days).
**Row count:** 9,216. Zero fully-duplicated rows, zero duplicate `visit_id` values.

### Mart: `fct_er_visit`

**Grain:** one row per ER visit (9,216 rows — matches source exactly; no row-count difference).

| Column | Type | Definition |
|---|---|---|
| `visit_id` | str | Natural key from source `Patient Id`. |
| `visit_ts` / `visit_date` / `visit_hour` | timestamp / date / int | Parsed admission timestamp and its date/hour parts. |
| `segment_key` | str (md5) | FK to `dim_patient_segment` (age_band x gender x race). |
| `department_referral` | str | FK to `dim_department`, including the explicit `None` member. |
| `wait_minutes` | int | Minutes from arrival to provider. |
| `wait_implausible_flag` | bool | `wait_minutes > max_plausible_wait_minutes` (240). Always `false` in this snapshot — flagged, not filtered, so visit counts always reconcile to source. |
| `within_target_flag` | bool | `wait_minutes <= wait_target_minutes` (30) and not implausible; 3,749 of 9,216 visits (40.7%). |
| `admitted_flag` | bool | Source `Patient Admission Flag`. |
| `satisfaction_score` | float, nullable | Responders only; 72.7% null. |
| `case_management_flag` | bool | Source `Patients CM`. |

### Other marts

`dim_date` (579 rows, continuous calendar), `dim_time_of_day` (24 rows, 0–23 with shift and a data-driven `is_peak` flag), `dim_patient_segment` (86 distinct age/gender/race combinations actually present in the data), `dim_department` (8 rows, 7 named departments + `None`), `agg_hourly_arrivals` (6,757 rows, one per date x hour with arrivals), `agg_daily_ops` (579 rows, one per day with XmR and p-chart control limits — 3 `run_of_8` signal days on the wait chart, 1 `point_beyond_limit` day on the admission-rate chart), `agg_segment_waits` (86 rows, median/P90 wait with a 95% CI per segment; segments under 30 plausible visits get `low_n_flag = true` and, where n is 1, a null CI rather than a fabricated one).
