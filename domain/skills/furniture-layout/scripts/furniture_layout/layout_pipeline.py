"""Layout-stage planning for supported cabinet families."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .layout_preview import render_layout_preview
from .layout_planning import CabinetLayout
from .layout_spec import LayoutSpec
from .layout_viewer import render_layout_viewer
from .room_planning import RoomModel, plan_room_placement


DEFAULT_BEDROOM_WIDTH_MM = 4200.0
DEFAULT_BEDROOM_DEPTH_MM = 3600.0
DEFAULT_BEDROOM_HEIGHT_MM = 2800.0
DEFAULT_WALL_CABINET_CEILING_CLEARANCE_MM = 450.0


def plan_layout(spec: LayoutSpec | Any) -> CabinetLayout:
    """Normalize the envelope for an independent room-layout request."""
    if not isinstance(spec, LayoutSpec):
        spec = LayoutSpec(
            furniture_type=str(spec.furniture_type),
            width=float(spec.width),
            depth=float(spec.depth),
            height=float(spec.height),
            door_count=int(getattr(spec, "door_count", spec.n_doors)),
        )
    return CabinetLayout.from_spec(spec)


def plan_layout_stage(
    spec: LayoutSpec,
    *,
    room: Mapping[str, Any] | None = None,
    placement: Mapping[str, Any] | None = None,
    furniture_label: str = "",
) -> dict[str, Any]:
    """Build one complete serializable independent-layout output.

    Missing room context is filled with an explicit default bedroom and a
    centered north-wall placement so every successful request has a visible
    3D envelope preview. The output records which values were assumed.  No
    board thickness, back construction, or final internal clearance is
    introduced by this independent capability.
    """
    layout = plan_layout(spec)
    output: dict[str, Any] = {"layout": asdict(layout)}
    if room is not None and not isinstance(room, Mapping):
        raise ValueError("layout.room must be an object")
    if placement is not None and not isinstance(placement, Mapping):
        raise ValueError("layout.placement must be an object")

    room_source = "provided"
    placement_source = "provided"
    resolved_room = room
    if resolved_room is None:
        resolved_room = _default_bedroom()
        room_source = "default_bedroom"
    resolved_placement = placement
    if resolved_placement is None:
        resolved_placement = _default_placement(
            layout,
            resolved_room,
            mount_mode=spec.mount_mode,
            mounting_height_mm=spec.mounting_height_mm,
        )
        placement_source = "default_north_wall_centered"

    room_placement = plan_room_placement(
        layout,
        resolved_room,
        resolved_placement,
        furniture_label=furniture_label or spec.furniture_type,
    )
    output["layout_context"] = {
        "room_source": room_source,
        "placement_source": placement_source,
    }
    output["room_placement"] = room_placement.to_dict()
    output["preview"] = render_layout_preview(room_placement, layout)
    output["viewer"] = render_layout_viewer(room_placement, layout)
    return output


def _default_bedroom() -> dict[str, Any]:
    return {
        "id": "default_bedroom",
        "name": "默认卧室（系统假设）",
        "width_mm": DEFAULT_BEDROOM_WIDTH_MM,
        "depth_mm": DEFAULT_BEDROOM_DEPTH_MM,
        "height_mm": DEFAULT_BEDROOM_HEIGHT_MM,
        "openings": [],
        "obstacles": [],
    }


def _default_placement(
    layout: CabinetLayout,
    room: Mapping[str, Any],
    *,
    mount_mode: str | None = None,
    mounting_height_mm: float | None = None,
) -> dict[str, Any]:
    room_model = RoomModel.from_dict(room)
    origin_z_mm = 0.0
    if layout.furniture_type == "wall_cabinet":
        if mount_mode == "flush_ceiling":
            origin_z_mm = max(0.0, room_model.height_mm - layout.height)
        elif mount_mode == "free_height" and mounting_height_mm is not None:
            origin_z_mm = float(mounting_height_mm)
        else:
            origin_z_mm = max(
                0.0,
                room_model.height_mm
                - layout.height
                - DEFAULT_WALL_CABINET_CEILING_CLEARANCE_MM,
            )
    return {
        "mode": "wall",
        "host_wall": "north",
        "offset_mm": max((room_model.width_mm - layout.width) / 2.0, 0.0),
        "origin_z_mm": origin_z_mm,
    }
