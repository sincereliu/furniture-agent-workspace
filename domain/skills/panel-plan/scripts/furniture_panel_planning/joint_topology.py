"""接触拓扑 — 板件之间的承面–端面邻接。

不依赖板件名称（"side"/"top" 等），只根据几何位置 + 语义面
推导出哪块板的承面被哪块板的端面顶住。
输出键 `bearing_id`/`end_id` 分别是承面/端面板件。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .panel_models import PanelPlacement


_JOINT_FIELDS = frozenset(
    {
        "bearing_id",
        "end_id",
        "face",
        "edge_axis",
        "edge_sign",
        "end_z",
        "end_size_z",
        "connection",
    }
)


@dataclass(frozen=True)
class PanelJoint:
    """一条承面–端面邻接：承面被端面顶住。

    `connection` 是制造阶段写入的连不连（on/off）。本阶段 `compute_joints()`
    只填几何邻接；字段默认 `on` 仅作序列化占位，制造层
    `default_joint_connection` 会按面板类型重解析。
    """

    bearing_id: str  # 承面板件 ID
    end_id: str  # 端面板件 ID
    face: str  # 承面所用语义面（inner_face 的值，如 "+x"）
    edge_axis: str  # 端面所在轴（"x"/"y"/"z"）
    edge_sign: int  # 端面方向：+1=轴正端，-1=轴负端
    end_z: float  # 端面件厚度中心线的 Z 坐标（几何基准）
    end_size_z: float = 0.0  # 端面件在 z 方向的尺寸（横板=板厚）
    connection: str = "on"  # resolved on/off; missing on old payloads means on

    def __post_init__(self) -> None:
        if self.connection not in {"on", "off"}:
            raise ValueError("connection must be 'on' or 'off'")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PanelJoint":
        """Restore one serialized contact. Unknown keys are rejected."""
        if not isinstance(data, Mapping):
            raise ValueError("panel joint must be an object")
        values = dict(data)
        unknown = sorted(set(values) - _JOINT_FIELDS)
        if unknown:
            raise ValueError("panel joint does not support: " + ", ".join(unknown))
        return cls(**values)


# ── 容差 ──────────────────────────────────────────────────────────
_SNAP_TOLERANCE = 0.5  # mm，面板端面与另一块板面的对齐容差


def _overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    """两个区间是否有交集（含容差）。"""
    return a_max > b_min - _SNAP_TOLERANCE and b_max > a_min - _SNAP_TOLERANCE


def _face_position(panel: PanelPlacement, face_dir: str) -> float:
    """面板某个语义面在世界坐标系中的位置。

    face_dir 如 "+x"→面板 x 最大值，"-x"→面板 x 最小值。
    """
    if face_dir == "+x":
        return panel.pos_x + panel.size_x
    if face_dir == "-x":
        return panel.pos_x
    if face_dir == "+y":
        return panel.pos_y + panel.size_y
    if face_dir == "-y":
        return panel.pos_y
    if face_dir == "+z":
        return panel.pos_z + panel.size_z
    if face_dir == "-z":
        return panel.pos_z
    return 0.0


def _axis_char(face_dir: str) -> str:
    """如 "+x" → "x"。"""
    return face_dir[1] if len(face_dir) >= 2 else ""


def _axis_sign(face_dir: str) -> int:
    """如 "+x" → +1。"""
    return 1 if face_dir.startswith("+") else -1


def _axis_range(panel: PanelPlacement, axis: str) -> tuple[float, float]:
    """面板在指定轴上的区间 [min, max]。"""
    if axis == "x":
        return (panel.pos_x, panel.pos_x + panel.size_x)
    if axis == "y":
        return (panel.pos_y, panel.pos_y + panel.size_y)
    return (panel.pos_z, panel.pos_z + panel.size_z)


def compute_joints(placements: Sequence[PanelPlacement]) -> list[PanelJoint]:
    """从板件列表推导所有承面–端面邻接。

    对每块有 inner_face 的板（承面候选），
    找出所有端面顶在该面上的板（端面候选）。
    """
    joints: list[PanelJoint] = []
    candidates = [p for p in placements if p.inner_face]

    def _is_drawer(panel: PanelPlacement) -> bool:
        return "drawer" in panel.panel_type

    for bearing in candidates:
        face_dir = bearing.inner_face
        face_axis = _axis_char(face_dir)
        face_pos = _face_position(bearing, face_dir)

        # 待检查的轴线（承面法向之外的另外两轴）
        other_axes = [a for a in ("x", "y", "z") if a != face_axis]

        for end_panel in placements:
            if end_panel.id == bearing.id:
                continue
            # 抽屉是滑动子装配：抽屉↔柜体的接触（如抽屉侧板贴柜体侧板、
            # 抽屉前板底边搁柜体底板）不是连接，排除跨装配 joint。
            if _is_drawer(bearing) != _is_drawer(end_panel):
                continue
            # 端面件必须在这个承面上有端面才可能接触
            end_min, end_max = _axis_range(end_panel, face_axis)

            if not (
                abs(end_min - face_pos) <= _SNAP_TOLERANCE
                or abs(end_max - face_pos) <= _SNAP_TOLERANCE
            ):
                continue

            # 另外两个轴必须重叠
            overlap_all = True
            for axis in other_axes:
                b_min, b_max = _axis_range(bearing, axis)
                e_min, e_max = _axis_range(end_panel, axis)
                if not _overlap(b_min, b_max, e_min, e_max):
                    overlap_all = False
                    break

            if not overlap_all:
                continue

            # 确定端面方向
            if abs(end_min - face_pos) <= _SNAP_TOLERANCE:
                edge_sign = -1
            else:
                edge_sign = +1

            joints.append(
                PanelJoint(
                    bearing_id=bearing.id,
                    end_id=end_panel.id,
                    face=face_dir,
                    edge_axis=face_axis,
                    edge_sign=edge_sign,
                    end_z=end_panel.pos_z + end_panel.size_z / 2.0,
                    end_size_z=end_panel.size_z,
                )
            )

    return joints


def joint_is_connected(joint: PanelJoint) -> bool:
    """True when the resolved switch says this contact should be fixed.

    ``connection`` 现在由制造层在 `plan_manufacturing` 中重解析（见制造层
    `default_joint_connection`）；panel-plan 只产接触拓扑，不再解析连不连。
    """
    return getattr(joint, "connection", "on") == "on"


def is_bearing(panel_id: str, joints: Sequence[PanelJoint]) -> bool:
    """该板是否在某条接触中担任承面。"""
    return any(j.bearing_id == panel_id for j in joints)


def is_end(panel_id: str, joints: Sequence[PanelJoint]) -> bool:
    """该板是否在某条接触中担任端面。"""
    return any(j.end_id == panel_id for j in joints)


def bearing_joints(panel_id: str, joints: Sequence[PanelJoint]) -> list[PanelJoint]:
    """该板作为承面参与的所有接触。"""
    return [j for j in joints if j.bearing_id == panel_id]


def end_joints(panel_id: str, joints: Sequence[PanelJoint]) -> list[PanelJoint]:
    """该板作为端面参与的所有接触。"""
    return [j for j in joints if j.end_id == panel_id]
