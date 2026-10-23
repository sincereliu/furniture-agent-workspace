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
from furniture_panel_planning.construction_geometry import (
    drawer_cell_report,
    shelf_bays,
)
from furniture_panel_planning.drawer_variants import drawer_panels_per_instance
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
    """抽屉区：`drawer_count>0` → 抽屉板件；门仍互斥，层板可共存（按格）。"""

    def _drawer_cabinet(
        self,
        drawer_count: int,
        n_doors: int = 0,
        shelf_count: int = 0,
        **overrides,
    ):
        spec = furniture_spec(
            furniture_category="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=n_doors,
            shelf_count=shelf_count,
            drawer_count=drawer_count,
            drawer_back_clearance=20.0,
            **overrides,
        )
        placements = plan_panels(spec, CabinetStructure.from_spec(spec))
        return spec, placements

    def test_drawer_zone_generates_six_panels_per_drawer(self) -> None:
        """一抽 6 块：抽面 + 左右侧板 + 背板 + 底板 + 前板。"""
        spec, placements = self._drawer_cabinet(3)
        types = {p.panel_type for p in placements}
        self.assertTrue(
            {
                "drawer_front",
                "drawer_box_front",
                "drawer_side",
                "drawer_back",
                "drawer_bottom",
            }
            <= types
        )
        self.assertNotIn("door", types)
        self.assertNotIn("fixed_shelf", types)

        drawer_panels = [p for p in placements if "drawer" in p.panel_type]
        self.assertEqual(
            len(drawer_panels), 3 * drawer_panels_per_instance(spec.drawer_front_board)
        )
        # label 契约：drawer_<角色>_z{位置}（实例 key = z 后缀）
        for panel in drawer_panels:
            self.assertRegex(
                panel.role,
                r"^drawer_(front|box_front|side_L|side_R|back|bottom)_z\d+$",
            )
        # 3 个抽屉实例，每个实例的板件数一致
        from collections import Counter

        instance_keys = Counter(
            panel.role.rsplit("_", 1)[1] for panel in drawer_panels
        )
        self.assertEqual(len(instance_keys), 3)
        self.assertTrue(
            all(count == 6 for count in instance_keys.values())
        )

    def test_drawer_without_front_board_has_five_panels(self) -> None:
        """没有前板：抽面直接当盒体前墙，5 块。"""
        spec, placements = self._drawer_cabinet(3, drawer_front_board=False)
        types = {p.panel_type for p in placements}
        self.assertNotIn("drawer_box_front", types)
        drawer_panels = [p for p in placements if "drawer" in p.panel_type]
        self.assertEqual(len(drawer_panels), 3 * 5)

    def test_drawer_box_sits_inside_its_cell(self) -> None:
        """盒高由格高减上下间隙给出：盒体比抽面矮，上下都留了空间。"""
        spec, placements = self._drawer_cabinet(3)
        structure = CabinetStructure.from_spec(spec)
        cell = drawer_cell_report(spec, structure)
        drawer_panels = [p for p in placements if "drawer" in p.panel_type]
        fronts = sorted(
            (p for p in drawer_panels if p.panel_type == "drawer_front"),
            key=lambda p: p.pos_z,
        )
        sides = sorted(
            (p for p in drawer_panels if p.panel_type == "drawer_side"),
            key=lambda p: p.pos_z,
        )
        fronts_h = [p.size_z for p in fronts]
        self.assertTrue(all(abs(h - fronts_h[0]) < 1e-6 for h in fronts_h))
        # 三个抽屉的盒高一致，且比抽面矮（上下间隙 + 10 取整的余量）
        sides_h = sorted({round(p.size_z, 6) for p in sides})
        self.assertEqual(sides_h, [cell["box_height"]])
        self.assertLess(sides_h[0], fronts_h[0])
        # 每层盒体起点 = 该层格的起点 + 下间隙
        for index, side_z in enumerate(sorted({round(p.pos_z, 6) for p in sides})):
            expected = structure.internal_z_start + index * cell["cell_height"] + cell["lower_gap"]
            self.assertAlmostEqual(side_z, expected, places=6)

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
        self.assertTrue(bottom_cams)
        # 底板上的孔数 = 底板作为端面件的连接 × 2 排；数量跟着构造走，不写死常数
        bottom_panel = next(p for p in placements if p.role == "drawer_bottom_z68")
        bottom_as_end = [
            joint for joint in bottom_panel.joints if joint.end_id == bottom_panel.id
        ]
        self.assertEqual(len(bottom_cams), 2 * len(bottom_as_end))
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

    def test_drawers_cannot_share_a_cabinet_with_doors(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot share one cabinet"):
            self._drawer_cabinet(1, n_doors=2)

    def test_drawers_among_shelves_need_a_bay(self) -> None:
        with self.assertRaisesRegex(ValueError, "require drawer_bay_index"):
            self._drawer_cabinet(1, shelf_count=3)

    def test_shelves_and_a_drawer_coexist_in_named_bays(self) -> None:
        """三块层板切出四格：抽屉落在第 3 格，层板照常出件。"""
        spec, placements = self._drawer_cabinet(1, shelf_count=3, drawer_bay_index=3)
        structure = CabinetStructure.from_spec(spec)
        cell = drawer_cell_report(spec, structure)
        bays = shelf_bays(spec, structure)
        self.assertEqual(len(bays), 4)
        self.assertAlmostEqual(cell["zone_start"], bays[2][0], places=6)
        self.assertAlmostEqual(cell["cell_height"], bays[2][1], places=6)
        types = [p.panel_type for p in placements]
        self.assertEqual(types.count("fixed_shelf"), 3)
        self.assertIn("drawer_front", types)
        # 抽屉落在第 3 格，与层板不重叠
        self.assertGreaterEqual(cell["zone_start"], structure.internal_z_start)
        self.assertLessEqual(
            cell["zone_start"] + cell["zone_height"], structure.internal_z_end
        )
        report = validate_panels(spec, structure, placements)
        self.assertTrue(report.passed, [issue.code for issue in report.issues])

    def test_bay_index_out_of_range_is_rejected(self) -> None:
        spec = furniture_spec(
            furniture_category="floor_cabinet", width=800, depth=600, height=1000,
            n_doors=0, shelf_count=3, drawer_count=1, drawer_bay_index=9,
            drawer_back_clearance=20.0,
        )
        structure = CabinetStructure.from_spec(spec)
        with self.assertRaisesRegex(ValueError, "out of range"):
            plan_panels(spec, structure)

    def test_bay_and_clear_height_are_exclusive(self) -> None:
        with self.assertRaisesRegex(ValueError, "exclusive"):
            self._drawer_cabinet(
                1, shelf_count=3, drawer_bay_index=1, drawer_clear_height_mm=200.0
            )

    def test_bay_index_without_shelves_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires shelves"):
            self._drawer_cabinet(1, drawer_bay_index=1)



if __name__ == "__main__":
    unittest.main()
