"""统一打孔引擎 — 根据规则和板件参数计算精确孔位坐标

职责:
  ✅ 输入: 板件参数 + 规则组标识
  ✅ 输出: List[Dict] 每个孔位的 (x, y, z, diameter, depth)
  ❌ 不关心硬件品牌/型号（那是 matcher 的职责）
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml


# ── 加载打孔规则 ──────────────────────────────────────────────
_RULES: Dict[str, Any] | None = None


def _load_rules() -> Dict[str, Any]:
    global _RULES
    if _RULES is None:
        rules_path = Path(__file__).resolve().parent / "hardware" / "rules.yaml"
        with open(rules_path, "r", encoding="utf-8") as f:
            _RULES = yaml.safe_load(f) or {}
    return _RULES


# ── 铰链孔位计算 ─────────────────────────────────────────────
def calc_hinge_positions(
    door_height_mm: float,
    door_width_mm: float,
    variant_group: str | None = None,
) -> List[Dict[str, Any]]:
    """计算门板上铰链杯孔的精确位置。

    Args:
        door_height_mm: 门板高度
        door_width_mm: 门板宽度
        variant_group: 规格组名（如"国内35mm杯全盖"），用于确定杯孔直径/深度/钻孔距离

    Returns:
        [{y: 100.0, x_offset: 5.0, cup_dia: 35, cup_depth: 11.5, bore_distance: 3}, ...]
        y: 孔位距门顶边的距离（沿门高方向）
        x_offset: 孔中心距门铰链侧边缘的距离
    """
    rules = _load_rules().get("hinge_drilling", {})

    # 1. 按门高分档取 count + 偏移值
    count, top_offset, bottom_offset = _hinge_count_with_offsets(door_height_mm, rules)
    # 2. 计算均匀分布位置
    y_positions = _distribute_positions(
        door_height_mm,
        count,
        top_offset=top_offset,
        bottom_offset=bottom_offset,
    )

    # 3. 确定杯孔参数
    edge_offset = rules.get("position", {}).get("edge_offset_mm", 5)
    cup_params = _cup_params_for_group(variant_group, rules)

    snap = rules.get("position", {}).get("snap_to_mm", 0.5)
    holes = []
    for y in y_positions:
        snapped = round(y / snap) * snap if snap > 0 else y
        holes.append({
            "y_mm": snapped,  # 距门顶边（按 snap_to_mm 取整）
            "x_offset_mm": edge_offset,  # 距铰链侧边缘
            "cup_diameter_mm": cup_params["cup_diameter_mm"],
            "cup_depth_mm": cup_params["cup_depth_mm"],
            "bore_distance_mm": cup_params["bore_distance_mm"],
            "side": "hinge_side",  # 铰链臂侧（左右门镜像时需翻转）
        })

    return holes


# ── 系统排钻孔位 ─────────────────────────────────────────────
def calc_system_holes(
    board_length: float,
    first: float = 64.0,
    last: float = 64.0,
    max_spacing: float = 512.0,
) -> List[float]:
    """32mm 系统排钻孔位计算（从 bom.py 原样保留，Phase 2b 升级时统一入口）。

    Returns:
        孔位列表（距板件边的距离）
    """
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


# ── 内部辅助 ─────────────────────────────────────────────────
def _hinge_count_with_offsets(
    door_height_mm: float, rules: Dict[str, Any],
) -> tuple[int, float, float]:
    """按门高分档返回 (count, top_offset, bottom_offset)。"""
    count_rules = rules.get("count_by_door_height", [])
    for entry in count_rules:
        if door_height_mm <= entry["max_height_mm"]:
            return (
                entry.get("count", 2),
                entry.get("top_offset_mm", 100),
                entry.get("bottom_offset_mm", 100),
            )
    # 兜底
    return 2, 100, 100


def _distribute_positions(
    total_length: float, count: int, top_offset: float, bottom_offset: float,
) -> List[float]:
    """在 [top_offset, total_length - bottom_offset] 内均匀分布 count 个点"""
    if count <= 0:
        return []
    if count == 1:
        return [total_length / 2]

    usable = total_length - top_offset - bottom_offset
    spacing = usable / (count - 1)
    return [top_offset + i * spacing for i in range(count)]


def _cup_params_for_group(
    variant_group: str | None, rules: Dict[str, Any],
) -> Dict[str, Any]:
    default = {"cup_diameter_mm": 35, "cup_depth_mm": 13, "bore_distance_mm": 3}
    if not variant_group:
        return default

    cup_map = rules.get("cup_by_variant_group", {})
    return cup_map.get(variant_group, default)