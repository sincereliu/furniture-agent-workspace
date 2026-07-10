"""五金件数据模型 — HardwareRecord"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HardwareRecord:
    """单条五金件记录。

    字段说明:
        name:     五金名称（如 三合一连接件, 液压缓冲铰链）
        spec:     规格描述（如 偏心轮φ15+预埋螺母+连杆）
        brand:    品牌（如 DTC, Blum，默认 "默认"）
        model:    型号（如 C80-110, 71B3550）
        quantity: 数量
        unit:     单位（默认"个"）
        note:     备注
        drilling: 打孔位置列表 [{"y_mm": 100, "x_offset_mm": 5, ...}, ...]
    """

    name: str
    spec: str
    quantity: int
    brand: str = "默认"
    model: str = ""
    unit: str = "个"
    note: str = ""
    drilling: list = None  # type: ignore[assignment]


