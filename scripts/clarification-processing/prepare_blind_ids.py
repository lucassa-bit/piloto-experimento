"""P5.1: opaque blind IDs + annotation presentation order.

Creates private crosswalk and regenerates evaluator sheets without
question_uid / condition / repetition leakage.

Does NOT modify questions.csv, PRR, or experimental run outputs.
Does NOT reselect the calibration set (same 30 question_uids).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.io import export_csv, import_csv  # noqa: E402
from lib.paths import (  # noqa: E402
    annotation_base_csv_path,
    annotation_dir,
    get_root,
    prr_reference_blind_csv_path,
)
from lib.runs import USER_STORY_IDS  # noqa: E402

# Exclusive to annotation presentation — never used in experimental runs.
ANNOTATION_ORDER_SEED = "piloto-annotation-order-v1-20260923"

CONDITION_TOKEN_RE = re.compile(r"\bC(?:0|L|O|D|S|T)\b")

EVALUATOR_FIELDS = [
    "blind_item_id",
    "user_story_id",
    "question_text_raw",
    "segment_id",
    "segment_text",
    "normalized_need",
    "mapped_gap_id",
    "mapping_status",
    "notes",
]

CROSSWALK_FIELDS = [
    "blind_item_id",
    "annotation_order",
    "question_uid",
    "run_id",
    "user_story_id",
    "condition",
    "repetition",
    "question_order",
    "question_text_raw",
]

CALIBRATION_SET_FIELDS = [
    "calibration_index",
    "blind_item_id",
    "question_uid",
    "user_story_id",
    "question_text_raw",
]


def seed_to_int(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def format_blind_id(n: int) -> str:
    return f"B{n:04d}"


def empty_evaluator_row(
    *,
    blind_item_id: str,
    user_story_id: str,
    question_text_raw: str,
) -> dict[str, object]:
    return {
        "blind_item_id": blind_item_id,
        "user_story_id": user_story_id,
        "question_text_raw": question_text_raw,
        "segment_id": "",
        "segment_text": "",
        "normalized_need": "",
        "mapped_gap_id": "",
        "mapping_status": "",
        "notes": "",
    }


def build_crosswalk(
    base_rows: list[dict[str, str]],
    *,
    seed: str,
) -> list[dict[str, object]]:
    by_us: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in base_rows:
        by_us[row["user_story_id"]].append(row)

    rng = random.Random(seed_to_int(seed))
    ordered: list[dict[str, str]] = []
    for us in USER_STORY_IDS:
        pool = list(by_us[us])
        # Stable pre-sort then shuffle → reproducible, not condition-ordered.
        pool.sort(key=lambda r: r["question_uid"])
        rng.shuffle(pool)
        ordered.extend(pool)

    if len(ordered) != len(base_rows):
        raise RuntimeError("crosswalk lost rows during shuffle")

    out: list[dict[str, object]] = []
    for i, row in enumerate(ordered, start=1):
        out.append(
            {
                "blind_item_id": format_blind_id(i),
                "annotation_order": i,
                "question_uid": row["question_uid"],
                "run_id": row["run_id"],
                "user_story_id": row["user_story_id"],
                "condition": row["condition"],
                "repetition": row["repetition"],
                "question_order": row["question_order"],
                "question_text_raw": row["question_text_raw"],
            }
        )
    return out


def assert_no_condition_leak_in_evaluator(rows: list[dict[str, object]], label: str) -> None:
    for row in rows:
        bid = str(row["blind_item_id"])
        if CONDITION_TOKEN_RE.search(bid):
            raise RuntimeError(f"{label}: condition token in blind_item_id {bid}")
        for key in ("question_uid", "run_id", "condition", "repetition", "question_order"):
            if key in row:
                raise RuntimeError(f"{label}: forbidden column {key}")
        # ID / uid-like cells must not embed condition codes
        for key in ("blind_item_id", "user_story_id", "segment_id"):
            val = str(row.get(key) or "")
            if CONDITION_TOKEN_RE.search(val):
                raise RuntimeError(f"{label}: condition token in {key}={val!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P5.1 blind ID preparation")
    parser.add_argument(
        "--seed",
        default=ANNOTATION_ORDER_SEED,
        help="Annotation-only order seed (never used in experimental runs)",
    )
    args = parser.parse_args(argv)
    try:
        get_root()
        ann = annotation_dir()
        ann.mkdir(parents=True, exist_ok=True)

        base_rows = import_csv(annotation_base_csv_path())
        if len(base_rows) != 269:
            raise RuntimeError(f"annotation-base expected 269, got {len(base_rows)}")

        cal_path = ann / "calibration-set.csv"
        cal_rows = import_csv(cal_path)
        if len(cal_rows) != 30:
            raise RuntimeError(f"calibration-set expected 30, got {len(cal_rows)}")
        original_uids = [r["question_uid"] for r in cal_rows]
        if len(set(original_uids)) != 30:
            raise RuntimeError("calibration-set has duplicate question_uid")

        crosswalk = build_crosswalk(base_rows, seed=args.seed)
        uid_to_blind = {str(r["question_uid"]): r for r in crosswalk}
        if len(uid_to_blind) != 269:
            raise RuntimeError("crosswalk question_uid not 1:1")

        # Preserve exact calibration membership; only attach blind ids.
        cal_out: list[dict[str, object]] = []
        for i, row in enumerate(cal_rows, start=1):
            mapped = uid_to_blind[row["question_uid"]]
            if mapped["user_story_id"] != row["user_story_id"]:
                raise RuntimeError(f"US mismatch for {row['question_uid']}")
            if mapped["question_text_raw"] != row["question_text_raw"]:
                raise RuntimeError(f"text mismatch for {row['question_uid']}")
            cal_out.append(
                {
                    "calibration_index": i,
                    "blind_item_id": mapped["blind_item_id"],
                    "question_uid": row["question_uid"],
                    "user_story_id": row["user_story_id"],
                    "question_text_raw": row["question_text_raw"],
                }
            )

        # Calibration presentation: same 30, shuffled within US (annotation seed).
        cal_by_us: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in cal_out:
            cal_by_us[str(row["user_story_id"])].append(row)
        cal_rng = random.Random(seed_to_int(args.seed + "::calibration"))
        cal_presenter: list[dict[str, object]] = []
        for us in USER_STORY_IDS:
            pool = list(cal_by_us[us])
            pool.sort(key=lambda r: str(r["blind_item_id"]))
            cal_rng.shuffle(pool)
            cal_presenter.extend(pool)

        cal_eval = [
            empty_evaluator_row(
                blind_item_id=str(r["blind_item_id"]),
                user_story_id=str(r["user_story_id"]),
                question_text_raw=str(r["question_text_raw"]),
            )
            for r in cal_presenter
        ]
        assert_no_condition_leak_in_evaluator(cal_eval, "calibration-evaluator")

        full_eval = [
            empty_evaluator_row(
                blind_item_id=str(r["blind_item_id"]),
                user_story_id=str(r["user_story_id"]),
                question_text_raw=str(r["question_text_raw"]),
            )
            for r in crosswalk  # already in annotation_order
        ]
        assert_no_condition_leak_in_evaluator(full_eval, "evaluator")

        export_csv(ann / "blind-id-map.csv", crosswalk, fieldnames=CROSSWALK_FIELDS)
        export_csv(cal_path, cal_out, fieldnames=CALIBRATION_SET_FIELDS)
        for name in ("calibration-evaluator-1.csv", "calibration-evaluator-2.csv"):
            export_csv(ann / name, cal_eval, fieldnames=EVALUATOR_FIELDS)
        for name in ("evaluator-1.csv", "evaluator-2.csv"):
            export_csv(ann / name, full_eval, fieldnames=EVALUATOR_FIELDS)

        meta = {
            "annotation_order_seed": args.seed,
            "annotation_order_seed_sha256": hashlib.sha256(
                args.seed.encode("utf-8")
            ).hexdigest(),
            "blind_item_count": len(crosswalk),
            "calibration_item_count": len(cal_out),
            "notes": (
                "annotation_order_seed is exclusive to annotation presentation. "
                "Never use it in experimental Spec Kit / Codex runs. "
                "blind-id-map.csv is private — do not give to evaluators during mapping. "
                "Calibration mappings must not be copied into the final annotation."
            ),
        }
        meta_path = ann / "annotation-blind-metadata.json"
        meta_path.write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        # Sanity: prr-reference-blind still clean
        prr_blind = import_csv(prr_reference_blind_csv_path())
        for row in prr_blind:
            for bad in ("condition", "gap_state", "importance", "category"):
                if bad in row:
                    raise RuntimeError(f"prr-reference-blind contains {bad}")

        dist = Counter(str(r["user_story_id"]) for r in cal_out)
        print("P5.1 blind ID prep OK")
        print(f"blind-id-map: {ann / 'blind-id-map.csv'} ({len(crosswalk)})")
        print(f"annotation_order_seed: {args.seed}")
        print(f"calibration same uids: {original_uids == [r['question_uid'] for r in cal_out]}")
        print("calibration_by_us", dict(dist))
        print(f"metadata: {meta_path}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
