"""Validation owned by the manufacturing-planning stage."""

from __future__ import annotations

from furniture_delivery_validation.validation import ValidationReport
from furniture_design_intent.design_spec import FurnitureSpec, resolve_back_mount
from furniture_panel_planning.panel_models import PanelPlacement

from .manufacturing_bom import BOMReport, emit_drilled_holes


def validate_manufacturing(
    spec: FurnitureSpec,
    bom: BOMReport,
    placements: list[PanelPlacement],
) -> ValidationReport:
    report = ValidationReport(stage="manufacturing_planned")
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
    hole_types = [
        hole["hole_type"]
        for panel in drilled["panels"]
        for hole in panel["holes"]
    ]
    hardware_by_name = {item.name: item for item in bom.hardware}
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
