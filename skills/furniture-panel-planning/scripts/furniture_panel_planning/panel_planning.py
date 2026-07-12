"""拆单器 — 将 PanelPlacement 列表转为 PanelRecord 列表，附加材质、封边信息。

职责边界:
  ✅ 输入: List[PanelPlacement]（来自 Planner）
  ✅ 输出: List[PanelRecord]（附加了材质、封边、开料尺寸等生产信息）
  ❌ 不创建 build123d Solid
  ❌ 不生成输出文件（那是 BOM 模块的职责）
"""

from __future__ import annotations

from typing import Dict, List

from .manufacturing_edge_banding import get_edge_banding
from .panel_models import PanelPlacement, PanelRecord

# 默认材料配置（与外部 generator.py 的 DEFAULT_MATERIALS 一致）
DEFAULT_MATERIALS: Dict[str, Dict[str, str | float]] = {
    "carcass": {"name": "18mm免漆板", "thickness": 18.0, "color": "深灰"},
    "back":    {"name": "9mm薄板",    "thickness": 9.0,  "color": "深灰"},
    "door":    {"name": "18mm颗粒板(纯白)", "thickness": 18.0, "color": "纯白"},
}

# 板件类型 → 材料角色映射
PANEL_TYPE_TO_MATERIAL: Dict[str, str] = {
    "side":         "carcass",
    "top":          "carcass",
    "bottom":       "carcass",
    "fixed_shelf":  "carcass",
    "movable_shelf":"carcass",
    "divider":      "carcass",
    "toe_kick":     "carcass",
    "back":         "back",
    "door":         "door",
}


def _get_material(panel_type: str) -> tuple[str, float]:
    """根据板件类型获取材质名和厚度。

    Returns:
        (material_name, thickness_mm)
    """
    role = PANEL_TYPE_TO_MATERIAL.get(panel_type, "carcass")
    mat = DEFAULT_MATERIALS.get(role, DEFAULT_MATERIALS["carcass"])
    return str(mat["name"]), float(mat["thickness"])


def _get_drill_length(placement: PanelPlacement) -> float:
    """计算系统孔计算长度。

    侧板、中立板 = 高度；顶板/底板/层板 = 宽度；门板 = 高度；背板/踢脚 = 0
    """
    pt = placement.panel_type
    if pt in ("side", "divider"):
        return placement.size_z
    if pt in ("top", "bottom", "fixed_shelf", "movable_shelf"):
        return placement.size_x
    if pt == "door":
        return placement.size_z
    return 0.0


def panelize(
    placements: List[PanelPlacement],
    edge_rules: Dict[str, Dict[str, str]] | None = None,
) -> List[PanelRecord]:
    """将规划结果转为带生产信息的 PanelRecord 列表。

    Args:
        placements: Planner 输出的 PanelPlacement 列表
        edge_rules: 封边规则字典，None 则使用默认规则

    Returns:
        List[PanelRecord]: 含完整生产数据的板件清单（不含 Solid）
    """
    records: List[PanelRecord] = []
    for placement in placements:
        material_name, thickness = _get_material(placement.panel_type)
        edge_banding = get_edge_banding(placement.panel_type, edge_rules)
        drill_length = _get_drill_length(placement)

        record = PanelRecord(
            label=placement.id,
            name=placement.name,
            panel_type=placement.panel_type,
            material=material_name,
            thickness=thickness,
            length_mm=placement.size_x,
            width_mm=placement.size_y,
            size_x=placement.size_x,
            size_y=placement.size_y,
            size_z=placement.size_z,
            pos_x=placement.pos_x,
            pos_y=placement.pos_y,
            pos_z=placement.pos_z,
            drill_length=drill_length,
            edge_banding=edge_banding,
            note=placement.note,
        )
        records.append(record)

    return records


def plan_panels(placements: List[PanelPlacement]) -> List[PanelRecord]:
    """Stage 3 entry: convert layout placements into panel records."""
    return panelize(placements)
