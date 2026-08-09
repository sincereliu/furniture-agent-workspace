"""三套坐标系统一变换接口。

坐标系:
  ① 柜体全局坐标 G:  原点=柜体左后下角, +X→右 +Y→前 +Z→上
  ② 板件局部坐标 L:  原点=板件左后下角, 轴与柜体轴平行
                      L = G - panel.pos  (方案B下panel.pos已含旋转偏移)
  ③ 六面钻加工坐标 M: 板件平放机床台面, 轴重映射由YAML配置
                      M = AxisRemap(L)

变换链:
  标准姿态面板 → [R_cabinet + 归锚] → 柜体全局 G
  G → [-panel.pos] → 板件局部 L
  L → [AxisRemap]   → 六面钻 M
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from furniture_manufacturing.transform import OrthoRotation


@dataclass
class PanelCoord:
    """板件在三套坐标系下的同一点坐标。"""
    global_: np.ndarray   # 柜体全局 G = (x_g, y_g, z_g)
    local: np.ndarray     # 板件局部 L = (x_l, y_l, z_l)
    machine: np.ndarray   # 六面钻加工 M = (xm, ym, zm)
    label: str = ""       # 孔位标签


class CoordinateSystem:
    """三套坐标系管理器, 提供统一换算接口。

    用法:
        cs = CoordinateSystem(rotation=STANDARD)
        cs.set_panel("left_side", pos=(0,0,0), size=(18,400,900))

        # 局部 → 全局
        g = cs.local_to_global(np.array([18, 64, 400]))
        # 局部 → 六面钻
        m = cs.local_to_machine(np.array([18, 64, 400]), panel_type="side")
    """

    def __init__(
        self,
        rotation: Optional[OrthoRotation] = None,
    ):
        self.rotation = rotation or OrthoRotation.from_cabinet_frame("+y", "+z")

        # 面板注册: label → {pos, size, panel_type}
        self._panels: dict[str, dict] = {}

    # ── 面板注册 ───────────────────────────────────────

    def set_panel(
        self, label: str, *,
        pos: np.ndarray | tuple,
        size: np.ndarray | tuple,
        panel_type: str = "side",
    ) -> None:
        """注册一个板件, pos/size 为全局坐标下的位置和尺寸。"""
        self._panels[label] = {
            "pos": np.asarray(pos, dtype=float),
            "size": np.asarray(size, dtype=float),
            "panel_type": panel_type,
        }

    def get_panel(self, label: str) -> dict:
        if label not in self._panels:
            raise KeyError(f"面板 '{label}' 未注册")
        return self._panels[label]

    # ── 三套坐标变换 ─────────────────────────────────

    def local_to_global(
        self, local: np.ndarray, panel_label: str,
    ) -> np.ndarray:
        """②→①: L + panel.pos = G."""
        p = self.get_panel(panel_label)
        return self.rotation.local_to_global(local, p["pos"])

    def global_to_local(
        self, global_: np.ndarray, panel_label: str,
    ) -> np.ndarray:
        """①→②: G - panel.pos = L."""
        p = self.get_panel(panel_label)
        return self.rotation.global_to_local(global_, p["pos"])

    def local_to_machine(
        self, local: np.ndarray, panel_type: str,
    ) -> np.ndarray:
        """②→③: AxisRemap(L) → M.

        panel_type 决定轴映射规则（与 six_side_drill_guigui.yaml 一致）。
        """
        lx, ly, lz = float(local[0]), float(local[1]), float(local[2])

        # 轴映射表: panel_type → (xm_from_L, ym_from_L, zm_from_L)
        axis_map = {
            "side":      (ly, lz, lx),  # 侧板: Xm←L_y(深), Ym←L_z(高), Zm←L_x(厚)
            "horizontal": (ly, lx, lz),  # 横板: Xm←L_y(深), Ym←L_x(宽), Zm←L_z(厚)
            "door":       (lz, lx, ly),  # 门板: Xm←L_z(高), Ym←L_x(宽), Zm←L_y(厚)
            "toe_kick":   (lx, lz, ly),  # 踢脚板: Xm←L_x(宽), Ym←L_z(高), Zm←L_y(厚)
        }

        mapped = axis_map.get(panel_type, axis_map["horizontal"])
        return np.array([float(mapped[0]), float(mapped[1]), float(mapped[2])])

    def global_to_machine(
        self, global_: np.ndarray, panel_label: str,
    ) -> np.ndarray:
        """①→③: G → L → M."""
        local = self.global_to_local(global_, panel_label)
        pt = self.get_panel(panel_label)["panel_type"]
        return self.local_to_machine(local, pt)

    def make_triple(
        self,
        local: np.ndarray,
        panel_label: str,
        label: str = "",
    ) -> PanelCoord:
        """从局部坐标一次生成三套坐标。"""
        p = self.get_panel(panel_label)
        g = self.local_to_global(local, panel_label)
        m = self.local_to_machine(local, p["panel_type"])
        return PanelCoord(global_=g, local=local, machine=m, label=label)

    # ── 批量面板旋转 ────────────────────────────────

    def apply_rotation_and_reanchor(self) -> dict[str, np.ndarray]:
        """对所有注册面板应用旋转 + 归锚, 返回新 pos。

        返回: {label: new_pos_3d}
        """
        panels = [{
            "pos_x": float(v["pos"][0]), "pos_y": float(v["pos"][1]),
            "pos_z": float(v["pos"][2]),
            "size_x": float(v["size"][0]), "size_y": float(v["size"][1]),
            "size_z": float(v["size"][2]),
        } for v in self._panels.values()]

        new_positions, _min_c = self.rotation.transform_panels_origin(
            panels, anchor=True,
        )

        new_pos_dict: dict[str, np.ndarray] = {}
        for (label, _), new_pos in zip(self._panels.items(), new_positions):
            self._panels[label]["pos"] = new_pos
            new_pos_dict[label] = new_pos

        return new_pos_dict
