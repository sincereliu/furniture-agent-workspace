"""Topology solver — convert cabinet topology data into panel placements.

Reads a cabinet topology YAML and a FurnitureSpec, then computes every panel's
3-D placement with size, position, and inner/outer faces.

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
from .cabinet_identity import DEFAULT_CABINET_ID, bind_panels_to_cabinet
from .construction_geometry import (
    back_panel_boxes,
    back_rail_boxes,
    cavity_flanks,
    divider_panel_boxes,
    door_panel_boxes,
    drawer_panel_boxes,
    shelf_panel_boxes,
    toe_kick_support_boxes,
)
from .joint_topology import compute_joints
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def _load_topology(furniture_category: str) -> dict[str, Any]:
    """Load a topology YAML file for the given furniture category."""
    topo_dir = (
        Path(__file__).resolve().parents[2]
        / "references"
        / "cabinet-topologies"
    )
    path = topo_dir / f"{furniture_category}.yaml"
    if not path.exists():
        raise FileNotFoundError(
            f"No topology defined for furniture_category='{furniture_category}'. "
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
    structure: CabinetStructure,
    cabinet_id: str = DEFAULT_CABINET_ID,
) -> list[PanelPlacement]:
    """Compute all panel placements from topology + spec + structure.

    Parameters
    ----------
    spec : FurnitureSpec
        Normalized cabinet dimensions and parameter choices.
    structure : CabinetStructure
        Panel-stage construction geometry and exact clear regions.
    cabinet_id : str
        Owning cabinet instance. Panel ids are qualified onto this parent.
    """
    topology = _load_topology(spec.furniture_category)
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
            placements.extend(_back_panel_variants(spec, structure, side_name, side_def, face_dir, frame))
            continue

        # Standard enclosure panel
        panel = _build_enclosure_panel(spec, structure, side_name, face_dir)
        placements.append(panel)

    # ── Doors ─────────────────────────────────────────────────────
    # 抽屉与门暂时互斥：有抽屉就不生成门（正面开口的缝/覆盖还没一起排）。
    front_side = enclosure.get("front", {})
    if front_side.get("type") == "opening" and spec.drawer_count <= 0:
        for subtype in front_side.get("subtypes", []):
            if subtype == "doors":
                placements.extend(_door_panels(spec, structure, frame))

    # ── Base (toe kick) ───────────────────────────────────────────
    base_def = topology.get("base", {})
    if base_def.get("type") == "toe_kick" and structure.toe_kick_height > 0:
        placements.extend(_toe_kick_panels(spec, structure, base_def, frame))

    # ── 中立板 ────────────────────────────────────────────────────
    # 区间与缝由评估器算（唯一公式）；这里只摆件、声明大面。
    if spec.dividers:
        placements.extend(_divider_panels(spec, structure, frame))

    # ── Internal shelves / drawers ────────────────────────────────
    internals = topology.get("internals", {})
    if spec.shelves:
        placements.extend(_shelves_from_spec(spec, structure, frame))
    if spec.drawer_count > 0:
        # 抽屉区：占满净高、显式净高或某一格，由 spec 决定；与层板可以共存。
        drawers_def = internals.get("drawers", {})
        if drawers_def.get("type") == "zone":
            placements.extend(_drawer_panels(spec, structure, drawers_def, frame))

    bind_panels_to_cabinet(placements, cabinet_id)

    # ── Connection topology ──────────────────────────────────────
    joints = compute_joints(placements)
    for panel in placements:
        panel.joints = [
            j for j in joints
            if j.bearing_id == panel.id or j.end_id == panel.id
        ]

    return placements


# ═══════════════════════════════════════════════════════════════════
# Panel builders
# ═══════════════════════════════════════════════════════════════════

def _build_enclosure_panel(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    side_name: str,
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
            px = structure.width - board
            inner = "-x"    # inner face points left (toward cabinet center)
        else:
            # Left face: panel sits at x=0
            px = 0.0
            inner = "+x"    # inner face points right
        sx, sy, sz = board, structure.side_depth, structure.height
        py = structure.carcass_y_start
        pz = 0.0
        name_map = {"left_side": "左侧板", "right_side": "右侧板"}
        ptype = "side"

    elif axis == "z":
        # Horizontal panel (top or bottom) — broad face is X-Y plane
        sx = structure.internal_width
        sy = structure.side_depth
        sz = board
        px = structure.internal_x_start
        py = structure.carcass_y_start
        if sign > 0:
            pz = structure.height - board  # top
            inner = "-z"
        else:
            pz = structure.toe_kick_height  # bottom
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

    return PanelPlacement(
        id=f"{side_name}_panel",
        name=name,
        panel_type=ptype,
        size_x=sx, size_y=sy, size_z=sz,
        pos_x=px, pos_y=py, pos_z=pz,
        material_role="carcass",
        inner_face=inner,
        outer_face=outer,
        note=f"{name}，厚{board:.0f}mm",
    )


def _back_panel_variants(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    side_name: str,
    side_def: dict[str, Any],
    face_dir: str,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """背板（每腔一块）与可选的背拉条。

    背板: 外表面=柜体背面, 内表面指向柜内=柜体前面。
    毫米来自 `construction_geometry.back_panel_boxes`——每腔一块、夹在两侧板/立板
    之间；这里只摆件，不再自己算宽度。
    """
    board = spec.board_thickness
    outer = face_dir          # frame.back
    inner = negate_axis(outer)  # frame.front

    pieces = back_panel_boxes(spec, structure)
    count = len(pieces)
    result: list[PanelPlacement] = []
    for index, box in enumerate(pieces, start=1):
        if count == 1:
            name = "背板"
            if structure.back_mount == "groove":
                note = f"四边入槽{spec.groove_depth:.0f}mm的成品背板"
            elif structure.back_mount == "insert":
                note = "内嵌背板，位于内部净空后侧"
            else:
                note = "外盖背板，覆盖整个背面"
        else:
            name = f"背板{index}"
            if structure.back_mount == "insert":
                note = f"内嵌背板第{index}/{count}块，四边三合一锁在侧板/中立板上"
            else:
                note = f"背板第{index}/{count}块，两侧入侧板/中立板的槽"
        flank_left, flank_right = cavity_flanks(
            spec, structure, index, count,
        )
        result.append(PanelPlacement(
            id=box.panel_id, name=name, panel_type="back",
            size_x=box.size_x, size_y=box.size_y, size_z=box.size_z,
            pos_x=box.pos_x, pos_y=box.pos_y, pos_z=box.pos_z,
            material_role="back",
            depends_on=[flank_left, flank_right, "top_panel", "bottom_panel"],
            inner_face=inner, outer_face=outer,
            note=note,
        ))

    if structure.back_mount == "groove":
        for box in back_rail_boxes(spec, structure):
            index = box.panel_id.rsplit("_", 1)[-1]
            if box.cavity_count == 1:
                name = f"背拉条{index}"
            else:
                name = f"背拉条(腔{box.cavity_index}·{index})"
            flank_left, flank_right = cavity_flanks(
                spec, structure, box.cavity_index, box.cavity_count,
            )
            result.append(PanelPlacement(
                id=box.panel_id, name=name,
                panel_type="back_rail",
                size_x=box.size_x, size_y=box.size_y, size_z=box.size_z,
                pos_x=box.pos_x, pos_y=box.pos_y, pos_z=box.pos_z,
                material_role="carcass",
                depends_on=[flank_left, flank_right],
                inner_face="+y", outer_face="-y",
                note=f"背板拉条，{box.size_z:.0f}×{board:.0f}mm",
            ))

    return result


_DOOR_LABELS = {"single_door": "门板", "left_door": "左门板", "right_door": "右门板"}


def _door_panels(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate door panels on the front face of the cabinet.

    每扇门的宽度与起点由评估器给（`door_panel_boxes`），这里只摆件、声明前脸。
    扇数不再限制成 1/2：一整排按从左到右的顺序出件，一扇 `single_door`、
    两扇 `left_door`/`right_door`、三扇以上 `door_1…door_n`。
    """
    inner = frame.back
    outer = frame.front
    panels: list[PanelPlacement] = []
    for index, box in enumerate(door_panel_boxes(spec, structure), start=1):
        panels.append(PanelPlacement(
            id=box.panel_id,
            name=_DOOR_LABELS.get(box.panel_id, f"门板{index}"),
            panel_type="door",
            size_x=box.size_x, size_y=box.size_y, size_z=box.size_z,
            pos_x=box.pos_x, pos_y=box.pos_y, pos_z=box.pos_z,
            material_role="door",
            depends_on=["left_side_panel", "right_side_panel"],
            inner_face=inner, outer_face=outer,
            # 铰链侧是板件属性：对开由几何定，单开来自提案；定不下来的留空。
            door_hinge_side=box.door_hinge_side,
            note=f"门板，{box.size_x:.0f}×{box.size_z:.0f}×{spec.door_thickness:.0f}mm",
        ))
    return panels


def _toe_kick_panels(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    base_def: dict[str, Any],
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate toe kick panels (front and rear kickboards + optional supports)."""
    board = spec.board_thickness
    kw = structure.internal_width
    x = structure.internal_x_start

    # Toe kick panels — outer faces outward, inner faces toward cabinet interior
    rear = PanelPlacement(
        id="toe_kick_back", name="后踢脚板", panel_type="toe_kick",
        size_x=kw, size_y=board, size_z=structure.toe_kick_height,
        pos_x=x, pos_y=structure.toe_kick_rear_y,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
        inner_face=frame.front, outer_face=frame.back,
    )
    front = PanelPlacement(
        id="toe_kick_front", name="前踢脚板", panel_type="toe_kick",
        size_x=kw, size_y=board, size_z=structure.toe_kick_height,
        pos_x=x, pos_y=structure.toe_kick_front_y - board,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
        inner_face=frame.back, outer_face=frame.front,
    )
    panels = [rear, front]
    for box in toe_kick_support_boxes(spec, structure):
        index = box.panel_id.rsplit("_", 1)[-1]
        panels.append(PanelPlacement(
            id=box.panel_id, name=f"踢脚支撑{index}",
            panel_type="toe_kick",
            size_x=box.size_x, size_y=box.size_y, size_z=box.size_z,
            pos_x=box.pos_x, pos_y=box.pos_y, pos_z=box.pos_z,
            material_role="carcass",
            depends_on=["toe_kick_back", "toe_kick_front"],
            inner_face="", outer_face="",
        ))
    return panels


def _divider_panels(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """中立板：站在内部净空里，两张朝柜内的大面都接端面。

    几何（缝、区间、板厚）由 `divider_panel_boxes` 调评估器算，这里不另算一套。
    """
    panels: list[PanelPlacement] = []
    for index, box in enumerate(divider_panel_boxes(spec, structure), start=1):
        panels.append(PanelPlacement(
            id=box.panel_id,
            name=f"中立板{index}",
            panel_type="divider",
            size_x=box.size_x, size_y=box.size_y, size_z=box.size_z,
            pos_x=box.pos_x, pos_y=box.pos_y, pos_z=box.pos_z,
            material_role="carcass",
            depends_on=["top_panel", "bottom_panel"],
            inner_face=frame.right, outer_face=frame.left,
            # 左右各朝一个腔：两张都是大面，少一张就少一侧的连接。
            bearing_faces=[frame.left],
            note=f"中立板，厚{box.size_x:.0f}mm，锚在缝上",
        ))
    return panels


def _shelves_from_spec(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """按 spec.shelves（从上到下）生成固定/活动层板。"""
    inner = frame.bottom
    outer = frame.top
    panels: list[PanelPlacement] = []
    for box in shelf_panel_boxes(spec, structure):
        # 分段层板同标高有好几块，名字必须带腔号，否则审查清单里分不出是哪些。
        where = (
            f"腔{box.cavity_index}·{box.center_z:.0f}mm"
            if box.cavity_count > 1
            else f"{box.center_z:.0f}mm"
        )
        if box.shelf_type == "fixed":
            panel_type = "fixed_shelf"
            name = f"层板({where})"
            note = "固定层板"
        else:
            panel_type = "movable_shelf"
            name = f"活动层板({where})"
            note = "活动层板"
        panels.append(PanelPlacement(
            id=box.panel_id, name=name, panel_type=panel_type,
            size_x=box.size_x, size_y=box.size_y, size_z=box.size_z,
            pos_x=box.pos_x, pos_y=box.pos_y, pos_z=box.pos_z,
            material_role="carcass",
            depends_on=list(box.supports) or ["left_side_panel", "right_side_panel"],
            inner_face=inner, outer_face=outer,
            note=note,
        ))
    return panels


def _drawer_panels(
    spec: FurnitureSpec,
    structure: CabinetStructure,
    drawers_def: dict[str, Any],
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Materialize full-height drawer boxes from the shared dimension chain."""
    roles = {
        "drawer_front": (
            "drawer_front", "抽面", frame.back, frame.front,
        ),
        "drawer_box_front": (
            "drawer_box_front", "抽屉前板", frame.back, frame.front,
        ),
        "drawer_side_L": (
            "drawer_side", "抽屉左板", frame.right, frame.left,
        ),
        "drawer_side_R": (
            "drawer_side", "抽屉右板", frame.left, frame.right,
        ),
        "drawer_back": (
            "drawer_back", "抽屉后板", frame.front, frame.back,
        ),
        "drawer_bottom": (
            "drawer_bottom", "抽屉底板", frame.top, frame.bottom,
        ),
    }
    panels: list[PanelPlacement] = []
    for box in drawer_panel_boxes(spec, structure):
        role_key = box.panel_id.rsplit("_z", 1)[0]
        panel_type, label, inner, outer = roles[role_key]
        z_label = box.panel_id.rsplit("_", 1)[-1][1:]
        panels.append(PanelPlacement(
            id=box.panel_id,
            name=f"{label}({z_label}mm)",
            panel_type=panel_type,
            size_x=box.size_x, size_y=box.size_y, size_z=box.size_z,
            pos_x=box.pos_x, pos_y=box.pos_y, pos_z=box.pos_z,
            material_role="carcass",
            inner_face=inner, outer_face=outer,
            note=(
                f"{label} {box.size_x:.0f}×{box.size_z:.0f}×{box.size_y:.0f}mm"
                if panel_type in ("drawer_front", "drawer_box_front")
                else f"{label} {box.size_y:.0f}×{box.size_z:.0f}×{box.size_x:.0f}mm"
            ),
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


