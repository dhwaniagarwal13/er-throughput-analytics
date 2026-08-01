-- Grain: one row per ER visit. See docs/measure_spec.md for the exact definition of
-- every flag below -- this model computes them, it does not just carry them.
select
    visit_id,
    visit_ts,
    visit_date,
    visit_hour,
    segment_key,
    department_referral,
    wait_minutes,
    wait_implausible_flag,
    -- False (never null) for implausible or missing waits, so BI tools can filter on
    -- this column directly without also having to reason about blanks.
    wait_minutes is not null
        and not wait_implausible_flag
        and wait_minutes <= {{ var('wait_target_minutes') }} as within_target_flag,
    admitted_flag,
    satisfaction_score,
    case_management_flag
from {{ ref('stg_er_visits') }}
