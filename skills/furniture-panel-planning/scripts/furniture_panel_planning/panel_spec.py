"""Construction inputs first materialized by the panels_planned stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent, SUPPORTED_TYPES


VALID_BACK_MOUNTS = frozenset({"auto", "groove", "insert", "cover"})

PANEL_SPEC_FIELDS = frozenset(
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
        "shelf_count",
        "n_doors",
        "door_count",
    }
)

PANEL_PRESETS: dict[str, dict[str, int]] = {
    "floor_cabinet": {"shelf_count": 4, "n_doors": 2},
    "wall_cabinet": {"shelf_count": 1, "n_doors": 2},
}


@dataclass
class FurnitureSpec:
    """Confirmed construction specification emitted with the panel plan."""

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
    drawer_count: int = 0
    groove_depth: float = 6.0
    groove_clearance: float = 1.0
    toe_kick_reveal_front: float = 1.0
    toe_kick_reveal_back: float = 30.0
    toe_kick_support_count: int | None = None
    back_mount: str = "auto"
    back_rail_height: float = 70.0

    def __post_init__(self) -> None:
        # ``back_mount`` is always a resolved mode (groove/insert/cover) once a
        # FurnitureSpec exists; ``auto`` only has meaning on the raw request.
        self.back_mount = resolve_back_mount(
            self.back_mount,
            self.back_thickness,
            self.board_thickness,
        )

    @classmethod
    def from_intent(
        cls,
        intent: DesignIntent,
        options: Mapping[str, Any] | None = None,
    ) -> "FurnitureSpec":
        values = dict(options or {})
        unknown = sorted(set(values) - PANEL_SPEC_FIELDS)
        if unknown:
            raise ValueError(
                "panel stage does not support: " + ", ".join(unknown)
            )
        if intent.furniture_type not in SUPPORTED_TYPES:
            raise ValueError(f"unsupported furniture type: {intent.furniture_type}")
        dimensions = (
            intent.overall_size.width_mm,
            intent.overall_size.depth_mm,
            intent.overall_size.height_mm,
        )
        if any(value is None for value in dimensions):
            raise ValueError("panel planning requires a confirmed finished envelope")
        if (
            "door_count" in values
            and "n_doors" in values
            and values["door_count"] != values["n_doors"]
        ):
            raise ValueError("door_count and n_doors must match when both are provided")
        preset = PANEL_PRESETS[intent.furniture_type]
        return cls.from_dict(
            {
                "type": intent.furniture_type,
                "width": dimensions[0],
                "depth": dimensions[1],
                "height": dimensions[2],
                "shelf_count": values.get(
                    "shelf_count", preset["shelf_count"]
                ),
                "n_doors": values.get(
                    "n_doors", values.get("door_count", preset["n_doors"])
                ),
                **values,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FurnitureSpec":
        furniture_type = str(
            data.get("type", data.get("furniture_type", ""))
        ).strip().lower()

        def value(key: str, fallback: Any) -> Any:
            current = data.get(key)
            return fallback if current is None else current

        board_thickness = float(value("board_thickness", 18.0))
        back_thickness = float(value("back_thickness", 9.0))
        requested_back_mount = str(value("back_mount", "auto"))
        effective_back_mount = resolve_back_mount(
            requested_back_mount,
            back_thickness,
            board_thickness,
        )

        def groove_float(key: str, fallback: float) -> float:
            raw = value(key, fallback)
            try:
                return float(raw)
            except (TypeError, ValueError):
                if effective_back_mount == "groove":
                    raise  # groove 模式下该字段必须有效，透传原始解析错误
                return fallback

        toe_kick_default = 0.0 if furniture_type == "wall_cabinet" else 50.0
        return cls(
            furniture_type=furniture_type,
            width=float(value("width", 0)),
            depth=float(value("depth", 0)),
            height=float(value("height", 0)),
            board_thickness=board_thickness,
            back_thickness=back_thickness,
            door_thickness=float(value("door_thickness", 18.0)),
            toe_kick_height=float(value("toe_kick_height", toe_kick_default)),
            back_offset=float(value("back_offset", 18.0)),
            door_margin=float(value("door_margin", 1.5)),
            door_hinge_gap=float(value("door_hinge_gap", 2.0)),
            shelf_count=_count(value("shelf_count", 4), "shelf_count"),
            n_doors=_count(value("n_doors", 2), "n_doors"),
            drawer_count=_count(value("drawer_count", 0), "drawer_count"),
            groove_depth=groove_float("groove_depth", 6.0),
            groove_clearance=groove_float("groove_clearance", 1.0),
            toe_kick_reveal_front=float(value("toe_kick_reveal_front", 1.0)),
            toe_kick_reveal_back=float(value("toe_kick_reveal_back", 30.0)),
            toe_kick_support_count=_optional_int(data.get("toe_kick_support_count")),
            back_mount=effective_back_mount,
            back_rail_height=groove_float("back_rail_height", 70.0),
        )


def resolve_back_mount(
    requested: str,
    back_thickness: float,
    board_thickness: float,
) -> str:
    """Resolve the panel-stage construction mode from a requested strategy."""
    mode = str(requested).strip().lower()
    if mode not in VALID_BACK_MOUNTS:
        raise ValueError(
            f"back_mount must be one of: {', '.join(sorted(VALID_BACK_MOUNTS))}"
        )
    if mode != "auto":
        return mode
    return "insert" if back_thickness >= board_thickness else "groove"


def _count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


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
