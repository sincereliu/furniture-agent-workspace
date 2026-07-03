"""五金件数据模型 — HardwareRecord"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HardwareRecord:
    """单条五金件记录。

    字段说明:
        name:     五金名称（如 三合一连接件, 液压缓冲铰链）
        spec:     规格描述（如 偏心轮φ15+预埋螺母+连杆）
        quantity: 数量
        unit:     单位（默认"个"）
        note:     备注
    """

    name: str
    spec: str
    quantity: int
    unit: str = "个"
    note: str = ""


@dataclass
class BOMReport:
    """完整的拆单报告（BOM）。

    字段说明:
        furniture_name: 家具名称
        dimensions:     外形尺寸描述（如 "800×1000×600mm"）
        panels:         板件清单
        hardware:       五金件清单
        total_area_m2:  总展开面积（平方米）
    """

    furniture_name: str
    dimensions: str
    panels: list  # List[PanelRecord]
    hardware: list  # List[HardwareRecord]
    total_area_m2: float = 0.0

    @property
    def panel_count(self) -> int:
        return len(self.panels)

    @property
    def hardware_item_count(self) -> int:
        return len(self.hardware)