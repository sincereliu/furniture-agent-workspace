"""铰链连接件 — 门板杯孔打孔。

铰链杯孔从门板内侧面钻入，`direction` 存钻入方向（往板内，
= inner_face 的反向）。内侧面方向由 panel.inner_face 提供，
不再硬编码 "+y"。
"""

from typing import Any, Dict, List, Mapping
from furniture_manufacturing.connectors.base import Connector, HoleSpec, _opposite
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


class HingeConnector(Connector):
    """铰链连接件：在门板内侧面钻铰链杯孔。"""

    name = "液压缓冲铰链"
    hole_type_for_json = "hinge"
    catalog_entry = "hinges"
    rules_section = "hinge_drilling"
    hole_legend = {
        "hinge": {"color": "#4A90D9", "label": "铰链杯孔 35mm", "glb_group": "铰链孔位"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        """匹配所有门板及相关规则。"""
        doors = [p for p in panels if p.panel_type == "door"]
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        catalog = self.catalog.get(self.catalog_entry, {})
        return {"doors": doors, "rules": rules, "catalog": catalog}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        """在一块门板上生成铰链杯孔。

        杯孔沿门板高度方向分布，从内侧面钻入；direction 为钻入方向
        （inner_face 的反向）。
        """
        result: List[HoleSpec] = []
        if panel.panel_type != "door":
            return result
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        entry = self._resolve_entry(self.catalog.get(self.catalog_entry, {}), {})
        count, top_offset, bottom_offset = self._hinge_count(panel.size_z, rules)
        positions = self._distribute(panel.size_z, count, top_offset, bottom_offset)
        edge_offset = float(entry.get("edge_offset_mm", 5))
        cup = entry.get("cup", {}) or {}
        cup_diameter = float(cup.get("diameter_mm", 35))
        cup_depth = float(cup.get("depth_mm", 13))
        # 杯孔中心距门边 = 边距 + 杯孔半径
        cup_center_from_edge = edge_offset + cup_diameter / 2
        inner = panel.inner_face or "+y"  # default for backward compat

        # 铰链侧：优先使用显式字段，否则根据 X 位置推断
        hinge_side = panel.door_hinge_side
        if hinge_side == "left":
            x_local = cup_center_from_edge
        elif hinge_side == "right":
            x_local = panel.size_x - cup_center_from_edge
        elif panel.pos_x < panel.size_x:
            x_local = cup_center_from_edge  # 兜底：X 位置靠左 → 左铰链
        else:
            x_local = panel.size_x - cup_center_from_edge  # 兜底：X 位置靠右 → 右铰链

        # Drill direction = 钻入方向（往板内）：杯孔从内侧面钻入，
        # 钻入方向 = inner_face 的反向（direction 语义统一约定，见 coordinate-naming.md）。
        cup_dir = _opposite(inner)

        for y_local in positions:
            hole = self._make_hole(
                panel=panel,
                x_local=x_local,
                y_local=0.0,
                z_local=y_local,
                diameter=cup_diameter,
                depth=cup_depth,
                direction=cup_dir,
                note="从门板内侧面钻入的铰链杯孔",
            )
            result.append(hole)

        return result

    def _make_hole(
        self,
        panel: PanelRecord,
        x_local: float,
        y_local: float,
        z_local: float,
        diameter: float,
        depth: float,
        direction: str,
        note: str,
    ) -> HoleSpec:
        """在面板 inner_face 上打杯孔。

        孔位先在面板局部坐标定义（局部为唯一真源），
        再由 to_global 派生世界坐标（当前轴对齐：仅平移）。
        """
        inner = panel.inner_face or "+y"
        face_axis = inner[1] if len(inner) >= 2 else "y"

        # 孔中心落在 inner_face 上：该轴局部坐标 = 面位置(0 或该轴尺寸)
        origin = {"x": panel.pos_x, "y": panel.pos_y, "z": panel.pos_z}[face_axis]
        face_local = panel.face_position(inner) - origin

        local = {"x": x_local, "y": y_local, "z": z_local}
        local[face_axis] = face_local

        x_global, y_global, z_global = panel.to_global(
            local["x"], local["y"], local["z"]
        )

        return HoleSpec(
            hole_type="hinge",
            panel_label=panel.label,
            x_global=x_global,
            y_global=y_global,
            z_global=z_global,
            x_local=local["x"],
            y_local=local["y"],
            z_local=local["z"],
            diameter=diameter,
            depth=depth,
            direction=direction,
            is_face_hole=True,
            note=note,
        )

    def _hinge_count(self, door_h: float, rules: Dict[str, Any]) -> tuple:
        """根据门板高度确定铰链数量和上下边距。"""
        for entry in rules.get("count_by_door_height", []):
            if door_h <= entry["max_height_mm"]:
                return entry.get("count", 2), entry.get("top_offset_mm", 100), entry.get("bottom_offset_mm", 100)
        return 2, 100, 100

    def _distribute(self, total: float, count: int, top: float, bottom: float) -> List[float]:
        """在总长度内均匀分布 count 个位置。"""
        if count <= 1:
            return [total / 2]
        usable = total - top - bottom
        spacing = usable / (count - 1)
        return [top + i * spacing for i in range(count)]

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        """生成铰链 BOM 清单。

        条目与品牌由确认选择（options[本 catalog_entry]）决定；未选择时
        仅当目录唯一才返回，否则抛错——不再按固定规格静默挑选。
        """
        doors = [p for p in panels if p.panel_type == "door"]
        if not doors:
            return []
        catalog = self.catalog.get(self.catalog_entry, {})
        opts = self._connector_options(options)
        entry = self._resolve_entry(catalog, opts)
        brand = self.resolve_brand(entry.get("brands", []), opts.get("brand"))
        records: List[HardwareRecord] = []
        for door in doors:
            count, _, _ = self._hinge_count(
                door.size_z, self.rules.get(self.rules_section, {})
            )
            records.append(HardwareRecord(
                name=self.name,
                spec=f"{brand['name']} {brand['model']} {entry.get('angle', 100)}°",
                quantity=count, brand=brand.get("name", "默认"), model=brand.get("model", ""),
                note=f"门板: {door.name}"))
        return records

    def _connector_options(self, options: Mapping[str, Any] | None) -> Dict[str, Any]:
        opts = (options or {}).get(self.catalog_entry, {})
        return dict(opts) if isinstance(opts, Mapping) else {}

    def _resolve_entry(
        self,
        catalog: Dict[str, Any],
        opts: Dict[str, Any],
    ) -> Dict[str, Any]:
        """返回唯一铰链条目；歧义时抛错，不按固定规格静默筛选。"""
        entries = list(catalog.items())
        if not entries:
            raise ValueError("hinge catalog is empty")
        filters = {k: opts[k] for k in ("angle",) if k in opts}
        if filters:
            entries = [
                (name, spec) for name, spec in entries
                if all(spec.get(k) == v for k, v in filters.items())
            ]
            if not entries:
                raise ValueError(f"no hinge entry matches {filters!r}")
        if len(entries) == 1:
            return entries[0][1]
        raise ValueError("multiple hinge entries require an explicit selection")

    def validate(
        self,
        report: Any,
        panels: List[PanelRecord],
        hardware: List[HardwareRecord],
        drilled: Dict[str, Any],
    ) -> None:
        """铰链专属校验：杯孔在门包络内、从内侧面钻入、深度≤门厚、侧别正确、孔数=BOM 数。"""
        drilled_by_panel = {
            panel["label"]: panel["holes"] for panel in drilled["panels"]
        }
        door_panels = [p for p in panels if p.panel_type == "door"]
        # 门厚适用范围校验：door_thickness_mm = [min, max]，仅目录唯一条目时适用
        entries = list(self.catalog.get(self.catalog_entry, {}).values())
        if len(entries) == 1:
            door_range = entries[0].get("door_thickness_mm")
            if isinstance(door_range, (list, tuple)) and len(door_range) == 2:
                lo, hi = float(door_range[0]), float(door_range[1])
                for panel in door_panels:
                    if panel.thickness < lo - 1e-6 or panel.thickness > hi + 1e-6:
                        report.add_error(
                            "HINGE_DOOR_THICKNESS_OUT_OF_RANGE",
                            f"{panel.label} door thickness {panel.thickness:g}mm is outside hinge range [{lo:g}, {hi:g}]mm",
                            panel.label,
                        )
        expected_hinge_count = sum(
            item.quantity for item in hardware if item.name == self.name
        )
        hinge_holes = [
            (panel, hole)
            for panel in door_panels
            for hole in drilled_by_panel.get(panel.label, [])
            if hole["hole_type"] == "hinge"
        ]
        for panel in door_panels:
            panel_hinges = [
                hole for hole in drilled_by_panel.get(panel.label, [])
                if hole["hole_type"] == "hinge"
            ]
            if not panel_hinges:
                report.add_error(
                    "MISSING_HINGE_HOLES",
                    f"{panel.label} requires hinge cup holes",
                    panel.label,
                )
            for hole in panel_hinges:
                radius = hole["diameter"] / 2
                if (
                    hole["diameter"] <= 0
                    or hole["local_x"] - radius < -1e-6
                    or hole["local_x"] + radius > panel.size_x + 1e-6
                    or hole["local_z"] - radius < -1e-6
                    or hole["local_z"] + radius > panel.size_z + 1e-6
                ):
                    report.add_error(
                        "HINGE_HOLE_OUTSIDE_DOOR",
                        f"hinge cup on {panel.label} exceeds the door envelope",
                        panel.label,
                    )
                expected_face_coordinate = (
                    panel.size_y if panel.inner_face == "+y" else 0.0
                )
                if (
                    panel.inner_face not in {"+y", "-y"}
                    or abs(hole["local_y"] - expected_face_coordinate) > 1e-6
                    or hole["direction"] != _opposite(panel.inner_face)
                    or not hole["is_face_hole"]
                ):
                    report.add_error(
                        "HINGE_HOLE_FACE_MISMATCH",
                        f"hinge cup on {panel.label} must enter from its inner face",
                        panel.label,
                    )
                if hole["depth"] <= 0 or hole["depth"] > panel.size_y + 1e-6:
                    report.add_error(
                        "INVALID_HINGE_HOLE_DEPTH",
                        f"hinge cup depth on {panel.label} exceeds door thickness",
                        panel.label,
                    )
                if (
                    panel.door_hinge_side == "left"
                    and hole["local_x"] >= panel.size_x / 2
                ) or (
                    panel.door_hinge_side == "right"
                    and hole["local_x"] <= panel.size_x / 2
                ):
                    report.add_error(
                        "HINGE_SIDE_MISMATCH",
                        f"hinge cup on {panel.label} is on the wrong door edge",
                        panel.label,
                    )
        if len(hinge_holes) != expected_hinge_count:
            report.add_error(
                "HINGE_HARDWARE_COUNT_MISMATCH",
                "hinge cup count must match hinge hardware quantity",
                "hardware",
            )

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        """生成铰链杯孔的 cut_box 加工指令。

        根据钻入方向将 cut_box 放置在孔位入口处，使其沿钻入方向
        展开，而不是跑到板件后方（direction 已是钻入方向语义）。
        """
        ops: List[MachiningOperation] = []
        for hole in self.generate_holes(panel):
            d = hole.diameter
            # 将 cut_box 放在孔位入口处，沿打孔方向展开
            if hole.direction == "+y":
                pos_y = hole.y_global
            elif hole.direction == "-y":
                pos_y = hole.y_global - hole.depth
            else:
                pos_y = hole.y_global - hole.depth
            ops.append(MachiningOperation(
                id=f"hinge_{panel.label}_{hole.z_local:.0f}",
                operation_type="cut_box", target_panel=panel.label,
                size_x=d, size_y=hole.depth, size_z=d,
                pos_x=hole.x_global - d / 2, pos_y=pos_y,
                pos_z=hole.z_global - d / 2,
                note=f"铰链杯孔 φ{d:g}"))
        return ops


