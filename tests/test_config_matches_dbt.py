"""The Python layer and the dbt layer both hold measure parameters.

If they drift, Streamlit and Power BI silently disagree about what "seen
within target" means -- the exact failure this project's architecture is
supposed to make impossible. So it is a test, not a comment.
"""

from __future__ import annotations

import yaml

from erops.config import (
    MAX_PLAUSIBLE_WAIT_MINUTES,
    ROOT,
    SPC_SIGMA,
    WAIT_TARGET_MINUTES,
)


def dbt_vars() -> dict:
    with open(ROOT / "dbt" / "dbt_project.yml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["vars"]


def test_wait_target_matches():
    assert dbt_vars()["wait_target_minutes"] == WAIT_TARGET_MINUTES


def test_max_plausible_wait_matches():
    assert dbt_vars()["max_plausible_wait_minutes"] == MAX_PLAUSIBLE_WAIT_MINUTES


def test_spc_sigma_matches():
    assert float(dbt_vars()["spc_sigma"]) == SPC_SIGMA
