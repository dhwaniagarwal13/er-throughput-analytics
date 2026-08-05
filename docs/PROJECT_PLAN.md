# Project plan

How this project was actually sequenced, the decisions made along the way, and what's
deliberately out of scope. The [README roadmap](../README.md#roadmap) has the phase
checklist; this doc is the reasoning behind the order and the tradeoffs.

## Objective

Turn the Maven Analytics Hospital ER dataset (~9K visits) into an analytics platform
that can answer five operational questions honestly: is demand predictable, how long
do patients actually wait, where does the wait break down, is the process in control,
and does experience differ by who you are. Two audiences, one source of truth: an
interactive Streamlit app for analysts, a Power BI report for executives.

## Build order and why

1. **Scaffold the warehouse and pipeline first, data source second.** The initial
   scaffold pointed at a Kaggle dataset slug that turned out to be a stale mirror —
   caught and swapped to the live one before any modelling started. Cheap to fix
   early, expensive to discover after marts were built on top of it.
2. **Phase 0 — profile before modelling.** `docs/data_dictionary.md` was written from
   actually looking at the raw data, not from assuming the schema. This is what
   caught, early, that there's no departure timestamp — which is why CMS OP-18 is
   documented as *not computable* rather than approximated later.
3. **Phase 1 → 2 → 3 → 4 → 5, in that order, same day.** Staging → star schema →
   SPC/CI-bearing aggregates → 7 notebooks → Streamlit → Power BI assets. Each phase
   depends on the previous one's tables being correct, so they run in a strict chain —
   there's no version of this where the dashboard comes before the aggregates are
   validated.
4. **One correction mid-build:** `agg_segment_waits` was originally *flagging* small
   demographic cells instead of *suppressing* them — the kind of bug that looks fine
   in a code review and only shows up when you check what the output actually says.
   Fixed the same day it was built, before it reached a notebook or dashboard.
5. **CI added after the pipeline was proven, not before.** Lint, `dbt build/test`,
   and `pytest` on push were wired up once there was something worth protecting —
   gating an empty pipeline isn't useful.
6. **Faculty proposal added last.** Same underlying findings, written for a different
   reader (an academic audience evaluating the analysis, not an analyst using it).

## Decisions that shaped the scope

- **All business logic lives in dbt, nothing in the BI layer.** Power BI only holds
  formatting. This was a deliberate constraint, not a default — the alternative
  (letting each dashboard compute its own numbers) is the standard way two "single
  source of truth" dashboards end up disagreeing.
- **Median and P90 over mean, everywhere.** Wait times are right-skewed; the mean
  describes nobody's actual experience. This is why the metrics table in the README
  reports median/P90/% within target instead of an average.
- **State what can't be computed instead of approximating it.** CMS OP-18 needs a
  departure timestamp this dataset doesn't have. The choice was to say so in
  `docs/measure_spec.md`, not fake a proxy metric that would look plausible and be wrong.
- **No predictive modelling, by design.** This is a descriptive analytics project.
  Adding a forecast model would have been easy to bolt on and hard to validate to the
  same standard as the rest of the work — descoped rather than half-done.

## What's explicitly out of scope

- `.pbix` assembly is a manual step in Power BI Desktop — there's no automation tool
  in this environment for it, and the README says so directly rather than implying
  the dashboard ships itself.
- Single unnamed facility, no acuity/ESI triage level, no staffing or bed-census data.
  These bound every finding in `docs/findings.md` and are listed in
  `docs/limitations.md` rather than left for a reader to discover the hard way.

## If this continued

Nothing is currently planned past Phase 5 — the analysis, both dashboards, and the
written findings are complete and validated. The one open thread is the manual Power
BI Desktop step noted above; everything upstream of it is automated and tested.
