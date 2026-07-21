"""生成带孔位标记和板件几何的 GLB 文件供 Viewer 预览。

读取钻孔数据 JSON 并导出半透明板件方块与按实际方向摆放的彩色孔位标记到单个 .glb。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import build123d as bd

# ── 板件类型 → 半透明颜色 ──────────────────────────────────────────
PANEL_TYPE_COLORS: dict[str, bd.Color] = {
    "side":      bd.Color(0.80, 0.70, 0.55, 0.30),   # 浅木色
    "top":       bd.Color(0.80, 0.70, 0.55, 0.30),
    "bottom":    bd.Color(0.80, 0.70, 0.55, 0.30),
    "fixed_shelf": bd.Color(0.82, 0.72, 0.58, 0.30),
    "back":      bd.Color(0.65, 0.60, 0.50, 0.25),     # 灰木色（背板薄）
    "back_rail": bd.Color(0.80, 0.70, 0.55, 0.30),
    "toe_kick":  bd.Color(0.60, 0.55, 0.45, 0.30),     # 踢脚暗色
    "door":      bd.Color(0.85, 0.78, 0.65, 0.50),     # 门板微亮
}
FALLBACK_PANEL_COLOR = bd.Color(0.75, 0.68, 0.55, 0.30)

# ── 打孔方向 → 将 +Z 转到该方向的 Rotation ───────────────────────────
_DIRECTION_ROT: dict[str, bd.RotationLike] = {
    "+x": (bd.Axis.Y, 90),
    "-x": (bd.Axis.Y, -90),
    "+y": (bd.Axis.X, 90),
    "-y": (bd.Axis.X, -90),
    "+z": None,      # 默认朝向，无需旋转
    "-z": (bd.Axis.X, 180),
}


def _panel_color(panel: dict[str, Any]) -> bd.Color:
    """根据板件类型返回对应半透明颜色。"""
    ptype = str(panel.get("panel_type", panel.get("name", ""))).lower()
    return PANEL_TYPE_COLORS.get(ptype, FALLBACK_PANEL_COLOR)


def export_drilled_holes_glb(
    drilled_holes: dict[str, Any],
    output_path: str | Path,
    *,
    marker_thickness: float = 2.0,
) -> Path:
    """导出板件方块 + 按方向摆放的孔位标记到单个 GLB。

    板件方块从每块板件的 ``box`` 字段（尺寸 + 位置）读取，以半透明有色
    方块呈现。孔位标记为薄圆柱体，旋转到与加工打孔方向一致。

    参数:
        drilled_holes: ``emit_drilled_holes()`` 返回的字典
        output_path: 目标 .glb 文件路径
        marker_thickness: 孔位标记圆柱的视觉厚度
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    geometry: list[bd.Solid] = []

    for panel in drilled_holes.get("panels", []):
        # ── 板件方块 ────────────────────────────────────────────
        box_info = panel.get("box", {})
        if box_info:
            sx = float(box_info.get("x", 0))
            sy = float(box_info.get("y", 0))
            sz = float(box_info.get("z", 0))
            px = float(box_info.get("pos_x", 0))
            py = float(box_info.get("pos_y", 0))
            pz = float(box_info.get("pos_z", 0))
            if sx > 0 and sy > 0 and sz > 0:
                # build123d.Box() 以原点为中心，需将中心移到
                # 板件中心 = 最小角 + 半边长。
                cx = px + sx / 2.0
                cy = py + sy / 2.0
                cz = pz + sz / 2.0
                box = bd.Box(sx, sy, sz)
                box.color = _panel_color(panel)
                box.label = panel.get("label", "panel")
                box.move(bd.Location((cx, cy, cz)))
                geometry.append(box)

        # ── 孔位标记 ─────────────────────────────────────────────
        for hole in panel.get("holes", []):
            diam = float(hole.get("diameter", 8))
            color_hex = hole.get("color", "#888888")
            direction = str(hole.get("direction", "+z"))
            x = float(hole.get("x", 0))
            y = float(hole.get("y", 0))
            z = float(hole.get("z", 0))

            radius = diam / 2.0
            cyl = bd.Cylinder(
                radius=radius,
                height=marker_thickness,
                align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER),
            )
            cyl.color = _hex_to_color(color_hex)
            cyl.label = hole.get("hole_type", "hole")

            # 将圆柱放到孔位中心，再旋转 Z 轴到打孔方向。
            # Location * Rotation 生成单一变换矩阵，
            # Compound → GLB 导出时不会丢失方向信息。
            rot = _DIRECTION_ROT.get(direction)
            transform = bd.Location((x, y, z))
            if rot is not None:
                transform = transform * bd.Rotation(*rot)
            cyl.move(transform)
            geometry.append(cyl)

    if not geometry:
        compound = bd.Compound()
    else:
        compound = bd.Compound(children=geometry)
        compound.label = "cabinet_with_holes"

    bd.export_gltf(compound, str(output_path), binary=True)
    return output_path


def load_drilled_holes_from_json(json_path: str | Path) -> dict[str, Any]:
    """从 JSON 文件加载钻孔数据。"""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _hex_to_color(hex_str: str) -> bd.Color:
    """将 '#RRGGBB' 十六进制颜色转为 build123d Color，alpha=0.9 用于叠加层。"""
    hex_str = hex_str.lstrip("#")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return bd.Color(r, g, b, 0.9)