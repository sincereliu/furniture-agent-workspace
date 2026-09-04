"""Topology solver — convert cabinet topology data into panel placements.

Reads a cabinet topology YAML and a FurnitureSpec, then computes every panel's
3-D placement with correct semantic face directions (inner/outer/cam).

The cabinet-type topology skeleton lives in the YAML files under
references/cabinet-topologies/. Deterministic execution rules that are shared
across supported topologies, such as admitted door labeling and the current
full-height drawer dimension chain, remain in code rather than being inferred
from natural language or hidden profiles.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .cabinet_frame import CabinetFrame, _negate as negate_axis
from .joint_topology import compute_joints
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec, resolve_shelf_gaps
from .panel_rules import (
    back_rail_clear_spacing,
    resolve_back_rail_count,
    resolve_door_hinge_side,
    resolve_toe_kick_support_count,
    toe_kick_support_clear_spacing,
)
from .structure_planning import CabinetStructure


def _load_topology(furniture_type: str) -> dict[str, Any]:
    """Load a topology YAML file for the given furniture type."""
    topo_dir = (
        Path(__file__).resolve().parents[2]
        / "references"
        / "cabinet-topologies"
    )
    path = topo_dir / f"{furniture_type}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"No topology defined for furniture_type='{furniture_type}'. "
            f"Expected: {path}"
        )
    with open(path, encoding="utf-8") as fp:
        return yaml.safe_load(fp) or {}


def _resolve_semantic_face(face_name: str, frame: CabinetFrame) -> str:
    """Map a semantic face name to a signed world axis.

    face_name is one of: front, back, top, bottom, left, right
    """
    return getattr(frame, face_name)


def solve_panel_placements(
    spec: FurnitureSpec,
    layout: CabinetStructure,
) -> list[PanelPlacement]:
    """Compute all panel placements from topology + spec + layout.

    Parameters
    ----------
    spec : FurnitureSpec
        Normalized cabinet dimensions and parameter choices.
    layout : CabinetStructure
        Panel-stage construction geometry and exact clear regions.

    Returns
    -------
    list[PanelPlacement]
        Every physical panel with size, position, and face semantics.
    """
    topology = _load_topology(spec.furniture_type)
    frame = CabinetFrame(**topology["frame"])

    placements: list[PanelPlacement] = []

    # ── Enclosure panels ──────────────────────────────────────────
    enclosure = topology.get("enclosure", {})
    board = spec.board_thickness

    for side_name, side_def in enclosure.items():
        sf_value = side_def.get("semantic_face", "")
        face_dir = _resolve_semantic_face(sf_value, frame)

        if side_def.get("type") == "opening":
            # Opening — generate door panels (managed separately below)
            continue

        if side_def.get("type") == "back_panel":
            placements.extend(_back_panel_variants(spec, layout, side_name, side_def, face_dir, frame))
            continue

        # Standard enclosure panel
        panel = _build_enclosure_panel(spec, layout, side_name, side_def, face_dir)
        placements.append(panel)

    # ── Doors ─────────────────────────────────────────────────────
    # 整高抽屉区下前开口被抽屉占满，不生成门
    front_side = enclosure.get("front", {})
    if front_side.get("type") == "opening" and spec.drawer_count <= 0:
        for subtype in front_side.get("subtypes", []):
            if subtype == "doors":
                placements.extend(_door_panels(spec, layout, frame))

    # ── Base (toe kick) ───────────────────────────────────────────
    base_def = topology.get("base", {})
    if base_def.get("type") == "toe_kick" and layout.toe_kick_height > 0:
        placements.extend(_toe_kick_panels(spec, layout, base_def, frame))

    # ── Internal shelves / drawers ────────────────────────────────
    internals = topology.get("internals", {})
    if spec.drawer_count > 0:
        # 整高抽屉区：抽屉占满内部净高，不生成固定层板
        drawers_def = internals.get("drawers", {})
        if drawers_def.get("type") == "full_height":
            placements.extend(_drawer_panels(spec, layout, drawers_def, frame))
    else:
        if spec.shelves:
            placements.extend(_shelves_from_spec(spec, layout, frame))

    # ── Connection topology ──────────────────────────────────────
    joints = compute_joints(placements)
    for panel in placements:
        panel.joints = [
            j for j in joints
            if j.female_id == panel.id or j.male_id == panel.id
        ]

    return placements


# ═══════════════════════════════════════════════════════════════════
# Panel builders
# ═══════════════════════════════════════════════════════════════════

def _build_enclosure_panel(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    side_name: str,
    side_def: dict[str, Any],
    face_dir: str,
) -> PanelPlacement:
    """Build a single enclosure panel."""
    board = spec.board_thickness
    axis = frame_axis(face_dir)  # x, y, or z
    sign = frame_sign(face_dir)  # +1 or -1

    # Compute panel size and position based on which enclosure face this is
    if axis == "x":
        # Side panel (left or right) — broad face is Y-Z plane
        if sign > 0:
            # Right face: panel sits at x=width-board
            px = layout.width - board
            inner = "-x"    # inner face points left (toward cabinet center)
        else:
            # Left face: panel sits at x=0
            px = 0.0
            inner = "+x"    # inner face points right
        sx, sy, sz = board, layout.side_depth, layout.height
        py = layout.carcass_y_start
        pz = 0.0
        name_map = {"left_side": "左侧板", "right_side": "右侧板"}
        ptype = "side"

    elif axis == "z":
        # Horizontal panel (top or bottom) — broad face is X-Y plane
        sx = layout.internal_width
        sy = layout.side_depth
        sz = board
        px = layout.internal_x_start
        py = layout.carcass_y_start
        if sign > 0:
            pz = layout.height - board  # top
            inner = "-z"
        else:
            pz = layout.toe_kick_height  # bottom
            inner = "+z"
        name_map = {"top": "顶板", "bottom": "底板"}
        ptype = "top" if sign > 0 else "bottom"

    else:
        raise ValueError(
            f"enclosure panel '{side_name}' has unsupported face axis "
            f"'{face_dir}'; back and front openings use dedicated builders"
        )

    name = name_map.get(side_name, side_name)
    outer = face_dir
    cam = side_def.get("cam_face")
    if cam:
        cam = _resolve_semantic_face(cam, _frame_from_spec(spec))

    return PanelPlacement(
        id=f"{side_name}_panel",
        name=name,
        panel_type=ptype,
        size_x=sx, size_y=sy, size_z=sz,
        pos_x=px, pos_y=py, pos_z=pz,
        material_role="carcass",
        inner_face=inner,
        outer_face=outer,
        cam_face=cam,
        note=f"{name}，厚{board:.0f}mm",
    )


def _back_panel_variants(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    side_name: str,
    side_def: dict[str, Any],
    face_dir: str,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate back panel and optional back rails for the selected mount mode."""
    board = spec.board_thickness
    back_mount = layout.back_mount
    back_y = layout.back_plane_y
    # 背板: 外表面=柜体背面, 内表面指向柜内=柜体前面
    outer = face_dir          # frame.back
    inner = negate_axis(outer)  # frame.front

    result: list[PanelPlacement] = []

    if back_mount == "groove":
        groove_d = spec.groove_depth
        bw = layout.internal_width + 2 * groove_d
        bh = layout.internal_height + 2 * groove_d
        result.append(PanelPlacement(
            id="back_panel", name="背板", panel_type="back",
            size_x=bw, size_y=spec.back_thickness, size_z=bh,
            pos_x=layout.internal_x_start - groove_d,
            pos_y=back_y,
            pos_z=layout.internal_z_start - groove_d,
            material_role="back",
            depends_on=["left_side_panel", "right_side_panel", "top_panel", "bottom_panel"],
            inner_face=inner, outer_face=outer, cam_face=None,
            note=f"四边入槽{groove_d:.0f}mm的成品背板",
        ))
        # back rails
        rail_h = spec.back_rail_height
        rail_count = resolve_back_rail_count(
            back_mount,
            layout.internal_height,
            rail_h,
        )
        if rail_h > 0 and rail_count > 0:
            step = back_rail_clear_spacing(
                layout.internal_height,
                rail_count,
                rail_h,
            )
            for i in range(rail_count):
                rz = layout.internal_z_start + step + i * (rail_h + step)
                result.append(PanelPlacement(
                    id=f"back_rail_{i + 1}", name=f"背拉条{i + 1}",
                    panel_type="back_rail",
                    size_x=layout.internal_width, size_y=board, size_z=rail_h,
                    pos_x=layout.internal_x_start, pos_y=layout.carcass_y_start, pos_z=rz,
                    material_role="carcass",
                    depends_on=["left_side_panel", "right_side_panel"],
                    inner_face="+y", outer_face="-y", cam_face=None,
                    note=f"背板拉条，{rail_h:.0f}×{board:.0f}mm",
                ))

    elif back_mount == "insert":
        result.append(PanelPlacement(
            id="back_panel", name="背板", panel_type="back",
            size_x=layout.internal_width, size_y=spec.back_thickness, size_z=layout.internal_height,
            pos_x=layout.internal_x_start, pos_y=back_y, pos_z=layout.internal_z_start,
            material_role="back",
            depends_on=["left_side_panel", "right_side_panel", "top_panel", "bottom_panel"],
            inner_face=inner, outer_face=outer, cam_face=None,
            note="内嵌背板，三合一连接",
        ))

    else:  # cover
        result.append(PanelPlacement(
            id="back_panel", name="背板", panel_type="back",
            size_x=layout.width, size_y=spec.back_thickness, size_z=layout.height,
            pos_x=0.0, pos_y=0.0, pos_z=0.0,
            material_role="back",
            depends_on=["left_side_panel", "right_side_panel", "top_panel", "bottom_panel"],
            inner_face=inner, outer_face=outer, cam_face=None,
            note="外盖背板，覆盖整个背面",
        ))

    return result


def _door_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate door panels on the front face of the cabinet."""
    count = layout.door_count
    if count <= 0:
        return []

    margin = spec.front_face_margin
    dw = (layout.width - margin * 2 * count) / count
    dh = layout.height - layout.toe_kick_height - margin * 2
    dy = layout.carcass_y_end + spec.door_hinge_gap

    # Door inner face points into the cabinet (= opposite of front)
    inner = frame.back   # back of cabinet = door inner face
    outer = frame.front  # front of cabinet = door outer face

    panels: list[PanelPlacement] = []
    for index in range(count):
        if count == 1:
            pid, pname = "single_door", "门板"
            x = layout.width / 2 - dw / 2
        elif count == 2:
            pid = "left_door" if index == 0 else "right_door"
            pname = "左门板" if index == 0 else "右门板"
            x = margin if index == 0 else layout.width - margin - dw
        else:
            pid = f"door_{index + 1}_door"
            pname = f"门板{index + 1}"
            x = margin * (2 * (index + 1) - 1) + dw * index
        hinge_side = resolve_door_hinge_side(
            count,
            index,
            spec.door_hinge_side,
        )

        panels.append(PanelPlacement(
            id=pid, name=pname, panel_type="door",
            size_x=dw, size_y=spec.door_thickness, size_z=dh,
            pos_x=x, pos_y=dy, pos_z=layout.toe_kick_height + margin,
            material_role="door",
            depends_on=["left_side_panel", "right_side_panel"],
            door_hinge_side=hinge_side,
            inner_face=inner, outer_face=outer, cam_face=None,
            note=f"门板，{dw:.0f}×{dh:.0f}×{spec.door_thickness:.0f}mm",
        ))
    return panels


def _toe_kick_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    base_def: dict[str, Any],
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate toe kick panels (front and rear kickboards + optional supports)."""
    board = spec.board_thickness
    kw = layout.internal_width
    x = layout.internal_x_start

    # Toe kick panels — outer faces outward, inner faces toward cabinet interior
    rear = PanelPlacement(
        id="toe_kick_back", name="后踢脚板", panel_type="toe_kick",
        size_x=kw, size_y=board, size_z=layout.toe_kick_height,
        pos_x=x, pos_y=layout.toe_kick_rear_y,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
        inner_face=frame.front, outer_face=frame.back, cam_face=None,
    )
    front = PanelPlacement(
        id="toe_kick_front", name="前踢脚板", panel_type="toe_kick",
        size_x=kw, size_y=board, size_z=layout.toe_kick_height,
        pos_x=x, pos_y=layout.toe_kick_front_y - board,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
        inner_face=frame.back, outer_face=frame.front, cam_face=None,
    )
    panels = [rear, front]

    count = resolve_toe_kick_support_count(spec.toe_kick_support_count, layout.width)
    if count == 0:
        return panels

    sy = layout.toe_kick_rear_y + board
    sd = layout.toe_kick_front_y - board - sy
    gap = toe_kick_support_clear_spacing(kw, count, board)
    for i in range(count):
        panels.append(PanelPlacement(
            id=f"toe_kick_support_{i + 1}", name=f"踢脚支撑{i + 1}",
            panel_type="toe_kick",
            size_x=board, size_y=sd, size_z=layout.toe_kick_height,
            pos_x=x + gap + i * (board + gap), pos_y=sy,
            material_role="carcass",
            depends_on=["toe_kick_back", "toe_kick_front"],
            inner_face="", outer_face="", cam_face=None,  # small support, no meaningful face
        ))
    return panels


def _shelves_from_spec(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """按 spec.shelves（从上到下）生成固定/活动层板；解析 auto 净高。"""
    gaps = resolve_shelf_gaps(spec, layout.internal_height)
    board = spec.board_thickness
    sd = layout.internal_y_end - layout.internal_y_start
    inner = frame.bottom
    outer = frame.top
    panels: list[PanelPlacement] = []
    top_z = layout.internal_z_end - spec.top_gap_mm  # 最上层板顶面
    for shelf, gap in zip(spec.shelves, gaps):
        bottom_z = top_z - board          # 这块板底面
        cz = bottom_z + board / 2         # 这块板中心
        if shelf.shelf_type == "fixed":
            panel_type = "fixed_shelf"
            cam = frame.bottom
            name = f"层板({cz:.0f}mm)"
            note = "固定层板"
            panel_id = f"shelf_z{cz:.0f}"
        else:
            panel_type = "movable_shelf"
            cam = None
            name = f"活动层板({cz:.0f}mm)"
            note = "活动层板"
            panel_id = f"movable_shelf_z{cz:.0f}"
        panels.append(PanelPlacement(
            id=panel_id, name=name, panel_type=panel_type,
            size_x=layout.internal_width, size_y=sd, size_z=board,
            pos_x=layout.internal_x_start, pos_y=layout.internal_y_start,
            pos_z=bottom_z,
            material_role="carcass",
            depends_on=["left_side_panel", "right_side_panel"],
            inner_face=inner, outer_face=outer, cam_face=cam,
            note=note,
        ))
        top_z = bottom_z - gap           # 下一层板顶面
    return panels


def _drawer_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    drawers_def: dict[str, Any],
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate full-height drawer box panels（首版：无面板，前板即前脸）。

    尺寸链口径见 references/drawer-dimension-chain.md：
    - 每层净高 band_h = 内部净高 ÷ drawer_count
    - 前板：高 = band_h − layer_gap；宽 = 内部宽 − 2×front_face_margin；厚 = 板厚
    - 盒体宽 = 内部宽 − 2×已准入的抽屉每侧净空
    - 盒体深 = 内部深 − 前板厚 − back_clearance(≥0)
    - 盒体高 = 前板高 − 2×front_overlap（底抽 18 全盖底板，顶/中 0）
    板件 label 以 z 位置后缀结尾（drawer_*_z{pos}），与 DrawerSlideConnector
    实例 key 契约一致。
    """
    count = spec.drawer_count
    if count <= 0:
        return []
    board = spec.board_thickness
    slide_gap = spec.drawer_side_clearance
    layer_gap = spec.drawer_layer_gap
    bottom_t = spec.drawer_bottom_thickness
    back_t = spec.drawer_back_thickness
    back_clear = spec.drawer_back_clearance

    iw = layout.internal_width
    internal_depth = layout.internal_y_end - layout.internal_y_start
    band_h = layout.internal_height / count
    front_h = band_h - layer_gap
    front_w = iw - 2 * spec.front_face_margin
    box_w = iw - 2 * slide_gap
    box_d = internal_depth - board - back_clear
    box_back_y = layout.internal_y_start + back_clear

    # 底板 x/y 端面分别顶住侧板内面/前后面（三合一连接）；底板 y 向延伸到前板
    bottom_size_y = box_d - board
    if min(front_h, front_w, box_w, box_d, bottom_size_y) <= 0:
        raise ValueError("admitted drawer parameters leave non-positive geometry")

    panels: list[PanelPlacement] = []
    for i in range(count):
        front_z = (
            layout.internal_z_start + i * band_h + (layer_gap if i > 0 else 0.0)
        )
        # 底抽前板全盖底板（overlap=板厚）；顶/中间抽屉无覆盖
        overlap = board if i == 0 else 0.0
        box_h = front_h - 2 * overlap
        box_z = front_z + overlap
        z_suffix = f"z{front_z:.0f}"

        panels.append(PanelPlacement(
            id=f"drawer_front_{z_suffix}", name=f"抽屉前板({front_z:.0f}mm)",
            panel_type="drawer_front",
            size_x=front_w, size_y=board, size_z=front_h,
            pos_x=layout.internal_x_start + spec.front_face_margin,
            pos_y=layout.carcass_y_end - board,
            pos_z=front_z,
            material_role="carcass",
            inner_face=frame.back, outer_face=frame.front, cam_face=None,
            note=f"抽屉前板 {front_w:.0f}×{front_h:.0f}×{board:.0f}mm",
        ))
        panels.append(PanelPlacement(
            id=f"drawer_side_L_{z_suffix}", name=f"抽屉左板({front_z:.0f}mm)",
            panel_type="drawer_side",
            size_x=board, size_y=box_d, size_z=box_h,
            pos_x=layout.internal_x_start + slide_gap,
            pos_y=box_back_y,
            pos_z=box_z,
            material_role="carcass",
            inner_face=frame.right, outer_face=frame.left,
            cam_face=frame.left,  # 偏心轮在侧板外侧面（抽屉外部操作）
            note=f"抽屉左侧板 {box_d:.0f}×{box_h:.0f}×{board:.0f}mm",
        ))
        panels.append(PanelPlacement(
            id=f"drawer_side_R_{z_suffix}", name=f"抽屉右板({front_z:.0f}mm)",
            panel_type="drawer_side",
            size_x=board, size_y=box_d, size_z=box_h,
            pos_x=layout.internal_x_end - board - slide_gap,
            pos_y=box_back_y,
            pos_z=box_z,
            material_role="carcass",
            inner_face=frame.left, outer_face=frame.right,
            cam_face=frame.right,  # 偏心轮在侧板外侧面（抽屉外部操作）
            note=f"抽屉右侧板 {box_d:.0f}×{box_h:.0f}×{board:.0f}mm",
        ))
        panels.append(PanelPlacement(
            id=f"drawer_back_{z_suffix}", name=f"抽屉后板({front_z:.0f}mm)",
            panel_type="drawer_back",
            size_x=box_w - 2 * board, size_y=back_t, size_z=box_h - 2 * board,
            pos_x=layout.internal_x_start + slide_gap + board,
            pos_y=box_back_y,
            pos_z=box_z,  # 背板底边与底板齐平：底板后端的连接杆轴线才能落在背板内
            material_role="carcass",
            inner_face=frame.front, outer_face=frame.back,
            cam_face=frame.back,  # 偏心轮在背板外侧面（抽屉外部操作）
            note=f"抽屉后板 {box_w - 2 * board:.0f}×{box_h - 2 * board:.0f}×{back_t:.0f}mm",
        ))
        panels.append(PanelPlacement(
            id=f"drawer_bottom_{z_suffix}", name=f"抽屉底板({front_z:.0f}mm)",
            panel_type="drawer_bottom",
            size_x=box_w - 2 * board, size_y=bottom_size_y, size_z=bottom_t,
            pos_x=layout.internal_x_start + slide_gap + board,
            pos_y=box_back_y + board,
            pos_z=box_z,
            material_role="carcass",
            inner_face=frame.top, outer_face=frame.bottom,
            cam_face=frame.bottom,  # 偏心轮在底板下面（抽屉外部操作）
            note=f"抽屉底板 {box_w - 2 * board:.0f}×{bottom_size_y:.0f}×{bottom_t:.0f}mm",
        ))
    return panels


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def frame_axis(signed: str) -> str:
    """Return the axis letter from a signed axis: "+x" → "x"."""
    return signed[1]


def frame_sign(signed: str) -> int:
    """Return +1 or -1 from a signed axis."""
    return 1 if signed[0] == "+" else -1


def _frame_from_spec(spec: FurnitureSpec) -> CabinetFrame:
    """Build a CabinetFrame for the spec's furniture type."""
    topology = _load_topology(spec.furniture_type)
    return CabinetFrame(**topology["frame"])
