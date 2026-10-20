"""三合一连接件（偏心轮 + 连接杆 + 预埋螺母）。

不再按 panel_type 名称判断角色。改用制造接触：
- female（面接触方）→ 预埋螺母孔，打在板面上
- male  （边接触方）→ 连接杆孔 + 偏心轮孔

每块板的 joints 字段由 topology_solver 在求解阶段填充。
"""

from typing import Any, Dict, List, Mapping

from furniture_manufacturing.connection_points import (
    ConnectionPoint,
    collect_connection_points,
)
from furniture_manufacturing.connectors.base import (
    Connector,
    HoleSpec,
    _opposite,
    make_connection_id,
)
from furniture_manufacturing.features import from_hole_spec
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord

from .trinity_joints import (
    _is_trinity_joint,
    _other_axis,
    _trinity_female,
    _trinity_male,
)


class TrinityConnector(Connector):
    """三合一连接件。

    偏心轮位于“边接触方”板件的板面（cam_face），从可操作面钻入。
    连接杆从“边接触方”板件的端面穿入，指向“面接触方”板件的预埋螺母。
    预埋螺母在“面接触方”板件的板面上，朝柜内方向钻入。

    深度方向：前后双排，分别距前/后边 first_hole_mm（默认 64mm）。
    偏心轮：沿连接杆方向(x)距端面 cam.hole.edge_offset_mm（33.5mm），深度方向与连接杆同排。
    """

    name = "三合一连接件"
    produces_connection_points = True
    hole_type_for_json = "three_in_one"
    catalog_entry = "three_in_one"
    rules_section = "system_32_drilling"
    hole_legend = {
        "three_in_one_cam": {"color": "#FF6B35", "label": "三合一偏心轮孔 12mm", "glb_group": "偏心轮孔"},
        "three_in_one_rod": {"color": "#FF4500", "label": "三合一连接杆端孔 8mm", "glb_group": "连接杆孔"},
        "three_in_one_nut": {"color": "#D95F02", "label": "三合一预埋螺母孔 10mm", "glb_group": "预埋螺母孔"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        """匹配 — 用连接拓扑而非 panel_type 名称。"""
        entry = self.catalog.get(self.catalog_entry, {})
        first_key = next(iter(entry)) if entry else None
        spec = entry.get(first_key, {}) if first_key else {}
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}

        by_label = {p.label: p for p in panels}
        female_panels = [p for p in panels if _trinity_female(p, by_label)]
        male_panels = [p for p in panels if _trinity_male(p, by_label)]

        return {
            "panels": female_panels + male_panels,
            "female": female_panels,
            "male": male_panels,
            "spec": spec,
            "rules": rules,
        }

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        """单板接口不打孔。三合一孔成对出现，只由 generate_holes_for_panels 按接触生成。"""
        return []

    # ── assembly-aware（连接驱动，轴无关）──────────────────────────

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        """生成所有三合一孔位。

        对每个端面件带 cam 的连接（边轴 x 或 y）成对生成：
        - female 面 → 预埋螺母孔（位置对齐 male 的连接杆轴线与连接排）
        - male 边   → 连接杆孔（端面）
        - male cam 面 → 偏心轮孔
        连接排沿"连接平面内除边轴与 cam 面轴之外的第三轴"分布。
        没有接触的板不打孔。
        """
        matched = self.match(panels)
        spec = matched.get("spec", {})
        cam_spec = spec.get("cam", {})
        rod_spec = spec.get("rod", {})
        nut_spec = spec.get("nut", {})
        rules = matched.get("rules", {})
        row_first = float(rules.get("first_hole_mm", 64))
        row_last = float(rules.get("last_hole_mm", 64))
        cam_offset = float(cam_spec.get("hole", {}).get("edge_offset_mm", 33.5))
        rod_axis_offset = float(cam_spec.get("rod_axis_to_cam_face_mm", 9))

        by_label = {panel.label: panel for panel in panels}
        result: List[HoleSpec] = []
        for panel in panels:
            fem_joints = [
                j for j in (panel.joints or [])
                if j.bearing_id == panel.label
                and _is_trinity_joint(j, by_label)
            ]
            mal_joints = [
                j for j in (panel.joints or [])
                if j.end_id == panel.label
                and _is_trinity_joint(j, by_label)
            ]
            # 螺母孔先发（按连接杆轴线位置排序），再杆、再轮
            for joint in sorted(
                fem_joints,
                key=lambda j: self._rod_axis_world(
                    j, by_label[j.end_id], rod_axis_offset
                ),
            ):
                result.extend(self._nut_holes(
                    panel, joint, by_label[joint.end_id], nut_spec, cam_spec,
                    row_first, row_last, rod_axis_offset,
                ))
            for joint in sorted(mal_joints, key=lambda j: j.edge_sign):
                result.extend(self._rod_holes(
                    panel, joint, rod_spec, cam_spec, cam_offset,
                    row_first, row_last, rod_axis_offset,
                ))
            for joint in sorted(mal_joints, key=lambda j: j.edge_sign):
                result.extend(self._cam_holes(
                    panel, joint, cam_spec, cam_offset,
                    row_first, row_last, rod_axis_offset,
                ))
        return result

    @staticmethod
    def _rod_axis_world(
        joint: Any, male: PanelRecord, rod_axis_offset: float
    ) -> float:
        """male 连接杆轴线在 cam 面法向轴上的世界坐标（取整到 0.001）。"""
        cam_face = male.cam_face or "+z"
        t = cam_face[1]
        size_t = getattr(male, f"size_{t}", 0.0)
        pos_t = getattr(male, f"pos_{t}", 0.0)
        if size_t <= 0:
            # 旧 joint 数据缺端面件尺寸：退回 end_z（旧行为，仅 z 轴有效）
            return joint.end_z
        rod_t = (
            size_t - rod_axis_offset if cam_face[0] == "+" else rod_axis_offset
        )
        return round(pos_t + rod_t, 3)

    def _nut_holes(
        self, panel: PanelRecord, joint: Any, male: PanelRecord,
        nut_spec: Dict[str, Any], cam_spec: Dict[str, Any],
        row_first: float, row_last: float, rod_axis_offset: float,
    ) -> List[HoleSpec]:
        """female 面板上的预埋螺母孔：与 male 的连接杆/轮同排同位。"""
        result: List[HoleSpec] = []
        n_diam = float(nut_spec.get("hole", {}).get("diameter_mm", 10))
        n_depth = float(nut_spec.get("hole", {}).get("depth_mm", 11))
        face = joint.face
        f = face[1]
        a = joint.edge_axis
        cam_face = male.cam_face or "+z"
        t = cam_face[1]
        s2 = _other_axis(a, t)
        face_local = panel.face_position(face) - getattr(panel, f"pos_{f}")
        t_rod_world = self._rod_axis_world(joint, male, rod_axis_offset)
        # 连接排沿 s2 以 male 的跨度为基准（世界坐标，螺母与杆/轮严格同排）
        rows_world = [
            getattr(male, f"pos_{s2}") + row_first,
            getattr(male, f"pos_{s2}") + getattr(male, f"size_{s2}") - row_last,
        ]
        nut_dir = _opposite(face)
        for row_index, row_world in enumerate(rows_world):
            local = {
                f: face_local,
                t: t_rod_world - getattr(panel, f"pos_{t}"),
                s2: row_world - getattr(panel, f"pos_{s2}"),
            }
            x_global, y_global, z_global = panel.to_global(
                local["x"], local["y"], local["z"]
            )
            result.append(HoleSpec(
                hole_type="three_in_one_nut", panel_label=panel.label,
                x_global=x_global, y_global=y_global, z_global=z_global,
                x_local=local["x"], y_local=local["y"], z_local=local["z"],
                diameter=n_diam, depth=n_depth, direction=nut_dir,
                is_face_hole=True, note="预埋螺母孔",
                connection_id=make_connection_id(
                    joint.bearing_id, joint.end_id, row_index,
                )))
        return result

    def _rod_holes(
        self, panel: PanelRecord, joint: Any,
        rod_spec: Dict[str, Any], cam_spec: Dict[str, Any], cam_offset: float,
        row_first: float, row_last: float, rod_axis_offset: float,
    ) -> List[HoleSpec]:
        """male 面板端面的连接杆孔（轴无关）。"""
        result: List[HoleSpec] = []
        r_diam = float(rod_spec.get("hole", {}).get("diameter_mm", 8))
        r_depth = float(rod_spec.get("hole", {}).get("depth_mm", 33))
        a = joint.edge_axis
        cam_face = panel.cam_face or "+z"
        t = cam_face[1]
        s2 = _other_axis(a, t)
        rows = [row_first, getattr(panel, f"size_{s2}") - row_last]
        edge_local = (
            0.0 if joint.edge_sign == -1 else getattr(panel, f"size_{a}")
        )
        rod_dir = f"{'+' if joint.edge_sign == -1 else '-'}{a}"
        size_t = getattr(panel, f"size_{t}")
        t_rod = (
            size_t - rod_axis_offset if cam_face[0] == "+" else rod_axis_offset
        )
        for row_index, row in enumerate(rows):
            local = {a: edge_local, s2: row, t: t_rod}
            x_global, y_global, z_global = panel.to_global(
                local["x"], local["y"], local["z"]
            )
            result.append(HoleSpec(
                hole_type="three_in_one_rod", panel_label=panel.label,
                x_global=x_global, y_global=y_global, z_global=z_global,
                x_local=local["x"], y_local=local["y"], z_local=local["z"],
                diameter=r_diam, depth=r_depth, direction=rod_dir,
                is_face_hole=False, note="连接杆孔",
                connection_id=make_connection_id(
                    joint.bearing_id, joint.end_id, row_index,
                )))
        return result

    def _cam_holes(
        self, panel: PanelRecord, joint: Any,
        cam_spec: Dict[str, Any], cam_offset: float,
        row_first: float, row_last: float, rod_axis_offset: float,
    ) -> List[HoleSpec]:
        """male 面板 cam 面上的偏心轮孔（轴无关）。"""
        result: List[HoleSpec] = []
        w_diam = float(cam_spec.get("hole", {}).get("diameter_mm", 12))
        w_depth = float(cam_spec.get("hole", {}).get("depth_mm", 13.5))
        a = joint.edge_axis
        cam_face = panel.cam_face or "+z"
        t = cam_face[1]
        s2 = _other_axis(a, t)
        rows = [row_first, getattr(panel, f"size_{s2}") - row_last]
        cam_a = (
            cam_offset
            if joint.edge_sign == -1
            else getattr(panel, f"size_{a}") - cam_offset
        )
        cam_t = (
            0.0 if cam_face[0] == "-" else getattr(panel, f"size_{t}")
        )
        cam_dir = _opposite(cam_face)
        for row_index, row in enumerate(rows):
            local = {a: cam_a, s2: row, t: cam_t}
            x_global, y_global, z_global = panel.to_global(
                local["x"], local["y"], local["z"]
            )
            result.append(HoleSpec(
                hole_type="three_in_one_cam", panel_label=panel.label,
                x_global=x_global, y_global=y_global, z_global=z_global,
                x_local=local["x"], y_local=local["y"], z_local=local["z"],
                diameter=w_diam, depth=w_depth, direction=cam_dir,
                is_face_hole=True, note="偏心轮孔",
                connection_id=make_connection_id(
                    joint.bearing_id, joint.end_id, row_index,
                )))
        return result

    def generate_connection_points(
        self,
        panels: List[PanelRecord],
    ) -> List[ConnectionPoint]:
        """三合一：轮/杆/螺母三件套按 connection_id 打包为带 owner 的连接点。"""
        return collect_connection_points(
            [from_hole_spec(h) for h in self.generate_holes_for_panels(panels)],
            owner=self.__class__.__name__,
        )

    def _own_connection_points(
        self,
        panels: List[PanelRecord],
        connection_points: List[ConnectionPoint] | None,
    ) -> List[ConnectionPoint]:
        """本连接件自己的连接点：有共享列表就按 owner 过滤，否则按点产出。"""
        if connection_points is None:
            return self.generate_connection_points(panels)
        return [
            p for p in connection_points if p.owner == self.__class__.__name__
        ]

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
        connection_points: List[ConnectionPoint] | None = None,
        features: List[Any] | None = None,
    ) -> List[HardwareRecord]:
        """生成三合一 BOM 清单。

        数量 = 连接点数（一套三合一 = 一个连接点，孔即真源）。
        品牌由确认选择（options）决定；未选择时目录唯一才返回。
        """
        matched = self.match(panels)
        spec = matched["spec"]
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        brand = self.resolve_brand(spec.get("brands", []), opts.get("brand"))
        quantity = len(self._own_connection_points(panels, connection_points))
        return [HardwareRecord(
            name=self.name,
            spec="偏心轮+连接杆+预埋螺母（实物规格待确认）",
            quantity=quantity,
            unit="套", brand=brand.get("name", "默认"), model=brand.get("model", "SJY-01"))]

    def validate(
        self,
        report: Any,
        panels: List[PanelRecord],
        hardware: List[HardwareRecord],
        drilled: Dict[str, Any],
        connection_points: List[ConnectionPoint] | None = None,
    ) -> None:
        """三合一专属校验：按连接点(ConnectionPoint)对齐，每个连接点恰好 1 轮 + 1 杆 + 1 螺母。

        只统计本连接件自己生成的孔（柜体三合一）；背板三合一由
        BackMountConnector 负责，合并孔类型后也不会把背板的孔算进柜体。
        """
        points = self._own_connection_points(panels, connection_points)
        hardware_by_name = {item.name: item for item in hardware}
        trinity_hardware = hardware_by_name.get(self.name)
        if trinity_hardware is not None and trinity_hardware.quantity != len(points):
            report.add_error(
                "TRINITY_HARDWARE_COUNT_MISMATCH",
                f"三合一连接件数量 {trinity_hardware.quantity} 与连接点数 {len(points)} 不一致",
                "hardware",
            )
        for point in points:
            cam = len(point.holes_of_type("three_in_one_cam"))
            rod = len(point.holes_of_type("three_in_one_rod"))
            nut = len(point.holes_of_type("three_in_one_nut"))
            if rod != cam:
                report.add_error(
                    "TRINITY_ROD_CAM_COUNT_MISMATCH",
                    f"连接点 {point.connection_id} 连接杆孔数 {rod} 与偏心轮孔数 {cam} 不一致（1:1 配对）",
                    "drilled_holes",
                )
            if nut != cam:
                report.add_error(
                    "TRINITY_NUT_CAM_COUNT_MISMATCH",
                    f"连接点 {point.connection_id} 预埋螺母孔数 {nut} 与偏心轮孔数 {cam} 不一致（1:1 配对）",
                    "drilled_holes",
                )

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        """圆孔走 HoleSpec。加工指令只留给槽类 cut_box。"""
        return []

