"""Stateless compatibility facade that composes stage-owned planners."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from furniture_design_intent.design_intent import EXECUTABLE_CATEGORIES
from furniture_manufacturing.manufacturing_bom import BOMReport, plan_manufacturing
from furniture_manufacturing.manufacturing_models import PanelRecord
from furniture_panel_planning.panel_models import PanelPlacement
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.panel_spec import FurnitureSpec
from furniture_panel_planning.structure_planning import CabinetStructure


@dataclass(frozen=True)
class CabinetPipelineResult:
    spec: FurnitureSpec
    structure: CabinetStructure
    placements: list[PanelPlacement]
    panels: list[PanelRecord]
    bom: BOMReport


def plan_cabinet(spec: FurnitureSpec) -> CabinetPipelineResult:
    """Compose panel and manufacturing planning without room placement."""
    normalized = FurnitureSpec.from_dict(asdict(spec))
    if normalized.furniture_category not in EXECUTABLE_CATEGORIES:
        supported = ", ".join(sorted(EXECUTABLE_CATEGORIES))
        raise ValueError(
            f"Unsupported cabinet category: {normalized.furniture_category!r}; supported: {supported}"
        )
    structure = CabinetStructure.from_spec(normalized)
    placements = plan_panels(normalized, structure)
    bom = plan_manufacturing(normalized, placements)
    return CabinetPipelineResult(
        spec=normalized,
        structure=structure,
        placements=placements,
        panels=bom.panels,
        bom=bom,
    )
