"""End-to-end analysis pipeline (callable from notebook or CLI)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from analysis import config
from analysis.src.loaders import AnalysisInputs, environment_versions, load_analysis_inputs
from analysis.src.mappings import build_final_mapping, explode_question_gap_mapping
from analysis.src.matrices import build_gap_run_matrix
from analysis.src.metrics import (
    classify_repetition_stability,
    dataset_description,
    format_rate,
    gap_recall,
    occurrence_rate,
    questions_summary_stats,
    requery_rate,
    viability_metrics,
)
from analysis.src import plots
from analysis.src.statistics import (
    clustered_bootstrap_ci,
    exploratory_inferential_models_disabled,
    fit_mixed_logit_recognized_future,
)
from analysis.src.validation import (
    AnalysisValidationError,
    validate_all_inputs,
)


@dataclass
class AnalysisArtifacts:
    inputs: AnalysisInputs
    final_map: pd.DataFrame
    question_gap_mapping: pd.DataFrame
    gap_run_matrix: pd.DataFrame
    tables: dict[str, pd.DataFrame]
    figure_paths: list[Path]
    meta: dict[str, Any]
    descriptive_notes: list[str]


def _ensure_dirs() -> None:
    for d in (config.TABLES, config.FIGURES, config.DERIVED):
        d.mkdir(parents=True, exist_ok=True)


def run_pipeline(
    *,
    collected: Path | None = None,
    pilot_asserts: bool = True,
    write_outputs: bool = True,
) -> AnalysisArtifacts:
    """
    Full deterministic pipeline. Raises AnalysisValidationError on critical failures.
    Does not modify experimental inputs.
    """
    _ensure_dirs()
    inputs = load_analysis_inputs(collected=collected)

    raw = validate_all_inputs(inputs, pilot_asserts=pilot_asserts)
    raw.raise_if_failed()

    final_map = build_final_mapping(
        blind_id_map=inputs.blind_id_map,
        evaluator_1=inputs.evaluator_1,
        evaluator_2=inputs.evaluator_2,
        disagreements=inputs.disagreements,
        prr_reference=inputs.prr_reference,
        validate=True,
        pilot_asserts=pilot_asserts,
    )

    qgm = explode_question_gap_mapping(final_map)
    matrix = build_gap_run_matrix(
        question_gap_mapping=qgm,
        prr_reference=inputs.prr_reference,
        prr_gap_states=inputs.prr_gap_states,
        run_summary=inputs.run_summary,
        validate=True,
        pilot_asserts=pilot_asserts,
    )

    # --- tables ---
    desc = dataset_description(
        questions=inputs.questions,
        prr_reference=inputs.prr_reference,
        run_summary=inputs.run_summary,
    )
    viability = viability_metrics(final_map, qgm)

    dataset_summary = pd.DataFrame(
        [
            {"metric": "n_user_stories", "value": desc["n_user_stories"]},
            {"metric": "n_gaps", "value": desc["n_gaps"]},
            {"metric": "n_runs", "value": desc["n_runs"]},
            {"metric": "n_questions", "value": desc["n_questions"]},
            {"metric": "direct_agreement", "value": viability["direct_agreement"]},
            {"metric": "adjudicated", "value": viability["adjudicated"]},
            {"metric": "none_count", "value": viability["none_count"]},
            {"metric": "none_rate", "value": viability["none_rate"]},
            {"metric": "multi_gap_count", "value": viability["multi_gap_count"]},
            {"metric": "gap_run_matrix_rows", "value": len(matrix)},
        ]
    )

    questions_by_condition = (
        inputs.questions.groupby("condition", as_index=False)
        .size()
        .rename(columns={"size": "n_questions"})
    )

    # RQ1 — C0 OPEN only
    rq1_global = gap_recall(matrix, conditions=["C0"], gap_state="OPEN")
    rq1_us = gap_recall(matrix, conditions=["C0"], gap_state="OPEN", groupby=["user_story_id"])
    rq1_imp = gap_recall(matrix, conditions=["C0"], gap_state="OPEN", groupby=["importance"])
    rq1_cat = gap_recall(matrix, conditions=["C0"], gap_state="OPEN", groupby=["gap_category"])

    # RQ2 — remaining OPEN under context conditions
    rq2_conditions = ["CL", "CO", "CD", "CS", "CT"]
    rq2_by_cond = gap_recall(matrix, conditions=rq2_conditions, gap_state="OPEN", groupby=["condition"])
    # include C0 in a full OPEN-by-condition table for export
    recall_all_cond = gap_recall(
        matrix,
        conditions=sorted(matrix["condition"].unique()),
        gap_state="OPEN",
        groupby=["condition"],
    )
    recall_by_us = gap_recall(matrix, gap_state="OPEN", groupby=["user_story_id"])
    recall_by_us_cond = gap_recall(
        matrix, gap_state="OPEN", groupby=["condition", "user_story_id"]
    )
    recall_by_cat = gap_recall(matrix, gap_state="OPEN", groupby=["gap_category"])
    recall_by_imp = gap_recall(matrix, gap_state="OPEN", groupby=["importance"])

    # RQ3 — requery ANSWERED
    requery_global = requery_rate(matrix)
    requery_by_cond = requery_rate(
        matrix, groupby=["condition"]
    )
    requery_by_us = requery_rate(matrix, groupby=["user_story_id"])
    requery_by_cat = requery_rate(matrix, groupby=["gap_category"])

    occ = occurrence_rate(matrix)
    stability = classify_repetition_stability(occ)

    # NONE summary
    none_mask = final_map["final_gap_ids"].astype(str).str.strip() == config.SPECIAL_NONE
    unmatched_summary = pd.DataFrame(
        [
            {
                "total_none": int(none_mask.sum()),
                "none_rate": viability["none_rate"],
            }
        ]
    )
    none_by_us = (
        final_map.assign(is_none=none_mask)
        .groupby("user_story_id")["is_none"]
        .agg(["sum", "mean"])
        .reset_index()
        .rename(columns={"sum": "none_count", "mean": "none_rate"})
    )
    none_by_cond = (
        final_map.assign(is_none=none_mask)
        .groupby("condition")["is_none"]
        .agg(["sum", "mean"])
        .reset_index()
        .rename(columns={"sum": "none_count", "mean": "none_rate"})
    )

    # Raw question counts
    q_per_run = inputs.questions.groupby("run_id").size()
    q_stats = questions_summary_stats(q_per_run)

    tables: dict[str, pd.DataFrame] = {
        "dataset-summary": dataset_summary,
        "questions-by-condition": questions_by_condition,
        "gap-recall-by-condition": recall_all_cond,
        "gap-recall-by-user-story": recall_by_us,
        "gap-recall-c0-by-user-story": rq1_us,
        "gap-recall-c0-by-importance": rq1_imp,
        "gap-recall-c0-by-category": rq1_cat,
        "gap-recall-rq2-by-condition": rq2_by_cond,
        "gap-recall-open-by-condition-us": recall_by_us_cond,
        "gap-recall-open-by-category": recall_by_cat,
        "gap-recall-open-by-importance": recall_by_imp,
        "requery-rate-global": requery_global,
        "requery-rate-by-condition": requery_by_cond,
        "requery-rate-by-user-story": requery_by_us,
        "requery-rate-by-category": requery_by_cat,
        "gap-occurrence-rate": occ,
        "repetition-stability": stability,
        "unmatched-summary": unmatched_summary,
        "none-by-user-story": none_by_us,
        "none-by-condition": none_by_cond,
        "question-count-stats-per-run": pd.DataFrame([q_stats]),
        "viability-metrics": pd.DataFrame([{k: v for k, v in viability.items()}]),
        "rq1-c0-global": rq1_global,
    }

    figure_paths: list[Path] = []
    if write_outputs:
        final_map.to_csv(config.DERIVED / "final-question-mapping.csv", index=False)
        qgm.to_csv(config.DERIVED / "question-gap-mapping.csv", index=False)
        matrix.to_csv(config.DERIVED / "gap-run-matrix.csv", index=False)

        for name, table in tables.items():
            table.to_csv(config.TABLES / f"{name}.csv", index=False)

        figure_paths.extend(plots.plot_questions_by_condition(inputs.questions, config.FIGURES))
        figure_paths.extend(plots.plot_gap_recall_by_condition(recall_all_cond, config.FIGURES))
        figure_paths.extend(plots.plot_requery_by_condition(requery_by_cond, config.FIGURES))
        figure_paths.extend(plots.plot_occurrence_heatmap(occ, config.FIGURES))
        for us in sorted(occ["user_story_id"].unique()):
            figure_paths.extend(
                plots.plot_occurrence_heatmap(occ, config.FIGURES, user_story_id=us)
            )
        figure_paths.extend(plots.plot_repetition_stability(stability, config.FIGURES))
        figure_paths.extend(plots.plot_none_rate_by_condition(final_map, config.FIGURES))

    # Descriptive notes only (no confirmatory language)
    notes: list[str] = [config.PILOT_DISCLAIMER]
    if not rq1_global.empty:
        notes.append(
            f"No piloto, a condição C0 apresentou Gap Recall de "
            f"{format_rate(rq1_global.iloc[0]['gap_recall'])} "
            f"(unidade: ocorrências Gap×Run OPEN)."
        )
    for _, row in requery_by_cond.iterrows():
        if row["condition"] == "CT":
            notes.append(
                f"Em CT, a taxa de reconsulta (ANSWERED) foi "
                f"{format_rate(row['requery_rate'])}."
            )

    # Clustered bootstrap demo on C0 recall — likely skipped with 4 US
    c0 = matrix[(matrix["condition"] == "C0") & (matrix["gap_state"] == "OPEN")]
    boot = clustered_bootstrap_ci(
        c0["recognized"].to_numpy(dtype=float),
        c0["user_story_id"].to_numpy(),
        min_clusters_for_ci=10,
    )

    meta = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "analysis_seed": config.ANALYSIS_SEED,
        "versions": environment_versions(),
        "input_hashes": inputs.input_hashes(),
        "pilot_disclaimer": config.PILOT_DISCLAIMER,
        "clustered_bootstrap_c0_recall": boot,
        "inferential_models": exploratory_inferential_models_disabled(),
        "mixed_logit_future": fit_mixed_logit_recognized_future(matrix, enabled=False),
        "viability": viability,
        "dataset": desc,
        "question_count_warning": (
            "Menor quantidade de perguntas não significa necessariamente melhor clarificação."
        ),
    }

    return AnalysisArtifacts(
        inputs=inputs,
        final_map=final_map,
        question_gap_mapping=qgm,
        gap_run_matrix=matrix,
        tables=tables,
        figure_paths=figure_paths,
        meta=meta,
        descriptive_notes=notes,
    )


def main() -> int:
    try:
        art = run_pipeline()
    except AnalysisValidationError as exc:
        print(str(exc))
        return 1
    print("Analysis completed.")
    print(f"questions={len(art.final_map)} gap_run_rows={len(art.gap_run_matrix)}")
    print(f"tables={len(art.tables)} figures={len(art.figure_paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
