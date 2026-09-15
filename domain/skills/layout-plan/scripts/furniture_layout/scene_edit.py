"""房间场景的编辑操作。

对场景的「源」应用**一次**编辑（单 op、原子）：只改目标 item 的字段，其余不动。
这里不做几何解析——应用后由 `plan_room_scene` 重算并校验；校验不过就不落盘。
"""

from __future__ import annotations

from typing import Any, Mapping

EDIT_OPERATIONS = frozenset({"move", "rotate", "resize"})
PLACEMENT_MODES = frozenset({"wall", "free"})

WALL_ONLY_FIELDS = frozenset({"host_wall", "offset_mm"})
FREE_ONLY_FIELDS = frozenset({"origin_x_mm", "origin_y_mm"})
SHARED_FIELDS = frozenset({"origin_z_mm", "mode"})
POSITION_FIELDS = WALL_ONLY_FIELDS | FREE_ONLY_FIELDS
MOVE_FIELDS = POSITION_FIELDS | SHARED_FIELDS
# 旋转只对 free 摆放有定义：墙摆的原点与 rotation_z_deg 都由 host_wall 派生
# （见 placement.py），转不动。所以墙摆要旋转，必须在同一次 op 里改成 free 并给出自由原点。
ROTATE_FIELDS = frozenset({"rotation_z_deg"}) | FREE_ONLY_FIELDS | {"mode"}
RESIZE_FIELDS = frozenset({"width", "depth", "height"})


def apply_edit(source: Mapping[str, Any], op: Mapping[str, Any]) -> dict[str, Any]:
    """把一次编辑应用到场景源，返回新的源；入参不被修改。"""
    name = op.get("op")
    if name not in EDIT_OPERATIONS:
        raise ValueError(f"unsupported edit op: {name!r}")
    item_id = op.get("item_id")
    if not isinstance(item_id, str) or not item_id:
        raise ValueError("edit requires item_id")

    items = [dict(item) for item in source["items"]]
    target = next((item for item in items if item.get("id") == item_id), None)
    if target is None:
        raise ValueError(f"unknown item: {item_id}")

    fields = set(op) - {"op", "item_id"}
    if name == "move":
        _apply_move(target, op, fields)
    elif name == "rotate":
        _apply_rotate(target, op, fields)
    else:
        _apply_resize(target, op, fields)
    return {**source, "items": items}


def _reject_unknown(name: str, fields: set[str], allowed: frozenset[str]) -> None:
    unknown = sorted(fields - allowed)
    if unknown:
        raise ValueError(f"{name} does not support: " + ", ".join(unknown))


def _placement_after(
    item: dict[str, Any], op: Mapping[str, Any], fields: set[str], *, name: str
) -> dict[str, Any]:
    """按 op 里的摆放字段算出新的 placement；不涉及旋转。"""
    placement = dict(item.get("placement") or {})
    current_mode = placement.get("mode", "wall")
    mode = op.get("mode", current_mode)
    if mode not in PLACEMENT_MODES:
        raise ValueError("placement mode must be 'wall' or 'free'")

    wall_fields = WALL_ONLY_FIELDS & fields
    free_fields = FREE_ONLY_FIELDS & fields
    if wall_fields and free_fields:
        raise ValueError(f"{name} cannot mix wall placement with free coordinates")
    if mode == "wall" and free_fields:
        raise ValueError(
            "wall placement moves by host_wall/offset_mm, "
            "not origin_x_mm/origin_y_mm"
        )
    if mode == "free" and wall_fields:
        raise ValueError(
            "free placement moves by origin_x_mm/origin_y_mm, "
            "not host_wall/offset_mm"
        )
    if mode != current_mode:
        required = FREE_ONLY_FIELDS if mode == "free" else WALL_ONLY_FIELDS
        if not (required & fields):
            raise ValueError(
                f"switching to {mode} placement requires "
                + "/".join(sorted(required))
            )

    for key in MOVE_FIELDS:
        if key in op:
            placement[key] = op[key]
    if mode == "wall":
        for key in FREE_ONLY_FIELDS:
            placement.pop(key, None)
    else:
        for key in WALL_ONLY_FIELDS:
            placement.pop(key, None)
    placement["mode"] = mode
    return placement


def _apply_move(item: dict[str, Any], op: Mapping[str, Any], fields: set[str]) -> None:
    _reject_unknown("move", fields, MOVE_FIELDS)

    current_mode = (item.get("placement") or {}).get("mode", "wall")
    if op.get("mode", current_mode) == current_mode and not (
        fields & (POSITION_FIELDS | {"origin_z_mm"})
    ):
        raise ValueError("move requires at least one position field")

    item["placement"] = _placement_after(item, op, fields, name="move")


def _apply_rotate(item: dict[str, Any], op: Mapping[str, Any], fields: set[str]) -> None:
    _reject_unknown("rotate", fields, ROTATE_FIELDS)
    if "rotation_z_deg" not in fields:
        raise ValueError("rotate requires rotation_z_deg")
    placement = _placement_after(item, op, fields, name="rotate")
    placement["rotation_z_deg"] = op["rotation_z_deg"]
    item["placement"] = placement


def _apply_resize(item: dict[str, Any], op: Mapping[str, Any], fields: set[str]) -> None:
    _reject_unknown("resize", fields, RESIZE_FIELDS)
    if not fields:
        raise ValueError("resize requires at least one of width/depth/height")
    for key in RESIZE_FIELDS:
        if key in op:
            item[key] = op[key]
