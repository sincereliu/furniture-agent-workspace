"""Translate between protocol-shaped input and the confirmed design contract."""

from __future__ import annotations

from typing import Any

from .design_intent import DesignIntent
from .design_spec import FurnitureSpec


def intent_from_spec(spec: dict[str, Any]) -> DesignIntent:
    """Convert the maintained flat executable JSON into a DesignIntent."""
    data = dict(spec)
    furniture_type = str(
        data.get("type", data.get("furniture_type", ""))
    ).strip().lower()
    size = data.get("overall_size", {})
    normalized_spec = FurnitureSpec.from_dict({**data, "type": furniture_type})

    def dimension(nested_key: str, flat_key: str, fallback: float) -> Any:
        value = size.get(nested_key, data.get(flat_key))
        return fallback if value is None else value

    layout = dict(data.get("layout", {}))
    for key in ("shelf_count", "n_doors", "toe_kick_height"):
        if key in data:
            layout[key] = data[key]

    structure = dict(data.get("structure", {}))
    reserved = {
        "type",
        "furniture_type",
        "width",
        "depth",
        "height",
        "overall_size",
        "purpose",
        "layout",
        "appearance",
        "structure",
        "constraints",
        "assumptions",
        "unresolved",
        "confirmed",
        "schema_version",
        "shelf_count",
        "n_doors",
        "toe_kick_height",
    }
    for key, value in data.items():
        if key not in reserved:
            structure[key] = value

    return DesignIntent.from_dict(
        {
            "furniture_type": furniture_type,
            "overall_size": {
                "width_mm": dimension(
                    "width_mm", "width", normalized_spec.width
                ),
                "depth_mm": dimension(
                    "depth_mm", "depth", normalized_spec.depth
                ),
                "height_mm": dimension(
                    "height_mm", "height", normalized_spec.height
                ),
            },
            "purpose": data.get("purpose", ""),
            "layout": layout,
            "appearance": data.get("appearance", {}),
            "structure": structure,
            "constraints": data.get("constraints", []),
            "assumptions": data.get("assumptions", {}),
            "unresolved": data.get("unresolved", []),
            "schema_version": data.get("schema_version", 1),
        }
    )


def spec_from_intent(intent: DesignIntent) -> FurnitureSpec:
    """Build the executable specification from one confirmed design intent."""
    data: dict[str, Any] = {
        "type": intent.furniture_type,
        "width": intent.overall_size.width_mm,
        "depth": intent.overall_size.depth_mm,
        "height": intent.overall_size.height_mm,
    }
    data.update(intent.structure)
    data.update(intent.layout)
    return FurnitureSpec.from_dict(data)
