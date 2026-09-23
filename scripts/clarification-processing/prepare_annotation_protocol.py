"""P5: annotation protocol prep (manual companion artifacts).

- prr-reference-blind.csv (no importance/category)
- calibration-set.csv (~30 uids, stratified, deterministic)
- calibration-evaluator-{1,2}.csv
- refresh evaluator sheets with segment_text column (mappings stay empty)

Does NOT modify questions.csv, PRR xlsx, or fill mappings.
Does NOT run derive_classified_questions.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.io import export_csv, import_csv  # noqa: E402
from lib.paths import (  # noqa: E402
    annotation_base_csv_path,
    annotation_blind_csv_path,
    annotation_dir,
    get_root,
    prr_reference_blind_csv_path,
    prr_reference_csv_path,
)
from lib.runs import USER_STORY_IDS  # noqa: E402

# Evaluator / blind working schema (P5 adds segment_text).
EVALUATOR_FIELDS = [
    "question_uid",
    "user_story_id",
    "question_text_raw",
    "segment_id",
    "segment_text",
    "normalized_need",
    "mapped_gap_id",
    "mapping_status",
    "notes",
]

PRR_BLIND_FIELDS = [
    "user_story_id",
    "gap_id",
    "gap_text",
    "reference_information",
]

CALIBRATION_SET_FIELDS = [
    "calibration_index",
    "question_uid",
    "user_story_id",
    "question_text_raw",
]

# ~30 items, stratified by US, no condition/outcome bias.
# Totals: 8+7+7+8 = 30. Allocation favors larger US pools slightly
# without reading experimental condition (blind sheet has no condition).
CALIBRATION_ALLOCATION = {
    "US02": 8,
    "US08": 7,
    "US18": 7,
    "US25": 8,
}


def evenly_spaced_indices(n: int, k: int) -> list[int]:
    """Deterministic subsample: k indices in [0, n) evenly spaced."""
    if k <= 0:
        return []
    if k > n:
        raise ValueError(f"cannot sample {k} from {n}")
    if k == 1:
        return [0]
    return [int(i * (n - 1) / (k - 1)) for i in range(k)]


def select_calibration(
    blind_rows: list[dict[str, str]],
    allocation: dict[str, int] = CALIBRATION_ALLOCATION,
) -> list[dict[str, object]]:
    by_us: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in blind_rows:
        by_us[row["user_story_id"]].append(row)
    selected: list[dict[str, object]] = []
    for us in USER_STORY_IDS:
        pool = sorted(by_us[us], key=lambda r: r["question_uid"])
        k = allocation[us]
        for idx in evenly_spaced_indices(len(pool), k):
            r = pool[idx]
            selected.append(
                {
                    "question_uid": r["question_uid"],
                    "user_story_id": r["user_story_id"],
                    "question_text_raw": r["question_text_raw"],
                }
            )
    selected.sort(key=lambda r: str(r["question_uid"]))
    out: list[dict[str, object]] = []
    for i, row in enumerate(selected, start=1):
        out.append(
            {
                "calibration_index": i,
                "question_uid": row["question_uid"],
                "user_story_id": row["user_story_id"],
                "question_text_raw": row["question_text_raw"],
            }
        )
    return out


def to_evaluator_rows(source_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """One row per original question; annotation fields empty."""
    rows: list[dict[str, object]] = []
    for r in source_rows:
        rows.append(
            {
                "question_uid": r["question_uid"],
                "user_story_id": r["user_story_id"],
                "question_text_raw": r["question_text_raw"],
                "segment_id": "",
                "segment_text": "",
                "normalized_need": "",
                "mapped_gap_id": "",
                "mapping_status": "",
                "notes": "",
            }
        )
    return rows


def build_prr_blind(prr_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "user_story_id": r["user_story_id"],
            "gap_id": r["gap_id"],
            "gap_text": r["gap_text"],
            "reference_information": r["reference_information"],
        }
        for r in prr_rows
    ]


def assert_empty_mappings(rows: list[dict[str, object]], label: str) -> None:
    for field in ("normalized_need", "mapped_gap_id", "mapping_status"):
        if any(str(r.get(field) or "").strip() for r in rows):
            raise RuntimeError(f"{label}: unexpected non-empty {field}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P5 annotation protocol preparation")
    parser.parse_args(argv)
    try:
        get_root()
        blind_path = annotation_blind_csv_path()
        base_path = annotation_base_csv_path()
        prr_path = prr_reference_csv_path()

        blind_rows = import_csv(blind_path)
        base_rows = import_csv(base_path)
        prr_rows = import_csv(prr_path)

        if len(blind_rows) != 269:
            raise RuntimeError(f"annotation-blind expected 269, got {len(blind_rows)}")
        if len(base_rows) != 269:
            raise RuntimeError(f"annotation-base expected 269, got {len(base_rows)}")

        # Refresh blind sheet with segment_text column (no mapping fill).
        blind_eval = to_evaluator_rows(blind_rows)
        assert_empty_mappings(blind_eval, "blind")
        export_csv(blind_path, blind_eval, fieldnames=EVALUATOR_FIELDS)

        # Keep annotation-base schema compatible: add segment_text empty.
        base_fields = [
            "question_uid",
            "run_id",
            "user_story_id",
            "condition",
            "repetition",
            "attempt",
            "question_order",
            "question_text_raw",
            "segment_id",
            "segment_text",
            "normalized_need",
            "mapped_gap_id",
            "mapping_status",
            "notes",
        ]
        base_out: list[dict[str, object]] = []
        for r in base_rows:
            base_out.append(
                {
                    "question_uid": r["question_uid"],
                    "run_id": r["run_id"],
                    "user_story_id": r["user_story_id"],
                    "condition": r["condition"],
                    "repetition": r["repetition"],
                    "attempt": r["attempt"],
                    "question_order": r["question_order"],
                    "question_text_raw": r["question_text_raw"],
                    "segment_id": r.get("segment_id", ""),
                    "segment_text": "",
                    "normalized_need": "",
                    "mapped_gap_id": "",
                    "mapping_status": "",
                    "notes": "",
                }
            )
        assert_empty_mappings(base_out, "annotation-base")
        export_csv(base_path, base_out, fieldnames=base_fields)

        prr_blind = build_prr_blind(prr_rows)
        export_csv(prr_reference_blind_csv_path(), prr_blind, fieldnames=PRR_BLIND_FIELDS)

        calibration = select_calibration(blind_rows)
        if len(calibration) != 30:
            raise RuntimeError(f"calibration expected 30, got {len(calibration)}")
        ann = annotation_dir()
        ann.mkdir(parents=True, exist_ok=True)
        cal_set_path = ann / "calibration-set.csv"
        export_csv(cal_set_path, calibration, fieldnames=CALIBRATION_SET_FIELDS)

        cal_uids = {str(r["question_uid"]) for r in calibration}
        cal_source = [r for r in blind_rows if r["question_uid"] in cal_uids]
        cal_source.sort(key=lambda r: r["question_uid"])
        cal_eval = to_evaluator_rows(cal_source)
        assert_empty_mappings(cal_eval, "calibration")
        for name in ("calibration-evaluator-1.csv", "calibration-evaluator-2.csv"):
            export_csv(ann / name, cal_eval, fieldnames=EVALUATOR_FIELDS)

        full_eval = to_evaluator_rows(blind_rows)
        assert_empty_mappings(full_eval, "full evaluators")
        for name in ("evaluator-1.csv", "evaluator-2.csv"):
            export_csv(ann / name, full_eval, fieldnames=EVALUATOR_FIELDS)

        dist = Counter(str(r["user_story_id"]) for r in calibration)
        print("P5 annotation protocol prep OK")
        print(f"prr-reference-blind: {prr_reference_blind_csv_path()} ({len(prr_blind)})")
        print(f"calibration-set: {cal_set_path} ({len(calibration)})")
        print("calibration_by_us", dict(dist))
        print(f"calibration-evaluator-1/2: {ann}")
        print(f"evaluator-1/2 refreshed with segment_text ({len(full_eval)} rows)")
        print("EVALUATOR_FIELDS", EVALUATOR_FIELDS)
        print("allocation", CALIBRATION_ALLOCATION)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
