from __future__ import annotations

from typing import Any

from furniture_layout.project_layout import ProjectLayout
from furniture_panel_planning.cabinet_envelope import CabinetEnvelope
from furniture_panel_planning.cabinet_identity import index_by_role
from furniture_panel_planning.panel_spec import FurnitureSpec


def by_role(items):
    """Index placements or manufacturing panels by cabinet-local role."""
    return index_by_role(items)


def _bind_inherited_stock(values: dict[str, Any], overrides: dict[str, Any]) -> None:
    """Keep test fixtures aligned with the shop process card."""
    board = values["board_thickness"]
    if "door_thickness" not in overrides:
        values["door_thickness"] = board
    if "drawer_bottom_thickness" not in overrides:
        values["drawer_bottom_thickness"] = board
    if "drawer_back_thickness" not in overrides:
        values["drawer_back_thickness"] = board
    if "back_thickness" not in overrides:
        values["back_thickness"] = (
            board if values.get("back_mount") == "insert" else 9.0
        )


def _even_shelves(count: int, *, height: float, board: float, toe_kick: float):
    """均分 count 层固定层板：所有格子（含顶格、底格）净高相等。"""
    internal_height = height - toe_kick - 2 * board
    gap = (internal_height - count * board) / (count + 1)
    shelves = [{"shelf_type": "fixed", "gap_below_mm": gap} for _ in range(count)]
    return shelves, gap


def panel_parameters(furniture_category: str = "floor_cabinet", **overrides: Any) -> dict[str, Any]:
    """Return a complete proposal owned only by the test suite."""
    wall = furniture_category == "wall_cabinet"
    values = {
        "board_thickness": 18.0, "back_thickness": 9.0, "door_thickness": 18.0,
        "toe_kick_height": 0.0 if wall else 50.0, "back_offset": 18.0,
        "front_face_margin": 1.5, "front_gap": 2.0,
        "groove_depth": 6.0, "groove_clearance": 1.0,
        "toe_kick_reveal_front": 0.0 if wall else 1.0,
        "toe_kick_reveal_back": 0.0 if wall else 30.0,
        "toe_kick_support_count": 0 if wall else 1, "back_mount": "groove", "back_rail_height": 70.0,
        "drawer_count": 0, "drawer_side_clearance": 13.0, "drawer_layer_gap": 1.5,
        "drawer_bottom_thickness": 18.0, "drawer_back_thickness": 18.0,
        "drawer_back_clearance": 0.0, "n_doors": 2,
        "shelves": [], "top_gap_mm": 0.0,
    }
    values.update(overrides)
    _bind_inherited_stock(values, overrides)
    return values


def _fill_shelves(overrides: dict[str, Any], *, wall: bool, height: float) -> None:
    """根据测试指定的层数生成均分层板与顶格净高。"""
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


def layout_rooms(
    *, furniture_category: str = "floor_cabinet", width: float = 800,
    depth: float = 600, height: float = 1000, origin_z_mm: float = 0,
) -> list[dict[str, Any]]:
    """Explicit room proposal used only by tests; no production defaults."""
    return [{
        "id": "room", "name": "测试房间",
        "width_mm": 4000, "depth_mm": 3000, "height_mm": 3200,
        "items": [{
            "id": "cabinet_1", "label": "cabinet_1", "category": "柜体",
            "furniture_category": furniture_category,
            "width": width, "depth": depth, "height": height,
            "placement": {"mode": "wall", "host_wall": "north",
                          "origin_z_mm": origin_z_mm},
        }],
    }]


def cabinet_layout(*, confirmed: bool = False, **dimensions: Any) -> ProjectLayout:
    layout = ProjectLayout.from_source({"rooms": layout_rooms(**dimensions)})
    return layout.confirm() if confirmed else layout


def cabinet_data(furniture_category: str = "floor_cabinet", **overrides: Any) -> dict[str, Any]:
    wall = furniture_category == "wall_cabinet"
    overrides = dict(overrides)
    height = overrides.get("height", 900 if wall else 1000)
    _fill_shelves(overrides, wall=wall, height=height)
    values = {
        "rooms": layout_rooms(
            furniture_category=furniture_category,
            width=overrides.pop("width", 800),
            depth=overrides.pop("depth", 350 if wall else 600),
            height=overrides.pop("height", height),
            origin_z_mm=2000 if wall else 0,
        ),
        "movable_shelf_connector": "two_in_one",
        "door_hinge_side": None,
        **panel_parameters(furniture_category),
    }
    values.update(overrides)
    _bind_inherited_stock(values, overrides)
    return values


def cabinet_envelope(
    cabinet_id: str = "cabinet_1",
    *,
    furniture_category: str = "floor_cabinet",
    width: float = 800,
    depth: float = 600,
    height: float = 1000,
) -> CabinetEnvelope:
    return CabinetEnvelope(
        id=cabinet_id,
        furniture_category=furniture_category,
        width=width,
        depth=depth,
        height=height,
    )


def confirmed_layout(
    *,
    furniture_category: str = "floor_cabinet",
    width: float = 800,
    depth: float = 600,
    height: float = 1000,
    origin_z_mm: float = 0,
) -> ProjectLayout:
    return cabinet_layout(
        furniture_category=furniture_category,
        width=width,
        depth=depth,
        height=height,
        origin_z_mm=origin_z_mm,
        confirmed=True,
    )


def furniture_spec(
    *, furniture_category: str = "floor_cabinet", width: float = 800,
    depth: float = 600, height: float = 1000, **overrides: Any,
) -> FurnitureSpec:
    wall = furniture_category == "wall_cabinet"
    overrides = dict(overrides)
    _fill_shelves(overrides, wall=wall, height=height)
    return FurnitureSpec(
        furniture_category=furniture_category, width=width, depth=depth, height=height,
        **panel_parameters(furniture_category, **overrides),
    )
