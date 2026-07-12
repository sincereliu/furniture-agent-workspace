"""Layout-stage planning for supported cabinet families."""

from __future__ import annotations

from furniture_design_intent.design_spec import FurnitureSpec
from furniture_panel_planning.panel_models import PanelPlacement

from .layout_planning import CabinetPlanner
from .layout_template import build_from_blueprint

SUPPORTED_TYPES = {"floor_cabinet", "wall_cabinet"}

def plan_layout(spec: FurnitureSpec) -> list[PanelPlacement]:
    """Stage 2: resolve cabinet spatial organization and placements."""
    if spec.furniture_type not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES))
        raise ValueError(
            f"Unsupported cabinet type: {spec.furniture_type!r}; supported: {supported}"
        )

    planner = CabinetPlanner(spec)
    build_from_blueprint(planner)
    return list(planner._placements)
