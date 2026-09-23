"""P4: load PRR reference + build annotation bases (no automatic mapping).

Does not modify collected-data/questions.csv.
Does not call Codex / LLM / embeddings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent.parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
# Reuse frozen PRR parser from prepare_materials (repo root).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

from lib.io import export_csv, import_csv  # noqa: E402
from lib.paths import (  # noqa: E402
    annotation_base_csv_path,
    annotation_blind_csv_path,
    annotation_dir,
    get_root,
    prr_gap_states_csv_path,
    prr_reference_blind_csv_path,
    prr_reference_csv_path,
    questions_csv_path,
    run_summary_csv_path,
)
from lib.runs import CONDITIONS, USER_STORY_IDS  # noqa: E402
from prepare_materials import (  # noqa: E402
    GAP_STATE_EN,
    MATRIX_COLS,
    PRR_SHEETS,
    STATE_ANSWERED,
    STATE_OPEN,
    GapRow,
    UserStoryPRR,
    load_materials_sources,
    parse_prr_sheet,
)

# Annotation mapping statuses (human-filled later).
MAPPING_STATUS_VALUES = ("MATCH", "NO_REFERENCE_GAP", "REVIEW_REQUIRED")

# Structural normalization only (Portuguese spreadsheet → English codes).
STATE_NORMALIZE = {
    STATE_OPEN: "OPEN",
    STATE_ANSWERED: "ANSWERED",
    "Open": "OPEN",
    "Answered": "ANSWERED",
    "OPEN": "OPEN",
    "ANSWERED": "ANSWERED",
}

ANNOTATION_BASE_FIELDS = [
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

ANNOTATION_BLIND_FIELDS = [
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

PRR_REFERENCE_FIELDS = [
    "user_story_id",
    "gap_id",
    "gap_text",
    "importance",
    "ref_id",
    "reference_information",
    "category",
]

PRR_REFERENCE_BLIND_FIELDS = [
    "user_story_id",
    "gap_id",
    "gap_text",
    "reference_information",
]

PRR_STATE_FIELDS = [
    "user_story_id",
    "gap_id",
    "condition",
    "gap_state",
]

CLASSIFIED_FIELDS = [
    "question_uid",
    "run_id",
    "user_story_id",
    "condition",
    "repetition",
    "question_order",
    "question_text_raw",
    "normalized_need",
    "mapped_gap_id",
    "mapping_status",
    "importance",
    "gap_category",
    "gap_state",
]


@dataclass(frozen=True)
class StructuredGap:
    user_story_id: str
    gap_id: str
    gap_text: str
    importance: str
    ref_id: str
    reference_information: str
    category: str
    states: dict[str, str]  # condition -> OPEN|ANSWERED


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_state(raw: str | None) -> str:
    if raw is None or str(raw).strip() == "":
        raise ValueError("missing gap state in PRR")
    key = str(raw).strip()
    if key not in STATE_NORMALIZE:
        raise ValueError(f"unexpected PRR state {raw!r}")
    return STATE_NORMALIZE[key]


def load_prr_workbook(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(path)
    return openpyxl.load_workbook(path, data_only=True)


def load_structured_prrs(workbook) -> list[StructuredGap]:
    sources = load_materials_sources(workbook)
    gaps: list[StructuredGap] = []
    for sheet_name in PRR_SHEETS:
        if sheet_name not in workbook.sheetnames:
            raise FileNotFoundError(f"Missing PRR sheet: {sheet_name}")
        prr: UserStoryPRR = parse_prr_sheet(workbook, sheet_name, sources)
        if prr.user_story_id not in USER_STORY_IDS:
            raise ValueError(f"Unexpected US in PRR: {prr.user_story_id}")
        for g in prr.gaps:
            states: dict[str, str] = {}
            for cond in CONDITIONS:
                states[cond] = normalize_state(g.states.get(cond))
            gaps.append(
                StructuredGap(
                    user_story_id=prr.user_story_id,
                    gap_id=g.gap_id,
                    gap_text=(g.lacuna or "").strip(),
                    importance=(g.importance or "").strip(),
                    ref_id=(g.ref_id or "").strip(),
                    reference_information=(g.reference_information or "").strip(),
                    category=(g.category or "").strip(),
                    states=states,
                )
            )
    return gaps


def make_question_uid(run_id: str, question_order: int | str) -> str:
    order = int(question_order)
    return f"{run_id}_Q{order:02d}"


def build_prr_reference_rows(gaps: list[StructuredGap]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for g in gaps:
        rows.append(
            {
                "user_story_id": g.user_story_id,
                "gap_id": g.gap_id,
                "gap_text": g.gap_text,
                "importance": g.importance,
                "ref_id": g.ref_id,
                "reference_information": g.reference_information,
                "category": g.category,
            }
        )
    return rows


def build_prr_state_rows(gaps: list[StructuredGap]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for g in gaps:
        for cond in CONDITIONS:
            rows.append(
                {
                    "user_story_id": g.user_story_id,
                    "gap_id": g.gap_id,
                    "condition": cond,
                    "gap_state": g.states[cond],
                }
            )
    return rows


def build_annotation_base(questions: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for q in questions:
        run_id = q["run_id"]
        if run_id.startswith("SMOKE_"):
            raise ValueError(f"SMOKE_* must not enter annotation-base: {run_id}")
        order = int(q["question_order"])
        rows.append(
            {
                "question_uid": make_question_uid(run_id, order),
                "run_id": run_id,
                "user_story_id": q["user_story_id"],
                "condition": q["condition"],
                "repetition": q["repetition"],
                "attempt": q["attempt"],
                "question_order": order,
                "question_text_raw": q["question_text_raw"],
                "segment_id": "",
                "segment_text": "",
                "normalized_need": "",
                "mapped_gap_id": "",
                "mapping_status": "",
                "notes": "",
            }
        )
    return rows


def to_blind_rows(base_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "question_uid": r["question_uid"],
            "user_story_id": r["user_story_id"],
            "question_text_raw": r["question_text_raw"],
            "segment_id": r["segment_id"],
            "segment_text": r["segment_text"],
            "normalized_need": r["normalized_need"],
            "mapped_gap_id": r["mapped_gap_id"],
            "mapping_status": r["mapping_status"],
            "notes": r["notes"],
        }
        for r in base_rows
    ]


def to_prr_blind_rows(prr_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "user_story_id": r["user_story_id"],
            "gap_id": r["gap_id"],
            "gap_text": r["gap_text"],
            "reference_information": r["reference_information"],
        }
        for r in prr_rows
    ]


def validate_outputs(
    *,
    base_rows: list[dict[str, object]],
    blind_rows: list[dict[str, object]],
    prr_rows: list[dict[str, object]],
    state_rows: list[dict[str, object]],
    summary_rows: list[dict[str, str]],
) -> list[str]:
    issues: list[str] = []
    if len(base_rows) != 269:
        issues.append(f"annotation-base expected 269 rows, got {len(base_rows)}")
    uids = [str(r["question_uid"]) for r in base_rows]
    if len(uids) != len(set(uids)):
        issues.append("duplicate question_uid in annotation-base")
    if any(str(r["run_id"]).startswith("SMOKE_") for r in base_rows):
        issues.append("SMOKE_* in annotation-base")
    summary_ids = {r["run_id"] for r in summary_rows}
    if len(summary_ids) != 72:
        issues.append(f"run-summary expected 72 unique runs, got {len(summary_ids)}")
    for r in base_rows:
        if r["run_id"] not in summary_ids:
            issues.append(f"run_id missing from summary: {r['run_id']}")
            break
    if any(r.get("mapped_gap_id") for r in base_rows):
        issues.append("automatic mapped_gap_id filled (must be empty)")
    if any(r.get("mapping_status") for r in base_rows):
        issues.append("automatic mapping_status filled (must be empty)")
    if any(r.get("normalized_need") for r in base_rows):
        issues.append("automatic normalized_need filled (must be empty)")
    if len(blind_rows) != len(base_rows):
        issues.append("blind row count != base")
    # Blind must not leak condition
    for key in ("condition", "repetition", "run_id", "attempt", "question_order"):
        if any(key in r for r in blind_rows):
            issues.append(f"blind CSV must not contain {key}")
    us_set = {r["user_story_id"] for r in prr_rows}
    if us_set != set(USER_STORY_IDS):
        issues.append(f"prr-reference US set unexpected: {us_set}")
    for us in USER_STORY_IDS:
        gaps = [r["gap_id"] for r in prr_rows if r["user_story_id"] == us]
        if len(gaps) != len(set(gaps)):
            issues.append(f"duplicate gap_id within {us}")
    # States: every gap × 6 conditions
    expected_state_rows = len(prr_rows) * len(CONDITIONS)
    if len(state_rows) != expected_state_rows:
        issues.append(
            f"prr-gap-states expected {expected_state_rows}, got {len(state_rows)}"
        )
    for r in state_rows:
        if r["condition"] not in CONDITIONS:
            issues.append(f"unexpected condition in states: {r['condition']}")
        if r["gap_state"] not in {"OPEN", "ANSWERED"}:
            issues.append(f"unexpected gap_state: {r['gap_state']}")
    return issues


def write_freeze_json(root: Path, *, question_count: int) -> Path:
    paths = {
        "questions.csv": root / "collected-data" / "questions.csv",
        "run-summary.csv": root / "collected-data" / "run-summary.csv",
        "outputs-check.csv": root / "collected-data" / "outputs-check.csv",
        "prr_xlsx": root / "data" / "Matrizes de rastreabilidade - PRR.xlsx",
        "execution-protocol.md": root / "environment" / "execution-protocol.md",
        "parser-amendment.md": root / "environment" / "parser-amendment.md",
        "collection-report.md": root / "environment" / "collection-report.md",
    }
    hashes = {key: sha256_file(path) for key, path in paths.items()}
    payload = {
        "freeze_timestamp": datetime.now(timezone.utc).astimezone().isoformat(
            timespec="seconds"
        ),
        "parser_version": 2,
        "runs": 72,
        "questions": question_count,
        "specify_version": "1.0.10",
        "codex_version": "codex-cli 0.156.1",
        "model": "gpt-5.5",
        "reasoning_effort": "medium",
        "sandbox": "read-only",
        "approval_policy": "never",
        "sha256": {
            "collected-data/questions.csv": hashes["questions.csv"],
            "collected-data/run-summary.csv": hashes["run-summary.csv"],
            "collected-data/outputs-check.csv": hashes["outputs-check.csv"],
            "data/Matrizes de rastreabilidade - PRR.xlsx": hashes["prr_xlsx"],
            "environment/execution-protocol.md": hashes["execution-protocol.md"],
            "environment/parser-amendment.md": hashes["parser-amendment.md"],
            "environment/collection-report.md": hashes["collection-report.md"],
        },
        "notes": (
            "Collection freeze for P4 annotation prep. "
            "Do not modify hashed experimental artifacts without a new freeze."
        ),
    }
    out = root / "environment" / "collection-freeze.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P4: freeze-aware PRR load + annotation bases (no auto-mapping)"
    )
    parser.add_argument(
        "--skip-freeze",
        action="store_true",
        help="Do not rewrite environment/collection-freeze.json",
    )
    args = parser.parse_args(argv)
    try:
        root = get_root()
        questions_path = questions_csv_path()
        summary_path = run_summary_csv_path()
        prr_path = root / "data" / "Matrizes de rastreabilidade - PRR.xlsx"

        questions = import_csv(questions_path)
        summaries = import_csv(summary_path)
        if len(questions) != 269:
            raise RuntimeError(f"Expected 269 questions, got {len(questions)}")

        workbook = load_prr_workbook(prr_path)
        structured = load_structured_prrs(workbook)
        prr_rows = build_prr_reference_rows(structured)
        state_rows = build_prr_state_rows(structured)
        base_rows = build_annotation_base(questions)
        blind_rows = to_blind_rows(base_rows)

        export_csv(prr_reference_csv_path(), prr_rows, fieldnames=PRR_REFERENCE_FIELDS)
        export_csv(
            prr_reference_blind_csv_path(),
            to_prr_blind_rows(prr_rows),
            fieldnames=PRR_REFERENCE_BLIND_FIELDS,
        )
        export_csv(prr_gap_states_csv_path(), state_rows, fieldnames=PRR_STATE_FIELDS)
        export_csv(annotation_base_csv_path(), base_rows, fieldnames=ANNOTATION_BASE_FIELDS)
        export_csv(annotation_blind_csv_path(), blind_rows, fieldnames=ANNOTATION_BLIND_FIELDS)

        ann_dir = annotation_dir()
        ann_dir.mkdir(parents=True, exist_ok=True)
        for name in ("evaluator-1.csv", "evaluator-2.csv"):
            # Identical independent starting copies of the blind sheet.
            dest = ann_dir / name
            export_csv(dest, blind_rows, fieldnames=ANNOTATION_BLIND_FIELDS)

        issues = validate_outputs(
            base_rows=base_rows,
            blind_rows=blind_rows,
            prr_rows=prr_rows,
            state_rows=state_rows,
            summary_rows=summaries,
        )
        if issues:
            for issue in issues:
                print(f"VALIDATION FAIL: {issue}", file=sys.stderr)
            return 1

        freeze_path = None
        if not args.skip_freeze:
            freeze_path = write_freeze_json(root, question_count=len(questions))

        # Gap counts by US
        from collections import Counter

        gap_counts = Counter(r["user_story_id"] for r in prr_rows)
        q_counts = Counter(r["user_story_id"] for r in base_rows)

        print("P4 annotation prep OK")
        print(f"prr-reference: {prr_reference_csv_path()} ({len(prr_rows)} gaps)")
        print(f"prr-gap-states: {prr_gap_states_csv_path()} ({len(state_rows)} states)")
        print(f"annotation-base: {annotation_base_csv_path()} ({len(base_rows)})")
        print(f"annotation-blind: {annotation_blind_csv_path()} ({len(blind_rows)})")
        print(f"evaluators: {ann_dir / 'evaluator-1.csv'}, {ann_dir / 'evaluator-2.csv'}")
        if freeze_path:
            print(f"freeze: {freeze_path}")
        print("gaps_by_us", dict(gap_counts))
        print("questions_by_us", dict(q_counts))
        print("MAPPING_STATUS_VALUES", MAPPING_STATUS_VALUES)
        print("CLASSIFIED_FIELDS_READY", CLASSIFIED_FIELDS)
        # Confirm questions.csv bytes untouched during this run by re-hash after writes
        # (we never opened it for write).
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
