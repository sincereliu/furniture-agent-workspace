"""Cabinet envelope admitted by panel-plan from a confirmed CAD unit.

Layout rooms, placement, origin, and rotation are not part of this contract.
Extra keys on a CAD-unit mapping are ignored so layout-only fields can change
without a panel-plan code change.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

CABINET_CATEGORIES = frozenset({"floor_cabinet", "wall_cabinet"})
ENVELOPE_FIELDS = ("id", "furniture_category", "width", "depth", "height")


@dataclass(frozen=True)
class CabinetEnvelope:
    """Category and finished box that panel planning may turn into boards."""

    id: str
    furniture_category: str
    width: float
    depth: float
    height: float

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any] | "CabinetEnvelope",
    ) -> "CabinetEnvelope":
        if isinstance(data, CabinetEnvelope):
            return data
        if not isinstance(data, Mapping):
            raise ValueError("panel planning requires a cabinet envelope")
        missing = [name for name in ENVELOPE_FIELDS if name not in data]
        if missing:
            raise ValueError(
                "cabinet envelope is incomplete; missing: " + ", ".join(missing)
            )
        cabinet_id = data["id"]
        if not isinstance(cabinet_id, str) or not cabinet_id.strip():
            raise ValueError("cabinet envelope id must be a non-empty identifier")
        category = str(data["furniture_category"]).strip()
        if category not in CABINET_CATEGORIES:
            raise ValueError(
                "panel planning requires an executable furniture_category: "
                + ", ".join(sorted(CABINET_CATEGORIES))
            )
        values: dict[str, Any] = {
            "id": cabinet_id.strip(),
            "furniture_category": category,
        }
        for name in ("width", "depth", "height"):
            value = data[name]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{name} must be a positive finite number")
            values[name] = float(value)
        return cls(**values)
