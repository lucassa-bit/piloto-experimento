"""Generate canonical baselines/<US>/spec.md via Codex $speckit-specify.

P1: one baseline per US from user-story.md only; staging isolation; promote
to canonical path; hash metadata. Does not run clarify or scaffold.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Ensure baseline-gen/ is importable when executed as a script.
_BASELINE_GEN_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _BASELINE_GEN_DIR.parent
for _path in (str(_SCRIPTS_DIR), str(_BASELINE_GEN_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from baseline_lib import (
    assert_baseline_inputs_user_story_only,
    assert_canonical_absent_or_force,
    build_baseline_metadata,
    canonical_checklist_path,
    canonical_spec_path,
    extract_user_story_body,
    generation_dir,
    prompt_forbids_context_inputs,
    promote_staging_to_canonical,
    reject_context_paths,
    render_specify_prompt,
    sha256_file,
    staging_feature_dir,
    staging_spec_path,
    write_json,
)
from lib.codex import (
    EXPERIMENT_MODEL,
    EXPERIMENT_REASONING_EFFORT,
    codex_version,
    ensure_codex_available,
    invoke_codex_exec,
    resolve_codex_executable,
)
from lib.io import export_csv, read_utf8, write_metadata
from lib.paths import (
    baseline_generation_csv_path,
    baselines_dir,
    collected_dir,
    get_root,
    materials_dir,
    specify_prompt_path,
)
from lib.runs import USER_STORY_IDS

PAUSE_BETWEEN_RUNS_SECONDS = 3
FEATURE_JSON_PATH = Path(".specify") / "feature.json"
DEFAULT_BASELINE_SANDBOX = "workspace-write"


def parse_user_story_ids(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return USER_STORY_IDS

    selected: list[str] = []
    known = set(USER_STORY_IDS)
    for item in raw.replace(" ", "").split(","):
        if not item:
            continue
        us_id = item.upper()
        if us_id not in known:
            raise ValueError(
                f"Unknown User Story {us_id}. Expected one of: {', '.join(USER_STORY_IDS)}"
            )
        if us_id not in selected:
            selected.append(us_id)
    if not selected:
        raise ValueError("No User Story IDs provided")
    return tuple(selected)


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


def snapshot_feature_json(root: Path) -> tuple[bool, bytes | None]:
    path = root / FEATURE_JSON_PATH
    if not path.is_file():
        return False, None
    return True, path.read_bytes()


def restore_feature_json(root: Path, existed: bool, content: bytes | None) -> None:
    path = root / FEATURE_JSON_PATH
    if existed:
        assert content is not None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return
    if path.exists():
        path.unlink()


def prepare_isolated_staging(root: Path, us_id: str, *, force: bool) -> Path:
    """
    Prepare an empty Spec Kit feature staging directory for one US.

    Canonical baselines/<US>/spec.md is protected unless --force.
    Staging feature dir is reset for a clean specify invocation.
    """
    assert_canonical_absent_or_force(root, us_id, force=force)
    feature_dir = staging_feature_dir(root, us_id)
    if feature_dir.exists():
        shutil.rmtree(feature_dir)
    feature_dir.mkdir(parents=True, exist_ok=True)
    return feature_dir


def build_row(
    us_id: str,
    *,
    status: str,
    start: str = "",
    end: str = "",
    error: str = "",
    root: Path,
) -> dict[str, object]:
    spec_path = canonical_spec_path(root, us_id)
    checklist_path = canonical_checklist_path(root, us_id)
    return {
        "US_ID": us_id,
        "Status": status,
        "Start": start,
        "End": end,
        "Spec_Path": str(spec_path) if spec_path.is_file() else "",
        "Checklist_Path": str(checklist_path) if checklist_path.is_file() else "",
        "Error": error,
    }


def generate_one_baseline(
    us_id: str,
    *,
    root: Path,
    template: str,
    force: bool,
    dry_run: bool,
    codex_executable: str,
    cli_version: str,
    specify_version: str,
) -> dict[str, object]:
    story_path = assert_baseline_inputs_user_story_only(root, us_id)
    reject_context_paths([story_path])

    story_raw = read_utf8(story_path)
    story_body = extract_user_story_body(story_raw)
    story_hash = sha256_file(story_path)

    feature_rel = f"baselines/{us_id}/generation/feature"
    prompt = render_specify_prompt(
        template,
        feature_directory=feature_rel,
        user_story=story_body,
    )
    prompt_forbids_context_inputs(prompt)

    start = datetime.now(timezone.utc).astimezone()
    gen_dir = generation_dir(root, us_id)
    gen_dir.mkdir(parents=True, exist_ok=True)
    human_meta = gen_dir / "metadata.txt"

    if dry_run:
        print(f"[dry-run] source: {story_path}")
        print(f"[dry-run] staging SPECIFY_FEATURE_DIRECTORY: {feature_rel}")
        print(f"[dry-run] canonical output: {canonical_spec_path(root, us_id)}")
        print(f"[dry-run] user_story_sha256: {story_hash}")
        return build_row(
            us_id,
            status="would-create",
            start=start.isoformat(timespec="seconds"),
            root=root,
        )

    prepare_isolated_staging(root, us_id, force=force)
    existed, feature_json = snapshot_feature_json(root)

    write_metadata(
        human_meta,
        {
            "US_ID": us_id,
            "Model": EXPERIMENT_MODEL,
            "Reasoning effort": EXPERIMENT_REASONING_EFFORT,
            "Codex version": cli_version,
            "Specify version": specify_version,
            "Sandbox": DEFAULT_BASELINE_SANDBOX,
            "Source user story": str(story_path),
            "Staging feature dir": feature_rel,
            "Status": "Started",
            "Start": start.isoformat(timespec="seconds"),
        },
    )

    try:
        print(f"Codex $speckit-specify (workdir=repo root, feature={feature_rel})...")
        started_mono = time.monotonic()
        result = invoke_codex_exec(
            workdir=root,
            prompt=prompt,
            artifact_parent=gen_dir,
            attempt=1,
            model=EXPERIMENT_MODEL,
            reasoning_effort=EXPERIMENT_REASONING_EFFORT,
            sandbox=DEFAULT_BASELINE_SANDBOX,
            codex_executable=codex_executable,
            approval_policy="never",
            extra_args=["--ephemeral", "--skip-git-repo-check"],
            env_overrides={"SPECIFY_FEATURE_DIRECTORY": feature_rel},
            execute=True,
        )
        duration = time.monotonic() - started_mono
        print(f"Codex finished in {int(duration // 60):02d}:{int(duration % 60):02d}")

        if result.exit_code != 0:
            raise RuntimeError(
                f"codex exec exited with code {result.exit_code}. Check {result.stderr_path}"
            )

        generated = staging_spec_path(root, us_id)
        canonical_spec, _canonical_checklist = promote_staging_to_canonical(
            root, us_id, force=force
        )
        end = datetime.now(timezone.utc).astimezone()
        spec_hash = sha256_file(canonical_spec)

        metadata = build_baseline_metadata(
            user_story_id=us_id,
            model=EXPERIMENT_MODEL,
            reasoning_effort=EXPERIMENT_REASONING_EFFORT,
            codex_version=cli_version,
            specify_version=specify_version,
            sandbox=DEFAULT_BASELINE_SANDBOX,
            started_at=result.started_at,
            finished_at=result.finished_at,
            exit_code=result.exit_code,
            source_user_story=story_path,
            generated_spec_path=generated,
            baseline_output_path=canonical_spec,
            user_story_sha256=story_hash,
            baseline_spec_sha256=spec_hash,
            extra={
                "stdout_path": str(result.stdout_path),
                "stderr_path": str(result.stderr_path),
                "last_message_path": str(result.last_message_path),
                "attempt": result.attempt,
                "checklist_path": str(canonical_checklist_path(root, us_id)),
            },
        )
        write_json(result.stdout_path.parent / "baseline-metadata.json", metadata)

        write_metadata(
            human_meta,
            {
                "US_ID": us_id,
                "Model": EXPERIMENT_MODEL,
                "Reasoning effort": EXPERIMENT_REASONING_EFFORT,
                "Codex version": cli_version,
                "Specify version": specify_version,
                "Sandbox": DEFAULT_BASELINE_SANDBOX,
                "Source user story": str(story_path),
                "Generated spec path": str(generated),
                "Baseline output path": str(canonical_spec),
                "User story sha256": story_hash,
                "Baseline spec sha256": spec_hash,
                "Exit code": str(result.exit_code),
                "Start": start.isoformat(timespec="seconds"),
                "End": end.isoformat(timespec="seconds"),
                "Status": "Valid",
            },
        )
        print(f"OK: {us_id} -> {canonical_spec}")
        print(f"     sha256(user-story)={story_hash}")
        print(f"     sha256(spec)={spec_hash}\n")
        return build_row(
            us_id,
            status="Valid",
            start=start.isoformat(timespec="seconds"),
            end=end.isoformat(timespec="seconds"),
            root=root,
        )
    except Exception as exc:  # noqa: BLE001
        end = datetime.now(timezone.utc).astimezone()
        error_message = str(exc)
        write_metadata(
            human_meta,
            {
                "US_ID": us_id,
                "Model": EXPERIMENT_MODEL,
                "Reasoning effort": EXPERIMENT_REASONING_EFFORT,
                "Codex version": cli_version,
                "Specify version": specify_version,
                "Sandbox": DEFAULT_BASELINE_SANDBOX,
                "Source user story": str(story_path),
                "Start": start.isoformat(timespec="seconds"),
                "End": end.isoformat(timespec="seconds"),
                "Status": "Failed",
                "Error": error_message,
            },
        )
        print(f"FAILED: {us_id}")
        print(f"{error_message}\n")
        return build_row(
            us_id,
            status="Failed",
            start=start.isoformat(timespec="seconds"),
            end=end.isoformat(timespec="seconds"),
            error=error_message,
            root=root,
        )
    finally:
        restore_feature_json(root, existed, feature_json)


def run_all(
    *,
    user_story_ids: tuple[str, ...],
    force: bool,
    dry_run: bool,
    root: Path | None = None,
) -> list[dict[str, object]]:
    root = (root or get_root()).resolve()
    prompt_file = specify_prompt_path()
    user_stories_root = materials_dir()

    if not prompt_file.is_file():
        raise FileNotFoundError(f"Prompt not found: {prompt_file}")
    if not user_stories_root.is_dir():
        raise FileNotFoundError(f"Materials folder not found: {user_stories_root}")

    template = read_utf8(prompt_file)
    prompt_forbids_context_inputs(template)

    if not dry_run:
        collected_dir().mkdir(parents=True, exist_ok=True)
        baselines_dir().mkdir(parents=True, exist_ok=True)
        ensure_codex_available()

    codex_executable = "" if dry_run else resolve_codex_executable()
    cli_version = "dry-run" if dry_run else codex_version(codex_executable)
    specify_version = "dry-run" if dry_run else specify_cli_version()

    rows: list[dict[str, object]] = []
    valid_count = 0
    failed_count = 0
    blocked_count = 0

    print(f"Root: {root}")
    print(f"User Stories: {', '.join(user_story_ids)}")
    print(
        f"Model: {EXPERIMENT_MODEL} | Reasoning: {EXPERIMENT_REASONING_EFFORT} | "
        f"Codex: {cli_version} | Specify: {specify_version} | "
        f"Sandbox: {DEFAULT_BASELINE_SANDBOX}\n"
    )
    if dry_run:
        print("Mode: dry-run (no Codex invocation)\n")

    for index, us_id in enumerate(user_story_ids, start=1):
        print("=" * 50)
        print(f"Baseline: {us_id} ({index}/{len(user_story_ids)})")
        print("=" * 50)

        try:
            if canonical_spec_path(root, us_id).is_file() and not force and not dry_run:
                blocked_count += 1
                msg = (
                    f"Canonical baseline already exists: {canonical_spec_path(root, us_id)}. "
                    "Pass --force to regenerate."
                )
                print(f"BLOCKED: {msg}\n")
                rows.append(build_row(us_id, status="Blocked", error=msg, root=root))
                continue

            row = generate_one_baseline(
                us_id,
                root=root,
                template=template,
                force=force,
                dry_run=dry_run,
                codex_executable=codex_executable,
                cli_version=cli_version,
                specify_version=specify_version,
            )
            rows.append(row)
            if row["Status"] == "Valid":
                valid_count += 1
            elif row["Status"] == "Failed":
                failed_count += 1
        except FileExistsError as exc:
            blocked_count += 1
            print(f"BLOCKED: {exc}\n")
            rows.append(build_row(us_id, status="Blocked", error=str(exc), root=root))
        except Exception as exc:  # noqa: BLE001
            failed_count += 1
            print(f"FAILED: {us_id}: {exc}\n")
            rows.append(build_row(us_id, status="Failed", error=str(exc), root=root))

        if index < len(user_story_ids) and not dry_run:
            time.sleep(PAUSE_BETWEEN_RUNS_SECONDS)

    print("=" * 50)
    print("BASELINE GENERATION FINISHED")
    print(
        f"Total: {len(user_story_ids)} | Valid: {valid_count} | "
        f"Blocked: {blocked_count} | Failed: {failed_count}"
    )
    if not dry_run:
        table_path = baseline_generation_csv_path()
        export_csv(table_path, rows)
        print(f"Table: {table_path}")
    print("=" * 50)
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate baselines/<US>/spec.md from materials/<US>/user-story.md only "
            "via Codex $speckit-specify. Staging under baselines/<US>/generation/feature."
        )
    )
    parser.add_argument(
        "--us",
        dest="user_stories",
        default=None,
        help=f"Comma-separated User Story IDs (default: {','.join(USER_STORY_IDS)})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Explicitly regenerate and overwrite an existing canonical baselines/<US>/spec.md",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned actions without invoking Codex",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        user_story_ids = parse_user_story_ids(args.user_stories)
        run_all(
            user_story_ids=user_story_ids,
            force=args.force,
            dry_run=args.dry_run,
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
