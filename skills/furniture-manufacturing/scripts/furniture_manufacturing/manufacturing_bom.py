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
                drilling=match["drilling"],
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
