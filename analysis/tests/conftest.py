"""Shared pytest fixtures for analysis unit tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def prr_reference() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"user_story_id": "US01", "gap_id": "G01", "importance": "Necessária", "category": "Léxica"},
            {"user_story_id": "US01", "gap_id": "G02", "importance": "Complementar", "category": "Escopo"},
            {"user_story_id": "US02", "gap_id": "G01", "importance": "Necessária", "category": "Léxica"},
        ]
    )


@pytest.fixture
def prr_gap_states() -> pd.DataFrame:
    rows = []
    for us, gaps in (("US01", ["G01", "G02"]), ("US02", ["G01"])):
        for gid in gaps:
            for cond, state in (
                ("C0", "OPEN"),
                ("CL", "OPEN"),
                ("CT", "ANSWERED"),
            ):
                rows.append(
                    {
                        "user_story_id": us,
                        "gap_id": gid,
                        "condition": cond,
                        "gap_state": "OPEN" if cond == "C0" else state,
                    }
                )
    # Fix CT all ANSWERED, CL: G01 OPEN G02 ANSWERED for US01
    out = []
    for us, gaps in (("US01", ["G01", "G02"]), ("US02", ["G01"])):
        for gid in gaps:
            out.append({"user_story_id": us, "gap_id": gid, "condition": "C0", "gap_state": "OPEN"})
            out.append(
                {
                    "user_story_id": us,
                    "gap_id": gid,
                    "condition": "CL",
                    "gap_state": "OPEN" if gid == "G01" else "ANSWERED",
                }
            )
            out.append(
                {"user_story_id": us, "gap_id": gid, "condition": "CT", "gap_state": "ANSWERED"}
            )
    return pd.DataFrame(out)


@pytest.fixture
def run_summary() -> pd.DataFrame:
    rows = []
    for us in ("US01", "US02"):
        for cond in ("C0", "CL", "CT"):
            for rep in (1, 2):
                rows.append(
                    {
                        "run_id": f"{us}_{cond}_R{rep}",
                        "user_story_id": us,
                        "condition": cond,
                        "repetition": str(rep),
                    }
                )
    return pd.DataFrame(rows)
