"""Structured contract admitted by the ``panels_planned`` stage."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent, SUPPORTED_TYPES


VALID_BACK_MOUNTS = frozenset({"auto", "groove", "insert", "cover"})

# Every field is an LLM/user proposal decision. Runtime rejects omissions instead
# of selecting a cabinet profile or filling construction defaults.
PANEL_PARAMETER_FIELDS = frozenset(
    {
        "board_thickness", "back_thickness", "door_thickness",
        "toe_kick_height", "back_offset", "door_margin", "door_hinge_gap",
        "groove_depth", "groove_clearance", "toe_kick_reveal_front",
        "toe_kick_reveal_back", "toe_kick_support_count", "back_mount",
        "back_rail_height", "drawer_count", "drawer_side_clearance",
        "drawer_layer_gap", "drawer_bottom_thickness", "drawer_back_thickness",
        "drawer_back_clearance", "shelf_count", "n_doors",
    }
)
PANEL_SPEC_FIELDS = PANEL_PARAMETER_FIELDS | {"door_count"}
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
    door_margin: float
    door_hinge_gap: float
    shelf_count: int
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

    def __post_init__(self) -> None:
        if self.furniture_type not in SUPPORTED_TYPES:
            raise ValueError(
                f"furniture_type must be an executable canonical type: "
                f"{self.furniture_type}"
            )
        for name in (
            "width", "depth", "height", "board_thickness", "back_thickness",
            "door_thickness", "toe_kick_height", "back_offset", "door_margin",
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
        for name in ("shelf_count", "n_doors", "drawer_count"):
            _require_count(getattr(self, name), name)
        if self.toe_kick_support_count is not None:
            _require_count(self.toe_kick_support_count, "toe_kick_support_count")
        self.back_mount = resolve_back_mount(
            self.back_mount, self.back_thickness, self.board_thickness
        )
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
        values = dict(options)
        unknown = sorted(set(values) - PANEL_SPEC_FIELDS)
        if unknown:
            raise ValueError("panel stage does not support: " + ", ".join(unknown))
        if "door_count" in values:
            if "n_doors" in values and values["n_doors"] != values["door_count"]:
                raise ValueError("door_count and n_doors must match")
            values["n_doors"] = values.pop("door_count")
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
        values = dict(data)
        if "type" in values:
            if "furniture_type" in values and values["furniture_type"] != values["type"]:
                raise ValueError("type and furniture_type must match")
            values["furniture_type"] = values.pop("type")
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
        return cls(**values)


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
        "toe_kick_height", "back_offset", "door_margin", "door_hinge_gap",
        "groove_clearance", "toe_kick_reveal_front", "toe_kick_reveal_back",
        "back_rail_height", "drawer_layer_gap", "drawer_back_clearance",
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
    if spec.drawer_count and (spec.shelf_count or spec.n_doors):
        raise ValueError("full-height drawers require shelf_count=0 and n_doors=0")
