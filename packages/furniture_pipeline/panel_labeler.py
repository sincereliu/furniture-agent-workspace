"""板件标签生成器 — 为每块板生成唯一标识码

标签格式: {订单号}-{房间缩写}-{板件类型缩写}{序号}
"""

from __future__ import annotations

from typing import Dict, List

from furniture_schema.panel import PanelLabel
from furniture_schema.panel import PanelRecord

# 房间名缩写映射
ROOM_ABBREV: Dict[str, str] = {
    "厨房": "KITCHEN",
    "卧室": "BEDROOM",
    "客厅": "LIVING",
    "书房": "STUDY",
    "卫生间": "BATH",
    "阳台": "BALCONY",
}

# 板件类型缩写
TYPE_ABBREV: Dict[str, str] = {
    "side": "S",
    "top": "T",
    "bottom": "B",
    "fixed_shelf": "FS",
    "movable_shelf": "MS",
    "divider": "D",
    "back": "BK",
    "door": "DR",
    "toe_kick": "TK",
}


def generate_labels(
    panels: List[PanelRecord],
    order_id: str,
    room: str,
) -> List[PanelLabel]:
    """为一批板件生成标签数据。

    Args:
        panels: 板件列表
        order_id: 订单号 "260709-0001"
        room: 房间名 "厨房"
    """
    room_code = ROOM_ABBREV.get(room, room.upper()[:4])
    labels: List[PanelLabel] = []
    type_counters: Dict[str, int] = {}

    for panel in panels:
        type_code = TYPE_ABBREV.get(panel.panel_type, panel.panel_type[:2].upper())
        type_counters[type_code] = type_counters.get(type_code, 0) + 1
        seq = f"{type_counters[type_code]:02d}"

        label_id = f"{order_id}-{room_code}-{type_code}{seq}"

        labels.append(PanelLabel(
            label_id=label_id,
            order_id=order_id,
            room=room,
            panel_name=panel.name,
            panel_type=panel.panel_type,
            length_mm=panel.length_mm,
            width_mm=panel.width_mm,
            thickness_mm=panel.thickness,
            material=panel.material,
            color="",
            edge_banding=panel.edge_banding_summary(),
            cut_x_mm=0.0,
            cut_y_mm=0.0,
            board_index=0,
        ))

    return labels