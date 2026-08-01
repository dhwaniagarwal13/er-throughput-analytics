# Validation

What was actually checked before this project was called done, and the real result of each check —
not a claim, a log.

## Automated checks

| Check | Command | Result |
|---|---|---|
| ✅ dbt data tests | `dbt test --project-dir dbt --profiles-dir dbt` | **34 of 34 passed** (uniqueness, not-null, and referential-integrity tests across every mart). |
| ✅ Python unit tests | `pytest -q` | **3 of 3 passed** (`tests/test_config_matches_dbt.py` — confirms `WAIT_TARGET_MINUTES`, `MAX_PLAUSIBLE_WAIT_MINUTES`, `SPC_SIGMA` are identical between `src/erops/config.py` and `dbt/dbt_project.yml`). |
| ✅ Lint | `ruff check src app tests` | **All checks passed**, zero warnings. |
| ✅ Notebook execution | `jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb` | All 7 notebooks execute end-to-end from a clean kernel with no errors; outputs committed are real, not hand-typed. |

## Cross-artifact reconciliation

Every KPI is computed exactly once, in `src/erops/metrics.py` (Python) or a dbt mart (SQL), and read
from there by every consumer. The checks below confirm that promise held in practice, not just in
theory:

| Check | Method | Result |
|---|---|---|
| ✅ Notebook metrics equal SQL | Every notebook calls `erops.metrics.*` functions directly — there is no separate SQL to drift from. | By construction: 7/7 notebooks import and call the shared module (zero inline `con.execute` calls outside `00_profile.ipynb`'s one-off, notebook-only categorical breakdown, which itself queries the same mart). |
| ✅ Streamlit KPIs reconcile | Manual browser walkthrough of all 7 tabs (`app/streamlit_app.py`) against notebook output. | Confirmed identical: Visits 9,216; Median wait 35 min; P90 56 min; % within target 40.7%; Admission rate 50.0%; Satisfaction response rate 27.3%; Mean satisfaction 4.99; SPC signal days 3 (wait) / 1 (admit); Segment low-n 16/86 (18.6%). No console errors, no exceptions, on any tab. |
| ✅ Exported CSVs validated | `python -m erops.export_dashboard`, re-run against the current warehouse. | Row counts match the live marts exactly: `fct_er_visit` 9,216, `agg_daily_ops` 579, `agg_hourly_arrivals` 6,757, `agg_segment_waits` 86, `dim_date` 579, `dim_time_of_day` 24, `dim_patient_segment` 86, `dim_department` 8. |
| ✅ Power BI assets regenerated | `powerbi_theme.json` JSON-validated, `dax_measures.txt` reviewed against `docs/measure_spec.md` (no metric is recomputed in DAX — every percentile and control limit is sourced from the dbt aggregate). | Current as of the latest export; `.pbix` assembly itself remains a manual Power BI Desktop step (see `dashboard/README.md`). |

## Data-quality validation (warehouse itself)

Computed by `erops.metrics.data_quality_report`, the same function backing the Streamlit "Data
Quality" tab and `notebooks/00_profile.ipynb`:

- **Row counts:** `fct_er_visit` 9,216 rows; every dimension and aggregate table's row count matches
  its expected grain (see `docs/architecture.md`).
- **Duplicates:** 0 duplicate `visit_id` values.
- **Date coverage:** gap-free, 2023-04-01 to 2024-10-30 (579 calendar days = 579 distinct visit dates).
- **Missing values:** every operational column 100% complete except `satisfaction_score` (72.7% null,
  structural non-response — see `notebooks/05_satisfaction.ipynb`).
- **Invalid values:** 0 implausible waits, 0 negative waits, 0 out-of-range satisfaction scores, 0 null
  admission flags.

## What was *not* automated

- **`.pbix` assembly** is a manual Power BI Desktop step (Get Data > Text/CSV, apply theme, paste DAX
  measures) — there is no Power BI automation tool available in this environment. See `dashboard/README.md`.
- **Notebook narrative quality** (are the interpretations correct, not just the numbers) was reviewed by
  the author while writing it, not independently checked by a second reviewer.
- **Visual regression** of chart appearance was checked once via a live browser walkthrough of the
  Streamlit app; there is no automated screenshot-diff test in this repo.
