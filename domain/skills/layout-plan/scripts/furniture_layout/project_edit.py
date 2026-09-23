"""项目布局的编辑：对已摆放的包络应用**一次** op。

和房间场景编辑（`scene_edit.py`）是同一套 op 词表、同一个应用器——项目布局的每一间房
本来就是一份 `RoomScene`（房间 + 已摆放包络），把它的 items 还原成"场景源"即可复用，
不需要第二套字段白名单。

这里只管几何：应用 op → 重新摆放并准入校验 → 交出新的 `ProjectLayout`。
版本、Revision、落盘、权限都不在这一层（见 `furniture_workflow/project_layout_edit.py`）。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .pipeline import plan_scene
from .project_layout import ProjectLayout
from .scene import RoomScene
from .scene_edit import apply_edit


def room_scene_source(scene: RoomScene) -> dict[str, Any]:
    """把一间已摆放的房间还原成场景源（房间定义 + 每件的摆放请求）。

    `PlacedItem.to_dict()` 里的 `footprint` / `clearances_mm` 是派生字段，
    `parse_item_specs` 根本不读它们，所以重算后不会留下过期值。
    """
    return {
        "room": scene.room.to_dict(),
        "items": [item.to_dict() for item in scene.items],
    }


def _target_index(layout: ProjectLayout, item_id: str) -> int:
    for index, scene in enumerate(layout.rooms):
        if any(item.id == item_id for item in scene.items):
            return index
    raise ValueError(f"unknown item: {item_id}")


def apply_layout_edit(
    layout: ProjectLayout,
    op: Mapping[str, Any],
) -> ProjectLayout:
    """应用一次编辑，返回新的布局；入参不被修改。

    新布局一律 `confirmed=False`：改过的内容没人点过头，不能继承上一位的确认位。
    改不动的情况抛 `ValueError`（op 不合法、找不到那一件、几何不通过），
    由调用方决定怎么回话；这里绝不落盘。
    """
    item_id = op.get("item_id")
    if not isinstance(item_id, str) or not item_id:
        raise ValueError("edit requires item_id")
    index = _target_index(layout, item_id)
    scene = layout.rooms[index]
    target = next(item for item in scene.items if item.id == item_id)
    if target.placement.fill:
        # fill 件的宽与偏移都由墙上的空段算出来（见 placement.fill_span），
        # 改它等于改完就被重算覆盖：与其静默丢掉这次编辑，不如直接说清为什么不行。
        raise ValueError(
            f"item {item_id!r} is a fill unit: its width and offset come from the "
            "wall span, so placement edits are recomputed away"
        )

    edited = apply_edit(room_scene_source(scene), op)
    replanned = plan_scene(edited["room"], edited["items"])
    rooms = list(layout.rooms)
    rooms[index] = replanned
    return replace(layout, rooms=tuple(rooms), confirmed=False)
