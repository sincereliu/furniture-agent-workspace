"""把预览页打开，并准备这一页要读的数据。

这一页画的是最新一版的房间和已摆放的盒子。板件仍读确认后冻住的宽、深、高。
"""

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser
from typing import Any

from furniture_layout.room_page import room_page_payload
from furniture_workflow.workflow_decisions import pending_decision_views
from furniture_workflow.workflow_lease import read_lease
from furniture_workflow.workflow_project import Project, Revision

PREVIEW_PORT = 8000
_SERVER_READY_SECONDS = 20.0
# 本机健康检查不能走 HTTP_PROXY，否则 127.0.0.1 会被转到外部代理并一直超时。
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def layout_version(revision: Revision) -> str:
    """布局的内容版本：内容摘要 + 确认位（如 `5d28c9b6…:0`）。

    两处用它，必须是同一个字符串：页面轮询靠它决定要不要重画；页面写回时把它
    当作 `expected_version`。不要把修订号编进去。
    """
    return f"{revision.layout_sha256}:{int(bool(revision.layout.confirmed))}"


def preview_page_data(
    project: Project,
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    """预览页要读的那份数据。不含预览 HTML。给了 `store_root` 就带上编辑租约快照。"""
    revision = project.latest
    confirmed = bool(revision.layout.confirmed)
    approved = revision.approved_room_ids()
    rooms = [
        {
            "id": scene.room.id,
            "name": scene.room.name,
            "approved": scene.room.id in approved,
            "scene": room_page_payload(scene),
        }
        for scene in revision.layout.rooms
    ]
    lease = read_lease(store_root, project.id) if store_root is not None else None
    return {
        "project_id": project.id,
        "revision_id": revision.id,
        "revision_number": revision.number,
        "layout_confirmed": confirmed,
        "working": {
            "open": not revision.has_downstream_artifacts(),
            "ops": len(revision.working_ops),
            "can_undo": bool(revision.working_ops),
            # 最近几次改动**是谁做的、改成了什么**：日志里本来就记着，
            # 但页面得让人看得见才算数（牌子点开就是这份列表）。
            "recent": [
                {
                    "at": str(entry.get("at") or ""),
                    "item_id": str(entry.get("item_id") or ""),
                    "op": deepcopy(entry.get("op") or {}),
                    "actor": deepcopy(entry.get("actor") or {}),
                }
                for entry in revision.working_ops[-3:]
            ],
        },
        "lease": lease.snapshot() if lease is not None else None,
        # 决策台账里**还没人确认**的那几条：页面上要看得见"哪些是助手替你定的"。
        # 全量台账在 `store/<id>/project.json`；页面只需要待确认的那一小撮。
        "decisions": {
            "pending": pending_decision_views(project.decisions),
            "total": len(project.decisions),
        },
        "approved_rooms": list(revision.approved_rooms),
        "pending_rooms": revision.pending_room_ids(),
        "inherited_rooms": deepcopy(revision.inherited_rooms),
        "version": layout_version(revision),
        "inherited": deepcopy(revision.inherited),
        "rooms": rooms,
    }


def project_list_url() -> str:
    """浏览器里项目名单的地址。"""
    return f"http://127.0.0.1:{PREVIEW_PORT}/projects"


def preview_url(project_id: str, *, mode: str | None = None) -> str:
    """一个项目的布局页地址。`mode="view"` 只改页面样子，不改写权限。"""
    base = f"http://127.0.0.1:{PREVIEW_PORT}/api/project/{project_id}/preview"
    return f"{base}?mode={mode}" if mode else base


def _preview_browser_enabled() -> bool:
    return os.environ.get("FURNITURE_PREVIEW_BROWSER") != "0"


def preview_server_is_up() -> bool:
    """本机预览进程是否已经在应答。"""
    try:
        with _LOCAL_OPENER.open(
            f"http://127.0.0.1:{PREVIEW_PORT}/health",
            timeout=0.4,
        ) as response:
            return response.status == 200
    except OSError:
        return False


def _python_executable(workspace_root: Path) -> Path:
    scripts = "Scripts" if sys.platform == "win32" else "bin"
    name = "python.exe" if sys.platform == "win32" else "python"
    venv_python = workspace_root / ".venv" / scripts / name
    if venv_python.is_file():
        return venv_python
    return Path(sys.executable)


def ensure_preview_server(workspace_root: Path) -> bool:
    """预览进程没起来时，用布局阶段的入口把它拉起来。"""
    if preview_server_is_up():
        return True
    server = (
        workspace_root
        / "domain"
        / "skills"
        / "layout-plan"
        / "scripts"
        / "open_projects.py"
    )
    popen_kwargs: dict[str, Any] = {
        "cwd": str(workspace_root),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        popen_kwargs["start_new_session"] = True
    subprocess.Popen(
        [str(_python_executable(workspace_root)), str(server)],
        **popen_kwargs,
    )
    deadline = time.monotonic() + _SERVER_READY_SECONDS
    while time.monotonic() < deadline:
        if preview_server_is_up():
            return True
        time.sleep(0.25)
    return False


def open_project_preview(
    project_id: str,
    *,
    workspace_root: str | Path,
    share: bool = False,
) -> dict[str, Any]:
    """打开这一版布局页。之后的修改由同一页自己刷新。"""
    url = preview_url(project_id, mode="view" if share else None)
    if not _preview_browser_enabled():
        return {"url": url, "opened": False}
    ready = ensure_preview_server(Path(workspace_root))
    opened = bool(ready and webbrowser.open(url, new=2))
    return {"url": url, "opened": opened}
