-- Grain: one row per day. Two independent control charts, per docs/measure_spec.md:
--   XmR on daily median wait      (wait_centre_line / wait_ucl / wait_lcl / spc_signal)
--   p-chart on daily admission rate (admit_centre_line / admit_ucl / admit_lcl / admit_signal)
-- Baseline = the full observation window (no separate baseline period is configured
-- anywhere in this project yet -- see docs/limitations.md on baseline sensitivity).
with daily as (

    select
        visit_date,
        count(*) as visits,
        count(*) filter (where admitted_flag) as admissions,
        median(wait_minutes) filter (where not wait_implausible_flag) as median_wait_minutes,
        quantile_cont(wait_minutes, 0.9) filter (where not wait_implausible_flag) as p90_wait_minutes
    from {{ ref('fct_er_visit') }}
    group by 1

),

-- ---- XmR chart (median wait) ----
mr as (

    select
        *,
        abs(median_wait_minutes - lag(median_wait_minutes) over (order by visit_date)) as moving_range
    from daily

),

xmr_limits as (

    select
        *,
        avg(median_wait_minutes) over () as wait_centre_line,
        avg(moving_range) over () / 1.128 as wait_sigma  -- 1.128 = d2 constant for n=2 moving range
    from mr

),

xmr_flags as (

    select
        *,
        wait_centre_line + {{ var('spc_sigma') }} * wait_sigma as wait_ucl,
        greatest(wait_centre_line - {{ var('spc_sigma') }} * wait_sigma, 0) as wait_lcl,
        case
            when median_wait_minutes > wait_centre_line + wait_sigma then 1
            when median_wait_minutes < wait_centre_line - wait_sigma then -1
            else 0
        end as beyond_1sigma_side,
        case
            when median_wait_minutes > wait_centre_line + 2 * wait_sigma then 1
            when median_wait_minutes < wait_centre_line - 2 * wait_sigma then -1
            else 0
        end as beyond_2sigma_side,
        case
            when median_wait_minutes > wait_centre_line then 1
            when median_wait_minutes < wait_centre_line then -1
            else 0
        end as centre_side
    from xmr_limits

),

-- Gaps-and-islands: group consecutive days on the same side of the centre line so a
-- "run of 8" can be counted per run rather than over the whole history.
xmr_runs as (

    select
        *,
        row_number() over (order by visit_date)
            - row_number() over (partition by centre_side order by visit_date) as run_group
    from xmr_flags

),

xmr_signals as (

    select
        *,
        row_number() over (partition by centre_side, run_group order by visit_date) as run_length_so_far,
        sum(case when beyond_2sigma_side = 1 then 1 else 0 end)
            over (order by visit_date rows between 2 preceding and current row) as pos_2sigma_last3,
        sum(case when beyond_2sigma_side = -1 then 1 else 0 end)
            over (order by visit_date rows between 2 preceding and current row) as neg_2sigma_last3
    from xmr_runs

),

xmr_final as (

    select
        visit_date,
        visits,
        admissions,
        median_wait_minutes,
        p90_wait_minutes,
        wait_centre_line,
        wait_ucl,
        wait_lcl,
        case
            when median_wait_minutes > wait_ucl or median_wait_minutes < wait_lcl then 'point_beyond_limit'
            when centre_side <> 0 and run_length_so_far >= 8 then 'run_of_8'
            when pos_2sigma_last3 >= 2 or neg_2sigma_last3 >= 2 then 'two_of_three_beyond_2sigma'
        end as spc_signal
    from xmr_signals

),

-- ---- p-chart (admission rate) ----
-- Pooled centre line (constant); limits vary by day because daily volume varies.
pchart_pooled as (

    select
        sum(admissions)::double / sum(visits) as admit_centre_line
    from daily

),

pchart as (

    select
        daily.visit_date,
        daily.admissions::double / daily.visits as admission_rate,
        pooled.admit_centre_line,
        sqrt(pooled.admit_centre_line * (1 - pooled.admit_centre_line) / daily.visits) as admit_sigma
    from daily
    cross join pchart_pooled as pooled

),

pchart_final as (

    select
        visit_date,
        admission_rate,
        admit_centre_line,
        least(admit_centre_line + {{ var('spc_sigma') }} * admit_sigma, 1) as admit_ucl,
        greatest(admit_centre_line - {{ var('spc_sigma') }} * admit_sigma, 0) as admit_lcl,
        -- Limits touching 0 or 1 are drawn but uninformative on low-volume days
        -- (docs/limitations.md) -- flagged here rather than silently clipped.
        (admit_centre_line + {{ var('spc_sigma') }} * admit_sigma > 1)
            or (admit_centre_line - {{ var('spc_sigma') }} * admit_sigma < 0) as admit_limits_clipped
    from pchart

)

select
    xmr_final.visit_date,
    xmr_final.visits,
    xmr_final.admissions,
    xmr_final.median_wait_minutes,
    xmr_final.p90_wait_minutes,
    xmr_final.wait_centre_line,
    xmr_final.wait_ucl,
    xmr_final.wait_lcl,
    xmr_final.spc_signal,
    pchart_final.admission_rate,
    pchart_final.admit_centre_line,
    pchart_final.admit_ucl,
    pchart_final.admit_lcl,
    pchart_final.admit_limits_clipped,
    case
        when pchart_final.admission_rate > pchart_final.admit_ucl
            or pchart_final.admission_rate < pchart_final.admit_lcl then 'point_beyond_limit'
    end as admit_signal
from xmr_final
inner join pchart_final on xmr_final.visit_date = pchart_final.visit_date
