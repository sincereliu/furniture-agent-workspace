"""房间页要画的数据。

画面、模板和三维脚本在网页模块 furniture_web。这里只把已经摆好的房间收成页面用的字典。
"""

from __future__ import annotations

from typing import Any

from .scene import RoomScene


def room_page_payload(scene: RoomScene) -> dict[str, Any]:
    """房间页要画的数据。重新打开后还是这个形状。"""
    return {
        "room": scene.room.to_dict(),
        # 与服务端 PlacedItem.to_dict() 同构：编辑后用同一形状替换，不引入第二种结构。
        "items": [item.to_dict() for item in scene.items],
        "obstacles": [
            {
                "label": obstacle.kind,
                "footprint": [list(point) for point in obstacle.footprint],
                "z_start": obstacle.z_mm,
                "z_end": obstacle.z_mm + obstacle.height_mm,
            }
            for obstacle in scene.room.obstacles
        ],
        "openings": [opening.to_dict() for opening in scene.room.openings],
    }
