"""Three-in-one connector (eccentric wheel + connecting rod + pre-embedded nut)."""
from typing import Any, Dict, List
from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


class TrinityConnector(Connector):
    name = "三合一连接件"
    hole_type_for_json = "three_in_one"
    catalog_entry = "three_in_one"
    rules_section = "system_32_drilling"

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
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

        if is_female:
            w_diam = float(wheel.get("diameter_mm", 12))
            w_depth = float(wheel.get("hole_depth_mm", 13.5))
            center_offset = float(wheel.get("center_offset_from_edge_mm", 33.5))
            for z_local in positions:
                result.append(HoleSpec(
                    hole_type="system_32_female", panel_label=panel.label,
                    x_global=panel.pos_x + panel.size_x,
                    y_global=panel.pos_y + panel.size_y - center_offset,
                    z_global=panel.pos_z + z_local,
                    x_local=panel.size_x, y_local=panel.size_y - center_offset, z_local=z_local,
                    diameter=w_diam, depth=w_depth, direction="-x", note="偏心轮孔"))
            n_diam = float(nut.get("diameter_mm", 10))
            n_depth = float(nut.get("depth_mm", 11))
            for z_local in positions:
                result.append(HoleSpec(
                    hole_type="system_32_pre_nut", panel_label=panel.label,
                    x_global=panel.pos_x + panel.size_x,
                    y_global=panel.pos_y + panel.size_y - center_offset,
                    z_global=panel.pos_z + z_local,
                    x_local=panel.size_x, y_local=panel.size_y - center_offset, z_local=z_local,
                    diameter=n_diam, depth=n_depth, direction="-x", note="预埋螺母孔"))

        if is_male:
            r_diam = float(rod.get("diameter_mm", 8))
            r_depth = float(rod.get("insertion_depth_mm", 33))
            for x_local in positions:
                for edge_x, sign in [(0, "-x"), (panel.size_x, "+x")]:
                    result.append(HoleSpec(
                        hole_type="system_32_male", panel_label=panel.label,
                        x_global=panel.pos_x + edge_x,
                        y_global=panel.pos_y + panel.size_y - 33.5,
                        z_global=panel.pos_z + panel.size_z,
                        x_local=edge_x, y_local=panel.size_y - 33.5, z_local=panel.size_z,
                        diameter=r_diam, depth=r_depth, direction=sign, note="连接杆孔"))
        return result

    def _system_32_positions(self, panel: PanelRecord, rules: Dict[str, Any]) -> List[float]:
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
        matched = self.match(panels)
        brand = matched["brand"]
        return [HardwareRecord(
            name=self.name,
            spec="偏心轮φ12+预埋螺母φ10×11+连接杆φ8×33",
            quantity=sum(len(self._system_32_positions(p, matched["rules"]))
                         for p in matched["female"]),
            unit="套", brand=brand.get("name", "默认"), model=brand.get("model", "SJY-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
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
