"""Read-only layout document for the persistent project preview.

The next stage still reads the frozen cabinet envelope. This document is only
the picture: rooms and placed boxes from the latest revision.
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

from furniture_layout.editor import editor_scene_payload
from furniture_workflow.workflow_project import Project, Revision

PREVIEW_PORT = 8000
_SERVER_READY_SECONDS = 20.0
# 本机健康检查不能走 HTTP_PROXY，否则 127.0.0.1 会被转到外部代理并一直超时。
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def layout_version(revision: Revision) -> str:
    """布局的**内容版本**：内容摘要 + 确认位（如 `5d28c9b6…:0`）。

    两处用它，必须是同一个字符串：
    - 页面轮询拿它判断"要不要重画"；
    - 页面写回时把最近看到的它当 `expected_version` 回传（乐观并发）。
    所以别在别处再拼一次，也别把 `revision.id` / `number` 编进去——
    "同一内容换了个修订号"不该看起来像变了，而"刚被确认"必须看起来变了。
    """
    return f"{revision.layout_sha256}:{int(bool(revision.layout.confirmed))}"


def project_layout_document(project: Project) -> dict[str, Any]:
    """Return the latest layout without preview HTML or viewer markup."""
    revision = project.latest
    confirmed = bool(revision.layout.confirmed)
    rooms = [
        {
            "id": scene.room.id,
            "name": scene.room.name,
            "scene": editor_scene_payload(scene),
        }
        for scene in revision.layout.rooms
    ]
    return {
        "project_id": project.id,
        "revision_id": revision.id,
        "revision_number": revision.number,
        "layout_confirmed": confirmed,
        "version": layout_version(revision),
        # 哪些阶段沿用了更早那一版的内容（内容逐字节相同 → 免掉再确认一次）。
        # 页面据此说明"这次没让你重新确认板件"，而不是悄悄少做一步。
        "inherited": deepcopy(revision.inherited),
        "rooms": rooms,
    }


def preview_url(project_id: str, *, mode: str | None = None) -> str:
    """Browser address for one project's live layout page.

    `mode="view"` 给出**分享形态**的链接（`?mode=view`）：牌子换成"只读分享"、
    页面不带「退出」按钮，适合转发给别人看。它不是权限——真正的门在服务端的
    `access_scope()`（见 references/runtime-contract.md「写权限」段）。
    """
    base = f"http://127.0.0.1:{PREVIEW_PORT}/api/project/{project_id}/preview"
    return f"{base}?mode={mode}" if mode else base


def _preview_browser_enabled() -> bool:
    return os.environ.get("FURNITURE_PREVIEW_BROWSER") != "0"


def preview_server_is_up() -> bool:
    """True when this machine is already serving the preview."""
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
    """Start the local preview server when it is not already up."""
    if preview_server_is_up():
        return True
    server = (
        workspace_root
        / "domain"
        / "skills"
        / "cad-generated"
        / "scripts"
        / "server.py"
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
    """Open the live preview once. Later layout edits refresh that same page.

    `share=True` 打开的是分享形态（`?mode=view`）：只影响页面表达，不改变权限。
    """
    url = preview_url(project_id, mode="view" if share else None)
    if not _preview_browser_enabled():
        return {"url": url, "opened": False}
    ready = ensure_preview_server(Path(workspace_root))
    opened = bool(ready and webbrowser.open(url, new=2))
    return {"url": url, "opened": opened}
