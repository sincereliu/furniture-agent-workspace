from __future__ import annotations

from math import hypot
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.cad import (
    _path_within,
    room_cad_artifact_name,
    write_room_cad_source,
)
from furniture_layout.pipeline import generate_room_cad, plan_project_layout, plan_room_scene
from furniture_layout.preview import _build_projector
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.scene import RoomScene
from furniture_layout.validation import validate_room_scene
from furniture_workflow.workflow_state import STAGE_SEQUENCE, WorkflowStage


def bedroom_room() -> dict:
    return {
        "id": "bedroom",
        "name": "主卧",
        "width_mm": 4200,
        "depth_mm": 3600,
        "height_mm": 2800,
        "openings": [
            {
                "id": "bedroom_door",
                "kind": "door",
                "wall": "east",
                "offset_mm": 2000,
                "width_mm": 900,
                "height_mm": 2100,
            }
        ],
        "obstacles": [],
    }


def bedroom_items() -> list[dict]:
    return [
        {
            "id": "bed",
            "label": "床",
            "category": "bed",
            "width": 1800,
            "depth": 2000,
            "height": 450,
            "placement": {
                "mode": "wall",
                "host_wall": "north",
                "offset_mm": 1200,
                "origin_z_mm": 0,
            },
        },
        {
            "id": "wardrobe",
            "label": "衣柜",
            "category": "wardrobe",
            "width": 800,
            "depth": 600,
            "height": 2400,
            "placement": {
                "mode": "wall",
                "host_wall": "east",
                "fill": True,
                "origin_z_mm": 0,
            },
        },
    ]


class RoomSceneLayoutTests(unittest.TestCase):
    def test_explicit_room_cad_artifact_id_must_be_safe(self) -> None:
        self.assertEqual(
            room_cad_artifact_name(
                artifact_id="bedroom-v1",
                room_id="ignored-room-id",
            ),
            "bedroom-v1",
        )
        for artifact_id in (
            "",
            "../escape",
            r"..\escape",
            "/absolute",
            r"C:\absolute",
            "bad name",
            "中文",
        ):
            with self.subTest(artifact_id=artifact_id):
                with self.assertRaisesRegex(ValueError, "artifact_id"):
                    room_cad_artifact_name(
                        artifact_id=artifact_id,
                        room_id="bedroom",
                    )

    def test_room_id_fallback_is_stable_and_safe(self) -> None:
        self.assertEqual(
            room_cad_artifact_name(artifact_id=None, room_id="bedroom"),
            "bedroom",
        )
        first = room_cad_artifact_name(artifact_id=None, room_id="主卧/套房")
        repeated = room_cad_artifact_name(artifact_id=None, room_id="主卧/套房")
        other = room_cad_artifact_name(artifact_id=None, room_id="儿童房")
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, other)
        self.assertRegex(first, re.compile(r"^room-[0-9a-f]{16}$"))

    def test_generated_path_guard_rejects_parent_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "allowed"
            with self.assertRaisesRegex(ValueError, "escapes"):
                _path_within(root, "..", "escape", "room.step")
            self.assertFalse(root.exists())

    def test_preview_projection_makes_near_geometry_larger(self) -> None:
        project = _build_projector(4200, 3600, 2800)
        near_bottom = project((4200, 0, 0))
        near_top = project((4200, 0, 1000))
        far_bottom = project((0, 3600, 0))
        far_top = project((0, 3600, 1000))
        near_height = hypot(
            near_top[0] - near_bottom[0],
            near_top[1] - near_bottom[1],
        )
        far_height = hypot(
            far_top[0] - far_bottom[0],
            far_top[1] - far_bottom[1],
        )
        self.assertGreater(near_height, far_height * 1.5)

    def test_missing_room_dimensions_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "width_mm"):
            plan_room_scene(
                {"id": "bedroom", "name": "主卧", "depth_mm": 3600, "height_mm": 2800},
                bedroom_items(),
            )

    def test_empty_items_fail(self) -> None:
        with self.assertRaisesRegex(ValueError, "items"):
            plan_room_scene(bedroom_room(), [])

    def test_bedroom_places_bed_and_fills_east_wall_around_door(self) -> None:
        output = plan_room_scene(bedroom_room(), bedroom_items())
        report = validate_room_scene(output)
        self.assertTrue(report.passed, report.to_dict())
        self.assertNotIn(getattr(WorkflowStage, "LAYOUT_PLANNED", "layout_planned"), STAGE_SEQUENCE)

        items = {item["id"]: item for item in output["items"]}
        bed = items["bed"]
        wardrobe = items["wardrobe"]
        self.assertEqual(bed["placement"]["host_wall"], "north")
        self.assertEqual(bed["placement"]["origin_x_mm"], 1200)
        self.assertEqual(bed["placement"]["origin_y_mm"], 0)
        self.assertEqual(bed["placement"]["rotation_z_deg"], 0)
        self.assertEqual(wardrobe["placement"]["host_wall"], "east")
        self.assertTrue(wardrobe["placement"]["fill"])
        self.assertEqual(wardrobe["placement"]["offset_mm"], 0)
        self.assertEqual(wardrobe["width"], 2000)
        self.assertEqual(wardrobe["placement"]["origin_x_mm"], 4200)
        self.assertEqual(wardrobe["placement"]["origin_y_mm"], 0)
        self.assertEqual(wardrobe["placement"]["rotation_z_deg"], 90)
        self.assertIn("<svg", output["preview"]["svg"])
        self.assertIn("主卧", output["preview"]["svg"])
        self.assertIn("床", output["preview"]["svg"])
        self.assertIn("衣柜", output["preview"]["svg"])
        self.assertIn('<canvas id="scene"', output["viewer"]["html"])

    def test_two_items_that_overlap_fail_validation(self) -> None:
        items = [
            {
                "id": "left",
                "label": "左柜",
                "category": "wardrobe",
                "width": 2000,
                "depth": 600,
                "height": 2400,
                "placement": {
                    "mode": "wall",
                    "host_wall": "north",
                    "offset_mm": 0,
                },
            },
            {
                "id": "right",
                "label": "右柜",
                "category": "wardrobe",
                "width": 2000,
                "depth": 600,
                "height": 2400,
                "placement": {
                    "mode": "wall",
                    "host_wall": "north",
                    "offset_mm": 1000,
                },
            },
        ]
        with self.assertRaisesRegex(ValueError, "interferes with item"):
            plan_room_scene(bedroom_room(), items)

    def test_cad_source_contains_room_and_item_transforms(self) -> None:
        output = plan_room_scene(bedroom_room(), bedroom_items())
        scene = RoomScene.from_dict(output)
        with tempfile.TemporaryDirectory() as temporary_directory:
            source_path = Path(temporary_directory) / "model.step.py"
            write_room_cad_source(scene, source_path)
            source = source_path.read_text(encoding="utf-8")
        self.assertIn("cut_box", source)
        self.assertIn("4200", source)
        self.assertIn("3600", source)
        self.assertIn("'id': 'bed'", source)
        self.assertIn("'id': 'wardrobe'", source)
        self.assertIn("'rotation_z_deg': 90.0", source)
        self.assertIn("'x': 1200.0", source)

    def test_generate_room_cad_uses_bridge_and_records_paths(self) -> None:
        output = plan_room_scene(bedroom_room(), bedroom_items())

        class FakeBridge:
            def generate_from_source(self, source_path, step_path, force=False):
                Path(step_path).parent.mkdir(parents=True, exist_ok=True)
                Path(step_path).write_text("STEP", encoding="utf-8")
                package = (
                    Path(source_path).parent
                    / "__cadgen__"
                    / "models"
                    / Path(source_path).name
                )
                package.mkdir(parents=True, exist_ok=True)
                (package / "assembly.json").write_text(
                    json.dumps({"ok": True}),
                    encoding="utf-8",
                )
                return type(
                    "BridgeResult",
                    (),
                    {
                        "status": "ok",
                        "message": "ok",
                        "step_path": str(step_path),
                        "topology_path": str(package / "assembly.json"),
                        "viewer_package_path": str(package),
                    },
                )()

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            result = generate_room_cad(
                output,
                workspace_root=workspace,
                output_root=workspace / "generated",
                cad_bridge=FakeBridge(),
                artifact_id="bedroom",
            )
        self.assertEqual(result["cad"]["status"], "ok")
        self.assertTrue(result["cad"]["source_path"].endswith("model.step.py"))
        self.assertTrue(result["cad"]["step_path"].endswith("room.step"))
        self.assertIn("cad", result)

    def test_generate_room_cad_rejects_unsafe_id_before_side_effects(self) -> None:
        output = plan_room_scene(bedroom_room(), bedroom_items())
        bridge = mock.Mock()
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            with self.assertRaisesRegex(ValueError, "artifact_id"):
                generate_room_cad(
                    output,
                    workspace_root=workspace,
                    output_root="generated",
                    cad_bridge=bridge,
                    artifact_id="../../escape",
                )
            self.assertFalse((workspace / "temp").exists())
            self.assertFalse((workspace / "generated").exists())
        bridge.generate_from_source.assert_not_called()

    def test_generate_room_cad_contains_paths_and_hashes_unsafe_room_id(self) -> None:
        room = bedroom_room()
        room["id"] = "主卧/套房"
        output = plan_room_scene(room, bedroom_items())

        class RecordingBridge:
            def __init__(self):
                self.calls = []

            def generate_from_source(self, source_path, step_path, force=False):
                self.calls.append((Path(source_path), Path(step_path), force))
                return type(
                    "BridgeResult",
                    (),
                    {
                        "status": "ok",
                        "message": "ok",
                        "step_path": str(step_path),
                        "topology_path": "topology.json",
                        "viewer_package_path": "viewer",
                    },
                )()

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            bridge = RecordingBridge()
            result = generate_room_cad(
                output,
                workspace_root=workspace,
                output_root="generated",
                cad_bridge=bridge,
            )
            source_path, step_path, _ = bridge.calls[0]
            source_root = (workspace / "temp" / "cad-source").resolve()
            step_root = (workspace / "generated" / "layout").resolve()
            self.assertTrue(source_path.resolve().is_relative_to(source_root))
            self.assertTrue(step_path.resolve().is_relative_to(step_root))
            artifact_name = step_path.parent.name
            self.assertRegex(artifact_name, re.compile(r"^room-[0-9a-f]{16}$"))
            self.assertEqual(
                Path(result["cad"]["step_path"]).parent.name,
                artifact_name,
            )


class ProjectLayoutAdmissionTests(unittest.TestCase):
    def test_fill_width_is_derived_when_omitted(self) -> None:
        items = bedroom_items()
        del items[1]["width"]
        output = plan_project_layout([{**bedroom_room(), "items": items}])
        wardrobe = next(
            item for item in output["rooms"][0]["items"]
            if item["id"] == "wardrobe"
        )
        self.assertEqual(wardrobe["width"], 2000)

    def test_fixed_item_still_requires_width(self) -> None:
        item = {"id": "fixed", "category": "wardrobe", "depth": 600,
                "height": 2400,
                "placement": {"mode": "wall", "host_wall": "north"}}
        with self.assertRaisesRegex(ValueError, "missing numeric field: width"):
            plan_project_layout([{**bedroom_room(), "items": [item]}])

    def test_overlapping_items_are_rejected_before_project_creation(self) -> None:
        items = [
            {"id": item_id, "category": "wardrobe", "width": 2000,
             "depth": 600, "height": 2400,
             "placement": {"mode": "wall", "host_wall": "north",
                           "offset_mm": offset}}
            for item_id, offset in (("left", 0), ("right", 1000))
        ]
        rooms = [{**bedroom_room(), "items": items}]
        with self.assertRaisesRegex(ValueError, "interferes with item"):
            plan_project_layout(rooms)
        with self.assertRaisesRegex(ValueError, "interferes with item"):
            ProjectLayout.from_source({"rooms": rooms})
        with self.assertRaisesRegex(ValueError, "interferes with item"):
            plan_room_scene(bedroom_room(), items)

    def test_out_of_room_item_is_rejected_before_project_creation(self) -> None:
        items = [{"id": "oversized", "category": "wardrobe", "width": 5000,
                  "depth": 600, "height": 2400,
                  "placement": {"mode": "wall", "host_wall": "north"}}]
        with self.assertRaisesRegex(ValueError, "inside the room"):
            plan_project_layout([{**bedroom_room(), "items": items}])


if __name__ == "__main__":
    unittest.main()
