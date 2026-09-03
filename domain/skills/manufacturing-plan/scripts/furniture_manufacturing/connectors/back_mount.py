"""背板安装连接件 — 内嵌背板四边三合一。

内嵌背板(insert)使用与柜体相同的三合一五金（偏心轮+连接杆+预埋螺母），
孔类型统一为 `three_in_one_cam/rod/nut`，靠 `connection_id` 与柜体三合一区分。
外盖(cover)与背拉条(groove)的螺钉连接属于组装现场工艺，不在柜体加工范围内，
不生成孔位与五金（cover 改三合一留待以后确定，见 runtime-map）。
"""

from __future__ import annotations

from math import ceil
from typing import Any, Dict, List, Mapping

from furniture_manufacturing.connectors.base import (
    Connector,
    HoleSpec,
    make_connection_id,
)
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    PanelRecord,
)


class BackMountConnector(Connector):
    """背板安装连接件。

    仅 insert 模式生成四边三合一（背板偏心轮孔 + 连接杆通道 + 柜体预埋螺母孔），
    孔类型与柜体三合一统一为 three_in_one_*，用 connection_id 区分来源。
    cover/groove 的螺钉孔与五金属于组装现场工艺，不加工、不出 BOM。
    """

    name = "背板安装连接件"
    hole_type_for_json = "back_mount"
    catalog_entry = "three_in_one"
    rules_section = "back_mount_drilling"
    # 孔类型与柜体三合一统一：图例由 TrinityConnector 的 three_in_one_* 提供
    hole_legend: Dict[str, Dict[str, str]] = {}

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
        quantity = self._connection_count(holes)
        if quantity <= 0:
            return []
        spec = self.catalog.get("three_in_one", {}).get("standard", {})
        opts = (options or {}).get(self.catalog_entry, {})
        opts = dict(opts) if isinstance(opts, Mapping) else {}
        brand = self.resolve_brand(spec.get("brands", []), opts.get("brand"))
        return [
            HardwareRecord(
                name="三合一连接件（背板）",
                spec="偏心轮+连接杆+预埋螺母（实物规格待确认）",
                quantity=quantity,
                unit="套",
                brand=brand.get("name", "默认"),
                model=brand.get("model", "SJY-01"),
                note="按四边连接点计（孔即真源），投产前确认连接点数量",
                drilling=[
                    {"hole_type": "three_in_one_cam", "quantity": quantity},
                    {"hole_type": "three_in_one_rod", "quantity": quantity},
                    {"hole_type": "three_in_one_nut", "quantity": quantity},
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
        """背板三合一（insert）专属校验：按连接点对齐，每个连接点 1 轮 + 1 杆 + 1 螺母。"""
        mode = self._mode(panels)
        if mode != "insert":
            return
        holes = self.generate_holes_for_panels(panels)
        by_conn: Dict[str, Dict[str, int]] = {}
        for hole in holes:
            if not hole.connection_id:
                continue
            entry = by_conn.setdefault(
                hole.connection_id, {"cam": 0, "rod": 0, "nut": 0}
            )
            key = {
                "three_in_one_cam": "cam",
                "three_in_one_rod": "rod",
                "three_in_one_nut": "nut",
            }.get(hole.hole_type)
            if key:
                entry[key] += 1
        hardware_by_name = {item.name: item for item in hardware}
        hardware_name = "三合一连接件（背板）"
        hardware_item = hardware_by_name.get(hardware_name)
        if hardware_item is None or hardware_item.quantity != len(by_conn):
            report.add_error(
                "BACK_MOUNT_HARDWARE_COUNT_MISMATCH",
                f"背板三合一数量与连接点数不一致（期望 {len(by_conn)} 套）",
                "hardware",
            )
        for conn_id, counts in sorted(by_conn.items()):
            if not (counts["cam"] == counts["rod"] == counts["nut"] == 1):
                report.add_error(
                    "BACK_MOUNT_HOLE_COUNT_MISMATCH",
                    f"背板连接点 {conn_id} 三件套不完整："
                    f"轮={counts['cam']} 杆={counts['rod']} 螺母={counts['nut']}（期望各 1）",
                    "drilled_holes",
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
        cam_spec = three_in_one.get("cam", {})
        rod_spec = three_in_one.get("rod", {})
        nut_spec = three_in_one.get("nut", {})
        cam_diameter = float(cam_spec.get("hole", {}).get("diameter_mm", 12))
        cam_depth = float(cam_spec.get("hole", {}).get("depth_mm", 13.5))
        cam_offset = float(cam_spec.get("hole", {}).get("edge_offset_mm", 33.5))
        rod_diameter = float(rod_spec.get("hole", {}).get("diameter_mm", 8))
        rod_depth = float(rod_spec.get("hole", {}).get("depth_mm", 33))
        nut_diameter = float(nut_spec.get("hole", {}).get("diameter_mm", 10))
        nut_depth = float(nut_spec.get("hole", {}).get("depth_mm", 11))
        y_center_local = back.size_y / 2
        y_face_local = back.size_y
        result: List[HoleSpec] = []

        def add_connection(
            row_index: int,
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
            conn_id = make_connection_id(target.label, back.label, row_index)
            result.append(
                self._hole(
                    back,
                    "three_in_one_cam",
                    cam_x_local,
                    y_face_local,
                    cam_z_local,
                    cam_diameter,
                    cam_depth,
                    "-y",
                    f"内嵌背板{edge_name}偏心轮孔",
                    is_face_hole=True,
                    connection_id=conn_id,
                )
            )
            result.append(
                self._hole(
                    back,
                    "three_in_one_rod",
                    rod_x_local,
                    y_center_local,
                    rod_z_local,
                    rod_diameter,
                    rod_depth,
                    rod_direction,
                    f"内嵌背板{edge_name}连接杆通道",
                    is_face_hole=False,
                    connection_id=conn_id,
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
                    "three_in_one_nut",
                    point[0] - target.pos_x,
                    point[1] - target.pos_y,
                    point[2] - target.pos_z,
                    nut_diameter,
                    nut_depth,
                    target_direction,
                    f"{target.name}与内嵌背板的预埋螺母孔",
                    is_face_hole=True,
                    connection_id=conn_id,
                )
            )

        for row_index, z_local in enumerate(
            self._spaced_positions(back.size_z, first, max_spacing)
        ):
            add_connection(
                row_index,
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
                row_index,
                targets["right"],
                back.size_x - cam_offset,
                z_local,
                back.size_x,
                z_local,
                "-x",
                "+x",
                "右边",
            )
        for row_index, x_local in enumerate(
            self._spaced_positions(back.size_x, first, max_spacing)
        ):
            add_connection(
                row_index,
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
                row_index,
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
    def _connection_count(holes: List[HoleSpec]) -> int:
        """统计不同连接点(connection_id)的数量（一套三合一 = 一个连接点）。"""
        return len({hole.connection_id for hole in holes if hole.connection_id})

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
        connection_id: str = "",
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
            connection_id=connection_id,
        )
