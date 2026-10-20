"""把画面脚本挂到预览进程。摆放求解和拖动换算仍由布局阶段提供，共用 /layout-view。"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

_PACKAGE = Path(__file__).resolve().parent
_WORKSPACE = _PACKAGE.parents[3]
WEB_STATIC = _PACKAGE / "static"
LAYOUT_RULES_STATIC = (
    _WORKSPACE
    / "domain"
    / "stages"
    / "layout-plan"
    / "scripts"
    / "furniture_layout"
    / "static"
)


class LayoutViewFiles(StaticFiles):
    """先找网页模块的画面，再找布局阶段留下的求解和拖动脚本。"""

    def __init__(self, directories: tuple[Path, ...]) -> None:
        super().__init__(directory=str(directories[0]))
        self._directories = tuple(path.resolve() for path in directories)

    def lookup_path(self, path: str) -> tuple[str, os.stat_result | None]:
        for directory in self._directories:
            full_path = (directory / path).resolve()
            try:
                full_path.relative_to(directory)
            except ValueError:
                continue
            if full_path.is_file():
                return str(full_path), full_path.stat()
        return "", None

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


layout_view = LayoutViewFiles((WEB_STATIC, LAYOUT_RULES_STATIC))


def mount_layout_view(app: FastAPI) -> None:
    app.mount("/layout-view", layout_view, name="layout_view")
