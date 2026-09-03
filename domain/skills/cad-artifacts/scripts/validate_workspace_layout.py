"""Enforce stage-owned skill scripts plus the disposable temp surface."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


SCRIPT_SUFFIXES = {
    ".bat",
    ".cmd",
    ".cjs",
    ".js",
    ".jsx",
    ".mjs",
    ".ps1",
    ".psm1",
    ".py",
    ".pyc",
    ".pyw",
    ".sh",
    ".ts",
    ".tsx",
}
STAGE_SKILL_NAMES = (
    "furniture-design-intent",
    "furniture-layout",
    "furniture-panel-planning",
    "furniture-manufacturing",
    "furniture-feature-tree",
    "furniture-cad",
    "furniture-delivery-validation",
)
ALLOWED_SCRIPT_ROOTS = tuple(
    Path("domain") / "skills" / skill_name / "scripts" for skill_name in STAGE_SKILL_NAMES
) + (Path("temp"),)
EXCLUDED_ROOTS = {".git", ".venv", "external"}
FORBIDDEN_TOP_LEVEL_CODE_TREES = {"packages", "scripts", "scratch", "tests", "tmp"}


def find_violations(workspace_root: Path) -> list[str]:
    workspace_root = workspace_root.resolve()
    violations: list[str] = []

    for name in sorted(FORBIDDEN_TOP_LEVEL_CODE_TREES):
        path = workspace_root / name
        if path.exists():
            violations.append(f"forbidden top-level code tree: {name}/")

    for current_root, directories, files in os.walk(workspace_root):
        current_path = Path(current_root)
        if current_path == workspace_root:
            directories[:] = [name for name in directories if name not in EXCLUDED_ROOTS]
        for filename in files:
            path = current_path / filename
            if path.suffix.lower() not in SCRIPT_SUFFIXES:
                continue
            relative = path.relative_to(workspace_root)
            if any(relative.is_relative_to(root) for root in ALLOWED_SCRIPT_ROOTS):
                continue
            violations.append(f"script outside allowed locations: {relative.as_posix()}")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that local scripts only exist in stage skills or temp/."
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    args = parser.parse_args()

    violations = find_violations(args.workspace_root)
    if violations:
        print("Workspace script layout is invalid:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Workspace script layout is valid: stage-owned domain/skills/*/scripts + temp only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
