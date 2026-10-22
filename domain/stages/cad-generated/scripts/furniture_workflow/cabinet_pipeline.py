"""Snapshot of confirmed panel and manufacturing outputs for CAD write."""

from __future__ import annotations

from dataclasses import dataclass

from furniture_manufacturing.manufacturing_bom import BOMReport
from furniture_manufacturing.manufacturing_models import PanelRecord


@dataclass(frozen=True)
class CabinetPipelineResult:
    """**一台柜**的制造快照。CAD 逐柜写 BOM、钻孔和 STEP 源时按它取料。

    `cabinet_id` 是身份：它同时是板件 id 的前缀、manifest 柜级记录的标记，
    也是产物文件名的区分依据——所以必须有，且与布局里的那台一致。
    板件几何留在已确认的板件文件里，这里不再重建板件类型。
    """

    cabinet_id: str
    panels: list[PanelRecord]
    bom: BOMReport


