# Data dictionary

**Status: to be completed in Phase 0.** Run `make ingest && make profile` and record the real output here.

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

## Template

### Raw: `data/raw/hospital_er.csv`

| Source column | Mapped to | Type | Null % | Distinct | Notes |
|---|---|---|---|---|---|
| _(fill from `make profile`)_ | | | | | |

**Observation window:** _(fill in)_
**Row count:** _(fill in)_

### Mart: `fct_er_visit`

**Grain:** one row per ER visit.

| Column | Type | Definition |
|---|---|---|
| _(fill in as models are built)_ | | |
