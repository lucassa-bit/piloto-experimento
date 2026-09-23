#!/usr/bin/env python3
"""Unit/static tests for P3 clarification runner (no Codex execution)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
CLARIFICATION = SCRIPTS / "clarification-gen"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(CLARIFICATION) not in sys.path:
    sys.path.insert(0, str(CLARIFICATION))

from lib.codex import (  # noqa: E402
    EXPERIMENT_MODEL,
    EXPERIMENT_REASONING_EFFORT,
    build_codex_exec_command,
    build_run_metadata_template,
    prepare_attempt_dir,
)
from lib.runs import RunInfo  # noqa: E402
import runner as clarify_runner  # noqa: E402


class TestCommandConstruction(unittest.TestCase):
    def test_explicit_model_reasoning_no_resume(self) -> None:
        command = build_codex_exec_command(
            workdir=Path("/tmp/run"),
            model=EXPERIMENT_MODEL,
            reasoning_effort=EXPERIMENT_REASONING_EFFORT,
            last_message_path=Path("/tmp/run/attempt-1/last-message.txt"),
            sandbox="read-only",
            approval_policy="never",
            codex_executable="codex",
            extra_args=["--ephemeral", "--skip-git-repo-check"],
        )
        self.assertEqual(command[1:3], ["--ask-for-approval", "never"])
        self.assertEqual(command[3], "exec")
        self.assertEqual(command[command.index("--model") + 1], "gpt-5.5")
        self.assertEqual(
            command[command.index("-c") + 1], "model_reasoning_effort=medium"
        )
        self.assertIn("--json", command)
        self.assertIn("--output-last-message", command)
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertNotIn("resume", command)
        self.assertNotIn("--approve-for-me", command)


class TestMetadataSchema(unittest.TestCase):
    def test_execution_fields(self) -> None:
        meta = build_run_metadata_template(
            run_id="SMOKE_C0_R1",
            user_story_id="SMOKE",
            condition="C0",
            repetition=1,
            attempt=1,
            sandbox="read-only",
            approval_policy="never",
            spec_sha256_before="aaa",
            spec_sha256_after="aaa",
            context_sha256=None,
            stdout_path="/tmp/stdout.jsonl",
            stderr_path="/tmp/stderr.txt",
            last_message_path="/tmp/last-message.txt",
            status="Valid",
            protocol_violation=False,
        )
        for key in (
            "run_id",
            "user_story_id",
            "condition",
            "repetition",
            "attempt",
            "model",
            "reasoning_effort",
            "sandbox",
            "approval_policy",
            "codex_version",
            "specify_version",
            "started_at",
            "finished_at",
            "exit_code",
            "spec_sha256_before",
            "spec_sha256_after",
            "context_sha256",
            "stdout_path",
            "stderr_path",
            "last_message_path",
        ):
            self.assertIn(key, meta)
        self.assertIsNone(meta["context_sha256"])
        self.assertNotIn("resume", meta)


class TestAttemptProtection(unittest.TestCase):
    def test_attempt_no_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            first = prepare_attempt_dir(parent, 1)
            (first / "stdout.jsonl").write_text("x\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                prepare_attempt_dir(parent, 1)


class TestC0Context(unittest.TestCase):
    def test_c0_context_sha_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp)
            (run_path / "experiment-input").mkdir(parents=True)
            digest = clarify_runner.context_sha256_for_run(run_path, "C0")
            self.assertIsNone(digest)

    def test_c0_rejects_existing_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp)
            ei = run_path / "experiment-input"
            ei.mkdir(parents=True)
            (ei / "context.md").write_text("nope\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                clarify_runner.context_sha256_for_run(run_path, "C0")

    def test_literal_context_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_path = Path(tmp)
            ei = run_path / "experiment-input"
            ei.mkdir(parents=True)
            (ei / "context.md").write_text("literal-context\n", encoding="utf-8")
            digest = clarify_runner.context_sha256_for_run(run_path, "CL")
            self.assertEqual(
                digest, clarify_runner.sha256_file(ei / "context.md")
            )


class TestPromptAuditOnly(unittest.TestCase):
    def test_prompt_forbids_spec_mutation_and_resume_path(self) -> None:
        text = (CLARIFICATION / "clarify-prompt.txt").read_text(encoding="utf-8")
        self.assertIn("$speckit-clarify", text)
        self.assertIn("Do not modify spec.md", text)
        self.assertIn("Do not answer the clarification questions", text)
        self.assertIn("NO_CLARIFICATION_NEEDED", text)
        self.assertNotIn("/speckit.clarify", text)


class TestExperimentalGuard(unittest.TestCase):
    def test_refuses_experimental_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_path = root / "runs" / "US02_C0_R1"
            (run_path / "experiment-input").mkdir(parents=True)
            (run_path / "checklists").mkdir(parents=True)
            (run_path / "spec.md").write_text("spec\n", encoding="utf-8")
            (run_path / "experiment-input" / "user-story.md").write_text(
                "story\n", encoding="utf-8"
            )
            (run_path / "metadata.json").write_text(
                json.dumps(
                    {
                        "run_id": "US02_C0_R1",
                        "user_story_id": "US02",
                        "condition": "C0",
                        "repetition": 1,
                    }
                ),
                encoding="utf-8",
            )
            run = RunInfo("US02_C0_R1", "US02", "C0", run_path)
            with self.assertRaises(RuntimeError):
                clarify_runner.run_one(
                    run,
                    root=root,
                    prompt="$speckit-clarify\n",
                    execute=False,
                    allow_experimental=False,
                )


class TestDryRunOneHashes(unittest.TestCase):
    def test_dry_run_records_matching_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_path = root / "tmp" / "SMOKE_C0_R1"
            (run_path / "experiment-input").mkdir(parents=True)
            (run_path / "checklists").mkdir(parents=True)
            (run_path / "spec.md").write_text("synthetic-spec\n", encoding="utf-8")
            (run_path / "experiment-input" / "user-story.md").write_text(
                "synthetic-story\n", encoding="utf-8"
            )
            (run_path / "metadata.json").write_text(
                json.dumps(
                    {
                        "run_id": "SMOKE_C0_R1",
                        "user_story_id": "SMOKE",
                        "condition": "C0",
                        "repetition": 1,
                    }
                ),
                encoding="utf-8",
            )
            before = clarify_runner.sha256_file(run_path / "spec.md")
            run = RunInfo("SMOKE_C0_R1", "SMOKE", "C0", run_path)
            outcome = clarify_runner.run_one(
                run,
                root=root,
                prompt="$speckit-clarify smoke\n",
                execute=False,
                allow_experimental=False,
            )
            self.assertEqual(outcome.spec_sha256_before, before)
            self.assertEqual(outcome.spec_sha256_after, before)
            self.assertIsNone(outcome.context_sha256)
            self.assertFalse(outcome.protocol_violation)
            self.assertTrue(
                (run_path / "attempt-1" / "execution-metadata.json").is_file()
            )


class TestCliSafety(unittest.TestCase):
    def test_main_does_not_execute_by_default(self) -> None:
        rc = clarify_runner.main([])
        self.assertEqual(rc, 0)

    def test_execute_all_requires_authorization(self) -> None:
        rc = clarify_runner.main(["--execute-all"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
