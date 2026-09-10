"""Serializable entrypoint for construction and physical panels."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Sequence

from furniture_design_intent.design_intent import DesignIntent

from .cabinet_identity import DEFAULT_CABINET_ID, admit_cabinet_id
from .panel_planning import plan_panels
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def plan_panel_stage(
    intent: DesignIntent,
    options: Mapping[str, Any],
) -> dict[str, Any]:
    """Plan one cabinet and wrap it as the canonical cabinets list."""
    return plan_panel_cabinets(((intent, options),))


def plan_panel_cabinets(
    requests: Sequence[tuple[DesignIntent, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Plan one or more cabinet instances with unique parent ids.

    Each request is (confirmed intent, panel parameters). Optional
    ``cabinet_id`` is identity, not a construction field, and is popped
    before spec admission. Duplicate ids are rejected.
    """
    if not requests:
        raise ValueError("panel planning requires at least one cabinet request")
    cabinets: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, (intent, options) in enumerate(requests, start=1):
        if not isinstance(options, Mapping):
            raise ValueError("panel proposal must be an object")
        values = dict(options)
        fallback = DEFAULT_CABINET_ID if index == 1 else f"cabinet_{index}"
        cabinet_id = admit_cabinet_id(values.pop("cabinet_id", None), fallback=fallback)
        if cabinet_id in seen:
            raise ValueError(f"duplicate cabinet_id: {cabinet_id}")
        seen.add(cabinet_id)
        requested_back_mount = values.get("back_mount")
        spec = FurnitureSpec.from_intent(intent, values)
        structure = CabinetStructure.from_spec(spec)
        panels = plan_panels(spec, structure, cabinet_id=cabinet_id)
        cabinets.append(
            {
                "id": cabinet_id,
                "spec": asdict(spec),
                "structure": asdict(structure),
                "back_mount_resolution": {
                    "requested": requested_back_mount,
                    "effective": spec.back_mount,
                },
                "panels": [asdict(item) for item in panels],
            }
        )
    primary = cabinets[0]
    return {
        "cabinets": cabinets,
        "cabinet_id": primary["id"],
        "spec": primary["spec"],
        "structure": primary["structure"],
        "back_mount_resolution": primary["back_mount_resolution"],
        "panels": primary["panels"],
    }
