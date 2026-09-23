"""Run discovery, matrix constants, and input validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

RUN_DIR_PATTERN = re.compile(r"^US\d+_(C0|CL|CO|CD|CS|CT)_R\d+$")
REPETITION_PATTERN = re.compile(r"_R(\d+)$")

USER_STORY_IDS = ("US02", "US08", "US18", "US25")
CONDITIONS = ("C0", "CL", "CO", "CD", "CS", "CT")
DEFAULT_REPETITIONS = 3
EXPECTED_RUN_COUNT = (
    len(USER_STORY_IDS) * len(CONDITIONS) * DEFAULT_REPETITIONS
)  # 72

# Materials file copied into experiment-input/context.md per condition.
# C0 intentionally omitted — no context.md.
CONDITION_CONTEXT_FILES = {
    "CL": "lexical.md",
    "CO": "operational.md",
    "CD": "decisional.md",
    "CS": "systemic.md",
    "CT": "total.md",
}


@dataclass
class RunInfo:
    run_id: str
    us_id: str
    condition: str
    run_path: Path


def make_run_id(us_id: str, condition: str, repetition: int) -> str:
    """Build Run_ID without zero-padding (e.g. US02_C0_R1)."""
    if us_id not in USER_STORY_IDS:
        raise ValueError(f"Unknown User Story: {us_id}")
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown condition: {condition}")
    if repetition < 1:
        raise ValueError(f"repetition must be >= 1, got {repetition}")
    return f"{us_id}_{condition}_R{repetition}"


def iter_planned_runs(
    repetitions: int = DEFAULT_REPETITIONS,
) -> list[tuple[str, str, str, int]]:
    """Return (run_id, us_id, condition, repetition) in deterministic order."""
    specs: list[tuple[str, str, str, int]] = []
    for us_id in USER_STORY_IDS:
        for condition in CONDITIONS:
            for repetition in range(1, repetitions + 1):
                specs.append(
                    (make_run_id(us_id, condition, repetition), us_id, condition, repetition)
                )
    return specs


def context_filename_for_condition(condition: str) -> str | None:
    """Return materials filename for condition, or None for C0."""
    if condition == "C0":
        return None
    if condition not in CONDITION_CONTEXT_FILES:
        raise ValueError(f"Unknown condition: {condition}")
    return CONDITION_CONTEXT_FILES[condition]


def discover_runs(runs_dir: Path) -> list[RunInfo]:
    """Discover run folders sorted deterministically (no shuffle)."""
    runs: list[RunInfo] = []
    if not runs_dir.is_dir():
        return runs
    for entry in sorted(runs_dir.iterdir()):
        if not entry.is_dir() or not RUN_DIR_PATTERN.match(entry.name):
            continue
        us_id, condition, _round = entry.name.split("_", 2)
        runs.append(RunInfo(entry.name, us_id, condition, entry))
    return runs


def validate_context_files(
    condition: str,
    *,
    context_path: Path,
    materials_context_source: Path | None,
) -> None:
    """
    Enforce C0/context mapping without silent fallbacks.

    - C0 must not have context.md
    - Other conditions must have context.md copied from the exact materials file
    """
    if condition == "C0":
        if context_path.exists():
            raise ValueError(f"Condition C0 must not contain context.md: {context_path}")
        return

    expected_name = context_filename_for_condition(condition)
    if expected_name is None:
        raise ValueError(f"Condition {condition} unexpectedly has no context mapping")

    if not context_path.is_file():
        raise FileNotFoundError(
            f"Condition {condition} requires context.md from materials/{expected_name}: "
            f"missing {context_path}"
        )

    if materials_context_source is None:
        # Allow structural checks when materials root is not supplied (existence only).
        if not context_path.is_file():
            raise FileNotFoundError(
                f"Condition {condition} should contain context.md in {context_path.parent}"
            )
        return

    if materials_context_source.name != expected_name:
        raise ValueError(
            f"Condition {condition} must use {expected_name}, "
            f"got {materials_context_source.name}"
        )
    if not materials_context_source.is_file():
        raise FileNotFoundError(
            f"Materials context source missing: {materials_context_source}"
        )

    # Literal copy check: run context must match materials byte-for-byte.
    if context_path.read_bytes() != materials_context_source.read_bytes():
        raise ValueError(
            f"context.md for {condition} does not match materials source "
            f"{materials_context_source} (scripts must copy literally, never rewrite)"
        )


def validate_run_inputs(run: RunInfo, *, root: Path | None = None) -> None:
    spec_path = run.run_path / "spec.md"
    user_story_path = run.run_path / "experiment-input" / "user-story.md"
    context_path = run.run_path / "experiment-input" / "context.md"

    if not spec_path.is_file():
        raise FileNotFoundError(f"spec.md not found in {run.run_path}")
    if not user_story_path.is_file():
        raise FileNotFoundError(f"user-story.md not found in {user_story_path.parent}")

    materials_source: Path | None = None
    if root is not None and run.condition != "C0":
        expected = context_filename_for_condition(run.condition)
        candidate = root / "materials" / run.us_id / expected
        # Experimental US: enforce literal match against materials/.
        # Synthetic SMOKE_* runs may carry context.md without a materials/ mirror.
        if run.us_id in USER_STORY_IDS:
            materials_source = candidate
        elif candidate.is_file():
            materials_source = candidate

    validate_context_files(
        run.condition,
        context_path=context_path,
        materials_context_source=materials_source,
    )


def parse_repeticao(run_id: str) -> int:
    match = REPETITION_PATTERN.search(run_id)
    if not match:
        raise ValueError(f"Cannot parse repetition from run id: {run_id}")
    return int(match.group(1))


def map_status_pt(internal_status: str, *, in_execution_order: bool) -> str:
    if internal_status == "Valid":
        return "Valida"
    if internal_status == "Failed":
        return "falha"
    if internal_status == "Started":
        return "incompleta"
    if in_execution_order:
        return "incompleta"
    return "excluída"
