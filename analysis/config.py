"""Configuration for the pilot analysis layer.

Pilot-specific expected counts may appear in asserts only.
General logic must discover US / conditions / gaps / repetitions from data.
"""

from __future__ import annotations

from pathlib import Path

ANALYSIS_SEED = 20260930

REPO_ROOT = Path(__file__).resolve().parent.parent
COLLECTED = REPO_ROOT / "collected-data"
ANNOTATION = COLLECTED / "annotation"
ANNOTATION_PRIVATE = ANNOTATION / "private"
REFERENCE = COLLECTED / "reference"
AUDIT = COLLECTED / "audit"

OUTPUTS = Path(__file__).resolve().parent / "outputs"
TABLES = OUTPUTS / "tables"
FIGURES = OUTPUTS / "figures"
DERIVED = OUTPUTS / "derived"

# Input candidates (first existing wins where applicable)
QUESTIONS_CSV = COLLECTED / "questions.csv"
EVALUATOR_1_CSV = ANNOTATION / "evaluator-1.csv"
EVALUATOR_2_CSV = ANNOTATION / "evaluator-2.csv"
DISAGREEMENTS_CSV = ANNOTATION / "disagreements.csv"
BLIND_ID_MAP_CSV = ANNOTATION_PRIVATE / "blind-id-map.csv"
PRR_REFERENCE_CSV = REFERENCE / "prr-reference.csv"
PRR_GAP_STATES_CSV = REFERENCE / "prr-gap-states.csv"
RUN_SUMMARY_CSV = AUDIT / "run-summary.csv"
# Consolidated workbook (annotations may live here when CSVs are still empty shells)
DATA_DIR = REPO_ROOT / "data"
PRR_WORKBOOK_GLOB = "Matrizes de rastreabilidade - PRR*.xlsx"

# Pilot-only expected counts (validation asserts — not business logic)
PILOT_EXPECTED_QUESTIONS = 269
PILOT_EXPECTED_RUNS = 72
PILOT_EXPECTED_GAPS = 42
PILOT_EXPECTED_GAP_RUN_ROWS = 756
PILOT_EXPECTED_GAPS_BY_US = {
    "US02": 11,
    "US08": 10,
    "US18": 10,
    "US25": 11,
}

PILOT_DISCLAIMER = (
    "Este estudo é um piloto metodológico. As estatísticas apresentadas são "
    "descritivas e exploratórias e têm como objetivo avaliar a viabilidade do "
    "método e identificar padrões preliminares. Não devem ser interpretadas "
    "como estimativas generalizáveis do comportamento de LLMs ou do Spec Kit."
)

SPECIAL_NONE = "NONE"
SPECIAL_REVIEW = "REVIEW"
SOURCE_DIRECT = "DIRECT_AGREEMENT"
SOURCE_ADJUDICATION = "ADJUDICATION"

FIGURE_DPI = 300
