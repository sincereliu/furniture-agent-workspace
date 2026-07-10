"""蓝图构造器 — 从 FurnitureSpec 参数调用 CabinetPlanner 构建柜体。

不再需要子类。一个函数覆盖落地柜/吊柜所有变体。
所有参数从 planner.spec (FurnitureSpec) 读取。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from furniture_planner.cabinet_planner import CabinetPlanner


def build_from_blueprint(planner: "CabinetPlanner") -> None:
    """根据 FurnitureSpec 参数调用 planner 的 place_*() 方法构建柜体。

    覆盖的变体:
        - 落地柜: toe_kick_height > 0 → 有踢脚线框架
        - 吊柜:   toe_kick_height = 0 → 无踢脚线框架
        - 层板数: shelf_count 控制 (0 = 无层板)
        - 门板数: n_doors 控制 (0 = 无门板)

    Args:
        planner: 已初始化 FurnitureSpec 的 CabinetPlanner 实例
    """
    spec = planner.spec

    # ── 外框 (必有) ──
    planner.place_side_panels()
    planner.place_top_panel()
    planner.place_bottom_panel()
    planner.place_back_panel()

    # ── 踢脚线 (条件) ──
    if spec.toe_kick_height > 0:
        planner.place_toe_kick_frame()

    # ── 层板 (条件) ──
    if spec.shelf_count > 0:
        total_layers = spec.shelf_count + 1
        layer_h = planner.internal_H / total_layers
        for i in range(1, spec.shelf_count + 1):
            z = planner.z_bottom_internal + i * layer_h - planner.T / 2
            planner.place_shelf(z, fixed=True)

    # ── 门板 (条件) ──
    if spec.n_doors == 1:
        door_w = planner.params.W - planner.params.door_margin * 2
        planner.place_door("single", door_w=door_w)
    elif spec.n_doors == 2:
        planner.place_door("left")
        planner.place_door("right")
    elif spec.n_doors > 2:
        planner.place_doors(spec.n_doors)