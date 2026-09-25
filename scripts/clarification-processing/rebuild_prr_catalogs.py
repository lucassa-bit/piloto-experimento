"""Rebuild PRR catalog CSVs from the frozen PRR workbook (no Codex).

Does NOT touch questions.csv, run-summary, outputs-check, runs/, baselines/,
or blind-id-map.csv.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
ROOT = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

from lib.io import export_csv  # noqa: E402
from lib.paths import (  # noqa: E402
    collected_dir,
    prr_gap_states_csv_path,
    prr_reference_blind_csv_path,
    prr_reference_csv_path,
    prr_xlsx_path,
)
from lib.runs import CONDITIONS, USER_STORY_IDS  # noqa: E402
from prepare_materials import (  # noqa: E402
    PRR_SHEETS,
    STATE_ANSWERED,
    STATE_OPEN,
    load_materials_sources,
    parse_prr_sheet,
)

STATE_NORMALIZE = {
    STATE_OPEN: "OPEN",
    STATE_ANSWERED: "ANSWERED",
    "Open": "OPEN",
    "Answered": "ANSWERED",
    "OPEN": "OPEN",
    "ANSWERED": "ANSWERED",
}

PRR_REFERENCE_FIELDS = [
    "user_story_id",
    "gap_id",
    "gap_text",
    "importance",
    "ref_id",
    "reference_information",
    "category",
]
PRR_BLIND_FIELDS = [
    "user_story_id",
    "gap_id",
    "gap_text",
    "reference_information",
]
PRR_STATE_FIELDS = [
    "user_story_id",
    "gap_id",
    "condition",
    "gap_state",
]


def normalize_state(raw: str | None) -> str:
    if raw is None or str(raw).strip() == "":
        raise ValueError("missing gap state in PRR")
    key = str(raw).strip()
    if key not in STATE_NORMALIZE:
        raise ValueError(f"unexpected PRR state {raw!r}")
    return STATE_NORMALIZE[key]


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Rebuild PRR CSV catalogs").parse_args(argv)
    try:
        prr_path = prr_xlsx_path()
        if not prr_path.is_file():
            raise FileNotFoundError(f"PRR workbook not found: {prr_path}")
        collected_dir().mkdir(parents=True, exist_ok=True)
        wb = openpyxl.load_workbook(prr_path, data_only=True)
        sources = load_materials_sources(wb)

        ref_rows: list[dict[str, object]] = []
        blind_rows: list[dict[str, object]] = []
        state_rows: list[dict[str, object]] = []

        for sheet_name in PRR_SHEETS:
            prr = parse_prr_sheet(wb, sheet_name, sources)
            if prr.user_story_id not in USER_STORY_IDS:
                raise ValueError(f"unexpected US: {prr.user_story_id}")
            for g in prr.gaps:
                ref_rows.append(
                    {
                        "user_story_id": prr.user_story_id,
                        "gap_id": g.gap_id,
                        "gap_text": (g.lacuna or "").strip(),
                        "importance": (g.importance or "").strip(),
                        "ref_id": (g.ref_id or "").strip(),
                        "reference_information": (g.reference_information or "").strip(),
                        "category": (g.category or "").strip(),
                    }
                )
                blind_rows.append(
                    {
                        "user_story_id": prr.user_story_id,
                        "gap_id": g.gap_id,
                        "gap_text": (g.lacuna or "").strip(),
                        "reference_information": (g.reference_information or "").strip(),
                    }
                )
                for cond in CONDITIONS:
                    state_rows.append(
                        {
                            "user_story_id": prr.user_story_id,
                            "gap_id": g.gap_id,
                            "condition": cond,
                            "gap_state": normalize_state(g.states.get(cond)),
                        }
                    )

        export_csv(prr_reference_csv_path(), ref_rows, fieldnames=PRR_REFERENCE_FIELDS)
        export_csv(
            prr_reference_blind_csv_path(), blind_rows, fieldnames=PRR_BLIND_FIELDS
        )
        export_csv(prr_gap_states_csv_path(), state_rows, fieldnames=PRR_STATE_FIELDS)
        print(f"prr-reference: {len(ref_rows)} gaps")
        print(f"prr-reference-blind: {len(blind_rows)}")
        print(f"prr-gap-states: {len(state_rows)}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
