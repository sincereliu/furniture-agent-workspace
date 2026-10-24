"""项目编辑复用布局阶段的严格 set_pose / resize 协议和几何准入。

这里只替换目标房间并清除确认；版本、Revision、权限和落盘归工作流。
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .project_layout import ProjectLayout
from .placement import build_placed_item
from .scene import ItemSpec, ResolvedPlacement
from .scene_edit import apply_scene_edit
from .scene_planning import plan_scene
from .validation import raise_unless_admitted


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
    replanned = apply_scene_edit(scene, op)
    rooms = list(layout.rooms)
    rooms[index] = replanned
    return replace(layout, rooms=tuple(rooms), confirmed=False)


def restore_layout_item(
    layout: ProjectLayout, item_id: str, snapshot: Mapping[str, Any],
) -> ProjectLayout:
    """Restore pose and dimensions together, including dependent against/fill geometry.

    Intermediate poses with the current dimensions are never admitted or published.
    The working log stores the target's previous state; deterministic dependencies
    are rebuilt from that state with ordinary wall positions kept as seeds.
    """
    index = _target_index(layout, item_id)
    scene = layout.rooms[index]
    previous = next(item for item in scene.items if item.id == item_id)
    spec = ItemSpec.from_dict({**previous.to_source(),
                              **{key: snapshot[key] for key in ("width", "depth", "height")}})
    restored = build_placed_item(spec, scene.room,
                                ResolvedPlacement.from_dict(snapshot["placement"]),
                                width=snapshot["width"])
    seeds = tuple(restored if item.id == item_id else item for item in scene.items)
    result = plan_scene(scene.room.to_dict(), [item.to_source() for item in seeds],
                        existing_items=seeds)
    # Keep the saved transform exact, including admitted fractional coordinates.
    # Admission checks it against the rebuilt dependencies with the domain tolerance.
    result = replace(result, items=tuple(restored if item.id == item_id else item for item in result.items))
    raise_unless_admitted(result)
    rooms = list(layout.rooms)
    rooms[index] = result
    return replace(layout, rooms=tuple(rooms), confirmed=False)
