"""三合一连接件（偏心轮 + 连接杆 + 预埋螺母）。

侧板（竖板）只生成预埋螺母孔。预埋螺母打在竖板的内侧面。
左侧板 inner_face="+x" → 螺母方向="-x"（从内侧面钻入）
右侧板 inner_face="-x" → 螺母方向="+x"（从内侧面钻入）

顶板/底板/固定层板（横板）生成连接杆孔和偏心轮孔。
偏心轮打在面板的可操作面（cam_face），由面板规划器标记。

三合一在深度方向为双排：前后各一组，偏移量按 system-32 的 first/last 规则（默认 64mm）。
偏心轮的深度偏移使用 center_offset_from_edge (默认 33.5mm，偏心轮圆心到板边缘的距离)。
"""

from typing import Any, Dict, List
from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


class TrinityConnector(Connector):
    """三合一连接件。

    偏心轮位于横板的 cam_face，从可操作面钻入。
    连接杆从横板端面穿入，指向竖板的预埋螺母。
    预埋螺母在竖板内侧面，朝柜内方向钻入。

    深度方向：前后双排，分别距前/后边 first_hole_mm（默认 64mm）。
    偏心轮：深度方向用 center_offset_from_edge（默认 33.5mm），
    这是偏心轮圆心到板边缘的距离，跟预埋螺母的 64mm 不同。
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

        竖板：预埋螺母，沿高度方向(Z)和深度方向(Y)双排分布，
              打在 panel 的 inner_face 面上。
        横板：连接杆孔（端面，深度方向双排）+ 偏心轮孔（cam_face，深度方向双排），
              左右端各一组。
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
        z_positions = self._system_32_positions(panel, rules)

        nut_first = float(rules.get("first_hole_mm", 64))
        nut_last = float(rules.get("last_hole_mm", 64))
        cam_offset = float(wheel.get("center_offset_from_edge_mm", 33.5))

        if is_female:
            # ── 竖板：预埋螺母打在 inner_face ──
            # 深度方向双排：距前边 nut_first, 距后边 nut_last
            n_diam = float(nut.get("diameter_mm", 10))
            n_depth = float(nut.get("depth_mm", 11))
            inner = panel.inner_face or ""
            nut_dir = _opposite(inner)

            if inner == "+x":
                x_global = panel.pos_x + panel.size_x
                x_local = panel.size_x
            elif inner == "-x":
                x_global = panel.pos_x
                x_local = 0.0
            else:
                x_global = panel.pos_x + panel.size_x
                x_local = panel.size_x

            for z_local in z_positions:
                for y_local in [nut_first, panel.size_y - nut_last]:
                    result.append(HoleSpec(
                        hole_type="system_32_pre_nut", panel_label=panel.label,
                        x_global=x_global,
                        y_global=panel.pos_y + y_local,
                        z_global=panel.pos_z + z_local,
                        x_local=x_local,
                        y_local=y_local,
                        z_local=z_local,
                        diameter=n_diam, depth=n_depth, direction=nut_dir,
                        is_face_hole=True,
                        note="预埋螺母孔"))

        if is_male:
            # ── 横板：连接杆孔（端面）+ 偏心轮孔（cam_face）──
            w_diam = float(wheel.get("diameter_mm", 12))
            w_depth = float(wheel.get("hole_depth_mm", 13.5))
            r_diam = float(rod.get("diameter_mm", 8))
            r_depth = float(rod.get("insertion_depth_mm", 33))
            z_top = panel.pos_z + panel.size_z
            cam = panel.cam_face or ""

            if cam == "+z":
                cam_z = panel.pos_z
                cam_zl = 0.0
            elif cam == "-z":
                cam_z = panel.pos_z + panel.size_z
                cam_zl = panel.size_z
            else:
                cam_z = panel.pos_z + panel.size_z
                cam_zl = panel.size_z
                cam = "+z"

            # 深度方向：连接杆和偏心轮各有不同的 Y 偏移
            # 连接杆：前后各一（距板前边 nut_first, 距板后边 nut_last）
            # 偏心轮：前后各一（距板前边 cam_offset, 距板后边 cam_offset）
            rod_y_offsets = [nut_first, panel.size_y - nut_last]
            cam_y_offsets = [cam_offset, panel.size_y - cam_offset]

            for edge_x, rod_sign in [(0, "+x"), (panel.size_x, "-x")]:
                x_global = panel.pos_x + edge_x
                x_local = edge_x

                for y_offset in rod_y_offsets:
                    result.append(HoleSpec(
                        hole_type="system_32_male", panel_label=panel.label,
                        x_global=x_global,
                        y_global=panel.pos_y + y_offset,
                        z_global=z_top,
                        x_local=x_local, y_local=y_offset,
                        z_local=panel.size_z,
                        diameter=r_diam, depth=r_depth, direction=rod_sign,
                        is_face_hole=False,
                        note="连接杆孔"))

                for y_offset in cam_y_offsets:
                    result.append(HoleSpec(
                        hole_type="system_32_female", panel_label=panel.label,
                        x_global=x_global,
                        y_global=panel.pos_y + y_offset,
                        z_global=cam_z,
                        x_local=x_local, y_local=y_offset,
                        z_local=cam_zl,
                        diameter=w_diam, depth=w_depth, direction=cam,
                        is_face_hole=True,
                        note="偏心轮孔"))

        return result

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        """对所有板件生成孔位，并对竖板补充横板高度处缺失的预埋螺母。

        基础孔位由 ``generate_holes()`` 逐板生成。此方法利用全板件列表
        交叉参照：对每块横板的顶面 Z 坐标，检查竖板上是否已有对应的
        预埋螺母；若没有则补充（深度方向双排）。
        """
        assigned_panels = {p.label for p in panels}
        result: List[HoleSpec] = [
            hole
            for panel in panels
            for hole in self.generate_holes(panel)
        ]

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
        nut = spec.get("pre_embedded_nut", {})
        n_diam = float(nut.get("diameter_mm", 10))
        n_depth = float(nut.get("depth_mm", 11))

        # 深度方向偏移
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        nut_first = float(rules.get("first_hole_mm", 64))
        nut_last = float(rules.get("last_hole_mm", 64))

        # 收集每块竖板上已有的 (z, y_local) 组合（用于去重）
        existing: dict[str, set[tuple[float, float]]] = {}
        for hole in result:
            if hole.panel_label in {f.label for f in female_panels}:
                existing.setdefault(hole.panel_label, set()).add(
                    (round(hole.z_global, 3), round(hole.y_local, 3))
                )

        for male in male_panels:
            z_global = round(male.pos_z + male.size_z, 3)

            for female in female_panels:
                inner = female.inner_face or ""
                if inner == "-x":
                    x_global_nut = female.pos_x
                    x_local_nut = 0.0
                else:
                    x_global_nut = female.pos_x + female.size_x
                    x_local_nut = female.size_x
                nut_dir = _opposite(inner) if inner else "-x"

                if not (female.pos_z <= z_global <= female.pos_z + female.size_z):
                    continue

                z_local = z_global - female.pos_z
                for y_local in [nut_first, female.size_y - nut_last]:
                    key = (round(z_global, 3), round(y_local, 3))
                    if key in existing.get(female.label, set()):
                        continue
                    existing.setdefault(female.label, set()).add(key)
                    result.append(HoleSpec(
                        hole_type="system_32_pre_nut",
                        panel_label=female.label,
                        x_global=x_global_nut,
                        y_global=female.pos_y + y_local,
                        z_global=z_global,
                        x_local=x_local_nut,
                        y_local=y_local,
                        z_local=z_local,
                        diameter=n_diam,
                        depth=n_depth,
                        direction=nut_dir,
                        is_face_hole=True,
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
                         for p in matched["female"]) * 2,
            unit="套", brand=brand.get("name", "默认"), model=brand.get("model", "SJY-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        """生成三合一孔位的 cut_box 加工指令。"""
        ops: List[MachiningOperation] = []
        for hole in self.generate_holes(panel):
            d = hole.diameter
            ops.append(MachiningOperation(
                id=f"{hole.hole_type}_{panel.label}_{hole.z_local:.0f}_{hole.y_local:.0f}",
                operation_type="cut_box", target_panel=panel.label,
                size_x=hole.depth if hole.direction in ("+x", "-x") else d,
                size_y=hole.depth if hole.direction in ("+y", "-y") else d,
                size_z=hole.depth if hole.direction in ("+z", "-z") else d,
                pos_x=hole.x_global - d / 2, pos_y=hole.y_global - d / 2,
                pos_z=hole.z_global - d / 2,
                note=f"{self.name} {hole.note}"))
        return ops


def _opposite(axis: str) -> str:
    """反转带符号轴方向："+x"→"-x"，"-y"→"+y"。"""
    if not axis or axis[0] not in ("+", "-"):
        return "-x"
    return f"{'+' if axis[0] == '-' else '-'}{axis[1]}"
