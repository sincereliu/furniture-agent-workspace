from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_design_intent.design_spec import FurnitureSpec
from furniture_layout.layout_pipeline import plan_layout
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
from furniture_panel_planning.panel_planning import plan_panels


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
        spec = FurnitureSpec(
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
            hole for hole in top_holes if hole.hole_type == "system_32_male"
        ]
        cam_holes = [
            hole for hole in top_holes if hole.hole_type == "system_32_female"
        ]
        self.assertEqual({hole.y_local for hole in rod_holes}, {64.0, 536.0})
        self.assertEqual({hole.y_local for hole in cam_holes}, {33.5, 566.5})
        self.assertTrue(all(not hole.is_face_hole for hole in rod_holes))
        self.assertTrue(all(hole.is_face_hole for hole in cam_holes))

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
        self.assertTrue(all(hole.direction == "-y" for hole in holes))
        self.assertTrue(all(hole.is_face_hole for hole in holes))

    def test_emitted_panels_include_type_and_safe_screw_clearance(self) -> None:
        spec = FurnitureSpec(
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
        clearance_holes = [
            hole
            for panel in drilled["panels"]
            for hole in panel["holes"]
            if hole["hole_type"] in {
                "cover_back_clearance",
                "back_rail_side_clearance",
            }
        ]
        self.assertTrue(clearance_holes)
        self.assertEqual(
            {hole["diameter"] for hole in clearance_holes},
            {4.5},
        )

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
                            "hole_type": "system_32_female",
                            "local_x": 100,
                            "local_y": 64,
                            "local_z": 18,
                            "diameter": 12,
                            "depth": 13.5,
                            "direction": "-z",
                            "is_face_hole": True,
                        },
                        {
                            "hole_type": "system_32_male",
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
