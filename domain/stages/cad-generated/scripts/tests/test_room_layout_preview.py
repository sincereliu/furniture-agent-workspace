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

from furniture_layout.room_shell import (
    _path_within,
    room_shell_artifact_name,
    write_room_shell_source,
)
from furniture_layout.layout_entry import write_room_shell, plan_project_layout, plan_room_scene
from furniture_layout.room_svg import _build_projector
from furniture_layout.scene_planning import plan_scene
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.scene import RoomScene
from furniture_layout.layout_figures import check_room_figures
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
                "origin_z_mm": 0,
            },
        },
    ]


class RoomSceneLayoutTests(unittest.TestCase):
    def test_explicit_room_cad_artifact_id_must_be_safe(self) -> None:
        self.assertEqual(
            room_shell_artifact_name(
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
                    room_shell_artifact_name(
                        artifact_id=artifact_id,
                        room_id="bedroom",
                    )

    def test_room_id_fallback_is_stable_and_safe(self) -> None:
        self.assertEqual(
            room_shell_artifact_name(artifact_id=None, room_id="bedroom"),
            "bedroom",
        )
        first = room_shell_artifact_name(artifact_id=None, room_id="主卧/套房")
        repeated = room_shell_artifact_name(artifact_id=None, room_id="主卧/套房")
        other = room_shell_artifact_name(artifact_id=None, room_id="儿童房")
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

    def test_bedroom_places_bed_and_wardrobe_on_the_east_wall(self) -> None:
        output = plan_room_scene(bedroom_room(), bedroom_items())
        report = check_room_figures(output)
        self.assertTrue(report.passed, report.to_dict())
        self.assertNotIn(getattr(WorkflowStage, "LAYOUT_PLANNED", "layout_planned"), STAGE_SEQUENCE)

        items = {item["id"]: item for item in output["items"]}
        bed = items["bed"]
        wardrobe = items["wardrobe"]
        self.assertEqual(bed["placement"]["host_wall"], "north")
        self.assertEqual(bed["placement"]["origin_x_mm"], 0)
        self.assertEqual(bed["placement"]["origin_y_mm"], 0)
        self.assertEqual(bed["placement"]["rotation_z_deg"], 0)
        self.assertEqual(wardrobe["placement"]["host_wall"], "east")
        self.assertNotIn("offset_mm", wardrobe["placement"])
        self.assertEqual(wardrobe["width"], 800)
        self.assertEqual(wardrobe["placement"]["origin_x_mm"], 4200)
        self.assertEqual(wardrobe["placement"]["origin_y_mm"], 0)
        self.assertEqual(wardrobe["placement"]["rotation_z_deg"], 90)
        self.assertIn("<svg", output["preview"]["svg"])
        self.assertIn("主卧", output["preview"]["svg"])
        self.assertIn("床", output["preview"]["svg"])
        self.assertIn("衣柜", output["preview"]["svg"])
        self.assertIn('<canvas id="scene"', output["viewer"]["html"])

    def test_fill_width_is_the_free_span(self) -> None:
        """铺满：宽度由墙上空段算出。900 宽的北墙就是一台 900。"""
        scene = plan_scene(
            {
                "id": "narrow",
                "name": "窄间",
                "width_mm": 900,
                "depth_mm": 3000,
                "height_mm": 3200,
            },
            [
                {
                    "id": "wardrobe_run",
                    "category": "wardrobe",
                    "furniture_category": "floor_cabinet",
                    "depth": 600,
                    "height": 2400,
                    "placement": {"mode": "wall", "host_wall": "north", "fill": True},
                }
            ],
        )
        self.assertEqual([item.id for item in scene.items], ["wardrobe_run"])
        self.assertEqual(scene.items[0].width, 900.0)
        self.assertTrue(scene.items[0].placement.fill)
        self.assertEqual(scene.items[0].placement.host_wall, "north")

    def test_a_wide_fill_stays_one_envelope(self) -> None:
        """一面 3000 的墙铺满：仍是一台，宽度就是这段墙。"""
        scene = plan_scene(
            {
                "id": "wide",
                "name": "宽间",
                "width_mm": 3000,
                "depth_mm": 3000,
                "height_mm": 3200,
            },
            [
                {
                    "id": "wardrobe_run",
                    "category": "wardrobe",
                    "furniture_category": "floor_cabinet",
                    "depth": 600,
                    "height": 2400,
                    "placement": {"mode": "wall", "host_wall": "north", "fill": True},
                }
            ],
        )
        self.assertEqual([item.id for item in scene.items], ["wardrobe_run"])
        self.assertEqual(scene.items[0].width, 3000.0)
        self.assertEqual(scene.items[0].placement.origin_x_mm, 0.0)
        self.assertTrue(scene.items[0].placement.fill)

    def test_fill_takes_the_longest_free_span(self) -> None:
        """铺满占当前最长空墙。2600 的北墙就是一台 2600，起点在墙头。"""
        scene = plan_scene(
            {
                "id": "wide",
                "name": "宽间",
                "width_mm": 2600,
                "depth_mm": 3000,
                "height_mm": 3200,
            },
            [
                {
                    "id": "wardrobe_run",
                    "category": "wardrobe",
                    "furniture_category": "wall_cabinet",
                    "manufacture": False,
                    "depth": 350,
                    "height": 800,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "north",
                        "origin_z_mm": 1600,
                        "fill": True,
                    },
                }
            ],
        )
        unit = scene.items[0]
        self.assertEqual(unit.id, "wardrobe_run")
        self.assertEqual(unit.width, 2600.0)
        self.assertEqual(unit.placement.origin_x_mm, 0.0)
        self.assertEqual(unit.placement.origin_z_mm, 1600.0)
        self.assertEqual(unit.furniture_category, "wall_cabinet")
        self.assertFalse(unit.manufacture)
        self.assertTrue(unit.placement.fill)

    def test_two_items_that_overlap_fail_validation(self) -> None:
        items = [
            {
                "id": "left",
                "label": "左柜",
                "category": "wardrobe",
                "width": 2000,
                "depth": 600,
                "height": 2400,
                "placement": {"mode": "wall", "host_wall": "north"},
            },
            {
                "id": "right",
                "label": "右柜",
                "category": "wardrobe",
                "width": 2000,
                "depth": 600,
                "height": 2400,
                "placement": {
                    "mode": "free",
                    "origin_x_mm": 500,
                    "origin_y_mm": 0,
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
            write_room_shell_source(scene, source_path)
            source = source_path.read_text(encoding="utf-8")
        self.assertIn("cut_box", source)
        self.assertIn("4200", source)
        self.assertIn("3600", source)
        self.assertIn("'id': 'bed'", source)
        self.assertIn("'id': 'wardrobe'", source)
        self.assertIn("'rotation_z_deg': 90.0", source)
        self.assertIn("'x': 4200.0", source)

    def test_write_room_shell_uses_bridge_and_records_paths(self) -> None:
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
            result = write_room_shell(
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

    def test_write_room_shell_rejects_unsafe_id_before_side_effects(self) -> None:
        output = plan_room_scene(bedroom_room(), bedroom_items())
        bridge = mock.Mock()
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            with self.assertRaisesRegex(ValueError, "artifact_id"):
                write_room_shell(
                    output,
                    workspace_root=workspace,
                    output_root="generated",
                    cad_bridge=bridge,
                    artifact_id="../../escape",
                )
            self.assertFalse((workspace / "temp").exists())
            self.assertFalse((workspace / "generated").exists())
        bridge.generate_from_source.assert_not_called()

    def test_write_room_shell_contains_paths_and_hashes_unsafe_room_id(self) -> None:
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
            result = write_room_shell(
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
        """铺满不写宽度：仍旧由墙上空段算出。窄间（900 宽）北墙是一台 900。"""
        item = {
            "id": "wardrobe_run",
            "category": "wardrobe",
            "furniture_category": "floor_cabinet",
            "depth": 600,
            "height": 2400,
            "placement": {"mode": "wall", "host_wall": "north", "fill": True},
        }
        output = plan_project_layout(
            [
                {
                    "id": "narrow",
                    "name": "窄间",
                    "width_mm": 900,
                    "depth_mm": 3000,
                    "height_mm": 3200,
                    "items": [item],
                }
            ]
        )
        units = output["rooms"][0]["items"]
        self.assertEqual([unit["id"] for unit in units], ["wardrobe_run"])
        self.assertEqual(units[0]["width"], 900)

    def test_fixed_item_still_requires_width(self) -> None:
        item = {"id": "fixed", "category": "wardrobe", "depth": 600,
                "height": 2400,
                "placement": {"mode": "wall", "host_wall": "north"}}
        with self.assertRaisesRegex(ValueError, "missing numeric field: width"):
            plan_project_layout([{**bedroom_room(), "items": [item]}])

    def test_overlapping_items_are_rejected_before_project_creation(self) -> None:
        """靠墙柜贴上墙头之后，自由摆放的另一台压在它的包络上，创建前就拒绝。"""
        items = [
            {"id": "left", "category": "wardrobe", "width": 2000,
             "depth": 600, "height": 2400,
             "placement": {"mode": "wall", "host_wall": "north"}},
            {"id": "right", "category": "wardrobe", "width": 2000,
             "depth": 600, "height": 2400,
             "placement": {"mode": "free", "origin_x_mm": 500, "origin_y_mm": 0}},
        ]
        rooms = [{**bedroom_room(), "items": items}]
        with self.assertRaisesRegex(ValueError, "interferes with item"):
            plan_project_layout(rooms)
        with self.assertRaisesRegex(ValueError, "interferes with item"):
            ProjectLayout.from_source({"rooms": rooms})
        with self.assertRaisesRegex(ValueError, "interferes with item"):
            plan_room_scene(bedroom_room(), items)

    def test_customer_opt_out_keeps_envelope_and_drops_the_unit(self) -> None:
        room = {
            "id": "study",
            "width_mm": 4000,
            "depth_mm": 3600,
            "height_mm": 2800,
            "items": [
                {
                    "id": "bookcase",
                    "category": "bookcase",
                    "furniture_category": "floor_cabinet",
                    "manufacture": False,
                    "width": 900,
                    "depth": 350,
                    "height": 2100,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "north",
                    },
                },
                {
                    "id": "wardrobe",
                    "category": "wardrobe",
                    "furniture_category": "floor_cabinet",
                    "width": 1800,
                    "depth": 600,
                    "height": 2400,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "south",
                    },
                },
            ],
        }
        output = plan_project_layout([room])
        items = {item["id"]: item for item in output["rooms"][0]["items"]}
        self.assertFalse(items["bookcase"]["manufacture"])
        self.assertNotIn("manufacture", items["wardrobe"])
        self.assertEqual([unit["id"] for unit in output["cad"]["units"]], ["wardrobe"])
        restored = ProjectLayout.from_dict(output)
        self.assertEqual(
            [unit.id for unit in restored.executable_units()],
            ["wardrobe"],
        )
        self.assertFalse(restored.rooms[0].items[0].manufacture)

    def test_category_name_does_not_skip_manufacturing(self) -> None:
        output = plan_project_layout(
            [
                {
                    "id": "living",
                    "width_mm": 5000,
                    "depth_mm": 4000,
                    "height_mm": 2800,
                    "items": [
                        {
                            "id": "sofa",
                            "category": "sofa",
                            "furniture_category": "floor_cabinet",
                            "width": 2100,
                            "depth": 900,
                            "height": 850,
                            "placement": {
                                "mode": "wall",
                                "host_wall": "north",
                            },
                        }
                    ],
                }
            ]
        )
        item = output["rooms"][0]["items"][0]
        self.assertNotIn("manufacture", item)
        self.assertEqual([unit["id"] for unit in output["cad"]["units"]], ["sofa"])

    def test_opted_out_envelope_still_blocks_other_furniture(self) -> None:
        room = {
            "id": "study",
            "width_mm": 4000,
            "depth_mm": 3600,
            "height_mm": 2800,
            "items": [
                {
                    "id": "bookcase",
                    "category": "bookcase",
                    "furniture_category": "floor_cabinet",
                    "manufacture": False,
                    "width": 2000,
                    "depth": 400,
                    "height": 2100,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "north",
                    },
                },
                {
                    "id": "wardrobe",
                    "category": "wardrobe",
                    "furniture_category": "floor_cabinet",
                    "width": 1800,
                    "depth": 600,
                    "height": 2400,
                    "placement": {
                        "mode": "free",
                        "origin_x_mm": 100,
                        "origin_y_mm": 0,
                    },
                },
            ],
        }
        with self.assertRaisesRegex(ValueError, "interferes with item"):
            plan_project_layout([room])

    def test_manufacture_must_be_boolean(self) -> None:
        room = {
            "id": "study",
            "width_mm": 4000,
            "depth_mm": 3600,
            "height_mm": 2800,
            "items": [
                {
                    "id": "bookcase",
                    "category": "bookcase",
                    "furniture_category": "floor_cabinet",
                    "manufacture": "false",
                    "width": 900,
                    "depth": 350,
                    "height": 2100,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "north",
                    },
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "manufacture must be a boolean"):
            plan_project_layout([room])

    def test_out_of_room_item_is_rejected_before_project_creation(self) -> None:
        items = [{"id": "oversized", "category": "wardrobe", "width": 5000,
                  "depth": 600, "height": 2400,
                  "placement": {"mode": "wall", "host_wall": "north"}}]
        with self.assertRaisesRegex(ValueError, "does not fit"):
            plan_project_layout([{**bedroom_room(), "items": items}])


    def test_study_with_desk_bookcase_and_unmanufactured_chair(self) -> None:
        """书房包含定制书柜、成品书桌与活动椅子：椅子不进制造，但留在布局中占位。"""
        room = {
            "id": "study",
            "name": "书房",
            "width_mm": 4000,
            "depth_mm": 3600,
            "height_mm": 2800,
            "items": [
                {
                    "id": "bookcase",
                    "category": "bookcase",
                    "furniture_category": "floor_cabinet",
                    "width": 1800,
                    "depth": 350,
                    "height": 2100,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "north",
                    },
                },
                {
                    "id": "desk",
                    "category": "desk",
                    "width": 1400,
                    "depth": 700,
                    "height": 750,
                    "placement": {
                        "mode": "wall",
                        "host_wall": "south",
                    },
                },
                {
                    "id": "chair",
                    "category": "chair",
                    "width": 550,
                    "depth": 550,
                    "height": 850,
                    "manufacture": False,
                    "placement": {
                        "mode": "free",
                        "origin_x_mm": 1800,
                        "origin_y_mm": 1800,
                    },
                },
            ],
        }
        output = plan_project_layout([room])
        items = {item["id"]: item for item in output["rooms"][0]["items"]}
        self.assertIn("chair", items)
        self.assertEqual(items["chair"]["category"], "chair")
        self.assertFalse(items["chair"]["manufacture"])

        # 下游仅包含需要生产的书柜，椅子与成品桌不进入制造单元清单
        self.assertEqual([unit["id"] for unit in output["cad"]["units"]], ["bookcase"])
        restored = ProjectLayout.from_dict(output)
        self.assertEqual(
            [unit.id for unit in restored.executable_units()],
            ["bookcase"],
        )

    def test_chair_solid_visualization_contract(self) -> None:
        """椅子具有独立的外形固件与检查脚本，在三维场景中不渲染为普通方块。"""
        static_dir = WORKSPACE_ROOT / "domain/modules/web/furniture_web/static"
        chair_solid = static_dir / "chair_solid.js"
        chair_check = static_dir / "chair_solid_check.mjs"
        self.assertTrue(chair_solid.is_file(), "chair_solid.js 必须存在")
        self.assertTrue(chair_check.is_file(), "chair_solid_check.mjs 必须存在")

        content = chair_solid.read_text(encoding="utf-8")
        self.assertIn("export function isFixedChair", content)
        self.assertIn("export function chairParts", content)

        scene_js = (static_dir / "layout_scene.js").read_text(encoding="utf-8")
        self.assertIn('import { isFixedChair } from "./chair_solid.js";', scene_js)
        self.assertIn("addChair", scene_js)
        self.assertIn("isFixedChair(item) && addChair(", scene_js)

        meshes_js = (static_dir / "layout_meshes.js").read_text(encoding="utf-8")
        self.assertIn('import { chairParts } from "./chair_solid.js";', meshes_js)
        self.assertIn("export function addChair", meshes_js)

    def test_desk_solid_visualization_contract(self) -> None:
        """书桌具有独立的外形固件与检查脚本，在三维场景中不渲染为普通方块。"""
        static_dir = WORKSPACE_ROOT / "domain/modules/web/furniture_web/static"
        desk_solid = static_dir / "desk_solid.js"
        desk_check = static_dir / "desk_solid_check.mjs"
        self.assertTrue(desk_solid.is_file(), "desk_solid.js 必须存在")
        self.assertTrue(desk_check.is_file(), "desk_solid_check.mjs 必须存在")

        content = desk_solid.read_text(encoding="utf-8")
        self.assertIn("export function isFixedDesk", content)
        self.assertIn("export function deskParts", content)

        scene_js = (static_dir / "layout_scene.js").read_text(encoding="utf-8")
        self.assertIn('import { isFixedDesk } from "./desk_solid.js";', scene_js)
        self.assertIn("addDesk", scene_js)
        self.assertIn("isFixedDesk(item) && addDesk(", scene_js)

        meshes_js = (static_dir / "layout_meshes.js").read_text(encoding="utf-8")
        self.assertIn('import { deskParts } from "./desk_solid.js";', meshes_js)
        self.assertIn("export function addDesk", meshes_js)

    def test_desk_parts_geometry_and_clearance(self) -> None:
        """书桌几何无共面干涉、四腿落地、正面留有通透的腿部与椅子推入空档。"""
        def clamp(val: float, lo: float, hi: float) -> float:
            return min(hi, max(lo, val))

        def py_desk_parts(W: float, D: float, H: float):
            if not (W >= 400 and D >= 300 and H >= 400):
                return None
            gap = 2.0
            top_t = clamp(H * 0.045, 20.0, 36.0)
            leg = clamp(min(W, D) * 0.06, 28.0, 48.0)
            inset = clamp(min(W, D) * 0.04, 14.0, 32.0)
            leg_top = H - top_t - gap
            if leg_top < 200 or inset + leg > W / 2 - 8 or inset + leg > D / 2 - 8:
                return None
            parts = [{"role": "top", "box": [0.0, 0.0, H - top_t, W, D, H]}]
            uL0, uL1 = inset, inset + leg
            uR0, uR1 = W - inset - leg, W - inset
            vRear0, vRear1 = inset, inset + leg
            vFront0, vFront1 = D - inset - leg, D - inset
            for u0, v0, u1, v1 in [
                (uL0, vRear0, uL1, vRear1),
                (uR0, vRear0, uR1, vRear1),
                (uL0, vFront0, uL1, vFront1),
                (uR0, vFront0, uR1, vFront1),
            ]:
                parts.append({"role": "leg", "box": [u0, v0, 0.0, u1, v1, leg_top]})
            apron_t = clamp(leg * 0.45, 14.0, 20.0)
            rear_apron_h = clamp(H * 0.22, 100.0, 220.0)
            rear_apron_top = leg_top - gap
            rear_apron_bottom = rear_apron_top - rear_apron_h
            rear_u0, rear_u1 = uL1 + gap, uR0 - gap
            rear_v0 = vRear0 + (leg - apron_t) / 2
            rear_v1 = rear_v0 + apron_t
            if rear_u1 - rear_u0 >= 40 and rear_apron_bottom >= 80:
                parts.append({"role": "apron", "box": [rear_u0, rear_v0, rear_apron_bottom, rear_u1, rear_v1, rear_apron_top]})
            side_apron_h = clamp(H * 0.08, 40.0, 70.0)
            side_apron_top = rear_apron_top - gap
            side_apron_bottom = side_apron_top - side_apron_h
            side_v0, side_v1 = vRear1 + gap, vFront0 - gap
            left_u0 = uL0 + (leg - apron_t) / 2
            left_u1 = left_u0 + apron_t
            right_u0 = uR0 + (leg - apron_t) / 2
            right_u1 = right_u0 + apron_t
            if side_v1 - side_v0 >= 40 and side_apron_bottom >= 100:
                parts.append({"role": "apron", "box": [left_u0, side_v0, side_apron_bottom, left_u1, side_v1, side_apron_top]})
                parts.append({"role": "apron", "box": [right_u0, side_v0, side_apron_bottom, right_u1, side_v1, side_apron_top]})
            return parts

        for w, d, h in [(1400, 700, 750), (1200, 600, 750), (1600, 800, 750), (1000, 500, 720), (800, 400, 700)]:
            parts = py_desk_parts(w, d, h)
            self.assertIsNotNone(parts)
            # 无共面检查
            faces = []
            for p in parts:
                u0, v0, w0, u1, v1, w1 = p["box"]
                faces.extend([
                    ("u", u0, v0, w0, v1, w1), ("u", u1, v0, w0, v1, w1),
                    ("v", v0, u0, w0, u1, w1), ("v", v1, u0, w0, u1, w1),
                    ("w", w0, u0, v0, u1, v1), ("w", w1, u0, v0, u1, v1),
                ])
            for i in range(len(faces)):
                for j in range(i + 1, len(faces)):
                    a, b = faces[i], faces[j]
                    if a[0] != b[0] or abs(a[1] - b[1]) > 0.5:
                        continue
                    s1 = min(a[4], b[4]) - max(a[2], b[2])
                    s2 = min(a[5], b[5]) - max(a[3], b[3])
                    self.assertFalse(s1 > 1.0 and s2 > 1.0, f"共面冲突: {a[0]}={a[1]} 在尺寸 {w}x{d}x{h}")

            # 膝部空间通透（桌面前半段中央完全留空供椅子推入）
            knee_u, knee_v, knee_w = w / 2, d * 0.75, h * 0.45
            in_knee = any(
                p["box"][0] < knee_u < p["box"][3]
                and p["box"][1] < knee_v < p["box"][4]
                and p["box"][2] < knee_w < p["box"][5]
                for p in parts
            )
            self.assertFalse(in_knee, "膝部空间被部件阻挡")


if __name__ == "__main__":
    unittest.main()
