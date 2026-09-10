"""Deterministic panel boxes shared by the solver and stage validation."""

from __future__ import annotations

from dataclasses import dataclass

from .panel_rules import (
    back_rail_clear_spacing,
    resolve_back_rail_count,
    resolve_toe_kick_support_count,
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


def drawer_panel_boxes(
    spec: FurnitureSpec,
    layout: CabinetStructure,
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
    iw = layout.internal_width
    internal_depth = layout.internal_y_end - layout.internal_y_start
    band_h = layout.internal_height / count
    front_h = band_h - layer_gap
    front_w = iw - 2 * spec.front_face_margin
    box_w = iw - 2 * slide_gap
    box_d = internal_depth - board - back_clear
    box_back_y = layout.internal_y_start + back_clear
    bottom_size_y = box_d - board
    if min(front_h, front_w, box_w, box_d, bottom_size_y) <= 0:
        raise ValueError("admitted drawer parameters leave non-positive geometry")

    boxes: list[PanelBox] = []
    for index in range(count):
        front_z = layout.internal_z_start + index * band_h + (
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
                    pos_x=layout.internal_x_start + spec.front_face_margin,
                    pos_y=layout.carcass_y_end - board,
                    pos_z=front_z,
                ),
                PanelBox(
                    panel_id=f"drawer_side_L_{suffix}",
                    size_x=board,
                    size_y=box_d,
                    size_z=box_h,
                    pos_x=layout.internal_x_start + slide_gap,
                    pos_y=box_back_y,
                    pos_z=box_z,
                ),
                PanelBox(
                    panel_id=f"drawer_side_R_{suffix}",
                    size_x=board,
                    size_y=box_d,
                    size_z=box_h,
                    pos_x=layout.internal_x_end - board - slide_gap,
                    pos_y=box_back_y,
                    pos_z=box_z,
                ),
                PanelBox(
                    panel_id=f"drawer_back_{suffix}",
                    size_x=box_w - 2 * board,
                    size_y=back_t,
                    size_z=box_h - 2 * board,
                    pos_x=layout.internal_x_start + slide_gap + board,
                    pos_y=box_back_y,
                    pos_z=box_z,
                ),
                PanelBox(
                    panel_id=f"drawer_bottom_{suffix}",
                    size_x=box_w - 2 * board,
                    size_y=bottom_size_y,
                    size_z=bottom_t,
                    pos_x=layout.internal_x_start + slide_gap + board,
                    pos_y=box_back_y + board,
                    pos_z=box_z,
                ),
            ]
        )
    return boxes


def shelf_panel_boxes(
    spec: FurnitureSpec,
    layout: CabinetStructure,
) -> list[PanelBox]:
    """Return shelf envelopes from the admitted list, top to bottom."""
    if not spec.shelves:
        return []
    gaps = resolve_shelf_gaps(spec, layout.internal_height)
    board = spec.board_thickness
    depth = layout.internal_y_end - layout.internal_y_start
    top_z = layout.internal_z_end - spec.top_gap_mm
    boxes: list[PanelBox] = []
    for shelf, gap in zip(spec.shelves, gaps):
        bottom_z = top_z - board
        center_z = bottom_z + board / 2
        if shelf.shelf_type == "fixed":
            panel_id = f"shelf_z{center_z:.0f}"
        else:
            panel_id = f"movable_shelf_z{center_z:.0f}"
        boxes.append(
            PanelBox(
                panel_id=panel_id,
                size_x=layout.internal_width,
                size_y=depth,
                size_z=board,
                pos_x=layout.internal_x_start,
                pos_y=layout.internal_y_start,
                pos_z=bottom_z,
                shelf_type=shelf.shelf_type,
                center_z=center_z,
            )
        )
        top_z = bottom_z - gap
    return boxes


def toe_kick_support_boxes(
    spec: FurnitureSpec,
    layout: CabinetStructure,
) -> list[PanelBox]:
    """Return equally spaced toe-kick supports, or an empty list."""
    if layout.toe_kick_height <= 0:
        return []
    count = resolve_toe_kick_support_count(spec.toe_kick_support_count, layout.width)
    if count <= 0:
        return []
    board = spec.board_thickness
    width = layout.internal_width
    origin_x = layout.internal_x_start
    pos_y = layout.toe_kick_rear_y + board
    size_y = layout.toe_kick_front_y - board - pos_y
    gap = toe_kick_support_clear_spacing(width, count, board)
    return [
        PanelBox(
            panel_id=f"toe_kick_support_{index + 1}",
            size_x=board,
            size_y=size_y,
            size_z=layout.toe_kick_height,
            pos_x=origin_x + gap + index * (board + gap),
            pos_y=pos_y,
            pos_z=0.0,
        )
        for index in range(count)
    ]


def back_rail_boxes(
    spec: FurnitureSpec,
    layout: CabinetStructure,
) -> list[PanelBox]:
    """Return grooved-back rail envelopes, or an empty list."""
    rail_h = spec.back_rail_height
    count = resolve_back_rail_count(
        layout.back_mount,
        layout.internal_height,
        rail_h,
    )
    if rail_h <= 0 or count <= 0:
        return []
    board = spec.board_thickness
    step = back_rail_clear_spacing(layout.internal_height, count, rail_h)
    return [
        PanelBox(
            panel_id=f"back_rail_{index + 1}",
            size_x=layout.internal_width,
            size_y=board,
            size_z=rail_h,
            pos_x=layout.internal_x_start,
            pos_y=layout.carcass_y_start,
            pos_z=layout.internal_z_start + step + index * (rail_h + step),
        )
        for index in range(count)
    ]
