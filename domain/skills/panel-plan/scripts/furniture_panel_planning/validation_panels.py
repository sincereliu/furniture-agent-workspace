"""Validation owned by the panel-planning stage."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from furniture_delivery_validation.validation import ValidationReport

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
    back_groove_allowance,
    back_panel_boxes,
    back_rail_boxes,
    divider_panel_boxes,
    door_panel_boxes,
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
    structure: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    if not isinstance(structure, CabinetStructure):
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
    report.issues.extend(_validate_doors(spec, structure, panels).issues)
    report.issues.extend(_validate_panel_basics(spec, panels, ids).issues)
    carcass_roles = {
        "left_side_panel",
        "right_side_panel",
        "top_panel",
        "bottom_panel",
    }
    report.issues.extend(
        _validate_carcass_panels(structure, panel_by_role, carcass_roles).issues
    )
    report.issues.extend(
        _validate_back_panel(spec, structure, panel_by_role, carcass_roles).issues
    )
    report.issues.extend(_validate_toe_kick_panels(spec, structure, panels).issues)
    report.issues.extend(_validate_back_rails(spec, structure, panels).issues)
    report.issues.extend(_validate_depth_aligned_panels(spec, structure, panels).issues)
    report.issues.extend(_validate_divider_panels(spec, structure, panels).issues)
    report.issues.extend(_validate_shelf_panels(spec, structure, panels).issues)
    drawer_report = _validate_drawer_panels(spec, structure, panels)
    report.issues.extend(drawer_report.issues)
    report.issues.extend(_validate_sheet_capacity(spec, panels).issues)
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
    structure: CabinetStructure,
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
    expected = door_panel_boxes(spec, structure)
    _mismatch_boxes(
        report,
        "DOOR_GEOMETRY_MISMATCH",
        {item.role: item for item in doors},
        expected,
    )
    by_role = {item.role: item for item in doors}
    for box in expected:
        panel = by_role.get(box.panel_id)
        if panel is not None and panel.door_hinge_side != box.door_hinge_side:
            report.add_error(
                "DOOR_HINGE_SIDE_MISMATCH",
                f"{box.panel_id} hinge side does not match the admitted layout",
                box.panel_id,
            )
    # 对开腔的铰链侧是几何逼出来的，一定有值；还能留空的只剩单开腔（和本拓扑
    # 表达不了的多扇腔）。这些要客户定：**阶段只报警告，不硬停** —— 停在这里的话
    # 板件页就没有这台柜，客户连"点一下左开/右开"的机会都没有。真正的闸门在制造：
    # 没有铰链侧的门排不了铰链孔，那里会拦。
    unknown = [item.role for item in doors if not item.door_hinge_side]
    if unknown:
        report.add_warning(
            "DOOR_HINGE_SIDE_UNKNOWN",
            "这些门还没定铰链侧，要在板件页上选左开/右开，或者在提案里给 door_hinges："
            + ", ".join(unknown),
            "door_hinges",
        )
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
    structure: CabinetStructure,
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
            abs(panel.pos_y - structure.carcass_y_start) > 1e-6
            or abs(panel.pos_y + panel.size_y - structure.carcass_y_end) > 1e-6
        ):
            report.add_error(
                "CARCASS_DEPTH_MISMATCH",
                f"{panel.id} must span the confirmed carcass depth",
                panel.id,
            )
    return report


def _validate_back_panel(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    panel_by_role: Mapping[str, PanelPlacement],
    carcass_roles: set[str],
) -> ValidationReport:
    """背板必须成套：每腔一块、夹在两侧板/立板之间、各块不能连成一片。

    别再用生成端那条公式重算一遍——那样只能拦住"摆放被改坏"，拦不住
    "这一块根本做不出来"（形状对不对由 `_validate_sheet_capacity` 管）。
    """
    report = ValidationReport(stage="panel_plan")
    pieces = sorted(
        (item for item in panel_by_role.values() if item.panel_type == "back"),
        key=lambda item: item.pos_x,
    )
    if not pieces:
        report.add_error(
            "MISSING_BACK_PANEL",
            "supported cabinet panel plan requires a back panel",
            "back_panel",
        )
        return report

    expected = back_panel_boxes(spec, structure)
    if len(pieces) != len(expected):
        report.add_error(
            "BACK_PANEL_COUNT_MISMATCH",
            f"back panel must be cut once per cavity: expected {len(expected)} "
            f"piece(s), found {len(pieces)}",
            "back_panel",
        )
        return report

    for panel, box in zip(pieces, expected):
        if abs(panel.pos_x - box.pos_x) > 1e-6 or abs(panel.size_x - box.size_x) > 1e-6:
            report.add_error(
                "BACK_PANEL_GEOMETRY_MISMATCH",
                f"{panel.id} must span its cavity ({box.pos_x:g}→"
                f"{box.pos_x + box.size_x:g})",
                panel.id,
            )
        if (
            abs(panel.pos_y - box.pos_y) > 1e-6
            or abs(panel.size_y - box.size_y) > 1e-6
            or abs(panel.pos_z - box.pos_z) > 1e-6
            or abs(panel.size_z - box.size_z) > 1e-6
        ):
            report.add_error(
                "BACK_MOUNT_GEOMETRY_MISMATCH",
                "back panel geometry does not match the confirmed mount mode",
                panel.id,
            )
    # 背板不能从立板背后通过：相邻两块之间的空档必须正好是一块立板减去两侧槽深。
    grooves = back_groove_allowance(spec, structure)
    dividers = divider_panel_boxes(spec, structure)
    for left, right, divider in zip(pieces, pieces[1:], dividers):
        gap = right.pos_x - (left.pos_x + left.size_x)
        expected_gap = divider.size_x - 2 * grooves
        if abs(gap - expected_gap) > 1e-6:
            report.add_error(
                "BACK_PANEL_SPAN_MISMATCH",
                f"back panels must stop at the divider: {left.id} and {right.id} "
                f"should leave a {expected_gap:g}mm gap, found {gap:g}",
                "back_panel",
            )
            break
    if structure.back_mount == "cover":
        back_front_y = pieces[0].pos_y + pieces[0].size_y
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


def _validate_sheet_capacity(
    spec: FurnitureSpec,
    panels: list[PanelPlacement],
) -> ValidationReport:
    """每块板的两个平面尺寸必须进得去车间板幅。

    板厚永远是三边里最小的（层板/背板/门板都一样，`_validate_panel_basics`
    也按这条认板厚），所以平面就是较大的那两边。旋转不改变能不能放下：
    板幅宽 × 长定死，`min ≤ 宽` 且 `max ≤ 长` 才切得出来。
    """
    report = ValidationReport(stage="panel_plan")
    width = spec.sheet_width_mm
    length = spec.sheet_length_mm
    for item in panels:
        short_side, long_side = sorted((item.size_x, item.size_y, item.size_z))[1:]
        if short_side <= width + 1e-6 and long_side <= length + 1e-6:
            continue
        if item.panel_type == "back":
            if spec.back_mount == "cover":
                hint = "外盖背板不按腔打断，宽柜得改用 groove/insert"
            else:
                hint = "加中立板把背面切开，或改柜宽"
        else:
            hint = "改用更长的板，或改柜宽/柜高"
        report.add_error(
            "PANEL_EXCEEDS_SHEET",
            f"{item.id} is {short_side:g}×{long_side:g}, does not fit the "
            f"{width:g}×{length:g} sheet stock; {hint}",
            item.id,
        )
    return report


def _validate_toe_kick_panels(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    support_panels = [
        item
        for item in panels
        if item.role.startswith("toe_kick_support_")
    ]
    expected_support_count = (
        spec.toe_kick_support_count if structure.toe_kick_height > 0 else 0
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
        structure.internal_width,
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
        toe_kick_support_boxes(spec, structure),
    )
    return report


def _validate_back_rails(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    rail_panels = [
        item for item in panels if item.panel_type == "back_rail"
    ]
    expected_boxes = back_rail_boxes(spec, structure)
    expected_rail_count = len(expected_boxes)
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
    # 每腔根数只在这里复算一次（出件在 `back_rail_boxes`，两边同一套规则函数）。
    per_cavity = resolve_back_rail_count(
        structure.back_mount,
        structure.internal_height,
        spec.back_rail_height,
    )
    if per_cavity > 0 and back_rail_clear_spacing(
        structure.internal_height,
        per_cavity,
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
        expected_boxes,
    )
    return report


def _validate_depth_aligned_panels(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    for item in panels:
        if item.panel_type in ("fixed_shelf", "movable_shelf") and (
            abs(item.pos_y - structure.internal_y_start) > 1e-6
            or abs(item.pos_y + item.size_y - structure.internal_y_end) > 1e-6
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


def _validate_divider_panels(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    panels: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="panel_plan")
    dividers = [item for item in panels if item.panel_type == "divider"]
    try:
        expected = divider_panel_boxes(spec, structure)
    except ValueError as exc:
        report.add_error("INVALID_DIVIDER_LAYOUT", str(exc), "dividers")
        return report
    if len(dividers) != len(expected):
        report.add_error(
            "DIVIDER_PANEL_COUNT_MISMATCH",
            "generated divider count must match the admitted dividers list",
            "dividers",
        )
    _mismatch_boxes(
        report,
        "DIVIDER_PANEL_GEOMETRY_MISMATCH",
        {item.role: item for item in dividers},
        expected,
    )
    return report


def _validate_shelf_panels(
    spec: FurnitureSpec,
    structure: CabinetStructure,
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
        expected = shelf_panel_boxes(spec, structure)
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
    structure: CabinetStructure,
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
        expected = drawer_panel_boxes(spec, structure)
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
