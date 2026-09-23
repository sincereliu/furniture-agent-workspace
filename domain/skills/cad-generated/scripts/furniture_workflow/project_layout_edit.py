"""页面改项目布局的写路径：一次 op → 一个新 Revision（草稿）。

契约（见 `references/runtime-contract.md`「页面写项目」段）：

- 一次请求只改一件、只改一处；校验不过就整体拒绝，**不落任何东西**。
- 必须带 `expected_version`（页面最近一次看到的 `version`）：对不上就拒绝，
  绝不拿旧画面去覆盖新内容。
- 成功 = **新 Revision**（不复用、不原地改），布局回到未确认、下游要重新走。
- 父修订的 `stage_inputs` 原样带走：那些是柜体构造意图（门数、层板、背板安装…），
  摆放变了它们没变。
- 默认关闭，靠 `FURNITURE_PROJECT_LAYOUT_EDIT=1` 灰度打开。

几何部分不在这里：op 词表、白名单、重新摆放与准入校验都在
`furniture_layout/project_edit.py`（与房间场景编辑共用同一套）。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from furniture_layout.project_edit import apply_layout_edit

from .project_preview import layout_version, project_layout_document
from .workflow_orchestrator import FurnitureOrchestrator
from .workflow_project import Project
from .workflow_store import JsonProjectStore

LAYOUT_EDIT_ENV = "FURNITURE_PROJECT_LAYOUT_EDIT"


def layout_edit_enabled() -> bool:
    """灰度开关：只有显式设成 `1` 才开。别的写法（`true` / `yes` / 空）都当关着。"""
    return os.environ.get(LAYOUT_EDIT_ENV) == "1"


class LayoutEditDisabled(RuntimeError):
    """灰度开关没开：这个部署不该接受页面写回。"""


class VersionConflict(RuntimeError):
    """页面手上的画面已经不是最新：不能拿它去覆盖。"""

    def __init__(self, current_version: str) -> None:
        super().__init__(f"layout changed; current version is {current_version}")
        self.current_version = current_version


def edit_project_layout(
    project: Project,
    op: Mapping[str, Any],
    *,
    expected_version: str,
    workspace_root: str | Path,
    store_root: str | Path,
) -> dict[str, Any]:
    """应用一次 op，落成新 Revision，返回新的布局文档。

    这里是页面写项目的**唯一门面**：HTTP 层不自己开 orchestrator
    （`test_entrypoint_architecture` 钉着这条），由本模块驱动生命周期并落盘。

    抛：`LayoutEditDisabled`（开关关着）、`VersionConflict`（版本对不上）、
    `ValueError`（op 不合法 / 找不到那一件 / 几何不通过）。
    """
    if not layout_edit_enabled():
        raise LayoutEditDisabled(f"{LAYOUT_EDIT_ENV} is not set to 1")
    revision = project.latest
    current = layout_version(revision)
    if expected_version != current:
        raise VersionConflict(current)
    layout = apply_layout_edit(revision.layout, op)
    orchestrator = FurnitureOrchestrator(
        workspace_root=workspace_root,
        project_store=JsonProjectStore(store_root),
    )
    orchestrator.revise(project, layout)
    return project_layout_document(project)
