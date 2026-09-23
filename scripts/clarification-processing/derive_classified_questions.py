"""Derive classified-questions.csv AFTER human mapping is filled.

gap_state is looked up mechanically from PRR states:
  (user_story_id, condition, mapped_gap_id) -> OPEN|ANSWERED

Does not invent mappings. Refuses if mapping columns are empty.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.io import export_csv, import_csv  # noqa: E402
from lib.paths import (  # noqa: E402
    annotation_base_csv_path,
    classified_questions_csv_path,
    get_root,
    prr_gap_states_csv_path,
    prr_reference_csv_path,
)

from build_classification_base import CLASSIFIED_FIELDS, MAPPING_STATUS_VALUES  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Derive classified questions from completed human annotation"
    )
    parser.add_argument(
        "--annotation",
        type=Path,
        default=None,
        help="Annotation CSV with mappings (default: annotation-base.csv)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path (default: collected-data/classified-questions.csv)",
    )
    args = parser.parse_args(argv)
    try:
        get_root()
        ann_path = args.annotation or annotation_base_csv_path()
        rows = import_csv(ann_path)
        filled = [
            r
            for r in rows
            if (r.get("mapping_status") or "").strip()
            or (r.get("mapped_gap_id") or "").strip()
        ]
        if not filled:
            print(
                "No human mappings found yet. "
                "Fill mapped_gap_id / mapping_status before deriving.",
                file=sys.stderr,
            )
            return 2

        ref = {
            (r["user_story_id"], r["gap_id"]): r
            for r in import_csv(prr_reference_csv_path())
        }
        states = {
            (r["user_story_id"], r["gap_id"], r["condition"]): r["gap_state"]
            for r in import_csv(prr_gap_states_csv_path())
        }

        out_rows: list[dict[str, object]] = []
        for r in rows:
            status = (r.get("mapping_status") or "").strip()
            gap_id = (r.get("mapped_gap_id") or "").strip()
            if status and status not in MAPPING_STATUS_VALUES:
                raise ValueError(f"invalid mapping_status {status!r} for {r['question_uid']}")

            importance = ""
            gap_category = ""
            gap_state = ""
            if status == "MATCH":
                if not gap_id:
                    raise ValueError(f"MATCH requires mapped_gap_id: {r['question_uid']}")
                key = (r["user_story_id"], gap_id)
                if key not in ref:
                    raise ValueError(f"unknown gap {gap_id} for {r['user_story_id']}")
                importance = ref[key]["importance"]
                gap_category = ref[key]["category"]
                state_key = (r["user_story_id"], gap_id, r["condition"])
                if state_key not in states:
                    raise ValueError(f"missing PRR state for {state_key}")
                gap_state = states[state_key]
            elif status == "NO_REFERENCE_GAP":
                if gap_id:
                    raise ValueError(
                        f"NO_REFERENCE_GAP must not set mapped_gap_id: {r['question_uid']}"
                    )
            # REVIEW_REQUIRED / empty: leave gap fields blank

            out_rows.append(
                {
                    "question_uid": r["question_uid"],
                    "run_id": r["run_id"],
                    "user_story_id": r["user_story_id"],
                    "condition": r["condition"],
                    "repetition": r["repetition"],
                    "question_order": r["question_order"],
                    "question_text_raw": r["question_text_raw"],
                    "normalized_need": r.get("normalized_need", ""),
                    "mapped_gap_id": gap_id,
                    "mapping_status": status,
                    "importance": importance,
                    "gap_category": gap_category,
                    "gap_state": gap_state,
                }
            )

        out = args.out or classified_questions_csv_path()
        export_csv(out, out_rows, fieldnames=CLASSIFIED_FIELDS)
        print(f"Wrote {out} ({len(out_rows)} rows)")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
