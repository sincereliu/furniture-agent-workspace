"""Panels-planned stage entrypoint."""

from __future__ import annotations

from .cabinet_panel_planner import build_cabinet_panels
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def plan_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure,
) -> list[PanelPlacement]:
    """Create physical panel roles, sizes, and placements."""
    if not isinstance(layout, CabinetStructure):
        raise TypeError(
            "plan_panels requires CabinetStructure; independent room layout is not a valid panel input"
        )
    return build_cabinet_panels(spec, layout)
