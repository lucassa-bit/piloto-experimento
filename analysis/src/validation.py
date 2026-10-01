"""Input and derived-artifact validation for the analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from analysis import config
from analysis.src.loaders import AnalysisInputs


class AnalysisValidationError(Exception):
    """Raised when critical validation fails; analysis must stop."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        msg = "Critical validation failed; analysis stopped.\n" + "\n".join(f"- {e}" for e in errors)
        super().__init__(msg)


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def raise_if_failed(self) -> None:
        if self.errors:
            raise AnalysisValidationError(self.errors)


def _norm_ids(value: str) -> list[str]:
    raw = (value or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    return parts


def validate_raw_inputs(inputs: AnalysisInputs, *, pilot_asserts: bool = True) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    blind = inputs.blind_id_map
    if "blind_item_id" not in blind.columns:
        errors.append("blind-id-map missing blind_item_id")
        return ValidationResult(False, errors, warnings)

    n_blind = blind["blind_item_id"].nunique()
    if blind["blind_item_id"].duplicated().any():
        errors.append("blind-id-map has duplicate blind_item_id values")
    if pilot_asserts and n_blind != config.PILOT_EXPECTED_QUESTIONS:
        errors.append(
            f"Expected {config.PILOT_EXPECTED_QUESTIONS} unique blind_item_id; found {n_blind}"
        )

    for name, df in (("evaluator-1", inputs.evaluator_1), ("evaluator-2", inputs.evaluator_2)):
        if "blind_item_id" not in df.columns or "mapped_gap_ids" not in df.columns:
            errors.append(f"{name} missing required columns")
            continue
        if set(df["blind_item_id"]) != set(blind["blind_item_id"]):
            errors.append(f"{name} blind_item_id set does not match blind-id-map")

    prr = inputs.prr_reference
    if not {"user_story_id", "gap_id"}.issubset(prr.columns):
        errors.append("prr-reference missing user_story_id/gap_id")
    else:
        gaps_by_us = prr.groupby("user_story_id")["gap_id"].nunique().to_dict()
        if pilot_asserts:
            for us, expected in config.PILOT_EXPECTED_GAPS_BY_US.items():
                got = int(gaps_by_us.get(us, 0))
                if got != expected:
                    errors.append(f"PRR gaps for {us}: expected {expected}, found {got}")
            total_gaps = int(prr["gap_id"].nunique()) if "gap_id" in prr.columns else 0
            # gaps are unique per US (same G03 on different US); count rows
            total_gap_defs = len(prr.drop_duplicates(["user_story_id", "gap_id"]))
            if total_gap_defs != config.PILOT_EXPECTED_GAPS:
                errors.append(
                    f"Expected {config.PILOT_EXPECTED_GAPS} gap definitions; found {total_gap_defs}"
                )

    states = inputs.prr_gap_states
    if not {"user_story_id", "gap_id", "condition", "gap_state"}.issubset(states.columns):
        errors.append("prr-gap-states missing required columns")
    else:
        bad_states = set(states["gap_state"].unique()) - {"OPEN", "ANSWERED"}
        if bad_states:
            errors.append(f"Unexpected gap_state values: {sorted(bad_states)}")

    runs = inputs.run_summary
    if "run_id" in runs.columns and pilot_asserts:
        n_runs = runs["run_id"].nunique()
        if n_runs != config.PILOT_EXPECTED_RUNS:
            warnings.append(f"Pilot expected {config.PILOT_EXPECTED_RUNS} runs; found {n_runs}")

    # C0: all gaps OPEN (scientific check when states present)
    if {"condition", "gap_state"}.issubset(states.columns):
        c0 = states[states["condition"] == "C0"]
        if not c0.empty and not (c0["gap_state"] == "OPEN").all():
            errors.append("C0 must have all gaps OPEN according to PRR")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def validate_final_mapping(
    final_map: pd.DataFrame,
    prr_reference: pd.DataFrame,
    *,
    pilot_asserts: bool = True,
) -> ValidationResult:
    """Validate the consolidated per-question final mapping (one row per question)."""
    errors: list[str] = []
    warnings: list[str] = []

    required = {
        "blind_item_id",
        "final_gap_ids",
        "mapping_source",
        "user_story_id",
        "question_text_raw",
    }
    missing = required - set(final_map.columns)
    if missing:
        errors.append(f"final mapping missing columns: {sorted(missing)}")
        return ValidationResult(False, errors, warnings)

    if final_map["blind_item_id"].duplicated().any():
        errors.append("final mapping has duplicate blind_item_id")
    if pilot_asserts and len(final_map) != config.PILOT_EXPECTED_QUESTIONS:
        errors.append(
            f"final mapping expected {config.PILOT_EXPECTED_QUESTIONS} rows; got {len(final_map)}"
        )

    empty = final_map["final_gap_ids"].astype(str).str.strip() == ""
    if empty.any():
        errors.append(f"{int(empty.sum())} questions lack a final mapping decision")

    # Build allowed gaps per US
    allowed = (
        prr_reference.groupby("user_story_id")["gap_id"].apply(lambda s: set(s.astype(str))).to_dict()
    )

    for row in final_map.itertuples(index=False):
        ids = _norm_ids(str(getattr(row, "final_gap_ids")))
        if not ids:
            continue
        if config.SPECIAL_REVIEW in ids:
            errors.append(
                f"{getattr(row, 'blind_item_id')}: REVIEW still pending — adjudication incomplete"
            )
            continue
        if config.SPECIAL_NONE in ids:
            if len(ids) != 1:
                errors.append(
                    f"{getattr(row, 'blind_item_id')}: NONE must appear alone, got {ids}"
                )
            continue
        if len(ids) != len(set(ids)):
            errors.append(f"{getattr(row, 'blind_item_id')}: duplicate gap ids in mapping")
        us = str(getattr(row, "user_story_id"))
        us_gaps = allowed.get(us, set())
        for gid in ids:
            if gid not in us_gaps:
                errors.append(
                    f"{getattr(row, 'blind_item_id')}: gap {gid} not in PRR for {us}"
                )

    sources = set(final_map["mapping_source"].unique()) - {
        config.SOURCE_DIRECT,
        config.SOURCE_ADJUDICATION,
    }
    if sources:
        errors.append(f"Unexpected mapping_source values: {sorted(sources)}")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def validate_gap_run_matrix(
    matrix: pd.DataFrame,
    prr_reference: pd.DataFrame,
    run_summary: pd.DataFrame,
    *,
    pilot_asserts: bool = True,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    required = {
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
    }
    missing = required - set(matrix.columns)
    if missing:
        errors.append(f"gap-run-matrix missing columns: {sorted(missing)}")
        return ValidationResult(False, errors, warnings)

    if pilot_asserts and len(matrix) != config.PILOT_EXPECTED_GAP_RUN_ROWS:
        errors.append(
            f"gap-run-matrix expected {config.PILOT_EXPECTED_GAP_RUN_ROWS} rows; got {len(matrix)}"
        )

    if not set(matrix["gap_state"].unique()).issubset({"OPEN", "ANSWERED"}):
        errors.append("gap_state must be OPEN or ANSWERED")
    if not set(matrix["recognized"].astype(int).unique()).issubset({0, 1}):
        errors.append("recognized must be 0 or 1")
    if (matrix["question_count_for_gap"].astype(int) < matrix["recognized"].astype(int)).any():
        errors.append("question_count_for_gap must be >= recognized")

    allowed_conditions = set(matrix["condition"].unique())
    if pilot_asserts:
        expected_c = {"C0", "CL", "CO", "CD", "CS", "CT"}
        if allowed_conditions != expected_c:
            errors.append(f"conditions expected {sorted(expected_c)}; got {sorted(allowed_conditions)}")
        reps = set(matrix["repetition"].astype(str).unique())
        if reps != {"1", "2", "3"} and set(matrix["repetition"].astype(int).unique()) != {1, 2, 3}:
            errors.append(f"repetitions unexpected: {sorted(reps)}")

    # Each run must have all gaps for its US
    gap_defs = prr_reference.drop_duplicates(["user_story_id", "gap_id"])
    expected_counts = gap_defs.groupby("user_story_id").size().to_dict()
    for run_id, grp in matrix.groupby("run_id"):
        us = grp["user_story_id"].iloc[0]
        exp = expected_counts.get(us)
        if exp is not None and len(grp) != exp:
            errors.append(f"run {run_id}: expected {exp} gap rows, got {len(grp)}")

    if "run_id" in run_summary.columns:
        missing_runs = set(run_summary["run_id"]) - set(matrix["run_id"])
        if missing_runs:
            errors.append(f"runs missing from gap-run-matrix: {sorted(missing_runs)[:10]}")

    if (matrix["gap_id"] == config.SPECIAL_NONE).any():
        errors.append("NONE must never appear as a PRR gap in gap-run-matrix")

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def validate_all_inputs(inputs: AnalysisInputs, *, pilot_asserts: bool = True) -> ValidationResult:
    return validate_raw_inputs(inputs, pilot_asserts=pilot_asserts)
