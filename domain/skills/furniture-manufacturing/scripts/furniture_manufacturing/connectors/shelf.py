"""Shelf connector — 活动层板连接件。

层板托孔打在**侧板内侧面**，这是受力支撑点。
层板本身只可选出小定位孔（暂未实现）。
减尺间隙由层板托支撑面自动补偿。

对于当前代码中 movable_shelf 未实际生成的情况，此连接件
暂时留在活动层板面板规划加入后再启用全量逻辑。
"""

from typing import Any, Dict, List, Mapping
from furniture_manufacturing.connectors.base import Connector, HoleSpec, _opposite
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


class ShelfConnector(Connector):
    name = "层板托连接件"
    hole_type_for_json = "shelf_connector"
    catalog_entry = "shelf_connectors"
    rules_section = None
    hole_legend = {
        "shelf_connector": {"color": "#00A86B", "label": "层板托孔", "glb_group": "层板孔位"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        movable = [p for p in panels if p.panel_type == "movable_shelf"]
        sides = [p for p in panels if p.panel_type == "side"]
        return {"shelves": movable, "sides": sides}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        """No single-panel holes — connector needs both shelf and side panels."""
        return []

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        """Generate shelf-connector holes on side panel inner faces.

        For each movable shelf, put paired holes on the left and right side
        panels at the shelf's Z position.
        """
        result: List[HoleSpec] = []
        sides = [p for p in panels if p.panel_type == "side"]
        shelves = [p for p in panels if p.panel_type == "movable_shelf"]
        if not sides or not shelves:
            return result

        for shelf in shelves:
            x_positions = self._shelf_positions(shelf.drill_length)
            for side in sides:
                inner = side.inner_face or ""
                # Determine the X position on the side panel's inner face
                # and the drilling direction (into the side panel from its inner face)
                nut_dir = _opposite(inner) if inner else "-x"

                # Hole's local Z on the side panel = shelf's Z position relative to
                # side panel's origin.  For standard vertical cabinets, shelf Z
                # is roughly at mid-height of the shelf.
                # We drill pairs at the front and back of the shelf depth.
                # 孔位先在面板局部坐标定义（局部为唯一真源），世界由 to_global 派生。
                shelf_z_centers = [shelf.pos_z + shelf.size_z / 2 - side.pos_z]

                for z_local_on_side in shelf_z_centers:
                    # Y position: near the front edge of the side panel
                    y_local_on_side = side.size_y - 32  # 32mm from front

                    for x_local_shelf in x_positions:
                        # Map shelf-local X to side-panel-local Y or X
                        # depending on inner_face direction
                        # Standard cabinet: left side inner_face="+x", right side inner_face="-x"
                        # We map the shelf's X position to the side panel's Y (depth) position
                        y_local_on_side = side.size_y - x_local_shelf

                        if inner == "+x":
                            # left side: inner face = right face = +size_x
                            x_local = side.size_x
                        elif inner == "-x":
                            # right side: inner face = left face = 0
                            x_local = 0.0
                        else:
                            # fallback for legacy
                            x_local = side.size_x

                        x_global, y_global, z_global = side.to_global(
                            x_local, y_local_on_side, z_local_on_side
                        )

                        result.append(HoleSpec(
                            hole_type="shelf_connector",
                            panel_label=side.label,
                            x_global=x_global,
                            y_global=y_global,
                            z_global=z_global,
                            x_local=x_local,
                            y_local=y_local_on_side,
                            z_local=z_local_on_side,
                            diameter=10.0, depth=12.0,
                            direction=nut_dir,
                            is_face_hole=True,
                            note=f"层板托孔(对应{shelf.name})",
                        ))
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

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        entry = self.catalog.get(self.catalog_entry, {}).get("二合一", {})
        brand = self.resolve_brand(entry.get("brands", []), opts.get("brand"))
        shelves = [p for p in panels if p.panel_type == "movable_shelf"]
        total = sum(len(self._shelf_positions(p.drill_length)) * 2
                    for p in shelves)
        return [HardwareRecord(
            name="二合一连接件",
            spec=f"{brand['name']} {brand['model']}",
            quantity=total, unit="套",
            brand=brand.get("name", "默认"), model=brand.get("model", "EYJ-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        # Shelf connector holes are round holes on side panels —
        # no box-cut operations needed.  The feature tree handles them
        # through HoleSpec from generate_holes_for_panels().
        return []


