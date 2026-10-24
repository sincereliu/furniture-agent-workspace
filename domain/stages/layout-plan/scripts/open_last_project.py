"""打开最近创建、并且当前预览打得开的那一个项目。

在仓库根目录运行：

    .venv/Scripts/python.exe domain/stages/layout-plan/scripts/open_last_project.py

如果要启动工作台控制台首页，双击根目录的 `start.bat` 或运行 `open_workbench.py`。已经在跑的预览不会再拉一次。
"""

from __future__ import annotations

import sys
from pathlib import Path


_WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
_SERVER_ROOT = (
    _WORKSPACE_ROOT / "domain" / "stages" / "cad-generated" / "scripts"
)
sys.path.insert(0, str(_SERVER_ROOT))

from runtime_paths import bootstrap_runtime_paths  # noqa: E402

bootstrap_runtime_paths(_WORKSPACE_ROOT)

from furniture_layout.open_preview import (  # noqa: E402
    open_home_preview,
    open_project_preview,
)
from furniture_workflow.workflow_store import JsonProjectStore  # noqa: E402


def main() -> int:
    ready = JsonProjectStore(_WORKSPACE_ROOT / "store").list_projects()
    if not ready:
        print("没有可打开的历史项目，正在打开工作台控制台...")
        result = open_home_preview(workspace_root=_WORKSPACE_ROOT)
        return 0 if result.get("opened") else 1
    project = ready[0]
    result = open_project_preview(project["id"], workspace_root=_WORKSPACE_ROOT)
    print(project["name"])
    if not result.get("opened"):
        print(result.get("url", ""))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
