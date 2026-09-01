"""Panels-planned stage entrypoint."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .cabinet_panel_planner import build_cabinet_panels
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def plan_panels(
    spec: FurnitureSpec,
    layout: CabinetStructure | Any,
) -> list[PanelPlacement]:
    """Create physical panel roles, sizes, and placements."""
    if not isinstance(layout, CabinetStructure):
        # Compatibility for direct pre-refactor callers. The serial workflow
        # never requests or imports a room-layout result.
        spec = FurnitureSpec.from_dict(asdict(spec))
        expected = (
            spec.furniture_type,
            spec.width,
            spec.depth,
            spec.height,
            spec.n_doors,
        )
        received = (
            getattr(layout, "furniture_type", None),
            getattr(layout, "width", None),
            getattr(layout, "depth", None),
            getattr(layout, "height", None),
            getattr(layout, "door_count", None),
        )
        if received != expected:
            raise ValueError("legacy layout does not match the panel specification")
        layout = CabinetStructure.from_spec(spec)
    return build_cabinet_panels(spec, layout)
