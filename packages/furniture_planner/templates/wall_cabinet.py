"""吊柜模板 — 侧板通高，顶底板嵌侧板，无踢脚线"""

from __future__ import annotations

from typing import TYPE_CHECKING

from furniture_planner.templates.base import CabinetTemplate

if TYPE_CHECKING:
    from furniture_planner.cabinet_planner import CabinetPlanner


class WallCabinet(CabinetTemplate):
    """吊柜：侧板通高，顶底板嵌侧板，无踢脚线，有背板"""

    name = "吊柜"
    description = "侧板通高，顶底板嵌侧板，无踢脚线，有背板"

    def __init__(self, *, shelf_count: int = 2, n_doors: int = 2):
        self.shelf_count = shelf_count
        self.n_doors = n_doors

    def build(self, planner: "CabinetPlanner") -> None:
        planner.place_side_panels()
        planner.place_top_panel()
        # 吊柜底板：底面=0（无踢脚线）
        planner.place_bottom_panel()
        planner.place_back_panel()
        # 吊柜无踢脚线
        planner.place_toe_kick_frame()

        # 层板：等分内高，全部固定
        if self.shelf_count > 0:
            total_layers = self.shelf_count + 1
            layer_h = planner.internal_H / total_layers
            for i in range(1, self.shelf_count + 1):
                z = planner.z_bottom_internal + i * layer_h - planner.T / 2
                planner.place_shelf(z, fixed=True)

        # 门板
        if self.n_doors == 1:
            door_w = planner.params.W - planner.params.door_margin * 2
            planner.place_door("single", door_w=door_w)
        elif self.n_doors == 2:
            planner.place_door("left")
            planner.place_door("right")
        else:
            planner.place_doors(self.n_doors)