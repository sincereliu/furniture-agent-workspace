"""Stateless compatibility facade that composes stage-owned planners."""

from __future__ import annotations

from dataclasses import dataclass

from furniture_design_intent.design_spec import FurnitureSpec
from furniture_layout.layout_pipeline import plan_layout
from furniture_manufacturing.manufacturing_bom import BOMReport, plan_manufacturing
from furniture_panel_planning.panel_models import PanelPlacement, PanelRecord
from furniture_panel_planning.panel_planning import plan_panels


@dataclass(frozen=True)
class CabinetPipelineResult:
    spec: FurnitureSpec
    placements: list[PanelPlacement]
    panels: list[PanelRecord]
    bom: BOMReport


def plan_cabinet(spec: FurnitureSpec) -> CabinetPipelineResult:
    """Compose stages 2-4 without becoming a second application workflow."""
    placements = plan_layout(spec)
    panels = plan_panels(placements)
    bom = plan_manufacturing(spec, panels)
    return CabinetPipelineResult(spec=spec, placements=placements, panels=panels, bom=bom)
