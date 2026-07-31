from __future__ import annotations

from copy import deepcopy
import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_state import WorkflowStage


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


class RoomLayoutPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.orchestrator = FurnitureOrchestrator(workspace_root=WORKSPACE_ROOT)

    def test_layout_stage_emits_room_position_footprint_and_svg(self) -> None:
        result = self.orchestrator.execute_spec(
            "主卧衣柜",
            wardrobe_spec(),
            through_stage=WorkflowStage.LAYOUT_PLANNED,
        )

        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.LAYOUT_PLANNED,
        )
        self.assertTrue(
            result.revision.is_stage_approved(WorkflowStage.LAYOUT_PLANNED)
        )
        output = result.revision.stage_outputs["layout_planned"]
        room_placement = output["room_placement"]
        placement = room_placement["placement"]
        self.assertEqual(placement["host_wall"], "south")
        self.assertEqual(placement["origin_x_mm"], 500)
        self.assertEqual(placement["origin_y_mm"], 0)
        self.assertEqual(placement["rotation_z_deg"], 0)
        self.assertEqual(
            room_placement["furniture_footprint"],
            [
                {"x_mm": 500.0, "y_mm": 0.0},
                {"x_mm": 2300.0, "y_mm": 0.0},
                {"x_mm": 2300.0, "y_mm": 600.0},
                {"x_mm": 500.0, "y_mm": 600.0},
            ],
        )
        self.assertEqual(room_placement["clearances_mm"]["north"], 3000)
        self.assertEqual(output["preview"]["media_type"], "image/svg+xml")
        self.assertIn("<svg", output["preview"]["svg"])
        self.assertIn("主卧衣柜", output["preview"]["svg"])
        self.assertEqual(
            ElementTree.fromstring(output["preview"]["svg"]).tag,
            "{http://www.w3.org/2000/svg}svg",
        )
        self.assertTrue(all(report.passed for report in result.revision.validations))

    def test_north_wall_position_derives_room_transform(self) -> None:
        spec = wardrobe_spec(wall="north", offset_mm=400)
        spec["room"]["obstacles"] = []
        result = self.orchestrator.execute_spec(
            "北墙衣柜",
            spec,
            through_stage=WorkflowStage.LAYOUT_PLANNED,
        )

        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.LAYOUT_PLANNED,
        )
        placement = result.revision.stage_outputs["layout_planned"][
            "room_placement"
        ]["placement"]
        self.assertEqual(placement["origin_x_mm"], 3800)
        self.assertEqual(placement["origin_y_mm"], 3600)
        self.assertEqual(placement["rotation_z_deg"], 180)
        self.assertEqual(
            result.revision.stage_outputs["layout_planned"]["room_placement"][
                "clearances_mm"
            ]["north"],
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
        result = self.orchestrator.execute_spec(
            "自由摆放衣柜",
            spec,
            through_stage=WorkflowStage.LAYOUT_PLANNED,
        )

        footprint = result.revision.stage_outputs["layout_planned"][
            "room_placement"
        ]["furniture_footprint"]
        self.assertEqual(
            footprint,
            [
                {"x_mm": 1000.0, "y_mm": 1000.0},
                {"x_mm": 1000.0, "y_mm": 2800.0},
                {"x_mm": 400.0, "y_mm": 2800.0},
                {"x_mm": 400.0, "y_mm": 1000.0},
            ],
        )
        self.assertEqual(
            result.revision.workflow.current,
            WorkflowStage.LAYOUT_PLANNED,
        )

    def test_layout_rejects_furniture_outside_room(self) -> None:
        result = self.orchestrator.execute_spec(
            "越界衣柜",
            wardrobe_spec(offset_mm=3000),
            through_stage=WorkflowStage.LAYOUT_PLANNED,
        )

        self.assertEqual(result.revision.workflow.current, WorkflowStage.FAILED)
        self.assertIn(
            "FURNITURE_OUTSIDE_ROOM",
            {issue.code for issue in result.revision.validations[-1].issues},
        )

    def test_layout_rejects_opening_and_obstacle_collisions(self) -> None:
        door_spec = wardrobe_spec(offset_mm=2200)
        door_result = self.orchestrator.execute_spec(
            "遮门衣柜",
            door_spec,
            through_stage=WorkflowStage.LAYOUT_PLANNED,
        )
        self.assertIn(
            "FURNITURE_OPENING_COLLISION",
            {issue.code for issue in door_result.revision.validations[-1].issues},
        )

        free_door_spec = wardrobe_spec()
        free_door_spec["placement"] = {
            "mode": "free",
            "origin_x_mm": 2200,
            "origin_y_mm": 0,
            "origin_z_mm": 0,
            "rotation_z_deg": 0,
        }
        free_door_result = self.orchestrator.execute_spec(
            "自由摆放遮门衣柜",
            free_door_spec,
            through_stage=WorkflowStage.LAYOUT_PLANNED,
        )
        self.assertIn(
            "FURNITURE_OPENING_COLLISION",
            {
                issue.code
                for issue in free_door_result.revision.validations[-1].issues
            },
        )

        obstacle_spec = wardrobe_spec()
        obstacle_spec["room"]["obstacles"] = [
            {
                "id": "low_column",
                "kind": "column",
                "x_mm": 1000,
                "y_mm": 200,
                "z_mm": 0,
                "width_mm": 300,
                "depth_mm": 300,
                "height_mm": 2800,
            }
        ]
        obstacle_result = self.orchestrator.execute_spec(
            "撞柱衣柜",
            obstacle_spec,
            through_stage=WorkflowStage.LAYOUT_PLANNED,
        )
        self.assertIn(
            "FURNITURE_OBSTACLE_COLLISION",
            {
                issue.code
                for issue in obstacle_result.revision.validations[-1].issues
            },
        )

    def test_revised_position_must_refresh_transform_and_preview(self) -> None:
        result = self.orchestrator.execute_spec(
            "可修改衣柜位置",
            wardrobe_spec(),
            through_stage=WorkflowStage.LAYOUT_PLANNED,
        )
        edited = deepcopy(result.revision.stage_outputs["layout_planned"])
        edited["room_placement"]["placement"]["offset_mm"] = 700
        revision = self.orchestrator.revise_stage_output(
            result.project,
            WorkflowStage.LAYOUT_PLANNED,
            edited,
        )

        self.orchestrator.confirm_stage(
            result.project,
            WorkflowStage.LAYOUT_PLANNED,
        )

        self.assertEqual(revision.workflow.current, WorkflowStage.FAILED)
        issue_codes = {issue.code for issue in revision.validations[-1].issues}
        self.assertIn("WALL_PLACEMENT_TRANSFORM_MISMATCH", issue_codes)
        self.assertIn("LAYOUT_PREVIEW_MISMATCH", issue_codes)


if __name__ == "__main__":
    unittest.main()
