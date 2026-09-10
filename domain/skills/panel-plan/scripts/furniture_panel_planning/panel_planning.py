"""Panels-planned stage entrypoint."""

from __future__ import annotations

from .cabinet_identity import DEFAULT_CABINET_ID
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure
from .topology_solver import solve_panel_placements


def plan_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
    cabinet_id: str = DEFAULT_CABINET_ID,
) -> list[PanelPlacement]:
    """Create physical panel roles, sizes, and placements."""
    if not isinstance(layout, CabinetStructure):
        raise TypeError(
            "plan_panels requires CabinetStructure; independent room layout is not a valid panel input"
        )
    return solve_panel_placements(spec, layout, cabinet_id=cabinet_id)
