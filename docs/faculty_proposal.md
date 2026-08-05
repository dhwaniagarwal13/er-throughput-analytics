# ER Throughput & Patient Flow Analytics
### Project Proposal — Problem Statement and Proposed Solution

---

## 1. Introduction

Every ER visit leaves a timestamped trail: arrival, referral department, wait, admission decision, sometimes a satisfaction score. In most departments that trail is scattered across spreadsheets and one-off queries, and the same number — "median wait time" — quietly gets computed three different ways in three different reports. This project builds one governed pipeline instead: a single warehouse, one set of metric definitions, and two views on top of it (an interactive analyst dashboard and an executive report) that read from the same tables and therefore cannot disagree.

The system will be built and validated against the Maven Analytics Hospital Emergency Room dataset — about 9,200 visits at a single facility over roughly 19 months, with patient demographics, arrival timestamp, referral department, wait time, admission outcome, and an optional post-visit satisfaction score.

---

## 2. Problem Statement

An ED can't control how many patients show up. It can only control how it's staffed and organized to meet that demand — which means the measurement layer underneath those staffing decisions has to be trustworthy. A few specific ways ad-hoc reporting setups fail at this:

No single source of truth. Wait time computed once in a notebook, again in a live dashboard, again in a quarterly deck, with slightly different filters each time, produces numbers that quietly disagree — a failure mode that's easy to ship and hard to catch.

The wrong headline metric. ED wait times are strongly right-skewed: most patients are seen quickly, a long tail waits much longer. Reporting the mean flattens that shape and describes nobody's actual experience. What's needed is the median, the 90th percentile, and the share of patients seen within target — the convention real ED operations reporting uses, for a reason.

No check on process stability. Day-to-day fluctuation in wait time is normal. A genuine operational problem is not. Without something like statistical process control, there's no principled way to tell noise from signal, which means every bad day either gets over-reacted to or every real shift gets shrugged off as noise.

Untested assumptions about capacity and equity. "Wait times spike when volume is high" and "some patient groups wait longer than others" are the kind of claims that get asserted from a glance at a chart. Both are testable with correlation analysis and confidence intervals, and both should be tested rather than assumed.

**The short version: EDs need a measurement layer that's accurate, statistically defensible, and consistent across every tool that reads from it, and that doesn't exist by default.**

---

## 3. Motivation

Off-the-shelf hospital reporting tools tend to optimize for breadth — more charts, more filters — over rigor. A few things most of them don't do:

- Separate *stability* (is the process behaving consistently?) from *target attainment* (is it meeting its goal?). These are independent, and conflating them produces false reassurance: "nothing looks unusual" can be true in the same month the department misses its target every single day.
- Test whether missing survey data is actually random, rather than assuming it. Satisfaction surveys in particular are usually answered by a minority of patients, and whether that minority is representative determines whether the average is worth reporting at all.
- Report demographic comparisons with confidence intervals instead of bare averages across dozens of small subgroups — a setup that reliably manufactures "differences" by chance alone once you're comparing enough segments.

This project applies the same rigor used in industrial process control and public-health measurement design to ED operations data, using tools that are free and auditable end-to-end — nothing here requires a hospital's BI budget to reproduce.

---

## 4. Objectives

Seven concrete questions drive the build:

1. **Is the data trustworthy?** Profile the raw dataset for duplicates, implausible values, and missingness before any metric is built on top of it.
2. **Is arrival volume predictable?** Check whether arrivals follow a stable hour-of-day / day-of-week pattern that staffing could actually be planned against, versus a department that's structurally reacting to whatever shows up.
3. **What does a typical wait look like?** Check whether the mean is a reliable summary at all, or whether the distribution's skew means median and percentile measures are the only honest way to report it.
4. **At what point does wait time degrade?** Look for a volume threshold past which service degrades non-linearly — the practical definition of a capacity ceiling.
5. **Is the process in statistical control?** Apply control-chart methodology to separate ordinary variation from a genuine special-cause signal worth investigating.
6. **Is the satisfaction data usable?** Test whether survey non-response correlates with wait time or admission outcome — a biased responder pool would make the average worse than useless.
7. **Does experience differ across patient groups?** Compare wait times across demographic and referral segments with confidence intervals, so any gap that gets reported is statistically defensible and not just eyeballed off a bar chart.

---

## 5. Proposed System / Solution

The architecture puts every metric definition, statistical calculation, and control limit in one transformation layer, and every downstream view — notebook, live dashboard, executive report — only reads from it. That's the whole trick for preventing the "two dashboards disagree" problem above: there's exactly one place a percentile or a control limit gets computed, so there's exactly one place it can be wrong, and fixing it there fixes it everywhere.

```
Raw CSV (Kaggle export)
        |
        v
DuckDB warehouse  <-- lightweight, file-based, no server to manage
        |
        v
dbt staging layer        cleans, types, and flags data-quality issues
        |
        v
dbt marts (star schema)
   fact table:     one row per ER visit (wait time, admission, satisfaction)
   dimensions:     date, time-of-day/shift, patient segment, referral department
   aggregates:     pre-computed hourly arrivals, daily KPIs + control limits,
                    segment wait times + confidence intervals
        |
        +---> Python analysis notebooks (exploratory + statistical testing)
        |
        +---> Streamlit dashboard        (interactive, analyst-facing)
        |
        +---> Power BI report            (static export, executive-facing)
```

---

## 6. Proposed Methodology

- **Percentile-based service reporting.** Median and 90th-percentile wait time, plus percent of visits within target, in place of a single mean that hides the tail.
- **Statistical process control.** An XmR (individuals/moving-range) chart for daily median wait and a p-chart for daily admission rate, 3-sigma limits, standard run-rule signal detection (Western Electric rules) to tell normal variation from a genuine anomaly.
- **Load-versus-wait analysis.** Correlate hourly arrival volume against observed wait time to see if there's a threshold where service quality actually degrades.
- **Non-response bias testing.** Test directly whether missingness in the satisfaction survey correlates with wait time or admission outcome, rather than assuming the responders are representative of everyone.
- **Segment comparison with confidence intervals.** Every demographic or departmental wait-time comparison gets a 95% CI, and small-sample segments are flagged or suppressed instead of plotted as if they meant something.

Predictive modeling is deliberately out of scope. This is a descriptive, measurement-first project — the contribution is rigor in what gets measured and how, not a forecast.

---

## 7. Tools & Technologies

| Layer | Tool |
|---|---|
| Language | Python 3.11 |
| Warehouse | DuckDB (embedded, file-based) |
| Transformation | dbt (dbt-duckdb adapter) |
| Analysis | pandas, Jupyter notebooks |
| Visualization | Plotly |
| Interactive dashboard | Streamlit |
| Executive report | Power BI (DAX measures) |
| Quality assurance | dbt tests, pytest, ruff (linting) |

Everything here is open-source or free-tier — the whole thing runs on a single machine with no infrastructure budget.

---

## 8. Dataset

**Source:** Maven Analytics "Hospital Emergency Room Data" (public dataset, distributed via Kaggle), used here for academic analysis only.

**Scope:** A single, unnamed facility; roughly 9,200 visit records over about 19 months. Fields include patient demographics (age, gender, race), arrival timestamp, referral department, wait time, admission flag, and an optional post-visit satisfaction score.

**What's missing, stated up front instead of discovered later:**
- No acuity/triage severity level, so findings can't be case-mix adjusted.
- No departure timestamp, so length-of-stay and the formal CMS throughput measures (e.g. OP-18) can't be computed from this dataset — this gets stated explicitly rather than approximated with a different interval.
- No staffing or bed-census data, so any capacity finding is correlational, not causal.
- Satisfaction responses are expected to be substantially incomplete — which is exactly why non-response bias testing (Objective 6) is in the methodology from the start, not bolted on after someone notices the gap.

---

## 9. Expected Outcomes

By the end of this project I expect to have:

A tested data warehouse with documented data-quality checks, serving as the one source of truth for every metric downstream. A determination of whether this department's demand is predictable enough to staff against, backed by a coefficient of variation and a weekday/weekend breakdown rather than a guess. A wait-time profile built on median and P90 instead of a mean that would misrepresent it. A control-chart verdict on whether the process is statistically stable, checked separately from whether it's hitting its target. A read on whether the satisfaction scores can be trusted as representative, or whether they're skewed by who bothers to respond. A confidence-interval-backed answer on whether wait times differ meaningfully across demographic groups. And two dashboards — one interactive, one executive-facing — that are provably reporting the same numbers because they're built from the same tables.

---

## 10. Scope & Limitations

This is descriptive analytics, not predictive modeling or causal inference, and I'm scoping it that way on purpose. Findings won't generalize past this one facility, and without acuity data, no wait-time or equity finding gets a causal interpretation attached to it. These constraints get documented next to each finding as it's produced, not left for whoever reads the report to notice on their own.

---

## 11. Proposed Work Plan

| Phase | Deliverable |
|---|---|
| 0 | Data profiling — validate raw data quality before any modelling begins |
| 1 | Staging layer — typed, cleaned, quality-flagged visit records |
| 2 | Star-schema marts — fact/dimension tables plus pre-computed aggregates (SPC limits, segment confidence intervals) |
| 3 | Analysis notebooks — one per objective (demand, wait distribution, load-vs-wait, process stability, non-response bias, segment equity), each concluding in a summary of findings, recommendations, and limitations |
| 4 | Interactive Streamlit dashboard — analyst-facing, live queries against the warehouse |
| 5 | Power BI executive report — static export built from the same governed metrics |

---

## 12. Conclusion

Every ED faces the same underlying problem: measuring throughput and patient experience in a way that holds up to scrutiny and doesn't quietly contradict itself across tools. This project's answer is to put the metric logic in one place and lean on methods that are already standard elsewhere — percentile reporting, control charts, bias testing, interval-based comparisons — rather than inventing something novel. The goal is a measurement foundation someone could actually make a staffing decision on, built entirely on tooling anyone can install for free and audit line by line.
