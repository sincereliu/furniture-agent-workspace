from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock
from xml.etree import ElementTree as ET


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_panel_planning.panel_spec import FurnitureSpec
from panel_fixtures import furniture_spec
from furniture_manufacturing.connectors.drawer_slide import DrawerSlideConnector
from furniture_manufacturing.connectors.hinge import HingeConnector
from furniture_manufacturing.connectors.trinity import TrinityConnector
from furniture_manufacturing.drilled_holes_glb import _build_grouped_geometry
from furniture_manufacturing.export_six_side_drill import (
    drill_json_to_xml_files,
)
from furniture_manufacturing.manufacturing_bom import (
    emit_drilled_holes,
    plan_manufacturing,
)
from furniture_manufacturing.manufacturing_models import PanelRecord
from furniture_manufacturing.validation import validate_manufacturing
from furniture_panel_planning.panel_planning import plan_panels
from furniture_panel_planning.structure_planning import CabinetStructure
from furniture_panel_planning.validation import validate_panels


def panel_record(
    *,
    label: str,
    name: str,
    panel_type: str,
    size_x: float,
    size_y: float,
    size_z: float,
    pos_x: float = 0,
    pos_y: float = 0,
    pos_z: float = 0,
    inner_face: str = "",
    cam_face: str | None = None,
    door_hinge_side: str | None = None,
) -> PanelRecord:
    return PanelRecord(
        label=label,
        name=name,
        panel_type=panel_type,
        material="测试板",
        thickness=min(size_x, size_y, size_z),
        length_mm=max(size_x, size_y, size_z),
        width_mm=sorted((size_x, size_y, size_z))[-2],
        size_x=size_x,
        size_y=size_y,
        size_z=size_z,
        pos_x=pos_x,
        pos_y=pos_y,
        pos_z=pos_z,
        inner_face=inner_face,
        cam_face=cam_face,
        door_hinge_side=door_hinge_side,
    )

class DrawerZoneTests(unittest.TestCase):
    """整高抽屉区（档 B 首版）：drawer_count>0 → 抽屉板件，无门无层板。"""

    def _drawer_cabinet(
        self,
        drawer_count: int,
        n_doors: int = 0,
        shelf_count: int = 0,
    ):
        spec = furniture_spec(
            furniture_category="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=n_doors,
            shelf_count=shelf_count,
            drawer_count=drawer_count,
        )
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        return spec, placements

    def test_full_height_drawer_zone_generates_five_panels_per_drawer(self) -> None:
        spec, placements = self._drawer_cabinet(3)
        types = {p.panel_type for p in placements}
        self.assertTrue(
            {"drawer_front", "drawer_side", "drawer_back", "drawer_bottom"}
            <= types
        )
        self.assertNotIn("door", types)
        self.assertNotIn("fixed_shelf", types)

        drawer_panels = [p for p in placements if "drawer" in p.panel_type]
        self.assertEqual(len(drawer_panels), 15)  # 3 抽屉 × 5 板
        # label 契约：drawer_<角色>_z{位置}（实例 key = z 后缀）
        for panel in drawer_panels:
            self.assertRegex(
                panel.role,
                r"^drawer_(front|side_L|side_R|back|bottom)_z\d+$",
            )
        # 3 个抽屉实例，每个 5 块板共享 z 后缀
        from collections import Counter

        instance_keys = Counter(
            panel.role.rsplit("_", 1)[1] for panel in drawer_panels
        )
        self.assertEqual(len(instance_keys), 3)
        self.assertTrue(all(count == 5 for count in instance_keys.values()))

    def test_bottom_drawer_front_covers_bottom_panel(self) -> None:
        """底抽前板全盖底板（front_overlap=18）：侧板高 = 前板高 − 36。"""
        _, placements = self._drawer_cabinet(3)
        drawer_panels = [p for p in placements if "drawer" in p.panel_type]
        fronts = sorted(
            (p for p in drawer_panels if p.panel_type == "drawer_front"),
            key=lambda p: p.pos_z,
        )
        sides = [
            p for p in drawer_panels if p.panel_type == "drawer_side"
        ]
        # 三个抽屉的前板高度相同（均分净高 − 层缝）
        front_h = fronts[0].size_z  # 未取整的实际前板高
        self.assertTrue(
            all(abs(p.size_z - front_h) < 1e-6 for p in fronts)
        )
        # 底抽（最小 front_z）：前板向下覆盖 18 → 侧板 pos_z = front_z + 18，高 = front_h − 36
        bottom_front_z = fronts[0].pos_z
        bottom_sides = [p for p in sides if p.pos_z == bottom_front_z + 18]
        self.assertEqual(len(bottom_sides), 2)
        self.assertTrue(all(abs(p.size_z - (front_h - 36)) < 1e-6 for p in bottom_sides))
        # 上两层抽屉：侧板 pos_z = 各自 front_z（无覆盖），高 = front_h
        for front in fronts[1:]:
            band_sides = [p for p in sides if p.pos_z == front.pos_z]
            self.assertEqual(len(band_sides), 2)
            self.assertTrue(all(abs(p.size_z - front_h) < 1e-6 for p in band_sides))

    def test_panel_validation_rejects_drawer_geometry_mismatch(self) -> None:
        spec, placements = self._drawer_cabinet(3)
        tampered = [
            p if p.role != "drawer_bottom_z68" else replace(
                p,
                size_y=p.size_y - 10,
            )
            for p in placements
        ]

        report = validate_panels(
            spec,
            CabinetStructure.from_spec(spec),
            tampered,
        )

        self.assertFalse(report.passed)
        self.assertIn(
            "DRAWER_PANEL_GEOMETRY_MISMATCH",
            {issue.code for issue in report.issues},
        )

    def test_drawer_zone_bom_emits_slides_per_drawer(self) -> None:
        spec, placements = self._drawer_cabinet(3)
        manufacturing = plan_manufacturing(spec, placements)
        slides = [h for h in manufacturing.hardware if h.name == "抽屉滑轨"]
        self.assertEqual(len(slides), 1)  # 同深度 → 单条记录
        self.assertEqual(slides[0].quantity, 6)  # 3 抽屉 × 每抽 2
        # 抽屉深 = 内部深(553) − 前板厚(18) → 535 → 匹配 450mm 三节轨
        self.assertIn("450mm", slides[0].spec)

        report = validate_manufacturing(spec, manufacturing, placements)
        self.assertTrue(report.passed)

    def test_drawer_zone_rejects_conflicting_doors_or_shelves(self) -> None:
        with self.assertRaisesRegex(ValueError, "full-height drawers require"):
            self._drawer_cabinet(3, n_doors=2, shelf_count=4)

    def test_drawer_box_uses_trinity_by_default(self) -> None:
        """抽屉盒默认三合一（全屋定制主流）：杆/轮/螺母 1:1:1，底板 cam 在底面。"""
        spec, placements = self._drawer_cabinet(1)
        manufacturing = plan_manufacturing(spec, placements)
        holes = TrinityConnector().generate_holes_for_panels(manufacturing.panels)
        drawer_labels = {
            p.label for p in manufacturing.panels if "drawer" in p.panel_type
        }
        drawer_holes = [h for h in holes if h.panel_label in drawer_labels]
        types = [h.hole_type for h in drawer_holes]
        # 1:1:1 配对（每连接：1 杆 + 1 轮 + 1 螺母）
        self.assertGreater(types.count("three_in_one_rod"), 0)
        self.assertEqual(
            types.count("three_in_one_rod"),
            types.count("three_in_one_cam"),
        )
        self.assertEqual(
            types.count("three_in_one_cam"),
            types.count("three_in_one_nut"),
        )
        # 底板轮孔在底面（cam_face=-z → z_local=0，钻入方向 +z）
        bottom_cams = [
            h for h in holes
            if h.panel_label.endswith("drawer_bottom_z68")
            and h.hole_type == "three_in_one_cam"
        ]
        self.assertEqual(len(bottom_cams), 8)  # 4 连接 × 2 排
        self.assertTrue(all(abs(h.z_local) < 1e-6 for h in bottom_cams))
        self.assertTrue(all(h.direction == "+z" for h in bottom_cams))
        # BOM 三合一数量 = 全部偏心轮孔数（柜体 + 抽屉，孔即真源）
        trinity = [h for h in manufacturing.hardware if h.name == "三合一连接件"]
        self.assertEqual(
            trinity[0].quantity,
            sum(1 for h in holes if h.hole_type == "three_in_one_cam"),
        )

    def test_no_drawer_keeps_doors_and_shelves(self) -> None:
        spec, placements = self._drawer_cabinet(0, n_doors=2, shelf_count=4)
        types = {p.panel_type for p in placements}
        self.assertIn("door", types)
        self.assertIn("fixed_shelf", types)
        self.assertTrue(all("drawer" not in p.panel_type for p in placements))



if __name__ == "__main__":
    unittest.main()
