"""Canonical inputs and placed geometry shared by project and standalone rooms."""

from __future__ import annotations

import re
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from .input_fields import boolean, fields, mapping, number, optional_number, text


WALLS = frozenset({"south", "east", "north", "west"})
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
    "spaces",
})
SPACE_FIELDS = frozenset({
    "id", "kind", "mode", "host_wall", "offset_mm", "width_mm", "depth_mm",
    "height_mm", "origin_x_mm", "origin_y_mm", "origin_z_mm", "constraints",
    "pinned",
})
OPENING_FIELDS = frozenset({
    "id", "kind", "wall", "offset_mm", "width_mm", "height_mm", "sill_height_mm",
})
OBSTACLE_FIELDS = frozenset({
    "id", "kind", "x_mm", "y_mm", "z_mm", "width_mm", "depth_mm", "height_mm",
})
PLACEMENT_FIELDS = frozenset({
    "mode", "host_wall", "offset_mm", "origin_x_mm", "origin_y_mm",
    "origin_z_mm", "rotation_z_deg", "fill",
})
ITEM_FIELDS = frozenset({
    "id", "label", "category", "width", "depth", "height", "placement",
    "furniture_category", "manufacture",
    #: 只对**沿墙铺满**（`placement.fill: true`）有意义：这块墙要做什么柜，
    #: 取值来自工艺目录的 `families`。它是 `fill` 走向"按目录展开成合规单元"的入口；
    #: 普通件不需要它（分几格、每格做什么属于 `spaces[]` 的约束）。
    "kind",
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
        fields(data, PLACEMENT_FIELDS, "placement")
        mode = text(data, "mode")
        if mode not in PLACEMENT_MODES:
            raise ValueError("placement.mode must be wall or free")
        return cls(
            mode=mode,
            host_wall=text(data, "host_wall") or None,
            offset_mm=optional_number(data, "offset_mm"),
            origin_x_mm=optional_number(data, "origin_x_mm"),
            origin_y_mm=optional_number(data, "origin_y_mm"),
            origin_z_mm=number(data, "origin_z_mm", default=0.0),
            rotation_z_deg=optional_number(data, "rotation_z_deg"),
            fill=boolean(data, "fill"),
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
        if not isinstance(data, Mapping):
            raise ValueError("placement must be an object")
        fields(data, PLACEMENT_FIELDS, "placement")
        mode = text(data, "mode")
        if mode not in PLACEMENT_MODES:
            raise ValueError("placement.mode must be wall or free")
        return cls(
            mode=mode,
            host_wall=text(data, "host_wall") or None,
            offset_mm=optional_number(data, "offset_mm"),
            origin_x_mm=number(data, "origin_x_mm"),
            origin_y_mm=number(data, "origin_y_mm"),
            origin_z_mm=number(data, "origin_z_mm", default=0.0),
            rotation_z_deg=number(data, "rotation_z_deg", default=0.0),
            fill=boolean(data, "fill"),
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
    manufacture: bool = True
    #: 沿墙铺满时的柜类（见 ITEM_FIELDS 的说明）：铺满的墙要按目录展开成合规单元。
    kind: str | None = None

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
        kind = text(data, "kind") or None
        if kind and not placement.fill:
            raise ValueError(
                f"items[{index}].kind only applies to fill items: 只有"
                "「把这条墙铺满」才需要在件上说柜类；要分几格、每格做什么，"
                "请写 rooms[].spaces[]"
            )
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
            kind=kind,
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
    #: 沿墙铺满那件的柜类（`fill` 展开时要用；展开后由单元自己带）。
    kind: str | None = None

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
            kind=text(data, "kind") or None,
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
        if self.kind is not None:
            payload["kind"] = self.kind
        if not self.manufacture:
            payload["manufacture"] = False
        return payload

    def to_source(self) -> dict[str, Any]:
        """Editable request fields; wall origins and angles are derived again."""
        payload = self.to_dict()
        del payload["footprint"]
        del payload["clearances_mm"]
        placement = payload["placement"]
        if self.placement.mode == "wall":
            for key in ("origin_x_mm", "origin_y_mm", "rotation_z_deg"):
                del placement[key]
        else:
            for key in ("host_wall", "offset_mm"):
                del placement[key]
        return payload

    @property
    def z_end(self) -> float:
        return self.placement.origin_z_mm + self.height

    @property
    def is_executable(self) -> bool:
        return self.manufacture and self.furniture_category in EXECUTABLE_CATEGORIES


@dataclass(frozen=True)
class SpaceRequest:
    """一块**空间**：区域 + 约束 + 锚（"北墙这 2400 做柜子"）。

    空间是**输入侧的源**：它进 `rooms[].spaces[]`，展开成 `items[]` 里的单元包络。
    它只说"这块地要做什么柜、有什么约束"，**不说"分几格、每格多宽"**——那是解，
    由 `space_split.split_space()` 确定性算出来。

    `kind`（柜类）是受控词表，取值由**工艺目录**的 `families` 决定（`craft_catalog.py`）；
    这里只校验形状，词表准入在求解时做（那时才加载目录）。
    """

    id: str
    kind: str
    mode: str
    width_mm: float
    host_wall: str | None = None
    offset_mm: float | None = None
    origin_x_mm: float | None = None
    origin_y_mm: float | None = None
    depth_mm: float | None = None
    height_mm: float | None = None
    origin_z_mm: float = 0.0
    constraints: tuple[str, ...] = ()
    pinned: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, index: int = 0) -> "SpaceRequest":
        if not isinstance(data, Mapping):
            raise ValueError(f"spaces[{index}] must be an object")
        fields(data, SPACE_FIELDS, f"spaces[{index}]")
        space_id = require_identifier(
            text(data, "id"), where=f"spaces[{index}].id"
        )
        kind = text(data, "kind")
        if not kind:
            raise ValueError(f"spaces[{index}].kind is required")
        mode = text(data, "mode")
        if mode not in PLACEMENT_MODES:
            raise ValueError(
                f"spaces[{index}].mode must be one of: "
                + ", ".join(sorted(PLACEMENT_MODES))
            )
        host_wall = text(data, "host_wall") or None
        offset = optional_number(data, "offset_mm")
        origin_x = optional_number(data, "origin_x_mm")
        origin_y = optional_number(data, "origin_y_mm")
        if mode == "wall":
            if not host_wall or host_wall not in WALLS:
                raise ValueError(
                    f"spaces[{index}].host_wall must be one of: "
                    + ", ".join(sorted(WALLS))
                )
            if offset is None:
                raise ValueError(f"spaces[{index}].offset_mm is required for wall spaces")
        else:
            # 自由空间也要有落脚点：没有坐标就说不清"这块地在哪"（与家具同一条口径）。
            if origin_x is None or origin_y is None:
                raise ValueError(
                    f"spaces[{index}] free space requires origin_x_mm and origin_y_mm"
                )
        width = number(data, "width_mm")
        require_positive(width)
        depth = optional_number(data, "depth_mm")
        height = optional_number(data, "height_mm")
        for label, value in (("depth_mm", depth), ("height_mm", height)):
            if value is not None:
                require_positive(value)
        origin_z = optional_number(data, "origin_z_mm") or 0.0
        if origin_z < 0:
            raise ValueError(f"spaces[{index}].origin_z_mm must not be negative")
        return cls(
            id=space_id,
            kind=kind,
            mode=mode,
            width_mm=width,
            host_wall=host_wall,
            offset_mm=offset,
            origin_x_mm=origin_x,
            origin_y_mm=origin_y,
            depth_mm=depth,
            height_mm=height,
            origin_z_mm=origin_z,
            constraints=_string_tuple(data.get("constraints"), f"spaces[{index}].constraints"),
            pinned=_string_tuple(data.get("pinned"), f"spaces[{index}].pinned"),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "mode": self.mode,
            "width_mm": self.width_mm,
        }
        if self.mode == "wall":
            payload["host_wall"] = self.host_wall
            payload["offset_mm"] = self.offset_mm
        else:
            payload["origin_x_mm"] = self.origin_x_mm
            payload["origin_y_mm"] = self.origin_y_mm
        if self.depth_mm is not None:
            payload["depth_mm"] = self.depth_mm
        if self.height_mm is not None:
            payload["height_mm"] = self.height_mm
        if self.origin_z_mm:
            payload["origin_z_mm"] = self.origin_z_mm
        if self.constraints:
            payload["constraints"] = list(self.constraints)
        if self.pinned:
            payload["pinned"] = list(self.pinned)
        return payload


def parse_space_requests(raw_spaces: Any) -> tuple[SpaceRequest, ...]:
    if raw_spaces is None:
        return ()
    if not isinstance(raw_spaces, list):
        raise ValueError("spaces must be a list")
    spaces = tuple(
        SpaceRequest.from_dict(space, index=index)
        for index, space in enumerate(raw_spaces)
    )
    seen: set[str] = set()
    for space in spaces:
        if space.id in seen:
            raise ValueError(f"duplicate space id: {space.id}")
        seen.add(space.id)
    return spaces


def _string_tuple(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{where} must be a list")
    items: list[str] = []
    for entry in value:
        if not isinstance(entry, str) or not entry.strip():
            raise ValueError(f"{where} must contain non-empty strings")
        items.append(entry)
    return tuple(items)


@dataclass(frozen=True)
class RoomScene:
    room: RoomModel
    items: tuple[PlacedItem, ...]
    #: 这块房间里声明的**空间**（可选）。它是输入侧的源，展开成上面的单元包络；
    #: 下游一个字段都不读它（身份不变式见 references/space-split-design.md）。
    spaces: tuple[SpaceRequest, ...] = ()

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
            spaces=parse_space_requests(data.get("spaces")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "room": self.room.to_dict(),
            "items": [item.to_dict() for item in self.items],
        }
        if self.spaces:
            payload["spaces"] = [space.to_dict() for space in self.spaces]
        return payload


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


def require_identifier(value: str, *, where: str) -> str:
    """**家具单元 id 与空间 id** 的入口校验：合法标识符、不含 `__`。

    为什么卡在入口：板件阶段用这个 id 拼板件编号（`{cabinet_id}__{role}`），
    不合格的 id（`cabinet-1`、`1cabinet`、`a__b`）**建项目时看不出来**，
    要跑到板件才炸。只校验**输入**，不校验读取——库里已有的旧 id 仍能打开，
    由一次性迁移改名（见 references/craft-catalog.md 的"已决定"段与 backlog）。
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
