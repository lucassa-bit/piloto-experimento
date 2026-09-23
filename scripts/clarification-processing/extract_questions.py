"""Extract clarification questions from last-message.txt (P3.5).

Canonical source: attempt-N/last-message.txt
Does not modify raw attempt artifacts.
Does not map to Gap IDs / PRR.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent.parent
CHECK_OUTPUTS_DIR = SCRIPTS / "check-outputs"
for _path in (str(SCRIPTS), str(CHECK_OUTPUTS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from lib.io import export_csv, read_utf8  # noqa: E402
from lib.paths import get_root, questions_csv_path, run_summary_csv_path, runs_dir  # noqa: E402
from lib.runs import RUN_DIR_PATTERN  # noqa: E402
from check_outputs import (  # noqa: E402
    PROTOCOL_VIOLATION,
    TECHNICAL_FAILURE,
    TECHNICAL_SUCCESS,
    check_run,
)

PARSE_OK = "PARSE_OK"
PARSE_REVIEW_REQUIRED = "PARSE_REVIEW_REQUIRED"
NO_CLARIFICATION_NEEDED = "NO_CLARIFICATION_NEEDED"
HAS_QUESTIONS = "HAS_QUESTIONS"

# Mechanical parser revision (marker-block segmentation without renumbering).
PARSER_VERSION = 2

SOURCE_FILE = "last-message.txt"

# Numbered item start: "1." / "1)" with optional marker.
NUMBERED_START = re.compile(
    r"^\s*(\d+)[\.)]\s+(.*)$",
)
BULLET_START = re.compile(
    r"^\s*[-*]\s+(.*)$",
)
NEEDS_MARKER = re.compile(r"\[NEEDS CLARIFICATION[^\]]*\]", re.IGNORECASE)
# Marker at the beginning of a line (optional leading whitespace only).
MARKER_LINE_START = re.compile(
    r"^[ \t]*(\[NEEDS CLARIFICATION[^\]]*\].*)$",
    re.IGNORECASE,
)
NO_CLARIFICATION_RE = re.compile(r"\bNO_CLARIFICATION_NEEDED\b", re.IGNORECASE)

QUESTION_FIELDNAMES = [
    "run_id",
    "user_story_id",
    "condition",
    "repetition",
    "attempt",
    "question_order",
    "question_text_raw",
    "source_file",
]

SUMMARY_FIELDNAMES = [
    "run_id",
    "user_story_id",
    "condition",
    "repetition",
    "attempt",
    "technical_status",
    "parse_status",
    "clarification_status",
    "question_count",
    "parser_version",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _finalize_block_lines(parts: list[str]) -> str:
    """Join block lines; strip only outer structural whitespace."""
    body = "\n".join(parts).strip("\n")
    body = "\n".join(line.rstrip() for line in body.split("\n")).strip()
    return body


def _parse_numbered_or_bullet(normalized: str) -> tuple[list[str], bool, bool]:
    """Return (questions, saw_numbered, saw_bullet)."""
    lines = normalized.split("\n")
    items: list[list[str]] = []
    current: list[str] | None = None
    saw_numbered = False
    saw_bullet = False

    for line in lines:
        numbered = NUMBERED_START.match(line)
        bullet = BULLET_START.match(line) if not numbered else None
        if numbered:
            saw_numbered = True
            if current is not None:
                items.append(current)
            current = [numbered.group(2)]
            continue
        if bullet:
            saw_bullet = True
            if current is not None:
                items.append(current)
            current = [bullet.group(1)]
            continue
        if current is not None:
            if line.strip() == "" and not any(part.strip() for part in current):
                continue
            current.append(line)
        elif line.strip() == "":
            continue

    if current is not None:
        items.append(current)

    questions = [_finalize_block_lines(parts) for parts in items if _finalize_block_lines(parts)]
    return questions, saw_numbered, saw_bullet


def _parse_marker_blocks(normalized: str) -> tuple[list[str], str]:
    """
    Segment by independent [NEEDS CLARIFICATION] blocks (parser v2).

    Delimiter is the marker at line start — not blank lines alone.
    Returns (questions, PARSE_OK|PARSE_REVIEW_REQUIRED).
    """
    lines = normalized.split("\n")

    # Ambiguity: marker mid-line, or multiple markers on one line.
    for line in lines:
        matches = list(NEEDS_MARKER.finditer(line))
        if not matches:
            continue
        first = matches[0]
        if line[: first.start()].strip():
            return [], PARSE_REVIEW_REQUIRED
        if len(matches) > 1:
            return [], PARSE_REVIEW_REQUIRED

    blocks: list[list[str]] = []
    current: list[str] | None = None
    leading_nonempty = False

    for line in lines:
        marker_match = MARKER_LINE_START.match(line)
        if marker_match:
            if current is not None:
                blocks.append(current)
            # Preserve marker + remainder literally (drop only indent before marker).
            current = [marker_match.group(1)]
            continue
        if current is None:
            if line.strip():
                leading_nonempty = True
            continue
        current.append(line)

    if current is not None:
        blocks.append(current)

    if leading_nonempty:
        return [], PARSE_REVIEW_REQUIRED
    if not blocks:
        return [], PARSE_REVIEW_REQUIRED

    questions: list[str] = []
    for parts in blocks:
        body = _finalize_block_lines(parts)
        if not body:
            return [], PARSE_REVIEW_REQUIRED
        if not re.match(r"\[NEEDS CLARIFICATION", body, re.IGNORECASE):
            return [], PARSE_REVIEW_REQUIRED
        rest = NEEDS_MARKER.sub("", body, count=1).strip()
        if not rest:
            # Marker-only / empty question body → ambiguous.
            return [], PARSE_REVIEW_REQUIRED
        questions.append(body)

    return questions, PARSE_OK


def parse_questions_from_last_message(text: str) -> tuple[list[str], str, str]:
    """
    Parse questions from last-message text (parser_version=2).

    Priority:
      A) valid numbered/bullet list → PARSE_OK
      B) independent [NEEDS CLARIFICATION] blocks (no list) → PARSE_OK
      C) otherwise → PARSE_REVIEW_REQUIRED

    question_text_raw preserves marker + text + internal newlines literally.
    """
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    stripped = normalized.strip()
    if not stripped:
        return [], PARSE_REVIEW_REQUIRED, ""

    has_no_clar = bool(NO_CLARIFICATION_RE.search(stripped))
    has_marker = bool(NEEDS_MARKER.search(stripped))

    if has_no_clar and not has_marker:
        return [], PARSE_OK, NO_CLARIFICATION_NEEDED

    # A) numbered / bullet
    list_questions, saw_numbered, saw_bullet = _parse_numbered_or_bullet(normalized)
    if saw_numbered or saw_bullet:
        if list_questions:
            return list_questions, PARSE_OK, HAS_QUESTIONS
        return [], PARSE_REVIEW_REQUIRED, ""

    # B) marker blocks without list scaffolding
    if has_marker:
        marker_questions, marker_status = _parse_marker_blocks(normalized)
        if marker_status == PARSE_OK and marker_questions:
            return marker_questions, PARSE_OK, HAS_QUESTIONS
        return [], PARSE_REVIEW_REQUIRED, ""

    if has_no_clar:
        return [], PARSE_OK, NO_CLARIFICATION_NEEDED

    # C) ambiguous / unstructured
    return [], PARSE_REVIEW_REQUIRED, ""


def extract_run(
    run_path: Path,
    *,
    attempt: int = 1,
    integrity_row: dict[str, object] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Extract question rows + summary row for one run (read-only on artifacts)."""
    run_path = run_path.resolve()
    attempt_path = run_path / f"attempt-{attempt}"
    last_path = attempt_path / "last-message.txt"

    integrity = integrity_row or check_run(run_path, attempt=attempt)
    technical_status = str(integrity["technical_status"])

    scaffold: dict[str, Any] = {}
    scaffold_path = run_path / "metadata.json"
    if scaffold_path.is_file():
        try:
            scaffold = _load_json(scaffold_path)
        except json.JSONDecodeError:
            scaffold = {}

    meta: dict[str, Any] = {}
    meta_path = attempt_path / "execution-metadata.json"
    if meta_path.is_file():
        try:
            meta = _load_json(meta_path)
        except json.JSONDecodeError:
            meta = {}

    run_id = str(meta.get("run_id") or scaffold.get("run_id") or run_path.name)
    user_story_id = str(
        meta.get("user_story_id") or scaffold.get("user_story_id") or integrity.get("user_story_id") or ""
    )
    condition = str(
        meta.get("condition") or scaffold.get("condition") or integrity.get("condition") or ""
    )
    repetition = meta.get("repetition", scaffold.get("repetition", integrity.get("repetition", "")))

    question_rows: list[dict[str, object]] = []
    parse_status = PARSE_REVIEW_REQUIRED
    clarification_status = ""
    question_count = 0

    if not last_path.is_file():
        parse_status = PARSE_REVIEW_REQUIRED
        clarification_status = ""
    else:
        text = read_utf8(last_path)
        questions, parse_status, clarification_status = parse_questions_from_last_message(text)
        question_count = len(questions)
        for order, question in enumerate(questions, start=1):
            question_rows.append(
                {
                    "run_id": run_id,
                    "user_story_id": user_story_id,
                    "condition": condition,
                    "repetition": repetition,
                    "attempt": attempt,
                    "question_order": order,
                    "question_text_raw": question,
                    "source_file": SOURCE_FILE,
                }
            )

    summary = {
        "run_id": run_id,
        "user_story_id": user_story_id,
        "condition": condition,
        "repetition": repetition,
        "attempt": attempt,
        "technical_status": technical_status,
        "parse_status": parse_status,
        "clarification_status": clarification_status,
        "question_count": question_count,
        "parser_version": PARSER_VERSION,
    }
    return question_rows, summary


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
        description=(
            "Extract clarification questions from last-message.txt (P3.5). "
            "Also writes run-summary.csv (one row per run, including 0 questions)."
        )
    )
    parser.add_argument(
        "--run-path",
        action="append",
        default=[],
        help="Explicit run directory (repeatable). Use for smoke.",
    )
    parser.add_argument(
        "--all-experimental",
        action="store_true",
        help="Scan runs/ for experimental Run_IDs (not used in P3.5 smoke).",
    )
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument(
        "--questions-out",
        type=Path,
        default=None,
        help=f"Questions CSV (default: {questions_csv_path()})",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=None,
        help=f"Run summary CSV (default: {run_summary_csv_path()})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        root = get_root()
        if args.run_path:
            run_paths = [
                (root / p).resolve() if not Path(p).is_absolute() else Path(p)
                for p in args.run_path
            ]
        elif args.all_experimental:
            run_paths = discover_experimental_run_paths(root)
        else:
            print(
                "Provide --run-path <dir> (smoke/P3.5) or --all-experimental.\n"
                "Refusing to scan silently.",
                file=sys.stderr,
            )
            return 2

        all_questions: list[dict[str, object]] = []
        summaries: list[dict[str, object]] = []
        for path in run_paths:
            if path.name.startswith("SMOKE_"):
                q_default = args.questions_out or questions_csv_path()
                s_default = args.summary_out or run_summary_csv_path()
                for out in (q_default, s_default):
                    out_res = out.resolve()
                    if "smoke" not in out_res.parts and out_res.parent == (
                        get_root() / "collected-data"
                    ).resolve():
                        print(
                            f"Refusing to write SMOKE_* run {path.name} into "
                            f"canonical experimental CSV {out}. "
                            f"Use collected-data/smoke/…",
                            file=sys.stderr,
                        )
                        return 2
            integrity = check_run(path, attempt=args.attempt)
            qrows, summary = extract_run(
                path, attempt=args.attempt, integrity_row=integrity
            )
            all_questions.extend(qrows)
            summaries.append(summary)
            print(
                f"{summary['run_id']}: technical={summary['technical_status']} "
                f"parse={summary['parse_status']} questions={summary['question_count']}"
            )

        q_out = args.questions_out or questions_csv_path()
        s_out = args.summary_out or run_summary_csv_path()
        export_csv(q_out, all_questions, fieldnames=QUESTION_FIELDNAMES)
        export_csv(s_out, summaries, fieldnames=SUMMARY_FIELDNAMES)
        print(f"Questions CSV:\n{q_out}")
        print(f"Run summary CSV:\n{s_out}")
        print(f"Total question rows: {len(all_questions)}")
        # Silence unused imports if linting — keep status constants available to tests.
        _ = (TECHNICAL_SUCCESS, TECHNICAL_FAILURE, PROTOCOL_VIOLATION)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
