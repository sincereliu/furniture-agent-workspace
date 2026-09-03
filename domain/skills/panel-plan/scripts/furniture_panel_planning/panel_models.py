"""Semantic panel contracts owned by the panels_planned stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


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
    inner_face: str = ""                 # panel face pointing toward cabinet interior
    outer_face: str = ""                 # panel face pointing toward cabinet exterior
    cam_face: str | None = None          # eccentric wheel accessible face, e.g. "-z"
    joints: list = field(default_factory=list)  # list[PanelJoint], populated after solve

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PanelPlacement":
        """Restore nested joint contracts after a stage-output JSON round trip."""

        from .joint_topology import PanelJoint

        values = dict(data)
        raw_joints = values.get("joints", [])
        if not isinstance(raw_joints, list):
            raise ValueError("panel joints must be a list")
        values["joints"] = [
            item if isinstance(item, PanelJoint) else PanelJoint(**item)
            for item in raw_joints
        ]
        return cls(**values)
