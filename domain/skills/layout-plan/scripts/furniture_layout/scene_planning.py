"""Shared room planning: parse requests, place envelopes, admit geometry."""

from __future__ import annotations

from typing import Any, Mapping

from .placement import place_items
from .scene import RoomModel, RoomScene, parse_item_specs
from .validation import raise_unless_admitted


def plan_scene(
    room: Mapping[str, Any],
    items: list[Mapping[str, Any]],
    *,
    allow_empty: bool = False,
) -> RoomScene:
    """规划一间房：把每件家具摆成包络，再做几何准入。

    `fill` 的宽度是这段墙的空段，仍是这一台的包络。柜门、层板和抽屉不在这里拆。
    """
    room_model = RoomModel.from_dict(room)
    specs = parse_item_specs(items, allow_empty=allow_empty)
    scene = RoomScene(room=room_model, items=place_items(room_model, specs))
    raise_unless_admitted(scene)
    return scene
