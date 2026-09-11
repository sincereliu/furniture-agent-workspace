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
    role: str = ""  # cabinet-local role, e.g. left_side_panel
    parent_id: str = ""  # owning cabinet instance id
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
        panel_id = str(values.get("id", "")).strip()
        if not panel_id:
            raise ValueError("panel requires id")
        if not str(values.get("role", "")).strip():
            raise ValueError(f"{panel_id} requires role")
        if not str(values.get("parent_id", "")).strip():
            raise ValueError(f"{panel_id} requires parent_id")
        return cls(**values)
