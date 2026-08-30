from __future__ import annotations

from copy import deepcopy
from math import hypot
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_workflow.input_adapter import (
    layout_stage_input,
    panel_stage_input,
    stage_inputs_from_spec,
)
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import STAGE_SEQUENCE, WorkflowStage
from furniture_layout.layout_pipeline import plan_layout_stage
from furniture_layout.layout_preview import _build_projector
from furniture_layout.layout_spec import LayoutSpec
from furniture_layout.validation import validate_layout_output


def wardrobe_spec(
    *,
    wall: str = "south",
    offset_mm: float = 500,
) -> dict:
    return {
        "type": "floor_cabinet",
        "width": 1800,
        "depth": 600,
        "height": 2400,
        "room": {
            "id": "bedroom",
            "name": "主卧",
            "width_mm": 4200,
            "depth_mm": 3600,
            "height_mm": 2800,
            "openings": [
                {
                    "id": "bedroom_door",
                    "kind": "door",
                    "wall": "south",
                    "offset_mm": 3000,
                    "width_mm": 900,
                    "height_mm": 2100,
                }
            ],
            "obstacles": [
                {
                    "id": "column",
                    "kind": "column",
                    "x_mm": 3700,
                    "y_mm": 2900,
                    "z_mm": 0,
                    "width_mm": 300,
                    "depth_mm": 400,
                    "height_mm": 2800,
                }
            ],
        },
        "placement": {
            "mode": "wall",
            "host_wall": wall,
            "offset_mm": offset_mm,
            "origin_z_mm": 0,
        },
    }


def run_independent_layout(name: str, spec: dict):
    orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)
    intent = orchestrator.intent_from_spec(spec).confirm()
    stage_inputs = stage_inputs_from_spec(spec)
    panel_parameters = panel_stage_input(stage_inputs).get("parameters", {})
    options = {
        key: panel_parameters[key]
        for key in ("shelf_count", "n_doors", "door_count")
        if key in panel_parameters
    }
    context = layout_stage_input(stage_inputs)
    layout_spec = LayoutSpec.from_intent(intent, options)
    output = plan_layout_stage(
        layout_spec,
        room=context.get("room"),
        placement=context.get("placement"),
        furniture_label=name,
    )
    return layout_spec, output, validate_layout_output(layout_spec, output)


class RoomLayoutPreviewTests(unittest.TestCase):
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

    def test_missing_room_context_uses_visible_default_bedroom(self) -> None:
        _, output, report = run_independent_layout(
            "1600衣柜",
            {
                "type": "floor_cabinet",
                "width": 1600,
                "depth": 600,
                "height": 2400,
            },
        )

        self.assertEqual(
            output["layout_context"],
            {
                "room_source": "default_bedroom",
                "placement_source": "default_north_wall_centered",
            },
        )
        self.assertEqual(
            output["room_placement"]["room"],
            {
                "id": "default_bedroom",
                "name": "默认卧室（系统假设）",
                "width_mm": 4200.0,
                "depth_mm": 3600.0,
                "height_mm": 2800.0,
                "openings": [],
                "obstacles": [],
            },
        )
        self.assertEqual(
            output["room_placement"]["placement"]["origin_x_mm"],
            1300,
        )
        self.assertEqual(
            output["room_placement"]["placement"]["host_wall"],
            "north",
        )
        self.assertEqual(
            output["preview"]["view_kind"],
            "perspective_envelope",
        )
        self.assertEqual(output["viewer"]["media_type"], "text/html")
        self.assertEqual(
            output["viewer"]["view_kind"],
            "interactive_orbit_envelope",
        )
        self.assertIn("drag_orbit", output["viewer"]["controls"])
        self.assertIn('data-view="top"', output["viewer"]["html"])
        self.assertIn('addEventListener("pointermove"', output["viewer"]["html"])
        self.assertIn('addEventListener("wheel"', output["viewer"]["html"])
        self.assertIn("透明为房间", output["preview"]["svg"])
        self.assertIn("默认卧室（系统假设）", output["preview"]["svg"])
        self.assertTrue(report.passed)

    def test_missing_placement_centers_furniture_in_provided_room(self) -> None:
        spec = wardrobe_spec()
        del spec["placement"]
        _, output, report = run_independent_layout(
            "主卧衣柜",
            spec,
        )

        self.assertTrue(report.passed)
        self.assertEqual(output["layout_context"]["room_source"], "provided")
        self.assertEqual(
            output["layout_context"]["placement_source"],
            "default_north_wall_centered",
        )
        self.assertEqual(
            output["room_placement"]["placement"]["origin_x_mm"],
            1200,
        )

    def test_wall_cabinet_default_placement_uses_confirmed_mounting_height(
        self,
    ) -> None:
        _, output, report = run_independent_layout(
            "吊柜",
            {
                "type": "wall_cabinet",
                "width": 800,
                "depth": 350,
                "height": 900,
                "mount_mode": "free_height",
                "mounting_height": 1800,
            },
        )

        self.assertTrue(report.passed)
        self.assertEqual(
            output["room_placement"]["placement"]["origin_z_mm"],
            1800,
        )
        self.assertEqual(
            output["room_placement"]["clearances_mm"]["floor"],
            1800,
        )

    def test_wall_cabinet_flush_ceiling_placement_uses_room_height(self) -> None:
        _, output, report = run_independent_layout(
            "到顶吊柜",
            {
                "type": "wall_cabinet",
                "width": 800,
                "depth": 350,
                "height": 900,
                "mount_mode": "flush_ceiling",
            },
        )

        self.assertTrue(report.passed)
        # 默认卧室层高 2800，贴顶 → 底边 = 2800 - 900 = 1900
        self.assertEqual(
            output["room_placement"]["placement"]["origin_z_mm"],
            1900,
        )

    def test_independent_layout_emits_room_position_footprint_and_svg(self) -> None:
        _, output, report = run_independent_layout(
            "主卧衣柜",
            wardrobe_spec(),
        )

        self.assertNotIn(WorkflowStage.LAYOUT_PLANNED, STAGE_SEQUENCE)
        room_placement = output["room_placement"]
        placement = room_placement["placement"]
        self.assertEqual(placement["host_wall"], "south")
        self.assertEqual(placement["origin_x_mm"], 3700)
        self.assertEqual(placement["origin_y_mm"], 3600)
        self.assertEqual(placement["rotation_z_deg"], 180)
        self.assertEqual(
            room_placement["furniture_footprint"],
            [
                {"x_mm": 3700.0, "y_mm": 3600.0},
                {"x_mm": 1900.0, "y_mm": 3600.0},
                {"x_mm": 1900.0, "y_mm": 3000.0},
                {"x_mm": 3700.0, "y_mm": 3000.0},
            ],
        )
        self.assertEqual(room_placement["clearances_mm"]["north"], 3000)
        self.assertEqual(output["preview"]["media_type"], "image/svg+xml")
        self.assertEqual(
            output["preview"]["view_kind"],
            "perspective_envelope",
        )
        self.assertIn("<svg", output["preview"]["svg"])
        self.assertIn("三维包络预览", output["preview"]["svg"])
        self.assertIn("主卧衣柜", output["preview"]["svg"])
        self.assertEqual(
            ElementTree.fromstring(output["preview"]["svg"]).tag,
            "{http://www.w3.org/2000/svg}svg",
        )
        self.assertTrue(report.passed)

    def test_north_wall_position_derives_room_transform(self) -> None:
        spec = wardrobe_spec(wall="north", offset_mm=400)
        spec["room"]["obstacles"] = []
        _, output, report = run_independent_layout(
            "北墙衣柜",
            spec,
        )

        self.assertTrue(report.passed)
        placement = output["room_placement"]["placement"]
        self.assertEqual(placement["origin_x_mm"], 400)
        self.assertEqual(placement["origin_y_mm"], 0)
        self.assertEqual(placement["rotation_z_deg"], 0)
        self.assertEqual(
            output["room_placement"]["clearances_mm"]["north"],
            0,
        )

    def test_free_position_supports_rotation(self) -> None:
        spec = wardrobe_spec()
        spec["placement"] = {
            "mode": "free",
            "origin_x_mm": 1000,
            "origin_y_mm": 1000,
            "origin_z_mm": 0,
            "rotation_z_deg": 90,
        }
        _, output, report = run_independent_layout(
            "自由摆放衣柜",
            spec,
        )

        self.assertTrue(report.passed)
        footprint = output["room_placement"]["furniture_footprint"]
        self.assertEqual(
            footprint,
            [
                {"x_mm": 1000.0, "y_mm": 1000.0},
                {"x_mm": 1000.0, "y_mm": 2800.0},
                {"x_mm": 400.0, "y_mm": 2800.0},
                {"x_mm": 400.0, "y_mm": 1000.0},
            ],
        )
    def test_layout_rejects_furniture_outside_room(self) -> None:
        _, _, report = run_independent_layout(
            "越界衣柜",
            wardrobe_spec(offset_mm=3000),
        )

        self.assertFalse(report.passed)
        self.assertIn(
            "FURNITURE_OUTSIDE_ROOM",
            {issue.code for issue in report.issues},
        )

    def test_layout_rejects_opening_and_obstacle_collisions(self) -> None:
        door_spec = wardrobe_spec(offset_mm=2200)
        _, _, door_report = run_independent_layout(
            "遮门衣柜",
            door_spec,
        )
        self.assertIn(
            "FURNITURE_OPENING_COLLISION",
            {issue.code for issue in door_report.issues},
        )

        free_door_spec = wardrobe_spec()
        free_door_spec["placement"] = {
            "mode": "free",
            "origin_x_mm": 0,
            "origin_y_mm": 3000,
            "origin_z_mm": 0,
            "rotation_z_deg": 0,
        }
        _, _, free_door_report = run_independent_layout(
            "自由摆放遮门衣柜",
            free_door_spec,
        )
        self.assertIn(
            "FURNITURE_OPENING_COLLISION",
            {
                issue.code for issue in free_door_report.issues
            },
        )

        obstacle_spec = wardrobe_spec()
        obstacle_spec["room"]["obstacles"] = [
            {
                "id": "low_column",
                "kind": "column",
                "x_mm": 2000,
                "y_mm": 3200,
                "z_mm": 0,
                "width_mm": 300,
                "depth_mm": 300,
                "height_mm": 2800,
            }
        ]
        _, _, obstacle_report = run_independent_layout(
            "撞柱衣柜",
            obstacle_spec,
        )
        self.assertIn(
            "FURNITURE_OBSTACLE_COLLISION",
            {
                issue.code for issue in obstacle_report.issues
            },
        )

    def test_revised_position_must_refresh_transform_and_preview(self) -> None:
        layout_spec, output, report = run_independent_layout(
            "可修改衣柜位置",
            wardrobe_spec(),
        )
        self.assertTrue(report.passed)
        edited = deepcopy(output)
        edited["room_placement"]["placement"]["offset_mm"] = 700
        edited_report = validate_layout_output(layout_spec, edited)

        self.assertFalse(edited_report.passed)
        issue_codes = {issue.code for issue in edited_report.issues}
        self.assertIn("WALL_PLACEMENT_TRANSFORM_MISMATCH", issue_codes)
        self.assertIn("LAYOUT_PREVIEW_MISMATCH", issue_codes)
        self.assertIn("LAYOUT_VIEWER_MISMATCH", issue_codes)


if __name__ == "__main__":
    unittest.main()
