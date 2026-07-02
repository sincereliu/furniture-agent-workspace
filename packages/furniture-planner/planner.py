from __future__ import annotations

from typing import Any


def plan_furniture(spec: dict[str, Any]) -> dict[str, Any]:
    furniture_type = str(spec.get("type", "")).strip().lower()
    if furniture_type != "table":
        raise ValueError(
            f"Unsupported furniture type {furniture_type!r}; the first vertical slice supports 'table'."
        )
    return plan_table(spec)


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
        "leg_front_left": (leg_inset, leg_inset, 0.0),
        "leg_front_right": (width - leg_inset - leg_size, leg_inset, 0.0),
        "leg_back_left": (leg_inset, depth - leg_inset - leg_size, 0.0),
        "leg_back_right": (
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
            "origin": "lower-left-ground-corner",
            "x": "left-to-right",
            "y": "front-to-back",
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
