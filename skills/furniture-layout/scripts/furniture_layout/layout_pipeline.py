"""Shared cabinet workflow used by services, scripts, and tests."""

from __future__ import annotations

from dataclasses import dataclass

from furniture.manufacturing_bom import BOMReport, generate_bom_report
from furniture.panel_planning import panelize
from furniture.layout_planning import CabinetPlanner
from furniture.layout_template import build_from_blueprint
from furniture.panel_models import PanelPlacement, PanelRecord
from furniture.design_spec import FurnitureSpec

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
    placements = plan_layout(spec)
    panels = plan_panels(placements)
    bom = plan_manufacturing(spec, panels)

    return CabinetPipelineResult(
        spec=spec,
        placements=placements,
        panels=panels,
        bom=bom,
    )


def plan_layout(spec: FurnitureSpec) -> list[PanelPlacement]:
    """Stage 2: resolve cabinet spatial organization and placements."""
    if spec.furniture_type not in SUPPORTED_TYPES:
        supported = ", ".join(sorted(SUPPORTED_TYPES))
        raise ValueError(
            f"Unsupported cabinet type: {spec.furniture_type!r}; supported: {supported}"
        )

    planner = CabinetPlanner(spec)
    build_from_blueprint(planner)
    return list(planner._placements)


def plan_panels(placements: list[PanelPlacement]) -> list[PanelRecord]:
    """Stage 3: convert layout placements into manufacturing panel records."""
    return panelize(placements)


def plan_manufacturing(
    spec: FurnitureSpec,
    panels: list[PanelRecord],
) -> BOMReport:
    """Stage 4: apply manufacturing, hardware, and BOM policy."""
    dimensions = f"{spec.width:.0f}×{spec.height:.0f}×{spec.depth:.0f}mm"
    return generate_bom_report(
        FURNITURE_NAMES.get(spec.furniture_type, spec.furniture_type),
        dimensions,
        panels,
    )
