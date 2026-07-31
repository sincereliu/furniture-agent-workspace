"""Panels-planned stage entrypoint."""

from __future__ import annotations

from dataclasses import asdict

from furniture_layout.layout_planning import CabinetLayout

from .cabinet_panel_planner import build_cabinet_panels
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def plan_panels(
    spec: FurnitureSpec,
    layout: CabinetLayout | CabinetStructure,
) -> list[PanelPlacement]:
    """Stage 3: create physical panel roles, sizes, and placements."""
    if isinstance(layout, CabinetLayout):
        spec = FurnitureSpec.from_dict(asdict(spec))
        if (
            spec.furniture_type,
            spec.width,
            spec.depth,
            spec.height,
            spec.shelf_count,
            spec.n_doors,
        ) != (
            layout.furniture_type,
            layout.width,
            layout.depth,
            layout.height,
            layout.shelf_count,
            layout.door_count,
        ):
            raise ValueError("panel specification must preserve the approved layout")
        layout = CabinetStructure.from_spec(spec)
    return build_cabinet_panels(spec, layout)
