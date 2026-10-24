from __future__ import annotations

import json
import shutil
import sys
import unittest
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(SCRIPT_ROOT))

from runtime_paths import bootstrap_runtime_paths

bootstrap_runtime_paths(WORKSPACE_ROOT)

from furniture_layout.scene_planning import plan_scene
from furniture_layout.scene import RoomScene, RoomModel
from furniture_layout.scene_store import (
    list_scene_ids,
    load_scene,
    save_scene,
    scene_exists,
)


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
        "placement": {"mode": "wall", "host_wall": "north"},
    }
]


class RoomSceneStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = WORKSPACE_ROOT / "temp" / "test-room-scene-store"
        if self.root.exists():
            shutil.rmtree(self.root)

    def tearDown(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)

    def test_round_trip_preserves_placed_geometry(self) -> None:
        save_scene("demo", plan_scene(ROOM, ITEMS), root=self.root)
        loaded = load_scene("demo", root=self.root)
        self.assertEqual(loaded, plan_scene(ROOM, ITEMS))
        import json
        payload=json.loads((self.root/'room-scenes/demo.json').read_text(encoding='utf-8'))
        self.assertEqual(set(payload), {'schema_version','scene_id','room','items'})
        self.assertIn('footprint',payload['items'][0])

    def test_missing_scene_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_scene("absent", root=self.root)

    def test_invalid_scene_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            save_scene("../escape", plan_scene(ROOM, ITEMS), root=self.root)

    def test_empty_items_rejected(self) -> None:
        with self.assertRaises(ValueError):
            save_scene("demo", RoomScene(RoomModel.from_dict(ROOM), ()), root=self.root)

    def test_exists_and_list(self) -> None:
        self.assertFalse(scene_exists("demo", root=self.root))
        save_scene("b", plan_scene(ROOM, ITEMS), root=self.root)
        save_scene("a", plan_scene(ROOM, ITEMS), root=self.root)
        self.assertTrue(scene_exists("a", root=self.root))
        self.assertEqual(list_scene_ids(root=self.root), ["a", "b"])

    def test_source_and_dual_formats_are_rejected_without_rewriting(self) -> None:
        path = save_scene("demo", plan_scene(ROOM, ITEMS), root=self.root)
        for data in (
            {"scene_id": "demo", "room": ROOM, "items": ITEMS},
            {"scene_id": "demo", "room": ROOM, "items": ITEMS,
             "placed_items": [item.to_dict() for item in plan_scene(ROOM, ITEMS).items]},
        ):
            with self.subTest(fields=list(data)):
                path.write_text(json.dumps(data), encoding="utf-8")
                before = path.read_bytes()
                with self.assertRaises(ValueError):
                    load_scene("demo", root=self.root)
                self.assertEqual(path.read_bytes(), before)

    def test_wrong_version_missing_pose_and_duplicate_source_are_rejected(self) -> None:
        path = save_scene("demo", plan_scene(ROOM, ITEMS), root=self.root)
        original = json.loads(path.read_text(encoding="utf-8"))
        for version in (None, True, "1", 2):
            with self.subTest(version=version):
                path.write_text(json.dumps({**original, "schema_version": version}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_scene("demo", root=self.root)
        missing = json.loads(json.dumps(original))
        del missing["items"][0]["placement"]["rotation_z_deg"]
        for data in (missing, {**original, "placed_items": original["items"]}):
            with self.subTest(fields=list(data)):
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_scene("demo", root=self.root)


if __name__ == "__main__":
    unittest.main()
