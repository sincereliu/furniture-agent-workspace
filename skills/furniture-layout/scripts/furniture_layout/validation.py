"""Validation owned by the layout-planning stage."""

from __future__ import annotations

from math import isfinite
from typing import Any, Mapping

from furniture_delivery_validation.validation import ValidationReport

from .layout_preview import render_layout_preview
from .layout_planning import CabinetLayout
from .layout_spec import LayoutSpec
from .layout_viewer import render_layout_viewer
from .room_planning import (
    EPSILON,
    PLACEMENT_MODES,
    WALLS,
    PlacementRequest,
    RoomPlacementPlan,
    build_room_placement,
    obstacle_collisions,
    opening_collisions,
    resolve_placement,
)


def validate_layout(
    spec: LayoutSpec | Any,
    layout: CabinetLayout,
) -> ValidationReport:
    report = ValidationReport(stage="layout_planned")
    if not isinstance(spec, LayoutSpec):
        spec = LayoutSpec(
            furniture_type=str(spec.furniture_type),
            width=float(spec.width),
            depth=float(spec.depth),
            height=float(spec.height),
            shelf_count=int(spec.shelf_count),
            door_count=int(getattr(spec, "door_count", spec.n_doors)),
        )
    if (
        layout.furniture_type,
        layout.width,
        layout.depth,
        layout.height,
    ) != (
        spec.furniture_type,
        spec.width,
        spec.depth,
        spec.height,
    ):
        report.add_error(
            "LAYOUT_ENVELOPE_MISMATCH",
            "layout envelope does not match confirmed design intent",
        )
    for name, count in (
        ("shelf_count", layout.shelf_count),
        ("door_count", layout.door_count),
    ):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            report.add_error(
                "INVALID_LAYOUT_COUNT",
                f"{name} must be a non-negative integer",
                name,
            )
    if (
        layout.shelf_count != spec.shelf_count
        or layout.door_count != spec.door_count
    ):
        report.add_error(
            "LAYOUT_COUNT_MISMATCH",
            "layout counts must match the customer-visible layout request",
        )
    return report


def validate_layout_output(
    spec: LayoutSpec,
    output: Mapping[str, Any],
) -> ValidationReport:
    """Validate the complete stage output, including optional room placement."""
    report = ValidationReport(stage="layout_planned")
    raw_layout = output.get("layout")
    if not isinstance(raw_layout, Mapping):
        report.add_error(
            "MISSING_LAYOUT",
            "layout stage output requires a layout object",
            "layout",
        )
        return report

    try:
        layout = CabinetLayout(**raw_layout)
    except (TypeError, ValueError) as exc:
        report.add_error("INVALID_LAYOUT", str(exc), "layout")
        return report

    cabinet_report = validate_layout(spec, layout)
    report.issues.extend(cabinet_report.issues)

    raw_context = output.get("layout_context")
    if not isinstance(raw_context, Mapping):
        report.add_error(
            "MISSING_LAYOUT_CONTEXT",
            "layout stage output requires layout_context source markers",
            "layout_context",
        )
    else:
        for key, allowed in (
            ("room_source", {"provided", "default_bedroom"}),
            (
                "placement_source",
                {"provided", "default_south_wall_centered"},
            ),
        ):
            if raw_context.get(key) not in allowed:
                report.add_error(
                    "INVALID_LAYOUT_CONTEXT",
                    f"layout_context.{key} has an unsupported value",
                    f"layout_context.{key}",
                )

    has_room_placement = "room_placement" in output
    has_preview = "preview" in output
    has_viewer = "viewer" in output
    if not has_room_placement and not has_preview and not has_viewer:
        report.add_error(
            "MISSING_ROOM_LAYOUT_OUTPUT",
            "room placement, SVG preview, and interactive viewer are required",
            "room_placement",
        )
        return report
    if not (has_room_placement and has_preview and has_viewer):
        report.add_error(
            "INCOMPLETE_ROOM_LAYOUT_OUTPUT",
            "room placement, SVG preview, and interactive viewer must be emitted together",
            "room_placement",
        )
        return report

    try:
        raw_room_placement = output["room_placement"]
        if not isinstance(raw_room_placement, Mapping):
            raise ValueError("room_placement must be an object")
        plan = RoomPlacementPlan.from_dict(raw_room_placement)
    except (KeyError, TypeError, ValueError) as exc:
        report.add_error(
            "INVALID_ROOM_LAYOUT_OUTPUT",
            str(exc),
            "room_placement",
        )
        return report

    _validate_room(plan, report)
    if any(issue.code == "INVALID_ROOM_DIMENSION" for issue in report.issues):
        return report
    expected_plan = _validate_placement(plan, layout, report)
    if expected_plan is None:
        return report

    _validate_derived_room_output(plan, expected_plan, report)
    _validate_room_fit(plan, layout, report)

    raw_preview = output.get("preview")
    if not isinstance(raw_preview, Mapping):
        report.add_error(
            "INVALID_LAYOUT_PREVIEW",
            "preview must be an object",
            "preview",
        )
    elif dict(raw_preview) != render_layout_preview(expected_plan, layout):
        report.add_error(
            "LAYOUT_PREVIEW_MISMATCH",
            "SVG preview must match the current room and furniture placement",
            "preview",
        )
    raw_viewer = output.get("viewer")
    if not isinstance(raw_viewer, Mapping):
        report.add_error(
            "INVALID_LAYOUT_VIEWER",
            "viewer must be an object",
            "viewer",
        )
    elif dict(raw_viewer) != render_layout_viewer(expected_plan, layout):
        report.add_error(
            "LAYOUT_VIEWER_MISMATCH",
            "interactive viewer must match the current room and furniture placement",
            "viewer",
        )
    return report


def _validate_room(
    plan: RoomPlacementPlan,
    report: ValidationReport,
) -> None:
    room = plan.room
    for name, value in (
        ("width_mm", room.width_mm),
        ("depth_mm", room.depth_mm),
        ("height_mm", room.height_mm),
    ):
        if not isfinite(value) or value <= 0:
            report.add_error(
                "INVALID_ROOM_DIMENSION",
                f"room.{name} must be a positive finite number",
                f"room_placement.room.{name}",
            )

    for index, opening in enumerate(room.openings):
        path = f"room_placement.room.openings[{index}]"
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
        path = f"room_placement.room.obstacles[{index}]"
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


def _validate_placement(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
    report: ValidationReport,
) -> RoomPlacementPlan | None:
    placement = plan.placement
    if placement.mode not in PLACEMENT_MODES:
        report.add_error(
            "INVALID_PLACEMENT_MODE",
            "placement.mode must be one of: "
            + ", ".join(sorted(PLACEMENT_MODES)),
            "room_placement.placement.mode",
        )
        return None
    if not _all_finite(
        placement.origin_x_mm,
        placement.origin_y_mm,
        placement.origin_z_mm,
        placement.rotation_z_deg,
    ):
        report.add_error(
            "INVALID_PLACEMENT_TRANSFORM",
            "placement transform values must be finite",
            "room_placement.placement",
        )
        return None

    expected_placement = placement
    if placement.mode == "wall":
        if placement.host_wall not in WALLS or placement.offset_mm is None:
            report.add_error(
                "INVALID_WALL_PLACEMENT",
                "wall placement requires a known host_wall and offset_mm",
                "room_placement.placement",
            )
            return None
        try:
            expected_placement = resolve_placement(
                plan.room,
                PlacementRequest(
                    mode="wall",
                    host_wall=placement.host_wall,
                    offset_mm=placement.offset_mm,
                    origin_x_mm=None,
                    origin_y_mm=None,
                    origin_z_mm=placement.origin_z_mm,
                    rotation_z_deg=None,
                ),
            )
        except ValueError as exc:
            report.add_error(
                "INVALID_WALL_PLACEMENT",
                str(exc),
                "room_placement.placement",
            )
            return None
        if not _placements_close(placement, expected_placement):
            report.add_error(
                "WALL_PLACEMENT_TRANSFORM_MISMATCH",
                "wall placement origin and rotation must be derived from wall and offset",
                "room_placement.placement",
            )
    elif placement.host_wall is not None or placement.offset_mm is not None:
        report.add_error(
            "INVALID_FREE_PLACEMENT",
            "free placement cannot retain host_wall or offset_mm",
            "room_placement.placement",
        )

    return build_room_placement(
        layout,
        plan.room,
        expected_placement,
        furniture_label=plan.furniture_label,
    )


def _validate_derived_room_output(
    actual: RoomPlacementPlan,
    expected: RoomPlacementPlan,
    report: ValidationReport,
) -> None:
    if not _points_close(
        actual.furniture_footprint,
        expected.furniture_footprint,
    ):
        report.add_error(
            "FURNITURE_FOOTPRINT_MISMATCH",
            "furniture footprint must match its envelope and placement transform",
            "room_placement.furniture_footprint",
        )
    for direction, expected_value in expected.clearances_mm.items():
        actual_value = actual.clearances_mm.get(direction)
        if actual_value is None or abs(actual_value - expected_value) > EPSILON:
            report.add_error(
                "ROOM_CLEARANCE_MISMATCH",
                f"{direction} clearance does not match the furniture footprint",
                f"room_placement.clearances_mm.{direction}",
            )


def _validate_room_fit(
    plan: RoomPlacementPlan,
    layout: CabinetLayout,
    report: ValidationReport,
) -> None:
    room = plan.room
    if any(
        x < -EPSILON
        or x > room.width_mm + EPSILON
        or y < -EPSILON
        or y > room.depth_mm + EPSILON
        for x, y in plan.furniture_footprint
    ) or plan.placement.origin_z_mm < -EPSILON or (
        plan.placement.origin_z_mm + layout.height
        > room.height_mm + EPSILON
    ):
        report.add_error(
            "FURNITURE_OUTSIDE_ROOM",
            "furniture envelope must remain inside the room",
            "room_placement.placement",
        )

    for obstacle in obstacle_collisions(plan, layout):
        report.add_error(
            "FURNITURE_OBSTACLE_COLLISION",
            f"furniture collides with obstacle: {obstacle.id}",
            "room_placement.room.obstacles",
        )
    for opening in opening_collisions(plan, layout):
        report.add_error(
            "FURNITURE_OPENING_COLLISION",
            f"furniture blocks {opening.kind}: {opening.id}",
            "room_placement.room.openings",
        )

    if layout.furniture_type == "wall_cabinet" and plan.placement.origin_z_mm <= 0:
        report.add_warning(
            "WALL_CABINET_AT_FLOOR_LEVEL",
            "wall cabinet placement has no mounting elevation",
            "room_placement.placement.origin_z_mm",
        )


def _placements_close(first: Any, second: Any) -> bool:
    return (
        first.mode == second.mode
        and first.host_wall == second.host_wall
        and first.offset_mm == second.offset_mm
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
