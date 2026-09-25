"""Prepare human annotation sheets from questions.csv (no auto-mapping).

Creates PRR catalogs (via rebuild), blind-id-map, calibration set, and empty
evaluator sheets. mapped_gap_ids is always left blank.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
REPO = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from lib.io import export_csv, import_csv, write_utf8  # noqa: E402
from lib.paths import (  # noqa: E402
    annotation_dir,
    questions_csv_path,
    workspace_root,
)
from lib.runs import USER_STORY_IDS  # noqa: E402
from simple_mapping import (  # noqa: E402
    DISAGREEMENT_FIELDS,
    FORBIDDEN_EVALUATOR_COLUMNS,
    SIMPLE_EVALUATOR_FIELDS,
)

CROSSWALK_FIELDS = [
    "blind_item_id",
    "annotation_order",
    "question_uid",
    "run_id",
    "user_story_id",
    "condition",
    "repetition",
    "question_text_raw",
]

CALIBRATION_FIELDS = [
    "blind_item_id",
    "question_uid",
    "user_story_id",
]

ANNOTATION_README = """# Anotação humana — pergunta → Gap ID

## O avaliador recebe

1. `evaluator-X.csv` (ou `calibration-evaluator-X.csv` na calibração)
2. `../prr-reference-blind.csv`
3. O README em `collected-data/annotation/README.md`

## Para cada pergunta

1. Ler `question_text_raw`
2. Consultar os gaps da mesma `user_story_id` em `prr-reference-blind.csv`
3. Preencher `mapped_gap_ids`:
   - `G03` — um gap
   - `G03;G07` — vários gaps
   - `NONE` — nenhum gap correspondente
   - `REVIEW` — dúvida
4. `notes` só se precisar comentar

## Regras

- Nada é decidido automaticamente (sem LLM, embedding, similaridade ou sugestões).
- Não altere `blind_item_id`, `user_story_id` ou `question_text_raw`.
- Não use `blind-id-map.csv` (arquivo privado do pesquisador).
- Não tente descobrir condição experimental (C0/CL/…).
"""


def empty_evaluator_row(r: dict[str, str]) -> dict[str, object]:
    return {
        "blind_item_id": r["blind_item_id"],
        "user_story_id": r["user_story_id"],
        "question_text_raw": r["question_text_raw"],
        "mapped_gap_ids": "",
        "notes": "",
    }


def assert_no_leak(rows: list[dict[str, object]], label: str) -> None:
    if not rows:
        raise RuntimeError(f"{label}: empty")
    leak = set(rows[0].keys()) & FORBIDDEN_EVALUATOR_COLUMNS
    if leak:
        raise RuntimeError(f"{label}: forbidden columns {sorted(leak)}")
    if any(str(r.get("mapped_gap_ids") or "").strip() for r in rows):
        raise RuntimeError(f"{label}: mapped_gap_ids must start empty")


def build_blind_crosswalk(
    questions: list[dict[str, str]],
    *,
    seed: str,
) -> list[dict[str, object]]:
    items = list(questions)
    rng = random.Random(seed)
    rng.shuffle(items)
    rows: list[dict[str, object]] = []
    for i, q in enumerate(items, start=1):
        rows.append(
            {
                "blind_item_id": f"B{i:04d}",
                "annotation_order": i,
                "question_uid": q.get("question_uid") or q.get("Question_UID") or "",
                "run_id": q.get("run_id") or q.get("Run_ID") or "",
                "user_story_id": q.get("user_story_id") or q.get("US_ID") or "",
                "condition": q.get("condition") or q.get("Condition") or "",
                "repetition": q.get("repetition") or q.get("Repetition") or "",
                "question_text_raw": (
                    q.get("question_text_raw") or q.get("question_text") or ""
                ).strip(),
            }
        )
    return rows


def select_calibration(
    crosswalk: list[dict[str, object]],
    *,
    seed: str,
    target: int = 30,
) -> list[dict[str, object]]:
    by_us: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in crosswalk:
        by_us[str(row["user_story_id"])].append(row)
    rng = random.Random(seed + ":calibration")
    selected: list[dict[str, object]] = []
    # Round-robin stratified sample across US ids
    pools = {us: list(rows) for us, rows in by_us.items()}
    for rows in pools.values():
        rng.shuffle(rows)
    us_cycle = [us for us in USER_STORY_IDS if pools.get(us)]
    if not us_cycle:
        us_cycle = sorted(pools.keys())
    while len(selected) < min(target, len(crosswalk)) and us_cycle:
        progress = False
        next_cycle: list[str] = []
        for us in us_cycle:
            if pools[us] and len(selected) < target:
                selected.append(pools[us].pop())
                progress = True
            if pools[us]:
                next_cycle.append(us)
        us_cycle = next_cycle
        if not progress:
            break
    return [
        {
            "blind_item_id": r["blind_item_id"],
            "question_uid": r["question_uid"],
            "user_story_id": r["user_story_id"],
        }
        for r in selected
    ]


def normalize_question_rows(raw: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for idx, q in enumerate(raw, start=1):
        text = (q.get("question_text_raw") or q.get("question_text") or "").strip()
        if not text:
            continue
        run_id = q.get("run_id") or q.get("Run_ID") or ""
        order = q.get("question_order") or q.get("question_order") or str(idx)
        uid = q.get("question_uid") or q.get("Question_UID") or ""
        if not uid:
            uid = f"{run_id}_Q{order}" if run_id else f"Q{idx:04d}"
        out.append(
            {
                "question_uid": uid,
                "run_id": run_id,
                "user_story_id": q.get("user_story_id") or q.get("US_ID") or "",
                "condition": q.get("condition") or q.get("Condition") or "",
                "repetition": q.get("repetition") or q.get("Repetition") or "",
                "question_text_raw": text,
            }
        )
    return out


def prepare_annotation(*, seed: str | None = None) -> dict[str, object]:
    ws = workspace_root()
    qpath = questions_csv_path()
    if not qpath.is_file():
        raise FileNotFoundError(f"questions.csv not found: {qpath}")

    questions = normalize_question_rows(import_csv(qpath))
    if not questions:
        raise RuntimeError("questions.csv has no question rows")

    # Rebuild PRR catalogs into workspace collected-data/
    from rebuild_prr_catalogs import main as rebuild_prr_main

    rc = rebuild_prr_main([])
    if rc != 0:
        raise RuntimeError(f"rebuild_prr_catalogs failed with rc={rc}")

    order_seed = seed or hashlib.sha256(
        f"{ws}:{len(questions)}:{questions[0]['question_text_raw']}".encode()
    ).hexdigest()[:16]

    crosswalk = build_blind_crosswalk(questions, seed=order_seed)
    cal = select_calibration(crosswalk, seed=order_seed)

    ann = annotation_dir()
    private = ann / "private"
    private.mkdir(parents=True, exist_ok=True)

    export_csv(ann / "blind-id-map.csv", crosswalk, fieldnames=CROSSWALK_FIELDS)
    export_csv(private / "calibration-set.csv", cal, fieldnames=CALIBRATION_FIELDS)

    cal_ids = {r["blind_item_id"] for r in cal}
    by_id = {r["blind_item_id"]: r for r in crosswalk}
    cal_source = [by_id[r["blind_item_id"]] for r in cal]
    # Preserve calibration presentation order as selected
    full_source = sorted(crosswalk, key=lambda r: int(r["annotation_order"]))

    cal_rows = [empty_evaluator_row(r) for r in cal_source]  # type: ignore[arg-type]
    full_rows = [empty_evaluator_row(r) for r in full_source]  # type: ignore[arg-type]
    assert_no_leak(cal_rows, "calibration")
    assert_no_leak(full_rows, "evaluator")

    for name in ("calibration-evaluator-1.csv", "calibration-evaluator-2.csv"):
        export_csv(ann / name, cal_rows, fieldnames=SIMPLE_EVALUATOR_FIELDS)
    for name in ("evaluator-1.csv", "evaluator-2.csv"):
        export_csv(ann / name, full_rows, fieldnames=SIMPLE_EVALUATOR_FIELDS)
    export_csv(ann / "disagreements.csv", [], fieldnames=DISAGREEMENT_FIELDS)
    write_utf8(ann / "README.md", ANNOTATION_README)

    meta = {
        "scheme": "simple-gap-mapping-v1",
        "evaluator_fields": SIMPLE_EVALUATOR_FIELDS,
        "calibration_items": len(cal_rows),
        "full_items": len(full_rows),
        "questions": len(questions),
        "annotation_order_seed": order_seed,
        "annotation_order_seed_sha256": hashlib.sha256(order_seed.encode()).hexdigest(),
        "auto_classification": False,
        "codex_mapping": False,
        "notes": (
            "Human-only mapping. mapped_gap_ids starts empty. "
            "No embeddings/LLM/similarity. blind-id-map.csv is private."
        ),
    }
    (ann / "annotation-blind-metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Sanity: evaluator sheets must not contain experimental columns
    for sheet in ("evaluator-1.csv", "calibration-evaluator-1.csv"):
        sample = import_csv(ann / sheet)
        leak = set(sample[0].keys()) & FORBIDDEN_EVALUATOR_COLUMNS if sample else set()
        if leak:
            raise RuntimeError(f"{sheet} leaked columns: {sorted(leak)}")
        if any((r.get("mapped_gap_ids") or "").strip() for r in sample):
            raise RuntimeError(f"{sheet} has non-empty mapped_gap_ids")

    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare human annotation sheets (no auto gap mapping)"
    )
    parser.add_argument("--seed", default=None, help="Optional annotation order seed")
    args = parser.parse_args(argv)
    try:
        meta = prepare_annotation(seed=args.seed)
        print("Annotation sheets ready (human mapping only)")
        print(f"  questions: {meta['questions']}")
        print(f"  evaluator rows: {meta['full_items']}")
        print(f"  calibration rows: {meta['calibration_items']}")
        print(f"  mapped_gap_ids: empty")
        print(f"  workspace: {workspace_root()}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
