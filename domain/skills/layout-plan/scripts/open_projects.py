"""开机后打开已经做过的项目。

在仓库根目录运行：

    .venv/Scripts/python.exe domain/skills/layout-plan/scripts/open_projects.py

浏览器打开项目列表。布局画面在这一阶段；本文件只负责把本机预览进程拉起来。
"""

from __future__ import annotations

import sys
from pathlib import Path


_SERVER_ROOT = (
    Path(__file__).resolve().parents[2]
    / "cad-generated"
    / "scripts"
)
sys.path.insert(0, str(_SERVER_ROOT))

from server import main  # noqa: E402


if __name__ == "__main__":
    main()
