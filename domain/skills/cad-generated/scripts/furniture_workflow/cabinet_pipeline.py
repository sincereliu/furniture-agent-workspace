"""Snapshot of confirmed panel and manufacturing outputs for CAD write."""

from __future__ import annotations

from dataclasses import dataclass

from furniture_manufacturing.manufacturing_bom import BOMReport
from furniture_manufacturing.manufacturing_models import PanelRecord
from furniture_panel_planning.panel_models import PanelPlacement
from furniture_panel_planning.panel_spec import FurnitureSpec
from furniture_panel_planning.structure_planning import CabinetStructure


@dataclass(frozen=True)
class CabinetPipelineResult:
    spec: FurnitureSpec
    structure: CabinetStructure
    placements: list[PanelPlacement]
    panels: list[PanelRecord]
    bom: BOMReport

