"""Canonical inputs and placed geometry shared by project and standalone rooms."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from .input_fields import boolean, fields, mapping, number, optional_number, text


WALLS = frozenset({"south", "east", "north", "west"})
#: 沿墙两头：先是沿墙起点那一头，再是沿墙终点那一头。与顺时针沿墙方向一致。
WALL_ENDS = {
    "north": ("west", "east"),
    "east": ("north", "south"),
    "south": ("east", "west"),
    "west": ("south", "north"),
}
AGAINST_WALL = "wall"
PLACEMENT_MODES = frozenset({"wall", "free"})
EXECUTABLE_CATEGORIES = frozenset({"floor_cabinet", "wall_cabinet"})
#: 家具单元 id 的形状。板件阶段拿它拼板件编号（`{cabinet_id}__{role}`），
#: 所以必须是合法 Python 标识符、且不含 `__`——与板件阶段的 `admit_cabinet_id()` 是同一条规则。
#: 阶段之间不互相 import，所以两边各写一条，由 tests/test_skill_architecture.py 钉住一致。
ITEM_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PANEL_ID_SEPARATOR = "__"
EPSILON = 1e-6

ROOM_FIELDS = frozenset({
    "id", "name", "width_mm", "depth_mm", "height_mm", "openings", "obstacles",
})
OPENING_FIELDS = frozenset({
    "id", "kind", "wall", "offset_mm", "width_mm", "height_mm", "sill_height_mm",
})
OBSTACLE_FIELDS = frozenset({
    "id", "kind", "x_mm", "y_mm", "z_mm", "width_mm", "depth_mm", "height_mm",
})
#: 靠墙柜子不收沿墙偏移。起点由包络贴合算出，只留在结果的原点里。
#: against 是沿墙两头贴墙还是贴着哪一台，会原样留在下一次请求里。
PLACEMENT_FIELDS = frozenset({
    "mode", "host_wall", "origin_x_mm", "origin_y_mm",
    "origin_z_mm", "rotation_z_deg", "fill", "against",
})
RESOLVED_PLACEMENT_FIELDS = PLACEMENT_FIELDS
ITEM_FIELDS = frozenset({
    "id", "label", "category", "width", "depth", "height", "placement",
    "furniture_category", "manufacture",
})
PLACED_ITEM_FIELDS = ITEM_FIELDS | {"footprint", "clearances_mm"}


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
        fields(data, OPENING_FIELDS, f"room.openings[{index}]")
        wall = text(data, "wall")
        kind = text(data, "kind")
        if kind not in {"door", "window"}:
            raise ValueError("opening.kind must be door or window")
        if wall not in WALLS:
            raise ValueError(
                f"room.openings[{index}].wall must be one of: "
                + ", ".join(sorted(WALLS))
            )
        return cls(
            id=text(data, "id") or f"opening_{index + 1}",
            kind=kind,
            wall=wall,
            offset_mm=number(data, "offset_mm", default=0.0),
            width_mm=number(data, "width_mm"),
            height_mm=number(data, "height_mm"),
            sill_height_mm=number(
                data,
                "sill_height_mm",
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
        fields(data, OBSTACLE_FIELDS, f"room.obstacles[{index}]")
        return cls(
            id=text(data, "id") or f"obstacle_{index + 1}",
            kind=text(data, "kind") or "obstacle",
            x_mm=number(data, "x_mm", default=0.0),
            y_mm=number(data, "y_mm", default=0.0),
            z_mm=number(data, "z_mm", default=0.0),
            width_mm=number(data, "width_mm"),
            depth_mm=number(data, "depth_mm"),
            height_mm=number(data, "height_mm"),
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
        fields(data, ROOM_FIELDS, "room")
        raw_openings = data.get("openings", [])
        raw_obstacles = data.get("obstacles", [])
        if not isinstance(raw_openings, list):
            raise ValueError("room.openings must be a list")
        if not isinstance(raw_obstacles, list):
            raise ValueError("room.obstacles must be a list")
        width_mm = number(data, "width_mm")
        depth_mm = number(data, "depth_mm")
        height_mm = number(data, "height_mm")
        require_positive(width_mm, depth_mm, height_mm)
        return cls(
            id=text(data, "id") or "room",
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
    origin_x_mm: float | None
    origin_y_mm: float | None
    origin_z_mm: float
    rotation_z_deg: float | None
    fill: bool = False
    against: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PlacementRequest":
        if not isinstance(data, Mapping):
            raise ValueError("placement must be an object")
        fields(data, PLACEMENT_FIELDS, "placement")
        mode = text(data, "mode")
        if mode not in PLACEMENT_MODES:
            raise ValueError("placement.mode must be wall or free")
        host_wall = text(data, "host_wall") or None
        return cls(
            mode=mode,
            host_wall=host_wall,
            origin_x_mm=optional_number(data, "origin_x_mm"),
            origin_y_mm=optional_number(data, "origin_y_mm"),
            origin_z_mm=number(data, "origin_z_mm", default=0.0),
            rotation_z_deg=optional_number(data, "rotation_z_deg"),
            fill=boolean(data, "fill"),
            against=_parse_against(data, mode=mode, host_wall=host_wall),
        )


@dataclass(frozen=True)
class ResolvedPlacement:
    mode: str
    host_wall: str | None
    origin_x_mm: float
    origin_y_mm: float
    origin_z_mm: float
    rotation_z_deg: float
    fill: bool = False
    against: tuple[tuple[str, str], ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ResolvedPlacement":
        if not isinstance(data, Mapping):
            raise ValueError("placement must be an object")
        fields(data, RESOLVED_PLACEMENT_FIELDS, "placement")
        mode = text(data, "mode")
        if mode not in PLACEMENT_MODES:
            raise ValueError("placement.mode must be wall or free")
        host_wall = text(data, "host_wall") or None
        return cls(
            mode=mode,
            host_wall=host_wall,
            origin_x_mm=number(data, "origin_x_mm"),
            origin_y_mm=number(data, "origin_y_mm"),
            origin_z_mm=number(data, "origin_z_mm", default=0.0),
            rotation_z_deg=number(data, "rotation_z_deg", default=0.0),
            fill=boolean(data, "fill"),
            against=_parse_against(data, mode=mode, host_wall=host_wall),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "mode": self.mode,
            "host_wall": self.host_wall,
            "origin_x_mm": self.origin_x_mm,
            "origin_y_mm": self.origin_y_mm,
            "origin_z_mm": self.origin_z_mm,
            "rotation_z_deg": self.rotation_z_deg,
            "fill": self.fill,
        }
        if self.against:
            payload["against"] = {direction: value for direction, value in self.against}
        return payload


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
    manufacture: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> "ItemSpec":
        if not isinstance(data, Mapping):
            raise ValueError(f"items[{index}] must be an object")
        fields(data, ITEM_FIELDS, f"items[{index}]")
        item_id = require_identifier(
            text(data, "id") or f"item_{index + 1}", where=f"items[{index}].id"
        )
        placement = PlacementRequest.from_dict(mapping(data, "placement"))
        width = optional_number(data, "width")
        depth = number(data, "depth")
        height = number(data, "height")
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
            manufacture=boolean(data, "manufacture", default=True),
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
    manufacture: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> "PlacedItem":
        if not isinstance(data, Mapping):
            raise ValueError(f"items[{index}] must be an object")
        fields(data, PLACED_ITEM_FIELDS, f"items[{index}]")
        raw_footprint = data.get("footprint", [])
        if not isinstance(raw_footprint, list) or len(raw_footprint) != 4:
            raise ValueError(f"items[{index}].footprint must contain 4 points")
        footprint: list[tuple[float, float]] = []
        for point_index, point in enumerate(raw_footprint):
            if not isinstance(point, Mapping):
                raise ValueError(
                    f"items[{index}].footprint[{point_index}] must be an object"
                )
            fields(point, {"x_mm", "y_mm"}, f"items[{index}].footprint[{point_index}]")
            footprint.append((number(point, "x_mm"), number(point, "y_mm")))
        raw_clearances = data.get("clearances_mm", {})
        if not isinstance(raw_clearances, Mapping):
            raise ValueError(f"items[{index}].clearances_mm must be an object")
        return cls(
            id=text(data, "id") or f"item_{index + 1}",
            label=text(data, "label") or text(data, "id") or f"item_{index + 1}",
            category=text(data, "category"),
            width=number(data, "width"),
            depth=number(data, "depth"),
            height=number(data, "height"),
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
            manufacture=boolean(data, "manufacture", default=True),
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
        if not self.manufacture:
            payload["manufacture"] = False
        return payload

    def to_source(self) -> dict[str, Any]:
        """Editable request fields. Wall corners are packed again next time."""
        payload = self.to_dict()
        del payload["footprint"]
        del payload["clearances_mm"]
        placement = payload["placement"]
        if self.placement.mode == "wall":
            for key in ("origin_x_mm", "origin_y_mm", "rotation_z_deg"):
                del placement[key]
        else:
            placement.pop("host_wall", None)
        return payload

    @property
    def z_end(self) -> float:
        return self.placement.origin_z_mm + self.height

    @property
    def is_executable(self) -> bool:
        return self.manufacture and self.furniture_category in EXECUTABLE_CATEGORIES


@dataclass(frozen=True)
class RoomScene:
    room: RoomModel
    items: tuple[PlacedItem, ...]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RoomScene":
        if not isinstance(data, Mapping):
            raise ValueError("scene must be an object")
        raw_items = data.get("items", [])
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


def _parse_against(
    data: Mapping[str, Any], *, mode: str, host_wall: str | None
) -> tuple[tuple[str, str], ...]:
    """沿墙两头。值 ``wall`` 是贴到侧面的墙，其他值是柜子 id。"""
    if "against" not in data or data.get("against") is None:
        return ()
    raw = data["against"]
    if not isinstance(raw, Mapping):
        raise ValueError("placement.against must be an object")
    fields(raw, WALLS, "placement.against")
    written = {
        direction: value for direction, value in raw.items() if value is not None
    }
    if mode == "free":
        if written:
            raise ValueError("free placement cannot define against")
        return ()
    if host_wall not in WALL_ENDS:
        if written:
            raise ValueError("placement.against requires host_wall")
        return ()
    low, high = WALL_ENDS[host_wall]
    pairs: list[tuple[str, str]] = []
    for direction in (low, high):
        if direction not in written:
            continue
        pairs.append((direction, _against_token(written[direction], direction)))
    for direction in written:
        if direction not in {low, high}:
            raise ValueError(
                f"placement.against on {host_wall} only allows {low} and {high}"
            )
    return tuple(pairs)


def _against_token(value: Any, direction: str) -> str:
    if isinstance(value, str):
        token = value.strip()
        if token == AGAINST_WALL or (
            ITEM_ID_PATTERN.fullmatch(token) and PANEL_ID_SEPARATOR not in token
        ):
            return token
    raise ValueError(
        f"placement.against.{direction} must be wall or a cabinet id"
    )


def require_identifier(value: str, *, where: str) -> str:
    """**家具单元 id 与空间 id** 的入口校验：合法标识符、不含 `__`。

    为什么卡在入口：板件阶段用这个 id 拼板件编号（`{cabinet_id}__{role}`），
    不合格的 id（`cabinet-1`、`1cabinet`、`a__b`）**建项目时看不出来**，
    要跑到板件才炸。只校验**输入**，不校验读取——库里已有的旧 id 仍能打开，
    由一次性迁移改名（见 references/backlog.md）。
    """
    if not ITEM_ID_PATTERN.fullmatch(value) or PANEL_ID_SEPARATOR in value:
        raise ValueError(
            f"{where} {value!r} is not usable: an id must be a Python identifier "
            "(letters, digits, underscore; not starting with a digit) and must not "
            "contain '__', because the panel stage builds panel ids from it"
        )
    return value


def _optional_furniture_category(
    data: Mapping[str, Any], index: int
) -> str | None:
    value = text(data, "furniture_category")
    if not value:
        return None
    if value not in EXECUTABLE_CATEGORIES:
        raise ValueError(
            f"items[{index}].furniture_category must be one of: "
            + ", ".join(sorted(EXECUTABLE_CATEGORIES))
        )
    return value
