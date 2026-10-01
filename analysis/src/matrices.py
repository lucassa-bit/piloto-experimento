"""Gap × Run analytic matrix construction."""

from __future__ import annotations

import pandas as pd

from analysis import config
from analysis.src.validation import validate_gap_run_matrix


def build_gap_run_matrix(
    *,
    question_gap_mapping: pd.DataFrame,
    prr_reference: pd.DataFrame,
    prr_gap_states: pd.DataFrame,
    run_summary: pd.DataFrame,
    validate: bool = True,
    pilot_asserts: bool = True,
) -> pd.DataFrame:
    """
    One row per gap definition × run.

    recognized = 1 if ≥1 question in that run mapped to the gap (excluding NONE).
    question_count_for_gap = count of mapped questions for that gap in the run.
    """
    runs = run_summary.copy()
    # Discover runs from data
    run_cols = ["run_id", "user_story_id", "condition", "repetition"]
    for c in run_cols:
        if c not in runs.columns:
            raise ValueError(f"run_summary missing column: {c}")
    runs = runs[run_cols].drop_duplicates("run_id")

    gaps = prr_reference.copy()
    meta_cols = ["user_story_id", "gap_id"]
    for optional in ("importance", "category", "gap_category"):
        if optional in gaps.columns:
            meta_cols.append(optional)
    gaps = gaps[meta_cols].drop_duplicates(["user_story_id", "gap_id"])
    if "gap_category" not in gaps.columns:
        if "category" in gaps.columns:
            gaps = gaps.rename(columns={"category": "gap_category"})
        else:
            gaps["gap_category"] = ""
    if "importance" not in gaps.columns:
        gaps["importance"] = ""

    # Cartesian: each run × gaps of that US
    matrix = runs.merge(gaps, on="user_story_id", how="inner")

    states = prr_gap_states[
        ["user_story_id", "gap_id", "condition", "gap_state"]
    ].drop_duplicates(["user_story_id", "gap_id", "condition"])
    matrix = matrix.merge(states, on=["user_story_id", "gap_id", "condition"], how="left")

    if matrix["gap_state"].isna().any():
        missing = matrix[matrix["gap_state"].isna()][
            ["user_story_id", "gap_id", "condition"]
        ].drop_duplicates()
        raise ValueError(
            "Missing gap_state for some US×gap×condition rows; "
            f"examples:\n{missing.head(10).to_string(index=False)}"
        )

    # Counts from mapping (exclude NONE — never a PRR gap)
    qgm = question_gap_mapping.copy()
    if not qgm.empty:
        qgm = qgm[qgm["mapped_gap_id"] != config.SPECIAL_NONE]
        counts = (
            qgm.groupby(["run_id", "mapped_gap_id"], as_index=False)
            .size()
            .rename(columns={"mapped_gap_id": "gap_id", "size": "question_count_for_gap"})
        )
    else:
        counts = pd.DataFrame(columns=["run_id", "gap_id", "question_count_for_gap"])

    matrix = matrix.merge(counts, on=["run_id", "gap_id"], how="left")
    matrix["question_count_for_gap"] = (
        matrix["question_count_for_gap"].fillna(0).astype(int)
    )
    matrix["recognized"] = (matrix["question_count_for_gap"] > 0).astype(int)

    matrix["repetition"] = matrix["repetition"].astype(int)

    out = matrix[
        [
            "run_id",
            "user_story_id",
            "condition",
            "repetition",
            "gap_id",
            "importance",
            "gap_category",
            "gap_state",
            "recognized",
            "question_count_for_gap",
        ]
    ].sort_values(["user_story_id", "condition", "repetition", "gap_id"])
    out = out.reset_index(drop=True)

    if validate:
        result = validate_gap_run_matrix(
            out, prr_reference, run_summary, pilot_asserts=pilot_asserts
        )
        result.raise_if_failed()

    return out
