"""Final question→gap mapping from human annotation (no semantic inference)."""

from __future__ import annotations

import pandas as pd

from analysis import config
from analysis.src.validation import AnalysisValidationError, validate_final_mapping


def normalize_gap_ids(value: str | None) -> str:
    """Normalize semicolon-separated gap ids; preserve NONE alone; sort multi-gaps canonically."""
    raw = (value or "").strip()
    if not raw:
        return ""
    # tolerate accidental commas from spreadsheets
    raw = raw.replace(",", ";")
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    if not parts:
        return ""
    # Excel / pandas sometimes stringify missing as "nan"
    parts = [p for p in parts if p.lower() != "nan"]
    if not parts:
        return ""
    if config.SPECIAL_NONE in parts:
        if len(parts) == 1:
            return config.SPECIAL_NONE
        # keep as-is for validation to catch; do not auto-fix
        return ";".join(parts)
    # Canonical order so G03;G04 == G04;G03 (same set)
    return ";".join(sorted(set(parts)))


def gap_id_set(value: str | None) -> frozenset[str]:
    norm = normalize_gap_ids(value)
    if not norm:
        return frozenset()
    return frozenset(norm.split(";"))


def build_final_mapping(
    *,
    blind_id_map: pd.DataFrame,
    evaluator_1: pd.DataFrame,
    evaluator_2: pd.DataFrame,
    disagreements: pd.DataFrame,
    prr_reference: pd.DataFrame,
    validate: bool = True,
    pilot_asserts: bool = True,
) -> pd.DataFrame:
    """
    Build one row per blind_item_id with final_gap_ids and mapping_source.

    Rule:
      - If Evaluator-1 == Evaluator-2 (after normalize): DIRECT_AGREEMENT
      - Else: exclusively final_gap_ids from human adjudication (disagreements)
    Never auto-pick between evaluators.
    """
    e1 = evaluator_1[["blind_item_id", "mapped_gap_ids"]].copy()
    e1 = e1.rename(columns={"mapped_gap_ids": "e1_mapped"})
    e2 = evaluator_2[["blind_item_id", "mapped_gap_ids"]].copy()
    e2 = e2.rename(columns={"mapped_gap_ids": "e2_mapped"})

    base_cols = [
        c
        for c in [
            "blind_item_id",
            "question_uid",
            "run_id",
            "user_story_id",
            "condition",
            "repetition",
            "question_order",
            "question_text_raw",
        ]
        if c in blind_id_map.columns
    ]
    base = blind_id_map[base_cols].copy()
    merged = base.merge(e1, on="blind_item_id", how="left").merge(e2, on="blind_item_id", how="left")

    merged["e1_norm"] = merged["e1_mapped"].map(normalize_gap_ids)
    merged["e2_norm"] = merged["e2_mapped"].map(normalize_gap_ids)

    adj = disagreements.copy()
    if not adj.empty and "blind_item_id" in adj.columns:
        adj_cols = ["blind_item_id"]
        if "final_gap_ids" in adj.columns:
            adj_cols.append("final_gap_ids")
        adj = adj[adj_cols].drop_duplicates("blind_item_id", keep="last")
        adj = adj.rename(columns={"final_gap_ids": "adjudicated_gap_ids"})
        merged = merged.merge(adj, on="blind_item_id", how="left")
    else:
        merged["adjudicated_gap_ids"] = ""

    final_ids: list[str] = []
    sources: list[str] = []
    errors: list[str] = []

    for row in merged.itertuples(index=False):
        e1n = str(getattr(row, "e1_norm") or "")
        e2n = str(getattr(row, "e2_norm") or "")
        bid = getattr(row, "blind_item_id")

        if not e1n or not e2n:
            errors.append(f"{bid}: incomplete evaluator mapping (E1/E2 empty)")
            final_ids.append("")
            sources.append("")
            continue

        if e1n == e2n:
            final_ids.append(e1n)
            sources.append(config.SOURCE_DIRECT)
            continue

        adj_val = normalize_gap_ids(str(getattr(row, "adjudicated_gap_ids") or ""))
        if not adj_val:
            errors.append(
                f"{bid}: evaluators diverge ({e1n!r} vs {e2n!r}) but adjudication final_gap_ids is empty"
            )
            final_ids.append("")
            sources.append("")
            continue
        final_ids.append(adj_val)
        sources.append(config.SOURCE_ADJUDICATION)

    merged["final_gap_ids"] = final_ids
    merged["mapping_source"] = sources

    out = merged[
        [
            c
            for c in [
                "blind_item_id",
                "question_uid",
                "run_id",
                "user_story_id",
                "condition",
                "repetition",
                "question_order",
                "question_text_raw",
                "e1_mapped",
                "e2_mapped",
                "final_gap_ids",
                "mapping_source",
            ]
            if c in merged.columns
        ]
    ].copy()

    if errors:
        n = len(errors)
        if n > 20:
            head = errors[:10]
            raise AnalysisValidationError(
                head
                + [
                    f"... and {n - 10} more mapping errors",
                    (
                        "Annotation incomplete or adjudication missing. "
                        "Fill evaluator mapped_gap_ids and disagreements.final_gap_ids "
                        "before running analysis. Do not invent mappings automatically."
                    ),
                ]
            )
        raise AnalysisValidationError(errors)

    if validate:
        result = validate_final_mapping(out, prr_reference, pilot_asserts=pilot_asserts)
        result.raise_if_failed()

    return out


def explode_question_gap_mapping(final_map: pd.DataFrame) -> pd.DataFrame:
    """
    One row per question × mapped gap.

    NONE is preserved as mapped_gap_id = NONE (single row).
    Multi-gap (G03;G07) → two rows.
    """
    rows: list[dict] = []
    for row in final_map.itertuples(index=False):
        ids = [p.strip() for p in str(getattr(row, "final_gap_ids")).split(";") if p.strip()]
        if not ids:
            continue
        for gid in ids:
            rows.append(
                {
                    "blind_item_id": getattr(row, "blind_item_id"),
                    "question_uid": getattr(row, "question_uid", ""),
                    "run_id": getattr(row, "run_id"),
                    "user_story_id": getattr(row, "user_story_id"),
                    "condition": getattr(row, "condition"),
                    "repetition": getattr(row, "repetition"),
                    "question_order": getattr(row, "question_order"),
                    "question_text_raw": getattr(row, "question_text_raw", ""),
                    "mapped_gap_id": gid,
                    "mapping_source": getattr(row, "mapping_source"),
                }
            )
    return pd.DataFrame(rows)
