#!/usr/bin/env python3
"""Static/unit tests for P0 mechanical adaptation (no Codex / Spec Kit execution)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.codex import (  # noqa: E402
    EXPERIMENT_MODEL,
    EXPERIMENT_REASONING_EFFORT,
    build_codex_exec_command,
    invoke_codex_exec,
    prepare_attempt_dir,
)
from lib.runs import (  # noqa: E402
    CONDITIONS,
    DEFAULT_REPETITIONS,
    EXPECTED_RUN_COUNT,
    USER_STORY_IDS,
    context_filename_for_condition,
    iter_planned_runs,
    make_run_id,
    validate_context_files,
)


class TestMatrix(unittest.TestCase):
    def test_user_stories(self) -> None:
        self.assertEqual(USER_STORY_IDS, ("US02", "US08", "US18", "US25"))
        self.assertNotIn("US19", USER_STORY_IDS)
        self.assertNotIn("US22", USER_STORY_IDS)

    def test_conditions_and_reps(self) -> None:
        self.assertEqual(CONDITIONS, ("C0", "CL", "CO", "CD", "CS", "CT"))
        self.assertEqual(DEFAULT_REPETITIONS, 3)
        self.assertEqual(EXPECTED_RUN_COUNT, 72)

    def test_run_ids_no_zero_pad(self) -> None:
        self.assertEqual(make_run_id("US02", "C0", 1), "US02_C0_R1")
        self.assertEqual(make_run_id("US02", "C0", 2), "US02_C0_R2")
        self.assertEqual(make_run_id("US02", "C0", 3), "US02_C0_R3")
        self.assertNotEqual(make_run_id("US02", "C0", 1), "US02_C0_R01")

    def test_planned_runs_count(self) -> None:
        specs = iter_planned_runs()
        self.assertEqual(len(specs), 72)
        self.assertEqual(specs[0][0], "US02_C0_R1")
        self.assertEqual(specs[-1][0], "US25_CT_R3")


class TestContextMapping(unittest.TestCase):
    def test_filenames(self) -> None:
        self.assertIsNone(context_filename_for_condition("C0"))
        self.assertEqual(context_filename_for_condition("CL"), "lexical.md")
        self.assertEqual(context_filename_for_condition("CO"), "operational.md")
        self.assertEqual(context_filename_for_condition("CD"), "decisional.md")
        self.assertEqual(context_filename_for_condition("CS"), "systemic.md")
        self.assertEqual(context_filename_for_condition("CT"), "total.md")

    def test_c0_rejects_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            context = Path(tmp) / "context.md"
            context.write_text("x", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_context_files(
                    "C0", context_path=context, materials_context_source=None
                )

    def test_literal_match_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "lexical.md"
            context = root / "context.md"
            source.write_text("alpha\n", encoding="utf-8")
            context.write_text("beta\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_context_files(
                    "CL",
                    context_path=context,
                    materials_context_source=source,
                )


class TestCodexWrapper(unittest.TestCase):
    def test_command_explicit_model_and_reasoning(self) -> None:
        command = build_codex_exec_command(
            workdir=Path("/tmp/workdir"),
            model=EXPERIMENT_MODEL,
            reasoning_effort=EXPERIMENT_REASONING_EFFORT,
            last_message_path=Path("/tmp/last-message.txt"),
            sandbox="read-only",
            approval_policy="never",
            codex_executable="codex",
        )
        self.assertEqual(command[0], "codex")
        self.assertEqual(command[1:3], ["--ask-for-approval", "never"])
        self.assertEqual(command[3], "exec")
        self.assertIn("--model", command)
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.5")
        self.assertIn("-c", command)
        self.assertEqual(
            command[command.index("-c") + 1], "model_reasoning_effort=medium"
        )
        self.assertIn("--json", command)
        self.assertIn("--output-last-message", command)
        self.assertIn("--sandbox", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertEqual(command[-1], "-")
        self.assertNotIn("resume", command)
        self.assertNotIn("--approve-for-me", command)

    def test_resume_forbidden_in_extra_args(self) -> None:
        with self.assertRaises(ValueError):
            build_codex_exec_command(
                workdir=Path("/tmp"),
                model="gpt-5.5",
                reasoning_effort="medium",
                last_message_path=Path("/tmp/lm.txt"),
                sandbox=None,
                codex_executable="codex",
                extra_args=["resume", "--last"],
            )

    def test_attempt_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            first = prepare_attempt_dir(parent, 1)
            (first / "stdout.jsonl").write_text("{}", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_attempt_dir(parent, 1)

    def test_invoke_dry_build_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            result = invoke_codex_exec(
                workdir=parent,
                prompt="hello",
                artifact_parent=parent,
                attempt=1,
                model=EXPERIMENT_MODEL,
                reasoning_effort=EXPERIMENT_REASONING_EFFORT,
                sandbox="read-only",
                codex_executable="codex",
                execute=False,
            )
            self.assertEqual(result.exit_code, -1)
            self.assertEqual(result.model, "gpt-5.5")
            self.assertEqual(result.reasoning_effort, "medium")
            self.assertEqual(result.attempt, 1)
            self.assertTrue(result.metadata_path.is_file())
            joined = " ".join(result.command)
            self.assertIn("--model gpt-5.5", joined)
            self.assertIn("model_reasoning_effort=medium", joined)
            self.assertNotIn("resume", joined)


class TestLegacyResidues(unittest.TestCase):
    def test_no_shuffle_seed_in_clarify_runner_source(self) -> None:
        text = (SCRIPTS / "clarification-gen" / "runner.py").read_text(encoding="utf-8")
        self.assertNotIn("20260708", text)
        self.assertNotIn("random.shuffle", text)
        self.assertNotIn("SHUFFLE_SEED", text)
        self.assertIn("Shuffle: off", text)

    def test_prompts_use_dollar_speckit(self) -> None:
        specify = (SCRIPTS / "baseline-gen" / "specify-prompt.txt").read_text(
            encoding="utf-8"
        )
        clarify = (SCRIPTS / "clarification-gen" / "clarify-prompt.txt").read_text(
            encoding="utf-8"
        )
        self.assertTrue(specify.startswith("$speckit-specify"))
        self.assertTrue(clarify.startswith("$speckit-clarify"))
        self.assertNotIn("/speckit.specify", specify)
        self.assertNotIn("/speckit.clarify", clarify)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
