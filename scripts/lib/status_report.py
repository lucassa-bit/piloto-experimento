"""Read-only status for the official collection."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.paths import (  # noqa: E402
    annotation_dir,
    baselines_dir,
    materials_dir,
    prr_xlsx_path,
    questions_csv_path,
    repo_root,
    runs_dir,
)
from lib.runs import EXPECTED_RUN_COUNT, USER_STORY_IDS  # noqa: E402


def status_lines() -> list[str]:
    root = repo_root()
    mats = materials_dir()
    mat_ok = all((mats / us / "user-story.md").is_file() for us in USER_STORY_IDS)
    base_n = sum(1 for us in USER_STORY_IDS if (baselines_dir() / us / "spec.md").is_file())
    run_dirs = [p for p in runs_dir().iterdir() if p.is_dir()] if runs_dir().is_dir() else []
    executed = sum(
        1
        for p in run_dirs
        if (p / "attempt-1" / "last-message.txt").is_file()
        or (p / "attempt-1" / "execution-metadata.json").is_file()
    )
    tech = 0
    for p in run_dirs:
        meta = p / "attempt-1" / "execution-metadata.json"
        if meta.is_file():
            try:
                if json.loads(meta.read_text(encoding="utf-8")).get("exit_code") == 0:
                    tech += 1
            except Exception:  # noqa: BLE001
                pass
    n_q = 0
    if questions_csv_path().is_file():
        with questions_csv_path().open(encoding="utf-8-sig", newline="") as fh:
            n_q = sum(1 for _ in csv.DictReader(fh))
    ann = annotation_dir()
    sheets_ready = (ann / "evaluator-1.csv").is_file() and (ann / "evaluator-2.csv").is_file()
    mapped = 0
    if sheets_ready:
        with (ann / "evaluator-1.csv").open(encoding="utf-8-sig", newline="") as fh:
            mapped = sum(1 for r in csv.DictReader(fh) if (r.get("mapped_gap_ids") or "").strip())

    return [
        f"Repo              {root}",
        f"PRR               {'OK' if prr_xlsx_path().is_file() else 'MISSING'}",
        f"Materials         {'OK' if mat_ok else 'MISSING'}",
        f"Baselines         {base_n}/4",
        f"Runs              {len(run_dirs)}/{EXPECTED_RUN_COUNT}",
        f"Attempts          {executed}/{EXPECTED_RUN_COUNT}",
        f"Technical success {tech}/{EXPECTED_RUN_COUNT}",
        f"Questions         {n_q}",
        f"Annotation sheets {'READY' if sheets_ready else 'NOT READY'}",
        f"Mapped (eval-1)   {mapped}/{n_q if n_q else '?'}",
    ]


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Official collection status").parse_args(argv)
    print("\n".join(status_lines()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
