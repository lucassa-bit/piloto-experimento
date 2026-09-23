#!/usr/bin/env python3
"""P1 baseline-gen static tests (no Codex / Spec Kit execution)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
BASELINE_GEN = SCRIPTS / "baseline-gen"
ROOT = SCRIPTS.parent

for path in (str(SCRIPTS), str(BASELINE_GEN)):
    if path not in sys.path:
        sys.path.insert(0, path)

from baseline_lib import (  # noqa: E402
    assert_baseline_inputs_user_story_only,
    assert_canonical_absent_or_force,
    build_baseline_metadata,
    canonical_spec_path,
    extract_user_story_body,
    prompt_forbids_context_inputs,
    promote_staging_to_canonical,
    reject_context_paths,
    render_specify_prompt,
    sha256_file,
    staging_feature_dir,
    staging_spec_path,
)
from lib.codex import (  # noqa: E402
    EXPERIMENT_MODEL,
    EXPERIMENT_REASONING_EFFORT,
    build_codex_exec_command,
)
from lib.runs import USER_STORY_IDS  # noqa: E402


class TestBaselineInputs(unittest.TestCase):
    def test_only_user_story_accepted(self) -> None:
        for us_id in USER_STORY_IDS:
            story = assert_baseline_inputs_user_story_only(ROOT, us_id)
            self.assertEqual(story.name, "user-story.md")
            self.assertTrue(story.is_file())
            reject_context_paths([story])

    def test_context_files_rejected_as_inputs(self) -> None:
        for name in (
            "lexical.md",
            "operational.md",
            "decisional.md",
            "systemic.md",
            "total.md",
            "user-story-original.md",
        ):
            with self.assertRaises(ValueError):
                reject_context_paths([ROOT / "materials" / "US02" / name])

    def test_four_us_paths(self) -> None:
        self.assertEqual(USER_STORY_IDS, ("US02", "US08", "US18", "US25"))
        for us_id in USER_STORY_IDS:
            expected = ROOT / "materials" / us_id / "user-story.md"
            self.assertEqual(assert_baseline_inputs_user_story_only(ROOT, us_id), expected)


class TestOverwriteProtection(unittest.TestCase):
    def test_overwrite_blocked_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = canonical_spec_path(root, "US02")
            spec.parent.mkdir(parents=True)
            spec.write_text("# spec\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                assert_canonical_absent_or_force(root, "US02", force=False)
            assert_canonical_absent_or_force(root, "US02", force=True)


class TestPromotionAndMetadata(unittest.TestCase):
    def test_promote_and_metadata_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            us_id = "US02"
            feature = staging_feature_dir(root, us_id)
            checklist = feature / "checklists"
            checklist.mkdir(parents=True)
            staging = staging_spec_path(root, us_id)
            staging.write_text("# Feature Spec\n\nBody\n", encoding="utf-8")
            (checklist / "requirements.md").write_text("# checklist\n", encoding="utf-8")

            canonical, _ = promote_staging_to_canonical(root, us_id, force=False)
            self.assertTrue(canonical.is_file())
            self.assertEqual(canonical, canonical_spec_path(root, us_id))

            story = root / "materials" / "US02" / "user-story.md"
            story.parent.mkdir(parents=True)
            story.write_text("# US02\n\nAs a user...\n", encoding="utf-8")

            meta = build_baseline_metadata(
                user_story_id="US02",
                model=EXPERIMENT_MODEL,
                reasoning_effort=EXPERIMENT_REASONING_EFFORT,
                codex_version="codex-cli 0.156.1",
                specify_version="specify 1.0.10",
                sandbox="workspace-write",
                started_at="t0",
                finished_at="t1",
                exit_code=0,
                source_user_story=story,
                generated_spec_path=staging,
                baseline_output_path=canonical,
                user_story_sha256=sha256_file(story),
                baseline_spec_sha256=sha256_file(canonical),
            )
            for key in (
                "user_story_id",
                "model",
                "reasoning_effort",
                "codex_version",
                "specify_version",
                "sandbox",
                "started_at",
                "finished_at",
                "exit_code",
                "source_user_story",
                "generated_spec_path",
                "baseline_output_path",
                "user_story_sha256",
                "baseline_spec_sha256",
            ):
                self.assertIn(key, meta)
            self.assertEqual(meta["model"], "gpt-5.5")
            self.assertEqual(meta["reasoning_effort"], "medium")
            self.assertEqual(meta["context_files_used"], [])


class TestPromptAndCommand(unittest.TestCase):
    def test_prompt_forbids_context(self) -> None:
        template = (BASELINE_GEN / "specify-prompt.txt").read_text(encoding="utf-8")
        prompt_forbids_context_inputs(template)
        self.assertTrue(template.startswith("$speckit-specify"))
        self.assertIn("Do not auto-create a directory under specs/", template)
        self.assertIn("Do not update `.specify/feature.json`", template)

    def test_render_uses_staging_feature_dir(self) -> None:
        template = (BASELINE_GEN / "specify-prompt.txt").read_text(encoding="utf-8")
        body = extract_user_story_body(
            (ROOT / "materials" / "US02" / "user-story.md").read_text(encoding="utf-8")
        )
        prompt = render_specify_prompt(
            template,
            feature_directory="baselines/US02/generation/feature",
            user_story=body,
        )
        self.assertIn("SPECIFY_FEATURE_DIRECTORY=baselines/US02/generation/feature", prompt)
        self.assertIn("zip code", prompt)
        self.assertNotIn("Proveniência", prompt)
        self.assertNotIn("utm_source", prompt)

    def test_command_explicit_no_resume(self) -> None:
        command = build_codex_exec_command(
            workdir=Path("/tmp/repo"),
            model=EXPERIMENT_MODEL,
            reasoning_effort=EXPERIMENT_REASONING_EFFORT,
            last_message_path=Path(
                "/tmp/repo/baselines/US02/generation/attempt-1/last-message.txt"
            ),
            sandbox="workspace-write",
            approval_policy="never",
            codex_executable="codex",
            extra_args=["--ephemeral", "--skip-git-repo-check"],
        )
        joined = " ".join(command)
        self.assertTrue(joined.startswith("codex --ask-for-approval never exec "))
        self.assertIn("--model gpt-5.5", joined)
        self.assertIn("model_reasoning_effort=medium", joined)
        self.assertIn("--sandbox workspace-write", joined)
        self.assertNotIn("resume", joined)
        self.assertNotIn("--approve-for-me", joined)


if __name__ == "__main__":
    raise SystemExit(unittest.main(verbosity=2))
