"""Cabinet spatial planning without manufacturing panel records."""

from __future__ import annotations

from dataclasses import dataclass

from furniture_design_intent.design_spec import FurnitureSpec


@dataclass(frozen=True)
class CabinetLayout:
    """Stage-2 spatial contract consumed by panel planning."""

    furniture_type: str
    width: float
    depth: float
    height: float
    side_depth: float
    internal_width: float
    internal_height: float
    internal_x_start: float
    internal_x_end: float
    internal_y_start: float
    internal_y_end: float
    internal_z_start: float
    internal_z_end: float
    back_plane_y: float
    toe_kick_height: float
    toe_kick_rear_y: float
    toe_kick_front_y: float
    shelf_count: int
    door_count: int

    @classmethod
    def from_spec(cls, spec: FurnitureSpec) -> "CabinetLayout":
        board = spec.board_thickness
        side_depth = spec.depth - spec.door_thickness - spec.door_hinge_gap
        toe_kick = (
            spec.toe_kick_height if spec.furniture_type != "wall_cabinet" else 0.0
        )
        return cls(
            furniture_type=spec.furniture_type,
            width=spec.width,
            depth=spec.depth,
            height=spec.height,
            side_depth=side_depth,
            internal_width=spec.width - 2 * board,
            internal_height=spec.height - toe_kick - 2 * board,
            internal_x_start=board,
            internal_x_end=spec.width - board,
            internal_y_start=spec.back_offset + spec.back_thickness,
            internal_y_end=side_depth,
            internal_z_start=toe_kick + board,
            internal_z_end=spec.height - board,
            back_plane_y=spec.back_offset,
            toe_kick_height=toe_kick,
            toe_kick_rear_y=spec.toe_kick_reveal_back,
            toe_kick_front_y=side_depth - spec.toe_kick_reveal_front,
            shelf_count=spec.shelf_count,
            door_count=spec.n_doors,
        )
