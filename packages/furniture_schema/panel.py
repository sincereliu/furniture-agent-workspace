"""板件数据模型 — PanelPlacement, PanelRecord 和 PanelLabel

纯 dataclass，不依赖任何 CAD 引擎（如 build123d）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PanelPlacement:
    """规划器输出的单块板件定位信息，不包含任何 CAD 对象。

    字段说明:
        id:           内部标识符（如 left_side_panel, top_panel）
        name:         中文名称（如 左侧板, 顶板）
        panel_type:   板件类型（side / top / bottom / shelf / divider / back / door / toe_kick）
        size_x/y/z:   板件三维尺寸 mm
        pos_x/y/z:    板件 min corner 在全局坐标系中的位置 mm
        depends_on:   依赖的其他板件 id 列表
        note:         备注说明
    """

    id: str
    name: str
    panel_type: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    depends_on: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class PanelLabel:
    """单块板件的标签数据（原在 order.py，移至面板模块更合理）"""

    label_id: str               # "260709-0001-KITCHEN-S01"
    order_id: str
    room: str
    panel_name: str
    panel_type: str
    length_mm: float
    width_mm: float
    thickness_mm: float
    material: str
    color: str = ""
    edge_banding: str = ""
    cut_x_mm: float = 0.0      # 在板材上的排样位置
    cut_y_mm: float = 0.0
    board_index: int = 1       # 所属板材编号


@dataclass
class PanelRecord:
    """单块板件的完整生产数据。

    字段说明:
        label:        内部标识符（如 left_side_panel, top_panel）
        name:         中文名称（如 左侧板, 顶板）
        panel_type:   板件类型（side / top / bottom / shelf / divider / back / door / toe_kick）
        material:     材料名称（如 18mm免漆板）
        thickness:    板厚 mm
        length_mm:    开料长度 mm（X 方向）
        width_mm:     开料宽度 mm（Y 方向）
        size_x/y/z:   板件三维尺寸 mm
        quantity:     数量
        drill_length: 系统孔计算长度 mm
        edge_banding: 封边规则 dict（边 → 封边材料）
        note:         备注说明
        pos_x/y/z:    左下前角在全局坐标系中的位置 mm

    注意：不包含 build123d Solid 对象。Solid 由 Emitter 层按需创建。
    """

    label: str
    name: str
    panel_type: str
    material: str
    thickness: float
    length_mm: float
    width_mm: float
    size_x: float = 0.0
    size_y: float = 0.0
    size_z: float = 0.0
    quantity: int = 1
    drill_length: float = 0.0
    edge_banding: Dict[str, str] = field(default_factory=dict)
    note: str = ""

    # 面约束定位：面板左下前角在全局坐标系中的位置
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0

    @property
    def area_m2(self) -> float:
        """展开面积（平方米）"""
        return self.length_mm * self.width_mm * self.quantity / 1_000_000

    @property
    def volume_m3(self) -> float:
        """体积（立方米）"""
        return (
            self.length_mm * self.width_mm * self.thickness * self.quantity
            / 1_000_000_000
        )

    def edge_banding_summary(self) -> str:
        """封边信息摘要"""
        if not self.edge_banding:
            return "无"
        return ", ".join(
            f"{edge}:{material}" for edge, material in self.edge_banding.items()
        )

    @classmethod
    def from_placement(
        cls,
        placement: PanelPlacement,
        material: str = "",
        thickness: float = 0.0,
        edge_banding: Dict[str, str] | None = None,
        drill_length: float = 0.0,
    ) -> "PanelRecord":
        """从 PanelPlacement 创建 PanelRecord。"""
        return cls(
            label=placement.id,
            name=placement.name,
            panel_type=placement.panel_type,
            material=material,
            thickness=thickness,
            length_mm=placement.size_x,
            width_mm=placement.size_y,
            size_x=placement.size_x,
            size_y=placement.size_y,
            size_z=placement.size_z,
            pos_x=placement.pos_x,
            pos_y=placement.pos_y,
            pos_z=placement.pos_z,
            drill_length=drill_length,
            edge_banding=edge_banding or {},
            note=placement.note,
        )