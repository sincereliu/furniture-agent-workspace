"""家具规格 — FurnitureSpec 和 Feature Tree 类型定义

所有下游模块共享的输入/输出契约。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ── 品类预设默认值 ──────────────────────────────────────────────
# 所有品类的默认尺寸统一在此定义，AI Agent 和运行时共用。
# 用户传入的 JSON 字段优先；缺失时从预设取值；预设缺字段时走 dataclass fallback。

CABINET_PRESETS: Dict[str, Dict[str, Any]] = {
    "floor_cabinet": {
        "width": 800,
        "height": 2000,
        "depth": 600,
        "toe_kick_height": 50,
        "shelf_count": 4,
        "n_doors": 2,
    },
    "wall_cabinet": {
        "width": 800,
        "height": 900,
        "depth": 350,
        "toe_kick_height": 0,
        "shelf_count": 1,
        "n_doors": 2,
    },
}


def _get_preset(furniture_type: str) -> Dict[str, Any] | None:
    """获取品类预设，找不到则返回 None。"""
    return CABINET_PRESETS.get(furniture_type)


@dataclass
class FurnitureSpec:
    """标准化的柜体输入规格。

    字段说明:
        furniture_type: 家具类型（floor_cabinet / wall_cabinet）
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
    groove_depth: float = 6.0
    groove_clearance: float = 1.0
    # 五金偏好 (Phase 2)
    hinge_brand: str = ""           # 铰链品牌 ""=默认, "Blum", "DTC" 等
    hinge_variant: str = ""         # 铰链规格组 ""=自动, "进口35mm杯全盖" 等
    hinge_overlay: str = "full"     # 盖法: full=全盖, half=半盖, inset=内嵌
    hinge_angle: int = 100          # 开启角度: 90, 110, 135, 165
    # 扩展
    options: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_cabinet(self) -> bool:
        return self.furniture_type in (
            "floor_cabinet",
            "wall_cabinet",
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FurnitureSpec":
        """从字典构建规格，自动做单位转换和默认值填充。

        品类默认尺寸从 CABINET_PRESETS 获取；用户传入值可覆盖。
        """
        furniture_type = str(data.get("type", "")).strip().lower()
        preset = _get_preset(furniture_type)

        def _get(key: str, fallback: Any) -> Any:
            if key in data and data[key] is not None:
                return data[key]
            if preset and key in preset:
                return preset[key]
            return fallback

        return cls(
            furniture_type=furniture_type,
            width=float(_get("width", 0)),
            depth=float(_get("depth", 0)),
            height=float(_get("height", 0)),
            board_thickness=float(_get("board_thickness", 18.0)),
            back_thickness=float(_get("back_thickness", 9.0)),
            door_thickness=float(_get("door_thickness", 18.0)),
            toe_kick_height=float(_get("toe_kick_height", 50.0)),
            back_offset=float(_get("back_offset", 18.0)),
            door_margin=float(_get("door_margin", 1.5)),
            door_hinge_gap=float(_get("door_hinge_gap", 2.0)),
            shelf_count=int(_get("shelf_count", 4)),
            n_doors=int(_get("n_doors", 2)),
            groove_depth=float(_get("groove_depth", 6.0)),
            groove_clearance=float(_get("groove_clearance", 1.0)),
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