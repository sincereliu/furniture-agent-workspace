from __future__ import annotations

import asyncio
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from fastapi import HTTPException

import server
from fake_request_support import local_request, remote_request


def save_request(scene_id: str = "") -> server.RoomSceneSaveRequest:
    return server.RoomSceneSaveRequest(
        scene_id=scene_id,
        room=server.RoomRequest(
            id="bedroom",
            name="卧室",
            width_mm=4200,
            depth_mm=3600,
            height_mm=2800,
        ),
        items=[
            server.SceneItemRequest(
                id="bed",
                label="床",
                category="bed",
                width=1800,
                depth=2000,
                height=450,
                placement=server.ItemPlacementRequest(
                    mode="wall",
                    host_wall="north",
                    offset_mm=1200,
                ),
            )
        ],
    )


class RoomSceneApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-room-scene-api"
        if self.root.exists():
            shutil.rmtree(self.root)
        self._patch = mock.patch.object(server, "OUTPUT_ROOT", self.root)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def test_openapi_exposes_scene_state_endpoints(self) -> None:
        paths = server.app.openapi()["paths"]
        self.assertIn("/api/room-scene/save", paths)
        self.assertIn("/api/room-scene/{scene_id}", paths)
        self.assertIn("/api/room-scenes", paths)

    def test_save_then_load_round_trip(self) -> None:
        saved = asyncio.run(server.save_room_scene(save_request("demo"), local_request()))
        self.assertEqual(saved["scene_id"], "demo")
        loaded = asyncio.run(server.load_room_scene("demo"))
        self.assertEqual(loaded.room["name"], "卧室")
        self.assertEqual(loaded.items[0]["id"], "bed")
        self.assertIsNotNone(loaded.preview)
        self.assertIsNotNone(loaded.viewer)

    def test_save_generates_id_when_absent(self) -> None:
        saved = asyncio.run(server.save_room_scene(save_request(""), local_request()))
        self.assertTrue(saved["scene_id"].startswith("scene-"))

    def test_load_missing_scene_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(server.load_room_scene("absent"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_list_room_scenes(self) -> None:
        asyncio.run(server.save_room_scene(save_request("b"), local_request()))
        asyncio.run(server.save_room_scene(save_request("a"), local_request()))
        result = asyncio.run(server.list_room_scenes())
        self.assertEqual(result["scene_ids"], ["a", "b"])

    def test_save_refuses_remote_caller(self) -> None:
        """落盘是写操作：非本机来源一律 403，且一个文件都不该留下。"""
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(server.save_room_scene(save_request("demo"), remote_request()))
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertFalse((self.root / "room-scenes").exists())

    def test_room_cad_api_rejects_unsafe_artifact_id(self) -> None:
        saved = save_request()
        request = server.RoomSceneRequest(
            room=saved.room,
            items=saved.items,
            artifact_id="../../escape",
        )
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(server.plan_room_cad(request, local_request()))
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("artifact_id", str(ctx.exception.detail))
        self.assertFalse(self.root.exists())

    def test_room_cad_api_keeps_normal_artifact_id(self) -> None:
        saved = save_request()
        request = server.RoomSceneRequest(
            room=saved.room,
            items=saved.items,
            artifact_id="bedroom-v1",
        )

        def fake_generate(output, **kwargs):
            self.assertEqual(kwargs["artifact_id"], "bedroom-v1")
            return {
                **output,
                "cad": {
                    "status": "ok",
                    "source_path": "source.py",
                    "step_path": "room.step",
                },
            }

        with mock.patch.object(server, "generate_room_cad", side_effect=fake_generate):
            response = asyncio.run(server.plan_room_cad(request, local_request()))
        self.assertEqual(response.cad["status"], "ok")

    def test_room_cad_refuses_remote_caller_before_generating(self) -> None:
        """出 CAD 会写文件：非本机来源连生成都不该触发。"""
        saved = save_request()
        request = server.RoomSceneRequest(room=saved.room, items=saved.items)
        with mock.patch.object(server, "generate_room_cad") as generator:
            with self.assertRaises(HTTPException) as ctx:
                asyncio.run(server.plan_room_cad(request, remote_request()))
        self.assertEqual(ctx.exception.status_code, 403)
        generator.assert_not_called()


if __name__ == "__main__":
    unittest.main()
