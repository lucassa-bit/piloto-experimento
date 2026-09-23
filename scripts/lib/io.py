"""UTF-8 file and CSV helpers."""

from __future__ import annotations

import csv
from pathlib import Path


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_utf8(path: Path, content: str) -> None:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(normalized)


def export_csv(
    path: Path,
    rows: list[dict[str, object]],
    *,
    fieldnames: list[str] | None = None,
) -> None:
    """Write CSV with QUOTE_ALL. Empty rows still write a header when fieldnames given."""
    if not rows and not fieldnames:
        return
    if rows and fieldnames is None:
        fieldnames = list(rows[0].keys())
    assert fieldnames is not None
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def import_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_metadata(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    fields: dict[str, str] = {}
    for line in read_utf8(path).splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key.strip()] = value.strip()
    return fields


def write_metadata(path: Path, fields: dict[str, str]) -> None:
    content = "\n".join(f"{key}: {value}" for key, value in fields.items())
    write_utf8(path, content + "\n")
