"""Translate protocol inputs to and from the confirmed design contract."""

from __future__ import annotations

from typing import Any

from furniture_design_intent.design_intent import DesignIntent
from furniture_design_intent.design_spec import (
    CABINET_PRESETS,
    FurnitureSpec,
    resolve_back_mount,
)


LAYOUT_SPEC_FIELDS = (
    "shelf_count",
    "n_doors",
    "toe_kick_height",
)
STRUCTURE_SPEC_FIELDS = (
    "board_thickness",
    "back_thickness",
    "door_thickness",
    "back_offset",
    "door_margin",
    "door_hinge_gap",
    "toe_kick_reveal_front",
    "toe_kick_reveal_back",
    "toe_kick_support_count",
    "back_mount",
    "hinge_brand",
    "hinge_variant",
    "hinge_overlay",
    "hinge_angle",
    "options",
)
GROOVE_SPEC_FIELDS = (
    "groove_depth",
    "groove_clearance",
    "back_rail_height",
)


def intent_from_spec(spec: dict[str, Any]) -> DesignIntent:
    """将标准化的扁平可执行 JSON 转换为 DesignIntent。"""
    data = dict(spec)
    furniture_type = str(
        data.get("type", data.get("furniture_type", ""))
    ).strip().lower()
    size = data.get("overall_size", {})
    if not isinstance(size, dict):
        raise ValueError("overall_size must be an object")

    layout = dict(data.get("layout", {}))
    for key in (
        "shelf_count",
        "n_doors",
        "toe_kick_height",
        "room",
        "placement",
    ):
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
        "constraint_mappings",
        "assumptions",
        "unresolved",
        "confirmed",
        "schema_version",
        "shelf_count",
        "n_doors",
        "toe_kick_height",
        "room",
        "placement",
    }
    for key, value in data.items():
        if key not in reserved:
            structure[key] = value

    normalized_input: dict[str, Any] = {
        "type": furniture_type,
        **structure,
        **layout,
    }
    for nested_key, flat_key in (
        ("width_mm", "width"),
        ("depth_mm", "depth"),
        ("height_mm", "height"),
    ):
        value = size.get(nested_key, data.get(flat_key))
        if value is not None:
            normalized_input[flat_key] = value
    normalized_spec = FurnitureSpec.from_dict(normalized_input)
    assumptions = dict(data.get("assumptions", {}))

    def materialize_default(
        values: dict[str, Any],
        section: str,
        key: str,
    ) -> None:
        if values.get(key) is not None:
            return
        value = getattr(normalized_spec, key)
        values[key] = dict(value) if isinstance(value, dict) else value
        assumptions.setdefault(
            f"{section}.{key}",
            _default_source(furniture_type, key),
        )

    for key in LAYOUT_SPEC_FIELDS:
        materialize_default(layout, "layout", key)
    for key in STRUCTURE_SPEC_FIELDS:
        materialize_default(structure, "structure", key)
    if resolve_back_mount(
        normalized_spec.back_mount,
        normalized_spec.back_thickness,
        normalized_spec.board_thickness,
    ) == "groove":
        for key in GROOVE_SPEC_FIELDS:
            materialize_default(structure, "structure", key)

    dimensions: dict[str, Any] = {}
    for nested_key, flat_key in (
        ("width_mm", "width"),
        ("depth_mm", "depth"),
        ("height_mm", "height"),
    ):
        value = size.get(nested_key, data.get(flat_key))
        if value is None:
            value = getattr(normalized_spec, flat_key)
            assumptions.setdefault(
                f"overall_size.{nested_key}",
                _default_source(furniture_type, flat_key),
            )
        dimensions[nested_key] = value

    return DesignIntent.from_dict(
        {
            "furniture_type": furniture_type,
            "overall_size": dimensions,
            "purpose": data.get("purpose", ""),
            "layout": layout,
            "appearance": data.get("appearance", {}),
            "structure": structure,
            "constraints": data.get("constraints", []),
            "constraint_mappings": data.get("constraint_mappings", {}),
            "assumptions": assumptions,
            "unresolved": data.get("unresolved", []),
            "schema_version": data.get("schema_version", 1),
        }
    )


def spec_from_intent(intent: DesignIntent) -> FurnitureSpec:
    """从已确认的设计意图构建可执行规格。"""
    dimensions = (
        intent.overall_size.width_mm,
        intent.overall_size.depth_mm,
        intent.overall_size.height_mm,
    )
    if any(value is None for value in dimensions):
        raise ValueError(
            "confirmed DesignIntent requires width_mm, depth_mm, and height_mm"
        )
    data: dict[str, Any] = {
        "type": intent.furniture_type,
        "width": intent.overall_size.width_mm,
        "depth": intent.overall_size.depth_mm,
        "height": intent.overall_size.height_mm,
    }
    data.update(intent.structure)
    data.update(intent.layout)
    return FurnitureSpec.from_dict(data)


def materialize_intent_defaults(intent: DesignIntent) -> DesignIntent:
    """Make every downstream default visible before intent confirmation."""
    payload = intent.to_dict()
    layout = dict(intent.layout)
    structure = dict(intent.structure)
    normalized_input: dict[str, Any] = {
        "type": intent.furniture_type,
        **structure,
        **layout,
    }
    for field_name, value in (
        ("width", intent.overall_size.width_mm),
        ("depth", intent.overall_size.depth_mm),
        ("height", intent.overall_size.height_mm),
    ):
        if value is not None:
            normalized_input[field_name] = value
    try:
        normalized_spec = FurnitureSpec.from_dict(normalized_input)
    except (TypeError, ValueError):
        # Validation owns malformed-input reporting. Defaults are materialized
        # only after a typed FurnitureSpec can be formed safely.
        return intent

    assumptions = dict(intent.assumptions)

    def materialize(
        values: dict[str, Any],
        section: str,
        key: str,
    ) -> None:
        if values.get(key) is not None:
            return
        value = getattr(normalized_spec, key)
        values[key] = dict(value) if isinstance(value, dict) else value
        assumptions.setdefault(
            f"{section}.{key}",
            _default_source(intent.furniture_type, key),
        )

    for key in LAYOUT_SPEC_FIELDS:
        materialize(layout, "layout", key)
    for key in STRUCTURE_SPEC_FIELDS:
        materialize(structure, "structure", key)
    if resolve_back_mount(
        normalized_spec.back_mount,
        normalized_spec.back_thickness,
        normalized_spec.board_thickness,
    ) == "groove":
        for key in GROOVE_SPEC_FIELDS:
            materialize(structure, "structure", key)

    payload["layout"] = layout
    payload["structure"] = structure
    payload["assumptions"] = assumptions
    return DesignIntent.from_dict(payload)


def _default_source(furniture_type: str, key: str) -> str:
    preset = CABINET_PRESETS.get(furniture_type, {})
    if key in preset:
        return f"defaulted from {furniture_type} category preset"
    return "defaulted from FurnitureSpec system default"
