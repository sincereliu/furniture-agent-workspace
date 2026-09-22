"""Read-only layout document for the persistent project preview.

The next stage still reads the frozen cabinet envelope. This document is only
the picture: rooms and placed boxes from the latest revision.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import webbrowser
from typing import Any

from furniture_layout.editor import editor_scene_payload
from furniture_workflow.workflow_project import Project

PREVIEW_PORT = 8000
_SERVER_READY_SECONDS = 20.0
# 本机健康检查不能走 HTTP_PROXY，否则 127.0.0.1 会被转到外部代理并一直超时。
_LOCAL_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


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
        "version": f"{revision.id}:{revision.number}:{int(confirmed)}",
        "rooms": rooms,
    }


def preview_url(project_id: str) -> str:
    """Browser address for one project's live layout page."""
    return (
        f"http://127.0.0.1:{PREVIEW_PORT}/api/project/{project_id}/preview"
    )


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
) -> dict[str, Any]:
    """Open the live preview once. Later layout edits refresh that same page."""
    url = preview_url(project_id)
    if not _preview_browser_enabled():
        return {"url": url, "opened": False}
    ready = ensure_preview_server(Path(workspace_root))
    opened = bool(ready and webbrowser.open(url, new=2))
    return {"url": url, "opened": opened}
