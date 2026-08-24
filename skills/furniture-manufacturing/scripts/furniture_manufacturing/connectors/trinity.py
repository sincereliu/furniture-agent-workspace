"""三合一连接件（偏心轮 + 连接杆 + 预埋螺母）。

不再按 panel_type 名称判断角色。改用连接拓扑（PanelJoint）：
- female（面接触方）→ 预埋螺母孔，打在 inner_face 面上
- male  （边接触方）→ 连接杆孔 + 偏心轮孔

每块板的 joints 字段由 topology_solver 在求解阶段填充。
"""

from typing import Any, Dict, List, Set

from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


# ── Joint helpers ──────────────────────────────────────────────────

def _joints_of(panel: PanelRecord) -> list:
    """面板参与的所有连接（PanelJoint 列表）。"""
    return list(panel.joints) if panel.joints else []


def _is_female(panel: PanelRecord) -> bool:
    """该板是否有面被其他板的端面顶着（面接触方 → 预埋螺母）。"""
    return any(j.female_id == panel.label for j in _joints_of(panel))


def _is_male(panel: PanelRecord) -> bool:
    """该板是否有端面顶着其他板的面（边接触方 → 连接杆+偏心轮）。"""
    return any(j.male_id == panel.label for j in _joints_of(panel))


def _trinity_female(panel: PanelRecord) -> bool:
    """x 轴方向的面接触方（侧板/隔板）。

    优先从连接拓扑推导；无连接拓扑时退回 panel_type 判断。
    """
    if panel.joints:
        return any(
            j.female_id == panel.label and j.face[1] == "x"
            for j in _joints_of(panel)
        )
    # fallback: no joint topology available
    return panel.panel_type in ("side", "divider")


def _trinity_male(panel: PanelRecord) -> bool:
    """x 轴方向的边接触方（横板），端面在 x 轴且 male_has_cam。

    优先从连接拓扑推导；无连接拓扑时退回 panel_type 判断。
    """
    if panel.joints:
        return any(
            j.male_id == panel.label and j.edge_axis == "x" and j.male_has_cam
            for j in _joints_of(panel)
        )
    # fallback: no joint topology available
    return panel.panel_type in ("top", "bottom", "fixed_shelf")


def _gather_joints(panels: list[PanelRecord]) -> list:
    """收集所有面板的连接拓扑（去重）。"""
    seen: Set[tuple] = set()
    result = []
    for p in panels:
        for j in _joints_of(p):
            key = (j.female_id, j.male_id)
            if key not in seen:
                seen.add(key)
                result.append(j)
    return result


def _trinity_joints(panels: list[PanelRecord]) -> list:
    """筛选三合一相关的连接（x 轴方向，male_has_cam）。"""
    return [
        j for j in _gather_joints(panels)
        if j.face[1] == "x" and j.edge_axis == "x" and j.male_has_cam
    ]


def _male_edge_signs(panel: PanelRecord) -> Set[int]:
    """male 面板的 x 轴端面连接方向（-1=左，+1=右）。

    优先从连接拓扑推导；无连接拓扑时返回两端。
    """
    if panel.joints:
        signs = {
            j.edge_sign for j in _joints_of(panel)
            if j.male_id == panel.label and j.edge_axis == "x"
        }
        if signs:
            return signs
    # fallback: no joint topology → assume both ends
    return {-1, 1}


def _opposite(axis: str) -> str:
    """反转带符号轴方向：\"+x\"→\"-x\"，\"-y\"→\"+y\"。"""
    if not axis or axis[0] not in ("+", "-"):
        return "-x"
    return f"{'+' if axis[0] == '-' else '-'}{axis[1]}"


class TrinityConnector(Connector):
    """三合一连接件。

    偏心轮位于横板的 cam_face，从可操作面钻入。
    连接杆从横板端面穿入，指向竖板的预埋螺母。
    预埋螺母在竖板内侧面，朝柜内方向钻入。

    深度方向：前后双排，分别距前/后边 first_hole_mm（默认 64mm）。
    偏心轮：沿连接杆方向(x)距端面 center_offset_from_edge（默认 33.5mm），深度方向与连接杆同排。
    """

    name = "三合一连接件"
    hole_type_for_json = "three_in_one"
    catalog_entry = "three_in_one"
    rules_section = "system_32_drilling"

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        """匹配 — 用连接拓扑而非 panel_type 名称。"""
        entry = self.catalog.get(self.catalog_entry, {})
        first_key = next(iter(entry)) if entry else None
        spec = entry.get(first_key, {}) if first_key else {}
        brand = (spec.get("brands", [{}]) or [{}])[0]
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}

        female_panels = [p for p in panels if _trinity_female(p)]
        male_panels = [p for p in panels if _trinity_male(p)]

        return {
            "panels": female_panels + male_panels,
            "female": female_panels,
            "male": male_panels,
            "spec": spec,
            "brand": brand,
            "rules": rules,
        }

    # ── single-panel holes ──────────────────────────────────────

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        """在一块板件上生成三合一孔位。

        female（面接触方）→ 预埋螺母孔
        male  （边接触方）→ 连接杆孔（端面）+ 偏心轮孔（cam_face）
        """
        result: List[HoleSpec] = []
        matched = self.match([panel])
        rules = matched.get("rules", {})
        spec = matched.get("spec", {})
        wheel = spec.get("eccentric_wheel", {})
        rod = spec.get("connecting_rod", {})
        nut = spec.get("pre_embedded_nut", {})
        z_positions = self._system_32_positions(panel, rules)
        nut_first = float(rules.get("first_hole_mm", 64))
        nut_last  = float(rules.get("last_hole_mm", 64))
        cam_offset = float(wheel.get("center_offset_from_edge_mm", 33.5))

        if _trinity_female(panel):
            result.extend(self._female_holes(
                panel, z_positions, nut_first, nut_last, nut, wheel))
        if _trinity_male(panel):
            result.extend(self._male_holes(
                panel, nut_first, nut_last, rod, wheel, cam_offset))

        return result

    def _female_holes(
        self, panel: PanelRecord, z_positions: List[float],
        nut_first: float, nut_last: float, nut: Dict[str, Any],
        wheel: Dict[str, Any],
    ) -> List[HoleSpec]:
        """竖板（面接触方）→ 预埋螺母打在 inner_face 上。

        有连接拓扑时：只在横板连接的 Z 高度打螺母（1:1:1）。\n        无连接拓扑时：回退系统-32 全高排钻。

        孔位先在面板局部坐标定义（局部为唯一真源），世界坐标由 to_global 派生。
        """
        result: List[HoleSpec] = []
        n_diam = float(nut.get("diameter_mm", 10))
        n_depth = float(nut.get("depth_mm", 11))
        inner = panel.inner_face or ""
        nut_dir = _opposite(inner)

        # 螺母孔打在 inner_face 上：用几何接口 face_position 定位（面在 x 轴），
        # 折算成板件局部坐标（局部为真源，世界由 to_global 派生）。
        face = inner if inner in ("+x", "-x") else "+x"
        x_local = panel.face_position(face) - panel.pos_x

        # 从连接拓扑确定螺母 Z 高度（每块横板一个高度，只取三合一连接）
        trinity_female_joints = [
            j for j in _joints_of(panel)
            if j.female_id == panel.label and j.face[1] == "x" and j.male_has_cam
        ]
        rod_axis_offset = float(wheel.get("rod_axis_offset_mm", 9))
        if trinity_female_joints:
            # 螺母孔与连接杆轴线同高(cam_face + 偏心距)，而非板厚中心；
            # joint 高度是柜体坐标，折算到板件局部坐标。
            z_locals = sorted({
                round(self._rod_axis_z_from_joint(j, rod_axis_offset), 3) - panel.pos_z
                for j in trinity_female_joints
            })
        else:
            # fallback: 系统-32 全高排钻（z_positions 已是局部坐标）
            z_locals = list(z_positions)

        for z_local in z_locals:
            for y_local in [nut_first, panel.size_y - nut_last]:
                x_global, y_global, z_global = panel.to_global(
                    x_local, y_local, z_local
                )
                result.append(HoleSpec(
                    hole_type="system_32_pre_nut", panel_label=panel.label,
                    x_global=x_global,
                    y_global=y_global,
                    z_global=z_global,
                    x_local=x_local, y_local=y_local,
                    z_local=z_local,
                    diameter=n_diam, depth=n_depth, direction=nut_dir,
                    is_face_hole=True, note="预埋螺母孔"))
        return result

    def _male_holes(
        self, panel: PanelRecord, nut_first: float, nut_last: float,
        rod: Dict[str, Any], wheel: Dict[str, Any], cam_offset: float,
    ) -> List[HoleSpec]:
        """横板（边接触方）→ 连接杆孔 + 偏心轮孔。

        根据 panel.joints 确定哪些端面有连接：
        edge_sign == -1 → 左端，+1 → 右端。只在实际有连接的端面生成孔位。

        孔位先在面板局部坐标定义（局部为唯一真源），世界坐标由 to_global 派生。
        """
        result: List[HoleSpec] = []
        r_diam = float(rod.get("diameter_mm", 8))
        r_depth = float(rod.get("insertion_depth_mm", 33))
        w_diam = float(wheel.get("diameter_mm", 12))
        w_depth = float(wheel.get("hole_depth_mm", 13.5))
        # 连接杆轴线高度 = cam_face ± 偏心距(五金参数)，与板厚无关。
        rod_axis_offset = float(wheel.get("rod_axis_offset_mm", 9))
        cam = panel.cam_face or ""

        # cam_face 是偏心轮的可操作面：孔应落在该面所在的局部坐标。
        # cam == "+z" → 顶面(z_local = size_z)；cam == "-z" → 底面(z_local = 0)。
        if cam == "+z":
            cam_zl = panel.size_z
            rod_zl = panel.size_z - rod_axis_offset
        elif cam == "-z":
            cam_zl = 0.0
            rod_zl = rod_axis_offset
        else:
            cam_zl = panel.size_z
            cam = "+z"
            rod_zl = panel.size_z - rod_axis_offset

        # direction 统一为钻入方向（往板内）：轮孔从 cam_face 钻入，
        # 钻入方向 = cam_face 的反向（direction 语义统一约定，见 coordinate-naming.md）。
        cam_dir = _opposite(cam)

        rod_y_offsets = [nut_first, panel.size_y - nut_last]

        edge_signs = _male_edge_signs(panel)
        for sign in edge_signs:
            if sign == -1:
                x_local = 0.0
                rod_sign = "+x"
                # 偏心轮圆心距端面 cam_offset，沿连接杆伸入方向(向板内)
                cam_x_local = cam_offset
            else:
                x_local = panel.size_x
                rod_sign = "-x"
                cam_x_local = panel.size_x - cam_offset

            # 与旧实现保持相同的发射顺序：先全部连接杆孔，再全部偏心轮孔
            for y_offset in rod_y_offsets:
                rod_x, rod_y, rod_z = panel.to_global(x_local, y_offset, rod_zl)
                result.append(HoleSpec(
                    hole_type="system_32_male", panel_label=panel.label,
                    x_global=rod_x,
                    y_global=rod_y,
                    z_global=rod_z,
                    x_local=x_local, y_local=y_offset, z_local=rod_zl,
                    diameter=r_diam, depth=r_depth, direction=rod_sign,
                    is_face_hole=False, note="连接杆孔"))

            for y_offset in rod_y_offsets:   # 偏心轮 y 与连接杆 y 一致
                cam_x, cam_y, cam_z = panel.to_global(cam_x_local, y_offset, cam_zl)
                result.append(HoleSpec(
                    hole_type="system_32_female", panel_label=panel.label,
                    x_global=cam_x,
                    y_global=cam_y,
                    z_global=cam_z,
                    x_local=cam_x_local, y_local=y_offset, z_local=cam_zl,
                    diameter=w_diam, depth=w_depth, direction=cam_dir,
                    is_face_hole=True, note="偏心轮孔"))

        return result

    @staticmethod
    def _rod_axis_z_from_joint(joint: Any, rod_axis_offset: float) -> float:
        """从连接拓扑反推连接杆轴线 Z（male 的 cam_face + 偏心距）。

        旧数据无 male_cam_face/male_size_z 时，退回 male_z（板厚中心，旧行为）。
        """
        cam_face = getattr(joint, "male_cam_face", None)
        size_z = getattr(joint, "male_size_z", 0.0)
        if not cam_face or size_z <= 0:
            return joint.male_z
        # joint.male_z = male 板厚中心；cam_face 位置 = 中心 ± 板厚/2
        if cam_face == "-z":
            return (joint.male_z - size_z / 2.0) + rod_axis_offset
        return (joint.male_z + size_z / 2.0) - rod_axis_offset

    # ── assembly-aware ──────────────────────────────────────────

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        """生成所有三合一孔位。

        基础孔位由 generate_holes() 逐板生成——female 螺母按 joint.male_z
        打（1:1:1），male 杆+轮按 joint.edge_sign 打。
        """
        return [
            hole
            for panel in panels
            for hole in self.generate_holes(panel)
        ]

    def _system_32_positions(self, panel: PanelRecord, rules: Dict[str, Any]) -> List[float]:
        """按系统 32 排钻规则计算孔位 Z 坐标列表。"""
        first = float(rules.get("first_hole_mm", 64))
        last = float(rules.get("last_hole_mm", 64))
        max_spacing = float(rules.get("max_spacing_mm", 512))
        min_spacing = float(rules.get("min_spacing_mm", 32))
        snap = float(rules.get("snap_to_mm", 0.5))
        usable = panel.drill_length - first - last
        if usable <= 0:
            return [panel.drill_length / 2]
        spacings = [512, 480, 448, 416, 384, 352, 320, 288, 256, 224, 192, 160, 128, 96, 64]
        best = 320.0
        for sp in spacings:
            if sp <= max_spacing and int(usable / sp) >= 1:
                best = sp
                break
        count = max(1, int(usable / best))
        actual = usable / count
        holes = [first] + [first + (i + 1) * actual for i in range(count - 1)] + [panel.drill_length - last]
        holes = sorted(set(holes))
        merged = [holes[0]]
        for h in holes[1:]:
            if h - merged[-1] >= min_spacing:
                merged.append(h)
        if snap > 0:
            merged = [round(h / snap) * snap for h in merged]
        return merged

    def boms(self, panels: List[PanelRecord]) -> List[HardwareRecord]:
        """生成三合一 BOM 清单。

        数量 = 实际生成的偏心轮孔数（孔即真源）。
        一套三合一 = 1 偏心轮 + 1 连接杆 + 1 预埋螺母。
        """
        matched = self.match(panels)
        brand = matched["brand"]
        holes = self.generate_holes_for_panels(panels)
        quantity = sum(1 for h in holes if h.hole_type == "system_32_female")
        return [HardwareRecord(
            name=self.name,
            spec="偏心轮φ12+预埋螺母φ10×11+连接杆φ8×33",
            quantity=quantity,
            unit="套", brand=brand.get("name", "默认"), model=brand.get("model", "SJY-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        """生成三合一孔位的 cut_box 加工指令。"""
        ops: List[MachiningOperation] = []
        for hole in self.generate_holes(panel):
            d = hole.diameter
            # id 含 x_local：区分左右两端同 (z,y) 的孔，避免 DUPLICATE_OPERATION_ID
            ops.append(MachiningOperation(
                id=(
                    f"{hole.hole_type}_{panel.label}_"
                    f"{hole.z_local:.0f}_{hole.y_local:.0f}_{hole.x_local:.0f}"
                ),
                operation_type="cut_box", target_panel=panel.label,
                size_x=hole.depth if hole.direction in ("+x", "-x") else d,
                size_y=hole.depth if hole.direction in ("+y", "-y") else d,
                size_z=hole.depth if hole.direction in ("+z", "-z") else d,
                pos_x=hole.x_global - d / 2, pos_y=hole.y_global - d / 2,
                pos_z=hole.z_global - d / 2,
                note=f"{self.name} {hole.note}"))
        return ops

