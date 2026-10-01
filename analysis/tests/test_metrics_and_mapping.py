"""Unit tests for mapping, matrix, and metrics (synthetic fixtures)."""

from __future__ import annotations

import pandas as pd
import pytest

from analysis import config
from analysis.src.mappings import build_final_mapping, explode_question_gap_mapping, normalize_gap_ids
from analysis.src.matrices import build_gap_run_matrix
from analysis.src.metrics import gap_recall, miss_rate, occurrence_rate, requery_rate
from analysis.src.validation import AnalysisValidationError


def _blind(*ids: str) -> pd.DataFrame:
    rows = []
    for i, bid in enumerate(ids, start=1):
        rows.append(
            {
                "blind_item_id": bid,
                "question_uid": f"US01_C0_R1_Q{i:02d}",
                "run_id": "US01_C0_R1",
                "user_story_id": "US01",
                "condition": "C0",
                "repetition": "1",
                "question_order": str(i),
                "question_text_raw": f"q{i}",
            }
        )
    return pd.DataFrame(rows)


def _eval(mapping: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"blind_item_id": k, "mapped_gap_ids": v, "user_story_id": "US01", "question_text_raw": "", "notes": ""}
            for k, v in mapping.items()
        ]
    )


def test_normalize_multi_and_none():
    assert normalize_gap_ids("G03;G07") == "G03;G07"
    assert normalize_gap_ids("NONE") == "NONE"
    assert normalize_gap_ids(" G01 ; G01 ") == "G01"


def test_direct_agreement(prr_reference):
    blind = _blind("B1", "B2")
    e1 = _eval({"B1": "G01", "B2": "NONE"})
    e2 = _eval({"B1": "G01", "B2": "NONE"})
    disag = pd.DataFrame(columns=["blind_item_id", "final_gap_ids"])
    final = build_final_mapping(
        blind_id_map=blind,
        evaluator_1=e1,
        evaluator_2=e2,
        disagreements=disag,
        prr_reference=prr_reference,
        validate=True,
        pilot_asserts=False,
    )
    assert list(final["mapping_source"]) == [config.SOURCE_DIRECT, config.SOURCE_DIRECT]
    assert list(final["final_gap_ids"]) == ["G01", "NONE"]


def test_adjudicated_mapping(prr_reference):
    blind = _blind("B1")
    e1 = _eval({"B1": "G01"})
    e2 = _eval({"B1": "G02"})
    disag = pd.DataFrame([{"blind_item_id": "B1", "final_gap_ids": "G01;G02"}])
    final = build_final_mapping(
        blind_id_map=blind,
        evaluator_1=e1,
        evaluator_2=e2,
        disagreements=disag,
        prr_reference=prr_reference,
        validate=True,
        pilot_asserts=False,
    )
    assert final.iloc[0]["mapping_source"] == config.SOURCE_ADJUDICATION
    assert final.iloc[0]["final_gap_ids"] == "G01;G02"


def test_multi_gap_explode(prr_reference):
    blind = _blind("B1")
    e1 = _eval({"B1": "G01;G02"})
    e2 = e1.copy()
    final = build_final_mapping(
        blind_id_map=blind,
        evaluator_1=e1,
        evaluator_2=e2,
        disagreements=pd.DataFrame(columns=["blind_item_id", "final_gap_ids"]),
        prr_reference=prr_reference,
        pilot_asserts=False,
    )
    qgm = explode_question_gap_mapping(final)
    assert len(qgm) == 2
    assert set(qgm["mapped_gap_id"]) == {"G01", "G02"}


def test_none_preserved(prr_reference):
    blind = _blind("B1")
    e = _eval({"B1": "NONE"})
    final = build_final_mapping(
        blind_id_map=blind,
        evaluator_1=e,
        evaluator_2=e,
        disagreements=pd.DataFrame(columns=["blind_item_id", "final_gap_ids"]),
        prr_reference=prr_reference,
        pilot_asserts=False,
    )
    qgm = explode_question_gap_mapping(final)
    assert len(qgm) == 1
    assert qgm.iloc[0]["mapped_gap_id"] == "NONE"


def test_nonexistent_gap_fails(prr_reference):
    blind = _blind("B1")
    e = _eval({"B1": "G99"})
    with pytest.raises(AnalysisValidationError):
        build_final_mapping(
            blind_id_map=blind,
            evaluator_1=e,
            evaluator_2=e,
            disagreements=pd.DataFrame(columns=["blind_item_id", "final_gap_ids"]),
            prr_reference=prr_reference,
            pilot_asserts=False,
        )


def test_divergence_without_adjudication_fails(prr_reference):
    blind = _blind("B1")
    e1 = _eval({"B1": "G01"})
    e2 = _eval({"B1": "G02"})
    with pytest.raises(AnalysisValidationError):
        build_final_mapping(
            blind_id_map=blind,
            evaluator_1=e1,
            evaluator_2=e2,
            disagreements=pd.DataFrame(columns=["blind_item_id", "final_gap_ids"]),
            prr_reference=prr_reference,
            pilot_asserts=False,
        )


def test_gap_run_recognized_and_counts(prr_reference, prr_gap_states, run_summary):
    qgm = pd.DataFrame(
        [
            {
                "blind_item_id": "B1",
                "question_uid": "x",
                "run_id": "US01_C0_R1",
                "user_story_id": "US01",
                "condition": "C0",
                "repetition": "1",
                "question_order": "1",
                "question_text_raw": "q",
                "mapped_gap_id": "G01",
                "mapping_source": config.SOURCE_DIRECT,
            },
            {
                "blind_item_id": "B2",
                "question_uid": "y",
                "run_id": "US01_C0_R1",
                "user_story_id": "US01",
                "condition": "C0",
                "repetition": "1",
                "question_order": "2",
                "question_text_raw": "q2",
                "mapped_gap_id": "G01",
                "mapping_source": config.SOURCE_DIRECT,
            },
            {
                "blind_item_id": "B3",
                "question_uid": "z",
                "run_id": "US01_C0_R1",
                "user_story_id": "US01",
                "condition": "C0",
                "repetition": "1",
                "question_order": "3",
                "question_text_raw": "q3",
                "mapped_gap_id": "NONE",
                "mapping_source": config.SOURCE_DIRECT,
            },
        ]
    )
    matrix = build_gap_run_matrix(
        question_gap_mapping=qgm,
        prr_reference=prr_reference,
        prr_gap_states=prr_gap_states,
        run_summary=run_summary,
        validate=True,
        pilot_asserts=False,
    )
    # US01 has 2 gaps × 3 conditions × 2 reps; US02 has 1 × 3 × 2
    assert len(matrix) == (2 * 3 * 2) + (1 * 3 * 2)
    row = matrix[(matrix["run_id"] == "US01_C0_R1") & (matrix["gap_id"] == "G01")].iloc[0]
    assert int(row["recognized"]) == 1
    assert int(row["question_count_for_gap"]) == 2
    row2 = matrix[(matrix["run_id"] == "US01_C0_R1") & (matrix["gap_id"] == "G02")].iloc[0]
    assert int(row2["recognized"]) == 0
    assert int(row2["question_count_for_gap"]) == 0
    assert (matrix["gap_id"] != "NONE").all()


def test_gap_recall_and_miss_rate():
    matrix = pd.DataFrame(
        [
            {"condition": "C0", "gap_state": "OPEN", "recognized": 1, "importance": "N", "gap_category": "A", "user_story_id": "US01"},
            {"condition": "C0", "gap_state": "OPEN", "recognized": 0, "importance": "N", "gap_category": "A", "user_story_id": "US01"},
            {"condition": "C0", "gap_state": "OPEN", "recognized": 1, "importance": "N", "gap_category": "A", "user_story_id": "US01"},
        ]
    )
    g = gap_recall(matrix, conditions=["C0"])
    assert g.iloc[0]["gap_recall"] == pytest.approx(2 / 3)
    m = miss_rate(matrix, conditions=["C0"])
    assert m.iloc[0]["miss_rate"] == pytest.approx(1 / 3)
    assert m.iloc[0]["miss_rate"] == pytest.approx(1 - g.iloc[0]["gap_recall"])


def test_requery_rate():
    matrix = pd.DataFrame(
        [
            {"condition": "CT", "gap_state": "ANSWERED", "recognized": 1, "user_story_id": "US01", "gap_category": "A"},
            {"condition": "CT", "gap_state": "ANSWERED", "recognized": 0, "user_story_id": "US01", "gap_category": "A"},
        ]
    )
    r = requery_rate(matrix, conditions=["CT"])
    assert r.iloc[0]["requery_rate"] == pytest.approx(0.5)


def test_condition_without_open_is_na():
    matrix = pd.DataFrame(
        [
            {"condition": "CT", "gap_state": "ANSWERED", "recognized": 1, "user_story_id": "US01", "gap_category": "A", "importance": "N"},
        ]
    )
    g = gap_recall(matrix, conditions=["CT"], gap_state="OPEN", groupby=["condition"])
    assert g.empty or (g.iloc[0]["gap_recall"] is None if not g.empty else True)
    # explicit empty slice
    g2 = gap_recall(matrix, conditions=["CT"], gap_state="OPEN")
    assert g2.iloc[0]["gap_recall"] is None
    assert g2.iloc[0]["open_gaps"] == 0


def test_occurrence_rate_arbitrary_repetitions():
    rows = []
    for rep in (1, 2, 3, 4, 5):
        rows.append(
            {
                "user_story_id": "US01",
                "gap_id": "G01",
                "condition": "C0",
                "repetition": rep,
                "gap_state": "OPEN",
                "recognized": 1 if rep <= 2 else 0,
            }
        )
    matrix = pd.DataFrame(rows)
    occ = occurrence_rate(matrix)
    assert occ.iloc[0]["repetitions"] == 5
    assert occ.iloc[0]["occurrences"] == 2
    assert occ.iloc[0]["occurrence_rate"] == pytest.approx(2 / 5)

    occ3 = occurrence_rate(matrix, expected_repetitions=5)
    assert occ3.iloc[0]["occurrence_rate"] == pytest.approx(0.4)
