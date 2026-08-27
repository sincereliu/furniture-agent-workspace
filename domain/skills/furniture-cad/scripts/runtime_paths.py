"""Expose the seven stage-owned runtime packages to CLI, API, and tests."""

from __future__ import annotations

import sys
from pathlib import Path


STAGE_SKILL_NAMES = (
    "furniture-design-intent",
    "furniture-layout",
    "furniture-panel-planning",
    "furniture-manufacturing",
    "furniture-feature-tree",
    "furniture-cad",
    "furniture-delivery-validation",
)


def stage_script_roots(workspace_root: Path) -> tuple[Path, ...]:
    skills_root = workspace_root.resolve() / "domain" / "skills"
    return tuple(skills_root / name / "scripts" for name in STAGE_SKILL_NAMES)


def bootstrap_runtime_paths(workspace_root: Path | None = None) -> tuple[Path, ...]:
    root = (workspace_root or Path(__file__).resolve().parents[4]).resolve()
    script_roots = stage_script_roots(root)
    for script_root in reversed(script_roots):
        path = str(script_root)
        if path not in sys.path:
            sys.path.insert(0, path)
    return script_roots
