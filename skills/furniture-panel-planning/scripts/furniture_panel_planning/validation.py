"""Validation owned by the panel-planning stage."""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport
from furniture_design_intent.design_spec import FurnitureSpec
from furniture_layout.layout_planning import CabinetLayout

from .panel_models import PanelPlacement
from .panel_rules import (
    back_rail_clear_spacing,
    resolve_back_rail_count,
    resolve_toe_kick_support_count,
    toe_kick_support_clear_spacing,
)


def validate_panels(
    spec: FurnitureSpec,
    layout: CabinetLayout,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panels_planned")
    if not panels:
        report.add_error("EMPTY_PANEL_PLAN", "panel plan contains no panels")
        return report
    ids = {item.id for item in panels}
    if len(ids) != len(panels):
        report.add_error("DUPLICATE_PANEL_ID", "panel ids must be unique")
    panel_by_id = {item.id: item for item in panels}
    for item in panels:
        if item.quantity <= 0:
            report.add_error(
                "INVALID_PANEL_QUANTITY",
                f"{item.id} quantity must be positive",
                item.id,
            )
        for axis, size, position, limit in (
            ("x", item.size_x, item.pos_x, spec.width),
            ("y", item.size_y, item.pos_y, spec.depth),
            ("z", item.size_z, item.pos_z, spec.height),
        ):
            if size <= 0:
                report.add_error(
                    "NON_POSITIVE_LAYOUT_SIZE",
                    f"{item.id}.{axis} size must be positive",
                    item.id,
                )
            if position < -1e-6 or position + size > limit + 1e-6:
                report.add_error(
                    "LAYOUT_OUTSIDE_ENVELOPE",
                    f"{item.id} exceeds the {axis.upper()} envelope",
                    item.id,
                )
        for dependency in item.depends_on:
            if dependency not in ids:
                report.add_error(
                    "UNKNOWN_LAYOUT_DEPENDENCY",
                    f"{item.id} depends on unknown placement {dependency}",
                    item.id,
                )
    carcass_ids = {
        "left_side_panel",
        "right_side_panel",
        "top_panel",
        "bottom_panel",
    }
    for panel_id in sorted(carcass_ids):
        panel = panel_by_id.get(panel_id)
        if panel is None:
            report.add_error(
                "MISSING_CARCASS_PANEL",
                f"panel plan is missing {panel_id}",
                panel_id,
            )
            continue
        if (
            abs(panel.pos_y - layout.carcass_y_start) > 1e-6
            or abs(panel.pos_y + panel.size_y - layout.carcass_y_end) > 1e-6
        ):
            report.add_error(
                "CARCASS_DEPTH_MISMATCH",
                f"{panel_id} must span the confirmed carcass depth",
                panel_id,
            )

    back = panel_by_id.get("back_panel")
    if back is None:
        report.add_error(
            "MISSING_BACK_PANEL",
            "supported cabinet panel plan requires a back panel",
            "back_panel",
        )
    else:
        if layout.back_mount == "groove":
            expected_back = (
                layout.internal_x_start - spec.groove_depth,
                layout.back_plane_y,
                layout.internal_z_start - spec.groove_depth,
                layout.internal_width + 2 * spec.groove_depth,
                spec.back_thickness,
                layout.internal_height + 2 * spec.groove_depth,
            )
        elif layout.back_mount == "insert":
            expected_back = (
                layout.internal_x_start,
                layout.back_plane_y,
                layout.internal_z_start,
                layout.internal_width,
                spec.back_thickness,
                layout.internal_height,
            )
        else:
            expected_back = (
                0.0,
                0.0,
                0.0,
                layout.width,
                spec.back_thickness,
                layout.height,
            )
        actual_back = (
            back.pos_x,
            back.pos_y,
            back.pos_z,
            back.size_x,
            back.size_y,
            back.size_z,
        )
        if any(
            abs(actual - expected) > 1e-6
            for actual, expected in zip(actual_back, expected_back)
        ):
            report.add_error(
                "BACK_MOUNT_GEOMETRY_MISMATCH",
                "back panel geometry does not match the confirmed mount mode",
                "back_panel",
            )
        if layout.back_mount == "cover":
            back_front_y = back.pos_y + back.size_y
            if any(
                panel_by_id[panel_id].pos_y < back_front_y - 1e-6
                for panel_id in carcass_ids
                if panel_id in panel_by_id
            ):
                report.add_error(
                    "COVER_BACK_OVERLAP",
                    "cover back must end before the cabinet carcass starts",
                    "back_panel",
                )

    support_panels = [
        item
        for item in panels
        if item.id.startswith("toe_kick_support_")
    ]
    expected_support_count = (
        resolve_toe_kick_support_count(
            spec.toe_kick_support_count,
            layout.width,
        )
        if layout.toe_kick_height > 0
        else 0
    )
    if expected_support_count < 0:
        report.add_error(
            "INVALID_TOE_KICK_SUPPORT_COUNT",
            "toe-kick support count cannot be negative",
            "toe_kick_support_count",
        )
    if len(support_panels) != max(expected_support_count, 0):
        report.add_error(
            "TOE_KICK_SUPPORT_COUNT_MISMATCH",
            "generated toe-kick support count does not match the panel rule",
            "toe_kick_support_count",
        )
    if expected_support_count > 0 and toe_kick_support_clear_spacing(
        layout.internal_width,
        expected_support_count,
        spec.board_thickness,
    ) <= 0:
        report.add_error(
            "NON_POSITIVE_TOE_KICK_SUPPORT_SPACING",
            "toe-kick supports leave no positive clear spacing",
            "toe_kick_support_count",
        )

    rail_panels = [
        item for item in panels if item.panel_type == "back_rail"
    ]
    expected_rail_count = resolve_back_rail_count(
        layout.back_mount,
        layout.internal_height,
        spec.back_rail_height,
    )
    if spec.back_rail_height < 0:
        report.add_error(
            "INVALID_BACK_RAIL_HEIGHT",
            "back_rail_height cannot be negative",
            "back_rail_height",
        )
    if len(rail_panels) != expected_rail_count:
        report.add_error(
            "BACK_RAIL_COUNT_MISMATCH",
            "generated back-rail count does not match the panel rule",
            "back_rail",
        )
    if expected_rail_count > 0 and back_rail_clear_spacing(
        layout.internal_height,
        expected_rail_count,
        spec.back_rail_height,
    ) <= 0:
        report.add_error(
            "NON_POSITIVE_BACK_RAIL_SPACING",
            "back rails leave no positive clear spacing",
            "back_rail",
        )

    for item in panels:
        if item.panel_type in ("fixed_shelf", "movable_shelf") and (
            abs(item.pos_y - layout.internal_y_start) > 1e-6
            or abs(item.pos_y + item.size_y - layout.internal_y_end) > 1e-6
        ):
            report.add_error(
                "INTERNAL_DEPTH_MISMATCH",
                f"{item.id} must span the confirmed internal depth",
                item.id,
            )
        if item.panel_type == "door" and abs(
            item.pos_y + item.size_y - spec.depth
        ) > 1e-6:
            report.add_error(
                "DOOR_DEPTH_MISMATCH",
                f"{item.id} must end at the finished depth",
                item.id,
            )
    return report
