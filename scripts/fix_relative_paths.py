"""Convert <REPO_ROOT> placeholders to repository-relative paths."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEXT_EXTENSIONS = {".txt", ".csv", ".md", ".log"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}


def to_relative_paths(text: str) -> str:
    updated = text.replace("<REPO_ROOT>\\", "").replace("<REPO_ROOT>/", "")
    return updated.replace("\\", "/")


def main() -> int:
    changed: list[str] = []

    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if path.name in {"anonymize_paths.py", "fix_relative_paths.py"}:
            continue

        try:
            original = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        updated = to_relative_paths(original)
        if updated == original:
            continue

        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated)
        changed.append(str(path.relative_to(REPO_ROOT)))

    print(f"Updated {len(changed)} files")
    for item in changed:
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
