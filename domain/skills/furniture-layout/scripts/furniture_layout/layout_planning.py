"""Customer-visible cabinet layout without construction geometry."""

from __future__ import annotations

from dataclasses import dataclass

from .layout_spec import LayoutSpec


@dataclass(frozen=True)
class CabinetLayout:
    """Stage-2 envelope and functional-count contract."""

    furniture_type: str
    width: float
    depth: float
    height: float
    door_count: int

    @classmethod
    def from_spec(cls, spec: LayoutSpec) -> "CabinetLayout":
        return cls(
            furniture_type=spec.furniture_type,
            width=spec.width,
            depth=spec.depth,
            height=spec.height,
            door_count=spec.door_count,
        )
