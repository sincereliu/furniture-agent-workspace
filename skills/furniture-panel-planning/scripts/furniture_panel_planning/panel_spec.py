"""Structured proposal admission for the ``panels_planned`` stage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent, SUPPORTED_TYPES


VALID_BACK_MOUNTS = frozenset({"auto", "groove", "insert", "cover"})

# These fields are decisions in the normalized LLM proposal. Runtime may
# validate and calculate from them, but it must not choose them when omitted.
PANEL_PARAMETER_FIELDS = frozenset(
    {
        "board_thickness",
        "back_thickness",
        "door_thickness",
        "toe_kick_height",
        "back_offset",
        "door_margin",
        "door_hinge_gap",
        "groove_depth",
        "groove_clearance",
        "toe_kick_reveal_front",
        "toe_kick_reveal_back",
        "toe_kick_support_count",
        "back_mount",
        "back_rail_height",
        "drawer_count",
        "drawer_side_clearance",
        "drawer_layer_gap",
        "drawer_bottom_thickness",
        "drawer_back_thickness",
        "drawer_back_clearance",
        "shelf_count",
        "n_doors",
    }
)

# ``door_count`` is a versioned structured-protocol alias. ``panel_profile``
# explicitly expands a named profile; neither is a natural-language alias nor
# a runtime-selected default.
PANEL_SPEC_FIELDS = frozenset(
    {*PANEL_PARAMETER_FIELDS, "door_count", "panel_profile"}
)

_SERIALIZED_SPEC_FIELDS = frozenset(
    {
        "furniture_type",
        "width",
        "depth",
        "height",
        *PANEL_PARAMETER_FIELDS,
    }
)

# Profiles are deterministic structured protocols. The LLM may recommend one
# and the user can confirm it; runtime code never selects one from cabinet text
# or furniture type. Every profile is complete, so there are no nested defaults.
PANEL_PROFILES: dict[str, dict[str, Any]] = {
    "floor_cabinet_standard_v1": {
        "furniture_type": "floor_cabinet",
        "board_thickness": 18.0,
        "back_thickness": 9.0,
        "door_thickness": 18.0,
        "toe_kick_height": 50.0,
        "back_offset": 18.0,
        "door_margin": 1.5,
        "door_hinge_gap": 2.0,
        "groove_depth": 6.0,
        "groove_clearance": 1.0,
        "toe_kick_reveal_front": 1.0,
        "toe_kick_reveal_back": 30.0,
        "toe_kick_support_count": None,
        "back_mount": "auto",
        "back_rail_height": 70.0,
        "drawer_count": 0,
        "drawer_side_clearance": 13.0,
        "drawer_layer_gap": 1.5,
        "drawer_bottom_thickness": 18.0,
        "drawer_back_thickness": 18.0,
        "drawer_back_clearance": 0.0,
        "shelf_count": 4,
        "n_doors": 2,
    },
    "wall_cabinet_standard_v1": {
        "furniture_type": "wall_cabinet",
        "board_thickness": 18.0,
        "back_thickness": 9.0,
        "door_thickness": 18.0,
        "toe_kick_height": 0.0,
        "back_offset": 18.0,
        "door_margin": 1.5,
        "door_hinge_gap": 2.0,
        "groove_depth": 6.0,
        "groove_clearance": 1.0,
        "toe_kick_reveal_front": 0.0,
        "toe_kick_reveal_back": 0.0,
        "toe_kick_support_count": None,
        "back_mount": "auto",
        "back_rail_height": 70.0,
        "drawer_count": 0,
        "drawer_side_clearance": 13.0,
        "drawer_layer_gap": 1.5,
        "drawer_bottom_thickness": 18.0,
        "drawer_back_thickness": 18.0,
        "drawer_back_clearance": 0.0,
        "shelf_count": 1,
        "n_doors": 2,
    },
}


@dataclass
class FurnitureSpec:
    """Admitted, complete construction specification emitted with the plan."""

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
        self.furniture_type = _canonical_token(
            self.furniture_type,
            "furniture_type",
        )
        for name in (
            "width",
            "depth",
            "height",
            "board_thickness",
            "back_thickness",
            "door_thickness",
            "toe_kick_height",
            "back_offset",
            "door_margin",
            "door_hinge_gap",
            "groove_depth",
            "groove_clearance",
            "toe_kick_reveal_front",
            "toe_kick_reveal_back",
            "back_rail_height",
            "drawer_side_clearance",
            "drawer_layer_gap",
            "drawer_bottom_thickness",
            "drawer_back_thickness",
            "drawer_back_clearance",
        ):
            setattr(self, name, _number(getattr(self, name), name))
        self.shelf_count = _count(self.shelf_count, "shelf_count")
        self.n_doors = _count(self.n_doors, "n_doors")
        self.drawer_count = _count(self.drawer_count, "drawer_count")
        self.toe_kick_support_count = _optional_count(
            self.toe_kick_support_count,
            "toe_kick_support_count",
        )
        self.back_mount = resolve_back_mount(
            self.back_mount,
            self.back_thickness,
            self.board_thickness,
        )
        _validate_spec_invariants(self)

    @classmethod
    def from_intent(
        cls,
        intent: DesignIntent,
        options: Mapping[str, Any] | None = None,
    ) -> "FurnitureSpec":
        """Admit a normalized proposal against a confirmed envelope."""
        return admit_panel_proposal(intent, options).spec

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FurnitureSpec":
        """Read a complete serialized spec; missing fields are never filled."""
        values = dict(data)
        if "type" in values:
            if (
                "furniture_type" in values
                and values["furniture_type"] != values["type"]
            ):
                raise ValueError("type and furniture_type must match")
            values["furniture_type"] = values.pop("type")
        unknown = sorted(set(values) - _SERIALIZED_SPEC_FIELDS)
        if unknown:
            raise ValueError(
                "serialized panel spec does not support: " + ", ".join(unknown)
            )
        missing = sorted(_SERIALIZED_SPEC_FIELDS - set(values))
        if missing:
            raise ValueError(
                "serialized panel spec is incomplete; missing: " + ", ".join(missing)
            )
        return cls(**values)


@dataclass(frozen=True)
class AdmittedPanelProposal:
    """Traceable result of deterministic proposal admission."""

    spec: FurnitureSpec
    requested_back_mount: str
    panel_profile: str | None
    explicit_fields: tuple[str, ...]
    proposal_sha256: str


def admit_panel_proposal(
    intent: DesignIntent,
    options: Mapping[str, Any] | None,
) -> AdmittedPanelProposal:
    """Validate and normalize one LLM-authored structured panel proposal."""
    if not isinstance(intent, DesignIntent) or not intent.confirmed:
        raise ValueError("panel planning requires a confirmed DesignIntent")
    if intent.furniture_type not in SUPPORTED_TYPES:
        raise ValueError(f"unsupported furniture type: {intent.furniture_type}")
    dimensions = (
        intent.overall_size.width_mm,
        intent.overall_size.depth_mm,
        intent.overall_size.height_mm,
    )
    if any(value is None for value in dimensions):
        raise ValueError("panel planning requires a confirmed finished envelope")
    if not isinstance(options, Mapping):
        raise ValueError("panel proposal must be an object")

    submitted = dict(options)
    unknown = sorted(set(submitted) - PANEL_SPEC_FIELDS)
    if unknown:
        raise ValueError("panel stage does not support: " + ", ".join(unknown))
    if (
        "door_count" in submitted
        and "n_doors" in submitted
        and submitted["door_count"] != submitted["n_doors"]
    ):
        raise ValueError("door_count and n_doors must match when both are provided")

    profile_name = submitted.pop("panel_profile", None)
    values: dict[str, Any] = {}
    if profile_name is not None:
        profile_name = _canonical_token(profile_name, "panel_profile")
        profile = PANEL_PROFILES.get(profile_name)
        if profile is None:
            raise ValueError(
                "panel_profile must be one of: "
                + ", ".join(sorted(PANEL_PROFILES))
            )
        if profile["furniture_type"] != intent.furniture_type:
            raise ValueError(
                f"panel_profile {profile_name!r} is not compatible with "
                f"{intent.furniture_type!r}"
            )
        values.update(
            {key: value for key, value in profile.items() if key != "furniture_type"}
        )

    if "door_count" in submitted and "n_doors" not in submitted:
        submitted["n_doors"] = submitted["door_count"]
    submitted.pop("door_count", None)
    explicit_fields = tuple(sorted(submitted))
    values.update(submitted)

    missing = sorted(PANEL_PARAMETER_FIELDS - set(values))
    if missing:
        raise ValueError(
            "panel proposal is incomplete; provide every field or an explicit "
            "panel_profile; missing: " + ", ".join(missing)
        )
    requested_back_mount = _canonical_token(values["back_mount"], "back_mount")
    spec = FurnitureSpec.from_dict(
        {
            "furniture_type": intent.furniture_type,
            "width": dimensions[0],
            "depth": dimensions[1],
            "height": dimensions[2],
            **values,
        }
    )
    return AdmittedPanelProposal(
        spec=spec,
        requested_back_mount=requested_back_mount,
        panel_profile=profile_name,
        explicit_fields=explicit_fields,
        proposal_sha256=proposal_sha256(
            profile_name,
            explicit_fields,
            requested_back_mount,
            asdict(spec),
        ),
    )


def proposal_sha256(
    panel_profile: str | None,
    explicit_fields: list[str] | tuple[str, ...],
    requested_back_mount: str,
    spec: Mapping[str, Any],
) -> str:
    """Return the stable digest for reconstructable proposal admission data."""
    return _digest(
        {
            "panel_profile": panel_profile,
            "explicit_fields": list(explicit_fields),
            "requested_back_mount": requested_back_mount,
            "spec": dict(spec),
        }
    )


def spec_sha256(spec: Mapping[str, Any]) -> str:
    """Return the stable digest used by the stage admission record."""
    return _digest(dict(spec))


def resolve_back_mount(
    requested: str,
    back_thickness: float,
    board_thickness: float,
) -> str:
    """Resolve an explicit canonical request to an executable mount mode."""
    mode = _canonical_token(requested, "back_mount")
    if mode not in VALID_BACK_MOUNTS:
        raise ValueError(
            f"back_mount must be one of: {', '.join(sorted(VALID_BACK_MOUNTS))}"
        )
    if mode != "auto":
        return mode
    return "insert" if back_thickness >= board_thickness else "groove"


def _validate_spec_invariants(spec: FurnitureSpec) -> None:
    if spec.furniture_type not in SUPPORTED_TYPES:
        raise ValueError(
            "furniture_type must be an executable canonical type: "
            + ", ".join(sorted(SUPPORTED_TYPES))
        )
    for name in (
        "width",
        "depth",
        "height",
        "board_thickness",
        "back_thickness",
        "door_thickness",
        "drawer_side_clearance",
        "drawer_bottom_thickness",
        "drawer_back_thickness",
    ):
        if getattr(spec, name) <= 0:
            raise ValueError(f"{name} must be positive")
    for name in (
        "toe_kick_height",
        "back_offset",
        "door_margin",
        "door_hinge_gap",
        "groove_clearance",
        "toe_kick_reveal_front",
        "toe_kick_reveal_back",
        "back_rail_height",
        "drawer_layer_gap",
        "drawer_back_clearance",
    ):
        if getattr(spec, name) < 0:
            raise ValueError(f"{name} cannot be negative")
    if spec.back_mount == "groove" and spec.groove_depth <= 0:
        raise ValueError("groove_depth must be positive for groove back_mount")
    if spec.furniture_type == "wall_cabinet":
        if spec.toe_kick_height != 0:
            raise ValueError("wall_cabinet requires toe_kick_height=0")
        if spec.toe_kick_support_count not in {None, 0}:
            raise ValueError("wall_cabinet cannot request toe-kick supports")
        if spec.drawer_count != 0:
            raise ValueError("wall_cabinet topology does not support drawers")
    if spec.toe_kick_height == 0 and spec.toe_kick_support_count not in {None, 0}:
        raise ValueError("toe-kick supports require a positive toe_kick_height")
    if spec.drawer_count > 0 and (spec.shelf_count > 0 or spec.n_doors > 0):
        raise ValueError(
            "full-height drawers require shelf_count=0 and n_doors=0; "
            "the LLM must resolve mixed-zone intent before admission"
        )
    if spec.n_doors > 0:
        if spec.width - 2 * spec.door_margin * spec.n_doors <= 0:
            raise ValueError("door margins leave no positive door width")
        if spec.height - spec.toe_kick_height - 2 * spec.door_margin <= 0:
            raise ValueError("door margins leave no positive door height")


def _canonical_token(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty canonical string")
    return value.strip().lower()


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    converted = float(value)
    if not isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _optional_count(value: Any, name: str) -> int | None:
    if value is None:
        return None
    return _count(value, name)


def _digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
