"""Structured contract admitted by the ``panel_plan`` stage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import isfinite
from typing import Any, Mapping

from .cabinet_envelope import CABINET_CATEGORIES, CabinetEnvelope
from .panel_rules import default_toe_kick_support_count, even_shelf_gap


VALID_BACK_MOUNTS = frozenset({"groove", "insert", "cover"})

VALID_SHELF_TYPES = frozenset({"fixed", "movable"})

#: 中立板相对那条缝怎么摆：缝定锚，板厚对称或贴在缝的一侧。
#: 毫米由评估器算（`interior_structure.evaluate_interior`），提案只说对准哪条缝。
VALID_DIVIDER_ALIGNS = frozenset({"center", "left_face", "right_face"})

#: 一扇门挂在哪条竖直边上。对开腔由几何决定（左 left、右 right）；
#: 单开腔由提案给，没给就留空（板件阶段只报警告，客户在板件页上选）。
VALID_DOOR_HINGES = frozenset({"left", "right"})

# Shop sheet-stock catalog. See references/sheet-stock-catalog.md.
CARCASS_STOCK_MM = frozenset({18.0, 22.0})
BACK_STOCK_MM = 9.0
PROCESS_CARD_CARCASS_MM = 18.0

#: 车间进料板幅 `(宽, 长)`。板件的两个平面尺寸进不去就是做不出来，
#: 校验按这一档判（见 validation_panels 的 `_validate_sheet_capacity`）。
SHEET_STOCK_MM = frozenset({(1220.0, 2440.0), (1220.0, 2745.0)})
PROCESS_CARD_SHEET_MM = (1220.0, 2440.0)


@dataclass(frozen=True)
class ShelfSpec:
    """一层板（固定/活动）及其下方净高。

    gap_below_mm：本层板底面 到 下方紧邻一层顶面 的净高（mm）；
    None 表示「计算层」，由内净高反推、吸收剩余。
    """

    shelf_type: str                # "fixed" | "movable"
    gap_below_mm: float | None     # None = 计算层


def _coerce_shelves(raw: Any) -> list[ShelfSpec]:
    """把 shelves 输入规范化为 ShelfSpec 列表。"""
    if not isinstance(raw, (list, tuple)):
        raise ValueError("shelves must be a list")
    result: list[ShelfSpec] = []
    for item in raw:
        if isinstance(item, ShelfSpec):
            result.append(item)
            continue
        if not isinstance(item, Mapping):
            raise ValueError("each shelf entry must be an object")
        shelf_type = item.get("shelf_type")
        if shelf_type not in VALID_SHELF_TYPES:
            raise ValueError(
                "shelf type must be one of: " + ", ".join(sorted(VALID_SHELF_TYPES))
            )
        gap = item.get("gap_below_mm")
        if gap is None:
            gap_below: float | None = None
        else:
            gap_below = float(gap)
            if gap_below < 0:
                raise ValueError("gap_below_mm must be non-negative or null")
        result.append(ShelfSpec(shelf_type=shelf_type, gap_below_mm=gap_below))
    return result

@dataclass(frozen=True)
class DividerSpec:
    """一块中立板：只说对准哪条缝。

    板厚不是提案字段——中立板是柜体板，厚度取已准入的 `board_thickness`；
    位置与区间由评估器按缝和板厚算，见 references/interior-structure-contract.md。
    """

    seam_index: int                # 缝序号，从左起、0 开始；缝 i 在门 i 与门 i+1 之间
    seam_align: str = "center"     # "center" | "left_face" | "right_face"


def _coerce_dividers(raw: Any) -> list[DividerSpec]:
    """把 dividers 输入规范化为 DividerSpec 列表；不写就是没有中立板。"""
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise ValueError("dividers must be a list")
    result: list[DividerSpec] = []
    for item in raw:
        if isinstance(item, DividerSpec):
            result.append(item)
            continue
        if not isinstance(item, Mapping):
            raise ValueError("each divider entry must be an object")
        unknown = sorted(set(item) - {"seam_index", "seam_align"})
        if unknown:
            raise ValueError("divider does not support: " + ", ".join(unknown))
        seam_index = item.get("seam_index")
        if isinstance(seam_index, bool) or not isinstance(seam_index, int):
            raise ValueError("divider seam_index must be an integer")
        if seam_index < 0:
            raise ValueError("divider seam_index cannot be negative")
        align = item.get("seam_align", "center")
        if align not in VALID_DIVIDER_ALIGNS:
            raise ValueError(
                "divider seam_align must be one of: "
                + ", ".join(sorted(VALID_DIVIDER_ALIGNS))
            )
        result.append(DividerSpec(seam_index=seam_index, seam_align=str(align)))
    return result


def _coerce_door_hinges(raw: Any) -> list[str]:
    """把 door_hinges 规范化为「每扇门一个 left/right」；不写就是没定。

    写法是 `["left", "right", …]`，从左到右、长度必须等于 `n_doors`。
    对开腔那两位必须左 left、右 right（几何逼死），单开腔由提案决定；
    一致性在几何层核对（`construction_geometry.door_hinge_sides`）。
    """
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise ValueError("door_hinges must be a list")
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str) or item not in VALID_DOOR_HINGES:
            raise ValueError(
                "door hinge must be one of: " + ", ".join(sorted(VALID_DOOR_HINGES))
            )
        result.append(item)
    return result


# Construction fields that remain required after proposal admission.
# Sheet stock, an omitted toe-kick support count, and a fully omitted
# shelf-gap set are expanded first. Serialized specs stay complete and
# do not pass through that expansion.
PANEL_REQUIRED_PARAMETER_FIELDS = frozenset(
    {
        "toe_kick_height", "back_offset", "front_face_margin", "front_gap",
        "groove_depth", "groove_clearance", "toe_kick_reveal_front",
        "toe_kick_reveal_back", "toe_kick_support_count", "back_mount",
        "back_rail_height", "drawer_count", "drawer_side_clearance",
        "drawer_layer_gap", "drawer_back_clearance", "shelves", "top_gap_mm",
        "n_doors",
    }
)
PANEL_STOCK_FIELDS = frozenset(
    {
        "board_thickness",
        "back_thickness",
        "door_thickness",
        "drawer_bottom_thickness",
        "drawer_back_thickness",
        "sheet_width_mm",
        "sheet_length_mm",
    }
)
#: 可省略的构造字段：不写 = 没有中立板 / 每扇门的铰链侧没定。省略不是「按柜型猜」，
#: 见 references/interior-structure-contract.md 与 references/door-hinge-side.md。
PANEL_OPTIONAL_PARAMETER_FIELDS = frozenset({"dividers", "door_hinges"})

PANEL_PARAMETER_FIELDS = (
    PANEL_REQUIRED_PARAMETER_FIELDS | PANEL_STOCK_FIELDS
    | PANEL_OPTIONAL_PARAMETER_FIELDS
)
PANEL_SPEC_FIELDS = PANEL_PARAMETER_FIELDS
_SERIALIZED_FIELDS = PANEL_PARAMETER_FIELDS | {
    "furniture_category", "width", "depth", "height",
}
#: 不写也合法的字段：序列化输出为空时不落盘（老工程产出逐字节不变）。
_OPTIONAL_SERIALIZED_FIELDS = PANEL_OPTIONAL_PARAMETER_FIELDS
#: 后加的料档字段：老冻结文件里没有，读时按工艺卡默认补（写时一定带上）。
_READ_DEFAULTED_FIELDS = frozenset({"sheet_width_mm", "sheet_length_mm"})


@dataclass
class FurnitureSpec:
    """Complete, executable construction specification."""

    furniture_category: str
    width: float
    depth: float
    height: float
    board_thickness: float
    back_thickness: float
    door_thickness: float
    toe_kick_height: float
    back_offset: float
    front_face_margin: float
    front_gap: float
    shelves: list[ShelfSpec]
    top_gap_mm: float
    n_doors: int
    drawer_count: int
    groove_depth: float
    groove_clearance: float
    toe_kick_reveal_front: float
    toe_kick_reveal_back: float
    toe_kick_support_count: int
    back_mount: str
    back_rail_height: float
    drawer_side_clearance: float
    drawer_layer_gap: float
    drawer_bottom_thickness: float
    drawer_back_thickness: float
    drawer_back_clearance: float

    #: 车间板幅 `(宽, 长)` 两档之一：1220×2440 或 1220×2745。提案可省略
    #: （工艺卡默认 1220×2440），省略后由 `expand_sheet_stock` 展开。
    #: 它决定"这块板做不做得出来"，所以随板件冻结，不再由校验临时猜。
    sheet_width_mm: float
    sheet_length_mm: float

    #: 中立板：可选。不写就是没有；写了则由评估器给毫米（见 construction_geometry）。
    dividers: list[DividerSpec] = field(default_factory=list)

    #: 每扇门的铰链侧：可选，从左到右、长度等于 `n_doors`。不写就由几何推
    #: （对开腔自动 left/right，单开腔留空）。见 references/door-hinge-side.md。
    door_hinges: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.furniture_category not in CABINET_CATEGORIES:
            raise ValueError(
                f"furniture_category must be an executable canonical category: "
                f"{self.furniture_category}"
            )
        for name in (
            "width", "depth", "height", "board_thickness", "back_thickness",
            "door_thickness", "toe_kick_height", "back_offset", "front_face_margin",
            "front_gap", "groove_depth", "groove_clearance",
            "toe_kick_reveal_front", "toe_kick_reveal_back", "back_rail_height",
            "drawer_side_clearance", "drawer_layer_gap", "drawer_bottom_thickness",
            "drawer_back_thickness", "drawer_back_clearance",
            "sheet_width_mm", "sheet_length_mm",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
            ):
                raise ValueError(f"{name} must be numeric and finite")
        for name in ("n_doors", "drawer_count", "toe_kick_support_count"):
            _require_count(getattr(self, name), name)
        self.back_mount = resolve_back_mount(self.back_mount)
        self.shelves = _coerce_shelves(self.shelves)
        self.dividers = _coerce_dividers(self.dividers)
        self.door_hinges = _coerce_door_hinges(self.door_hinges)
        _validate_objective_invariants(self)
        _validate_sheet_stock(self)

    @classmethod
    def from_envelope(
        cls,
        envelope: CabinetEnvelope | Mapping[str, Any],
        options: Mapping[str, Any] | None,
    ) -> "FurnitureSpec":
        """Admit a proposal against a cabinet envelope snapshot.

        Omitted sheet stock, an omitted toe-kick support count, and a
        fully omitted shelf-gap set are expanded here. Explicit numbers
        are kept.
        """
        unit = CabinetEnvelope.from_mapping(envelope)
        if not isinstance(options, Mapping):
            raise ValueError("panel proposal must be an object")
        values = dict(options)
        unknown = sorted(set(values) - PANEL_SPEC_FIELDS)
        if unknown:
            raise ValueError("panel stage does not support: " + ", ".join(unknown))
        values = expand_sheet_stock(values)
        values = expand_omitted_panel_geometry(
            values, width=unit.width, height=unit.height,
        )
        missing = sorted(PANEL_REQUIRED_PARAMETER_FIELDS - set(values))
        if missing:
            raise ValueError(
                "panel proposal is incomplete; missing: " + ", ".join(missing)
            )
        return cls.from_dict(
            {
                "furniture_category": unit.furniture_category,
                "width": unit.width,
                "depth": unit.depth,
                "height": unit.height,
                **values,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FurnitureSpec":
        """Read a serialized complete spec without filling missing values."""
        values = dict(data)
        unknown = sorted(set(values) - _SERIALIZED_FIELDS)
        missing = sorted(
            _SERIALIZED_FIELDS - _OPTIONAL_SERIALIZED_FIELDS
            - _READ_DEFAULTED_FIELDS - set(values)
        )
        if unknown:
            raise ValueError(
                "serialized panel spec does not support: " + ", ".join(unknown)
            )
        if missing:
            raise ValueError(
                "serialized panel spec is incomplete; missing: " + ", ".join(missing)
            )
        # 老冻结文件里没有 dividers / door_hinges 键也要读得回来。
        values.setdefault("dividers", [])
        values.setdefault("door_hinges", [])
        # 板幅是后加的字段：老冻结文件没写，按工艺卡默认读回来（和提案省略同一口径）。
        # 不改写文件，新产出一律带上这两个毫米。
        values.setdefault("sheet_width_mm", PROCESS_CARD_SHEET_MM[0])
        values.setdefault("sheet_length_mm", PROCESS_CARD_SHEET_MM[1])
        if "shelves" in values:
            values["shelves"] = _coerce_shelves(values["shelves"])
        return cls(**values)


def spec_payload(spec: FurnitureSpec) -> dict[str, Any]:
    """板件阶段写进柜体 `spec` 的序列化形状。

    为空的**可选**字段不落盘（现在有 `dividers`、`door_hinges`）：没有中立板、
    没有逐扇铰链侧的老工程产出，与加这两个字段之前逐字节相同。冻结文件里带了值就照写。
    """
    payload = asdict(spec)
    for name in _OPTIONAL_SERIALIZED_FIELDS:
        if not payload.get(name):
            payload.pop(name, None)
    return payload


def resolve_back_mount(requested: str) -> str:
    """Admit an explicit back-mount strategy."""
    if requested not in VALID_BACK_MOUNTS:
        raise ValueError(
            f"back_mount must be one of: {', '.join(sorted(VALID_BACK_MOUNTS))}"
        )
    return requested


def expand_sheet_stock(options: Mapping[str, Any]) -> dict[str, Any]:
    """Fill omitted sheet-stock fields from the shop process card.

    Structured protocol: carcass 18; rolled back 9 for groove/cover;
    insert back and drawer box inherit carcass; door inherits carcass
    unless an admitted catalog value is supplied; sheet format defaults
    to 1220×2440. Serialized specs must already be complete and do not go
    through this expansion.
    """
    values = dict(options)
    board = _admit_optional_stock(
        values.pop("board_thickness", None),
        "board_thickness",
        PROCESS_CARD_CARCASS_MM,
        CARCASS_STOCK_MM,
    )
    values["board_thickness"] = board
    back_default, back_allowed = _back_stock_for_mount(values.get("back_mount"), board)
    values["back_thickness"] = _admit_optional_stock(
        values.pop("back_thickness", None),
        "back_thickness",
        back_default,
        back_allowed,
    )
    values["door_thickness"] = _admit_optional_stock(
        values.pop("door_thickness", None),
        "door_thickness",
        board,
        CARCASS_STOCK_MM,
    )
    sheet_width, sheet_length = _admit_sheet_format(
        values.pop("sheet_width_mm", None),
        values.pop("sheet_length_mm", None),
    )
    values["sheet_width_mm"] = sheet_width
    values["sheet_length_mm"] = sheet_length
    for name in ("drawer_bottom_thickness", "drawer_back_thickness"):
        values[name] = _admit_optional_stock(
            values.pop(name, None),
            name,
            board,
            frozenset({board}),
        )
    return values


def expand_omitted_panel_geometry(
    options: Mapping[str, Any],
    *,
    width: float,
    height: float,
) -> dict[str, Any]:
    """Fill an omitted support count and a fully omitted shelf-gap set.

    Structured protocol for proposal admission only. An explicit support
    count is kept. Shelf openings are even-split only when every shelf
    omits ``gap_below_mm`` and ``top_gap_mm`` is absent. Serialized specs
    must already contain the concrete numbers and do not call this.
    """
    values = dict(options)
    _fill_omitted_support_count(values, width)
    _fill_omitted_even_shelves(values, height)
    return values


def _fill_omitted_support_count(values: dict[str, Any], width: float) -> None:
    if "toe_kick_support_count" in values:
        return
    toe_kick_height = values.get("toe_kick_height")
    if not _is_finite_number(toe_kick_height):
        return
    values["toe_kick_support_count"] = default_toe_kick_support_count(
        width, float(toe_kick_height),
    )


def _fill_omitted_even_shelves(values: dict[str, Any], height: float) -> None:
    if "top_gap_mm" in values:
        return
    shelves = values.get("shelves")
    if not isinstance(shelves, (list, tuple)) or len(shelves) < 1:
        return
    if not all(_shelf_gap_unspecified(item) for item in shelves):
        return
    board_thickness = values.get("board_thickness")
    toe_kick_height = values.get("toe_kick_height")
    if not _is_finite_number(board_thickness) or not _is_finite_number(toe_kick_height):
        return
    internal_height = height - float(toe_kick_height) - 2 * float(board_thickness)
    gap = even_shelf_gap(internal_height, len(shelves), float(board_thickness))
    values["shelves"] = [_shelf_with_gap(item, gap) for item in shelves]
    values["top_gap_mm"] = gap


def _shelf_gap_unspecified(item: Any) -> bool:
    if isinstance(item, ShelfSpec):
        return item.gap_below_mm is None
    if isinstance(item, Mapping):
        return item.get("gap_below_mm") is None
    return False


def _shelf_with_gap(item: Any, gap: float) -> Any:
    if isinstance(item, ShelfSpec):
        return ShelfSpec(shelf_type=item.shelf_type, gap_below_mm=gap)
    if isinstance(item, Mapping):
        copied = dict(item)
        copied["gap_below_mm"] = gap
        return copied
    return item


def _is_finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(value)
    )


def thickness_for_material_role(spec: FurnitureSpec, material_role: str) -> float:
    """Return the admitted stock thickness for a panel material role."""
    if material_role == "back":
        return spec.back_thickness
    if material_role == "door":
        return spec.door_thickness
    return spec.board_thickness


def _back_stock_for_mount(back_mount: Any, board: float) -> tuple[float, frozenset[float]]:
    """Groove/cover use rolled 9mm back; insert uses carcass stock."""
    if back_mount == "insert":
        return board, frozenset({board})
    return BACK_STOCK_MM, frozenset({BACK_STOCK_MM})


def _admit_optional_stock(
    raw: Any,
    name: str,
    default: float,
    allowed: frozenset[float],
) -> float:
    if raw is None:
        return default
    value = _finite_mm(raw, name)
    if value not in allowed:
        if name in {"drawer_bottom_thickness", "drawer_back_thickness"}:
            raise ValueError(f"{name} must equal board_thickness")
        raise ValueError(_stock_choice_error(name, allowed))
    return value


def _admit_sheet_format(
    raw_width: Any,
    raw_length: Any,
) -> tuple[float, float]:
    """板幅要么两个都给，要么都不给（工艺卡默认 1220×2440）。

    只给一个就是没说清是哪一档——不猜「宽都是 1220，那就按长补」。
    """
    if raw_width is None and raw_length is None:
        return PROCESS_CARD_SHEET_MM
    if raw_width is None or raw_length is None:
        raise ValueError(
            "sheet_width_mm and sheet_length_mm must be given together, or both omitted"
        )
    pair = (
        _finite_mm(raw_width, "sheet_width_mm"),
        _finite_mm(raw_length, "sheet_length_mm"),
    )
    if pair not in SHEET_STOCK_MM:
        raise ValueError(_sheet_choice_error())
    return pair


def _sheet_choice_error() -> str:
    shown = ", ".join(f"{width:g}×{length:g}" for width, length in sorted(SHEET_STOCK_MM))
    return f"sheet size must be one of: {shown}"


def _finite_mm(value: Any, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise ValueError(f"{name} must be numeric and finite")
    return float(value)


def _stock_choice_error(name: str, allowed: frozenset[float]) -> str:
    shown = ", ".join(
        str(int(item) if float(item).is_integer() else item)
        for item in sorted(allowed)
    )
    if len(allowed) == 1:
        return f"{name} must be {shown}"
    return f"{name} must be one of: {shown}"


def _validate_sheet_stock(spec: FurnitureSpec) -> None:
    if spec.board_thickness not in CARCASS_STOCK_MM:
        raise ValueError(_stock_choice_error("board_thickness", CARCASS_STOCK_MM))
    _, back_allowed = _back_stock_for_mount(spec.back_mount, spec.board_thickness)
    if spec.back_thickness not in back_allowed:
        raise ValueError(_stock_choice_error("back_thickness", back_allowed))
    if spec.door_thickness not in CARCASS_STOCK_MM:
        raise ValueError(_stock_choice_error("door_thickness", CARCASS_STOCK_MM))
    if (spec.sheet_width_mm, spec.sheet_length_mm) not in SHEET_STOCK_MM:
        raise ValueError(_sheet_choice_error())
    for name in ("drawer_bottom_thickness", "drawer_back_thickness"):
        if getattr(spec, name) != spec.board_thickness:
            raise ValueError(f"{name} must equal board_thickness")


def resolve_shelf_gaps(spec: FurnitureSpec, internal_height: float) -> list[float]:
    """返回每层板下方净高（从上到下），并解析空值计算层为「剩余」。

    computed = 内净高 − top_gap_mm − N×板厚 − 其余显式净高之和。
    """
    board = spec.board_thickness
    count = len(spec.shelves)
    explicit = [s.gap_below_mm for s in spec.shelves if s.gap_below_mm is not None]
    computed_count = count - len(explicit)
    if computed_count == 1:
        computed = internal_height - spec.top_gap_mm - count * board - sum(explicit)
        if computed < 0:
            raise ValueError("shelf gaps exceed the internal height")
        return [
            computed if s.gap_below_mm is None else s.gap_below_mm for s in spec.shelves
        ]
    total = spec.top_gap_mm + count * board + sum(explicit)
    if abs(total - internal_height) > 0.5:
        raise ValueError(
            "explicit shelf gaps and top gap do not fill the internal height "
            f"(sum={total:g}, internal_height={internal_height:g})"
        )
    return list(explicit)


def _require_count(value: Any, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")


def _validate_objective_invariants(spec: FurnitureSpec) -> None:
    positive = (
        "width", "depth", "height", "board_thickness", "back_thickness",
        "door_thickness", "drawer_side_clearance", "drawer_bottom_thickness",
        "drawer_back_thickness",
    )
    non_negative = (
        "toe_kick_height", "back_offset", "front_face_margin", "front_gap",
        "groove_clearance", "toe_kick_reveal_front", "toe_kick_reveal_back",
        "back_rail_height", "drawer_layer_gap", "drawer_back_clearance",
        "top_gap_mm",
    )
    if any(getattr(spec, name) <= 0 for name in positive):
        raise ValueError("positive dimensions and thicknesses are required")
    if any(getattr(spec, name) < 0 for name in non_negative):
        raise ValueError("clearances, margins and offsets cannot be negative")
    if spec.back_mount == "groove" and spec.groove_depth <= 0:
        raise ValueError("groove_depth must be positive for groove back_mount")
    if spec.furniture_category == "wall_cabinet" and (
        spec.toe_kick_height != 0
        or spec.toe_kick_support_count != 0
        or spec.drawer_count != 0
    ):
        raise ValueError(
            "wall_cabinet cannot contain a toe kick or full-height drawers"
        )
    if spec.toe_kick_height == 0 and spec.toe_kick_support_count != 0:
        raise ValueError("toe-kick supports require a positive toe_kick_height")
    if spec.drawer_count and (spec.shelves or spec.n_doors):
        raise ValueError("full-height drawers require no shelves and n_doors=0")
    if spec.dividers and spec.drawer_count:
        # 中立板站在内部净空里，整高抽屉区把这段净空占满了。
        raise ValueError("a full-height drawer zone cannot take a divider")
    if spec.dividers and spec.n_doors < 2:
        # 缝定锚：一扇门没有内缝，中立板无处可对。
        raise ValueError("a divider needs an inner seam, so at least 2 doors")
    if sum(1 for s in spec.shelves if s.gap_below_mm is None) > 1:
        raise ValueError("at most one shelf gap may be null")
    if spec.door_hinges and len(spec.door_hinges) != spec.n_doors:
        raise ValueError("door_hinges must have exactly one entry per door")
