#!/usr/bin/env python3
"""Idempotent reprocess of collected experimental runs with parser v2 (no Codex)."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "check-outputs"))
sys.path.insert(0, str(SCRIPTS / "clarification-processing"))

from lib.io import export_csv  # noqa: E402
from lib.paths import (  # noqa: E402
    get_root,
    outputs_check_csv_path,
    questions_csv_path,
    run_summary_csv_path,
    runs_dir,
)
import check_outputs as chk  # noqa: E402
import extract_questions as exq  # noqa: E402

# Runs with attempt-1 already executed (frozen order).
COLLECTED_RUN_IDS = (
    "US02_C0_R1",
    "US02_C0_R2",
    "US02_C0_R3",
    "US02_CL_R1",
    "US02_CL_R2",
)


def main() -> int:
    root = get_root()
    all_questions: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    outputs: list[dict[str, object]] = []

    print(f"Reprocessing {len(COLLECTED_RUN_IDS)} runs with parser_version={exq.PARSER_VERSION}")
    for run_id in COLLECTED_RUN_IDS:
        if run_id.startswith("SMOKE_"):
            print(f"Refusing SMOKE_*: {run_id}", file=sys.stderr)
            return 2
        run_path = runs_dir() / run_id
        if not (run_path / "attempt-1" / "last-message.txt").is_file():
            print(f"Missing attempt-1 for {run_id}", file=sys.stderr)
            return 1
        integrity = chk.check_run(run_path, attempt=1)
        qrows, summary = exq.extract_run(run_path, attempt=1, integrity_row=integrity)
        print(
            f"{run_id}: technical={summary['technical_status']} "
            f"parse={summary['parse_status']} questions={summary['question_count']} "
            f"parser={summary['parser_version']}"
        )
        if integrity["technical_status"] != chk.TECHNICAL_SUCCESS:
            print(f"STOP: {run_id} not TECHNICAL_SUCCESS", file=sys.stderr)
            return 1
        if summary["parse_status"] != exq.PARSE_OK:
            print(f"STOP: {run_id} parse={summary['parse_status']}", file=sys.stderr)
            return 1
        outputs.append(integrity)
        summaries.append(summary)
        all_questions.extend(qrows)

    # Idempotent full rewrite of experimental CSVs for collected subset only.
    # (Later collection appends remaining runs.)
    export_csv(questions_csv_path(), all_questions, fieldnames=exq.QUESTION_FIELDNAMES)
    export_csv(run_summary_csv_path(), summaries, fieldnames=exq.SUMMARY_FIELDNAMES)
    export_csv(outputs_check_csv_path(), outputs, fieldnames=chk.CHECK_FIELDNAMES)

    # Uniqueness checks
    ids = [s["run_id"] for s in summaries]
    if len(ids) != len(set(ids)):
        print("STOP: duplicate run_id in summary", file=sys.stderr)
        return 1
    if any(str(i).startswith("SMOKE_") for i in ids):
        print("STOP: SMOKE_* in experimental CSV", file=sys.stderr)
        return 1

    print(f"Wrote {questions_csv_path()} ({len(all_questions)} questions)")
    print(f"Wrote {run_summary_csv_path()} ({len(summaries)} runs)")
    print(f"Wrote {outputs_check_csv_path()} ({len(outputs)} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
