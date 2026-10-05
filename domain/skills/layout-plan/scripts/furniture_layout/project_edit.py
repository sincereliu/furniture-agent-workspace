"""项目布局的编辑：对已摆放的包络应用**一次** op。

和房间场景编辑（`scene_edit.py`）是同一套 op 词表、同一个应用器——项目布局的每一间房
本来就是一份 `RoomScene`（房间 + 已摆放包络），把它的 items 还原成"场景源"即可复用，
不需要第二套字段白名单。

这里只管几何：应用 op → 重新摆放并准入校验 → 交出新的 `ProjectLayout`。
版本、Revision、落盘、权限都不在这一层（见 `furniture_workflow/project_layout_edit.py`）。
"""

from __future__ import annotations

from dataclasses import replace
from math import isfinite
from typing import Any, Mapping

from .scene_planning import plan_scene
from .project_layout import ProjectLayout
from .scene import EPSILON, RoomScene
from .scene_edit import apply_edit


def room_scene_source(scene: RoomScene) -> dict[str, Any]:
    """把一间已摆放的房间还原成场景源（房间定义 + 每件的摆放请求）。

    只保留输入字段；footprint、净距和墙摆变换在下次规划时重算。
    **`spaces` 必须一起带走**：它是输入侧的源，丢了它这一排就再也解不回来了
    （单元会退化成"手工摆的几件家具"）。空的不写，老来源逐字节不变。
    """
    room = scene.room.to_dict()
    if scene.spaces:
        room["spaces"] = [space.to_dict() for space in scene.spaces]
    return {
        "room": room,
        "items": [item.to_source() for item in scene.items],
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

    两类 op：
    - **件级**（`move` / `rotate` / `resize`）：改某一台。改的是**空间单元**时，顺手把它
      记进那个空间的 `pinned`——客户手改过的那台从此重解不再动（设计稿 §五）。
    - **空间级**（`space`）：改"这块地方"（`offset_mm` / `width_mm`），然后**重解**：
      没钉住的单元由空间重新解出来，钉住的原样不动。

    新布局一律 `confirmed=False`：改过的内容没人点过头，不能继承上一位的确认位。
    改不动的情况抛 `ValueError`（op 不合法、找不到那一件、几何不通过），
    由调用方决定怎么回话；这里绝不落盘。
    """
    if op.get("op") == "space":
        return _edit_space(layout, op)
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
    # **先钉住、再重解**：钉住要在源里就写好，否则重解会把客户刚改的那台当"旧解"丢掉
    # （`plan_scene` 的口径：没钉住的单元由空间重新解出来）。
    edited = _pin_in_source(edited, item_id)
    replanned = plan_scene(edited["room"], edited["items"])
    rooms = list(layout.rooms)
    rooms[index] = replanned
    return replace(layout, rooms=tuple(rooms), confirmed=False)


def _pin_in_source(source: dict[str, Any], item_id: str) -> dict[str, Any]:
    """手改过的**空间单元**在源里记进 `spaces[].pinned`；不是空间单元就原样返回。

    这就是设计稿 §五 那条"客户手改 = 升格为钉住"：从此重解不再动这一台。
    """
    spaces = source.get("room", {}).get("spaces")
    if not isinstance(spaces, list):
        return source
    changed = False
    updated: list[Any] = []
    for entry in spaces:
        if not isinstance(entry, Mapping):
            updated.append(entry)
            continue
        space_id = str(entry.get("id") or "")
        if not item_id.startswith(f"{space_id}_u"):
            updated.append(entry)
            continue
        pinned = [
            str(unit) for unit in entry.get("pinned", []) if isinstance(unit, str)
        ]
        if item_id in pinned:
            updated.append(entry)
            continue
        updated.append({**entry, "pinned": [*pinned, item_id]})
        changed = True
    if not changed:
        return source
    return {
        **source,
        "room": {**source["room"], "spaces": updated},
    }


SPACE_EDIT_FIELDS = frozenset({"op", "space_id", "offset_mm", "width_mm"})


def _edit_space(layout: ProjectLayout, op: Mapping[str, Any]) -> ProjectLayout:
    """改"这块地方"：更新空间条目 → 重解这一间（钉住的单元不动）。"""
    unknown = sorted(set(op) - SPACE_EDIT_FIELDS)
    if unknown:
        raise ValueError("space edit does not support: " + ", ".join(unknown))
    space_id = op.get("space_id")
    if not isinstance(space_id, str) or not space_id:
        raise ValueError("space edit requires space_id")
    index, scene = _target_space(layout, space_id)
    space = next(entry for entry in scene.spaces if entry.id == space_id)

    changes: dict[str, Any] = {}
    for key in ("offset_mm", "width_mm"):
        if key not in op:
            continue
        raw = op[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"space edit {key} must be a number")
        value = float(raw)
        if not isfinite(value):
            raise ValueError(f"space edit {key} must be finite")
        if key == "width_mm" and value <= 0:
            raise ValueError("space edit width_mm must be positive")
        if key == "offset_mm" and value < 0:
            raise ValueError("space edit offset_mm must not be negative")
        changes[key] = value
    if not changes:
        raise ValueError("space edit requires offset_mm or width_mm")
    if space.mode != "wall" and "offset_mm" in changes:
        raise ValueError("space edit offset_mm only applies to wall spaces")
    if space.mode != "wall":
        raise ValueError("space edit is not implemented for free spaces yet")

    updated = replace(space, **changes)
    source = room_scene_source(scene)
    source["room"]["spaces"] = [
        (updated.to_dict() if entry.id == space_id else entry.to_dict())
        for entry in scene.spaces
    ]
    # 没钉住的旧解要从源里去掉：留着它们，重解就"看见"旧单元而不重算（见 plan_scene 的口径）。
    source["items"] = [
        item
        for item in source["items"]
        if not str(item.get("id") or "").startswith(f"{space_id}_u")
        or str(item.get("id") or "") in updated.pinned
    ]
    replanned = plan_scene(source["room"], source["items"])
    _require_pinned_units_inside(replanned, space_id)
    rooms = list(layout.rooms)
    rooms[index] = replanned
    return replace(layout, rooms=tuple(rooms), confirmed=False)


def _target_space(layout: ProjectLayout, space_id: str) -> tuple[int, RoomScene]:
    for index, scene in enumerate(layout.rooms):
        if any(space.id == space_id for space in scene.spaces):
            return index, scene
    raise ValueError(f"unknown space: {space_id}")


def _require_pinned_units_inside(scene: RoomScene, space_id: str) -> None:
    """钉住的单元必须仍在这块地方的范围内——**放不下就停问**，不静默挤压（设计稿 §五）。"""
    space = next(entry for entry in scene.spaces if entry.id == space_id)
    if space.mode != "wall":
        return
    start = float(space.offset_mm or 0.0)
    end = start + float(space.width_mm)
    for item_id in space.pinned:
        item = next((entry for entry in scene.items if entry.id == item_id), None)
        if item is None:
            continue
        same_wall = (
            item.placement.mode == "wall"
            and item.placement.host_wall == space.host_wall
        )
        if not same_wall:
            continue
        left = float(item.placement.offset_mm or 0.0)
        right = left + float(item.width)
        if left < start - EPSILON or right > end + EPSILON:
            raise ValueError(
                f"你钉住的那台 {item_id}（{left:g}~{right:g}）放不进这块地方"
                f"（{start:g}~{end:g}）了——把空间放宽到至少 {right - start:g}，"
                "或者取消钉住让求解器重排。"
            )
