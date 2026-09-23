"""Repository and artifact path helpers."""

from __future__ import annotations

import os
from pathlib import Path


def get_root() -> Path:
    if os.environ.get("CLARIFY_ROOT"):
        return Path(os.environ["CLARIFY_ROOT"]).resolve()
    return Path(__file__).resolve().parent.parent.parent


def scripts_dir() -> Path:
    return get_root() / "scripts"


def gen_dir() -> Path:
    return scripts_dir() / "clarification-gen"


def baseline_gen_dir() -> Path:
    return scripts_dir() / "baseline-gen"


def baselines_dir() -> Path:
    return get_root() / "baselines"


def materials_dir() -> Path:
    return get_root() / "materials"


def runs_dir() -> Path:
    return get_root() / "runs"


def collected_dir() -> Path:
    return get_root() / "collected-data"


def prompt_path() -> Path:
    return gen_dir() / "clarify-prompt.txt"


def specify_prompt_path() -> Path:
    return baseline_gen_dir() / "specify-prompt.txt"


def baseline_generation_csv_path() -> Path:
    return collected_dir() / "baseline-generation.csv"


def baseline_gen_logs_dir() -> Path:
    return collected_dir() / "baseline-gen"


def execution_table_path() -> Path:
    return collected_dir() / "execution-table.csv"

def questions_raw_csv_path() -> Path:
    """Legacy path (pre-P3.5). Prefer questions_csv_path()."""
    return collected_dir() / "questions_raw.csv"


def questions_csv_path() -> Path:
    return collected_dir() / "questions.csv"


def run_summary_csv_path() -> Path:
    return collected_dir() / "run-summary.csv"


def classification_base_csv_path() -> Path:
    """Legacy path; P4 uses annotation-base.csv instead."""
    return collected_dir() / "classification_base.csv"


def annotation_base_csv_path() -> Path:
    return collected_dir() / "annotation-base.csv"


def annotation_blind_csv_path() -> Path:
    return collected_dir() / "annotation-blind.csv"


def prr_reference_csv_path() -> Path:
    return collected_dir() / "prr-reference.csv"


def prr_reference_blind_csv_path() -> Path:
    return collected_dir() / "prr-reference-blind.csv"


def prr_gap_states_csv_path() -> Path:
    return collected_dir() / "prr-gap-states.csv"


def classified_questions_csv_path() -> Path:
    return collected_dir() / "classified-questions.csv"


def annotation_dir() -> Path:
    return collected_dir() / "annotation"


def outputs_check_csv_path() -> Path:
    return collected_dir() / "outputs-check.csv"
