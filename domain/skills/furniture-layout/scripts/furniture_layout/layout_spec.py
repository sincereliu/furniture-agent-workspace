"""Envelope inputs for the independent room-placement capability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent, SUPPORTED_TYPES


LAYOUT_PRESETS: dict[str, dict[str, int]] = {
    "floor_cabinet": {"shelf_count": 4, "door_count": 2},
    "wall_cabinet": {"shelf_count": 1, "door_count": 2},
}


@dataclass(frozen=True)
class LayoutSpec:
    """Envelope plus legacy count fields; no construction inputs."""

    furniture_type: str
    width: float
    depth: float
    height: float
    shelf_count: int
    door_count: int

    @classmethod
    def from_intent(
        cls,
        intent: DesignIntent,
        options: Mapping[str, Any] | None = None,
    ) -> "LayoutSpec":
        values = dict(options or {})
        unknown = sorted(set(values) - {"shelf_count", "n_doors", "door_count"})
        if unknown:
            raise ValueError(
                "independent layout does not support: " + ", ".join(unknown)
            )
        if intent.furniture_type not in SUPPORTED_TYPES:
            raise ValueError(f"unsupported furniture type: {intent.furniture_type}")
        dimensions = (
            intent.overall_size.width_mm,
            intent.overall_size.depth_mm,
            intent.overall_size.height_mm,
        )
        if any(value is None for value in dimensions):
            raise ValueError("layout requires a confirmed finished envelope")
        preset = LAYOUT_PRESETS[intent.furniture_type]
        shelf_count = _count(values.get("shelf_count", preset["shelf_count"]), "shelf_count")
        door_count = _count(
            values.get("door_count", values.get("n_doors", preset["door_count"])),
            "door_count",
        )
        return cls(
            furniture_type=intent.furniture_type,
            width=float(dimensions[0]),
            depth=float(dimensions[1]),
            height=float(dimensions[2]),
            shelf_count=shelf_count,
            door_count=door_count,
        )


def _count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value
