"""Technical integrity check for clarify runs (P3.5).

Classifies TECHNICAL_SUCCESS / TECHNICAL_FAILURE / PROTOCOL_VIOLATION.
Does not judge semantic quality. Does not treat 0 questions as failure.

Never modifies attempt artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from lib.io import export_csv, read_utf8
from lib.paths import get_root, outputs_check_csv_path, runs_dir
from lib.runs import RUN_DIR_PATTERN

# Frozen collection config (P3 smoke / P3.5).
EXPECTED_MODEL = "gpt-5.5"
EXPECTED_REASONING = "medium"
EXPECTED_SANDBOX = "read-only"
EXPECTED_APPROVAL = "never"

TECHNICAL_SUCCESS = "TECHNICAL_SUCCESS"
TECHNICAL_FAILURE = "TECHNICAL_FAILURE"
PROTOCOL_VIOLATION = "PROTOCOL_VIOLATION"

REQUIRED_ATTEMPT_FILES = (
    "execution-metadata.json",
    "stdout.jsonl",
    "stderr.txt",
    "last-message.txt",
)

PROGRESSION_PATTERNS = (
    re.compile(r"\$speckit-plan\b", re.I),
    re.compile(r"\$speckit-tasks\b", re.I),
    re.compile(r"\$speckit-implement\b", re.I),
    re.compile(r"/speckit\.plan\b", re.I),
    re.compile(r"/speckit\.tasks\b", re.I),
    re.compile(r"/speckit\.implement\b", re.I),
)
AUTO_ANSWER_PATTERNS = (
    re.compile(r"\buser reply\b", re.I),
    re.compile(r"\bi choose\b", re.I),
    re.compile(r"\banswer:\s*[a-e]\b", re.I),
    re.compile(r"\bsimulat(?:e|ed|ing)\s+(?:user\s+)?answer", re.I),
)

CHECK_FIELDNAMES = [
    "run_id",
    "user_story_id",
    "condition",
    "repetition",
    "attempt",
    "technical_status",
    "exit_code",
    "spec_unchanged",
    "model_ok",
    "reasoning_ok",
    "sandbox_ok",
    "approval_ok",
    "context_ok",
    "identity_ok",
    "artifacts_ok",
    "no_progression",
    "no_auto_answer",
    "issues",
    "run_path",
    "attempt_path",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _detect_forbidden(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(p.search(text) for p in patterns)


def check_run(
    run_path: Path,
    *,
    attempt: int = 1,
    expected_model: str = EXPECTED_MODEL,
    expected_reasoning: str = EXPECTED_REASONING,
    expected_sandbox: str = EXPECTED_SANDBOX,
    expected_approval: str = EXPECTED_APPROVAL,
) -> dict[str, object]:
    """Return one integrity row for a run folder (read-only)."""
    run_path = run_path.resolve()
    issues: list[str] = []
    attempt_path = run_path / f"attempt-{attempt}"

    scaffold: dict[str, Any] = {}
    scaffold_path = run_path / "metadata.json"
    if scaffold_path.is_file():
        try:
            scaffold = _load_json(scaffold_path)
        except json.JSONDecodeError:
            issues.append("scaffold metadata.json is not valid JSON")

    run_id = str(scaffold.get("run_id") or run_path.name)
    user_story_id = str(scaffold.get("user_story_id") or "")
    condition = str(scaffold.get("condition") or "")
    repetition = scaffold.get("repetition", "")

    artifacts_ok = True
    if not run_path.is_dir():
        issues.append("run directory missing")
        artifacts_ok = False
    if not attempt_path.is_dir():
        issues.append(f"attempt-{attempt} directory missing")
        artifacts_ok = False

    meta: dict[str, Any] = {}
    meta_path = attempt_path / "execution-metadata.json"
    for name in REQUIRED_ATTEMPT_FILES:
        path = attempt_path / name
        if not path.is_file():
            issues.append(f"missing {name}")
            artifacts_ok = False

    if meta_path.is_file():
        try:
            meta = _load_json(meta_path)
        except json.JSONDecodeError:
            issues.append("execution-metadata.json is not valid JSON")
            artifacts_ok = False

    exit_code = meta.get("exit_code")
    model = meta.get("model")
    reasoning = meta.get("reasoning_effort")
    sandbox = meta.get("sandbox")
    approval = meta.get("approval_policy")
    spec_before = meta.get("spec_sha256_before")
    spec_after = meta.get("spec_sha256_after")
    context_sha = meta.get("context_sha256", "__missing__")
    meta_run_id = meta.get("run_id")
    meta_us = meta.get("user_story_id")
    meta_condition = meta.get("condition")
    meta_rep = meta.get("repetition")
    meta_attempt = meta.get("attempt")

    # Fill identity from execution metadata when scaffold incomplete (fixtures).
    if not user_story_id and meta_us:
        user_story_id = str(meta_us)
    if not condition and meta_condition:
        condition = str(meta_condition)
    if repetition == "" and meta_rep is not None:
        repetition = meta_rep
    if meta_run_id:
        run_id = str(meta_run_id)

    model_ok = model == expected_model
    reasoning_ok = reasoning == expected_reasoning
    sandbox_ok = sandbox == expected_sandbox
    approval_ok = approval == expected_approval
    if not model_ok:
        issues.append(f"model={model!r} expected={expected_model!r}")
    if not reasoning_ok:
        issues.append(f"reasoning_effort={reasoning!r} expected={expected_reasoning!r}")
    if not sandbox_ok:
        issues.append(f"sandbox={sandbox!r} expected={expected_sandbox!r}")
    if not approval_ok:
        issues.append(f"approval_policy={approval!r} expected={expected_approval!r}")

    spec_unchanged = (
        isinstance(spec_before, str)
        and isinstance(spec_after, str)
        and spec_before == spec_after
        and bool(spec_before)
    )
    if spec_before is None or spec_after is None:
        issues.append("spec_sha256_before/after missing")
    elif not spec_unchanged:
        issues.append("spec_sha256_before != spec_sha256_after")

    identity_ok = True
    if meta_run_id and str(meta_run_id) != run_path.name:
        identity_ok = False
        issues.append(f"run_id mismatch meta={meta_run_id!r} folder={run_path.name!r}")
    if scaffold.get("run_id") and str(scaffold.get("run_id")) != run_path.name:
        identity_ok = False
        issues.append(
            f"scaffold run_id mismatch scaffold={scaffold.get('run_id')!r} "
            f"folder={run_path.name!r}"
        )
    if meta_us and user_story_id and str(meta_us) != str(user_story_id):
        identity_ok = False
        issues.append("user_story_id mismatch scaffold vs execution-metadata")
    if meta_condition and condition and str(meta_condition) != str(condition):
        identity_ok = False
        issues.append("condition mismatch scaffold vs execution-metadata")
    if meta_rep is not None and repetition != "" and int(meta_rep) != int(repetition):
        identity_ok = False
        issues.append("repetition mismatch scaffold vs execution-metadata")
    if meta_attempt is not None and int(meta_attempt) != int(attempt):
        identity_ok = False
        issues.append(f"attempt mismatch meta={meta_attempt} expected={attempt}")

    # Infer condition from folder name when possible (US02_C0_R1).
    # SMOKE_* synthetic folders may use labels like CTX; trust metadata.condition.
    parts = run_path.name.split("_")
    folder_condition = parts[1] if len(parts) >= 3 else ""
    if (
        condition
        and folder_condition
        and condition != folder_condition
        and not run_path.name.startswith("SMOKE_")
    ):
        identity_ok = False
        issues.append(
            f"condition mismatch folder={folder_condition!r} metadata={condition!r}"
        )
    if not condition and folder_condition and not run_path.name.startswith("SMOKE_"):
        condition = folder_condition

    context_ok = True
    if condition == "C0":
        if context_sha is not None and context_sha != "__missing__":
            context_ok = False
            issues.append("C0 requires context_sha256=null")
        context_path = run_path / "experiment-input" / "context.md"
        if context_path.exists():
            context_ok = False
            issues.append("C0 must not have experiment-input/context.md")
    elif condition in {"CL", "CO", "CD", "CS", "CT"}:
        if context_sha is None or context_sha == "__missing__" or context_sha == "":
            context_ok = False
            issues.append(f"{condition} requires non-null context_sha256")
        context_path = run_path / "experiment-input" / "context.md"
        if not context_path.is_file():
            context_ok = False
            issues.append(f"{condition} missing experiment-input/context.md")

    last_text = ""
    stdout_text = ""
    last_path = attempt_path / "last-message.txt"
    stdout_path = attempt_path / "stdout.jsonl"
    if last_path.is_file():
        last_text = read_utf8(last_path)
    if stdout_path.is_file():
        stdout_text = read_utf8(stdout_path)
    audit_blob = last_text + "\n" + stdout_text

    no_progression = not _detect_forbidden(audit_blob, PROGRESSION_PATTERNS)
    no_auto_answer = not _detect_forbidden(audit_blob, AUTO_ANSWER_PATTERNS)
    if not no_progression:
        issues.append("detected plan/tasks/implement continuation markers")
    if not no_auto_answer:
        issues.append("detected possible automatic answers to questions")

    # Status precedence: protocol violation > technical failure > success
    if spec_before is not None and spec_after is not None and spec_before != spec_after:
        technical_status = PROTOCOL_VIOLATION
    elif meta.get("protocol_violation") is True:
        technical_status = PROTOCOL_VIOLATION
        if "protocol_violation flag set" not in issues:
            issues.append("protocol_violation flag set in execution-metadata")
    elif (
        not artifacts_ok
        or exit_code != 0
        or not model_ok
        or not reasoning_ok
        or not sandbox_ok
        or not approval_ok
        or not identity_ok
        or not context_ok
        or not no_progression
        or not no_auto_answer
        or not spec_unchanged
    ):
        # Missing hashes already make spec_unchanged false → failure unless unequal
        # (unequal already handled as PROTOCOL_VIOLATION above).
        if (
            spec_before is not None
            and spec_after is not None
            and spec_before != spec_after
        ):
            technical_status = PROTOCOL_VIOLATION
        else:
            technical_status = TECHNICAL_FAILURE
    else:
        technical_status = TECHNICAL_SUCCESS

    if exit_code != 0 and technical_status == TECHNICAL_SUCCESS:
        technical_status = TECHNICAL_FAILURE
        issues.append(f"exit_code={exit_code}")
    elif exit_code != 0 and f"exit_code={exit_code}" not in issues:
        issues.append(f"exit_code={exit_code}")

    return {
        "run_id": run_id,
        "user_story_id": user_story_id,
        "condition": condition,
        "repetition": repetition,
        "attempt": attempt,
        "technical_status": technical_status,
        "exit_code": exit_code if exit_code is not None else "",
        "spec_unchanged": spec_unchanged,
        "model_ok": model_ok,
        "reasoning_ok": reasoning_ok,
        "sandbox_ok": sandbox_ok,
        "approval_ok": approval_ok,
        "context_ok": context_ok,
        "identity_ok": identity_ok,
        "artifacts_ok": artifacts_ok,
        "no_progression": no_progression,
        "no_auto_answer": no_auto_answer,
        "issues": "; ".join(issues),
        "run_path": str(run_path),
        "attempt_path": str(attempt_path),
    }


def discover_experimental_run_paths(root: Path | None = None) -> list[Path]:
    """Discover experimental run folders only (never SMOKE_*)."""
    root = root or get_root()
    base = runs_dir() if root == get_root() else root / "runs"
    if not base.is_dir():
        return []
    paths: list[Path] = []
    for p in sorted(base.iterdir()):
        if not p.is_dir() or not RUN_DIR_PATTERN.match(p.name):
            continue
        if p.name.startswith("SMOKE_"):
            continue
        paths.append(p)
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Technical integrity check for clarify attempt artifacts (P3.5)."
    )
    parser.add_argument(
        "--run-path",
        action="append",
        default=[],
        help="Explicit run directory (repeatable). Use for smoke; does not scan runs/.",
    )
    parser.add_argument(
        "--all-experimental",
        action="store_true",
        help="Scan runs/ for experimental Run_IDs (not used in P3.5 smoke).",
    )
    parser.add_argument(
        "--attempt",
        type=int,
        default=1,
        help="Attempt number to check (default: 1)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=f"CSV output path (default: {outputs_check_csv_path()})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = get_root()
        run_paths: list[Path] = []
        if args.run_path:
            run_paths = [(root / p).resolve() if not Path(p).is_absolute() else Path(p) for p in args.run_path]
        elif args.all_experimental:
            run_paths = discover_experimental_run_paths(root)
        else:
            print(
                "Provide --run-path <dir> (smoke/P3.5) or --all-experimental.\n"
                "Refusing to scan silently.",
                file=sys.stderr,
            )
            return 2

        rows = [check_run(path, attempt=args.attempt) for path in run_paths]
        out = args.out or outputs_check_csv_path()
        export_csv(out, rows, fieldnames=CHECK_FIELDNAMES)
        print(f"Output saved to:\n{out}")
        print(f"Total runs checked: {len(rows)}")
        for row in rows:
            print(f"  {row['run_id']}: {row['technical_status']}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
