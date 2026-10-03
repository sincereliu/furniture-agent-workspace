"""Cabinet instance identity and panel parent/child ownership."""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Iterable, Mapping

from .assembly_tree import flatten_panels_for_handoff
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure

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
    """Return the cabinet-local role from a qualified panel id, or the id itself if it is already a role."""
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
    """Return cabinet units from panel_plan output. No flattened top-level copy."""
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


def handoffs_from_output(
    output: Mapping[str, Any],
) -> list[tuple[str, Mapping[str, Any], dict[str, Any], list[Any]]]:
    """每台柜的 `(cabinet_id, spec, derived structure, derived panels)`——**逐柜**下游的手交接口。

    布局里摆了几台柜，制造 / 特征树 / CAD / 交付就该覆盖几台（板件阶段早就支持多柜，
    下游以前只读主柜）。"只看一台"的调用请用 `cabinet_handoff(output, cabinet_id)`，
    **把哪一台说清**——不要取第一台然后只做一台。
    """
    handoffs: list[tuple[str, Mapping[str, Any], dict[str, Any], list[Any]]] = []
    for cabinet in cabinets_from_output(output):
        cabinet_id = str(cabinet.get("id") or DEFAULT_CABINET_ID)
        spec = cabinet.get("spec")
        if not isinstance(spec, Mapping):
            raise ValueError(f"{cabinet_id} requires spec")
        if "interior" not in cabinet:
            raise ValueError(f"{cabinet_id} requires interior")
        structure = asdict(CabinetStructure.from_spec(FurnitureSpec.from_dict(spec)))
        if "assemblies" not in cabinet:
            raise ValueError(f"{cabinet_id} requires assemblies")
        handoffs.append(
            (cabinet_id, spec, structure, flatten_panels_for_handoff(cabinet))
        )
    return handoffs


def cabinet_handoff(
    output: Mapping[str, Any],
    cabinet_id: str,
) -> tuple[Mapping[str, Any], dict[str, Any], list[Any]]:
    """**指名某台柜**的 `(spec, 结构, 板件)`。

    逐柜下游按柜名取料；旁路分析（审计、择优）也用它——**"哪一台"必须由调用方说清**，
    不许默默取第一台（多柜工程里那会算错对象）。
    """
    for existing_id, spec, structure, panels in handoffs_from_output(output):
        if existing_id == cabinet_id:
            return spec, structure, panels
    known = ", ".join(entry[0] for entry in handoffs_from_output(output))
    raise ValueError(f"unknown cabinet id: {cabinet_id} (known: {known})")


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
