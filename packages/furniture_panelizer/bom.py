"""BOM 生成器 — 五金件估算 + 汇总输出。

从外部 generator.py 的 get_hardware_list() 和 print_bom() 迁移。
不依赖 build123d，纯数据统计。
"""

from __future__ import annotations

from typing import List

from furniture_schema.hardware import HardwareRecord
from furniture_schema.panel import PanelRecord

from dataclasses import dataclass


@dataclass
class BOMReport:
    """完整的拆单报告。

    这是 Panelizer（拆单层）的产出物，不是 Schema 定义。
    """

    furniture_name: str
    dimensions: str
    panels: list  # List[PanelRecord]
    hardware: list  # List[HardwareRecord]
    total_area_m2: float = 0.0
    cut_plans: list | None = None  # List[CuttingPlan] from cut_optimizer

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    @property
    def hardware_item_count(self) -> int:
        return len(self.hardware)


# ============================================================
# 孔位算法（从外部 generator.py 原样迁移，零改动）
# ============================================================
def calc_system_holes(
    board_length: float, first: float = 64.0, last: float = 64.0, max_spacing: float = 512.0
) -> List[float]:
    """32mm 系统排钻孔位计算"""
    usable = board_length - first - last
    if usable <= 0:
        return [board_length / 2]
    spacings = [512, 480, 448, 416, 384, 352, 320, 288, 256, 224, 192, 160, 128, 96, 64]
    best = 320.0
    for sp in spacings:
        if sp <= max_spacing and int(usable / sp) >= 1:
            best = sp
            break
    count = max(1, int(usable / best))
    actual = usable / count
    holes = [first] + [first + (i + 1) * actual for i in range(count - 1)] + [board_length - last]
    holes = sorted(set(holes))
    merged = [holes[0]]
    for h in holes[1:]:
        if h - merged[-1] >= 32:
            merged.append(h)
    return merged


def calc_shelf_holes(board_length: float) -> List[float]:
    """层板托孔位计算"""
    if board_length <= 192:
        return [32.0, board_length - 32.0]
    if board_length <= 550:
        return [64.0, board_length - 64.0]
    holes = [64.0, board_length / 2, board_length - 64.0]
    if board_length > 1100:
        usable = board_length - 128
        extra = int((board_length - 1100) / 550) + 1
        spacing = usable / (extra + 1)
        for i in range(1, extra + 1):
            holes.append(64.0 + i * spacing)
    return sorted(set(holes))


def calc_hinge_positions(door_h: float) -> List[float]:
    """铰链位置计算（按门高自动递增）"""
    if door_h <= 900:
        return [100.0, door_h - 100.0]
    if door_h <= 1500:
        return [100.0, door_h / 2, door_h - 100.0]
    if door_h <= 2200:
        return [100.0, door_h / 3, door_h * 2 / 3, door_h - 100.0]
    return [100.0, door_h / 4, door_h / 2, door_h * 3 / 4, door_h - 100.0]


# ============================================================
# 五金估算
# ============================================================
def estimate_hardware(panels: List[PanelRecord]) -> List[HardwareRecord]:
    """根据板件列表估算五金件数量。

    Phase 1 不依赖外部五金库，仅做近似计算。
    """
    hw: List[HardwareRecord] = []

    # 三合一连接件 — 使用硬件匹配引擎
    from furniture_panelizer.hardware_matcher import match_three_in_one
    tio_matches = match_three_in_one(panels)
    if tio_matches:
        tio = tio_matches[0]  # 汇总结果
        hw.append(HardwareRecord(
            name="三合一连接件",
            spec="偏心轮φ12+预埋螺母φ10×11+连接杆φ8×33",
            quantity=tio["sets"],
            unit="套",
            brand=tio["brand"],
            model=tio["model"],
        ))

    # 活动层板连接件 — 使用硬件匹配引擎
    from furniture_panelizer.hardware_matcher import match_shelf_connectors
    shelf_matches = match_shelf_connectors(panels)
    if shelf_matches:
        total_shelf_sets = sum(m["sets"] for m in shelf_matches)
        hw.append(HardwareRecord(
            name=f"{shelf_matches[0]['connector_type']}连接件",
            spec=f"{shelf_matches[0]['brand']} {shelf_matches[0]['model']}",
            quantity=total_shelf_sets,
            unit="套",
            brand=shelf_matches[0]["brand"],
            model=shelf_matches[0]["model"],
        ))
    # 如果当前柜体没有活动层板，则匹配结果为空

    # 铰链 — 使用硬件匹配引擎（接入真实避让数据）
    door_panels = [p for p in panels if p.panel_type == "door"]
    if door_panels:
        from furniture_panelizer.hardware_matcher import match_hinges
        from furniture_panelizer.drilling_engine import calc_system_32_holes

        # 计算侧板系统排钻孔位（用于铰链避让）
        side_panel = next((p for p in panels if p.panel_type == "side"), None)
        real_system_holes = calc_system_32_holes(side_panel.drill_length) if side_panel else None

        # 计算固定层板+顶板+底板的 Z 高度（用于铰链避让层板位置）
        shelf_zs = [p.pos_z for p in panels if p.panel_type in ("top", "bottom", "fixed_shelf")]

        hinge_matches = match_hinges(
            door_panels,
            system_holes=real_system_holes,
            shelf_positions=shelf_zs,
        )
        for match in hinge_matches:
            hw.append(HardwareRecord(
                "液压缓冲铰链",
                f"{match['brand']} {match['model']} {match['angle']}°{match['overlay']}",
                match["quantity"],
                brand=match["brand"],
                model=match["model"],
                note=f"门板: {match['panel_name']}",
                drilling=match["drilling"],
            ))

    # 踢脚线角码
    if any(p.panel_type == "toe_kick" for p in panels):
        hw.append(HardwareRecord(name="L型角码", spec="25×25mm镀锌", quantity=4, unit="个"))

    # 背板螺丝
    if any(p.panel_type == "back" for p in panels):
        hw.append(HardwareRecord(name="自攻螺丝", spec="3.5×16mm", quantity=30, unit="个"))

    # 抽屉滑轨 — 当柜体含抽屉时触发
    # 抽屉深度 = 柜体深度 - 背板偏移 - 滑轨间隙
    drawer_flag = any("drawer" in (p.panel_type or "") for p in panels)
    if drawer_flag:
        from furniture_panelizer.hardware_matcher import match_drawer_slides

        # 从板件列表中推断抽屉参数（depth = 柜体depth方向，width = 柜体width方向）
        drawer_depth = max((p.size_y for p in panels if p.panel_type in ("side", "bottom")), default=450)
        drawer_width = max((p.size_x for p in panels if p.panel_type in ("top", "bottom")), default=800)

        slide_matches = match_drawer_slides(drawer_depth, drawer_width)
        for slide in slide_matches:
            hw.append(HardwareRecord(
                name="抽屉滑轨",
                spec=f"{slide['brand']} {slide['model']} {slide['length_mm']}mm {slide['load_rating']}",
                quantity=slide["quantity"],
                unit="副",
                brand=slide["brand"],
                model=slide["model"],
                note=f"{slide['slide_type']} | {slide['mounting']}",
            ))

    # 门碰
    door_n = sum(1 for p in panels if p.panel_type == "door")
    if door_n:
        hw.append(HardwareRecord(name="弹压门碰", spec="推弹式", quantity=door_n, unit="个"))

    return hw


# ============================================================
# BOM 汇总
# ============================================================
def generate_bom_report(
    furniture_name: str,
    dimensions: str,
    panels: List[PanelRecord],
) -> BOMReport:
    """生成完整 BOM 报告。

    Args:
        furniture_name: 家具名称
        dimensions: 外形尺寸描述（如 "800×1000×600mm"）
        panels: 板件清单

    Returns:
        BOMReport 包含面板、五金、总面积
    """
    hardware = estimate_hardware(panels)
    total_area = sum(p.area_m2 for p in panels)

    return BOMReport(
        furniture_name=furniture_name,
        dimensions=dimensions,
        panels=panels,
        hardware=hardware,
        total_area_m2=total_area,
    )


# ============================================================
# Markdown 格式输出
# ============================================================
def format_bom_markdown(report: BOMReport) -> str:
    """将 BOMReport 格式化为 Markdown 字符串。"""
    lines = []
    lines.append(f"## 拆单报告 - {report.furniture_name}")
    lines.append("")
    lines.append(f"外形尺寸: **{report.dimensions}**")
    lines.append("")
    lines.append(f"### 板件清单 ({report.panel_count} 块)")
    lines.append("")
    lines.append(
        "| 序号 | 名称 | 类型 | 开料尺寸(mm) | 厚度 | 数量 | 封边 | 备注 |"
    )
    lines.append(
        "|------|------|------|-------------|------|------|------|------|"
    )
    for i, p in enumerate(report.panels, 1):
        eb = p.edge_banding_summary()
        lines.append(
            f"| {i} | {p.name} | {p.panel_type} | "
            f"{p.length_mm:.0f}×{p.width_mm:.0f} | "
            f"{p.thickness:.0f} | {p.quantity} | {eb} | {p.note} |"
        )
    lines.append("")
    lines.append(f"**总展开面积**: {report.total_area_m2:.4f} m²")

    if report.hardware:
        lines.append("")
        lines.append(f"### 五金清单 ({len(report.hardware)} 项)")
        lines.append("")
        lines.append("| 名称 | 规格 | 数量 | 单位 |")
        lines.append("|------|------|------|------|")
        for h in report.hardware:
            lines.append(f"| {h.name} | {h.spec} | {h.quantity} | {h.unit} |")

    return "\n".join(lines)


def print_bom(report: BOMReport) -> None:
    """打印 BOM 到终端"""
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  拆单报告 - {report.furniture_name}")
    print(f"  外形: {report.dimensions}")
    print(f"{sep}")

    print(f"\n【板件清单】{report.panel_count} 块")
    print("-" * 60)
    for i, p in enumerate(report.panels, 1):
        eb = p.edge_banding_summary()
        print(f"  [{i:2d}] {p.name} ×{p.quantity}")
        print(
            f"       材质:{p.material} 厚:{p.thickness}mm "
            f"开料:{p.length_mm:.0f}×{p.width_mm:.0f}mm"
        )
        print(f"       封边:{eb}")
        if p.note:
            print(f"       备注:{p.note}")

    print(f"\n  总展开面积: {report.total_area_m2:.4f} m²")

    if report.hardware:
        print(f"\n【五金清单】{len(report.hardware)} 项")
        print("-" * 60)
        for h in report.hardware:
            print(f"  · {h.name} {h.spec} ×{h.quantity}{h.unit}")

    print(f"\n{sep}\n")