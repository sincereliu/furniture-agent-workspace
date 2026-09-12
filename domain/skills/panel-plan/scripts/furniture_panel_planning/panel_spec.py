"""Structured contract admitted by the ``panels_planned`` stage."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent, EXECUTABLE_CATEGORIES


VALID_BACK_MOUNTS = frozenset({"groove", "insert", "cover"})

VALID_SHELF_TYPES = frozenset({"fixed", "movable"})

# Shop sheet-stock catalog. See references/sheet-stock-catalog.md.
CARCASS_STOCK_MM = frozenset({18.0, 22.0})
BACK_STOCK_MM = 9.0
PROCESS_CARD_CARCASS_MM = 18.0


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

# Construction fields that remain required on every proposal. Sheet-stock
# fields may be omitted and are expanded from the shop process card.
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
    }
)
PANEL_PARAMETER_FIELDS = PANEL_REQUIRED_PARAMETER_FIELDS | PANEL_STOCK_FIELDS
PANEL_SPEC_FIELDS = PANEL_PARAMETER_FIELDS
_SERIALIZED_FIELDS = PANEL_PARAMETER_FIELDS | {
    "furniture_category", "width", "depth", "height",
}


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

    def __post_init__(self) -> None:
        if self.furniture_category not in EXECUTABLE_CATEGORIES:
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
        _validate_objective_invariants(self)
        _validate_sheet_stock(self)

    @classmethod
    def from_intent(
        cls,
        intent: DesignIntent,
        options: Mapping[str, Any] | None,
    ) -> "FurnitureSpec":
        """Admit a proposal against a confirmed finished envelope."""
        if not isinstance(intent, DesignIntent) or not intent.confirmed:
            raise ValueError("panel planning requires a confirmed DesignIntent")
        if not isinstance(options, Mapping):
            raise ValueError("panel proposal must be an object")
        values = dict(options)
        unknown = sorted(set(values) - PANEL_SPEC_FIELDS)
        if unknown:
            raise ValueError("panel stage does not support: " + ", ".join(unknown))
        values = expand_sheet_stock(values)
        missing = sorted(PANEL_REQUIRED_PARAMETER_FIELDS - set(values))
        if missing:
            raise ValueError(
                "panel proposal is incomplete; missing: " + ", ".join(missing)
            )
        dimensions = (
            intent.finished_envelope.width_mm,
            intent.finished_envelope.depth_mm,
            intent.finished_envelope.height_mm,
        )
        if any(value is None for value in dimensions):
            raise ValueError("panel planning requires a confirmed finished envelope")
        return cls.from_dict(
            {
                "furniture_category": intent.furniture_category,
                "width": dimensions[0],
                "depth": dimensions[1],
                "height": dimensions[2],
                **values,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FurnitureSpec":
        """Read a serialized complete spec without filling missing values."""
        values = dict(data)
        unknown = sorted(set(values) - _SERIALIZED_FIELDS)
        missing = sorted(_SERIALIZED_FIELDS - set(values))
        if unknown:
            raise ValueError(
                "serialized panel spec does not support: " + ", ".join(unknown)
            )
        if missing:
            raise ValueError(
                "serialized panel spec is incomplete; missing: " + ", ".join(missing)
            )
        if "shelves" in values:
            values["shelves"] = _coerce_shelves(values["shelves"])
        return cls(**values)


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
    unless an admitted catalog value is supplied. Serialized specs must
    already be complete and do not go through this expansion.
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
    for name in ("drawer_bottom_thickness", "drawer_back_thickness"):
        values[name] = _admit_optional_stock(
            values.pop(name, None),
            name,
            board,
            frozenset({board}),
        )
    return values


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
    if spec.n_doors > 2:
        raise ValueError(
            "current panel topology supports at most 2 doors; disambiguate multi-door opening strategy first"
        )
    if sum(1 for s in spec.shelves if s.gap_below_mm is None) > 1:
        raise ValueError("at most one shelf gap may be null")
