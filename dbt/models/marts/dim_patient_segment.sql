-- Grain: one row per distinct (age_band, gender, race) combination present in the data --
-- a bridge table, not a full cross-join, so it never implies a segment that doesn't exist.
select distinct
    segment_key,
    age_band,
    gender,
    race
from {{ ref('stg_er_visits') }}
