"""Pure helpers for experimental baseline generation (no Codex I/O here)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from lib.runs import CONDITION_CONTEXT_FILES, USER_STORY_IDS

FORBIDDEN_CONTEXT_FILES = tuple(CONDITION_CONTEXT_FILES.values()) + (
    "user-story-original.md",
)

TEMPLATE_LEFTOVERS = ("[FEATURE NAME]", "$ARGUMENTS", "[DATE]")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def materials_user_story_path(root: Path, us_id: str) -> Path:
    if us_id not in USER_STORY_IDS:
        raise ValueError(f"Unknown User Story: {us_id}")
    return root / "materials" / us_id / "user-story.md"


def assert_baseline_inputs_user_story_only(root: Path, us_id: str) -> Path:
    """
    Ensure the only experimental material input for baseline is user-story.md.
    Raises if the story is missing or if the caller tries to bind context files.
    """
    story = materials_user_story_path(root, us_id)
    if not story.is_file():
        raise FileNotFoundError(f"Baseline requires materials user story: {story}")

    materials_dir = root / "materials" / us_id
    for name in FORBIDDEN_CONTEXT_FILES:
        # Presence on disk is OK (materials package), but must never be selected
        # as baseline input. This function documents the allow-list.
        path = materials_dir / name
        if path.resolve() == story.resolve():
            raise ValueError(f"Internal error: forbidden file coincides with story: {path}")

    return story


def reject_context_paths(paths: list[Path] | tuple[Path, ...]) -> None:
    """Fail if any path selected as an *input* is a contextual materials file."""
    for path in paths:
        name = path.name
        if name in CONDITION_CONTEXT_FILES.values() or name == "user-story-original.md":
            raise ValueError(
                f"Baseline generation must not use contextual material: {path}"
            )
        if name != "user-story.md" and "materials" in Path(path).parts:
            raise ValueError(
                f"Baseline generation rejects non-story materials path: {path}"
            )


def extract_user_story_body(markdown: str) -> str:
    """
    Extract the User Story text for the specify prompt.
    Keeps the narrative body; drops provenance metadata sections.
    """
    text = markdown.replace("\r\n", "\n").replace("\r", "\n")
    # Drop provenance / metadata headings commonly present in materials.
    cut = re.split(r"\n##\s+Proveni[eê]ncia\b", text, maxsplit=1, flags=re.IGNORECASE)
    body = cut[0].strip()
    # Remove a leading H1 title line if present, keep the story paragraph(s).
    lines = body.splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    body = "\n".join(lines).strip()
    if not body:
        raise ValueError("User Story body is empty after stripping metadata")
    return body


def canonical_baseline_dir(root: Path, us_id: str) -> Path:
    return root / "baselines" / us_id


def canonical_spec_path(root: Path, us_id: str) -> Path:
    return canonical_baseline_dir(root, us_id) / "spec.md"


def canonical_checklist_path(root: Path, us_id: str) -> Path:
    return canonical_baseline_dir(root, us_id) / "checklists" / "requirements.md"


def generation_dir(root: Path, us_id: str) -> Path:
    return canonical_baseline_dir(root, us_id) / "generation"


def staging_feature_dir(root: Path, us_id: str) -> Path:
    """Isolated Spec Kit feature directory for one US (not the canonical baseline)."""
    return generation_dir(root, us_id) / "feature"


def staging_spec_path(root: Path, us_id: str) -> Path:
    return staging_feature_dir(root, us_id) / "spec.md"


def staging_checklist_path(root: Path, us_id: str) -> Path:
    return staging_feature_dir(root, us_id) / "checklists" / "requirements.md"


def assert_canonical_absent_or_force(root: Path, us_id: str, *, force: bool) -> None:
    spec = canonical_spec_path(root, us_id)
    if spec.is_file() and not force:
        raise FileExistsError(
            f"Canonical baseline already exists: {spec}. "
            "Regenerating a baseline is methodologically relevant; pass --force to overwrite."
        )


def render_specify_prompt(template: str, *, feature_directory: str, user_story: str) -> str:
    if "lexical.md" in user_story or "operational.md" in user_story:
        raise ValueError("User Story payload must not embed context filenames as input")
    return (
        template.replace("{{FEATURE_DIRECTORY}}", feature_directory).replace(
            "{{USER_STORY}}", user_story.strip()
        )
    )


def prompt_forbids_context_inputs(prompt: str) -> None:
    """Static guard: rendered prompt must instruct not to read context files."""
    required_snippets = (
        "lexical.md",
        "operational.md",
        "decisional.md",
        "systemic.md",
        "total.md",
        "Do not read",
        "SPECIFY_FEATURE_DIRECTORY",
    )
    for snippet in required_snippets:
        if snippet not in prompt:
            raise ValueError(f"Specify prompt missing isolation rule mentioning: {snippet}")


def validate_staging_outputs(root: Path, us_id: str) -> tuple[Path, Path]:
    spec = staging_spec_path(root, us_id)
    checklist = staging_checklist_path(root, us_id)
    if not spec.is_file() or spec.stat().st_size == 0:
        raise FileNotFoundError(f"Spec Kit did not produce staging spec.md: {spec}")
    if not checklist.is_file() or checklist.stat().st_size == 0:
        raise FileNotFoundError(
            f"Spec Kit did not produce staging checklist: {checklist}"
        )
    text = spec.read_text(encoding="utf-8")
    leftovers = [marker for marker in TEMPLATE_LEFTOVERS if marker in text]
    if leftovers:
        raise ValueError(
            f"{spec} still contains template placeholders: {', '.join(leftovers)}"
        )
    return spec, checklist


def promote_staging_to_canonical(root: Path, us_id: str, *, force: bool) -> tuple[Path, Path]:
    """Copy staging Spec Kit outputs to canonical baselines/<US>/ paths."""
    assert_canonical_absent_or_force(root, us_id, force=force)
    staging_spec, staging_checklist = validate_staging_outputs(root, us_id)

    canonical_spec = canonical_spec_path(root, us_id)
    canonical_checklist = canonical_checklist_path(root, us_id)
    canonical_spec.parent.mkdir(parents=True, exist_ok=True)
    canonical_checklist.parent.mkdir(parents=True, exist_ok=True)

    canonical_spec.write_bytes(staging_spec.read_bytes())
    canonical_checklist.write_bytes(staging_checklist.read_bytes())

    if canonical_spec.read_bytes() != staging_spec.read_bytes():
        raise RuntimeError("Failed literal promotion of staging spec.md")
    if canonical_checklist.read_bytes() != staging_checklist.read_bytes():
        raise RuntimeError("Failed literal promotion of staging checklist")

    return canonical_spec, canonical_checklist


def build_baseline_metadata(
    *,
    user_story_id: str,
    model: str,
    reasoning_effort: str,
    codex_version: str,
    specify_version: str,
    sandbox: str,
    started_at: str,
    finished_at: str,
    exit_code: int | None,
    source_user_story: Path,
    generated_spec_path: Path,
    baseline_output_path: Path,
    user_story_sha256: str,
    baseline_spec_sha256: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user_story_id": user_story_id,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "codex_version": codex_version,
        "specify_version": specify_version,
        "sandbox": sandbox,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "source_user_story": str(source_user_story),
        "generated_spec_path": str(generated_spec_path),
        "baseline_output_path": str(baseline_output_path),
        "user_story_sha256": user_story_sha256,
        "baseline_spec_sha256": baseline_spec_sha256,
        "context_files_used": [],
        "inputs_allowed": ["user-story.md"],
    }
    if extra:
        payload.update(extra)
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite metadata: {path}")
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
