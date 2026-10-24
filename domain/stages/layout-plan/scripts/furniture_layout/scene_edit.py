"""Strict placed-scene edits: set_pose supplies a complete transform; resize supplies dimensions."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .input_fields import fields
from .placement import build_placed_item
from .scene import ItemSpec, PlacedItem, ResolvedPlacement, RoomScene
from .scene_planning import plan_scene
from .validation import raise_unless_admitted

POSE_FIELDS = frozenset({"mode", "origin_x_mm", "origin_y_mm", "origin_z_mm", "rotation_z_deg"})
SIZE_FIELDS = frozenset({"width", "depth", "height"})


def apply_scene_edit(scene: RoomScene, op: Mapping[str, Any]) -> RoomScene:
    name = op.get("op")
    if name not in {"set_pose", "resize"}:
        raise ValueError("edit op must be set_pose or resize")
    item_id = op.get("item_id")
    if not isinstance(item_id, str) or not item_id:
        raise ValueError("edit requires item_id")
    previous = next((item for item in scene.items if item.id == item_id), None)
    if previous is None:
        raise ValueError(f"unknown item: {item_id!r}")
    values = {key: value for key, value in op.items() if key not in {"op", "item_id"}}
    if name == "set_pose":
        fields(values, POSE_FIELDS | {"host_wall", "against"}, "set_pose")
        missing = {key for key in POSE_FIELDS if key not in values or values[key] is None}
        if missing:
            raise ValueError("set_pose requires: " + ", ".join(sorted(missing)))
        target = _set_pose(scene, previous, values)
    else:
        fields(values, SIZE_FIELDS, "resize")
        if not values:
            raise ValueError("resize requires width, depth or height")
        if previous.placement.fill:
            raise ValueError("a fill item only supports changing height above the floor")
        sources = [{**item.to_source(), **values} if item.id == item_id else item.to_source()
                   for item in scene.items]
        return plan_scene(scene.room.to_dict(), sources, existing_items=scene.items)
    result = replace(scene, items=tuple(target if item.id == target.id else item for item in scene.items))
    raise_unless_admitted(result)
    return result


def _set_pose(scene: RoomScene, previous: PlacedItem, op: Mapping[str, Any]) -> PlacedItem:
    previous_pose = previous.placement.to_dict()
    planar_fields = ("mode", "host_wall", "origin_x_mm", "origin_y_mm", "rotation_z_deg")
    raw = {key: op[key] for key in POSE_FIELDS}
    raw["host_wall"] = op.get("host_wall")
    if "against" in op:
        raw["against"] = op["against"]
    elif all(raw.get(key) == previous_pose.get(key) for key in planar_fields):
        raw["against"] = previous_pose.get("against", {})
    if previous.placement.fill:
        if any(raw.get(key) != previous_pose.get(key) for key in planar_fields):
            raise ValueError("a fill item only supports changing origin_z_mm")
        raw["fill"] = True
    placement = ResolvedPlacement.from_dict(raw)
    if previous.placement.fill and placement.against != previous.placement.against:
        raise ValueError("a fill item only supports changing origin_z_mm")
    return build_placed_item(ItemSpec.from_dict(previous.to_source()), scene.room,
                             placement, width=previous.width)
