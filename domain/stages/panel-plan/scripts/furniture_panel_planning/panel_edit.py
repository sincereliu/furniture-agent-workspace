"""Pure edits of panel-owned properties; lifecycle and persistence belong to workflow."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from .assembly_tree import iter_assembly_panels
from .construction_geometry import door_hinge_sides
from .grain_rules import normalize_grain_axis
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


@dataclass(frozen=True)
class PanelEditResult:
    output: dict[str, Any]
    panels: tuple[str, ...]
    door_hinges: dict[str, str]


def edit_cabinet_panels(
    output: Mapping[str, Any],
    cabinet_id: str,
    *,
    axes: Mapping[str, str] | None = None,
    hinges: Mapping[str, str] | None = None,
) -> PanelEditResult:
    """Validate a complete edit before returning a new panel checkpoint."""
    if not isinstance(output, Mapping):
        raise ValueError("this project has no panel plan to change")

    # 先把要改的都对一遍，再动任何东西——校验不过整体拒绝，不留半改状态。
    cabinets = output.get("cabinets")
    if not isinstance(cabinets, list):
        raise ValueError("panel plan has no cabinets")
    target = next(
        (item for item in cabinets if str(item.get("id") or "") == cabinet_id), None
    )
    if target is None:
        raise ValueError(f"no such cabinet in the panel plan: {cabinet_id}")

    by_id = {str(panel.get("id") or ""): panel for panel in iter_assembly_panels(target)}
    wanted: dict[str, str] = {}
    for panel_id, axis in (axes or {}).items():
        if panel_id not in by_id:
            raise ValueError(f"no such panel in {cabinet_id}: {panel_id}")
        wanted[panel_id] = normalize_grain_axis(axis, str(by_id[panel_id].get("panel_type") or ""))
    sides: dict[str, str] = {}
    spec_hinges: list[str] = []
    if hinges:
        resolved = _resolve_door_hinges(cabinet_id, target, hinges)
        sides = resolved["sides"]
        spec_hinges = resolved["door_hinges"]
    if not wanted and not sides:
        raise ValueError("nothing to change")

    changed = deepcopy(dict(output))
    for cabinet in changed["cabinets"]:
        if str(cabinet.get("id") or "") != cabinet_id:
            continue
        if spec_hinges:
            spec = cabinet.get("spec")
            if not isinstance(spec, dict):
                raise ValueError(f"{cabinet_id} has no spec to carry door_hinges")
            spec["door_hinges"] = list(spec_hinges)
        for panel in iter_assembly_panels(cabinet):
            panel_id = str(panel.get("id") or "")
            if panel_id in wanted:
                panel["grain_axis"] = wanted[panel_id]
            if panel_id in sides:
                panel["door_hinge_side"] = sides[panel_id]

    return PanelEditResult(
        output=changed,
        panels=tuple(sorted(set(wanted) | set(sides))),
        door_hinges={key: sides[key] for key in sorted(sides)},
    )


def _resolve_door_hinges(
    cabinet_id: str,
    cabinet: Mapping[str, Any],
    wanted: Mapping[str, str],
) -> dict[str, Any]:
    """把「这几扇门改成左开/右开」算成一整排值，并复核几何。

    铰链侧有两个来源：对开腔那两扇被几何逼死（左 left、右 right），单开腔由人给。
    所以这里不是"改一个字段"，而是：**先把整排值拼出来**（没点到的沿用原值），
    再用 `door_hinge_sides()` 复核——对开腔被单独改会在这里被拒，而不是等到冻结时才炸。

    返回 `{"door_hinges": 整排, "sides": {板件 id: 值}}`。
    """
    spec = cabinet.get("spec")
    if not isinstance(spec, Mapping):
        raise ValueError(f"{cabinet_id} has no spec")
    doors = [
        panel
        for panel in iter_assembly_panels(cabinet)
        if str(panel.get("panel_type") or "") == "door"
    ]
    if not doors:
        raise ValueError(f"{cabinet_id} has no doors")
    ordered = sorted(
        doors,
        key=lambda item: (float(item.get("pos_x") or 0.0), str(item.get("id") or "")),
    )
    known = {str(item.get("id") or "") for item in ordered}
    index_by_id = {str(item.get("id") or ""): index for index, item in enumerate(ordered)}
    values = [str(item.get("door_hinge_side") or "") for item in ordered]
    for panel_id, side in wanted.items():
        if panel_id not in known:
            raise ValueError(f"no such door in {cabinet_id}: {panel_id}")
        text = str(side or "").strip().lower()
        if text not in {"left", "right"}:
            raise ValueError("door hinge side must be 'left' or 'right'")
        values[index_by_id[panel_id]] = text

    payload = dict(spec)
    # `door_hinges` 不接受空串：还没定的那几扇要**先**点名，别让它变成一句
    # "door hinge must be one of: left, right" —— 页面只点了一扇时最需要人话。
    missing = [
        str(item.get("id") or "") for item, value in zip(ordered, values) if not value
    ]
    if missing:
        raise ValueError("these doors still have no hinge side: " + ", ".join(missing))
    payload["door_hinges"] = values
    admitted = FurnitureSpec.from_dict(payload)
    structure = CabinetStructure.from_spec(admitted)
    try:
        resolved = door_hinge_sides(admitted, structure)
    except ValueError as exc:
        # 对开腔那两扇不能单独改：几何逼死左 left、右 right。
        raise ValueError(f"these hinge sides cannot be changed: {exc}") from exc
    missing = [
        str(item.get("id") or "")
        for item, side in zip(ordered, resolved)
        if not side
    ]
    if missing:
        raise ValueError("these doors still have no hinge side: " + ", ".join(missing))
    return {
        "door_hinges": list(resolved),
        "sides": {
            str(item.get("id") or ""): side for item, side in zip(ordered, resolved)
        },
    }
