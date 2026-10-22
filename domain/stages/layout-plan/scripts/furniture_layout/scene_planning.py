"""Shared room planning: parse requests, place envelopes, admit geometry."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .placement import place_items
from .scene import PlacedItem, RoomModel, RoomScene, parse_item_specs
from .validation import raise_unless_admitted


def plan_scene(
    room: Mapping[str, Any],
    items: list[Mapping[str, Any]],
    *,
    allow_empty: bool = False,
    existing_items: Sequence[PlacedItem] = (),
) -> RoomScene:
    """规划一间房：把每件家具摆成包络，再做几何准入。

    `fill` 的宽度是这段墙的空段，仍是这一台的包络。柜门、层板和抽屉不在这里拆。
    局部编辑传入 existing_items 保留普通定宽墙摆位置；新规划不传。
    """
    room_model = RoomModel.from_dict(room)
    specs = parse_item_specs(items, allow_empty=allow_empty)
    scene = RoomScene(room=room_model, items=place_items(
        room_model, specs, existing_items=existing_items,
    ))
    raise_unless_admitted(scene)
    return scene
