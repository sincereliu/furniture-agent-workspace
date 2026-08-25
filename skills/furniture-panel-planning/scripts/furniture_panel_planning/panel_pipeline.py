"""Serializable entrypoint for construction and physical panels."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent

from .panel_planning import plan_panels
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def plan_panel_stage(
    intent: DesignIntent,
    options: Mapping[str, Any],
) -> dict[str, Any]:
    requested_back_mount = options.get("back_mount") if isinstance(options, Mapping) else None
    spec = FurnitureSpec.from_intent(intent, options)
    structure = CabinetStructure.from_spec(spec)
    panels = plan_panels(spec, structure)
    return {
        "spec": asdict(spec),
        "structure": asdict(structure),
        "back_mount_resolution": {
            "requested": requested_back_mount,
            "effective": spec.back_mount,
        },
        "panels": [asdict(item) for item in panels],
    }
