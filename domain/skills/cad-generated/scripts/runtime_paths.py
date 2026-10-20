"""Expose stage packages and independent application modules to host entrypoints."""

from __future__ import annotations

import sys
from pathlib import Path


STAGE_SKILL_NAMES = (
    "layout-plan",
    "panel-plan",
    "manufacture-plan",
    "feature-tree",
    "cad-generated",
    "delivery-validated",
)
AI_MODULE_RELATIVE_ROOT = Path("domain") / "modules" / "ai"


def stage_script_roots(workspace_root: Path) -> tuple[Path, ...]:
    skills_root = workspace_root.resolve() / "domain" / "skills"
    return tuple(skills_root / name / "scripts" for name in STAGE_SKILL_NAMES)


def bootstrap_runtime_paths(workspace_root: Path | None = None) -> tuple[Path, ...]:
    root = (workspace_root or Path(__file__).resolve().parents[4]).resolve()
    script_roots = (*stage_script_roots(root), root / AI_MODULE_RELATIVE_ROOT)
    for script_root in reversed(script_roots):
        path = str(script_root)
        if path not in sys.path:
            sys.path.insert(0, path)
    return script_roots
