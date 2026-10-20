"""Enforce stage-owned scripts, the independent application modules, and disposable temp."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from runtime_paths import MODULE_RELATIVE_ROOTS, STAGE_NAMES


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
ALLOWED_SCRIPT_ROOTS = tuple(
    Path("domain") / "stages" / stage_name / "scripts" for stage_name in STAGE_NAMES
) + MODULE_RELATIVE_ROOTS + (Path("temp"),)
#: 根目录点名的例外：只有一个给人双击的启动器，本身不承载逻辑
#: （只 cd 到仓库根、转去跑布局阶段的 `scripts/open_last_project.py`）。
#: 别往这里加第二个文件——要加就先问「它为什么不放在某个阶段的 scripts/ 里」。
ALLOWED_ROOT_SCRIPTS = frozenset({Path("open_last_project.bat")})
EXCLUDED_ROOTS = {".git", ".venv", "external", "vendor"}
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
            if relative in ALLOWED_ROOT_SCRIPTS:
                continue
            if any(relative.is_relative_to(root) for root in ALLOWED_SCRIPT_ROOTS):
                continue
            violations.append(f"script outside allowed locations: {relative.as_posix()}")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate stage scripts, the independent application modules, and temp/."
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

    print("Workspace script layout is valid: stage scripts + domain/modules/ai + domain/modules/web + temp.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
