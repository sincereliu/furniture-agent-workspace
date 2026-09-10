"""Envelope inputs for the independent room-placement capability."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from furniture_design_intent.design_intent import DesignIntent, EXECUTABLE_CATEGORIES


LAYOUT_PRESETS: dict[str, dict[str, int]] = {
    "floor_cabinet": {"door_count": 2},
    "wall_cabinet": {"door_count": 2},
}


@dataclass(frozen=True)
class LayoutSpec:
    """Envelope plus layout-owned count fields; no construction inputs.

    ``door_count`` is still the layout serialization name. Renaming it requires a
    coordinated layout API/storage change, not a panel-stage cleanup.
    """

    furniture_category: str
    width: float
    depth: float
    height: float
    door_count: int
    hanging_mode: str | None = None
    hanging_height_mm: float | None = None

    @classmethod
    def from_intent(
        cls,
        intent: DesignIntent,
        options: Mapping[str, Any] | None = None,
    ) -> "LayoutSpec":
        values = dict(options or {})
        unknown = sorted(set(values) - {"n_doors", "door_count"})
        if unknown:
            raise ValueError(
                "independent layout does not support: " + ", ".join(unknown)
            )
        if intent.furniture_category not in EXECUTABLE_CATEGORIES:
            raise ValueError(
                f"unsupported furniture category: {intent.furniture_category}"
            )
        dimensions = (
            intent.finished_envelope.width_mm,
            intent.finished_envelope.depth_mm,
            intent.finished_envelope.height_mm,
        )
        if any(value is None for value in dimensions):
            raise ValueError("layout requires a confirmed finished envelope")
        preset = LAYOUT_PRESETS[intent.furniture_category]
        door_count = _count(
            values.get("door_count", values.get("n_doors", preset["door_count"])),
            "door_count",
        )
        return cls(
            furniture_category=intent.furniture_category,
            width=float(dimensions[0]),
            depth=float(dimensions[1]),
            height=float(dimensions[2]),
            door_count=door_count,
            hanging_mode=intent.hanging_mode,
            hanging_height_mm=intent.hanging_height_mm,
        )


def _count(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value
