from __future__ import annotations

from typing import Any

from furniture_panel_planning.panel_spec import FurnitureSpec, PANEL_PROFILES


def furniture_spec(
    *,
    furniture_type: str = "floor_cabinet",
    width: float = 800,
    depth: float = 600,
    height: float = 1000,
    **overrides: Any,
) -> FurnitureSpec:
    """Build a complete structured test spec from an explicit versioned profile."""
    profile_name = (
        "wall_cabinet_standard_v1"
        if furniture_type == "wall_cabinet"
        else "floor_cabinet_standard_v1"
    )
    values = {
        key: value
        for key, value in PANEL_PROFILES[profile_name].items()
        if key != "furniture_type"
    }
    values.update(overrides)
    return FurnitureSpec(
        furniture_type=furniture_type,
        width=width,
        depth=depth,
        height=height,
        **values,
    )
