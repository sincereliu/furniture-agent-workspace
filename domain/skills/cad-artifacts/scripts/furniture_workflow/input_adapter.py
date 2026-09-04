"""Route flat protocol inputs to the stage that owns each decision."""

from __future__ import annotations

from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent
from furniture_panel_planning.panel_spec import PANEL_SPEC_FIELDS


PANEL_CONFIGURATION_FIELDS = frozenset({"n_doors"})
LAYOUT_CONTEXT_FIELDS = frozenset({"room", "placement"})
MANUFACTURING_SPEC_FIELDS = frozenset(
    {
        "options",
    }
)
PROTOCOL_FIELDS = frozenset(
    {
        "furniture_type",
        "width",
        "depth",
        "height",
        "overall_size",
        "mounting_height",
        "mounting_height_mm",
        "mount_mode",
        "purpose",
        "layout",
        "appearance",
        "structure",
        "manufacturing",
        "constraints",
        "constraint_mappings",
        "room",
        "placement",
        *PANEL_CONFIGURATION_FIELDS,
        *PANEL_SPEC_FIELDS,
        *MANUFACTURING_SPEC_FIELDS,
    }
)


def intent_from_spec(spec: Mapping[str, Any]) -> DesignIntent:
    """Translate only category and finished-envelope values to DesignIntent."""
    data = _reject_legacy_protocol_aliases(dict(spec))
    furniture_type = str(data.get("furniture_type", "")).strip().lower()
    size = data.get("overall_size", {})
    if not isinstance(size, Mapping):
        raise ValueError("overall_size must be an object")
    mount_mode = data.get("mount_mode")
    if mount_mode is not None:
        mount_mode = str(mount_mode).strip().lower()
    return DesignIntent.from_dict(
        {
            "furniture_type": furniture_type,
            "overall_size": {
                "width_mm": size.get("width_mm", data.get("width")),
                "depth_mm": size.get("depth_mm", data.get("depth")),
                "height_mm": size.get("height_mm", data.get("height")),
            },
            "mount_mode": mount_mode,
            "mounting_height_mm": data.get(
                "mounting_height_mm", data.get("mounting_height")
            ),
        }
    )


def stage_inputs_from_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve downstream requests without treating them as confirmed intent."""
    data = _reject_legacy_protocol_aliases(dict(spec))
    unknown = sorted(set(data) - PROTOCOL_FIELDS)
    if unknown:
        raise ValueError("request field has no owning stage: " + ", ".join(unknown))
    raw_layout = data.get("layout", {})
    raw_structure = data.get("structure", {})
    raw_manufacturing = data.get("manufacturing", {})
    if not isinstance(raw_layout, Mapping):
        raise ValueError("layout must be an object")
    if not isinstance(raw_structure, Mapping):
        raise ValueError("structure must be an object")
    if not isinstance(raw_manufacturing, Mapping):
        raise ValueError("manufacturing must be an object")

    unknown_layout = sorted(
        set(raw_layout) - LAYOUT_CONTEXT_FIELDS - PANEL_CONFIGURATION_FIELDS
    )
    if unknown_layout:
        raise ValueError(
            "layout input only accepts independent room placement or panel counts: "
            + ", ".join(unknown_layout)
        )
    panel_parameters = dict(raw_structure)
    for key in PANEL_CONFIGURATION_FIELDS:
        if key in raw_layout:
            panel_parameters[key] = raw_layout[key]
    manufacturing_parameters = dict(raw_manufacturing)

    for key in PANEL_SPEC_FIELDS:
        if key in data:
            panel_parameters[key] = data[key]
    for key in MANUFACTURING_SPEC_FIELDS:
        if key in data:
            manufacturing_parameters[key] = data[key]

    room = data.get("room", raw_layout.get("room"))
    placement = data.get("placement", raw_layout.get("placement"))
    output: dict[str, Any] = {
        "layout": {
            "room": room,
            "placement": placement,
        },
        "panels": {"parameters": panel_parameters},
        "manufacturing": {
            "parameters": manufacturing_parameters,
            "appearance": dict(data.get("appearance", {})),
        },
    }
    purpose = str(data.get("purpose", "")).strip()
    if purpose:
        output["layout"]["purpose"] = purpose
    _route_constraints(data, output)
    return output


def _route_constraints(data: Mapping[str, Any], output: dict[str, Any]) -> None:
    constraints = data.get("constraints", [])
    mappings = data.get("constraint_mappings", {})
    if not isinstance(constraints, list):
        raise ValueError("constraints must be a list")
    if not isinstance(mappings, Mapping):
        raise ValueError("constraint_mappings must be an object")
    informational: list[str] = []
    envelope: list[dict[str, str]] = []
    for constraint in constraints:
        if not isinstance(constraint, str) or not constraint.strip():
            raise ValueError("constraints must contain non-empty strings")
        target = mappings.get(constraint)
        if target is None:
            raise ValueError(f"constraint has no stage mapping: {constraint}")
        target = str(target)
        if target == "informational":
            informational.append(constraint)
            continue
        record = {"text": constraint, "target": target}
        if target == "furniture_type" or target.startswith("overall_size."):
            if not _envelope_target_is_explicit(data, target):
                raise ValueError(f"constraint target is not explicit: {target}")
            envelope.append(record)
        elif target.startswith("layout."):
            field = target.split(".", 1)[1]
            if field in PANEL_CONFIGURATION_FIELDS:
                if field not in output["panels"].get("parameters", {}):
                    raise ValueError(f"constraint target is not explicit: {target}")
                output["panels"].setdefault("constraints", []).append(record)
            else:
                if field not in LAYOUT_CONTEXT_FIELDS or output["layout"].get(field) is None:
                    raise ValueError(f"constraint target is not explicit: {target}")
                output["layout"].setdefault("constraints", []).append(record)
        elif target.startswith(("structure.", "panels.")):
            field = target.split(".", 1)[1]
            if field not in output["panels"].get("parameters", {}):
                raise ValueError(f"constraint target is not explicit: {target}")
            output["panels"].setdefault("constraints", []).append(record)
        elif target.startswith("manufacturing."):
            field = target.split(".", 1)[1]
            if field not in output["manufacturing"].get("parameters", {}):
                raise ValueError(f"constraint target is not explicit: {target}")
            output["manufacturing"].setdefault("constraints", []).append(record)
        else:
            raise ValueError(f"constraint target has no owning stage: {target}")
    stale = sorted(set(mappings) - set(constraints))
    if stale:
        raise ValueError(
            "constraint mapping has no matching constraint: "
            + ", ".join(stale)
        )
    if informational:
        output["informational_constraints"] = informational
    if envelope:
        output["envelope_constraints"] = envelope


def _envelope_target_is_explicit(data: Mapping[str, Any], target: str) -> bool:
    if target == "furniture_type":
        return bool(data.get("furniture_type"))
    field = target.split(".", 1)[1]
    size = data.get("overall_size", {})
    flat_name = {
        "width_mm": "width",
        "depth_mm": "depth",
        "height_mm": "height",
    }.get(field)
    return (
        isinstance(size, Mapping)
        and size.get(field) is not None
    ) or (flat_name is not None and data.get(flat_name) is not None)


def layout_stage_input(stage_inputs: Mapping[str, Any]) -> dict[str, Any]:
    value = stage_inputs.get("layout", {})
    return dict(value) if isinstance(value, Mapping) else {}


def panel_stage_input(stage_inputs: Mapping[str, Any]) -> dict[str, Any]:
    value = stage_inputs.get("panels", {})
    return dict(value) if isinstance(value, Mapping) else {}


def manufacturing_stage_input(stage_inputs: Mapping[str, Any]) -> dict[str, Any]:
    value = stage_inputs.get("manufacturing", {})
    return dict(value) if isinstance(value, Mapping) else {}


def _reject_legacy_protocol_aliases(data: dict[str, Any]) -> dict[str, Any]:
    """Reject historical flat-request aliases now that canonical names are required."""
    if "type" in data:
        raise ValueError("flat requests must use furniture_type; type is no longer accepted")
    return data
