"""Preflight checks against the official collection (no wipe / no workspace)."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.codex import (  # noqa: E402
    EXPERIMENT_MODEL,
    EXPERIMENT_REASONING_EFFORT,
    codex_version,
    resolve_codex_executable,
)
from lib.paths import (  # noqa: E402
    audit_dir,
    collection_integrity_path,
    environment_dir,
    prompt_path,
    prr_xlsx_path,
    repo_root,
    runs_dir,
    specify_prompt_path,
)

EXPECTED_SPECIFY = "1.0.10"
EXPECTED_CODEX = "0.156.1"
REQUIRED_SKILLS = ("speckit-specify", "speckit-clarify")


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        return 1, str(exc)
    out = (result.stdout or result.stderr or "").strip()
    return result.returncode, out


def specify_version() -> str:
    resolved = shutil.which("specify")
    if not resolved:
        return ""
    code, out = _run([resolved, "--version"])
    if code != 0:
        return ""
    return out.splitlines()[0].strip() if out else ""


def find_skills(root: Path) -> list[str]:
    names: list[str] = []
    for base in (root / ".agents" / "skills", root / ".specify"):
        if not base.is_dir():
            continue
        for entry in sorted(base.iterdir()):
            if entry.is_dir() and entry.name.startswith("speckit-"):
                names.append(entry.name)
    return names


def check_python_deps() -> list[str]:
    missing: list[str] = []
    for mod in ("openpyxl",):
        if importlib.util.find_spec(mod) is None:
            missing.append(mod)
    return missing


def verify_collection_integrity() -> tuple[bool, list[str]]:
    path = collection_integrity_path()
    if not path.is_file():
        return False, [f"missing integrity file: {path}"]
    data = json.loads(path.read_text(encoding="utf-8"))
    sha = data.get("sha256") or {}
    root = repo_root()
    messages: list[str] = []
    ok = True
    for rel, expected in sha.items():
        target = root / rel
        if not target.is_file():
            ok = False
            messages.append(f"MISSING {rel}")
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != expected:
            ok = False
            messages.append(f"CHANGED {rel}")
        else:
            messages.append(f"OK {rel}")
    return ok, messages


# Back-compat alias
verify_official_freeze = verify_collection_integrity


def run_preflight(*, write_report: bool = True) -> tuple[bool, str]:
    root = repo_root()
    lines: list[str] = ["# Preflight report", ""]
    lines.append(
        f"- timestamp: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}"
    )
    lines.append(f"- repo: `{root}`")
    lines.append(f"- python: {sys.version.split()[0]}")

    critical_ok = True

    missing_deps = check_python_deps()
    if missing_deps:
        critical_ok = False
        lines.append(f"- python deps: FAIL missing {missing_deps}")
    else:
        lines.append("- python deps: OK (openpyxl)")

    spec_ver = specify_version()
    if not spec_ver:
        critical_ok = False
        lines.append("- specify: FAIL (not found)")
    else:
        ok = EXPECTED_SPECIFY in spec_ver
        critical_ok = critical_ok and ok
        lines.append(
            f"- specify: {'PASS' if ok else 'FAIL'} (`{spec_ver}`; expected {EXPECTED_SPECIFY})"
        )

    try:
        codex_exe = resolve_codex_executable()
        cver = codex_version(codex_exe)
        ok = EXPECTED_CODEX in cver
        critical_ok = critical_ok and ok
        lines.append(
            f"- codex: {'PASS' if ok else 'FAIL'} (`{cver}`; expected {EXPECTED_CODEX})"
        )
    except Exception as exc:  # noqa: BLE001
        critical_ok = False
        lines.append(f"- codex: FAIL ({exc})")

    skills = find_skills(root)
    for skill in REQUIRED_SKILLS:
        present = skill in skills
        critical_ok = critical_ok and present
        lines.append(f"- skill {skill}: {'PASS' if present else 'FAIL'}")

    env = environment_dir()
    for label, path in (
        ("environment.md", env / "environment.md"),
        ("collection-report.md", env / "collection-report.md"),
        ("clarify-prompt", prompt_path()),
        ("specify-prompt", specify_prompt_path()),
        ("PRR xlsx", prr_xlsx_path()),
        ("collection integrity", collection_integrity_path()),
        ("runs/", runs_dir()),
    ):
        ok = path.exists()
        critical_ok = critical_ok and ok
        lines.append(f"- {label}: {'PASS' if ok else 'FAIL'} (`{path}`)")

    lines.append(f"- model expected: {EXPERIMENT_MODEL}")
    lines.append(f"- reasoning expected: {EXPERIMENT_REASONING_EFFORT}")

    integ_ok, integ_msgs = verify_collection_integrity()
    lines.append(f"- collection integrity: {'PASS' if integ_ok else 'FAIL'}")
    for msg in integ_msgs:
        lines.append(f"  - {msg}")
    critical_ok = critical_ok and integ_ok

    lines.append("")
    lines.append(f"## Status: {'PASS' if critical_ok else 'FAIL'}")
    report = "\n".join(lines) + "\n"

    if write_report:
        out_dir = audit_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "preflight-report.md").write_text(report, encoding="utf-8")

    return critical_ok, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Official collection preflight")
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args(argv)
    ok, report = run_preflight(write_report=not args.no_report)
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
