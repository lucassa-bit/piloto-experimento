"""Shared helpers for simplified question → Gap ID annotation (human-only)."""

from __future__ import annotations

import re
from typing import Iterable

SPECIAL_NONE = "NONE"
SPECIAL_REVIEW = "REVIEW"
SPECIALS = frozenset({SPECIAL_NONE, SPECIAL_REVIEW})

GAP_ID_RE = re.compile(r"^G\d{2}$")

SIMPLE_EVALUATOR_FIELDS = [
    "blind_item_id",
    "user_story_id",
    "question_text_raw",
    "mapped_gap_ids",
    "notes",
]

DISAGREEMENT_FIELDS = [
    "blind_item_id",
    "user_story_id",
    "question_text_raw",
    "evaluator_1_gap_ids",
    "evaluator_2_gap_ids",
    "final_gap_ids",
    "notes",
]

QUESTION_GAP_MAPPING_FIELDS = [
    "blind_item_id",
    "question_uid",
    "run_id",
    "user_story_id",
    "condition",
    "repetition",
    "question_text_raw",
    "mapped_gap_ids",
]

FORBIDDEN_EVALUATOR_COLUMNS = frozenset(
    {
        "question_uid",
        "run_id",
        "condition",
        "repetition",
        "question_order",
        "gap_state",
        "segment_id",
        "segment_text",
        "normalized_need",
        "mapping_status",
        "mapped_gap_id",
        "importance",
        "category",
    }
)


def gap_sort_key(gap_id: str) -> tuple[int, str]:
    m = re.fullmatch(r"G(\d+)", gap_id.strip())
    if not m:
        return (10**9, gap_id)
    return (int(m.group(1)), gap_id)


def parse_mapped_gap_ids(raw: str | None) -> tuple[str, ...]:
    text = (raw or "").strip()
    if not text:
        return tuple()
    return tuple(p.strip() for p in text.split(";") if p.strip())


def normalize_mapped_gap_ids(raw: str | None) -> str:
    """Structural normalize only (sort gaps; uppercase NONE/REVIEW). Raises on bad form."""
    tokens = list(parse_mapped_gap_ids(raw))
    if not tokens:
        return ""

    upper = [t.upper() if t.upper() in SPECIALS else t for t in tokens]
    specials_present = [t for t in upper if t in SPECIALS]
    gaps = [t for t in upper if t not in SPECIALS]

    if specials_present and gaps:
        raise ValueError(f"NONE/REVIEW cannot coexist with Gap IDs: {raw!r}")
    if len(specials_present) > 1:
        raise ValueError(f"multiple special tokens not allowed: {raw!r}")
    if len(specials_present) == 1:
        if len(upper) != 1:
            raise ValueError(f"NONE/REVIEW must stand alone: {raw!r}")
        return specials_present[0]

    for g in gaps:
        if not GAP_ID_RE.fullmatch(g):
            raise ValueError(f"invalid Gap ID token {g!r} in {raw!r}")
    if len(gaps) != len(set(gaps)):
        raise ValueError(f"duplicate Gap ID in {raw!r}")

    return ";".join(sorted(gaps, key=gap_sort_key))


def validate_against_us(normalized: str, *, allowed_gaps: Iterable[str]) -> list[str]:
    issues: list[str] = []
    if not normalized or normalized in SPECIALS:
        return issues
    allowed = set(allowed_gaps)
    for g in normalized.split(";"):
        if g not in allowed:
            issues.append(f"UNKNOWN_GAP:{g}")
    return issues
