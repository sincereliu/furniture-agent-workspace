"""连接拓扑 — 板件之间的面-边邻接关系。

不依赖板件名称（"side"/"top" 等），只根据几何位置 + 语义面
推导出哪块板的哪个面碰到了哪块板的哪个端面。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .panel_models import PanelPlacement


@dataclass(frozen=True)
class PanelJoint:
    """一条面-边邻接：female 的面碰 male 的端面。

    对于三合一连接件：
    - female（面接触方）→ 预埋螺母孔
    - male  （边接触方）→ 连接杆孔 + 偏心轮孔
    """

    female_id: str   # 面板 ID（面被接触的那块板）
    male_id: str     # 面板 ID（端面顶住面的那块板）
    face: str        # female 的哪个语义面被接触（inner_face 的值，如 "+x"）
    edge_axis: str   # male 的端面所在轴（"x"/"y"/"z"）
    edge_sign: int   # male 的端面方向：+1=轴正端，-1=轴负端
    male_z: float    # male 面板厚度中心线的 Z 坐标（female 螺母所在的 Z 高度）
    male_has_cam: bool = False  # male 是否有 cam_face（三合一标志）


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
    """从板件列表推导所有面-边邻接。

    对每块有 inner_face 的板（female 候选），
    找出所有端面顶在该面上的板（male 候选）。
    """
    joints: list[PanelJoint] = []
    candidates = [p for p in placements if p.inner_face]

    for female in candidates:
        face_dir = female.inner_face
        face_axis = _axis_char(face_dir)
        face_pos = _face_position(female, face_dir)

        # 待检查的轴线（female 面法向之外的另外两轴）
        other_axes = [a for a in ("x", "y", "z") if a != face_axis]

        for male in placements:
            if male.id == female.id:
                continue
            # male 必须在这个面上有端面才可能接触
            male_min, male_max = _axis_range(male, face_axis)

            if not (
                abs(male_min - face_pos) <= _SNAP_TOLERANCE
                or abs(male_max - face_pos) <= _SNAP_TOLERANCE
            ):
                continue

            # 另外两个轴必须重叠
            overlap_all = True
            for axis in other_axes:
                f_min, f_max = _axis_range(female, axis)
                m_min, m_max = _axis_range(male, axis)
                if not _overlap(f_min, f_max, m_min, m_max):
                    overlap_all = False
                    break

            if not overlap_all:
                continue

            # 确定 male 的端面方向
            if abs(male_min - face_pos) <= _SNAP_TOLERANCE:
                edge_sign = -1
            else:
                edge_sign = +1

            joints.append(
                PanelJoint(
                    female_id=female.id,
                    male_id=male.id,
                    face=face_dir,
                    edge_axis=face_axis,
                    edge_sign=edge_sign,
                    male_z=male.pos_z + male.size_z / 2.0,  # 厚度中心线 Z，螺母打在这
                    male_has_cam=bool(male.cam_face),  # 有 cam_face 才是三合一
                )
            )

    return joints


def is_female(panel_id: str, joints: Sequence[PanelJoint]) -> bool:
    """该板是否是某个连接的 female（面接触方）。"""
    return any(j.female_id == panel_id for j in joints)


def is_male(panel_id: str, joints: Sequence[PanelJoint]) -> bool:
    """该板是否是某个连接的 male（边接触方）。"""
    return any(j.male_id == panel_id for j in joints)


def female_joints(panel_id: str, joints: Sequence[PanelJoint]) -> list[PanelJoint]:
    """该板作为 female 参与的所有连接。"""
    return [j for j in joints if j.female_id == panel_id]


def male_joints(panel_id: str, joints: Sequence[PanelJoint]) -> list[PanelJoint]:
    """该板作为 male 参与的所有连接。"""
    return [j for j in joints if j.male_id == panel_id]
