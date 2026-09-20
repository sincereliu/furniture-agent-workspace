"""Route flat protocol inputs to the stage that owns each decision."""

from __future__ import annotations

from typing import Any, Mapping

from furniture_layout.project_layout import ProjectLayout, single_cabinet_layout
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
        "furniture_category",
        "furniture_type",
        "width",
        "depth",
        "height",
        "finished_envelope",
        "overall_size",
        "rooms",
        "origin_z_mm",
        "hanging_height",
        "hanging_height_mm",
        "mounting_height",
        "mounting_height_mm",
        "hanging_mode",
        "mount_mode",
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
_ENVELOPE_TARGETS = frozenset(
    {
        "furniture_category",
        "furniture_type",
    }
)
_ENVELOPE_PREFIXES = ("finished_envelope.", "overall_size.")


def layout_from_spec(spec: Mapping[str, Any]) -> ProjectLayout:
    """Expand a flat cabinet request into a one-room layout."""
    data = _reject_legacy_protocol_aliases(dict(spec))
    if isinstance(data.get("rooms"), list):
        return ProjectLayout.from_source({"rooms": data["rooms"]})
    furniture_category = str(
        _first_present(data, "furniture_category", "furniture_type") or ""
    ).strip().lower()
    size = _first_present(data, "finished_envelope", "overall_size") or {}
    if size is None:
        size = {}
    if not isinstance(size, Mapping):
        raise ValueError("finished_envelope must be an object")
    width = size.get("width_mm", data.get("width"))
    depth = size.get("depth_mm", data.get("depth"))
    height = size.get("height_mm", data.get("height"))
    origin_z = _first_present(
        data,
        "origin_z_mm",
        "hanging_height_mm",
        "hanging_height",
        "mounting_height_mm",
        "mounting_height",
    )
    hanging_mode = _first_present(data, "hanging_mode", "mount_mode")
    if hanging_mode is not None:
        hanging_mode = str(hanging_mode).strip().lower()
        if hanging_mode in {"free_height", "free_hanging_height"}:
            hanging_mode = "free_hanging_height"
        elif hanging_mode == "flush_ceiling":
            origin_z = None
    if width is None or depth is None or height is None:
        raise ValueError("width, depth and height are required")
    return single_cabinet_layout(
        furniture_category=furniture_category,
        width=float(width),
        depth=float(depth),
        height=float(height),
        origin_z_mm=None if origin_z is None else float(origin_z),
    )


def stage_inputs_from_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Route panel/manufacturing fields; nested layout cannot carry construction."""
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
        if target in _ENVELOPE_TARGETS or target.startswith(_ENVELOPE_PREFIXES):
            if not _envelope_target_is_explicit(data, target):
                raise ValueError(f"constraint target is not explicit: {target}")
            envelope.append(record)
        elif target.startswith("layout."):
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
    if envelope:
        output["envelope_constraints"] = envelope


def _envelope_target_is_explicit(data: Mapping[str, Any], target: str) -> bool:
    if target in _ENVELOPE_TARGETS:
        return bool(_first_present(data, "furniture_category", "furniture_type"))
    field = target.split(".", 1)[1]
    size = _first_present(data, "finished_envelope", "overall_size") or {}
    flat_name = {
        "width_mm": "width",
        "depth_mm": "depth",
        "height_mm": "height",
    }.get(field)
    return (
        isinstance(size, Mapping)
        and size.get(field) is not None
    ) or (flat_name is not None and data.get(flat_name) is not None)


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


def _first_present(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _reject_legacy_protocol_aliases(data: dict[str, Any]) -> dict[str, Any]:
    """Reject historical flat-request aliases now that canonical names are required."""
    if "type" in data:
        raise ValueError(
            "flat requests must use furniture_category; type is no longer accepted"
        )
    return data
