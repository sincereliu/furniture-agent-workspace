"""导出孔位预览的 GLB/STEP 文件。

STEP 文件用 Assembly 分组建模，支持在 Viewer 中独立开关板件和各类孔位。
GLB 文件为向后兼容保留，含板件+孔位的 Compound 合并体。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import build123d as bd

from .connectors import ALL_CONNECTORS

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

# ── 孔位分类 → Assembly 子组名称（由各 Connector 的 glb_group 派生）──
def _build_hole_group_map() -> dict[str, str]:
    group_map: dict[str, str] = {}
    for connector_cls in ALL_CONNECTORS:
        for hole_type, meta in connector_cls.hole_legend.items():
            group_map[hole_type] = meta.get("glb_group", "其他孔位")
    return group_map


HOLE_GROUP_MAP = _build_hole_group_map()


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

    group_solids = _build_grouped_geometry(drilled_holes, marker_thickness)

    # 每组建一个 Compound，包进根 Compound
    children: list[bd.Compound] = []
    for group_name, solids in group_solids.items():
        comp = bd.Compound(children=solids, label=group_name)
        children.append(comp)

    root = bd.Compound(children=children, label="cabinet_assembly")

    try:
        bd.export_step(root, str(output_path))
        glb_sidecar = Path(str(output_path) + ".glb")
        bd.export_gltf(root, str(glb_sidecar), binary=True)
    except Exception as exc:
        raise RuntimeError(
            f"unable to export drilled-hole STEP assembly: {output_path}"
        ) from exc

    for artifact in (output_path, glb_sidecar):
        if not artifact.is_file() or artifact.stat().st_size == 0:
            raise RuntimeError(f"drilled-hole artifact is missing or empty: {artifact}")

    return output_path


def _panel_solid(panel: dict[str, Any]) -> bd.Solid | None:
    """Build one panel solid, independent of its dynamic label."""
    box_info = panel.get("box", {})
    if not box_info:
        return None
    sx = float(box_info.get("x", 0))
    sy = float(box_info.get("y", 0))
    sz = float(box_info.get("z", 0))
    if min(sx, sy, sz) <= 0:
        return None
    px = float(box_info.get("pos_x", 0))
    py = float(box_info.get("pos_y", 0))
    pz = float(box_info.get("pos_z", 0))
    box = bd.Box(sx, sy, sz)
    box.color = _panel_color(panel)
    box.label = str(panel.get("label", "panel"))
    box.move(
        bd.Location(
            (
                px + sx / 2.0,
                py + sy / 2.0,
                pz + sz / 2.0,
            )
        )
    )
    return box


def _hole_solids(
    panel: dict[str, Any],
    marker_thickness: float,
) -> list[bd.Solid]:
    """Build the visual solids for every hole on one panel."""
    solids: list[bd.Solid] = []
    for hole in panel.get("holes", []):
        diam = float(hole.get("diameter", 8))
        color_hex = hole.get("color", "#888888")
        direction = str(hole.get("direction", "+z"))
        hole_type = str(hole.get("hole_type", "hole"))
        x = float(hole.get("x", 0))
        y = float(hole.get("y", 0))
        z = float(hole.get("z", 0))

        cyl = bd.Cylinder(
            radius=diam / 2.0,
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
        solids.append(cyl)
    return solids


def _build_grouped_geometry(
    drilled_holes: dict[str, Any],
    marker_thickness: float,
) -> dict[str, list[bd.Solid]]:
    """Group panels by source role and holes by machining type."""
    groups: dict[str, list[bd.Solid]] = {}
    for panel in drilled_holes.get("panels", []):
        panel_solid = _panel_solid(panel)
        if panel_solid is not None:
            groups.setdefault("板件", []).append(panel_solid)
        for solid in _hole_solids(panel, marker_thickness):
            groups.setdefault(
                HOLE_GROUP_MAP.get(solid.label, "其他孔位"),
                [],
            ).append(solid)
    return groups


def _build_geometry(
    drilled_holes: dict[str, Any],
    marker_thickness: float,
) -> list[bd.Solid]:
    """构建所有板件和孔位 solid 列表。"""
    geometry: list[bd.Solid] = []

    for panel in drilled_holes.get("panels", []):
        panel_solid = _panel_solid(panel)
        if panel_solid is not None:
            geometry.append(panel_solid)
        geometry.extend(_hole_solids(panel, marker_thickness))

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
