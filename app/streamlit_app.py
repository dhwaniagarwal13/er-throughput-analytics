"""ER throughput dashboard — analyst-facing view over the DuckDB warehouse.

    make app     (or: streamlit run app/streamlit_app.py)

Reads the dbt marts directly. Every metric shown here is computed in dbt, so
this app and the Power BI report cannot disagree; the code below queries and
draws, it does not define measures.

Tab bodies land in Phase 4 -- the shell, the warehouse guard and the shared
filter state are here so the structure is fixed before the charts arrive.
"""

from __future__ import annotations

import duckdb
import streamlit as st

from erops.config import WAIT_TARGET_MINUTES, WAREHOUSE

st.set_page_config(page_title="ER Throughput Analytics", layout="wide")


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

    tabs = st.tabs(
        ["Overview", "Demand", "Wait performance", "Stability", "Segments", "Data quality"]
    )
    for tab, name in zip(tabs, ["overview", "demand", "wait", "spc", "segments", "quality"]):
        with tab:
            st.info(f"`{name}` panel — Phase 4.")

    del con  # placeholder until the panels query it


if __name__ == "__main__":
    main()
