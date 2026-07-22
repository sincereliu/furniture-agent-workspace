"""导出孔位预览的 GLB/STEP 文件。

STEP 文件用 Assembly 分组建模，支持在 Viewer 中独立开关板件和各类孔位。
GLB 文件为向后兼容保留，含板件+孔位的 Compound 合并体。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import build123d as bd

# ── 板件类型 → 颜色 ──────────────────────────────────────────────
PANEL_TYPE_COLORS: dict[str, bd.Color] = {
    "side":      bd.Color(0.80, 0.70, 0.55, 0.30),
    "top":       bd.Color(0.80, 0.70, 0.55, 0.30),
    "bottom":    bd.Color(0.80, 0.70, 0.55, 0.30),
    "fixed_shelf": bd.Color(0.82, 0.72, 0.58, 0.30),
    "back":      bd.Color(0.65, 0.60, 0.50, 0.25),
    "back_rail": bd.Color(0.80, 0.70, 0.55, 0.30),
    "toe_kick":  bd.Color(0.60, 0.55, 0.45, 0.30),
    "door":      bd.Color(0.85, 0.78, 0.65, 0.50),
}
FALLBACK_PANEL_COLOR = bd.Color(0.75, 0.68, 0.55, 0.30)

# ── 打孔方向 → Rotation ────────────────────────────────────────
_DIRECTION_ROT: dict[str, bd.RotationLike] = {
    "+x": (bd.Axis.Y, 90),
    "-x": (bd.Axis.Y, -90),
    "+y": (bd.Axis.X, 90),
    "-y": (bd.Axis.X, -90),
    "+z": None,
    "-z": (bd.Axis.X, 180),
}

# ── 孔位分类 → Assembly 子组名称 ──────────────────────────────
HOLE_GROUP_MAP = {
    "system_32_female":     "偏心轮孔",
    "system_32_male":       "连接杆孔",
    "system_32_pre_nut":    "预埋螺母孔",
    "hinge":                "铰链孔位",
    "back_rail_side_clearance": "背拉条孔位",
    "back_rail_pilot":      "背拉条孔位",
    "shelf_connector":      "层板孔位",
}


def _panel_color(panel: dict[str, Any]) -> bd.Color:
    ptype = str(panel.get("panel_type", panel.get("name", ""))).lower()
    return PANEL_TYPE_COLORS.get(ptype, FALLBACK_PANEL_COLOR)


def export_drilled_holes_glb(
    drilled_holes: dict[str, Any],
    output_path: str | Path,
    *,
    marker_thickness: float = 2.0,
) -> Path:
    """导出板件 + 孔位标记到单个 GLB（向后兼容）。"""
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    geometry = _build_geometry(drilled_holes, marker_thickness)
    if not geometry:
        compound = bd.Compound()
    else:
        compound = bd.Compound(children=geometry)
        compound.label = "cabinet_with_holes"
    bd.export_gltf(compound, str(output_path), binary=True)
    return output_path


# ── 板件 label 集合（用于区分板件 vs 孔位）─────────────────────
_PANEL_LABELS = frozenset({
    "left_side_panel", "right_side_panel", "top_panel",
    "bottom_panel", "back_panel", "back_rail_1", "back_rail_2",
    "toe_kick_back", "toe_kick_front", "toe_kick_support_1",
    "toe_kick_support_2", "shelf_z316", "left_door", "right_door",
})


def export_drilled_holes_step(
    drilled_holes: dict[str, Any],
    output_path: str | Path,
    *,
    marker_thickness: float = 2.0,
) -> Path:
    """导出嵌套 Compound 结构的 STEP 文件，支持 Viewer 按组 toggle。

    build123d 的 export_step 保留 Compound 层级和子 Solid 标签名。
    Viewer 将嵌套 Compound 按组显示，可独立隐藏/显示。
    """
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 先收集所有几何并按组归类
    group_solids: dict[str, list[bd.Solid]] = {}
    for solid in _build_geometry(drilled_holes, marker_thickness):
        label = solid.label
        if label in _PANEL_LABELS:
            group_solids.setdefault("板件", []).append(solid)
        else:
            group_name = HOLE_GROUP_MAP.get(label, "其他孔位")
            group_solids.setdefault(group_name, []).append(solid)

    # 每组建一个 Compound，包进根 Compound
    children: list[bd.Compound] = []
    for group_name, solids in group_solids.items():
        comp = bd.Compound(children=solids, label=group_name)
        children.append(comp)

    root = bd.Compound(children=children, label="cabinet_assembly")

    try:
        bd.export_step(root, str(output_path))
        # 生成 STEP 的 GLB 侧车文件供 Viewer 渲染装配树
        glb_sidecar = Path(str(output_path) + ".glb")
        bd.export_gltf(root, str(glb_sidecar), binary=True)
    except Exception:
        # 如果 STEP 导出失败（build123d 不支持嵌套 Compound 层级），
        # 保留 GLB 文件作为兜底
        bd.export_gltf(root, str(output_path.with_suffix(".glb")), binary=True)

    return output_path


def _build_geometry(
    drilled_holes: dict[str, Any],
    marker_thickness: float,
) -> list[bd.Solid]:
    """构建所有板件和孔位 solid 列表。"""
    geometry: list[bd.Solid] = []

    for panel in drilled_holes.get("panels", []):
        # ── 板件方块 ──────────────────────────────────────────
        box_info = panel.get("box", {})
        if box_info:
            sx = float(box_info.get("x", 0))
            sy = float(box_info.get("y", 0))
            sz = float(box_info.get("z", 0))
            px = float(box_info.get("pos_x", 0))
            py = float(box_info.get("pos_y", 0))
            pz = float(box_info.get("pos_z", 0))
            if sx > 0 and sy > 0 and sz > 0:
                cx = px + sx / 2.0
                cy = py + sy / 2.0
                cz = pz + sz / 2.0
                box = bd.Box(sx, sy, sz)
                box.color = _panel_color(panel)
                box.label = panel.get("label", "panel")
                box.move(bd.Location((cx, cy, cz)))
                geometry.append(box)

        # ── 孔位标记 ─────────────────────────────────────────
        for hole in panel.get("holes", []):
            diam = float(hole.get("diameter", 8))
            color_hex = hole.get("color", "#888888")
            direction = str(hole.get("direction", "+z"))
            hole_type = str(hole.get("hole_type", "hole"))
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
            cyl.label = hole_type

            rot = _DIRECTION_ROT.get(direction)
            transform = bd.Location((x, y, z))
            if rot is not None:
                transform = transform * bd.Rotation(*rot)
            cyl.move(transform)
            geometry.append(cyl)

    return geometry


def load_drilled_holes_from_json(json_path: str | Path) -> dict[str, Any]:
    """从 JSON 文件加载钻孔数据。"""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _hex_to_color(hex_str: str) -> bd.Color:
    """十六进制颜色 -> build123d Color（alpha=0.9）。"""
    hex_str = hex_str.lstrip("#")
    r = int(hex_str[0:2], 16) / 255.0
    g = int(hex_str[2:4], 16) / 255.0
    b = int(hex_str[4:6], 16) / 255.0
    return bd.Color(r, g, b, 0.9)