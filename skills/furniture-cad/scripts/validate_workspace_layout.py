"""Enforce the furniture workspace's two allowed local script surfaces."""

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
ALLOWED_SCRIPT_ROOTS = (
    Path("skills/furniture-cad/scripts"),
    Path("temp"),
)
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
        description="Validate that local scripts only exist in the furniture skill or temp/."
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    args = parser.parse_args()

    violations = find_violations(args.workspace_root)
    if violations:
        print("Workspace script layout is invalid:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("Workspace script layout is valid: skills/furniture-cad/scripts + temp only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
