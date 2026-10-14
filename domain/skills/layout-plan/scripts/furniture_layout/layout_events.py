"""布局页的事件流。

项目文件或编辑租约变了才推一笔。
房间几何不在这一笔里：`version` 变了，页面再读 `GET /layout`。
本机打开的连接同时表示这一页还开着。
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from furniture_layout.open_preview import layout_page_meta
from furniture_workflow.workflow_lease import lease_path, read_lease
from furniture_workflow.workflow_store import JsonProjectStore, project_preview_status

# 只用来发现磁盘上的替换。页面不按这个节拍重画。
LAYOUT_WATCH_SECONDS = 0.4
_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]+$")

router = APIRouter()


class _Host:
    store_root: Callable[[], Path] | None = None
    may_edit: Callable[[Request], bool] | None = None
    touch_presence: Callable[[], None] | None = None


_host = _Host()


def bind_layout_events(
    *,
    store_root: Callable[[], Path],
    may_edit: Callable[[Request], bool],
    touch_presence: Callable[[], None],
) -> None:
    """本机进程启动时注入项目目录、写权限，以及「这一页还开着」。"""
    _host.store_root = store_root
    _host.may_edit = may_edit
    _host.touch_presence = touch_presence


def _store_root() -> Path:
    if _host.store_root is None or _host.may_edit is None or _host.touch_presence is None:
        raise RuntimeError("layout event host is not bound")
    return _host.store_root()


def _file_stamp(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def layout_file_stamp(store_root: str | Path, project_id: str) -> tuple[Any, Any]:
    """`project.json` 与 `edit-lease.json` 的修改时间与大小。没变就不读文件。"""
    root = JsonProjectStore(store_root).project_dir(project_id)
    return (
        _file_stamp(root / "project.json"),
        _file_stamp(lease_path(store_root, project_id)),
    )


def read_layout_notice(store_root: str | Path, project_id: str) -> dict[str, Any]:
    """读当前这一笔。项目读不动时抛 `ValueError`。"""
    project = JsonProjectStore(store_root).load(project_id)
    availability, reason = project_preview_status(project, project_id)
    if availability != "ready":
        raise ValueError(reason)
    return layout_page_meta(project, store_root=store_root)


def notice_for_change(
    store_root: str | Path,
    project_id: str,
    previous: tuple[Any, Any] | None,
    current: tuple[Any, Any],
) -> dict[str, Any] | None:
    """文件戳没变返回 `None`。只变了租约文件时不重读整份项目。"""
    if previous == current:
        return None
    project_changed = previous is None or previous[0] != current[0]
    if not project_changed:
        lease = read_lease(store_root, project_id)
        return {"lease": None if lease is None else lease.snapshot()}
    return read_layout_notice(store_root, project_id)


def _open_layout_notice(store_root: Path, project_id: str) -> dict[str, Any]:
    if not _PROJECT_ID.fullmatch(project_id):
        raise HTTPException(
            status_code=422,
            detail="project_id may contain only letters, digits, '-' and '_'",
        )
    try:
        return read_layout_notice(store_root, project_id)
    except ValueError as exc:
        message = str(exc)
        status = 404 if message.startswith("project not found") else 422
        raise HTTPException(status_code=status, detail=message) from exc
    except (OSError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _sse(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"data: {body}\n\n"


async def _disconnected(request: Request) -> bool:
    check = getattr(request, "is_disconnected", None)
    if check is None:
        return False
    result = check()
    if isinstance(result, Awaitable):
        return bool(await result)
    return bool(result)


async def iter_layout_events(
    project_id: str,
    request: Request,
    *,
    interval: float = LAYOUT_WATCH_SECONDS,
) -> AsyncIterator[str]:
    """先推当前这一笔，之后只在两个文件之一被替换时再推。"""
    previous: tuple[Any, Any] | None = None
    local = bool(_host.may_edit and _host.may_edit(request))
    while True:
        if local and _host.touch_presence is not None:
            _host.touch_presence()
        if await _disconnected(request):
            return
        root = _store_root()
        current = layout_file_stamp(root, project_id)
        try:
            notice = notice_for_change(root, project_id, previous, current)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            notice = None
        if notice is not None:
            previous = current
            yield _sse(notice)
        await asyncio.sleep(interval)


@router.get("/api/project/{project_id}/layout/events")
async def project_layout_events(project_id: str, request: Request) -> StreamingResponse:
    """布局页订阅这一条。推送不含房间几何。"""
    _open_layout_notice(_store_root(), project_id)
    return StreamingResponse(
        iter_layout_events(project_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )
