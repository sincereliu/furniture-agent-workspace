from __future__ import annotations

from typing import Any


def plan_furniture(spec: dict[str, Any]) -> dict[str, Any]:
    """统一入口：根据 type 路由到 table 或 cabinet 规划器。

    支持的类型: table / floor_cabinet / wall_cabinet / wardrobe
    返回标准 Feature Tree dict，兼容 emitter 和 pipeline 测试。
    """
    furniture_type = str(spec.get("type", "")).strip().lower()

    if furniture_type == "table":
        return plan_table(spec)

    if furniture_type in ("floor_cabinet", "wall_cabinet", "wardrobe"):
        return _plan_cabinet(spec, furniture_type)

    raise ValueError(
        f"Unsupported furniture type {furniture_type!r}; "
        f"supported: table, floor_cabinet, wall_cabinet, wardrobe."
    )


def plan_table(spec: dict[str, Any]) -> dict[str, Any]:
    width = _positive_number(spec, "width")
    depth = _positive_number(spec, "depth")
    height = _positive_number(spec, "height")
    top_thickness = _positive_number(spec, "top_thickness", default=30.0)
    leg_size = _positive_number(spec, "leg_size", default=60.0)
    leg_inset = _non_negative_number(spec, "leg_inset", default=50.0)

    leg_height = height - top_thickness
    if leg_height <= 0:
        raise ValueError("height must be greater than top_thickness")
    if width < 2 * leg_inset + leg_size:
        raise ValueError("width is too small for the selected leg_size and leg_inset")
    if depth < 2 * leg_inset + leg_size:
        raise ValueError("depth is too small for the selected leg_size and leg_inset")

    leg_positions = {
        "leg_back_left": (leg_inset, leg_inset, 0.0),
        "leg_back_right": (width - leg_inset - leg_size, leg_inset, 0.0),
        "leg_front_left": (leg_inset, depth - leg_inset - leg_size, 0.0),
        "leg_front_right": (
            width - leg_inset - leg_size,
            depth - leg_inset - leg_size,
            0.0,
        ),
    }

    features = [
        _box_feature(
            "table_top",
            size=(width, depth, top_thickness),
            position=(0.0, 0.0, leg_height),
        )
    ]
    features.extend(
        _box_feature(
            feature_id,
            size=(leg_size, leg_size, leg_height),
            position=position,
            depends_on=["table_top"],
        )
        for feature_id, position in leg_positions.items()
    )

    return {
        "schema_version": 1,
        "furniture_type": "table",
        "units": "mm",
        "coordinate_system": {
            "origin": "lower-left-rear-ground-corner",
            "x": "left-to-right",
            "y": "rear-to-front",
            "z": "up",
        },
        "parameters": {
            "width": width,
            "depth": depth,
            "height": height,
            "top_thickness": top_thickness,
            "leg_size": leg_size,
            "leg_inset": leg_inset,
        },
        "features": features,
        "root": {
            "id": "table_assembly",
            "type": "compound",
            "children": [feature["id"] for feature in features],
        },
    }


def _plan_cabinet(spec: dict[str, Any], furniture_type: str) -> dict[str, Any]:
    """委托给新的 CabinetPlanner + 模板架构，返回 Feature Tree dict。"""
    from furniture_schema.spec import FurnitureSpec
    from furniture_planner.cabinet_planner import CabinetPlanner
    from furniture_planner.templates.floor_cabinet import FloorCabinet
    from furniture_planner.templates.wall_cabinet import WallCabinet
    from furniture_planner.templates.wardrobe import Wardrobe

    fspec = FurnitureSpec.from_dict(spec)

    template_map = {
        "floor_cabinet": FloorCabinet,
        "wall_cabinet": WallCabinet,
        "wardrobe": Wardrobe,
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


def _box_feature(
    feature_id: str,
    *,
    size: tuple[float, float, float],
    position: tuple[float, float, float],
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": feature_id,
        "type": "box",
        "size": {"x": size[0], "y": size[1], "z": size[2]},
        "position": {"x": position[0], "y": position[1], "z": position[2]},
        "depends_on": list(depends_on or []),
    }


def _positive_number(
    spec: dict[str, Any], key: str, *, default: float | None = None
) -> float:
    value = _number(spec, key, default=default)
    if value <= 0:
        raise ValueError(f"{key} must be greater than zero")
    return value


def _non_negative_number(
    spec: dict[str, Any], key: str, *, default: float | None = None
) -> float:
    value = _number(spec, key, default=default)
    if value < 0:
        raise ValueError(f"{key} must be zero or greater")
    return value


def _number(
    spec: dict[str, Any], key: str, *, default: float | None = None
) -> float:
    raw_value = spec.get(key, default)
    if raw_value is None or isinstance(raw_value, bool):
        raise ValueError(f"{key} must be a number")
    try:
        return float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc
