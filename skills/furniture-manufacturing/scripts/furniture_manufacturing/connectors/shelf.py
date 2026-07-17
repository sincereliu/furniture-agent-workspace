"""Shelf connector -- pin holes on side panels for movable shelves."""
from typing import Any, Dict, List
from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


class ShelfConnector(Connector):
    name = "层板托连接件"
    hole_type_for_json = "shelf_connector"
    catalog_entry = "shelf_connectors"
    rules_section = None

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        movable = [p for p in panels if p.panel_type == "movable_shelf"]
        sides = [p for p in panels if p.panel_type == "side"]
        return {"shelves": movable, "sides": sides}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        result: List[HoleSpec] = []
        if panel.panel_type != "movable_shelf":
            return result
        positions = self._shelf_positions(panel.drill_length)
        y_local = panel.size_y - 32
        for x_local in positions:
            result.append(HoleSpec(
                hole_type="shelf_connector", panel_label=panel.label,
                x_global=panel.pos_x + x_local,
                y_global=panel.pos_y + y_local,
                z_global=panel.pos_z + panel.size_z / 2,
                x_local=x_local, y_local=y_local, z_local=panel.size_z / 2,
                diameter=10.0, depth=12.0, direction="-x", note="层板托孔"))
        return result

    def _shelf_positions(self, length: float) -> List[float]:
        if length <= 192:
            return [32.0, length - 32.0]
        if length <= 550:
            return [64.0, length - 64.0]
        holes = [64.0, length / 2, length - 64.0]
        if length > 1100:
            usable = length - 128
            extra = int((length - 1100) / 550) + 1
            spacing = usable / (extra + 1)
            for i in range(1, extra + 1):
                holes.append(64.0 + i * spacing)
        return sorted(set(holes))

    def boms(self, panels: List[PanelRecord]) -> List[HardwareRecord]:
        entry = self.catalog.get(self.catalog_entry, {}).get("二合一", {})
        brand = (entry.get("brands", [{}]) or [{}])[0]
        total = sum(len(self._shelf_positions(p.drill_length)) * 2
                    for p in panels if p.panel_type == "movable_shelf")
        return [HardwareRecord(
            name="二合一连接件",
            spec=f"{brand['name']} {brand['model']}",
            quantity=total, unit="套",
            brand=brand.get("name", "默认"), model=brand.get("model", "EYJ-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        ops: List[MachiningOperation] = []
        for hole in self.generate_holes(panel):
            ops.append(MachiningOperation(
                id=f"shelf_hole_{panel.label}_{hole.x_local:.0f}",
                operation_type="cut_box", target_panel=panel.label,
                size_x=10.0, size_y=12.0, size_z=10.0,
                pos_x=hole.x_global - 5.0, pos_y=hole.y_global,
                pos_z=hole.z_global - 5.0,
                note="层板托孔 φ10"))
        return ops
