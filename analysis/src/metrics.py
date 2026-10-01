"""Descriptive / exploratory metrics for the pilot analysis."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from analysis import config


def _rate(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def format_rate(rate: float | None, digits: int = 4) -> str:
    if rate is None:
        return "N/A"
    return f"{rate:.{digits}f}"


def gap_recall(
    matrix: pd.DataFrame,
    *,
    conditions: list[str] | None = None,
    gap_state: str = "OPEN",
    groupby: list[str] | None = None,
) -> pd.DataFrame:
    """
    GapRecall = recognized OPEN gaps / total OPEN gaps (same unit).

    Unit is whichever rows remain after filters — typically run-level
    Gap×Run occurrences. Returns N/A (null rate) when denominator is 0.
    """
    df = matrix.copy()
    if conditions is not None:
        df = df[df["condition"].isin(conditions)]
    df = df[df["gap_state"] == gap_state]

    groups = groupby or []
    if not groups:
        open_gaps = len(df)
        recognized = int(df["recognized"].sum())
        rate = _rate(recognized, open_gaps)
        return pd.DataFrame(
            [
                {
                    "open_gaps": open_gaps,
                    "recognized_open_gaps": recognized,
                    "gap_recall": rate,
                    "miss_rate": None if rate is None else 1.0 - rate,
                }
            ]
        )

    rows: list[dict[str, Any]] = []
    for keys, grp in df.groupby(groups, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        open_gaps = len(grp)
        recognized = int(grp["recognized"].sum())
        rate = _rate(recognized, open_gaps)
        row = dict(zip(groups, keys))
        row.update(
            {
                "open_gaps": open_gaps,
                "recognized_open_gaps": recognized,
                "gap_recall": rate,
                "miss_rate": None if rate is None else 1.0 - rate,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def miss_rate(
    matrix: pd.DataFrame,
    *,
    conditions: list[str] | None = None,
    gap_state: str = "OPEN",
    groupby: list[str] | None = None,
) -> pd.DataFrame:
    """MissRate = 1 - GapRecall on the same unit/set. Not an independent discovery."""
    return gap_recall(matrix, conditions=conditions, gap_state=gap_state, groupby=groupby)


def requery_rate(
    matrix: pd.DataFrame,
    *,
    conditions: list[str] | None = None,
    groupby: list[str] | None = None,
) -> pd.DataFrame:
    """
    RequeryRate = ANSWERED gaps with recognized=1 / total ANSWERED gaps.

    N/A when no ANSWERED gaps in the slice.
    """
    df = matrix.copy()
    if conditions is not None:
        df = df[df["condition"].isin(conditions)]
    df = df[df["gap_state"] == "ANSWERED"]

    groups = groupby or []
    if not groups:
        total = len(df)
        recognized = int(df["recognized"].sum())
        return pd.DataFrame(
            [
                {
                    "answered_gaps": total,
                    "requery_count": recognized,
                    "requery_rate": _rate(recognized, total),
                }
            ]
        )

    rows: list[dict[str, Any]] = []
    for keys, grp in df.groupby(groups, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        total = len(grp)
        recognized = int(grp["recognized"].sum())
        row = dict(zip(groups, keys))
        row.update(
            {
                "answered_gaps": total,
                "requery_count": recognized,
                "requery_rate": _rate(recognized, total),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def occurrence_rate(
    matrix: pd.DataFrame,
    *,
    expected_repetitions: int | None = None,
) -> pd.DataFrame:
    """
    OccurrenceRate for each user_story_id × gap_id × condition.

    Uses n_runs_observed / n_runs_expected derived from data (or expected_repetitions
    if provided). Does not hardcode 3.
    """
    df = matrix.copy()
    if expected_repetitions is None:
        # expected = max observed repetitions count per US×gap×condition key group size mode
        # Prefer distinct repetitions present in the matrix overall per condition slice
        per_key = (
            df.groupby(["user_story_id", "gap_id", "condition"], as_index=False)
            .agg(
                occurrences=("recognized", "sum"),
                repetitions=("repetition", "nunique"),
                gap_state=("gap_state", "first"),
            )
        )
        per_key["occurrence_rate"] = per_key["occurrences"] / per_key["repetitions"]
    else:
        per_key = (
            df.groupby(["user_story_id", "gap_id", "condition"], as_index=False)
            .agg(
                occurrences=("recognized", "sum"),
                gap_state=("gap_state", "first"),
            )
        )
        per_key["repetitions"] = int(expected_repetitions)
        per_key["occurrence_rate"] = per_key["occurrences"] / per_key["repetitions"]

    return per_key[
        [
            "user_story_id",
            "gap_id",
            "condition",
            "gap_state",
            "occurrences",
            "repetitions",
            "occurrence_rate",
        ]
    ]


def classify_repetition_stability(occurrence: pd.DataFrame) -> pd.DataFrame:
    """
    Descriptive labels for pilot frequencies (not universal categories).

    Uses occurrences/repetitions fractions.
    """
    out = occurrence.copy()

    def _label(row: pd.Series) -> str:
        reps = int(row["repetitions"])
        occ = int(row["occurrences"])
        if reps <= 0:
            return "undefined"
        # descriptive names for common pilot pattern; also work for other n
        if occ == 0:
            return "nunca reconhecido"
        if occ == reps:
            return "reconhecimento consistente"
        if occ == 1 and reps >= 3:
            return "reconhecimento raro"
        if occ == reps - 1 and reps >= 3:
            return "reconhecimento frequente"
        # generic fallback for arbitrary repetition counts
        frac = occ / reps
        if frac <= 1 / 3:
            return "reconhecimento raro"
        if frac < 1:
            return "reconhecimento frequente"
        return "reconhecimento consistente"

    out["stability_label"] = out.apply(_label, axis=1)
    out["label_note"] = "DESCRITIVO (piloto); não categoria universal"
    return out


def viability_metrics(
    final_map: pd.DataFrame,
    question_gap_mapping: pd.DataFrame,
) -> dict[str, Any]:
    """Method-viability diagnostics (not inter-rater reliability evidence)."""
    n = len(final_map)
    sources = final_map["mapping_source"].value_counts().to_dict()
    direct = int(sources.get(config.SOURCE_DIRECT, 0))
    adj = int(sources.get(config.SOURCE_ADJUDICATION, 0))

    # Per-question gap multiplicity from final_map
    def n_gaps(val: str) -> int:
        parts = [p for p in str(val).split(";") if p.strip()]
        return len(parts)

    counts = final_map["final_gap_ids"].map(n_gaps)
    is_none = final_map["final_gap_ids"].astype(str).str.strip() == config.SPECIAL_NONE
    has_prr = (~is_none) & (counts >= 1)
    multi = (~is_none) & (counts > 1)

    return {
        "n_questions": n,
        "direct_agreement": direct,
        "adjudicated": adj,
        "adjudication_burden": _rate(adj, n),
        "direct_agreement_rate": _rate(direct, n),
        "none_count": int(is_none.sum()),
        "none_rate": _rate(int(is_none.sum()), n),
        "multi_gap_count": int(multi.sum()),
        "multi_gap_rate": _rate(int(multi.sum()), n),
        "prr_mapped_count": int(has_prr.sum()),
        "prr_mapped_rate": _rate(int(has_prr.sum()), n),
        "note": (
            "Divergência reportada apenas como diagnóstico do procedimento de anotação. "
            "Não usar Cohen's kappa como evidência de confiabilidade interavaliadores neste "
            "piloto (Avaliador 2 assistivo/ChatGPT)."
        ),
    }


def questions_summary_stats(counts: pd.Series) -> dict[str, float]:
    arr = counts.astype(float)
    q1, q3 = np.percentile(arr, [25, 75]) if len(arr) else (np.nan, np.nan)
    return {
        "mean": float(arr.mean()) if len(arr) else float("nan"),
        "median": float(arr.median()) if len(arr) else float("nan"),
        "std": float(arr.std(ddof=1)) if len(arr) > 1 else float("nan"),
        "min": float(arr.min()) if len(arr) else float("nan"),
        "max": float(arr.max()) if len(arr) else float("nan"),
        "iqr": float(q3 - q1) if len(arr) else float("nan"),
    }


def dataset_description(
    *,
    questions: pd.DataFrame,
    prr_reference: pd.DataFrame,
    run_summary: pd.DataFrame,
) -> dict[str, Any]:
    gaps = prr_reference.drop_duplicates(["user_story_id", "gap_id"])
    cat_col = "gap_category" if "gap_category" in gaps.columns else "category"
    imp_col = "importance" if "importance" in gaps.columns else None

    desc: dict[str, Any] = {
        "n_user_stories": int(gaps["user_story_id"].nunique()),
        "n_gaps": len(gaps),
        "gaps_by_user_story": gaps.groupby("user_story_id").size().to_dict(),
        "n_runs": int(run_summary["run_id"].nunique()),
        "n_questions": len(questions),
        "questions_by_user_story": questions.groupby("user_story_id").size().to_dict(),
        "questions_by_condition": questions.groupby("condition").size().to_dict(),
        "questions_by_repetition": questions.groupby("repetition").size().to_dict(),
    }
    if cat_col in gaps.columns:
        desc["gaps_by_category"] = gaps.groupby(cat_col).size().to_dict()
    if imp_col:
        desc["gaps_by_importance"] = gaps.groupby(imp_col).size().to_dict()
    return desc
