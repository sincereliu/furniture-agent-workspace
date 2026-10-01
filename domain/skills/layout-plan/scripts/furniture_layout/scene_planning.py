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
    room_model = RoomModel.from_dict(room)
    specs = parse_item_specs(items, allow_empty=allow_empty)
    scene = RoomScene(room=room_model, items=place_items(room_model, specs))
    raise_unless_admitted(scene)
    return scene
