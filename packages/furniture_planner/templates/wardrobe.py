"""衣柜模板 — 基于落地柜，带挂衣杆"""

from __future__ import annotations

from typing import TYPE_CHECKING

from furniture_planner.templates.base import CabinetTemplate

if TYPE_CHECKING:
    from furniture_planner.cabinet_planner import CabinetPlanner


class Wardrobe(CabinetTemplate):
    """衣柜：基于落地柜结构，可选挂衣杆和抽屉区"""

    name = "衣柜"
    description = "基于落地柜，侧板落地，有踢脚线、背板，可选挂衣杆"

    def __init__(
        self,
        *,
        shelf_count: int = 4,
        n_doors: int = 2,
        has_hanging_rod: bool = True,
    ):
        self.shelf_count = shelf_count
        self.n_doors = n_doors
        self.has_hanging_rod = has_hanging_rod

    def build(self, planner: "CabinetPlanner") -> None:
        planner.place_side_panels()
        planner.place_top_panel()
        planner.place_bottom_panel()
        planner.place_back_panel()
        planner.place_toe_kick_frame()

        p = planner.params

        # 衣柜默认有挂衣杆：左半区挂衣，右半区放层板
        if self.has_hanging_rod:
            # 中立板：在宽度 1/3 处
            divider_x = p.W / 3
            planner.place_divider(divider_x)

            # 左区（挂衣区）：不放层板，挂衣杆在 1600mm 高处
            # 注：挂衣杆不是板件，不做 PanelPlacement，由拆单层标记五金件

            # 右区（层板区）：在右侧区域内等分层板
            if self.shelf_count > 0:
                layer_h = planner.internal_H / (self.shelf_count + 1)
                for i in range(1, self.shelf_count + 1):
                    z = planner.z_bottom_internal + i * layer_h - planner.T / 2
                    # x_range 限制在右侧区域
                    planner.place_shelf(
                        z,
                        fixed=True,
                        x_range=(divider_x, p.W - p.T),
                    )
        else:
            # 无挂衣杆：全宽等分层板
            if self.shelf_count > 0:
                layer_h = planner.internal_H / (self.shelf_count + 1)
                for i in range(1, self.shelf_count + 1):
                    z = planner.z_bottom_internal + i * layer_h - planner.T / 2
                    planner.place_shelf(z, fixed=True)

        # 门板
        if self.n_doors == 2:
            planner.place_door("left")
            planner.place_door("right")
        elif self.n_doors == 1:
            door_w = p.W - p.door_margin * 2
            planner.place_door("single", door_w=door_w)
        else:
            planner.place_doors(self.n_doors)