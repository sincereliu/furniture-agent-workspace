"""Route flat protocol inputs to the stage that owns each decision."""

from __future__ import annotations

from typing import Any, Mapping

from furniture_layout.project_layout import ProjectLayout
from furniture_panel_planning.cabinet_envelope import CabinetEnvelope
from furniture_panel_planning.panel_spec import PANEL_SPEC_FIELDS


MANUFACTURING_SPEC_FIELDS = frozenset(
    {
        "options",
        "movable_shelf_connector",
        "door_hinge_side",
        "edge_banding",
    }
)
PROTOCOL_FIELDS = frozenset(
    {
        "rooms",
        "purpose",
        "layout",
        "appearance",
        "structure",
        "manufacturing",
        "constraints",
        "constraint_mappings",
        *PANEL_SPEC_FIELDS,
        *MANUFACTURING_SPEC_FIELDS,
    }
)


def stage_inputs_from_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Route panel/manufacturing fields; nested layout cannot carry construction."""
    data = dict(spec)
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

    if raw_layout:
        raise ValueError(
            "layout input does not accept panel construction: "
            + ", ".join(sorted(raw_layout))
        )
    panel_parameters = dict(raw_structure)
    manufacturing_parameters = dict(raw_manufacturing)

    for key in PANEL_SPEC_FIELDS:
        if key in data:
            panel_parameters[key] = data[key]
    for key in MANUFACTURING_SPEC_FIELDS:
        if key in data:
            manufacturing_parameters[key] = data[key]

    output: dict[str, Any] = {
        "layout": {},
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
        if target.startswith("layout."):
            raise ValueError(f"constraint target has no owning stage: {target}")
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


def panel_envelopes_from_layout(layout: ProjectLayout) -> tuple[CabinetEnvelope, ...]:
    """Project a confirmed layout onto the panel-plan envelope contract.

    Rooms, placement, origin, and rotation stay in layout-plan. Panel-plan
    only receives cabinet id, category, and finished width/depth/height.
    """
    if not isinstance(layout, ProjectLayout) or not layout.confirmed:
        raise ValueError("panel planning requires a confirmed project layout")
    units = layout.executable_units()
    if not units:
        raise ValueError("panel planning requires at least one executable cabinet unit")
    return tuple(CabinetEnvelope.from_mapping(unit.to_dict()) for unit in units)


def panel_stage_input(stage_inputs: Mapping[str, Any]) -> dict[str, Any]:
    value = stage_inputs.get("panels", {})
    return dict(value) if isinstance(value, Mapping) else {}


def manufacturing_stage_input(stage_inputs: Mapping[str, Any]) -> dict[str, Any]:
    value = stage_inputs.get("manufacturing", {})
    return dict(value) if isinstance(value, Mapping) else {}
