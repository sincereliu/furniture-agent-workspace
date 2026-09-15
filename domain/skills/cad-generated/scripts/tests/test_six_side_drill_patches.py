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
