"""Repository path helpers.

Default layout: materials/, baselines/, runs/, collected-data/ under the repo.
Scripts must not wipe official runs/. Audit outputs go under collected-data/audit/.
"""

from __future__ import annotations

import os
from pathlib import Path

PRR_XLSX_NAME = "Matrizes de rastreabilidade - PRR.xlsx"


def repo_root() -> Path:
    if os.environ.get("CLARIFY_REPO"):
        return Path(os.environ["CLARIFY_REPO"]).resolve()
    return Path(__file__).resolve().parent.parent.parent


def workspace_root() -> Path:
    """Artifact root; defaults to repo (official collection)."""
    for key in ("CLARIFY_WORKSPACE", "CLARIFY_ROOT"):
        raw = os.environ.get(key)
        if not raw:
            continue
        path = Path(raw).resolve()
        # Ignore stale workspace env pointing at deleted validation dirs.
        if path == repo_root() or (path / "runs").is_dir() or (path / "collected-data").is_dir():
            return path
    return repo_root()


def get_root() -> Path:
    return workspace_root()


def scripts_dir() -> Path:
    return repo_root() / "scripts"


def gen_dir() -> Path:
    return scripts_dir() / "clarification-gen"


def baseline_gen_dir() -> Path:
    return scripts_dir() / "baseline-gen"


def baselines_dir() -> Path:
    return workspace_root() / "baselines"


def materials_dir() -> Path:
    return workspace_root() / "materials"


def runs_dir() -> Path:
    return workspace_root() / "runs"


def collected_dir() -> Path:
    return workspace_root() / "collected-data"


def audit_dir() -> Path:
    return collected_dir() / "audit"


def environment_dir() -> Path:
    return repo_root() / "environment"


def workspace_environment_dir() -> Path:
    return environment_dir()


def workspace_logs_dir() -> Path:
    return audit_dir() / "logs"


def prr_xlsx_path() -> Path:
    return repo_root() / "data" / PRR_XLSX_NAME


def collection_integrity_path() -> Path:
    return audit_dir() / "collection-integrity.json"


def collection_freeze_path() -> Path:
    """Alias kept for older call sites; integrity lives under audit/."""
    return collection_integrity_path()


def prompt_path() -> Path:
    return gen_dir() / "clarify-prompt.txt"


def specify_prompt_path() -> Path:
    return baseline_gen_dir() / "specify-prompt.txt"


def baseline_generation_csv_path() -> Path:
    return audit_dir() / "baseline-generation.csv"


def execution_table_path() -> Path:
    return audit_dir() / "execution-table.csv"


def questions_csv_path() -> Path:
    return collected_dir() / "questions.csv"


def run_summary_csv_path() -> Path:
    return collected_dir() / "run-summary.csv"


def prr_reference_csv_path() -> Path:
    return collected_dir() / "prr-reference.csv"


def prr_reference_blind_csv_path() -> Path:
    return collected_dir() / "prr-reference-blind.csv"


def prr_gap_states_csv_path() -> Path:
    return collected_dir() / "prr-gap-states.csv"


def annotation_dir() -> Path:
    return collected_dir() / "annotation"


def outputs_check_csv_path() -> Path:
    return collected_dir() / "outputs-check.csv"


def validation_report_path() -> Path:
    return audit_dir() / "validation-report.md"
