"""Structured contract admitted by the ``panels_planned`` stage."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent, SUPPORTED_TYPES

from .panel_rules import resolve_door_hinge_side


VALID_BACK_MOUNTS = frozenset({"auto", "groove", "insert", "cover"})

# 活动层板连接方式：二选一。默认候选为 two_in_one，但必须是显式+待确认的提案值，
# 不得由代码静默补齐（见 panel-plan SKILL.md）。
VALID_MOVABLE_SHELF_CONNECTORS = frozenset({"two_in_one", "shelf_pin"})

VALID_SHELF_TYPES = frozenset({"fixed", "movable"})


@dataclass(frozen=True)
class ShelfSpec:
    """一层板（固定/活动）及其下方净高。

    gap_below_mm：本层板底面 到 下方紧邻一层顶面 的净高（mm）；
    None 表示「计算层」，由内净高反推、吸收剩余。
    """

    shelf_type: str                # "fixed" | "movable"
    gap_below_mm: float | None     # None = auto（计算层）


def _coerce_shelves(raw: Any) -> list[ShelfSpec]:
    """把 shelves 输入规范化为 ShelfSpec 列表（自动解析 gap_below_mm 的 auto）。"""
    if not isinstance(raw, (list, tuple)):
        raise ValueError("shelves must be a list")
    result: list[ShelfSpec] = []
    for item in raw:
        if isinstance(item, ShelfSpec):
            result.append(item)
            continue
        if not isinstance(item, Mapping):
            raise ValueError("each shelf entry must be an object")
        shelf_type = item.get("shelf_type", item.get("type"))
        if shelf_type not in VALID_SHELF_TYPES:
            raise ValueError(
                "shelf type must be one of: " + ", ".join(sorted(VALID_SHELF_TYPES))
            )
        gap = item.get("gap_below_mm")
        if gap is None or gap == "auto":
            gap_below: float | None = None
        else:
            gap_below = float(gap)
            if gap_below < 0:
                raise ValueError("gap_below_mm must be non-negative or 'auto'")
        result.append(ShelfSpec(shelf_type=shelf_type, gap_below_mm=gap_below))
    return result

# Every field is an LLM/user proposal decision. Runtime rejects omissions instead
# of selecting a cabinet profile or filling construction defaults.
PANEL_PARAMETER_FIELDS = frozenset(
    {
        "board_thickness", "back_thickness", "door_thickness",
        "toe_kick_height", "back_offset", "front_face_margin", "door_hinge_gap",
        "groove_depth", "groove_clearance", "toe_kick_reveal_front",
        "toe_kick_reveal_back", "toe_kick_support_count", "back_mount",
        "back_rail_height", "drawer_count", "drawer_side_clearance",
        "drawer_layer_gap", "drawer_bottom_thickness", "drawer_back_thickness",
        "drawer_back_clearance", "shelves", "top_gap_mm", "n_doors",
        "door_hinge_side", "movable_shelf_connector",
    }
)
PANEL_SPEC_FIELDS = PANEL_PARAMETER_FIELDS
_SERIALIZED_FIELDS = PANEL_PARAMETER_FIELDS | {
    "furniture_type", "width", "depth", "height",
}


@dataclass
class FurnitureSpec:
    """Complete, executable construction specification."""

    furniture_type: str
    width: float
    depth: float
    height: float
    board_thickness: float
    back_thickness: float
    door_thickness: float
    toe_kick_height: float
    back_offset: float
    front_face_margin: float
    door_hinge_gap: float
    shelves: list[ShelfSpec]
    top_gap_mm: float
    n_doors: int
    drawer_count: int
    groove_depth: float
    groove_clearance: float
    toe_kick_reveal_front: float
    toe_kick_reveal_back: float
    toe_kick_support_count: int | None
    back_mount: str
    back_rail_height: float
    drawer_side_clearance: float
    drawer_layer_gap: float
    drawer_bottom_thickness: float
    drawer_back_thickness: float
    drawer_back_clearance: float
    door_hinge_side: str | None
    movable_shelf_connector: str

    def __post_init__(self) -> None:
        if self.furniture_type not in SUPPORTED_TYPES:
            raise ValueError(
                f"furniture_type must be an executable canonical type: "
                f"{self.furniture_type}"
            )
        for name in (
            "width", "depth", "height", "board_thickness", "back_thickness",
            "door_thickness", "toe_kick_height", "back_offset", "front_face_margin",
            "door_hinge_gap", "groove_depth", "groove_clearance",
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
        for name in ("n_doors", "drawer_count"):
            _require_count(getattr(self, name), name)
        if self.toe_kick_support_count is not None:
            _require_count(self.toe_kick_support_count, "toe_kick_support_count")
        self.back_mount = resolve_back_mount(
            self.back_mount, self.back_thickness, self.board_thickness
        )
        self.shelves = _coerce_shelves(self.shelves)
        _validate_objective_invariants(self)

    @classmethod
    def from_intent(
        cls,
        intent: DesignIntent,
        options: Mapping[str, Any] | None,
    ) -> "FurnitureSpec":
        """Admit a complete proposal against a confirmed finished envelope."""
        if not isinstance(intent, DesignIntent) or not intent.confirmed:
            raise ValueError("panel planning requires a confirmed DesignIntent")
        if not isinstance(options, Mapping):
            raise ValueError("panel proposal must be an object")
        values = _normalize_panel_input_aliases(dict(options))
        unknown = sorted(set(values) - PANEL_SPEC_FIELDS)
        if unknown:
            raise ValueError("panel stage does not support: " + ", ".join(unknown))
        missing = sorted(PANEL_PARAMETER_FIELDS - set(values))
        if missing:
            raise ValueError(
                "panel proposal is incomplete; missing: " + ", ".join(missing)
            )
        dimensions = (
            intent.overall_size.width_mm,
            intent.overall_size.depth_mm,
            intent.overall_size.height_mm,
        )
        if any(value is None for value in dimensions):
            raise ValueError("panel planning requires a confirmed finished envelope")
        return cls.from_dict(
            {
                "furniture_type": intent.furniture_type,
                "width": dimensions[0],
                "depth": dimensions[1],
                "height": dimensions[2],
                **values,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FurnitureSpec":
        """Read a serialized complete spec without filling missing values."""
        values = _normalize_legacy_serialized_spec(dict(data))
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


def _normalize_front_face_margin_key(values: dict[str, Any]) -> dict[str, Any]:
    """Collapse the historical door_margin name onto front_face_margin."""
    if "door_margin" not in values:
        return values
    if (
        "front_face_margin" in values
        and values["front_face_margin"] != values["door_margin"]
    ):
        raise ValueError("front_face_margin and door_margin must match")
    values["front_face_margin"] = values.pop("door_margin")
    return values


def _normalize_panel_input_aliases(values: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy aliases still tolerated for active panel inputs."""
    return _normalize_front_face_margin_key(values)


def _normalize_legacy_serialized_spec(values: dict[str, Any]) -> dict[str, Any]:
    """Normalize historical serialized spec aliases when loading old data."""
    values = _normalize_front_face_margin_key(values)
    values = _legacy_spec_loader_furniture_type(values)
    return values


def _legacy_spec_loader_furniture_type(values: dict[str, Any]) -> dict[str, Any]:
    """Recover the historical serialized ``type`` field into ``furniture_type``."""
    if "type" not in values:
        return values
    if "furniture_type" in values and values["furniture_type"] != values["type"]:
        raise ValueError("type and furniture_type must match")
    values["furniture_type"] = values.pop("type")
    return values


def resolve_back_mount(
    requested: str,
    back_thickness: float,
    board_thickness: float,
) -> str:
    """Resolve the explicitly requested strategy by a deterministic rule."""
    if requested not in VALID_BACK_MOUNTS:
        raise ValueError(
            f"back_mount must be one of: {', '.join(sorted(VALID_BACK_MOUNTS))}"
        )
    if requested != "auto":
        return requested
    return "insert" if back_thickness >= board_thickness else "groove"


def resolve_shelf_gaps(spec: FurnitureSpec, internal_height: float) -> list[float]:
    """返回每层板下方净高（从上到下），并解析 auto 层为「剩余」。

    auto = 内净高 − top_gap_mm − N×板厚 − 其余显式净高之和。
    """
    board = spec.board_thickness
    count = len(spec.shelves)
    explicit = [s.gap_below_mm for s in spec.shelves if s.gap_below_mm is not None]
    auto_count = count - len(explicit)
    if auto_count == 1:
        auto = internal_height - spec.top_gap_mm - count * board - sum(explicit)
        if auto < 0:
            raise ValueError("shelf gaps exceed the internal height")
        return [auto if s.gap_below_mm is None else s.gap_below_mm for s in spec.shelves]
    total = spec.top_gap_mm + count * board + sum(explicit)
    if abs(total - internal_height) > 0.5:
        raise ValueError(
            "explicit shelf gaps and top gap do not fill the internal height "
            f"(sum={total:g}, internal_height={internal_height:g})"
        )
    return list(explicit)


def migrate_legacy_panel_hinge_side(
    panel_parameters: dict[str, Any] | None,
    panel_output: dict[str, Any] | None,
) -> None:
    """Upgrade persisted pre-field panel data without guessing a preference.

    ``door_count`` handling below is retained only for historical persisted panel
    outputs. It can be removed when those legacy revisions are no longer loaded.
    """
    output_side_available = False
    migrated_side: str | None = None
    if isinstance(panel_output, dict):
        spec = panel_output.get("spec")
        if isinstance(spec, dict):
            if "door_hinge_side" not in spec:
                door_count = _legacy_spec_loader_panel_output_door_count(spec)
                doors = _legacy_doors(panel_output)
                if len(doors) != door_count:
                    raise ValueError(
                        "legacy panel output door count does not match its specification"
                    )
                if door_count == 1:
                    migrated_side = doors[0].get("door_hinge_side")
                    if migrated_side not in {"left", "right"}:
                        raise ValueError(
                            "legacy single-door output requires one explicit panel "
                            "door_hinge_side for migration"
                        )
                ordered_doors = sorted(
                    doors,
                    key=lambda panel: (
                        float(panel.get("pos_x", 0.0)),
                        str(panel.get("id", "")),
                    ),
                )
                for index, door in enumerate(ordered_doors):
                    expected_side = resolve_door_hinge_side(
                        door_count,
                        index,
                        migrated_side,
                    )
                    actual_side = door.get("door_hinge_side")
                    if door_count == 2 and actual_side is None:
                        door["door_hinge_side"] = expected_side
                    elif actual_side != expected_side:
                        raise ValueError(
                            "legacy panel output has inconsistent door_hinge_side values"
                        )
                spec["door_hinge_side"] = migrated_side
            else:
                migrated_side = spec["door_hinge_side"]
            output_side_available = True

    if not isinstance(panel_parameters, dict) or "door_hinge_side" in panel_parameters:
        return
    if output_side_available:
        panel_parameters["door_hinge_side"] = migrated_side
        return
    door_count = _legacy_spec_loader_panel_input_door_count(panel_parameters)
    if (
        isinstance(door_count, int)
        and not isinstance(door_count, bool)
        and door_count >= 0
        and door_count != 1
    ):
        panel_parameters["door_hinge_side"] = None


def _legacy_spec_loader_panel_output_door_count(spec: Mapping[str, Any]) -> int:
    value = spec.get("n_doors", spec.get("door_count"))
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("legacy panel spec requires a valid n_doors for migration")
    return value


def _legacy_spec_loader_panel_input_door_count(
    panel_parameters: Mapping[str, Any],
) -> Any:
    """Recover ``n_doors`` from historical panel input payloads."""
    return panel_parameters.get(
        "n_doors",
        panel_parameters.get("door_count"),
    )


def _legacy_doors(panel_output: Mapping[str, Any]) -> list[dict[str, Any]]:
    panels = panel_output.get("panels")
    if not isinstance(panels, list):
        return []
    return [
        panel
        for panel in panels
        if isinstance(panel, dict) and panel.get("panel_type") == "door"
    ]


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
        "toe_kick_height", "back_offset", "front_face_margin", "door_hinge_gap",
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
    if spec.furniture_type == "wall_cabinet" and (
        spec.toe_kick_height != 0
        or spec.toe_kick_support_count not in {None, 0}
        or spec.drawer_count != 0
    ):
        raise ValueError(
            "wall_cabinet cannot contain a toe kick or full-height drawers"
        )
    if spec.toe_kick_height == 0 and spec.toe_kick_support_count not in {None, 0}:
        raise ValueError("toe-kick supports require a positive toe_kick_height")
    if spec.drawer_count and (spec.shelves or spec.n_doors):
        raise ValueError("full-height drawers require no shelves and n_doors=0")
    if spec.n_doors > 2:
        raise ValueError(
            "current panel topology supports at most 2 doors; disambiguate multi-door opening strategy first"
        )
    if spec.door_hinge_side not in {None, "left", "right"}:
        raise ValueError("door_hinge_side must be 'left', 'right', or null")
    if spec.n_doors == 1:
        if spec.door_hinge_side not in {"left", "right"}:
            raise ValueError(
                "a single door requires an explicit door_hinge_side 'left' or 'right'"
            )
    elif spec.door_hinge_side is not None:
        raise ValueError(
            "door_hinge_side only applies to a single door; use null otherwise"
        )
    if spec.movable_shelf_connector not in VALID_MOVABLE_SHELF_CONNECTORS:
        raise ValueError(
            "movable_shelf_connector must be one of: "
            + ", ".join(sorted(VALID_MOVABLE_SHELF_CONNECTORS))
        )
    if sum(1 for s in spec.shelves if s.gap_below_mm is None) > 1:
        raise ValueError("at most one shelf gap may be 'auto'")
