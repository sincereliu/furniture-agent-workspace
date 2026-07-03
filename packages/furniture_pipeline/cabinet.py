"""Shared cabinet workflow used by services, scripts, and tests."""

from __future__ import annotations

from dataclasses import dataclass

from furniture_panelizer.bom import BOMReport, generate_bom_report
from furniture_panelizer.panelizer import panelize
from furniture_planner.cabinet_planner import CabinetPlanner
from furniture_planner.templates.base import CabinetTemplate
from furniture_planner.templates.floor_cabinet import FloorCabinet
from furniture_planner.templates.wall_cabinet import WallCabinet
from furniture_schema.panel import PanelPlacement, PanelRecord
from furniture_schema.spec import FurnitureSpec


TEMPLATE_TYPES: dict[str, type[CabinetTemplate]] = {
    "floor_cabinet": FloorCabinet,
    "wall_cabinet": WallCabinet,
}

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
    template_type = TEMPLATE_TYPES.get(spec.furniture_type)
    if template_type is None:
        supported = ", ".join(TEMPLATE_TYPES)
        raise ValueError(
            f"Unsupported cabinet type: {spec.furniture_type!r}; supported: {supported}"
        )

    planner = CabinetPlanner(spec)
    template = template_type(
        shelf_count=spec.shelf_count,
        n_doors=spec.n_doors,
    )
    template.build(planner)

    placements = list(planner._placements)
    panels = panelize(placements)
    dimensions = f"{spec.width:.0f}×{spec.height:.0f}×{spec.depth:.0f}mm"
    bom = generate_bom_report(
        FURNITURE_NAMES[spec.furniture_type],
        dimensions,
        panels,
    )

    return CabinetPipelineResult(
        spec=spec,
        placements=placements,
        panels=panels,
        bom=bom,
    )