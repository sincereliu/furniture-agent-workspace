"""Resolve wall, free, and fill placements into room-space transforms."""

from __future__ import annotations

from math import cos, isfinite, radians, sin
from typing import Sequence

from .scene import (
    EPSILON,
    AGAINST_WALL,
    ItemSpec,
    PLACEMENT_MODES,
    PlacementRequest,
    PlacedItem,
    ResolvedPlacement,
    RoomModel,
    WALL_ENDS,
    WALLS,
    clean,
)


WALL_ROTATION_DEG = {
    "south": 180.0,
    "east": 90.0,
    "north": 0.0,
    "west": 270.0,
}


def resolve_placement(
    room: RoomModel,
    request: PlacementRequest,
    *,
    along_mm: float = 0.0,
) -> ResolvedPlacement:
    """Turn a request into a room transform.

    ``along_mm`` is the packed start of a wall envelope. Callers compute it
    from neighboring envelopes. It is not a customer offset.
    """
    if request.mode not in PLACEMENT_MODES:
        raise ValueError(
            "placement.mode must be one of: " + ", ".join(sorted(PLACEMENT_MODES))
        )
    if request.fill and request.mode != "wall":
        raise ValueError("placement.fill requires mode=wall")
    if request.mode == "free":
        if request.origin_x_mm is None or request.origin_y_mm is None:
            raise ValueError("free placement requires origin_x_mm and origin_y_mm")
        if request.host_wall is not None:
            raise ValueError("free placement cannot define host_wall")
        return ResolvedPlacement(
            mode="free",
            host_wall=None,
            origin_x_mm=request.origin_x_mm,
            origin_y_mm=request.origin_y_mm,
            origin_z_mm=request.origin_z_mm,
            rotation_z_deg=request.rotation_z_deg or 0.0,
            fill=False,
            against=request.against,
        )

    wall = request.host_wall
    if wall not in WALLS:
        raise ValueError(
            "wall placement requires host_wall: " + ", ".join(sorted(WALLS))
        )
    if request.origin_x_mm is not None or request.origin_y_mm is not None:
        raise ValueError(
            "wall placement derives its origin from how envelopes fit"
        )
    expected_rotation = WALL_ROTATION_DEG[wall]
    if (
        request.rotation_z_deg is not None
        and abs((request.rotation_z_deg - expected_rotation) % 360.0) > EPSILON
    ):
        raise ValueError(
            f"wall placement rotation is derived as {expected_rotation:g} degrees"
        )
    origin = wall_origin(room, wall, along_mm)
    return ResolvedPlacement(
        mode="wall",
        host_wall=wall,
        origin_x_mm=origin[0],
        origin_y_mm=origin[1],
        origin_z_mm=request.origin_z_mm,
        rotation_z_deg=expected_rotation,
        fill=request.fill,
        against=request.against,
    )


def wall_origin(room: RoomModel, wall: str, along_mm: float) -> tuple[float, float]:
    """Envelope corner for a back that sits on ``wall`` at packed start ``along_mm``."""
    return {
        "north": (along_mm, 0.0),
        "east": (room.width_mm, along_mm),
        "south": (room.width_mm - along_mm, room.depth_mm),
        "west": (0.0, room.depth_mm - along_mm),
    }[wall]


def furniture_footprint(
    width: float,
    depth: float,
    placement: ResolvedPlacement,
) -> tuple[tuple[float, float], ...]:
    angle = radians(placement.rotation_z_deg)
    cos_angle = cos(angle)
    sin_angle = sin(angle)

    def transform(x: float, y: float) -> tuple[float, float]:
        world_x = placement.origin_x_mm + x * cos_angle - y * sin_angle
        world_y = placement.origin_y_mm + x * sin_angle + y * cos_angle
        return (clean(world_x), clean(world_y))

    return tuple(
        transform(x, y)
        for x, y in (
            (0.0, 0.0),
            (width, 0.0),
            (width, depth),
            (0.0, depth),
        )
    )


def build_placed_item(
    spec: ItemSpec,
    room: RoomModel,
    placement: ResolvedPlacement,
    *,
    width: float,
) -> PlacedItem:
    footprint = furniture_footprint(width, spec.depth, placement)
    xs = [point[0] for point in footprint]
    ys = [point[1] for point in footprint]
    return PlacedItem(
        id=spec.id,
        label=spec.label,
        category=spec.category,
        width=width,
        depth=spec.depth,
        height=spec.height,
        placement=placement,
        footprint=footprint,
        clearances_mm={
            "west": clean(min(xs)),
            "east": clean(room.width_mm - max(xs)),
            "south": clean(room.depth_mm - max(ys)),
            "north": clean(min(ys)),
            "floor": clean(placement.origin_z_mm),
            "ceiling": clean(room.height_mm - placement.origin_z_mm - spec.height),
        },
        furniture_category=spec.furniture_category,
        manufacture=spec.manufacture,
    )


# (宿主墙, 这一头的方向) → 墙角。同一墙角只能有一台把这一头写成 wall。
CORNER_OF = {
    ("north", "west"): "northwest",
    ("north", "east"): "northeast",
    ("east", "north"): "northeast",
    ("east", "south"): "southeast",
    ("south", "east"): "southeast",
    ("south", "west"): "southwest",
    ("west", "south"): "southwest",
    ("west", "north"): "northwest",
}


def place_items(room: RoomModel, specs: Sequence[ItemSpec]) -> tuple[PlacedItem, ...]:
    """摆下一间房的包络。

    固定宽度里写了 against 的先占它声明的那一头。普通固定宽度柜子接着按清单
    占最早空段。铺满最后摆：没写 against 占最长空段，写了就占贴着那一头的空段。
    """
    specs = tuple(specs)
    _reject_corner_claims(specs)
    _reject_against_targets(specs)
    placed: dict[str, PlacedItem] = {}
    _place_group(room, [spec for spec in specs if not spec.placement.fill], placed)
    _place_group(room, [spec for spec in specs if spec.placement.fill], placed)
    ordered = [spec for spec in specs if not spec.placement.fill]
    ordered += [spec for spec in specs if spec.placement.fill]
    items = [placed[spec.id] for spec in ordered]
    _assert_finite_placements(items)
    return tuple(items)


def _place_group(
    room: RoomModel,
    group: Sequence[ItemSpec],
    placed: dict[str, PlacedItem],
) -> None:
    pending = {spec.id for spec in group}
    while pending:
        explicit = [
            spec
            for spec in group
            if spec.id in pending
            and spec.placement.against
            and _against_ready(spec, placed)
        ]
        if explicit:
            for spec in explicit:
                _commit(room, spec, placed, pending)
            continue
        blockers = [
            spec
            for spec in group
            if spec.id in pending
            and spec.id in _unplaced_targets(group, pending, placed)
            and _against_ready(spec, placed)
        ]
        if blockers:
            for spec in blockers:
                _commit(room, spec, placed, pending)
            continue
        if any(_against_targets(spec) for spec in group if spec.id in pending):
            names = ", ".join(sorted(pending))
            raise ValueError(f"against cycle: {names}")
        for spec in group:
            if spec.id in pending:
                _commit(room, spec, placed, pending)
        return


def _commit(
    room: RoomModel,
    spec: ItemSpec,
    placed: dict[str, PlacedItem],
    pending: set[str],
) -> None:
    placed[spec.id] = _place_one(room, spec, tuple(placed.values()))
    pending.remove(spec.id)


def _place_one(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: tuple[PlacedItem, ...],
) -> PlacedItem:
    if spec.placement.mode != "wall" or not spec.placement.against:
        if spec.placement.fill:
            return _place_fill(room, spec, already_placed)
        return _place_fixed(room, spec, already_placed)
    along, width = _against_interval(room, spec, already_placed)
    placement = resolve_placement(room, spec.placement, along_mm=along)
    return build_placed_item(spec, room, placement, width=width)


def _against_targets(spec: ItemSpec) -> tuple[str, ...]:
    return tuple(
        value for _direction, value in spec.placement.against if value != AGAINST_WALL
    )


def _against_ready(spec: ItemSpec, placed: dict[str, PlacedItem]) -> bool:
    return all(target in placed for target in _against_targets(spec))


def _unplaced_targets(
    group: Sequence[ItemSpec],
    pending: set[str],
    placed: dict[str, PlacedItem],
) -> set[str]:
    needed: set[str] = set()
    for spec in group:
        if spec.id not in pending:
            continue
        for target in _against_targets(spec):
            if target not in placed and target in pending:
                needed.add(target)
    return needed


def _reject_corner_claims(specs: Sequence[ItemSpec]) -> None:
    """同一墙角、高度重叠的柜子里，只能有一台把这一头写成 wall。"""
    claimed: dict[str, list[ItemSpec]] = {}
    for spec in specs:
        wall = spec.placement.host_wall
        for direction, value in spec.placement.against:
            if value != AGAINST_WALL or wall is None:
                continue
            corner = CORNER_OF[(wall, direction)]
            z_start = spec.placement.origin_z_mm
            z_end = z_start + spec.height
            for previous in claimed.get(corner, ()):
                if ranges_overlap(
                    z_start,
                    z_end,
                    previous.placement.origin_z_mm,
                    previous.placement.origin_z_mm + previous.height,
                ):
                    raise ValueError(
                        f"{corner} corner is claimed by {previous.id!r} and {spec.id!r}"
                    )
            claimed.setdefault(corner, []).append(spec)


def _reject_against_targets(specs: Sequence[ItemSpec]) -> None:
    by_id = {spec.id: spec for spec in specs}
    for spec in specs:
        for direction, value in spec.placement.against:
            if value == AGAINST_WALL:
                continue
            if value == spec.id:
                raise ValueError(
                    f"item {spec.id!r} against.{direction} names itself"
                )
            target = by_id.get(value)
            if target is None:
                raise ValueError(
                    f"item {spec.id!r} against.{direction} names unknown item {value!r}"
                )
            if target.placement.fill and not spec.placement.fill:
                raise ValueError(
                    f"item {spec.id!r} against.{direction} names {value!r}; "
                    "a fixed cabinet cannot stop against a fill"
                )


def _against_interval(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: Sequence[PlacedItem],
) -> tuple[float, float]:
    wall = spec.placement.host_wall
    if wall not in WALL_ENDS:
        raise ValueError(f"item {spec.id!r} wall placement requires host_wall")
    placed = {item.id: item for item in already_placed}
    low, high = WALL_ENDS[wall]
    against = dict(spec.placement.against)
    low_at = (
        _end_contact(room, spec, placed, low, against[low]) if low in against else None
    )
    high_at = (
        _end_contact(room, spec, placed, high, against[high])
        if high in against
        else None
    )
    length = room.wall_length(wall)
    if low_at is not None and high_at is not None:
        if high_at <= low_at + EPSILON:
            raise ValueError(
                f"item {spec.id!r} against ends do not form a span on {wall}"
            )
        width = high_at - low_at
        if (
            not spec.placement.fill
            and spec.width is not None
            and abs(spec.width - width) > EPSILON
        ):
            raise ValueError(
                f"item {spec.id!r} width does not match its against ends"
            )
        _require_free(room, spec, already_placed, low_at, high_at)
        return clean(low_at), clean(width if spec.placement.fill else spec.width or width)
    if low_at is not None:
        return _one_end(
            room, spec, already_placed, contact=low_at, at_low=True, length=length
        )
    if high_at is None:
        raise ValueError(f"item {spec.id!r} against does not name an end")
    return _one_end(
        room, spec, already_placed, contact=high_at, at_low=False, length=length
    )


def _one_end(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: Sequence[PlacedItem],
    *,
    contact: float,
    at_low: bool,
    length: float,
) -> tuple[float, float]:
    wall = spec.placement.host_wall or ""
    if spec.placement.fill:
        start, end = _touching_free_span(
            room, spec, already_placed, contact, at_low=at_low
        )
        return clean(start), clean(end - start)
    if spec.width is None:
        raise ValueError(f"item {spec.id!r} requires width without fill")
    if at_low:
        start, end = contact, contact + spec.width
    else:
        start, end = contact - spec.width, contact
    if start < -EPSILON or end > length + EPSILON:
        raise ValueError(f"item {spec.id!r} envelope does not fit on {wall} wall")
    _require_free(room, spec, already_placed, start, end)
    return clean(start), clean(spec.width)


def _end_contact(
    room: RoomModel,
    spec: ItemSpec,
    placed: dict[str, PlacedItem],
    direction: str,
    value: str,
) -> float:
    wall = spec.placement.host_wall
    if wall not in WALL_ENDS:
        raise ValueError(f"item {spec.id!r} wall placement requires host_wall")
    low, _high = WALL_ENDS[wall]
    if value == AGAINST_WALL:
        return 0.0 if direction == low else room.wall_length(wall)
    target = placed[value]
    if not ranges_overlap(
        spec.placement.origin_z_mm,
        spec.placement.origin_z_mm + spec.height,
        target.placement.origin_z_mm,
        target.z_end,
    ):
        raise ValueError(
            f"item {spec.id!r} against.{direction} names {value!r}, "
            "which does not meet that end"
        )
    span = footprint_span_on_wall(room, wall, target.footprint)
    if span is None:
        raise ValueError(
            f"item {spec.id!r} against.{direction} names {value!r}, "
            "which does not meet that end"
        )
    return span[1] if direction == low else span[0]


def _require_free(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: Sequence[PlacedItem],
    start: float,
    end: float,
) -> None:
    wall = spec.placement.host_wall
    if wall not in WALLS:
        raise ValueError(f"item {spec.id!r} wall placement requires host_wall")
    occupied = occupied_wall_spans(
        room,
        wall,
        z_start=spec.placement.origin_z_mm,
        z_end=spec.placement.origin_z_mm + spec.height,
        already_placed=already_placed,
    )
    for occupied_start, occupied_end in occupied:
        if ranges_overlap(start, end, occupied_start, occupied_end):
            raise ValueError(f"item {spec.id!r} envelope does not fit on {wall} wall")


def _touching_free_span(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: Sequence[PlacedItem],
    contact: float,
    *,
    at_low: bool,
) -> tuple[float, float]:
    wall = spec.placement.host_wall
    if wall not in WALLS:
        raise ValueError(f"item {spec.id!r} wall placement requires host_wall")
    free = free_spans(
        room.wall_length(wall),
        occupied_wall_spans(
            room,
            wall,
            z_start=spec.placement.origin_z_mm,
            z_end=spec.placement.origin_z_mm + spec.height,
            already_placed=already_placed,
        ),
    )
    for start, end in free:
        if at_low and abs(start - contact) <= EPSILON:
            return start, end
        if not at_low and abs(end - contact) <= EPSILON:
            return start, end
    raise ValueError(f"item {spec.id!r} has no free span on {wall} wall")


def _place_fixed(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: tuple[PlacedItem, ...],
) -> PlacedItem:
    if spec.width is None:
        raise ValueError(f"item {spec.id!r} requires width without fill")
    along = 0.0
    if spec.placement.mode == "wall":
        along = pack_along(room, spec, already_placed, spec.width)
    placement = resolve_placement(room, spec.placement, along_mm=along)
    return build_placed_item(spec, room, placement, width=spec.width)


def _place_fill(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: tuple[PlacedItem, ...],
) -> PlacedItem:
    resolve_placement(room, spec.placement, along_mm=0.0)
    along, width = fill_span(room, spec, already_placed)
    placement = resolve_placement(room, spec.placement, along_mm=along)
    return build_placed_item(spec, room, placement, width=width)


def pack_along(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: Sequence[PlacedItem],
    width: float,
) -> float:
    """Start of the earliest free span on the host wall that can hold ``width``."""
    wall = spec.placement.host_wall
    if wall not in WALLS:
        raise ValueError(f"item {spec.id!r} wall placement requires host_wall")
    length = room.wall_length(wall)
    occupied = occupied_wall_spans(
        room,
        wall,
        z_start=spec.placement.origin_z_mm,
        z_end=spec.placement.origin_z_mm + spec.height,
        already_placed=already_placed,
    )
    for start, end in free_spans(length, occupied):
        if end - start + EPSILON >= width:
            return clean(start)
    raise ValueError(f"item {spec.id!r} envelope does not fit on {wall} wall")


def fill_span(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: Sequence[PlacedItem],
) -> tuple[float, float]:
    wall = spec.placement.host_wall
    if wall not in WALLS:
        raise ValueError(f"item {spec.id!r} fill requires host_wall")
    length = room.wall_length(wall)
    occupied = occupied_wall_spans(
        room,
        wall,
        z_start=spec.placement.origin_z_mm,
        z_end=spec.placement.origin_z_mm + spec.height,
        already_placed=already_placed,
    )
    free = free_spans(length, occupied)
    if not free:
        raise ValueError(f"item {spec.id!r} has no free span on {wall} wall")
    start, end = max(free, key=lambda span: span[1] - span[0])
    width = end - start
    if width <= EPSILON:
        raise ValueError(f"item {spec.id!r} fill span on {wall} is empty")
    return (clean(start), clean(width))


def occupied_wall_spans(
    room: RoomModel,
    wall: str,
    *,
    z_start: float,
    z_end: float,
    already_placed: Sequence[PlacedItem],
) -> list[tuple[float, float]]:
    occupied: list[tuple[float, float]] = []
    for opening in room.openings:
        if opening.wall != wall:
            continue
        if not ranges_overlap(
            z_start,
            z_end,
            opening.sill_height_mm,
            opening.sill_height_mm + opening.height_mm,
        ):
            continue
        occupied.append(
            (opening.offset_mm, opening.offset_mm + opening.width_mm)
        )
    for obstacle in room.obstacles:
        if not ranges_overlap(
            z_start,
            z_end,
            obstacle.z_mm,
            obstacle.z_mm + obstacle.height_mm,
        ):
            continue
        span = footprint_span_on_wall(room, wall, obstacle.footprint)
        if span is not None:
            occupied.append(span)
    for item in already_placed:
        if not ranges_overlap(
            z_start,
            z_end,
            item.placement.origin_z_mm,
            item.z_end,
        ):
            continue
        span = footprint_span_on_wall(room, wall, item.footprint)
        if span is not None:
            occupied.append(span)
    return occupied


def footprint_span_on_wall(
    room: RoomModel,
    wall: str,
    footprint: Sequence[tuple[float, float]],
) -> tuple[float, float] | None:
    xs = [point[0] for point in footprint]
    ys = [point[1] for point in footprint]
    if wall == "north" and min(ys) <= EPSILON:
        return (min(xs), max(xs))
    if wall == "east" and max(xs) >= room.width_mm - EPSILON:
        return (min(ys), max(ys))
    if wall == "south" and max(ys) >= room.depth_mm - EPSILON:
        return (
            room.width_mm - max(xs),
            room.width_mm - min(xs),
        )
    if wall == "west" and min(xs) <= EPSILON:
        return (
            room.depth_mm - max(ys),
            room.depth_mm - min(ys),
        )
    return None


def free_spans(
    length: float,
    occupied: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    merged: list[list[float]] = []
    for start, end in sorted(occupied):
        if end <= start + EPSILON:
            continue
        if not merged or start > merged[-1][1] + EPSILON:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    free: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in merged:
        clipped_start = max(start, 0.0)
        clipped_end = min(end, length)
        if clipped_start > cursor + EPSILON:
            free.append((cursor, clipped_start))
        cursor = max(cursor, clipped_end)
    if length > cursor + EPSILON:
        free.append((cursor, length))
    return free


def ranges_overlap(
    first_start: float,
    first_end: float,
    second_start: float,
    second_end: float,
) -> bool:
    return min(first_end, second_end) > max(first_start, second_start) + EPSILON


def _assert_finite_placements(items: Sequence[PlacedItem]) -> None:
    for item in items:
        placement = item.placement
        if not all(
            isfinite(value)
            for value in (
                placement.origin_x_mm,
                placement.origin_y_mm,
                placement.origin_z_mm,
                placement.rotation_z_deg,
                item.width,
                item.depth,
                item.height,
            )
        ):
            raise ValueError(f"item {item.id!r} transform values must be finite")
