# Limitations

What this dataset cannot support. Written up front so that no finding in the report overreaches it.

## Structural limits of the data

**Single facility, unnamed.** One emergency department. Nothing here generalises to other hospitals, and there is no comparator or benchmark. Every finding is internal-relative: this department against its own history.

**No acuity or triage level.** No ESI score, no chief complaint. Wait times therefore cannot be case-mix adjusted, and a longer wait for one group may reflect lower clinical urgency rather than worse service. **This is the single most important caveat in the project** and it constrains the equity analysis in particular: an observed demographic gap in wait time is a description of what happened, not evidence of differential treatment.

**No departure timestamps.** Only arrival-to-provider wait is available. Length of stay, boarding time, and the standard CMS throughput measures (OP-18, OP-22) are not computable — see [`measure_spec.md`](measure_spec.md).

**No staffing or capacity data.** The load-versus-wait analysis infers a capacity ceiling from observed behaviour. It cannot attribute that ceiling to a cause — nurse ratios, bed availability, physician coverage and downstream inpatient flow are all invisible here.

**No patient history.** Visits cannot be linked into patient journeys, so return visits, frequent attenders and 72-hour ED revisits cannot be identified.

## Data quality limits

**Incomplete satisfaction scores.** A large share of visits have no score, and the missingness is almost certainly not random. This is analysed directly rather than ignored (`notebooks/05_satisfaction_and_nonresponse.ipynb`); any satisfaction figure is reported alongside its response rate.

**Small n in demographic cells.** Cross-tabulating race × age band × shift produces cells with very few visits. Confidence intervals are reported on every segment comparison, and segments below a minimum cell size are suppressed rather than plotted as if meaningful.

**Implausible wait values.** Waits beyond `max_plausible_wait_minutes` are flagged in staging and excluded from wait statistics, but retained in the fact table so that visit counts always reconcile to the source file. The exclusion is visible in the data-quality tab, not silent.

**Unverified provenance.** This is a teaching dataset distributed via Kaggle. It is plausible it is synthetic or partly synthetic. It is treated as a realistic modelling exercise, and conclusions are framed as "what this data shows", not "what this hospital should do".

## Methodological limits

**Descriptive, not causal.** Every relationship reported here is association. The load-versus-wait relationship is the closest thing to a mechanism, and even that is confounded by anything that varies with time of day.

**SPC baseline sensitivity.** Control limits depend on which period is treated as the baseline. If the baseline itself contains a shift, the limits absorb it and the chart looks calmer than reality. The chosen baseline is stated explicitly wherever a control chart appears.

**No seasonality decomposition.** The observation window is likely too short to separate seasonal effect from trend, so apparent trends are reported as observations over the window rather than as ongoing directions.
