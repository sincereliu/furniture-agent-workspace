"""三合一连接件（偏心轮 + 连接杆 + 预埋螺母）。

侧板（竖板）只生成预埋螺母孔（X 方向）。
顶板/底板/固定层板（横板）生成偏心轮孔（Z 方向）和连接杆端孔（X 方向）。
"""

from typing import Any, Dict, List
from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


class TrinityConnector(Connector):
    """三合一连接件。

    偏心轮位于横板顶面/底面（Z 方向），连接杆从横板端面穿入（X 方向），
    预埋螺母在竖板内侧面（X 方向）与连接杆对锁。
    """

    name = "三合一连接件"
    hole_type_for_json = "three_in_one"
    catalog_entry = "three_in_one"
    rules_section = "system_32_drilling"

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        """匹配竖板（侧板/隔板）和横板（顶板/底板/固定层板）。"""
        entry = self.catalog.get(self.catalog_entry, {})
        first_key = next(iter(entry)) if entry else None
        spec = entry.get(first_key, {}) if first_key else {}
        brand = (spec.get("brands", [{}]) or [{}])[0]
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        female_panels = [p for p in panels if p.panel_type in ("side", "divider")]
        male_panels = [p for p in panels if p.panel_type in ("top", "bottom", "fixed_shelf")]
        return {"panels": female_panels + male_panels, "female": female_panels,
                "male": male_panels, "spec": spec, "brand": brand, "rules": rules}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        """在一块板件上生成三合一孔位。

        竖板：仅预埋螺母（X 方向），沿系统 32 排钻孔位分布。
        横板：连接杆孔（X 方向） + 偏心轮孔（Z 方向），左右端各一组。
        """
        result: List[HoleSpec] = []
        matched = self.match([panel])
        rules = matched.get("rules", {})
        spec = matched.get("spec", {})
        wheel = spec.get("eccentric_wheel", {})
        rod = spec.get("connecting_rod", {})
        nut = spec.get("pre_embedded_nut", {})
        is_female = panel.panel_type in ("side", "divider")
        is_male = panel.panel_type in ("top", "bottom", "fixed_shelf")
        positions = self._system_32_positions(panel, rules)

        center_offset = float(wheel.get("center_offset_from_edge_mm", 33.5))

        if is_female:
            # 竖板只生成预埋螺母（X 方向），偏心轮在配对的横板上
            n_diam = float(nut.get("diameter_mm", 10))
            n_depth = float(nut.get("depth_mm", 11))
            for z_local in positions:
                result.append(HoleSpec(
                    hole_type="system_32_pre_nut", panel_label=panel.label,
                    x_global=panel.pos_x + panel.size_x,
                    y_global=panel.pos_y + panel.size_y - center_offset,
                    z_global=panel.pos_z + z_local,
                    x_local=panel.size_x, y_local=panel.size_y - center_offset,
                    z_local=z_local,
                    diameter=n_diam, depth=n_depth, direction="-x",
                    note="预埋螺母孔"))

        if is_male:
            # 横板在左右端各生成连接杆孔（X 方向）和偏心轮孔（Z 方向）
            w_diam = float(wheel.get("diameter_mm", 12))
            w_depth = float(wheel.get("hole_depth_mm", 13.5))
            r_diam = float(rod.get("diameter_mm", 8))
            r_depth = float(rod.get("insertion_depth_mm", 33))
            y_center = panel.pos_y + panel.size_y - center_offset
            z_top = panel.pos_z + panel.size_z
            for edge_x, rod_sign in [(0, "+x"), (panel.size_x, "-x")]:
                x_global = panel.pos_x + edge_x
                # 连接杆孔 — X 方向，从板件端面钻入
                result.append(HoleSpec(
                    hole_type="system_32_male", panel_label=panel.label,
                    x_global=x_global,
                    y_global=y_center,
                    z_global=z_top,
                    x_local=edge_x, y_local=panel.size_y - center_offset,
                    z_local=panel.size_z,
                    diameter=r_diam, depth=r_depth, direction=rod_sign,
                    note="连接杆孔"))
                # 偏心轮孔 — Z 方向，从板件顶面钻入
                result.append(HoleSpec(
                    hole_type="system_32_female", panel_label=panel.label,
                    x_global=x_global,
                    y_global=y_center,
                    z_global=z_top,
                    x_local=edge_x, y_local=panel.size_y - center_offset,
                    z_local=panel.size_z,
                    diameter=w_diam, depth=w_depth, direction="+z",
                    note="偏心轮孔(顶面)"))
        return result

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        """对所有板件生成孔位，并对竖板补充横板高度处缺失的预埋螺母。

        基础孔位由 ``generate_holes()`` 逐板生成。此方法利用全板件列表
        交叉参照：对每块横板的顶面 Z 坐标，检查竖板上是否已有对应的
        预埋螺母；若没有则补充。
        """
        assigned_panels = {p.label for p in panels}
        result: List[HoleSpec] = [
            hole
            for panel in panels
            for hole in self.generate_holes(panel)
        ]

        # 单板调用无交叉参照上下文，直接返回
        if len(assigned_panels) <= 1:
            return result

        female_panels = [
            p for p in panels if p.panel_type in ("side", "divider")
        ]
        male_panels = [
            p for p in panels if p.panel_type in ("top", "bottom", "fixed_shelf")
        ]
        if not female_panels or not male_panels:
            return result

        spec_entry = self.catalog.get(self.catalog_entry, {})
        first_key = next(iter(spec_entry)) if spec_entry else None
        spec = spec_entry.get(first_key, {}) if first_key else {}
        wheel = spec.get("eccentric_wheel", {})
        nut = spec.get("pre_embedded_nut", {})
        center_offset = float(
            wheel.get("center_offset_from_edge_mm", 33.5)
        )
        n_diam = float(nut.get("diameter_mm", 10))
        n_depth = float(nut.get("depth_mm", 11))

        # 收集每块竖板上已有的 Z 坐标（用于去重）
        existing: dict[str, set[float]] = {}
        for hole in result:
            if hole.panel_label in {f.label for f in female_panels}:
                existing.setdefault(hole.panel_label, set()).add(
                    round(hole.z_global, 3)
                )

        for male in male_panels:
            z_global = round(male.pos_z + male.size_z, 3)

            for female in female_panels:
                if (
                    z_global not in existing.get(female.label, set())
                    and female.pos_z <= z_global <= female.pos_z + female.size_z
                ):
                    x_center = round(female.pos_x + female.size_x, 3)
                    y_center = round(
                        female.pos_y + female.size_y - center_offset, 3
                    )
                    result.append(HoleSpec(
                        hole_type="system_32_pre_nut",
                        panel_label=female.label,
                        x_global=x_center,
                        y_global=y_center,
                        z_global=z_global,
                        x_local=female.size_x,
                        y_local=female.size_y - center_offset,
                        z_local=z_global - female.pos_z,
                        diameter=n_diam,
                        depth=n_depth,
                        direction="-x",
                        note=f"预埋螺母孔(对应{male.name})",
                    ))

        return result

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
        """生成三合一 BOM 清单。"""
        matched = self.match(panels)
        brand = matched["brand"]
        return [HardwareRecord(
            name=self.name,
            spec="偏心轮φ12+预埋螺母φ10×11+连接杆φ8×33",
            quantity=sum(len(self._system_32_positions(p, matched["rules"]))
                         for p in matched["female"]),
            unit="套", brand=brand.get("name", "默认"), model=brand.get("model", "SJY-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        """生成三合一孔位的 cut_box 加工指令。"""
        ops: List[MachiningOperation] = []
        for hole in self.generate_holes(panel):
            d = hole.diameter
            ops.append(MachiningOperation(
                id=f"{hole.hole_type}_{panel.label}_{hole.z_local:.0f}",
                operation_type="cut_box", target_panel=panel.label,
                size_x=hole.depth if hole.direction in ("+x", "-x") else d,
                size_y=hole.depth if hole.direction in ("+y", "-y") else d,
                size_z=hole.depth if hole.direction in ("+z", "-z") else d,
                pos_x=hole.x_global - d / 2, pos_y=hole.y_global - d / 2,
                pos_z=hole.z_global - d / 2,
                note=f"{self.name} {hole.note}"))
        return ops