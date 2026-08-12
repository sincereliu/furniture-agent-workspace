"""Manufacturing-stage panel, hardware, and machining records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


@dataclass
class PanelRecord:
    label: str
    name: str
    panel_type: str
    material: str
    thickness: float
    length_mm: float
    width_mm: float
    size_x: float
    size_y: float
    size_z: float
    quantity: int = 1
    drill_length: float = 0.0
    edge_banding: Dict[str, str] = field(default_factory=dict)
    note: str = ""
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    depends_on: list[str] = field(default_factory=list)
    door_hinge_side: str | None = None
    door_overlay: str | None = None
    back_mount: str = ""
    inner_face: str = ""
    outer_face: str = ""
    cam_face: str | None = None
    joints: list = field(default_factory=list)  # list[PanelJoint], face-to-edge adjacencies

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PanelRecord":
        """Restore serialized panel joints at the manufacturing boundary."""

        from furniture_panel_planning.joint_topology import PanelJoint

        values = dict(data)
        raw_joints = values.get("joints", [])
        if not isinstance(raw_joints, list):
            raise ValueError("manufacturing panel joints must be a list")
        values["joints"] = [
            item if isinstance(item, PanelJoint) else PanelJoint(**item)
            for item in raw_joints
        ]
        return cls(**values)

    @property
    def area_m2(self) -> float:
        return self.length_mm * self.width_mm * self.quantity / 1_000_000

    @property
    def volume_m3(self) -> float:
        return (
            self.length_mm * self.width_mm * self.thickness * self.quantity
            / 1_000_000_000
        )

    def edge_banding_summary(self) -> str:
        if not self.edge_banding:
            return "无"
        return ", ".join(
            f"{edge}:{material}" for edge, material in self.edge_banding.items()
        )


@dataclass(frozen=True)
class MachiningOperation:
    id: str
    operation_type: str
    target_panel: str
    size_x: float
    size_y: float
    size_z: float
    pos_x: float
    pos_y: float
    pos_z: float
    note: str = ""


@dataclass
class HardwareRecord:
    name: str
    spec: str
    quantity: int
    brand: str = "默认"
    model: str = ""
    unit: str = "个"
    note: str = ""
    drilling: list = None  # type: ignore[assignment]

