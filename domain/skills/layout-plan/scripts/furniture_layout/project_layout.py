"""Project-level layout: many rooms, each furniture envelope a CAD unit."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

from .cad import scene_to_cad_tree
from .placement import place_items
from .preview import render_preview
from .scene import (
    EXECUTABLE_CATEGORIES,
    EPSILON,
    ItemSpec,
    PlacedItem,
    RoomModel,
    RoomScene,
    parse_item_specs,
)
from .viewer import render_viewer


LAYOUT_SCHEMA_VERSION = 1
DEFAULT_STUDIO_WIDTH_MM = 4000.0
DEFAULT_STUDIO_DEPTH_MM = 3000.0
DEFAULT_STUDIO_HEIGHT_MM = 3200.0


@dataclass(frozen=True)
class LayoutUnit:
    """One furniture envelope that panel-plan may admit as a cabinet."""

    id: str
    room_id: str
    furniture_category: str
    width: float
    depth: float
    height: float
    origin_x_mm: float
    origin_y_mm: float
    origin_z_mm: float
    rotation_z_deg: float
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "label": self.label,
            "furniture_category": self.furniture_category,
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "origin_x_mm": self.origin_x_mm,
            "origin_y_mm": self.origin_y_mm,
            "origin_z_mm": self.origin_z_mm,
            "rotation_z_deg": self.rotation_z_deg,
        }

    @classmethod
    def from_placed(cls, room_id: str, item: PlacedItem) -> "LayoutUnit":
        if item.furniture_category not in EXECUTABLE_CATEGORIES:
            raise ValueError(
                f"item {item.id!r} is not an executable cabinet unit"
            )
        return cls(
            id=item.id,
            room_id=room_id,
            furniture_category=item.furniture_category,
            width=item.width,
            depth=item.depth,
            height=item.height,
            origin_x_mm=item.placement.origin_x_mm,
            origin_y_mm=item.placement.origin_y_mm,
            origin_z_mm=item.placement.origin_z_mm,
            rotation_z_deg=item.placement.rotation_z_deg,
            label=item.label,
        )


@dataclass(frozen=True)
class ProjectLayout:
    """Confirmed or draft home layout: rooms plus placed envelopes."""

    rooms: tuple[RoomScene, ...]
    confirmed: bool = False
    schema_version: int = LAYOUT_SCHEMA_VERSION

    def confirm(self) -> "ProjectLayout":
        errors = self.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return replace(self, confirmed=True)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.schema_version != LAYOUT_SCHEMA_VERSION:
            errors.append(
                f"unsupported ProjectLayout schema_version: {self.schema_version}"
            )
        if not self.rooms:
            errors.append("layout requires at least one room")
        seen_rooms: set[str] = set()
        seen_items: set[str] = set()
        for scene in self.rooms:
            if scene.room.id in seen_rooms:
                errors.append(f"duplicate room id: {scene.room.id}")
            seen_rooms.add(scene.room.id)
            for item in scene.items:
                if item.id in seen_items:
                    errors.append(f"duplicate item id: {item.id}")
                seen_items.add(item.id)
        return errors

    def executable_units(self) -> tuple[LayoutUnit, ...]:
        units: list[LayoutUnit] = []
        for scene in self.rooms:
            for item in scene.items:
                if item.is_executable:
                    units.append(LayoutUnit.from_placed(scene.room.id, item))
        return tuple(units)

    def cad_trees(self) -> list[dict[str, Any]]:
        return [scene_to_cad_tree(scene) for scene in self.rooms]

    def to_dict(self) -> dict[str, Any]:
        rooms: list[dict[str, Any]] = []
        for scene in self.rooms:
            payload: dict[str, Any] = scene.to_dict()
            if scene.items:
                payload["preview"] = render_preview(scene)
                payload["viewer"] = render_viewer(scene)
            rooms.append(payload)
        return {
            "schema_version": self.schema_version,
            "confirmed": self.confirmed,
            "rooms": rooms,
            "cad": {"units": [unit.to_dict() for unit in self.executable_units()]},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProjectLayout":
        if not isinstance(data, Mapping):
            raise ValueError("layout must be an object")
        raw_rooms = data.get("rooms")
        if not isinstance(raw_rooms, list) or not raw_rooms:
            raise ValueError("layout.rooms must be a non-empty list")
        rooms = tuple(
            RoomScene.from_dict(_room_scene_payload(item))
            for item in raw_rooms
        )
        schema_version = int(data.get("schema_version", LAYOUT_SCHEMA_VERSION))
        return cls(
            rooms=rooms,
            confirmed=bool(data.get("confirmed", False)),
            schema_version=schema_version,
        )

    @classmethod
    def from_source(cls, data: Mapping[str, Any]) -> "ProjectLayout":
        """Plan rooms from source requests (no footprints required)."""
        raw_rooms = data.get("rooms") if isinstance(data, Mapping) else None
        if not isinstance(raw_rooms, list) or not raw_rooms:
            raise ValueError("layout.rooms must be a non-empty list")
        planned: list[RoomScene] = []
        for index, raw in enumerate(raw_rooms):
            if not isinstance(raw, Mapping):
                raise ValueError(f"rooms[{index}] must be an object")
            room_fields = {
                key: value for key, value in raw.items() if key != "items"
            }
            room = RoomModel.from_dict(room_fields)
            specs = parse_item_specs(raw.get("items"), allow_empty=True)
            planned.append(
                RoomScene(room=room, items=place_items(room, specs) if specs else ())
            )
        layout = cls(rooms=tuple(planned), confirmed=False)
        errors = layout.validate()
        if errors:
            raise ValueError("; ".join(errors))
        # The project tool and the pure planner both enter through from_source.
        # Reject invalid geometry before it becomes a draft revision.
        from .validation import admit_scene

        messages: list[str] = []
        for scene in layout.rooms:
            report = admit_scene(scene)
            if not report.passed:
                messages.extend(issue.message for issue in report.issues)
        if messages:
            raise ValueError("; ".join(messages))
        return layout


def single_cabinet_layout(
    *,
    furniture_category: str = "floor_cabinet",
    width: float = 800.0,
    depth: float = 600.0,
    height: float = 1000.0,
    origin_z_mm: float | None = None,
    room_height_mm: float = DEFAULT_STUDIO_HEIGHT_MM,
    cabinet_id: str = "cabinet_1",
    room_id: str = "room",
    confirmed: bool = False,
) -> ProjectLayout:
    """Studio-room shortcut: one executable cabinet on the north wall."""
    if furniture_category not in EXECUTABLE_CATEGORIES:
        raise ValueError(
            "furniture_category must be one of: "
            + ", ".join(sorted(EXECUTABLE_CATEGORIES))
        )
    z_mm = 0.0 if origin_z_mm is None else float(origin_z_mm)
    if furniture_category == "wall_cabinet" and origin_z_mm is None:
        z_mm = max(0.0, room_height_mm - height)
        if z_mm <= EPSILON:
            z_mm = 0.0
    spec: dict[str, Any] = {
        "id": cabinet_id,
        "label": cabinet_id,
        "category": furniture_category,
        "furniture_category": furniture_category,
        "width": width,
        "depth": depth,
        "height": height,
        "placement": {
            "mode": "wall",
            "host_wall": "north",
            "offset_mm": 0,
            "origin_z_mm": z_mm,
        },
    }
    layout = ProjectLayout.from_source(
        {
            "rooms": [
                {
                    "id": room_id,
                    "name": "房间",
                    "width_mm": DEFAULT_STUDIO_WIDTH_MM,
                    "depth_mm": DEFAULT_STUDIO_DEPTH_MM,
                    "height_mm": room_height_mm,
                    "items": [spec],
                }
            ]
        }
    )
    return replace(layout, confirmed=confirmed) if confirmed else layout


def _room_scene_payload(raw: Mapping[str, Any]) -> dict[str, Any]:
    if "room" in raw:
        return {
            "room": raw["room"],
            "items": raw.get("items", []),
        }
    room_fields = {key: value for key, value in raw.items() if key != "items"}
    return {"room": room_fields, "items": raw.get("items", [])}
