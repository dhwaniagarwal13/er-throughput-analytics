"""Export the marts to flat CSVs for the Power BI layer.

    python -m erops.export_dashboard

Flat CSVs rather than a live DuckDB connection: Power BI *can* reach DuckDB
over ODBC, but that couples the report to a driver install and to this
machine's file path. "Get Data > Text/CSV" has nothing to configure, so the
.pbix opens from the export alone -- no DuckDB, no dbt, no Python env.

The important consequence is architectural: every number in Power BI is
computed in dbt, so the Streamlit app and the .pbix cannot disagree. Power BI
holds presentation logic only.

Re-run after `make build`. The exports are git-ignored build artefacts.
"""

from __future__ import annotations

import sys

import duckdb

from erops.config import EXPORTS, WAREHOUSE

# Marts the BI layer consumes. Add here, not in Power BI.
TABLES = [
    "fct_er_visit",
    "agg_daily_ops",
    "agg_hourly_arrivals",
    "agg_segment_waits",
    "dim_date",
    "dim_time_of_day",
    "dim_patient_segment",
    "dim_department",
]


def main() -> int:
    if not WAREHOUSE.exists():
        raise SystemExit(f"{WAREHOUSE} not found -- run `make build` first.")

    EXPORTS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        for table in TABLES:
            df = con.execute(f"select * from main_marts.{table}").fetchdf()
            out = EXPORTS / f"{table}.csv"
            df.to_csv(out, index=False)
            print(f"wrote {out.name} ({len(df):,} rows, {len(df.columns)} columns)")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
