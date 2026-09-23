"""Compare independent evaluator annotation sheets.

Reports agreement metrics and lists disagreements.
Does NOT resolve disagreements or alter evaluator files.

Supports P5.1 opaque keys: blind_item_id (+ segment_id).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.io import export_csv, import_csv  # noqa: E402
from lib.paths import annotation_dir, get_root  # noqa: E402

DISAGREE_FIELDS = [
    "blind_item_id",
    "segment_id",
    "question_text_raw",
    "normalized_need_evaluator_1",
    "normalized_need_evaluator_2",
    "mapped_gap_evaluator_1",
    "mapped_gap_evaluator_2",
    "mapping_status_evaluator_1",
    "mapping_status_evaluator_2",
    "disagree_fields",
]


def _norm(value: str | None) -> str:
    return (value or "").strip()


def item_id(row: dict[str, str]) -> str:
    """Prefer blind_item_id (P5.1); fall back to legacy question_uid."""
    bid = _norm(row.get("blind_item_id"))
    if bid:
        return bid
    return _norm(row.get("question_uid"))


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return (item_id(row), _norm(row.get("segment_id")))


def group_by_item(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[item_id(row)].append(row)
    for iid in grouped:
        grouped[iid].sort(
            key=lambda r: (_norm(r.get("segment_id")), r.get("segment_text", ""))
        )
    return grouped


def segmentation_signature(rows: list[dict[str, str]]) -> tuple[str, ...]:
    segs = [_norm(r.get("segment_id")) for r in rows]
    if segs == [""]:
        return ("",)
    return tuple(sorted(segs))


def is_annotated(row: dict[str, str]) -> bool:
    return bool(
        _norm(row.get("normalized_need"))
        or _norm(row.get("mapped_gap_id"))
        or _norm(row.get("mapping_status"))
        or _norm(row.get("segment_text"))
        or _norm(row.get("notes"))
    )


def cohens_kappa(pairs: Iterable[tuple[str, str]]) -> float | None:
    items = [(a, b) for a, b in pairs if a != "" and b != ""]
    n = len(items)
    if n == 0:
        return None
    labels = sorted({x for pair in items for x in pair})
    if len(labels) == 1:
        return 1.0 if all(a == b for a, b in items) else 0.0
    agree = sum(1 for a, b in items if a == b)
    po = agree / n
    count1 = Counter(a for a, _ in items)
    count2 = Counter(b for _, b in items)
    pe = sum((count1[l] / n) * (count2[l] / n) for l in labels)
    if abs(1.0 - pe) < 1e-12:
        return None
    return (po - pe) / (1.0 - pe)


def index_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    indexed: dict[tuple[str, str], dict[str, str]] = {}
    for row in rows:
        key = row_key(row)
        if key in indexed:
            raise RuntimeError(f"duplicate key in evaluator sheet: {key}")
        indexed[key] = row
    return indexed


def compare(
    e1_rows: list[dict[str, str]],
    e2_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    g1 = group_by_item(e1_rows)
    g2 = group_by_item(e2_rows)
    ids = sorted(set(g1) | set(g2))
    if set(g1) != set(g2):
        only2 = sorted(set(g2) - set(g1))
        only1 = sorted(set(g1) - set(g2))
        raise RuntimeError(
            f"blind_item_id sets differ; only in e2={only2[:5]} only in e1={only1[:5]}"
        )

    seg_agree = 0
    for iid in ids:
        if segmentation_signature(g1[iid]) == segmentation_signature(g2[iid]):
            seg_agree += 1
    seg_rate = seg_agree / len(ids) if ids else 0.0

    idx1 = index_rows(e1_rows)
    idx2 = index_rows(e2_rows)
    all_keys = sorted(set(idx1) | set(idx2))

    disagreements: list[dict[str, object]] = []
    status_pairs: list[tuple[str, str]] = []
    gap_pairs: list[tuple[str, str]] = []
    status_agree = 0
    status_compared = 0
    gap_agree = 0
    gap_compared = 0

    for key in all_keys:
        a = idx1.get(key)
        b = idx2.get(key)
        if a is None or b is None:
            present = a or b
            assert present is not None
            other_empty = {
                "normalized_need": "",
                "mapped_gap_id": "",
                "mapping_status": "",
                "question_text_raw": present.get("question_text_raw", ""),
            }
            left = a if a is not None else other_empty
            right = b if b is not None else other_empty
            disagreements.append(
                {
                    "blind_item_id": key[0],
                    "segment_id": key[1],
                    "question_text_raw": present.get("question_text_raw", ""),
                    "normalized_need_evaluator_1": _norm(left.get("normalized_need")),
                    "normalized_need_evaluator_2": _norm(right.get("normalized_need")),
                    "mapped_gap_evaluator_1": _norm(left.get("mapped_gap_id")),
                    "mapped_gap_evaluator_2": _norm(right.get("mapped_gap_id")),
                    "mapping_status_evaluator_1": _norm(left.get("mapping_status")),
                    "mapping_status_evaluator_2": _norm(right.get("mapping_status")),
                    "disagree_fields": "segment_presence",
                }
            )
            continue

        fields_diff: list[str] = []
        n1, n2 = _norm(a.get("normalized_need")), _norm(b.get("normalized_need"))
        g1v, g2v = _norm(a.get("mapped_gap_id")), _norm(b.get("mapped_gap_id"))
        s1, s2 = _norm(a.get("mapping_status")), _norm(b.get("mapping_status"))

        if n1 != n2:
            fields_diff.append("normalized_need")
        if g1v != g2v:
            fields_diff.append("mapped_gap_id")
        if s1 != s2:
            fields_diff.append("mapping_status")
        if _norm(a.get("segment_text")) != _norm(b.get("segment_text")):
            fields_diff.append("segment_text")

        if s1 or s2:
            status_compared += 1
            status_pairs.append((s1, s2))
            if s1 == s2 and s1 != "":
                status_agree += 1
        if g1v or g2v:
            gap_compared += 1
            gap_pairs.append((g1v, g2v))
            if g1v == g2v and g1v != "":
                gap_agree += 1

        if fields_diff:
            disagreements.append(
                {
                    "blind_item_id": key[0],
                    "segment_id": key[1],
                    "question_text_raw": a.get("question_text_raw")
                    or b.get("question_text_raw")
                    or "",
                    "normalized_need_evaluator_1": n1,
                    "normalized_need_evaluator_2": n2,
                    "mapped_gap_evaluator_1": g1v,
                    "mapped_gap_evaluator_2": g2v,
                    "mapping_status_evaluator_1": s1,
                    "mapping_status_evaluator_2": s2,
                    "disagree_fields": "|".join(fields_diff),
                }
            )

    summary: dict[str, object] = {
        "items": len(ids),
        "segments_evaluator_1": len(e1_rows),
        "segments_evaluator_2": len(e2_rows),
        "annotated_items_evaluator_1": sum(
            1 for iid, rows in g1.items() if any(is_annotated(r) for r in rows)
        ),
        "annotated_items_evaluator_2": sum(
            1 for iid, rows in g2.items() if any(is_annotated(r) for r in rows)
        ),
        "annotated_segments_evaluator_1": sum(1 for r in e1_rows if is_annotated(r)),
        "annotated_segments_evaluator_2": sum(1 for r in e2_rows if is_annotated(r)),
        "segmentation_agreement_count": seg_agree,
        "segmentation_agreement_rate": round(seg_rate, 4),
        "mapping_status_pairs_compared": status_compared,
        "mapping_status_exact_agreement_count": status_agree,
        "mapping_status_exact_agreement_rate": (
            round(status_agree / status_compared, 4) if status_compared else None
        ),
        "mapping_status_cohens_kappa": (
            None
            if cohens_kappa(status_pairs) is None
            else round(float(cohens_kappa(status_pairs)), 4)
        ),
        "mapped_gap_id_pairs_compared": gap_compared,
        "mapped_gap_id_exact_agreement_count": gap_agree,
        "mapped_gap_id_exact_agreement_rate": (
            round(gap_agree / gap_compared, 4) if gap_compared else None
        ),
        "mapped_gap_id_cohens_kappa": (
            None
            if cohens_kappa(gap_pairs) is None
            else round(float(cohens_kappa(gap_pairs)), 4)
        ),
        "disagreement_rows": len(disagreements),
        "scope_note": (
            "If comparing calibration sheets, metrics are diagnostic only "
            "(not final study reliability)."
        ),
    }
    return disagreements, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare evaluator annotation sheets")
    parser.add_argument("--e1", type=Path, default=None)
    parser.add_argument("--e2", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--summary-json", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        get_root()
        ann = annotation_dir()
        e1_path = args.e1 or (ann / "evaluator-1.csv")
        e2_path = args.e2 or (ann / "evaluator-2.csv")
        if not e1_path.is_file() or not e2_path.is_file():
            raise FileNotFoundError(f"missing evaluator sheets: {e1_path} / {e2_path}")

        disagreements, summary = compare(import_csv(e1_path), import_csv(e2_path))
        out = args.out or (ann / "disagreements.csv")
        export_csv(out, disagreements, fieldnames=DISAGREE_FIELDS)

        if args.summary_json:
            args.summary_json.write_text(
                json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        print("Agreement summary:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        print(f"Disagreements written: {out} ({len(disagreements)} rows)")
        print("Note: disagreements are listed only; nothing was auto-resolved.")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
