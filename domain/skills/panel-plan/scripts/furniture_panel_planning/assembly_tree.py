"""Cabinet → assembly → panel tree for the panel_plan checkpoint.

The solver still emits a flat placement list. This module groups that list
into carcass / optional base / fronts / drawer boxes and scopes contacts to
each assembly. Downstream readers that still want a panel list derive it
with flatten_panels_for_handoff().
"""

from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Iterable, Mapping

from .joint_topology import compute_joints
from .panel_models import PanelPlacement
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure

CABINET_OUTPUT_FIELDS = frozenset(
    {
        "id",
        "spec",
        "interior",
        "back_mount_resolution",
        "assemblies",
    }
)
ASSEMBLY_OBJECT_FIELDS = frozenset({"carcass", "base", "fronts", "drawers"})
BASE_CONSTRUCTIONS = frozenset({"integrated"})
ZONE_KINDS = frozenset({"doors", "full_height_drawers"})
INTERIOR_FIELDS = frozenset({"cavity", "zones"})
CAVITY_FIELDS = frozenset({"width", "height", "depth", "origin"})

_DRAWER_ROLE = re.compile(
    r"^(drawer_front|drawer_side_L|drawer_side_R|drawer_back|drawer_bottom)_(z-?\d+)$"
)
_CONTACT_KEY_FIELDS = ("bearing_id", "end_id", "face", "edge_axis", "edge_sign")


def build_cabinet_tree(
    cabinet_id: str,
    spec: FurnitureSpec,
    structure: CabinetStructure,
    panels: list[PanelPlacement],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Group solved panels into assemblies and the interior cavity/zones."""
    carcass_panels: list[PanelPlacement] = []
    front_panels: list[PanelPlacement] = []
    drawer_groups: dict[str, list[PanelPlacement]] = {}
    for panel in panels:
        suffix = _drawer_suffix(panel.role)
        if suffix is not None:
            drawer_groups.setdefault(suffix, []).append(panel)
            continue
        if panel.panel_type.startswith("drawer_"):
            raise ValueError(f"{panel.id} is not a recognized drawer role")
        if panel.panel_type == "door":
            front_panels.append(panel)
            continue
        carcass_panels.append(panel)

    carcass_id = f"{cabinet_id}__carcass"
    fronts_id = f"{cabinet_id}__fronts"
    assemblies: dict[str, Any] = {
        "carcass": _assembly_unit(carcass_id, "carcass", carcass_panels),
        "fronts": _assembly_unit(fronts_id, "fronts", front_panels),
        "drawers": [],
    }
    if structure.toe_kick_height > 0:
        assemblies["base"] = {
            "id": f"{cabinet_id}__base",
            "kind": "base",
            "construction": "integrated",
            "panels": [],
            "joints": [],
        }

    drawer_ids: list[str] = []
    for index, suffix in enumerate(sorted(drawer_groups, key=_drawer_sort_key), start=1):
        group = drawer_groups[suffix]
        drawer_id = f"{cabinet_id}__drawer_{index}"
        front = next(
            (item for item in group if item.panel_type == "drawer_front"),
            None,
        )
        if front is None:
            raise ValueError(f"{drawer_id} requires a drawer front")
        assemblies["drawers"].append(
            {
                "id": drawer_id,
                "index": index,
                "front_id": front.id,
                "box": {
                    "panels": [_panel_payload(item, drawer_id) for item in group],
                    "joints": _joints_payload(group),
                },
            }
        )
        drawer_ids.append(drawer_id)

    if spec.drawer_count != len(assemblies["drawers"]):
        raise ValueError("drawer assemblies must match drawer_count")
    if spec.n_doors != len(front_panels):
        raise ValueError("front assemblies must match n_doors")

    zones: list[dict[str, Any]] = []
    if spec.n_doors > 0:
        zones.append(
            {
                "id": f"{cabinet_id}__zone_front",
                "kind": "doors",
                "members": [item.id for item in front_panels],
            }
        )
    if spec.drawer_count > 0:
        zones.append(
            {
                "id": f"{cabinet_id}__zone_front",
                "kind": "full_height_drawers",
                "members": drawer_ids,
            }
        )
    interior = {"cavity": structure.cavity(), "zones": zones}
    return assemblies, interior


def iter_assembly_panels(cabinet: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Walk checkpoint panels in carcass, base, fronts, then drawer order."""
    assemblies = _require_assemblies(cabinet)
    panels: list[dict[str, Any]] = []
    panels.extend(_mapping_list(assemblies["carcass"], "panels"))
    base = assemblies.get("base")
    if isinstance(base, Mapping):
        panels.extend(_mapping_list(base, "panels"))
    fronts = assemblies.get("fronts")
    if isinstance(fronts, Mapping):
        panels.extend(_mapping_list(fronts, "panels"))
    for drawer in _drawer_entries(assemblies):
        box = drawer.get("box")
        if not isinstance(box, Mapping):
            raise ValueError(f"{drawer.get('id', 'drawer')} requires box")
        panels.extend(_mapping_list(box, "panels"))
    return panels


def iter_assembly_joints(cabinet: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Walk unique assembly-scoped contacts in the same order as panels."""
    assemblies = _require_assemblies(cabinet)
    joints: list[dict[str, Any]] = []
    joints.extend(_mapping_list(assemblies["carcass"], "joints"))
    base = assemblies.get("base")
    if isinstance(base, Mapping):
        joints.extend(_mapping_list(base, "joints"))
    fronts = assemblies.get("fronts")
    if isinstance(fronts, Mapping):
        joints.extend(_mapping_list(fronts, "joints"))
    for drawer in _drawer_entries(assemblies):
        box = drawer.get("box")
        if not isinstance(box, Mapping):
            raise ValueError(f"{drawer.get('id', 'drawer')} requires box")
        joints.extend(_mapping_list(box, "joints"))
    return joints


def flatten_panels_for_handoff(cabinet: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Derive a panel list and reattach each assembly contact onto its panels."""
    by_panel: dict[str, list[dict[str, Any]]] = {}
    for joint in iter_assembly_joints(cabinet):
        if not isinstance(joint, Mapping):
            raise ValueError("each contact must be an object")
        for panel_id in (joint.get("bearing_id"), joint.get("end_id")):
            if not isinstance(panel_id, str) or not panel_id:
                raise ValueError("each contact requires bearing_id and end_id")
            bucket = by_panel.setdefault(panel_id, [])
            if joint not in bucket:
                bucket.append(dict(joint))
    flattened: list[dict[str, Any]] = []
    for panel in iter_assembly_panels(cabinet):
        if not isinstance(panel, Mapping):
            raise ValueError("each panel must be an object")
        item = dict(panel)
        item["joints"] = list(by_panel.get(str(item.get("id", "")), []))
        flattened.append(item)
    return flattened


def _require_assemblies(cabinet: Mapping[str, Any]) -> Mapping[str, Any]:
    cabinet_id = str(cabinet.get("id") or "").strip() or "cabinet"
    if "panels" in cabinet:
        raise ValueError(f"{cabinet_id} must not copy panels at cabinet level")
    assemblies = cabinet.get("assemblies")
    if not isinstance(assemblies, Mapping):
        raise ValueError(f"{cabinet_id} requires assemblies")
    carcass = assemblies.get("carcass")
    if not isinstance(carcass, Mapping):
        raise ValueError(f"{cabinet_id} requires carcass assembly")
    return assemblies


def _drawer_entries(assemblies: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    drawers = assemblies.get("drawers", [])
    if not isinstance(drawers, list):
        raise ValueError("drawers must be a list")
    entries: list[Mapping[str, Any]] = []
    for item in drawers:
        if not isinstance(item, Mapping):
            raise ValueError("each drawer must be an object")
        entries.append(item)
    return entries


def _mapping_list(owner: Mapping[str, Any], key: str) -> list[Any]:
    raw = owner.get(key)
    if not isinstance(raw, list):
        raise ValueError(f"{owner.get('id', 'assembly')} requires {key}")
    return list(raw)


def _assembly_unit(
    assembly_id: str,
    kind: str,
    panels: Iterable[PanelPlacement],
) -> dict[str, Any]:
    material = list(panels)
    return {
        "id": assembly_id,
        "kind": kind,
        "panels": [_panel_payload(item, assembly_id) for item in material],
        "joints": _joints_payload(material),
    }


def _panel_payload(panel: PanelPlacement, assembly_id: str) -> dict[str, Any]:
    panel.assembly_id = assembly_id
    payload = asdict(panel)
    payload.pop("joints", None)
    return payload


def _joints_payload(panels: list[PanelPlacement]) -> list[dict[str, Any]]:
    unique: dict[tuple[Any, ...], dict[str, Any]] = {}
    for joint in compute_joints(panels):
        payload = asdict(joint)
        key = tuple(payload[field] for field in _CONTACT_KEY_FIELDS)
        unique[key] = payload
    return [unique[key] for key in sorted(unique)]


def _drawer_suffix(role: str) -> str | None:
    match = _DRAWER_ROLE.fullmatch(role)
    if match is None:
        return None
    return match.group(2)


def _drawer_sort_key(suffix: str) -> int:
    return int(suffix[1:])
