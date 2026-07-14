"""Panels-planned stage entrypoint."""

from __future__ import annotations

from furniture_design_intent.design_spec import FurnitureSpec
from furniture_layout.layout_planning import CabinetLayout

from .cabinet_panel_planner import build_cabinet_panels
from .panel_models import PanelPlacement


def plan_panels(
    spec: FurnitureSpec,
    layout: CabinetLayout,
) -> list[PanelPlacement]:
    """Stage 3: create physical panel roles, sizes, and placements."""
    return build_cabinet_panels(spec, layout)
