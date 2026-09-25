"""Create run folders from baselines/ and materials/ (P2 scaffold).

Copies only — never regenerates baselines, contexts, or user stories.
Does not invoke Codex or $speckit-clarify.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


from lib.paths import workspace_root
from lib.runs import (
    CONDITION_CONTEXT_FILES,
    CONDITIONS,
    DEFAULT_REPETITIONS,
    EXPECTED_RUN_COUNT,
    RUN_DIR_PATTERN,
    USER_STORY_IDS,
    RunInfo,
    context_filename_for_condition,
    iter_planned_runs,
    validate_run_inputs,
)

# Official-collection baseline SHA-256 (package root). Isolated reruns use
# baselines/baseline-freeze.json written after baseline generation.
FROZEN_BASELINE_SHA256: dict[str, str] = {
    "US02": "ee9291c398af0edfda42b8420017355a54df2a71ed3ae1aac38fb014a169a4aa",
    "US08": "427e858ff781a8a8375a37eedbdaa6ecef127a821c7f2809265ef3116d547a84",
    "US18": "55f45f8e5811dc7b29d226fcb5945cd57814d3eb0b90e38a3a9921778ea13eaa",
    "US25": "0d14d17c97bccc0deb8b78229be963b75293139e7dc6aed59c0c1ef1bf118c8a",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_baseline_hashes(root: Path) -> dict[str, str]:
    local_freeze = root / "baselines" / "baseline-freeze.json"
    if local_freeze.is_file():
        payload = json.loads(local_freeze.read_text(encoding="utf-8"))
        sha = payload.get("sha256") or payload
        return {str(k): str(v) for k, v in sha.items()}
    return dict(FROZEN_BASELINE_SHA256)


def verify_frozen_baselines(root: Path) -> None:
    """Stop immediately if any baseline hash diverges from this root's freeze."""
    expected = expected_baseline_hashes(root)
    for us_id in USER_STORY_IDS:
        path = root / "baselines" / us_id / "spec.md"
        if not path.is_file():
            raise FileNotFoundError(f"Missing baseline: {path}")
        if path.is_symlink():
            raise RuntimeError(f"Baseline must be a physical file, not symlink: {path}")
        digest = sha256_file(path)
        if us_id not in expected:
            raise RuntimeError(f"No expected hash for {us_id} in baseline freeze")
        if digest != expected[us_id]:
            raise RuntimeError(
                f"Baseline hash mismatch for {us_id}: got {digest}, "
                f"expected {expected[us_id]}. STOP."
            )


def _iter_run_specs(repetitions: int) -> list[tuple[str, str, str, int]]:
    """Return (run_id, us_id, condition, repetition) for the full matrix."""
    return iter_planned_runs(repetitions)


def _remove_matching_runs(target_runs_dir: Path, *, dry_run: bool) -> int:
    removed = 0
    if not target_runs_dir.is_dir():
        return removed

    for entry in sorted(target_runs_dir.iterdir()):
        if not entry.is_dir() or not RUN_DIR_PATTERN.match(entry.name):
            continue
        removed += 1
        if dry_run:
            print(f"[dry-run] remove {entry}")
            continue
        shutil.rmtree(entry)
        print(f"Removed {entry.name}")
    return removed


def _assert_no_preexisting_runs(target_runs_dir: Path) -> None:
    """Fail by default if any Run_ID folder already exists (no silent overwrite)."""
    if not target_runs_dir.is_dir():
        return
    existing = sorted(
        entry.name
        for entry in target_runs_dir.iterdir()
        if entry.is_dir() and RUN_DIR_PATTERN.match(entry.name)
    )
    if existing:
        preview = ", ".join(existing[:8])
        more = f" (+{len(existing) - 8} more)" if len(existing) > 8 else ""
        raise FileExistsError(
            f"Refusing to scaffold: {len(existing)} pre-existing run folder(s) "
            f"under {target_runs_dir}: {preview}{more}. "
            f"Use --force only after explicit authorization (not default)."
        )


def scaffold_run(
    run_path: Path,
    us_id: str,
    condition: str,
    repetition: int,
    *,
    root: Path,
    force: bool,
    dry_run: bool,
    scaffolded_at: str,
) -> str:
    """
    Create one run folder with inputs only (no outputs / no Codex logs).

    Layout (P0 convention):
      runs/<Run_ID>/spec.md
      runs/<Run_ID>/checklists/requirements.md
      runs/<Run_ID>/experiment-input/user-story.md
      runs/<Run_ID>/experiment-input/context.md   # absent for C0
      runs/<Run_ID>/metadata.json

    Returns: 'created' | 'updated' | 'would-create' | 'would-update'
    """
    baseline_dir = root / "baselines" / us_id
    materials_dir = root / "materials" / us_id
    if condition not in CONDITIONS:
        raise ValueError(f"Unknown condition for scaffold: {condition}")
    if condition == "C0":
        context_source_name = None
    else:
        context_source_name = context_filename_for_condition(condition)
        if CONDITION_CONTEXT_FILES.get(condition) != context_source_name:
            raise ValueError(
                f"Internal mapping error for {condition}: expected "
                f"{CONDITION_CONTEXT_FILES.get(condition)}, got {context_source_name}"
            )

    baseline_spec = baseline_dir / "spec.md"
    user_story_src = materials_dir / "user-story.md"
    required = [
        baseline_spec,
        baseline_dir / "checklists" / "requirements.md",
        user_story_src,
    ]
    if context_source_name:
        required.append(materials_dir / context_source_name)

    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing source files for {run_path.name}:\n- " + "\n- ".join(missing)
        )

    baseline_digest = sha256_file(baseline_spec)
    expected_baseline = expected_baseline_hashes(root)[us_id]
    if baseline_digest != expected_baseline:
        raise RuntimeError(
            f"Baseline hash mismatch for {us_id} while scaffolding {run_path.name}: "
            f"got {baseline_digest}, expected {expected_baseline}. STOP."
        )

    user_story_digest = sha256_file(user_story_src)
    context_source_rel: str | None = None
    context_digest: str | None = None
    if context_source_name:
        context_src = materials_dir / context_source_name
        context_source_rel = f"materials/{us_id}/{context_source_name}"
        context_digest = sha256_file(context_src)

    exists = run_path.is_dir()
    if exists and not force:
        raise FileExistsError(
            f"Run folder already exists (refusing overwrite): {run_path}. "
            f"Pass --force only with explicit authorization."
        )
    if dry_run:
        return "would-update" if exists else "would-create"

    if exists and force:
        shutil.rmtree(run_path)

    experiment_input = run_path / "experiment-input"
    checklists = run_path / "checklists"
    experiment_input.mkdir(parents=True, exist_ok=True)
    checklists.mkdir(parents=True, exist_ok=True)

    # Cópias físicas literais — sem symlink.
    dest_spec = run_path / "spec.md"
    shutil.copy2(baseline_spec, dest_spec)
    if dest_spec.is_symlink():
        raise RuntimeError(f"spec.md must not be a symlink: {dest_spec}")
    copied_digest = sha256_file(dest_spec)
    if copied_digest != expected_baseline:
        raise RuntimeError(
            f"Copied spec hash mismatch for {run_path.name}: "
            f"got {copied_digest}, expected {expected_baseline}. STOP."
        )

    shutil.copy2(
        baseline_dir / "checklists" / "requirements.md",
        checklists / "requirements.md",
    )
    dest_story = experiment_input / "user-story.md"
    shutil.copy2(user_story_src, dest_story)
    if sha256_file(dest_story) != user_story_digest:
        raise RuntimeError(f"user-story copy mismatch for {run_path.name}")

    context_path = experiment_input / "context.md"
    if condition == "C0":
        if context_path.exists():
            context_path.unlink()
    else:
        assert context_source_name is not None
        source = materials_dir / context_source_name
        shutil.copy2(source, context_path)
        if context_path.is_symlink():
            raise RuntimeError(f"context.md must not be a symlink: {context_path}")
        if context_path.read_bytes() != source.read_bytes():
            raise RuntimeError(
                f"Failed literal copy of {source} -> {context_path}"
            )

    # Metadados estáticos do scaffold apenas (sem campos de execução).
    metadata = {
        "run_id": run_path.name,
        "user_story_id": us_id,
        "condition": condition,
        "repetition": repetition,
        "baseline_source": f"baselines/{us_id}/spec.md",
        "baseline_sha256": copied_digest,
        "user_story_source": f"materials/{us_id}/user-story.md",
        "user_story_sha256": user_story_digest,
        "context_source": context_source_rel,
        "context_sha256": context_digest,
        "scaffolded_at": scaffolded_at,
    }
    (run_path / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return "updated" if exists else "created"


def scaffold_all(
    *,
    repetitions: int,
    clean: bool,
    force: bool,
    dry_run: bool,
    root: Path | None = None,
) -> int:
    root = (root or workspace_root()).resolve()
    target_runs_dir = root / "runs"

    if repetitions < 1:
        raise ValueError("repetitions must be >= 1")

    specs = _iter_run_specs(repetitions)
    print(f"Root: {root}")
    print(f"Runs dir: {target_runs_dir}")
    print(
        f"Matrix: {len(USER_STORY_IDS)} US × {len(CONDITIONS)} conditions × "
        f"{repetitions} repetitions = {len(specs)} runs"
    )
    if repetitions == DEFAULT_REPETITIONS and len(specs) != EXPECTED_RUN_COUNT:
        raise ValueError(
            f"Planned run count {len(specs)} != expected {EXPECTED_RUN_COUNT}"
        )

    verify_frozen_baselines(root)
    print("Frozen baseline hashes: OK")

    if dry_run:
        print("Mode: dry-run (no filesystem changes)")
    print()

    if clean:
        # Hard stop: never wipe official (or any) runs matrix automatically.
        existing = []
        if target_runs_dir.is_dir():
            existing = [
                p.name
                for p in target_runs_dir.iterdir()
                if p.is_dir() and RUN_DIR_PATTERN.match(p.name)
            ]
        if existing:
            raise RuntimeError(
                f"--clean refused: {len(existing)} run folders already exist under "
                f"{target_runs_dir}. Official runs/ must not be deleted by scripts."
            )
        print("Clean requested but nothing to remove (runs/ empty of matching IDs)\n")
    elif not force and not dry_run:
        _assert_no_preexisting_runs(target_runs_dir)

    if not dry_run:
        target_runs_dir.mkdir(parents=True, exist_ok=True)

    counts = {
        "created": 0,
        "updated": 0,
        "would-create": 0,
        "would-update": 0,
    }

    scaffolded_at = datetime.now().astimezone().isoformat(timespec="seconds")

    for run_id, us_id, condition, repetition in specs:
        run_path = target_runs_dir / run_id
        action = scaffold_run(
            run_path,
            us_id,
            condition,
            repetition,
            root=root,
            force=force or clean,
            dry_run=dry_run,
            scaffolded_at=scaffolded_at,
        )
        if dry_run and clean:
            action = "would-create"
        counts[action] += 1
        if action in {"created", "updated", "would-create", "would-update"}:
            print(f"{action:12} {run_id}")

    if not dry_run:
        for run_id, us_id, condition, _repetition in specs:
            validate_run_inputs(
                RunInfo(run_id, us_id, condition, target_runs_dir / run_id),
                root=root,
            )
        # Reconfirmar baselines congelados após writes (isolation).
        verify_frozen_baselines(root)

    print("\nSummary")
    for key, value in counts.items():
        if value:
            print(f"  {key}: {value}")
    print(f"  total planned: {len(specs)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Scaffold clarification run folders from baselines/ and materials/. "
            f"Default matrix uses {DEFAULT_REPETITIONS} repetitions."
        )
    )
    parser.add_argument(
        "-n",
        "--repetitions",
        type=int,
        default=DEFAULT_REPETITIONS,
        help=f"Repetitions per US×condition (default: {DEFAULT_REPETITIONS})",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help=(
            "FORBIDDEN on the official collection. Refuses if runs/ already has "
            "experimental folders. Kept only for dry-run planning messages."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite inputs inside an existing run folder (does not delete other runs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show actions without writing or deleting anything",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return scaffold_all(
            repetitions=args.repetitions,
            clean=args.clean,
            force=args.force,
            dry_run=args.dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
