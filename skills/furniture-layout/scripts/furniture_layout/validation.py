"""Validation owned by the layout-planning stage."""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport
from furniture_design_intent.design_spec import FurnitureSpec, resolve_back_mount

from .layout_planning import CabinetLayout


def validate_layout(
    spec: FurnitureSpec,
    layout: CabinetLayout,
) -> ValidationReport:
    report = ValidationReport(stage="layout_planned")
    back_mount = resolve_back_mount(
        spec.back_mount,
        spec.back_thickness,
        spec.board_thickness,
    )
    expected_carcass_y_start = (
        spec.back_thickness if back_mount == "cover" else 0.0
    )
    expected_carcass_y_end = (
        spec.depth - spec.door_thickness - spec.door_hinge_gap
    )
    expected_toe_kick = (
        spec.toe_kick_height
        if spec.furniture_type != "wall_cabinet"
        else 0.0
    )
    expected_internal_width = spec.width - 2 * spec.board_thickness
    expected_internal_height = (
        spec.height - expected_toe_kick - 2 * spec.board_thickness
    )
    expected_side_depth = (
        expected_carcass_y_end - expected_carcass_y_start
    )
    expected_internal_y_start = (
        expected_carcass_y_start
        if back_mount == "cover"
        else spec.back_offset + spec.back_thickness
    )
    if (layout.width, layout.depth, layout.height) != (
        spec.width,
        spec.depth,
        spec.height,
    ):
        report.add_error(
            "LAYOUT_ENVELOPE_MISMATCH",
            "layout envelope does not match confirmed design intent",
        )
    if layout.back_mount != back_mount:
        report.add_error(
            "BACK_MOUNT_MISMATCH",
            "layout back mount does not match confirmed design intent",
            "back_mount",
        )
    if (
        abs(layout.carcass_y_start - expected_carcass_y_start) > 1e-6
        or abs(layout.carcass_y_end - expected_carcass_y_end) > 1e-6
        or abs(
            layout.side_depth
            - (layout.carcass_y_end - layout.carcass_y_start)
        )
        > 1e-6
    ):
        report.add_error(
            "CARCASS_DEPTH_MISMATCH",
            "layout carcass depth must preserve the finished depth envelope",
            "side_depth",
        )
    if min(layout.internal_width, layout.internal_height, layout.side_depth) <= 0:
        report.add_error(
            "NON_POSITIVE_LAYOUT_REGION",
            "layout internal regions must be positive",
        )
    if min(
        expected_internal_width,
        expected_internal_height,
        expected_side_depth,
    ) <= 0:
        report.add_error(
            "NON_POSITIVE_INTERNAL_CLEARANCE",
            "confirmed dimensions leave no positive cabinet clearance",
            "internal_clearance",
        )
    if (
        abs(layout.internal_width - expected_internal_width) > 1e-6
        or abs(layout.internal_height - expected_internal_height) > 1e-6
        or abs(layout.internal_y_start - expected_internal_y_start) > 1e-6
        or abs(layout.internal_y_end - expected_carcass_y_end) > 1e-6
    ):
        report.add_error(
            "INTERNAL_CLEARANCE_MISMATCH",
            "layout must own and preserve the final internal clearances",
            "internal_clearance",
        )
    if not (
        0 <= layout.internal_x_start < layout.internal_x_end <= layout.width
        and 0 <= layout.internal_z_start < layout.internal_z_end <= layout.height
        and 0
        <= layout.carcass_y_start
        < layout.carcass_y_end
        <= layout.depth
        and layout.carcass_y_start
        <= layout.internal_y_start
        < layout.internal_y_end
        <= layout.carcass_y_end
        and 0 <= layout.back_plane_y < layout.internal_y_start
    ):
        report.add_error(
            "LAYOUT_REGION_OUTSIDE_ENVELOPE",
            "layout regions must remain inside the finished envelope",
        )
    if layout.toe_kick_height > 0 and not (
        layout.carcass_y_start
        <= layout.toe_kick_rear_y
        < layout.toe_kick_front_y
        <= layout.carcass_y_end
    ):
        report.add_error(
            "INVALID_TOE_KICK_REGION",
            "toe-kick region must have positive depth inside the cabinet",
        )
    for name, value in (
        ("toe_kick_height", spec.toe_kick_height),
        ("door_hinge_gap", spec.door_hinge_gap),
        ("toe_kick_reveal_front", spec.toe_kick_reveal_front),
        ("toe_kick_reveal_back", spec.toe_kick_reveal_back),
    ):
        if value < 0:
            report.add_error(
                "INVALID_LAYOUT_INPUT",
                f"{name} cannot be negative",
                name,
            )
    if back_mount in {"groove", "insert"} and (
        spec.back_offset < expected_carcass_y_start
        or spec.back_offset + spec.back_thickness >= expected_carcass_y_end
    ):
        report.add_error(
            "INVALID_BACK_LAYOUT",
            f"{back_mount} back must leave positive internal depth",
            "back_offset",
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
    return report
