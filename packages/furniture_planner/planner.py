from __future__ import annotations

from typing import Any


def plan_furniture(spec: dict[str, Any]) -> dict[str, Any]:
    """统一入口：根据 type 路由到柜体规划器。

    支持的类型: floor_cabinet / wall_cabinet
    返回标准 Feature Tree dict，兼容 emitter 和 pipeline 测试。
    """
    furniture_type = str(spec.get("type", "")).strip().lower()

    if furniture_type in ("floor_cabinet", "wall_cabinet"):
        return _plan_cabinet(spec, furniture_type)

    raise ValueError(
        f"Unsupported furniture type {furniture_type!r}; "
        f"supported: floor_cabinet, wall_cabinet."
    )


def _plan_cabinet(spec: dict[str, Any], furniture_type: str) -> dict[str, Any]:
    """委托给 CabinetPlanner + 模板架构，返回 Feature Tree dict。"""
    from furniture_schema.spec import FurnitureSpec
    from furniture_planner.cabinet_planner import CabinetPlanner
    from furniture_planner.templates.floor_cabinet import FloorCabinet
    from furniture_planner.templates.wall_cabinet import WallCabinet

    fspec = FurnitureSpec.from_dict(spec)

    template_map = {
        "floor_cabinet": FloorCabinet,
        "wall_cabinet": WallCabinet,
    }
    template_cls = template_map[furniture_type]
    shelf_count = int(spec.get("shelf_count", 4))
    n_doors = int(spec.get("n_doors", 2))
    template = template_cls(shelf_count=shelf_count, n_doors=n_doors)

    planner = CabinetPlanner(fspec)
    template.build(planner)

    features = [
        {
            "id": p.id,
            "type": "box",
            "size": {"x": p.size_x, "y": p.size_y, "z": p.size_z},
            "position": {"x": p.pos_x, "y": p.pos_y, "z": p.pos_z},
            "depends_on": list(p.depends_on),
        }
        for p in planner._placements
    ]

    return {
        "schema_version": 1,
        "furniture_type": furniture_type,
        "units": "mm",
        "coordinate_system": {
            "origin": "lower-left-rear-ground-corner",
            "x": "left-to-right",
            "y": "rear-to-front",
            "z": "up",
        },
        "parameters": {
            "width": fspec.width,
            "depth": fspec.depth,
            "height": fspec.height,
            "board_thickness": fspec.board_thickness,
        },
        "features": features,
        "root": {
            "id": f"{furniture_type}_assembly",
            "type": "compound",
            "children": [f["id"] for f in features],
        },
    }