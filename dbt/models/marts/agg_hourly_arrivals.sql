-- Grain: one row per (visit_date x hour_of_day). Feeds the demand heatmap and the
-- load-vs-wait scatter (arrivals per hour against that hour's observed median wait).
select
    visit_date,
    visit_hour as hour_of_day,
    count(*) as arrivals,
    median(wait_minutes) filter (where not wait_implausible_flag) as median_wait_minutes
from {{ ref('fct_er_visit') }}
group by 1, 2
