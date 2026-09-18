"""Room-scene inputs and placed-item records for independent room layout."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping


WALLS = frozenset({"south", "east", "north", "west"})
PLACEMENT_MODES = frozenset({"wall", "free"})
EXECUTABLE_CATEGORIES = frozenset({"floor_cabinet", "wall_cabinet"})
EPSILON = 1e-6


def number(
    data: Mapping[str, Any],
    *keys: str,
    default: float | None = None,
) -> float:
    for key in keys:
        if key in data and data[key] is not None:
            value = data[key]
            if isinstance(value, bool):
                raise ValueError(f"{key} must be numeric")
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{key} must be numeric") from exc
    if default is not None:
        return float(default)
    raise ValueError(f"missing numeric field: {keys[0]}")


def optional_number(data: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in data and data[key] is not None:
            return number(data, key)
    return None


def text(data: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        if key in data and data[key] is not None:
            return str(data[key]).strip()
    return default


def mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value


def clean(value: float) -> float:
    return 0.0 if abs(value) < EPSILON else round(value, 6)


def require_positive(*values: float) -> None:
    if not all(isfinite(value) and value > 0 for value in values):
        raise ValueError("dimensions must be positive finite numbers")


@dataclass(frozen=True)
class RoomOpening:
    id: str
    kind: str
    wall: str
    offset_mm: float
    width_mm: float
    height_mm: float
    sill_height_mm: float = 0.0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> "RoomOpening":
        if not isinstance(data, Mapping):
            raise ValueError(f"room.openings[{index}] must be an object")
        wall = text(data, "wall", default="").lower()
        if wall not in WALLS:
            raise ValueError(
                f"room.openings[{index}].wall must be one of: "
                + ", ".join(sorted(WALLS))
            )
        return cls(
            id=text(data, "id") or f"opening_{index + 1}",
            kind=(text(data, "kind") or "opening").lower(),
            wall=wall,
            offset_mm=number(data, "offset_mm", "offset", default=0.0),
            width_mm=number(data, "width_mm", "width"),
            height_mm=number(data, "height_mm", "height"),
            sill_height_mm=number(
                data,
                "sill_height_mm",
                "sill_height",
                default=0.0,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "wall": self.wall,
            "offset_mm": self.offset_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "sill_height_mm": self.sill_height_mm,
        }


@dataclass(frozen=True)
class RoomObstacle:
    id: str
    kind: str
    x_mm: float
    y_mm: float
    z_mm: float
    width_mm: float
    depth_mm: float
    height_mm: float

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> "RoomObstacle":
        if not isinstance(data, Mapping):
            raise ValueError(f"room.obstacles[{index}] must be an object")
        return cls(
            id=text(data, "id") or f"obstacle_{index + 1}",
            kind=(text(data, "kind") or "obstacle").lower(),
            x_mm=number(data, "x_mm", "x", default=0.0),
            y_mm=number(data, "y_mm", "y", default=0.0),
            z_mm=number(data, "z_mm", "z", default=0.0),
            width_mm=number(data, "width_mm", "width"),
            depth_mm=number(data, "depth_mm", "depth"),
            height_mm=number(data, "height_mm", "height"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "width_mm": self.width_mm,
            "depth_mm": self.depth_mm,
            "height_mm": self.height_mm,
        }

    @property
    def footprint(self) -> tuple[tuple[float, float], ...]:
        return (
            (self.x_mm, self.y_mm),
            (self.x_mm + self.width_mm, self.y_mm),
            (self.x_mm + self.width_mm, self.y_mm + self.depth_mm),
            (self.x_mm, self.y_mm + self.depth_mm),
        )


@dataclass(frozen=True)
class RoomModel:
    id: str
    name: str
    width_mm: float
    depth_mm: float
    height_mm: float
    openings: tuple[RoomOpening, ...] = ()
    obstacles: tuple[RoomObstacle, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoomModel":
        if not isinstance(data, Mapping):
            raise ValueError("room must be an object")
        raw_openings = data.get("openings", [])
        raw_obstacles = data.get("obstacles", [])
        if not isinstance(raw_openings, list):
            raise ValueError("room.openings must be a list")
        if not isinstance(raw_obstacles, list):
            raise ValueError("room.obstacles must be a list")
        width_mm = number(data, "width_mm", "width")
        depth_mm = number(data, "depth_mm", "depth")
        height_mm = number(data, "height_mm", "height")
        require_positive(width_mm, depth_mm, height_mm)
        return cls(
            id=text(data, "id", "room_id") or "room",
            name=text(data, "name") or "房间",
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
            openings=tuple(
                RoomOpening.from_dict(item, index=index)
                for index, item in enumerate(raw_openings)
            ),
            obstacles=tuple(
                RoomObstacle.from_dict(item, index=index)
                for index, item in enumerate(raw_obstacles)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "width_mm": self.width_mm,
            "depth_mm": self.depth_mm,
            "height_mm": self.height_mm,
            "openings": [item.to_dict() for item in self.openings],
            "obstacles": [item.to_dict() for item in self.obstacles],
        }

    def wall_length(self, wall: str) -> float:
        return self.width_mm if wall in {"south", "north"} else self.depth_mm


@dataclass(frozen=True)
class PlacementRequest:
    mode: str
    host_wall: str | None
    offset_mm: float | None
    origin_x_mm: float | None
    origin_y_mm: float | None
    origin_z_mm: float
    rotation_z_deg: float | None
    fill: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlacementRequest":
        if not isinstance(data, Mapping):
            raise ValueError("placement must be an object")
        host_wall = text(data, "host_wall", "wall", default="").lower() or None
        explicit_mode = text(data, "mode", default="").lower()
        mode = explicit_mode or ("wall" if host_wall else "free")
        fill = data.get("fill", False)
        if fill not in {True, False}:
            raise ValueError("placement.fill must be a boolean")
        return cls(
            mode=mode,
            host_wall=host_wall,
            offset_mm=optional_number(data, "offset_mm", "offset"),
            origin_x_mm=optional_number(data, "origin_x_mm", "x_mm", "x"),
            origin_y_mm=optional_number(data, "origin_y_mm", "y_mm", "y"),
            origin_z_mm=number(
                data,
                "origin_z_mm",
                "elevation_mm",
                "z_mm",
                "z",
                default=0.0,
            ),
            rotation_z_deg=optional_number(
                data,
                "rotation_z_deg",
                "rotation_deg",
                "rotation",
            ),
            fill=bool(fill),
        )


@dataclass(frozen=True)
class ResolvedPlacement:
    mode: str
    host_wall: str | None
    offset_mm: float | None
    origin_x_mm: float
    origin_y_mm: float
    origin_z_mm: float
    rotation_z_deg: float
    fill: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResolvedPlacement":
        return cls(
            mode=text(data, "mode", default="free").lower(),
            host_wall=text(data, "host_wall", default="").lower() or None,
            offset_mm=optional_number(data, "offset_mm"),
            origin_x_mm=number(data, "origin_x_mm"),
            origin_y_mm=number(data, "origin_y_mm"),
            origin_z_mm=number(data, "origin_z_mm", default=0.0),
            rotation_z_deg=number(data, "rotation_z_deg", default=0.0),
            fill=bool(data.get("fill", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "host_wall": self.host_wall,
            "offset_mm": self.offset_mm,
            "origin_x_mm": self.origin_x_mm,
            "origin_y_mm": self.origin_y_mm,
            "origin_z_mm": self.origin_z_mm,
            "rotation_z_deg": self.rotation_z_deg,
            "fill": self.fill,
        }


@dataclass(frozen=True)
class ItemSpec:
    id: str
    label: str
    category: str
    width: float | None
    depth: float
    height: float
    placement: PlacementRequest
    furniture_category: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> "ItemSpec":
        if not isinstance(data, Mapping):
            raise ValueError(f"items[{index}] must be an object")
        item_id = text(data, "id") or f"item_{index + 1}"
        placement = PlacementRequest.from_dict(mapping(data, "placement"))
        width = optional_number(data, "width", "width_mm")
        depth = number(data, "depth", "depth_mm")
        height = number(data, "height", "height_mm")
        if width is None and not placement.fill:
            raise ValueError("missing numeric field: width")
        require_positive(depth, height)
        if width is not None:
            require_positive(width)
        category = text(data, "category")
        if not category:
            raise ValueError(f"items[{index}].category is required")
        return cls(
            id=item_id,
            label=text(data, "label") or item_id,
            category=category,
            width=width,
            depth=depth,
            height=height,
            placement=placement,
            furniture_category=_optional_furniture_category(data, index),
        )


@dataclass(frozen=True)
class PlacedItem:
    id: str
    label: str
    category: str
    width: float
    depth: float
    height: float
    placement: ResolvedPlacement
    footprint: tuple[tuple[float, float], ...]
    clearances_mm: dict[str, float]
    furniture_category: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> "PlacedItem":
        if not isinstance(data, Mapping):
            raise ValueError(f"items[{index}] must be an object")
        raw_footprint = data.get("footprint", [])
        if not isinstance(raw_footprint, list) or len(raw_footprint) != 4:
            raise ValueError(f"items[{index}].footprint must contain 4 points")
        footprint: list[tuple[float, float]] = []
        for point_index, point in enumerate(raw_footprint):
            if not isinstance(point, Mapping):
                raise ValueError(
                    f"items[{index}].footprint[{point_index}] must be an object"
                )
            footprint.append((number(point, "x_mm"), number(point, "y_mm")))
        raw_clearances = data.get("clearances_mm", {})
        if not isinstance(raw_clearances, Mapping):
            raise ValueError(f"items[{index}].clearances_mm must be an object")
        return cls(
            id=text(data, "id") or f"item_{index + 1}",
            label=text(data, "label") or text(data, "id") or f"item_{index + 1}",
            category=text(data, "category"),
            width=number(data, "width", "width_mm"),
            depth=number(data, "depth", "depth_mm"),
            height=number(data, "height", "height_mm"),
            placement=ResolvedPlacement.from_dict(mapping(data, "placement")),
            footprint=tuple(footprint),
            clearances_mm={
                direction: number(raw_clearances, direction)
                for direction in (
                    "west",
                    "east",
                    "south",
                    "north",
                    "floor",
                    "ceiling",
                )
            },
            furniture_category=_optional_furniture_category(data, index),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "id": self.id,
            "label": self.label,
            "category": self.category,
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "placement": self.placement.to_dict(),
            "footprint": [{"x_mm": x, "y_mm": y} for x, y in self.footprint],
            "clearances_mm": dict(self.clearances_mm),
        }
        if self.furniture_category is not None:
            payload["furniture_category"] = self.furniture_category
        return payload

    @property
    def z_end(self) -> float:
        return self.placement.origin_z_mm + self.height

    @property
    def is_executable(self) -> bool:
        return self.furniture_category in EXECUTABLE_CATEGORIES


@dataclass(frozen=True)
class RoomScene:
    room: RoomModel
    items: tuple[PlacedItem, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoomScene":
        if not isinstance(data, Mapping):
            raise ValueError("scene must be an object")
        raw_items = data.get("items", [])
        if raw_items is None:
            raw_items = []
        if not isinstance(raw_items, list):
            raise ValueError("items must be a list")
        return cls(
            room=RoomModel.from_dict(mapping(data, "room")),
            items=tuple(
                PlacedItem.from_dict(item, index=index)
                for index, item in enumerate(raw_items)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "room": self.room.to_dict(),
            "items": [item.to_dict() for item in self.items],
        }


def parse_item_specs(
    raw_items: Any, *, allow_empty: bool = False
) -> tuple[ItemSpec, ...]:
    if raw_items is None:
        raw_items = []
    if not isinstance(raw_items, list):
        raise ValueError("items must be a list")
    if not raw_items and not allow_empty:
        raise ValueError("items must be a non-empty list")
    specs = tuple(
        ItemSpec.from_dict(item, index=index)
        for index, item in enumerate(raw_items)
    )
    seen: set[str] = set()
    for spec in specs:
        if spec.id in seen:
            raise ValueError(f"duplicate item id: {spec.id}")
        seen.add(spec.id)
    return specs


def _optional_furniture_category(
    data: Mapping[str, Any], index: int
) -> str | None:
    value = text(data, "furniture_category")
    if not value:
        return None
    category = value.lower()
    if category not in EXECUTABLE_CATEGORIES:
        raise ValueError(
            f"items[{index}].furniture_category must be one of: "
            + ", ".join(sorted(EXECUTABLE_CATEGORIES))
        )
    return category
