"""Moving a wall item into the room preserves the wall-derived orientation."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

WORKSPACE = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(WORKSPACE / "domain/stages/cad-generated/scripts"))
from runtime_paths import bootstrap_runtime_paths
bootstrap_runtime_paths(WORKSPACE)

sys.path.insert(0, str(WORKSPACE / "domain/stages/cad-generated/scripts/tests"))
from layout_edit_test_support import pose
from furniture_layout.project_edit import apply_layout_edit
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.scene_edit import apply_scene_edit
from furniture_layout.scene_planning import plan_scene
from furniture_layout.scene_store import load_scene, save_scene


def wall_layout(wall, category="sofa"):
    return ProjectLayout.from_source({"rooms": [{
        "id": "study", "width_mm": 3600, "depth_mm": 3000, "height_mm": 2800,
        "items": [{"id": "seat", "category": category, "width": 900,
                   "depth": 500, "height": 800, "manufacture": False,
                   "placement": {"mode": "wall", "host_wall": wall,
                                 "origin_z_mm": 100}}],
    }]})


class WallDetachRotationTests(unittest.TestCase):
    def test_project_and_standalone_move_preserve_footprint_and_saved_rotation(self):
        for wall, delta in (("north", (700, 120)), ("east", (-120, 700)),
                            ("south", (-700, -120)), ("west", (120, -700))):
            for category in ("sofa", "chair"):
                with self.subTest(wall=wall, category=category), tempfile.TemporaryDirectory() as directory:
                    layout = wall_layout(wall, category)
                    before = layout.rooms[0].items[0]
                    op = pose(layout,"seat",mode="free",
                              origin_x_mm=before.placement.origin_x_mm+delta[0],
                              origin_y_mm=before.placement.origin_y_mm+delta[1])
                    expected = tuple((x + delta[0], y + delta[1]) for x, y in before.footprint)
                    edited = apply_layout_edit(layout, op)
                    reloaded = ProjectLayout.from_dict(edited.to_dict())
                    edited_scene=apply_scene_edit(layout.rooms[0],op)
                    save_scene("study",edited_scene,root=directory)
                    standalone=load_scene("study",root=directory)
                    for item in (reloaded.rooms[0].items[0], standalone.items[0]):
                        self.assertEqual(item.placement.mode, "free")
                        self.assertEqual(item.placement.rotation_z_deg, before.placement.rotation_z_deg)
                        self.assertEqual(item.placement.origin_z_mm, 100)
                        self.assertEqual(item.footprint, expected)
                    self.assertEqual(layout.rooms[0].items[0], before)

    def test_explicit_rotation_still_overrides_wall_orientation(self):
        layout = wall_layout("east")
        result=apply_layout_edit(layout,pose(layout,"seat",mode="free",origin_x_mm=1800,origin_y_mm=1600,rotation_z_deg=15))
        moved=apply_layout_edit(result,pose(result,"seat",origin_x_mm=1900))
        self.assertEqual(moved.rooms[0].items[0].placement.rotation_z_deg, 15)

    def test_project_endpoint_saves_and_reloads_detached_sofa(self):
        import server
        from starlette.requests import Request
        from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
        from furniture_workflow.workflow_store import JsonProjectStore

        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(os.environ, {
            "FURNITURE_PREVIEW_BROWSER": "0", server.LAYOUT_EDIT_ENV: "1",
        }), mock.patch.object(server, "STORE_ROOT", Path(directory)):
            store = JsonProjectStore(directory)
            layout = wall_layout("east")
            project = FurnitureOrchestrator(workspace_root=WORKSPACE, project_store=store).create_project("study", layout)
            before = asyncio.run(server.project_layout(project.id))
            request = Request({"type": "http", "client": ("127.0.0.1", 1234), "headers": []})
            result = asyncio.run(server.edit_project_layout_endpoint(project.id,
                server.ProjectLayoutEditRequest(**pose(layout,"seat",mode="free",origin_x_mm=3480,origin_y_mm=700),expected_version=before["version"]), request))
            self.assertNotEqual(result["version"], before["version"])
            item = store.load(project.id).latest.layout.rooms[0].items[0]
            self.assertEqual(item.placement.rotation_z_deg, 90)
            self.assertEqual((item.placement.origin_x_mm, item.placement.origin_y_mm), (3480, 700))


if __name__ == "__main__":
    unittest.main()
