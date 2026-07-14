"""Stateless compatibility facade that composes stage-owned planners."""

from __future__ import annotations

from dataclasses import dataclass

from furniture_design_intent.design_spec import FurnitureSpec
from furniture_layout.layout_pipeline import plan_layout
from furniture_layout.layout_planning import CabinetLayout
from furniture_manufacturing.manufacturing_bom import BOMReport, plan_manufacturing
from furniture_manufacturing.manufacturing_models import PanelRecord
from furniture_panel_planning.panel_models import PanelPlacement
from furniture_panel_planning.panel_planning import plan_panels


@dataclass(frozen=True)
class CabinetPipelineResult:
    spec: FurnitureSpec
    layout: CabinetLayout
    placements: list[PanelPlacement]
    panels: list[PanelRecord]
    bom: BOMReport


def plan_cabinet(spec: FurnitureSpec) -> CabinetPipelineResult:
    """Compose stages 2-4 without becoming a second application workflow."""
    layout = plan_layout(spec)
    placements = plan_panels(spec, layout)
    bom = plan_manufacturing(spec, placements)
    return CabinetPipelineResult(
        spec=spec,
        layout=layout,
        placements=placements,
        panels=bom.panels,
        bom=bom,
    )
