"""启动 Furniture Agent 工作台控制台首页。

在仓库根目录运行：

    .venv/Scripts/python.exe domain/stages/layout-plan/scripts/open_workbench.py

仓库根目录的 `start.bat` 跑的就是这一条。已经在跑的预览不会再拉一次。
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

from furniture_layout.open_preview import open_home_preview  # noqa: E402


def main() -> int:
    result = open_home_preview(workspace_root=_WORKSPACE_ROOT)
    url = result.get("url", "")
    if not result.get("opened"):
        print(url)
        return 1
    print(f"Furniture Agent 工作台已在浏览器打开：{url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
