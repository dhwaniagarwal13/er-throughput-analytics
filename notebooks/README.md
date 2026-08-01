# Analysis notebooks

Each notebook answers one question and **ends in a written conclusion**, not a chart. A notebook whose last cell is a plot has not finished the analysis.

All of them read the dbt marts from `data/er.duckdb` through the shared query functions in `src/erops/metrics.py` — none of them re-derive metrics from the raw CSV or write ad hoc SQL, so the numbers here match the Streamlit dashboard by construction, not by convention. Every notebook also closes with an Executive Summary, Business Recommendations, Limitations, and Next Steps section.

| Notebook | Question |
|---|---|
| `00_profile.ipynb` | What is actually in this file? (Phase 0 — run before anything else) |
| `01_demand_patterns.ipynb` | Is arrival volume predictable enough to staff against? |
| `02_wait_distribution.ipynb` | What does a typical wait look like, and what does the tail look like? |
| `03_load_vs_wait.ipynb` | At what arrival volume does wait time degrade? |
| `04_spc.ipynb` | Is the process in control, or drifting? |
| `05_satisfaction.ipynb` | Who answers the satisfaction survey, and does that bias the score? |
| `06_segment_equity.ipynb` | Does wait time differ by patient group, and is the difference real? |

Note on `06`: the dataset has no acuity or triage level, so waits cannot be case-mix adjusted. Differences found there describe what happened; they are not evidence of differential treatment. See `docs/limitations.md`.
