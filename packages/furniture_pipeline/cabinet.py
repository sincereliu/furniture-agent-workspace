"""Shared cabinet workflow used by services, scripts, and tests."""

from __future__ import annotations

from dataclasses import dataclass

from furniture_panelizer.bom import BOMReport, generate_bom_report
from furniture_panelizer.panelizer import panelize
from furniture_planner.cabinet_planner import CabinetPlanner
from furniture_planner.templates.base import build_from_blueprint
from furniture_schema.panel import PanelPlacement, PanelRecord
from furniture_schema.spec import FurnitureSpec

SUPPORTED_TYPES = {"floor_cabinet", "wall_cabinet"}

FURNITURE_NAMES = {
    "floor_cabinet": "落地柜",
    "wall_cabinet": "吊柜",
}


@dataclass(frozen=True)
class CabinetPipelineResult:
    """Outputs from the reusable cabinet planning and panelizing workflow."""

    spec: FurnitureSpec
    placements: list[PanelPlacement]
    panels: list[PanelRecord]
    bom: BOMReport


def plan_cabinet(spec: FurnitureSpec) -> CabinetPipelineResult:
    """Plan a supported cabinet type and produce its panel and BOM records."""
    if spec.furniture_type not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES))
        raise ValueError(
            f"Unsupported cabinet type: {spec.furniture_type!r}; supported: {supported}"
        )

    planner = CabinetPlanner(spec)
    build_from_blueprint(planner)

    placements = list(planner._placements)
    panels = panelize(placements)
    dimensions = f"{spec.width:.0f}×{spec.height:.0f}×{spec.depth:.0f}mm"
    bom = generate_bom_report(
        FURNITURE_NAMES.get(spec.furniture_type, spec.furniture_type),
        dimensions,
        panels,
    )

    return CabinetPipelineResult(
        spec=spec,
        placements=placements,
        panels=panels,
        bom=bom,
    )