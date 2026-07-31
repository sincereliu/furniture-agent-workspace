"""Turn a confirmed cabinet layout into physical panel placements.

Now delegates to the topology solver instead of hardcoding panel positions.
The topology YAML defines what panels exist and their semantic faces;
the solver computes exact positions, sizes, and face directions.
"""

from __future__ import annotations

from furniture_design_intent.design_spec import FurnitureSpec
from furniture_layout.layout_planning import CabinetLayout

from .panel_models import PanelPlacement
from .topology_solver import solve_panel_placements


def build_cabinet_panels(
    spec: FurnitureSpec,
    layout: CabinetLayout,
) -> list[PanelPlacement]:
    """Stage 3: create physical panel roles, sizes, and placements.

    Delegates to the universal topology solver.  All panel positions,
    dimensions, and face directions are computed from the topology YAML
    for the spec's furniture type.
    """
    return solve_panel_placements(spec, layout)
