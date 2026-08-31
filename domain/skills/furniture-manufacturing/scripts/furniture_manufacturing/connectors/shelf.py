"""活动层板连接件：二合一与隔板钉。

两者都服务 movable_shelf（活动层板），用于层板可拆卸 / 小范围调整：
- 二合一（TwoInOneConnector）：偏心轮装在层板底面、连接杆打在侧板，有固定作用；
- 隔板钉（ShelfPinConnector）：单钉打在侧板，单纯架住层板。

注意：movable_shelf 目前未在板件规划生成（shelf_count 生成 fixed_shelf），
两个连接件为休眠占位；下列几何定位（前后排、高度对齐、层板侧边投影）为
软件暂定，投产前确认。
"""

from typing import Any, Dict, List, Mapping

from furniture_manufacturing.connectors.base import Connector, HoleSpec, _opposite
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


def _shelf_positions(length: float) -> List[float]:
    """沿层板深度（前→后）分布连接点，返回相对前边的距离列表。"""
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


def _movable_shelves(panels: List[PanelRecord]) -> List[PanelRecord]:
    return [p for p in panels if p.panel_type == "movable_shelf"]


def _selected_shelves(panels: List[PanelRecord], connector_key: str) -> List[PanelRecord]:
    """只取选中该连接方式的活动层板（movable_shelf_connector == connector_key）。"""
    return [p for p in _movable_shelves(panels) if p.movable_shelf_connector == connector_key]


def _side_faces(panels: List[PanelRecord]) -> List[tuple]:
    """侧板内侧面定位：返回 (side, inner_face, x_local, 钻入方向)。"""
    out = []
    for side in [p for p in panels if p.panel_type == "side"]:
        inner = side.inner_face or ""
        x_local = side.size_x if inner in ("+x", "") else 0.0
        out.append((side, inner, x_local, _opposite(inner) if inner else "-x"))
    return out


class TwoInOneConnector(Connector):
    """二合一连接件：一套 = 偏心轮 + 连接杆（固定塑料件并入连接杆）。

    偏心轮孔打在层板底面（从下往上钻 +z），圆心距层板朝向侧板的侧边 edge_offset_mm；
    连接杆孔打在侧板内侧面，与偏心轮孔同排同位。
    """

    name = "二合一连接件"
    hole_type_for_json = "two_in_one"
    catalog_entry = "two_in_one"
    rules_section = None
    hole_legend = {
        "two_in_one_cam": {"color": "#27AE60", "label": "二合一偏心轮孔 12mm", "glb_group": "二合一偏心轮孔"},
        "two_in_one_rod": {"color": "#2E86C1", "label": "二合一连接杆孔 5mm", "glb_group": "二合一连接杆孔"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        return {"shelves": _movable_shelves(panels), "sides": [s for s, *_ in _side_faces(panels)]}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        return []

    def generate_holes_for_panels(self, panels: List[PanelRecord]) -> List[HoleSpec]:
        spec = self.catalog.get(self.catalog_entry, {}).get("standard", {})
        cam_spec = spec.get("cam", {})
        cam_hole = cam_spec.get("hole", {})
        rod_hole = spec.get("rod", {}).get("hole", {})
        cam_d = float(cam_hole.get("diameter_mm", 12))
        cam_depth = float(cam_hole.get("depth_mm", 13.5))
        cam_edge = float(cam_hole.get("edge_offset_mm", 4.5))
        rod_d = float(rod_hole.get("diameter_mm", 5))
        rod_depth = float(rod_hole.get("depth_mm", 10))
        rod_axis_offset = float(cam_spec.get("rod_axis_to_cam_face_mm", 9))

        result: List[HoleSpec] = []
        for shelf in _selected_shelves(panels, self.catalog_entry):
            for side, inner, side_x, rod_dir in _side_faces(panels):
                for depth in _shelf_positions(shelf.drill_length):
                    y_local = side.size_y - depth
                    # 连接杆孔：侧板内侧面水平钻入；杆轴 = 层板底面 + rod_axis_to_cam_face_mm
                    z_local = (shelf.pos_z + rod_axis_offset) - side.pos_z
                    sx, sy, sz = side.to_global(side_x, y_local, z_local)
                    result.append(HoleSpec(
                        hole_type="two_in_one_rod", panel_label=side.label,
                        x_global=sx, y_global=sy, z_global=sz,
                        x_local=side_x, y_local=y_local, z_local=z_local,
                        diameter=rod_d, depth=rod_depth, direction=rod_dir,
                        is_face_hole=True, note=f"二合一连接杆孔({shelf.name})"))

                    # 偏心轮孔：层板底面从下往上钻；圆心距朝向侧板的侧边 cam_edge（待确认）
                    cam_x = cam_edge if inner in ("+x", "") else shelf.size_x - cam_edge
                    cam_y = depth
                    cam_z = 0.0
                    cx, cy, cz = shelf.to_global(cam_x, cam_y, cam_z)
                    result.append(HoleSpec(
                        hole_type="two_in_one_cam", panel_label=shelf.label,
                        x_global=cx, y_global=cy, z_global=cz,
                        x_local=cam_x, y_local=cam_y, z_local=cam_z,
                        diameter=cam_d, depth=cam_depth, direction="+z",
                        is_face_hole=True, note=f"二合一偏心轮孔({shelf.name})"))
        return result

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        shelves = _selected_shelves(panels, self.catalog_entry)
        if not shelves:
            return []
        spec = self.catalog.get(self.catalog_entry, {}).get("standard", {})
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        brand = self.resolve_brand(spec.get("brands", []), opts.get("brand"))
        total = sum(len(_shelf_positions(p.drill_length)) * 2 for p in shelves)
        return [HardwareRecord(
            name=self.name,
            spec="偏心轮+连接杆（实物规格待确认）",
            quantity=total, unit="套",
            brand=brand.get("name", "默认"), model=brand.get("model", "EYJ-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        return []


class ShelfPinConnector(Connector):
    """隔板钉：单钉打在侧板，单纯架住层板。

    钉孔打在侧板内侧面（水平钻入），钉孔中心比层板底面低 shelf_bottom_offset_mm
    （= 钉半径 2.5mm），层板架在钉上。
    """

    name = "隔板钉"
    hole_type_for_json = "shelf_pin"
    catalog_entry = "shelf_pin"
    rules_section = None
    hole_legend = {
        "shelf_pin": {"color": "#00A86B", "label": "隔板钉孔 5mm", "glb_group": "隔板钉孔"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        return {"shelves": _movable_shelves(panels), "sides": [s for s, *_ in _side_faces(panels)]}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        return []

    def generate_holes_for_panels(self, panels: List[PanelRecord]) -> List[HoleSpec]:
        spec = self.catalog.get(self.catalog_entry, {}).get("standard", {})
        pin = spec.get("pin", {})
        pin_hole = pin.get("hole", {})
        pin_d = float(pin_hole.get("diameter_mm", 5))
        pin_depth = float(pin_hole.get("depth_mm", 9))
        bottom_offset = float(pin.get("shelf_bottom_offset_mm", 2.5))

        result: List[HoleSpec] = []
        for shelf in _selected_shelves(panels, self.catalog_entry):
            for side, _inner, side_x, drill_dir in _side_faces(panels):
                # 钉孔中心 = 层板底面 - bottom_offset（层板架在钉上）
                z_local = (shelf.pos_z - bottom_offset) - side.pos_z
                for depth in _shelf_positions(shelf.drill_length):
                    y_local = side.size_y - depth
                    sx, sy, sz = side.to_global(side_x, y_local, z_local)
                    result.append(HoleSpec(
                        hole_type="shelf_pin", panel_label=side.label,
                        x_global=sx, y_global=sy, z_global=sz,
                        x_local=side_x, y_local=y_local, z_local=z_local,
                        diameter=pin_d, depth=pin_depth, direction=drill_dir,
                        is_face_hole=True, note=f"隔板钉孔({shelf.name})"))
        return result

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        shelves = _selected_shelves(panels, self.catalog_entry)
        if not shelves:
            return []
        spec = self.catalog.get(self.catalog_entry, {}).get("standard", {})
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        brand = self.resolve_brand(spec.get("brands", []), opts.get("brand"))
        total = sum(len(_shelf_positions(p.drill_length)) * 2 for p in shelves)
        return [HardwareRecord(
            name=self.name,
            spec="钉（实物规格待确认）",
            quantity=total, unit="个",
            brand=brand.get("name", "默认"), model=brand.get("model", "GBD-01"))]

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        return []
