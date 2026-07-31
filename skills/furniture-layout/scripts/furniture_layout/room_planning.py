"""Room-aware furniture placement for the layout-planning checkpoint."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, radians, sin
from typing import Any, Iterable, Mapping

from .layout_planning import CabinetLayout


WALLS = frozenset({"south", "east", "north", "west"})
PLACEMENT_MODES = frozenset({"wall", "free"})
EPSILON = 1e-6


def _number(data: Mapping[str, Any], *keys: str, default: float | None = None) -> float:
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


def _optional_number(data: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in data and data[key] is not None:
            return _number(data, key)
    return None


def _text(data: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        if key in data and data[key] is not None:
            return str(data[key]).strip()
    return default


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
        return cls(
            id=_text(data, "id") or f"opening_{index + 1}",
            kind=(_text(data, "kind") or "opening").lower(),
            wall=_text(data, "wall", default="").lower(),
            offset_mm=_number(data, "offset_mm", "offset", default=0.0),
            width_mm=_number(data, "width_mm", "width"),
            height_mm=_number(data, "height_mm", "height"),
            sill_height_mm=_number(
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
            id=_text(data, "id") or f"obstacle_{index + 1}",
            kind=(_text(data, "kind") or "obstacle").lower(),
            x_mm=_number(data, "x_mm", "x", default=0.0),
            y_mm=_number(data, "y_mm", "y", default=0.0),
            z_mm=_number(data, "z_mm", "z", default=0.0),
            width_mm=_number(data, "width_mm", "width"),
            depth_mm=_number(data, "depth_mm", "depth"),
            height_mm=_number(data, "height_mm", "height"),
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
        return cls(
            id=_text(data, "id", "room_id") or "room",
            name=_text(data, "name") or "房间",
            width_mm=_number(data, "width_mm", "width"),
            depth_mm=_number(data, "depth_mm", "depth"),
            height_mm=_number(data, "height_mm", "height"),
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

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlacementRequest":
        if not isinstance(data, Mapping):
            raise ValueError("placement must be an object")
        host_wall = _text(data, "host_wall", "wall", default="").lower() or None
        explicit_mode = _text(data, "mode", default="").lower()
        mode = explicit_mode or ("wall" if host_wall else "free")
        return cls(
            mode=mode,
            host_wall=host_wall,
            offset_mm=_optional_number(data, "offset_mm", "offset"),
            origin_x_mm=_optional_number(data, "origin_x_mm", "x_mm", "x"),
            origin_y_mm=_optional_number(data, "origin_y_mm", "y_mm", "y"),
            origin_z_mm=_number(
                data,
                "origin_z_mm",
                "elevation_mm",
                "z_mm",
                "z",
                default=0.0,
            ),
            rotation_z_deg=_optional_number(
                data,
                "rotation_z_deg",
                "rotation_deg",
                "rotation",
            ),
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

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResolvedPlacement":
        return cls(
            mode=_text(data, "mode", default="free").lower(),
            host_wall=_text(data, "host_wall", default="").lower() or None,
            offset_mm=_optional_number(data, "offset_mm"),
            origin_x_mm=_number(data, "origin_x_mm"),
            origin_y_mm=_number(data, "origin_y_mm"),
            origin_z_mm=_number(data, "origin_z_mm", default=0.0),
            rotation_z_deg=_number(data, "rotation_z_deg", default=0.0),
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
        }


@dataclass(frozen=True)
class RoomPlacementPlan:
    furniture_label: str
    room: RoomModel
    placement: ResolvedPlacement
    furniture_footprint: tuple[tuple[float, float], ...]
    clearances_mm: dict[str, float]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoomPlacementPlan":
        raw_footprint = data.get("furniture_footprint", [])
        if not isinstance(raw_footprint, list) or len(raw_footprint) != 4:
            raise ValueError("room_placement.furniture_footprint must contain 4 points")
        footprint: list[tuple[float, float]] = []
        for index, point in enumerate(raw_footprint):
            if not isinstance(point, Mapping):
                raise ValueError(
                    f"room_placement.furniture_footprint[{index}] must be an object"
                )
            footprint.append(
                (
                    _number(point, "x_mm"),
                    _number(point, "y_mm"),
                )
            )
        raw_clearances = data.get("clearances_mm", {})
        if not isinstance(raw_clearances, Mapping):
            raise ValueError("room_placement.clearances_mm must be an object")
        return cls(
            furniture_label=_text(
                data,
                "furniture_label",
                default="家具",
            ),
            room=RoomModel.from_dict(_mapping(data, "room")),
            placement=ResolvedPlacement.from_dict(_mapping(data, "placement")),
            furniture_footprint=tuple(footprint),
            clearances_mm={
                direction: _number(raw_clearances, direction)
                for direction in (
                    "west",
                    "east",
                    "south",
                    "north",
                    "floor",
                    "ceiling",
                )
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "furniture_label": self.furniture_label,
            "room": self.room.to_dict(),
            "placement": self.placement.to_dict(),
            "furniture_footprint": [
                {"x_mm": x, "y_mm": y} for x, y in self.furniture_footprint
            ],
            "clearances_mm": dict(self.clearances_mm),
        }


def _mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object")
    return value


def resolve_placement(
    room: RoomModel,
    request: PlacementRequest,
) -> ResolvedPlacement:
    """Resolve wall-relative or free placement to a room-space transform."""
    if request.mode not in PLACEMENT_MODES:
        raise ValueError(
            "placement.mode must be one of: " + ", ".join(sorted(PLACEMENT_MODES))
        )
    if request.mode == "free":
        if request.origin_x_mm is None or request.origin_y_mm is None:
            raise ValueError(
                "free placement requires origin_x_mm and origin_y_mm"
            )
        if request.host_wall is not None or request.offset_mm is not None:
            raise ValueError(
                "free placement cannot define host_wall or offset_mm"
            )
        return ResolvedPlacement(
            mode="free",
            host_wall=None,
            offset_mm=None,
            origin_x_mm=request.origin_x_mm,
            origin_y_mm=request.origin_y_mm,
            origin_z_mm=request.origin_z_mm,
            rotation_z_deg=request.rotation_z_deg or 0.0,
        )

    wall = request.host_wall
    if wall not in WALLS:
        raise ValueError(
            "wall placement requires host_wall: "
            + ", ".join(sorted(WALLS))
        )
    if request.origin_x_mm is not None or request.origin_y_mm is not None:
        raise ValueError(
            "wall placement derives its origin; use offset_mm instead of x/y"
        )
    expected_rotation = {
        "south": 0.0,
        "east": 90.0,
        "north": 180.0,
        "west": 270.0,
    }[wall]
    if (
        request.rotation_z_deg is not None
        and abs((request.rotation_z_deg - expected_rotation) % 360.0) > EPSILON
    ):
        raise ValueError(
            f"wall placement rotation is derived as {expected_rotation:g} degrees"
        )
    offset = request.offset_mm or 0.0
    origin = {
        "south": (offset, 0.0),
        "east": (room.width_mm, offset),
        "north": (room.width_mm - offset, room.depth_mm),
        "west": (0.0, room.depth_mm - offset),
    }[wall]
    return ResolvedPlacement(
        mode="wall",
        host_wall=wall,
        offset_mm=offset,
        origin_x_mm=origin[0],
        origin_y_mm=origin[1],
        origin_z_mm=request.origin_z_mm,
        rotation_z_deg=expected_rotation,
    )


def furniture_footprint(
    layout: CabinetLayout,
    placement: ResolvedPlacement,
) -> tuple[tuple[float, float], ...]:
    angle = radians(placement.rotation_z_deg)
    cos_angle = cos(angle)
    sin_angle = sin(angle)

    def transform(x: float, y: float) -> tuple[float, float]:
        world_x = placement.origin_x_mm + x * cos_angle - y * sin_angle
        world_y = placement.origin_y_mm + x * sin_angle + y * cos_angle
        return (_clean(world_x), _clean(world_y))

    return tuple(
        transform(x, y)
        for x, y in (
            (0.0, 0.0),
            (layout.width, 0.0),
            (layout.width, layout.depth),
            (0.0, layout.depth),
        )
    )


def build_room_placement(
    layout: CabinetLayout,
    room: RoomModel,
    placement: ResolvedPlacement,
    *,
    furniture_label: str,
) -> RoomPlacementPlan:
    footprint = furniture_footprint(layout, placement)
    xs = [point[0] for point in footprint]
    ys = [point[1] for point in footprint]
    return RoomPlacementPlan(
        furniture_label=furniture_label or layout.furniture_type,
        room=room,
        placement=placement,
        furniture_footprint=footprint,
        clearances_mm={
            "west": _clean(min(xs)),
            "east": _clean(room.width_mm - max(xs)),
            "south": _clean(min(ys)),
            "north": _clean(room.depth_mm - max(ys)),
            "floor": _clean(placement.origin_z_mm),
            "ceiling": _clean(
                room.height_mm - placement.origin_z_mm - layout.height
            ),
        },
    )


def plan_room_placement(
    layout: CabinetLayout,
    room_data: Mapping[str, Any],
    placement_data: Mapping[str, Any],
    *,
    furniture_label: str,
) -> RoomPlacementPlan:
    room = RoomModel.from_dict(room_data)
    if not all(
        isfinite(value) and value > 0
        for value in (room.width_mm, room.depth_mm, room.height_mm)
    ):
        raise ValueError("room width, depth, and height must be positive finite numbers")
    placement = resolve_placement(room, PlacementRequest.from_dict(placement_data))
    if not all(
        isfinite(value)
        for value in (
            placement.origin_x_mm,
            placement.origin_y_mm,
            placement.origin_z_mm,
            placement.rotation_z_deg,
        )
    ):
        raise ValueError("placement transform values must be finite")
    return build_room_placement(
        layout,
        room,
        placement,
        furniture_label=furniture_label,
    )


def obstacle_collisions(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
) -> tuple[RoomObstacle, ...]:
    furniture_z_start = plan.placement.origin_z_mm
    furniture_z_end = furniture_z_start + layout.height
    collisions: list[RoomObstacle] = []
    for obstacle in plan.room.obstacles:
        vertical_overlap = _ranges_overlap(
            furniture_z_start,
            furniture_z_end,
            obstacle.z_mm,
            obstacle.z_mm + obstacle.height_mm,
        )
        if vertical_overlap and polygons_overlap(
            plan.furniture_footprint,
            obstacle.footprint,
        ):
            collisions.append(obstacle)
    return tuple(collisions)


def opening_collisions(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
) -> tuple[RoomOpening, ...]:
    furniture_z_start = plan.placement.origin_z_mm
    furniture_z_end = furniture_z_start + layout.height
    collisions: list[RoomOpening] = []
    for opening in plan.room.openings:
        furniture_span = _footprint_span_on_wall(plan, opening.wall)
        if furniture_span is None:
            continue
        furniture_start, furniture_end = furniture_span
        if _ranges_overlap(
            furniture_start,
            furniture_end,
            opening.offset_mm,
            opening.offset_mm + opening.width_mm,
        ) and _ranges_overlap(
            furniture_z_start,
            furniture_z_end,
            opening.sill_height_mm,
            opening.sill_height_mm + opening.height_mm,
        ):
            collisions.append(opening)
    return tuple(collisions)


def _footprint_span_on_wall(
    plan: RoomPlacementPlan,
    wall: str,
) -> tuple[float, float] | None:
    xs = [point[0] for point in plan.furniture_footprint]
    ys = [point[1] for point in plan.furniture_footprint]
    if wall == "south" and min(ys) <= EPSILON:
        return (min(xs), max(xs))
    if wall == "east" and max(xs) >= plan.room.width_mm - EPSILON:
        return (min(ys), max(ys))
    if wall == "north" and max(ys) >= plan.room.depth_mm - EPSILON:
        return (
            plan.room.width_mm - max(xs),
            plan.room.width_mm - min(xs),
        )
    if wall == "west" and min(xs) <= EPSILON:
        return (
            plan.room.depth_mm - max(ys),
            plan.room.depth_mm - min(ys),
        )
    return None


def polygons_overlap(
    first: Iterable[tuple[float, float]],
    second: Iterable[tuple[float, float]],
) -> bool:
    """Return True for positive-area overlap; touching edges are allowed."""
    polygon_a = tuple(first)
    polygon_b = tuple(second)
    for polygon in (polygon_a, polygon_b):
        for index, point in enumerate(polygon):
            next_point = polygon[(index + 1) % len(polygon)]
            edge = (next_point[0] - point[0], next_point[1] - point[1])
            axis = (-edge[1], edge[0])
            projection_a = [
                candidate[0] * axis[0] + candidate[1] * axis[1]
                for candidate in polygon_a
            ]
            projection_b = [
                candidate[0] * axis[0] + candidate[1] * axis[1]
                for candidate in polygon_b
            ]
            if (
                max(projection_a) <= min(projection_b) + EPSILON
                or max(projection_b) <= min(projection_a) + EPSILON
            ):
                return False
    return True


def _ranges_overlap(
    first_start: float,
    first_end: float,
    second_start: float,
    second_end: float,
) -> bool:
    return min(first_end, second_end) > max(first_start, second_start) + EPSILON


def _clean(value: float) -> float:
    return 0.0 if abs(value) < EPSILON else round(value, 6)
