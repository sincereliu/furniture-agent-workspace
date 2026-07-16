"""Manufacturing policy, machining operations, hardware, and BOM output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from furniture_design_intent.design_spec import FurnitureSpec, resolve_back_mount
from furniture_panel_planning.panel_models import PanelPlacement

from .manufacturing_edge_banding import get_edge_banding
from .manufacturing_drilling import calc_system_32_holes
from .manufacturing_hardware import (
    match_drawer_slides,
    match_hinges,
    match_shelf_connectors,
    match_three_in_one,
)
from .manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


FURNITURE_NAMES = {
    "floor_cabinet": "落地柜",
    "wall_cabinet": "吊柜",
}


@dataclass
class BOMReport:
    furniture_name: str
    dimensions: str
    panels: list[PanelRecord]
    hardware: list[HardwareRecord]
    operations: list[MachiningOperation]
    total_area_m2: float = 0.0

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    @property
    def hardware_item_count(self) -> int:
        return len(self.hardware)


def plan_manufacturing(
    spec: FurnitureSpec,
    placements: list[PanelPlacement],
) -> BOMReport:
    """Stage 4: apply materials and emit explicit machining operations."""
    back_mount = resolve_back_mount(
        spec.back_mount, spec.back_thickness, spec.board_thickness
    )
    panels = [_manufacturing_panel(spec, back_mount, item) for item in placements]
    operations = _back_groove_operations(spec, back_mount, placements)
    dimensions = f"{spec.width:.0f}×{spec.height:.0f}×{spec.depth:.0f}mm"
    return BOMReport(
        furniture_name=FURNITURE_NAMES.get(spec.furniture_type, spec.furniture_type),
        dimensions=dimensions,
        panels=panels,
        hardware=estimate_hardware(panels),
        operations=operations,
        total_area_m2=sum(panel.area_m2 for panel in panels),
    )


def _manufacturing_panel(spec: FurnitureSpec, back_mount: str, placement: PanelPlacement) -> PanelRecord:
    if placement.material_role == "back":
        material = f"{spec.back_thickness:g}mm背板"
        thickness = spec.back_thickness
    elif placement.material_role == "door":
        material = f"{spec.door_thickness:g}mm门板"
        thickness = spec.door_thickness
    else:
        material = f"{spec.board_thickness:g}mm柜体板"
        thickness = spec.board_thickness
    drill_length = 0.0
    if placement.panel_type in ("side", "divider"):
        drill_length = placement.size_z
    elif placement.panel_type in ("top", "bottom", "fixed_shelf", "movable_shelf"):
        drill_length = placement.size_x
    elif placement.panel_type == "door":
        drill_length = placement.size_z
    return PanelRecord(
        label=placement.id,
        name=placement.name,
        panel_type=placement.panel_type,
        material=material,
        thickness=thickness,
        length_mm=placement.size_x,
        width_mm=placement.size_y,
        size_x=placement.size_x,
        size_y=placement.size_y,
        size_z=placement.size_z,
        quantity=placement.quantity,
        drill_length=drill_length,
        edge_banding=_edge_banding_for(placement.panel_type, back_mount),
        note=placement.note,
        pos_x=placement.pos_x,
        pos_y=placement.pos_y,
        pos_z=placement.pos_z,
        depends_on=list(placement.depends_on),
    )


def _drill_operations(panels: list[PanelRecord]) -> list[MachiningOperation]:
    """Generate MachiningOperations for every drill hole.

    Each hole is modelled as a square-section cut_box (diameter × diameter × depth)
    placed at the global hole position. The cylindrical hole is approximated by
    a square cross-section, which is visually sufficient for STEP geometry.
    """
    ops: list[MachiningOperation] = []
    # Use the same coordinate conversion logic as emit_drilled_holes
    panel_by_label = {p.label: p for p in panels}
    hardware = estimate_hardware(panels)
    hole_index = 0

    for hw in hardware:
        drilling = hw.drilling
        if not drilling or not isinstance(drilling, dict):
            continue
        hole_type = drilling.get("hole_type", "")

        if hole_type == "hinge":
            panel_id = drilling.get("panel_id", "")
            panel = panel_by_label.get(panel_id)
            if not panel:
                continue
            for hole in drilling.get("holes", []):
                y_local = float(hole.get("y_mm", 0))
                x_offset = float(hole.get("x_offset_mm", 5))
                diam = float(hole.get("cup_diameter_mm", 35))
                depth = float(hole.get("cup_depth_mm", 13))
                diam = float(hole.get("cup_diameter_mm", 35))
                depth = float(hole.get("cup_depth_mm", 13))
                # Place hole center at x_offset from panel edge, clip within panel
                cx = max(panel.pos_x + diam / 2, min(panel.pos_x + panel.size_x - diam / 2, panel.pos_x + x_offset))
                y_global = panel.pos_y + panel.size_y
                z_global = panel.pos_z + y_local
                hole_index += 1
                ops.append(MachiningOperation(
                    id=f"hinge_hole_{hole_index:03d}",
                    operation_type="cut_box",
                    target_panel=panel.label,
                    size_x=diam,
                    size_y=depth,
                    size_z=diam,
                    pos_x=cx - diam / 2,
                    pos_y=y_global - depth,
                    pos_z=z_global - diam / 2,
                    note=f"铰链杯孔 φ{diam:g}",
                ))

        elif hole_type == "three_in_one":
            wheel = drilling.get("eccentric_wheel", {})
            rod = drilling.get("connecting_rod", {})
            w_diam = float(wheel.get("diameter_mm", 12))
            w_depth = float(wheel.get("hole_depth_mm", 13.5))
            r_diam = float(rod.get("diameter_mm", 8))
            r_depth = float(rod.get("insertion_depth_mm", 33))

            for fd in drilling.get("female", []):
                panel_id = fd.get("panel_id", "")
                panel = panel_by_label.get(panel_id)
                if not panel:
                    continue
                z_start = panel.pos_z
                y_global = panel.pos_y + panel.size_y - wheel.get("center_offset_from_edge_mm", 33.5)
                x_global = panel.pos_x + panel.size_x
                for y_local in fd.get("hole_positions_y_mm", []):
                    z_global = z_start + float(y_local)
                    hole_index += 1
                    ops.append(MachiningOperation(
                        id=f"female_hole_{hole_index:03d}",
                        operation_type="cut_box",
                        target_panel=panel.label,
                        size_x=w_depth,
                        size_y=w_diam,
                        size_z=w_diam,
                        pos_x=x_global - w_depth,
                        pos_y=y_global - w_diam / 2,
                        pos_z=z_global - w_diam / 2,
                        note=f"偏心轮孔 φ{w_diam:g}",
                    ))

            for md in drilling.get("male", []):
                panel_id = md.get("panel_id", "")
                panel = panel_by_label.get(panel_id)
                if not panel:
                    continue
                panel_z = float(md.get("panel_z_mm", panel.pos_z))
                y_global = panel.pos_y + panel.size_y - 33.5
                for x_local in md.get("hole_positions_on_edge_mm", []):
                    x_global = panel.pos_x + float(x_local)
                    hole_index += 1
                    ops.append(MachiningOperation(
                        id=f"male_hole_{hole_index:03d}",
                        operation_type="cut_box",
                        target_panel=panel.label,
                        size_x=r_depth,
                        size_y=r_diam,
                        size_z=r_diam,
                        pos_x=x_global,
                        pos_y=y_global - r_diam / 2,
                        pos_z=panel_z + panel.size_z - r_diam,
                        note=f"连接杆孔 φ{r_diam:g}",
                    ))

        elif hole_type == "shelf_connector":
            for sp in drilling.get("panels", []):
                panel_id = sp.get("panel_id", "")
                panel = panel_by_label.get(panel_id)
                if not panel:
                    continue
                y_global = panel.pos_y + panel.size_y - 32
                for x_local in sp.get("hole_positions_on_edge_mm", []):
                    x_global = panel.pos_x + float(x_local)
                    z_global = panel.pos_z + panel.size_z / 2
                    hole_index += 1
                    ops.append(MachiningOperation(
                        id=f"shelf_hole_{hole_index:03d}",
                        operation_type="cut_box",
                        target_panel=panel.label,
                        size_x=10.0,
                        size_y=12.0,
                        size_z=10.0,
                        pos_x=x_global - 5.0,
                        pos_y=y_global,
                        pos_z=z_global - 5.0,
                        note="层板托孔 φ10",
                    ))

    return ops


def _edge_banding_for(panel_type: str, back_mount: str) -> dict[str, str]:
    if panel_type == "back" and back_mount == "groove":
        return {}
    return get_edge_banding(panel_type)


def _back_groove_operations(
    spec: FurnitureSpec,
    back_mount: str,
    placements: list[PanelPlacement],
) -> list[MachiningOperation]:
    if back_mount != "groove":
        return []
    by_id = {panel.id: panel for panel in placements}
    required = {"left_side_panel", "right_side_panel", "top_panel", "bottom_panel", "back_panel"}
    if not required.issubset(by_id):
        return []
    back = by_id["back_panel"]
    board = spec.board_thickness
    depth = spec.groove_depth
    groove_width = spec.back_thickness + spec.groove_clearance
    groove_y = spec.back_offset
    common = {"operation_type": "cut_box", "size_y": groove_width, "pos_y": groove_y}
    return [
        MachiningOperation(
            id="left_side_back_groove",
            target_panel="left_side_panel",
            size_x=depth,
            size_z=back.size_z,
            pos_x=board - depth,
            pos_z=back.pos_z,
            note="左侧板背板槽",
            **common,
        ),
        MachiningOperation(
            id="right_side_back_groove",
            target_panel="right_side_panel",
            size_x=depth,
            size_z=back.size_z,
            pos_x=spec.width - board,
            pos_z=back.pos_z,
            note="右侧板背板槽",
            **common,
        ),
        MachiningOperation(
            id="top_back_groove",
            target_panel="top_panel",
            size_x=spec.width - 2 * board,
            size_z=depth,
            pos_x=board,
            pos_z=spec.height - board,
            note="顶板背板槽",
            **common,
        ),
        MachiningOperation(
            id="bottom_back_groove",
            target_panel="bottom_panel",
            size_x=spec.width - 2 * board,
            size_z=depth,
            pos_x=board,
            pos_z=by_id["bottom_panel"].pos_z + board - depth,
            note="底板背板槽",
            **common,
        ),
    ]


def estimate_hardware(panels: List[PanelRecord]) -> List[HardwareRecord]:
    hardware: List[HardwareRecord] = []
    three_in_one = match_three_in_one(panels)
    if three_in_one:
        match = three_in_one[0]
        hardware.append(HardwareRecord(
            name="三合一连接件",
            spec="偏心轮φ12+预埋螺母φ10×11+连接杆φ8×33",
            quantity=match["sets"],
            unit="套",
            brand=match["brand"],
            model=match["model"],
            drilling={
                "hole_type": "three_in_one",
                "female": match["female_details"],
                "male": match["male_details"],
                "eccentric_wheel": match["eccentric_wheel"],
                "connecting_rod": match["connecting_rod"],
            },
        ))
    shelf_matches = match_shelf_connectors(panels)
    if shelf_matches:
        hardware.append(HardwareRecord(
            name=f"{shelf_matches[0]['connector_type']}连接件",
            spec=f"{shelf_matches[0]['brand']} {shelf_matches[0]['model']}",
            quantity=sum(item["sets"] for item in shelf_matches),
            unit="套",
            brand=shelf_matches[0]["brand"],
            model=shelf_matches[0]["model"],
            drilling={
                "hole_type": "shelf_connector",
                "panels": shelf_matches,
            },
        ))
    doors = [panel for panel in panels if panel.panel_type == "door"]
    if doors:
        side = next((panel for panel in panels if panel.panel_type == "side"), None)
        system_holes = calc_system_32_holes(side.drill_length) if side else None
        shelf_zs = [
            panel.pos_z
            for panel in panels
            if panel.panel_type in ("top", "bottom", "fixed_shelf")
        ]
        for match in match_hinges(doors, system_holes=system_holes, shelf_positions=shelf_zs):
            hardware.append(HardwareRecord(
                name="液压缓冲铰链",
                spec=f"{match['brand']} {match['model']} {match['angle']}°{match['overlay']}",
                quantity=match["quantity"],
                brand=match["brand"],
                model=match["model"],
                note=f"门板: {match['panel_name']}",
                drilling={
                    "hole_type": "hinge",
                    "panel_id": match["panel_id"],
                    "holes": match["drilling"],
                },
            ))
        hardware.append(HardwareRecord(name="弹压门碰", spec="推弹式", quantity=len(doors)))
    if any(panel.panel_type == "toe_kick" for panel in panels):
        hardware.append(HardwareRecord(name="L型角码", spec="25×25mm镀锌", quantity=4))
    if any("drawer" in panel.panel_type for panel in panels):
        drawer_depth = max((p.size_y for p in panels if p.panel_type in ("side", "bottom")), default=450)
        drawer_width = max((p.size_x for p in panels if p.panel_type in ("top", "bottom")), default=800)
        for slide in match_drawer_slides(drawer_depth, drawer_width):
            hardware.append(HardwareRecord(
                name="抽屉滑轨",
                spec=f"{slide['brand']} {slide['model']} {slide['length_mm']}mm {slide['load_rating']}",
                quantity=slide["quantity"],
                unit="副",
                brand=slide["brand"],
                model=slide["model"],
            ))
    return hardware


def format_bom_markdown(report: BOMReport) -> str:
    lines = [
        f"## 拆单报告 - {report.furniture_name}",
        "",
        f"外形尺寸: **{report.dimensions}**",
        "",
        f"### 板件清单 ({report.panel_count} 块)",
        "",
        "| 序号 | 名称 | 类型 | 开料尺寸(mm) | 厚度 | 数量 | 封边 | 备注 |",
        "|------|------|------|-------------|------|------|------|------|",
    ]
    for index, panel in enumerate(report.panels, 1):
        lines.append(
            f"| {index} | {panel.name} | {panel.panel_type} | "
            f"{panel.length_mm:.0f}×{panel.width_mm:.0f} | "
            f"{panel.thickness:.0f} | {panel.quantity} | "
            f"{panel.edge_banding_summary()} | {panel.note} |"
        )
    lines.extend(["", f"**总展开面积**: {report.total_area_m2:.4f} m²"])
    if report.operations:
        lines.extend(["", f"### 加工操作 ({len(report.operations)} 项)", ""])
        for operation in report.operations:
            lines.append(
                f"- {operation.note}: {operation.target_panel}, "
                f"{operation.size_x:g}×{operation.size_y:g}×{operation.size_z:g}mm"
            )
    if report.hardware:
        lines.extend(["", f"### 五金清单 ({len(report.hardware)} 项)", ""])
        for item in report.hardware:
            lines.append(f"- {item.name} {item.spec} ×{item.quantity}{item.unit}")
    return "\n".join(lines)


_COLOR_LEGEND = {
    "hinge":           {"color": "#4A90D9", "label": "铰链杯孔 35mm"},
    "system_32_female": {"color": "#FF6B35", "label": "三合一偏心轮孔 12mm"},
    "system_32_male":  {"color": "#FF4500", "label": "三合一连接杆端孔 8mm"},
    "shelf_connector": {"color": "#00A86B", "label": "层板托孔"},
    "back_groove":     {"color": "#FFD700", "label": "背板槽"},
}


def emit_drilled_holes(bom: BOMReport) -> dict:
    """Generate a per-panel hole summary for Viewer overlay.

    Walks BOMReport.hardware drilling data, groups holes by panel label,
    converts local coordinates to global, and attaches hole_type + color.
    """
    panel_by_label = {p.label: p for p in bom.panels}
    panel_holes: dict[str, list[dict]] = {}

    for hw in bom.hardware:
        drilling = hw.drilling
        if not drilling or not isinstance(drilling, dict):
            continue

        hole_type = drilling.get("hole_type", "")

        if hole_type == "hinge":
            _add_hinge_holes(panel_holes, panel_by_label, drilling)

        elif hole_type == "three_in_one":
            _add_three_in_one_female(panel_holes, panel_by_label, drilling)
            _add_three_in_one_male(panel_holes, panel_by_label, drilling)

        elif hole_type == "shelf_connector":
            _add_shelf_connector_holes(panel_holes, panel_by_label, drilling)

    panels_out = []
    for panel in bom.panels:
        entry: dict = {
            "label": panel.label,
            "name": panel.name,
            "box": {
                "x": panel.size_x, "y": panel.size_y, "z": panel.size_z,
                "pos_x": panel.pos_x, "pos_y": panel.pos_y, "pos_z": panel.pos_z,
            },
            "holes": panel_holes.get(panel.label, []),
        }
        panels_out.append(entry)

    return {
        "furniture_name": bom.furniture_name,
        "dimensions": bom.dimensions,
        "color_legend": _COLOR_LEGEND,
        "panels": panels_out,
    }


def _add_hinge_holes(
    panel_holes: dict, panel_by_label: dict, drilling: dict,
) -> None:
    panel_id = drilling.get("panel_id", "")
    panel = panel_by_label.get(panel_id)
    if not panel:
        return
    for hole in drilling.get("holes", []):
        y_local = float(hole.get("y_mm", 0))
        x_offset = float(hole.get("x_offset_mm", 5))
        # Door panel hinge-side edge:
        #   left door hinge on left edge  → x = pos_x + x_offset
        #   right door hinge on right edge → x = pos_x + size_x - x_offset
        if panel.pos_x < panel.size_x:
            x_global = panel.pos_x + x_offset
        else:
            x_global = panel.pos_x + panel.size_x - x_offset

        z_global = panel.pos_z + y_local
        # Door face: Y is the panel's pos_y + size_y (front face)
        y_global = panel.pos_y + panel.size_y

        panel_holes.setdefault(panel_id, []).append({
            "hole_type": "hinge",
            "color": _COLOR_LEGEND["hinge"]["color"],
            "x": round(x_global, 2),
            "y": round(y_global, 2),
            "z": round(z_global, 2),
            "diameter": float(hole.get("cup_diameter_mm", 35)),
            "depth": float(hole.get("cup_depth_mm", 13)),
            "direction": "+y",
        })


def _add_three_in_one_female(
    panel_holes: dict, panel_by_label: dict, drilling: dict,
) -> None:
    """Eccentric wheel holes on side/divider panel inner faces."""
    wheel = drilling.get("eccentric_wheel", {})
    diam = float(wheel.get("diameter_mm", 12))
    depth = float(wheel.get("hole_depth_mm", 13.5))
    center_offset = float(wheel.get("center_offset_from_edge_mm", 33.5))

    for fd in drilling.get("female", []):
        panel_id = fd.get("panel_id", "")
        panel = panel_by_label.get(panel_id)
        if not panel:
            continue
        z_start = panel.pos_z
        for y_local in fd.get("hole_positions_y_mm", []):
            z_global = z_start + float(y_local)
            # Face center: for left side panel inner face is at x = pos_x + size_x
            # Y from front edge (panel.pos_y + panel.size_y - center_offset)
            x_global = panel.pos_x + panel.size_x
            y_global = panel.pos_y + panel.size_y - center_offset

            panel_holes.setdefault(panel_id, []).append({
                "hole_type": "system_32_female",
                "color": _COLOR_LEGEND["system_32_female"]["color"],
                "x": round(x_global, 2),
                "y": round(y_global, 2),
                "z": round(z_global, 2),
                "diameter": diam,
                "depth": depth,
                "direction": "-x",
            })


def _add_three_in_one_male(
    panel_holes: dict, panel_by_label: dict, drilling: dict,
) -> None:
    """Connecting rod holes on top/bottom/shelf panel edges."""
    rod = drilling.get("connecting_rod", {})
    diam = float(rod.get("diameter_mm", 8))
    depth = float(rod.get("insertion_depth_mm", 33))

    for md in drilling.get("male", []):
        panel_id = md.get("panel_id", "")
        panel = panel_by_label.get(panel_id)
        if not panel:
            continue
        panel_z = float(md.get("panel_z_mm", panel.pos_z))
        # Holes on both left and right edges of top/bottom/shelf panels
        # Edge faces: left edge at x = pos_x, right edge at x = pos_x + size_x
        for x_local in md.get("hole_positions_on_edge_mm", []):
            x_global = panel.pos_x + float(x_local)
            # Holes on both ends (left and right edges where panel meets side panels)
            # Each hole position has two instances (one per edge)
            for edge_x, sign in [(panel.pos_x, "-x"), (panel.pos_x + panel.size_x, "+x")]:
                y_global = panel.pos_y + panel.size_y - 33.5  # same Y as eccentric wheel
                panel_holes.setdefault(panel_id, []).append({
                    "hole_type": "system_32_male",
                    "color": _COLOR_LEGEND["system_32_male"]["color"],
                    "x": round(edge_x, 2),
                    "y": round(y_global, 2),
                    "z": round(panel_z + panel.size_z, 2),
                    "diameter": diam,
                    "depth": depth,
                    "direction": sign,
                })


def _add_shelf_connector_holes(
    panel_holes: dict, panel_by_label: dict, drilling: dict,
) -> None:
    """Shelf pin holes on side panels for movable shelves."""
    for sp in drilling.get("panels", []):
        panel_id = sp.get("panel_id", "")
        panel = panel_by_label.get(panel_id)
        if not panel:
            continue
        for x_local in sp.get("hole_positions_on_edge_mm", []):
            x_global = panel.pos_x + float(x_local)
            # Shelf pin holes go on the inner face of side panels
            # Y = pos_y + size_y - standard offset (~32mm)
            y_global = panel.pos_y + panel.size_y - 32
            z_global = panel.pos_z + panel.size_z / 2  # approximate

            panel_holes.setdefault(panel_id, []).append({
                "hole_type": "shelf_connector",
                "color": _COLOR_LEGEND["shelf_connector"]["color"],
                "x": round(x_global, 2),
                "y": round(y_global, 2),
                "z": round(z_global, 2),
                "diameter": 10.0,
                "depth": 12.0,
                "direction": "-x",
            })
