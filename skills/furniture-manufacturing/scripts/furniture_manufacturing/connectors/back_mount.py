"""Assembly-aware connectors for the three cabinet back mounting modes."""

from __future__ import annotations

from math import ceil
from typing import Any, Dict, List

from furniture_manufacturing.connectors.base import Connector, HoleSpec
from furniture_manufacturing.manufacturing_models import (
    HardwareRecord,
    MachiningOperation,
    PanelRecord,
)


class BackMountConnector(Connector):
    """Generate matched holes and hardware for back panels and back rails.

    Inserted backs use three-in-one fittings, cover backs use perimeter
    countersunk screws, and groove-mode back rails use end screws. The latter
    two are repository defaults and remain subject to factory confirmation.
    """

    name = "背板安装连接件"
    hole_type_for_json = "back_mount"
    catalog_entry = "back_fasteners"
    rules_section = "back_mount_drilling"

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
        if mode == "cover":
            return self._cover_holes(panels)
        if mode == "groove":
            return self._back_rail_holes(panels)
        return []

    def boms(self, panels: List[PanelRecord]) -> List[HardwareRecord]:
        mode = self._mode(panels)
        holes = self.generate_holes_for_panels(panels)
        if mode == "insert":
            quantity = self._hole_count(holes, "back_insert_cam")
            if quantity <= 0:
                return []
            spec = self.catalog.get("three_in_one", {}).get("标准", {})
            brand = (spec.get("brands", [{}]) or [{}])[0]
            return [
                HardwareRecord(
                    name="三合一连接件（内嵌背板）",
                    spec="偏心轮φ12+预埋螺母φ10×11+连接杆φ8×33",
                    quantity=quantity,
                    unit="套",
                    brand=brand.get("name", "默认"),
                    model=brand.get("model", "SJY-01"),
                    note="按四边连接点估算，投产前确认连接点数量",
                    drilling=[
                        {"hole_type": "back_insert_cam", "quantity": quantity},
                        {"hole_type": "back_insert_rod", "quantity": quantity},
                        {
                            "hole_type": "back_insert_pre_nut",
                            "quantity": quantity,
                        },
                    ],
                )
            ]
        if mode == "cover":
            quantity = self._hole_count(holes, "cover_back_clearance")
            if quantity <= 0:
                return []
            item = self.catalog.get("back_fasteners", {}).get(
                "cover_back_screw",
                {},
            )
            brand = (item.get("brands", [{}]) or [{}])[0]
            diameter = float(item.get("diameter_mm", 4))
            length = float(item.get("length_mm", 30))
            return [
                HardwareRecord(
                    name="沉头木螺钉（外盖背板）",
                    spec=f"{diameter:g}×{length:g}mm",
                    quantity=quantity,
                    unit="颗",
                    brand=brand.get("name", "默认"),
                    model=brand.get("model", "GB-COVER-4030"),
                    note="软件暂定周边螺钉方案，投产前确认规格与间距",
                    drilling=[
                        {
                            "hole_type": "cover_back_clearance",
                            "quantity": quantity,
                        },
                        {
                            "hole_type": "cover_back_pilot",
                            "quantity": quantity,
                        },
                    ],
                )
            ]
        if mode == "groove":
            quantity = self._hole_count(
                holes,
                "back_rail_side_clearance",
            )
            if quantity <= 0:
                return []
            item = self.catalog.get("back_fasteners", {}).get(
                "back_rail_screw",
                {},
            )
            brand = (item.get("brands", [{}]) or [{}])[0]
            diameter = float(item.get("diameter_mm", 4))
            length = float(item.get("length_mm", 40))
            return [
                HardwareRecord(
                    name="沉头木螺钉（背拉条）",
                    spec=f"{diameter:g}×{length:g}mm",
                    quantity=quantity,
                    unit="颗",
                    brand=brand.get("name", "默认"),
                    model=brand.get("model", "GB-RAIL-4040"),
                    note="软件暂定端部螺钉方案，投产前确认规格与孔位",
                    drilling=[
                        {
                            "hole_type": "back_rail_side_clearance",
                            "quantity": quantity,
                        },
                        {
                            "hole_type": "back_rail_pilot",
                            "quantity": quantity,
                        },
                    ],
                )
            ]
        return []

    def machining_operations(
        self,
        panel: PanelRecord,
    ) -> List[MachiningOperation]:
        # Round holes are emitted through HoleSpec and the drilled-holes
        # artifact; BOMReport.operations remains the box-cut contract.
        return []

    def _insert_holes(self, panels: List[PanelRecord]) -> List[HoleSpec]:
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
        three_in_one = self.catalog.get("three_in_one", {}).get("标准", {})
        wheel = three_in_one.get("eccentric_wheel", {})
        rod = three_in_one.get("connecting_rod", {})
        nut = three_in_one.get("pre_embedded_nut", {})
        cam_diameter = float(wheel.get("diameter_mm", 12))
        cam_depth = float(wheel.get("hole_depth_mm", 13.5))
        cam_offset = float(
            wheel.get("center_offset_from_edge_mm", 33.5)
        )
        rod_diameter = float(rod.get("diameter_mm", 8))
        rod_depth = float(rod.get("insertion_depth_mm", 33))
        nut_diameter = float(nut.get("diameter_mm", 10))
        nut_depth = float(nut.get("depth_mm", 11))
        y_center = back.pos_y + back.size_y / 2
        y_face = back.pos_y + back.size_y
        result: List[HoleSpec] = []

        def add_connection(
            target: PanelRecord | None,
            cam_x: float,
            cam_z: float,
            rod_x: float,
            rod_z: float,
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
                    cam_x,
                    y_face,
                    cam_z,
                    cam_diameter,
                    cam_depth,
                    "-y",
                    f"内嵌背板{edge_name}偏心轮孔",
                )
            )
            result.append(
                self._hole(
                    back,
                    "back_insert_rod",
                    rod_x,
                    y_center,
                    rod_z,
                    rod_diameter,
                    rod_depth,
                    rod_direction,
                    f"内嵌背板{edge_name}连接杆通道",
                )
            )
            result.append(
                self._hole(
                    target,
                    "back_insert_pre_nut",
                    rod_x,
                    y_center,
                    rod_z,
                    nut_diameter,
                    nut_depth,
                    target_direction,
                    f"{target.name}与内嵌背板的预埋螺母孔",
                )
            )

        for z_local in self._spaced_positions(
            back.size_z,
            first,
            max_spacing,
        ):
            z_global = back.pos_z + z_local
            add_connection(
                targets["left"],
                back.pos_x + cam_offset,
                z_global,
                back.pos_x,
                z_global,
                "+x",
                "-x",
                "左边",
            )
            add_connection(
                targets["right"],
                back.pos_x + back.size_x - cam_offset,
                z_global,
                back.pos_x + back.size_x,
                z_global,
                "-x",
                "+x",
                "右边",
            )
        for x_local in self._spaced_positions(
            back.size_x,
            first,
            max_spacing,
        ):
            x_global = back.pos_x + x_local
            add_connection(
                targets["bottom"],
                x_global,
                back.pos_z + cam_offset,
                x_global,
                back.pos_z,
                "+z",
                "-z",
                "下边",
            )
            add_connection(
                targets["top"],
                x_global,
                back.pos_z + back.size_z - cam_offset,
                x_global,
                back.pos_z + back.size_z,
                "-z",
                "+z",
                "上边",
            )
        return result

    def _cover_holes(self, panels: List[PanelRecord]) -> List[HoleSpec]:
        by_label = {panel.label: panel for panel in panels}
        back = by_label.get("back_panel")
        if back is None:
            return []
        rules = self.rules.get("back_mount_drilling", {}).get("cover", {})
        first = float(rules.get("first_hole_mm", 50))
        max_spacing = float(rules.get("max_spacing_mm", 200))
        clearance_diameter = float(
            rules.get("clearance_hole_diameter_mm", 4.5)
        )
        pilot_diameter = float(rules.get("pilot_hole_diameter_mm", 3))
        pilot_depth = float(rules.get("pilot_depth_mm", 20))
        targets = [
            by_label.get("left_side_panel"),
            by_label.get("right_side_panel"),
            by_label.get("top_panel"),
            by_label.get("bottom_panel"),
        ]
        result: List[HoleSpec] = []

        def add_screw(
            target: PanelRecord | None,
            x_global: float,
            z_global: float,
        ) -> None:
            if target is None:
                return
            result.append(
                self._hole(
                    back,
                    "cover_back_clearance",
                    x_global,
                    back.pos_y,
                    z_global,
                    clearance_diameter,
                    back.size_y,
                    "+y",
                    f"外盖背板至{target.name}的螺钉通孔",
                )
            )
            result.append(
                self._hole(
                    target,
                    "cover_back_pilot",
                    x_global,
                    target.pos_y,
                    z_global,
                    pilot_diameter,
                    min(pilot_depth, target.size_y),
                    "+y",
                    f"{target.name}外盖背板螺钉预孔",
                )
            )

        for target in targets[:2]:
            if target is None:
                continue
            x_global = target.pos_x + target.size_x / 2
            for z_local in self._spaced_positions(
                target.size_z,
                first,
                max_spacing,
            ):
                add_screw(target, x_global, target.pos_z + z_local)
        for target in targets[2:]:
            if target is None:
                continue
            z_global = target.pos_z + target.size_z / 2
            for x_local in self._spaced_positions(
                target.size_x,
                first,
                max_spacing,
            ):
                add_screw(target, target.pos_x + x_local, z_global)
        return result

    def _back_rail_holes(
        self,
        panels: List[PanelRecord],
    ) -> List[HoleSpec]:
        by_label = {panel.label: panel for panel in panels}
        left = by_label.get("left_side_panel")
        right = by_label.get("right_side_panel")
        rails = [
            panel for panel in panels if panel.panel_type == "back_rail"
        ]
        if left is None or right is None or not rails:
            return []
        rules = self.rules.get("back_mount_drilling", {}).get("back_rail", {})
        count_per_end = int(rules.get("count_per_end", 2))
        end_offset = float(rules.get("end_offset_mm", 20))
        clearance_diameter = float(
            rules.get("clearance_hole_diameter_mm", 4.5)
        )
        pilot_diameter = float(rules.get("pilot_hole_diameter_mm", 3))
        pilot_depth = float(rules.get("pilot_depth_mm", 20))
        result: List[HoleSpec] = []

        for rail in rails:
            y_global = rail.pos_y + rail.size_y / 2
            for z_local in self._fixed_count_positions(
                rail.size_z,
                count_per_end,
                end_offset,
            ):
                z_global = rail.pos_z + z_local
                result.append(
                    self._hole(
                        left,
                        "back_rail_side_clearance",
                        left.pos_x,
                        y_global,
                        z_global,
                        clearance_diameter,
                        left.size_x,
                        "+x",
                        f"左侧板至{rail.name}的螺钉通孔",
                    )
                )
                result.append(
                    self._hole(
                        rail,
                        "back_rail_pilot",
                        rail.pos_x,
                        y_global,
                        z_global,
                        pilot_diameter,
                        min(pilot_depth, rail.size_x / 2),
                        "+x",
                        f"{rail.name}左端预孔",
                    )
                )
                result.append(
                    self._hole(
                        right,
                        "back_rail_side_clearance",
                        right.pos_x + right.size_x,
                        y_global,
                        z_global,
                        clearance_diameter,
                        right.size_x,
                        "-x",
                        f"右侧板至{rail.name}的螺钉通孔",
                    )
                )
                result.append(
                    self._hole(
                        rail,
                        "back_rail_pilot",
                        rail.pos_x + rail.size_x,
                        y_global,
                        z_global,
                        pilot_diameter,
                        min(pilot_depth, rail.size_x / 2),
                        "-x",
                        f"{rail.name}右端预孔",
                    )
                )
        return result

    @staticmethod
    def _mode(panels: List[PanelRecord]) -> str:
        modes = {panel.back_mount for panel in panels if panel.back_mount}
        return next(iter(modes)) if len(modes) == 1 else ""

    @staticmethod
    def _hole_count(holes: List[HoleSpec], hole_type: str) -> int:
        return sum(hole.hole_type == hole_type for hole in holes)

    @staticmethod
    def _spaced_positions(
        length: float,
        edge_offset: float,
        max_spacing: float,
    ) -> List[float]:
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
    def _fixed_count_positions(
        length: float,
        count: int,
        edge_offset: float,
    ) -> List[float]:
        if length <= 0 or count <= 0:
            return []
        if count == 1:
            return [length / 2]
        if length <= 2 * edge_offset:
            return [
                length * (index + 1) / (count + 1)
                for index in range(count)
            ]
        usable = length - 2 * edge_offset
        return [
            edge_offset + usable * index / (count - 1)
            for index in range(count)
        ]

    @staticmethod
    def _hole(
        panel: PanelRecord,
        hole_type: str,
        x_global: float,
        y_global: float,
        z_global: float,
        diameter: float,
        depth: float,
        direction: str,
        note: str,
    ) -> HoleSpec:
        return HoleSpec(
            hole_type=hole_type,
            panel_label=panel.label,
            x_global=x_global,
            y_global=y_global,
            z_global=z_global,
            x_local=x_global - panel.pos_x,
            y_local=y_global - panel.pos_y,
            z_local=z_global - panel.pos_z,
            diameter=diameter,
            depth=depth,
            direction=direction,
            note=note,
        )
