"""家具规格 — FurnitureSpec 和 Feature Tree 类型定义

所有下游模块共享的输入/输出契约。
"""

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

    def validation_errors(self) -> list[str]:
        """Validate the executable cabinet contract before stage execution."""
        errors: list[str] = []
        positive_fields = {
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "board_thickness": self.board_thickness,
            "back_thickness": self.back_thickness,
            "door_thickness": self.door_thickness,
        }
        for name, value in positive_fields.items():
            if value <= 0:
                errors.append(f"{name} must be greater than zero")

        non_negative_fields = {
            "toe_kick_height": self.toe_kick_height,
            "door_margin": self.door_margin,
            "door_hinge_gap": self.door_hinge_gap,
            "toe_kick_reveal_front": self.toe_kick_reveal_front,
            "toe_kick_reveal_back": self.toe_kick_reveal_back,
            "back_rail_height": self.back_rail_height,
        }
        for name, value in non_negative_fields.items():
            if value < 0:
                errors.append(f"{name} cannot be negative")

        if self.shelf_count < 0:
            errors.append("shelf_count cannot be negative")
        if self.n_doors < 0:
            errors.append("n_doors cannot be negative")
        if self.toe_kick_support_count is not None and self.toe_kick_support_count < 0:
            errors.append("toe_kick_support_count cannot be negative")

        try:
            back_mount = resolve_back_mount(
                self.back_mount,
                self.back_thickness,
                self.board_thickness,
            )
        except ValueError as exc:
            errors.append(str(exc))
            back_mount = None

        carcass_y_start = self.back_thickness if back_mount == "cover" else 0.0
        carcass_y_end = self.depth - self.door_thickness - self.door_hinge_gap
        carcass_depth = carcass_y_end - carcass_y_start
        internal_width = self.width - 2 * self.board_thickness
        actual_toe_kick = (
            self.toe_kick_height if self.furniture_type != "wall_cabinet" else 0.0
        )
        internal_height = self.height - actual_toe_kick - 2 * self.board_thickness

        if carcass_depth <= 0:
            if back_mount == "cover":
                errors.append(
                    "depth must exceed back_thickness + door_thickness + "
                    "door_hinge_gap for cover back mount"
                )
            else:
                errors.append("depth must exceed door_thickness + door_hinge_gap")
        if internal_width <= 0:
            errors.append("width must exceed twice board_thickness")
        if internal_height <= 0:
            errors.append(
                "height must exceed toe_kick_height + twice board_thickness"
            )

        if back_mount == "groove":
            if self.back_offset < carcass_y_start:
                errors.append("back_offset cannot be behind the cabinet carcass")
            if self.groove_depth <= 0:
                errors.append("groove_depth must be greater than zero")
            if self.groove_clearance < 0:
                errors.append("groove_clearance cannot be negative")
            if self.groove_depth > self.board_thickness:
                errors.append("groove_depth cannot exceed board_thickness")
            groove_width = self.back_thickness + self.groove_clearance
            if (
                self.back_offset < carcass_y_start
                or self.back_offset + groove_width > carcass_y_end
            ):
                errors.append("back groove must remain inside the cabinet side depth")
            rail_count = int(internal_height // 500) if internal_height > 0 else 0
            if (
                self.back_rail_height > 0
                and rail_count > 0
                and rail_count * self.back_rail_height > internal_height
            ):
                errors.append("back_rail_height leaves no positive rail spacing")
        elif back_mount == "insert":
            if self.back_offset < carcass_y_start:
                errors.append("back_offset cannot be behind the cabinet carcass")
            elif self.back_offset + self.back_thickness >= carcass_y_end:
                errors.append(
                    "inserted back must leave positive cabinet internal depth"
                )

        if actual_toe_kick > 0:
            support_depth = (
                carcass_depth
                - self.toe_kick_reveal_front
                - self.toe_kick_reveal_back
                - 2 * self.board_thickness
            )
            if support_depth <= 0:
                errors.append("toe-kick reveals leave no positive support depth")
            support_count = resolve_toe_kick_support_count(
                self.toe_kick_support_count,
                self.width,
            )
            if support_count * self.board_thickness >= internal_width:
                errors.append("toe_kick_support_count leaves no positive clear spacing")

        return errors

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
    """Derive the effective back mount mode.

    "auto"  → "groove" for thin back (back_thickness < board_thickness)
               "insert" for thick back (back_thickness >= board_thickness)
    "groove" / "insert" / "cover"  → as-is (explicit override)
    """
    mode = str(spec_back_mount).strip().lower()
    if mode not in VALID_BACK_MOUNTS:
        raise ValueError(
            f"back_mount must be one of: {', '.join(sorted(VALID_BACK_MOUNTS))}"
        )
    if mode != "auto":
        return mode
    return "insert" if back_thickness >= board_thickness else "groove"


def resolve_toe_kick_support_count(explicit: int | None, width: float) -> int:
    """Resolve the maintained project default for toe-kick supports."""
    if explicit is not None:
        return explicit
    if width < 600:
        return 0
    return 1 + int((width - 600) // 300)
