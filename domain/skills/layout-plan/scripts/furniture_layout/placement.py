"""Resolve wall, free, and fill placements into room-space transforms."""

from __future__ import annotations

from math import cos, isfinite, radians, sin
from typing import Sequence

from .scene import (
    EPSILON,
    ItemSpec,
    PLACEMENT_MODES,
    PlacementRequest,
    PlacedItem,
    ResolvedPlacement,
    RoomModel,
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
) -> ResolvedPlacement:
    if request.mode not in PLACEMENT_MODES:
        raise ValueError(
            "placement.mode must be one of: " + ", ".join(sorted(PLACEMENT_MODES))
        )
    if request.fill and request.mode != "wall":
        raise ValueError("placement.fill requires mode=wall")
    if request.mode == "free":
        if request.origin_x_mm is None or request.origin_y_mm is None:
            raise ValueError("free placement requires origin_x_mm and origin_y_mm")
        if request.host_wall is not None or request.offset_mm is not None:
            raise ValueError("free placement cannot define host_wall or offset_mm")
        return ResolvedPlacement(
            mode="free",
            host_wall=None,
            offset_mm=None,
            origin_x_mm=request.origin_x_mm,
            origin_y_mm=request.origin_y_mm,
            origin_z_mm=request.origin_z_mm,
            rotation_z_deg=request.rotation_z_deg or 0.0,
            fill=False,
        )

    wall = request.host_wall
    if wall not in WALLS:
        raise ValueError(
            "wall placement requires host_wall: " + ", ".join(sorted(WALLS))
        )
    if request.origin_x_mm is not None or request.origin_y_mm is not None:
        raise ValueError(
            "wall placement derives its origin; use offset_mm instead of x/y"
        )
    expected_rotation = WALL_ROTATION_DEG[wall]
    if (
        request.rotation_z_deg is not None
        and abs((request.rotation_z_deg - expected_rotation) % 360.0) > EPSILON
    ):
        raise ValueError(
            f"wall placement rotation is derived as {expected_rotation:g} degrees"
        )
    offset = request.offset_mm or 0.0
    origin = wall_origin(room, wall, offset)
    return ResolvedPlacement(
        mode="wall",
        host_wall=wall,
        offset_mm=offset,
        origin_x_mm=origin[0],
        origin_y_mm=origin[1],
        origin_z_mm=request.origin_z_mm,
        rotation_z_deg=expected_rotation,
        fill=request.fill,
    )


def wall_origin(room: RoomModel, wall: str, offset_mm: float) -> tuple[float, float]:
    return {
        "north": (offset_mm, 0.0),
        "east": (room.width_mm, offset_mm),
        "south": (room.width_mm - offset_mm, room.depth_mm),
        "west": (0.0, room.depth_mm - offset_mm),
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
    )


def place_items(room: RoomModel, specs: Sequence[ItemSpec]) -> tuple[PlacedItem, ...]:
    placed: list[PlacedItem] = []
    deferred_fill: list[ItemSpec] = []
    for spec in specs:
        if spec.placement.fill:
            deferred_fill.append(spec)
            continue
        placed.append(_place_fixed(room, spec))
    for spec in deferred_fill:
        placed.append(_place_fill(room, spec, tuple(placed)))
    _assert_finite_placements(placed)
    return tuple(placed)


def _place_fixed(room: RoomModel, spec: ItemSpec) -> PlacedItem:
    placement = resolve_placement(room, spec.placement)
    return build_placed_item(spec, room, placement, width=spec.width)


def _place_fill(
    room: RoomModel,
    spec: ItemSpec,
    already_placed: tuple[PlacedItem, ...],
) -> PlacedItem:
    wall = spec.placement.host_wall
    if wall not in WALLS:
        raise ValueError(f"item {spec.id!r} fill requires host_wall")
    offset, width = fill_span(
        room,
        spec,
        already_placed,
    )
    request = PlacementRequest(
        mode="wall",
        host_wall=wall,
        offset_mm=offset,
        origin_x_mm=None,
        origin_y_mm=None,
        origin_z_mm=spec.placement.origin_z_mm,
        rotation_z_deg=spec.placement.rotation_z_deg,
        fill=True,
    )
    placement = resolve_placement(room, request)
    return build_placed_item(spec, room, placement, width=width)


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
    requested_offset = spec.placement.offset_mm
    if requested_offset is None:
        start, end = max(free, key=lambda span: span[1] - span[0])
    else:
        match = next(
            (
                span
                for span in free
                if span[0] - EPSILON <= requested_offset <= span[1] + EPSILON
            ),
            None,
        )
        if match is None:
            raise ValueError(
                f"item {spec.id!r} fill offset_mm is not on a free span of {wall}"
            )
        start, end = requested_offset, match[1]
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
