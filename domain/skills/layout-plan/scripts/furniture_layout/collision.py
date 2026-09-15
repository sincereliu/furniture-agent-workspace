"""Geometric collisions for a multi-item room scene."""

from __future__ import annotations

from typing import Iterable

from .placement import footprint_span_on_wall, ranges_overlap
from .scene import EPSILON, PlacedItem, RoomModel, RoomObstacle, RoomOpening, RoomScene


def item_outside_room(room: RoomModel, item: PlacedItem) -> bool:
    return any(
        x < -EPSILON
        or x > room.width_mm + EPSILON
        or y < -EPSILON
        or y > room.depth_mm + EPSILON
        for x, y in item.footprint
    ) or item.placement.origin_z_mm < -EPSILON or (
        item.z_end > room.height_mm + EPSILON
    )


def obstacle_collisions(
    room: RoomModel,
    item: PlacedItem,
) -> tuple[RoomObstacle, ...]:
    hits: list[RoomObstacle] = []
    for obstacle in room.obstacles:
        if ranges_overlap(
            item.placement.origin_z_mm,
            item.z_end,
            obstacle.z_mm,
            obstacle.z_mm + obstacle.height_mm,
        ) and polygons_overlap(item.footprint, obstacle.footprint):
            hits.append(obstacle)
    return tuple(hits)


def opening_collisions(
    room: RoomModel,
    item: PlacedItem,
) -> tuple[RoomOpening, ...]:
    hits: list[RoomOpening] = []
    for opening in room.openings:
        span = footprint_span_on_wall(room, opening.wall, item.footprint)
        if span is None:
            continue
        if ranges_overlap(
            span[0],
            span[1],
            opening.offset_mm,
            opening.offset_mm + opening.width_mm,
        ) and ranges_overlap(
            item.placement.origin_z_mm,
            item.z_end,
            opening.sill_height_mm,
            opening.sill_height_mm + opening.height_mm,
        ):
            hits.append(opening)
    return tuple(hits)


def item_collisions(
    item: PlacedItem,
    others: Iterable[PlacedItem],
) -> tuple[PlacedItem, ...]:
    hits: list[PlacedItem] = []
    for other in others:
        if other.id == item.id:
            continue
        if ranges_overlap(
            item.placement.origin_z_mm,
            item.z_end,
            other.placement.origin_z_mm,
            other.z_end,
        ) and polygons_overlap(item.footprint, other.footprint):
            hits.append(other)
    return tuple(hits)


def scene_collisions(scene: RoomScene) -> dict[str, tuple[str, ...]]:
    """Return item-id -> collision descriptions for every failing item."""
    report: dict[str, tuple[str, ...]] = {}
    for item in scene.items:
        labels: list[str] = []
        if item_outside_room(scene.room, item):
            labels.append("outside_room")
        for obstacle in obstacle_collisions(scene.room, item):
            labels.append(f"obstacle:{obstacle.id}")
        for opening in opening_collisions(scene.room, item):
            labels.append(f"opening:{opening.id}")
        for other in item_collisions(item, scene.items):
            labels.append(f"item:{other.id}")
        if labels:
            report[item.id] = tuple(labels)
    return report


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
