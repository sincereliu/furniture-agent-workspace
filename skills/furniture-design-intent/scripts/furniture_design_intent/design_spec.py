"""Confirmed cabinet inputs shared by the stage runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

VALID_BACK_MOUNTS = frozenset({"auto", "groove", "insert", "cover"})
SUPPORTED_TYPES = frozenset({"floor_cabinet", "wall_cabinet"})

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
    toe_kick_reveal_front: float = 1.0
    toe_kick_reveal_back: float = 30.0
    toe_kick_support_count: int | None = None
    back_mount: str = "auto"
    back_rail_height: float = 70.0
    # 五金偏好（第二阶段）
    hinge_brand: str = ""           # 铰链品牌 ""=默认, "Blum", "DTC" 等
    hinge_variant: str = ""         # 铰链规格组 ""=自动, "进口35mm杯全盖" 等
    hinge_overlay: str = "full"     # 盖法: full=全盖, half=半盖, inset=内嵌
    hinge_angle: int = 100          # 开启角度: 90, 110, 135, 165
    # 扩展
    options: Dict[str, Any] = field(default_factory=dict)

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
            toe_kick_reveal_front=float(_get("toe_kick_reveal_front", 1.0)),
            toe_kick_reveal_back=float(_get("toe_kick_reveal_back", 30.0)),
            toe_kick_support_count=_optional_int(data.get("toe_kick_support_count")),
            back_mount=str(_get("back_mount", "auto")),
            back_rail_height=float(_get("back_rail_height", 70.0)),
            hinge_brand=str(_get("hinge_brand", "")),
            hinge_variant=str(_get("hinge_variant", "")),
            hinge_overlay=str(_get("hinge_overlay", "full")),
            hinge_angle=int(_get("hinge_angle", 100)),
            options=data.get("options", {}),
        )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("toe_kick_support_count must be an integer or null")
    try:
        converted = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("toe_kick_support_count must be an integer or null") from exc
    if isinstance(value, float) and not value.is_integer():
        raise ValueError("toe_kick_support_count must be an integer or null")
    if isinstance(value, str) and value.strip() != str(converted):
        raise ValueError("toe_kick_support_count must be an integer or null")
    return converted


def resolve_back_mount(spec_back_mount: str, back_thickness: float, board_thickness: float) -> str:
    """推导有效的背板安装模式。

    "auto"  → 薄背板 (back_thickness < board_thickness) 时使用 "groove"（槽装）
               厚背板 (back_thickness >= board_thickness) 时使用 "insert"（内嵌）
    "groove" / "insert" / "cover"  → 保持原值（显式覆盖）
    """
    mode = str(spec_back_mount).strip().lower()
    if mode not in VALID_BACK_MOUNTS:
        raise ValueError(
            f"back_mount must be one of: {', '.join(sorted(VALID_BACK_MOUNTS))}"
        )
    if mode != "auto":
        return mode
    return "insert" if back_thickness >= board_thickness else "groove"
