-- Shift bands use the standard 8-hour ED convention (day / evening / night), not a
-- data-driven cut -- shift handover times are an operational fact, not a statistical one.
-- `is_peak`, by contrast, IS data-driven: an hour counts as peak if its total arrival
-- volume across the whole observation window is at or above the median hour's volume.
with hours as (

    select unnest(generate_series(0, 23)) as hour_of_day

),

arrivals_by_hour as (

    select visit_hour as hour_of_day, count(*) as arrivals
    from {{ ref('stg_er_visits') }}
    group by 1

),

with_median as (

    select
        arrivals_by_hour.*,
        median(arrivals) over () as median_arrivals
    from arrivals_by_hour

)

select
    hours.hour_of_day,
    case
        when hours.hour_of_day between 7 and 14 then 'Day'
        when hours.hour_of_day between 15 and 22 then 'Evening'
        else 'Night'
    end as shift,
    coalesce(with_median.arrivals, 0) >= coalesce(with_median.median_arrivals, 0) as is_peak
from hours
left join with_median on hours.hour_of_day = with_median.hour_of_day
order by hours.hour_of_day
