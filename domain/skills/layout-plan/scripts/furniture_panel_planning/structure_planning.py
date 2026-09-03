"""Exact cabinet construction geometry owned by panels_planned."""

from __future__ import annotations

from dataclasses import dataclass

from .panel_spec import FurnitureSpec


@dataclass(frozen=True)
class CabinetStructure:
    """Exact carcass, internal-clearance, back, and toe-kick geometry."""

    furniture_type: str
    width: float
    depth: float
    height: float
    side_depth: float
    carcass_y_start: float
    carcass_y_end: float
    internal_width: float
    internal_height: float
    internal_x_start: float
    internal_x_end: float
    internal_y_start: float
    internal_y_end: float
    internal_z_start: float
    internal_z_end: float
    back_plane_y: float
    back_mount: str
    toe_kick_height: float
    toe_kick_rear_y: float
    toe_kick_front_y: float
    door_count: int

    @classmethod
    def from_spec(cls, spec: FurnitureSpec) -> "CabinetStructure":
        board = spec.board_thickness
        carcass_y_end = spec.depth - spec.door_thickness - spec.door_hinge_gap
        if spec.back_mount == "cover":
            carcass_y_start = spec.back_thickness
            back_plane_y = 0.0
            internal_y_start = carcass_y_start
        else:
            carcass_y_start = 0.0
            back_plane_y = spec.back_offset
            internal_y_start = spec.back_offset + spec.back_thickness
        # Topology-specific legality was checked during proposal admission;
        # geometry consumes the admitted value without silently overriding it.
        toe_kick = spec.toe_kick_height
        return cls(
            furniture_type=spec.furniture_type,
            width=spec.width,
            depth=spec.depth,
            height=spec.height,
            side_depth=carcass_y_end - carcass_y_start,
            carcass_y_start=carcass_y_start,
            carcass_y_end=carcass_y_end,
            internal_width=spec.width - 2 * board,
            internal_height=spec.height - toe_kick - 2 * board,
            internal_x_start=board,
            internal_x_end=spec.width - board,
            internal_y_start=internal_y_start,
            internal_y_end=carcass_y_end,
            internal_z_start=toe_kick + board,
            internal_z_end=spec.height - board,
            back_plane_y=back_plane_y,
            back_mount=spec.back_mount,
            toe_kick_height=toe_kick,
            toe_kick_rear_y=carcass_y_start + spec.toe_kick_reveal_back,
            toe_kick_front_y=carcass_y_end - spec.toe_kick_reveal_front,
            door_count=spec.n_doors,
        )
