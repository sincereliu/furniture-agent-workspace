from __future__ import annotations

import json
import sys
import tempfile
import unittest
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
from furniture_layout.layout_pipeline import plan_layout
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


class PanelAndConnectorPatchTests(unittest.TestCase):
    def test_standard_doors_have_explicit_hinge_sides(self) -> None:
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        doors = {
            panel.id: panel
            for panel in placements
            if panel.panel_type == "door"
        }

        self.assertEqual(doors["left_door"].door_hinge_side, "left")
        self.assertEqual(doors["right_door"].door_hinge_side, "right")

    def test_single_door_requires_explicit_hinge_side(self) -> None:
        # 单门铰链侧是开放偏好，必须由提案显式提交，缺省不得由代码补默认值
        with self.assertRaises(ValueError):
            furniture_spec(n_doors=1)

        right_spec = furniture_spec(n_doors=1, door_hinge_side="right")
        placements = plan_panels(right_spec, plan_layout(right_spec))
        door = next(p for p in placements if p.panel_type == "door")
        self.assertEqual(door.door_hinge_side, "right")

        # 双门铰链侧由代码确定性推导，不接受显式标量覆盖
        with self.assertRaises(ValueError):
            furniture_spec(n_doors=2, door_hinge_side="left")

    def test_trinity_uses_two_depth_rows_and_explicit_hole_faces(self) -> None:
        connector = TrinityConnector()
        side = panel_record(
            label="left_side_panel",
            name="左侧板",
            panel_type="side",
            size_x=18,
            size_y=600,
            size_z=1000,
            inner_face="+x",
        )
        top = panel_record(
            label="top_panel",
            name="顶板",
            panel_type="top",
            size_x=764,
            size_y=600,
            size_z=18,
            pos_x=18,
            pos_z=982,
            cam_face="-z",
        )

        side_holes = connector.generate_holes(side)
        self.assertEqual({hole.y_local for hole in side_holes}, {64.0, 536.0})
        self.assertTrue(all(hole.is_face_hole for hole in side_holes))
        self.assertTrue(all(hole.direction == "-x" for hole in side_holes))

        top_holes = connector.generate_holes(top)
        rod_holes = [
            hole for hole in top_holes if hole.hole_type == "three_in_one_rod"
        ]
        cam_holes = [
            hole for hole in top_holes if hole.hole_type == "three_in_one_cam"
        ]
        self.assertEqual({hole.y_local for hole in rod_holes}, {64.0, 536.0})
        # 偏心轮 y 与连接杆同排；x 为端面 + cam_offset（= 插入深度 + 圆心到杆头端距离 = 33.5）
        self.assertEqual({hole.y_local for hole in cam_holes}, {64.0, 536.0})
        self.assertEqual({hole.x_local for hole in cam_holes}, {33.5, 764 - 33.5})
        self.assertTrue(all(not hole.is_face_hole for hole in rod_holes))
        self.assertTrue(all(hole.is_face_hole for hole in cam_holes))

    def test_trinity_machining_operation_ids_are_unique_per_end(self) -> None:
        """两端连接的三合一板，加工指令 id 必须含 x_local 以区分左右端。"""
        connector = TrinityConnector()
        top = panel_record(
            label="top_panel",
            name="顶板",
            panel_type="top",
            size_x=764,
            size_y=600,
            size_z=18,
            pos_x=18,
            pos_z=982,
            cam_face="-z",
        )
        ops = connector.machining_operations(top)
        ids = [op.id for op in ops]
        # 唯一性：旧实现 id 无 x_local 时，左右两端同 (z,y) 的孔 id 重复
        self.assertEqual(len(ids), len(set(ids)))
        # 同一深度排(y=64)的两个连接杆孔（左端 x=0 / 右端 x=764）id 必须不同
        male_front = [
            op for op in ops
            if "three_in_one_rod" in op.id and "_64_" in op.id
        ]
        self.assertEqual(len(male_front), 2)
        self.assertNotEqual(male_front[0].id, male_front[1].id)

    def test_trinity_rod_cam_count_mismatch_is_rejected(self) -> None:
        """删掉一个连接杆孔后，校验必须报 TRINITY_ROD_CAM_COUNT_MISMATCH。"""
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        manufacturing = plan_manufacturing(spec, placements)
        orig = TrinityConnector.generate_holes_for_panels

        def drop_one_male(self, panels):
            holes = orig(self, panels)
            dropped = False
            kept = []
            for hole in holes:
                if not dropped and hole.hole_type == "three_in_one_rod":
                    dropped = True
                    continue
                kept.append(hole)
            return kept

        with mock.patch.object(
            TrinityConnector, "generate_holes_for_panels", drop_one_male
        ):
            report = validate_manufacturing(spec, manufacturing, placements)

        self.assertFalse(report.passed)
        self.assertIn(
            "TRINITY_ROD_CAM_COUNT_MISMATCH",
            {issue.code for issue in report.issues},
        )

    def test_drawer_slide_connector_emits_per_drawer_bom(self) -> None:
        """每个抽屉实例一副滑轨（左右各 1）；不同深度各配各的长度。"""
        drawer_1 = [
            panel_record(
                label="drawer_side_L_z300", name="抽屉左板",
                panel_type="drawer_side", size_x=18, size_y=500, size_z=150,
                pos_x=0, pos_y=0, pos_z=300,
            ),
            panel_record(
                label="drawer_side_R_z300", name="抽屉右板",
                panel_type="drawer_side", size_x=18, size_y=500, size_z=150,
                pos_x=350, pos_y=0, pos_z=300,
            ),
            panel_record(
                label="drawer_front_z300", name="抽屉前板",
                panel_type="drawer_front", size_x=380, size_y=18, size_z=150,
                pos_x=0, pos_y=0, pos_z=300,
            ),
            panel_record(
                label="drawer_bottom_z300", name="抽屉底板",
                panel_type="drawer_bottom", size_x=380, size_y=500, size_z=12,
                pos_x=0, pos_y=0, pos_z=300,
            ),
        ]
        drawer_2 = [
            panel_record(
                label="drawer_side_L_z600", name="抽屉左板",
                panel_type="drawer_side", size_x=18, size_y=550, size_z=150,
                pos_x=0, pos_y=0, pos_z=600,
            ),
            panel_record(
                label="drawer_side_R_z600", name="抽屉右板",
                panel_type="drawer_side", size_x=18, size_y=550, size_z=150,
                pos_x=350, pos_y=0, pos_z=600,
            ),
            panel_record(
                label="drawer_front_z600", name="抽屉前板",
                panel_type="drawer_front", size_x=400, size_y=18, size_z=150,
                pos_x=0, pos_y=0, pos_z=600,
            ),
            panel_record(
                label="drawer_bottom_z600", name="抽屉底板",
                panel_type="drawer_bottom", size_x=400, size_y=550, size_z=12,
                pos_x=0, pos_y=0, pos_z=600,
            ),
        ]

        records = DrawerSlideConnector().boms(drawer_1 + drawer_2)

        self.assertEqual(len(records), 2)
        self.assertTrue(all(r.name == "抽屉滑轨" for r in records))
        self.assertTrue(all(r.unit == "副" for r in records))
        # 每抽一副（左右各 1）；深度 500→450mm、550→500mm
        self.assertEqual({r.quantity for r in records}, {2})
        self.assertEqual({r.model for r in records}, {"SJG-01"})
        self.assertEqual(
            {r.spec for r in records},
            {"默认 SJG-01 450mm 30kg", "默认 SJG-01 500mm 30kg"},
        )

    def test_drawer_slide_connector_absent_without_drawer_panels(self) -> None:
        """无抽屉板件时不产出滑轨 BOM（且全流水线 BOM 无滑轨行）。"""
        self.assertEqual(DrawerSlideConnector().boms([panel_record(
            label="left_side_panel", name="左侧板", panel_type="side",
            size_x=18, size_y=600, size_z=1000,
        )]), [])
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800, depth=600, height=1000, n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        bom = plan_manufacturing(spec, placements)
        self.assertNotIn("抽屉滑轨", [item.name for item in bom.hardware])

    def test_hinge_cup_uses_center_distance_and_inner_face(self) -> None:
        door = panel_record(
            label="left_door",
            name="左门板",
            panel_type="door",
            size_x=397,
            size_y=18,
            size_z=948,
            inner_face="-y",
            door_hinge_side="left",
        )

        holes = HingeConnector().generate_holes(door)

        self.assertTrue(holes)
        self.assertEqual({hole.x_local for hole in holes}, {22.5})
        # direction 统一为钻入方向：内侧面 "-y" → 往板内钻 "+y"
        self.assertTrue(all(hole.direction == "+y" for hole in holes))
        self.assertTrue(all(hole.is_face_hole for hole in holes))

    def test_manufacturing_validation_rejects_hinge_outside_door(self) -> None:
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        manufacturing = plan_manufacturing(spec, placements)
        left_door = next(
            panel
            for panel in manufacturing.panels
            if panel.label == "left_door"
        )
        left_door.size_x = 30

        report = validate_manufacturing(
            spec,
            manufacturing,
            placements,
        )

        self.assertFalse(report.passed)
        self.assertIn(
            "HINGE_HOLE_OUTSIDE_DOOR",
            {issue.code for issue in report.issues},
        )

    def test_emitted_panels_include_type_and_no_screw_holes(self) -> None:
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            back_mount="cover",
            back_thickness=9,
            n_doors=2,
        )
        placements = plan_panels(spec, plan_layout(spec))
        drilled = emit_drilled_holes(plan_manufacturing(spec, placements))

        self.assertTrue(
            all(panel.get("panel_type") for panel in drilled["panels"])
        )
        # 螺钉孔为组装现场工艺，不应出现在柜体加工孔位中
        screw_holes = [
            hole
            for panel in drilled["panels"]
            for hole in panel["holes"]
            if hole["hole_type"] in {
                "cover_back_clearance",
                "cover_back_pilot",
                "back_rail_side_clearance",
                "back_rail_pilot",
            }
        ]
        self.assertEqual(screw_holes, [])

    def test_dynamic_panel_labels_stay_in_panel_step_group(self) -> None:
        groups = _build_grouped_geometry(
            {
                "panels": [
                    {
                        "label": "shelf_z999",
                        "panel_type": "fixed_shelf",
                        "box": {
                            "x": 600,
                            "y": 500,
                            "z": 18,
                            "pos_x": 0,
                            "pos_y": 0,
                            "pos_z": 999,
                        },
                        "holes": [],
                    }
                ]
            },
            marker_thickness=2,
        )

        self.assertEqual([solid.label for solid in groups["板件"]], ["shelf_z999"])
        self.assertNotIn("其他孔位", groups)


class DrawerZoneTests(unittest.TestCase):
    """整高抽屉区（档 B 首版）：drawer_count>0 → 抽屉板件，无门无层板。"""

    def _drawer_cabinet(
        self,
        drawer_count: int,
        n_doors: int = 0,
        shelf_count: int = 0,
    ):
        spec = furniture_spec(
            furniture_type="floor_cabinet",
            width=800,
            depth=600,
            height=1000,
            n_doors=n_doors,
            shelf_count=shelf_count,
            drawer_count=drawer_count,
        )
        placements = plan_panels(spec, plan_layout(spec))
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
                panel.id,
                r"^drawer_(front|side_L|side_R|back|bottom)_z\d+$",
            )
        # 3 个抽屉实例，每个 5 块板共享 z 后缀
        from collections import Counter

        instance_keys = Counter(
            panel.id.rsplit("_", 1)[1] for panel in drawer_panels
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
            if h.panel_label == "drawer_bottom_z68"
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


class SixSideDrillPatchTests(unittest.TestCase):
    def _sample_data(self, *, slots: list[dict] | None = None) -> dict:
        return {
            "panels": [
                {
                    "label": "top_panel",
                    "name": "顶板",
                    "panel_type": "top",
                    "box": {
                        "x": 764,
                        "y": 580,
                        "z": 18,
                        "pos_x": 10,
                        "pos_y": 20,
                        "pos_z": 30,
                    },
                    "holes": [
                        {
                            "hole_type": "three_in_one_cam",
                            "local_x": 100,
                            "local_y": 64,
                            "local_z": 18,
                            "diameter": 12,
                            "depth": 13.5,
                            "direction": "-z",
                            "is_face_hole": True,
                        },
                        {
                            "hole_type": "three_in_one_rod",
                            "x": 98,
                            "y": 97,
                            "z": 39,
                            "diameter": 8,
                            "depth": 33,
                            "direction": "+x",
                            "is_face_hole": False,
                        },
                    ],
                    "slots": slots or [],
                }
            ]
        }

    def test_xml_uses_machine_axes_localizes_legacy_holes_and_closes_once(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "drilled.json"
            source.write_text(
                json.dumps(self._sample_data(), ensure_ascii=False),
                encoding="utf-8",
            )

            [xml_path] = drill_json_to_xml_files(source, root / "xml")
            document = ET.fromstring(xml_path.read_text(encoding="utf-8"))

        self.assertEqual(document.findtext("./PANEL/PanelLength"), "580.0")
        self.assertEqual(document.findtext("./PANEL/PanelWidth"), "764.0")
        self.assertEqual(document.findtext("./PANEL/PanelThickness"), "18.0")

        vertices = [
            (
                float(vertex.findtext("X1", "0")),
                float(vertex.findtext("Y1", "0")),
            )
            for vertex in document.findall("./PANEL/PanelOutline/Vertex")
        ]
        self.assertEqual(
            vertices,
            [
                (0.0, 764.0),
                (0.0, 0.0),
                (580.0, 0.0),
                (580.0, 764.0),
                (0.0, 764.0),
            ],
        )

        face_hole, edge_hole = document.findall("./CAD")
        self.assertEqual(face_hole.findtext("TypeNo"), "1")
        self.assertEqual(face_hole.findtext("X1"), "64.0")
        self.assertEqual(face_hole.findtext("Y1"), "100.0")

        self.assertEqual(edge_hole.findtext("TypeNo"), "2")
        self.assertEqual(edge_hole.findtext("X1"), "77.0")
        self.assertEqual(edge_hole.findtext("Y1"), "88.0")
        self.assertEqual(edge_hole.findtext("Z1"), "9.00")
        self.assertEqual(edge_hole.findtext("Quadrant"), "3")

    def test_slot_input_is_rejected_instead_of_silently_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "drilled.json"
            source.write_text(
                json.dumps(
                    self._sample_data(slots=[{"type": "groove"}]),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "slot export is not implemented",
            ):
                drill_json_to_xml_files(source, root / "xml")


if __name__ == "__main__":
    unittest.main()
