"""Validation owned by independent room-scene layout."""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from furniture_delivery_validation.validation import ValidationReport

from .collision import (
    item_collisions,
    item_outside_room,
    obstacle_collisions,
    opening_collisions,
)
from .placement import (
    build_placed_item,
    furniture_footprint,
    resolve_placement,
)
from .preview import render_preview
from .scene import (
    EPSILON,
    ItemSpec,
    PLACEMENT_MODES,
    PlacementRequest,
    PlacedItem,
    RoomModel,
    RoomScene,
    WALLS,
)
from .viewer import render_viewer


def validate_room_scene(output: Mapping[str, Any]) -> ValidationReport:
    report = ValidationReport(stage="layout_plan")
    try:
        scene = RoomScene.from_dict(output)
    except (KeyError, TypeError, ValueError) as exc:
        report.add_error("INVALID_ROOM_SCENE", str(exc), "items")
        return report

    _validate_room(scene.room, report)
    if any(issue.code == "INVALID_ROOM_DIMENSION" for issue in report.issues):
        return report

    seen_ids: set[str] = set()
    for index, item in enumerate(scene.items):
        path = f"items[{index}]"
        if item.id in seen_ids:
            report.add_error("DUPLICATE_ITEM_ID", f"duplicate item id: {item.id}", path)
        seen_ids.add(item.id)
        expected = _validate_item_placement(scene.room, item, report, path)
        if expected is None:
            continue
        _validate_derived_item(item, expected, report, path)
        _validate_item_fit(scene, item, report, path)

    raw_preview = output.get("preview")
    if not isinstance(raw_preview, Mapping):
        report.add_error("INVALID_LAYOUT_PREVIEW", "preview must be an object", "preview")
    elif dict(raw_preview) != render_preview(scene):
        report.add_error(
            "LAYOUT_PREVIEW_MISMATCH",
            "SVG preview must match the current room and furniture placement",
            "preview",
        )
    raw_viewer = output.get("viewer")
    if not isinstance(raw_viewer, Mapping):
        report.add_error("INVALID_LAYOUT_VIEWER", "viewer must be an object", "viewer")
    elif dict(raw_viewer) != render_viewer(scene):
        report.add_error(
            "LAYOUT_VIEWER_MISMATCH",
            "interactive viewer must match the current room and furniture placement",
            "viewer",
        )
    return report


def _validate_room(room: RoomModel, report: ValidationReport) -> None:
    for name, value in (
        ("width_mm", room.width_mm),
        ("depth_mm", room.depth_mm),
        ("height_mm", room.height_mm),
    ):
        if not isfinite(value) or value <= 0:
            report.add_error(
                "INVALID_ROOM_DIMENSION",
                f"room.{name} must be a positive finite number",
                f"room.{name}",
            )

    for index, opening in enumerate(room.openings):
        path = f"room.openings[{index}]"
        if opening.wall not in WALLS:
            report.add_error(
                "INVALID_OPENING_WALL",
                "opening.wall must be one of: " + ", ".join(sorted(WALLS)),
                f"{path}.wall",
            )
            continue
        wall_length = room.wall_length(opening.wall)
        if (
            not _all_finite(
                opening.offset_mm,
                opening.width_mm,
                opening.height_mm,
                opening.sill_height_mm,
            )
            or opening.offset_mm < 0
            or opening.width_mm <= 0
            or opening.offset_mm + opening.width_mm > wall_length + EPSILON
            or opening.sill_height_mm < 0
            or opening.height_mm <= 0
            or opening.sill_height_mm + opening.height_mm
            > room.height_mm + EPSILON
        ):
            report.add_error(
                "OPENING_OUTSIDE_ROOM",
                f"opening {opening.id!r} must fit on its wall and inside room height",
                path,
            )

    for index, obstacle in enumerate(room.obstacles):
        path = f"room.obstacles[{index}]"
        if (
            not _all_finite(
                obstacle.x_mm,
                obstacle.y_mm,
                obstacle.z_mm,
                obstacle.width_mm,
                obstacle.depth_mm,
                obstacle.height_mm,
            )
            or obstacle.x_mm < 0
            or obstacle.y_mm < 0
            or obstacle.z_mm < 0
            or obstacle.width_mm <= 0
            or obstacle.depth_mm <= 0
            or obstacle.height_mm <= 0
            or obstacle.x_mm + obstacle.width_mm > room.width_mm + EPSILON
            or obstacle.y_mm + obstacle.depth_mm > room.depth_mm + EPSILON
            or obstacle.z_mm + obstacle.height_mm > room.height_mm + EPSILON
        ):
            report.add_error(
                "OBSTACLE_OUTSIDE_ROOM",
                f"obstacle {obstacle.id!r} must be a positive box inside the room",
                path,
            )


def _validate_item_placement(
    room: RoomModel,
    item: PlacedItem,
    report: ValidationReport,
    path: str,
) -> PlacedItem | None:
    placement = item.placement
    if placement.mode not in PLACEMENT_MODES:
        report.add_error(
            "INVALID_PLACEMENT_MODE",
            "placement.mode must be one of: " + ", ".join(sorted(PLACEMENT_MODES)),
            f"{path}.placement.mode",
        )
        return None
    if not _all_finite(
        placement.origin_x_mm,
        placement.origin_y_mm,
        placement.origin_z_mm,
        placement.rotation_z_deg,
        item.width,
        item.depth,
        item.height,
    ):
        report.add_error(
            "INVALID_PLACEMENT_TRANSFORM",
            "placement transform values must be finite",
            f"{path}.placement",
        )
        return None

    expected_placement = placement
    if placement.mode == "wall":
        if placement.host_wall not in WALLS or placement.offset_mm is None:
            report.add_error(
                "INVALID_WALL_PLACEMENT",
                "wall placement requires a known host_wall and offset_mm",
                f"{path}.placement",
            )
            return None
        try:
            expected_placement = resolve_placement(
                room,
                PlacementRequest(
                    mode="wall",
                    host_wall=placement.host_wall,
                    offset_mm=placement.offset_mm,
                    origin_x_mm=None,
                    origin_y_mm=None,
                    origin_z_mm=placement.origin_z_mm,
                    rotation_z_deg=None,
                    fill=placement.fill,
                ),
            )
        except ValueError as exc:
            report.add_error("INVALID_WALL_PLACEMENT", str(exc), f"{path}.placement")
            return None
        if not _placements_close(placement, expected_placement):
            report.add_error(
                "WALL_PLACEMENT_TRANSFORM_MISMATCH",
                "wall placement origin and rotation must be derived from wall and offset",
                f"{path}.placement",
            )
    elif placement.host_wall is not None or placement.offset_mm is not None:
        report.add_error(
            "INVALID_FREE_PLACEMENT",
            "free placement cannot retain host_wall or offset_mm",
            f"{path}.placement",
        )

    spec = ItemSpec(
        id=item.id,
        label=item.label,
        category=item.category,
        width=item.width,
        depth=item.depth,
        height=item.height,
        placement=PlacementRequest(
            mode=expected_placement.mode,
            host_wall=expected_placement.host_wall,
            offset_mm=expected_placement.offset_mm,
            origin_x_mm=(
                None
                if expected_placement.mode == "wall"
                else expected_placement.origin_x_mm
            ),
            origin_y_mm=(
                None
                if expected_placement.mode == "wall"
                else expected_placement.origin_y_mm
            ),
            origin_z_mm=expected_placement.origin_z_mm,
            rotation_z_deg=(
                None
                if expected_placement.mode == "wall"
                else expected_placement.rotation_z_deg
            ),
            fill=expected_placement.fill,
        ),
    )
    return build_placed_item(spec, room, expected_placement, width=item.width)


def _validate_derived_item(
    actual: PlacedItem,
    expected: PlacedItem,
    report: ValidationReport,
    path: str,
) -> None:
    expected_footprint = furniture_footprint(
        expected.width,
        expected.depth,
        expected.placement,
    )
    if not _points_close(actual.footprint, expected_footprint):
        report.add_error(
            "FURNITURE_FOOTPRINT_MISMATCH",
            "furniture footprint must match its envelope and placement transform",
            f"{path}.footprint",
        )
    for direction, expected_value in expected.clearances_mm.items():
        actual_value = actual.clearances_mm.get(direction)
        if actual_value is None or abs(actual_value - expected_value) > EPSILON:
            report.add_error(
                "ROOM_CLEARANCE_MISMATCH",
                f"{direction} clearance does not match the furniture footprint",
                f"{path}.clearances_mm.{direction}",
            )


def _validate_item_fit(
    scene: RoomScene,
    item: PlacedItem,
    report: ValidationReport,
    path: str,
) -> None:
    if item_outside_room(scene.room, item):
        report.add_error(
            "FURNITURE_OUTSIDE_ROOM",
            f"item {item.id!r} envelope must remain inside the room",
            f"{path}.placement",
        )
    for obstacle in obstacle_collisions(scene.room, item):
        report.add_error(
            "FURNITURE_OBSTACLE_COLLISION",
            f"item {item.id!r} collides with obstacle: {obstacle.id}",
            "room.obstacles",
        )
    for opening in opening_collisions(scene.room, item):
        report.add_error(
            "FURNITURE_OPENING_COLLISION",
            f"item {item.id!r} blocks {opening.kind}: {opening.id}",
            "room.openings",
        )
    for other in item_collisions(item, scene.items):
        if item.id > other.id:
            continue
        report.add_error(
            "FURNITURE_ITEM_COLLISION",
            f"item {item.id!r} collides with item {other.id!r}",
            "items",
        )


def _placements_close(first: Any, second: Any) -> bool:
    return (
        first.mode == second.mode
        and first.host_wall == second.host_wall
        and first.offset_mm == second.offset_mm
        and first.fill == second.fill
        and abs(first.origin_x_mm - second.origin_x_mm) <= EPSILON
        and abs(first.origin_y_mm - second.origin_y_mm) <= EPSILON
        and abs(first.origin_z_mm - second.origin_z_mm) <= EPSILON
        and abs(
            ((first.rotation_z_deg - second.rotation_z_deg + 180.0) % 360.0)
            - 180.0
        )
        <= EPSILON
    )


def _points_close(
    first: tuple[tuple[float, float], ...],
    second: tuple[tuple[float, float], ...],
) -> bool:
    return len(first) == len(second) and all(
        abs(first_point[0] - second_point[0]) <= EPSILON
        and abs(first_point[1] - second_point[1]) <= EPSILON
        for first_point, second_point in zip(first, second)
    )


def _all_finite(*values: float) -> bool:
    return all(isfinite(value) for value in values)
