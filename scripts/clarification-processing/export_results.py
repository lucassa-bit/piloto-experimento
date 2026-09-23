"""Export adjudicated sheets from results/emerging-results.xlsx to collected-data/."""

from __future__ import annotations

import csv
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
XLSX_PATH = REPO_ROOT / "results" / "emerging-results.xlsx"
OUTPUT_DIR = REPO_ROOT / "collected-data"

EXPORTS = {
    "Gap_presence": "gaps_normalized.csv",
    "adjudication": "questions_adjudicated.csv",
    "Comparations": "gap_comparisons.csv",
    "reference": "gap_reference.csv",
}


def export_sheet(sheet_name: str, output_name: str) -> int:
    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True, data_only=True)
    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return 0

    headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
    data_rows: list[dict[str, str]] = []

    for row in rows[1:]:
        if not any(cell is not None and str(cell).strip() for cell in row):
            continue
        record = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            value = row[index] if index < len(row) else None
            record[header] = "" if value is None else str(value).strip()
        data_rows.append(record)

    output_path = OUTPUT_DIR / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(data_rows)

    return len(data_rows)


def main() -> int:
    if not XLSX_PATH.is_file():
        raise FileNotFoundError(f"Workbook not found: {XLSX_PATH}")

    for sheet_name, output_name in EXPORTS.items():
        count = export_sheet(sheet_name, output_name)
        print(f"{sheet_name} -> collected-data/{output_name} ({count} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
