-- "None" (no referral) is a real, common member of this dimension -- 58.6% of visits per
-- the Phase 0 profile -- not a null to be filtered out or coalesced away.
select distinct
    department_referral
from {{ ref('stg_er_visits') }}
