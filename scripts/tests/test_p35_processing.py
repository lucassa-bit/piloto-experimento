#!/usr/bin/env python3
"""P3.5 unit tests: check_outputs + extract_questions (no Codex)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "check-outputs"))
sys.path.insert(0, str(SCRIPTS / "clarification-processing"))

import check_outputs as chk  # noqa: E402
import extract_questions as exq  # noqa: E402


def _write_attempt(
    run_path: Path,
    *,
    run_id: str,
    user_story_id: str = "SMOKE",
    condition: str = "C0",
    repetition: int = 1,
    attempt: int = 1,
    exit_code: int = 0,
    spec_before: str = "aaa",
    spec_after: str = "aaa",
    context_sha256: str | None = None,
    last_message: str = "",
    protocol_violation: bool = False,
    model: str = "gpt-5.5",
    reasoning: str = "medium",
    sandbox: str = "read-only",
    approval: str = "never",
) -> Path:
    attempt_path = run_path / f"attempt-{attempt}"
    attempt_path.mkdir(parents=True, exist_ok=True)
    (run_path / "experiment-input").mkdir(parents=True, exist_ok=True)
    (run_path / "spec.md").write_text("spec\n", encoding="utf-8")
    (run_path / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "user_story_id": user_story_id,
                "condition": condition,
                "repetition": repetition,
                "context_sha256": context_sha256,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    meta = {
        "run_id": run_id,
        "user_story_id": user_story_id,
        "condition": condition,
        "repetition": repetition,
        "attempt": attempt,
        "model": model,
        "reasoning_effort": reasoning,
        "sandbox": sandbox,
        "approval_policy": approval,
        "exit_code": exit_code,
        "spec_sha256_before": spec_before,
        "spec_sha256_after": spec_after,
        "context_sha256": context_sha256,
        "protocol_violation": protocol_violation,
        "status": "Valid" if exit_code == 0 and not protocol_violation else "Failed",
        "error": "",
    }
    (attempt_path / "execution-metadata.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    (attempt_path / "stdout.jsonl").write_text(
        '{"type":"turn.completed"}\n', encoding="utf-8"
    )
    (attempt_path / "stderr.txt").write_text("", encoding="utf-8")
    (attempt_path / "last-message.txt").write_text(last_message, encoding="utf-8")
    return attempt_path


FOUR_QUESTIONS = """1. [NEEDS CLARIFICATION] What exact order statuses qualify as “ready” for printing, and which statuses must block printing?

2. [NEEDS CLARIFICATION] When a packing slip is reprinted, should the system record an audit event, display a “reprint” marker, or limit who can reprint?

3. [NEEDS CLARIFICATION] If the printer is unavailable, should the system generate a downloadable/previewable slip, queue the print job, or fail with an error?

4. [NEEDS CLARIFICATION] Besides order identifier and item quantities, what item details must appear on the packing slip, such as SKU, item name, location/bin, or barcode?
"""


class TestParserFixtures(unittest.TestCase):
    def test_a_four_numbered(self) -> None:
        qs, parse, clar = exq.parse_questions_from_last_message(FOUR_QUESTIONS)
        self.assertEqual(parse, exq.PARSE_OK)
        self.assertEqual(clar, exq.HAS_QUESTIONS)
        self.assertEqual(len(qs), 4)
        self.assertTrue(qs[0].startswith("[NEEDS CLARIFICATION] What exact"))
        self.assertTrue(qs[3].endswith("barcode?"))

    def test_b_one_question(self) -> None:
        text = "1. [NEEDS CLARIFICATION] Only one gap remains?\n"
        qs, parse, clar = exq.parse_questions_from_last_message(text)
        self.assertEqual(len(qs), 1)
        self.assertEqual(parse, exq.PARSE_OK)
        self.assertEqual(clar, exq.HAS_QUESTIONS)

    def test_c_zero_questions(self) -> None:
        text = "NO_CLARIFICATION_NEEDED\n"
        qs, parse, clar = exq.parse_questions_from_last_message(text)
        self.assertEqual(qs, [])
        self.assertEqual(parse, exq.PARSE_OK)
        self.assertEqual(clar, exq.NO_CLARIFICATION_NEEDED)

    def test_d_multiline_question(self) -> None:
        text = (
            "1. [NEEDS CLARIFICATION] First line of the question\n"
            "   continues on the next line with more detail?\n\n"
            "2. [NEEDS CLARIFICATION] Second question alone?\n"
        )
        qs, parse, clar = exq.parse_questions_from_last_message(text)
        self.assertEqual(parse, exq.PARSE_OK)
        self.assertEqual(len(qs), 2)
        self.assertIn("\n", qs[0])
        self.assertIn("continues on the next line", qs[0])
        self.assertTrue(qs[1].startswith("[NEEDS CLARIFICATION] Second"))

    def test_e_malformed_review_required(self) -> None:
        text = (
            "Here are some unclear bits [NEEDS CLARIFICATION] but this is not a list "
            "and we cannot confidently split questions without structure."
        )
        qs, parse, clar = exq.parse_questions_from_last_message(text)
        self.assertEqual(qs, [])
        self.assertEqual(parse, exq.PARSE_REVIEW_REQUIRED)

    def test_h_marker_blocks_without_numbering(self) -> None:
        text = (
            "[NEEDS CLARIFICATION] What supported region or ZIP code format should the feature accept?\n\n"
            "[NEEDS CLARIFICATION] What search radius should define “nearby” recycling facilities?\n\n"
            "[NEEDS CLARIFICATION] What facility data source should be used?\n\n"
            "[NEEDS CLARIFICATION] Which facility details are required beyond name?\n\n"
            "[NEEDS CLARIFICATION] How should distance be calculated and displayed?\n"
        )
        qs, parse, clar = exq.parse_questions_from_last_message(text)
        self.assertEqual(parse, exq.PARSE_OK)
        self.assertEqual(clar, exq.HAS_QUESTIONS)
        self.assertEqual(len(qs), 5)
        self.assertTrue(qs[0].startswith("[NEEDS CLARIFICATION] What supported"))
        self.assertTrue(qs[4].startswith("[NEEDS CLARIFICATION] How should distance"))

    def test_i_marker_multiline_block(self) -> None:
        text = (
            "[NEEDS CLARIFICATION] First line of an unnumbered question\n"
            "continues here with more detail about the gap?\n\n"
            "[NEEDS CLARIFICATION] Second standalone question?\n"
        )
        qs, parse, clar = exq.parse_questions_from_last_message(text)
        self.assertEqual(parse, exq.PARSE_OK)
        self.assertEqual(len(qs), 2)
        self.assertIn("\n", qs[0])
        self.assertIn("continues here", qs[0])
        self.assertTrue(qs[0].startswith("[NEEDS CLARIFICATION]"))

    def test_j_ambiguous_consecutive_markers(self) -> None:
        text = (
            "[NEEDS CLARIFICATION] One? [NEEDS CLARIFICATION] Two on the same line?\n"
        )
        qs, parse, clar = exq.parse_questions_from_last_message(text)
        self.assertEqual(qs, [])
        self.assertEqual(parse, exq.PARSE_REVIEW_REQUIRED)

    def test_k_prose_without_marker(self) -> None:
        text = "The specification looks mostly fine but a few areas remain vague.\n"
        qs, parse, clar = exq.parse_questions_from_last_message(text)
        self.assertEqual(qs, [])
        self.assertEqual(parse, exq.PARSE_REVIEW_REQUIRED)

    def test_l_numbered_format_still_works(self) -> None:
        qs, parse, clar = exq.parse_questions_from_last_message(FOUR_QUESTIONS)
        self.assertEqual(parse, exq.PARSE_OK)
        self.assertEqual(len(qs), 4)
        self.assertEqual(exq.PARSER_VERSION, 2)


class TestUs02ClR2RealArtifact(unittest.TestCase):
    def test_marker_blocks_parse_five(self) -> None:
        path = (
            ROOT
            / "runs"
            / "US02_CL_R2"
            / "attempt-1"
            / "last-message.txt"
        )
        if not path.is_file():
            self.skipTest("US02_CL_R2 attempt missing")
        text = path.read_text(encoding="utf-8")
        qs, parse, clar = exq.parse_questions_from_last_message(text)
        self.assertEqual(parse, exq.PARSE_OK)
        self.assertEqual(clar, exq.HAS_QUESTIONS)
        self.assertEqual(len(qs), 5)
        for q in qs:
            self.assertTrue(q.startswith("[NEEDS CLARIFICATION]"))



class TestIntegrityFixtures(unittest.TestCase):
    def test_f_exit_code_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "SMOKE_C0_R1"
            _write_attempt(
                run_path,
                run_id="SMOKE_C0_R1",
                exit_code=1,
                last_message="NO_CLARIFICATION_NEEDED\n",
            )
            row = chk.check_run(run_path)
            self.assertEqual(row["technical_status"], chk.TECHNICAL_FAILURE)

    def test_g_spec_hash_protocol_violation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "SMOKE_C0_R1"
            _write_attempt(
                run_path,
                run_id="SMOKE_C0_R1",
                spec_before="aaa",
                spec_after="bbb",
                last_message="1. [NEEDS CLARIFICATION] Something?\n",
            )
            row = chk.check_run(run_path)
            self.assertEqual(row["technical_status"], chk.PROTOCOL_VIOLATION)

    def test_success_zero_questions_not_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp) / "SMOKE_C0_R1"
            _write_attempt(
                run_path,
                run_id="SMOKE_C0_R1",
                last_message="NO_CLARIFICATION_NEEDED\n",
            )
            row = chk.check_run(run_path)
            self.assertEqual(row["technical_status"], chk.TECHNICAL_SUCCESS)
            qrows, summary = exq.extract_run(run_path, integrity_row=row)
            self.assertEqual(qrows, [])
            self.assertEqual(summary["question_count"], 0)
            self.assertEqual(summary["clarification_status"], exq.NO_CLARIFICATION_NEEDED)
            self.assertEqual(summary["technical_status"], chk.TECHNICAL_SUCCESS)


class TestSmokeRealArtifacts(unittest.TestCase):
    """Uses the frozen P3 smoke attempt (read-only)."""

    def test_smoke_four_questions_literal(self) -> None:
        smoke = ROOT / "tmp" / "clarify-smoke" / "SMOKE_C0_R1"
        if not (smoke / "attempt-1" / "last-message.txt").is_file():
            self.skipTest("smoke artifacts missing")

        before_files = {
            p: p.read_bytes()
            for p in (smoke / "attempt-1").iterdir()
            if p.is_file()
        }

        row = chk.check_run(smoke)
        self.assertEqual(row["technical_status"], chk.TECHNICAL_SUCCESS)
        self.assertTrue(row["spec_unchanged"])

        qrows, summary = exq.extract_run(smoke, integrity_row=row)
        self.assertEqual(summary["parse_status"], exq.PARSE_OK)
        self.assertEqual(summary["question_count"], 4)
        self.assertEqual(len(qrows), 4)

        raw = (smoke / "attempt-1" / "last-message.txt").read_text(encoding="utf-8")
        parsed, _, _ = exq.parse_questions_from_last_message(raw)
        self.assertEqual([r["question_text_raw"] for r in qrows], parsed)

        # Literal presence: each extracted body appears in the original file.
        for q in parsed:
            self.assertIn(q.split("\n")[0], raw)

        # Artifacts unchanged
        for path, content in before_files.items():
            self.assertEqual(path.read_bytes(), content)


class TestDoesNotTouchExperimental(unittest.TestCase):
    def test_cli_refuses_silent_scan(self) -> None:
        self.assertEqual(chk.main([]), 2)
        self.assertEqual(exq.main([]), 2)


if __name__ == "__main__":
    unittest.main()
