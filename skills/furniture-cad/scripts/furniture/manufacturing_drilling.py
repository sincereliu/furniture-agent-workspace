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
        rules_path = Path(__file__).resolve().parent / "hardware_rules.yaml"
        with open(rules_path, "r", encoding="utf-8") as f:
            _RULES = yaml.safe_load(f) or {}
    return _RULES


# ── 铰链孔位计算 ─────────────────────────────────────────────
def calc_hinge_positions(
    door_height_mm: float,
    door_width_mm: float,
    variant_group: str | None = None,
    *,
    system_holes: List[float] | None = None,
    shelf_positions: List[float] | None = None,
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

    # 4. 应用避让规则
    y_positions = apply_hinge_conflict_avoidance(
        y_positions, rules, door_height_mm,
        system_holes=system_holes, shelf_positions=shelf_positions, snap=snap,
    )

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


# ── 三合一系统排钻孔位 ──────────────────────────────────────
def calc_system_32_holes(
    board_length: float,
    board_type: str | None = None,
) -> List[float]:
    """32mm 系统排钻孔位计算，使用 hardware_rules.yaml 的 system_32_drilling 规则。

    Args:
        board_length: 板的打孔方向长度（侧板=高度，顶底板/层板=宽度）
        board_type: 板件类型，用于确定适用的打孔参数

    Returns:
        孔位列表（距板件打孔方向起点的距离，沿板面深度方向排列）
    """
    rules = _load_rules().get("system_32_drilling", {})
    first = float(rules.get("first_hole_mm", 64))
    last = float(rules.get("last_hole_mm", 64))
    max_spacing = float(rules.get("max_spacing_mm", 512))
    min_spacing = float(rules.get("min_spacing_mm", 32))
    snap = float(rules.get("snap_to_mm", 0.5))

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
        if h - merged[-1] >= min_spacing:
            merged.append(h)

    # 按 snap_to_mm 取整
    if snap > 0:
        merged = [round(h / snap) * snap for h in merged]

    return merged


# ── 活动层板托孔位 ────────────────────────────────────────
def calc_shelf_holes(board_length: float) -> List[float]:
    """活动层板托孔位计算"""
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


# ── 旧接口（兼容） ──────────────────────────────────────────
def calc_system_holes(
    board_length: float,
    first: float = 64.0,
    last: float = 64.0,
    max_spacing: float = 512.0,
) -> List[float]:
    """32mm 系统排钻孔位计算（旧接口，内部委托给 calc_system_32_holes）。"""
    return calc_system_32_holes(board_length)


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


# ── 铰链避让引擎 ──────────────────────────────────────────
def apply_hinge_conflict_avoidance(
    y_positions: List[float],
    rules: Dict[str, Any],
    door_height_mm: float,
    *,
    system_holes: List[float] | None = None,
    shelf_positions: List[float] | None = None,
    snap: float = 0.5,
) -> List[float]:
    """对铰链孔位应用避让规则。

    当铰链孔位与系统排钻孔/层板位置冲突时，在允许范围内微调。
    优先级: 1) 层板位置 2) 系统排钻孔

    Args:
        y_positions: 原始计算孔位（已按 top/bottom offset 分布）
        rules: hinge_drilling 规则字典
        door_height_mm: 门板高度
        system_holes: 侧板系统排钻孔位列表（全局坐标），None 则跳过
        shelf_positions: 层板高度位置列表（全局坐标 mm），None 则跳过
        snap: 取整精度

    Returns:
        微调后的孔位列表（与输入长度相同）
    """
    avoidance = rules.get("conflict_avoidance", {})
    if not avoidance:
        return y_positions

    min_system = float(avoidance.get("min_spacing_to_system_holes_mm", 50))
    min_shelf = float(avoidance.get("min_spacing_to_shelf_mm", 80))
    max_shift = float(avoidance.get("adjustment_max_shift_mm", 30))
    priority: List[str] = avoidance.get("priority", ["shelf", "system_holes"])

    adjusted = list(y_positions)

    for idx, y in enumerate(adjusted):
        # 按优先级依次检查
        for conflict_type in priority:
            conflict_zones: List[tuple[float, float]] = []

            if conflict_type == "shelf" and shelf_positions:
                conflict_zones = [
                    (sz - min_shelf, sz + min_shelf) for sz in shelf_positions
                ]
            elif conflict_type == "system_holes" and system_holes:
                conflict_zones = [
                    (sh - min_system, sh + min_system) for sh in system_holes
                ]

            # 检查是否在冲突区域内
            in_conflict = False
            for low, high in conflict_zones:
                if low <= y <= high:
                    in_conflict = True
                    break

            if not in_conflict:
                continue

            # 尝试微调：向上、向下均可，优先远离冲突区
            shift_up = y + max_shift
            shift_down = y - max_shift

            # 确保不超出门板范围
            top_limit = rules.get("count_by_door_height", [{}])[0].get("top_offset_mm", 100)
            bottom_limit = door_height_mm - rules.get("count_by_door_height", [{}])[0].get("bottom_offset_mm", 100)
            shift_up = min(shift_up, door_height_mm - bottom_limit)
            shift_down = max(shift_down, top_limit)

            # 检查哪个方向可行（不在任何冲突区）
            candidates = []
            for candidate_y in (shift_down, shift_up):
                still_conflict = False
                for low, high in conflict_zones:
                    if low <= candidate_y <= high:
                        still_conflict = True
                        break
                if not still_conflict and snap > 0:
                    candidate_y = round(candidate_y / snap) * snap
                if not still_conflict:
                    candidates.append(candidate_y)

            if candidates:
                # 选最近的一个
                adjusted[idx] = min(candidates, key=lambda c: abs(c - y))
            # 无可避开位置：保持原位

    return adjusted
