"""订单构建器 — 将订单中的所有柜体合并计算，生成各交付文件

职责:
  ✅ 遍历订单所有柜体 → 合并 BOM / 五金 / 开料 / 打孔
  ✅ 生成 采购/ 生产/ 归档/ 三个交付组的所有文件
  ❌ 不管理订单目录（那是 order_manager 的职责）
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from furniture_schema.order import Order, OrderItem
from furniture_schema.panel import PanelRecord
from furniture_schema.hardware import HardwareRecord


def build_order(order: Order, order_dir: Path) -> dict:
    """为订单构建所有产出文件。

    Returns:
        包含所有文件路径的摘要 dict
    """
    # 收集所有柜体的数据
    all_panels: List[PanelRecord] = []
    all_hardware: List[HardwareRecord] = []
    all_drilling: list = []

    for item in order.items:
        from furniture_pipeline.cabinet import plan_cabinet
        result = plan_cabinet(item.spec)
        all_panels.extend(result.panels)
        all_hardware.extend(result.bom.hardware)

        # 收集打孔数据
        from furniture_panelizer.drilling_engine import calc_system_32_holes, calc_hinge_positions
        for panel in result.panels:
            holes_data = {"panel_id": panel.label, "panel_name": panel.name, "panel_type": panel.panel_type}
            if panel.panel_type in ("side", "top", "bottom", "fixed_shelf"):
                holes_data["system_32_holes"] = calc_system_32_holes(panel.drill_length)
            if panel.panel_type == "door":
                holes_data["hinge_holes"] = calc_hinge_positions(
                    door_height_mm=panel.size_z, door_width_mm=panel.size_x,
                    variant_group="国内35mm杯全盖"
                )
            all_drilling.append(holes_data)

    # ── 1. 采购组 ──
    purchase_dir = order_dir / "采购"
    hardware_json = purchase_dir / "hardware_list.json"
    hardware_md = purchase_dir / "hardware_list.md"
    _write_hardware_files(all_hardware, hardware_json, hardware_md)

    # 板材采购单
    from furniture_panelizer.cut_optimizer import optimize_cutting, CutListReport
    cut_plans = optimize_cutting(all_panels)
    cut_report = CutListReport.from_plans(cut_plans)

    panel_purchase = {}
    for plan in cut_plans:
        key = f"{plan.board_thickness_mm:.0f}mm {plan.board_name.rsplit(' ', 1)[0]}"
        panel_purchase[key] = panel_purchase.get(key, 0) + 1

    panel_purchase_json = purchase_dir / "panel_purchase.json"
    panel_purchase_md = purchase_dir / "panel_purchase.md"
    _write_panel_purchase(panel_purchase, panel_purchase_json, panel_purchase_md)

    # ── 2. 生产组 ──
    prod_dir = order_dir / "生产"
    cut_json = prod_dir / "cut_list.json"
    cut_md = prod_dir / "cut_list.md"
    _write_cut_files(cut_report, cut_json, cut_md)

    # 排样 PNG
    from furniture_panelizer.cut_optimizer import render_cut_layout_png
    for i, plan in enumerate(cut_plans):
        render_cut_layout_png(plan, prod_dir / "cut_plans" / f"board_{i+1}.png")

    # 打孔数据
    drilling_json = prod_dir / "drilling_data.json"
    drilling_json.write_text(json.dumps(all_drilling, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 3. 归档组 ──
    archive_dir = order_dir / "归档"
    panel_json = archive_dir / "panel_list.json"
    panel_md = archive_dir / "panel_list.md"
    _write_panel_files(all_panels, panel_json, panel_md)

    return {
        "order_id": order.order_id,
        "purchase": [str(hardware_json), str(hardware_md), str(panel_purchase_json), str(panel_purchase_md)],
        "production": [str(cut_json), str(cut_md), str(drilling_json)],
        "archive": [str(panel_json), str(panel_md)],
        "total_panels": len(all_panels),
        "total_hardware_items": len(all_hardware),
        "total_boards": cut_report.total_boards,
    }


def _write_hardware_files(hw_list: List[HardwareRecord], json_path: Path, md_path: Path):
    json_path.write_text(json.dumps([
        {"name": h.name, "spec": h.spec, "quantity": h.quantity, "unit": h.unit, "brand": h.brand, "model": h.model}
        for h in hw_list
    ], ensure_ascii=False, indent=2), encoding="utf-8")

    lines = ["# 五金料单", "", "| 名称 | 规格 | 数量 | 单位 |", "|------|------|------|------|"]
    for h in hw_list:
        lines.append(f"| {h.name} | {h.spec} | {h.quantity} | {h.unit} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def _write_panel_purchase(data: dict, json_path: Path, md_path: Path):
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 板材采购单", "", "| 板材类型 | 数量(张) |", "|------|------|"]
    for k, v in data.items():
        lines.append(f"| {k} | {v} |")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def _write_cut_files(report: "CutListReport", json_path: Path, md_path: Path):
    from furniture_panelizer.cut_optimizer import CuttingPlan
    json_path.write_text(json.dumps([
        {"board": p.board_name, "length": p.board_length_mm, "width": p.board_width_mm,
         "pieces": len(p.pieces), "utilization": p.utilization_pct}
        for p in report.plans
    ], ensure_ascii=False, indent=2), encoding="utf-8")

    from furniture_panelizer.cut_optimizer import format_cut_list_markdown
    md_path.write_text(format_cut_list_markdown(report), encoding="utf-8")


def _write_panel_files(panels: List[PanelRecord], json_path: Path, md_path: Path):
    json_path.write_text(json.dumps([
        {"name": p.name, "type": p.panel_type, "length": p.length_mm, "width": p.width_mm,
         "thickness": p.thickness, "material": p.material, "quantity": p.quantity}
        for p in panels
    ], ensure_ascii=False, indent=2), encoding="utf-8")

    from furniture_panelizer.bom import format_bom_markdown
    from furniture_panelizer.bom import BOMReport
    fake_report = BOMReport(furniture_name="", dimensions="", panels=panels, hardware=[], total_area_m2=0)
    md_path.write_text(format_bom_markdown(fake_report), encoding="utf-8")