"""Validation owned by the panel-planning stage."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from furniture_delivery_validation.validation import ValidationReport
from furniture_design_intent.design_intent import DesignIntent

from .assembly_tree import (
    ASSEMBLY_OBJECT_FIELDS,
    BASE_CONSTRUCTIONS,
    CABINET_OUTPUT_FIELDS,
    CAVITY_FIELDS,
    INTERIOR_FIELDS,
    ZONE_KINDS,
    flatten_panels_for_handoff,
)
from .cabinet_identity import (
    cabinets_from_output,
    index_by_role,
    panel_role,
    qualify_panel_id,
)
from .construction_geometry import (
    back_rail_boxes,
    drawer_panel_boxes,
    shelf_panel_boxes,
    toe_kick_support_boxes,
)
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec, resolve_back_mount, thickness_for_material_role
from .panel_rules import (
    back_rail_clear_spacing,
    resolve_back_rail_count,
    toe_kick_support_clear_spacing,
)
from .structure_planning import CabinetStructure


def validate_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    if not isinstance(layout, CabinetStructure):
        raise TypeError(
            "validate_panels requires CabinetStructure; independent room layout is not a valid panel input"
        )
    if not panels:
        report.add_error("EMPTY_PANEL_PLAN", "panel plan contains no panels")
        return report
    ids = {item.id for item in panels}
    if len(ids) != len(panels):
        report.add_error("DUPLICATE_PANEL_ID", "panel ids must be unique")
    panel_by_id = {item.id: item for item in panels}
    panel_by_role = index_by_role(panels)
    report.issues.extend(_validate_doors(spec, panels).issues)
    report.issues.extend(_validate_panel_basics(spec, panels, ids).issues)
    carcass_roles = {
        "left_side_panel",
        "right_side_panel",
        "top_panel",
        "bottom_panel",
    }
    report.issues.extend(
        _validate_carcass_panels(layout, panel_by_role, carcass_roles).issues
    )
    report.issues.extend(
        _validate_back_panel(spec, layout, panel_by_role, carcass_roles).issues
    )
    report.issues.extend(_validate_toe_kick_panels(spec, layout, panels).issues)
    report.issues.extend(_validate_back_rails(spec, layout, panels).issues)
    report.issues.extend(_validate_depth_aligned_panels(spec, layout, panels).issues)
    report.issues.extend(_validate_shelf_panels(spec, layout, panels).issues)
    drawer_report = _validate_drawer_panels(spec, layout, panels)
    report.issues.extend(drawer_report.issues)
    return report


def _panel_geometry(panel: PanelPlacement) -> tuple[float, float, float, float, float, float]:
    return (
        panel.size_x,
        panel.size_y,
        panel.size_z,
        panel.pos_x,
        panel.pos_y,
        panel.pos_z,
    )


def _mismatch_boxes(
    report: ValidationReport,
    code: str,
    actual_by_id: Mapping[str, PanelPlacement],
    boxes,
) -> None:
    for box in boxes:
        panel = actual_by_id.get(box.panel_id)
        if panel is None:
            report.add_error(code, f"missing {box.panel_id}", box.panel_id)
            continue
        if any(
            abs(actual - expected) > 1e-6
            for actual, expected in zip(_panel_geometry(panel), box.geometry)
        ):
            report.add_error(
                code,
                f"{box.panel_id} does not match the admitted construction geometry",
                box.panel_id,
            )


def _validate_doors(
    spec: FurnitureSpec,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    doors = sorted(
        (item for item in panels if item.panel_type == "door"),
        key=lambda item: (item.pos_x, item.id),
    )
    if len(doors) != spec.n_doors:
        report.add_error(
            "DOOR_COUNT_MISMATCH",
            "generated door count must match the admitted panel specification",
            "n_doors",
        )
        return report
    return report


def _validate_panel_basics(
    spec: FurnitureSpec,
    panels: list[PanelPlacement],
    ids: set[str],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
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
        expected = thickness_for_material_role(spec, item.material_role)
        actual = min(item.size_x, item.size_y, item.size_z)
        if abs(actual - expected) > 0.5:
            report.add_error(
                "PANEL_STOCK_THICKNESS_MISMATCH",
                f"{item.id} thickness {actual:g} must match {item.material_role} stock {expected:g}",
                item.id,
            )
    return report


def _validate_carcass_panels(
    layout: CabinetStructure,
    panel_by_role: Mapping[str, PanelPlacement],
    carcass_roles: set[str],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    for role in sorted(carcass_roles):
        panel = panel_by_role.get(role)
        if panel is None:
            report.add_error(
                "MISSING_CARCASS_PANEL",
                f"panel plan is missing {role}",
                role,
            )
            continue
        if (
            abs(panel.pos_y - layout.carcass_y_start) > 1e-6
            or abs(panel.pos_y + panel.size_y - layout.carcass_y_end) > 1e-6
        ):
            report.add_error(
                "CARCASS_DEPTH_MISMATCH",
                f"{panel.id} must span the confirmed carcass depth",
                panel.id,
            )
    return report


def _validate_back_panel(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    panel_by_role: Mapping[str, PanelPlacement],
    carcass_roles: set[str],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    back = panel_by_role.get("back_panel")
    if back is None:
        report.add_error(
            "MISSING_BACK_PANEL",
            "supported cabinet panel plan requires a back panel",
            "back_panel",
        )
        return report
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
            panel_by_role[role].pos_y < back_front_y - 1e-6
            for role in carcass_roles
            if role in panel_by_role
        ):
            report.add_error(
                "COVER_BACK_OVERLAP",
                "cover back must end before the cabinet carcass starts",
                "back_panel",
            )
    return report


def _validate_toe_kick_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    support_panels = [
        item
        for item in panels
        if item.role.startswith("toe_kick_support_")
    ]
    expected_support_count = (
        spec.toe_kick_support_count if layout.toe_kick_height > 0 else 0
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
    _mismatch_boxes(
        report,
        "TOE_KICK_SUPPORT_GEOMETRY_MISMATCH",
        {item.role: item for item in support_panels},
        toe_kick_support_boxes(spec, layout),
    )
    return report


def _validate_back_rails(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
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
    _mismatch_boxes(
        report,
        "BACK_RAIL_GEOMETRY_MISMATCH",
        {item.role: item for item in rail_panels},
        back_rail_boxes(spec, layout),
    )
    return report


def _validate_depth_aligned_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
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


def _validate_shelf_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    if spec.drawer_count > 0:
        return report
    shelf_panels = [
        item
        for item in panels
        if item.panel_type in ("fixed_shelf", "movable_shelf")
    ]
    try:
        expected = shelf_panel_boxes(spec, layout)
    except ValueError as exc:
        report.add_error("INVALID_SHELF_GAPS", str(exc), "shelves")
        return report
    if len(shelf_panels) != len(expected):
        report.add_error(
            "SHELF_PANEL_COUNT_MISMATCH",
            "generated shelf count must match the admitted shelves list",
            "shelves",
        )
    _mismatch_boxes(
        report,
        "SHELF_PANEL_GEOMETRY_MISMATCH",
        {item.role: item for item in shelf_panels},
        expected,
    )
    return report


def _validate_drawer_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    drawer_panels = [item for item in panels if item.panel_type.startswith("drawer_")]
    if spec.drawer_count <= 0:
        if drawer_panels:
            report.add_error(
                "UNEXPECTED_DRAWER_PANELS",
                "drawer panels require drawer_count > 0",
                "drawer_count",
            )
        return report

    if any(item.panel_type == "door" for item in panels) or any(
        item.panel_type in ("fixed_shelf", "movable_shelf") for item in panels
    ):
        report.add_error(
            "DRAWER_ZONE_MIXED_WITH_DOORS_OR_SHELVES",
            "full-height drawer output must not contain doors or shelf panels",
            "drawer_count",
        )

    try:
        expected = drawer_panel_boxes(spec, layout)
    except ValueError as exc:
        report.add_error("INVALID_DRAWER_GEOMETRY", str(exc), "drawer_count")
        return report
    if len(drawer_panels) != len(expected):
        report.add_error(
            "DRAWER_PANEL_COUNT_MISMATCH",
            "generated drawer panel count must match 5 panels per drawer instance",
            "drawer_count",
        )
    _mismatch_boxes(
        report,
        "DRAWER_PANEL_GEOMETRY_MISMATCH",
        {item.role: item for item in drawer_panels},
        expected,
    )
    return report
