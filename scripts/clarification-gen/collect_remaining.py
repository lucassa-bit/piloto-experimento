#!/usr/bin/env python3
"""Collect the remaining experimental clarify runs (skip frozen US02_C0_R1).

Sequential, deterministic, no shuffle, no auto-retry, stop on first protocol/
technical/parse failure. Does not touch baselines/scaffold/materials.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "clarification-gen"))
sys.path.insert(0, str(SCRIPTS / "check-outputs"))
sys.path.insert(0, str(SCRIPTS / "clarification-processing"))

from lib.codex import (  # noqa: E402
    EXPERIMENT_MODEL,
    EXPERIMENT_REASONING_EFFORT,
    codex_version,
    ensure_codex_available,
    resolve_codex_executable,
)
from lib.io import export_csv, import_csv, read_utf8  # noqa: E402
from lib.paths import (  # noqa: E402
    get_root,
    outputs_check_csv_path,
    prompt_path,
    questions_csv_path,
    run_summary_csv_path,
    runs_dir,
)
from lib.runs import (  # noqa: E402
    EXPECTED_RUN_COUNT,
    RunInfo,
    USER_STORY_IDS,
    iter_planned_runs,
    validate_run_inputs,
)
import check_outputs as chk  # noqa: E402
import extract_questions as exq  # noqa: E402
from runner import (  # noqa: E402
    DEFAULT_APPROVAL_POLICY,
    DEFAULT_CLARIFY_SANDBOX,
    run_one,
    sha256_file,
    specify_cli_version,
)
from scaffold_runs import FROZEN_BASELINE_SHA256  # noqa: E402

SKIP_RUN_ID = "US02_C0_R1"
PAUSE_SECONDS = 2
PROGRESS_PATH_REL = "environment/collection-progress.md"
REPORT_PATH_REL = "environment/collection-report.md"


class CollectionStop(Exception):
    """Fatal stop — do not continue to next runs."""


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_export_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    export_csv(tmp, rows, fieldnames=fieldnames)
    tmp.replace(path)


def precheck_run(root: Path, run_id: str, us_id: str, condition: str, repetition: int) -> Path:
    run_path = runs_dir() / run_id
    if not run_path.is_dir():
        raise CollectionStop(f"Missing run directory: {run_path}")

    scaffold_path = run_path / "metadata.json"
    if not scaffold_path.is_file():
        raise CollectionStop(f"Missing scaffold metadata.json: {scaffold_path}")
    meta = load_json(scaffold_path)

    if meta.get("run_id") != run_id:
        raise CollectionStop(f"run_id mismatch in metadata: {meta.get('run_id')} != {run_id}")
    if meta.get("user_story_id") != us_id:
        raise CollectionStop(f"user_story_id mismatch for {run_id}")
    if meta.get("condition") != condition:
        raise CollectionStop(f"condition mismatch for {run_id}")
    if int(meta.get("repetition", -1)) != int(repetition):
        raise CollectionStop(f"repetition mismatch for {run_id}")

    spec_path = run_path / "spec.md"
    if not spec_path.is_file():
        raise CollectionStop(f"Missing spec.md: {spec_path}")
    spec_sha = sha256_file(spec_path)
    expected_baseline = FROZEN_BASELINE_SHA256[us_id]
    if spec_sha != expected_baseline:
        raise CollectionStop(
            f"spec hash != frozen baseline for {run_id}: {spec_sha} != {expected_baseline}"
        )
    if meta.get("baseline_sha256") and meta["baseline_sha256"] != spec_sha:
        raise CollectionStop(f"scaffold baseline_sha256 mismatch for {run_id}")

    story_path = run_path / "experiment-input" / "user-story.md"
    if not story_path.is_file():
        raise CollectionStop(f"Missing user-story.md: {story_path}")
    story_sha = sha256_file(story_path)
    materials_story = root / "materials" / us_id / "user-story.md"
    if materials_story.is_file() and sha256_file(materials_story) != story_sha:
        raise CollectionStop(f"user-story hash != materials for {run_id}")
    if meta.get("user_story_sha256") and meta["user_story_sha256"] != story_sha:
        raise CollectionStop(f"scaffold user_story_sha256 mismatch for {run_id}")

    context_path = run_path / "experiment-input" / "context.md"
    if condition == "C0":
        if context_path.exists():
            raise CollectionStop(f"C0 must not have context.md: {run_id}")
        if meta.get("context_sha256") is not None:
            raise CollectionStop(f"C0 scaffold context_sha256 must be null: {run_id}")
    else:
        if not context_path.is_file():
            raise CollectionStop(f"{condition} missing context.md: {run_id}")
        ctx_sha = sha256_file(context_path)
        if meta.get("context_sha256") != ctx_sha:
            raise CollectionStop(f"context hash != scaffold metadata for {run_id}")
        # Literal match to materials
        from lib.runs import context_filename_for_condition

        mat = root / "materials" / us_id / context_filename_for_condition(condition)
        if not mat.is_file() or sha256_file(mat) != ctx_sha:
            raise CollectionStop(f"context.md != materials source for {run_id}")

    validate_run_inputs(RunInfo(run_id, us_id, condition, run_path), root=root)

    attempt_path = run_path / "attempt-1"
    if attempt_path.exists() and any(attempt_path.iterdir() if attempt_path.is_dir() else []):
        raise CollectionStop(f"Unexpected pre-existing attempt-1 for {run_id}")
    if attempt_path.is_dir() and not any(attempt_path.iterdir()):
        # empty dir odd — still refuse
        raise CollectionStop(f"Empty attempt-1 directory already present for {run_id}")

    return run_path


def ensure_no_smoke_in_rows(rows: list[dict[str, Any]], key: str = "run_id") -> None:
    for row in rows:
        rid = str(row.get(key, ""))
        if rid.startswith("SMOKE_"):
            raise CollectionStop(f"SMOKE_* row found in experimental CSV: {rid}")


def upsert_csvs(
    *,
    integrity: dict[str, object],
    question_rows: list[dict[str, object]],
    summary: dict[str, object],
) -> None:
    run_id = str(summary["run_id"])
    if run_id.startswith("SMOKE_"):
        raise CollectionStop(f"Refusing to write SMOKE_* into experimental CSVs: {run_id}")

    q_path = questions_csv_path()
    s_path = run_summary_csv_path()
    o_path = outputs_check_csv_path()

    summaries = import_csv(s_path) if s_path.is_file() else []
    questions = import_csv(q_path) if q_path.is_file() else []
    outputs = import_csv(o_path) if o_path.is_file() else []

    ensure_no_smoke_in_rows(summaries)
    ensure_no_smoke_in_rows(questions)
    ensure_no_smoke_in_rows(outputs)

    existing_ids = {r["run_id"] for r in summaries}
    if run_id in existing_ids:
        raise CollectionStop(f"Duplicate run_id in run-summary.csv: {run_id}")

    # Also refuse duplicate question blocks for same run_id
    if any(r["run_id"] == run_id for r in questions):
        raise CollectionStop(f"Duplicate run_id already in questions.csv: {run_id}")
    if any(r["run_id"] == run_id for r in outputs):
        raise CollectionStop(f"Duplicate run_id already in outputs-check.csv: {run_id}")

    summaries.append({k: str(summary[k]) for k in exq.SUMMARY_FIELDNAMES})
    outputs.append({k: str(integrity[k]) for k in chk.CHECK_FIELDNAMES})
    for row in question_rows:
        questions.append({k: str(row[k]) for k in exq.QUESTION_FIELDNAMES})

    atomic_export_csv(s_path, summaries, exq.SUMMARY_FIELDNAMES)
    atomic_export_csv(o_path, outputs, chk.CHECK_FIELDNAMES)
    atomic_export_csv(q_path, questions, exq.QUESTION_FIELDNAMES)


def write_progress(root: Path, rows: list[dict[str, object]], *, stopped: str = "") -> None:
    path = root / PROGRESS_PATH_REL
    lines = [
        "# Collection progress (operational)",
        "",
        f"**Updated:** {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"**Skip (frozen):** `{SKIP_RUN_ID}`",
        f"**Completed this session + prior:** {len(rows)}",
        "",
        "| run_id | exit_code | technical_status | parse_status | question_count | duration_s | spec_unchanged |",
        "| --- | ---: | --- | --- | ---: | ---: | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['run_id']} | {r['exit_code']} | {r['technical_status']} | "
            f"{r['parse_status']} | {r['question_count']} | {r['duration_s']} | "
            f"{r['spec_unchanged']} |"
        )
    if stopped:
        lines.extend(["", f"**STOPPED:** {stopped}", ""])
    else:
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_final_report(root: Path, progress_rows: list[dict[str, object]]) -> None:
    s_path = run_summary_csv_path()
    q_path = questions_csv_path()
    summaries = import_csv(s_path)
    questions = import_csv(q_path)
    ensure_no_smoke_in_rows(summaries)
    ensure_no_smoke_in_rows(questions)

    planned = [r[0] for r in iter_planned_runs()]
    ids = [r["run_id"] for r in summaries]
    tech_ok = sum(1 for r in summaries if r["technical_status"] == chk.TECHNICAL_SUCCESS)
    tech_fail = sum(1 for r in summaries if r["technical_status"] == chk.TECHNICAL_FAILURE)
    proto = sum(1 for r in summaries if r["technical_status"] == chk.PROTOCOL_VIOLATION)
    parse_review = sum(1 for r in summaries if r["parse_status"] == exq.PARSE_REVIEW_REQUIRED)
    parse_ok = sum(1 for r in summaries if r["parse_status"] == exq.PARSE_OK)
    zero_q = [r["run_id"] for r in summaries if int(r["question_count"]) == 0]
    total_q = len(questions)

    by_us: dict[str, int] = {}
    by_cond: dict[str, int] = {}
    by_rep: dict[str, int] = {}
    for r in questions:
        by_us[r["user_story_id"]] = by_us.get(r["user_story_id"], 0) + 1
        by_cond[r["condition"]] = by_cond.get(r["condition"], 0) + 1
        by_rep[str(r["repetition"])] = by_rep.get(str(r["repetition"]), 0) + 1

    durations: list[float] = []
    for r in progress_rows:
        raw = r.get("duration_s", "")
        try:
            durations.append(float(raw))
        except (TypeError, ValueError):
            continue
    total_dur = sum(durations) if durations else 0.0
    mean_dur = (total_dur / len(durations)) if durations else 0.0

    # Integrity: baselines/materials/specs
    baselines_ok = True
    for us, expected in FROZEN_BASELINE_SHA256.items():
        p = root / "baselines" / us / "spec.md"
        if not p.is_file() or sha256_file(p) != expected:
            baselines_ok = False
    specs_ok = True
    for run_id, us_id, _c, _r in iter_planned_runs():
        sp = runs_dir() / run_id / "spec.md"
        if not sp.is_file() or sha256_file(sp) != FROZEN_BASELINE_SHA256[us_id]:
            specs_ok = False
            break
    attempt2 = list(runs_dir().rglob("attempt-2"))
    materials_ok = True
    for us in USER_STORY_IDS:
        story = root / "materials" / us / "user-story.md"
        if not story.is_file():
            materials_ok = False

    unique_ok = len(ids) == len(set(ids)) == EXPECTED_RUN_COUNT
    order_ok = ids == planned

    lines = [
        "# Collection report — experimental clarify (72 runs)",
        "",
        f"**Finished:** {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"**Config:** model=`{EXPERIMENT_MODEL}` · reasoning=`{EXPERIMENT_REASONING_EFFORT}` · "
        f"sandbox=`{DEFAULT_CLARIFY_SANDBOX}` · approval=`{DEFAULT_APPROVAL_POLICY}`",
        "",
        "## Totals",
        "",
        f"- Runs planned: **{EXPECTED_RUN_COUNT}**",
        f"- Runs in run-summary.csv: **{len(summaries)}**",
        f"- Unique run_ids: **{len(set(ids))}**",
        f"- Technical successes: **{tech_ok}**",
        f"- Technical failures: **{tech_fail}**",
        f"- Protocol violations: **{proto}**",
        f"- PARSE_OK: **{parse_ok}**",
        f"- PARSE_REVIEW_REQUIRED: **{parse_review}**",
        f"- Total questions: **{total_q}**",
        f"- Runs with 0 questions: **{len(zero_q)}** ({', '.join(zero_q) if zero_q else 'none'})",
        f"- Duration sum (progress rows): **{total_dur:.1f}s**",
        f"- Duration mean: **{mean_dur:.1f}s**",
        "",
        "## Questions by US",
        "",
    ]
    for us in USER_STORY_IDS:
        lines.append(f"- {us}: {by_us.get(us, 0)}")
    lines.extend(["", "## Questions by condition", ""])
    for cond in ("C0", "CL", "CO", "CD", "CS", "CT"):
        lines.append(f"- {cond}: {by_cond.get(cond, 0)}")
    lines.extend(["", "## Questions by repetition", ""])
    for rep in ("1", "2", "3"):
        lines.append(f"- R{rep}: {by_rep.get(rep, 0)}")
    lines.extend(
        [
            "",
            "## Integrity",
            "",
            f"- All run specs == frozen baselines: **{specs_ok}**",
            f"- baselines/ unchanged vs frozen table: **{baselines_ok}**",
            f"- materials/ present: **{materials_ok}**",
            f"- attempt-2 directories: **{len(attempt2)}** ({attempt2 or 'none'})",
            f"- run-summary unique + count 72: **{unique_ok}**",
            f"- run-summary order matches planned matrix: **{order_ok}**",
            f"- No SMOKE_* in experimental CSVs: **True**",
            f"- Frozen skip preserved (`{SKIP_RUN_ID}`): **{SKIP_RUN_ID in ids}**",
            "",
            "## Verdict",
            "",
        ]
    )
    all_good = (
        unique_ok
        and tech_fail == 0
        and proto == 0
        and parse_review == 0
        and specs_ok
        and baselines_ok
        and len(attempt2) == 0
        and len(summaries) == EXPECTED_RUN_COUNT
    )
    lines.append(f"**{'PASS' if all_good else 'INCOMPLETE/FAIL'}**")
    lines.append("")
    lines.append("Classification / Gap mapping **not** started.")
    lines.append("")
    (root / REPORT_PATH_REL).write_text("\n".join(lines), encoding="utf-8")


def completed_run_ids_from_csv() -> set[str]:
    """Runs already recorded as technical+parse success (do not re-execute)."""
    s_path = run_summary_csv_path()
    if not s_path.is_file():
        return set()
    done: set[str] = set()
    for row in import_csv(s_path):
        rid = row.get("run_id", "")
        if rid.startswith("SMOKE_"):
            continue
        if (
            row.get("technical_status") == chk.TECHNICAL_SUCCESS
            and row.get("parse_status") == exq.PARSE_OK
        ):
            done.add(rid)
    return done


def collect(*, dry_run_precheck_only: bool = False) -> int:
    root = get_root().resolve()
    planned = iter_planned_runs()
    if len(planned) != EXPECTED_RUN_COUNT:
        raise CollectionStop(f"Planned size {len(planned)} != {EXPECTED_RUN_COUNT}")

    completed = completed_run_ids_from_csv()
    # Also treat frozen US02_C0_R1 as completed if attempt exists even before CSV rewrite.
    if (runs_dir() / SKIP_RUN_ID / "attempt-1" / "execution-metadata.json").is_file():
        completed.add(SKIP_RUN_ID)

    # Unexpected attempt-1 only for runs not already completed.
    for run_id, _us, _c, _r in planned:
        if run_id in completed:
            continue
        ap = runs_dir() / run_id / "attempt-1"
        if ap.exists() and (not ap.is_dir() or any(ap.iterdir())):
            raise CollectionStop(f"Unexpected attempt-1 before collection: {run_id}")

    frozen_attempt = runs_dir() / SKIP_RUN_ID / "attempt-1" / "execution-metadata.json"
    if not frozen_attempt.is_file():
        raise CollectionStop(f"Frozen run missing attempt artifacts: {SKIP_RUN_ID}")

    progress_rows: list[dict[str, object]] = []
    s_path = run_summary_csv_path()
    if s_path.is_file():
        for row in import_csv(s_path):
            if row["run_id"] in completed:
                progress_rows.append(
                    {
                        "run_id": row["run_id"],
                        "exit_code": "0",
                        "technical_status": row["technical_status"],
                        "parse_status": row["parse_status"],
                        "question_count": row["question_count"],
                        "duration_s": "(prior)",
                        "spec_unchanged": "True",
                    }
                )

    ensure_codex_available()
    exe = resolve_codex_executable()
    cli_version = codex_version(exe)
    spec_ver = specify_cli_version()
    prompt = read_utf8(prompt_path())

    remaining = [
        (rid, us, cond, rep)
        for rid, us, cond, rep in planned
        if rid not in completed
    ]
    print(
        f"Collecting {len(remaining)} runs "
        f"(already completed={len(completed)}; skip re-exec)"
    )
    print(
        f"Model={EXPERIMENT_MODEL} reasoning={EXPERIMENT_REASONING_EFFORT} "
        f"sandbox={DEFAULT_CLARIFY_SANDBOX} approval={DEFAULT_APPROVAL_POLICY}"
    )
    if remaining:
        print(f"Next run: {remaining[0][0]}")

    write_progress(root, progress_rows)

    if dry_run_precheck_only:
        for run_id, us_id, condition, repetition in remaining:
            precheck_run(root, run_id, us_id, condition, repetition)
            print(f"PRECHECK_OK {run_id}")
        print("All prechecks OK (no Codex executed)")
        return 0

    if not remaining:
        write_final_report(root, progress_rows)
        print("Nothing left to collect")
        return 0

    for index, (run_id, us_id, condition, repetition) in enumerate(remaining, start=1):
        print("=" * 60)
        print(f"[{index}/{len(remaining)}] {run_id}")
        print("=" * 60)
        try:
            run_path = precheck_run(root, run_id, us_id, condition, repetition)
            started = time.monotonic()
            outcome = run_one(
                RunInfo(run_id, us_id, condition, run_path),
                root=root,
                prompt=prompt,
                sandbox=DEFAULT_CLARIFY_SANDBOX,
                approval_policy=DEFAULT_APPROVAL_POLICY,
                attempt=1,
                ordem=len(completed) + index,
                codex_executable=exe,
                codex_cli_version=cli_version,
                specify_version=spec_ver,
                execute=True,
                pause_after=False,
                allow_experimental=True,
            )
            duration = round(time.monotonic() - started, 1)

            if outcome.protocol_violation:
                raise CollectionStop(
                    f"PROTOCOL_VIOLATION on {run_id}: {outcome.error}"
                )
            if outcome.status != "Valid" or outcome.exit_code != 0:
                raise CollectionStop(
                    f"TECHNICAL_FAILURE on {run_id}: status={outcome.status} "
                    f"exit={outcome.exit_code} error={outcome.error}"
                )
            if outcome.spec_sha256_before != outcome.spec_sha256_after:
                raise CollectionStop(f"spec hash changed on {run_id}")

            integrity = chk.check_run(run_path, attempt=1)
            if integrity["technical_status"] != chk.TECHNICAL_SUCCESS:
                raise CollectionStop(
                    f"{integrity['technical_status']} on {run_id}: {integrity['issues']}"
                )

            qrows, summary = exq.extract_run(
                run_path, attempt=1, integrity_row=integrity
            )
            if summary["parse_status"] == exq.PARSE_REVIEW_REQUIRED:
                raise CollectionStop(f"PARSE_REVIEW_REQUIRED on {run_id}")
            if summary["parse_status"] != exq.PARSE_OK:
                raise CollectionStop(
                    f"Unexpected parse_status={summary['parse_status']} on {run_id}"
                )

            upsert_csvs(integrity=integrity, question_rows=qrows, summary=summary)

            progress_rows.append(
                {
                    "run_id": run_id,
                    "exit_code": outcome.exit_code if outcome.exit_code is not None else "",
                    "technical_status": integrity["technical_status"],
                    "parse_status": summary["parse_status"],
                    "question_count": summary["question_count"],
                    "duration_s": duration,
                    "spec_unchanged": outcome.spec_sha256_before
                    == outcome.spec_sha256_after,
                }
            )
            write_progress(root, progress_rows)
            print(
                f"OK {run_id}: questions={summary['question_count']} "
                f"duration={duration}s"
            )
            time.sleep(PAUSE_SECONDS)
        except CollectionStop as exc:
            write_progress(root, progress_rows, stopped=str(exc))
            print(f"STOP: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            write_progress(root, progress_rows, stopped=f"UNFORESEEN: {exc}")
            print(f"STOP UNFORESEEN: {exc}", file=sys.stderr)
            return 1

    write_final_report(root, progress_rows)
    write_progress(root, progress_rows)
    print("COLLECTION COMPLETE")
    print(f"Report: {root / REPORT_PATH_REL}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect remaining 71 experimental clarify runs")
    parser.add_argument(
        "--precheck-only",
        action="store_true",
        help="Validate all remaining runs without calling Codex",
    )
    parser.add_argument(
        "--i-authorize-experimental-collection",
        action="store_true",
        help="Required authorization flag",
    )
    args = parser.parse_args(argv)
    if not args.i_authorize_experimental_collection:
        print("Refusing without --i-authorize-experimental-collection", file=sys.stderr)
        return 2
    try:
        return collect(dry_run_precheck_only=args.precheck_only)
    except CollectionStop as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
