"""品类模板基类 — 所有板式家具模板的父类

子类只需重写 build() 方法，声明结构即可。
规划器通过 planner 参数注入：

    class MyCabinet(CabinetTemplate):
        def build(self, planner):
            planner.place_side_panels()
            planner.place_top_panel()
            ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from furniture_planner.cabinet_planner import CabinetPlanner


class CabinetTemplate:
    """品类模板基类

    属性:
        name: 品类名称（如"落地柜"、"吊柜"）
        description: 简要描述
    """

    name: str = "通用柜体"
    description: str = ""

    def build(self, planner: "CabinetPlanner") -> None:
        """核心方法：描述柜体结构。

        子类必须重写此方法，通过 planner 的各项 place_* 来声明：
        - 有哪些板件
        - 板件放在哪里
        - 哪些固定、哪些活动

        Args:
            planner: CabinetPlanner 实例，已初始化尺寸参数
        """
        raise NotImplementedError("子类必须实现 build(planner) 方法")