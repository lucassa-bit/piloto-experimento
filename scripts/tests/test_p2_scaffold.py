#!/usr/bin/env python3
"""Unit/static tests for P2 scaffold (no Codex / Spec Kit execution)."""

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

import scaffold_runs as scaffold  # noqa: E402
from lib.runs import EXPECTED_RUN_COUNT, iter_planned_runs  # noqa: E402


FROZEN = scaffold.FROZEN_BASELINE_SHA256


class TestFrozenHashes(unittest.TestCase):
    def test_frozen_table(self) -> None:
        self.assertEqual(
            FROZEN["US02"],
            "ee9291c398af0edfda42b8420017355a54df2a71ed3ae1aac38fb014a169a4aa",
        )
        self.assertEqual(
            FROZEN["US08"],
            "427e858ff781a8a8375a37eedbdaa6ecef127a821c7f2809265ef3116d547a84",
        )
        self.assertEqual(
            FROZEN["US18"],
            "55f45f8e5811dc7b29d226fcb5945cd57814d3eb0b90e38a3a9921778ea13eaa",
        )
        self.assertEqual(
            FROZEN["US25"],
            "0d14d17c97bccc0deb8b78229be963b75293139e7dc6aed59c0c1ef1bf118c8a",
        )

    def test_matrix_size(self) -> None:
        self.assertEqual(len(iter_planned_runs()), EXPECTED_RUN_COUNT)
        self.assertEqual(EXPECTED_RUN_COUNT, 72)


class TestScaffoldIsolation(unittest.TestCase):
    def _seed_sources(self, root: Path) -> None:
        for us_id, digest in FROZEN.items():
            bdir = root / "baselines" / us_id
            (bdir / "checklists").mkdir(parents=True)
            # Conteúdo artificial com hash forçado via escrita + monkeypatch não;
            # usamos conteúdo cujo sha256 bate com FROZEN só se reescrevermos FROZEN
            # no teste local. Em vez disso: escrever bytes e patch FROZEN.
            spec = bdir / "spec.md"
            spec.write_text(f"SPEC-{us_id}\n", encoding="utf-8")
            (bdir / "checklists" / "requirements.md").write_text(
                "checklist\n", encoding="utf-8"
            )
            mdir = root / "materials" / us_id
            mdir.mkdir(parents=True)
            (mdir / "user-story.md").write_text(f"STORY-{us_id}\n", encoding="utf-8")
            for name in (
                "lexical.md",
                "operational.md",
                "decisional.md",
                "systemic.md",
                "total.md",
            ):
                (mdir / name).write_text(f"{us_id}-{name}\n", encoding="utf-8")

    def test_creates_c0_without_context_and_ct_with_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_sources(root)
            # Patch frozen hashes to match seeded content.
            local_frozen = {
                us: scaffold.sha256_file(root / "baselines" / us / "spec.md")
                for us in FROZEN
            }
            original = scaffold.FROZEN_BASELINE_SHA256
            scaffold.FROZEN_BASELINE_SHA256 = local_frozen
            try:
                rc = scaffold.scaffold_all(
                    repetitions=1,
                    clean=False,
                    force=False,
                    dry_run=False,
                    root=root,
                )
                self.assertEqual(rc, 0)
                c0 = root / "runs" / "US02_C0_R1"
                self.assertTrue((c0 / "spec.md").is_file())
                self.assertTrue((c0 / "experiment-input" / "user-story.md").is_file())
                self.assertFalse((c0 / "experiment-input" / "context.md").exists())
                meta = json.loads((c0 / "metadata.json").read_text(encoding="utf-8"))
                self.assertIsNone(meta["context_source"])
                self.assertIsNone(meta["context_sha256"])
                self.assertNotIn("exit_code", meta)

                ct = root / "runs" / "US02_CT_R1"
                ctx = ct / "experiment-input" / "context.md"
                src = root / "materials" / "US02" / "total.md"
                self.assertEqual(ctx.read_bytes(), src.read_bytes())
                meta_ct = json.loads((ct / "metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(meta_ct["context_source"], "materials/US02/total.md")

                # Sem symlink
                self.assertFalse((c0 / "spec.md").is_symlink())
                self.assertFalse(ctx.is_symlink())
            finally:
                scaffold.FROZEN_BASELINE_SHA256 = original

    def test_refuses_preexisting_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_sources(root)
            local_frozen = {
                us: scaffold.sha256_file(root / "baselines" / us / "spec.md")
                for us in FROZEN
            }
            original = scaffold.FROZEN_BASELINE_SHA256
            scaffold.FROZEN_BASELINE_SHA256 = local_frozen
            try:
                scaffold.scaffold_all(
                    repetitions=1,
                    clean=False,
                    force=False,
                    dry_run=False,
                    root=root,
                )
                with self.assertRaises(FileExistsError):
                    scaffold.scaffold_all(
                        repetitions=1,
                        clean=False,
                        force=False,
                        dry_run=False,
                        root=root,
                    )
            finally:
                scaffold.FROZEN_BASELINE_SHA256 = original

    def test_hash_mismatch_stops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._seed_sources(root)
            # FROZEN leave as real values → mismatch
            with self.assertRaises(RuntimeError):
                scaffold.verify_frozen_baselines(root)


if __name__ == "__main__":
    unittest.main()
