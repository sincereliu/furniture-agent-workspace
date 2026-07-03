"""家具规格 — FurnitureSpec 和 Feature Tree 类型定义

所有下游模块共享的输入/输出契约。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FurnitureSpec:
    """标准化的家具输入规格。

    字段说明:
        furniture_type: 家具类型（table / floor_cabinet / wall_cabinet / wardrobe）
        width:          总宽 mm（X 方向）
        depth:          总深 mm（Y 方向）
        height:         总高 mm（Z 方向）
        board_thickness: 柜体板厚 mm（默认 18.0）
        back_thickness:  背板板厚 mm（默认 9.0）
        door_thickness:  门板板厚 mm（默认 18.0）
        toe_kick_height: 踢脚线高度 mm（默认 50.0，吊柜为 0）
        back_offset:     背板距后 mm（默认 18.0）
        door_margin:     门板四周间隙 mm（默认 1.5）
        door_hinge_gap:  门铰链深度间隙 mm（默认 2.0）
        shelf_count:     层板数量（默认 4）
        n_doors:         门板数量（默认 2）
        top_thickness:   桌面厚度 mm（仅 table）
        leg_size:        桌腿截面尺寸 mm（仅 table）
        leg_inset:       桌腿内缩 mm（仅 table）
        options:         扩展选项字典
    """

    furniture_type: str
    width: float
    depth: float
    height: float
    board_thickness: float = 18.0
    back_thickness: float = 9.0
    door_thickness: float = 18.0
    toe_kick_height: float = 50.0
    back_offset: float = 18.0
    door_margin: float = 1.5
    door_hinge_gap: float = 2.0
    shelf_count: int = 4
    n_doors: int = 2
    # table 特有参数
    top_thickness: float = 30.0
    leg_size: float = 60.0
    leg_inset: float = 50.0
    # 扩展
    options: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_cabinet(self) -> bool:
        return self.furniture_type in (
            "floor_cabinet",
            "wall_cabinet",
            "wardrobe",
        )

    @property
    def is_table(self) -> bool:
        return self.furniture_type == "table"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FurnitureSpec":
        """从字典构建规格，自动做单位转换和默认值填充。"""
        furniture_type = str(data.get("type", "")).strip().lower()
        return cls(
            furniture_type=furniture_type,
            width=float(data.get("width", 0)),
            depth=float(data.get("depth", 0)),
            height=float(data.get("height", 0)),
            board_thickness=float(data.get("board_thickness", 18.0)),
            back_thickness=float(data.get("back_thickness", 9.0)),
            door_thickness=float(data.get("door_thickness", 18.0)),
            toe_kick_height=float(data.get("toe_kick_height", 50.0)),
            back_offset=float(data.get("back_offset", 18.0)),
            door_margin=float(data.get("door_margin", 1.5)),
            door_hinge_gap=float(data.get("door_hinge_gap", 2.0)),
            shelf_count=int(data.get("shelf_count", 4)),
            n_doors=int(data.get("n_doors", 2)),
            top_thickness=float(data.get("top_thickness", 30.0)),
            leg_size=float(data.get("leg_size", 60.0)),
            leg_inset=float(data.get("leg_inset", 50.0)),
            options=data.get("options", {}),
        )


@dataclass
class Feature:
    """特征树中的单个特征。

    字段说明:
        id:         唯一标识符
        type:       特征类型（box / compound）
        size:       {x, y, z} 尺寸 mm
        position:   {x, y, z} min corner 位置 mm
        depends_on: 依赖特征 id 列表
        tags:       语义标签列表（如 ["side", "left"]）
    """

    id: str
    type: str  # "box" | "compound"
    size: Dict[str, float]
    position: Dict[str, float]
    depends_on: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_placement(cls, placement: "PanelPlacement") -> "Feature":
        """从 PanelPlacement 构建 Feature。"""
        from .panel import PanelPlacement

        return cls(
            id=placement.id,
            type="box",
            size={"x": placement.size_x, "y": placement.size_y, "z": placement.size_z},
            position={"x": placement.pos_x, "y": placement.pos_y, "z": placement.pos_z},
            depends_on=list(placement.depends_on),
            tags=[placement.panel_type],
        )