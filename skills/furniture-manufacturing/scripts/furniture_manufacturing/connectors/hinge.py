"""铰链连接件 — 门板杯孔打孔。

铰链杯孔从门板内侧面钻入。内侧面方向由 panel.inner_face 提供，
不再硬编码 "+y"。
"""

from typing import Any, Dict, List
from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import HardwareRecord, MachiningOperation, PanelRecord


class HingeConnector(Connector):
    """铰链连接件：在门板内侧面钻铰链杯孔。"""

    name = "液压缓冲铰链"
    hole_type_for_json = "hinge"
    catalog_entry = "hinges"
    rules_section = "hinge_drilling"

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        """匹配所有门板及相关规则。"""
        doors = [p for p in panels if p.panel_type == "door"]
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        catalog = self.catalog.get(self.catalog_entry, {})
        return {"doors": doors, "rules": rules, "catalog": catalog}

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        """在一块门板上生成铰链杯孔。

        杯孔沿门板高度方向分布，从 inner_face 方向钻入。
        """
        result: List[HoleSpec] = []
        if panel.panel_type != "door":
            return result
        rules = self.rules.get(self.rules_section, {}) if self.rules_section else {}
        count, top_offset, bottom_offset = self._hinge_count(panel.size_z, rules)
        positions = self._distribute(panel.size_z, count, top_offset, bottom_offset)
        edge_offset = float(rules.get("position", {}).get("edge_offset_mm", 5))
        cup_params = self._cup_params(rules)
        inner = panel.inner_face or "+y"  # default for backward compat

        # 铰链侧：优先使用显式字段，否则根据 X 位置推断
        hinge_side = panel.door_hinge_side
        if hinge_side == "left":
            x_local = edge_offset
        elif hinge_side == "right":
            x_local = panel.size_x - edge_offset
        elif panel.pos_x < panel.size_x:
            x_local = edge_offset  # 兜底：X 位置靠左 → 左铰链
        else:
            x_local = panel.size_x - edge_offset  # 兜底：X 位置靠右 → 右铰链

        # Drill direction = inner_face (cup drilled from inner face into the door)
        cup_dir = inner

        for y_local in positions:
            hole = self._make_hole(
                panel=panel,
                x_local=x_local,
                y_local=0.0,
                z_local=y_local,
                diameter=float(cup_params.get("cup_diameter_mm", 35)),
                depth=float(cup_params.get("cup_depth_mm", 13)),
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
        """Create a HoleSpec with correct global coordinates for the inner face."""
        inner = panel.inner_face or "+y"

        # Determine which axis is the inner face axis
        # inner_face is one of: "+x", "-x", "+y", "-y", "+z", "-z"
        if inner[1] == "x":
            if inner[0] == "+":
                x_global = panel.pos_x + panel.size_x  # inner at right face
            else:
                x_global = panel.pos_x                  # inner at left face
            y_global = panel.pos_y + y_local
            z_global = panel.pos_z + z_local
            hole_x_local = panel.size_x if inner[0] == "+" else 0.0
            hole_y_local = y_local
            hole_z_local = z_local
        elif inner[1] == "y":
            # Door panels: inner_face = "-y" (inner face is the front face)
            # or "+y" for back panels
            x_global = panel.pos_x + x_local
            if inner[0] == "+":
                y_global = panel.pos_y + panel.size_y  # inner at front
                hole_y_local = panel.size_y
            else:
                y_global = panel.pos_y                  # inner at back
                hole_y_local = 0.0
            z_global = panel.pos_z + z_local
            hole_x_local = x_local
            hole_z_local = z_local
        else:
            # "+z" or "-z"
            x_global = panel.pos_x + x_local
            y_global = panel.pos_y + y_local
            if inner[0] == "+":
                z_global = panel.pos_z + panel.size_z
                hole_z_local = panel.size_z
            else:
                z_global = panel.pos_z
                hole_z_local = 0.0
            hole_x_local = x_local
            hole_y_local = y_local

        return HoleSpec(
            hole_type="hinge",
            panel_label=panel.label,
            x_global=x_global,
            y_global=y_global,
            z_global=z_global,
            x_local=hole_x_local,
            y_local=hole_y_local,
            z_local=hole_z_local,
            diameter=diameter,
            depth=depth,
            direction=direction,
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

    def _cup_params(self, rules: Dict[str, Any]) -> Dict[str, Any]:
        """获取杯孔参数（默认国内 35mm 全盖）。"""
        default = {"cup_diameter_mm": 35, "cup_depth_mm": 13}
        return rules.get("cup_by_variant_group", {}).get("国内35mm杯全盖", default)

    def boms(self, panels: List[PanelRecord]) -> List[HardwareRecord]:
        """生成铰链 BOM 清单。"""
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
        """从目录中选择全盖 100° 铰链。"""
        candidates = [v for v in catalog.values() if v.get("overlay") == "full" and v.get("angle") == 100]
        return candidates[0] if candidates else None

    def machining_operations(self, panel: PanelRecord) -> List[MachiningOperation]:
        """生成铰链杯孔的 cut_box 加工指令。

        根据打孔方向将 cut_box 放置在孔位入口处，使其沿钻入方向
        展开，而不是跑到板件后方。
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
