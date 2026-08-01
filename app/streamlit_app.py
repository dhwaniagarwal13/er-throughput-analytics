"""ER throughput dashboard — analyst-facing view over the DuckDB warehouse.

    make app     (or: streamlit run app/streamlit_app.py)

Reads the dbt marts through `erops.metrics` -- the exact same functions the
Phase 3 notebooks call. Every metric shown here is computed in dbt and
retrieved through that one shared module, so this app, the notebooks, and
the Power BI report cannot disagree: the code below queries and draws, it
does not define measures.
"""

from __future__ import annotations

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from erops import metrics
from erops.config import WAIT_TARGET_MINUTES, WAREHOUSE

st.set_page_config(page_title="ER Throughput Analytics", layout="wide")

AGE_ORDER = ["0-17", "18-34", "35-49", "50-64", "65+"]


@st.cache_resource
def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(WAREHOUSE), read_only=True)


def warehouse_missing() -> None:
    st.title("ER Throughput Analytics")
    st.error(f"No warehouse at `{WAREHOUSE}`.")
    st.markdown(
        """
        Build it first:

        ```
        make ingest    # fetch the Kaggle CSV into data/raw/
        make profile   # Phase 0 profile -- fills docs/data_dictionary.md
        make build     # dbt run -> data/er.duckdb
        ```
        """
    )


# ---------------------------------------------------------------------------
# Cached loaders -- one per tab, wrapping erops.metrics calls so the warehouse
# is queried once per session (until Streamlit's cache is cleared) rather than
# on every widget interaction. `_con` (leading underscore) tells Streamlit not
# to hash the connection object.
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _load_overview(_con):
    return {"kpi": metrics.kpi_summary(_con), "monthly": metrics.monthly_trend(_con)}


@st.cache_data(show_spinner=False)
def _load_demand(_con):
    return {
        "weekday": metrics.demand_by_weekday(_con),
        "hour": metrics.demand_by_hour(_con),
        "heatmap": metrics.demand_heatmap(_con),
        "stats": metrics.demand_volume_stats(_con),
    }


@st.cache_data(show_spinner=False)
def _load_wait(_con):
    return {
        "stats": metrics.wait_summary_stats(_con),
        "histogram": metrics.wait_histogram(_con),
        "within_target": metrics.wait_within_target(_con),
        "daily_trend": metrics.wait_daily_trend(_con),
        "load_hourly": metrics.load_vs_wait_hourly(_con),
        "load_corr": metrics.load_vs_wait_correlation(_con),
        "load_quintiles": metrics.load_vs_wait_quintiles(_con),
    }


@st.cache_data(show_spinner=False)
def _load_stability(_con):
    return {
        "wait_chart": metrics.spc_wait_chart(_con),
        "admit_chart": metrics.spc_admit_chart(_con),
        "signals": metrics.spc_signal_days(_con),
    }


@st.cache_data(show_spinner=False)
def _load_satisfaction(_con):
    return {
        "overview": metrics.satisfaction_overview(_con),
        "by_wait": metrics.satisfaction_by_wait_bucket(_con),
        "by_admitted": metrics.satisfaction_by_admitted(_con),
        "bias": metrics.satisfaction_nonresponse_bias(_con),
    }


@st.cache_data(show_spinner=False)
def _load_equity(_con):
    return {
        "gender": metrics.segment_equity_by(_con, "gender"),
        "age_band": metrics.segment_equity_by(_con, "age_band"),
        "race": metrics.segment_equity_by(_con, "race"),
        "extremes": metrics.segment_equity_extremes(_con, n=10),
        "low_n": metrics.segment_low_n_summary(_con),
    }


@st.cache_data(show_spinner=False)
def _load_quality(_con):
    return metrics.data_quality_report(_con)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------


def tab_overview(con: duckdb.DuckDBPyConnection) -> None:
    data = _load_overview(con)
    kpi, monthly = data["kpi"], data["monthly"]

    st.caption(
        f"Observation window: {kpi['date_min'].date()} to {kpi['date_max'].date()} "
        f"({kpi['n_days']} days, gap-free)."
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Visits", f"{kpi['visits']:,.0f}")
    c2.metric("Median wait", f"{kpi['median_wait_minutes']:.0f} min")
    c3.metric("% within target", f"{kpi['pct_within_target']:.1%}")
    c4.metric("Admission rate", f"{kpi['admission_rate']:.1%}")
    c5.metric(
        "Satisfaction response rate",
        f"{kpi['satisfaction_response_rate']:.1%}",
        help=f"Mean score among responders: {kpi['mean_satisfaction']:.2f} / 10",
    )

    fig = px.line(monthly, x="month", y="visits", markers=True, title="Monthly Visit Volume")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Business insight:** monthly volume has stayed in a narrow band with no sustained growth or "
        "decline trend across the 19-month window — see the Demand tab for why (arrival volume is close "
        "to flat by day-of-week and hour-of-day too), which supports planning around a stable baseline "
        "rather than a growth forecast."
    )

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=monthly["month"], y=monthly["median_wait_minutes"], mode="lines+markers",
                               name="Median wait"))
    fig2.add_hline(y=WAIT_TARGET_MINUTES, line_dash="dash", line_color="firebrick",
                    annotation_text=f"{WAIT_TARGET_MINUTES}-min target")
    fig2.update_layout(title="Monthly Median Wait vs. Target", xaxis_title="", yaxis_title="Minutes")
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        f"**Business insight:** median wait has run above the {WAIT_TARGET_MINUTES}-minute target in "
        "every single month of the observation window — this is a consistent, structural gap, not an "
        "occasional bad month. See the Wait Times tab for the full distribution and the Operational "
        "Stability tab for whether this gap is worsening."
    )


def tab_demand(con: duckdb.DuckDBPyConnection) -> None:
    data = _load_demand(con)
    weekday, hour, heatmap, stats = data["weekday"], data["hour"], data["heatmap"], data["stats"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Daily arrivals CV", f"{stats['cv_daily']:.2f}")
    c2.metric("Weekday avg / day", f"{stats['weekday_avg']:.1f}")
    c3.metric("Weekend avg / day", f"{stats['weekend_avg']:.1f}")

    weekday = weekday.sort_values("day_of_week_num")
    fig = px.bar(weekday, x="day_name", y="arrivals", title="Total Arrivals by Day of Week")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Business insight:** arrivals vary by less than 10% across days of the week (1,260-1,377), "
        "with only a mild weekend uptick — a uniform weekly staffing roster is defensible from this data; "
        "day-specific over/understaffing is not supported."
    )

    fig2 = px.bar(hour, x="hour_of_day", y="arrivals", color="is_peak",
                   title="Total Arrivals by Hour of Day", labels={"is_peak": "At/above median hour"})
    fig2.update_layout(xaxis={"dtick": 1})
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "**Business insight:** hourly totals show no pronounced diurnal peak or trough, and `is_peak` "
        "hours are scattered rather than clustered into a contiguous busy block — flat, not front- or "
        "back-loaded, shift staffing is what this data supports."
    )

    order = heatmap.drop_duplicates("day_of_week_num").sort_values("day_of_week_num")["day_name"].tolist()
    pivot = heatmap.pivot(index="day_name", columns="hour_of_day", values="arrivals").reindex(order)
    fig3 = px.imshow(pivot, color_continuous_scale="Blues", aspect="auto",
                      labels={"color": "Arrivals"}, title="Arrivals Heatmap — Day of Week x Hour of Day")
    st.plotly_chart(fig3, use_container_width=True)
    st.caption(
        "**Business insight:** no day x hour cell stands out as a hot spot — there is no specific "
        "combination (e.g. Friday evenings) that this data says needs extra coverage."
    )


def tab_wait(con: duckdb.DuckDBPyConnection) -> None:
    data = _load_wait(con)
    stats, target = data["stats"], data["within_target"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Median wait", f"{stats['median_wait']:.0f} min")
    c2.metric("P90 wait", f"{stats['p90_wait']:.0f} min")
    c3.metric("% within target", f"{target['pct']:.1%}")
    c4.metric("Mean wait", f"{stats['mean_wait']:.1f} min",
               help="Shown alongside the median for reference; measure_spec.md treats median as the "
                    "headline number.")

    hist = data["histogram"]
    fig = px.bar(hist, x="bucket_start", y="n", title="Wait Time Distribution (5-minute bins)")
    fig.add_vline(x=stats["median_wait"], line_dash="dash", line_color="firebrick",
                  annotation_text="Median")
    fig.add_vline(x=stats["p90_wait"], line_dash="dot", line_color="orange", annotation_text="P90")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"**Business insight:** the distribution is close to symmetric (skew {stats['skew_wait']:.2f}) "
        "with no long right tail (max observed wait 60 minutes) — the typical patient's experience, not "
        "a handful of outliers, is what drives target performance here."
    )

    daily = data["daily_trend"]
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=daily["visit_date"], y=daily["median_wait_minutes"], mode="lines",
                               name="Daily median wait", line={"width": 1}))
    fig2.add_trace(go.Scatter(x=daily["visit_date"], y=daily["p90_wait_minutes"], mode="lines",
                               name="Daily P90 wait", line={"width": 1, "dash": "dot"}))
    fig2.add_hline(y=WAIT_TARGET_MINUTES, line_dash="dash", line_color="firebrick",
                    annotation_text="Target")
    fig2.update_layout(title="Daily Median and P90 Wait Over Time", xaxis_title="", yaxis_title="Minutes")
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        f"**Business insight:** only {target['within']:,.0f} of {target['eligible']:,.0f} eligible "
        f"visits ({target['pct']:.1%}) meet the {WAIT_TARGET_MINUTES}-minute target, and the shortfall "
        "is persistent across the whole window rather than concentrated in a few bad days — see the "
        "Operational Stability tab for confirmation this is a stable-but-underperforming process."
    )

    st.markdown("#### Load vs. wait")
    hourly, corr, quintiles = data["load_hourly"], data["load_corr"], data["load_quintiles"]
    fig3 = px.scatter(hourly, x="arrivals", y="median_wait_minutes", opacity=0.35,
                       title=f"Arrivals per Hour vs. Median Wait (r = {corr:.3f})")
    st.plotly_chart(fig3, use_container_width=True)
    fig4 = px.bar(quintiles, x="arrivals_quintile", y="avg_median_wait",
                   title="Average Median Wait by Hourly-Arrivals Quintile")
    st.plotly_chart(fig4, use_container_width=True)
    st.caption(
        "**Business insight:** correlation between hourly arrival volume and wait time is essentially "
        f"zero (r = {corr:.3f}), and average wait is flat across all five volume quintiles — this data "
        "does not support a volume-triggered surge-staffing rule; the wait-time gap above is not "
        "explained by concurrent patient load."
    )


def tab_stability(con: duckdb.DuckDBPyConnection) -> None:
    data = _load_stability(con)
    wait_chart, admit_chart, signals = data["wait_chart"], data["admit_chart"], data["signals"]
    cl = wait_chart["wait_centre_line"].iloc[0]
    ucl = wait_chart["wait_ucl"].iloc[0]
    lcl = wait_chart["wait_lcl"].iloc[0]
    admit_cl = admit_chart["admit_centre_line"].iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Wait signal days", f"{wait_chart['spc_signal'].notna().sum()} / {len(wait_chart)}")
    c2.metric("Admission signal days", f"{admit_chart['admit_signal'].notna().sum()} / {len(admit_chart)}")
    c3.metric("Wait centre line", f"{cl:.1f} min")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=wait_chart["visit_date"], y=wait_chart["median_wait_minutes"],
                              mode="lines+markers", name="Daily median wait", marker={"size": 4}))
    sig = wait_chart[wait_chart["spc_signal"].notna()]
    fig.add_trace(go.Scatter(x=sig["visit_date"], y=sig["median_wait_minutes"], mode="markers",
                              name="Signal", marker={"color": "red", "size": 10, "symbol": "diamond"}))
    fig.add_hline(y=cl, line_dash="dot", annotation_text="Centre line")
    fig.add_hline(y=ucl, line_dash="dash", line_color="firebrick", annotation_text="UCL")
    fig.add_hline(y=lcl, line_dash="dash", line_color="firebrick", annotation_text="LCL")
    fig.update_layout(title="XmR Chart — Daily Median Wait", xaxis_title="", yaxis_title="Minutes")
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"**Business insight:** only {wait_chart['spc_signal'].notna().sum()} of {len(wait_chart)} days "
        "signal, all in a narrow mid-2023 window with no recurrence since — the wait-time process is "
        "stable, so the persistent target miss (Wait Times tab) needs a structural fix, not a reaction "
        "to day-to-day noise."
    )

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=admit_chart["visit_date"], y=admit_chart["admission_rate"], mode="markers",
                               name="Daily admission rate", marker={"size": 4, "opacity": 0.6}))
    fig2.add_trace(go.Scatter(x=admit_chart["visit_date"], y=admit_chart["admit_ucl"], mode="lines",
                               name="UCL", line={"color": "firebrick", "dash": "dash", "width": 1}))
    fig2.add_trace(go.Scatter(x=admit_chart["visit_date"], y=admit_chart["admit_lcl"], mode="lines",
                               name="LCL", line={"color": "firebrick", "dash": "dash", "width": 1}))
    fig2.add_hline(y=admit_cl, line_dash="dot", annotation_text="Centre line")
    sig2 = admit_chart[admit_chart["admit_signal"].notna()]
    fig2.add_trace(go.Scatter(x=sig2["visit_date"], y=sig2["admission_rate"], mode="markers",
                               name="Signal", marker={"color": "red", "size": 10, "symbol": "diamond"}))
    fig2.update_layout(title="p-Chart — Daily Admission Rate", xaxis_title="", yaxis_title="Admission rate")
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "**Business insight:** a single isolated admission-rate signal day, with control limits that "
        "widen on lower-volume days as expected — no sustained shift in case-mix proxy is evident."
    )

    if not signals.empty:
        st.markdown("**Signal days (both charts)**")
        st.dataframe(signals, use_container_width=True)


def tab_satisfaction(con: duckdb.DuckDBPyConnection) -> None:
    data = _load_satisfaction(con)
    overview, bias = data["overview"], data["bias"]

    c1, c2 = st.columns(2)
    c1.metric("Response rate", f"{overview['response_rate']:.1%}",
               help=f"{overview['responders']:,.0f} of {overview['total']:,.0f} visits")
    c2.metric("Mean satisfaction (responders)", f"{overview['mean_score']:.2f} / 10")
    st.caption(
        "Per `docs/measure_spec.md`, mean satisfaction must never be shown without the response rate "
        "beside it — both KPI cards above are mandatory pairing, not a stylistic choice."
    )

    by_wait = data["by_wait"]
    fig = px.bar(by_wait, x="wait_bucket", y="response_rate",
                  title="Survey Response Rate by Wait Bucket")
    fig.update_layout(yaxis_tickformat=".0%")
    st.plotly_chart(fig, use_container_width=True)

    by_admit = data["by_admitted"]
    fig2 = px.bar(by_admit, x="admitted_flag", y="response_rate",
                   title="Survey Response Rate by Admission Status")
    fig2.update_layout(yaxis_tickformat=".0%")
    st.plotly_chart(fig2, use_container_width=True)

    st.caption(
        f"**Business insight:** response propensity is essentially flat across wait buckets and "
        f"admission status (corr with wait = {bias['corr_wait_responded']:.3f}, corr with admitted = "
        f"{bias['corr_admitted_responded']:.3f}) — non-response does not appear driven by wait time or "
        "admission outcome, though it could still be driven by the patient's actual (unmeasured) "
        "satisfaction, which this data cannot test. See `notebooks/05_satisfaction.ipynb`."
    )


def tab_equity(con: duckdb.DuckDBPyConnection) -> None:
    data = _load_equity(con)
    low_n = data["low_n"]

    c1, c2 = st.columns(2)
    c1.metric("Segments below minimum cell size", f"{low_n['low_n_segments']:.0f} / {low_n['total_segments']:.0f}")
    c2.metric("% of segments suppressed from ranking", f"{low_n['pct_low_n']:.1%}")

    st.warning(
        "This dataset has no acuity or triage level. Wait time cannot be case-mix adjusted here — "
        "differences below describe what happened, not whether care was equitable. See "
        "`docs/limitations.md`."
    )

    by_age = data["age_band"].set_index("segment_value").reindex(AGE_ORDER).reset_index()
    c1, c2, c3 = st.columns(3)
    with c1:
        fig = px.bar(data["gender"], x="segment_value", y="median_wait", title="Median Wait by Gender")
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.bar(by_age, x="segment_value", y="median_wait", title="Median Wait by Age Band")
        st.plotly_chart(fig, use_container_width=True)
    with c3:
        fig = px.bar(data["race"], x="segment_value", y="median_wait", title="Median Wait by Race")
        fig.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "**Business insight:** group medians cluster within a few minutes of each other on every "
        "dimension — no single demographic axis shows a gap large enough, on its own, to flag as an "
        "equity concern."
    )

    extremes = data["extremes"]
    top = extremes["top"].head(5).assign(group="Top 5")
    bottom = extremes["bottom"].head(5).assign(group="Bottom 5")
    combined = pd.concat([top, bottom])
    combined["label"] = combined["age_band"] + " / " + combined["gender"] + " / " + combined["race"]
    combined["err_plus"] = combined["ci_upper"] - combined["median_wait_minutes"]
    combined["err_minus"] = combined["median_wait_minutes"] - combined["ci_lower"]
    fig2 = px.bar(combined, x="label", y="median_wait_minutes", color="group",
                   error_y="err_plus", error_y_minus="err_minus",
                   title="Top 5 vs Bottom 5 Segments by Median Wait, with 95% CI")
    fig2.update_layout(xaxis_tickangle=-25)
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "**Business insight:** the single most extreme segment gap is statistically distinguishable "
        "(non-overlapping CIs), but it is one comparison out of 86 segments — with that many "
        "comparisons, an extreme pair is expected to appear by chance alone. Treat this as a lead for "
        "qualitative review, not a policy conclusion. See `notebooks/06_segment_equity.ipynb`."
    )


def tab_quality(con: duckdb.DuckDBPyConnection) -> None:
    dq = _load_quality(con)
    cov, dup, inv = dq["date_coverage"], dq["duplicates"], dq["invalid_values"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Duplicate visit IDs", f"{dup['n_duplicate_ids']:.0f}")
    c2.metric("Date coverage", "Gap-free" if cov["gap_free"] else "Has gaps")
    c3.metric("Implausible waits", f"{inv['implausible_waits']:.0f}")
    c4.metric("Out-of-range satisfaction", f"{inv['out_of_range_satisfaction']:.0f}")

    st.caption(
        f"Observation window: {cov['min_date'].date()} to {cov['max_date'].date()} "
        f"({cov['span_days']} calendar days, {cov['distinct_days']} distinct visit dates)."
    )

    fig = px.bar(dq["row_counts"], x="table", y="row_count", title="Row Count per Mart Table")
    st.plotly_chart(fig, use_container_width=True)

    nulls = dq["nulls"]
    fig2 = px.bar(nulls.sort_values("pct_null", ascending=False), x="column", y="pct_null",
                   title="Percent Null by Column (fct_er_visit)")
    fig2.update_layout(yaxis_tickformat=".0%")
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        "**Business insight:** every operational column is 100% complete; the only material gap is "
        "`satisfaction_score` (~73% null), which is structural non-response, not a loading defect — see "
        "the Patient Satisfaction tab for whether that missingness biases the reported score."
    )

    st.markdown("**Full null / completeness report**")
    st.dataframe(nulls, use_container_width=True)


def main() -> None:
    if not WAREHOUSE.exists():
        warehouse_missing()
        return

    con = connect()
    st.title("ER Throughput Analytics")
    st.caption(
        f"Service-level target: seen within {WAIT_TARGET_MINUTES} minutes. "
        "All measures defined in docs/measure_spec.md."
    )

    tab_names = [
        "Overview", "Demand", "Wait Times", "Operational Stability",
        "Patient Satisfaction", "Equity", "Data Quality",
    ]
    tab_fns = [
        tab_overview, tab_demand, tab_wait, tab_stability,
        tab_satisfaction, tab_equity, tab_quality,
    ]
    for tab, fn in zip(st.tabs(tab_names), tab_fns):
        with tab:
            fn(con)


if __name__ == "__main__":
    main()
