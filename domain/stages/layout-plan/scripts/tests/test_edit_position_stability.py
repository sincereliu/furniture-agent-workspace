"""Editing one item must not repack the other fixed-width wall envelopes."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(WORKSPACE_ROOT / "domain/stages/cad-generated/scripts"))
from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

sys.path.insert(0, str(WORKSPACE_ROOT / "domain/stages/cad-generated/scripts/tests"))

from furniture_layout.project_edit import apply_layout_edit
from layout_edit_test_support import pose, planning_source
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.scene_planning import plan_scene
from furniture_layout.validation import admit_scene


def study_layout() -> ProjectLayout:
    return ProjectLayout.from_source({"rooms": [{
        "id": "study", "width_mm": 3600, "depth_mm": 3000,
        "height_mm": 2800, "items": [
            {"id": "chair", "category": "chair", "width": 500,
             "depth": 500, "height": 900, "manufacture": False,
             "placement": {"mode": "free", "origin_x_mm": 0,
                           "origin_y_mm": 2500}},
            {"id": "bookcase", "category": "bookcase", "width": 2200,
             "depth": 380, "height": 2400,
             "furniture_category": "floor_cabinet",
             "placement": {"mode": "wall", "host_wall": "west"}},
        ],
    }]})


class EditPositionStabilityTests(unittest.TestCase):
    def test_fixed_wall_positions_are_stable_on_all_four_walls(self):
        for wall, origin in (
            ("north", (0, 0)), ("east", (3100, 0)),
            ("south", (3100, 2500)), ("west", (0, 2500)),
        ):
            with self.subTest(wall=wall):
                source = study_layout()
                request = planning_source(source.rooms[0])
                request["items"][0]["placement"].update(
                    origin_x_mm=origin[0], origin_y_mm=origin[1],
                )
                request["items"][1]["placement"]["host_wall"] = wall
                before = replace(source, rooms=(plan_scene(request["room"], request["items"]),))
                edited = apply_layout_edit(before, pose(before, "chair", origin_x_mm=1500, origin_y_mm=1500))
                self.assertEqual(edited.rooms[0].items[1], before.rooms[0].items[1])

    def test_moving_chair_preserves_bookcase_through_reload_and_confirmation(self):
        before = study_layout()
        cabinet = before.rooms[0].items[1]
        self.assertEqual(cabinet.placement.origin_y_mm, 2500)
        edited = apply_layout_edit(before, pose(before, "chair", origin_x_mm=1000, origin_y_mm=1500))
        self.assertEqual(edited.rooms[0].items[1], cabinet)
        self.assertEqual(before.rooms[0].items[0].placement.origin_x_mm, 0)
        reloaded = ProjectLayout.from_dict(edited.to_dict())
        self.assertTrue(admit_scene(reloaded.rooms[0]).passed)
        self.assertEqual(reloaded.confirm().rooms[0].items[1], cabinet)
        again = apply_layout_edit(reloaded, pose(reloaded, "chair", origin_x_mm=1100))
        self.assertEqual(again.rooms[0].items[1], cabinet)

    def test_collision_with_saved_bookcase_is_rejected_without_repacking(self):
        with self.assertRaises(ValueError):
            apply_layout_edit(study_layout(), pose(study_layout(), "chair", origin_x_mm=0, origin_y_mm=1500))

    def test_preserving_along_wall_position_does_not_accept_invalid_wall_geometry(self):
        scene = study_layout().rooms[0]
        chair, cabinet = scene.items
        for changes in (
            {"origin_x_mm": 20}, {"rotation_z_deg": 0}, {"origin_y_mm": 2000},
        ):
            with self.subTest(changes=changes):
                invalid = replace(cabinet, placement=replace(cabinet.placement, **changes))
                self.assertFalse(admit_scene(replace(scene, items=(chair, invalid))).passed)

    def test_resize_and_height_edit_preserve_wall_start(self):
        before = study_layout()
        placement = before.rooms[0].items[1].placement
        moved = apply_layout_edit(before, pose(before, "chair", origin_x_mm=1000, origin_y_mm=1500))
        for operation in (
            {"op": "resize", "width": 2100},
            pose(moved,"bookcase",origin_z_mm=100),
        ):
            with self.subTest(operation=operation):
                edited = apply_layout_edit(moved, {"item_id": "bookcase", **operation})
                actual = edited.rooms[0].items[1].placement
                self.assertEqual((actual.origin_x_mm, actual.origin_y_mm),
                                 (placement.origin_x_mm, placement.origin_y_mm))
                self.assertTrue(admit_scene(edited.rooms[0]).passed)

    def test_project_endpoint_saves_and_reloads_without_moving_bookcase(self):
        import server
        from starlette.requests import Request
        from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
        from furniture_workflow.workflow_store import JsonProjectStore

        with tempfile.TemporaryDirectory(prefix="edit-stability-") as directory, \
                mock.patch.dict(os.environ, {"FURNITURE_PREVIEW_BROWSER": "0"}), \
                mock.patch.object(server, "STORE_ROOT", Path(directory)):
            store = JsonProjectStore(directory)
            project = FurnitureOrchestrator(
                workspace_root=WORKSPACE_ROOT, project_store=store,
            ).create_project("书房", study_layout())
            before = asyncio.run(server.project_layout(project.id))
            request = Request({"type": "http", "client": ("127.0.0.1", 1234), "headers": []})
            server.enable_local_layout_edit()
            after = asyncio.run(server.edit_project_layout_endpoint(
                project.id,
                server.ProjectLayoutEditRequest(
                    **pose(study_layout(),"chair",origin_x_mm=1000,origin_y_mm=1500), expected_version=before["version"],
                ),
                request,
            ))
            self.assertNotEqual(after["version"], before["version"])
            self.assertEqual(after["rooms"][0]["scene"]["items"][1],
                             before["rooms"][0]["scene"]["items"][1])
            self.assertEqual(store.load(project.id).latest.layout.rooms[0].items[1],
                             study_layout().rooms[0].items[1])


if __name__ == "__main__":
    unittest.main()
