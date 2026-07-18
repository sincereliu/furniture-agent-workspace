"""Hinge connector — cup hole drilling on door panels."""
from typing import Any, Dict, List
from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


class HingeConnector(Connector):
    name = "液压缓冲铰链"
    hole_type_for_json = "hinge"
    catalog_entry = "hinges"
    rules_section = "hinge_drilling"

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        doors = [p for p in panels if p.panel_type == "door"]
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        catalog = self.catalog.get(self.catalog_entry, {})
        return {"doors": doors, "rules": rules, "catalog": catalog}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        result: List[HoleSpec] = []
        if panel.panel_type != "door":
            return result
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        count, top_offset, bottom_offset = self._hinge_count(panel.size_z, rules)
        positions = self._distribute(panel.size_z, count, top_offset, bottom_offset)
        edge_offset = float(rules.get("position", {}).get("edge_offset_mm", 5))
        cup_params = self._cup_params(rules)

        # hinge side: use explicit field if set, otherwise infer from position
        hinge_side = panel.door_hinge_side
        if hinge_side == "left":
            x_local = edge_offset
        elif hinge_side == "right":
            x_local = panel.size_x - edge_offset
        elif panel.pos_x < panel.size_x:
            x_local = edge_offset  # fallback: left-positioned door → left hinge
        else:
            x_local = panel.size_x - edge_offset  # fallback: right-positioned door → right hinge

        for y_local in positions:
            result.append(HoleSpec(
                hole_type="hinge",
                panel_label=panel.label,
                x_global=panel.pos_x + x_local,
                y_global=panel.pos_y,
                z_global=panel.pos_z + y_local,
                x_local=x_local,
                y_local=0.0,
                z_local=y_local,
                diameter=float(cup_params.get("cup_diameter_mm", 35)),
                depth=float(cup_params.get("cup_depth_mm", 13)),
                direction="+y",
                note="从门板内侧面钻入的铰链杯孔"))

        return result

    def _hinge_count(self, door_h: float, rules: Dict[str, Any]) -> tuple:
        for entry in rules.get("count_by_door_height", []):
            if door_h <= entry["max_height_mm"]:
                return entry.get("count", 2), entry.get("top_offset_mm", 100), entry.get("bottom_offset_mm", 100)
        return 2, 100, 100

    def _distribute(self, total: float, count: int, top: float, bottom: float) -> List[float]:
        if count <= 1:
            return [total / 2]
        usable = total - top - bottom
        spacing = usable / (count - 1)
        return [top + i * spacing for i in range(count)]

    def _cup_params(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        default = {"cup_diameter_mm": 35, "cup_depth_mm": 13}
        return rules.get("cup_by_variant_group", {}).get("国内35mm杯全盖", default)

    def boms(self, panels: List[PanelRecord]) -> List[HardwareRecord]:
        doors = [p for p in panels if p.panel_type == "door"]
        catalog = self.catalog.get(self.catalog_entry, {})
        records: List[HardwareRecord] = []
        for door in doors:
            entry = self._pick_hinge_entry(catalog)
            brand = (entry.get("brands", [{}]) or [{}])[0] if entry else {"name": "默认", "model": "HJ-100-F"}
            count, _, _ = self._hinge_count(door.size_z, self.rules.get(self.rules_section, {}))
            records.append(HardwareRecord(
                name=self.name,
                spec=f"{brand['name']} {brand['model']} {entry.get('angle', 100)}°{entry.get('overlay', 'full')}" if entry else f"{brand['name']} {brand['model']}",
                quantity=count, brand=brand.get("name", "默认"), model=brand.get("model", ""),
                note=f"门板: {door.name}"))
        return records

    def _pick_hinge_entry(self, catalog: Dict[str, Any]) -> Dict[str, Any] | None:
        candidates = [v for v in catalog.values() if v.get("overlay") == "full" and v.get("angle") == 100]
        return candidates[0] if candidates else None

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        ops: List[MachiningOperation] = []
        for hole in self.generate_holes(panel):
            d = hole.diameter
            ops.append(MachiningOperation(
                id=f"hinge_{panel.label}_{hole.z_local:.0f}",
                operation_type="cut_box", target_panel=panel.label,
                size_x=d, size_y=hole.depth, size_z=d,
                pos_x=hole.x_global - d / 2, pos_y=hole.y_global - hole.depth,
                pos_z=hole.z_global - d / 2,
                note=f"铰链杯孔 φ{d:g}"))
        return ops
