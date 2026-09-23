"""Batch Codex clarify runner for experiment collections (P3).

Protocol: one new Codex session per run → exactly one $speckit-clarify →
collect questions → stop without answering. No auto-retry.

Does NOT invoke collection unless explicitly authorized via CLI flags.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from lib.codex import (
    EXPERIMENT_MODEL,
    EXPERIMENT_REASONING_EFFORT,
    build_run_metadata_template,
    codex_version,
    ensure_codex_available,
    invoke_codex_exec,
    resolve_codex_executable,
)
from lib.io import export_csv, read_metadata, read_utf8, write_metadata, write_utf8
from lib.paths import collected_dir, execution_table_path, get_root, prompt_path, runs_dir
from lib.runs import (
    EXPECTED_RUN_COUNT,
    USER_STORY_IDS,
    RunInfo,
    discover_runs,
    map_status_pt,
    parse_repeticao,
    validate_run_inputs,
)

PAUSE_BETWEEN_RUNS_SECONDS = 3

# Sandbox default until smoke closes the decision (read-only first).
DEFAULT_CLARIFY_SANDBOX = "read-only"
DEFAULT_APPROVAL_POLICY = "never"
EXECUTION_METADATA_NAME = "execution-metadata.json"
CLARIFICATION_FULL_NAME = "clarification-full.md"

# Extra flags for fresh non-interactive sessions (same family as baseline-gen).
CLARIFY_EXTRA_ARGS = ["--ephemeral", "--skip-git-repo-check"]


@dataclass
class ClarifyRunResult:
    run_id: str
    status: str
    exit_code: int | None
    protocol_violation: bool
    spec_sha256_before: str | None
    spec_sha256_after: str | None
    context_sha256: str | None
    attempt_dir: Path | None
    execution_metadata_path: Path | None
    error: str
    command: tuple[str, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def specify_cli_version() -> str:
    resolved = shutil.which("specify")
    if not resolved:
        return "unknown"
    try:
        result = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    output = (result.stdout or result.stderr or "").strip()
    return output.splitlines()[0].strip() if output else "unknown"


def extract_clarification_full_text(last_message_path: Path) -> str:
    """Prefer last-message artifact; JSONL parsing deferred until smoke findings."""
    text = read_utf8(last_message_path).strip()
    if not text:
        raise ValueError(f"Empty last-message: {last_message_path}")
    return text


def load_scaffold_metadata(run_path: Path) -> dict[str, Any]:
    path = run_path / "metadata.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_condition(run: RunInfo, scaffold_meta: dict[str, Any]) -> str:
    """Condition comes from scaffold metadata when present; else RunInfo."""
    meta_condition = scaffold_meta.get("condition")
    if meta_condition:
        if meta_condition != run.condition:
            raise ValueError(
                f"Condition mismatch for {run.run_id}: "
                f"folder={run.condition} metadata={meta_condition}"
            )
        return str(meta_condition)
    return run.condition


def feature_directory_rel(root: Path, run_path: Path) -> str:
    """Path relative to repo root for SPECIFY_FEATURE_DIRECTORY."""
    resolved = run_path.resolve()
    try:
        return str(resolved.relative_to(root.resolve()))
    except ValueError:
        return str(resolved)


def context_sha256_for_run(run_path: Path, condition: str) -> str | None:
    context_path = run_path / "experiment-input" / "context.md"
    if condition == "C0":
        if context_path.exists():
            raise ValueError(f"C0 must not have context.md: {context_path}")
        return None
    if not context_path.is_file():
        raise FileNotFoundError(
            f"Condition {condition} requires context.md at {context_path}"
        )
    return sha256_file(context_path)


def write_execution_metadata(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def run_one(
    run: RunInfo,
    *,
    root: Path,
    prompt: str,
    sandbox: str = DEFAULT_CLARIFY_SANDBOX,
    approval_policy: str = DEFAULT_APPROVAL_POLICY,
    attempt: int = 1,
    ordem: int | None = None,
    codex_executable: str | None = None,
    codex_cli_version: str | None = None,
    specify_version: str | None = None,
    execute: bool = True,
    pause_after: bool = False,
    allow_experimental: bool = False,
) -> ClarifyRunResult:
    """
    Execute exactly one clarify attempt for a prepared run folder.

    Experimental US IDs under runs/ require allow_experimental=True.
    """
    if attempt < 1:
        raise ValueError(f"attempt must be >= 1, got {attempt}")
    if attempt != 1:
        # Auto-retry is not implemented; attempt=2 only when caller opts in later.
        pass

    root = root.resolve()
    run_path = run.run_path.resolve()

    # Guard: refuse accidental experimental collection unless authorized.
    experimental_runs_root = (root / "runs").resolve()
    if (
        run_path.parent == experimental_runs_root
        and run.us_id in USER_STORY_IDS
        and not allow_experimental
    ):
        raise RuntimeError(
            f"Refusing experimental run {run.run_id} without "
            f"allow_experimental=True / CLI authorization."
        )

    scaffold_meta = load_scaffold_metadata(run_path)
    condition = resolve_condition(run, scaffold_meta)
    repetition = int(scaffold_meta.get("repetition") or parse_repeticao(run.run_id))

    validate_run_inputs(RunInfo(run.run_id, run.us_id, condition, run_path), root=root)

    spec_path = run_path / "spec.md"
    if not spec_path.is_file():
        raise FileNotFoundError(f"spec.md not found: {spec_path}")

    spec_before = sha256_file(spec_path)
    context_digest = context_sha256_for_run(run_path, condition)

    executable = codex_executable or resolve_codex_executable()
    cli_version = codex_cli_version or codex_version(executable)
    spec_ver = specify_version or specify_cli_version()

    feature_rel = feature_directory_rel(root, run_path)
    env_overrides = {"SPECIFY_FEATURE_DIRECTORY": feature_rel}

    start = datetime.now().astimezone()
    metadata_txt = run_path / "metadata.txt"
    clarification_full_path = run_path / CLARIFICATION_FULL_NAME

    write_metadata(
        metadata_txt,
        {
            "Run_ID": run.run_id,
            "US_ID": run.us_id,
            "Condition": condition,
            "Repetition": str(repetition),
            "Attempt": str(attempt),
            "Ordem": str(ordem) if ordem is not None else "",
            "Model": EXPERIMENT_MODEL,
            "Reasoning effort": EXPERIMENT_REASONING_EFFORT,
            "Codex version": cli_version,
            "Specify version": spec_ver,
            "Sandbox": sandbox,
            "Approval policy": approval_policy,
            "Shuffle": "off",
            "Start": start.isoformat(timespec="seconds"),
            "Run path": str(run_path),
            "SPECIFY_FEATURE_DIRECTORY": feature_rel,
            "spec_sha256_before": spec_before,
            "Status": "Started",
        },
    )

    error_message = ""
    status = "Started"
    protocol_violation = False
    result = None
    exit_code: int | None = None
    spec_after: str | None = None
    attempt_path: Path | None = None
    exec_meta_path: Path | None = None
    command: tuple[str, ...] = ()

    try:
        print(
            f"Codex $speckit-clarify (workdir=run, feature={feature_rel}, "
            f"sandbox={sandbox}, attempt={attempt})..."
        )
        codex_started = time.monotonic()
        result = invoke_codex_exec(
            workdir=run_path,
            prompt=prompt,
            artifact_parent=run_path,
            attempt=attempt,
            model=EXPERIMENT_MODEL,
            reasoning_effort=EXPERIMENT_REASONING_EFFORT,
            sandbox=sandbox,
            approval_policy=approval_policy,
            codex_executable=executable,
            extra_args=list(CLARIFY_EXTRA_ARGS),
            env_overrides=env_overrides,
            execute=execute,
        )
        duration = time.monotonic() - codex_started
        if execute:
            print(
                f"Codex finished in "
                f"{int(duration // 60):02d}:{int(duration % 60):02d}"
            )

        exit_code = result.exit_code
        command = result.command
        attempt_path = result.stdout_path.parent
        exec_meta_path = attempt_path / EXECUTION_METADATA_NAME

        spec_after = sha256_file(spec_path) if spec_path.is_file() else None
        if spec_after != spec_before:
            protocol_violation = True
            raise RuntimeError(
                f"PROTOCOL VIOLATION: spec.md mutated during clarify "
                f"(before={spec_before}, after={spec_after}). "
                f"Artifacts preserved; no auto-repair."
            )

        if execute and result.exit_code != 0:
            raise RuntimeError(
                f"codex exec exited with code {result.exit_code}. "
                f"Check {result.stderr_path}"
            )
        if execute:
            if not result.last_message_path.is_file():
                raise FileNotFoundError("last-message.txt was not created")
            if result.last_message_path.stat().st_size == 0:
                raise ValueError("last-message.txt was created but is empty")
            write_utf8(
                clarification_full_path,
                extract_clarification_full_text(result.last_message_path),
            )

        status = "Valid"
        end = datetime.now().astimezone()
        payload = build_run_metadata_template(
            run_id=run.run_id,
            user_story_id=run.us_id,
            condition=condition,
            repetition=repetition,
            attempt=attempt,
            model=EXPERIMENT_MODEL,
            reasoning_effort=EXPERIMENT_REASONING_EFFORT,
            codex_version_str=cli_version,
            specify_version=spec_ver,
            sandbox=sandbox,
            approval_policy=approval_policy,
            started_at=result.started_at,
            finished_at=result.finished_at,
            exit_code=result.exit_code,
            workdir=str(result.workdir),
            spec_sha256_before=spec_before,
            spec_sha256_after=spec_after,
            context_sha256=context_digest,
            stdout_path=str(result.stdout_path),
            stderr_path=str(result.stderr_path),
            last_message_path=str(result.last_message_path),
            status=status,
            protocol_violation=False,
            error="",
        )
        write_execution_metadata(exec_meta_path, payload)

        write_metadata(
            metadata_txt,
            {
                "Run_ID": run.run_id,
                "US_ID": run.us_id,
                "Condition": condition,
                "Repetition": str(repetition),
                "Attempt": str(attempt),
                "Ordem": str(ordem) if ordem is not None else "",
                "Model": EXPERIMENT_MODEL,
                "Reasoning effort": EXPERIMENT_REASONING_EFFORT,
                "Codex version": cli_version,
                "Specify version": spec_ver,
                "Sandbox": sandbox,
                "Approval policy": approval_policy,
                "Shuffle": "off",
                "Start": start.isoformat(timespec="seconds"),
                "End": end.isoformat(timespec="seconds"),
                "Exit code": str(result.exit_code),
                "Run path": str(run_path),
                "SPECIFY_FEATURE_DIRECTORY": feature_rel,
                "spec_sha256_before": spec_before,
                "spec_sha256_after": spec_after or "",
                "context_sha256": context_digest or "",
                "Stdout path": str(result.stdout_path),
                "Stderr path": str(result.stderr_path),
                "Last message path": str(result.last_message_path),
                "Clarification full path": str(clarification_full_path),
                "Status": status,
            },
        )
        print(f"OK: {run.run_id}")
    except Exception as exc:  # noqa: BLE001
        error_message = str(exc)
        if protocol_violation or "PROTOCOL VIOLATION" in error_message:
            status = "ProtocolViolation"
            protocol_violation = True
        else:
            status = "Failed"
        end = datetime.now().astimezone()

        # Preserve whatever hashes/paths we have; never delete attempt artifacts.
        if result is not None:
            attempt_path = result.stdout_path.parent
            exec_meta_path = attempt_path / EXECUTION_METADATA_NAME
            command = result.command
            exit_code = result.exit_code
            if spec_after is None and spec_path.is_file():
                spec_after = sha256_file(spec_path)
            if not exec_meta_path.exists():
                payload = build_run_metadata_template(
                    run_id=run.run_id,
                    user_story_id=run.us_id,
                    condition=condition,
                    repetition=repetition,
                    attempt=attempt,
                    model=EXPERIMENT_MODEL,
                    reasoning_effort=EXPERIMENT_REASONING_EFFORT,
                    codex_version_str=cli_version,
                    specify_version=spec_ver,
                    sandbox=sandbox,
                    approval_policy=approval_policy,
                    started_at=result.started_at,
                    finished_at=result.finished_at,
                    exit_code=result.exit_code,
                    workdir=str(result.workdir),
                    spec_sha256_before=spec_before,
                    spec_sha256_after=spec_after,
                    context_sha256=context_digest,
                    stdout_path=str(result.stdout_path),
                    stderr_path=str(result.stderr_path),
                    last_message_path=str(result.last_message_path),
                    status=status,
                    protocol_violation=protocol_violation,
                    error=error_message,
                )
                write_execution_metadata(exec_meta_path, payload)

        write_metadata(
            metadata_txt,
            {
                "Run_ID": run.run_id,
                "US_ID": run.us_id,
                "Condition": condition,
                "Repetition": str(repetition),
                "Attempt": str(attempt),
                "Ordem": str(ordem) if ordem is not None else "",
                "Model": EXPERIMENT_MODEL,
                "Reasoning effort": EXPERIMENT_REASONING_EFFORT,
                "Codex version": cli_version,
                "Specify version": spec_ver,
                "Sandbox": sandbox,
                "Approval policy": approval_policy,
                "Shuffle": "off",
                "Start": start.isoformat(timespec="seconds"),
                "End": end.isoformat(timespec="seconds"),
                "Run path": str(run_path),
                "SPECIFY_FEATURE_DIRECTORY": feature_rel,
                "spec_sha256_before": spec_before,
                "spec_sha256_after": spec_after or "",
                "Status": status,
                "Error": error_message,
            },
        )
        print(f"{status.upper()}: {run.run_id}")
        print(error_message)

    if pause_after:
        time.sleep(PAUSE_BETWEEN_RUNS_SECONDS)

    return ClarifyRunResult(
        run_id=run.run_id,
        status=status,
        exit_code=exit_code,
        protocol_violation=protocol_violation,
        spec_sha256_before=spec_before,
        spec_sha256_after=spec_after,
        context_sha256=context_digest,
        attempt_dir=attempt_path,
        execution_metadata_path=exec_meta_path,
        error=error_message,
        command=command,
    )


def build_execution_row(
    run: RunInfo,
    metadata: dict[str, str],
    *,
    ordem: str | int = "",
    in_execution_order: bool = False,
) -> dict[str, object]:
    internal_status = metadata.get("Status", "")
    clarification_full_path = run.run_path / CLARIFICATION_FULL_NAME
    arquivo_saida = str(clarification_full_path) if clarification_full_path.is_file() else ""

    return {
        "Run_ID": run.run_id,
        "US_ID": run.us_id,
        "Condicao": run.condition,
        "Repeticao": parse_repeticao(run.run_id),
        "Ordem": ordem if ordem != "" else metadata.get("Ordem", ""),
        "Data_hora": metadata.get("End") or metadata.get("Start", ""),
        "Arquivo_saida": arquivo_saida,
        "Status": map_status_pt(internal_status, in_execution_order=in_execution_order),
        "Erro": metadata.get("Error", ""),
    }


def build_execution_table(root: Path | None = None) -> list[dict[str, object]]:
    root = root or get_root()
    rows: list[dict[str, object]] = []

    for run in discover_runs(runs_dir()):
        metadata = read_metadata(run.run_path / "metadata.txt")
        in_order = bool(metadata.get("Ordem"))
        rows.append(build_execution_row(run, metadata, in_execution_order=in_order))

    rows.sort(
        key=lambda row: (
            row["Ordem"] == "",
            int(row["Ordem"]) if str(row["Ordem"]).isdigit() else 999,
            str(row["Run_ID"]),
        )
    )
    return rows


def export_execution_table(
    root: Path | None = None,
    rows: list[dict[str, object]] | None = None,
) -> Path:
    table_rows = rows if rows is not None else build_execution_table(root)
    path = execution_table_path()
    export_csv(path, table_rows)
    return path


def run_all(
    root: Path | None = None,
    *,
    sandbox: str = DEFAULT_CLARIFY_SANDBOX,
    attempt: int = 1,
    allow_experimental: bool = False,
) -> list[dict[str, object]]:
    """
    Execute clarify runs in deterministic US×condition×rep order.

    Requires allow_experimental=True. Shuffle disabled. No auto-retry.
    """
    if not allow_experimental:
        raise RuntimeError(
            "run_all requires allow_experimental=True "
            "(use CLI --i-authorize-experimental-collection)."
        )
    if attempt != 1:
        pass

    root = (root or get_root()).resolve()
    prompt_file = prompt_path()

    if not runs_dir().is_dir():
        raise FileNotFoundError(f"Runs folder not found: {runs_dir()}")
    if not prompt_file.is_file():
        raise FileNotFoundError(f"Prompt not found: {prompt_file}")

    ensure_codex_available()
    codex_executable = resolve_codex_executable()
    codex_cli_version = codex_version(codex_executable)
    spec_ver = specify_cli_version()
    collected_dir().mkdir(parents=True, exist_ok=True)

    runs = discover_runs(runs_dir())
    if not runs:
        raise RuntimeError(f"No run folders found in {runs_dir()}")

    prompt = read_utf8(prompt_file)
    total_runs = len(runs)
    execution_table: list[dict[str, object]] = []
    completed_count = 0
    valid_count = 0
    failed_count = 0
    violation_count = 0

    print(
        f"\nTotal runs: {total_runs} "
        f"(expected matrix size when fully scaffolded: {EXPECTED_RUN_COUNT})"
    )
    print(
        f"Model: {EXPERIMENT_MODEL} | Reasoning: {EXPERIMENT_REASONING_EFFORT} | "
        f"Codex: {codex_cli_version} | Specify: {spec_ver} | "
        f"Sandbox: {sandbox} | Attempt: {attempt} | Shuffle: off\n"
    )

    for run_index, run in enumerate(runs, start=1):
        remaining_count = total_runs - run_index
        print("=" * 50)
        print(f"Running: {run.run_id} ({run_index}/{total_runs})")
        print(f"US: {run.us_id} | Condition: {run.condition}")
        print(
            f"Progress: done={completed_count} | remaining={remaining_count} "
            f"| valid={valid_count} | failed={failed_count} | "
            f"violations={violation_count}"
        )
        print("=" * 50)

        outcome = run_one(
            run,
            root=root,
            prompt=prompt,
            sandbox=sandbox,
            attempt=attempt,
            ordem=run_index,
            codex_executable=codex_executable,
            codex_cli_version=codex_cli_version,
            specify_version=spec_ver,
            execute=True,
            pause_after=True,
            allow_experimental=True,
        )
        if outcome.status == "Valid":
            valid_count += 1
        elif outcome.protocol_violation:
            violation_count += 1
            failed_count += 1
        else:
            failed_count += 1

        completed_count += 1
        metadata = read_metadata(run.run_path / "metadata.txt")
        execution_table.append(
            build_execution_row(run, metadata, ordem=run_index, in_execution_order=True)
        )
        export_execution_table(root, execution_table)
        print(
            f"Updated progress: done={completed_count}/{total_runs} | "
            f"remaining={total_runs - completed_count} | valid={valid_count} | "
            f"failed={failed_count} | violations={violation_count}\n"
        )

    print("\n" + "=" * 50)
    print("EXECUTION FINISHED")
    print(
        f"Total: {total_runs} | Done: {completed_count} | Valid: {valid_count} | "
        f"Failed: {failed_count} | ProtocolViolations: {violation_count}"
    )
    table_path = export_execution_table(root, execution_table)
    print(f"Execution table saved to:\n{table_path}")
    print("=" * 50)

    return execution_table


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Clarification runner (P3). Default action is safe: does not run "
            "the 72 experimental collects without explicit authorization."
        )
    )
    parser.add_argument(
        "--build-execution-table",
        action="store_true",
        help="Rebuild collected-data/execution-table.csv from run metadata only",
    )
    parser.add_argument(
        "--run-id",
        action="append",
        default=[],
        help=(
            "Execute a single experimental Run_ID under runs/ "
            "(repeatable). Requires --i-authorize-experimental-collection. "
            "Does not imply --execute-all."
        ),
    )
    parser.add_argument(
        "--execute-all",
        action="store_true",
        help="Execute all discovered runs under runs/ (requires authorization flag)",
    )
    parser.add_argument(
        "--i-authorize-experimental-collection",
        action="store_true",
        help="Required to touch experimental runs (--run-id or --execute-all)",
    )
    parser.add_argument(
        "--sandbox",
        default=DEFAULT_CLARIFY_SANDBOX,
        choices=("read-only", "workspace-write"),
        help=f"Codex sandbox (default: {DEFAULT_CLARIFY_SANDBOX})",
    )
    parser.add_argument(
        "--attempt",
        type=int,
        default=1,
        help="Attempt number (default 1; auto-retry not implemented)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.build_execution_table:
            path = export_execution_table()
            print(f"Execution table saved to: {path}")
            return 0

        if args.execute_all and args.run_id:
            print("Refusing to combine --execute-all with --run-id.", file=sys.stderr)
            return 2

        if args.run_id:
            if not args.i_authorize_experimental_collection:
                print(
                    "Refusing --run-id without "
                    "--i-authorize-experimental-collection.",
                    file=sys.stderr,
                )
                return 2
            root = get_root().resolve()
            prompt_file = prompt_path()
            if not prompt_file.is_file():
                raise FileNotFoundError(f"Prompt not found: {prompt_file}")
            ensure_codex_available()
            codex_executable = resolve_codex_executable()
            cli_version = codex_version(codex_executable)
            spec_ver = specify_cli_version()
            prompt = read_utf8(prompt_file)
            collected_dir().mkdir(parents=True, exist_ok=True)

            failures = 0
            for run_id in args.run_id:
                if run_id.startswith("SMOKE_"):
                    print(f"Refusing smoke Run_ID via experimental CLI: {run_id}", file=sys.stderr)
                    return 2
                run_path = runs_dir() / run_id
                if not run_path.is_dir():
                    raise FileNotFoundError(f"Run folder not found: {run_path}")
                us_id, condition, _rest = run_id.split("_", 2)
                run = RunInfo(run_id, us_id, condition, run_path)
                print("=" * 50)
                print(f"Authorized single run: {run_id}")
                print("=" * 50)
                outcome = run_one(
                    run,
                    root=root,
                    prompt=prompt,
                    sandbox=args.sandbox,
                    attempt=args.attempt,
                    ordem=1,
                    codex_executable=codex_executable,
                    codex_cli_version=cli_version,
                    specify_version=spec_ver,
                    execute=True,
                    pause_after=False,
                    allow_experimental=True,
                )
                if outcome.status != "Valid":
                    failures += 1
                    print(f"STOP after failure/violation on {run_id}: {outcome.status}")
                    return 1
            return 1 if failures else 0

        if args.execute_all:
            if not args.i_authorize_experimental_collection:
                print(
                    "Refusing --execute-all without "
                    "--i-authorize-experimental-collection.",
                    file=sys.stderr,
                )
                return 2
            run_all(sandbox=args.sandbox, attempt=args.attempt, allow_experimental=True)
            return 0

        print(
            "Clarification runner ready (P3). No experimental collection started.\n"
            "Use tmp/clarify-smoke/run_smoke.py for non-experimental smoke.\n"
            "Single experimental run:\n"
            "  --run-id US02_C0_R1 --i-authorize-experimental-collection\n"
            "Full matrix requires:\n"
            "  --execute-all --i-authorize-experimental-collection"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
