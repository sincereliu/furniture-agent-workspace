"""Validation owned by the manufacturing-planning stage."""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport
from furniture_panel_planning.panel_spec import FurnitureSpec, resolve_back_mount
from furniture_panel_planning.panel_models import PanelPlacement

from .manufacturing_bom import (
    BOMReport,
    VALID_MANUFACTURING_READINESS,
    emit_drilled_holes,
)


def validate_manufacturing(
    spec: FurnitureSpec,
    bom: BOMReport,
    placements: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="manufacturing_planned")
    if bom.requested_options:
        report.add_warning(
            "REQUESTED_MANUFACTURING_OPTIONS_PENDING",
            "requested manufacturing options are recorded but remain preliminary",
            "requested_options",
        )
    if bom.appearance:
        report.add_warning(
            "REQUESTED_APPEARANCE_PENDING",
            "appearance preferences are recorded for manufacturing review",
            "appearance",
        )
    if bom.readiness not in VALID_MANUFACTURING_READINESS:
        report.add_error(
            "INVALID_MANUFACTURING_READINESS",
            "manufacturing readiness must be one of: "
            + ", ".join(sorted(VALID_MANUFACTURING_READINESS)),
            "readiness",
        )
    if bom.panel_count != len(placements):
        report.add_error(
            "BOM_PANEL_MISMATCH",
            "BOM panel count does not match the confirmed panel plan",
        )
    if bom.total_area_m2 <= 0:
        report.add_error("INVALID_BOM_AREA", "BOM total area must be positive")
    for item in bom.hardware:
        if item.quantity < 0:
            report.add_error(
                "INVALID_HARDWARE_QUANTITY",
                f"{item.name} quantity cannot be negative",
                item.name,
            )
    placement_by_id = {item.id: item for item in placements}
    placement_ids = set(placement_by_id)
    manufacturing_ids = {item.label for item in bom.panels}
    if placement_ids != manufacturing_ids:
        report.add_error(
            "MANUFACTURING_PANEL_ID_MISMATCH",
            "manufacturing records must preserve every confirmed panel id",
        )
    operation_ids: set[str] = set()
    for operation in bom.operations:
        if operation.id in operation_ids:
            report.add_error(
                "DUPLICATE_OPERATION_ID",
                f"duplicate machining operation: {operation.id}",
                operation.id,
            )
        operation_ids.add(operation.id)
        if operation.target_panel not in placement_ids:
            report.add_error(
                "UNKNOWN_OPERATION_TARGET",
                f"{operation.id} targets unknown panel {operation.target_panel}",
                operation.id,
            )
        else:
            target = placement_by_id[operation.target_panel]
            outside_target = False
            for axis, size, position, target_size, target_position in (
                ("x", operation.size_x, operation.pos_x, target.size_x, target.pos_x),
                ("y", operation.size_y, operation.pos_y, target.size_y, target.pos_y),
                ("z", operation.size_z, operation.pos_z, target.size_z, target.pos_z),
            ):
                if (
                    position < target_position - 1e-6
                    or position + size > target_position + target_size + 1e-6
                ):
                    report.add_error(
                        "OPERATION_OUTSIDE_TARGET",
                        f"{operation.id} exceeds {operation.target_panel} on {axis.upper()}",
                        operation.id,
                    )
                    outside_target = True
            if "back_groove" in operation.id and outside_target:
                report.add_error(
                    "GROOVE_OUTSIDE_TARGET",
                    f"{operation.id} must remain inside its target panel envelope",
                    operation.id,
                )
        if operation.operation_type != "cut_box":
            report.add_error(
                "UNSUPPORTED_OPERATION",
                f"unsupported machining operation: {operation.operation_type}",
                operation.id,
            )
        if min(operation.size_x, operation.size_y, operation.size_z) <= 0:
            report.add_error(
                "NON_POSITIVE_OPERATION_SIZE",
                f"{operation.id} must have positive cutter dimensions",
                operation.id,
            )
    expected_back_groove_ids = {
        "left_side_back_groove",
        "right_side_back_groove",
        "top_back_groove",
        "bottom_back_groove",
    }
    back_groove_operations = [
        operation
        for operation in bom.operations
        if "back_groove" in operation.id
    ]
    actual_back_groove_ids = {
        operation.id for operation in back_groove_operations
    }
    back_mount = resolve_back_mount(
        spec.back_mount,
        spec.back_thickness,
        spec.board_thickness,
    )
    if (
        back_mount == "groove"
        and actual_back_groove_ids != expected_back_groove_ids
    ):
        report.add_error(
            "INCOMPLETE_BACK_GROOVES",
            "grooved back strategy requires four target-specific groove cuts",
            "operations",
        )
    if back_mount == "groove":
        if spec.groove_depth <= 0:
            report.add_error(
                "INVALID_GROOVE_DEPTH",
                "groove_depth must be greater than zero",
                "groove_depth",
            )
        elif spec.groove_depth > spec.board_thickness:
            report.add_error(
                "GROOVE_DEPTH_EXCEEDS_PANEL_THICKNESS",
                "groove_depth cannot exceed board_thickness",
                "groove_depth",
            )
        if spec.groove_clearance < 0:
            report.add_error(
                "INVALID_GROOVE_CLEARANCE",
                "groove_clearance cannot be negative",
                "groove_clearance",
            )
        expected_groove_width = (
            spec.back_thickness + spec.groove_clearance
        )
        for operation in back_groove_operations:
            if abs(operation.size_y - expected_groove_width) > 1e-6:
                report.add_error(
                    "GROOVE_WIDTH_MISMATCH",
                    f"{operation.id} does not preserve the specified groove width",
                    operation.id,
                )
    elif back_mount != "groove" and back_groove_operations:
        report.add_error(
            "UNEXPECTED_BACK_GROOVES",
            f"{back_mount} back strategy must not contain groove cuts",
            "operations",
        )
    manufacturing_by_id = {item.label: item for item in bom.panels}
    recorded_mounts = {item.back_mount for item in bom.panels}
    if recorded_mounts != {back_mount}:
        report.add_error(
            "BACK_MOUNT_CONTEXT_MISMATCH",
            "every manufacturing panel must retain the resolved back_mount",
            "panels",
        )
    back_panel = manufacturing_by_id.get("back_panel")
    expected_back_edges = (
        {} if back_mount == "groove"
        else {"四边": "ABS 1.0mm同色"}
    )
    if back_panel is None or back_panel.edge_banding != expected_back_edges:
        report.add_error(
            "BACK_EDGE_BANDING_MISMATCH",
            f"{back_mount} back strategy has incorrect edge banding",
            "back_panel",
        )
    rails = [
        item for item in bom.panels if item.panel_type == "back_rail"
    ]
    if any(
        rail.edge_banding != {"四边": "ABS 1.0mm同色"}
        for rail in rails
    ):
        report.add_error(
            "BACK_RAIL_EDGE_BANDING_MISMATCH",
            "back rails must follow the repository four-edge rule",
            "back_rail",
        )

    drilled = emit_drilled_holes(bom)
    drilled_by_panel = {
        panel["label"]: panel["holes"]
        for panel in drilled["panels"]
    }
    hole_types = [
        hole["hole_type"]
        for panel in drilled["panels"]
        for hole in panel["holes"]
    ]
    hardware_by_name = {item.name: item for item in bom.hardware}
    door_panels = [
        item for item in bom.panels if item.panel_type == "door"
    ]
    hinge_holes = [
        (panel, hole)
        for panel in door_panels
        for hole in drilled_by_panel.get(panel.label, [])
        if hole["hole_type"] == "hinge"
    ]
    for panel in door_panels:
        panel_hinges = [
            hole
            for hole in drilled_by_panel.get(panel.label, [])
            if hole["hole_type"] == "hinge"
        ]
        if not panel_hinges:
            report.add_error(
                "MISSING_HINGE_HOLES",
                f"{panel.label} requires hinge cup holes",
                panel.label,
            )
        for hole in panel_hinges:
            radius = hole["diameter"] / 2
            if (
                hole["diameter"] <= 0
                or hole["local_x"] - radius < -1e-6
                or hole["local_x"] + radius > panel.size_x + 1e-6
                or hole["local_z"] - radius < -1e-6
                or hole["local_z"] + radius > panel.size_z + 1e-6
            ):
                report.add_error(
                    "HINGE_HOLE_OUTSIDE_DOOR",
                    f"hinge cup on {panel.label} exceeds the door envelope",
                    panel.label,
                )
            expected_face_coordinate = (
                panel.size_y
                if panel.inner_face == "+y"
                else 0.0
            )
            if (
                panel.inner_face not in {"+y", "-y"}
                or abs(hole["local_y"] - expected_face_coordinate) > 1e-6
                or hole["direction"] != panel.inner_face
                or not hole["is_face_hole"]
            ):
                report.add_error(
                    "HINGE_HOLE_FACE_MISMATCH",
                    f"hinge cup on {panel.label} must enter from its inner face",
                    panel.label,
                )
            if hole["depth"] <= 0 or hole["depth"] > panel.size_y + 1e-6:
                report.add_error(
                    "INVALID_HINGE_HOLE_DEPTH",
                    f"hinge cup depth on {panel.label} exceeds door thickness",
                    panel.label,
                )
            if (
                panel.door_hinge_side == "left"
                and hole["local_x"] >= panel.size_x / 2
            ) or (
                panel.door_hinge_side == "right"
                and hole["local_x"] <= panel.size_x / 2
            ):
                report.add_error(
                    "HINGE_SIDE_MISMATCH",
                    f"hinge cup on {panel.label} is on the wrong door edge",
                    panel.label,
                )
    expected_hinge_count = sum(
        item.quantity
        for item in bom.hardware
        if item.name == "液压缓冲铰链"
    )
    if len(hinge_holes) != expected_hinge_count:
        report.add_error(
            "HINGE_HARDWARE_COUNT_MISMATCH",
            "hinge cup count must match hinge hardware quantity",
            "hardware",
        )
    manufacturing_contracts: dict[
        str,
        tuple[str, tuple[str, ...]],
    ] = {
        "insert": (
            "三合一连接件（内嵌背板）",
            (
                "back_insert_cam",
                "back_insert_rod",
                "back_insert_pre_nut",
            ),
        ),
        "cover": (
            "沉头木螺钉（外盖背板）",
            (
                "cover_back_clearance",
                "cover_back_pilot",
            ),
        ),
    }
    if back_mount == "groove" and rails:
        manufacturing_contracts["groove"] = (
            "沉头木螺钉（背拉条）",
            (
                "back_rail_side_clearance",
                "back_rail_pilot",
            ),
        )
    contract = manufacturing_contracts.get(back_mount)
    if contract is not None:
        hardware_name, required_hole_types = contract
        hardware = hardware_by_name.get(hardware_name)
        counts = {
            hole_type: hole_types.count(hole_type)
            for hole_type in required_hole_types
        }
        if hardware is None or hardware.quantity <= 0:
            report.add_error(
                "MISSING_BACK_MOUNT_HARDWARE",
                f"{back_mount} back strategy is missing {hardware_name}",
                "hardware",
            )
        if any(count <= 0 for count in counts.values()):
            report.add_error(
                "MISSING_BACK_MOUNT_HOLES",
                f"{back_mount} back strategy is missing matched hole records",
                "drilled_holes",
            )
        elif len(set(counts.values())) != 1:
            report.add_error(
                "BACK_MOUNT_HOLE_COUNT_MISMATCH",
                f"{back_mount} mating hole counts do not match",
                "drilled_holes",
            )
        elif (
            hardware is not None
            and hardware.quantity != next(iter(counts.values()))
        ):
            report.add_error(
                "BACK_MOUNT_HARDWARE_COUNT_MISMATCH",
                f"{hardware_name} quantity does not match its hole pattern",
                "hardware",
            )
    return report
