"""Semantic panel contracts owned by the panels_planned stage."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PanelPlacement:
    """One physical panel with final size and assembly placement."""

    id: str
    name: str
    panel_type: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    quantity: int = 1
    material_role: str = "carcass"
    orientation: str = "xyz"
    depends_on: list[str] = field(default_factory=list)
    note: str = ""
    door_hinge_side: str | None = None   # "left" / "right", only for door panels
    door_overlay: str | None = None      # "full" / "half" / "inset", only for door panels
