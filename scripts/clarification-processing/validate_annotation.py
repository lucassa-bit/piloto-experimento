"""Validate filled evaluator annotation sheets (P5.1).

Reports structural/consistency issues. Does NOT auto-correct.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.io import export_csv, import_csv  # noqa: E402
from lib.paths import annotation_dir, get_root, prr_reference_blind_csv_path  # noqa: E402

VALID_STATUS = {"MATCH", "NO_REFERENCE_GAP", "REVIEW_REQUIRED"}

ISSUE_FIELDS = [
    "severity",
    "blind_item_id",
    "segment_id",
    "issue_code",
    "detail",
]


def _norm(value: str | None) -> str:
    return (value or "").strip()


def validate_sheet(
    rows: list[dict[str, str]],
    *,
    crosswalk: dict[str, dict[str, str]],
    gaps_by_us: dict[str, set[str]],
    expected_ids: set[str] | None = None,
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []

    def add(
        *,
        severity: str,
        blind_item_id: str,
        segment_id: str,
        issue_code: str,
        detail: str,
    ) -> None:
        issues.append(
            {
                "severity": severity,
                "blind_item_id": blind_item_id,
                "segment_id": segment_id,
                "issue_code": issue_code,
                "detail": detail,
            }
        )

    seen_ids = {_norm(r.get("blind_item_id")) for r in rows}
    if expected_ids is not None:
        missing = sorted(expected_ids - seen_ids)
        extra = sorted(seen_ids - expected_ids)
        for bid in missing:
            add(
                severity="error",
                blind_item_id=bid,
                segment_id="",
                issue_code="MISSING_BLIND_ITEM",
                detail="expected blind_item_id absent from sheet",
            )
        for bid in extra:
            add(
                severity="error",
                blind_item_id=bid,
                segment_id="",
                issue_code="UNKNOWN_BLIND_ITEM_ID",
                detail="blind_item_id not in expected set / crosswalk",
            )

    # Duplicate segment_id within the same blind item
    by_item: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_item[_norm(row.get("blind_item_id"))].append(row)

    for bid, item_rows in by_item.items():
        if bid and bid not in crosswalk:
            add(
                severity="error",
                blind_item_id=bid,
                segment_id="",
                issue_code="UNKNOWN_BLIND_ITEM_ID",
                detail="not present in blind-id-map.csv",
            )
            continue

        seg_ids = [_norm(r.get("segment_id")) for r in item_rows]
        # Multiple rows with empty segment_id = duplicate unsegmented rows
        counts: dict[str, int] = defaultdict(int)
        for sid in seg_ids:
            counts[sid] += 1
        for sid, n in counts.items():
            if n > 1:
                add(
                    severity="error",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="DUPLICATE_SEGMENT_ID",
                    detail=f"segment_id appears {n} times for this item",
                )

        # If any segment_id is non-empty, all rows for the item should be segmented
        non_empty = [s for s in seg_ids if s]
        if non_empty and any(s == "" for s in seg_ids):
            add(
                severity="error",
                blind_item_id=bid,
                segment_id="",
                issue_code="MIXED_SEGMENTATION",
                detail="item mixes empty and non-empty segment_id rows",
            )

        expected_text = crosswalk.get(bid, {}).get("question_text_raw", "")
        us = crosswalk.get(bid, {}).get("user_story_id", "")

        for row in item_rows:
            sid = _norm(row.get("segment_id"))
            status = _norm(row.get("mapping_status"))
            gap = _norm(row.get("mapped_gap_id"))
            need = _norm(row.get("normalized_need"))
            seg_text = _norm(row.get("segment_text"))
            raw = row.get("question_text_raw", "")
            row_us = _norm(row.get("user_story_id"))

            if expected_text and raw != expected_text:
                add(
                    severity="error",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="QUESTION_TEXT_ALTERED",
                    detail="question_text_raw differs from blind-id-map",
                )

            if us and row_us and row_us != us:
                add(
                    severity="error",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="USER_STORY_MISMATCH",
                    detail=f"sheet US={row_us} map US={us}",
                )

            if sid and not seg_text:
                add(
                    severity="error",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="EMPTY_SEGMENT_TEXT",
                    detail="segment_id set but segment_text empty",
                )

            if not status and not need and not gap and not seg_text and not _norm(row.get("notes")):
                # untouched row — ok for incomplete sheets
                continue

            if status and status not in VALID_STATUS:
                add(
                    severity="error",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="INVALID_MAPPING_STATUS",
                    detail=f"unexpected status {status!r}",
                )

            if status and not need:
                add(
                    severity="error",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="EMPTY_NORMALIZED_NEED",
                    detail="mapping_status set but normalized_need empty",
                )

            if status == "MATCH" and not gap:
                add(
                    severity="error",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="MATCH_WITHOUT_GAP",
                    detail="MATCH requires mapped_gap_id",
                )

            if status == "NO_REFERENCE_GAP" and gap:
                add(
                    severity="error",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="NO_REFERENCE_GAP_WITH_GAP",
                    detail="NO_REFERENCE_GAP must leave mapped_gap_id empty",
                )

            if status == "REVIEW_REQUIRED" and gap:
                add(
                    severity="error",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="REVIEW_REQUIRED_INCONSISTENT",
                    detail="REVIEW_REQUIRED must leave mapped_gap_id empty (use notes for candidates)",
                )

            if gap:
                allowed = gaps_by_us.get(row_us or us, set())
                if gap not in allowed:
                    add(
                        severity="error",
                        blind_item_id=bid,
                        segment_id=sid,
                        issue_code="UNKNOWN_GAP_FOR_US",
                        detail=f"{gap} not in PRR gaps for {row_us or us}",
                    )

            if need and not status:
                add(
                    severity="warning",
                    blind_item_id=bid,
                    segment_id=sid,
                    issue_code="NEED_WITHOUT_STATUS",
                    detail="normalized_need filled without mapping_status",
                )

    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate evaluator annotation CSV")
    parser.add_argument("sheet", type=Path, help="Path to evaluator CSV")
    parser.add_argument(
        "--expected-from",
        type=Path,
        default=None,
        help="CSV whose blind_item_id set defines the expected items "
        "(default: all ids in blind-id-map, or calibration-set if name contains calibration)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional issues CSV path",
    )
    args = parser.parse_args(argv)
    try:
        get_root()
        ann = annotation_dir()
        crosswalk_rows = import_csv(ann / "blind-id-map.csv")
        crosswalk = {r["blind_item_id"]: r for r in crosswalk_rows}

        prr_rows = import_csv(prr_reference_blind_csv_path())
        gaps_by_us: dict[str, set[str]] = defaultdict(set)
        for r in prr_rows:
            gaps_by_us[r["user_story_id"]].add(r["gap_id"])

        sheet_rows = import_csv(args.sheet)

        expected: set[str] | None
        if args.expected_from:
            expected = {
                _norm(r.get("blind_item_id"))
                for r in import_csv(args.expected_from)
                if _norm(r.get("blind_item_id"))
            }
        elif "calibration" in args.sheet.name:
            cal = import_csv(ann / "calibration-set.csv")
            expected = {_norm(r.get("blind_item_id")) for r in cal}
        else:
            expected = set(crosswalk)

        issues = validate_sheet(
            sheet_rows,
            crosswalk=crosswalk,
            gaps_by_us=gaps_by_us,
            expected_ids=expected,
        )
        out = args.out
        if out is None:
            out = args.sheet.with_name(args.sheet.stem + "-validation-issues.csv")
        export_csv(out, issues, fieldnames=ISSUE_FIELDS)

        errors = sum(1 for i in issues if i["severity"] == "error")
        warnings = sum(1 for i in issues if i["severity"] == "warning")
        print(f"Validated: {args.sheet}")
        print(f"Issues: {len(issues)} (errors={errors}, warnings={warnings})")
        print(f"Report: {out}")
        return 1 if errors else 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
