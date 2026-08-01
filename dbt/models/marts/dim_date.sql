-- Continuous calendar from min to max observed visit date -- not just the distinct dates
-- that happen to have visits. Power BI's DATEADD(..., -1, MONTH) time intelligence (see
-- dashboard/dax_measures.txt) requires a gap-free date table, so a `select distinct
-- visit_date` here would silently break every MoM measure on a day with zero arrivals.
with bounds as (

    select min(visit_date) as min_date, max(visit_date) as max_date
    from {{ ref('stg_er_visits') }}

),

calendar as (

    select unnest(generate_series(min_date, max_date, interval 1 day))::date as date_day
    from bounds

)

select
    date_day,
    extract(year from date_day) as year,
    extract(month from date_day) as month,
    strftime(date_day, '%B') as month_name,
    extract(dayofweek from date_day) as day_of_week_num,
    strftime(date_day, '%A') as day_name,
    extract(dayofweek from date_day) in (0, 6) as is_weekend
from calendar
