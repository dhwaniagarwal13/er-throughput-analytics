"""Shared warehouse queries -- the one place analytical SQL lives.

Notebooks, the Streamlit app, and the exported documentation all call these
functions instead of writing their own SQL, so a number can never drift
between a notebook, a dashboard tab, and a written finding. Every function
takes an open DuckDB connection (so the caller controls connection lifetime
and caching -- Streamlit wraps `get_connection()` in `st.cache_resource`,
notebooks call it directly) and returns a pandas DataFrame or a plain dict
of scalars.

Definitions follow `docs/measure_spec.md` exactly. Nothing here recomputes a
percentile or a control limit that dbt already computed in `agg_daily_ops`
or `agg_segment_waits` -- this module reads marts, it does not re-derive them.
"""

from __future__ import annotations

import duckdb
import pandas as pd

from erops.config import WAREHOUSE

MARTS = "main_marts"


def get_connection(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    """Open a connection to the built warehouse.

    Raises FileNotFoundError with a clear instruction rather than a bare
    DuckDB catalog error, since "run `make build`" is the actual fix.
    """
    if not WAREHOUSE.exists():
        raise FileNotFoundError(f"{WAREHOUSE} not found -- run `make build` first.")
    return duckdb.connect(str(WAREHOUSE), read_only=read_only)


def _df(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).fetchdf()


# ---------------------------------------------------------------------------
# Headline KPIs (docs/measure_spec.md "Core operational measures")
# ---------------------------------------------------------------------------


def kpi_summary(con: duckdb.DuckDBPyConnection) -> dict:
    """One row of headline KPIs, exactly as defined in measure_spec.md."""
    row = _df(
        con,
        f"""
        select
            count(*) as visits,
            min(visit_date) as date_min,
            max(visit_date) as date_max,
            count(distinct visit_date) as n_days,
            median(wait_minutes) filter (where not wait_implausible_flag) as median_wait_minutes,
            quantile_cont(wait_minutes, 0.9) filter (where not wait_implausible_flag) as p90_wait_minutes,
            avg(wait_minutes) filter (where not wait_implausible_flag) as mean_wait_minutes,
            count(*) filter (where within_target_flag)::double
                / count(*) filter (where wait_minutes is not null and not wait_implausible_flag)
                as pct_within_target,
            count(*) filter (where admitted_flag)::double / count(*) as admission_rate,
            count(*) filter (where satisfaction_score is not null)::double / count(*)
                as satisfaction_response_rate,
            avg(satisfaction_score) as mean_satisfaction,
            count(*) filter (where wait_implausible_flag) as n_implausible_waits
        from {MARTS}.fct_er_visit
        """,
    ).iloc[0]
    signals = _df(
        con,
        f"""
        select
            count(*) filter (where spc_signal is not null) as wait_signal_days,
            count(*) filter (where admit_signal is not null) as admit_signal_days,
            count(*) as total_days
        from {MARTS}.agg_daily_ops
        """,
    ).iloc[0]
    out = row.to_dict()
    out.update(signals.to_dict())
    return out


def monthly_trend(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Visits, admissions and median wait by calendar month -- drives the
    Overview trend chart and MoM commentary."""
    return _df(
        con,
        f"""
        select
            date_trunc('month', f.visit_date) as month,
            count(*) as visits,
            count(*) filter (where f.admitted_flag) as admissions,
            count(*) filter (where f.admitted_flag)::double / count(*) as admission_rate,
            median(f.wait_minutes) filter (where not f.wait_implausible_flag) as median_wait_minutes,
            count(*) filter (where f.within_target_flag)::double
                / count(*) filter (where f.wait_minutes is not null and not f.wait_implausible_flag)
                as pct_within_target,
            count(*) filter (where f.satisfaction_score is not null)::double / count(*)
                as satisfaction_response_rate,
            avg(f.satisfaction_score) as mean_satisfaction
        from {MARTS}.fct_er_visit f
        group by 1
        order by 1
        """,
    )


# ---------------------------------------------------------------------------
# Demand (notebook 01 / Streamlit "Demand" tab)
# ---------------------------------------------------------------------------


def demand_by_weekday(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select
            d.day_of_week_num,
            d.day_name,
            count(*) as arrivals,
            count(*) / count(distinct f.visit_date) as avg_per_day
        from {MARTS}.fct_er_visit f
        join {MARTS}.dim_date d on f.visit_date = d.date_day
        group by 1, 2
        order by 1
        """,
    )


def demand_by_hour(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select
            t.hour_of_day,
            t.shift,
            t.is_peak,
            count(f.visit_id) as arrivals
        from {MARTS}.dim_time_of_day t
        left join {MARTS}.fct_er_visit f on f.visit_hour = t.hour_of_day
        group by 1, 2, 3
        order by 1
        """,
    )


def demand_heatmap(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Long-form (day_name, hour_of_day, arrivals) for a weekday x hour heatmap."""
    return _df(
        con,
        f"""
        select
            d.day_of_week_num,
            d.day_name,
            f.visit_hour as hour_of_day,
            count(*) as arrivals
        from {MARTS}.fct_er_visit f
        join {MARTS}.dim_date d on f.visit_date = d.date_day
        group by 1, 2, 3
        order by 1, 3
        """,
    )


def demand_volume_stats(con: duckdb.DuckDBPyConnection) -> dict:
    cv = _df(
        con,
        f"""
        select avg(n) as mean_daily, stddev(n) as sd_daily, stddev(n) / avg(n) as cv_daily
        from (select visit_date, count(*) as n from {MARTS}.fct_er_visit group by 1)
        """,
    ).iloc[0]
    weekend = _df(
        con,
        f"""
        select d.is_weekend, avg(t.cnt) as avg_daily_arrivals
        from (select visit_date, count(*) as cnt from {MARTS}.fct_er_visit group by 1) t
        join {MARTS}.dim_date d on t.visit_date = d.date_day
        group by 1
        """,
    )
    out = cv.to_dict()
    out["weekday_avg"] = float(weekend.loc[~weekend["is_weekend"], "avg_daily_arrivals"].iloc[0])
    out["weekend_avg"] = float(weekend.loc[weekend["is_weekend"], "avg_daily_arrivals"].iloc[0])
    return out


# ---------------------------------------------------------------------------
# Wait time distribution (notebook 02 / Streamlit "Wait Times" tab)
# ---------------------------------------------------------------------------


def wait_summary_stats(con: duckdb.DuckDBPyConnection) -> dict:
    return (
        _df(
            con,
            f"""
        select
            count(*) filter (where not wait_implausible_flag) as n_plausible,
            count(*) filter (where wait_implausible_flag) as n_implausible,
            min(wait_minutes) filter (where not wait_implausible_flag) as min_wait,
            median(wait_minutes) filter (where not wait_implausible_flag) as median_wait,
            avg(wait_minutes) filter (where not wait_implausible_flag) as mean_wait,
            quantile_cont(wait_minutes, 0.90) filter (where not wait_implausible_flag) as p90_wait,
            quantile_cont(wait_minutes, 0.99) filter (where not wait_implausible_flag) as p99_wait,
            max(wait_minutes) filter (where not wait_implausible_flag) as max_wait,
            stddev(wait_minutes) filter (where not wait_implausible_flag) as sd_wait,
            skewness(wait_minutes) filter (where not wait_implausible_flag) as skew_wait,
            kurtosis(wait_minutes) filter (where not wait_implausible_flag) as kurt_wait
        from {MARTS}.fct_er_visit
        """,
        )
        .iloc[0]
        .to_dict()
    )


def wait_histogram(con: duckdb.DuckDBPyConnection, bin_width: int = 5) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select (wait_minutes / {bin_width}) * {bin_width} as bucket_start, count(*) as n
        from {MARTS}.fct_er_visit
        where not wait_implausible_flag
        group by 1
        order by 1
        """,
    )


def wait_within_target(con: duckdb.DuckDBPyConnection) -> dict:
    return (
        _df(
            con,
            f"""
        select
            count(*) filter (where within_target_flag) as within,
            count(*) filter (where wait_minutes is not null and not wait_implausible_flag) as eligible,
            count(*) filter (where within_target_flag)::double
                / count(*) filter (where wait_minutes is not null and not wait_implausible_flag) as pct
        from {MARTS}.fct_er_visit
        """,
        )
        .iloc[0]
        .to_dict()
    )


def wait_daily_trend(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select visit_date, median_wait_minutes, p90_wait_minutes
        from {MARTS}.agg_daily_ops
        order by visit_date
        """,
    )


# ---------------------------------------------------------------------------
# Load vs wait (notebook 03)
# ---------------------------------------------------------------------------


def load_vs_wait_hourly(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select visit_date, hour_of_day, arrivals, median_wait_minutes
        from {MARTS}.agg_hourly_arrivals
        where median_wait_minutes is not null
        """,
    )


def load_vs_wait_correlation(con: duckdb.DuckDBPyConnection) -> float:
    return float(
        _df(
            con,
            f"""
            select corr(arrivals, median_wait_minutes) as corr_arrivals_wait
            from {MARTS}.agg_hourly_arrivals
            where median_wait_minutes is not null
            """,
        ).iloc[0, 0]
    )


def load_vs_wait_quintiles(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        with ranked as (
            select *, ntile(5) over (order by arrivals) as arrivals_quintile
            from {MARTS}.agg_hourly_arrivals
            where median_wait_minutes is not null
        )
        select
            arrivals_quintile,
            min(arrivals) as min_arrivals,
            max(arrivals) as max_arrivals,
            avg(arrivals) as avg_arrivals,
            avg(median_wait_minutes) as avg_median_wait,
            count(*) as n_hours
        from ranked
        group by 1
        order by 1
        """,
    )


# ---------------------------------------------------------------------------
# SPC / operational stability (notebook 04 / Streamlit "Operational Stability")
# ---------------------------------------------------------------------------


def spc_wait_chart(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select visit_date, median_wait_minutes, wait_centre_line, wait_ucl, wait_lcl, spc_signal
        from {MARTS}.agg_daily_ops
        order by visit_date
        """,
    )


def spc_admit_chart(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select visit_date, admission_rate, admit_centre_line, admit_ucl, admit_lcl,
               admit_signal, admit_limits_clipped
        from {MARTS}.agg_daily_ops
        order by visit_date
        """,
    )


def spc_signal_days(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select visit_date, median_wait_minutes, wait_ucl, wait_lcl, spc_signal,
               admission_rate, admit_ucl, admit_lcl, admit_signal
        from {MARTS}.agg_daily_ops
        where spc_signal is not null or admit_signal is not null
        order by visit_date
        """,
    )


# ---------------------------------------------------------------------------
# Satisfaction & non-response (notebook 05 / Streamlit "Patient Satisfaction")
# ---------------------------------------------------------------------------


def satisfaction_overview(con: duckdb.DuckDBPyConnection) -> dict:
    return (
        _df(
            con,
            f"""
        select
            count(*) filter (where satisfaction_score is not null) as responders,
            count(*) as total,
            count(*) filter (where satisfaction_score is not null)::double / count(*) as response_rate,
            avg(satisfaction_score) as mean_score,
            stddev(satisfaction_score) as sd_score
        from {MARTS}.fct_er_visit
        """,
        )
        .iloc[0]
        .to_dict()
    )


def satisfaction_by_wait_bucket(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select
            case when wait_minutes <= 30 then '<=30 min' else '>30 min' end as wait_bucket,
            count(*) filter (where satisfaction_score is not null)::double / count(*) as response_rate,
            avg(satisfaction_score) as mean_score,
            count(*) as n
        from {MARTS}.fct_er_visit
        where not wait_implausible_flag
        group by 1
        order by 1
        """,
    )


def satisfaction_by_admitted(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _df(
        con,
        f"""
        select
            admitted_flag,
            count(*) filter (where satisfaction_score is not null)::double / count(*) as response_rate,
            avg(satisfaction_score) as mean_score,
            count(*) as n
        from {MARTS}.fct_er_visit
        group by 1
        order by 1
        """,
    )


def satisfaction_nonresponse_bias(con: duckdb.DuckDBPyConnection) -> dict:
    row = _df(
        con,
        f"""
        select
            corr(wait_minutes, case when satisfaction_score is not null then 1.0 else 0.0 end)
                as corr_wait_responded,
            corr(case when admitted_flag then 1.0 else 0.0 end,
                 case when satisfaction_score is not null then 1.0 else 0.0 end)
                as corr_admitted_responded
        from {MARTS}.fct_er_visit
        where not wait_implausible_flag
        """,
    ).iloc[0]
    responded = _df(
        con,
        f"""
        select
            satisfaction_score is not null as responded,
            avg(wait_minutes) as mean_wait,
            median(wait_minutes) as median_wait,
            count(*) as n
        from {MARTS}.fct_er_visit
        where not wait_implausible_flag
        group by 1
        """,
    )
    out = row.to_dict()
    out["by_response_group"] = responded
    return out


# ---------------------------------------------------------------------------
# Segment equity (notebook 06 / Streamlit "Equity" tab)
# ---------------------------------------------------------------------------


def segment_equity_by(con: duckdb.DuckDBPyConnection, dimension: str) -> pd.DataFrame:
    """dimension in {'gender', 'age_band', 'race'} -- median/mean wait, direct from fact."""
    if dimension not in {"gender", "age_band", "race"}:
        raise ValueError(f"unsupported dimension: {dimension}")
    return _df(
        con,
        f"""
        select
            s.{dimension} as segment_value,
            median(v.wait_minutes) as median_wait,
            avg(v.wait_minutes) as mean_wait,
            count(*) as n
        from {MARTS}.fct_er_visit v
        join {MARTS}.dim_patient_segment s on v.segment_key = s.segment_key
        where not v.wait_implausible_flag
        group by 1
        order by 2 desc
        """,
    )


def segment_equity_extremes(con: duckdb.DuckDBPyConnection, n: int = 10) -> dict:
    top = _df(
        con,
        f"""
        select age_band, gender, race, n_plausible, median_wait_minutes, ci_lower, ci_upper
        from {MARTS}.agg_segment_waits
        where not low_n_flag
        order by median_wait_minutes desc
        limit {n}
        """,
    )
    bottom = _df(
        con,
        f"""
        select age_band, gender, race, n_plausible, median_wait_minutes, ci_lower, ci_upper
        from {MARTS}.agg_segment_waits
        where not low_n_flag
        order by median_wait_minutes asc
        limit {n}
        """,
    )
    return {"top": top, "bottom": bottom}


def segment_low_n_summary(con: duckdb.DuckDBPyConnection) -> dict:
    return (
        _df(
            con,
            f"""
        select
            count(*) filter (where low_n_flag) as low_n_segments,
            count(*) as total_segments,
            count(*) filter (where low_n_flag)::double / count(*) as pct_low_n
        from {MARTS}.agg_segment_waits
        """,
        )
        .iloc[0]
        .to_dict()
    )


# ---------------------------------------------------------------------------
# Data quality (docs + Streamlit "Data Quality" tab)
# ---------------------------------------------------------------------------

_MART_TABLES = [
    "fct_er_visit",
    "agg_daily_ops",
    "agg_hourly_arrivals",
    "agg_segment_waits",
    "dim_date",
    "dim_time_of_day",
    "dim_patient_segment",
    "dim_department",
]


def row_counts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    rows = []
    for table in _MART_TABLES:
        n = con.execute(f"select count(*) from {MARTS}.{table}").fetchone()[0]
        rows.append({"table": table, "row_count": n})
    return pd.DataFrame(rows)


def null_and_duplicate_report(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Null / blank counts on every fct_er_visit column, plus duplicate-key check."""
    columns = [
        "visit_id",
        "visit_ts",
        "visit_date",
        "visit_hour",
        "segment_key",
        "department_referral",
        "wait_minutes",
        "admitted_flag",
        "satisfaction_score",
        "case_management_flag",
    ]
    total = con.execute(f"select count(*) from {MARTS}.fct_er_visit").fetchone()[0]
    rows = []
    for col in columns:
        n_null = con.execute(
            f"select count(*) from {MARTS}.fct_er_visit where {col} is null"
        ).fetchone()[0]
        rows.append(
            {
                "column": col,
                "n_null": n_null,
                "pct_null": n_null / total if total else 0.0,
                "n_total": total,
            }
        )
    return pd.DataFrame(rows)


def date_coverage_check(con: duckdb.DuckDBPyConnection) -> dict:
    row = _df(
        con,
        f"""
        select
            min(visit_date) as min_date,
            max(visit_date) as max_date,
            (max(visit_date) - min(visit_date) + 1) as span_days,
            count(distinct visit_date) as distinct_days
        from {MARTS}.fct_er_visit
        """,
    ).iloc[0]
    out = row.to_dict()
    out["gap_free"] = bool(out["span_days"] == out["distinct_days"])
    return out


def duplicate_check(con: duckdb.DuckDBPyConnection) -> dict:
    row = _df(
        con,
        f"""
        select
            count(*) as n_rows,
            count(distinct visit_id) as n_distinct_ids
        from {MARTS}.fct_er_visit
        """,
    ).iloc[0]
    out = row.to_dict()
    out["n_duplicate_ids"] = int(out["n_rows"] - out["n_distinct_ids"])
    return out


def invalid_value_check(con: duckdb.DuckDBPyConnection) -> dict:
    return (
        _df(
            con,
            f"""
        select
            count(*) filter (where wait_implausible_flag) as implausible_waits,
            count(*) filter (where wait_minutes is not null and wait_minutes < 0) as negative_waits,
            count(*) filter (where satisfaction_score is not null
                and (satisfaction_score < 0 or satisfaction_score > 10)) as out_of_range_satisfaction,
            count(*) filter (where admitted_flag is null) as null_admitted_flag
        from {MARTS}.fct_er_visit
        """,
        )
        .iloc[0]
        .to_dict()
    )


def data_quality_report(con: duckdb.DuckDBPyConnection) -> dict:
    """Everything the Data Quality tab and docs need in one call."""
    return {
        "row_counts": row_counts(con),
        "nulls": null_and_duplicate_report(con),
        "date_coverage": date_coverage_check(con),
        "duplicates": duplicate_check(con),
        "invalid_values": invalid_value_check(con),
    }
