-- Grain: one row per patient segment (age_band x gender x race). Median/P90 wait with a
-- 95% CI on the median, so small-n segments are not read as confidently as large ones.
--
-- CI method: normal approximation to the sampling distribution of the median,
-- SE(median) ~= 1.2533 * SE(mean) = 1.2533 * (stddev / sqrt(n)). This is a standard
-- large-sample approximation, not a bootstrap -- treat it as indicative, not exact,
-- for the smallest segments (see low_n_flag below).
--
-- 30 is this project's minimum-cell-size convention (docs/limitations.md: "segments
-- below a minimum cell size are suppressed rather than plotted as if meaningful").
with segment_waits as (

    select
        fct.segment_key,
        dim.age_band,
        dim.gender,
        dim.race,
        count(*) as n_visits,
        count(*) filter (where not fct.wait_implausible_flag) as n_plausible,
        median(fct.wait_minutes) filter (where not fct.wait_implausible_flag) as median_wait_minutes,
        quantile_cont(fct.wait_minutes, 0.9) filter (where not fct.wait_implausible_flag) as p90_wait_minutes,
        avg(fct.wait_minutes) filter (where not fct.wait_implausible_flag) as mean_wait_minutes,
        stddev_samp(fct.wait_minutes) filter (where not fct.wait_implausible_flag) as stddev_wait_minutes
    from {{ ref('fct_er_visit') }} as fct
    inner join {{ ref('dim_patient_segment') }} as dim on fct.segment_key = dim.segment_key
    group by 1, 2, 3, 4

)

select
    segment_key,
    age_band,
    gender,
    race,
    n_visits,
    n_plausible,
    median_wait_minutes,
    p90_wait_minutes,
    mean_wait_minutes,
    median_wait_minutes - 1.96 * (1.2533 * stddev_wait_minutes / sqrt(n_plausible)) as ci_lower,
    median_wait_minutes + 1.96 * (1.2533 * stddev_wait_minutes / sqrt(n_plausible)) as ci_upper,
    n_plausible < 30 as low_n_flag
from segment_waits
