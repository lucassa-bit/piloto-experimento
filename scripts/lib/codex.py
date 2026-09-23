"""Codex CLI resolution and non-interactive exec helpers.

Experimental invocations MUST pass model and reasoning effort explicitly.
Never use `codex exec resume` — each call starts a new session.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Frozen protocol defaults (also passed explicitly on every exec).
EXPERIMENT_MODEL = "gpt-5.5"
EXPERIMENT_REASONING_EFFORT = "medium"

ATTEMPT_STDOUT = "stdout.jsonl"
ATTEMPT_STDERR = "stderr.txt"
ATTEMPT_LAST_MESSAGE = "last-message.txt"
ATTEMPT_METADATA = "metadata.json"
ATTEMPT_COMMAND = "command.txt"


@dataclass(frozen=True)
class CodexExecResult:
    exit_code: int
    stdout_path: Path
    stderr_path: Path
    last_message_path: Path
    started_at: str
    finished_at: str
    attempt: int
    model: str
    reasoning_effort: str
    sandbox: str | None
    workdir: Path
    command: tuple[str, ...]
    metadata_path: Path

    def to_metadata_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "stdout_path": str(self.stdout_path),
            "stderr_path": str(self.stderr_path),
            "last_message_path": str(self.last_message_path),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "attempt": self.attempt,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "sandbox": self.sandbox,
            "workdir": str(self.workdir),
            "command": list(self.command),
        }


def resolve_codex_executable() -> str:
    if os.name == "nt":
        for candidate in ("codex.cmd", "codex.exe", "codex"):
            resolved = shutil.which(candidate)
            if resolved:
                return os.path.abspath(resolved)

    resolved = shutil.which("codex")
    if resolved:
        return os.path.abspath(resolved)

    raise RuntimeError("Command 'codex' not found. Install the Codex CLI and add it to PATH.")


def ensure_codex_available() -> str:
    return resolve_codex_executable()


def codex_version(codex_executable: str | None = None) -> str:
    executable = codex_executable or resolve_codex_executable()
    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    output = (result.stdout or result.stderr or "").strip()
    return output.splitlines()[0].strip() if output else "unknown"


def attempt_dir(parent: Path, attempt: int) -> Path:
    if attempt < 1:
        raise ValueError(f"attempt must be >= 1, got {attempt}")
    return parent / f"attempt-{attempt}"


def _dir_has_artifacts(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(path.iterdir())


def prepare_attempt_dir(parent: Path, attempt: int) -> Path:
    """
    Create attempt-N directory. Refuse if it already contains artifacts
    (attempt=1 must never be overwritten).
    """
    target = attempt_dir(parent, attempt)
    if _dir_has_artifacts(target):
        raise FileExistsError(
            f"Attempt directory already has artifacts and must not be overwritten: {target}"
        )
    target.mkdir(parents=True, exist_ok=True)
    return target


def build_codex_exec_command(
    *,
    workdir: Path,
    model: str,
    reasoning_effort: str,
    last_message_path: Path,
    sandbox: str | None,
    codex_executable: str,
    approval_policy: str | None = "never",
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build argv for a fresh Codex session (never resume).

    Global flags such as ``--ask-for-approval`` MUST appear before ``exec``.
    Do not combine ``--sandbox`` with ``--approve-for-me`` (incompatible on 0.156.1).
    """
    forbidden = {"resume", "--approve-for-me", "--dangerously-bypass-approvals-and-sandbox"}
    for arg in extra_args or ():
        if arg in forbidden or arg == "danger-full-access":
            raise ValueError(f"Forbidden Codex flag/arg for experimental runs: {arg}")

    # Global options before subcommand.
    command = [codex_executable]
    if approval_policy:
        command.extend(["--ask-for-approval", approval_policy])
    command.append("exec")
    command.extend(
        [
            "--model",
            model,
            "-c",
            f"model_reasoning_effort={reasoning_effort}",
            "--cd",
            str(workdir),
            "--json",
            "--output-last-message",
            str(last_message_path),
        ]
    )
    if sandbox:
        if sandbox == "danger-full-access":
            raise ValueError("danger-full-access sandbox is forbidden")
        command.extend(["--sandbox", sandbox])
    if extra_args:
        command.extend(extra_args)
    command.append("-")  # prompt on stdin
    return command


def invoke_codex_exec(
    *,
    workdir: Path,
    prompt: str,
    artifact_parent: Path,
    attempt: int = 1,
    model: str = EXPERIMENT_MODEL,
    reasoning_effort: str = EXPERIMENT_REASONING_EFFORT,
    sandbox: str | None = "read-only",
    approval_policy: str | None = "never",
    codex_executable: str | None = None,
    extra_args: list[str] | None = None,
    env_overrides: dict[str, str] | None = None,
    execute: bool = True,
) -> CodexExecResult:
    """
    Run (or dry-build) a new Codex exec session.

    Artifacts are written under artifact_parent/attempt-N/ and never overwrite
    an existing populated attempt directory.

    env_overrides are merged into the process environment (e.g.
    SPECIFY_FEATURE_DIRECTORY for Spec Kit 1.0.10).

    Set execute=False to only prepare paths and return the would-be command
    (exit_code=-1, no process started) — for static tests.
    """
    executable = codex_executable or resolve_codex_executable()
    attempt_path = prepare_attempt_dir(artifact_parent, attempt)

    stdout_path = attempt_path / ATTEMPT_STDOUT
    stderr_path = attempt_path / ATTEMPT_STDERR
    last_message_path = attempt_path / ATTEMPT_LAST_MESSAGE
    metadata_path = attempt_path / ATTEMPT_METADATA
    command_path = attempt_path / ATTEMPT_COMMAND

    for path in (stdout_path, stderr_path, last_message_path, metadata_path, command_path):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")

    command = build_codex_exec_command(
        workdir=workdir,
        model=model,
        reasoning_effort=reasoning_effort,
        last_message_path=last_message_path,
        sandbox=sandbox,
        approval_policy=approval_policy,
        codex_executable=executable,
        extra_args=extra_args,
    )
    command_path.write_text(" ".join(command) + "\n", encoding="utf-8")

    started = datetime.now(timezone.utc).astimezone()
    if not execute:
        finished = datetime.now(timezone.utc).astimezone()
        result = CodexExecResult(
            exit_code=-1,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            last_message_path=last_message_path,
            started_at=started.isoformat(timespec="seconds"),
            finished_at=finished.isoformat(timespec="seconds"),
            attempt=attempt,
            model=model,
            reasoning_effort=reasoning_effort,
            sandbox=sandbox,
            workdir=workdir.resolve(),
            command=tuple(command),
            metadata_path=metadata_path,
        )
        write_attempt_metadata(
            metadata_path,
            result,
            extra={
                "execute": False,
                "env_overrides": env_overrides or {},
                "approval_policy": approval_policy,
                "sandbox_requested": sandbox,
            },
        )
        return result

    env = os.environ.copy()
    env.setdefault("LC_ALL", "C.UTF-8")
    env.setdefault("LANG", "C.UTF-8")
    if env_overrides:
        env.update(env_overrides)

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as prompt_file:
        prompt_file.write(prompt)
        prompt_file_path = prompt_file.name

    try:
        with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_file, Path(prompt_file_path).open("r", encoding="utf-8") as stdin_file:
            completed = subprocess.run(
                command,
                stdin=stdin_file,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=str(workdir),
                env=env,
                check=False,
            )
        exit_code = completed.returncode
    finally:
        Path(prompt_file_path).unlink(missing_ok=True)

    finished = datetime.now(timezone.utc).astimezone()
    result = CodexExecResult(
        exit_code=exit_code,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        last_message_path=last_message_path,
        started_at=started.isoformat(timespec="seconds"),
        finished_at=finished.isoformat(timespec="seconds"),
        attempt=attempt,
        model=model,
        reasoning_effort=reasoning_effort,
        sandbox=sandbox,
        workdir=workdir.resolve(),
        command=tuple(command),
        metadata_path=metadata_path,
    )
    write_attempt_metadata(
        metadata_path,
        result,
        extra={
            "env_overrides": env_overrides or {},
            "approval_policy": approval_policy,
            "sandbox_requested": sandbox,
        },
    )
    return result


def write_attempt_metadata(
    path: Path,
    result: CodexExecResult,
    *,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = result.to_metadata_dict()
    if extra:
        payload.update(extra)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_run_metadata_template(
    *,
    run_id: str,
    user_story_id: str,
    condition: str,
    repetition: int,
    attempt: int,
    model: str = EXPERIMENT_MODEL,
    reasoning_effort: str = EXPERIMENT_REASONING_EFFORT,
    codex_version_str: str = "",
    specify_version: str = "",
    sandbox: str | None = None,
    approval_policy: str = "never",
    started_at: str = "",
    finished_at: str = "",
    exit_code: int | None = None,
    workdir: str = "",
    spec_sha256_before: str | None = None,
    spec_sha256_after: str | None = None,
    context_sha256: str | None = None,
    stdout_path: str = "",
    stderr_path: str = "",
    last_message_path: str = "",
    status: str = "",
    protocol_violation: bool | None = None,
    error: str = "",
) -> dict[str, Any]:
    """Execution metadata schema for clarify attempts (P3)."""
    return {
        "run_id": run_id,
        "user_story_id": user_story_id,
        "condition": condition,
        "repetition": repetition,
        "attempt": attempt,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "sandbox": sandbox,
        "approval_policy": approval_policy,
        "codex_version": codex_version_str,
        "specify_version": specify_version,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "spec_sha256_before": spec_sha256_before,
        "spec_sha256_after": spec_sha256_after,
        "context_sha256": context_sha256,
        "stdout_path": stdout_path,
        "stderr_path": stderr_path,
        "last_message_path": last_message_path,
        "workdir": workdir,
        "status": status,
        "protocol_violation": protocol_violation,
        "error": error,
    }
