"""Layout-stage planning for supported cabinet families."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from furniture_design_intent.design_spec import FurnitureSpec, SUPPORTED_TYPES

from .layout_preview import render_layout_preview
from .layout_planning import CabinetLayout
from .room_planning import plan_room_placement


def plan_layout(spec: FurnitureSpec) -> CabinetLayout:
    """Stage 2: resolve cabinet envelope, clear regions, and layout counts."""
    if spec.furniture_type not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES))
        raise ValueError(
            f"Unsupported cabinet type: {spec.furniture_type!r}; supported: {supported}"
        )
    return CabinetLayout.from_spec(spec)


def plan_layout_stage(
    spec: FurnitureSpec,
    *,
    room: Mapping[str, Any] | None = None,
    placement: Mapping[str, Any] | None = None,
    furniture_label: str = "",
) -> dict[str, Any]:
    """Build the complete serializable stage-2 output.

    Room context is optional for compatibility. When present, both the room and
    placement are required so the checkpoint never pretends that an unresolved
    site position is a completed layout.
    """
    layout = plan_layout(spec)
    output: dict[str, Any] = {"layout": asdict(layout)}
    if room is None and placement is None:
        return output
    if room is None or placement is None:
        raise ValueError(
            "room-aware layout requires both layout.room and layout.placement"
        )
    if not isinstance(room, Mapping) or not isinstance(placement, Mapping):
        raise ValueError("layout.room and layout.placement must be objects")

    room_placement = plan_room_placement(
        layout,
        room,
        placement,
        furniture_label=furniture_label or spec.furniture_type,
    )
    output["room_placement"] = room_placement.to_dict()
    output["preview"] = render_layout_preview(room_placement, layout)
    return output
