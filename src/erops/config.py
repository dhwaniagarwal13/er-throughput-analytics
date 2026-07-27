"""Central paths and settings.

Everything that varies by machine or by run lives here, so no script needs a
hardcoded absolute path.
"""

from __future__ import annotations

import os
from pathlib import Path

# Repo root = three levels up from src/erops/config.py
ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data"
RAW = DATA / "raw"  # bronze: exactly what Kaggle shipped
EXPORTS = DATA / "exports"  # gold: flat CSVs for the BI layer
WAREHOUSE = DATA / "er.duckdb"

for _d in (RAW, EXPORTS):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Source dataset
# ---------------------------------------------------------------------------
# Maven Analytics "Hospital Emergency Room Data", mirrored on Kaggle. The CSV
# is not committed -- it is not ours to redistribute -- so `make ingest` pulls
# it and this is the one place that knows where from.
KAGGLE_DATASET = os.environ.get(
    "ER_KAGGLE_DATASET", "yashsahu02/hospital-emergency-room-data"
)

# Where ingest looks / writes. Any CSV dropped here by hand is picked up too,
# so a manual Kaggle download works identically to the API path.
RAW_CSV = RAW / "hospital_er.csv"

# ---------------------------------------------------------------------------
# Measure parameters
# ---------------------------------------------------------------------------
# These mirror dbt/dbt_project.yml `vars`. Both layers must agree, so if you
# change one, change the other -- tests/test_config_matches_dbt.py enforces it.
WAIT_TARGET_MINUTES = int(os.environ.get("ER_WAIT_TARGET_MINUTES", "30"))
MAX_PLAUSIBLE_WAIT_MINUTES = int(os.environ.get("ER_MAX_PLAUSIBLE_WAIT", "240"))
SPC_SIGMA = float(os.environ.get("ER_SPC_SIGMA", "3"))
