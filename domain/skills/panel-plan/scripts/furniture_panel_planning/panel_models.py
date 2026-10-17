"""Semantic panel contracts owned by the panel_plan stage."""

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
    assembly_id: str = ""  # owning sub-assembly, e.g. cabinet_1__carcass
    door_overlay: str | None = None      # "full" / "half" / "inset", only for door panels
    inner_face: str = ""                 # panel face pointing toward cabinet interior
    outer_face: str = ""                 # panel face pointing toward cabinet exterior
    #: 除 `inner_face` 之外，还拿哪张大面去接别人的端面。常规板是空的；
    #: 中立板两张大面都朝柜内（左右各一个腔），所以多声明一张，见 `joint_topology`。
    bearing_faces: list[str] = field(default_factory=list)
    #: 顺纹方向（柜体轴 x/y/z，或 none=不限）。由板件类型给默认值，见 `grain_rules`。
    #: 它是板件属性：进了冻结文件，制造/开料可以据此排版。空值按类型取默认。
    grain_axis: str = ""
    joints: list = field(default_factory=list)  # list[PanelJoint], populated after solve

    def __post_init__(self) -> None:
        """落默认顺纹方向。放在这里，所有 `PanelPlacement(...)` 都不用各自记得传。"""
        from .grain_rules import normalize_grain_axis

        self.grain_axis = normalize_grain_axis(self.grain_axis, self.panel_type)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PanelPlacement":
        """Restore nested joint contracts after a stage-output JSON round trip."""

        from .joint_topology import PanelJoint

        values = dict(data)
        raw_joints = values.get("joints", [])
        if not isinstance(raw_joints, list):
            raise ValueError("panel joints must be a list")
        values["joints"] = [
            item if isinstance(item, PanelJoint) else PanelJoint.from_dict(item)
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
