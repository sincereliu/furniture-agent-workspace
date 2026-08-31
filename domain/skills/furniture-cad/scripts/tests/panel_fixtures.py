from __future__ import annotations

from typing import Any

from furniture_panel_planning.panel_spec import FurnitureSpec


def panel_parameters(furniture_type: str = "floor_cabinet", **overrides: Any) -> dict[str, Any]:
    """Return a complete proposal owned only by the test suite."""
    wall = furniture_type == "wall_cabinet"
    values = {
        "board_thickness": 18.0, "back_thickness": 9.0, "door_thickness": 18.0,
        "toe_kick_height": 0.0 if wall else 50.0, "back_offset": 18.0,
        "door_margin": 1.5, "door_hinge_gap": 2.0,
        "groove_depth": 6.0, "groove_clearance": 1.0,
        "toe_kick_reveal_front": 0.0 if wall else 1.0,
        "toe_kick_reveal_back": 0.0 if wall else 30.0,
        "toe_kick_support_count": None, "back_mount": "auto", "back_rail_height": 70.0,
        "drawer_count": 0, "drawer_side_clearance": 13.0, "drawer_layer_gap": 1.5,
        "drawer_bottom_thickness": 18.0, "drawer_back_thickness": 18.0,
        "drawer_back_clearance": 0.0, "shelf_count": 1 if wall else 4, "n_doors": 2,
        "door_hinge_side": None,
        "movable_shelf_connector": "two_in_one",
    }
    values.update(overrides)
    return values


def cabinet_data(furniture_type: str = "floor_cabinet", **overrides: Any) -> dict[str, Any]:
    wall = furniture_type == "wall_cabinet"
    values = {
        "type": furniture_type, "width": 800, "depth": 350 if wall else 600,
        "height": 900 if wall else 1000, **panel_parameters(furniture_type),
    }
    if wall:
        values["mount_mode"] = "free_height"
        values["mounting_height"] = 2000
    values.update(overrides)
    return values


def furniture_spec(
    *, furniture_type: str = "floor_cabinet", width: float = 800,
    depth: float = 600, height: float = 1000, **overrides: Any,
) -> FurnitureSpec:
    return FurnitureSpec(
        furniture_type=furniture_type, width=width, depth=depth, height=height,
        **panel_parameters(furniture_type, **overrides),
    )
