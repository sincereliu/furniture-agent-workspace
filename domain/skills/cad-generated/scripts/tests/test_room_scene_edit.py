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
from furniture_layout.scene_edit import apply_edit


def _source() -> dict:
    return {
        "scene_id": "demo",
        "room": {
            "id": "room",
            "name": "卧室",
            "width_mm": 3000,
            "depth_mm": 4000,
            "height_mm": 2400,
        },
        "items": [
            {
                "id": "wardrobe",
                "label": "衣柜",
                "category": "wardrobe",
                "width": 1800,
                "depth": 600,
                "height": 2200,
                "placement": {
                    "mode": "wall",
                    "host_wall": "north",
                    "offset_mm": 200,
                },
            },
            {
                "id": "desk",
                "label": "书桌",
                "category": "desk",
                "width": 1200,
                "depth": 600,
                "height": 750,
                "placement": {
                    "mode": "free",
                    "origin_x_mm": 100.0,
                    "origin_y_mm": 100.0,
                },
            },
        ],
    }


class SceneEditTests(unittest.TestCase):
    def test_resize_changes_multiple_fields(self) -> None:
        edited = apply_edit(
            _source(),
            {"op": "resize", "item_id": "wardrobe", "width": 900, "depth": 650},
        )
        item = edited["items"][0]
        self.assertEqual(item["width"], 900)
        self.assertEqual(item["depth"], 650)
        self.assertEqual(item["height"], 2200)

    def test_resize_requires_a_field(self) -> None:
        with self.assertRaises(ValueError):
            apply_edit(_source(), {"op": "resize", "item_id": "wardrobe"})

    def test_resize_rejects_foreign_field(self) -> None:
        with self.assertRaises(ValueError):
            apply_edit(
                _source(),
                {"op": "resize", "item_id": "wardrobe", "origin_x_mm": 1},
            )

    def test_move_wall_uses_offset(self) -> None:
        edited = apply_edit(
            _source(), {"op": "move", "item_id": "wardrobe", "offset_mm": 500}
        )
        self.assertEqual(edited["items"][0]["placement"]["offset_mm"], 500)

    def test_move_wall_rejects_free_coordinates(self) -> None:
        with self.assertRaises(ValueError):
            apply_edit(
                _source(),
                {"op": "move", "item_id": "wardrobe", "origin_x_mm": 500},
            )

    def test_move_cannot_mix_modes(self) -> None:
        with self.assertRaises(ValueError):
            apply_edit(
                _source(),
                {
                    "op": "move",
                    "item_id": "wardrobe",
                    "offset_mm": 500,
                    "origin_x_mm": 100,
                },
            )

    def test_move_switch_mode_requires_target_coordinates(self) -> None:
        with self.assertRaises(ValueError):
            apply_edit(_source(), {"op": "move", "item_id": "wardrobe", "mode": "free"})
        edited = apply_edit(
            _source(),
            {
                "op": "move",
                "item_id": "wardrobe",
                "mode": "free",
                "origin_x_mm": 300,
                "origin_y_mm": 400,
            },
        )
        placement = edited["items"][0]["placement"]
        self.assertEqual(placement["mode"], "free")
        self.assertNotIn("host_wall", placement)
        self.assertEqual(placement["origin_x_mm"], 300)

    def test_move_origin_z_only(self) -> None:
        edited = apply_edit(
            _source(), {"op": "move", "item_id": "desk", "origin_z_mm": 100}
        )
        self.assertEqual(edited["items"][1]["placement"]["origin_z_mm"], 100)

    def test_rotate(self) -> None:
        edited = apply_edit(
            _source(),
            {"op": "rotate", "item_id": "desk", "rotation_z_deg": 90},
        )
        self.assertEqual(edited["items"][1]["placement"]["rotation_z_deg"], 90)

    def test_rotate_rejects_foreign_field(self) -> None:
        with self.assertRaises(ValueError):
            apply_edit(
                _source(),
                {"op": "rotate", "item_id": "desk", "width": 900},
            )

    def test_rotate_reanchors_wall_item_to_free(self) -> None:
        edited = apply_edit(
            _source(),
            {
                "op": "rotate",
                "item_id": "wardrobe",
                "rotation_z_deg": 270,
                "mode": "free",
                "origin_x_mm": 800,
                "origin_y_mm": 1200,
            },
        )
        placement = edited["items"][0]["placement"]
        self.assertEqual(placement["mode"], "free")
        self.assertEqual(placement["rotation_z_deg"], 270)
        self.assertEqual(placement["origin_x_mm"], 800)
        self.assertNotIn("host_wall", placement)
        self.assertNotIn("offset_mm", placement)

    def test_rotate_switch_to_free_requires_free_coordinates(self) -> None:
        with self.assertRaises(ValueError):
            apply_edit(
                _source(),
                {
                    "op": "rotate",
                    "item_id": "wardrobe",
                    "rotation_z_deg": 90,
                    "mode": "free",
                },
            )

    def test_rotate_rejects_wall_position_fields(self) -> None:
        # 墙摆的旋转由 host_wall 派生，rotate 不接受墙摆坐标——否则 rotation_z_deg=0
        # 会伪装成一次沿墙移动。
        with self.assertRaises(ValueError):
            apply_edit(
                _source(),
                {
                    "op": "rotate",
                    "item_id": "wardrobe",
                    "rotation_z_deg": 0,
                    "offset_mm": 300,
                },
            )

    def test_rotate_keeps_free_placement_and_reanchors(self) -> None:
        edited = apply_edit(
            _source(),
            {
                "op": "rotate",
                "item_id": "desk",
                "rotation_z_deg": 45,
                "origin_x_mm": 200.0,
                "origin_y_mm": 300.0,
            },
        )
        placement = edited["items"][1]["placement"]
        self.assertEqual(placement["mode"], "free")
        self.assertEqual(placement["rotation_z_deg"], 45)
        self.assertEqual(placement["origin_x_mm"], 200)

    def test_unknown_item_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            apply_edit(
                _source(),
                {"op": "rotate", "item_id": "absent", "rotation_z_deg": 90},
            )

    def test_unsupported_op_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            apply_edit(_source(), {"op": "delete", "item_id": "desk"})

    def test_apply_does_not_mutate_input(self) -> None:
        source = _source()
        apply_edit(source, {"op": "resize", "item_id": "wardrobe", "width": 900})
        self.assertEqual(source["items"][0]["width"], 1800)


class RoomSceneEditApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-room-scene-edit"
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
                ),
                local_request(),
            )
        )

    def test_edit_persists_and_recomputes(self) -> None:
        self._save()
        response = asyncio.run(
            server.edit_room_scene(
                "demo",
                server.RoomSceneEditRequest(
                    op="resize", item_id="wardrobe", width=900
                ),
                local_request(),
            )
        )
        self.assertEqual(response.items[0]["width"], 900)
        reloaded = asyncio.run(server.load_room_scene("demo"))
        self.assertEqual(reloaded.items[0]["width"], 900)

    def test_invalid_edit_does_not_persist(self) -> None:
        self._save()
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                server.edit_room_scene(
                    "demo",
                    server.RoomSceneEditRequest(
                        op="move", item_id="wardrobe", origin_x_mm=100
                    ),
                    local_request(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        reloaded = asyncio.run(server.load_room_scene("demo"))
        self.assertEqual(reloaded.items[0]["placement"]["offset_mm"], 200)
        self.assertEqual(reloaded.items[0]["width"], 1800)

    def test_geometry_conflict_does_not_persist(self) -> None:
        self._save()
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                server.edit_room_scene(
                    "demo",
                    server.RoomSceneEditRequest(
                        op="resize", item_id="wardrobe", width=5000
                    ),
                    local_request(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        reloaded = asyncio.run(server.load_room_scene("demo"))
        self.assertEqual(reloaded.items[0]["width"], 1800)

    def test_edit_missing_scene_returns_404(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                server.edit_room_scene(
                    "absent",
                    server.RoomSceneEditRequest(
                        op="resize", item_id="wardrobe", width=900
                    ),
                    local_request(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_edit_refuses_remote_caller(self) -> None:
        """编辑会落盘：非本机来源 403，且改动一个字都不许进文件。"""
        self._save()
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                server.edit_room_scene(
                    "demo",
                    server.RoomSceneEditRequest(
                        op="resize", item_id="wardrobe", width=900
                    ),
                    remote_request(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 403)
        reloaded = asyncio.run(server.load_room_scene("demo"))
        self.assertEqual(reloaded.items[0]["width"], 1800)

    def test_rotating_a_wall_item_to_free_is_accepted_end_to_end(self) -> None:
        """编辑器拖旋转手柄发出的 op：绕中心转 270°，并收回房间内，改成自由摆放。

        衣柜 1800×600 贴北墙，绕本身中心转 90° 会扫到 y<0；编辑器按最小位移把它推回
        房间（y 0..1800），这个 op 必须能通过下游校验并落盘。
        """
        self._save()
        response = asyncio.run(
            server.edit_room_scene(
                "demo",
                server.RoomSceneEditRequest(
                    op="rotate",
                    item_id="wardrobe",
                    rotation_z_deg=270,
                    mode="free",
                    origin_x_mm=800,
                    origin_y_mm=1800,
                ),
                local_request(),
            )
        )
        placement = response.items[0]["placement"]
        self.assertEqual(placement["mode"], "free")
        self.assertEqual(placement["rotation_z_deg"], 270)
        footprint = [(p["x_mm"], p["y_mm"]) for p in response.items[0]["footprint"]]
        xs = [p[0] for p in footprint]
        ys = [p[1] for p in footprint]
        # 转 90° 后长边贴墙：600 宽 × 1800 深。
        self.assertAlmostEqual(max(xs) - min(xs), 600)
        self.assertAlmostEqual(max(ys) - min(ys), 1800)
        for x, y in footprint:
            self.assertTrue(0 <= x <= 3000 and 0 <= y <= 4000, (x, y))
        reloaded = asyncio.run(server.load_room_scene("demo"))
        self.assertEqual(reloaded.items[0]["placement"]["mode"], "free")

    def test_rotating_a_wall_item_without_free_mode_is_rejected(self) -> None:
        """墙摆的 rotation_z_deg 由 host_wall 派生，直接转会被下游拒绝且不落盘。"""
        self._save()
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(
                server.edit_room_scene(
                    "demo",
                    server.RoomSceneEditRequest(
                        op="rotate", item_id="wardrobe", rotation_z_deg=45
                    ),
                    local_request(),
                )
            )
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("derived", str(ctx.exception.detail))
        reloaded = asyncio.run(server.load_room_scene("demo"))
        self.assertEqual(reloaded.items[0]["placement"]["mode"], "wall")
        self.assertEqual(reloaded.items[0]["placement"]["offset_mm"], 200)


if __name__ == "__main__":
    unittest.main()
