"""Structural validation of the official collection (read-only on runs/)."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
PROC = SCRIPTS / "clarification-processing"
for _p in (str(SCRIPTS), str(PROC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib.io import import_csv  # noqa: E402
from lib.paths import (  # noqa: E402
    annotation_dir,
    baseline_generation_csv_path,
    baselines_dir,
    materials_dir,
    outputs_check_csv_path,
    prr_gap_states_csv_path,
    prr_reference_blind_csv_path,
    prr_reference_csv_path,
    prr_xlsx_path,
    questions_csv_path,
    repo_root,
    run_summary_csv_path,
    runs_dir,
    validation_report_path,
    workspace_root,
)
from lib.preflight import verify_collection_integrity  # noqa: E402
from lib.runs import (  # noqa: E402
    CONDITION_CONTEXT_FILES,
    EXPECTED_RUN_COUNT,
    USER_STORY_IDS,
)
from simple_mapping import FORBIDDEN_EVALUATOR_COLUMNS  # noqa: E402

MATERIAL_FILES = (
    "user-story.md",
    "lexical.md",
    "operational.md",
    "decisional.md",
    "systemic.md",
    "total.md",
)


def _check(name: str, ok: bool, detail: str = "") -> dict[str, object]:
    return {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}


def validate_workspace() -> tuple[bool, list[dict[str, object]], str]:
    ws = workspace_root()
    checks: list[dict[str, object]] = []

    freeze_ok, freeze_msgs = verify_collection_integrity()
    checks.append(
        _check(
            "Collection integrity",
            freeze_ok,
            "; ".join(m for m in freeze_msgs if m.startswith(("CHANGED", "MISSING"))),
        )
    )

    checks.append(_check("PRR present", prr_xlsx_path().is_file(), str(prr_xlsx_path())))

    mats = materials_dir()
    mat_ok = all((mats / us / name).is_file() for us in USER_STORY_IDS for name in MATERIAL_FILES)
    checks.append(_check("Materials", mat_ok))

    base_ok = all((baselines_dir() / us / "spec.md").is_file() for us in USER_STORY_IDS)
    checks.append(_check("4 baselines", base_ok))

    csv_path = baseline_generation_csv_path()
    csv_ok = False
    csv_detail = "missing"
    if csv_path.is_file():
        rows = import_csv(csv_path)
        ids = [r.get("US_ID") for r in rows]
        csv_ok = len(rows) == 4 and set(ids) == set(USER_STORY_IDS)
        csv_detail = f"rows={len(rows)} ids={ids}"
    checks.append(_check("Baseline audit CSV", csv_ok, csv_detail))

    run_paths = sorted(p for p in runs_dir().iterdir() if p.is_dir()) if runs_dir().is_dir() else []
    checks.append(_check("72 runs present", len(run_paths) == EXPECTED_RUN_COUNT, f"count={len(run_paths)}"))

    c0_ok = True
    routing_ok = True
    for p in run_paths:
        parts = p.name.split("_")
        if len(parts) < 2:
            continue
        cond = parts[1]
        ctx = p / "experiment-input" / "context.md"
        if cond == "C0":
            if ctx.exists():
                c0_ok = False
        else:
            if not ctx.is_file():
                routing_ok = False
    checks.append(_check("C0 context absence", c0_ok))
    checks.append(_check("Context routing", routing_ok))

    executed = 0
    tech_ok_count = 0
    for p in run_paths:
        attempt = p / "attempt-1"
        if (attempt / "last-message.txt").is_file() or (attempt / "execution-metadata.json").is_file():
            executed += 1
        meta_path = attempt / "execution-metadata.json"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("exit_code") == 0:
                    tech_ok_count += 1
            except Exception:  # noqa: BLE001
                pass
    checks.append(
        _check(
            "Clarification attempts",
            executed == EXPECTED_RUN_COUNT,
            f"executed={executed}/{EXPECTED_RUN_COUNT} tech_exit0≈{tech_ok_count}",
        )
    )

    q_ok = questions_csv_path().is_file()
    n_questions = 0
    if q_ok:
        with questions_csv_path().open(encoding="utf-8-sig", newline="") as fh:
            n_questions = sum(1 for _ in csv.DictReader(fh))
    checks.append(_check("questions.csv", q_ok, f"questions={n_questions}"))
    checks.append(
        _check(
            "run-summary + outputs-check",
            run_summary_csv_path().is_file() and outputs_check_csv_path().is_file(),
        )
    )

    ann = annotation_dir()
    sheets = [
        ann / "evaluator-1.csv",
        ann / "evaluator-2.csv",
        ann / "calibration-evaluator-1.csv",
        ann / "calibration-evaluator-2.csv",
        ann / "blind-id-map.csv",
    ]
    ann_ok = all(p.is_file() for p in sheets) and prr_reference_blind_csv_path().is_file()
    checks.append(_check("Annotation sheets present", ann_ok))

    blindness_ok = True
    auto_map_absent = True
    if (ann / "evaluator-1.csv").is_file():
        rows = import_csv(ann / "evaluator-1.csv")
        if rows:
            leak = set(rows[0].keys()) & FORBIDDEN_EVALUATOR_COLUMNS
            if leak:
                blindness_ok = False
            # empty mappings are OK (pre-human); filled mappings are also OK after annotation
            # only fail if forbidden experimental columns leak
    if prr_reference_blind_csv_path().is_file():
        brows = import_csv(prr_reference_blind_csv_path())
        if brows:
            allowed = {"user_story_id", "gap_id", "gap_text", "reference_information"}
            extra = set(brows[0].keys()) - allowed
            if extra & {"importance", "ref_id", "category", "condition", "gap_state"}:
                blindness_ok = False
    checks.append(_check("Blindness", blindness_ok))
    checks.append(_check("PRR catalogs", prr_reference_csv_path().is_file() and prr_gap_states_csv_path().is_file()))

    # Mark unused to silence linters
    _ = auto_map_absent

    all_ok = all(c["status"] == "PASS" for c in checks)
    lines = [
        "# Validation report (official collection)",
        "",
        f"- repo: `{repo_root()}`",
        f"- workspace/root: `{ws}`",
        f"- questions: **{n_questions}**",
        f"- runs: {len(run_paths)}",
        f"- attempts present: {executed}",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for c in checks:
        detail = str(c["detail"]).replace("|", "\\|")
        lines.append(f"| {c['name']} | {c['status']} | {detail} |")
    lines.append("")
    lines.append(f"## Overall: {'PASS' if all_ok else 'FAIL'}")
    lines.append("")
    return all_ok, checks, "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Validate official collection").parse_args(argv)
    ok, _checks, report = validate_workspace()
    out = validation_report_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"Wrote: {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
