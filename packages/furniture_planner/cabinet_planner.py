"""板式家具规划引擎 — 从 FurnitureSpec 计算所有面板的尺寸和位置。

职责边界:
  ✅ 尺寸推导: W,H,D → internal_W, internal_H, side_depth, shelf_depth 等
  ✅ 坐标计算: 使用 FaceQuery 计算每块板的 min corner (x, y, z)
  ✅ 输出 PanelPlacement 列表（纯数据，不含 CAD 对象）
  ❌ 不创建 build123d Solid / Box
  ❌ 不生成 BOM / 封边（那是 Panelizer 的职责）
  ❌ 不生成 CAD 源码（那是 Emitter 的职责）

坐标系: 原点=柜体左-后-下角, X→右, Y→前, Z→上
参考: docs/coordinate-system.md, external references/panel-placement.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from furniture_planner.face_query import FaceQuery
from furniture_schema.panel import PanelPlacement
from furniture_schema.spec import FurnitureSpec


@dataclass
class CabinetParams:
    """柜体内部计算参数 — 从 FurnitureSpec 推导出的全部派生尺寸。

    所有单位为 mm。
    """

    W: float         # 柜体总宽
    H: float         # 柜体总高
    D_total: float   # 柜体总深
    T: float         # 柜体板厚
    T_back: float    # 背板厚
    T_door: float    # 门板厚
    toe_kick_h: float  # 踢脚线高
    back_offset: float  # 背板距后
    door_margin: float  # 门板四周缝
    door_hinge_gap: float  # 门铰链深度间隙

    # 派生尺寸
    side_depth: float     # 侧板深度 = D_total - T_door - door_hinge_gap
    internal_W: float     # 内部净宽 = W - 2T
    internal_H: float     # 内部净高 = H - toe_kick_h - 2T
    z_bottom_internal: float  # 内部底面 Z（不含底板厚）
    z_top_internal: float     # 内部顶面 Z

    @classmethod
    def from_spec(cls, spec: FurnitureSpec) -> "CabinetParams":
        T = spec.board_thickness
        T_back = spec.back_thickness
        T_door = spec.door_thickness
        toe_kick_h = spec.toe_kick_height
        back_offset = spec.back_offset
        door_margin = spec.door_margin
        door_hinge_gap = spec.door_hinge_gap

        side_depth = spec.depth - T_door - door_hinge_gap
        internal_W = spec.width - 2 * T
        internal_H = spec.height - toe_kick_h - 2 * T

        # 踢脚线高度: 吊柜为 0
        actual_toe_kick = toe_kick_h if spec.furniture_type != "wall_cabinet" else 0.0
        actual_internal_H = spec.height - actual_toe_kick - 2 * T

        return cls(
            W=spec.width,
            H=spec.height,
            D_total=spec.depth,
            T=T,
            T_back=T_back,
            T_door=T_door,
            toe_kick_h=actual_toe_kick,
            back_offset=back_offset,
            door_margin=door_margin,
            door_hinge_gap=door_hinge_gap,
            side_depth=side_depth,
            internal_W=internal_W,
            internal_H=actual_internal_H,
            z_bottom_internal=actual_toe_kick + T,
            z_top_internal=spec.height - T,
        )


class CabinetPlanner:
    """板式柜体规划器。

    使用方法:
        spec = FurnitureSpec(furniture_type="floor_cabinet", width=800, height=1000, depth=600)
        planner = CabinetPlanner(spec)
        placements = planner.plan_all()          # 基础结构
        # 或逐步构建（模板模式）
        placements = []
        placements.extend(planner.place_side_panels())
        placements.append(planner.place_top_panel(placements[0], placements[1]))
        ...
    """

    def __init__(self, spec: FurnitureSpec):
        self.spec = spec
        self.params = CabinetParams.from_spec(spec)
        self._placements: List[PanelPlacement] = []

    # ---- 尺寸查询 ----
    @property
    def T(self) -> float:
        return self.params.T

    @property
    def T_back(self) -> float:
        return self.params.T_back

    @property
    def T_door(self) -> float:
        return self.params.T_door

    @property
    def side_depth(self) -> float:
        return self.params.side_depth

    @property
    def internal_W(self) -> float:
        return self.params.internal_W

    @property
    def internal_H(self) -> float:
        return self.params.internal_H

    @property
    def z_bottom_internal(self) -> float:
        return self.params.z_bottom_internal

    @property
    def z_top_internal(self) -> float:
        return self.params.z_top_internal

    # ---- 面板放置方法（每个方法输出 PanelPlacement，不创建 Solid） ----

    def place_side_panels(self) -> List[PanelPlacement]:
        """放置左右侧板。

        左板 min=(0, 0, 0), 右板 min=(W-T, 0, 0)
        深度=side_depth, 高度=H（通高）
        """
        p = self.params
        left = PanelPlacement(
            id="left_side_panel",
            name="左侧板",
            panel_type="side",
            size_x=p.T,
            size_y=p.side_depth,
            size_z=p.H,
            pos_x=0.0,
            pos_y=0.0,
            pos_z=0.0,
            note=f"侧板，深{p.side_depth:.0f}×高{p.H:.0f}×厚{p.T:.0f}mm",
        )
        right = PanelPlacement(
            id="right_side_panel",
            name="右侧板",
            panel_type="side",
            size_x=p.T,
            size_y=p.side_depth,
            size_z=p.H,
            pos_x=p.W - p.T,
            pos_y=0.0,
            pos_z=0.0,
            depends_on=["left_side_panel"],
            note=f"侧板，深{p.side_depth:.0f}×高{p.H:.0f}×厚{p.T:.0f}mm",
        )
        self._placements.extend([left, right])
        return [left, right]

    def place_top_panel(
        self,
        side_L: PanelPlacement | None = None,
        side_R: PanelPlacement | None = None,
    ) -> PanelPlacement:
        """放置顶板：夹在左右侧板之间，顶面=侧板顶面。

        Args:
            side_L: 左侧板 PanelPlacement（可选，默认取 self._placements[0]）
            side_R: 右侧板 PanelPlacement（可选，默认取 self._placements[1]）
        """
        p = self.params
        if side_L is None:
            side_L = self._placements[0]
        if side_R is None:
            side_R = self._placements[1]

        cx, top_w = FaceQuery.placed_between_x(side_L, side_R)
        x = cx - top_w / 2
        z = FaceQuery.top(side_L) - p.T

        placement = PanelPlacement(
            id="top_panel",
            name="顶板",
            panel_type="top",
            size_x=top_w,
            size_y=p.side_depth,
            size_z=p.T,
            pos_x=x,
            pos_y=0.0,
            pos_z=z,
            depends_on=["left_side_panel", "right_side_panel"],
            note="盖在侧板上方",
        )
        self._placements.append(placement)
        return placement

    def place_bottom_panel(
        self,
        side_L: PanelPlacement | None = None,
        side_R: PanelPlacement | None = None,
    ) -> PanelPlacement:
        """放置底板：夹在左右侧板之间，底面=踢脚线顶面。

        Args:
            side_L: 左侧板
            side_R: 右侧板
        """
        p = self.params
        if side_L is None:
            side_L = self._placements[0]
        if side_R is None:
            side_R = self._placements[1]

        cx, bottom_w = FaceQuery.placed_between_x(side_L, side_R)
        x = cx - bottom_w / 2
        z = p.toe_kick_h

        placement = PanelPlacement(
            id="bottom_panel",
            name="底板",
            panel_type="bottom",
            size_x=bottom_w,
            size_y=p.side_depth,
            size_z=p.T,
            pos_x=x,
            pos_y=0.0,
            pos_z=z,
            depends_on=["left_side_panel", "right_side_panel"],
            note="踢脚线上方",
        )
        self._placements.append(placement)
        return placement

    def place_shelf(
        self,
        z_center: float,
        *,
        fixed: bool = True,
        label: str = "",
        name: str = "",
        side_L: PanelPlacement | None = None,
        side_R: PanelPlacement | None = None,
        x_range: Tuple[float, float] | None = None,
    ) -> PanelPlacement:
        """放置层板。

        Args:
            z_center: 层板中心 Z 坐标 mm
            fixed: 固定层板 True，活动层板 False
            label: 自定义内部标识符
            name: 自定义中文名称
            side_L: 左侧板
            side_R: 右侧板
            x_range: (x0, x1) 限制宽度（用于中立板打断），None 则为全宽
        """
        p = self.params
        label = label or f"shelf_z{z_center:.0f}"
        name = name or f"层板({z_center:.0f}mm)"
        panel_type = "fixed_shelf" if fixed else "movable_shelf"

        shelf_d = p.side_depth - p.back_offset - p.T_back

        if x_range is not None:
            x0, x1 = x_range
            shelf_w = x1 - x0
            x = x0
        else:
            if side_L is None:
                side_L = self._placements[0]
            if side_R is None:
                side_R = self._placements[1]
            cx, shelf_w = FaceQuery.placed_between_x(side_L, side_R)
            x = cx - shelf_w / 2

        y = p.back_offset + p.T_back
        placement = PanelPlacement(
            id=label,
            name=name,
            panel_type=panel_type,
            size_x=shelf_w,
            size_y=shelf_d,
            size_z=p.T,
            pos_x=x,
            pos_y=y,
            pos_z=z_center - p.T / 2,
            depends_on=["left_side_panel", "right_side_panel"],
            note="固定层板" if fixed else "活动层板",
        )
        self._placements.append(placement)
        return placement

    def place_divider(
        self,
        x_center: float,
        *,
        from_z: float | None = None,
        to_z: float | None = None,
    ) -> PanelPlacement:
        """放置中立板（竖隔板）。

        Args:
            x_center: 中立板 X 中心 mm
            from_z: 起始 Z（默认 z_bottom_internal）
            to_z: 终止 Z（默认 z_top_internal）
        """
        p = self.params
        z0 = from_z if from_z is not None else p.z_bottom_internal
        z1 = to_z if to_z is not None else p.z_top_internal
        dh = z1 - z0
        divider_d = p.side_depth - p.back_offset - p.T_back
        y = p.back_offset + p.T_back

        placement = PanelPlacement(
            id=f"divider_x{x_center:.0f}",
            name=f"中立板({x_center:.0f})",
            panel_type="divider",
            size_x=p.T,
            size_y=divider_d,
            size_z=dh,
            pos_x=x_center - p.T / 2,
            pos_y=y,
            pos_z=z0,
            depends_on=["left_side_panel", "right_side_panel"],
            note=f"中立板，高{dh:.0f}mm",
        )
        self._placements.append(placement)
        return placement

    def place_toe_kick_frame(
        self,
        side_L: PanelPlacement | None = None,
        side_R: PanelPlacement | None = None,
    ) -> List[PanelPlacement]:
        """放置踢脚板框架：后踢脚 + 前踢脚 + 2条中间支撑。

        踢脚线高度为 0 时跳过。
        """
        p = self.params
        if p.toe_kick_h <= 0:
            return []

        if side_L is None:
            side_L = self._placements[0]
        if side_R is None:
            side_R = self._placements[1]

        cx, kick_w = FaceQuery.placed_between_x(side_L, side_R)
        x = cx - kick_w / 2
        results = []

        # 后踢脚板（Y=0~T，靠背板侧）
        back_kick = PanelPlacement(
            id="toe_kick_back",
            name="后踢脚板",
            panel_type="toe_kick",
            size_x=kick_w,
            size_y=p.T,
            size_z=p.toe_kick_h,
            pos_x=x,
            pos_y=0.0,
            pos_z=0.0,
            depends_on=["left_side_panel", "right_side_panel"],
        )
        self._placements.append(back_kick)
        results.append(back_kick)

        # 前踢脚板（Y=side_depth-T~side_depth，靠门侧）
        front_kick = PanelPlacement(
            id="toe_kick_front",
            name="前踢脚板",
            panel_type="toe_kick",
            size_x=kick_w,
            size_y=p.T,
            size_z=p.toe_kick_h,
            pos_x=x,
            pos_y=p.side_depth - p.T,
            pos_z=0.0,
            depends_on=["left_side_panel", "right_side_panel"],
        )
        self._placements.append(front_kick)
        results.append(front_kick)

        # 中间支撑板 ×2（沿 X 方向分布）
        inner_d = p.side_depth - 2 * p.T
        gap = kick_w / 3
        for i in range(2):
            sx = x + (i + 1) * gap
            support = PanelPlacement(
                id=f"toe_kick_support_{i + 1}",
                name=f"踢脚支撑{i + 1}",
                panel_type="toe_kick",
                size_x=p.T,
                size_y=inner_d,
                size_z=p.toe_kick_h,
                pos_x=sx,
                pos_y=p.T,
                pos_z=0.0,
                depends_on=["left_side_panel", "right_side_panel"],
            )
            self._placements.append(support)
            results.append(support)

        return results

    def place_back_panel(
        self,
        side_L: PanelPlacement | None = None,
        side_R: PanelPlacement | None = None,
    ) -> PanelPlacement:
        """放置背板：距背面 back_offset mm，插槽安装。

        背板高度 = H - toe_kick_h，宽度 = internal_W。
        """
        p = self.params
        if side_L is None:
            side_L = self._placements[0]
        if side_R is None:
            side_R = self._placements[1]

        cx, back_w = FaceQuery.placed_between_x(side_L, side_R)
        x = cx - back_w / 2
        bh = p.H - p.toe_kick_h
        z = p.toe_kick_h
        y = p.back_offset

        placement = PanelPlacement(
            id="back_panel",
            name="背板",
            panel_type="back",
            size_x=back_w,
            size_y=p.T_back,
            size_z=bh,
            pos_x=x,
            pos_y=y,
            pos_z=z,
            depends_on=["left_side_panel", "right_side_panel", "bottom_panel"],
            note=f"距后{p.back_offset:.0f}mm插槽安装",
        )
        self._placements.append(placement)
        return placement

    def place_door(
        self,
        side: str,
        *,
        door_w: float | None = None,
        door_h: float | None = None,
    ) -> PanelPlacement:
        """放置门板。

        Args:
            side: "left" / "right" / "single" / "mid_{i}"
            door_w: 门板宽度（None 则按等分计算）
            door_h: 门板高度（None 则按全高 - 间隙计算）
        """
        p = self.params
        if door_h is None:
            door_h = p.H - p.toe_kick_h - p.door_margin * 2
        if door_w is None:
            door_w = (p.W - p.door_margin * 2 * 2) / 2

        if side == "left":
            x = p.door_margin
            name = "左门板"
        elif side == "right":
            x = p.W - p.door_margin - door_w
            name = "右门板"
        elif side == "single":
            x = p.W / 2 - door_w / 2
            name = "门板"
        else:
            if side.startswith("door_"):
                idx = int(side.split("_")[1])
                x = p.door_margin * (2 * idx - 1) + door_w * (idx - 1)
                name = f"门板{idx}"
            else:
                x = p.W / 2 - door_w / 2
                name = "门板"

        door_y = p.side_depth + p.door_hinge_gap

        placement = PanelPlacement(
            id=f"{side}_door",
            name=name,
            panel_type="door",
            size_x=door_w,
            size_y=p.T_door,
            size_z=door_h,
            pos_x=x,
            pos_y=door_y,
            pos_z=p.toe_kick_h + p.door_margin,
            depends_on=["left_side_panel", "right_side_panel"],
            note=f"门板，{door_w:.0f}×{door_h:.0f}×{p.T_door:.0f}mm",
        )
        self._placements.append(placement)
        return placement

    def place_doors(self, n: int = 2) -> List[PanelPlacement]:
        """放置 n 扇等宽门板。

        Args:
            n: 门板数量
        """
        door_w = (self.params.W - self.params.door_margin * 2 * n) / n
        results = []
        for i in range(n):
            if n == 1:
                side = "single"
            elif n == 2:
                side = "left" if i == 0 else "right"
            else:
                side = f"door_{i + 1}"
            results.append(self.place_door(side, door_w=door_w))
        return results

    # ---- 批量规划 ----

    def plan_all(
        self,
        shelf_count: int = 4,
        n_doors: int = 2,
    ) -> List[PanelPlacement]:
        """一键规划完整柜体（落地柜默认结构）。

        等同于:
            侧板×2 + 顶板 + 底板 + 背板 + 踢脚线 + N层板 + N门板

        Returns:
            List[PanelPlacement]: 按放置顺序排列
        """
        self.place_side_panels()
        self.place_top_panel()
        self.place_bottom_panel()
        self.place_back_panel()
        self.place_toe_kick_frame()

        # 层板：等分内高
        if shelf_count > 0:
            total_layers = shelf_count + 1
            layer_h = self.internal_H / total_layers
            for i in range(1, shelf_count + 1):
                z = self.z_bottom_internal + i * layer_h - self.T / 2
                self.place_shelf(z, fixed=True)

        # 门板
        if n_doors > 0:
            self.place_doors(n_doors)

        return self._placements