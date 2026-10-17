"""Deterministic panel boxes shared by the solver and stage validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .interior_structure import evaluate_interior
from .panel_rules import (
    back_rail_clear_spacing,
    resolve_back_rail_count,
    toe_kick_support_clear_spacing,
)
from .panel_spec import FurnitureSpec, resolve_shelf_gaps
from .structure_planning import CabinetStructure


@dataclass(frozen=True)
class PanelBox:
    """Axis-aligned panel envelope used by both generation and checks."""

    panel_id: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    shelf_type: str | None = None
    center_z: float | None = None
    #: 分段层板所在的腔（1 起）；没有中立板时是 1，且 `cavity_count` 也是 1。
    cavity_index: int = 1
    cavity_count: int = 1
    #: 这块板两侧的支撑（侧板或中立板）。只有分段层板用得上；不参与几何核对。
    supports: tuple[str, ...] = ()

    @property
    def geometry(self) -> tuple[float, float, float, float, float, float]:
        return (
            self.size_x,
            self.size_y,
            self.size_z,
            self.pos_x,
            self.pos_y,
            self.pos_z,
        )


def _interior_payload(spec: FurnitureSpec) -> dict[str, Any]:
    """评估器入参：正面 + 中立板。门与立板共用这一份，缝与零头只算一次。"""
    payload: dict[str, Any] = {
        "width_mm": spec.width,
        "n_doors": spec.n_doors,
        "margin_mm": spec.front_face_margin,
        "side_thickness_mm": spec.board_thickness,
    }
    if spec.dividers:
        payload["dividers"] = [
            {
                "id": f"divider_{index}",
                "seam_index": item.seam_index,
                "seam_align": item.seam_align,
                "thickness_mm": spec.board_thickness,
            }
            for index, item in enumerate(spec.dividers, start=1)
        ]
    return payload


def divider_interior_report(spec: FurnitureSpec) -> dict[str, Any]:
    """中立板的毫米来源：提案只说对准哪条缝，毫米由评估器算。

    这是板件阶段与 `furniture_evaluate_interior` 之间唯一的接口——缝、区间都出自
    同一份公式，板件阶段不再自己算一遍（见
    references/interior-materialization-design.md「决定 1：单一来源」）。
    板厚不是提案字段：中立板是柜体板，取已准入的 `board_thickness`。
    """
    if not spec.dividers:
        return {}
    return evaluate_interior(_interior_payload(spec))


def door_interior_report(spec: FurnitureSpec) -> dict[str, Any]:
    """门宽的毫米来源：等分槽位、缝、零头归宿都由评估器算。

    板件阶段不再自己推导门宽——旧 `_door_panels` 里那份
    `(柜宽 − 边距×2×扇数)/扇数` 是第二套公式，两扇门时恰好同值，多扇就会分叉。
    """
    if spec.n_doors <= 0:
        return {}
    return evaluate_interior(_interior_payload(spec))


def door_panel_boxes(
    spec: FurnitureSpec,
    structure: CabinetStructure,
) -> list[PanelBox]:
    """门板盒子：宽与起点只从评估器的回报里取，摆放口径沿用前脸。"""
    report = door_interior_report(spec)
    if not report:
        return []
    doors = report["doors"]
    widths = [float(value) for value in doors["door_widths_mm"]]
    starts = [float(value) for value in doors["door_starts_mm"]]
    height = (
        structure.height
        - structure.toe_kick_height
        - spec.front_face_margin * 2
    )
    pos_y = structure.carcass_y_end + spec.front_gap
    pos_z = structure.toe_kick_height + spec.front_face_margin
    return [
        PanelBox(
            panel_id=_door_panel_id(index, len(widths)),
            size_x=width,
            size_y=spec.door_thickness,
            size_z=height,
            pos_x=start,
            pos_y=pos_y,
            pos_z=pos_z,
        )
        for index, (start, width) in enumerate(zip(starts, widths), start=1)
    ]


def _door_panel_id(index: int, count: int) -> str:
    """一块门的角色名。一扇、两扇沿用老名字（冻结文件与测试都钉着）。"""
    if count == 1:
        return "single_door"
    if count == 2:
        return "left_door" if index == 1 else "right_door"
    return f"door_{index}"


def divider_intervals(spec: FurnitureSpec) -> list[tuple[str, float, float]]:
    """中立板的 `(角色名, 起点, 终点)`，从左到右；评估器说 blocked 就不出件。"""
    report = divider_interior_report(spec)
    if not report:
        return []
    if report.get("blocked"):
        reasons = "；".join(
            str(item.get("message"))
            for item in report.get("findings", ())
            if item.get("status") == "blocked"
        )
        raise ValueError(
            "divider layout is blocked: " + (reasons or "see the interior report")
        )
    placed = sorted(
        report.get("dividers", ()),
        key=lambda item: (float(item["start_mm"]), int(item["seam_index"])),
    )
    return [
        (f"divider_{index}", float(item["start_mm"]), float(item["end_mm"]))
        for index, item in enumerate(placed, start=1)
    ]


def divider_panel_boxes(
    spec: FurnitureSpec,
    structure: CabinetStructure,
) -> list[PanelBox]:
    """中立板盒子：站在内部净空里，从底板上表面到顶板下表面。"""
    depth = structure.internal_y_end - structure.internal_y_start
    height = structure.internal_z_end - structure.internal_z_start
    return [
        PanelBox(
            panel_id=role,
            size_x=end - start,
            size_y=depth,
            size_z=height,
            pos_x=start,
            pos_y=structure.internal_y_start,
            pos_z=structure.internal_z_start,
        )
        for role, start, end in divider_intervals(spec)
    ]


def interior_cavity_bounds(
    spec: FurnitureSpec,
    structure: CabinetStructure,
) -> list[tuple[float, float]]:
    """各腔的 X 区间（从左到右）：没有中立板时就是一整个内空。"""
    return _cavity_bounds(structure, divider_panel_boxes(spec, structure))


def _cavity_bounds(
    structure: CabinetStructure,
    dividers: Sequence[PanelBox],
) -> list[tuple[float, float]]:
    bounds: list[tuple[float, float]] = []
    left = structure.internal_x_start
    for box in dividers:
        bounds.append((left, box.pos_x))
        left = box.pos_x + box.size_x
    bounds.append((left, structure.internal_x_end))
    return bounds


def drawer_panel_boxes(
    spec: FurnitureSpec,
    structure: CabinetStructure,
) -> list[PanelBox]:
    """Return the admitted full-height drawer dimension chain.

    Formulas live here so validation can compare against the same numbers
    the solver materializes. See references/drawer-dimension-chain.md.
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
    iw = structure.internal_width
    internal_depth = structure.internal_y_end - structure.internal_y_start
    band_h = structure.internal_height / count
    front_h = band_h - layer_gap
    front_w = iw - 2 * spec.front_face_margin
    box_w = iw - 2 * slide_gap
    box_d = internal_depth - board - back_clear
    box_back_y = structure.internal_y_start + back_clear
    bottom_size_y = box_d - board
    if min(front_h, front_w, box_w, box_d, bottom_size_y) <= 0:
        raise ValueError("admitted drawer parameters leave non-positive geometry")

    boxes: list[PanelBox] = []
    for index in range(count):
        front_z = structure.internal_z_start + index * band_h + (
            layer_gap if index > 0 else 0.0
        )
        overlap = board if index == 0 else 0.0
        box_h = front_h - 2 * overlap
        box_z = front_z + overlap
        suffix = f"z{front_z:.0f}"
        boxes.extend(
            [
                PanelBox(
                    panel_id=f"drawer_front_{suffix}",
                    size_x=front_w,
                    size_y=board,
                    size_z=front_h,
                    pos_x=structure.internal_x_start + spec.front_face_margin,
                    pos_y=structure.carcass_y_end - board,
                    pos_z=front_z,
                ),
                PanelBox(
                    panel_id=f"drawer_side_L_{suffix}",
                    size_x=board,
                    size_y=box_d,
                    size_z=box_h,
                    pos_x=structure.internal_x_start + slide_gap,
                    pos_y=box_back_y,
                    pos_z=box_z,
                ),
                PanelBox(
                    panel_id=f"drawer_side_R_{suffix}",
                    size_x=board,
                    size_y=box_d,
                    size_z=box_h,
                    pos_x=structure.internal_x_end - board - slide_gap,
                    pos_y=box_back_y,
                    pos_z=box_z,
                ),
                PanelBox(
                    panel_id=f"drawer_back_{suffix}",
                    size_x=box_w - 2 * board,
                    size_y=back_t,
                    size_z=box_h - 2 * board,
                    pos_x=structure.internal_x_start + slide_gap + board,
                    pos_y=box_back_y,
                    pos_z=box_z,
                ),
                PanelBox(
                    panel_id=f"drawer_bottom_{suffix}",
                    size_x=box_w - 2 * board,
                    size_y=bottom_size_y,
                    size_z=bottom_t,
                    pos_x=structure.internal_x_start + slide_gap + board,
                    pos_y=box_back_y + board,
                    pos_z=box_z,
                ),
            ]
        )
    return boxes


def shelf_panel_boxes(
    spec: FurnitureSpec,
    structure: CabinetStructure,
) -> list[PanelBox]:
    """Return shelf envelopes from the admitted list, top to bottom.

    有中立板时每层按腔分段出件：中立板站在内部净空里，层板跨不过去。
    没有中立板时与老产出同名同几何（腔序号不写进 id）。
    """
    if not spec.shelves:
        return []
    gaps = resolve_shelf_gaps(spec, structure.internal_height)
    board = spec.board_thickness
    depth = structure.internal_y_end - structure.internal_y_start
    dividers = divider_panel_boxes(spec, structure)
    cavities = _cavity_bounds(structure, dividers)
    top_z = structure.internal_z_end - spec.top_gap_mm
    boxes: list[PanelBox] = []
    for shelf, gap in zip(spec.shelves, gaps):
        bottom_z = top_z - board
        center_z = bottom_z + board / 2
        for index, (start, end) in enumerate(cavities, start=1):
            boxes.append(
                PanelBox(
                    panel_id=_shelf_panel_id(
                        shelf.shelf_type, center_z, index, len(cavities),
                    ),
                    size_x=end - start,
                    size_y=depth,
                    size_z=board,
                    pos_x=start,
                    pos_y=structure.internal_y_start,
                    pos_z=bottom_z,
                    shelf_type=shelf.shelf_type,
                    center_z=center_z,
                    cavity_index=index,
                    cavity_count=len(cavities),
                    supports=_cavity_supports(structure, dividers, start, end),
                )
            )
        top_z = bottom_z - gap
    return boxes


def _shelf_panel_id(
    shelf_type: str,
    center_z: float,
    cavity_index: int,
    cavity_count: int,
) -> str:
    prefix = "shelf" if shelf_type == "fixed" else "movable_shelf"
    if cavity_count == 1:
        return f"{prefix}_z{center_z:.0f}"
    return f"{prefix}_c{cavity_index}_z{center_z:.0f}"


def _cavity_supports(
    structure: CabinetStructure,
    dividers: Sequence[PanelBox],
    start: float,
    end: float,
) -> tuple[str, ...]:
    """这个腔两侧撑着层板的是谁：侧板还是哪块中立板。"""
    left = "left_side_panel"
    right = "right_side_panel"
    for box in dividers:
        if abs(box.pos_x + box.size_x - start) < 1e-6:
            left = box.panel_id
        if abs(box.pos_x - end) < 1e-6:
            right = box.panel_id
    return (left, right)


def toe_kick_support_boxes(
    spec: FurnitureSpec,
    structure: CabinetStructure,
) -> list[PanelBox]:
    """Return equally spaced toe-kick supports, or an empty list."""
    if structure.toe_kick_height <= 0:
        return []
    count = spec.toe_kick_support_count
    if count <= 0:
        return []
    board = spec.board_thickness
    width = structure.internal_width
    origin_x = structure.internal_x_start
    pos_y = structure.toe_kick_rear_y + board
    size_y = structure.toe_kick_front_y - board - pos_y
    gap = toe_kick_support_clear_spacing(width, count, board)
    return [
        PanelBox(
            panel_id=f"toe_kick_support_{index + 1}",
            size_x=board,
            size_y=size_y,
            size_z=structure.toe_kick_height,
            pos_x=origin_x + gap + index * (board + gap),
            pos_y=pos_y,
            pos_z=0.0,
        )
        for index in range(count)
    ]


def back_rail_boxes(
    spec: FurnitureSpec,
    structure: CabinetStructure,
) -> list[PanelBox]:
    """Return grooved-back rail envelopes, or an empty list."""
    rail_h = spec.back_rail_height
    count = resolve_back_rail_count(
        structure.back_mount,
        structure.internal_height,
        rail_h,
    )
    if rail_h <= 0 or count <= 0:
        return []
    board = spec.board_thickness
    step = back_rail_clear_spacing(structure.internal_height, count, rail_h)
    return [
        PanelBox(
            panel_id=f"back_rail_{index + 1}",
            size_x=structure.internal_width,
            size_y=board,
            size_z=rail_h,
            pos_x=structure.internal_x_start,
            pos_y=structure.carcass_y_start,
            pos_z=structure.internal_z_start + step + index * (rail_h + step),
        )
        for index in range(count)
    ]
