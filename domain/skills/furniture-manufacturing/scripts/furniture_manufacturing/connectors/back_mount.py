"""背板安装连接件 — 内嵌背板四边三合一。

外盖(cover)与背拉条(groove)的螺钉连接属于组装现场工艺，
不在柜体加工范围内，不生成孔位与五金。
"""

from __future__ import annotations

from math import ceil
from typing import Any, Dict, List, Mapping

from furniture_manufacturing.connectors.base import (
    Connector,
    HoleSpec,
    cam_offset_from,
    rod_length_from,
)
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    PanelRecord,
)


class BackMountConnector(Connector):
    """背板安装连接件。

    仅 insert 模式生成四边三合一（背板偏心轮孔 + 连接杆通道 + 柜体预埋螺母孔）。
    cover/groove 的螺钉孔与五金属于组装现场工艺，不加工、不出 BOM。
    """

    name = "背板安装连接件"
    hole_type_for_json = "back_mount"
    catalog_entry = "three_in_one"
    rules_section = "back_mount_drilling"
    hole_legend = {
        "back_insert_cam": {"color": "#8E44AD", "label": "内嵌背板偏心轮孔", "glb_group": "内嵌背板偏心轮孔"},
        "back_insert_rod": {"color": "#9B59B6", "label": "内嵌背板连接杆孔", "glb_group": "内嵌背板连接杆孔"},
        "back_insert_nut": {"color": "#6C3483", "label": "内嵌背板预埋螺母孔", "glb_group": "内嵌背板预埋螺母孔"},
    }

    def match(self, panels: List[PanelRecord]) -> Dict[str, Any]:
        return {
            "mode": self._mode(panels),
            "back": next(
                (panel for panel in panels if panel.panel_type == "back"),
                None,
            ),
            "rails": [
                panel for panel in panels if panel.panel_type == "back_rail"
            ],
            "panels": panels,
        }

    def generate_holes(self, panel: PanelRecord) -> List[HoleSpec]:
        # Back mounting requires the mating panel geometry. The bulk method
        # below is the supported entry point used by emit_drilled_holes().
        return []

    def generate_holes_for_panels(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        mode = self._mode(panels)
        if mode == "insert":
            return self._insert_holes(panels)
        return []

    def boms(
        self,
        panels: List[PanelRecord],
        *,
        options: Mapping[str, Any] | None = None,
    ) -> List[HardwareRecord]:
        mode = self._mode(panels)
        if mode != "insert":
            return []
        holes = self.generate_holes_for_panels(panels)
        quantity = self._hole_count(holes, "back_insert_cam")
        if quantity <= 0:
            return []
        spec = self.catalog.get("three_in_one", {}).get("standard", {})
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        brand = self.resolve_brand(spec.get("brands", []), opts.get("brand"))
        rod_length = rod_length_from(spec.get("rod", {}), spec.get("nut", {}))
        return [
            HardwareRecord(
                name="三合一连接件（内嵌背板）",
                spec=f"偏心轮φ12+预埋螺母φ10×11+连接杆φ8×{rod_length:.0f}",
                quantity=quantity,
                unit="套",
                brand=brand.get("name", "默认"),
                model=brand.get("model", "SJY-01"),
                note="按四边连接点估算，投产前确认连接点数量",
                drilling=[
                    {"hole_type": "back_insert_cam", "quantity": quantity},
                    {"hole_type": "back_insert_rod", "quantity": quantity},
                    {
                        "hole_type": "back_insert_nut",
                        "quantity": quantity,
                    },
                ],
            )
        ]

    def validate(
        self,
        report: Any,
        panels: List[PanelRecord],
        hardware: List[HardwareRecord],
        drilled: Dict[str, Any],
    ) -> None:
        """内嵌背板（insert）专属校验：三件套孔（轮/杆/螺母）数量一致且匹配 BOM。"""
        mode = self._mode(panels)
        hole_types = [
            hole["hole_type"]
            for panel in drilled["panels"]
            for hole in panel["holes"]
        ]
        hardware_by_name = {item.name: item for item in hardware}
        contract = {
            "insert": (
                "三合一连接件（内嵌背板）",
                ("back_insert_cam", "back_insert_rod", "back_insert_nut"),
            ),
        }.get(mode)
        if contract is None:
            return
        hardware_name, required_hole_types = contract
        hardware_item = hardware_by_name.get(hardware_name)
        counts = {
            hole_type: hole_types.count(hole_type)
            for hole_type in required_hole_types
        }
        if hardware_item is None or hardware_item.quantity <= 0:
            report.add_error(
                "MISSING_BACK_MOUNT_HARDWARE",
                f"{mode} back strategy is missing {hardware_name}",
                "hardware",
            )
        if any(count <= 0 for count in counts.values()):
            report.add_error(
                "MISSING_BACK_MOUNT_HOLES",
                f"{mode} back strategy is missing matched hole records",
                "drilled_holes",
            )
        elif len(set(counts.values())) != 1:
            report.add_error(
                "BACK_MOUNT_HOLE_COUNT_MISMATCH",
                f"{mode} mating hole counts do not match",
                "drilled_holes",
            )
        elif (
            hardware_item is not None
            and hardware_item.quantity != next(iter(counts.values()))
        ):
            report.add_error(
                "BACK_MOUNT_HARDWARE_COUNT_MISMATCH",
                f"{hardware_name} quantity does not match its hole pattern",
                "hardware",
            )

    def machining_operations(
        self,
        panel: PanelRecord,
    ) -> List[MachiningOperation]:
        # Round holes are emitted through HoleSpec and the drilled-holes
        # artifact; BOMReport.operations remains the box-cut contract.
        return []

    def _insert_holes(self, panels: List[PanelRecord]) -> List[HoleSpec]:
        """内嵌背板：四边三合一成对孔。

        连接点在背板局部坐标定义（背板为装配锚点，局部为唯一真源），
        配合板按"同一世界点 − 板件原点"折算到各自局部坐标，
        世界坐标统一由各板的 to_global 派生。
        """
        by_label = {panel.label: panel for panel in panels}
        back = by_label.get("back_panel")
        if back is None:
            return []
        targets = {
            "left": by_label.get("left_side_panel"),
            "right": by_label.get("right_side_panel"),
            "top": by_label.get("top_panel"),
            "bottom": by_label.get("bottom_panel"),
        }
        rules = self.rules.get("back_mount_drilling", {}).get("insert", {})
        first = float(rules.get("first_hole_mm", 64))
        max_spacing = float(rules.get("max_spacing_mm", 400))
        three_in_one = self.catalog.get("three_in_one", {}).get("standard", {})
        wheel = three_in_one.get("cam", {})
        rod = three_in_one.get("rod", {})
        nut = three_in_one.get("nut", {})
        cam_diameter = float(wheel.get("diameter_mm", 12))
        cam_depth = float(wheel.get("hole_depth_mm", 13.5))
        cam_offset = cam_offset_from(rod, wheel)
        rod_diameter = float(rod.get("diameter_mm", 8))
        rod_depth = float(rod.get("insertion_depth_mm", 33))
        nut_diameter = float(nut.get("diameter_mm", 10))
        nut_depth = float(nut.get("depth_mm", 11))
        y_center_local = back.size_y / 2
        y_face_local = back.size_y
        result: List[HoleSpec] = []

        def add_connection(
            target: PanelRecord | None,
            cam_x_local: float,
            cam_z_local: float,
            rod_x_local: float,
            rod_z_local: float,
            rod_direction: str,
            target_direction: str,
            edge_name: str,
        ) -> None:
            if target is None:
                return
            result.append(
                self._hole(
                    back,
                    "back_insert_cam",
                    cam_x_local,
                    y_face_local,
                    cam_z_local,
                    cam_diameter,
                    cam_depth,
                    "-y",
                    f"内嵌背板{edge_name}偏心轮孔",
                    is_face_hole=True,
                )
            )
            result.append(
                self._hole(
                    back,
                    "back_insert_rod",
                    rod_x_local,
                    y_center_local,
                    rod_z_local,
                    rod_diameter,
                    rod_depth,
                    rod_direction,
                    f"内嵌背板{edge_name}连接杆通道",
                    is_face_hole=False,
                )
            )
            # 配合板预埋螺母孔必须与背板连接杆落在同一世界点：
            # 以背板局部点为中间量折算到目标板局部坐标，再 to_global。
            point = (
                back.pos_x + rod_x_local,
                back.pos_y + y_center_local,
                back.pos_z + rod_z_local,
            )
            result.append(
                self._hole(
                    target,
                    "back_insert_nut",
                    point[0] - target.pos_x,
                    point[1] - target.pos_y,
                    point[2] - target.pos_z,
                    nut_diameter,
                    nut_depth,
                    target_direction,
                    f"{target.name}与内嵌背板的预埋螺母孔",
                    is_face_hole=True,
                )
            )

        for z_local in self._spaced_positions(
            back.size_z,
            first,
            max_spacing,
        ):
            add_connection(
                targets["left"],
                cam_offset,
                z_local,
                0.0,
                z_local,
                "+x",
                "-x",
                "左边",
            )
            add_connection(
                targets["right"],
                back.size_x - cam_offset,
                z_local,
                back.size_x,
                z_local,
                "-x",
                "+x",
                "右边",
            )
        for x_local in self._spaced_positions(
            back.size_x,
            first,
            max_spacing,
        ):
            add_connection(
                targets["bottom"],
                x_local,
                cam_offset,
                x_local,
                0.0,
                "+z",
                "-z",
                "下边",
            )
            add_connection(
                targets["top"],
                x_local,
                back.size_z - cam_offset,
                x_local,
                back.size_z,
                "-z",
                "+z",
                "上边",
            )
        return result

    @staticmethod
    def _mode(panels: List[PanelRecord]) -> str:
        """从面板列表中提取统一的背板安装模式。"""
        modes = {panel.back_mount for panel in panels if panel.back_mount}
        return next(iter(modes)) if len(modes) == 1 else ""

    @staticmethod
    def _hole_count(holes: List[HoleSpec], hole_type: str) -> int:
        """统计某类孔的数量。"""
        return sum(hole.hole_type == hole_type for hole in holes)

    @staticmethod
    def _spaced_positions(
        length: float,
        edge_offset: float,
        max_spacing: float,
    ) -> List[float]:
        """沿指定长度均匀分布连接点，首末距边 edge_offset。"""
        if length <= 0:
            return []
        if length <= 2 * edge_offset:
            return [length / 2]
        usable = length - 2 * edge_offset
        intervals = max(1, ceil(usable / max(max_spacing, 1)))
        return [
            edge_offset + usable * index / intervals
            for index in range(intervals + 1)
        ]

    @staticmethod
    def _hole(
        panel: PanelRecord,
        hole_type: str,
        x_local: float,
        y_local: float,
        z_local: float,
        diameter: float,
        depth: float,
        direction: str,
        note: str,
        is_face_hole: bool = True,
    ) -> HoleSpec:
        """在指定板上生成孔位：局部坐标定义（唯一真源），世界由 to_global 派生。"""
        x_global, y_global, z_global = panel.to_global(
            x_local, y_local, z_local
        )
        return HoleSpec(
            hole_type=hole_type,
            panel_label=panel.label,
            x_global=x_global,
            y_global=y_global,
            z_global=z_global,
            x_local=x_local,
            y_local=y_local,
            z_local=z_local,
            diameter=diameter,
            depth=depth,
            direction=direction,
            is_face_hole=is_face_hole,
            note=note,
        )
