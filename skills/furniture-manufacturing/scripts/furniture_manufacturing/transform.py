"""柜体正交旋转矩阵。

从 CabinetFrame(front, top) 自动推导 3×3 旋转矩阵（仅支持 90° 整数倍正交旋转）。
支持方案B归锚：旋转后平移使柜体左后下角回到 (0,0,0)。

坐标约定（与现存代码一致）:
    柜体全局 G: +X→右, +Y→前, +Z→上
    板件局部 L: 原点=板件左后下角=(pos_x, pos_y, pos_z)
    变换: G = panel.pos + L  ;  L = G - panel.pos
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


def _signed_axis_to_vector(signed: str) -> np.ndarray:
    """带符号轴→3D单位向量: "+x"→[+1,0,0], "-y"→[0,-1,0]."""
    axis_idx = "xyz".index(signed[1])
    sign = 1 if signed[0] == "+" else -1
    vec = np.zeros(3, dtype=float)
    vec[axis_idx] = sign
    return vec


def _cross_signed(front: str, top: str) -> str:
    """右手定则: front × top = right."""
    s1 = 1 if front[0] == "+" else -1
    s2 = 1 if top[0] == "+" else -1
    a, b = front[1], top[1]
    cycle = {
        ("x","y"):("z",1), ("y","z"):("x",1), ("z","x"):("y",1),
        ("y","x"):("z",-1), ("z","y"):("x",-1), ("x","z"):("y",-1),
    }
    axis_r, sign_r = cycle[(a, b)]
    return f"{'+' if s1*s2*sign_r>0 else '-'}{axis_r}"


@dataclass(frozen=True)
class OrthoRotation:
    """正交旋转矩阵（90°整数倍）, 方案B归锚。

    R[:,0]=right(柜体X), R[:,1]=front(柜体Y), R[:,2]=top(柜体Z)
    """

    matrix: np.ndarray  # 3×3
    front: str
    top: str

    @staticmethod
    def from_cabinet_frame(front: str, top: str) -> "OrthoRotation":
        right = _cross_signed(front, top)
        R = np.column_stack([
            _signed_axis_to_vector(right),
            _signed_axis_to_vector(front),
            _signed_axis_to_vector(top),
        ])
        return OrthoRotation(matrix=R, front=front, top=top)

    @property
    def right(self) -> str:
        return _cross_signed(self.front, self.top)

    def __repr__(self) -> str:
        return (f"OrthoRotation(front={self.front!r}, top={self.top!r}, "
                f"right={self.right!r})")

    def transform_point(self, point: np.ndarray) -> np.ndarray:
        """P' = R @ P."""
        return self.matrix @ np.asarray(point, dtype=float)

    def transform_points(
        self, points: np.ndarray, *, anchor: bool = True,
    ) -> np.ndarray:
        """批量旋转 N×3 点, anchor=True 归锚(平移 min→0)."""
        pts = np.asarray(points, dtype=float)
        rotated = pts @ self.matrix.T
        if anchor:
            rotated = rotated - rotated.min(axis=0)
        return rotated


    def transform_panels_origin(
        self, panels: Sequence[dict], *, anchor: bool = True,
    ) -> tuple:
        """面板组旋转归锚, 返回 (new_positions:N×3, min_corner:3)."""
        all_corners = []
        for p in panels:
            px, py, pz = p["pos_x"], p["pos_y"], p["pos_z"]
            sx, sy, sz = p["size_x"], p["size_y"], p["size_z"]
            for dx in (0, sx):
                for dy in (0, sy):
                    for dz in (0, sz):
                        all_corners.append((px + dx, py + dy, pz + dz))
        corners = np.array(all_corners, dtype=float)
        rotated_corners = self.transform_points(corners, anchor=False)
        min_c = rotated_corners.min(axis=0) if anchor else np.zeros(3)
        new_positions = []
        for p in panels:
            orig = np.array([p["pos_x"], p["pos_y"], p["pos_z"]], dtype=float)
            new_p = self.transform_point(orig)
            if anchor:
                new_p = new_p - min_c
            new_positions.append(new_p)
        return np.array(new_positions), min_c

    def local_to_global(self, local: np.ndarray, panel_pos: np.ndarray) -> np.ndarray:
        """L→G: G = panel_pos + L (方案B下panel_pos已含旋转偏移)."""
        return np.asarray(panel_pos) + np.asarray(local)

    def global_to_local(self, global_: np.ndarray, panel_pos: np.ndarray) -> np.ndarray:
        """G→L: L = G - panel_pos."""
        return np.asarray(global_) - np.asarray(panel_pos)

    def is_identity(self) -> bool:
        return bool(np.allclose(self.matrix, np.eye(3)))


# 预定义常见姿态
STANDARD = OrthoRotation.from_cabinet_frame("+y", "+z")   # 标准
RIGHT_90 = OrthoRotation.from_cabinet_frame("+x", "+z")   # 顺时针右转90°开口朝-X
ROT_180  = OrthoRotation.from_cabinet_frame("-y", "+z")   # 转180°
LEFT_90  = OrthoRotation.from_cabinet_frame("-x", "+z")   # 逆时针左转90°开口朝+X
FLAT     = OrthoRotation.from_cabinet_frame("+z", "-y")   # 榻榻米平放

ALL_ORTHO_ROTATIONS = [STANDARD, RIGHT_90, ROT_180, LEFT_90, FLAT]
