-- Phase 0 profiling (src/erops/profile.py, docs/data_dictionary.md) showed:
--   * "Patient Id" is unique per row (0 duplicates) -- usable directly as the visit grain key.
--   * "Department Referral" ships the literal text "None" for no referral, never a blank field.
--     Read everything as VARCHAR so DuckDB's type inference can't quietly turn that "None"
--     text into a real NULL -- dim_department needs it as an explicit member, not a null.
--   * "Patient Admission Date" is DD-MM-YYYY HH:MM (e.g. 20-03-2024 -> day 20, not month 20).
--   * "Patient Satisfaction Score" is genuinely blank (real NULL) for ~73% of rows.
with source as (

    select *
    from read_csv(
        '{{ env_var("ER_ROOT") }}/data/raw/hospital_er.csv',
        header = true,
        columns = {
            'patient_id': 'VARCHAR',
            'admission_date_raw': 'VARCHAR',
            'first_initial': 'VARCHAR',
            'last_name': 'VARCHAR',
            'gender_raw': 'VARCHAR',
            'age_raw': 'VARCHAR',
            'race_raw': 'VARCHAR',
            'department_referral_raw': 'VARCHAR',
            'admitted_flag_raw': 'VARCHAR',
            'satisfaction_score_raw': 'VARCHAR',
            'wait_minutes_raw': 'VARCHAR',
            'case_management_flag_raw': 'VARCHAR'
        }
    )

),

typed as (

    select
        patient_id as visit_id,
        strptime(admission_date_raw, '%d-%m-%Y %H:%M') as visit_ts,
        first_initial,
        last_name,
        trim(gender_raw) as gender,
        try_cast(age_raw as integer) as age,
        trim(race_raw) as race,
        trim(department_referral_raw) as department_referral,
        upper(trim(admitted_flag_raw)) = 'TRUE' as admitted_flag,
        try_cast(satisfaction_score_raw as double) as satisfaction_score,
        try_cast(wait_minutes_raw as integer) as wait_minutes,
        case_management_flag_raw = '1' as case_management_flag
    from source

),

banded as (

    select
        *,
        case
            when age is null then null
            when age < 18 then '0-17'
            when age < 35 then '18-34'
            when age < 50 then '35-49'
            when age < 65 then '50-64'
            else '65+'
        end as age_band
    from typed

)

select
    visit_id,
    visit_ts,
    cast(visit_ts as date) as visit_date,
    extract(hour from visit_ts) as visit_hour,
    first_initial,
    last_name,
    gender,
    age,
    age_band,
    race,
    department_referral,
    admitted_flag,
    satisfaction_score,
    wait_minutes,
    -- Flagged, not dropped: visit counts must always reconcile to the source file.
    -- See measure_spec.md -- these are excluded from wait statistics downstream, not here.
    wait_minutes > {{ var('max_plausible_wait_minutes') }} as wait_implausible_flag,
    case_management_flag,
    md5(coalesce(age_band, 'unknown') || '|' || coalesce(gender, 'unknown') || '|' || coalesce(race, 'unknown'))
        as segment_key
from banded
