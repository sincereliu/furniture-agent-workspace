"""Serializable stage entrypoint for construction and physical panels."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from furniture_layout.layout_planning import CabinetLayout

from .panel_planning import plan_panels
from .panel_spec import FurnitureSpec
from .structure_planning import CabinetStructure


def plan_panel_stage(
    layout: CabinetLayout,
    options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    values = dict(options or {})
    requested_back_mount = str(values.get("back_mount", "auto")).strip().lower()
    spec = FurnitureSpec.from_layout(layout, values)
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
