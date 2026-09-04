from __future__ import annotations

from typing import Any

from furniture_panel_planning.panel_spec import FurnitureSpec


def _even_shelves(count: int, *, height: float, board: float, toe_kick: float):
    """均分 count 层固定层板：所有格子（含顶格、底格）净高相等。"""
    internal_height = height - toe_kick - 2 * board
    gap = (internal_height - count * board) / (count + 1)
    shelves = [{"shelf_type": "fixed", "gap_below_mm": gap} for _ in range(count)]
    return shelves, gap


def panel_parameters(furniture_type: str = "floor_cabinet", **overrides: Any) -> dict[str, Any]:
    """Return a complete proposal owned only by the test suite."""
    wall = furniture_type == "wall_cabinet"
    values = {
        "board_thickness": 18.0, "back_thickness": 9.0, "door_thickness": 18.0,
        "toe_kick_height": 0.0 if wall else 50.0, "back_offset": 18.0,
        "front_face_margin": 1.5, "door_hinge_gap": 2.0,
        "groove_depth": 6.0, "groove_clearance": 1.0,
        "toe_kick_reveal_front": 0.0 if wall else 1.0,
        "toe_kick_reveal_back": 0.0 if wall else 30.0,
        "toe_kick_support_count": None, "back_mount": "auto", "back_rail_height": 70.0,
        "drawer_count": 0, "drawer_side_clearance": 13.0, "drawer_layer_gap": 1.5,
        "drawer_bottom_thickness": 18.0, "drawer_back_thickness": 18.0,
        "drawer_back_clearance": 0.0, "n_doors": 2,
        "door_hinge_side": None,
        "movable_shelf_connector": "two_in_one",
        "shelves": [], "top_gap_mm": 0.0,
    }
    values.update(overrides)
    return values


def _fill_shelves(overrides: dict[str, Any], *, wall: bool, height: float) -> None:
    """把 shelf_count 兼容地转成 shelves + top_gap_mm（测试夹具便利）。"""
    if "shelves" in overrides or "top_gap_mm" in overrides:
        return
    count = overrides.pop("shelf_count", 1 if wall else 4)
    if count <= 0:
        return
    params = panel_parameters("wall_cabinet" if wall else "floor_cabinet")
    board = overrides.get("board_thickness", params["board_thickness"])
    toe_kick = overrides.get("toe_kick_height", params["toe_kick_height"])
    shelves, top_gap = _even_shelves(count, height=height, board=board, toe_kick=toe_kick)
    overrides["shelves"] = shelves
    overrides["top_gap_mm"] = top_gap


def cabinet_data(furniture_type: str = "floor_cabinet", **overrides: Any) -> dict[str, Any]:
    wall = furniture_type == "wall_cabinet"
    overrides = dict(overrides)
    height = overrides.get("height", 900 if wall else 1000)
    _fill_shelves(overrides, wall=wall, height=height)
    values = {
        "furniture_type": furniture_type, "width": 800, "depth": 350 if wall else 600,
        "height": height, **panel_parameters(furniture_type),
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
    wall = furniture_type == "wall_cabinet"
    overrides = dict(overrides)
    _fill_shelves(overrides, wall=wall, height=height)
    return FurnitureSpec(
        furniture_type=furniture_type, width=width, depth=depth, height=height,
        **panel_parameters(furniture_type, **overrides),
    )
