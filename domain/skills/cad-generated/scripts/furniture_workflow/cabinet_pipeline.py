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
    """**一台柜**的完整快照（板件 + 制造），CAD 逐柜写产物时按它取料。

    `cabinet_id` 是身份：它同时是板件 id 的前缀、manifest 柜级记录的标记，
    也是产物文件名的区分依据——所以必须有，且与布局里的那台一致。
    """

    cabinet_id: str
    spec: FurnitureSpec
    structure: CabinetStructure
    placements: list[PanelPlacement]
    panels: list[PanelRecord]
    bom: BOMReport


