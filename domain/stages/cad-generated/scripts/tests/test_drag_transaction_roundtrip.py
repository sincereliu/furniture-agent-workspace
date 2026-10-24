"""Actual JS gesture output must survive Python admission, save, reload and undo."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

WORKSPACE = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(WORKSPACE / "domain/stages/cad-generated/scripts"))
from runtime_paths import bootstrap_runtime_paths
bootstrap_runtime_paths(WORKSPACE)

import server
from fake_request_support import local_request
from furniture_layout.project_edit import apply_layout_edit
from furniture_layout.project_layout import ProjectLayout
from furniture_layout.scene_edit import apply_scene_edit
from layout_edit_test_support import pose
from furniture_layout.scene_planning import plan_scene
from furniture_layout.room_page import room_page_payload
from furniture_layout.scene_store import load_scene, save_scene
from furniture_workflow.project_layout_edit import undo_layout_edit
from furniture_workflow.workflow_orchestrator import FurnitureOrchestrator
from furniture_workflow.workflow_store import JsonProjectStore


class DragTransactionRoundTripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("Node is required to exercise the real gesture module")
        result = subprocess.run([node, str(WORKSPACE / "domain/stages/layout-plan/scripts/furniture_layout/static/interaction_check.mjs"), "--fixtures"],
                                capture_output=True, text=True, check=True, timeout=30)
        cls.fixtures = json.loads(result.stdout)

    def assert_geometry(self, item, expected):
        for key in ("mode", "host_wall", "origin_x_mm", "origin_y_mm", "origin_z_mm", "rotation_z_deg"):
            self.assertEqual(getattr(item.placement, key), expected["placement"][key], key)
        for actual, wanted in zip(item.footprint, expected["footprint"]):
            for value, target in zip(actual, wanted):
                self.assertAlmostEqual(value, target, places=6)

    def test_js_preview_matches_project_admission_and_reload(self):
        for fixture in self.fixtures:
            with self.subTest(operation=fixture["operation"]):
                layout = ProjectLayout.from_source({"rooms": [{**fixture["room"], "items": [fixture["source"]]}]})
                before = layout.to_dict()
                edited = apply_layout_edit(layout, fixture["operation"])
                self.assertEqual(layout.to_dict(), before)
                self.assert_geometry(ProjectLayout.from_dict(edited.to_dict()).rooms[0].items[0], fixture["expected"])
                self.assert_geometry(edited.confirm().rooms[0].items[0], fixture["expected"])

    def test_exact_move_preserves_neighbours_and_rejects_broken_against(self):
        fixture = self.fixtures[0]
        neighbour = {"id": "shelf", "category": "shelf", "width": 400, "depth": 300, "height": 400,
                     "manufacture": False, "placement": {"mode": "free", "origin_x_mm": 1500,
                     "origin_y_mm": 1500, "origin_z_mm": 2000}}
        scene = plan_scene(fixture["room"], [fixture["source"], neighbour])
        result = apply_scene_edit(scene, fixture["operation"])
        self.assertEqual(scene.items[1], result.items[1])
        constrained = plan_scene(fixture["room"], [
            {**fixture["source"], "placement": {"mode": "wall", "host_wall": "north"}},
            {**neighbour, "placement": {"mode": "wall", "host_wall": "north", "against": {
                "west": {"kind": "item", "id": "cab"}}}},
        ])
        before = constrained.to_dict()
        with self.assertRaises(ValueError):
            apply_scene_edit(constrained, fixture["operation"])
        self.assertEqual(constrained.to_dict(), before)

    def test_real_project_and_standalone_endpoints_save_the_js_pose(self):
        with tempfile.TemporaryDirectory(prefix="drag-roundtrip-") as directory, mock.patch.dict(os.environ, {
            "FURNITURE_PREVIEW_BROWSER": "0", server.LAYOUT_EDIT_ENV: "1",
        }), mock.patch.object(server, "STORE_ROOT", Path(directory)), mock.patch.object(server, "OUTPUT_ROOT", Path(directory)):
            store = JsonProjectStore(directory)
            for index, fixture in enumerate(self.fixtures):
                with self.subTest(index=index):
                    layout = ProjectLayout.from_source({"rooms": [{**fixture["room"], "items": [fixture["source"]]}]})
                    project = FurnitureOrchestrator(workspace_root=WORKSPACE, project_store=store).create_project("drag", layout)
                    before = asyncio.run(server.project_layout(project.id))
                    op = fixture["operation"]
                    asyncio.run(server.edit_project_layout_endpoint(project.id,
                        server.ProjectLayoutEditRequest(**op, expected_version=before["version"]), local_request()))
                    self.assert_geometry(store.load(project.id).latest.layout.rooms[0].items[0], fixture["expected"])
                    scene_id = f"drag-{index}"
                    asyncio.run(server.save_room_scene(server.RoomSceneSaveRequest(scene_id=scene_id,
                        room=fixture["room"], items=[fixture["source"]]), local_request()))
                    saved = asyncio.run(server.edit_room_scene(scene_id, server.RoomSceneEditRequest(**op), local_request()))
                    reloaded = asyncio.run(server.load_room_scene(scene_id))
                    self.assertEqual(saved.items, reloaded.items)
                    from furniture_layout.scene import RoomScene
                    self.assert_geometry(RoomScene.from_dict(reloaded.model_dump()).items[0], fixture["expected"])
                    # Subsequent ordinary edits must retain the saved wall start too.
                    asyncio.run(server.edit_room_scene(scene_id, server.RoomSceneEditRequest(**{**op, "origin_z_mm": 100}), local_request()))
                    again = asyncio.run(server.load_room_scene(scene_id))
                    self.assertEqual(again.items[0]["placement"]["origin_x_mm"], op["origin_x_mm"])
                    self.assertEqual(again.items[0]["placement"]["origin_y_mm"], op["origin_y_mm"])

    def test_exact_pose_rejects_partial_invalid_and_colliding_results_atomically(self):
        fixture = self.fixtures[0]
        scene = plan_scene(fixture["room"], [fixture["source"]])
        before = scene.to_dict()
        for changes in ({"rotation_z_deg": 15}, {"origin_y_mm": 20}, {"origin_x_mm": -100}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                apply_scene_edit(scene, {**fixture["operation"], **changes})
        with self.assertRaises(ValueError):
            op = dict(fixture["operation"]);del op["origin_z_mm"]
            apply_scene_edit(scene, op)
        other = replace(scene.items[0], id="other")
        with self.assertRaises(ValueError):
            apply_scene_edit(replace(scene, items=(scene.items[0], other)), fixture["operation"])
        self.assertEqual(scene.to_dict(), before)

    def test_undo_restores_the_saved_wall_position(self):
        fixture = self.fixtures[0]
        with tempfile.TemporaryDirectory(prefix="drag-undo-") as directory, mock.patch.dict(os.environ, {
            "FURNITURE_PREVIEW_BROWSER": "0", server.LAYOUT_EDIT_ENV: "1",
        }), mock.patch.object(server, "STORE_ROOT", Path(directory)):
            store = JsonProjectStore(directory)
            layout = ProjectLayout.from_source({"rooms": [{**fixture["room"], "items": [fixture["source"]]}]})
            project = FurnitureOrchestrator(workspace_root=WORKSPACE, project_store=store).create_project("drag", layout)
            before = asyncio.run(server.project_layout(project.id))
            saved = asyncio.run(server.edit_project_layout_endpoint(project.id, server.ProjectLayoutEditRequest(
                **fixture["operation"], expected_version=before["version"]), local_request()))
            op = {**fixture["operation"], "mode": "free", "origin_y_mm": 120}
            op.pop("host_wall")
            moved = asyncio.run(server.edit_project_layout_endpoint(project.id, server.ProjectLayoutEditRequest(
                **op, expected_version=saved["version"]), local_request()))
            undo_layout_edit(store.load(project.id), expected_version=moved["version"], workspace_root=WORKSPACE, store_root=directory)
            self.assert_geometry(store.load(project.id).latest.layout.rooms[0].items[0], fixture["expected"])

    def test_fill_pose_only_changes_height_and_retains_its_constraint(self):
        fixture = self.fixtures[0]
        source = {**fixture["source"], "placement": {"mode": "wall", "host_wall": "north",
                  "fill": True, "against": {"west": {"kind": "wall"}}}}
        scene = plan_scene(fixture["room"], [source])
        p = scene.items[0].placement
        op = {"op": "set_pose", "item_id": "cab", "mode": p.mode, "host_wall": p.host_wall,
              "origin_x_mm": p.origin_x_mm, "origin_y_mm": p.origin_y_mm,
              "origin_z_mm": 100, "rotation_z_deg": p.rotation_z_deg}
        edited = apply_scene_edit(scene, op)
        self.assertEqual(edited.items[0].width, scene.items[0].width)
        self.assertEqual(edited.items[0].placement.against, p.against)
        self.assertEqual(edited.items[0].placement.origin_z_mm, 100)
        for changes in ({"against": {}}, {"origin_x_mm": 10}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                apply_scene_edit(scene, {**op, **changes})

    def test_invalid_saved_position_checkpoint_is_rejected(self):
        fixture = self.fixtures[0]
        scene = apply_scene_edit(plan_scene(fixture["room"], [fixture["source"]]), fixture["operation"])
        with tempfile.TemporaryDirectory(prefix="drag-checkpoint-") as directory:
            path = save_scene("check", scene, root=directory)
            data = json.loads(path.read_text(encoding="utf-8"))
            data["items"][0]["placement"]["origin_y_mm"] = 10
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_scene("check", root=directory)

    def test_constraints_in_js_preview_match_python_admission(self):
        cases = []
        def add(label, scene, action="move", screen=None, value=None, blocked=True, z=None,
                reason="placement_constraint"):
            cases.append({"label": label, "scene": scene, "action": action,
                          "screen": screen or [0, 120], "value": value,
                          "blocked": blocked, "z": z, "reason": reason})
        room = {"id": "room", "width_mm": 3600, "depth_mm": 3000, "height_mm": 2800}
        for wall, end, normal in (("north", "west", (0, 1)), ("east", "north", (-1, 0)),
                                  ("south", "east", (0, -1)), ("west", "south", (1, 0))):
            anchor = {"id": "cab", "category": "cabinet", "furniture_category": "floor_cabinet",
                      "width": 900, "depth": 400, "height": 1000,
                      "placement": {"mode": "wall", "host_wall": wall}}
            dependent = {"id": "shelf", "category": "shelf", "width": 400, "depth": 300, "height": 1000,
                         "placement": {"mode": "wall", "host_wall": wall,
                                       "against": {end: {"kind": "item", "id": "cab"}}}}
            fill = {"id": "fill", "category": "shelf", "depth": 300, "height": 1000,
                    "placement": {"mode": "wall", "host_wall": wall, "fill": True}}
            screen = [normal[0] * 120 / 2**-.5, normal[1] * 120]
            constrained = plan_scene(room, [anchor, dependent])
            add(wall + " dependent detach", constrained, screen=screen)
            add(wall + " fill detach", plan_scene(room, [anchor, fill]), screen=screen)
            add(wall + " dependent height", constrained, "height", [0, -1200], z=999)
            add(wall + " dependent numeric height", constrained, "numericHeight", value=1200, z=999)
            add(wall + " constrained self detach", plan_scene(room, [
                {**anchor, "placement": {**anchor["placement"], "against": {end: {"kind": "wall"}}}}
            ]), screen=screen, blocked=False)
            # A fill in a disjoint height band cannot lock this cabinet's movement.
            add(wall + " disjoint fill", plan_scene(room, [anchor,
                {**fill, "height": 600, "placement": {**fill["placement"], "origin_z_mm": 1500}}]),
                screen=screen, blocked=False)
        anchor = {"id": "cab", "category": "cabinet", "furniture_category": "floor_cabinet",
                  "width": 900, "depth": 400, "height": 1000,
                  "placement": {"mode": "wall", "host_wall": "north"}}
        dependent = {"id": "shelf", "category": "shelf", "width": 400, "depth": 300, "height": 1000,
                     "placement": {"mode": "wall", "host_wall": "north",
                                   "against": {"west": {"kind": "item", "id": "cab"}}}}
        constrained = plan_scene(room, [anchor, dependent])
        add("dependent rotation", constrained, "rotate", [0, 100])
        add("dependent numeric rotation", constrained, "numericRotation", value=90)
        # Raising a full-wall item past the sill would change its computed width.
        window_room = {**room, "openings": [{"id": "window", "kind": "window", "wall": "north",
            "offset_mm": 1000, "width_mm": 600, "height_mm": 500, "sill_height_mm": 1200}]}
        full = {**anchor, "height": 700, "placement": {**anchor["placement"], "fill": True}}
        add("fill height at window", plan_scene(window_room, [full]), "numericHeight", value=800, z=500,
            reason="blocked_opening")
        low_window_room = {**room, "openings": [{"id": "window", "kind": "window", "wall": "north",
            "offset_mm": 1000, "width_mm": 600, "height_mm": 1000, "sill_height_mm": 0}]}
        add("fill height must retain the selected span", plan_scene(low_window_room, [full]),
            "height", [0, -1200], z=999)
        # Multiple fills are admitted in dependency order, with wall obstacles and openings included.
        corner_room = {**room, "openings": [{"id": "door", "kind": "door", "wall": "north",
            "offset_mm": 1400, "width_mm": 700, "height_mm": 2100}],
            "obstacles": [{"id": "column", "x_mm": 3000, "y_mm": 0, "z_mm": 0,
                           "width_mm": 200, "depth_mm": 200, "height_mm": 2800}]}
        floating = {**anchor, "width": 600, "placement": {"mode": "free", "origin_x_mm": 800,
                     "origin_y_mm": 1200, "rotation_z_deg": 0}}
        left = {**full, "id": "left", "height": 1000, "placement": {"mode": "wall", "host_wall": "north",
                  "fill": True, "against": {"west": {"kind": "wall"}}}}
        right = {**full, "id": "right", "height": 1000}
        add("independent free move beside multiple fills", plan_scene(corner_room, [floating, left, right]),
            blocked=False)
        north_fill = {**full, "id": "north_fill", "height": 1000}
        east_fill = {**full, "id": "east_fill", "height": 1000, "placement": {
            "mode": "wall", "host_wall": "east", "fill": True,
            "against": {"north": {"kind": "item", "id": "north_fill"}}}}
        add("fill dependency order differs from input order", plan_scene(room, [floating, east_fill, north_fill]),
            blocked=False)
        inputs = [{"scene": room_page_payload(case["scene"]), "action": case["action"],
                   "screen": case["screen"], "value": case["value"]} for case in cases]
        result = subprocess.run([shutil.which("node"), str(WORKSPACE /
            "domain/stages/layout-plan/scripts/furniture_layout/static/interaction_check.mjs"), "--scenes"],
            input=json.dumps(inputs), capture_output=True, text=True, check=True, timeout=30)
        for case, preview in zip(cases, json.loads(result.stdout), strict=True):
            with self.subTest(case=case["label"]):
                self.assertEqual(bool(preview["blocker"]), case["blocked"], preview)
                if case["blocked"]:
                    self.assertEqual(preview["blocker"]["reason"], case["reason"])
                if case["z"] is not None:
                    self.assertEqual(preview["placement"]["origin_z_mm"], case["z"])
                edited = apply_scene_edit(case["scene"], preview["operation"])
                self.assertEqual(edited.items[0].placement.to_dict(), preview["placement"])
                with tempfile.TemporaryDirectory(prefix="constraint-roundtrip-") as directory:
                    save_scene("constraints", edited, root=directory)
                    self.assertEqual(load_scene("constraints", root=directory), edited)


if __name__ == "__main__":
    unittest.main()
