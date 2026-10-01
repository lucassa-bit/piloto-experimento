"""Reusable analysis library for the Spec Kit clarification pilot."""

from analysis.src.loaders import load_analysis_inputs
from analysis.src.mappings import build_final_mapping, explode_question_gap_mapping
from analysis.src.matrices import build_gap_run_matrix
from analysis.src.metrics import (
    gap_recall,
    miss_rate,
    occurrence_rate,
    requery_rate,
    viability_metrics,
)
from analysis.src.validation import AnalysisValidationError, validate_all_inputs

__all__ = [
    "AnalysisValidationError",
    "build_final_mapping",
    "build_gap_run_matrix",
    "explode_question_gap_mapping",
    "gap_recall",
    "load_analysis_inputs",
    "miss_rate",
    "occurrence_rate",
    "requery_rate",
    "validate_all_inputs",
    "viability_metrics",
]
