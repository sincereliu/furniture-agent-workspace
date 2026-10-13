"""从最新布局里取出一台，给板件页用。

不看整份布局有没有确认，也不写出板件。页上的宽、深、高就是这里已摆好的数。
"""

from __future__ import annotations

from typing import Any

from furniture_layout.project_layout import ProjectLayout


class CabinetNotFound(LookupError):
    """布局里没有这个 id。"""


class CabinetNotExecutable(ValueError):
    """这件留在房间里，不进板件页。"""


def cabinet_for_panel_page(layout: ProjectLayout, cabinet_id: str) -> dict[str, Any]:
    """已保存外形。`manufacture: false` 或不是落地柜/吊柜时拒绝。"""
    if not isinstance(cabinet_id, str) or not cabinet_id:
        raise CabinetNotFound(cabinet_id)
    found: tuple[str, Any] | None = None
    for scene in layout.rooms:
        for item in scene.items:
            if item.id != cabinet_id:
                continue
            if found is not None:
                raise ValueError(f"duplicate cabinet id: {cabinet_id}")
            found = (scene.room.id, item)
    if found is None:
        raise CabinetNotFound(cabinet_id)
    room_id, item = found
    if not item.is_executable:
        raise CabinetNotExecutable(cabinet_id)
    return {
        "id": item.id,
        "label": item.label or item.id,
        "room_id": room_id,
        "furniture_category": item.furniture_category,
        "width": item.width,
        "depth": item.depth,
        "height": item.height,
    }
