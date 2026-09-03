"""孔位校验器 — 深度校验 + 边界检测 + 空间干涉检测。"""

from __future__ import annotations

import math
import warnings as _warnings
from typing import List

import numpy as np

from furniture_manufacturing.connectors.base import HoleSpec
from furniture_manufacturing.manufacturing_models import PanelRecord


class HoleValidationError(Exception):
    """孔位校验失败。"""


# ── 深度校验 ──────────────────────────────────────────────────

def _panel_size_along(panel: PanelRecord, direction: str) -> float:
    """打孔方向上的板件尺寸。

    面钻孔沿板厚方向（如侧板 ±x → size_x 即板厚）；
    端面钻孔沿板内方向（如横板连接杆 ±x → size_x 即板宽）。
    """
    axis = direction[1] if len(direction) >= 2 else "z"
    return {
        "x": panel.size_x,
        "y": panel.size_y,
        "z": panel.size_z,
    }.get(axis, panel.thickness)


def validate_hole_depth(hole: HoleSpec, panel: PanelRecord) -> None:
    """检查孔深度 ≤ 打孔方向上的板件尺寸。

    深度与打孔方向的板件尺寸比较，而非一律与板厚比较：
    端面钻入的连接杆/预孔沿板内方向走，深度可大于板厚。
    连接杆孔超限时发出警告而非报错（杆将穿入相邻板预埋螺母）。
    """
    limit = _panel_size_along(panel, hole.direction)
    if hole.depth <= limit:
        return

    if "连接杆" in hole.note:
        _warnings.warn(
            f"[三合一] {panel.label} 连接杆孔深 {hole.depth}mm > "
            f"打孔方向尺寸 {limit}mm, 杆将穿入相邻板预埋螺母。"
        )
        return

    raise HoleValidationError(
        f"{panel.label} 孔深 {hole.depth}mm > 打孔方向尺寸 {limit}mm: "
        f"{hole.note} (类型={hole.hole_type}, 方向={hole.direction}, 局部="
        f"({hole.x_local:.1f},{hole.y_local:.1f},{hole.z_local:.1f}))"
    )


# ── 边界检测 ──────────────────────────────────────────────────

def validate_hole_bounds(hole: HoleSpec, panel: PanelRecord) -> None:
    """检查孔位在板件边界内（含孔半径 margin）。"""
    r = hole.diameter / 2.0
    x, y, z = hole.x_local, hole.y_local, hole.z_local
    sx, sy, sz = panel.size_x, panel.size_y, panel.size_z

    def _in_range(v: float, size: float, margin: float) -> bool:
        return -margin <= v <= size + margin

    if not (_in_range(x, sx, r) and _in_range(y, sy, r) and _in_range(z, sz, r)):
        raise HoleValidationError(
            f"{panel.label} {hole.note}: 孔中心({x:.1f},{y:.1f},{z:.1f}) "
            f"超出板件 [{sx:.1f}×{sy:.1f}×{sz:.1f}], 半径={r:.1f}"
        )


# ── 干涉检测 ──────────────────────────────────────────────────

def _hole_cylinders_collide(
    h1: HoleSpec, h2: HoleSpec, safety_gap: float = 3.0,
) -> bool:
    """检查同方向平行孔是否干涉（开口间距）。

    正交孔（如三合一连接杆孔与偏心轮孔）是设计上的配合关系，
    不做空间球包围判定，避免把正常配合误报为干涉。
    """
    if h1.direction != h2.direction:
        return False
    p1 = np.array([h1.x_local, h1.y_local, h1.z_local])
    p2 = np.array([h2.x_local, h2.y_local, h2.z_local])

    # 同方向: 投影到垂直平面检查 2D 中心距
    axis_map = {"x": (1, 2), "y": (0, 2), "z": (0, 1)}
    dir_axis = h1.direction[1]
    axes = axis_map.get(dir_axis, (0, 1))
    dist_2d = math.sqrt(
        (p1[axes[0]] - p2[axes[0]]) ** 2
        + (p1[axes[1]] - p2[axes[1]]) ** 2
    )
    min_dist = (h1.diameter + h2.diameter) / 2.0 + safety_gap
    return dist_2d < min_dist


def validate_holes_no_interference(
    holes: List[HoleSpec],
    panel: PanelRecord,
    safety_gap: float = 3.0,
) -> None:
    """检查同一板件上的孔位是否有空间干涉。"""
    n = len(holes)
    for i in range(n):
        for j in range(i + 1, n):
            h1, h2 = holes[i], holes[j]
            if _hole_cylinders_collide(h1, h2, safety_gap):
                raise HoleValidationError(
                    f"{panel.label} 孔位干涉: {h1.note}({h1.x_local:.1f},"
                    f"{h1.y_local:.1f},{h1.z_local:.1f}) ↔ "
                    f"{h2.note}({h2.x_local:.1f},{h2.y_local:.1f},{h2.z_local:.1f})"
                )


# ── 批量校验 ──────────────────────────────────────────────────

def validate_all_holes(
    holes: List[HoleSpec],
    panel: PanelRecord,
    safety_gap: float = 3.0,
) -> List[str]:
    """对单块板件的全部孔位执行所有校验, 返回警告列表。"""
    warns: List[str] = []
    for hole in holes:
        try:
            validate_hole_depth(hole, panel)
        except HoleValidationError as e:
            warns.append(str(e))
        try:
            validate_hole_bounds(hole, panel)
        except HoleValidationError as e:
            warns.append(str(e))
    try:
        validate_holes_no_interference(holes, panel, safety_gap)
    except HoleValidationError as e:
        warns.append(str(e))
    return warns

