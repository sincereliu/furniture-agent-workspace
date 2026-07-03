"""面约束定位引擎 — 板件之间通过面对齐，不再手工计算坐标。

用法:
    from furniture_planner.face_query import FaceQuery

    # 查询已放置板件的面位置
    panel = PanelPlacement(id="left_side", pos_x=0, pos_y=0, pos_z=0, size_x=18, size_y=580, size_z=1000)
    top_z = FaceQuery.top(panel)   # → 1000.0

注意：FaceQuery 接收 PanelPlacement（纯数据），不依赖 build123d。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from furniture_schema.panel import PanelPlacement


class FaceQuery:
    """查询已放置面板的 6 个面在全局坐标系中的位置。

    坐标系: 原点=柜体左-后-下角, X→右, Y→前, Z→上
    所有 pos 指 min corner。
    """

    # ---- 全局坐标查询 ----
    @staticmethod
    def top(panel: "PanelPlacement") -> float:
        """面板顶面的 Z 坐标"""
        return panel.pos_z + panel.size_z

    @staticmethod
    def bottom(panel: "PanelPlacement") -> float:
        """面板底面的 Z 坐标"""
        return panel.pos_z

    @staticmethod
    def front(panel: "PanelPlacement") -> float:
        """面板前面的 Y 坐标"""
        return panel.pos_y + panel.size_y

    @staticmethod
    def back(panel: "PanelPlacement") -> float:
        """面板后面的 Y 坐标"""
        return panel.pos_y

    @staticmethod
    def left(panel: "PanelPlacement") -> float:
        """面板左面的 X 坐标"""
        return panel.pos_x

    @staticmethod
    def right(panel: "PanelPlacement") -> float:
        """面板右面的 X 坐标"""
        return panel.pos_x + panel.size_x

    @staticmethod
    def center_x(panel: "PanelPlacement") -> float:
        return panel.pos_x + panel.size_x / 2

    @staticmethod
    def center_y(panel: "PanelPlacement") -> float:
        return panel.pos_y + panel.size_y / 2

    @staticmethod
    def center_z(panel: "PanelPlacement") -> float:
        return panel.pos_z + panel.size_z / 2

    # ---- 与侧板相关的快捷查询 ----
    @staticmethod
    def side_inner_left(panel: "PanelPlacement") -> float:
        """侧板内面（右面）的 X 坐标 — 只对左侧板有意义"""
        return panel.pos_x + panel.size_x

    @staticmethod
    def side_inner_right(panel: "PanelPlacement") -> float:
        """侧板内面（左面）的 X 坐标 — 只对右侧板有意义"""
        return panel.pos_x

    # ---- 计算辅助 ----
    @staticmethod
    def placed_between_x(
        left_panel: "PanelPlacement", right_panel: "PanelPlacement"
    ) -> tuple[float, float]:
        """计算夹在左右侧板之间的面板应有的 X 中心和宽度。

        Returns:
            (cx, width): X 中心坐标和面板宽度 mm
        """
        x0 = FaceQuery.side_inner_left(left_panel)
        x1 = FaceQuery.side_inner_right(right_panel)
        width = x1 - x0
        cx = (x0 + x1) / 2
        return cx, width


def shelf_depth(
    side_depth: float, back_offset: float, T_back: float
) -> float:
    """层板深度：从侧板前面到背板前表面。

    Args:
        side_depth: 侧板深度 mm
        back_offset: 背板距后 mm
        T_back: 背板厚 mm

    Returns:
        层板深度 mm
    """
    return side_depth - back_offset - T_back