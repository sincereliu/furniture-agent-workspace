"""Topology solver — convert cabinet topology data into panel placements.

Reads a cabinet topology YAML and a FurnitureSpec, then computes every panel's
3-D placement with correct semantic face directions (inner/outer/cam).

The solver is universal — it does not branch on furniture_type.  All
cabinet-specific knowledge lives in the topology YAML files under
references/cabinet-topologies/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from furniture_design_intent.design_spec import FurnitureSpec, resolve_toe_kick_support_count
from furniture_layout.layout_planning import CabinetLayout

from .cabinet_frame import CabinetFrame
from .panel_models import PanelPlacement


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
    layout: CabinetLayout,
) -> list[PanelPlacement]:
    """Compute all panel placements from topology + spec + layout.

    Parameters
    ----------
    spec : FurnitureSpec
        Normalized cabinet dimensions and parameter choices.
    layout : CabinetLayout
        Pre-computed spatial contract (envelope, clear regions, counts).

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
            placements.extend(_back_panel_variants(spec, layout, side_name, side_def, face_dir))
            continue

        # Standard enclosure panel
        panel = _build_enclosure_panel(spec, layout, side_name, side_def, face_dir)
        placements.append(panel)

    # ── Doors ─────────────────────────────────────────────────────
    front_side = enclosure.get("front", {})
    if front_side.get("type") == "opening":
        for subtype in front_side.get("subtypes", []):
            if subtype == "doors":
                placements.extend(_door_panels(spec, layout, frame))

    # ── Base (toe kick) ───────────────────────────────────────────
    base_def = topology.get("base", {})
    if base_def.get("type") == "toe_kick" and layout.toe_kick_height > 0:
        placements.extend(_toe_kick_panels(spec, layout, base_def, frame))

    # ── Internal shelves ──────────────────────────────────────────
    shelves_def = topology.get("internals", {}).get("shelves", {})
    if shelves_def.get("type") == "fixed" and layout.shelf_count > 0:
        placements.extend(_fixed_shelves(spec, layout, shelves_def, frame))

    return placements


# ═══════════════════════════════════════════════════════════════════
# Panel builders
# ═══════════════════════════════════════════════════════════════════

def _build_enclosure_panel(
    spec: FurnitureSpec,
    layout: CabinetLayout,
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

    else:  # y
        # Back panel — broad face is X-Z plane
        # Handled by _back_panel_variants; fallback
        sx = layout.internal_width
        sy = spec.back_thickness
        sz = layout.internal_height
        px = layout.internal_x_start
        py = layout.back_plane_y
        pz = layout.internal_z_start
        inner = "-y"
        name_map = {"back": "背板"}
        ptype = "back"

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
        material_role=_material_role(axis, axis == "y"),
        inner_face=inner,
        outer_face=outer,
        cam_face=cam,
        note=f"{name}，厚{board:.0f}mm",
    )


def _back_panel_variants(
    spec: FurnitureSpec,
    layout: CabinetLayout,
    side_name: str,
    side_def: dict[str, Any],
    face_dir: str,
) -> list[PanelPlacement]:
    """Generate back panel and optional back rails for the selected mount mode."""
    board = spec.board_thickness
    back_mount = layout.back_mount
    back_y = layout.back_plane_y
    inner = "+y"  # inner face points frontward into cabinet
    outer = "-y"

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
        rail_count = int(layout.internal_height // 500)
        if rail_h > 0 and rail_count > 0:
            step = (layout.internal_height - rail_count * rail_h) / rail_count
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
    layout: CabinetLayout,
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate door panels on the front face of the cabinet."""
    count = layout.door_count
    if count <= 0:
        return []

    margin = spec.door_margin
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
            hinge_side = "left"
        elif count == 2:
            pid = "left_door" if index == 0 else "right_door"
            pname = "左门板" if index == 0 else "右门板"
            x = margin if index == 0 else layout.width - margin - dw
            hinge_side = "left" if index == 0 else "right"
        else:
            pid = f"door_{index + 1}_door"
            pname = f"门板{index + 1}"
            x = margin * (2 * (index + 1) - 1) + dw * index
            hinge_side = None

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
    layout: CabinetLayout,
    base_def: dict[str, Any],
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate toe kick panels (front and rear kickboards + optional supports)."""
    board = spec.board_thickness
    kw = layout.internal_width
    x = layout.internal_x_start

    # Toe kick panels — their inner face is toward cabinet interior (+y for rear, -y for front)
    rear = PanelPlacement(
        id="toe_kick_back", name="后踢脚板", panel_type="toe_kick",
        size_x=kw, size_y=board, size_z=layout.toe_kick_height,
        pos_x=x, pos_y=layout.toe_kick_rear_y,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
        inner_face="+y", outer_face="-y", cam_face=None,
    )
    front = PanelPlacement(
        id="toe_kick_front", name="前踢脚板", panel_type="toe_kick",
        size_x=kw, size_y=board, size_z=layout.toe_kick_height,
        pos_x=x, pos_y=layout.toe_kick_front_y - board,
        material_role="carcass",
        depends_on=["left_side_panel", "right_side_panel"],
        inner_face="-y", outer_face="+y", cam_face=None,
    )
    panels = [rear, front]

    count = resolve_toe_kick_support_count(spec.toe_kick_support_count, layout.width)
    if count == 0:
        return panels

    sy = layout.toe_kick_rear_y + board
    sd = layout.toe_kick_front_y - board - sy
    gap = (kw - count * board) / (count + 1)
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


def _fixed_shelves(
    spec: FurnitureSpec,
    layout: CabinetLayout,
    shelves_def: dict[str, Any],
    frame: CabinetFrame,
) -> list[PanelPlacement]:
    """Generate fixed shelf panels between top and bottom."""
    board = spec.board_thickness
    if layout.shelf_count <= 0:
        return []

    layer_h = layout.internal_height / (layout.shelf_count + 1)
    sd = layout.internal_y_end - layout.internal_y_start

    # Fixed shelves are horizontal: inner face = bottom (same cam accessibility)
    panels = []
    for i in range(1, layout.shelf_count + 1):
        cz = layout.internal_z_start + i * layer_h
        panels.append(PanelPlacement(
            id=f"shelf_z{cz:.0f}", name=f"层板({cz:.0f}mm)",
            panel_type="fixed_shelf",
            size_x=layout.internal_width, size_y=sd, size_z=board,
            pos_x=layout.internal_x_start, pos_y=layout.internal_y_start,
            pos_z=cz - board / 2,
            material_role="carcass",
            depends_on=["left_side_panel", "right_side_panel"],
            inner_face="-z", outer_face="+z", cam_face="-z",  # cam accessible from below
            note="固定层板",
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


def _material_role(axis: str, is_back: bool) -> str:
    if is_back:
        return "back"
    return "carcass"
