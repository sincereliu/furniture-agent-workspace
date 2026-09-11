"""Cabinet instance identity and panel parent/child ownership."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

DEFAULT_CABINET_ID = "cabinet_1"
PANEL_ID_SEPARATOR = "__"
_CABINET_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def admit_cabinet_id(value: Any, *, fallback: str = DEFAULT_CABINET_ID) -> str:
    """Admit an optional structured cabinet id, or use a deterministic fallback."""
    if value is None:
        return _validate_cabinet_id(fallback)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("cabinet_id must be a non-empty identifier")
    return _validate_cabinet_id(value.strip())


def _validate_cabinet_id(cabinet_id: str) -> str:
    if not _CABINET_ID_PATTERN.fullmatch(cabinet_id) or PANEL_ID_SEPARATOR in cabinet_id:
        raise ValueError(
            "cabinet_id must be a Python identifier and must not contain '__'"
        )
    return cabinet_id


def qualify_panel_id(cabinet_id: str, role: str) -> str:
    """Return the globally unique panel id for a cabinet-local role."""
    if not role:
        raise ValueError("panel role is required")
    if role.startswith(f"{cabinet_id}{PANEL_ID_SEPARATOR}"):
        return role
    if PANEL_ID_SEPARATOR in role:
        return role
    return f"{cabinet_id}{PANEL_ID_SEPARATOR}{role}"


def panel_role(panel_id: str) -> str:
    """Return the cabinet-local role from a qualified or legacy panel id."""
    if PANEL_ID_SEPARATOR in panel_id:
        return panel_id.split(PANEL_ID_SEPARATOR, 1)[1]
    return panel_id


def panel_cabinet_id(panel_id: str) -> str | None:
    if PANEL_ID_SEPARATOR not in panel_id:
        return None
    return panel_id.split(PANEL_ID_SEPARATOR, 1)[0]


def index_by_role(items: Iterable[Any], *, parent_id: str | None = None) -> dict[str, Any]:
    """Index panels by cabinet-local role, optionally within one parent."""
    indexed: dict[str, Any] = {}
    for item in items:
        item_parent = getattr(item, "parent_id", "") or ""
        if parent_id is not None and item_parent and item_parent != parent_id:
            continue
        role = getattr(item, "role", "") or panel_role(
            getattr(item, "id", None) or getattr(item, "label", "")
        )
        indexed[role] = item
    return indexed


_PANEL_OUTPUT_FIELDS = frozenset({"cabinets"})


def cabinets_from_output(output: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return cabinet units from panels_planned output. No flattened top-level copy."""
    unknown = sorted(set(output) - _PANEL_OUTPUT_FIELDS)
    if unknown:
        raise ValueError(
            "panel stage output does not support: " + ", ".join(unknown)
        )
    raw = output.get("cabinets")
    if not isinstance(raw, list) or not raw:
        raise ValueError("panel stage output requires cabinets")
    cabinets: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("each cabinet must be an object")
        cabinets.append(dict(item))
    return cabinets


def primary_cabinet(output: Mapping[str, Any]) -> dict[str, Any]:
    cabinets = cabinets_from_output(output)
    if not cabinets:
        raise ValueError("panel stage output requires at least one cabinet")
    return cabinets[0]


def require_primary_handoff(
    output: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any], list[Any]]:
    """Return spec, structure, and panels from the first cabinet."""
    cabinet = primary_cabinet(output)
    spec = cabinet.get("spec")
    structure = cabinet.get("structure")
    panels = cabinet.get("panels")
    cabinet_id = cabinet.get("id") or DEFAULT_CABINET_ID
    if not isinstance(spec, Mapping):
        raise ValueError(f"{cabinet_id} requires spec")
    if not isinstance(structure, Mapping):
        raise ValueError(f"{cabinet_id} requires structure")
    if not isinstance(panels, list):
        raise ValueError(f"{cabinet_id} requires panels")
    return spec, structure, panels


def bind_panels_to_cabinet(placements: list[Any], cabinet_id: str) -> list[Any]:
    """Rewrite local panel ids onto a cabinet parent. Joints must be computed after this."""
    cabinet_id = _validate_cabinet_id(cabinet_id)
    for panel in placements:
        role = panel.role or panel.id
        panel.role = panel_role(role)
        panel.parent_id = cabinet_id
        panel.id = qualify_panel_id(cabinet_id, panel.role)
        panel.depends_on = [
            qualify_panel_id(cabinet_id, panel_role(dependency))
            for dependency in panel.depends_on
        ]
    return placements
