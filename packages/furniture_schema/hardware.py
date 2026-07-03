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


