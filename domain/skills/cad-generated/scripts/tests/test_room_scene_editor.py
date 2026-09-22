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
from furniture_layout.editor import render_editor
from furniture_layout.pipeline import plan_room_scene
from furniture_layout.scene import RoomScene


ROOM = {
    "id": "room",
    "name": "卧室",
    "width_mm": 3000,
    "depth_mm": 4000,
    "height_mm": 2400,
}
ITEMS = [
    {
        "id": "wardrobe",
        "label": "衣柜",
        "category": "wardrobe",
        "width": 1800,
        "depth": 600,
        "height": 2200,
        "placement": {"mode": "wall", "host_wall": "north", "offset_mm": 200},
    },
    {
        "id": "desk",
        "label": "书桌",
        "category": "desk",
        "width": 1200,
        "depth": 600,
        "height": 750,
        "placement": {"mode": "free", "origin_x_mm": 500.0, "origin_y_mm": 900.0},
    },
]


def _scene() -> RoomScene:
    planned = plan_room_scene(ROOM, ITEMS)
    return RoomScene.from_dict(
        {"room": planned["room"], "items": planned["items"]}
    )


class RoomSceneEditorTests(unittest.TestCase):
    def test_editor_is_self_contained_html(self) -> None:
        result = render_editor("demo", _scene())
        self.assertEqual(result["media_type"], "text/html")
        html = str(result["html"])
        self.assertIn("<canvas", html)
        self.assertIn("const SCENE_ID=\"demo\"", html)
        self.assertIn('"id":"wardrobe"', html)
        self.assertIn('"mode":"wall"', html)
        self.assertIn('"offset_mm":200', html)

    def test_editor_allows_same_origin_fetch(self) -> None:
        html = str(render_editor("demo", _scene())["html"])
        self.assertIn("connect-src 'self'", html)

    def test_editor_leaves_no_placeholders(self) -> None:
        html = str(render_editor("demo", _scene())["html"])
        self.assertIn("const READ_ONLY=false", html)
        for placeholder in (
            "__SCENE_ID__",
            "__SCENE_JSON__",
            "__HEADING__",
            "__HEADING_SUFFIX__",
            "__READ_ONLY__",
            "__POLL_URL__",
            "__ROOMS_JSON__",
            "__VERSION_JSON__",
            "__BODY_CLASS__",
            "__APP_LABEL__",
            "__TIPS__",
            "__SHUTDOWN_BUTTON__",
        ):
            self.assertNotIn(placeholder, html)
        self.assertNotIn('id="shutdown-preview"', html)

    def test_editor_declares_move_and_rotate_controls(self) -> None:
        result = render_editor("demo", _scene())
        controls = result["controls"]
        self.assertIn("select_item", controls)
        self.assertIn("drag_item", controls)
        self.assertIn("drag_rotate_handle", controls)
        self.assertIn("drag_height_handle", controls)
        self.assertIn("front_orientation", controls)
        self.assertIn("manual_distance_input", controls)
        self.assertIn("manual_rotation_input", controls)
        self.assertIn("view_transition", controls)
        self.assertIn("dimension_readout", controls)
        self.assertIn("view_elevation", controls)
        self.assertIn("placement_stop", controls)
        self.assertIn("旋转", str(result["alt_text"]))
        self.assertIn("接触", str(result["alt_text"]))
        self.assertIn("离地高度", str(result["alt_text"]))

    def test_editor_offers_orthographic_views(self) -> None:
        html = str(render_editor("demo", _scene())["html"])
        for view in ("perspective", "top", "front", "back", "left", "right"):
            self.assertIn(f'data-view="{view}"', html)
        # 立面视图必须落在 pitch 0，编辑器据此切换成竖直平面拖动
        self.assertIn("front:{yaw:Math.PI/2,pitch:0}", html)
        self.assertIn("left:{yaw:Math.PI,pitch:0}", html)


class RoomSceneEditorApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-room-scene-editor"
        if self.root.exists():
            shutil.rmtree(self.root)
        self._patch = mock.patch.object(server, "OUTPUT_ROOT", self.root)
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def _save(self) -> None:
        asyncio.run(
            server.save_room_scene(
                server.RoomSceneSaveRequest(
                    scene_id="demo",
                    room=server.RoomRequest(
                        id="room",
                        name="卧室",
                        width_mm=3000,
                        depth_mm=4000,
                        height_mm=2400,
                    ),
                    items=[
                        server.SceneItemRequest(
                            id="wardrobe",
                            label="衣柜",
                            category="wardrobe",
                            width=1800,
                            depth=600,
                            height=2200,
                            placement=server.ItemPlacementRequest(
                                mode="wall",
                                host_wall="north",
                                offset_mm=200,
                            ),
                        )
                    ],
                )
            )
        )

    def test_editor_endpoint_returns_html(self) -> None:
        self._save()
        response = asyncio.run(server.room_scene_editor("demo"))
        self.assertEqual(response.media_type, "text/html")
        self.assertIn(b"<canvas", response.body)
        self.assertIn(b"const SCENE_ID=\"demo\"", response.body)

    def test_editor_missing_scene_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(server.room_scene_editor("absent"))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_openapi_exposes_editor_endpoint(self) -> None:
        paths = server.app.openapi()["paths"]
        self.assertIn("/api/room-scene/{scene_id}/editor", paths)


if __name__ == "__main__":
    unittest.main()
